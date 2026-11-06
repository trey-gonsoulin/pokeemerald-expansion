// mapjson.cpp

#include <iostream>
using std::cout; using std::endl;

#include <string>
using std::string;

#include <vector>
using std::vector;

#include <algorithm>
using std::sort; using std::find;

#include <map>
using std::map;

#include <set>

#include <cmath>

#include <fstream>
using std::ofstream; using std::ifstream;

#include <sstream>
using std::ostringstream;

#include <limits>
using std::numeric_limits;

#include "json11.h"
using json11::Json;

#include <regex>

#include "mapjson.h"

#include <filesystem>

string version;
// System directory separator
string sep;
// Read and rewritten from the working directory (the repo root, where make runs mapjson)
const string HEAL_LOCATIONS_FILEPATH = "src/data/heal_locations.json";

string read_text_file(string filepath) {
    ifstream in_file(filepath);

    if (!in_file.is_open())
        FATAL_ERROR("Cannot open file %s for reading.\n", filepath.c_str());

    string text;

    in_file.seekg(0, std::ios::end);
    text.resize(in_file.tellg());

    in_file.seekg(0, std::ios::beg);
    in_file.read(&text[0], text.size());

    in_file.close();

    return text;
}

void write_text_file(string filepath, string text) {
    ofstream out_file(filepath, std::ofstream::binary);

    if (!out_file.is_open())
        FATAL_ERROR("Cannot open file %s for writing.\n", filepath.c_str());

    out_file << text;

    out_file.close();
}


string json_to_string(const Json &data, const string &field = "", bool silent = false) {
    const Json value = !field.empty() ? data[field] : data;
    string output = "";
    switch (value.type()) {
        case Json::Type::STRING:
            output = value.string_value();
            break;
        case Json::Type::NUMBER:
            // int_value() would cut 3.5 to 3, and casts a number past the int range out of range.
            if (std::trunc(value.number_value()) != value.number_value()
             || value.number_value() < numeric_limits<int>::min() || value.number_value() > numeric_limits<int>::max()) {
                string s = !field.empty() ? ("Value for '" + field + "'") : "JSON field";
                FATAL_ERROR("%s must be an integer in the int range, not %g.\n", s.c_str(), value.number_value());
            }
            output = std::to_string(value.int_value());
            break;
        case Json::Type::BOOL:
            output = value.bool_value() ? "TRUE" : "FALSE";
            break;
        case Json::Type::NUL:
            output = "";
            break;
        default:{
            if (!silent) {
                string s = !field.empty() ? ("Value for '" + field + "'") : "JSON field";
                FATAL_ERROR("%s is unexpected type; expected string, number, or bool.\n", s.c_str());
            }
        }
    }

    if (!silent && output.empty()) {
        string s = !field.empty() ? ("Value for '" + field + "'") : "JSON field";
        FATAL_ERROR("%s cannot be empty.\n", s.c_str());
    }

    return output;
}

string get_generated_warning(const string &filename, bool isAsm) {
    string comment = isAsm ? "@" : "//";

    ostringstream warning;
    warning << comment << "\n"
            << comment << " DO NOT MODIFY THIS FILE! It is auto-generated from " << filename << "\n"
            << comment << "\n\n";
    return warning.str();
}

string get_include_guard_start(const string &name) {
    ostringstream guard;
    guard << "#ifndef GUARD_" << name << "_H\n"
          << "#define GUARD_" << name << "_H\n\n";
    return guard.str();
}

string get_include_guard_end(const string &name) {
    ostringstream guard;
    guard << "#endif // GUARD_" << name << "_H\n";
    return guard.str();
}

string generate_map_header_text(Json map_data, Json layouts_data) {
    string map_layout_id = json_to_string(map_data, "layout");

    vector<Json> matched;

    for (auto &layout : layouts_data["layouts"].array_items()) {
        if (map_layout_id == json_to_string(layout, "id", true))
            matched.push_back(layout);
    }

    if (matched.size() != 1)
        FATAL_ERROR("Failed to find matching layout for %s.\n", map_layout_id.c_str());

    Json layout = matched[0];

    ostringstream text;

    string mapName = json_to_string(map_data, "name");
    text << get_generated_warning("data/maps/" + mapName + "/map.json", true);

    text << mapName << ":\n"
         << "\t.4byte " << json_to_string(layout, "name") << "\n";

    if (map_data.object_items().find("shared_events_map") != map_data.object_items().end())
        text << "\t.4byte " << json_to_string(map_data, "shared_events_map") << "_MapEvents\n";
    else
        text << "\t.4byte " << mapName << "_MapEvents\n";

    if (map_data.object_items().find("shared_scripts_map") != map_data.object_items().end())
        text << "\t.4byte " << json_to_string(map_data, "shared_scripts_map") << "_MapScripts\n";
    else
        text << "\t.4byte " << mapName << "_MapScripts\n";

    if (map_data.object_items().find("connections") != map_data.object_items().end()
     && map_data["connections"].array_items().size() > 0 && json_to_string(map_data, "connections_no_include", true) != "TRUE")
        text << "\t.4byte " << mapName << "_MapConnections\n";
    else
        text << "\t.4byte NULL\n";

    text << "\t.2byte " << json_to_string(map_data, "music") << "\n";

    text << "\t.2byte " << json_to_string(layout, "id") << "\n"
         << "\t.byte "  << json_to_string(map_data, "region_map_section") << "\n"
         << "\t.byte "  << json_to_string(map_data, "weather") << "\n"
         << "\t.byte "  << json_to_string(map_data, "map_type") << "\n";

    string floor_number = json_to_string(map_data, "floor_number", true);
    if (floor_number.empty())
        text << "\t.byte 0\n";
    else
        text << "\t.byte " << floor_number << "\n";

    if (!map_data["night_music"].is_null())
        text << "\t.2byte " << json_to_string(map_data, "night_music") << "\n";
    else
        text << "\t.2byte MUS_NONE\n";

    if (version == "ruby")
        text << "\t.byte " << json_to_string(map_data, "show_map_name") << "\n";
    else if (version == "emerald" || version == "firered")
    {
        text << "\tmap_header_flags "
             << "allow_cycling=" << json_to_string(map_data, "allow_cycling") << ", "
             << "allow_escaping=" << json_to_string(map_data, "allow_escaping") << ", "
             << "allow_running=" << json_to_string(map_data, "allow_running") << ", "
             << "show_map_name=" << json_to_string(map_data, "show_map_name") << ", ";
        if (map_data.object_items().find("write_specialvar_iseffect") != map_data.object_items().end())
            text << "write_specialvar_iseffect=" << json_to_string(map_data, "write_specialvar_iseffect") << ", ";
        else
            text  << "write_specialvar_iseffect=FALSE" << ", ";
        text << "requires_flash=" << json_to_string(map_data, "requires_flash") << "\n";
    }

     text << "\t.byte " << json_to_string(map_data, "battle_scene") << "\n\n";

    return text.str();
}

