"""Tests for wild_encounters_to_header.py. Run from the repo root:
python3 -m unittest discover -s tools/wild_encounters
"""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

import wild_encounters_to_header as gen

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SCRIPT = os.path.join(REPO, "tools", "wild_encounters", "wild_encounters_to_header.py")
REAL_JSON = os.path.join(REPO, "src", "data", "wild_encounters.json")

TIMES_OF_DAY = {"TIME_MORNING": "Morning", "TIME_DAY": "Day", "TIME_EVENING": "Evening", "TIME_NIGHT": "Night"}


def mons(count, min_level=2, max_level=5):
    return [{"min_level": min_level, "max_level": max_level, "species": "SPECIES_ZIGZAGOON"} for _ in range(count)]


def sample():
    """A two-field file: land with 3 slots, water with 2."""
    return {
        "wild_encounter_groups": [
            {
                "label": "gWildMonHeaders",
                "for_maps": True,
                "fields": [
                    {"type": "land_mons", "encounter_rates": [50, 30, 20]},
                    {"type": "water_mons", "encounter_rates": [60, 40]},
                ],
                "encounters": [
                    {
                        "map": "MAP_ROUTE101",
                        "base_label": "gRoute101",
                        "land_mons": {"encounter_rate": 20, "mons": mons(3)},
                        "water_mons": {"encounter_rate": 4, "mons": mons(2)},
                    }
                ],
            },
            {
                "label": "gBattlePikeWildMonHeaders",
                "for_maps": False,
                "encounters": [
                    {"base_label": "gBattlePike_1", "land_mons": {"encounter_rate": 10, "mons": mons(3)}}
                ],
            },
        ]
    }


def route101(data):
    return data["wild_encounter_groups"][0]["encounters"][0]


def validate(data):
    """Both checks, as ConvertToHeaderFile runs them."""
    gen.ValidateEncounters(data)
    gen.ValidateLabels(data, TIMES_OF_DAY, "TIME_MORNING")


def add_fishing(data, rates, groups):
    data["wild_encounter_groups"][0]["fields"].append({"type": "fishing_mons", "encounter_rates": rates, "groups": groups})
    route101(data)["fishing_mons"] = {"encounter_rate": 20, "mons": mons(len(rates))}


