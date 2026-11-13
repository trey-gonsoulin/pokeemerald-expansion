"""How many KOs a solo Pokemon (Medium Slow) needs to climb from the curve level to a target, against the
best repeatable foe of that point, under the game's exp formula with the over-level penalty."""
import os, sys
sys.path.insert(0, '.')
import rebalance as RB, gamedata as G

repo = G.REPO
gd = G.load(repo); m = gd['modern']
trainers = G.parse_trainers(os.path.join(repo, 'src', 'data', 'trainers.party'))
stages = RB.load_stages(RB.DEFAULT_STAGES, trainers, repo)
scaling = RB.game_scaling(m, G.parse_scaling_factors(repo))
wilds = RB.load_wilds(repo, stages)['modern']
over = RB.Overlevel.from_configs(m)
GROWTH = 'GROWTH_MEDIUM_SLOW'


def award(yield_, foe, getter, trainer, mult, penalty=True):
    calc = yield_ * foe // 5
    r = calc * mult  # affection 1.2x, Lucky Egg 1.5x (applied before the scaling, as the game does)
    r = int(r) * scaling[foe * 2 + 10] // scaling[foe + getter + 10] + 1
    return over.apply(r, foe, getter) if penalty else r


def kos(start, target, foes, trainer, mult, penalty=True):
    """KOs from ``start`` to ``target``; ``foes`` [(yield, level)] fought in turn (a team, or one wild)."""
    exp, goal, n = RB.exp_for_level(GROWTH, start), RB.exp_for_level(GROWTH, target), 0
    while exp < goal and n < 100000:
        for y, lv in foes:
            exp += award(y, lv, RB.level_for_exp(GROWTH, exp), trainer, mult, penalty)
            n += 1
    return n


def best_wild(upto):
    """The best-exp wild Pokemon (yield x level) of the stages up to ``upto``: DexNav can hunt it."""
    best = (0, 0, '')
    for i in range(upto + 1):
        for field, slot, _ in wilds.get(i, ()):
            if field != 'land_mons' and not (field == 'water_mons' and upto >= stage_of['Winona']):
                continue  # no Surf before Winona's stage; rods left out
            y = m.species[slot['species']].exp_yield
            best = max(best, (y, slot['max_level'], slot['species']), key=lambda b: b[0] * b[1])
    return best


def best_rematch():
    ladders = RB.rematch_ladders(G.parse_rematches(repo), stages, trainers)
    best = None
    for lad in ladders['regular'] + ladders['unstaged']:
        for tid in lad[1:]:
            team = [(m.species[x.species].exp_yield, x.level) for x in trainers[tid].mons]
            total = sum(y * lv for y, lv in team)
            if best is None or total > best[0]:
                best = (total, tid, team)
    return best


stage_of = {st['name']: i for i, st in enumerate(stages)}
CASES = [  # (label, stage, curve level, target)
    ('Treecko vs Rustboro rival', 'Brawly', 18, 23),
    ('Torchic vs Wattson', 'Wattson', 26, 35),
    ('Treecko vs Flannery', 'Flannery', 41, 54),
    ('Treecko vs Winona', 'Winona', 57, 71),
    ('Mudkip vs Route 119 rival', 'Winona', 56, 76),
    ('Mudkip vs Lilycove rival', 'Tate and Liza', 66, 91),
    ('Treecko vs Drake', 'Elite Four', 83, 95),
    ('Torchic vs Wallace', 'Elite Four', 84, 100),
]
rm = best_rematch()
print('best rematch team:', rm[1], rm[2])
for label, stage, start, target in CASES:
    y, lv, sp = best_wild(stage_of[stage])
    row = [label, f'{start}->{target}', f'{sp[8:]} {lv}']
    for mult in (1.2, 1.8):
        row.append(kos(start, target, [(y, lv)], False, mult))
    row.append(kos(start, target, [(y, lv)], False, 1.2, penalty=False))
    if stage_of[stage] > stage_of['Norman']:
        row.append(kos(start, target, rm[2], True, 1.2) // len(rm[2]))
        row.append(kos(start, target, rm[2], True, 1.8) // len(rm[2]))
    print(' | '.join(map(str, row)))