vector<string> get_existing_maps() {
    vector<string> v = {};
    string map_constants = read_text_file("include/constants/map_groups.h");

    std::regex map_regex("(MAP_\\w+)\\s+=\\s+\\(\\d+");

    for (std::smatch sm; regex_search(map_constants, sm, map_regex);)
    {
        v.push_back(sm[1]);
        map_constants = sm.suffix();
    }
    return v;
}

Json parse_required_map_defines(void);

// A map that required_map_defines.json lists keeps its MAP_ constant when it is taken out of
// map_groups.json, so references to it are dropped (connections) or cleaned (heal locations).
bool is_removed_required_map(const string &map_id) {
    static const std::set<string> required_maps = [] {
        std::set<string> ids;
        Json required_map_defines = parse_required_map_defines();
        for (auto &required_map : required_map_defines["required_maps"].array_items())
            ids.insert(json_to_string(required_map[0]));
        return ids;
    }();
    return required_maps.count(map_id) > 0;
}

string generate_map_connections_text(Json map_data) {
    if (map_data["connections"] == Json())
        return string("\n");

    string mapName = json_to_string(map_data, "name");

    vector<string> existing_maps = get_existing_maps();
    ostringstream text;
    text << get_generated_warning("data/maps/" + mapName + "/map.json", true);
    text << mapName << "_MapConnectionsList:\n";

    size_t count = 0;
    for (auto &connection : map_data["connections"].array_items()) {
        string map_id = json_to_string(connection, "map");
        auto it = find(existing_maps.begin(), existing_maps.end(), map_id);
        if (it == existing_maps.end()) {
            if (is_removed_required_map(map_id))
                continue;
            FATAL_ERROR("%s: connection to unknown map %s (not in include/constants/map_groups.h).\n", mapName.c_str(), map_id.c_str());
        }
        text << "\tconnection "
             << json_to_string(connection, "direction") << ", "
             << json_to_string(connection, "offset") << ", "
             << map_id << "\n";
        count++;
    }

    // src/fieldmap.c reads this many entries from the list.
    text << "\n" << mapName << "_MapConnections:\n"
         << "\t.4byte " << count << "\n"
         << "\t.4byte " << mapName << "_MapConnectionsList\n\n";

    return text.str();
}

