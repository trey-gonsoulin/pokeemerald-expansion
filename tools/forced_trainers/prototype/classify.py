"""Classify each story stage's regular trainers as FORCED / AVOIDABLE / UNCERTAIN.

Run: python3 classify.py [--verbose]  -> writes trainers.json next to this file.
"""
import itertools
import re
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import collections
from engine import REPO, Map, abilities, world_search, FOLDER_OF  # noqa: E402
sys.path.insert(0, os.path.join(REPO, 'tools/rebalance'))
import gamedata as G  # noqa: E402
import rebalance as R  # noqa: E402
from specs import AREAS, MANUAL, OPTIONAL_MAPS, BOSS_NOTES  # noqa: E402

VERBOSE = '--verbose' in sys.argv


def tiles_for(maps, spec):
    """'Folder/kind:arg' ('|'-separated alternatives) -> (set of (folder, xy), set of (folder, xy, edge dir))."""
    if '|' in spec:
        tiles, edges = set(), set()
        for part in spec.split('|'):
            t, e = tiles_for(maps, part)
            tiles |= t
            edges |= e
        return tiles, edges
    folder, _, rest = spec.partition('/')
    m = maps[folder]
    kind, _, arg = rest.partition(':')
    if kind == 'conn':
        d, _, target = arg.partition(':')
        rng = set()
        for cd, cm, off in m.conn_list:
            if cd == d and (not target or cm == 'MAP_' + target):
                om = Map(FOLDER_OF[cm])
                size = om.h if d in ('left', 'right') else om.w
                rng |= set(range(off, off + size))
        if not rng:
            raise SystemExit(f'{folder}: no {d} connection to {target or "anything"}')
        if d == 'left':
            ts = {(0, y) for y in range(m.h)}
        elif d == 'right':
            ts = {(m.w - 1, y) for y in range(m.h)}
        elif d == 'up':
            ts = {(x, 0) for x in range(m.w)}
        else:
            ts = {(x, m.h - 1) for x in range(m.w)}
        ts = {t for t in ts if (t[1] if d in ('left', 'right') else t[0]) in rng}
        ts = {t for t in ts if not m.coll[t]}
        return {(folder, t) for t in ts}, {(folder, t, d) for t in ts}
    if kind == 'deep':  # the deep-water (dive) patch nearest x,y
        x, y = map(int, arg.split(','))
        deep = [p for p, b in m.mb.items() if b == 'MB_DEEP_WATER']
        start = min(deep, key=lambda p: abs(p[0] - x) + abs(p[1] - y))
        patch, todo = {start}, [start]
        while todo:
            p = todo.pop()
            for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                q = (p[0] + dx, p[1] + dy)
                if q not in patch and m.mb.get(q) == 'MB_DEEP_WATER':
                    patch.add(q)
                    todo.append(q)
        return {(folder, p) for p in patch}, set()
    if kind == 'warp':
        return {(folder, (m.warps[int(i)]['x'], m.warps[int(i)]['y'])) for i in arg.split(',')}, set()
    if kind == 'xy':
        return {(folder, tuple(int(v) for v in part.split(','))) for part in arg.split(';')}, set()
    if kind == 'rect':  # x0,y0,x1,y1 inclusive
        x0, y0, x1, y1 = map(int, arg.split(','))
        return {(folder, (x, y)) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}, set()
    if kind == 'near':
        objs = m.trainers.get(arg) or [o for o in m.objects if o.get('script') == arg]
        if not objs:
            raise SystemExit(f'{folder}: no object for {arg}')
        return {(folder, (o['x'] + dx, o['y'] + dy)) for o in objs
                for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0))}, set()
    raise SystemExit(f'bad spec {spec}')


def path_ok(maps, pair, ab, forbidden, objs):
    src, _ = tiles_for(maps, pair[0])
    tgt, edge = tiles_for(maps, pair[1])
    tgt = tgt | {(f + '#B', p) for f, p in tgt if f + '#B' in maps}
    return world_search(maps, src, tgt - {(f, p) for f, p, _ in edge}, edge, ab, forbidden, objs)


