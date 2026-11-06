"""Tests for wild_encounters_to_header.py. Run from the repo root:
python3 -m unittest discover -s tools/wild_encounters
"""

import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

import wild_encounters_to_header as gen

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SCRIPT = os.path.join(REPO, "tools", "wild_encounters", "wild_encounters_to_header.py")
REAL_JSON = os.path.join(REPO, "src", "data", "wild_encounters.json")
JSONPROC = os.path.join(REPO, "tools", "jsonproc", "jsonproc")
CONSTANTS_TEMPLATE = os.path.join(REPO, "src", "data", "wild_encounters.constants.json.txt")

TIMES_OF_DAY = {"TIME_MORNING": "Morning", "TIME_DAY": "Day", "TIME_EVENING": "Evening", "TIME_NIGHT": "Night"}


def mons(count, min_level=2, max_level=5):
    return [{"min_level": min_level, "max_level": max_level, "species": "SPECIES_ZIGZAGOON"} for _ in range(count)]


LAND_RATES = [20, 20, 10, 10, 10, 10, 5, 5, 4, 4, 1, 1]
ROD_GROUPS = {"old_rod": [0, 1], "good_rod": [2, 3, 4], "super_rod": [5, 6, 7, 8, 9]}
ROD_RATES = [70, 30, 60, 20, 20, 40, 40, 15, 4, 1]


def land_rates(*head):
    """Land encounter_rates starting with head, the other slots 0."""
    return list(head) + [0] * (len(LAND_RATES) - len(head))


def sample():
    """A two-field file with the pickers' slot counts: land 12, water 5."""
    return {
        "wild_encounter_groups": [
            {
                "label": "gWildMonHeaders",
                "for_maps": True,
                "fields": [
                    {"type": "land_mons", "encounter_rates": list(LAND_RATES)},
                    {"type": "water_mons", "encounter_rates": [60, 30, 5, 4, 1]},
                ],
                "encounters": [
                    {
                        "map": "MAP_ROUTE101",
                        "base_label": "gRoute101",
                        "land_mons": {"encounter_rate": 20, "mons": mons(12)},
                        "water_mons": {"encounter_rate": 4, "mons": mons(5)},
                    }
                ],
            },
            {
                "label": "gBattlePikeWildMonHeaders",
                "for_maps": False,
                "encounters": [
                    {"base_label": "gBattlePike_1", "land_mons": {"encounter_rate": 10, "mons": mons(12)}}
                ],
            },
        ]
    }


def route101(data):
    return data["wild_encounter_groups"][0]["encounters"][0]


def add_encounter(data, base_label, group=0, **changes):
    """A copy of the group's first encounter under another label."""
    encounters = data["wild_encounter_groups"][group]["encounters"]
    encounters.append(dict(encounters[0], base_label=base_label, **changes))


def validate(data, time_encounters=False):
    """Both checks, as ConvertToHeaderFile runs them."""
    gen.ValidateEncounters(data)
    gen.ValidateLabels(data, TIMES_OF_DAY, "TIME_MORNING", time_encounters)


def add_field(data, field_type, rates, groups=None):
    """A field, and a table of it on gRoute101."""
    field = {"type": field_type, "encounter_rates": rates}
    if groups is not None:
        field["groups"] = groups
    data["wild_encounter_groups"][0]["fields"].append(field)
    route101(data)[field_type] = {"encounter_rate": 20, "mons": mons(len(rates))}