string generate_map_events_text(Json map_data) {
    if (map_data.object_items().find("shared_events_map") != map_data.object_items().end())
        return string("\n");

    string mapName = json_to_string(map_data, "name");

    ostringstream text;
    text << get_generated_warning("data/maps/" + mapName + "/map.json", true);
    text << "\t.align 2\n\n";

    string objects_label, warps_label, coords_label, bgs_label;

    if (map_data["object_events"].array_items().size() > 0) {
        objects_label = mapName + "_ObjectEvents";
        text << objects_label << ":\n";
        for (unsigned int i = 0; i < map_data["object_events"].array_items().size(); i++) {
            auto obj_event = map_data["object_events"].array_items()[i];
            string type = json_to_string(obj_event, "type", true);

            // If no type field is present, assume it's a regular object event.
            if (type == "" || type == "object") {
                text << "\tobject_event " << i + 1 << ", "
                     << json_to_string(obj_event, "graphics_id") << ", "
                     << json_to_string(obj_event, "x") << ", "
                     << json_to_string(obj_event, "y") << ", "
                     << json_to_string(obj_event, "elevation") << ", "
                     << json_to_string(obj_event, "movement_type") << ", "
                     << json_to_string(obj_event, "movement_range_x") << ", "
                     << json_to_string(obj_event, "movement_range_y") << ", "
                     << json_to_string(obj_event, "trainer_type") << ", "
                     << json_to_string(obj_event, "trainer_sight_or_berry_tree_id") << ", "
                     << json_to_string(obj_event, "script") << ", "
                     << json_to_string(obj_event, "flag") << "\n";
            } else if (type == "clone") {
                text << "\tclone_event " << i + 1 << ", "
                     << json_to_string(obj_event, "graphics_id") << ", "
                     << json_to_string(obj_event, "x") << ", "
                     << json_to_string(obj_event, "y") << ", "
                     << json_to_string(obj_event, "target_local_id") << ", "
                     << json_to_string(obj_event, "target_map") << "\n";
            } else {
                FATAL_ERROR("Unknown object event type '%s'. Expected 'object' or 'clone'.\n", type.c_str());
            }
        }
        text << "\n";
    } else {
        objects_label = "NULL";
    }

    if (map_data["warp_events"].array_items().size() > 0) {
        warps_label = mapName + "_MapWarps";
        text << warps_label << ":\n";
        for (auto &warp_event : map_data["warp_events"].array_items()) {
            text << "\twarp_def "
                 << json_to_string(warp_event, "x") << ", "
                 << json_to_string(warp_event, "y") << ", "
                 << json_to_string(warp_event, "elevation") << ", "
                 << json_to_string(warp_event, "dest_warp_id") << ", "
                 << json_to_string(warp_event, "dest_map") << "\n";
        }
        text << "\n";
    } else {
        warps_label = "NULL";
    }

    if (map_data["coord_events"].array_items().size() > 0) {
        coords_label = mapName + "_MapCoordEvents";
        text << coords_label << ":\n";
        for (auto &coord_event : map_data["coord_events"].array_items()) {
            string type = json_to_string(coord_event, "type");
            if (type == "trigger") {
                text << "\tcoord_event "
                     << json_to_string(coord_event, "x") << ", "
                     << json_to_string(coord_event, "y") << ", "
                     << json_to_string(coord_event, "elevation") << ", "
                     << json_to_string(coord_event, "var") << ", "
                     << json_to_string(coord_event, "var_value") << ", "
                     << json_to_string(coord_event, "script") << "\n";
            }
            else if (type == "weather") {
                text << "\tcoord_weather_event "
                     << json_to_string(coord_event, "x") << ", "
                     << json_to_string(coord_event, "y") << ", "
                     << json_to_string(coord_event, "elevation") << ", "
                     << json_to_string(coord_event, "weather") << "\n";
            } else {
                FATAL_ERROR("Unknown coord event type '%s'. Expected 'trigger' or 'weather'.\n", type.c_str());
            }
        }
        text << "\n";
    } else {
        coords_label = "NULL";
    }

    if (map_data["bg_events"].array_items().size() > 0) {
        bgs_label = mapName + "_MapBGEvents";
        text << bgs_label << ":\n";
        for (auto &bg_event : map_data["bg_events"].array_items()) {
            string type = json_to_string(bg_event, "type");
            if (type == "sign") {
                text << "\tbg_sign_event "
                     << json_to_string(bg_event, "x") << ", "
                     << json_to_string(bg_event, "y") << ", "
                     << json_to_string(bg_event, "elevation") << ", "
                     << json_to_string(bg_event, "player_facing_dir") << ", "
                     << json_to_string(bg_event, "script") << "\n";
            }
            else if (type == "hidden_item") {
                string quantity = json_to_string(bg_event, "quantity", true);
                if (quantity.empty()) {
                    quantity = "1";
                }
                string underfoot = json_to_string(bg_event, "underfoot", true);
                if (underfoot.empty()) {
                    underfoot = "FALSE";
                }
                text << "\tbg_hidden_item_event "
                     << json_to_string(bg_event, "x") << ", "
                     << json_to_string(bg_event, "y") << ", "
                     << json_to_string(bg_event, "elevation") << ", "
                     << json_to_string(bg_event, "item") << ", "
                     << json_to_string(bg_event, "flag") << ", "
                     << quantity << ", "
                     << underfoot << "\n";
            }
            else if (type == "secret_base") {
                text << "\tbg_secret_base_event "
                     << json_to_string(bg_event, "x") << ", "
                     << json_to_string(bg_event, "y") << ", "
                     << json_to_string(bg_event, "elevation") << ", "
                     << json_to_string(bg_event, "secret_base_id") << "\n";
            } else {
                FATAL_ERROR("Unknown bg event type '%s'. Expected 'sign', 'hidden_item', or 'secret_base'.\n", type.c_str());
            }
        }
        text << "\n";
    } else {
        bgs_label = "NULL";
    }

    text << mapName << "_MapEvents::\n"
         << "\tmap_events " << objects_label << ", " << warps_label << ", "
         << coords_label << ", " << bgs_label << "\n\n";

    return text.str();
}

string strip_trailing_separator(string filename) {
    if(filename.back() == '/' || filename.back() == '\\')
        filename.pop_back();

    return filename;
}
void infer_separator(string filename) {
    size_t dir_pos = filename.find_last_of("/\\");
    sep = dir_pos == string::npos ? "/" : string(1, filename[dir_pos]);
}
string file_parent(string filename){
    size_t dir_pos = filename.find_last_of("/\\");
    return filename.substr(0, dir_pos + 1);
}

void process_map(string map_filepath, string layouts_filepath, string output_dir) {
    string mapdata_err, layouts_err;

    string mapdata_json_text = read_text_file(map_filepath);
    string layouts_json_text = read_text_file(layouts_filepath);

    Json map_data = Json::parse(mapdata_json_text, mapdata_err);
    if (map_data == Json())
        FATAL_ERROR("%s\n", mapdata_err.c_str());

    Json layouts_data = Json::parse(layouts_json_text, layouts_err);
    if (layouts_data == Json())
        FATAL_ERROR("%s\n", layouts_err.c_str());

    string header_text = generate_map_header_text(map_data, layouts_data);
    string events_text = generate_map_events_text(map_data);
    string connections_text = generate_map_connections_text(map_data);

    string out_dir = strip_trailing_separator(output_dir).append(sep);
    write_text_file(out_dir + "header.inc", header_text);
    write_text_file(out_dir + "events.inc", events_text);
    write_text_file(out_dir + "connections.inc", connections_text);
}

