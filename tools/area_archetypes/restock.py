#!/usr/bin/env python3
"""Restock src/data/wild_encounters.json from the archetype pools.

    python3 tools/area_archetypes/area_archetypes.py restock [options]

Reads ``output/archetype_pools.json`` and ``output/emerald_maps.json`` (from
``build``), so it doesn't need the PokeAPI cache. For every encounter table of
every selected map it mixes the table's own species with species drawn from
the table's archetype pool, then hands out the table's slots so the most
common species get the highest-rate slots. Slot counts, encounter rates and
every slot's level range stay as they are; only ``species`` changes.

The natives always come from ``--base``, the vanilla baseline
(``output/wild_encounters.vanilla.json``), never from the file ``--write``
overwrites, so reruns don't compound. Without ``--write`` nothing in src/ is
touched: the restocked JSON and a slot-by-slot report go to ``--out-dir`` for
review. The same base, options and seed give the same output. The JSON
restock writes carries a top-level ``restocked_by`` stamp, and a stamped file
is refused as ``--base`` unless ``--force``.

Every default below is a placeholder until the design questions in issue #8
are settled. Each is also a command-line flag.
"""

import argparse
import collections
import copy
import dataclasses
import json
import os
import random
import re
import sys
from typing import Callable, NamedTuple

import area_archetypes as AA

DEFAULT_OUT_DIR = os.path.join(AA.HERE, 'restock')

# Share of each table's encounter rate that goes to species from the pool;
# the rest stays with the table's own species. 0 = unchanged, 1 = replace all.
DEFAULT_RATIO = 0.5
DEFAULT_SEED = 1
# Kanto (FRLG) tables in wild_encounters.json aren't reachable in Emerald.
DEFAULT_REGIONS = ('hoenn',)
# Pool species with any of these flags are never placed (unless
# --allow-legendaries for the legendary ones; battle-only forms never).
LEGENDARY_FLAGS = frozenset({'isRestrictedLegendary', 'isSubLegendary', 'isMythical',
                             'isUltraBeast', 'isParadox'})
BATTLE_ONLY_FLAGS = frozenset({'isMegaEvolution', 'isGigantamax', 'isPrimalReversion',
                               'isTotem', 'isUltraBurst', 'isTeraForm'})
# Below ratio 1, every species a table already has keeps at least one slot,
# so rare natives (Ralts, Seedot, Kecleon) don't vanish.
KEEP_EVERY_NATIVE = True
# Earliest level for an evolution that isn't by level (stone, trade,
# friendship...): max(pre-evolution's earliest level + GAP, FLOOR).
# Evolutions out of baby species have no floor, so Pikachu and Marill stay
# low-level species.
NONLEVEL_EVO_GAP = 10
NONLEVEL_EVO_FLOOR = 30
BABY_SPECIES = frozenset('SPECIES_' + s for s in (
    'PICHU', 'CLEFFA', 'IGGLYBUFF', 'TOGEPI', 'TYROGUE', 'SMOOCHUM', 'ELEKID', 'MAGBY',
    'AZURILL', 'WYNAUT', 'BUDEW', 'CHINGLING', 'BONSLY', 'MIME_JR', 'HAPPINY', 'MUNCHLAX',
    'RIOLU', 'MANTYKE', 'TOXEL'))
# Alolan, Galarian, Hisuian and Paldean forms (skipped with --no-regional-forms),
# each with the generation its forms debuted in, which --gens and --gen-weight use.
REGIONAL_FORM_GEN = {'isAlolanForm': AA.REGIONAL_FORM_GENS['ALOLA'],
                     'isGalarianForm': AA.REGIONAL_FORM_GENS['GALAR'],
                     'isHisuianForm': AA.REGIONAL_FORM_GENS['HISUI'],
                     'isPaldeanForm': AA.REGIONAL_FORM_GENS['PALDEA']}
REGIONAL_FLAGS = frozenset(REGIONAL_FORM_GEN)
# Config headers that aren't part of a normal build.
SKIPPED_CONFIGS = ('test.h',)

TABLE_FIELDS = ('land_mons', 'water_mons', 'rock_smash_mons')


# ---------------------------------------------------------------------------
# Species data from the expansion's headers
# ---------------------------------------------------------------------------

def parse_defines(repo):
    """Every ``#define NAME value`` in include/config/*.h (last one wins)."""
    defines = {}
    cfg = os.path.join(repo, 'include', 'config')
    for name in sorted(os.listdir(cfg)):
        if not name.endswith('.h') or name in SKIPPED_CONFIGS:
            continue
        with open(os.path.join(cfg, name), encoding='utf-8') as f:
            for line in f:
                m = re.match(r'\s*#\s*define\s+([A-Za-z_]\w*)(?![\w(])\s*(.*)', line)
                if m:
                    defines[m[1]] = re.sub(r'//.*|/\*.*?\*/', '', m[2]).strip()
    return defines


