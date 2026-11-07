#!/usr/bin/env python3
"""Classify wild-encounter areas from every main-series game into archetypes
and build cross-generation species pools for each archetype.

    python3 tools/area_archetypes/area_archetypes.py fetch
    python3 tools/area_archetypes/area_archetypes.py build
    python3 tools/area_archetypes/area_archetypes.py baseline [--force]
    python3 tools/area_archetypes/area_archetypes.py restock [--help]

``fetch`` copies PokeAPI's CSV dump (encounters for Gens 1-8) at commit
POKEAPI_REF from a pokesearch checkout (``--pokesearch``) into a local cache, with
its provenance (ref, pokesearch SHA, date, sha256s). ``build`` classifies every
encounter table, then writes to ``output/`` (the JSON files with that provenance):

* ``archetype_pools.json``   archetype -> method group -> weighted species pool
* ``archetype_pools.md``     readable summary of the top of each pool
* ``area_classification.csv`` every source table and the archetype it got
* ``emerald_maps.json``      archetype for each table in the vanilla baseline,
                             and the baseline's SHA-256

The vanilla baseline is ``output/wild_encounters.vanilla.json``, a committed
copy of the unrestocked src/data/wild_encounters.json that ``build`` and
``restock`` read instead of the live file. ``baseline`` refreshes it from
src/data/wild_encounters.json (after an upstream merge, say), and refuses a
file ``restock`` wrote unless ``--force``.

``restock`` writes the pools back into wild_encounters.json (``restock.py``).
Archetype rules live in ``archetypes.py``.
"""

import argparse
import collections
import csv
import datetime
import hashlib
import io
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import archetypes as A  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
DEFAULT_CACHE = os.path.join(HERE, '.cache', 'pokeapi')
DEFAULT_OUT = os.path.join(HERE, 'output')
SRC_WILD = os.path.join(REPO, 'src', 'data', 'wild_encounters.json')
VANILLA_WILD = os.path.join(DEFAULT_OUT, 'wild_encounters.vanilla.json')
# Wild level offsets (map -> table field -> levels), which restock applies
# after the species; tools/rebalance's apply writes them (#150).
LEVEL_OFFSETS = os.path.join(HERE, 'level_offsets.json')
# The --config the committed src/data/wild_encounters.json is restocked with,
# which tools/rebalance's apply passes too: ratio 0, the vanilla species.
RESTOCK_SETTINGS = os.path.join(HERE, 'restock_settings.json')
# Top-level key restock adds to the JSON it writes, so a restocked file is
# never mistaken for the vanilla baseline.
RESTOCK_STAMP = 'restocked_by'
# The pokesearch checkout fetch copies from (--pokesearch overrides it), and in
# it the CSV dir and the file there naming the PokeAPI commit the CSVs are from.
DEFAULT_POKESEARCH = os.path.expanduser('~/code/pokesearch')
POKESEARCH_CSV_DIR = os.path.join('data', 'pokeapi', 'csv')
POKESEARCH_STAMP = 'COMMIT'
POKESEARCH_HINT = 'run `python -m poke_extract.pokeapi` in pokesearch'
REFETCH_HINT = f'run `{sys.argv[0]} fetch` first'
# PokeAPI commit fetch accepts; pokesearch's poke_extract.pokeapi.COMMIT must match.
POKEAPI_REF = 'e2710d30d14b3f4dc6a02a4a71e8619cd835b7ff'
# Where fetch records the ref, SHA, date and CSV hashes in the cache, and the key
# build copies them under into archetype_pools.json and emerald_maps.json.
PROVENANCE_FILE = 'provenance.json'
PROVENANCE_KEY = 'provenance'
# Key in emerald_maps.json for the SHA-256 of the base build classified, which
# restock compares with its own base to warn about stale archetypes.
BASE_HASH_KEY = 'base_sha256'
BASE_HINT = 'pass a vanilla wild_encounters.json'
# The wild_encounter_groups entry with the maps' tables (map_headers).
MAP_HEADERS_LABEL = 'gWildMonHeaders'
# Each CSV the build reads -> the columns it reads from it.
CSV_FILES = {
    'encounters': ('version_id', 'location_area_id', 'encounter_slot_id', 'pokemon_id',
                   'min_level', 'max_level'),
    'encounter_slots': ('id', 'encounter_method_id', 'rarity'),
    'encounter_methods': ('id', 'identifier'),
    'locations': ('id', 'identifier', 'region_id'),
    'location_areas': ('id', 'identifier', 'location_id'),
    'regions': ('id', 'identifier'),
    'versions': ('id', 'version_group_id'),
    'version_groups': ('id', 'identifier', 'generation_id'),
    'pokemon': ('id', 'identifier', 'species_id'),
    'pokemon_species': ('id', 'identifier', 'generation_id'),
    'pokemon_types': ('pokemon_id', 'type_id'),
    'types': ('id', 'identifier'),
}
# The read columns that may be blank, which the build handles; a blank in any
# other would stop it. PokeAPI leaves the first two blank on real rows.
CSV_BLANK_OK = {
    'locations': {'region_id'},
    'location_areas': {'identifier'},
    'encounter_slots': {'rarity'},
}
# Species whose share of a pool is below this are dropped from the output.
MIN_POOL_SHARE = 0.001
MD_TOP_N = 15
# Generation each region's forms debuted in. A regional form's introduced_gen
# is its form's, not its base species' (SPECIES_RATTATA_ALOLA is Gen 7).
REGIONAL_FORM_GENS = {'ALOLA': 7, 'GALAR': 8, 'HISUI': 8, 'PALDEA': 9}
REGIONAL_FORM_RE = re.compile(r'_(' + '|'.join(REGIONAL_FORM_GENS) + r')(?:_|$)')


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_base(path, force=False):
    """(wild_encounters.json at path, its SHA-256), refusing one restock wrote unless force."""
    raw = read_or_exit(path, BASE_HINT)
    return check_base(path, raw, force), hashlib.sha256(raw).hexdigest()