void process_event_constants(const vector<string> &map_filepaths, string output_ids_file) {
    string warning = get_generated_warning("data/maps/*/map.json", false);

    string guard_name = "CONSTANTS_MAP_EVENT_IDS";
    ostringstream ids_file_text;
    ids_file_text << get_include_guard_start(guard_name) << warning;

    // Two maps may share a name only for the same value: gcc only warns on a redefinition, and the later one wins.
    map<string, std::pair<unsigned int, string>> defined_ids;
    auto define_id = [&](ostringstream &text, const string &field, unsigned int value, const string &map_id, const Json &event) {
        string name = json_to_string(event, field);
        string where = map_id + "'s " + field;
        auto [it, inserted] = defined_ids.emplace(name, std::make_pair(value, where));
        if (!inserted && it->second.first != value)
            FATAL_ERROR("%s is %u as %s but %u as %s.\n", name.c_str(), it->second.first, it->second.second.c_str(), value, where.c_str());
        text << "#define " << name << " " << value << "\n";
    };

    for (const string &filepath : map_filepaths) {
        string err;
        string map_json_text = read_text_file(filepath);
        Json map_data = Json::parse(map_json_text, err);
        if (map_data == Json())
            FATAL_ERROR("Failed to read '%s' while generating map event constants: %s\n", filepath.c_str(), err.c_str());

        string map_id = json_to_string(map_data, "id");

        // Get IDs from the object/clone events.
        ostringstream map_ids_text;
        auto obj_events = map_data["object_events"].array_items();
        for (unsigned int i = 0; i < obj_events.size(); i++) {
            auto obj_event = obj_events[i];
            if (obj_event.object_items().find("local_id") != obj_event.object_items().end())
                define_id(map_ids_text, "local_id", i + 1, map_id, obj_event);
        }
        // Get IDs from the warp events.
        auto warp_events = map_data["warp_events"].array_items();
        for (unsigned int i = 0; i < warp_events.size(); i++) {
            auto warp_event = warp_events[i];
            if (warp_event.object_items().find("warp_id") != warp_event.object_items().end())
                define_id(map_ids_text, "warp_id", i, map_id, warp_event);
        }
        // Only output if we found any IDs
        string temp = map_ids_text.str();
        if (!temp.empty()) {
            ids_file_text << "// " << map_id << "\n" << temp << "\n";
        }
    }

    ids_file_text << get_include_guard_end(guard_name);
    write_text_file(output_ids_file, ids_file_text.str());
}

string generate_groups_text(Json groups_data, vector<string> &invalid_maps) {
    ostringstream text;

    text << get_generated_warning("data/maps/map_groups.json", true);

    vector<string> valid_groups;
    for (auto &key : groups_data["group_order"].array_items()) {
        string group = json_to_string(key);
        vector<string> valid_maps;
        auto maps = groups_data[group].array_items();
        for (Json &map_name : maps) {
            string map_name_str = json_to_string(map_name);
            auto it = find(invalid_maps.begin(), invalid_maps.end(), map_name_str);
            if (it == invalid_maps.end()) {
                valid_maps.push_back(map_name_str);
            }
        }

        if (valid_maps.size() > 0) {
            text << group << "::\n";
            for (string map : valid_maps)
                text << "\t.4byte " << map << "\n";
            text << "\n";
            valid_groups.push_back(group);
        }
    }

    text << "\t.align 2\n" << "gMapGroups::\n";
    for (auto &group : groups_data["group_order"].array_items()) {
        string group_str = json_to_string(group);
        if (find(valid_groups.begin(), valid_groups.end(), group_str) != valid_groups.end())
            text << "\t.4byte " << group_str << "\n";
        else
            text << "\t.4byte NULL\n";
    }
    text << "\n";

    return text.str();
}

string generate_connections_text(Json groups_data, vector<string> &invalid_maps, string include_path) {
    vector<Json> map_names;

    for (auto &group : groups_data["group_order"].array_items()) {
        for (auto map_name : groups_data[json_to_string(group)].array_items()) {
            string map_name_str = json_to_string(map_name);
            auto it = find(invalid_maps.begin(), invalid_maps.end(), map_name_str);
            if (it == invalid_maps.end())
                map_names.push_back(map_name);
        }
    }

    vector<Json> connections_include_order = groups_data["connections_include_order"].array_items();

    if (connections_include_order.size() > 0)
        // A map missing from the order sorts after every listed one (its position is the list's size), in map_groups order.
        std::stable_sort(map_names.begin(), map_names.end(), [connections_include_order](const Json &a, const Json &b) {
            auto pos_a = find(connections_include_order.begin(), connections_include_order.end(), a) - connections_include_order.begin();
            auto pos_b = find(connections_include_order.begin(), connections_include_order.end(), b) - connections_include_order.begin();
            return pos_a < pos_b;
        });

    ostringstream text;

    text << get_generated_warning("data/maps/map_groups.json", true);

    for (Json map_name : map_names)
        text << "\t.include \"" << include_path << "/" <<  json_to_string(map_name) << "/connections.inc\"\n";

    return text.str();
}

string generate_headers_text(Json groups_data, vector<string> &invalid_maps, string include_path) {
    vector<string> map_names;

    for (auto &group : groups_data["group_order"].array_items()) {
        for (auto map_name : groups_data[json_to_string(group)].array_items()) {
            string map_name_str = json_to_string(map_name);
            auto it = find(invalid_maps.begin(), invalid_maps.end(), map_name_str);
            if (it == invalid_maps.end())
                map_names.push_back(json_to_string(map_name));
        }
    }

    ostringstream text;

    text << get_generated_warning("data/maps/map_groups.json", true);

    for (string map_name : map_names)
        text << "\t.include \"" << include_path << "/" << map_name << "/header.inc\"\n";

    return text.str();
}

