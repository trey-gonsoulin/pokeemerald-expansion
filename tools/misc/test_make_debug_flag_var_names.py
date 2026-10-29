"""Tests for make_debug_flag_var_names.py. Run from the repo root:
python3 -m unittest discover -s tools/misc
"""

import os
import re
import tempfile
import unittest

import make_debug_flag_var_names as gen

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
FLAGS_H = os.path.join(REPO, "include", "constants", "flags.h")
FLAGS_FRLG_H = os.path.join(REPO, "include", "constants", "flags_frlg.h")
VARS_H = os.path.join(REPO, "include", "constants", "vars.h")


def primary_names(names, values):
    """What the compiler keeps for each value: the last initializer in emit order."""
    kept = {}
    for name in gen.emit_order(names):
        kept[values[name]] = name
    return kept


class ReadNamesTest(unittest.TestCase):
    def read(self, text, prefix="FLAG_"):
        with tempfile.NamedTemporaryFile("w", suffix=".h", delete=False) as f:
            f.write(text)
        self.addCleanup(os.remove, f.name)
        return gen.read_names([f.name], prefix)

    def test_reads_defines_in_order_once(self):
        text = (
            "#define FLAG_B 2\n"
            "  #  define FLAG_A (FLAG_B + 1)\n"
            "#if IS_FRLG\n#define FLAG_B 7\n#endif\n"
            "#define FLAGS_COUNT 10\n"
            "#define VAR_X 0x4000\n"
            "#define FLAG_MACRO(x) (x)\n"
            "// #define FLAG_COMMENTED 1\n"
            "#define FLAG_EMPTY\n"
            "#define FLAG_COMMENT_ONLY // no value\n"
        )
        self.assertEqual(self.read(text), ["FLAG_B", "FLAG_A"])
        self.assertEqual(self.read(text, "VAR_"), ["VAR_X"])


class PrimaryNameTest(unittest.TestCase):
    def test_first_defined_name_wins(self):
        names = ["FLAG_FIRST", "FLAG_ALIAS"]
        self.assertEqual(primary_names(names, {"FLAG_FIRST": 1, "FLAG_ALIAS": 1}), {1: "FLAG_FIRST"})

    def test_real_names_beat_placeholders_and_markers(self):
        names = ["FLAG_HIDDEN_ITEMS_START", "FLAG_UNUSED_0x1F4", "FLAG_HIDDEN_ITEM_ICE_HEAL", "FLAG_LATER"]
        values = {"FLAG_HIDDEN_ITEMS_START": 5, "FLAG_UNUSED_0x1F4": 5, "FLAG_HIDDEN_ITEM_ICE_HEAL": 5, "FLAG_LATER": 5}
        self.assertEqual(primary_names(names, values), {5: "FLAG_HIDDEN_ITEM_ICE_HEAL"})

    def test_marker_shows_when_nothing_else_names_its_value(self):
        names = ["FLAG_SYS_TV_START", "FLAG_UNUSED_1"]
        self.assertEqual(primary_names(names, {"FLAG_SYS_TV_START": 3, "FLAG_UNUSED_1": 4}),
                         {3: "FLAG_SYS_TV_START", 4: "FLAG_UNUSED_1"})

    def test_first_placeholder_wins_among_placeholders(self):
        names = ["FLAG_UNUSED_A", "FLAG_UNUSED_B"]
        self.assertEqual(primary_names(names, {"FLAG_UNUSED_A": 1, "FLAG_UNUSED_B": 1}), {1: "FLAG_UNUSED_A"})


class GenerateTest(unittest.TestCase):
    def test_entries_are_guarded_and_prefix_stripped(self):
        text = gen.generate(["FLAG_BADGE01_GET"], ["VAR_TEMP_0"])
        self.assertIn('#ifdef FLAG_BADGE01_GET\n    [DEBUG_FLAG_NAME_INDEX(FLAG_BADGE01_GET)] = COMPOUND_STRING("BADGE01_GET"),\n#endif', text)
        self.assertIn('[DEBUG_VAR_NAME_INDEX(VAR_TEMP_0)] = COMPOUND_STRING("TEMP_0")', text)
        self.assertIn("static const u8 *const sDebugFlagNames[FLAGS_COUNT + 1] =", text)
        self.assertIn("static const u8 *const sDebugVarNames[VARS_END - VARS_START + 2] =", text)
        self.assertLess(text.index("diagnostic push"), text.index("sDebugFlagNames"))
        self.assertGreater(text.index("diagnostic pop"), text.index("sDebugVarNames"))

    def test_real_headers(self):
        flags = gen.read_names([FLAGS_H, FLAGS_FRLG_H], "FLAG_")
        variables = gen.read_names([VARS_H], "VAR_")
        text = gen.generate(flags, variables)
        # Every flag and var once, and nothing from vars_frlg.h
        self.assertEqual(len(re.findall(r"^#ifdef FLAG_", text, re.M)), len(flags))
        self.assertEqual(len(re.findall(r"^#ifdef VAR_", text, re.M)), len(variables))
        self.assertGreater(len(flags), 2000)
        self.assertGreater(len(variables), 200)
        for name in ("FLAG_BADGE05_GET", "FLAG_SYS_TV_START", "FLAG_UNUSED_0x264", "VAR_TEMP_1", "VAR_RESULT"):
            self.assertIn(f"#ifdef {name}\n", text)
        self.assertFalse(any(name.endswith("_FRLG") for name in variables))
        # VAR_TEMP_1's aliases come after it, so VAR_TEMP_1 is emitted after them and wins
        self.assertGreater(text.index("#ifdef VAR_TEMP_1\n"), text.index("#ifdef VAR_TEMP_TRANSFERRED_SPECIES\n"))


if __name__ == "__main__":
    unittest.main()
