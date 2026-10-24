#!/usr/bin/env python3
"""Restock src/data/wild_encounters.json from the archetype pools.

    python3 tools/area_archetypes/area_archetypes.py restock [options]

Reads ``output/archetype_pools.json`` and ``output/emerald_maps.json`` (from
``build``), so it doesn't need the PokeAPI cache. For every encounter table of
every selected map it mixes the table's own species with species drawn from
the table's archetype pool, then hands out the table's slots so the most
common species get the highest-rate slots. Slot counts, encounter rates and
every slot's level range stay as they are; only ``species`` changes.

Without ``--write`` nothing in src/ is touched: the restocked JSON and a
slot-by-slot report go to ``--out-dir`` for review. Same seed and options
give the same output.

Every default below is a placeholder until the design questions in issue #8
are settled. Each is also a command-line flag.
"""

import argparse
import collections
import copy
import json
import os
import random
import re
import sys

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
# Evolutions out of baby species (no eggs, but evolves) have no floor, so
# Pikachu and Marill stay low-level species.
NONLEVEL_EVO_GAP = 10
NONLEVEL_EVO_FLOOR = 30
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


class SpeciesInfo:
    """Which species the build enables, their flags, and their pre-evolutions."""

    def __init__(self, repo):
        self.constants = AA.load_species_constants(repo)
        defines = parse_defines(repo)
        info_dir = os.path.join(repo, 'src', 'data', 'pokemon', 'species_info')
        entries = collections.defaultdict(list)
        for name in sorted(os.listdir(info_dir)):
            if not re.fullmatch(r'gen_\d+_families\.h', name):
                continue
            current = None
            for line in active_lines(os.path.join(info_dir, name), defines):
                m = re.match(r'\s*\[(SPECIES_\w+)\]\s*=', line)
                if m:
                    current = m[1]
                if current:
                    entries[current].append(line)
        with open(os.path.join(repo, 'include', 'constants', 'species.h'), encoding='utf-8') as f:
            # SPECIES_BURMY = SPECIES_BURMY_PLANT and the like
            self.alias = dict(re.findall(r'^\s*(SPECIES_\w+)\s*=\s*(SPECIES_\w+)\s*,', f.read(), re.M))
        self.enabled = set(entries) & self.constants
        self.enabled |= {a for a in self.alias if self.canon(a) in self.enabled}
        self.flags = {}
        self.pre_evos = collections.defaultdict(list)  # species -> [(from, method, param)]
        self.baby = set()
        for sp, lines in entries.items():
            text = ''.join(lines)
            self.flags[sp] = set(re.findall(r'\.(is\w+)\s*=\s*TRUE', text))
            m = re.search(r'\.evolutions\s*=\s*EVOLUTION\(', text)
            if not m:
                continue
            if 'EGG_GROUP_NO_EGGS_DISCOVERED' in text:
                self.baby.add(sp)
            for method, param, target in re.findall(
                    r'\{\s*(EVO_\w+)\s*,\s*([^,{}]+?)\s*,\s*(SPECIES_\w+)', balanced(text, m.end())):
                if target in self.enabled:
                    self.pre_evos[self.canon(target)].append((sp, method, param))
        self._min_level = {}

    def canon(self, species):
        seen = set()
        while species in self.alias and species not in seen:
            seen.add(species)
            species = self.alias[species]
        return species

    def flags_of(self, species):
        return self.flags.get(self.canon(species), set())

    def min_level(self, species, _seen=()):
        """Earliest level a species can have through its evolution line."""
        species = self.canon(species)
        if species in self._min_level:
            return self._min_level[species]
        options = []
        for src, method, param in self.pre_evos.get(species, ()):
            if src in _seen:
                continue
            base = self.min_level(src, _seen + (species,))
            if method.startswith('EVO_LEVEL') and param.isdigit() and int(param) > 0:
                options.append(max(base, int(param)))
            elif method == 'EVO_SPLIT_FROM_EVO' and param not in _seen + (species,):
                options.append(self.min_level(param, _seen + (species,)))  # Shedinja: as Ninjask
            elif src in self.baby:
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


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def parse_gens(text):
    """'1-3,5' -> {1, 2, 3, 5}."""
    gens = set()
    for part in filter(None, (p.strip() for p in text.split(','))):
        lo, _, hi = part.partition('-')
        gens.update(range(int(lo), int(hi or lo) + 1))
    return gens