def c_eval(expr, defines, depth=0):
    """Evaluate a preprocessor condition. Unknown names are 0, as in C."""
    expr = re.sub(r'//.*|/\*.*?\*/', '', expr)
    expr = re.sub(r'defined\s*\(\s*(\w+)\s*\)|defined\s+(\w+)',
                  lambda m: '1' if (m[1] or m[2]) in defines else '0', expr)

    def ident(m):
        name = m[0]
        if name == 'TRUE':
            return '1'
        if name in defines and defines[name] and depth < 32:
            return f'({c_eval(defines[name], defines, depth + 1)})'
        return '0'

    expr = re.sub(r'\b[A-Za-z_]\w*\b', ident, expr)
    expr = expr.replace('&&', ' and ').replace('||', ' or ')
    expr = re.sub(r'!(?!=)', ' not ', expr)
    expr = re.sub(r'\b(\d+)[uUlL]+\b', r'\1', expr)
    try:
        return int(eval(expr, {'__builtins__': {}}))  # noqa: S307 - digits and operators only
    except Exception:
        return 0


def active_lines(path, defines):
    """Lines of a header that survive the preprocessor's #if/#else blocks."""
    stack = []  # (parent_active, branch_taken)
    active = True
    with open(path, encoding='utf-8') as f:
        for line in f:
            m = re.match(r'\s*#\s*(ifdef|ifndef|if|elif|else|endif)\b(.*)', line)
            if not m:
                if active:
                    yield line
                continue
            kind, rest = m[1], m[2]
            if kind in ('if', 'ifdef', 'ifndef'):
                if kind == 'if':
                    cond = c_eval(rest, defines)
                else:
                    cond = (rest.split()[0] in defines) == (kind == 'ifdef')
                stack.append((active, bool(cond)))
                active = active and bool(cond)
            elif kind == 'elif' and stack:
                parent, taken = stack[-1]
                cond = not taken and c_eval(rest, defines)
                stack[-1] = (parent, taken or bool(cond))
                active = parent and bool(cond)
            elif kind == 'else' and stack:
                parent, taken = stack[-1]
                stack[-1] = (parent, True)
                active = parent and not taken
            elif kind == 'endif' and stack:
                active = stack.pop()[0]


def balanced(text, start):
    """text[start:] up to the ')' that closes the '(' at text[start - 1]."""
    depth = 1
    for i in range(start, len(text)):
        if text[i] == '(':
            depth += 1
        elif text[i] == ')':
            depth -= 1
            if depth == 0:
                return text[start:i]
    return text[start:]


def split_args(text):
    """'A, f(b, c), D' -> ['A', 'f(b, c)', 'D']."""
    args, depth, cur = [], 0, []
    for ch in text:
        if ch == ',' and depth == 0:
            args.append(''.join(cur).strip())
            cur = []
            continue
        depth += (ch == '(') - (ch == ')')
        cur.append(ch)
    return args + [''.join(cur).strip()]


def expand_macros(text, macros, pattern, depth=0):
    """Expand the family files' own macros, e.g. SPEWPA_SPECIES_INFO(POLAR)."""
    if not pattern or depth > 8:
        return text
    out, pos = [], 0
    while m := pattern.search(text, pos):
        params, body = macros[m[1]]
        end = m.end()
        if params is not None:
            call = re.match(r'\s*\(', text[end:])
            if not call:
                out.append(text[pos:end])
                pos = end
                continue
            start = end + call.end()
            inner = balanced(text, start)
            end = start + len(inner) + 1
            args = dict(zip(params, split_args(inner)))
            body = re.sub(r'\w+', lambda w: args.get(w[0], w[0]), body)
            body = re.sub(r'\s*##\s*', '', body)
        out += [text[pos:m.start()], expand_macros(body, macros, pattern, depth + 1)]
        pos = end
    out.append(text[pos:])
    return ''.join(out)


