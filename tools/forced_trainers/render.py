"""Draw a story map as text, to check the classifier's grid by eye. Run from the repo root:

    python3 tools/forced_trainers/render.py Route110 [stage 0-9] [x0,y0,x1,y1]

T trainer, 0-9/a-z warp index, o blocking object, # wall, ~ water, b bike-only tile, % ice, spin or
current tile, s tile a trainer sees, ^ v < > ledge, and the elevation or . elsewhere.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Map, abilities, WATER, JUMP, BIKE, SPECIAL

folder = sys.argv[1]
stage = int(sys.argv[2]) if len(sys.argv) > 2 else 9
x0, y0, x1, y1 = (map(int, sys.argv[3].split(',')) if len(sys.argv) > 3 else (0, 0, 10**9, 10**9))
m = Map(folder)
ab = abilities(stage)
objs = m.obj_tiles(ab)
sight = set()
for t in m.trainers:
    sight |= m.sight(t, objs)
tr = {(o['x'], o['y']) for os_ in m.trainers.values() for o in os_}
warps = {(w['x'], w['y']): i for i, w in enumerate(m.warps)}
JCH = {'right': '>', 'left': '<', 'up': '^', 'down': 'v'}
print('    ' + ''.join(str((x // 10) % 10) for x in range(max(0, x0), min(m.w, x1 + 1))))
print('    ' + ''.join(str(x % 10) for x in range(max(0, x0), min(m.w, x1 + 1))))
for y in range(max(0, y0), min(m.h, y1 + 1)):
    row = ''
    for x in range(max(0, x0), min(m.w, x1 + 1)):
        p = (x, y)
        b = m.mb[p]
        if p in tr:
            c = 'T'
        elif p in warps:
            c = chr(ord('0') + warps[p]) if warps[p] < 10 else chr(ord('a') + warps[p] - 10)
        elif p in objs:
            c = 'o'
        elif b in JUMP:
            c = JCH[JUMP[b]]
        elif m.coll[p]:
            c = '#'
        elif b in WATER:
            c = '~'
        elif b in BIKE:
            c = 'b'
        elif b in SPECIAL:
            c = '%'
        elif p in sight:
            c = 's'
        else:
            c = '.' if m.elev[p] in (3, 0, 15) else str(m.elev[p] % 10)
        row += c
    print('%3d ' % y + row)
