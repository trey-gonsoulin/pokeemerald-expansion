"""Today's data under two players: fights every story trainer (full clear) vs only the forced ones
(trainers.json from the unavoidable-trainer analysis), with the Exp. Share lead's level against each boss ace."""
import copy, json, os, sys
sys.path.insert(0, 'tools/rebalance')
import rebalance as RB, gamedata as G

HERE = os.path.dirname(os.path.abspath(__file__))
cls = json.load(open(os.path.join(HERE, 'unavoidable', 'trainers.json')))
inputs = RB.repo_inputs(G.REPO, info=G.R.SpeciesInfo(G.REPO))
knobs = {**json.load(open(RB.CURVE_SETTINGS)), 'margin': None, 'trainer_gap': None, 'wild_gap': None,
         'rematch_step': None}

# The skip-all player: FORCED trainers, plus one pick of each choose-one group (its first members).
groups = {}
for tid, v in cls['regular'].items():
    if 'one_of' in v:
        groups[tuple(v['one_of'])] = v['one_of']
picked = {g[0] for g in groups}
forced = {t for t, v in cls['regular'].items() if v['class'] == 'FORCED'} | picked
optional_bosses = {b for b, v in cls['bosses'].items() if not v.get('required', True)}


def run(skip):
    snap = dict(inputs)
    snap['stages'] = copy.deepcopy(inputs['stages'])
    if skip:
        for st in snap['stages']:
            st['regular'] = [t for t in st['regular'] if t in forced]
            st['bosses'] = [b for b in st['bosses'] if b not in optional_bosses]
    return {r['boss']: r for r in RB.explore_run(snap, knobs)['bosses']}


full, skip = run(False), run(True)
print(f"{'boss':28} {'ace':>4} {'full lead':>9} {'%':>6} {'skip lead':>9} {'%':>6}")
for bid, r in full.items():
    if r['stage'].startswith('Rematch') or r['stage'] == 'Post-game':
        continue
    ace, fl = r['boss_ace'], r['levels'][0]
    s = skip.get(bid)
    sl = s['levels'][0] if s else None
    pct = lambda lv: f"{(lv - ace) * 100 / ace:+.0f}%" if lv else '-'
    print(f"{r['name'][:28]:28} {ace:4} {fl:9} {pct(fl):>6} {sl if sl else 'skipped':>9} {pct(sl):>6}")
