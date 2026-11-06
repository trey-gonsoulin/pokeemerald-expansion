"""Matchup-relative strength (prototype): how a story boss's team fares
against a stand-in for the player's team at that point, types included.

power.py's effective level scores a Pokemon against a typeless reference.
This scores it against Pokemon the player could have: per boss and starter,

- **the stand-in team** (``stand_in_team``, matchup_settings.json): the
  starter line at the Exp. Share lead's level, and the best catches the
  wild tables met so far offer, by base stat total and new types, at the
  bench's level. Each keeps the attacks of its default moveset and the TMs
  open by then that cover the most defending types (``pick_moves``);
- **the matrix** (``fight``): power.score with the type chart for each
  stand-in against each boss Pokemon (above 1: the stand-in is ahead);
- **the readings**: each boss Pokemon's best answer (the team's highest
  score against it), the hardest boss Pokemon (the lowest best answer),
  coverage (boss Pokemon with an answer of 1 or more) and the answer to
  the boss's lead (the AI's first party slot).

The rival teams follow the starter (TRAINER_MAY_RUSTBORO_TREECKO is the
team met after choosing Treecko). Everything power.py leaves out stays out,
and the stand-in is a guess: README, "Matchup-relative strength". Standard
library only.
"""

import json
import os

import gamedata as G
import power as P

SETTINGS = os.path.join(G.HERE, 'matchup_settings.json')
ANSWERED = 1.0  # a best answer at least this good covers its boss Pokemon


def load_settings(path=SETTINGS):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def bst(gd, species):
    return sum(gd.species[species].stats.values())


def starter_boss(bid, starter, starters, trainers):
    """The team of fight ``bid`` met after choosing ``starter``: a rival
    team's id with that starter's suffix, any other boss as it is."""
    for s in starters:
        if bid.endswith('_' + s):
            out = bid[:-len(s)] + starter
            return out if out in trainers else None
    return bid


def defending_types(gd):
    """Every type a species has, the moves' coverage targets."""
    return sorted({t for sp in gd.species.values() for t in sp.types})


def pick_moves(gd, species, level, ivs, extra, n, targets):
    """Up to ``n`` of the species' attacks at ``level`` (its default
    moveset, then ``extra``: the TMs it can learn), picked one at a time for
    the largest gain in its best expected damage summed over ``targets``
    (single defending types, at its own stats and level)."""
    pool = list(dict.fromkeys(gd.default_moves(species, level) + list(extra)))
    attacks = P.fighter(gd, species, level, pool, ivs).attacks
    if not attacks:
        return []
    me = P.fighter(gd, species, level, [], ivs)
    foes = [P.Fighter(level, me.stats, [], (t,)) for t in targets]

    def damage(attack, foe):
        return P.expected_damage(P.Fighter(level, me.stats, [attack]), foe, gd.chart)
    table = [[damage(a, foe) for foe in foes] for a in attacks]
    chosen, best = [], [0.0] * len(foes)
    while len(chosen) < min(n, len(attacks)):
        # The highest total, the earliest move on a tie.
        k = max((i for i in range(len(table)) if i not in chosen),
                key=lambda i: (sum(max(d, b) for d, b in zip(table[i], best)), -i))
        chosen.append(k)
        best = [max(d, b) for d, b in zip(table[k], best)]
    return [attacks[i][0] for i in chosen]


def stand_in(gd, species, level, ivs, tm_moves, teachables, n, targets):
    """A stand-in Pokemon as {species, level, moves, fighter}: ``tm_moves``
    (the open TMs) that its teachables (``teachables``: gamedata.move_lists)
    hold are offered to pick_moves."""
    learnable = teachables.get(gd.species[species].teachables, frozenset())
    moves = pick_moves(gd, species, level, ivs, [m for m in tm_moves if m in learnable], n, targets)
    return {'species': species, 'level': level, 'moves': moves,
            'fighter': P.fighter(gd, species, level, moves, ivs)}


