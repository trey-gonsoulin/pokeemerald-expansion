"""Solo walls (#350): how high a starter has to be to beat each story boss
alone, and the grind from the fight-everyone lead up to it.

Per starter and staged story boss (``solo_walls``):

- **the solo Pokemon** (``solo_fighter``): the starter line evolved for its
  level, with the attacks of its default moveset and the TMs open by the
  boss's stage picked for coverage (matchup.stand_in, matchup_settings.json's
  ``ivs`` and ``moves``), and full EVs spread evenly (SOLO_EVS in each stat);
- **the wall** (``wall_level``): the lowest level at which it wins each
  one-on-one with the boss team on power.score with the type chart (healing
  between Pokemon); **the sweep** (``sweep_level``): the lowest at which it
  beats the whole team without healing;
- **the grind** (``grind_kos``): KOs from the fight-everyone lead to the
  wall against the best wild Pokemon reachable by then (``best_wild``: grass
  before the Surf stage, Surf from it, no rods; DexNav can hunt a species),
  with max friendship's 1.2x and no Lucky Egg, under the exp configs it is
  given; after Norman (REMATCH_UNLOCK), also the battles against the
  strongest rematch team open by then.

A double battle (Tate and Liza) is fought one-on-one like the rest. The grind
budget (GRIND_BUDGET) is what the penalty tuning aims for. Standard library
only.
"""

import dataclasses
import functools

import gamedata as G
import matchup as M
import power as P
import rebalance as R

SOLO_EVS = 85  # per stat: 510 EVs spread evenly
GRIND_BUDGET = 50  # KOs from the fight-everyone lead to any budgeted solo wall
# Solo walls the owner accepted over the budget: (boss team, starter) -> why.
SOLO_OUTLIERS = {('TRAINER_WALLACE', 'MUDKIP'): 'owner accepted, #350'}
OPTIONAL = 'optional, not budgeted'
ACCEPTED = 'accepted outlier'
AFFECTION = 1.2  # max friendship's 4915/4096 (B_AFFECTION_MECHANICS)


def solo_fighter(gd, species, level, tm_moves, teachables, evolve, targets, ivs, moves=4):
    """The starter line at ``level`` (``evolve(species, level)``) as a
    power.Fighter: up to ``moves`` attacks from its default moveset and
    ``tm_moves`` (matchup.stand_in), with SOLO_EVS in every stat."""
    f = M.stand_in(gd, evolve(species, level), level, ivs, tm_moves, teachables, moves, targets)['fighter']
    bump = SOLO_EVS // 4 * level / 100
    return dataclasses.replace(f, stats={k: v + bump for k, v in f.stats.items()})


def first_level(gd, species, foes, tm_moves, teachables, evolve, targets, ivs, wins, start=1, moves=4):
    """The lowest level from ``start`` up to 100 whose solo fighter's scores
    against ``foes`` satisfy ``wins``, or None."""
    for level in range(start, 101):
        me = solo_fighter(gd, species, level, tm_moves, teachables, evolve, targets, ivs, moves)
        if wins([P.score(me, foe, gd.chart) for foe in foes]):
            return level
    return None


def wall_level(gd, species, foes, tm_moves, teachables, evolve, targets, ivs, start=1, moves=4):
    """The lowest level, up to 100, that wins every one-on-one with
    ``foes`` (power.Fighters): each score at least 1. None: unwinnable."""
    return first_level(gd, species, foes, tm_moves, teachables, evolve, targets, ivs,
                       lambda scores: min(scores) >= 1, start, moves)


def sweep_level(gd, species, foes, tm_moves, teachables, evolve, targets, ivs, start=1, moves=4):
    """The lowest level, up to 100, that beats ``foes`` in a row without
    healing: the share of a fight each takes (1/score) adds up to at most 1.
    Never below wall_level, so ``start`` can be the wall."""
    return first_level(gd, species, foes, tm_moves, teachables, evolve, targets, ivs,
                       lambda scores: sum(1 / s if s else float('inf') for s in scores) <= 1, start, moves)