string generate_events_text(Json groups_data, vector<string> &invalid_maps, string include_path) {
    vector<string> map_names;

    for (auto &group : groups_data["group_order"].array_items()) {
        for (auto map_name : groups_data[json_to_string(group)].array_items()) {

            string map_name_str = json_to_string(map_name);
            auto it = find(invalid_maps.begin(), invalid_maps.end(), map_name_str);
            if (it == invalid_maps.end())
                map_names.push_back(json_to_string(map_name));
        }
    }

    ostringstream text;

    text << get_generated_warning(include_path + "/map_groups.json", true);

    for (string map_name : map_names)
        text << "\t.include \"" << include_path << "/" << map_name << "/events.inc\"\n";

    return text.str();
}

Json parse_required_map_defines(void) {
    string json_err;

    string json_text = read_text_file("tools/mapjson/required_map_defines.json");

    Json json_data = Json::parse(json_text, json_err);
    if (json_data == Json())
        FATAL_ERROR("%s\n", json_err.c_str());
    return json_data;
}

string generate_map_constants_text(string groups_filepath, Json groups_data, vector<string> &valid_map_ids, string &map_count_text) {
    string file_dir = file_parent(groups_filepath) + sep;

    string guard_name = "CONSTANTS_MAP_GROUPS";
    ostringstream text;
    ostringstream mapCountText;

    text << get_include_guard_start(guard_name) << get_generated_warning("data/maps/map_groups.json", false);

    text << "//\n// DO NOT MODIFY THIS FILE! It is auto-generated from data/maps/map_groups.json\n//\n\n";

    text << "enum\n{\n";

    int group_num = 0;
    vector<int> map_count_vec; //DEBUG
    for (auto &group : groups_data["group_order"].array_items()) {
        string groupName = json_to_string(group);
        text << "    // " << groupName << "\n";
        vector<string> map_ids;
        size_t max_length = 0;

        int map_count = 0; //DEBUG

        for (auto &map_name : groups_data[groupName].array_items()) {
            string map_filepath = file_dir + json_to_string(map_name) + sep + "map.json";
            string err_str;
            Json map_data = Json::parse(read_text_file(map_filepath), err_str);
            if (map_data == Json())
                FATAL_ERROR("%s: %s\n", map_filepath.c_str(), err_str.c_str());
            string id = json_to_string(map_data, "id", true);
            map_ids.push_back(id);
            valid_map_ids.push_back(id);
            if (id.length() > max_length)
                max_length = id.length();
            map_count++; //DEBUG
        }

        int map_id_num = 0;
        for (string map_id : map_ids) {
            text << "    " << map_id << string(max_length - map_id.length(), ' ')
                 << " = (" << map_id_num++ << " | (" << group_num << " << 8)),\n";
        }

        text << "\n";

        group_num++;
        map_count_vec.push_back(map_count); //DEBUG
    }

    text << "};\n\n";

    text << "//Constants for unused maps\n";
    int map_id_num = 0;
    int old_map_group = -1;
    Json required_map_defines = parse_required_map_defines();
    map <int, string> filtered_map_defines;
    size_t max_length = 0;
    for (auto required_map_id : required_map_defines["required_maps"].array_items()) {
        string map_id = json_to_string(required_map_id[0]);
        auto it = find(valid_map_ids.begin(), valid_map_ids.end(), map_id);
        int current_map_group = required_map_id[1].int_value();
        if (old_map_group != current_map_group) {
            map_id_num = 0;
        } else {
            map_id_num++;
        }
        if (it == valid_map_ids.end()) {
            filtered_map_defines[(map_id_num + 256 * current_map_group)] = map_id;
            if (map_id.length() > max_length)
                max_length = map_id.length();
        }
        old_map_group = current_map_group;
    }

    for ( const auto &[map_value, map_id]: filtered_map_defines) {
        text << "#define " << map_id << string(max_length - map_id.length(), ' ')
             << "  " << map_value << "\n";
    }

    text << "\n#define MAP_GROUPS_COUNT " << group_num << "\n\n";
    text << get_include_guard_end(guard_name);

    mapCountText << "static const u8 MAP_GROUP_COUNT[] = {"; //DEBUG
    for(int i=0; i<group_num; i++){                          //DEBUG
        mapCountText << map_count_vec[i] << ", ";            //DEBUG
    }                                                        //DEBUG
    mapCountText << "0};\n";                                 //DEBUG
    map_count_text = mapCountText.str(); // process_groups writes it with the other outputs

    return text.str();
}

// The text span (between the quotes) of each heal location's respawn_npc string, or npos for an
// entry without one, in the order of the "heal_locations" array. json11 keeps no positions, so
// this scans the text, which json11 has already parsed: strings, and the nesting of {} and [].
static vector<std::pair<size_t, size_t>> find_respawn_npc_values(const string &text)
{
    vector<std::pair<size_t, size_t>> spans; // start and length
    vector<char> nesting;
    bool in_locations = false; // in the "heal_locations" array
    bool expect_key = false;   // the next string in an entry is a key
    string last_string, key;
    for (size_t i = 0; i < text.size(); i++) {
        char c = text[i];
        if (c == '"') {
            size_t start = ++i;
            while (i < text.size() && text[i] != '"')
                i += text[i] == '\\' ? 2 : 1;
            last_string = text.substr(start, i - start);
            if (in_locations && nesting.size() == 3) {
                if (expect_key)
                    key = last_string;
                else if (key == "respawn_npc")
                    spans.back() = {start, i - start};
            }
        } else if (c == '{' || c == '[') {
            if (c == '[' && nesting.size() == 1 && last_string == "heal_locations")
                in_locations = true;
            nesting.push_back(c);
            if (in_locations && nesting.size() == 3) {
                spans.push_back({string::npos, 0});
                expect_key = true;
            }
        } else if (c == '}' || c == ']') {
            nesting.pop_back();
            if (nesting.size() == 1)
                in_locations = false;
        } else if (in_locations && nesting.size() == 3) {
            if (c == ',')
                expect_key = true;
            else if (c == ':')
                expect_key = false;
        }
    }
    return spans;
}