def analyse(name, spec):
    maps = {f: Map(f) for f in spec['maps']}
    for f, switches in spec.get('toggle', {}).items():
        import engine
        alt = Map(f)
        alt.folder = f + '#B'
        engine.mauville_gym_toggle(alt)
        maps[f + '#B'] = alt
        for p in switches:
            maps[f].switch_to[tuple(p)] = f + '#B'
            alt.switch_to[tuple(p)] = f
    ab = abilities(spec['stage'])
    ab.update(spec.get('abilities', {}))
    objs = {f: m.obj_tiles(ab) | {tuple(p) for p in spec.get('block', {}).get(f, ())} for f, m in maps.items()}
    for f, ps in spec.get('unblock', {}).items():
        objs[f] -= {tuple(p) for p in ps}
    for t in spec.get('hide', ()):
        for f, m in maps.items():
            for o in m.trainers.pop(t, []):
                objs[f].discard((o['x'], o['y']))
    sights = collections.defaultdict(set)
    timed = collections.defaultdict(set)
    kinds = {}
    where = {}
    for f, m in maps.items():
        for t, os_ in m.trainers.items():
            where.setdefault(t, f)
            if any(not o.get('talk_only') for o in os_):
                sights[t] |= {(f, p) for p in m.sight(t, objs[f])}
                timed[t] |= {(f, p) for p in m.sight(t, objs[f], timed=True)}
                k = m.kind(t)
                kinds[t] = k if kinds.get(t, 'fixed') == 'fixed' else kinds[t]
    for t, tiles in spec.get('script_tiles', {}).items():
        where.setdefault(t, next(iter(tiles)))
        sights[t] |= {(f, tuple(p)) for f, ps in tiles.items() for p in ps}
        timed[t] |= {(f, tuple(p)) for f, ps in tiles.items() for p in ps}
        kinds[t] = 'script'
    sight_trainers = [t for t in sights if sights[t]]
    res = {}
    notes = []
    for pair in spec['pairs']:
        if not path_ok(maps, pair, ab, set(), objs):
            notes.append(f'no path at all for {pair}')
            for t in sight_trainers:
                res.setdefault(t, ('UNCERTAIN', f'model finds no path {pair[0]} -> {pair[1]} even ignoring trainers'))
            continue
        forced = [t for t in sight_trainers if not path_ok(maps, pair, ab, sights[t], objs)]
        for t in forced:
            if res.get(t, ('',))[0] == 'FORCED':
                continue
            k = kinds.get(t, 'fixed')
            if k in ('fixed', 'script'):
                res[t] = ('FORCED', f'every path {pair[0]} -> {pair[1]} crosses its sight/trigger tiles')
            elif k == 'turning' and path_ok(maps, pair, ab, timed[t], objs):
                if res.get(t, ('',))[0] not in ('FORCED', 'UNCERTAIN'):
                    res[t] = ('AVOIDABLE', f'turning trainer: every path {pair[0]} -> {pair[1]} crosses one of its facings, so it is skipped only by timing its turns', 'timing')
            elif k == 'turning':
                res[t] = ('FORCED', f'every path {pair[0]} -> {pair[1]} crosses a tile it sees in every facing')
            elif res.get(t, ('',))[0] != 'FORCED':
                res[t] = ('UNCERTAIN', f'moving trainer whose patrol/sight covers every path {pair[0]} -> {pair[1]}; may be skippable by timing')
        rest = [t for t in sight_trainers if t not in forced]
        allf = set().union(*(sights[t] for t in rest)) if rest else set()
        if path_ok(maps, pair, ab, allf, objs):
            continue
        found = None
        for k in (1, 2, 3):
            combos = []
            for c in itertools.combinations(rest, k):
                f = set().union(*(sights[t] for t in rest if t not in c))
                if path_ok(maps, pair, ab, f, objs):
                    combos.append(c)
            if combos:
                found = combos
                break
        if found:
            # Turning trainers in a combination: can the player time all of them?
            timed_f = set().union(*((timed[t] if kinds.get(t) == 'turning' else sights[t]) for t in rest))
            timing_ok = path_ok(maps, pair, ab, timed_f, objs)
            alts = ' | '.join('+'.join(x[8:] for x in c) for c in found)
            if timing_ok:
                for t in sorted(set(itertools.chain(*found))):
                    if kinds.get(t) == 'turning' and res.get(t, ('',))[0] not in ('FORCED', 'UNCERTAIN'):
                        res[t] = ('AVOIDABLE', f'turning trainer: paths {pair[0]} -> {pair[1]} pass its line, skipped by timing its turns (with [{alts}])', 'timing')
                continue
            for t in sorted(set(itertools.chain(*found))):
                if res.get(t, ('',))[0] != 'FORCED':
                    res[t] = ('UNCERTAIN', f'{pair[0]} -> {pair[1]}: must fight one of [{alts}] (none forced alone)')
            notes.append(f'{pair}: alternatives {alts}')
        else:
            notes.append(f'{pair}: needs 4+ of the rest')
    return {'res': res, 'notes': notes, 'sight': set(sight_trainers), 'where': where}


