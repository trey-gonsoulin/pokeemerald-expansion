#!/usr/bin/env python3
"""Classify wild-encounter areas from every main-series game into archetypes
and build cross-generation species pools for each archetype.

    python3 tools/area_archetypes/area_archetypes.py fetch
    python3 tools/area_archetypes/area_archetypes.py build

``fetch`` downloads PokeAPI's CSV dump (encounters for Gens 1-8) into a local
cache. ``build`` classifies every encounter table, then writes to ``output/``:

* ``archetype_pools.json``   archetype -> method group -> weighted species pool
* ``archetype_pools.md``     readable summary of the top of each pool
* ``area_classification.csv`` every source table and the archetype it got
* ``emerald_maps.json``      archetype for each table in src/data/wild_encounters.json

Archetype rules live in ``archetypes.py``.
"""

import argparse
import collections
import csv
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import archetypes as A  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
DEFAULT_CACHE = os.path.join(HERE, '.cache', 'pokeapi')
DEFAULT_OUT = os.path.join(HERE, 'output')
POKEAPI_CSV_URL = 'https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/'
CSV_FILES = [
    'encounters', 'encounter_slots', 'encounter_methods', 'locations', 'location_areas',
    'regions', 'versions', 'version_groups', 'pokemon', 'pokemon_species',
    'pokemon_types', 'types',
]
# Species whose share of a pool is below this are dropped from the output.
MIN_POOL_SHARE = 0.001
MD_TOP_N = 15


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def fetch(cache):
    os.makedirs(cache, exist_ok=True)
    for name in CSV_FILES:
        url = f'{POKEAPI_CSV_URL}{name}.csv'
        print(f'fetching {url}')
        with urllib.request.urlopen(url) as resp, open(os.path.join(cache, name + '.csv'), 'wb') as f:
            f.write(resp.read())


def read_csv(cache, name):
    path = os.path.join(cache, name + '.csv')
    if not os.path.exists(path):
        sys.exit(f'missing {path}; run `{sys.argv[0]} fetch` first')
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


class PokeData:
    """The slices of PokeAPI's CSVs the classifier needs, keyed by id."""

    def __init__(self, cache):
        rd = lambda n: read_csv(cache, n)  # noqa: E731
        self.regions = {r['id']: r['identifier'] for r in rd('regions')}
        self.locations = {r['id']: r for r in rd('locations')}
        self.areas = {r['id']: r for r in rd('location_areas')}
        self.version_groups = {r['id']: r for r in rd('version_groups')}
        self.version_to_group = {r['id']: r['version_group_id'] for r in rd('versions')}
        self.methods = {r['id']: r['identifier'] for r in rd('encounter_methods')}
        self.slots = {r['id']: r for r in rd('encounter_slots')}
        self.species = {r['id']: r for r in rd('pokemon_species')}
        self.pokemon = {r['id']: r for r in rd('pokemon')}
        type_names = {r['id']: r['identifier'] for r in rd('types')}
        self.types = collections.defaultdict(list)
        for r in rd('pokemon_types'):
            self.types[r['pokemon_id']].append(type_names[r['type_id']])
        self.encounters = rd('encounters')

    def species_ident(self, pokemon_id):
        return self.species[self.pokemon[pokemon_id]['species_id']]['identifier']

    def species_gen(self, pokemon_id):
        return int(self.species[self.pokemon[pokemon_id]['species_id']]['generation_id'])


def load_species_constants(repo):
    with open(os.path.join(repo, 'include', 'constants', 'species.h'), encoding='utf-8') as f:
        return set(re.findall(r'\b(SPECIES_[A-Z0-9_]+)\s*=', f.read()))


def to_constant(ident):
    return 'SPECIES_' + re.sub(r'[^A-Z0-9]+', '_', ident.upper()).strip('_')


class SpeciesMap:
    """PokeAPI pokemon id <-> expansion SPECIES_* constant."""

    def __init__(self, data, constants):
        self.to_const = {}
        self.unmapped = set()
        for pid, p in data.pokemon.items():
            const = to_constant(p['identifier'])
            if const not in constants:  # cosmetic/alternate form: use base species
                const = to_constant(data.species_ident(pid))
            if const in constants:
                self.to_const[pid] = const
            else:
                self.unmapped.add(p['identifier'])
        self.from_const = {}
        for pid in sorted(self.to_const, key=int):  # lowest id = default form wins
            self.from_const.setdefault(self.to_const[pid], pid)


