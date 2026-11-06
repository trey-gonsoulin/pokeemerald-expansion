"""Tests for patchelf's symbol checks (#261).

Builds the tool with its own Makefile, then runs it on a crafted ELF32 file, as
`make check` does on the test ELF (gTestRunnerArgv, gTestRunnerHeadless and
gTestRunnerSkipIsFail).

Run from the repo root: python3 -m unittest discover -s tools/patchelf
"""

import pathlib
import struct
import subprocess
import tempfile
import unittest

TOOL_DIR = pathlib.Path(__file__).resolve().parent
TOOL = TOOL_DIR / "patchelf"

SHT_PROGBITS, SHT_SYMTAB, SHT_STRTAB, SHT_NOBITS = 1, 2, 3, 8
SHN_ABS = 0xFFF1
DATA_ADDR = 0x08000000
DATA = b"ABCDEFGH"


def setUpModule():
    subprocess.run(["make", "-C", str(TOOL_DIR)], check=True, capture_output=True)


def strtab(names):
    table = b"\0"
    offsets = {}
    for name in names:
        offsets[name] = len(table)
        table += name.encode() + b"\0"
    return table, offsets


def build_elf():
    """An ELF with .data (8 bytes), .bss, a section past the end of the file and these symbols:
    gData (.data 0-3), gData2 (.data 4-7), gBss (.bss), gAbs (SHN_ABS), gBadIndex (section 7, the section count),
    gPastSection (.data 8-11) and gFar (in the section past the file)."""
    section_names = [".data", ".bss", ".far", ".symtab", ".strtab", ".shstrtab"]
    shstrtab, sh_offsets = strtab(section_names)
    symbols = [
        ("gData", DATA_ADDR, 4, 1),
        ("gData2", DATA_ADDR + 4, 4, 1),
        ("gBss", 0x03000000, 4, 2),
        ("gAbs", 0, 4, SHN_ABS),
        ("gBadIndex", 0, 4, 7),
        ("gPastSection", DATA_ADDR + 8, 4, 1),
        ("gFar", 0x09000000, 4, 3),
    ]
    sym_strtab, sym_offsets = strtab(name for name, *_ in symbols)
    symtab = b"\0" * 16
    for name, value, size, shndx in symbols:
        symtab += struct.pack("<IIIBBH", sym_offsets[name], value, size, 0x11, 0, shndx)

    body = DATA + symtab + sym_strtab + shstrtab
    data_off = 52
    symtab_off = data_off + len(DATA)
    sym_strtab_off = symtab_off + len(symtab)
    shstrtab_off = sym_strtab_off + len(sym_strtab)
    shoff = data_off + len(body)

    def shdr(name, sh_type, addr, offset, size, entsize=0):
        name_off = sh_offsets[name] if name else 0
        return struct.pack("<10I", name_off, sh_type, 0, addr, offset, size, 0, 0, 4, entsize)

    shdrs = (
        shdr(None, 0, 0, 0, 0)
        + shdr(".data", SHT_PROGBITS, DATA_ADDR, data_off, len(DATA))
        + shdr(".bss", SHT_NOBITS, 0x03000000, data_off, 16)
        + shdr(".far", SHT_PROGBITS, 0x09000000, 0x100000, 16)
        + shdr(".symtab", SHT_SYMTAB, 0, symtab_off, len(symtab), 16)
        + shdr(".strtab", SHT_STRTAB, 0, sym_strtab_off, len(sym_strtab))
        + shdr(".shstrtab", SHT_STRTAB, 0, shstrtab_off, len(shstrtab))
    )
    ident = b"\x7fELF\x01\x01\x01" + b"\0" * 9
    ehdr = ident + struct.pack("<HHIIIIIHHHHHH", 2, 40, 1, 0, 0, shoff, 0, 52, 0, 0, 40, 7, 6)
    return ehdr + body + shdrs


class PatchelfTestCase(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = pathlib.Path(directory.name) / "test.elf"
        self.original = build_elf()
        self.path.write_bytes(self.original)

    def run_tool(self, *args):
        return subprocess.run([str(TOOL), str(self.path), *args], capture_output=True)

    def data(self):
        return self.path.read_bytes()[52:52 + len(DATA)]

    def assertRejected(self, args, message):
        result = self.run_tool(*args)
        stderr = result.stderr.decode()
        self.assertEqual(result.returncode, 1, stderr)
        self.assertIn(message, stderr)
        self.assertEqual(self.path.read_bytes(), self.original, "the file changed")


class Valid(PatchelfTestCase):
    def test_patches_a_data_symbol(self):
        result = self.run_tool("gData", "x\\0", "gData2", "\\x01")
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(self.data(), b"x\0CD\x01FGH")

    def test_no_symbols_is_a_no_op(self):
        result = self.run_tool()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(self.path.read_bytes(), self.original)


class Rejected(PatchelfTestCase):
    def test_missing_symbol(self):
        self.assertRejected(["gNoSuchSymbol", "abc"], "gNoSuchSymbol: symbol not found")

    def test_missing_symbol_after_a_good_one_writes_nothing(self):
        self.assertRejected(["gData", "x", "gNoSuchSymbol", "abc"], "gNoSuchSymbol: symbol not found")

    def test_bad_value_after_a_good_one_writes_nothing(self):
        self.assertRejected(["gData", "x", "gData2", "\\q"], "gData2: illegal escape \\q")

    def test_nobits_symbol(self):
        self.assertRejected(["gBss", "x"], "gBss: symbol's section has no data in the file")

    def test_absolute_symbol(self):
        self.assertRejected(["gAbs", "x"], "gAbs: symbol has no section")

    def test_section_index_equal_to_the_count(self):
        self.assertRejected(["gBadIndex", "x"], "gBadIndex: symbol has no section (index 7)")

    def test_symbol_past_its_section(self):
        self.assertRejected(["gPastSection", "x"], "gPastSection: symbol lies outside its section")

    def test_section_past_the_file(self):
        self.assertRejected(["gFar", "x"], "gFar: symbol's section lies outside the file")

    def test_value_too_long(self):
        self.assertRejected(["gData", "abcde"], "gData: overflows size (4)")


if __name__ == "__main__":
    unittest.main()
