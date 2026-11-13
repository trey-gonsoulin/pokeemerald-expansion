"""Spread between the full-clear and skip-all leads (vs today's boss aces) for 1.5x trainer exp on/off,
a uniform percent raise on every story regular trainer, and today's vs a softened over-level penalty."""
import copy, json, os, statistics, sys
sys.path.insert(0, 'tools/rebalance')
import rebalance as RB, gamedata as G

HERE = os.path.dirname(os.path.abspath(__file__))
cls = json.load(open(os.path.join(HERE, 'unavoidable', 'trainers.json')))
inputs = RB.repo_inputs(G.REPO, info=G.R.SpeciesInfo(G.REPO))
base = {**json.load(open(RB.CURVE_SETTINGS)), 'margin': None, 'trainer_gap': None, 'wild_gap': None,
        'rematch_step': None}
groups = {tuple(v['one_of']) for v in cls['regular'].values() if 'one_of' in v}
forced = {t for t, v in cls['regular'].items() if v['class'] == 'FORCED'} | {g[0] for g in groups}
optional_bosses = {b for b, v in cls['bosses'].items() if not v.get('required', True)}
regular = {t for st in inputs['stages'] for t in st['regular']}
PENALTIES = {'today 15%/4/10%': {}, 'soft 30%/6/30%': {'overlevel_cutoff': 30, 'overlevel_width': 6, 'overlevel_floor': 30}}


def raised(pct):
    trainers = copy.deepcopy(inputs['trainers'])
    for tid in regular:
        for mon in trainers[tid].mons:
            mon.level = min(100, round(mon.level * (1 + pct / 100)))
    return trainers


def run(trainers, knobs, skip):
    snap = {**inputs, 'trainers': trainers, 'stages': copy.deepcopy(inputs['stages'])}
    if skip:
        for st in snap['stages']:
            st['regular'] = [t for t in st['regular'] if t in forced]
            st['bosses'] = [b for b in st['bosses'] if b not in optional_bosses]
    return {r['boss']: r for r in RB.explore_run(snap, knobs)['bosses']
            if not (r['stage'].startswith('Rematch') or r['stage'] == 'Post-game')}


print(f"{'1.5x':5} {'raise':>5} {'penalty':16} | {'full mean':>9} {'skip mean':>9} {'spread':>6} | Wallace full/skip | Norman full/skip")
for exp in ('1.5x off', '1.5x on'):
    for pct in (0, 10, 20):
        trainers = raised(pct)
        for pname, pen in PENALTIES.items():
            knobs = {**base, 'trainer_exp': exp, **pen}
            full, skip = run(trainers, knobs, False), run(trainers, knobs, True)
            f = {b: (r['levels'][0] - r['boss_ace']) * 100 / r['boss_ace'] for b, r in full.items()}
            s = {b: (r['levels'][0] - r['boss_ace']) * 100 / r['boss_ace'] for b, r in skip.items()}
            both = [b for b in s if b in f and full[b]['boss_ace'] >= 15]
            fm, sm = statistics.mean(f[b] for b in both), statistics.mean(s[b] for b in both)
            w, n = 'TRAINER_WALLACE', 'TRAINER_NORMAN_1'
            print(f"{exp[-3:]:5} {pct:>4}% {pname:16} | {fm:+8.1f}% {sm:+8.1f}% {fm - sm:5.1f} | "
                  f"{full[w]['levels'][0]}/{skip[w]['levels'][0]} (ace {full[w]['boss_ace']}) | "
                  f"{full[n]['levels'][0]}/{skip[n]['levels'][0]} (ace {full[n]['boss_ace']})")
