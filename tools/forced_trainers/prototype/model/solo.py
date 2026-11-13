"""Solo-run level needed per story boss: the starter line alone (default moves + open TMs, 4 picked
for coverage, IV 15) against each boss team, by power.score with the type chart."""
import os, sys, json
sys.path.insert(0, 'tools/rebalance')
import rebalance as RB, matchup as M, power as P, gamedata as G

EVS = len(sys.argv) > 1 and sys.argv[1] == 'evs'
repo = G.REPO
gd = G.load(repo); m = gd['modern']
trainers = G.parse_trainers(os.path.join(repo, 'src', 'data', 'trainers.party'))
stages = RB.load_stages(RB.DEFAULT_STAGES, trainers, repo)
scaling = RB.game_scaling(m, G.parse_scaling_factors(repo))
wilds = RB.load_wilds(repo, stages)
share = RB.share_curves(stages, trainers, m, scaling, wilds['modern'])
bench_rows = {r['boss']: r for r in share[RB.POWER_BENCH[0]]['now'][RB.POWER_BENCH[1]]}
info = G.R.SpeciesInfo(repo)
teachables = G.move_lists(repo)
map_tms = G.map_tms(repo)
settings = M.load_settings()
targets = M.defending_types(m)


def evolve(sp, lv):
    out = info.evolve(sp, lv, grace=0)
    return out if out in m.species else sp


ivs = dict.fromkeys(G.IV_STATS, settings['ivs'])


def solo(species, level, tm_moves):
    s = M.stand_in(m, evolve(species, level), level, ivs, tm_moves, teachables, 4, targets)
    f = s['fighter']
    if EVS:  # 510 EVs spread evenly: +85/4 per stat point per 100 levels
        bump = 85 / 4 * level / 100
        f.stats.update({k: v + bump for k, v in f.stats.items()})
    return s, f


out = []
for i, st in enumerate(stages):
    tm_moves = [mv for mv in M.open_tms(map_tms, stages, i, settings['tm_exclude_maps']) if mv in m.moves]
    for bid in st['bosses']:
        row = bench_rows.get(bid)
        if not row:
            continue
        lead = row['levels'][0]
        for name, species in settings['starters'].items():
            tid = M.starter_boss(bid, name, settings['starters'], trainers)
            if tid is None:
                continue
            foes = [P.fighter(m, mon.species, mon.level, P.team_moves(m, mon), mon.ivs) for mon in trainers[tid].mons]
            each = sweep = None
            for L in range(2, 101):
                s, f = solo(species, L, tm_moves)
                sc = [P.score(f, foe, m.chart) for foe in foes]
                if each is None and min(sc) >= 1:
                    each = L
                if sweep is None and sum(1 / x if x else 99 for x in sc) <= 1:
                    sweep = (L, s)
                    break
            out.append(dict(stage=st['name'], boss=tid, starter=name, ace=max(x.level for x in trainers[tid].mons),
                            lead=lead, each=each, sweep=sweep and sweep[0],
                            line=sweep and sweep[1]['species'], moves=sweep and sweep[1]['moves'],
                            double=trainers[tid].double))
json.dump(out, open(os.environ['CLAUDE_JOB_DIR'] + f'/tmp/solo{"_evs" if EVS else ""}.json', 'w'), indent=1)
for r in out:
    e = f"{r['each'] - r['lead']:+}" if r['each'] else '-'
    w = f"{r['sweep'] - r['lead']:+}" if r['sweep'] else '-'
    print(f"{r['boss'][8:34]:26} {r['starter'][:3]} ace {r['ace']:3} solo {r['lead']:3} | each {r['each']} ({e}) "
          f"sweep {r['sweep']} ({w})  {(r['line'] or '')[8:]} {[x[5:] for x in r['moves'] or []]}")