# ---------------------------------------------------------------------------
# Encounter tables
# ---------------------------------------------------------------------------

class Table:
    """One version group's encounters for one method group in one area."""

    def __init__(self, vg, region, location, area, group):
        self.vg, self.region, self.location, self.area, self.group = vg, region, location, area, group
        self.weight = collections.Counter()   # pokemon id -> weighted rarity
        self.levels = {}                       # pokemon id -> [min, max]
        self.level_sum = 0.0
        self.habitat = self.stage = self.reason = None

    def add(self, pid, w, lo, hi):
        self.weight[pid] += w
        self.level_sum += w * (lo + hi) / 2
        cur = self.levels.setdefault(pid, [lo, hi])
        cur[0], cur[1] = min(cur[0], lo), max(cur[1], hi)

    @property
    def total(self):
        return sum(self.weight.values())

    @property
    def level(self):
        return self.level_sum / self.total

    def shares(self):
        t = self.total
        return {pid: w / t for pid, w in self.weight.items()}

    @property
    def archetype(self):
        return f'{self.habitat}/{self.stage}'


def build_tables(data):
    tables = {}
    for e in data.encounters:
        slot = data.slots[e['encounter_slot_id']]
        group_w = A.METHODS.get(data.methods[slot['encounter_method_id']])
        if not group_w:
            continue
        group, mweight = group_w
        area = data.areas[e['location_area_id']]
        loc = data.locations[area['location_id']]
        if loc['identifier'].startswith(A.SKIP_LOCATION_PREFIXES) or area['identifier'] in A.SKIP_AREAS:
            continue
        vg = data.version_groups[data.version_to_group[e['version_id']]]['identifier']
        rarity = int(slot['rarity'] or 0)
        if rarity <= 0:
            continue
        # Seaweed is surfing underwater: same Emerald field, its own habitat.
        area_ident = 'underwater' if group == 'underwater' else area['identifier']
        group = 'surf' if group == 'underwater' else group
        key = (vg, loc['identifier'], area_ident, group)
        t = tables.get(key)
        if t is None:
            region = data.regions.get(loc['region_id'], 'other')
            t = tables[key] = Table(vg, region, loc['identifier'], area_ident, group)
        t.add(e['pokemon_id'], rarity * mweight, int(e['min_level']), int(e['max_level']))
    return list(tables.values())


def pooled_shares(tables, keyfn):
    """Average per-table shares of ``keyfn(pid)`` values across tables."""
    acc = collections.Counter()
    for t in tables:
        for pid, s in t.shares().items():
            for k in keyfn(pid):
                acc[k] += s / len(tables)
    return acc


def classify_tables(data, tables):
    by_place = collections.defaultdict(list)
    for t in tables:
        by_place[(t.location, t.area)].append(t)
    by_location = collections.defaultdict(list)
    for t in tables:
        by_location[t.location].append(t)

    def type_shares(ts):
        # Each pokemon's share is split across its types so shares sum to 1.
        acc = collections.Counter()
        for t in ts:
            for pid, s in t.shares().items():
                types = data.types[pid]
                for ty in types:
                    acc[ty] += s / len(types) / len(ts)
        return acc

    for (loc, area), ts in by_place.items():
        # Habitat type mix comes from the area's grass table, else the location's.
        land = [t for t in ts if t.group == 'land'] or [t for t in by_location[loc] if t.group == 'land']
        land_hab, land_reason = A.land_habitat(loc, area, type_shares(land))
        water = [t for t in ts if t.group in A.WATER_GROUPS]
        water_hab = water_reason = None
        if water:
            sp = pooled_shares(water, lambda pid: [data.species_ident(pid)])
            water_hab, water_reason = A.water_habitat(loc, area, sp, land_hab)
        for t in ts:
            if t.group in A.WATER_GROUPS:
                t.habitat, t.reason = water_hab, water_reason
            else:
                t.habitat, t.reason = land_hab, land_reason
            t.stage = A.stage_for_level(t.level)


