"""Tests for make_debug_flag_var_names.py. Run from the repo root:
python3 -m unittest discover -s tools/misc
"""

import glob
import os
import re
import subprocess
import sys
import tempfile
import unittest

import make_debug_flag_var_names as gen

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
FLAGS_H = os.path.join(REPO, "include", "constants", "flags.h")
FLAGS_FRLG_H = os.path.join(REPO, "include", "constants", "flags_frlg.h")
VARS_H = os.path.join(REPO, "include", "constants", "vars.h")
VARS_FRLG_H = os.path.join(REPO, "include", "constants", "vars_frlg.h")
CONFIGS = sorted(glob.glob(os.path.join(REPO, "include", "config", "*.h")))


def primary_names(names, values, aliases=()):
    """What the compiler keeps for each value: the last initializer in emit order."""
    kept = {}
    for macro, shown, _ in gen.emit_order(names, "FLAG_", aliases):
        kept[values[macro]] = shown
    return kept


def write_temp(test, text):
    with tempfile.NamedTemporaryFile("w", suffix=".h", delete=False) as f:
        f.write(text)
    test.addCleanup(os.remove, f.name)
    return f.name


class ReadNamesTest(unittest.TestCase):
    def test_reads_defines_in_order_once(self):
        path = write_temp(self, (
            "#define FLAG_B 2\n"
            "  #  define FLAG_A (FLAG_B + 1)\n"
            "#if IS_FRLG\n#define FLAG_B 7\n#endif\n"
            "#define FLAGS_COUNT 10\n"
            "#define VAR_X 0x4000\n"
            "#define FLAG_MACRO(x) (x)\n"
            "// #define FLAG_COMMENTED 1\n"
            "#define FLAG_EMPTY\n"
            "#define FLAG_COMMENT_ONLY // no value\n"
        ))
        self.assertEqual(gen.read_names([path], "FLAG_"), ["FLAG_B", "FLAG_A"])
        self.assertEqual(gen.read_names([path], "VAR_"), ["VAR_X"])

    def test_reads_config_aliases(self):
        path = write_temp(self, (
            "#define I_EXP_SHARE_FLAG        FLAG_UNUSED_0x264           // If this flag is set\n"
            "#define B_FLAG_SKY_BATTLE       0     // a flag number, not a constant\n"
            "#define B_VAR_DIFFICULTY        (VAR_UNUSED_0x404E)\n"
            "#define FLAG_ALIAS              FLAG_OTHER\n"
            "#define B_SOMETHING             FLAG_A + 1\n"
        ))
        self.assertEqual(gen.read_aliases([path], "FLAG_"), [("I_EXP_SHARE_FLAG", "FLAG_UNUSED_0x264")])
        self.assertEqual(gen.read_aliases([path], "VAR_"), [("B_VAR_DIFFICULTY", "VAR_UNUSED_0x404E")])


class PrimaryNameTest(unittest.TestCase):
    def test_first_defined_name_wins(self):
        names = ["FLAG_FIRST", "FLAG_ALIAS"]
        self.assertEqual(primary_names(names, {"FLAG_FIRST": 1, "FLAG_ALIAS": 1}), {1: "FIRST"})

    def test_real_names_beat_placeholders_and_markers(self):
        names = ["FLAG_HIDDEN_ITEMS_START", "FLAG_UNUSED_0x1F4", "FLAG_HIDDEN_ITEM_ICE_HEAL", "FLAG_LATER"]
        values = {"FLAG_HIDDEN_ITEMS_START": 5, "FLAG_UNUSED_0x1F4": 5, "FLAG_HIDDEN_ITEM_ICE_HEAL": 5, "FLAG_LATER": 5}
        self.assertEqual(primary_names(names, values), {5: "HIDDEN_ITEM_ICE_HEAL"})

    def test_marker_shows_when_nothing_else_names_its_value(self):
        names = ["FLAG_SYS_TV_START", "FLAG_UNUSED_1"]
        self.assertEqual(primary_names(names, {"FLAG_SYS_TV_START": 3, "FLAG_UNUSED_1": 4}),
                         {3: "SYS_TV_START", 4: "UNUSED_1"})

    def test_first_placeholder_wins_among_placeholders(self):
        names = ["FLAG_UNUSED_A", "FLAG_UNUSED_B"]
        self.assertEqual(primary_names(names, {"FLAG_UNUSED_A": 1, "FLAG_UNUSED_B": 1}), {1: "UNUSED_A"})

    def test_config_aliases_beat_placeholders_but_not_real_names(self):
        names = ["FLAG_UNUSED_0x264", "FLAG_BADGE01_GET"]
        aliases = [("I_EXP_SHARE_FLAG", "FLAG_UNUSED_0x264"), ("B_FLAG_BADGE_BOOST_ATTACK", "FLAG_BADGE01_GET")]
        values = {"FLAG_UNUSED_0x264": 1, "FLAG_BADGE01_GET": 2, "I_EXP_SHARE_FLAG": 1, "B_FLAG_BADGE_BOOST_ATTACK": 2}
        self.assertEqual(primary_names(names, values, aliases), {1: "I_EXP_SHARE_FLAG", 2: "BADGE01_GET"})