class SpeciesInfo:
    """Which species the build enables, their flags, and their pre-evolutions."""

    def __init__(self, repo):
        self.constants = AA.load_species_constants(repo)
        defines = parse_defines(repo)
        info_dir = os.path.join(repo, 'src', 'data', 'pokemon', 'species_info')
        entries = collections.defaultdict(list)
        entry_files = {}
        macros = {}  # name -> (params or None, body)
        for name in sorted(os.listdir(info_dir)):
            if not re.fullmatch(r'gen_\d+_families\.h', name):
                continue
            current = None
            macro = None  # [name, params, body lines] while reading a multi-line #define
            for line in active_lines(os.path.join(info_dir, name), defines):
                line = line.rstrip('\n')
                if macro:
                    macro[2].append(line.rstrip().removesuffix('\\'))
                    if not line.rstrip().endswith('\\'):
                        macros[macro[0]] = (macro[1], '\n'.join(macro[2]))
                        macro = None
                    continue
                m = re.match(r'\s*#\s*define\s+(\w+)(?:\(([^)]*)\))?\s*(.*)', line)
                if m:
                    params = [x.strip() for x in m[2].split(',')] if m[2] is not None else None
                    body = m[3].rstrip()
                    if body.endswith('\\'):
                        macro = [m[1], params, [body.removesuffix('\\')]]
                    else:
                        macros[m[1]] = (params, body)
                    continue
                m = re.match(r'\s*\[(SPECIES_\w+)\]\s*=', line)
                if m:
                    current = m[1]
                    entry_files.setdefault(current, name)
                if current:
                    entries[current].append(line + '\n')
        with open(os.path.join(repo, 'include', 'constants', 'species.h'), encoding='utf-8') as f:
            # SPECIES_BURMY = SPECIES_BURMY_PLANT and the like
            self.alias = dict(re.findall(r'^\s*(SPECIES_\w+)\s*=\s*(SPECIES_\w+)\s*,', f.read(), re.M))
        self.enabled = set(entries) & self.constants
        self.enabled |= {a for a in self.alias if self.canon(a) in self.enabled}
        self.flags = {}
        self.pre_evos = collections.defaultdict(list)  # species -> [(from, method, param)]
        # Generation of each species' family file; restock() refines it from the pools.
        self.gen = {sp: int(re.search(r'\d+', name)[0]) for sp, name in entry_files.items()}
        pattern = re.compile(r'\b(' + '|'.join(map(re.escape, macros)) + r')\b') if macros else None
        for sp, lines in entries.items():
            text = expand_macros(''.join(lines), macros, pattern)
            self.flags[sp] = set(re.findall(r'\.(is\w+)\s*=\s*TRUE', text))
            m = re.search(r'\.evolutions\s*=\s*EVOLUTION\(', text)
            if not m:
                continue
            for method, param, target in re.findall(
                    r'\{\s*(EVO_\w+)\s*,\s*([^,{}]+?)\s*,\s*(SPECIES_\w+)', balanced(text, m.end())):
                if target in self.enabled:
                    self.pre_evos[self.canon(target)].append((sp, method, param))
        # A regional form counts as its form's generation, not its family file's.
        for sp, flags in self.flags.items():
            for flag in flags & REGIONAL_FLAGS:
                self.gen[sp] = REGIONAL_FORM_GEN[flag]
        self._min_level = {}

    def canon(self, species):
        seen = set()
        while species in self.alias and species not in seen:
            seen.add(species)
            species = self.alias[species]
        return species

    def flags_of(self, species):
        return self.flags.get(self.canon(species), set())

    def gen_of(self, species):
        return self.gen.get(self.canon(species))

    def learn_gens(self, pools):
        """Take each pool species' generation from the pools (PokeAPI), which,
        unlike the family files, put Pichu in Gen 2."""
        for e in pool_entries(pools):
            self.gen[self.canon(e['species'])] = e['introduced_gen']

    def min_level(self, species, _seen=()):
        """Earliest level a species can have through its evolution line."""
        species = self.canon(species)
        if species in self._min_level:
            return self._min_level[species]
        options = []
        path = _seen + (species,)
        for src, method, param in self.pre_evos.get(species, ()):
            if src in _seen:
                continue
            base = self.min_level(src, path)
            if method.startswith('EVO_LEVEL') and param.isdigit() and int(param) > 0:
                options.append(max(base, int(param)))
            elif method == 'EVO_SPLIT_FROM_EVO' and param not in path:
                options.append(self.min_level(param, path))  # Shedinja: as Ninjask
            elif src in BABY_SPECIES:
                options.append(base)
            else:
                options.append(max(base + NONLEVEL_EVO_GAP, NONLEVEL_EVO_FLOOR))
        best = min(options, default=1)
        self._min_level[species] = best
        return best

    def family(self, species):
        """First stage of a species' evolution line (Golbat -> Zubat)."""
        return self.devolve(species, 0)

    def devolve(self, species, level):
        """Walk back down the evolution line until the species fits ``level``."""
        seen = {self.canon(species)}
        while self.min_level(species) > level:
            pres = [p[0] for p in self.pre_evos.get(self.canon(species), ()) if p[0] not in seen]
            if not pres:
                break
            species = min(pres, key=lambda s: (self.min_level(s), s))
            seen.add(species)
        return species


def pool_entries(pools):
    """Every species entry of every archetype pool."""
    for arch in pools['archetypes'].values():
        for pool in arch.get('pools', {}).values():
            yield from pool


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def parse_gens(text):
    """'1-3,5' -> {1, 2, 3, 5}."""
    gens = set()
    for part in filter(None, (p.strip() for p in text.split(','))):
        lo, _, hi = part.partition('-')
        try:
            span = range(int(lo), int(hi or lo) + 1)
        except ValueError:
            raise ValueError(f'not a generation or range: {part!r}') from None
        if not span:  # '9-4': an empty set would mean every generation
            raise ValueError(f'empty generation range {part!r}')
        gens.update(span)
    return gens


