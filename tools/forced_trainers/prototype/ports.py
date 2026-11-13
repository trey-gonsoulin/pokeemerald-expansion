import sys
sys.path.insert(0, '/Users/trey/.claude-personal/jobs/183d03aa/tmp/unavoidable')
from engine import Map
for f in sys.argv[1:]:
    m = Map(f)
    ws = ' '.join(f"{i}:{w['dest_map'][4:]}@{w['x']},{w['y']}" for i, w in enumerate(m.warps))
    trs = ' '.join(f"{t[8:]}@{o['x']},{o['y']}{'(talk)' if o.get('talk_only') else ''}" for t, os_ in m.trainers.items() for o in os_[:1])
    print(f"## {f} {m.w}x{m.h} conns={ {k: v[4:] for k, v in m.conns.items()} }\n   warps: {ws}\n   trainers: {trs}")