def best_wild(gd, wilds, stage_index, surf_index, cost=None):
    """The wild Pokemon to grind on in the stages up to ``stage_index``
    (``wilds``: stage -> rebalance.stage_slots' slots), at its slot's
    highest level, as (yield, level, species): land tables, and water from
    ``surf_index`` (None: never). No rods or Rock Smash. With ``cost``
    (``cost((yield, level))``: the KOs a climb takes on it, None for no
    exp), the one with the fewest KOs (#350: under the over-level penalty
    the most exp per KO isn't always the fewest KOs); else, and on a tie,
    the one worth the most exp per KO (yield x level). None when there is
    none."""
    fields = ('land_mons', 'water_mons') if surf_index is not None and stage_index >= surf_index else ('land_mons',)
    found = set()
    for i in range(stage_index + 1):
        for field, slot, _ in wilds.get(i, ()):
            if field in fields and slot['species'] in gd.species:
                found.add((gd.species[slot['species']].exp_yield, slot['max_level'], slot['species']))
    ranked = sorted(found, key=lambda c: (c[0] * c[1], c), reverse=True)
    if cost is None or not ranked:
        return ranked[0] if ranked else None
    # More yield and more level never cost more KOs: only the rest can be the fewest.
    front = [c for c in ranked if not any(o[:2] != c[:2] and o[0] >= c[0] and o[1] >= c[1] for o in ranked)]
    kos = {c[:2]: cost(c[:2]) for c in front}
    return min(front, key=lambda c: (kos[c[:2]] is None, kos[c[:2]] or 0))


def grind_kos(gd, scaling, overlevel, start, target, foes, mult=AFFECTION, growth='GROWTH_MEDIUM_SLOW',
              trainer=False):
    """KOs a solo Pokemon of ``growth`` needs from level ``start`` to
    ``target`` against ``foes`` ([(yield, level)], fought in turn and whole:
    one wild Pokemon, or a trainer's team), each worth rebalance.exp_award
    under ``gd``'s configs, ``scaling`` and ``overlevel`` (None: no penalty),
    times ``mult`` before the scaling (1.2: max friendship). None if the
    foes give no exp."""
    exp, goal, kos = R.exp_for_level(growth, start), R.exp_for_level(growth, target), 0
    bonus = round(mult * 4096)
    while exp < goal:
        before = exp
        for y, level in foes:
            exp += R.exp_award(gd, scaling, y, level, R.level_for_exp(growth, exp), trainer, 1, overlevel=overlevel,
                               bonus=bonus)
            kos += 1
        if exp == before:
            return None
    return kos


def best_rematch(gd, trainers, stages, ladders, stage_index):
    """The rematch team worth the most exp per battle (yield x level summed)
    among ``ladders``' rematches (rematch_ladders' regular ones) open at
    ``stage_index``: after REMATCH_UNLOCK's stage, for a ladder first fought
    by then. (exp, trainer id, [(yield, level)]) or None."""
    unlock = next((i for i, st in enumerate(stages) if R.REMATCH_UNLOCK in st['bosses']), None)
    if unlock is None or stage_index <= unlock:
        return None
    stage_of = {t: i for i, st in enumerate(stages) for t in st['regular']}
    best = None
    for first, *rematches in ladders:
        if stage_of.get(first, len(stages)) > stage_index:
            continue
        for tid in rematches:
            team = [(gd.species[m.species].exp_yield, m.level) for m in trainers[tid].mons]
            here = (sum(y * lv for y, lv in team), tid, team)
            if best is None or here[:2] > best[:2]:
                best = here
    return best


def boss_foes(gd, trainer, ace, evolve=None, devolve=None):
    """``trainer``'s Pokemon as power.Fighters, moved to the boss row's
    ``ace`` (a curve's raise or lowering, or a rival variant at its fight's
    levels), and evolved (``evolve(species, level, gender)``) or devolved
    (rebalance.devolver's ``devolve``) for it as the curve's run fights
    them (rebalance.team_species, a boss's team's species kept distinct).
    Set moves stay; a default moveset follows the new species and level."""
    delta = ace - R.team_ace(trainer)
    out = []
    for mon, species in zip(trainer.mons, R.team_species(trainer, delta, evolve, devolve, True)):
        mon = dataclasses.replace(mon, species=species, level=max(1, min(mon.level + delta, 100)))
        out.append(P.fighter(gd, mon.species, mon.level, P.team_moves(gd, mon), mon.ivs))
    return out


