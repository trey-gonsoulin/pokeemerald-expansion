import json
import re
import sys

# The keys each object of wild_encounters.json must have, and the others it may have.
# An encounter's are built in ValidateEncounters: base_label, "map" in a group with
# for_maps, and one key per field type (land_mons, water_mons, ...).
GROUP_KEYS = ({"label", "encounters"}, {"for_maps", "fields"})
FIELD_KEYS = ({"type", "encounter_rates"}, {"groups"})
MONS_ENTRY_KEYS = ({"encounter_rate", "mons"}, set())
MON_KEYS = ({"species"}, {"min_level", "max_level"})

DEFAULT_MIN_LEVEL = 2
MIN_LEVEL = 1
MAX_LEVEL = 100
MAX_ENCOUNTER_RATE = 255 # struct WildPokemonInfo's u8 encounterRate
# A field's encounter_rates (each group's, in a field with groups) are percentages. The
# fishing picker draws one number for every rod, so a group that falls short misses slots.
RATES_TOTAL = 100
VERSION_SUFFIXES = {"_FireRed": "FIRERED", "_LeafGreen": "LEAFGREEN"}


class WildEncountersError(Exception):
    pass


def CheckKeys(obj, required, optional, where):
    missing = sorted(required - set(obj))
    if missing:
        raise WildEncountersError(f"{where}: missing key(s) {', '.join(missing)}")
    unknown = sorted(set(obj) - required - optional)
    if unknown:
        raise WildEncountersError(f"{where}: unknown key(s) {', '.join(unknown)}")


def CheckInt(value, low, high, what, where):
    if type(value) is not int or not low <= value <= high:
        raise WildEncountersError(f"{where}: {what} is {value!r}, expected {low} to {high}")


def CheckRates(rates, slots, where):
    for slot in slots:
        CheckInt(rates[slot], 0, RATES_TOTAL, f"encounter_rates[{slot}]", where)
    total = sum(rates[slot] for slot in slots)
    if total != RATES_TOTAL:
        raise WildEncountersError(f"{where}: encounter_rates add up to {total}, expected {RATES_TOTAL}")


def CheckGroups(field, where):
    """Each slot in exactly one group, each group's slots consecutive (WriteMacros sums
    them in order), and each group's rates adding up to RATES_TOTAL."""
    slot_count = len(field["encounter_rates"])
    slot_groups = {}
    for name, slots in field["groups"].items():
        group_where = f"{where} group {name}"
        if not slots:
            raise WildEncountersError(f"{group_where}: no slots")
        for slot in slots:
            CheckInt(slot, 0, slot_count - 1, "slot index", group_where)
            if slot in slot_groups:
                raise WildEncountersError(f"{group_where}: slot {slot} is also in group {slot_groups[slot]}")
            slot_groups[slot] = name
        if slots != list(range(slots[0], slots[0] + len(slots))):
            raise WildEncountersError(f"{group_where}: slots {slots} aren't consecutive")
        CheckRates(field["encounter_rates"], slots, group_where)
    ungrouped = [str(slot) for slot in range(slot_count) if slot not in slot_groups]
    if ungrouped:
        raise WildEncountersError(f"{where}: slot(s) {', '.join(ungrouped)} in no group")


def ValidateEncounters(json_data):
    """Raise WildEncountersError on data the header would carry silently wrong: a
    table whose slot count differs from its field's encounter_rates, encounter_rates
    that don't add up to RATES_TOTAL, a bad groups index, an unknown key, a missing
    key, a level outside 1-100 or above max_level, or an encounter rate past a u8."""
    slot_counts = {}
    for group in json_data["wild_encounter_groups"]:
        CheckKeys(group, *GROUP_KEYS, group.get("label", "wild encounter group"))
        for field in group.get("fields", []):
            field_where = f"{group['label']} field {field.get('type')}"
            CheckKeys(field, *FIELD_KEYS, field_where)
            if "groups" in field:
                CheckGroups(field, field_where)
            else:
                CheckRates(field["encounter_rates"], range(len(field["encounter_rates"])), field_where)
            slot_count = len(field["encounter_rates"])
            if slot_counts.setdefault(field["type"], slot_count) != slot_count:
                raise WildEncountersError(f"{group['label']} field {field['type']}: {slot_count} encounter_rates, but another group's has {slot_counts[field['type']]}")

    for group in json_data["wild_encounter_groups"]:
        required = {"base_label", "map"} if group.get("for_maps") else {"base_label"}
        for idx, map_encounters in enumerate(group["encounters"]):
            where = map_encounters.get("base_label", f"{group['label']} encounter {idx}")
            CheckKeys(map_encounters, required, {"map"} | slot_counts.keys(), where)
            for mon_type, slot_count in slot_counts.items():
                if mon_type not in map_encounters:
                    continue
                mons_entry = map_encounters[mon_type]
                type_where = f"{where} {mon_type}"
                CheckKeys(mons_entry, *MONS_ENTRY_KEYS, type_where)
                CheckInt(mons_entry["encounter_rate"], 0, MAX_ENCOUNTER_RATE, "encounter_rate", type_where)
                mons = mons_entry["mons"]
                if len(mons) != slot_count:
                    raise WildEncountersError(f"{type_where}: {len(mons)} mons, but the {mon_type} field has {slot_count} encounter_rates")
                for slot, mon in enumerate(mons):
                    mon_where = f"{type_where} slot {slot}"
                    CheckKeys(mon, *MON_KEYS, mon_where)
                    min_level = mon.get("min_level", DEFAULT_MIN_LEVEL)
                    max_level = mon.get("max_level", MAX_LEVEL)
                    CheckInt(max_level, MIN_LEVEL, MAX_LEVEL, "max_level", mon_where)
                    CheckInt(min_level, MIN_LEVEL, max_level, "min_level", mon_where)