def parse_species_list(values):
    out = set()
    for v in values or ():
        for s in filter(None, (x.strip() for x in v.split(','))):
            out.add(s if s.startswith('SPECIES_') else 'SPECIES_' + s.upper())
    return out


class Settings:
    def __init__(self, ratio=DEFAULT_RATIO, seed=DEFAULT_SEED, regions=DEFAULT_REGIONS,
                 gens=None, gen_weight=None, allow=(), deny=(), allow_legendaries=False,
                 maps=None, new_species=None, keep_every_native=KEEP_EVERY_NATIVE):
        self.ratio = ratio
        self.seed = seed
        self.regions = set(regions)
        self.gens = set(gens) if gens else None
        self.gen_weight = dict(gen_weight or {})
        self.allow = set(allow)
        self.deny = set(deny)
        self.allow_legendaries = allow_legendaries
        self.maps = maps or {}  # base_label -> {ratio, allow, deny, skip, new_species}
        self.new_species = new_species
        self.keep_every_native = keep_every_native

    def for_map(self, label):
        """(ratio, allow, deny, new_species, skip) with per-map overrides applied."""
        o = self.maps.get(label, {})
        return (float(o.get('ratio', self.ratio)),
                parse_species_list(o['allow']) if 'allow' in o else self.allow,
                self.deny | parse_species_list(o.get('deny')),
                o.get('new_species', self.new_species),
                bool(o.get('skip')))


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


def candidates(pool, info, settings, allow, deny, natives):
    """Pool species that may be added to a table, with their draw weights.

    Species from an evolution line the table already has are left out.
    """
    native_lines = {info.family(s) for s in natives}
    out = {}
    for e in pool:
        sp = e['species']
        if sp not in info.enabled or sp in deny or info.family(sp) in native_lines:
            continue
        if allow and sp not in allow:
            continue
        if settings.gens and e['introduced_gen'] not in settings.gens:
            continue
        flags = info.flags_of(sp)
        if flags & BATTLE_ONLY_FLAGS:
            continue
        if not settings.allow_legendaries and flags & LEGENDARY_FLAGS:
            continue
        w = e['share'] * settings.gen_weight.get(e['introduced_gen'], 1.0)
        if w > 0:
            out[sp] = out.get(sp, 0) + w
    return out