def solo_walls(trainers, gd, stages, rows, wilds, map_tms, teachables, evolve, scaling, overlevel, settings,
               ladders=(), foe_evolve=None, foe_devolve=None, cache=None, optional=frozenset()):
    """Per staged story boss with a row in ``rows`` (share_run's boss rows:
    ``levels[0]`` is the fight-everyone lead, ``boss_ace`` the team's ace)
    and starter in ``settings`` (matchup_settings.json's; starters ``gd``
    lacks are skipped): {stage, boss (the team met after choosing that
    starter), starter, ace, double, lead, wall, sweep, kos, source (the
    grind's wild [species, level]: best_wild's fewest KOs), rematch,
    battles, exempt}. ``exempt``: why the wall is outside the grind budget
    (OPTIONAL for a boss in ``optional``, the optional fights;
    ACCEPTED for SOLO_OUTLIERS), else None. ``kos``: the grind from the lead to the wall (0 at or below
    the lead, None when the wall is). ``battles``: the same climb against
    the best ``ladders`` rematch team (``rematch``) after Norman, else None.
    ``wilds``: stage -> stage_slots' slots; ``map_tms``: gamedata.map_tms;
    ``teachables``: gamedata.move_lists; ``evolve(species, level)``: the
    player's line; ``gd``, ``scaling`` and ``overlevel``: the exp configs.
    The boss teams move to their row's ace evolved by ``foe_evolve`` and
    devolved by ``foe_devolve`` (boss_foes: the run's own evolver and
    devolver). ``cache`` (a dict) keeps each wall and sweep by stage, team,
    starter and ace for later calls on the same data and evolutions (the
    penalty sweep's candidates, which differ only in their exp and
    levels)."""
    by_boss = {r['boss']: r for r in rows}
    starters = {k: v for k, v in settings['starters'].items() if v in gd.species}
    targets = M.defending_types(gd)
    ivs = dict.fromkeys(G.IV_STATS, settings['ivs'])
    names = [st['name'] for st in stages]
    surf = names.index(R.SURF_STAGE) if R.SURF_STAGE in names else None
    cache = {} if cache is None else cache

    @functools.lru_cache(maxsize=None)
    def climb(lead, wall, growth, foes, trainer=False):
        return grind_kos(gd, scaling, overlevel, lead, wall, list(foes), growth=growth, trainer=trainer)
    out = []
    for i, st in enumerate(stages):
        tm_moves = [mv for mv in M.open_tms(map_tms, stages, i, settings['tm_exclude_maps']) if mv in gd.moves]
        rematch = best_rematch(gd, trainers, stages, ladders, i)
        for bid in st['bosses']:
            row = by_boss.get(bid)
            if row is None:
                continue
            lead = row['levels'][0]
            for name, species in starters.items():
                tid = M.starter_boss(bid, name, starters, trainers)
                if tid is None:
                    continue
                key = (i, tid, name, row['boss_ace'])
                if key not in cache:
                    foes = boss_foes(gd, trainers[tid], row['boss_ace'], foe_evolve, foe_devolve)
                    args = (gd, species, foes, tm_moves, teachables, evolve, targets, ivs)
                    wall = wall_level(*args, moves=settings['moves'])
                    cache[key] = wall, None if wall is None else sweep_level(*args, start=wall,
                                                                            moves=settings['moves'])
                wall, sweep = cache[key]
                growth = gd.species[species].growth
                climbs = wall is not None and wall > lead
                wild = best_wild(gd, wilds, i, surf, (lambda foe: climb(lead, wall, growth, (foe,))) if climbs
                                 else None)

                def grind(foes, trainer=False):
                    if wall is None or foes is None:
                        return None
                    return climb(lead, wall, growth, tuple(foes), trainer) if climbs else 0
                battles = grind(rematch and rematch[2], True)
                out.append({'stage': st['name'], 'boss': tid, 'starter': name, 'ace': row['boss_ace'],
                            'double': trainers[tid].double, 'lead': lead, 'wall': wall, 'sweep': sweep,
                            'kos': grind(wild and [wild[:2]]), 'source': wild and [wild[2], wild[1]],
                            'rematch': rematch and rematch[1],
                            'battles': battles if not battles else battles // len(rematch[2]),
                            'exempt': OPTIONAL if tid in optional else ACCEPTED if (tid, name) in SOLO_OUTLIERS
                            else None})
    return out