// Returns heal_locations.json with the respawn NPC of each respawn map taken out of map_groups.json
// set to 0 (its LOCALID_ is gone with the map), for process_groups to write once every output is ready.
// Each entry's own respawn_map decides its own respawn_npc, whatever the order of the keys, and the
// rest of the text is left as it is.
string clean_heal_locations(vector<string> &valid_map_ids)
{
    string text = read_text_file(HEAL_LOCATIONS_FILEPATH);
    string err;
    Json data = Json::parse(text, err);
    if (data == Json())
        FATAL_ERROR("%s: %s\n", HEAL_LOCATIONS_FILEPATH.c_str(), err.c_str());
    const auto &locations = data["heal_locations"].array_items();

    vector<std::pair<size_t, size_t>> npc_spans = find_respawn_npc_values(text);
    if (npc_spans.size() != locations.size())
        FATAL_ERROR("%s: found %zu heal locations in the text, but the JSON has %zu.\n",
                    HEAL_LOCATIONS_FILEPATH.c_str(), npc_spans.size(), locations.size());

    vector<std::pair<size_t, size_t>> cleared_spans;
    for (size_t i = 0; i < locations.size(); i++) {
        const Json &respawn_map = locations[i]["respawn_map"];
        if (!respawn_map.is_string())
            continue;
        string map_id = respawn_map.string_value();
        if (find(valid_map_ids.begin(), valid_map_ids.end(), map_id) != valid_map_ids.end())
            continue;
        // Anything else is a typo, which would lose the NPC ID for good.
        if (!is_removed_required_map(map_id))
            FATAL_ERROR("%s: unknown respawn_map %s (not in data/maps/map_groups.json or tools/mapjson/required_map_defines.json).\n",
                        HEAL_LOCATIONS_FILEPATH.c_str(), map_id.c_str());
        if (npc_spans[i].first != string::npos)
            cleared_spans.push_back(npc_spans[i]);
    }

    // Backwards, so each edit leaves the earlier positions alone.
    std::regex npc_regex("LOCALID_\\w+");
    for (auto it = cleared_spans.rbegin(); it != cleared_spans.rend(); ++it)
        text.replace(it->first, it->second, std::regex_replace(text.substr(it->first, it->second), npc_regex, "0"));

    return text;
}

// Map and group name strings for the debug menu's Warp, indexed like gMapGroups:
// a group with no map in this version's region is NULL, and its maps are skipped as in groups.inc.
// sDebugMapNameCounts has each group's name count, so a lookup is bounded by the names listed here.
string generate_debug_map_names_text(Json groups_data, vector<string> &invalid_maps) {
    const string group_prefix = "gMapGroup_";
    ostringstream text;
    ostringstream group_names;
    ostringstream group_maps;
    ostringstream group_counts;

    text << get_generated_warning("data/maps/map_groups.json", false);

    for (auto &key : groups_data["group_order"].array_items()) {
        string group = json_to_string(key);
        string short_name = group.compare(0, group_prefix.length(), group_prefix) == 0 ? group.substr(group_prefix.length()) : group;
        vector<string> valid_maps;
        for (auto &map_name : groups_data[group].array_items()) {
            string map_name_str = json_to_string(map_name);
            if (find(invalid_maps.begin(), invalid_maps.end(), map_name_str) == invalid_maps.end())
                valid_maps.push_back(map_name_str);
        }

        group_names << "    COMPOUND_STRING(\"" << short_name << "\"),\n";
        group_counts << "    " << valid_maps.size() << ",\n";
        if (valid_maps.size() > 0) {
            text << "static const u8 *const sDebugMapNames_" << short_name << "[] = {\n";
            for (string map : valid_maps)
                text << "    COMPOUND_STRING(\"" << map << "\"),\n";
            text << "};\n\n";
            group_maps << "    sDebugMapNames_" << short_name << ",\n";
        } else {
            group_maps << "    NULL,\n";
        }
    }

    text << "static const u8 *const sDebugMapGroupNames[] = {\n" << group_names.str() << "};\n\n";
    text << "static const u8 *const *const sDebugMapNames[] = {\n" << group_maps.str() << "};\n\n";
    text << "static const u8 sDebugMapNameCounts[] = {\n" << group_counts.str() << "};\n";
    return text.str();
}

