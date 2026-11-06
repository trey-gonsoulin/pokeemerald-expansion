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
# The most a field's encounter_rates (each group's, in a field with groups) can add up to:
# the pickers in src/wild_encounter.c draw a u8 below that total. The fishing picker draws
# one number below the largest rod's total for every rod, so the rods' totals must match.
MAX_RATES_TOTAL = 256
# The slots the pickers in src/wild_encounter.c choose from (ChooseWildMonIndex_Land and the
# rest), whose lure swaps (11 - index, ...) and else branches assume exactly these. Keep in
# step with the pickers.
PICKER_SLOT_COUNTS = {"land_mons": 12, "water_mons": 5, "rock_smash_mons": 5, "fishing_mons": 10, "hidden_mons": 3}
PICKER_GROUPS = {"fishing_mons": {"old_rod": [0, 1], "good_rod": [2, 3, 4], "super_rod": [5, 6, 7, 8, 9]}}
VERSION_SUFFIXES = {"_FireRed": "FIRERED", "_LeafGreen": "LEAFGREEN"}
# Maps whose tables are labels of their own on one map, each with its table count: from the
# map's first header, GetCurrentMapWildMonHeaderId takes the one VAR_ALTERING_CAVE_WILD_SET
# (below NUM_ALTERING_CAVE_TABLES) further on, so the labels of each version have to be that
# many and consecutive. FRLG's Altering Cave has its tables the same way, though no C code
# rotates them yet (only the first is used).
ROTATING_TABLE_MAPS = {"MAP_ALTERING_CAVE": 9, "MAP_SIX_ISLAND_ALTERING_CAVE": 9}


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
    """Return the slots' total, which has to be 1 to MAX_RATES_TOTAL."""
    for slot in slots:
        CheckInt(rates[slot], 0, MAX_RATES_TOTAL, f"encounter_rates[{slot}]", where)
    total = sum(rates[slot] for slot in slots)
    CheckInt(total, 1, MAX_RATES_TOTAL, "the encounter_rates total", where)
    return total


def CheckGroups(field, where):
    """Each slot in exactly one group, each group's slots consecutive in any
    order (WriteMacros sums them by slot), and every group's rates adding up to
    the same total."""
    slot_count = len(field["encounter_rates"])
    slot_groups = {}
    group_totals = {}
    if type(field["groups"]) is not dict:
        raise WildEncountersError(f"{where}: groups is {field['groups']!r}, expected an object of slot lists")
    for name, slots in field["groups"].items():
        group_where = f"{where} group {name}"
        if type(slots) is not list or not slots:
            raise WildEncountersError(f"{group_where}: slots are {slots!r}, expected a list of slot indices")
        for slot in slots:
            CheckInt(slot, 0, slot_count - 1, "slot index", group_where)
            if slot in slot_groups:
                raise WildEncountersError(f"{group_where}: slot {slot} is also in group {slot_groups[slot]}")
            slot_groups[slot] = name
        if sorted(slots) != list(range(min(slots), min(slots) + len(slots))):
            raise WildEncountersError(f"{group_where}: slots {slots} aren't consecutive")
        group_totals[name] = CheckRates(field["encounter_rates"], slots, group_where)
    ungrouped = [str(slot) for slot in range(slot_count) if slot not in slot_groups]
    if ungrouped:
        raise WildEncountersError(f"{where}: slot(s) {', '.join(ungrouped)} in no group")
    if len(set(group_totals.values())) > 1:
        totals = ", ".join(f"{name} {total}" for name, total in group_totals.items())
        raise WildEncountersError(f"{where}: the groups' encounter_rates totals differ ({totals})")


def CheckPickerShape(field, slot_count, where):
    """The field's slots and groups as its picker in src/wild_encounter.c takes them."""
    field_type = field["type"]
    if field_type not in PICKER_SLOT_COUNTS:
        raise WildEncountersError(f"{where}: no picker in src/wild_encounter.c reads this field type")
    if slot_count != PICKER_SLOT_COUNTS[field_type]:
        raise WildEncountersError(f"{where}: {slot_count} encounter_rates, but src/wild_encounter.c picks from {PICKER_SLOT_COUNTS[field_type]} slots")
    groups = field.get("groups")
    sorted_groups = None if groups is None else {name: sorted(slots) for name, slots in groups.items()}
    expected = PICKER_GROUPS.get(field_type)
    if sorted_groups != expected:
        raise WildEncountersError(f"{where}: groups are {groups}, but src/wild_encounter.c picks from {expected}")


