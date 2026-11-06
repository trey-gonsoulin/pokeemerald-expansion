"""Tests for the learnset helpers. Run from the repo root:
python3 -m unittest discover -s tools/learnset_helpers
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import make_learnables
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
            "    [SPECIES_IF_ELSE] =",
            "    {",
            "        .teachingType = TM_ILLITERATE,",
            "    #define INNER_MACRO 1",
            "#if P_FOO",
            "        .teachableLearnset = sIfTeachableLearnset,",
            "#else",
            "        .teachableLearnset = sElseTeachableLearnset,",
            "#endif",
            "    },",
            "    [SPECIES_TERNARY] =",
            "    {",
            "        .teachingType = P_GEN_7 ? TM_ILLITERATE : DEFAULT_LEARNING,",
            "        .teachableLearnset = sTernaryTeachableLearnset,",
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
            "If": "TM_ILLITERATE",
            "Else": "TM_ILLITERATE",
            "Ternary": "DEFAULT_LEARNING",
            "Last": "DEFAULT_LEARNING",
        })


def run_make_learnables(inputs_dir, out, **kwargs):
    return subprocess.run([sys.executable, os.path.join(HELPERS_DIR, "make_learnables.py"), inputs_dir, out],
                          **kwargs)


def porymoves_entry(move):
    return {"LevelMoves": [{"Move": move}], "TMMoves": [], "EggMoves": [], "TutorMoves": []}


class LearnablesOrderTest(RepoDirTest):
    """all_learnables.json comes out the same under any hash seed (#258)."""

    def test_same_output_under_any_hash_seed(self):
        species = ["ZUBAT", "ABRA", "MEW", "KOFFING", "BULBASAUR", "PIDGEY", "ONIX", "EEVEE"]
        entry = porymoves_entry("MOVE_TACKLE")
        self.write("inputs/a.json", json.dumps({name: entry for name in species[:5]}))
        self.write("inputs/b.json", json.dumps({name: entry for name in species[3:]}))
        outputs = []
        for seed in ("1", "2", "3"):
            run_make_learnables("inputs", f"out{seed}.json", env={**os.environ, "PYTHONHASHSEED": seed}, check=True)
            with open(f"out{seed}.json") as f:
                outputs.append(f.read())
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0], outputs[2])
        self.assertEqual(list(json.loads(outputs[0])), sorted(species))


class LearnablesKeyTest(RepoDirTest):
    """Every species key comes out in the snake-case form make_teachables looks up (#274)."""

    def make(self, inputs):
        for name, species in inputs.items():
            entries = {key: porymoves_entry(move) for key, move in species.items()}
            self.write(f"inputs/{name}.json", json.dumps(entries))
        return run_make_learnables("inputs", "out.json", capture_output=True, text=True)

    def learnables(self, inputs):
        self.make(inputs).check_returncode()
        with open("out.json") as f:
            return json.load(f)

    def test_punctuated_names_become_snake_case(self):
        out = self.learnables({"new": {"MR. MIME": "MOVE_A", "MIME JR.": "MOVE_B", "MR. RIME": "MOVE_C",
                                       "PORYGON-Z": "MOVE_D", "FARFETCH'D": "MOVE_F"},
                               "sv": {"MR_MIME": "MOVE_E"}})
        self.assertEqual(out, {"MR_MIME": ["MOVE_A", "MOVE_E"], "MIME_JR": ["MOVE_B"], "MR_RIME": ["MOVE_C"],
                               "PORYGON_Z": ["MOVE_D"], "FARFETCHD": ["MOVE_F"]})

    def test_accented_and_misencoded_names_lose_their_accents(self):
        out = self.learnables({"za": {"FLABÃ©BÃ©": "MOVE_A"},
                               "xy": {"FLABÉBÉ": "MOVE_B"},
                               "sv": {"FLABEBE": "MOVE_C"}})
        self.assertEqual(out, {"FLABEBE": ["MOVE_A", "MOVE_B", "MOVE_C"]})

    def test_merged_form_entries_are_skipped(self):
        out = self.learnables({"za": {"SLOWBRO": "MOVE_A", "MR. MIME": "MOVE_B", "HOOPA": "MOVE_C",
                                      "PIKACHU": "MOVE_D"},
                               "sv": {"SLOWBRO": "MOVE_E", "SLOWBRO_GALAR": "MOVE_F", "HOOPA_UNBOUND": "MOVE_G"}})
        self.assertEqual(out, {"SLOWBRO": ["MOVE_E"], "SLOWBRO_GALAR": ["MOVE_F"], "HOOPA_UNBOUND": ["MOVE_G"],
                               "PIKACHU": ["MOVE_D"]})

    def test_unreadable_key_stops_the_build(self):
        result = self.make({"za": {"PIKACHU": "MOVE_A", "???": "MOVE_B"}})
        self.assertEqual(result.returncode, 1)
        self.assertIn("za.json", result.stderr)
        self.assertIn("'???'", result.stderr)
        self.assertFalse(os.path.exists("out.json"))


class CommittedLearnablesTest(unittest.TestCase):
    """The committed all_learnables.json is what make_learnables.py makes from porymoves_files (#274)."""

    PORYMOVES_DIR = pathlib.Path(HELPERS_DIR, "porymoves_files")

    def test_committed_file_is_up_to_date(self):
        repo = os.path.dirname(os.path.dirname(HELPERS_DIR))
        committed = os.path.join(repo, "src", "data", "pokemon", "all_learnables.json")
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "all_learnables.json")
            run_make_learnables(str(self.PORYMOVES_DIR), out, check=True)
            with open(out) as f, open(committed) as g:
                self.assertTrue(f.read() == g.read(),
                                "all_learnables.json is stale: run `make src/data/pokemon/all_learnables.json`")

    def test_za_merged_forms_are_the_bare_names_of_other_games_forms(self):
        # A bare name in za.json whose forms za.json doesn't list but another game does. Older games
        # aren't checked: their bare names (rse's MAROWAK) predate the forms.
        keys = {}
        for fname in self.PORYMOVES_DIR.glob("*.json"):
            with open(fname, encoding="utf-8") as f:
                keys[fname.name] = {make_learnables.species_key(fname, species) for species in json.load(f)}
        za = keys.pop("za.json")
        others = set().union(*keys.values())
        merged = {key for key in za
                  if not any(k.startswith(key + "_") for k in za) and any(k.startswith(key + "_") for k in others)}
        self.assertEqual(merged, make_learnables.ZA_MERGED_FORMS)


if __name__ == "__main__":
    unittest.main()