def parse_species_list(values):
    out = set()
    for v in [values] if isinstance(values, str) else values or ():
        for s in filter(None, (x.strip() for x in v.split(','))):
            out.add(s if s.startswith('SPECIES_') else 'SPECIES_' + s.upper())
    return out


class MapSettings(NamedTuple):
    ratio: float
    allow: frozenset
    deny: frozenset
    new_species: int | None
    skip: bool


@dataclasses.dataclass(frozen=True)
class Settings:
    """Restock options; the fields are the --config keys (see OPTIONS)."""
    ratio: float = DEFAULT_RATIO
    seed: int = DEFAULT_SEED
    regions: frozenset = frozenset(DEFAULT_REGIONS)
    gens: frozenset | None = None
    gen_weight: dict = dataclasses.field(default_factory=dict)
    allow: frozenset = frozenset()
    deny: frozenset = frozenset()
    allow_legendaries: bool = False
    maps: dict = dataclasses.field(default_factory=dict)  # base_label -> per-map options
    new_species: int | None = None
    drop_rare_natives: bool = not KEEP_EVERY_NATIVE
    no_regional_forms: bool = False

    def __post_init__(self):
        for name, value in (('ratio', min(max(float(self.ratio), 0.0), 1.0)),
                            ('regions', frozenset(self.regions)),
                            ('gens', frozenset(self.gens) if self.gens else None),
                            ('gen_weight', dict(self.gen_weight or {})),
                            ('allow', frozenset(self.allow)), ('deny', frozenset(self.deny)),
                            ('maps', dict(self.maps or {}))):
            object.__setattr__(self, name, value)

    @property
    def keep_every_native(self):
        return not self.drop_rare_natives

    @property
    def regional_forms(self):
        return not self.no_regional_forms

    def for_map(self, label):
        """The table options for one map, with its per-map overrides applied."""
        o = self.maps.get(label, {})
        return MapSettings(float(o.get('ratio', self.ratio)),
                           frozenset(parse_species_list(o['allow'])) if 'allow' in o else self.allow,
                           self.deny | parse_species_list(o.get('deny')),
                           o.get('new_species', self.new_species),
                           bool(o.get('skip')))


# ---------------------------------------------------------------------------
# Options: one table for the command line, --config and per-map overrides
# ---------------------------------------------------------------------------
# Each ``parse`` checks a --config value (any JSON type) and returns the
# Settings value, raising ValueError with what it expected. The command-line
# types go through the same functions.

def is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def as_ratio(v):
    if not is_number(v) or not 0 <= v <= 1:
        raise ValueError(f'expected a number from 0 to 1, got {v!r}')
    return float(v)


def as_int(v):
    if not isinstance(v, int) or isinstance(v, bool):
        raise ValueError(f'expected a whole number, got {v!r}')
    return v


def as_count(v):
    if as_int(v) < 0:
        raise ValueError(f'expected 0 or more, got {v!r}')
    return v


def as_bool(v):
    if not isinstance(v, bool):
        raise ValueError(f'expected true or false, got {v!r}')
    return v


def as_names(v):
    """'a,b' or ['a', 'b'] -> ['a', 'b']."""
    if isinstance(v, str):
        return [s.strip() for s in v.split(',') if s.strip()]
    if isinstance(v, list) and all(isinstance(s, str) for s in v):
        return v
    raise ValueError(f'expected a comma-separated string or a list of strings, got {v!r}')


def as_species(v):
    return frozenset(parse_species_list(as_names(v)))


def as_gens(v):
    gens, detail = None, ''
    if isinstance(v, str):
        try:
            gens = parse_gens(v)
        except ValueError as e:
            detail = f' ({e})'
    elif isinstance(v, list) and all(isinstance(g, int) and not isinstance(g, bool) for g in v):
        gens = set(v)
    if gens:
        return gens
    if gens is not None:  # an empty set would mean every generation: that's leaving gens out
        detail = ' (no generations; leave gens out to allow every generation)'
    raise ValueError(f"expected generations like '4-9' or a list of numbers, got {v!r}{detail}")


def as_gen_weight(v):
    """{'4': 2} -> {4: 2.0}."""
    if not isinstance(v, dict):
        raise ValueError(f'expected an object of generation: factor, got {v!r}')
    return dict(gen_factor(g, f) for g, f in v.items())


def gen_factor(gen, factor):
    try:
        gen = int(gen)
    except ValueError:
        raise ValueError(f'expected a generation number, got {gen!r}') from None
    if not is_number(factor) or factor < 0:
        raise ValueError(f'expected a factor of 0 or more for gen {gen}, got {factor!r}')
    return gen, float(factor)


def as_map_overrides(v):
    """{label: {per-map key: value}}; labels are checked against the base later."""
    if not isinstance(v, dict):
        raise ValueError(f'expected an object of map label: overrides, got {v!r}')
    errors = []
    for label, o in v.items():
        if not isinstance(o, dict):
            errors.append(f'{label}: expected an object, got {o!r}')
            continue
        errors += [f'{label}: {e}' for e in parse_keys(o, MAP_OPTIONS, 'per-map key')[1]]
    if errors:
        raise ValueError('; '.join(errors))
    return v


