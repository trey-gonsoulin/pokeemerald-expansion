"""Combat power estimate: how strong a trainer Pokemon is for its level.

Level alone misses base stats, IVs and moves. This scores a Pokemon in a
one-on-one fight with a reference Pokemon of the same level, on turns to
KO, and gives the result as an *effective level*: the level at which the
reference itself would score the same. 50 means "fights like a typical
level-50 Pokemon", whatever its level.

- **The reference** (``reference``): base REFERENCE_BASE in every stat, IV
  REFERENCE_IV in each (a typical caught Pokemon), no EVs, no type. Its one
  attack has the expected power (STAB, accuracy and strikes included) that
  ``fit_reference_power`` fits to the trainer data's best moves by ln(level), and
  it hits the mean of the physical and the special damage.
- **The fight** (``score``): each side uses its best expected damage per
  turn (``expected_damage``: the damage formula without rounding, the mean
  random roll, STAB, accuracy, strikes, the turns a move takes (TURN_COST:
  recharge, charging, Future Sight), Water Spout's power over the fight
  (HP_POWER_MEAN), nothing for a move that faints the user). The score is
  the turns the reference needs to KO the Pokemon over the turns the
  Pokemon needs to KO the reference, each side's up to half a turn longer
  by its chance to move first (``first_strike``). 1 is an even fight.
- **Effective level** (``effective_level``): bisection on the reference's
  level against a reference foe at the Pokemon's level.

Abilities count only where trainers.party leaves no doubt, since it sets
none: a species whose regular slots hold one ability (``certain_ability``)
gets ABILITY_ATTACK's Attack or ABILITY_TURNS's turn cost (Slaking's Truant,
Medicham's Pure Power).

The reference has no type, so every hit on or by it is neutral. ``score``
with a type chart (``chart``) counts types and ABILITY_IMMUNE's certain
immunities instead: matchup.py's pairwise fights (README, "Matchup-relative
strength").

Left out: other abilities, held items, natures and EVs (trainers.party sets
none), status and stat moves, critical hits, fixed-damage moves other than
Night Shade's and Psywave's, and attacks that need a state of their own
(CONDITIONAL_EFFECTS).
Modern data only. Standard library only.
"""

import dataclasses
import math

import gamedata as G

REFERENCE_BASE = 80
REFERENCE_IV = 15
RANDOM_MEAN = 0.925  # the 85-100% damage roll
STAB = 1.5
# Expected strikes of a multiHit move: 2 to 5, by B_MULTI_HIT_CHANCE.
MULTI_HIT_MEAN = {True: 3.1, False: 3.0}  # Gen 5+ (35/35/15/15%), Gen 3 (37.5/37.5/12.5/12.5%)
# Turns a use takes: charging moves, and Future Sight, which can't be used
# again until it lands two turns later. Recharge moves take RECHARGE_COST.
TURN_COST = {'EFFECT_TWO_TURNS_ATTACK': 2, 'EFFECT_SEMI_INVULNERABLE': 2, 'EFFECT_SOLAR_BEAM': 2,
             'EFFECT_FUTURE_SIGHT': 3}
RECHARGE_COST = 2
# Water Spout and Eruption over a fight: full power on the first turn, less
# as the user's HP falls.
HP_POWER_MEAN = 0.6
HP_POWER_EFFECTS = frozenset(('EFFECT_POWER_BASED_ON_USER_HP',))
# Abilities a trainer Pokemon is sure to have that the model scores.
ABILITY_ATTACK = {'ABILITY_HUGE_POWER': 2, 'ABILITY_PURE_POWER': 2}  # Attack multiplier
ABILITY_TURNS = {'ABILITY_TRUANT': 2}  # turns per attack
# Move types a certain ability takes no damage from, counted when ``score``
# has a type chart. Lightning Rod and Storm Drain since Gen 5
# (B_REDIRECT_ABILITY_IMMUNITY).
ABILITY_IMMUNE = {'ABILITY_LEVITATE': 'TYPE_GROUND', 'ABILITY_EARTH_EATER': 'TYPE_GROUND',
                  'ABILITY_FLASH_FIRE': 'TYPE_FIRE', 'ABILITY_WELL_BAKED_BODY': 'TYPE_FIRE',
                  'ABILITY_VOLT_ABSORB': 'TYPE_ELECTRIC', 'ABILITY_MOTOR_DRIVE': 'TYPE_ELECTRIC',
                  'ABILITY_WATER_ABSORB': 'TYPE_WATER', 'ABILITY_DRY_SKIN': 'TYPE_WATER',
                  'ABILITY_SAP_SIPPER': 'TYPE_GRASS'}
REDIRECT_IMMUNE = {'ABILITY_LIGHTNING_ROD': 'TYPE_ELECTRIC', 'ABILITY_STORM_DRAIN': 'TYPE_WATER'}
# Attacks that work only in some state a straight fight doesn't have
# (Focus Punch: not hit this turn; Dream Eater: an asleep target; Fake Out:
# the first turn), scored as no attack.
CONDITIONAL_EFFECTS = frozenset(('EFFECT_FOCUS_PUNCH', 'EFFECT_DREAM_EATER', 'EFFECT_SNORE', 'EFFECT_FIRST_TURN_ONLY',
                                 'EFFECT_LAST_RESORT', 'EFFECT_SYNCHRONOISE', 'EFFECT_BELCH', 'EFFECT_POLTERGEIST'))