class ValidateTest(unittest.TestCase):
    def assertRejected(self, data, message):
        with self.assertRaises(gen.WildEncountersError) as context:
            validate(data)
        self.assertIn(message, str(context.exception))

    def test_sample_passes(self):
        validate(sample())

    def test_real_data_passes(self):
        with open(REAL_JSON) as json_file:
            validate(json.load(json_file))

    def test_default_levels_pass(self):
        data = sample()
        route101(data)["land_mons"]["mons"] = [{"species": "SPECIES_ZIGZAGOON"}] * 3
        validate(data)

    def test_too_few_slots(self):
        data = sample()
        route101(data)["land_mons"]["mons"].pop()
        self.assertRejected(data, "gRoute101 land_mons: 2 mons, but the land_mons field has 3 encounter_rates")

    def test_too_many_slots(self):
        data = sample()
        route101(data)["water_mons"]["mons"].append(mons(1)[0])
        self.assertRejected(data, "gRoute101 water_mons: 3 mons")

    def test_slot_count_checked_in_groups_without_fields(self):
        data = sample()
        data["wild_encounter_groups"][1]["encounters"][0]["land_mons"]["mons"].pop()
        self.assertRejected(data, "gBattlePike_1 land_mons: 2 mons")

    def test_misspelled_level_keys(self):
        data = sample()
        route101(data)["land_mons"]["mons"][1] = {"min_lvl": 3, "max_lvl": 4, "species": "SPECIES_ZIGZAGOON"}
        self.assertRejected(data, "gRoute101 land_mons slot 1: unknown key(s) max_lvl, min_lvl")

    def test_misspelled_field_key(self):
        data = sample()
        route101(data)["lnd_mons"] = route101(data).pop("land_mons")
        self.assertRejected(data, "gRoute101: unknown key(s) lnd_mons")

    def test_unknown_mons_entry_key(self):
        data = sample()
        route101(data)["land_mons"]["rate"] = 20
        self.assertRejected(data, "gRoute101 land_mons: unknown key(s) rate")

    def test_unknown_field_and_group_keys(self):
        data = sample()
        data["wild_encounter_groups"][0]["fields"][0]["encounter_rate"] = 1
        self.assertRejected(data, "field land_mons: unknown key(s) encounter_rate")
        data = sample()
        data["wild_encounter_groups"][1]["for_map"] = True
        self.assertRejected(data, "gBattlePikeWildMonHeaders: unknown key(s) for_map")

    def test_missing_keys(self):
        data = sample()
        del route101(data)["land_mons"]["mons"][0]["species"]
        self.assertRejected(data, "gRoute101 land_mons slot 0: missing key(s) species")
        data = sample()
        del route101(data)["water_mons"]["encounter_rate"]
        self.assertRejected(data, "gRoute101 water_mons: missing key(s) encounter_rate")
        data = sample()
        del route101(data)["map"]
        self.assertRejected(data, "gRoute101: missing key(s) map")
        data = sample()
        del data["wild_encounter_groups"][1]["encounters"][0]["base_label"]
        self.assertRejected(data, "gBattlePikeWildMonHeaders encounter 0: missing key(s) base_label")

    def test_field_type_with_two_slot_counts(self):
        data = sample()
        data["wild_encounter_groups"][1]["fields"] = [{"type": "land_mons", "encounter_rates": [100]}]
        self.assertRejected(data, "gBattlePikeWildMonHeaders field land_mons: 1 encounter_rates, but another group's has 3")

    def test_levels_out_of_range(self):
        for min_level, max_level, message in (
            (0, 5, "min_level is 0, expected 1 to 5"),
            (2, 250, "max_level is 250, expected 1 to 100"),
            (2, 101, "max_level is 101"),
            (6, 5, "min_level is 6, expected 1 to 5"),
            (2, "5", "max_level is '5'"),
        ):
            with self.subTest(min_level=min_level, max_level=max_level):
                data = sample()
                route101(data)["land_mons"]["mons"][2] = mons(1, min_level, max_level)[0]
                self.assertRejected(data, f"gRoute101 land_mons slot 2: {message}")

    def test_default_min_level_above_max(self):
        data = sample()
        route101(data)["land_mons"]["mons"][0] = {"max_level": 1, "species": "SPECIES_ZIGZAGOON"}
        self.assertRejected(data, "min_level is 2, expected 1 to 1")

    def test_level_bounds_pass(self):
        data = sample()
        route101(data)["land_mons"]["mons"][0] = mons(1, 1, 1)[0]
        route101(data)["land_mons"]["mons"][1] = mons(1, 100, 100)[0]
        validate(data)

    def test_encounter_rate_range(self):
        data = sample()
        route101(data)["land_mons"]["encounter_rate"] = 255
        validate(data)
        route101(data)["land_mons"]["encounter_rate"] = 400
        self.assertRejected(data, "gRoute101 land_mons: encounter_rate is 400, expected 0 to 255")
        route101(data)["land_mons"]["encounter_rate"] = -1
        self.assertRejected(data, "encounter_rate is -1")

    def test_rate_totals_up_to_256_pass(self):
        for rates in ([50, 30, 19], [50, 30, 30], [1, 0, 0], [200, 50, 6]):
            with self.subTest(rates=rates):
                data = sample()
                data["wild_encounter_groups"][0]["fields"][0]["encounter_rates"] = rates
                validate(data)

    def test_rate_totals_and_rates_out_of_range(self):
        for rates, message in (
            ([0, 0, 0], "gWildMonHeaders field land_mons: the encounter_rates total is 0, expected 1 to 256"),
            ([200, 50, 7], "the encounter_rates total is 257"),
            ([100, -10, 10], "encounter_rates[1] is -10, expected 0 to 256"),
            ([257, 0, 0], "encounter_rates[0] is 257"),
            ([50, 30, 20.0], "encounter_rates[2] is 20.0"),
        ):
            with self.subTest(rates=rates):
                data = sample()
                data["wild_encounter_groups"][0]["fields"][0]["encounter_rates"] = rates
                self.assertRejected(data, message)

    def test_rod_groups_share_one_total(self):
        for rates, groups in (
            ([70, 30, 60, 20, 20], {"old_rod": [0, 1], "good_rod": [2, 3, 4]}),
            ([70, 30, 60, 20, 20], {"old_rod": [1, 0], "good_rod": [4, 2, 3]}),
            ([60, 30, 60, 20, 10], {"old_rod": [0, 1], "good_rod": [2, 3, 4]}),
        ):
            with self.subTest(rates=rates, groups=groups):
                data = sample()
                add_fishing(data, rates, groups)
                validate(data)
        data = sample()
        add_fishing(data, [70, 30, 60, 20, 10], {"old_rod": [0, 1], "good_rod": [2, 3, 4]})
        self.assertRejected(data, "gWildMonHeaders field fishing_mons: the groups' encounter_rates totals differ (old_rod 100, good_rod 90)")
        data = sample()
        add_fishing(data, [200, 57, 200, 50, 7], {"old_rod": [0, 1], "good_rod": [2, 3, 4]})
        self.assertRejected(data, "field fishing_mons group old_rod: the encounter_rates total is 257")

    def test_group_indices(self):
        for groups, message in (
            ({"old_rod": [0, 1], "good_rod": [2, 3, 5]}, "group good_rod: slot index is 5, expected 0 to 4"),
            ({"old_rod": [0, 1], "good_rod": [2, 3, -1]}, "group good_rod: slot index is -1"),
            ({"old_rod": [0, 1], "good_rod": [2, 3, "4"]}, "slot index is '4'"),
            ({"old_rod": [0, 1], "good_rod": [1, 2, 3, 4]}, "group good_rod: slot 1 is also in group old_rod"),
            ({"old_rod": [0, 2], "good_rod": [1, 3, 4]}, "group old_rod: slots [0, 2] aren't consecutive"),
            ({"old_rod": [0, 1], "good_rod": [2, 3, 4], "super_rod": []}, "group super_rod: slots are [], expected a list of slot indices"),
            ({"old_rod": 1, "good_rod": [1, 2, 3, 4]}, "group old_rod: slots are 1, expected a list"),
            ({"old_rod": "01", "good_rod": [2, 3, 4]}, "group old_rod: slots are '01', expected a list"),
            ([[0, 1], [2, 3, 4]], "field fishing_mons: groups is [[0, 1], [2, 3, 4]], expected an object of slot lists"),
        ):
            with self.subTest(groups=groups):
                data = sample()
                add_fishing(data, [70, 30, 60, 20, 20], groups)
                self.assertRejected(data, message)

    def test_slot_in_no_group(self):
        data = sample()
        add_fishing(data, [70, 30, 80, 20, 0], {"old_rod": [0, 1], "good_rod": [2, 3]})
        self.assertRejected(data, "gWildMonHeaders field fishing_mons: slot(s) 4 in no group")

    def test_same_label_and_time_twice(self):
        for second_label in ("gRoute101", "gRoute101_Morning"):
            with self.subTest(second_label=second_label):
                data = sample()
                second = dict(route101(data), base_label=second_label)
                data["wild_encounter_groups"][0]["encounters"].append(second)
                self.assertRejected(data, f"{second_label}: same label and time of day as gRoute101 (gRoute101, TIME_MORNING)")

    def test_other_times_of_one_label_pass(self):
        data = sample()
        for label in ("gRoute101_Day", "gRoute101_Night"):
            data["wild_encounter_groups"][0]["encounters"].append(dict(route101(data), base_label=label))
        data["wild_encounter_groups"][0]["encounters"].append(dict(route101(data), base_label="gRoute101_FireRed"))
        data["wild_encounter_groups"][1]["encounters"].append(
            dict(data["wild_encounter_groups"][1]["encounters"][0], base_label="gBattlePike_1_Night"))
        validate(data)

    def test_times_of_one_label_name_one_map(self):
        data = sample()
        night = dict(route101(data), base_label="gRoute101_Night", map="MAP_ROUTE102")
        data["wild_encounter_groups"][0]["encounters"].append(night)
        self.assertRejected(data, "gRoute101_Night: map MAP_ROUTE102, but gRoute101 has MAP_ROUTE101")


