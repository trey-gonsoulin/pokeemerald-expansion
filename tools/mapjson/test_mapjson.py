"""Tests for mapjson's checks on map, layout and heal location data (#256).

Each test builds a small tree (two maps, one layout, a heal location) in a temporary
directory, runs the built tool there as the Makefile does, and checks its exit code,
message and outputs. Run from the repo root after `make -C tools/mapjson`:

    python3 -m unittest discover -s tools/mapjson
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAPJSON = os.path.join(REPO, "tools", "mapjson", "mapjson")


def make_map(map_id, name, layout="LAYOUT_A", **fields):
    data = {
        "id": map_id,
        "name": name,
        "layout": layout,
        "music": "MUS_NONE",
        "region_map_section": "MAPSEC_NONE",
        "requires_flash": False,
        "weather": "WEATHER_NONE",
        "map_type": "MAP_TYPE_ROUTE",
        "allow_cycling": True,
        "allow_escaping": False,
        "allow_running": True,
        "show_map_name": True,
        "battle_scene": "MAP_BATTLE_SCENE_NORMAL",
        "connections": None,
        "object_events": [],
        "warp_events": [],
        "coord_events": [],
        "bg_events": [],
    }
    data.update(fields)
    return data


def make_object(local_id=None):
    obj = {
        "graphics_id": "OBJ_EVENT_GFX_BOY_1",
        "x": 1,
        "y": 2,
        "elevation": 3,
        "movement_type": "MOVEMENT_TYPE_NONE",
        "movement_range_x": 0,
        "movement_range_y": 0,
        "trainer_type": "TRAINER_TYPE_NONE",
        "trainer_sight_or_berry_tree_id": "0",
        "script": "NULL",
        "flag": "0",
    }
    if local_id:
        obj["local_id"] = local_id
    return obj


def make_warp(warp_id=None):
    warp = {"x": 1, "y": 1, "elevation": 0, "dest_map": "MAP_A", "dest_warp_id": "0"}
    if warp_id:
        warp["warp_id"] = warp_id
    return warp


def make_layout(layout_id, name, folder, version="emerald"):
    return {
        "id": layout_id,
        "name": name,
        "width": 2,
        "height": 2,
        "primary_tileset": "gTileset_General",
        "secondary_tileset": "gTileset_Petalburg",
        "border_filepath": f"data/layouts/{folder}/border.bin",
        "blockdata_filepath": f"data/layouts/{folder}/map.bin",
        "layout_version": version,
    }


HEAL_LOCATIONS = {
    "heal_locations": [
        {
            "id": "HEAL_LOCATION_A",
            "map": "MAP_A",
            "x": 1,
            "y": 2,
            "respawn_map": "MAP_B",
            "respawn_npc": "LOCALID_B_NURSE",
            "respawn_x": 3,
            "respawn_y": 4,
        }
    ]
}


@unittest.skipUnless(os.path.exists(MAPJSON), "mapjson isn't built (make -C tools/mapjson)")
class MapjsonTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        self.maps = {
            "MapA": make_map("MAP_A", "MapA", connections=[{"map": "MAP_B", "offset": 0, "direction": "up"}]),
            "MapB": make_map("MAP_B", "MapB", object_events=[make_object("LOCALID_B_NURSE")]),
        }
        self.groups = {"group_order": ["gMapGroup_Test"], "gMapGroup_Test": ["MapA", "MapB"]}
        self.layouts = {"layouts_table_label": "gMapLayouts", "layouts": [make_layout("LAYOUT_A", "A_Layout", "A")]}
        self.heal_locations = json.dumps(HEAL_LOCATIONS, indent=2) + "\n"
        self.required = {"required_maps": [["MAP_A", 0], ["MAP_B", 0], ["MAP_REMOVED", 0]], "required_layouts": []}
        self.write_bin("A")

    def path(self, rel):
        return os.path.join(self.root, rel)

    def write(self, rel, text):
        os.makedirs(os.path.dirname(self.path(rel)), exist_ok=True)
        with open(self.path(rel), "w") as f:
            f.write(text)

    def read(self, rel):
        with open(self.path(rel)) as f:
            return f.read()

    def write_bin(self, folder, border=True, blockdata=True):
        if border:
            self.write(f"data/layouts/{folder}/border.bin", "")
        if blockdata:
            self.write(f"data/layouts/{folder}/map.bin", "")

    def write_tree(self):
        for name, data in self.maps.items():
            self.write(f"data/maps/{name}/map.json", json.dumps(data))
        self.write("data/maps/map_groups.json", json.dumps(self.groups))
        self.write("data/layouts/layouts.json", json.dumps(self.layouts))
        self.write("src/data/heal_locations.json", self.heal_locations)
        self.write("tools/mapjson/required_map_defines.json", json.dumps(self.required))
        os.makedirs(self.path("include/constants"), exist_ok=True)

    def map_files(self):
        return [f"data/maps/{name}/map.json" for name in self.maps]

    def run_mapjson(self, *args):
        return subprocess.run([MAPJSON, *args], cwd=self.root, capture_output=True, text=True)

    def run_layouts(self, version="emerald"):
        self.write_tree()
        return self.run_mapjson("layouts", version, "data/layouts/layouts.json", "data/layouts", "include/constants")

    def run_groups(self):
        self.write_tree()
        return self.run_mapjson("groups", "emerald", "data/maps/map_groups.json", *self.map_files(),
                                "data/maps", "include/constants")

    def run_map(self, name):
        self.write("include/constants/map_groups.h", "enum\n{\n    MAP_A = (0 | (0 << 8)),\n    MAP_B = (1 | (0 << 8)),\n};\n"
                   "#define MAP_REMOVED  2\n")
        self.write_tree()
        return self.run_mapjson("map", "emerald", f"data/maps/{name}/map.json", "data/layouts/layouts.json",
                                f"data/maps/{name}")

    def run_event_constants(self):
        self.write_tree()
        return self.run_mapjson("event_constants", "emerald", *self.map_files(), "include/constants/map_event_ids.h")

    def assert_fails(self, result, *messages):
        self.assertEqual(result.returncode, 1, result.stderr)
        for message in messages:
            self.assertIn(message, result.stderr)

    def assert_succeeds(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_valid_tree_builds(self):
        self.assert_succeeds(self.run_layouts())
        self.assert_succeeds(self.run_groups())
        self.assert_succeeds(self.run_event_constants())
        self.assert_succeeds(self.run_map("MapA"))
        self.assertEqual(self.read("src/data/heal_locations.json"), self.heal_locations)
        connections = self.read("data/maps/MapA/connections.inc")
        self.assertIn("\tconnection up, 0, MAP_B\n", connections)
        self.assertIn("\t.4byte 1\n", connections)
        self.assertIn("#define LOCALID_B_NURSE 1\n", self.read("include/constants/map_event_ids.h"))
        self.assertIn("#define LAYOUT_A 1\n", self.read("include/constants/layouts.h"))

    # Connections

    def test_connection_to_unknown_map_fails_and_writes_nothing(self):
        self.maps["MapA"]["connections"].append({"map": "MAP_ROUTE10l_TYPO", "offset": 0, "direction": "down"})
        self.assert_fails(self.run_map("MapA"), "MapA", "MAP_ROUTE10l_TYPO")
        for output in ("header.inc", "events.inc", "connections.inc"):
            self.assertFalse(os.path.exists(self.path(f"data/maps/MapA/{output}")), output)

    def test_connection_to_removed_required_map_is_dropped_from_the_count(self):
        self.maps["MapA"]["connections"].append({"map": "MAP_REMOVED", "offset": 0, "direction": "down"})
        self.assert_succeeds(self.run_map("MapA"))
        connections = self.read("data/maps/MapA/connections.inc")
        self.assertNotIn("MAP_REMOVED", connections)
        self.assertIn("\t.4byte 1\n", connections)

    # Heal locations

    def test_unknown_respawn_map_fails_and_leaves_heal_locations_alone(self):
        self.heal_locations = self.heal_locations.replace('"MAP_B"', '"MAP_B_TYPO"')
        self.assert_fails(self.run_groups(), "src/data/heal_locations.json", "MAP_B_TYPO")
        self.assertEqual(self.read("src/data/heal_locations.json"), self.heal_locations)
        self.assertEqual(os.listdir(self.path("include/constants")), [])
        self.assertFalse(os.path.exists(self.path("src/data/map_group_count.h")))
        self.assertFalse(os.path.exists(self.path("data/maps/groups.inc")))

    def test_removed_required_respawn_map_clears_its_npc(self):
        # Upstream's cleanup for a map taken out of map_groups.json: its LOCALID_ is gone with it.
        self.heal_locations = self.heal_locations.replace('"MAP_B"', '"MAP_REMOVED"')
        self.assert_succeeds(self.run_groups())
        self.assertIn('"respawn_npc": "0"', self.read("src/data/heal_locations.json"))

    def add_removed_map_location_without_npc(self):
        location = dict(HEAL_LOCATIONS["heal_locations"][0], id="HEAL_LOCATION_REMOVED", respawn_map="MAP_REMOVED")
        del location["respawn_npc"]
        data = json.loads(self.heal_locations)
        data["heal_locations"].insert(0, location)
        self.heal_locations = json.dumps(data, indent=2) + "\n"

    def test_removed_map_without_npc_leaves_the_next_npc_alone(self):
        self.add_removed_map_location_without_npc()
        self.assert_succeeds(self.run_groups())
        self.assertEqual(self.read("src/data/heal_locations.json"), self.heal_locations)

    def put_npc_before_map(self):
        # Each entry's respawn_npc before its respawn_map, as JSON allows (#301).
        data = json.loads(self.heal_locations)
        data["heal_locations"] = [{key: location[key] for key in sorted(location, key=lambda k: k != "respawn_npc")}
                                  for location in data["heal_locations"]]
        self.heal_locations = json.dumps(data, indent=2) + "\n"

    def test_removed_map_clears_its_own_npc_before_it(self):
        self.heal_locations = self.heal_locations.replace('"MAP_B"', '"MAP_REMOVED"')
        self.put_npc_before_map()
        expected = self.heal_locations.replace('"LOCALID_B_NURSE"', '"0"')
        self.assertLess(self.heal_locations.index('"respawn_npc"'), self.heal_locations.index('"respawn_map"'))
        self.assert_succeeds(self.run_groups())
        self.assertEqual(self.read("src/data/heal_locations.json"), expected)

    def test_removed_map_without_npc_leaves_the_next_npc_before_its_map_alone(self):
        self.add_removed_map_location_without_npc()
        self.put_npc_before_map()
        self.assert_succeeds(self.run_groups())
        self.assertEqual(self.read("src/data/heal_locations.json"), self.heal_locations)

    def test_removed_map_with_npc_before_it_leaves_the_previous_npc_alone(self):
        # The valid entry first, then a removed map's with its NPC before its map.
        location = dict(HEAL_LOCATIONS["heal_locations"][0], id="HEAL_LOCATION_REMOVED", respawn_map="MAP_REMOVED",
                        respawn_npc="LOCALID_REMOVED_NURSE")
        data = json.loads(self.heal_locations)
        data["heal_locations"].append(location)
        self.heal_locations = json.dumps(data, indent=2) + "\n"
        self.put_npc_before_map()
        expected = self.heal_locations.replace('"LOCALID_REMOVED_NURSE"', '"0"')
        self.assert_succeeds(self.run_groups())
        self.assertEqual(self.read("src/data/heal_locations.json"), expected)

    def test_heal_locations_formatting_is_kept(self):
        # Not json11's output: the cleanup edits the NPC's text in place.
        self.heal_locations = self.heal_locations.replace('"MAP_B"', '"MAP_REMOVED"').replace("  ", "\t")
        self.heal_locations = self.heal_locations.replace('"x": 1,\n', '"x": 1, "note": "a \\"respawn_npc\\": x",\n')
        expected = self.heal_locations.replace('"LOCALID_B_NURSE"', '"0"')
        self.assert_succeeds(self.run_groups())
        self.assertEqual(self.read("src/data/heal_locations.json"), expected)

    def test_respawn_map_after_a_removed_map_is_still_checked(self):
        self.add_removed_map_location_without_npc()
        self.heal_locations = self.heal_locations.replace('"MAP_B"', '"MAP_B_TYPO"')
        self.assert_fails(self.run_groups(), "MAP_B_TYPO")
        self.assertEqual(self.read("src/data/heal_locations.json"), self.heal_locations)

    # Layouts

    def test_missing_border_file_fails(self):
        os.remove(self.path("data/layouts/A/border.bin"))
        self.assert_fails(self.run_layouts(), "LAYOUT_A", "border_filepath", "data/layouts/A/border.bin")
        self.assertFalse(os.path.exists(self.path("include/constants/layouts.h")))

    def test_missing_blockdata_file_fails(self):
        os.remove(self.path("data/layouts/A/map.bin"))
        self.assert_fails(self.run_layouts(), "LAYOUT_A", "blockdata_filepath", "data/layouts/A/map.bin")
        self.assertFalse(os.path.exists(self.path("include/constants/layouts.h")))

    def test_other_version_layout_without_files_is_skipped(self):
        self.layouts["layouts"].insert(0, make_layout("LAYOUT_FRLG", "Frlg_Layout", "Frlg", version="frlg"))
        self.layouts["layouts"].append(make_layout("LAYOUT_B", "B_Layout", "B"))
        self.write_bin("B")
        self.assert_succeeds(self.run_layouts())
        constants = self.read("include/constants/layouts.h")
        self.assertNotIn("LAYOUT_FRLG", constants)
        self.assertIn("#define LAYOUT_A 1\n", constants)
        self.assertIn("#define LAYOUT_B 2\n", constants)
        # The same layout is this version's in a FireRed build, so its files are needed there.
        self.assert_fails(self.run_layouts("firered"), "LAYOUT_FRLG", "border_filepath")

    # Event IDs

    def test_local_id_with_two_values_fails(self):
        self.maps["MapA"]["object_events"] = [make_object(), make_object("LOCALID_B_NURSE")]
        self.assert_fails(self.run_event_constants(),
                          "LOCALID_B_NURSE is 2 as MAP_A's local_id but 1 as MAP_B's local_id")
        self.assertFalse(os.path.exists(self.path("include/constants/map_event_ids.h")))

    def test_warp_id_with_two_values_fails(self):
        self.maps["MapA"]["warp_events"] = [make_warp("WARP_ID_DOOR")]
        self.maps["MapB"]["warp_events"] = [make_warp(), make_warp("WARP_ID_DOOR")]
        self.assert_fails(self.run_event_constants(), "WARP_ID_DOOR is 0 as MAP_A's warp_id but 1 as MAP_B's warp_id")

    def test_shared_id_with_one_value_is_allowed(self):
        self.maps["MapA"]["object_events"] = [make_object("LOCALID_B_NURSE")]
        self.assert_succeeds(self.run_event_constants())
        self.assertEqual(self.read("include/constants/map_event_ids.h").count("#define LOCALID_B_NURSE 1\n"), 2)

    # Minor

    def test_non_integer_number_fails(self):
        self.layouts["layouts"][0]["width"] = 3.5
        self.assert_fails(self.run_layouts(), "'width'", "3.5")

    def test_number_past_the_int_range_fails(self):
        self.layouts["layouts"][0]["width"] = 3000000000
        self.assert_fails(self.run_layouts(), "'width'", "int range")

    def test_path_without_separator_works(self):
        self.write_tree()
        shutil.copy(self.path("data/layouts/layouts.json"), self.path("layouts.json"))
        self.assert_succeeds(self.run_mapjson("layouts", "emerald", "layouts.json", "data/layouts", "include/constants"))
        self.assertIn("A_Layout::\n", self.read("data/layouts/layouts.inc"))


if __name__ == "__main__":
    unittest.main()