def SplitTimeOfDay(base_label, times_of_day, time_fallback):
    """The label without its time-of-day suffix (_Morning, _Day, ...) and that
    time, or the label and the fallback time when it has no such suffix."""
    for time_ident, suffix in times_of_day.items():
        if base_label.endswith("_" + suffix):
            return base_label[:-len("_" + suffix)], time_ident
    return base_label, time_fallback


def GetLabelVersion(shared_label):
    """The game a label's encounters are for, from its _FireRed or _LeafGreen suffix."""
    for suffix, version in VERSION_SUFFIXES.items():
        if shared_label.endswith(suffix):
            return version
    return "EMERALD"


def ValidateLabels(json_data, times_of_day, time_fallback):
    """Raise WildEncountersError when two encounters of a group share a label and time
    of day, or two times of one label name different maps: WriteEncounters would keep
    only the later one's tables, or map, in the header."""
    for group in json_data["wild_encounter_groups"]:
        label_times = {}
        label_maps = {}
        for map_encounters in group["encounters"]:
            where = map_encounters["base_label"]
            shared_label, time = SplitTimeOfDay(where, times_of_day, time_fallback)
            if (shared_label, time) in label_times:
                raise WildEncountersError(f"{where}: same label and time of day as {label_times[shared_label, time]} ({shared_label}, {time})")
            label_times[shared_label, time] = where
            map_name = map_encounters.get("map")
            first_map, first_where = label_maps.setdefault(shared_label, (map_name, where))
            if map_name != first_map:
                raise WildEncountersError(f"{where}: map {map_name}, but {first_where} has {first_map}")

class Config:
    def __init__(self, config_file_name, rtc_constants_file_name, encounters_json_data):
        self.times_of_day = None
        self.mon_types = None
        self.time_encounters = None
        self.disable_time_fallback = None
        self.time_fallback = None

        self.ParseTimeEnum(rtc_constants_file_name)
        if self.times_of_day == None:
            raise Exception(f"Failed to parse 'enum TimeOfDay' in '{rtc_constants_file_name}'")

        self.ParseMonTypes(encounters_json_data)
        if self.mon_types == None:
            raise Exception("No fields defined in 'wild_encounters.json'")

        with open(config_file_name, 'r') as config_file:
            lines = config_file.readlines()
            for line in lines:
                self.ParseTimeConfig(line)
        
        if self.time_encounters == None:
            raise Exception("OW_TIME_OF_DAY_ENCOUNTERS not defined.")
        if self.disable_time_fallback == None:
            raise Exception("OW_TIME_OF_DAY_DISABLE_FALLBACK not defined.")
        if self.time_fallback == None:
            raise Exception("OW_TIME_OF_DAY_FALLBACK not defined.")
    
    def ParseTimeEnum(self, rtc_constants_file_name):
        with open(rtc_constants_file_name, 'r') as rtc_constants_file:
            DEFAULT_TIME_PAT = re.compile(r"enum\s+TimeOfDay\s*\{(?P<rtc_val>[\s*\w+,\=\d*]+)\s*\}\s*\;")
            file = rtc_constants_file.read()

            m = DEFAULT_TIME_PAT.search(file)
            if m:
                txt = m.group('rtc_val')
                values = re.findall(r'TIME_\w+', txt)
                self.times_of_day = {}
                for value in values:
                    self.times_of_day[value] = value.title().replace("Time_", "").replace("_", "")

    def ParseMonTypes(self, encounters_json_data):
        for group in encounters_json_data["wild_encounter_groups"]:
            if "fields" in group:
                for field in group["fields"]:
                    field_type = field["type"]
                    if not self.mon_types:
                        self.mon_types = []
                    self.mon_types.append(field_type)

    def ParseTimeConfig(self, line):
        m = re.search(r'#define OW_TIME_OF_DAY_ENCOUNTERS\s+(\w+)', line)
        if m:
            self.time_encounters = m.group(1) == "TRUE"

        m = re.search(r'#define OW_TIME_OF_DAY_DISABLE_FALLBACK\s+(\w+)', line)
        if m:
            self.disable_time_fallback = m.group(1) == "TRUE"

        m = re.search(r'#define OW_TIME_OF_DAY_FALLBACK\s+(\w+)', line)
        if m:
            self.time_fallback = m.group(1)