def water_habitat_by_location(tables):
    """location -> the water habitat most of its (non-underwater) tables got."""
    votes = collections.defaultdict(collections.Counter)
    for t in tables:
        if t.group in A.WATER_GROUPS and t.habitat != 'underwater':
            votes[t.location][t.habitat] += 1
    return {loc: c.most_common(1)[0][0] for loc, c in votes.items()}


# ---------------------------------------------------------------------------
# Pools
# ---------------------------------------------------------------------------

def build_pools(data, smap, tables):
    """archetype -> group -> species list.

    Every version group contributes equally to a pool; within a version group
    each location counts equally, and within a location each area does. So a
    nine-room cave doesn't outweigh a one-map forest, and SwSh's hundreds of
    tables don't outweigh Red/Blue's.
    """
    grouped = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list)))
    for t in tables:
        grouped[(t.archetype, t.group)][t.vg][t.location].append(t)

    pools = collections.defaultdict(dict)
    sources = collections.defaultdict(set)
    for (arch, group), by_vg in grouped.items():
        score = collections.Counter()
        games = collections.defaultdict(set)
        levels = {}
        for vg, by_loc in by_vg.items():
            for loc, ts in by_loc.items():
                sources[arch].add(f'{vg}:{loc}')
                for t in ts:
                    w = 1 / len(by_vg) / len(by_loc) / len(ts)
                    for pid, s in t.shares().items():
                        const = smap.to_const.get(pid)
                        if not const:
                            continue
                        score[const] += w * s
                        games[const].add(vg)
                        lo, hi = t.levels[pid]
                        cur = levels.setdefault(const, [lo, hi])
                        cur[0], cur[1] = min(cur[0], lo), max(cur[1], hi)
        entries = []
        for const, s in score.most_common():
            if s < MIN_POOL_SHARE:
                break
            pid = smap.from_const[const]
            entries.append({
                'species': const,
                'share': round(s, 4),
                'games': len(games[const]),
                'introduced_gen': data.species_gen(pid),
                'types': data.types[pid],
                'levels': levels[const],
            })
        pools[arch][group] = entries
    return pools, sources


def archetype_order(arch):
    habitat, stage = arch.split('/')
    return (A.HABITATS.index(habitat), A.STAGE_NAMES.index(stage))


# ---------------------------------------------------------------------------
# Emerald maps
# ---------------------------------------------------------------------------

EMERALD_FIELDS = {
    'land_mons': 'land',
    'rock_smash_mons': 'rock_smash',
    'water_mons': 'surf',
}
# Map names whose PokeAPI location isn't a run of the map name's own words.
LOCATION_ALIASES = {
    'kanto-victory-road': 'kanto-victory-road-2',
    'three-island-port': 'three-isle-port',
    'five-island-meadow': 'five-isle-meadow',
}


def emerald_location(map_const, region, known):
    """Best PokeAPI location identifier for an Emerald/FRLG map constant.

    Tries every contiguous run of the map name's words (plus region-prefixed
    variants) and keeps the longest known one, preferring the rightmost on a
    tie: SEVEN_ISLAND_TANOBY_RUINS_MONEAN_CHAMBER -> monean-chamber,
    MT_EMBER_RUBY_PATH_B1F -> mt-ember, ROUTE21_NORTH -> kanto-sea-route-21.
    Returns (identifier, matched); unmatched maps get their own kebab name.
    """
    name = map_const.removeprefix('MAP_').lower().replace('_', '-')
    name = re.sub(r'route(\d+)', r'route-\1', name).replace('ssanne', 'ss-anne')
    words = name.split('-')
    best = None
    for i in range(len(words)):
        for j in range(i + 1, len(words) + 1):
            run = '-'.join(words[i:j])
            for c in (run, f'{region}-{run}', f'{region}-sea-{run}'):
                c = LOCATION_ALIASES.get(c, c)
                if c in known and (best is None or j - i >= best[0]):
                    best = (j - i, c)
    if best:
        return best[1], True
    return name, False