def stand_in_team(gd, settings, stage_index, levels, starter, seen, tm_moves, teachables, evolve, targets):
    """The stand-in team before a boss of stage ``stage_index``: the
    ``starter`` species line at the lead's level (``levels[0]``: the Exp.
    Share curve's party, lead first), then up to ``catches_per_stage`` catches
    per earlier stage from ``seen`` (the species of the wild tables met by
    then), each evolved for the bench's level (``evolve(species, level)``)
    and picked by base stat total, new types first."""
    ivs = dict.fromkeys(G.IV_STATS, settings['ivs'])
    n = settings['moves']
    lead = stand_in(gd, evolve(starter, levels[0]), levels[0], ivs, tm_moves, teachables, n, targets)
    team = [lead] if lead['moves'] else []
    room = min(settings['team_size'] - 1, settings['catches_per_stage'] * stage_index, len(levels) - 1)
    if room <= 0:
        return team
    bench = levels[1:1 + room]
    level = min(bench)
    exclude = set(settings['exclude'])
    options = sorted({evolve(sp, level) for sp in seen if sp in gd.species} - exclude - {lead['species']},
                     key=lambda sp: (-bst(gd, sp), sp))
    picked, types = [], set(gd.species[lead['species']].types)
    for new_types_only in (True, False):
        for sp in options:
            if len(picked) == room:
                break
            if sp in picked or (new_types_only and types & set(gd.species[sp].types)):
                continue
            if not stand_in(gd, sp, level, ivs, tm_moves, teachables, n, targets)['moves']:
                continue  # no attack to score (Wobbuffet, Abra)
            picked.append(sp)
            types |= set(gd.species[sp].types)
    return team + [stand_in(gd, sp, lv, ivs, tm_moves, teachables, n, targets) for sp, lv in zip(picked, bench)]


def fight(gd, team, trainer):
    """The matrix of ``team`` (stand_in_team) against ``trainer``'s
    Pokemon, and its readings: per boss Pokemon its best answer, the hardest
    of them, coverage and the lead's answer."""
    bosses = [(mon, P.fighter(gd, mon.species, mon.level, P.team_moves(gd, mon), mon.ivs)) for mon in trainer.mons]
    answers = []
    for mon, foe in bosses:
        scores = [(P.score(p['fighter'], foe, gd.chart), p['species']) for p in team]
        best, by = max(scores, default=(0.0, None))
        answers.append({'species': mon.species, 'level': mon.level, 'answer': round(best, 2), 'by': by,
                        'scores': [round(s, 2) for s, _ in scores]})
    hardest = min(answers, key=lambda a: a['answer'])
    return {'answers': answers, 'hardest': hardest, 'lead': answers[0],
            'coverage': sum(a['answer'] >= ANSWERED for a in answers)}


def open_tms(map_tms, stages, stage_index, exclude_maps):
    """The moves of the TMs on the maps of the stages before ``stage_index``
    (a boss's own stage hands out its TMs as the fight's reward or after
    it), leaving out ``exclude_maps`` (``map_tms``: gamedata.map_tms)."""
    moves = set()
    for folder, items in map_tms.items():
        i = G.stage_of(folder, stages)
        if i is not None and i < stage_index and folder not in exclude_maps:
            moves.update('MOVE_' + item[len('ITEM_TM_'):] for item, _ in items)
    return sorted(moves)


def seen_species(wilds, stage_index, fields):
    """The species of ``fields``' wild slots in the stages up to ``stage_index``."""
    return {slot['species'] for i in range(stage_index + 1) for field, slot, _ in wilds.get(i, ())
            if field in fields}


def matchups(trainers, gd, stages, bench_rows, wilds, map_tms, teachables, evolve, settings=None):
    """Every story boss fight against each starter's stand-in team.
    ``bench_rows``: boss -> the Exp. Share curve's row before it (its
    ``levels``); ``wilds``: stage -> wild slots; ``map_tms``:
    gamedata.map_tms; ``teachables``: gamedata.move_lists; ``evolve(species,
    level)``.
    Starters ``gd`` doesn't have are skipped."""
    settings = settings or load_settings()
    starters = {k: v for k, v in settings['starters'].items() if v in gd.species}
    targets = defending_types(gd)
    fights = []
    for i, st in enumerate(stages):
        seen = seen_species(wilds, i, settings['fields'])
        tm_moves = [mv for mv in open_tms(map_tms, stages, i, settings['tm_exclude_maps']) if mv in gd.moves]
        for bid in st['bosses']:
            row = bench_rows.get(bid)
            if row is None:
                continue
            per = {}
            for name, species in starters.items():
                tid = starter_boss(bid, name, starters, trainers)
                if tid is None:
                    continue
                team = stand_in_team(gd, settings, i, row['levels'], species, seen, tm_moves, teachables,
                                     evolve, targets)
                if not team:
                    continue
                per[name] = {'boss': tid, 'team': [{k: p[k] for k in ('species', 'level', 'moves')} for p in team],
                             **fight(gd, team, trainers[tid])}
            if per:
                fights.append({'stage': st['name'], 'boss': bid, 'double': trainers[bid].double,
                               'boss_ace': row['boss_ace'], 'bench': row['bench'], 'starters': per})
    return {'starters': list(starters), 'fights': fights}