// Output paths are directories with trailing path separators
void process_groups(string groups_filepath, vector<string> &map_filepaths, string output_asm, string output_c) {
    output_asm = strip_trailing_separator(output_asm); // Remove separator if existing.
    output_c = strip_trailing_separator(output_c);

    string err;
    Json groups_data = Json::parse(read_text_file(groups_filepath), err);
    vector<string> invalid_maps;
    vector<string> valid_map_ids;

    for (const string &filepath : map_filepaths) {
        string err;
        string map_json_text = read_text_file(filepath);
        Json map_data = Json::parse(map_json_text, err);
        if (map_data == Json())
            FATAL_ERROR("Failed to read '%s' while processing groups: %s\n", filepath.c_str(), err.c_str());

        string region = json_to_string(map_data, "region", true);

        if (region.empty()) {
            if (version == "emerald")
                region = "REGION_HOENN";
            else if (version == "firered")
                region = "REGION_KANTO";
        }
        string map_name = json_to_string(map_data, "name");

        if ((version == "emerald" && region != "REGION_HOENN")
         || (version == "firered" && region != "REGION_KANTO")) {
            invalid_maps.push_back(map_name);
        }
    }

    if (groups_data == Json())
        FATAL_ERROR("%s\n", err.c_str());

    string groups_text = generate_groups_text(groups_data, invalid_maps);
    string connections_text = generate_connections_text(groups_data, invalid_maps, output_asm);
    string headers_text = generate_headers_text(groups_data, invalid_maps, output_asm);
    string events_text = generate_events_text(groups_data, invalid_maps, output_asm);
    string map_count_text;
    string map_header_text = generate_map_constants_text(groups_filepath, groups_data, valid_map_ids, map_count_text);
    string debug_map_names_text = generate_debug_map_names_text(groups_data, invalid_maps);
    string heal_locations_text = clean_heal_locations(valid_map_ids);

    // Nothing is written until every output is ready, and the tracked heal_locations.json goes last,
    // so an error leaves it as it was.
    string data_dir = file_parent(groups_filepath) + sep + ".." + sep + ".." + sep + "src" + sep + "data" + sep;
    write_text_file(output_asm + sep + "groups.inc", groups_text);
    write_text_file(output_asm + sep + "connections.inc", connections_text);
    write_text_file(output_asm + sep + "headers.inc", headers_text);
    write_text_file(output_asm + sep + "events.inc", events_text);
    write_text_file(output_c + sep + "map_groups.h", map_header_text);
    write_text_file(data_dir + "map_group_count.h", map_count_text);
    // Next to map_group_count.h, which the debug menu reads too
    write_text_file(data_dir + "debug_map_names.h", debug_map_names_text);
    write_text_file(HEAL_LOCATIONS_FILEPATH, heal_locations_text);
}

// Whether a layout goes in the layout outputs. All three skip the same layouts, so the LAYOUT_ IDs
// match the table. A layout of another version is skipped when its border file is missing (a
// checkout without that version's layouts), but one of this version needs both of its files:
// skipping it shifts every later ID and leaves its map's header pointing at a label never written.
bool is_layout_included(const Json &layout) {
    string layout_version = json_to_string(layout, "layout_version", true);
    bool other_version = (version == "emerald" && !layout_version.empty() && layout_version != "emerald")
                      || (version == "firered" && !layout_version.empty() && layout_version != "frlg");
    if (other_version)
        return std::filesystem::exists(json_to_string(layout, "border_filepath"));

    for (const string field : {"border_filepath", "blockdata_filepath"}) {
        string filepath = json_to_string(layout, field);
        if (!std::filesystem::exists(filepath))
            FATAL_ERROR("Layout %s: %s %s doesn't exist.\n", json_to_string(layout, "id", true).c_str(), field.c_str(), filepath.c_str());
    }
    return true;
}

string generate_layout_headers_text(Json layouts_data) {
    ostringstream text;

    text << get_generated_warning("data/layouts/layouts.json", true);

    for (auto &layout : layouts_data["layouts"].array_items()) {
        if (layout == Json::object()) continue;
        if (!is_layout_included(layout))
            continue;
        string layout_version = json_to_string(layout, "layout_version", true);

        if (layout_version.empty()) {
            if (version == "emerald")
                layout_version = "emerald";
            else if (version == "firered")
                layout_version = "frlg";
        }
        if ((version == "emerald" && layout_version != "emerald")
         || (version == "firered" && layout_version != "frlg"))
            continue;
        string layoutName = json_to_string(layout, "name");
        string border_label = layoutName + "_Border";
        string blockdata_label = layoutName + "_Blockdata";
        text << border_label << "::\n"
             << "\t.incbin \"" << json_to_string(layout, "border_filepath") << "\"\n\n"
             << blockdata_label << "::\n"
             << "\t.incbin \"" << json_to_string(layout, "blockdata_filepath") << "\"\n\n"
             << "\t.align 2\n"
             << layoutName << "::\n"
             << "\t.4byte " << json_to_string(layout, "width") << "\n"
             << "\t.4byte " << json_to_string(layout, "height") << "\n"
             << "\t.4byte " << border_label << "\n"
             << "\t.4byte " << blockdata_label << "\n"
             << "\t.4byte " << json_to_string(layout, "primary_tileset") << "\n"
             << "\t.4byte " << json_to_string(layout, "secondary_tileset") << "\n";
        if (layout_version == "frlg")
            text << "\t.byte TRUE\n";
        else
            text << "\t.byte FALSE\n";

        if (layout_version == "frlg")
        {
            text << "\t.byte " << json_to_string(layout, "border_width") << "\n"
                 << "\t.byte " << json_to_string(layout, "border_height") << "\n"
                 << "\t.byte 0\n";
        }
        else
        {
            text << "\t.2byte 0\n"
                 << "\t.byte 0\n";
        }
        text << "\n";
    }

    return text.str();
}

string generate_layouts_table_text(Json layouts_data) {
    ostringstream text;

    text << get_generated_warning("data/layouts/layouts.json", true);

    text << "\t.align 2\n"
         << json_to_string(layouts_data, "layouts_table_label") << "::\n";

    for (auto &layout : layouts_data["layouts"].array_items()) {
        if (!is_layout_included(layout))
            continue;
        string layout_version = json_to_string(layout, "layout_version", true);
        if (layout_version.empty()) {
            if (version == "emerald")
                layout_version = "emerald";
            else if (version == "firered")
                layout_version = "frlg";
        }
        if ((version == "emerald" && layout_version != "emerald") || (version == "firered" && layout_version != "frlg")) {
            text << "\t.4byte NULL\n";
        } else {
            string layout_name = json_to_string(layout, "name", true);
            if (layout_name.empty()) layout_name = "NULL";
            text << "\t.4byte " << layout_name << "\n";
        }
    }

    return text.str();
}