class GenerateTest(unittest.TestCase):
    def test_entries_are_guarded_and_prefix_stripped(self):
        text = gen.generate(["FLAG_BADGE01_GET"], ["VAR_TEMP_0"], [("I_EXP_SHARE_FLAG", "FLAG_UNUSED_0x264")])
        self.assertIn('#if defined(FLAG_BADGE01_GET)\n    [DEBUG_FLAG_NAME_INDEX(FLAG_BADGE01_GET)] = COMPOUND_STRING("BADGE01_GET"),\n#endif', text)
        # An alias needs its target too: FLAG_UNUSED_0x264 isn't defined in FRLG
        self.assertIn('#if defined(I_EXP_SHARE_FLAG) && defined(FLAG_UNUSED_0x264)\n    [DEBUG_FLAG_NAME_INDEX(I_EXP_SHARE_FLAG)] = COMPOUND_STRING("I_EXP_SHARE_FLAG"),', text)
        self.assertIn('[DEBUG_VAR_NAME_INDEX(VAR_TEMP_0)] = COMPOUND_STRING("TEMP_0")', text)
        self.assertIn("static const u8 *const sDebugFlagNames[FLAGS_COUNT + 1] =", text)
        self.assertIn("static const u8 *const sDebugVarNames[VARS_END - VARS_START + 2] =", text)
        self.assertLess(text.index("diagnostic push"), text.index("sDebugFlagNames"))
        self.assertGreater(text.index("diagnostic pop"), text.index("sDebugVarNames"))
        self.assertNotIn("IS_FRLG", text)

    def test_frlg_vars_go_last_under_is_frlg(self):
        text = gen.generate([], ["VAR_REPEL_STEP_COUNT"], frlg_var_names=["VAR_HAPPINESS_STEP_COUNTER"])
        frlg = text.index("#if IS_FRLG\n")
        self.assertLess(text.index("defined(VAR_REPEL_STEP_COUNT)"), frlg)
        self.assertLess(frlg, text.index("defined(VAR_HAPPINESS_STEP_COUNTER)"))
        self.assertLess(text.index("defined(VAR_HAPPINESS_STEP_COUNTER)"), text.index("#endif // IS_FRLG"))

    def test_real_headers(self):
        flags = gen.read_names([FLAGS_H, FLAGS_FRLG_H], "FLAG_")
        variables = gen.read_names([VARS_H], "VAR_")
        frlg_variables = gen.read_names([VARS_FRLG_H], "VAR_")
        aliases = gen.read_aliases(CONFIGS, "FLAG_")
        text = gen.generate(flags, variables, aliases, gen.read_aliases(CONFIGS, "VAR_"), frlg_variables)
        # Every flag, var and alias once
        self.assertEqual(len(re.findall(r"^#if defined\(FLAG_", text, re.M)), len(flags))
        self.assertEqual(len(re.findall(r"^#if defined\(VAR_", text, re.M)), len(variables) + len(frlg_variables))
        self.assertGreater(len(flags), 2000)
        self.assertGreater(len(variables), 200)
        self.assertIn(("I_EXP_SHARE_FLAG", "FLAG_UNUSED_0x264"), aliases)
        for name in ("FLAG_BADGE05_GET", "FLAG_SYS_TV_START", "FLAG_UNUSED_0x264", "VAR_TEMP_1", "VAR_RESULT"):
            self.assertIn(f"#if defined({name})\n", text)
        # vars_frlg.h's names under IS_FRLG; Emerald shows them only where vars.h has the same define
        frlg = text.index("#if IS_FRLG\n")
        self.assertTrue(frlg_variables)
        for name in frlg_variables:
            self.assertGreater(text.rindex(f"#if defined({name})\n"), frlg)
            self.assertEqual(text.index(f"#if defined({name})\n") > frlg, name not in variables)
        # VAR_TEMP_1's aliases come after it, so VAR_TEMP_1 is emitted after them and wins
        self.assertGreater(text.index("#if defined(VAR_TEMP_1)\n"), text.index("#if defined(VAR_TEMP_TRANSFERRED_SPECIES)\n"))

    def test_main_writes_the_output(self):
        flags = write_temp(self, "#define FLAG_A 1\n")
        variables = write_temp(self, "#define VAR_B 0x4001\n")
        out = os.path.join(tempfile.mkdtemp(), "names.h")
        self.addCleanup(os.rmdir, os.path.dirname(out))
        self.addCleanup(os.remove, out)
        subprocess.run([sys.executable, gen.__file__, out, "--flags", flags, "--vars", variables], check=True)
        with open(out, encoding="utf-8") as f:
            self.assertEqual(f.read(), gen.generate(["FLAG_A"], ["VAR_B"]))
        self.assertEqual(os.listdir(os.path.dirname(out)), ["names.h"])


if __name__ == "__main__":
    unittest.main()