LEVEL_DAMAGE_EFFECTS = frozenset(('EFFECT_LEVEL_DAMAGE', 'EFFECT_PSYWAVE'))  # Psywave's mean is the level
# Turns of first strike: a side gets SPEED_BONUS times its chance to move
# first, which rises smoothly with the speed ratio (SPEED_STEEPNESS: 10%
# faster is a 72% chance), since near-ties, priority and paralysis blur it.
SPEED_BONUS = 0.5
SPEED_STEEPNESS = 10
# Bisection range and steps for effective_level.
LEVEL_RANGE = (1.0, 300.0)
BISECT_STEPS = 40
# The reference's expected power never goes below this (a level-1 fit).
MIN_REFERENCE_POWER = 20


@dataclasses.dataclass
class Fighter:
    level: float
    stats: dict  # hp, atk, def, spa, spd, spe
    attacks: list  # (move name, or None for the reference's attack; expected power per turn; kind; move type)
    types: tuple = ()  # none: every hit on it is neutral
    immune: frozenset = frozenset()  # move types it takes nothing from (ABILITY_IMMUNE)


def stats(base, ivs, level):
    """The Gen 3+ stat formula with a neutral nature and no EVs, unrounded."""
    def stat(b, iv):
        return (2 * b + iv) * level / 100
    return {'hp': stat(base['baseHP'], ivs['HP']) + level + 10,
            'atk': stat(base['baseAttack'], ivs['Atk']) + 5,
            'def': stat(base['baseDefense'], ivs['Def']) + 5,
            'spa': stat(base['baseSpAttack'], ivs['SpA']) + 5,
            'spd': stat(base['baseSpDefense'], ivs['SpD']) + 5,
            'spe': stat(base['baseSpeed'], ivs['Spe']) + 5}


def move_power(gd, mv, types):
    """A move's expected power per turn before the attacking and defending
    stats: power, STAB, accuracy, strikes and turn cost. 0 for a move this
    model doesn't score (status, fixed damage, faints the user, CONDITIONAL_EFFECTS)."""
    if not mv.attacking or mv.explosion or mv.fixed_damage or mv.effect in CONDITIONAL_EFFECTS:
        return 0
    power = mv.power * (STAB if mv.type in types else 1)
    power *= MULTI_HIT_MEAN[bool(gd.flag('B_MULTI_HIT_CHANCE >= GEN_5'))] if mv.multi_hit else mv.strikes
    if mv.effect in HP_POWER_EFFECTS:
        power *= HP_POWER_MEAN
    return power * accuracy(mv) / (RECHARGE_COST if mv.recharge else TURN_COST.get(mv.effect, 1))


def accuracy(mv):
    return mv.accuracy / 100 if mv.accuracy else 1  # 0: never misses


def certain_ability(sp):
    """The ability a trainer Pokemon of species ``sp`` has whatever its
    personality (both regular slots, ABILITY_NONE aside, hold it), or None."""
    regular = {a for a in sp.abilities[:2] if a != 'ABILITY_NONE'}
    return regular.pop() if len(regular) == 1 else None


def fighter(gd, species, level, moves, ivs):
    """A trainer Pokemon (``moves``: its set moves or default moveset;
    ``ivs`` None: trainerproc's default)."""
    sp = gd.species[species]
    ivs = ivs or G.DEFAULT_IVS
    ability = certain_ability(sp)
    turns = ABILITY_TURNS.get(ability, 1)
    attacks = []
    for name in moves:
        mv = gd.move(name, ivs)
        if mv.attacking and mv.effect in LEVEL_DAMAGE_EFFECTS:
            attacks.append((name, level * accuracy(mv) / turns, 'fixed', mv.type))
        elif move_power(gd, mv, sp.types):
            attacks.append((name, move_power(gd, mv, sp.types) / turns,
                            'physical' if mv.category == 'DAMAGE_CATEGORY_PHYSICAL' else 'special', mv.type))
    st = stats(sp.stats, ivs, level)
    st['atk'] *= ABILITY_ATTACK.get(ability, 1)
    immune = ABILITY_IMMUNE.get(ability) or (
        REDIRECT_IMMUNE.get(ability) if gd.flag('B_REDIRECT_ABILITY_IMMUNITY >= GEN_5') else None)
    return Fighter(level, st, attacks, tuple(sp.types), frozenset((immune,)) if immune else frozenset())


def reference(level, power_fn):
    base = dict.fromkeys(('baseHP', 'baseAttack', 'baseDefense', 'baseSpAttack', 'baseSpDefense', 'baseSpeed'),
                         REFERENCE_BASE)
    ivs = dict.fromkeys(('HP', 'Atk', 'Def', 'SpA', 'SpD', 'Spe'), REFERENCE_IV)
    return Fighter(level, stats(base, ivs, level), [(None, power_fn(level), 'mixed', None)])