def classify_emerald(data, smap, repo, water_by_loc):
    """Archetype for every table of every map in src/data/wild_encounters.json.

    Land habitat runs the same rules as PokeAPI areas, on the matched PokeAPI
    location name (so overrides apply) and this repo's own species. Water
    habitat reuses what the matched location's PokeAPI tables mostly got, so a
    map agrees with its source games; unmatched maps fall back to the rules.
    """
    with open(os.path.join(repo, 'src', 'data', 'wild_encounters.json'), encoding='utf-8') as f:
        wild = json.load(f)
    group = next(g for g in wild['wild_encounter_groups'] if g['label'] == 'gWildMonHeaders')
    field_defs = {fd['type']: fd for fd in group['fields']}
    known = {l['identifier'] for l in data.locations.values()}
    out = {}
    for enc in group['encounters']:
        label, map_const = enc['base_label'], enc['map']
        region = 'kanto' if label.endswith(('_FireRed', '_LeafGreen')) or re.fullmatch(
            r'MAP_ROUTE\d{1,2}(_.*)?', map_const) else 'hoenn'
        loc, matched = emerald_location(map_const, region, known)
        area = 'underwater' if 'UNDERWATER' in map_const else ''

        def table(field, idxs=None):
            mons = enc[field]['mons']
            rates = field_defs[field]['encounter_rates']
            idxs = range(len(mons)) if idxs is None else idxs
            t = Table('emerald-plus', region, loc, area, field)
            for i in idxs:
                m = mons[i]
                pid = smap.from_const.get(m['species'])
                if pid:
                    t.add(pid, rates[i], m['min_level'], m['max_level'])
            return t if t.total else None

        def types_of(t):
            acc = collections.Counter()
            for pid, s in t.shares().items():
                for ty in data.types[pid]:
                    acc[ty] += s / len(data.types[pid])
            return acc

        land_t = table('land_mons') if 'land_mons' in enc else None
        land_hab, land_reason = A.land_habitat(loc, area, types_of(land_t) if land_t else {})
        water_ts = []
        result = {'map': map_const, 'location': loc, 'matched_pokeapi': matched, 'region': region}
        fields = {}
        for field, gname in EMERALD_FIELDS.items():
            if field in enc and (t := table(field)):
                fields[field] = (t, gname)
                if gname == 'surf':
                    water_ts.append(t)
        fishing = {}
        if 'fishing_mons' in enc:
            for rod, idxs in field_defs['fishing_mons']['groups'].items():
                if t := table('fishing_mons', idxs):
                    fishing[rod] = t
                    water_ts.append(t)
        water_hab = water_reason = None
        if water_ts and area == 'underwater':
            water_hab, water_reason = 'underwater', 'area:underwater'
        elif water_ts and matched and loc in water_by_loc:
            water_hab, water_reason = water_by_loc[loc], f'pokeapi-majority:{loc}'
        elif water_ts:
            sp = pooled_shares(water_ts, lambda pid: [data.species_ident(pid)])
            water_hab, water_reason = A.water_habitat(loc, area, sp, land_hab)
        for field, (t, gname) in fields.items():
            hab = water_hab if gname == 'surf' else land_hab
            result[field] = {'archetype': f'{hab}/{A.stage_for_level(t.level)}',
                             'pool': gname, 'level': round(t.level, 1)}
        if fishing:
            result['fishing_mons'] = {
                rod: {'archetype': f'{water_hab}/{A.stage_for_level(t.level)}',
                      'pool': {'old_rod': 'fish_old', 'good_rod': 'fish_good',
                               'super_rod': 'fish_super'}[rod],
                      'level': round(t.level, 1)}
                for rod, t in fishing.items()}
        result['reason'] = {'land': land_reason, 'water': water_reason}
        out[label] = result
    return out


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_outputs(out_dir, data, tables, pools, sources, emerald):
    os.makedirs(out_dir, exist_ok=True)
    archs = sorted(pools, key=archetype_order)
    vg_gen = {v['identifier']: int(v['generation_id']) for v in data.version_groups.values()}

    doc = {
        'about': ('Cross-generation wild species pools per area archetype '
                  '(<habitat>/<stage>), built from PokeAPI encounter data by '
                  'tools/area_archetypes. share = average fraction of encounters '
                  'across contributing games; games = how many version groups '
                  'have the species in this archetype.'),
        'stages': {s: top for s, top in A.STAGES},
        'habitats': {'land': A.LAND_HABITATS, 'water': A.WATER_HABITATS},
        'archetypes': {},
    }
    for arch in archs:
        srcs = sorted(sources[arch])
        doc['archetypes'][arch] = {
            'generations': sorted({vg_gen[s.split(':')[0]] for s in srcs}),
            'sources': srcs,
            'pools': {g: pools[arch][g] for g in A.METHOD_GROUPS if g in pools[arch]},
        }
    with open(os.path.join(out_dir, 'archetype_pools.json'), 'w', encoding='utf-8') as f:
        json.dump(doc, f, indent=1)
        f.write('\n')

    with open(os.path.join(out_dir, 'area_classification.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['version_group', 'generation', 'region', 'location', 'area', 'method_group',
                    'archetype', 'level', 'reason', 'top_species'])
        for t in sorted(tables, key=lambda t: (vg_gen[t.vg], t.vg, t.location, t.area, t.group)):
            top = sorted(t.shares().items(), key=lambda kv: -kv[1])[:5]
            w.writerow([t.vg, vg_gen[t.vg], t.region, t.location, t.area, t.group, t.archetype,
                        round(t.level, 1), t.reason,
                        ' '.join(f'{data.pokemon[p]["identifier"]}:{s:.2f}' for p, s in top)])

    with open(os.path.join(out_dir, 'emerald_maps.json'), 'w', encoding='utf-8') as f:
        json.dump(emerald, f, indent=1)
        f.write('\n')

    lines = ['# Area archetype pools', '',
             'Generated by `tools/area_archetypes/area_archetypes.py build`; see the README there.',
             f'Top {MD_TOP_N} species per method; full pools in `archetype_pools.json`.', '',
             '| stage | max table level |', '|---|---|']
    lines += [f'| {s} | {top if top < 999 else "-"} |' for s, top in A.STAGES]
    for arch in archs:
        info = doc['archetypes'][arch]
        locs = sorted({s.split(':')[1] for s in info['sources']})
        lines += ['', f'## {arch}', '',
                  f'Gens {", ".join(map(str, info["generations"]))} - {len(locs)} locations, e.g. '
                  + ', '.join(locs[:8]) + (' ...' if len(locs) > 8 else ''), '']
        for g, entries in info['pools'].items():
            top = ', '.join(f'{e["species"].removeprefix("SPECIES_")} {e["share"]:.0%}'
                            for e in entries[:MD_TOP_N])
            lines.append(f'- **{g}**: {top}')
    with open(os.path.join(out_dir, 'archetype_pools.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


def build(cache, out_dir, repo):
    data = PokeData(cache)
    smap = SpeciesMap(data, load_species_constants(repo))
    tables = build_tables(data)
    classify_tables(data, tables)
    pools, sources = build_pools(data, smap, tables)
    emerald = classify_emerald(data, smap, repo, water_habitat_by_location(tables))
    write_outputs(out_dir, data, tables, pools, sources, emerald)
    counts = collections.Counter(t.archetype for t in tables)
    wild = {pid for t in tables for pid in t.weight}
    unmapped = sorted(data.pokemon[p]['identifier'] for p in wild if p not in smap.to_const)
    print(f'{len(tables)} tables -> {len(pools)} archetypes; '
          f'{len(emerald)} Emerald maps classified; output in {out_dir}')
    if unmapped:
        print(f'  wild forms with no SPECIES_ constant (left out of pools): {", ".join(unmapped)}')
    for arch in sorted(counts, key=archetype_order):
        print(f'  {arch:24} {counts[arch]:5} tables')
    return data, smap, tables, pools, emerald


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('command', choices=['fetch', 'build'])
    p.add_argument('--cache', default=DEFAULT_CACHE, help='PokeAPI CSV cache dir')
    p.add_argument('--out', default=DEFAULT_OUT, help='output dir')
    args = p.parse_args(argv)
    if args.command == 'fetch':
        fetch(args.cache)
    else:
        build(args.cache, args.out, REPO)


if __name__ == '__main__':
    main()
