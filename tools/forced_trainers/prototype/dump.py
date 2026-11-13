import sys
sys.path.insert(0, '/Users/trey/.claude-personal/jobs/183d03aa/tmp/unavoidable')
from engine import Map
for f in sys.argv[1:]:
    m = Map(f)
    print('##', f, m.w, 'x', m.h, 'conns', m.conns)
    for i, w in enumerate(m.warps):
        print('  warp', i, (w['x'], w['y']), w['dest_map'], w['dest_warp_id'])
    for t, os_ in m.trainers.items():
        for o in os_:
            print('  TR', t, (o['x'], o['y']), 'e', o['elevation'], o['movement_type'][14:], o.get('movement_range_x'), o.get('movement_range_y'),
                  o.get('trainer_type', '')[13:], 'r', o.get('trainer_sight_or_berry_tree_id'), 'flag', o.get('flag'), 'TALK' if o.get('talk_only') else '')
    for c in m.j.get('coord_events') or []:
        print('  coord', (c['x'], c['y']), c.get('var'), c.get('var_value'), c.get('script'))