def check_base(path, raw, force):
    """The parsed wild_encounters.json bytes from path, refusing a bad table or one restock wrote unless force."""
    try:
        wild = json.loads(raw)
    except ValueError as e:
        sys.exit(f'{path} is not valid JSON ({e}); {BASE_HINT}')
    if not has_map_headers(wild):
        sys.exit(f'{path} has no usable {MAP_HEADERS_LABEL} group; {BASE_HINT}')
    if RESTOCK_STAMP in wild and not force:
        sys.exit(f'{path} was written by restock ({RESTOCK_STAMP} is set), so it is not a vanilla '
                 f'baseline; pass a vanilla file, or --force to use it anyway')
    return wild


def has_map_headers(wild):
    """Whether parsed JSON has the group map_headers finds, with the entries classify_emerald looks up."""
    groups = wild.get('wild_encounter_groups') if isinstance(wild, dict) else None
    if not isinstance(groups, list) or not all(isinstance(g, dict) and 'label' in g for g in groups):
        return False
    try:
        group = map_headers(wild)
    except StopIteration:
        return False
    encounters, fields = group.get('encounters'), group.get('fields')
    return (isinstance(encounters, list) and isinstance(fields, list)
            and all(isinstance(e, dict) and 'base_label' in e and 'map' in e for e in encounters)
            and all(isinstance(f, dict) and 'type' in f for f in fields))


def refresh_baseline(src=SRC_WILD, base=VANILLA_WILD, force=False, out=DEFAULT_OUT):
    """Copy src over the vanilla baseline, unless restock wrote src, then warn if out's maps need a rebuild."""
    raw = read_or_exit(src, BASE_HINT)
    check_base(src, raw, force)
    if os.path.exists(base) and os.path.samefile(src, base):
        sys.exit(f'{src} is already the baseline')
    try:
        write_atomic(base, raw)
    except OSError as e:
        sys.exit(f'cannot write {base}: {e.strerror}')
    print(f'wrote {base} from {src}')
    warn_if_maps_stale(os.path.join(out, 'emerald_maps.json'), base, hashlib.sha256(raw).hexdigest())


