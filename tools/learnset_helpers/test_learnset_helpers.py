"""Tests for the learnset helpers. Run from the repo root:
python3 -m unittest discover -s tools/learnset_helpers
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

import make_teachables
import make_teaching_types
import make_tutors

HELPERS_DIR = os.path.dirname(os.path.abspath(__file__))


class RepoDirTest(unittest.TestCase):
    """Runs each test in an empty directory, since the helpers read paths relative to the repo root."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cwd = os.getcwd()
        self.addCleanup(os.chdir, cwd)
        os.chdir(tmp.name)

    def write(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)


class ConfigTest(RepoDirTest):
    """A config line without a trailing comment still reads its value (#258)."""

    def test_enabled_without_comment(self):
        self.write("include/config/pokemon.h",
                   "#define P_LEARNSET_HELPER_TEACHABLE TRUE\n#define P_OTHER FALSE\n")
        for module in (make_teachables, make_tutors, make_teaching_types):
            self.assertTrue(module.enabled(), module.__name__)

    def test_disabled_without_comment(self):
        self.write("include/config/pokemon.h", "#define P_LEARNSET_HELPER_TEACHABLE FALSE\n")
        for module in (make_teachables, make_tutors, make_teaching_types):
            self.assertFalse(module.enabled(), module.__name__)

    def test_enabled_with_comment_against_value(self):
        self.write("include/config/pokemon.h", "#define P_LEARNSET_HELPER_TEACHABLE TRUE// on\n")
        for module in (make_teachables, make_tutors, make_teaching_types):
            self.assertTrue(module.enabled(), module.__name__)

    def test_empty_value_does_not_read_next_line(self):
        self.write("include/config/pokemon.h",
                   "#define P_LEARNSET_HELPER_TEACHABLE\n#define TRUE 1\n"
                   "#define P_TM_LITERACY\nGEN_7\n")
        for module in (make_teachables, make_tutors, make_teaching_types):
            self.assertFalse(module.enabled(), module.__name__)
        self.assertFalse(make_teachables.extract_tm_litteracy_config())

    def test_tm_literacy_without_comment(self):
        for value, literate in (("GEN_6", False), ("GEN_7", True), ("GEN_LATEST", True), ("GEN_7//x", True)):
            self.write("include/config/pokemon.h",
                       f"#define P_TM_LITERACY {value}\n#define P_OTHER TRUE\n")
            self.assertEqual(make_teachables.extract_tm_litteracy_config(), literate, value)

    def test_hgss_sort_without_comment(self):
        match = make_teachables.ALPHABETICAL_ORDER_ENABLED_PAT.search(
            "#define HGSS_SORT_TMS_BY_NUM\tFALSE\n#define HGSS_OTHER TRUE\n")
        assert match is not None
        self.assertEqual(match.group("cfg_val"), "FALSE")


class TmLiteracyTest(RepoDirTest):
    """A TM-illiterate species keeps every TM and tutor move it learns before Gen 7 (#258)."""

    def teachables(self, literacy):
        self.write("include/config/pokemon.h", f"#define P_TM_LITERACY {literacy}\n")
        special = {"signatureTeachables": [], "universalMoves": ["MOVE_U"]}
        learnables = {"FOO_BAR": ["MOVE_C", "MOVE_A", "MOVE_U", "MOVE_T"]}
        types = [{"name": "FooBar", "teaching_type": "TM_ILLITERATE"}]
        out = make_teachables.prepare_output(
            learnables, ["MOVE_A", "MOVE_B", "MOVE_C", "MOVE_U"], ["MOVE_T"], special, types, "")
        body = out.split("sFooBarTeachableLearnset[] = {\n")[1].split("};")[0]
        return [move.strip() for move in body.split(",") if move.strip()]

    def test_illiterate_before_gen_7(self):
        self.assertEqual(self.teachables("GEN_6"), ["MOVE_A", "MOVE_C", "MOVE_T", "MOVE_UNAVAILABLE"])

    def test_literate_from_gen_7(self):
        self.assertEqual(self.teachables("GEN_7"),
                         ["MOVE_A", "MOVE_C", "MOVE_U", "MOVE_T", "MOVE_UNAVAILABLE"])


class TeachingTypeTest(RepoDirTest):
    """A teaching type belongs to the species whose initializer has it (#258)."""

    def test_teaching_type_stays_with_its_species(self):
        self.write("src/data/pokemon/species_info/gen_1_families.h", "\n".join([
            "#define MACRO_INFO(x)                                     \\",
            "    {                                                     \\",
            "        .teachingType = TM_ILLITERATE,                    \\",
            "        .teachableLearnset = sMacroTeachableLearnset,     \\",
            "    }",
            "    [SPECIES_AFTER] =",
            "    {",
            "        .teachableLearnset = sAfterTeachableLearnset,",
            "        .teachingType = TM_ILLITERATE,",
            "    },",
            "    [SPECIES_PLAIN] =",
            "    {",
            "        .teachableLearnset = sPlainTeachableLearnset,",
            "    },",
            "    [SPECIES_NO_COMMA] =",
            "    {",
            "        .teachableLearnset = sNoCommaTeachableLearnset,",
            "        .teachingType = ALL_TEACHABLES",
            "    },",
            "    [SPECIES_LAST] =",
            "    {",
            "        .teachableLearnset = sLastTeachableLearnset,",
            "    },",
            "",
        ]))
        self.write("src/data/pokemon/species_info.h", "")
        types = {entry["name"]: entry["teaching_type"]
                 for entry in make_teaching_types.extract_repo_species_data()
                 if isinstance(entry, dict)}
        self.assertEqual(types, {
            "Macro": "TM_ILLITERATE",
            "After": "TM_ILLITERATE",
            "Plain": "DEFAULT_LEARNING",
            "NoComma": "ALL_TEACHABLES",
            "Last": "DEFAULT_LEARNING",
        })


class LearnablesOrderTest(RepoDirTest):
    """all_learnables.json comes out the same under any hash seed (#258)."""

    def test_same_output_under_any_hash_seed(self):
        species = ["ZUBAT", "ABRA", "MEW", "KOFFING", "BULBASAUR", "PIDGEY", "ONIX", "EEVEE"]
        entry = {"LevelMoves": [{"Move": "MOVE_TACKLE"}], "TMMoves": [], "EggMoves": [], "TutorMoves": []}
        self.write("inputs/a.json", json.dumps({name: entry for name in species[:5]}))
        self.write("inputs/b.json", json.dumps({name: entry for name in species[3:]}))
        outputs = []
        for seed in ("1", "2", "3"):
            subprocess.run([sys.executable, os.path.join(HELPERS_DIR, "make_learnables.py"),
                            "inputs", f"out{seed}.json"],
                           env={**os.environ, "PYTHONHASHSEED": seed}, check=True)
            with open(f"out{seed}.json") as f:
                outputs.append(f.read())
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0], outputs[2])
        self.assertEqual(list(json.loads(outputs[0])), sorted(species))


if __name__ == "__main__":
    unittest.main()