def add_fishing(data, rates=ROD_RATES, groups=ROD_GROUPS):
    add_field(data, "fishing_mons", rates, groups)


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
        route101(data)["land_mons"]["mons"] = [{"species": "SPECIES_ZIGZAGOON"}] * 12
        validate(data)

    def test_too_few_slots(self):
        data = sample()
        route101(data)["land_mons"]["mons"].pop()
        self.assertRejected(data, "gRoute101 land_mons: 11 mons, but the land_mons field has 12 encounter_rates")

    def test_too_many_slots(self):
        data = sample()
        route101(data)["water_mons"]["mons"].append(mons(1)[0])
        self.assertRejected(data, "gRoute101 water_mons: 6 mons")

    def test_slot_count_checked_in_groups_without_fields(self):
        data = sample()
        data["wild_encounter_groups"][1]["encounters"][0]["land_mons"]["mons"].pop()
        self.assertRejected(data, "gBattlePike_1 land_mons: 11 mons")

    def test_field_slot_counts_match_the_pickers(self):
        for field_type, count in (("land_mons", 11), ("land_mons", 13), ("water_mons", 4), ("rock_smash_mons", 6), ("hidden_mons", 4)):
            with self.subTest(field_type=field_type, count=count):
                data = sample()
                rates = [1] * count
                fields = data["wild_encounter_groups"][0]["fields"]
                fields[:] = [field for field in fields if field["type"] != field_type]
                fields.append({"type": field_type, "encounter_rates": rates})
                for encounters in (route101(data), data["wild_encounter_groups"][1]["encounters"][0]):
                    if field_type in encounters:
                        encounters[field_type]["mons"] = mons(count)
                expected = gen.PICKER_SLOT_COUNTS[field_type]
                self.assertRejected(data, f"gWildMonHeaders field {field_type}: {count} encounter_rates, but src/wild_encounter.c picks from {expected} slots")

    def test_rock_smash_and_hidden_fields_pass(self):
        data = sample()
        add_field(data, "rock_smash_mons", [60, 30, 5, 4, 1])
        add_field(data, "hidden_mons", [50, 30, 20])
        route101(data)["hidden_mons"]["encounter_rate"] = 1
        validate(data)

    def test_hidden_encounter_rate_is_dexnavs_land_or_water_flag(self):
        data = sample()
        add_field(data, "hidden_mons", [50, 30, 20])
        for flag in (0, 1):
            route101(data)["hidden_mons"]["encounter_rate"] = flag
            validate(data)
        for rate in (2, 20, 255, -1):
            with self.subTest(rate=rate):
                route101(data)["hidden_mons"]["encounter_rate"] = rate
                self.assertRejected(data, f"gRoute101 hidden_mons: encounter_rate is {rate}, expected 0 to 1")

    def test_field_type_without_a_picker(self):
        data = sample()
        data["wild_encounter_groups"][0]["fields"].append({"type": "headbutt_mons", "encounter_rates": [100]})
        self.assertRejected(data, "gWildMonHeaders field headbutt_mons: no picker in src/wild_encounter.c reads this field type")

    def test_rod_groups_match_the_picker(self):
        for groups, rates in (
            ({"old_rod": [0], "good_rod": [1, 2, 3, 4], "super_rod": [5, 6, 7, 8, 9]}, [100, 40, 30, 20, 10] + ROD_RATES[5:]),
            ({"old_rod": [0, 1], "good_rod": [2, 3, 4, 5], "super_rod": [6, 7, 8, 9]}, [70, 30, 60, 20, 10, 10, 40, 40, 19, 1]),
            ({"old": [0, 1], "good_rod": [2, 3, 4], "super_rod": [5, 6, 7, 8, 9]}, ROD_RATES),
            ({"old_rod": [0, 1], "good_rod": [2, 3, 4, 5, 6, 7, 8, 9]}, [70, 30, 20, 20, 20, 10, 10, 10, 5, 5]),
        ):
            with self.subTest(groups=groups):
                data = sample()
                add_fishing(data, rates, groups)
                self.assertRejected(data, "gWildMonHeaders field fishing_mons: groups are "
                                    f"{groups}, but src/wild_encounter.c picks from {gen.PICKER_GROUPS['fishing_mons']}")
        data = sample()
        add_fishing(data, [10] * 10, None)
        self.assertRejected(data, "field fishing_mons: groups are None")
        data = sample()
        data["wild_encounter_groups"][0]["fields"][1]["groups"] = {"water": [0, 1, 2, 3, 4]}
        self.assertRejected(data, "field water_mons: groups are {'water': [0, 1, 2, 3, 4]}, but src/wild_encounter.c picks from None")

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
        self.assertRejected(data, "gBattlePikeWildMonHeaders field land_mons: 1 encounter_rates, but src/wild_encounter.c picks from 12 slots")

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
        for rates in (land_rates(50, 30, 19), land_rates(50, 30, 30), land_rates(1), land_rates(200, 50, 6), land_rates(256)):
            with self.subTest(rates=rates):
                data = sample()
                data["wild_encounter_groups"][0]["fields"][0]["encounter_rates"] = rates
                validate(data)

    def test_rate_totals_and_rates_out_of_range(self):
        for rates, message in (
            (land_rates(), "gWildMonHeaders field land_mons: the encounter_rates total is 0, expected 1 to 256"),
            (land_rates(200, 50, 7), "the encounter_rates total is 257"),
            (land_rates(100, -10, 10), "encounter_rates[1] is -10, expected 0 to 256"),
            (land_rates(257), "encounter_rates[0] is 257"),
            (land_rates(50, 30, 20.0), "encounter_rates[2] is 20.0"),
        ):
            with self.subTest(rates=rates):
                data = sample()
                data["wild_encounter_groups"][0]["fields"][0]["encounter_rates"] = rates
                self.assertRejected(data, message)

    def test_rod_groups_share_one_total(self):
        for rates, groups in (
            (ROD_RATES, ROD_GROUPS),
            (ROD_RATES, {"super_rod": [9, 5, 6, 8, 7], "old_rod": [1, 0], "good_rod": [4, 2, 3]}),
            ([60, 30, 60, 20, 10, 50, 30, 5, 4, 1], ROD_GROUPS),
        ):
            with self.subTest(rates=rates, groups=groups):
                data = sample()
                add_fishing(data, rates, groups)
                validate(data)
        data = sample()
        add_fishing(data, [70, 30, 60, 20, 10] + ROD_RATES[5:])
        self.assertRejected(data, "gWildMonHeaders field fishing_mons: the groups' encounter_rates totals differ (old_rod 100, good_rod 90, super_rod 100)")
        data = sample()
        add_fishing(data, [200, 57, 200, 50, 7, 200, 50, 4, 2, 1])
        self.assertRejected(data, "field fishing_mons group old_rod: the encounter_rates total is 257")

    def test_group_indices(self):
        super_rod = ROD_GROUPS["super_rod"]
        for groups, message in (
            ({"old_rod": [0, 1], "good_rod": [2, 3, 10], "super_rod": super_rod}, "group good_rod: slot index is 10, expected 0 to 9"),
            ({"old_rod": [0, 1], "good_rod": [2, 3, -1], "super_rod": super_rod}, "group good_rod: slot index is -1"),
            ({"old_rod": [0, 1], "good_rod": [2, 3, "4"], "super_rod": super_rod}, "slot index is '4'"),
            ({"old_rod": [0, 1], "good_rod": [1, 2, 3, 4], "super_rod": super_rod}, "group good_rod: slot 1 is also in group old_rod"),
            ({"old_rod": [0, 2], "good_rod": [1, 3, 4], "super_rod": super_rod}, "group old_rod: slots [0, 2] aren't consecutive"),
            ({"old_rod": [0, 1], "good_rod": [2, 3, 4], "super_rod": []}, "group super_rod: slots are [], expected a list of slot indices"),
            ({"old_rod": 1, "good_rod": [1, 2, 3, 4], "super_rod": super_rod}, "group old_rod: slots are 1, expected a list"),
            ({"old_rod": "01", "good_rod": [2, 3, 4], "super_rod": super_rod}, "group old_rod: slots are '01', expected a list"),
            ([[0, 1], [2, 3, 4], super_rod], "field fishing_mons: groups is [[0, 1], [2, 3, 4], [5, 6, 7, 8, 9]], expected an object of slot lists"),
        ):
            with self.subTest(groups=groups):
                data = sample()
                add_fishing(data, ROD_RATES, groups)
                self.assertRejected(data, message)

    def test_slot_in_no_group(self):
        data = sample()
        add_fishing(data, ROD_RATES[:9] + [0], {"old_rod": [0, 1], "good_rod": [2, 3, 4], "super_rod": [5, 6, 7, 8]})
        self.assertRejected(data, "gWildMonHeaders field fishing_mons: slot(s) 9 in no group")

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

    def test_one_map_under_two_labels(self):
        for label in ("gRoute101Too", "gRoute101Too_Night"):
            with self.subTest(label=label):
                data = sample()
                add_encounter(data, label)
                self.assertRejected(data, f"{label}: map MAP_ROUTE101 already has gRoute101's encounters (EMERALD)")
        data = sample()
        add_encounter(data, "sRoute101_FireRed")
        add_encounter(data, "sRoute101_LeafGreen")
        add_encounter(data, "sRoute101Too_LeafGreen")
        self.assertRejected(data, "sRoute101Too_LeafGreen: map MAP_ROUTE101 already has sRoute101_LeafGreen's encounters (LEAFGREEN)")

    def test_one_map_under_one_label_per_version_passes(self):
        data = sample()
        add_encounter(data, "sRoute101_FireRed")
        add_encounter(data, "sRoute101_LeafGreen")
        add_encounter(data, "gBattlePike_2", group=1)
        validate(data)

    def test_altering_cave_takes_a_label_per_table(self):
        data = sample()
        for table in range(1, 10):
            add_encounter(data, f"gAlteringCave{table}", map="MAP_ALTERING_CAVE")
            add_encounter(data, f"sAlteringCave{table}_FireRed", map="MAP_SIX_ISLAND_ALTERING_CAVE")
            add_encounter(data, f"sAlteringCave{table}_LeafGreen", map="MAP_SIX_ISLAND_ALTERING_CAVE")
        validate(data)

    def test_altering_cave_tables_are_all_there_and_together(self):
        data = sample()
        for table in range(1, 9):
            add_encounter(data, f"gAlteringCave{table}", map="MAP_ALTERING_CAVE")
        self.assertRejected(data, "gAlteringCave1: map MAP_ALTERING_CAVE has 8 labels (EMERALD), expected 9, one per table")
        add_encounter(data, "gRoute102", map="MAP_ROUTE102")
        add_encounter(data, "gAlteringCave9", map="MAP_ALTERING_CAVE")
        self.assertRejected(data, "gAlteringCave1: map MAP_ALTERING_CAVE's labels (EMERALD) aren't consecutive")
        data = sample()
        for table in range(1, 10):
            add_encounter(data, f"gAlteringCave{table}", map="MAP_ALTERING_CAVE")
            add_encounter(data, f"gAlteringCave{table}_Night", map="MAP_ALTERING_CAVE")
        add_encounter(data, "sAlteringCave1_FireRed", map="MAP_SIX_ISLAND_ALTERING_CAVE")
        self.assertRejected(data, "sAlteringCave1_FireRed: map MAP_SIX_ISLAND_ALTERING_CAVE has 1 labels (FIRERED), expected 9")

    def test_label_without_its_fallback_time(self):
        data = sample()
        add_encounter(data, "gRoute102_Day", map="MAP_ROUTE102")
        add_encounter(data, "gRoute102_Night", map="MAP_ROUTE102")
        self.assertRejected(data, "gRoute102_Day: with OW_TIME_OF_DAY_ENCOUNTERS FALSE only TIME_MORNING encounters are used, "
                            "and gRoute102 has none (gRoute102 or gRoute102_Morning)")
        validate(data, time_encounters=True)
        add_encounter(data, "gRoute102_Morning", map="MAP_ROUTE102")
        validate(data)

    def test_version_suffix_after_a_time_suffix(self):
        for label, renamed in (("sRoute1_Night_FireRed", "sRoute1_FireRed_Night"), ("sRoute1_Morning_LeafGreen", "sRoute1_LeafGreen_Morning")):
            with self.subTest(label=label):
                data = sample()
                add_encounter(data, label, map="MAP_ROUTE1")
                self.assertRejected(data, f"{label}: version suffix after the time of day suffix, expected {renamed}")
        data = sample()
        add_encounter(data, "sRoute1_FireRed", map="MAP_ROUTE1")
        add_encounter(data, "sRoute1_FireRed_Night", map="MAP_ROUTE1")
        add_encounter(data, "gSunDayRoad_FireRed", map="MAP_ROUTE2")
        validate(data)


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

    def run_generator(self, data, overworld_edit=lambda text: text):
        with tempfile.TemporaryDirectory() as root:
            for path in ("include/config/overworld.h", "include/constants/rtc.h"):
                os.makedirs(os.path.join(root, os.path.dirname(path)), exist_ok=True)
                with open(os.path.join(REPO, path)) as src, open(os.path.join(root, path), "w") as dst:
                    text = src.read()
                    dst.write(overworld_edit(text) if path.endswith("overworld.h") else text)
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
        self.assertIn("src/data/wild_encounters.json: gRoute101 land_mons: 11 mons", result.stderr)
        self.assertFalse(wrote_header)

    def test_repeated_label_fails_without_writing_the_header(self):
        data = sample()
        data["wild_encounter_groups"][0]["encounters"].append(dict(route101(data), base_label="gRoute101_Morning"))
        result, wrote_header = self.run_generator(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("src/data/wild_encounters.json: gRoute101_Morning: same label and time of day", result.stderr)
        self.assertFalse(wrote_header)

    def test_fallback_other_than_the_default_time_fails_without_time_encounters(self):
        def set_fallback(text, fallback="TIME_DAY", time_encounters="FALSE"):
            text = re.sub(r"(#define OW_TIME_OF_DAY_FALLBACK\s+)\w+", rf"\g<1>{fallback}", text)
            return re.sub(r"(#define OW_TIME_OF_DAY_ENCOUNTERS\s+)\w+", rf"\g<1>{time_encounters}", text)
        result, wrote_header = self.run_generator(sample(), set_fallback)
        self.assertEqual(result.returncode, 1)
        self.assertIn("OW_TIME_OF_DAY_FALLBACK is TIME_DAY, but with OW_TIME_OF_DAY_ENCOUNTERS FALSE "
                      "src/wild_encounter.c reads only TIME_MORNING encounters", result.stderr)
        self.assertFalse(wrote_header)
        result, wrote_header = self.run_generator(sample(), lambda text: set_fallback(text, time_encounters="TRUE"))
        self.assertEqual(result.returncode, 0, result.stderr)
        result, wrote_header = self.run_generator(sample(), lambda text: set_fallback(text, fallback="TIME_MORNING"))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_good_data_writes_the_header(self):
        result, wrote_header = self.run_generator(sample())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(wrote_header)


@unittest.skipUnless(os.path.exists(JSONPROC), "jsonproc isn't built")
class ConstantsTemplateTest(unittest.TestCase):
    """include/constants/wild_encounter.h as jsonproc writes it from the template."""

    def slot_count_defines(self, data):
        with tempfile.TemporaryDirectory() as root:
            json_path = os.path.join(root, "wild_encounters.json")
            header_path = os.path.join(root, "wild_encounter.h")
            with open(json_path, "w") as json_file:
                json.dump(data, json_file)
            subprocess.run([JSONPROC, json_path, CONSTANTS_TEMPLATE, header_path], check=True, capture_output=True)
            with open(header_path) as header:
                return re.findall(r"#define NUM_HIDDEN_MONS_ENCOUNTER_SLOTS\s+(.*)", header.read())

    def test_hidden_slot_count_is_defined_once(self):
        self.assertEqual(self.slot_count_defines(sample()), ["3"])
        data = sample()
        add_field(data, "hidden_mons", [50, 30, 20])
        self.assertEqual(self.slot_count_defines(data), ["(3)"])


if __name__ == "__main__":
    unittest.main()
