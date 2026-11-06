"""Tests for compresSmol's and compresSmolTilemap's input checks (#259).

Each test writes a crafted input to a temporary directory, runs the built tool on it
as the Makefile does, and checks its exit code, message and output. Run from the repo
root after `make -C tools/compresSmol`:

    python3 -m unittest discover -s tools/compresSmol
"""

import os
import random
import struct
import subprocess
import tempfile
import unittest

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
SMOL = os.path.join(TOOL_DIR, "compresSmol")
SMOL_TILEMAP = os.path.join(TOOL_DIR, "compresSmolTilemap")

# The modes in a smol header's low 4 bits (include/decompress.h)
BASE_ONLY = 1
ENCODE_BOTH_DELTA_SYMS = 6


def tile_data(size, seed):
    """Bytes that compress like a 4bpp image: a few repeated tiles with some noise."""
    rng = random.Random(seed)
    tiles = [bytes(rng.choice((0x00, 0x11, 0x12, 0x21, 0x22, 0x33)) for _ in range(32)) for _ in range(4)]
    out = bytearray()
    while len(out) < size:
        tile = bytearray(rng.choice(tiles))
        tile[rng.randrange(32)] = rng.randrange(256)
        out += tile
    return bytes(out[:size])


def header(data):
    """The fields of a smol header (struct SmolHeader, include/decompress.h)."""
    word0, word1 = struct.unpack_from("<II", data)
    return {
        "mode": word0 & 0xF,
        "imageSize": (word0 >> 4) & 0x3FFF,
        "symSize": (word0 >> 18) & 0x3FFF,
        "loSize": (word1 >> 19) & 0x1FFF,
    }


def base_only(image_bytes, syms, lo):
    """A hand-made BASE_ONLY smol: the header, then the raw symbols and LO bytes."""
    word0 = BASE_ONLY | (image_bytes // 4) << 4 | len(syms) << 18
    word1 = len(lo) << 19
    raw = struct.pack(f"<{len(syms)}H", *syms) + bytes(lo)
    raw += bytes(-len(raw) % 4)
    return struct.pack("<II", word0, word1) + raw


class ToolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for tool in (SMOL, SMOL_TILEMAP):
            if not os.path.exists(tool):
                raise unittest.SkipTest(f"{tool} isn't built: run make -C tools/compresSmol")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, name):
        return os.path.join(self.dir, name)

    def write(self, name, data):
        with open(self.path(name), "wb") as f:
            f.write(data)
        return self.path(name)

    def read(self, name):
        with open(self.path(name), "rb") as f:
            return f.read()

    def run_tool(self, *args, tool=SMOL):
        return subprocess.run([tool, *args], capture_output=True, text=True)

    def assertFails(self, result, message):
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(message, result.stderr)

    def compress(self, data, *settings):
        src = self.write("in.4bpp", data)
        result = self.run_tool("-w", src, self.path("in.4bpp.smol"), *settings)
        self.assertEqual(result.returncode, 0, result.stderr)
        return self.read("in.4bpp.smol")

    def decode(self, smol):
        src = self.write("check.smol", smol)
        return self.run_tool("-d", src, self.path("check.4bpp"))


class ImageSizeTest(ToolTest):
    def test_an_empty_image_fails(self):
        result = self.run_tool("-w", self.write("in.4bpp", b""), self.path("out.smol"))
        self.assertFails(result, "is empty")
        self.assertFalse(os.path.exists(self.path("out.smol")))

    def test_a_size_that_isnt_a_multiple_of_4_fails(self):
        # 1 and 33 bytes crashed (an odd size overflowed the copy), and 34 was recorded as 32
        for size in (1, 2, 33, 34):
            with self.subTest(size=size):
                result = self.run_tool("-w", self.write("in.4bpp", tile_data(size, 1)), self.path("out.smol"))
                self.assertFails(result, f"is {size} bytes, not a multiple of 4")

    def test_an_image_past_the_header_limit_fails(self):
        # imageSize is 14 bits of 4-byte units: 65,532 bytes at most
        result = self.run_tool("-w", self.write("in.4bpp", tile_data(65536, 1)), self.path("out.smol"))
        self.assertFails(result, "is 65536 bytes, past the header's limit of 65532")

    def test_the_largest_image_round_trips(self):
        data = tile_data(65532, 2)
        smol = self.compress(data)
        self.assertEqual(header(smol)["imageSize"] * 4, 65532)
        self.assertEqual(self.decode(smol).returncode, 0)
        self.assertEqual(self.read("check.4bpp"), data)

    def test_an_image_whose_size_in_words_is_odd_uses_the_encoded_modes(self):
        # The mode was read with a 5-bit mask, so imageSize's low bit made every encoded
        # mode fail its own check and left the image uncompressed (BASE_ONLY)
        sizes = {}
        for size in (4096, 4100):
            smol = self.compress(tile_data(size, 3))
            fields = header(smol)
            self.assertEqual(fields["imageSize"] * 4, size)
            self.assertNotEqual(fields["mode"], BASE_ONLY, size)
            self.assertEqual(self.decode(smol).returncode, 0)
            self.assertEqual(self.read("check.4bpp"), tile_data(size, 3))
            sizes[size] = len(smol)
        self.assertLess(sizes[4100], sizes[4096] + 64)