def cli_type(parse, convert=str):
    """argparse type= that runs ``parse(convert(text))``."""
    def to_value(text):
        try:
            return parse(convert(text))
        except ValueError as e:
            raise argparse.ArgumentTypeError(str(e)) from None
    to_value.__name__ = parse.__name__
    return to_value


def gen_weight_pair(text):
    """'4=2' -> (4, 2.0)."""
    gen, eq, factor = text.partition('=')
    if not eq:
        raise ValueError(f'expected GEN=FACTOR, e.g. 4=2, got {text!r}')
    return gen_factor(gen, float(factor))


def cli_wins(cli, cfg):
    return cfg if cli is None else cli


def cli_lists_win(cli, cfg):
    """Repeated --allow/--deny replace the config list."""
    return frozenset().union(*cli) if cli else cfg


def cli_gen_weights_win(cli, cfg):
    return {**(cfg or {}), **dict(cli or ())}


class Option(NamedTuple):
    name: str          # the flag is --name-with-dashes; with a parse, also the Settings field and config key
    flag: dict | None  # argparse keywords, or None for config only
    parse: Callable | None = None  # None: command line only (so the --maps file isn't the config's maps)
    per_map: bool = False  # also a per-map override
    top: bool = True       # also a top-level --config key
    merge: Callable = cli_wins  # (flag value or None, config value or None) -> Settings value


OPTIONS = (
    Option('ratio', dict(type=cli_type(as_ratio, float),
                         help=f'share of each table given to pool species, 0-1 (default {DEFAULT_RATIO})'),
           as_ratio, per_map=True),
    Option('seed', dict(type=int, help=f'RNG seed (default {DEFAULT_SEED})'), as_int),
    Option('regions', dict(type=cli_type(as_names),
                           help=f'comma list of regions to restock (default {",".join(DEFAULT_REGIONS)})'),
           as_names),
    Option('gens', dict(type=cli_type(as_gens),
                        help="generations new species may come from, e.g. '4-9' (default all); "
                             "a regional form counts as its form's: Alola 7, Galar and Hisui 8, Paldea 9"),
           as_gens),
    Option('gen_weight', dict(type=cli_type(gen_weight_pair), action='append', metavar='GEN=FACTOR',
                              help="multiply the draw weight of a generation's species, e.g. 4=2 (repeatable)"),
           as_gen_weight, merge=cli_gen_weights_win),
    Option('allow', dict(type=cli_type(as_species), action='append', metavar='SPECIES,...',
                         help='only draw new species from this list (repeatable)'),
           as_species, per_map=True, merge=cli_lists_win),
    Option('deny', dict(type=cli_type(as_species), action='append', metavar='SPECIES,...',
                        help='never place these species, and drop them where they are native (repeatable)'),
           as_species, per_map=True, merge=cli_lists_win),
    Option('allow_legendaries', dict(action='store_true', default=None,
                                     help='let legendary, mythical, Ultra Beast and Paradox species into the draw'),
           as_bool),
    Option('drop_rare_natives', dict(action='store_true', default=None,
                                     help="let a table's own rare species lose their only slot "
                                          "(default: each keeps one)"),
           as_bool),
    Option('no_regional_forms', dict(action='store_true', default=None,
                                     help='never draw Alolan, Galarian, Hisuian or Paldean forms'),
           as_bool),
    Option('new_species', dict(type=cli_type(as_count, int),
                               help="new species per table (default: scales with ratio and the table's "
                                    "own species count)"),
           as_count, per_map=True),
    Option('maps', None, as_map_overrides),
    Option('skip', None, as_bool, per_map=True, top=False),
    Option('config', dict(help='JSON file with any of the options above plus per-map overrides; '
                               'flags win over it. See README.')),
    Option('base', dict(default=AA.VANILLA_WILD,
                        help='vanilla wild_encounters.json the natives come from (default: the committed '
                             'snapshot)')),
    Option('wild', dict(default=AA.SRC_WILD, help='file --write overwrites (not a source of natives)')),
    Option('pools', dict(default=os.path.join(AA.DEFAULT_OUT, 'archetype_pools.json'))),
    Option('maps', dict(default=os.path.join(AA.DEFAULT_OUT, 'emerald_maps.json'))),
    Option('out_dir', dict(default=DEFAULT_OUT_DIR, help='where the preview JSON and report go')),
    Option('write', dict(action='store_true', help='also overwrite --wild with the result')),
    Option('force', dict(action='store_true',
                         help='accept a --base that restock wrote, and --write over a --wild that differs '
                              'from --base in more than species')),
    Option('repo', dict(default=AA.REPO, help=argparse.SUPPRESS)),
)
CONFIG_OPTIONS = {o.name: o for o in OPTIONS if o.parse and o.top}
MAP_OPTIONS = {o.name: o for o in OPTIONS if o.per_map}