vector<string> parse_required_layout_defines()
{
    vector<string> v;
    string json_err;

    string json_text = read_text_file("tools/mapjson/required_map_defines.json");

    Json json_data = Json::parse(json_text, json_err);
    if (json_data == Json())
        FATAL_ERROR("%s\n", json_err.c_str());

    for (auto required_layout : json_data["required_layouts"].array_items()) {
        v.push_back(json_to_string(required_layout));
    }

    return v;
}
string generate_layouts_constants_text(Json layouts_data) {
    string guard_name = "CONSTANTS_LAYOUTS";
    ostringstream text;
    vector<string> defined_layouts;
    text << get_include_guard_start(guard_name) << get_generated_warning("data/layouts/layouts.json", false);

    int i = 1;
    for (auto &layout : layouts_data["layouts"].array_items()) {
        if (!is_layout_included(layout))
            continue;
        if (layout != Json::object())
        {
            text << "#define " << json_to_string(layout, "id") << " " << i << "\n";
            defined_layouts.push_back(json_to_string(layout, "id"));
        }
        i++;
    }

    text << "\n//Constants for unused layouts\n";
    vector<string> required_layout_defines = parse_required_layout_defines();
    vector<string> filtered_layout_defines;
    size_t max_length = 0;
    for (auto &layout : required_layout_defines) {
        auto it = find(defined_layouts.begin(), defined_layouts.end(), layout);
        if (it == defined_layouts.end()) {
            filtered_layout_defines.push_back(layout);
            if (layout.length() > max_length)
                max_length = layout.length();
        }
    }

    for (auto &layout : filtered_layout_defines) {
        text << "#define " << layout << string(max_length - layout.length(), ' ')
             << "  0xFFFF\n";
    }
    text << "\n" << get_include_guard_end(guard_name);

    return text.str();
}

void process_layouts(string layouts_filepath, string output_asm, string output_c) {
    output_asm = strip_trailing_separator(output_asm).append(sep);
    output_c = strip_trailing_separator(output_c).append(sep);

    string err;
    Json layouts_data = Json::parse(read_text_file(layouts_filepath), err);

    if (layouts_data == Json())
        FATAL_ERROR("%s\n", err.c_str());

    string layout_headers_text = generate_layout_headers_text(layouts_data);
    string layouts_table_text = generate_layouts_table_text(layouts_data);
    string layouts_constants_text = generate_layouts_constants_text(layouts_data);

    write_text_file(output_asm + "layouts.inc", layout_headers_text);
    write_text_file(output_asm + "layouts_table.inc", layouts_table_text);
    write_text_file(output_c + "layouts.h", layouts_constants_text);
}

int main(int argc, char *argv[]) {
    if (argc < 3)
        FATAL_ERROR("USAGE: mapjson <mode> <game-version> [options]\n");

    char *version_arg = argv[2];
    version = string(version_arg);
    if (version != "emerald" && version != "ruby" && version != "firered")
        FATAL_ERROR("ERROR: <game-version> must be 'emerald', 'firered', or 'ruby'.\n");

    char *mode_arg = argv[1];
    string mode(mode_arg);
    if (mode == "map") {
        if (argc != 6)
            FATAL_ERROR("USAGE: mapjson map <game-version> <map_file> <layouts_file> <output_dir>\n");

        infer_separator(argv[3]);
        string filepath(argv[3]);
        string layouts_filepath(argv[4]);
        string output_dir(argv[5]);

        process_map(filepath, layouts_filepath, output_dir);
    }
    else if (mode == "groups") {
        if (argc < 6)
            FATAL_ERROR("USAGE: mapjson groups <game-version> <groups_file> <map_file> [additional_map_files] <output_asm_dir> <output_c_dir>\n");

        infer_separator(argv[3]);
        string filepath(argv[3]);

        vector<string> map_filepaths;
        const int firstMapFileArg = 4;
        const int lastMapFileArg = argc - 3;
        for (int i = firstMapFileArg; i <= lastMapFileArg; i++) {
            map_filepaths.push_back(argv[i]);
        }

        string output_asm(argv[argc - 2]);
        string output_c(argv[argc - 1]);

        process_groups(filepath, map_filepaths, output_asm, output_c);
    }
    else if (mode == "layouts") {
        if (argc != 6)
            FATAL_ERROR("USAGE: mapjson layouts <game-version> <layouts_file> <output_asm_dir> <output_c_dir>\n");

        infer_separator(argv[3]);
        string filepath(argv[3]);
        string output_asm(argv[4]);
        string output_c(argv[5]);

        process_layouts(filepath, output_asm, output_c);
    }
    else if (mode == "event_constants") {
        if (argc < 5)
            FATAL_ERROR("USAGE: mapjson event_constants <game-version> <map_file> [additional_map_files] <output_ids_file>");

        infer_separator(argv[3]);

        vector<string> filepaths;
        const int firstMapFileArg = 3;
        const int lastMapFileArg = argc - 2;
        for (int i = firstMapFileArg; i <= lastMapFileArg; i++) {
            filepaths.push_back(argv[i]);
        }
        string output_ids_file(argv[argc - 1]);

        process_event_constants(filepaths, output_ids_file);
    }
    else {
        FATAL_ERROR("ERROR: <mode> must be 'layouts', 'map', 'event_constants', or 'groups'.\n");
    }

    return 0;
}