class WildEncounterAssembler:
    def __init__(self, output_file, json_data, config):
        self.output_file = output_file
        self.json_data = json_data
        self.config = config
    
    def WriteLine(self, line="", indents = 0):
        self.output_file.write(4 * indents * " " + line + "\n")

    def WriteHeader(self):
        self.WriteLine("//")
        self.WriteLine("// DO NOT MODIFY THIS FILE! It is auto-generated by tools/wild_encounters/wild_encounters_to_header.py")
        self.WriteLine("//")
        self.output_file.write("\n\n")

    def WriteMacro(self, macro, value):
        self.output_file.write("#define " + macro + " " + value + "\n")

    def WriteMacros(self):
        wild_encounter_groups = self.json_data["wild_encounter_groups"]
        for wild_encounter_group in wild_encounter_groups:
            if "fields" in wild_encounter_group:
                fields = wild_encounter_group["fields"]
                for field in fields:
                    field_type = field["type"]
                    macro_base = "ENCOUNTER_CHANCE_" + field_type.upper()
                    previous_group = None
                    previous_macro = None
                    encounter_rates = field["encounter_rates"]

                    group_name_mapping = len(encounter_rates) * [""]
                    if "groups" in field:
                        groups = field["groups"]
                        for group_name, indices in groups.items():
                            for index in indices:
                                group_name_mapping[index] = "_" + group_name.upper()
                    
                    for idx, rate in enumerate(encounter_rates):
                        macro_name = macro_base + group_name_mapping[idx] + "_SLOT_" + str(idx)
                        macro_value = str(rate)
                        if previous_group == group_name_mapping[idx]:
                            macro_value = "(" + previous_macro + " + " + macro_value + ")"
                        elif idx > 0:
                            macro_total_name = macro_base + group_name_mapping[idx - 1] + "_TOTAL"
                            self.WriteMacro(macro_total_name, "(" + previous_macro + ")")
                        self.WriteMacro(macro_name, macro_value)
                        previous_group = group_name_mapping[idx]
                        previous_macro = macro_name
                        if idx == len(encounter_rates) - 1:
                            macro_total_name = macro_base + group_name_mapping[idx] + "_TOTAL"
                            self.WriteMacro(macro_total_name, "(" + previous_macro + ")")
                    macro_total_name = macro_base + group_name_mapping[-1] + "_TOTAL"
                    self.WriteLine()
    
    def WriteMonInfos(self, name, mons, encounter_rate):
        info_name = name + "Info"
        self.WriteLine(f"const struct WildPokemon {name}[] =")
        self.WriteLine("{")
        for mon in mons:
            species = mon["species"]
            min_level = mon.get("min_level", DEFAULT_MIN_LEVEL)
            max_level = mon.get("max_level", MAX_LEVEL)
            self.WriteLine(f"{{ {min_level}, {max_level}, {species} }},", 1)

        self.WriteLine("};")
        self.WriteLine()
        self.WriteLine(f"const struct WildPokemonInfo {info_name} = {{ {encounter_rate}, {name} }};")
        self.WriteLine()
    
    def WriteTerminator(self):
        self.WriteLine("{", 1)
        self.WriteLine(".mapGroup = MAP_GROUP(MAP_UNDEFINED),", 2)
        self.WriteLine(".mapNum = MAP_NUM(MAP_UNDEFINED),", 2)
        self.WriteLine(".encounterTypes =", 2)
        self.WriteLine("{", 2)
        for time in self.config.times_of_day:
            if not self.config.time_encounters and time != self.config.time_fallback:
                continue
            self.WriteLine(f"[{time}] =", 3)
            self.WriteLine("{", 3)
            for mon_type in self.config.mon_types:
                member_name = mon_type.title().replace("_", "")
                member_name = member_name[0].lower() + member_name[1:] + "Info"
                self.WriteLine(f".{member_name} = NULL,", 4)
            self.WriteLine("},", 3)
        self.WriteLine("},", 2)
        self.WriteLine("},", 1)

    def WritePokemonHeaders(self, headers):
        label = headers["label"]
        self.WriteLine(f"const struct WildPokemonHeader {label}[] =")
        self.WriteLine("{")
        for shared_label in headers["data"]:
            self.WriteLine()
            map_data = headers["data"][shared_label]
            encounter_data = map_data
            map_group = map_data["mapGroup"]
            map_num = map_data["mapNum"]
            self.WriteLine(f"#ifdef {GetLabelVersion(shared_label)}")

            self.WriteLine("{", 1)
            self.WriteLine(f".mapGroup = {map_group},", 2)
            self.WriteLine(f".mapNum = {map_num},", 2)
            self.WriteLine(".encounterTypes =", 2)
            self.WriteLine("{", 2)
            for time in self.config.times_of_day:
                if not self.config.time_encounters and time != self.config.time_fallback:
                    continue
                self.WriteLine(f"[{time}] =", 4)
                self.WriteLine("{", 4)
                for mon_type in self.config.mon_types:
                    member_name = mon_type.title().replace("_", "")
                    member_name = member_name[0].lower() + member_name[1:] + "Info"
                    value = "NULL"
                    if time in encounter_data and mon_type in encounter_data[time]:
                        value = encounter_data[time][mon_type]
                    if value != "NULL":
                        value = "&" + value
                    self.WriteLine(f".{member_name} = {value},", 5)

                self.WriteLine("},", 3)
            
            self.WriteLine("},", 2)
            self.WriteLine("},", 1)
            self.WriteLine(f"#endif")
        self.WriteTerminator()
        self.WriteLine("};")


    def WriteEncounters(self):
        wild_encounter_groups = self.json_data["wild_encounter_groups"]
        for wild_encounter_group in wild_encounter_groups:
            headers = {}
            headers["label"] = wild_encounter_group["label"]
            headers["data"] = {}
            for_maps = False
            map_num_counter = 1
            if "for_maps" in wild_encounter_group:
                for_maps = wild_encounter_group["for_maps"]
            encounters = wild_encounter_group["encounters"]

            for map_encounters in encounters:
                map_group = "0"
                map_num = str(map_num_counter)
                if for_maps:
                    map_name = map_encounters["map"]
                    map_group = f"MAP_GROUP({map_name})"
                    map_num = f"MAP_NUM({map_name})"
                map_num_counter += 1
                base_label = map_encounters["base_label"]
                shared_label, time = SplitTimeOfDay(base_label, self.config.times_of_day, self.config.time_fallback)

                if shared_label not in headers["data"]:
                    headers["data"][shared_label] = {}
                if time not in headers["data"][shared_label]:
                    headers["data"][shared_label][time] = {}
                headers["data"][shared_label]["mapGroup"] = map_group
                headers["data"][shared_label]["mapNum"] = map_num

                self.WriteLine(f"#ifdef {GetLabelVersion(shared_label)}")
                for mon_type in self.config.mon_types:
                    if mon_type not in map_encounters:
                        headers["data"][shared_label][mon_type] = "NULL"
                        continue
                    
                    mons_entry = map_encounters[mon_type]
                    encounter_rate = mons_entry["encounter_rate"]
                    mons = mons_entry["mons"]

                    mon_array_name = base_label + "_" + mon_type.title().replace("_", "")
                    self.WriteMonInfos(mon_array_name, mons, encounter_rate)
                    headers["data"][shared_label][time][mon_type] = mon_array_name + "Info"
                self.WriteLine(f"#endif")

            self.WritePokemonHeaders(headers)


def ConvertToHeaderFile(json_data):
    ValidateEncounters(json_data)
    config = Config('include/config/overworld.h', 'include/constants/rtc.h', json_data)
    ValidateLabels(json_data, config.times_of_day, config.time_fallback)
    with open('src/data/wild_encounters.h', 'w') as output_file:
        assembler = WildEncounterAssembler(output_file, json_data, config)
        assembler.WriteHeader()
        assembler.WriteMacros()
        assembler.WriteEncounters()

def main():
    with open('src/data/wild_encounters.json', 'r') as json_file:
        json_data = json.load(json_file)
    try:
        ConvertToHeaderFile(json_data)
    except WildEncountersError as error:
        sys.exit(f"src/data/wild_encounters.json: {error}")


if __name__ == '__main__':
    main()