def warn_if_maps_stale(maps_path, base_path, base_sha256):
    """Warn unless emerald_maps.json records this base: its archetypes may be from another one.

    Quiet when there's no such file, since then no archetypes can be stale.
    """
    try:
        with open(maps_path, 'rb') as f:
            maps = json.load(f)
    except FileNotFoundError:
        return
    except (OSError, ValueError):
        maps = None
    recorded = maps.get(BASE_HASH_KEY) if isinstance(maps, dict) else None
    if recorded == base_sha256:
        return
    why = 'records no base hash' if recorded is None else 'was built from another base'
    out = os.path.dirname(os.path.abspath(maps_path))
    print(f'warning: {maps_path} {why}, so its archetypes may be stale for {base_path}; '
          f'run area_archetypes.py build --base {base_path} --out {out}', file=sys.stderr)


def write_atomic(path, data):
    """Write bytes to path through path.tmp, so an interrupted write leaves the old file."""
    tmp = path + '.tmp'
    try:
        with open(tmp, 'wb') as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def read_or_exit(path, hint):
    """The bytes of path, exiting with hint if it can't be read."""
    try:
        with open(path, 'rb') as f:
            return f.read()
    except OSError as e:
        sys.exit(f'cannot read {path}: {e.strerror}; {hint}')


def parse_csv(name, raw, where, hint):
    """The rows of CSV bytes, refusing any that are empty, unreadable, cut short, without CSV_FILES' columns
    or blank in one outside CSV_BLANK_OK."""
    if not raw:
        sys.exit(f'{where} is empty; {hint}')
    columns = CSV_FILES[name]
    required = [c for c in columns if c not in CSV_BLANK_OK.get(name, ())]
    rows = []
    try:
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8'), newline=''))
        missing = [c for c in columns if c not in reader.fieldnames]
        if missing:
            sys.exit(f'{where} has no {", ".join(missing)} column; {hint}')
        for row in reader:
            if None in row.values():
                sys.exit(f'{where} line {reader.line_num} is cut short; {hint}')
            blank = [c for c in required if not row[c]]
            if blank:
                sys.exit(f'{where} line {reader.line_num} has a blank {", ".join(blank)}; {hint}')
            rows.append(row)
    except (UnicodeDecodeError, csv.Error) as e:
        sys.exit(f'{where} is not a readable CSV ({e}); {hint}')
    if not rows:
        sys.exit(f'{where} has no rows; {hint}')
    return rows


def pokesearch_sha(pokesearch):
    """The checkout's git HEAD. Its CSVs are gitignored, so this names the code that fetches them."""
    not_checkout = f'{pokesearch} is not a git checkout of pokesearch; pass it with --pokesearch'
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    try:
        top, sha = subprocess.run(['git', '-C', pokesearch, 'rev-parse', '--show-toplevel', 'HEAD'], check=True,
                                  capture_output=True, text=True, env=env).stdout.splitlines()
    except OSError as e:
        sys.exit(f'cannot run git: {e.strerror}; fetch needs it on PATH')
    except subprocess.CalledProcessError:
        sys.exit(not_checkout)
    if not os.path.samefile(top, pokesearch):
        sys.exit(not_checkout)
    return sha


def committed_hashes(out, ref):
    """The CSV hashes out records for PokeAPI ref; none if it holds no build or one of another ref."""
    path = os.path.join(out, 'archetype_pools.json')
    if not os.path.exists(path):
        return {}
    fix = 'restore it, or name other outputs with --out'
    try:
        doc = json.loads(read_or_exit(path, fix))
    except ValueError:
        doc = None
    provenance = doc.get(PROVENANCE_KEY, {}) if isinstance(doc, dict) else None
    hashes = provenance.get('csv_sha256', {}) if isinstance(provenance, dict) else None
    if not isinstance(hashes, dict):
        sys.exit(f'{path} is not a build record; {fix}')
    return hashes if provenance.get('ref') == ref else {}


