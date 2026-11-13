"""Debug: show the reachable tiles of a pair with some trainers' sight forbidden.
python3 dbg.py AREA SRC TGT [TRAINER ...] [--rows y0,y1]"""
import collections
import sys
sys.path.insert(0, '/Users/trey/.claude-personal/jobs/183d03aa/tmp/unavoidable')
import engine
from classify import tiles_for
from specs import AREAS

args = [a for a in sys.argv[1:] if not a.startswith('--')]
spec = AREAS[args[0]]
maps = {f: engine.Map(f) for f in spec['maps']}
ab = engine.abilities(spec['stage'])
ab.update(spec.get('abilities', {}))
objs = {f: m.obj_tiles(ab) | {tuple(p) for p in spec.get('block', {}).get(f, ())} for f, m in maps.items()}
pair = (args[1], args[2])
forb = set()
for t in args[3:]:
    for f, m in maps.items():
        if t in m.trainers:
            forb |= {(f, p) for p in m.sight(t, objs[f])}
    for f, ps in spec.get('script_tiles', {}).get(t, {}).items():
        forb |= {(f, tuple(p)) for p in ps}
seen_all = []


class D(collections.deque):
    def append(self, x):
        seen_all.append(x)
        super().append(x)


engine.collections.deque = D
src, _ = tiles_for(maps, pair[0])
tgt, edge = tiles_for(maps, pair[1])
print('ok', engine.world_search(maps, src, tgt - {(f, p) for f, p, _ in edge}, edge, ab, forb, objs))
only = [a[2:] for a in sys.argv[1:] if a.startswith('--')]
for f, m in maps.items():
    if only and f not in only:
        continue
    pts = {s[1] for s in seen_all if s[0] == f}
    print(f)
    tr = {(o['x'], o['y']) for os_ in m.trainers.values() for o in os_}
    for y in range(m.h):
        row = ''
        for x in range(m.w):
            p = (x, y)
            if p in tr:
                c = 'T'
            elif p in pts:
                c = '*'
            elif (f, p) in forb:
                c = 's'
            elif p in objs[f]:
                c = 'o'
            elif m.mb[p] in engine.JUMP:
                c = {'right': '>', 'left': '<', 'up': '^', 'down': 'v'}[engine.JUMP[m.mb[p]]]
            elif m.coll[p]:
                c = '#'
            elif m.mb[p] in engine.WATER:
                c = '~'
            else:
                c = '.'
            row += c
        print('%3d ' % y + row)