def parse_keys(obj, options, what):
    """Parsed values of a config object, and one message per bad key or value."""
    values, errors = {}, []
    for key, v in obj.items():
        o = options.get(key)
        if o is None:
            errors.append(f'unknown {what} {key!r} (expected one of: {", ".join(options)})')
            continue
        try:
            values[key] = o.parse(v)
        except ValueError as e:
            errors.append(f'{key}: {e}')
    return values, errors


def add_options(p):
    for o in OPTIONS:
        if o.flag is not None:
            p.add_argument('--' + o.name.replace('_', '-'), **o.flag)


def settings_from(args, cfg):
    """Settings from parsed flags and parsed --config values; flags win."""
    values = {}
    for o in CONFIG_OPTIONS.values():
        v = o.merge(getattr(args, o.name) if o.flag else None, cfg.get(o.name))
        if v is not None:
            values[o.name] = v
    return Settings(**values)


# ---------------------------------------------------------------------------
# Restocking
# ---------------------------------------------------------------------------

def assign_slots(targets, rates, ensure=()):
    """Give each slot to the species furthest below its target share.

    Slots are handed out from the highest rate down, so the most common
    species take the 20% slots. Then every species in ``ensure`` that got no
    slot takes the lowest-rate slot of a species that has more than one.
    Returns one species per slot, in slot order.
    """
    total = sum(rates)
    assigned = collections.Counter()
    out = [None] * len(rates)
    order = sorted(targets, key=lambda s: (-targets[s], s))
    for i in sorted(range(len(rates)), key=lambda i: (-rates[i], i)):
        sp = max(order, key=lambda s: targets[s] * total - assigned[s])
        out[i] = sp
        assigned[sp] += rates[i]
    for sp in sorted(set(ensure) - set(out), key=lambda s: (-targets.get(s, 0), s)):
        count = collections.Counter(out)
        spare = [i for i in range(len(rates)) if count[out[i]] > 1]
        if spare:
            out[min(spare, key=lambda i: (rates[i], -i))] = sp
    return out


def weighted_sample(rng, weights, k, group=lambda s: s):
    """k keys drawn by weight, without replacement, at most one per group."""
    pool = dict(weights)
    picked = []
    for _ in range(min(k, len(pool))):
        keys = sorted(pool)
        r = rng.random() * sum(pool[s] for s in keys)
        for s in keys:
            r -= pool[s]
            if r <= 0:
                break
        picked.append(s)
        pool = {o: w for o, w in pool.items() if group(o) != group(s)}
        if not pool:
            break
    return picked


def candidates(pool, info, settings, allow, deny, natives, levels):
    """Pool species that may be added to a table, with their draw weights.

    Species from an evolution line the table already has are left out. So is
    any species that would be devolved, for one of the slot ``levels``, into a
    stage that fails the filters: denying Zubat also keeps Golbat out of
    low-level tables.
    """
    def allowed(sp, gen):
        if sp not in info.enabled or sp in deny or (allow and sp not in allow):
            return False
        if settings.gens and gen not in settings.gens:
            return False
        flags = info.flags_of(sp)
        return not (flags & BATTLE_ONLY_FLAGS
                    or (not settings.allow_legendaries and flags & LEGENDARY_FLAGS)
                    or (not settings.regional_forms and flags & REGIONAL_FLAGS))

    native_lines = {info.family(s) for s in natives}
    out = {}
    for e in pool:
        sp = e['species']
        if info.family(sp) in native_lines or not allowed(sp, e['introduced_gen']):
            continue
        stages = {info.devolve(sp, lv) for lv in levels} - {sp}
        if not all(allowed(st, info.gen_of(st)) for st in stages):
            continue
        w = e['share'] * settings.gen_weight.get(e['introduced_gen'], 1.0)
        if w > 0:
            out[sp] = out.get(sp, 0) + w
    return out


def restock_table(mons, rates, pool, info, settings, label, field):
    """New species for one table's slots, or None to leave it alone."""
    ratio, allow, deny, new_species, skip = settings.for_map(label)
    ratio = min(max(ratio, 0.0), 1.0)
    natives = collections.Counter()
    for m, r in zip(mons, rates):
        natives[m['species']] += r
    real = [s for s in natives if s != 'SPECIES_NONE']
    kept = {s: natives[s] for s in real if s not in deny}
    denied = len(kept) < len(real)  # denied natives go even if nothing is added
    if skip or (ratio == 0 and not denied):
        return None
    if not kept:
        ratio = 1.0
    if new_species is None:
        n = len(kept) or len(real) or 1
        new_species = n if ratio >= 1 else max(1, round(n * ratio / (1 - ratio)))
    keep_all = ratio < 1 and settings.keep_every_native
    room = len(rates) - (len(kept) if keep_all else 0)
    cands, picked = {}, []
    if ratio > 0 and room > 0:
        cands = candidates(pool, info, settings, allow, deny, set(natives),
                           {m['min_level'] for m in mons})
        rng = random.Random(f'{settings.seed}/{label}/{field}')
        picked = weighted_sample(rng, cands, min(int(new_species), room), info.family)
    if not picked and not denied:
        return None
    targets = collections.Counter()
    kept_total = sum(kept.values())
    for s, r in kept.items() if ratio < 1 or not picked else ():
        targets[s] += (1 - ratio) * r / kept_total
    picked_total = sum(cands[s] for s in picked)
    for s in picked:
        targets[s] += ratio * cands[s] / picked_total
    if not targets:  # every native denied and nothing to draw: no species left to fill with
        print(f'warning: {label} {field}: every native is denied and nothing can be drawn; '
              f'left as is', file=sys.stderr)
        return None
    slots = assign_slots(targets, rates, kept if keep_all else ())
    return [s if s in natives else info.devolve(s, m['min_level'])
            for s, m in zip(slots, mons)]