def assembler(json_data, time_encounters=False):
    config = SimpleNamespace(
        times_of_day=TIMES_OF_DAY,
        time_fallback="TIME_MORNING",
        time_encounters=time_encounters,
        mon_types=["land_mons", "water_mons"],
    )
    return gen.WildEncounterAssembler(io.StringIO(), json_data, config)


class TimeOfDayTest(unittest.TestCase):
    def test_suffix_is_matched_exactly(self):
        def split(label):
            return gen.SplitTimeOfDay(label, TIMES_OF_DAY, "TIME_MORNING")
        self.assertEqual(split("gRoute101"), ("gRoute101", "TIME_MORNING"))
        self.assertEqual(split("gRoute101_Night"), ("gRoute101", "TIME_NIGHT"))
        self.assertEqual(split("gRoute101_Day"), ("gRoute101", "TIME_DAY"))
        self.assertEqual(split("gSunDayRoad_Craft"), ("gSunDayRoad_Craft", "TIME_MORNING"))
        self.assertEqual(split("gRoute101_DayCare"), ("gRoute101_DayCare", "TIME_MORNING"))
        self.assertEqual(split("gNightRoute_Day"), ("gNightRoute", "TIME_DAY"))

    def test_label_containing_a_time_keeps_its_encounters(self):
        data = sample()
        route101(data)["base_label"] = "gSunDayRoad_Craft"
        writer = assembler(data)
        writer.WriteEncounters()
        output = writer.output_file.getvalue()
        self.assertIn(".landMonsInfo = &gSunDayRoad_Craft_LandMonsInfo,", output)