def fetch(cache, pokesearch, out):
    """Copy CSV_FILES from pokesearch, then record the ref, SHA, date and hashes.

    Every file is read and checked before any is written, so a bad source
    leaves the cache as it was. While out records this ref, a CSV also has to
    have the hash recorded there: pokesearch's stamp doesn't change until a
    re-download finishes, so it can't vouch for files an interrupted one left.
    """
    source = os.path.join(pokesearch, POKESEARCH_CSV_DIR)
    sha = pokesearch_sha(pokesearch)
    stamp = os.path.join(source, POKESEARCH_STAMP)
    ref = read_or_exit(stamp, POKESEARCH_HINT).decode('utf-8', 'replace').strip()
    if ref != POKEAPI_REF:
        sys.exit(f'{source} holds PokeAPI {ref}, not POKEAPI_REF {POKEAPI_REF}; '
                 'to take its data, bump POKEAPI_REF')
    committed = committed_hashes(out, ref)
    raws, hashes = {}, {}
    for name in CSV_FILES:
        path = os.path.join(source, name + '.csv')
        raws[name] = read_or_exit(path, POKESEARCH_HINT)
        parse_csv(name, raws[name], path, POKESEARCH_HINT)
        hashes[name] = hashlib.sha256(raws[name]).hexdigest()
        if committed.get(name, hashes[name]) != hashes[name]:
            sys.exit(f'{path} is not the file {out} was built from at PokeAPI {ref}; '
                     f'remove {stamp}, then {POKESEARCH_HINT}')
    os.makedirs(cache, exist_ok=True)
    for name, raw in raws.items():
        write_atomic(os.path.join(cache, name + '.csv'), raw)
    provenance = {'ref': ref, 'pokesearch': sha,
                  'fetched': datetime.datetime.now(datetime.timezone.utc).date().isoformat(),
                  'csv_sha256': hashes}
    write_atomic(os.path.join(cache, PROVENANCE_FILE),
                 (json.dumps(provenance, indent=1) + '\n').encode('utf-8'))
    print(f'copied {len(raws)} CSVs from {source} to {cache} (PokeAPI {ref}, pokesearch {sha})')


def load_provenance(cache):
    """The cache's provenance.json, once every CSV still has the hash fetch recorded."""
    path = os.path.join(cache, PROVENANCE_FILE)
    record = read_or_exit(path, f'the cache records no PokeAPI ref; {REFETCH_HINT}')
    try:
        provenance = json.loads(record)
    except ValueError:
        provenance = None
    if (not isinstance(provenance, dict) or not isinstance(provenance.get('csv_sha256'), dict)
            or not all(isinstance(provenance.get(k), str) for k in ('ref', 'pokesearch', 'fetched'))):
        sys.exit(f'{path} is not a fetch record; {REFETCH_HINT}')
    hashes, ref = provenance['csv_sha256'], provenance['ref']
    for name in CSV_FILES:
        csv_path = os.path.join(cache, name + '.csv')
        digest = hashlib.sha256(read_or_exit(csv_path, REFETCH_HINT)).hexdigest()
        if hashes.get(name) != digest:
            sys.exit(f'{csv_path} is not the file fetch recorded in {path}; {REFETCH_HINT}')
    if ref != POKEAPI_REF:
        print(f'warning: {cache} holds PokeAPI {ref}, not POKEAPI_REF {POKEAPI_REF}', file=sys.stderr)
    return provenance


def read_csv(cache, name):
    """The checked rows of a cached CSV (parse_csv)."""
    path = os.path.join(cache, name + '.csv')
    return parse_csv(name, read_or_exit(path, REFETCH_HINT), path, REFETCH_HINT)


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


def introduced_gen(const, species_gen):
    """A regional form's own generation, else its species' (``species_gen``)."""
    m = REGIONAL_FORM_RE.search(const)
    return REGIONAL_FORM_GENS[m[1]] if m else species_gen


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
                'introduced_gen': introduced_gen(const, data.species_gen(pid)),
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


def map_headers(wild):
    """The gWildMonHeaders group of wild (wild_encounters.json): the maps' tables, without
    the Battle Pyramid's and Battle Pike's groups."""
    return next(g for g in wild['wild_encounter_groups'] if g['label'] == MAP_HEADERS_LABEL)