def tables_of(enc, emerald, field_defs):
    """(field, rod or None, slot indices, archetype info) for every table of a map."""
    for field in TABLE_FIELDS:
        if field in enc and field in emerald:
            yield field, None, list(range(len(enc[field]['mons']))), emerald[field]
    if 'fishing_mons' in enc and 'fishing_mons' in emerald:
        for rod, idxs in field_defs['fishing_mons']['groups'].items():
            if rod in emerald['fishing_mons']:
                yield 'fishing_mons', rod, idxs, emerald['fishing_mons'][rod]


def wild_headers(wild):
    return next(g for g in wild['wild_encounter_groups'] if g['label'] == 'gWildMonHeaders')


def restock(wild, emerald_maps, pools, info, settings):
    """Restocked copy of wild_encounters.json, plus a list of changed tables."""
    wild = copy.deepcopy(wild)
    group = wild_headers(wild)
    field_defs = {fd['type']: fd for fd in group['fields']}
    archetypes = pools['archetypes']
    info.learn_gens(pools)
    changes = []
    unmapped = [e['base_label'] for e in group['encounters'] if e['base_label'] not in emerald_maps]
    if unmapped:
        print(f'warning: {len(unmapped)} gWildMonHeaders labels have no emerald_maps entry and are '
              f'left alone (rerun build?): {", ".join(unmapped)}', file=sys.stderr)
    for enc in group['encounters']:
        label = enc['base_label']
        em = emerald_maps.get(label)
        if not em or em.get('region') not in settings.regions:
            continue
        for field, rod, idxs, arch in tables_of(enc, em, field_defs):
            pool = archetypes.get(arch['archetype'], {}).get('pools', {}).get(arch['pool'])
            if not pool:
                continue
            mons = [enc[field]['mons'][i] for i in idxs]
            rates = [field_defs[field]['encounter_rates'][i] for i in idxs]
            table = f'{field}:{rod}' if rod else field
            new = restock_table(mons, rates, pool, info, settings, label, table)
            if new is None or new == [m['species'] for m in mons]:
                continue
            changes.append({'label': label, 'map': enc.get('map'), 'table': table,
                            'archetype': arch['archetype'],
                            'slots': [{'rate': r, 'levels': [m['min_level'], m['max_level']],
                                       'before': m['species'], 'after': s}
                                      for m, r, s in zip(mons, rates, new)]})
            for m, s in zip(mons, new):
                m['species'] = s
    return wild, changes


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def species_shares(slots, key):
    c = collections.Counter()
    for s in slots:
        c[s[key]] += s['rate']
    return c


def short(sp):
    return sp.removeprefix('SPECIES_')


def fmt_shares(shares):
    return ', '.join(f'{short(k)} {v}%' for k, v in sorted(shares.items(), key=lambda kv: (-kv[1], kv[0])))


def summarize(changes):
    added = collections.Counter()
    removed = collections.Counter()
    for ch in changes:
        before = {sl['before'] for sl in ch['slots']}
        after = {sl['after'] for sl in ch['slots']}
        added.update(after - before)
        removed.update(before - after)
    return {'tables_changed': len(changes),
            'maps_changed': len({ch['label'] for ch in changes}),
            'slots_changed': sum(s['before'] != s['after'] for ch in changes for s in ch['slots']),
            'distinct_species_added': len(added),
            'distinct_species_removed': len(removed),
            'added': added, 'removed': removed}