class VersionTest(unittest.TestCase):
    def test_version_suffix_is_matched_exactly(self):
        for label, version in (
            ("gRoute101", "EMERALD"),
            ("sRoute1_FireRed", "FIRERED"),
            ("sRoute1_LeafGreen", "LEAFGREEN"),
            ("gFireRedRoad", "EMERALD"),
            ("gLeafGreenGrove_Cave", "EMERALD"),
            ("sRoute1_FireRedGate", "EMERALD"),
        ):
            with self.subTest(label=label):
                self.assertEqual(gen.GetLabelVersion(label), version)

    def test_label_containing_a_version_stays_emerald(self):
        data = sample()
        data["wild_encounter_groups"][0]["encounters"].append(dict(route101(data), base_label="gFireRedRoad", map="MAP_ROUTE102"))
        data["wild_encounter_groups"][0]["encounters"].append(dict(route101(data), base_label="sRoute1_LeafGreen_Night", map="MAP_ROUTE103"))
        writer = assembler(data, time_encounters=True)
        writer.WriteEncounters()
        output = writer.output_file.getvalue()
        self.assertNotIn("#ifdef FIRERED", output)
        self.assertEqual(output.count("#ifdef LEAFGREEN"), 2)  # its tables and its header entry
        self.assertIn("#ifdef EMERALD\n    {\n        .mapGroup = MAP_GROUP(MAP_ROUTE102)", output)


class MainTest(unittest.TestCase):
    """The generator as the Makefile runs it, from a copy of the repo's inputs."""

    def run_generator(self, data):
        with tempfile.TemporaryDirectory() as root:
            for path in ("include/config/overworld.h", "include/constants/rtc.h"):
                os.makedirs(os.path.join(root, os.path.dirname(path)), exist_ok=True)
                with open(os.path.join(REPO, path)) as src, open(os.path.join(root, path), "w") as dst:
                    dst.write(src.read())
            os.makedirs(os.path.join(root, "src", "data"))
            with open(os.path.join(root, "src", "data", "wild_encounters.json"), "w") as json_file:
                json.dump(data, json_file)
            result = subprocess.run([sys.executable, SCRIPT], cwd=root, capture_output=True, text=True)
            header = os.path.join(root, "src", "data", "wild_encounters.h")
            return result, os.path.exists(header)

    def test_bad_data_fails_without_writing_the_header(self):
        data = sample()
        route101(data)["land_mons"]["mons"].pop()
        result, wrote_header = self.run_generator(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("src/data/wild_encounters.json: gRoute101 land_mons: 2 mons", result.stderr)
        self.assertFalse(wrote_header)

    def test_repeated_label_fails_without_writing_the_header(self):
        data = sample()
        data["wild_encounter_groups"][0]["encounters"].append(dict(route101(data), base_label="gRoute101_Morning"))
        result, wrote_header = self.run_generator(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("src/data/wild_encounters.json: gRoute101_Morning: same label and time of day", result.stderr)
        self.assertFalse(wrote_header)

    def test_good_data_writes_the_header(self):
        result, wrote_header = self.run_generator(sample())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(wrote_header)


if __name__ == "__main__":
    unittest.main()