def classify_emerald(data, smap, wild, water_by_loc):
    """Archetype for every table of every map in wild (wild_encounters.json).

    Land habitat runs the same rules as PokeAPI areas, on the matched PokeAPI
    location name (so overrides apply) and this repo's own species. Water
    habitat reuses what the matched location's PokeAPI tables mostly got, so a
    map agrees with its source games; unmatched maps fall back to the rules.
    """
    group = map_headers(wild)
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

def write_outputs(out_dir, data, tables, pools, sources, emerald, provenance, base_sha256):
    os.makedirs(out_dir, exist_ok=True)
    archs = sorted(pools, key=archetype_order)
    vg_gen = {v['identifier']: int(v['generation_id']) for v in data.version_groups.values()}

    doc = {
        'about': ('Cross-generation wild species pools per area archetype '
                  '(<habitat>/<stage>), built from PokeAPI encounter data by '
                  'tools/area_archetypes. share = average fraction of encounters '
                  'across contributing games; games = how many version groups '
                  'have the species in this archetype.'),
        PROVENANCE_KEY: provenance,
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
        json.dump({PROVENANCE_KEY: provenance, BASE_HASH_KEY: base_sha256, **emerald}, f, indent=1)
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


def build(cache, out_dir, repo, base=VANILLA_WILD, force=False):
    provenance = load_provenance(cache)
    data = PokeData(cache)
    smap = SpeciesMap(data, load_species_constants(repo))
    tables = build_tables(data)
    classify_tables(data, tables)
    pools, sources = build_pools(data, smap, tables)
    base_wild, base_sha256 = load_base(base, force)
    emerald = classify_emerald(data, smap, base_wild, water_habitat_by_location(tables))
    write_outputs(out_dir, data, tables, pools, sources, emerald, provenance, base_sha256)
    counts = collections.Counter(t.archetype for t in tables)
    wild = {pid for t in tables for pid in t.weight}
    unmapped = sorted(data.pokemon[p]['identifier'] for p in wild if p not in smap.to_const)
    print(f'{len(tables)} tables -> {len(pools)} archetypes; '
          f'{len(emerald)} Emerald maps classified; output in {out_dir}')
    print(f'  PokeAPI ref {provenance["ref"]}, fetched {provenance["fetched"]}')
    if unmapped:
        print(f'  wild forms with no SPECIES_ constant (left out of pools): {", ".join(unmapped)}')
    for arch in sorted(counts, key=archetype_order):
        print(f'  {arch:24} {counts[arch]:5} tables')
    return data, smap, tables, pools, emerald


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ['restock']:  # own options; see restock.py
        import restock
        restock.main(argv[1:])
        return
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('command', choices=['fetch', 'build', 'baseline', 'restock'],
                   help='restock takes its own options: restock --help')
    p.add_argument('--cache', default=DEFAULT_CACHE, help='PokeAPI CSV cache dir')
    p.add_argument('--out', default=DEFAULT_OUT, help='output dir')
    p.add_argument('--base', default=VANILLA_WILD,
                   help='vanilla wild_encounters.json that build classifies and baseline writes')
    p.add_argument('--wild', help='file baseline copies from (default src/data/wild_encounters.json)')
    p.add_argument('--force', action='store_true', help='accept a --base or --wild that restock wrote')
    p.add_argument('--pokesearch', help=f'pokesearch checkout fetch copies from (default {DEFAULT_POKESEARCH})')
    args = p.parse_args(argv)
    if args.command == 'restock':
        p.error('restock must come first: area_archetypes.py restock [options]')
    if args.wild and args.command != 'baseline':
        p.error('--wild only applies to baseline')
    if args.pokesearch and args.command != 'fetch':
        p.error('--pokesearch only applies to fetch')
    if args.command == 'fetch':
        fetch(args.cache, args.pokesearch or DEFAULT_POKESEARCH, args.out)
    elif args.command == 'baseline':
        refresh_baseline(args.wild or SRC_WILD, args.base, args.force, args.out)
    else:
        build(args.cache, args.out, REPO, args.base, args.force)


if __name__ == '__main__':
    main()