class DecodeTest(ToolTest):
    def test_base_only_round_trips_with_an_odd_symbol_count(self):
        # The raw LO bytes then start halfway into a word, which read with a shift of 32 or more
        odd = 0
        for seed in range(8):
            data = tile_data(256, seed)
            smol = self.compress(data, "false", "false", "false")
            fields = header(smol)
            self.assertEqual(fields["mode"], BASE_ONLY)
            odd += fields["symSize"] % 2
            self.assertEqual(self.decode(smol).returncode, 0)
            self.assertEqual(self.read("check.4bpp"), data)
        self.assertGreater(odd, 0, "no input gave an odd symbol count")

    def test_a_length_that_isnt_whole_words_fails(self):
        smol = self.compress(tile_data(256, 1))
        self.assertFails(self.decode(smol + b"\x00"), "not a whole number of 4-byte words")

    def test_a_file_shorter_than_the_header_fails(self):
        self.assertFails(self.decode(b"\x01\x00\x00\x00"), "shorter than the 2-word header")

    def test_a_file_shorter_than_its_header_says_fails(self):
        smol = self.compress(tile_data(256, 1))
        self.assertFails(self.decode(smol[:-4]), "the header needs")

    def test_a_mode_that_isnt_an_image_mode_fails(self):
        smol = self.compress(tile_data(256, 1))
        for mode in (0, 7, 8, 15):
            with self.subTest(mode=mode):
                broken = bytes([(smol[0] & 0xF0) | mode]) + smol[1:]
                self.assertFails(self.decode(broken), f"mode {mode} isn't a smol image mode")

    def test_frequencies_that_dont_fill_the_table_fail(self):
        smol = self.compress(tile_data(1024, 1))
        mode = header(smol)["mode"]
        self.assertGreater(mode, BASE_ONLY)
        self.assertLessEqual(mode, ENCODE_BOTH_DELTA_SYMS)
        # The first frequency word: each of its five 6-bit fields at 63 overruns the 64-entry table
        broken = smol[:8] + struct.pack("<I", 0x3FFFFFFF) + smol[12:]
        self.assertFails(self.decode(broken), "frequencies add up to")

    def test_a_bitstream_shorter_than_its_data_needs_fails(self):
        smol = self.compress(tile_data(1024, 1))
        word1 = struct.unpack_from("<I", smol, 4)[0]
        self.assertGreater((word1 >> 6) & 0x1FFF, 1)
        broken = smol[:4] + struct.pack("<I", (word1 & ~(0x1FFF << 6)) | 1 << 6) + smol[8:]
        self.assertFails(self.decode(broken), "runs past the 1-word bitstream")

    def test_a_hand_made_base_only_file_decodes(self):
        # Two literal symbols: a length of 0 and a count of 2
        self.assertEqual(self.decode(base_only(4, [0x1234, 0x5678], [0x00, 0x02])).returncode, 0)
        self.assertEqual(self.read("check.4bpp"), struct.pack("<2H", 0x1234, 0x5678))

    def test_lo_instructions_that_read_past_their_data_fail(self):
        for name, syms, lo in (
            ("a copy with no symbol left", [], [0x01, 0x01]),
            ("more literals than symbols", [0x1234, 0x5678], [0x00, 0x05]),
            ("a copy from before the image", [0x1234], [0x02, 0x05]),
            ("a copy from offset 0", [0x1234], [0x02, 0x00]),
            ("an offset cut off by the end of the data", [0x1234], [0x01]),
        ):
            with self.subTest(name):
                self.assertFails(self.decode(base_only(4, syms, lo)), "the LO instructions read past the data")

    def test_a_header_whose_image_size_disagrees_with_its_data_fails(self):
        # The GBA decoder writes imageSize bytes, so the data has to decode to exactly that
        self.assertFails(self.decode(base_only(8, [0x1234, 0x5678], [0x00, 0x02])),
                         "the data decodes to 4 bytes, but the header gives 8")


class ArgumentTest(ToolTest):
    def test_wrong_arguments_print_the_usage_and_fail(self):
        src = self.write("in.4bpp", tile_data(256, 1))
        out = self.path("out.smol")
        for args in ((), ("-W", src, out), ("-w", src), ("-d", src), ("-w", src, out, "true"),
                     ("-w", src, out, "true", "false"), ("-w", src, out, "false", "false", "false", "false")):
            with self.subTest(args=args):
                self.assertFails(self.run_tool(*args), "Usage:")
        self.assertFalse(os.path.exists(out))

    def test_a_setting_that_isnt_true_or_false_fails(self):
        src = self.write("in.4bpp", tile_data(256, 1))
        result = self.run_tool("-w", src, self.path("out.smol"), "false", "maybe", "false")
        self.assertFails(result, 'Unrecognized setting "maybe"')
        self.assertFalse(os.path.exists(self.path("out.smol")))

    def test_three_settings_are_read(self):
        # The Makefile's .fastSmol rule
        smol = self.compress(tile_data(1024, 1), "false", "false", "false")
        self.assertEqual(header(smol)["mode"], BASE_ONLY)


class TilemapTest(ToolTest):
    def test_an_odd_length_tilemap_fails(self):
        result = self.run_tool(self.write("map.bin", bytes(33)), self.path("map.smolTM"), tool=SMOL_TILEMAP)
        self.assertFails(result, "is 33 bytes, not a whole number of 2-byte tilemap entries")
        self.assertFalse(os.path.exists(self.path("map.smolTM")))

    def test_an_empty_tilemap_fails(self):
        result = self.run_tool(self.write("map.bin", b""), self.path("map.smolTM"), tool=SMOL_TILEMAP)
        self.assertFails(result, "is empty")

    def test_an_even_length_tilemap_compresses(self):
        result = self.run_tool(self.write("map.bin", tile_data(2048, 1)), self.path("map.smolTM"), tool=SMOL_TILEMAP)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