def restock_table(mons, rates, pool, info, settings, label, field):
    """New species for one table's slots, or None to leave it alone."""
    ratio, allow, deny, new_species, skip = settings.for_map(label)
    ratio = min(max(ratio, 0.0), 1.0)
    if skip or ratio == 0:
        return None
    natives = collections.Counter()
    for m, r in zip(mons, rates):
        natives[m['species']] += r
    kept = {s: r for s, r in natives.items() if s not in deny and s != 'SPECIES_NONE'}
    if not kept:
        ratio = 1.0
    cands = candidates(pool, info, settings, allow, deny, set(natives))
    if not cands:
        return None
    if new_species is None:
        n = max(len(kept), 1)
        new_species = n if ratio >= 1 else max(1, round(n * ratio / (1 - ratio)))
    keep_all = ratio < 1 and settings.keep_every_native
    room = len(rates) - (len(kept) if keep_all else 0)
    if room <= 0:
        return None
    rng = random.Random(f'{settings.seed}/{label}/{field}')
    picked = weighted_sample(rng, cands, min(int(new_species), room), info.family)
    targets = collections.Counter()
    kept_total = sum(kept.values())
    for s, r in kept.items() if ratio < 1 else ():
        targets[s] += (1 - ratio) * r / kept_total
    picked_total = sum(cands[s] for s in picked)
    for s in picked:
        targets[s] += ratio * cands[s] / picked_total
    if not targets:
        return None
    slots = assign_slots(targets, rates, kept if keep_all else ())
    return [s if s in natives else info.devolve(s, m['max_level'])
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


def restock(wild, emerald_maps, pools, info, settings):
    """Restocked copy of wild_encounters.json, plus a list of changed tables."""
    wild = copy.deepcopy(wild)
    group = next(g for g in wild['wild_encounter_groups'] if g['label'] == 'gWildMonHeaders')
    field_defs = {fd['type']: fd for fd in group['fields']}
    archetypes = pools['archetypes']
    changes = []
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
             f'legendaries {"allowed" if settings.allow_legendaries else "excluded"}',
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


def main(argv=None):
    p = argparse.ArgumentParser(prog='area_archetypes.py restock', description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--ratio', type=float,
                   help=f'share of each table given to pool species, 0-1 (default {DEFAULT_RATIO})')
    p.add_argument('--seed', type=int, help=f'RNG seed (default {DEFAULT_SEED})')
    p.add_argument('--regions', help=f'comma list of regions to restock (default {",".join(DEFAULT_REGIONS)})')
    p.add_argument('--gens', help="generations new species may come from, e.g. '4-9' (default all)")
    p.add_argument('--gen-weight', action='append', default=[], metavar='GEN=FACTOR',
                   help="multiply the draw weight of a generation's species, e.g. 4=2 (repeatable)")
    p.add_argument('--allow', action='append', metavar='SPECIES,...',
                   help='only draw new species from this list (repeatable)')
    p.add_argument('--deny', action='append', metavar='SPECIES,...',
                   help='never place these species, and drop them where they are native (repeatable)')
    p.add_argument('--allow-legendaries', action='store_true',
                   help='let legendary, mythical, Ultra Beast and Paradox species into the draw')
    p.add_argument('--drop-rare-natives', action='store_true',
                   help="let a table's own rare species lose their only slot (default: each keeps one)")
    p.add_argument('--new-species', type=int,
                   help='new species per table (default: scales with ratio and the table\'s own species count)')
    p.add_argument('--config', help='JSON file with any of the options above plus per-map overrides; '
                                    'flags win over it. See README.')
    p.add_argument('--wild', default=os.path.join(AA.REPO, 'src', 'data', 'wild_encounters.json'))
    p.add_argument('--pools', default=os.path.join(AA.DEFAULT_OUT, 'archetype_pools.json'))
    p.add_argument('--maps', default=os.path.join(AA.DEFAULT_OUT, 'emerald_maps.json'))
    p.add_argument('--out-dir', default=DEFAULT_OUT_DIR, help='where the preview JSON and report go')
    p.add_argument('--write', action='store_true', help='also overwrite --wild with the result')
    p.add_argument('--repo', default=AA.REPO, help=argparse.SUPPRESS)
    args = p.parse_args(argv)

    cfg = load_json(args.config) if args.config else {}

    def opt(name, default):
        v = getattr(args, name)
        return v if v is not None else cfg.get(name, default)

    gen_weight = {int(k): float(v) for k, v in cfg.get('gen_weight', {}).items()}
    for gw in args.gen_weight:
        g, _, f = gw.partition('=')
        gen_weight[int(g)] = float(f)
    gens = opt('gens', None)
    regions = opt('regions', ','.join(DEFAULT_REGIONS))
    settings = Settings(
        ratio=float(opt('ratio', DEFAULT_RATIO)), seed=int(opt('seed', DEFAULT_SEED)),
        regions=[r.strip() for r in regions.split(',')] if isinstance(regions, str) else regions,
        gens=parse_gens(gens) if isinstance(gens, str) else gens, gen_weight=gen_weight,
        allow=parse_species_list(args.allow or cfg.get('allow')),
        deny=parse_species_list(args.deny or cfg.get('deny')),
        allow_legendaries=args.allow_legendaries or bool(cfg.get('allow_legendaries')),
        maps=cfg.get('maps'), new_species=opt('new_species', None),
        keep_every_native=not (args.drop_rare_natives or cfg.get('drop_rare_natives')))

    info = SpeciesInfo(args.repo)
    named = settings.allow | settings.deny
    for o in settings.maps.values():
        named |= parse_species_list(o.get('allow')) | parse_species_list(o.get('deny'))
    unknown = sorted(named - info.constants)
    if unknown:
        sys.exit(f'unknown species: {", ".join(unknown)}')
    wild = load_json(args.wild)
    new, changes = restock(wild, load_json(args.maps), load_json(args.pools), info, settings)
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