def ValidateEncounters(json_data):
    """Raise WildEncountersError on data the header would carry silently wrong: a
    field whose slots or groups differ from its picker's, a table whose slot count
    differs from its field's encounter_rates, encounter_rates whose total is 0 or
    past MAX_RATES_TOTAL (or differs between groups), a bad groups index, an unknown
    key, a missing key, a level outside 1-100 or above max_level, or an encounter
    rate past a u8."""
    field_types = []
    for group in json_data["wild_encounter_groups"]:
        CheckKeys(group, *GROUP_KEYS, group.get("label", "wild encounter group"))
        for field in group.get("fields", []):
            field_where = f"{group['label']} field {field.get('type')}"
            CheckKeys(field, *FIELD_KEYS, field_where)
            slot_count = len(field["encounter_rates"])
            if "groups" in field:
                CheckGroups(field, field_where)
            else:
                CheckRates(field["encounter_rates"], range(slot_count), field_where)
            CheckPickerShape(field, slot_count, field_where)
            if field["type"] not in field_types:
                field_types.append(field["type"])

    for group in json_data["wild_encounter_groups"]:
        required = {"base_label", "map"} if group.get("for_maps") else {"base_label"}
        for idx, map_encounters in enumerate(group["encounters"]):
            where = map_encounters.get("base_label", f"{group['label']} encounter {idx}")
            CheckKeys(map_encounters, required, {"map", *field_types}, where)
            for mon_type in field_types:
                if mon_type not in map_encounters:
                    continue
                slot_count = PICKER_SLOT_COUNTS[mon_type]
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


def CheckVersionSuffixLast(label, times_of_day):
    """A version suffix goes before the time of day suffix (sRoute1_FireRed_Night):
    SplitTimeOfDay and GetLabelVersion each read only the last suffix."""
    for version_suffix in VERSION_SUFFIXES:
        if label.endswith(version_suffix):
            stem, time = SplitTimeOfDay(label[:-len(version_suffix)], times_of_day, None)
            if time:
                raise WildEncountersError(f"{label}: version suffix after the time of day suffix, expected {stem}{version_suffix}_{times_of_day[time]}")


def CheckRotatingTables(label_maps):
    """Each version's labels on a map of ROTATING_TABLE_MAPS number its table count and
    sit together in header order (label_maps' order, each label's first encounter)."""
    version_labels = {}
    for shared_label, (map_name, first_where) in label_maps.items():
        version_labels.setdefault(GetLabelVersion(shared_label), []).append((map_name, first_where))
    for version, labels in version_labels.items():
        for map_name, table_count in ROTATING_TABLE_MAPS.items():
            indices = [index for index, (label_map, _) in enumerate(labels) if label_map == map_name]
            if not indices:
                continue
            first_where = labels[indices[0]][1]
            if len(indices) != table_count:
                raise WildEncountersError(f"{first_where}: map {map_name} has {len(indices)} labels ({version}), expected {table_count}, one per table")
            if indices[-1] - indices[0] + 1 != table_count:
                raise WildEncountersError(f"{first_where}: map {map_name}'s labels ({version}) aren't consecutive, so its tables would read another map's")


def ValidateLabels(json_data, times_of_day, time_fallback, time_encounters):
    """Raise WildEncountersError when two encounters of a group share a label and time
    of day, or two times of one label name different maps: WriteEncounters would keep
    only the later one's tables, or map, in the header. Also when two labels of one
    version name one map (outside ROTATING_TABLE_MAPS, which need their table count of
    consecutive labels), since GetCurrentMapWildMonHeaderId takes the first; when a label's
    time of day suffix comes before its version suffix;
    and, with time_encounters off, when a label has no time_fallback encounters, the only
    ones WritePokemonHeaders writes then."""
    for group in json_data["wild_encounter_groups"]:
        label_times = {}
        label_maps = {}
        map_labels = {}
        for map_encounters in group["encounters"]:
            where = map_encounters["base_label"]
            CheckVersionSuffixLast(where, times_of_day)
            shared_label, time = SplitTimeOfDay(where, times_of_day, time_fallback)
            if (shared_label, time) in label_times:
                raise WildEncountersError(f"{where}: same label and time of day as {label_times[shared_label, time]} ({shared_label}, {time})")
            label_times[shared_label, time] = where
            map_name = map_encounters.get("map")
            first_map, first_where = label_maps.setdefault(shared_label, (map_name, where))
            if map_name != first_map:
                raise WildEncountersError(f"{where}: map {map_name}, but {first_where} has {first_map}")
            if map_name is not None and map_name not in ROTATING_TABLE_MAPS:
                version = GetLabelVersion(shared_label)
                map_label = map_labels.setdefault((map_name, version), shared_label)
                if map_label != shared_label:
                    raise WildEncountersError(f"{where}: map {map_name} already has {map_label}'s encounters ({version})")

        CheckRotatingTables(label_maps)

        if not time_encounters:
            for shared_label, (_, first_where) in label_maps.items():
                if (shared_label, time_fallback) not in label_times:
                    raise WildEncountersError(f"{first_where}: with OW_TIME_OF_DAY_ENCOUNTERS FALSE only {time_fallback} encounters are used, "
                                              f"and {shared_label} has none ({shared_label} or {shared_label}_{times_of_day[time_fallback]})")

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
        default_time = next(iter(self.times_of_day))
        if not self.time_encounters and self.time_fallback != default_time:
            # GetTimeOfDayForEncounters then reads TIME_OF_DAY_DEFAULT (the first time), but
            # WritePokemonHeaders writes only the fallback time's tables.
            raise Exception(f"OW_TIME_OF_DAY_FALLBACK is {self.time_fallback}, but with OW_TIME_OF_DAY_ENCOUNTERS FALSE "
                            f"src/wild_encounter.c reads only {default_time} encounters: set it to {default_time}.")
    
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
    ValidateLabels(json_data, config.times_of_day, config.time_fallback, config.time_encounters)
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
