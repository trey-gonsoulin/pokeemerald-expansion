"""Re-run boulder areas with Strength boulders as walls, to see which results depend on the
'boulders already pushed' assumption."""
import copy
import sys
sys.path.insert(0, '/Users/trey/.claude-personal/jobs/183d03aa/tmp/unavoidable')
from classify import analyse
from specs import AREAS

for name in sys.argv[1:]:
    spec = copy.deepcopy(AREAS[name])
    opt = analyse(name, spec)
    spec['abilities'] = dict(spec.get('abilities', {}), strength=False)
    pes = analyse(name, spec)
    print('==', name, 'notes(pessimistic):', pes['notes'])
    for t in sorted(opt['where']):
        a = opt['res'].get(t, ('AVOIDABLE' if t in opt['sight'] else '-',))[0]
        b = pes['res'].get(t, ('AVOIDABLE' if t in pes['sight'] else '-',))[0]
        print(f'   {t[8:]:26} optimistic={a:10} boulders-as-walls={b}')