def main():
    trainers = G.parse_trainers(os.path.join(REPO, 'src/data/trainers.party'))
    stages = R.load_stages(os.path.join(REPO, 'tools/rebalance/story_stages.json'), trainers, REPO)
    mt = G.map_trainers(REPO)
    results = {name: analyse(name, spec) for name, spec in AREAS.items()}
    area_of = {}
    for name, r in results.items():
        for t in r['where']:
            area_of.setdefault(t, name)
        for n in r['notes']:
            print('NOTE', name, n)
    out = {}
    for st in stages:
        for tid in st['regular']:
            folder = mt[tid]
            entry = {'stage': st['name'], 'map': folder}
            if tid in MANUAL:
                cls, why = MANUAL[tid]
                entry.update({'class': cls, 'reason': why, 'method': 'manual'})
            elif folder in OPTIONAL_MAPS:
                entry.update({'class': 'AVOIDABLE', 'reason': OPTIONAL_MAPS[folder], 'method': 'optional map'})
            elif tid in area_of:
                name = area_of[tid]
                r = results[name]
                entry['map'] = r['where'][tid]
                if tid in r['res']:
                    cls, why = r['res'][tid][:2]
                    if len(r['res'][tid]) > 2:
                        entry['timing'] = True
                elif tid in r['sight']:
                    cls, why = 'AVOIDABLE', 'grid search finds a route around its sight line'
                else:
                    cls, why = 'AVOIDABLE', 'no sight line (talk-to only) and not on the only route'
                if AREAS[name].get('note'):
                    why += '; ' + AREAS[name]['note']
                if AREAS[name].get('optimistic'):
                    why += '; ' + AREAS[name]['optimistic']
                    if cls == 'AVOIDABLE':
                        cls = 'UNCERTAIN'
                entry.update({'class': cls, 'reason': why, 'method': 'grid:' + name})
            else:
                entry.update({'class': 'UNCERTAIN', 'reason': 'not analysed', 'method': 'none'})
            m1 = re.search(r'must fight one of \[([^\]]*)\]', entry['reason'])
            if m1:
                entry['one_of'] = ['TRAINER_' + x.strip() for x in m1[1].split('|')]
            if 'Petalburg Gym:' in entry['reason']:
                entry['one_of'] = next(['TRAINER_' + x for x in g] for g in (('RANDALL', 'MARY'), ('PARKER', 'ALEXIA', 'GEORGE'), ('JODY', 'BERKE')) if tid[8:] in g)
            out[tid] = entry
    bosses = {}
    for st in stages:
        for b in st['bosses']:
            bosses[b] = {'stage': st['name'], **BOSS_NOTES.get(b, {'required': True, 'reason': 'story boss'})}
            for name, r in results.items():
                if b in r['res']:
                    bosses[b]['grid'] = f"{r['res'][b][0]} ({name}): {r['res'][b][1]}"
                elif b in r['sight']:
                    bosses[b]['grid'] = f'AVOIDABLE by sight ({name}); story script may still force it'
    with open(os.path.join(HERE, 'trainers.json'), 'w') as f:
        json.dump({'regular': out, 'bosses': bosses}, f, indent=1)
    # Summary
    for st in stages:
        rows = [(t, out[t]) for t in st['regular']]
        c = {k: sum(1 for _, e in rows if e['class'] == k) for k in ('FORCED', 'AVOIDABLE', 'UNCERTAIN')}
        req = [b for b in st['bosses'] if bosses[b]['required']]
        for b in st['bosses']:
            print(f"   boss {b[8:]:28} required={bosses[b]['required']} {bosses[b]['reason']} {bosses[b].get('grid', '')}")
        tm = sum(1 for _, e in rows if e.get('timing'))
        print(f"== {st['name']}: regular {len(rows)}: forced {c['FORCED']} avoidable {c['AVOIDABLE']} (of which {tm} only by timing turns) uncertain {c['UNCERTAIN']}; bosses required {len(req)}/{len(st['bosses'])}")
        for t, e in rows:
            if e['class'] != 'AVOIDABLE' or VERBOSE or e.get('timing'):
                print(f"   {e['class']:9} {t[8:]:24} {e['map']:32} {e['reason']}")


if __name__ == '__main__':
    main()