def write_report(path, changes, settings):
    s = summarize(changes)
    lines = ['# Restock report', '',
             'Generated by `tools/area_archetypes/area_archetypes.py restock`.', '',
             f'- ratio {settings.ratio}, seed {settings.seed}, regions {", ".join(sorted(settings.regions))}, '
             f'gens {",".join(map(str, sorted(settings.gens))) if settings.gens else "all"}, '
             f'legendaries {"allowed" if settings.allow_legendaries else "excluded"}, '
             f'regional forms {"allowed" if settings.regional_forms else "excluded"}',
             f'- {s["maps_changed"]} maps, {s["tables_changed"]} tables, {s["slots_changed"]} slots changed',
             f'- {s["distinct_species_added"]} species added somewhere, '
             f'{s["distinct_species_removed"]} removed somewhere', '']
    for ch in changes:
        lines += [f'## {ch["label"]} {ch["table"]} ({ch["archetype"]})', '',
                  f'before: {fmt_shares(species_shares(ch["slots"], "before"))}  ',
                  f'after: {fmt_shares(species_shares(ch["slots"], "after"))}', '',
                  '| slot | rate | levels | before | after |', '|---|---|---|---|---|']
        for i, sl in enumerate(ch['slots']):
            lv = sl['levels'][0] if sl['levels'][0] == sl['levels'][1] else f'{sl["levels"][0]}-{sl["levels"][1]}'
            after = short(sl['after']) if sl['after'] != sl['before'] else '='
            lines.append(f'| {i} | {sl["rate"]} | {lv} | {short(sl["before"])} | {after} |')
        lines.append('')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return s


def dump_wild(wild, path):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(wild, indent=2, ensure_ascii=False) + '\n')


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def skeleton(wild):
    """wild without its stamp and species: equal for two files that differ only by restocking."""
    wild = {k: v for k, v in wild.items() if k != AA.RESTOCK_STAMP}
    return json.loads(json.dumps(wild), object_hook=lambda d: {**d, 'species': None} if 'species' in d else d)


def main(argv=None):
    p = argparse.ArgumentParser(prog='area_archetypes.py restock', description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    add_options(p)
    args = p.parse_args(argv)

    cfg = {}
    if args.config:
        raw = load_json(args.config)
        if not isinstance(raw, dict):
            p.error(f'--config {args.config}: expected a JSON object')
        cfg, errors = parse_keys(raw, CONFIG_OPTIONS, 'key')
        if errors:
            p.error(f'--config {args.config}: ' + '; '.join(errors))
    settings = settings_from(args, cfg)

    info = SpeciesInfo(args.repo)
    named = settings.allow | settings.deny
    for o in settings.maps.values():
        named |= parse_species_list(o.get('allow')) | parse_species_list(o.get('deny'))
    unknown = sorted(named - info.constants)
    if unknown:
        sys.exit(f'unknown species: {", ".join(unknown)}')
    base, base_sha256 = AA.load_base(args.base, args.force)
    emerald_maps = load_json(args.maps)
    unknown = sorted(set(settings.maps) - {e['base_label'] for e in wild_headers(base)['encounters']})
    if unknown:
        p.error(f'maps: not a gWildMonHeaders base label in {args.base}: {", ".join(unknown)}')
    known = {m['region'] for m in emerald_maps.values() if m.get('region')}
    regions_in = f'(regions in {args.maps}: {", ".join(sorted(known))})'
    if not settings.regions:
        p.error(f'regions: empty, so nothing would be restocked {regions_in}')
    unknown = sorted(settings.regions - known)
    if unknown:
        p.error(f'unknown region: {", ".join(unknown)} {regions_in}')
    pools = load_json(args.pools)
    pool_gens = {e['introduced_gen'] for e in pool_entries(pools)}
    if settings.gens and not settings.gens & pool_gens:
        p.error(f'gens: {",".join(map(str, sorted(settings.gens)))} matches no pool species, so nothing '
                f'would be restocked (generations in {args.pools}: {",".join(map(str, sorted(pool_gens)))})')
    if (args.write and not args.force and os.path.exists(args.wild)
            and skeleton(load_json(args.wild)) != skeleton(base)):
        sys.exit(f'{args.wild} differs from {args.base} in more than species (an upstream merge or '
                 f'a hand edit?), and --write would lose that; refresh the baseline (README), '
                 f'or --force to overwrite anyway')
    new, changes = restock(base, emerald_maps, pools, info, settings)
    stamp = {'base_sha256': base_sha256, 'seed': settings.seed, 'ratio': settings.ratio}
    if AA.RESTOCK_STAMP in base:  # --force on a restocked base: keep its history
        stamp['base_restocked_by'] = base[AA.RESTOCK_STAMP]
    new[AA.RESTOCK_STAMP] = stamp
    os.makedirs(args.out_dir, exist_ok=True)
    preview = os.path.join(args.out_dir, 'wild_encounters.json')
    report = os.path.join(args.out_dir, 'restock_report.md')
    dump_wild(new, preview)
    s = write_report(report, changes, settings)
    print(f'{s["maps_changed"]} maps / {s["tables_changed"]} tables / {s["slots_changed"]} slots changed; '
          f'{s["distinct_species_added"]} species added, {s["distinct_species_removed"]} removed')
    print(f'  report: {report}\n  preview: {preview}')
    if args.write:
        dump_wild(new, args.wild)
        print(f'  wrote {args.wild}')
    return new, changes


if __name__ == '__main__':
    main()