def formula(level, power, attack, defense):
    return ((2 * level / 5 + 2) * power * attack / defense / 50 + 2) * RANDOM_MEAN


def type_multiplier(chart, move_type, dfn):
    """The type chart's multiplier for ``move_type`` on ``dfn`` (1 without a
    chart or a move type), 0 for a type its ability is immune to."""
    if chart is None or move_type is None:
        return 1.0
    if move_type in dfn.immune:
        return 0.0
    return G.effectiveness(chart, move_type, dfn.types)


def expected_damage(att, dfn, chart=None):
    """``att``'s best expected damage per turn on ``dfn``, with ``chart``
    (gamedata's type chart) counting types."""
    best = 0
    for _, power, kind, move_type in att.attacks:
        mult = type_multiplier(chart, move_type, dfn)
        if not mult:
            continue
        if kind == 'fixed':  # immunity only: Night Shade does its level to anything it can hit
            dmg = power
            mult = 1
            dmg = power
        elif kind == 'physical':
            dmg = formula(att.level, power, att.stats['atk'], dfn.stats['def'])
        elif kind == 'special':
            dmg = formula(att.level, power, att.stats['spa'], dfn.stats['spd'])
        else:
            dmg = (formula(att.level, power, att.stats['atk'], dfn.stats['def'])
                   + formula(att.level, power, att.stats['spa'], dfn.stats['spd'])) / 2
        best = max(best, dmg * mult)
    return best


def score(a, b, chart=None):
    """How far ``a`` is ahead of ``b``: turns ``b`` needs to KO it over turns
    it needs to KO ``b``, the faster side SPEED_BONUS turns longer. 0 when
    ``a`` can't damage ``b``. ``chart``: count types (expected_damage)."""
    hit_a, hit_b = expected_damage(a, b, chart), expected_damage(b, a, chart)
    if not hit_a:
        return 0.0
    if not hit_b:
        return float('inf')
    first = first_strike(a.stats['spe'], b.stats['spe'])
    turns_a = b.stats['hp'] / hit_a + SPEED_BONUS * (1 - first)
    turns_b = a.stats['hp'] / hit_b + SPEED_BONUS * first
    return turns_b / turns_a


def first_strike(speed_a, speed_b):
    """The modelled chance that the side with ``speed_a`` moves first."""
    return 1 / (1 + (speed_b / speed_a) ** SPEED_STEEPNESS)


def effective_level(mon, power_fn):
    """The reference's level whose score against a reference foe at
    ``mon``'s level matches ``mon``'s, clamped to LEVEL_RANGE; None for a
    Pokemon with no attack this model scores."""
    if not mon.attacks:
        return None
    foe = reference(mon.level, power_fn)
    target = score(mon, foe)
    lo, hi = LEVEL_RANGE
    if score(reference(hi, power_fn), foe) <= target:
        return hi
    if score(reference(lo, power_fn), foe) >= target:
        return lo
    for _ in range(BISECT_STEPS):
        mid = (lo * hi) ** 0.5
        if score(reference(mid, power_fn), foe) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def best_power(gd, species, level, moves, ivs):
    """A Pokemon's best expected power per turn (``move_power``; the level
    for Night Shade), 0 with no scored attack."""
    return max((p for _, p, *_ in fighter(gd, species, level, moves, ivs).attacks), default=0)


def fit_reference_power(gd, mons):
    """A least-squares fit of ``mons``' (TrainerMon, moves) best expected
    power to ``intercept + slope * ln(level)`` (it climbs fast early and
    flattens late), as a function of level (at least MIN_REFERENCE_POWER),
    with its intercept and slope."""
    points = [(math.log(m.level), p) for m, moves in mons
              if (p := best_power(gd, m.species, m.level, moves, m.ivs))]
    n = len(points)
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    slope = (sum((x - mx) * (y - my) for x, y in points) / sum((x - mx) ** 2 for x, _ in points))
    intercept = my - slope * mx

    def power_fn(level):
        return max(intercept + slope * math.log(level), MIN_REFERENCE_POWER)
    return power_fn, intercept, slope


def team_moves(gd, mon):
    """The moves a trainer Pokemon battles with: its set moves, or the default moveset."""
    return mon.moves or gd.default_moves(mon.species, mon.level)


def team_power(gd, trainer, power_fn):
    """Each of ``trainer``'s Pokemon as {species, level, effective, best_move}."""
    out = []
    for mon in trainer.mons:
        f = fighter(gd, mon.species, mon.level, team_moves(gd, mon), mon.ivs)
        eff = effective_level(f, power_fn)
        foe = reference(mon.level, power_fn)
        best = max(f.attacks, key=lambda a: expected_damage(Fighter(f.level, f.stats, [a]), foe), default=None)
        out.append({'species': mon.species, 'level': mon.level,
                    'effective': None if eff is None else round(eff, 1),
                    'best_move': best[0] if best else None, 'set_moves': bool(mon.moves)})
    return out
