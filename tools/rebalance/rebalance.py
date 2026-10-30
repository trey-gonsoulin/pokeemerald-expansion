#!/usr/bin/env python3
"""Measure how far Emerald's balance has drifted from vanilla (issue #113).

    python3 tools/rebalance/rebalance.py [--repo DIR] [--stages FILE] [--out-dir DIR]

Reads the repo's own data twice, once as the fork builds it (``modern``) and
once with the data and formula configs set to GEN_3 (``vanilla``, see
gamedata.VANILLA_OVERRIDES), and writes to ``output/``:

- ``report.md``: every table the findings are based on;
- ``trainer_mons.csv``: each trainer Pokemon with its vanilla and modern
  default moveset and the flags below;
- ``summary.json``: the same numbers as report.md, for scripts.

Nothing in src/ or data/ is written. Standard library only.
"""

import argparse
import bisect
import collections
import copy
import csv
import fnmatch
import functools
import http.server
import itertools
import json
import os
import re
import sys

import gamedata as G

DEFAULT_OUT_DIR = os.path.join(G.HERE, 'output')
DEFAULT_STAGES = os.path.join(G.HERE, 'story_stages.json')
CURVE_DATA = 'curve_data.json'  # the explorer's snapshot, in the output dir
# area_archetypes' vanilla snapshot, relative to the repo so --repo can point elsewhere.
VANILLA_WILD = os.path.relpath(G.R.AA.VANILLA_WILD, G.R.AA.REPO)

# A default-moveset attacking move counts as "above the level band" when it
# has at least this much power and the Gen 3 learnset teaches it at least
# ABOVE_BAND_LEVELS later than the Pokemon's level, or not at all.
ABOVE_BAND_POWER = 70
ABOVE_BAND_LEVELS = 10
# A hand-written move's category flip matters when the stat it now uses is
# this much stronger or weaker than the one it used in Gen 3.
STAT_SHIFT = 0.15
FLAGS = ('no_attack', 'lost_all_attacks', 'one_attack', 'lost_stab', 'above_band', 'new_strong')
# Party models for the level curve: name -> (regime, party size, Exp. Share on).
PARTY_MODELS = {
    'vanilla_solo': ('vanilla', 1, False),
    'vanilla_rotate4': ('vanilla', 4, False),
    'modern_solo': ('modern', 1, False),
    'modern_rotate4': ('modern', 4, False),
    'modern_share6': ('modern', 6, True),
}
START_LEVEL = 5
ECONOMY_ITEMS = ('POTION', 'SUPER_POTION', 'HYPER_POTION', 'MAX_POTION', 'FULL_RESTORE', 'REVIVE',
                 'FRESH_WATER', 'SODA_POP', 'LEMONADE', 'MOOMOO_MILK',
                 'FULL_HEAL', 'ANTIDOTE', 'PARALYZE_HEAL', 'POKE_BALL', 'GREAT_BALL', 'ULTRA_BALL',
                 'REPEL', 'SUPER_REPEL', 'ESCAPE_ROPE', 'NUGGET', 'STAR_PIECE', 'PEARL', 'BIG_PEARL')
# Level-curve scenarios: name -> (share of each stage's regular trainers
# fought, average wild battles per stage). The first gets the full table.
SCENARIOS = {
    'full clear': (1.0, 0),
    'half clear': (0.5, 0),
    'full clear + 20 wild battles per stage': (1.0, 20),
}
# Species the issue names for the physical/special split, plus the other
# Hoenn Pokemon whose STAB types sit on the "wrong" side of the Gen 3 rule.
SPLIT_WATCH = tuple('SPECIES_' + s for s in (
    'SCEPTILE', 'BLAZIKEN', 'SWAMPERT', 'SABLEYE', 'DUSCLOPS', 'BANETTE', 'SHARPEDO', 'GYARADOS',
    'MIGHTYENA', 'CRAWDAUNT', 'ABSOL', 'CACTURNE', 'SHIFTRY', 'GLALIE', 'WALREIN', 'MANECTRIC',
    'CAMERUPT', 'TORKOAL', 'KINGDRA', 'SALAMENCE', 'FLYGON', 'ALTARIA', 'GARDEVOIR', 'AZUMARILL',
    'MAWILE', 'AGGRON', 'METAGROSS', 'SKARMORY', 'BRELOOM', 'HARIYAMA', 'MEDICHAM', 'CLAYDOL'))
CURVE_CLASSES =('TRAINER_CLASS_LEADER', 'TRAINER_CLASS_ELITE_FOUR', 'TRAINER_CLASS_CHAMPION')

# Exp. Share curve (#127): the share6 party (one KO-taker, five on the Gen 6
# Exp. Share bench), modern data, under both trainer-exp settings and three
# affection brackets, with catch exp.
# B_TRAINER_EXP_MULTIPLIER values: Cmd_getexp gives the 1.5x for <= GEN_7.
TRAINER_EXP = {'1.5x off': 'GEN_LATEST', '1.5x on': 'GEN_6'}
AFFECTION = ('none', 'friendship', 'always')
# Catches per stage (B_EXP_CATCH: a catch gives the exp of a KO), at the
# stage's land-table average: about 30 over the story, a team of six plus
# some Pokedex filling.
CATCHES_PER_STAGE = 3
# Steps walked per stage for the friendship model: one walking event per 128
# steps, which applies half the time (+1).
WALK_STEPS_PER_STAGE = 4096
# sFriendshipEventModifiers rows the model uses, per friendship band.
FRIENDSHIP_EVENTS = {'level': (5, 3, 2), 'league': (3, 2, 1), 'walk': (1, 1, 1)}
AFFECTION_FOUR_HEARTS = 220  # GetMonAffectionHearts
MAX_FRIENDSHIP = 255
STANDARD_FRIENDSHIP = 50  # P_UPDATED_FRIENDSHIP >= GEN_8; 70 before
# Targets: on a full clear (modelled friendship), each story boss's ace sits
# TARGET_MARGIN levels above the Exp. Share bench; bosses are only raised.
# A half clear should leave the bench at most HALF_CLEAR_GAP below the ace
# (the half-clear bench trails the full-clear one by up to 7 levels late on,
# so no boss level is within 1 of one and a few levels of the other).
TARGET_MARGIN = 1
HALF_CLEAR_GAP = 8
# The owner's Elite Four and Champion spacing (#127): each at least this
# many levels above the one before, over the margin rule.
LEAGUE_STEPS = {'TRAINER_PHOEBE': ('TRAINER_SIDNEY', 1), 'TRAINER_GLACIA': ('TRAINER_PHOEBE', 1),
                'TRAINER_DRAKE': ('TRAINER_GLACIA', 1), 'TRAINER_WALLACE': ('TRAINER_DRAKE', 3)}
# Ordinary trainers and wild Pokemon (#150): each stage's regular trainers
# go up by one amount until their aces average at most TRAINER_GAP below
# the bench when fought, and its wild tables until their land average sits
# WILD_GAP below the bench at the stage's start. Raised Pokemon evolve
# (restock.SpeciesInfo.evolve, EVOLVE_GRACE levels past the evolution),
# except on EVOLVE_EXEMPT's teams: Wally's Ralts, caught on Route 102 (#138).
TRAINER_GAP = 5
WILD_GAP = 10
EVOLVE_EXEMPT = frozenset({'TRAINER_WALLY_MAUVILLE'})
# The party level the boss margin and the trainer and wild gaps measure
# against (#151), from the six members' levels and the KO-takers' count:
# the lowest member off the KO rotation (with five benched, the bench; with
# all six rotating, the lowest), the KO-takers' mean, the party's mean, the
# highest member.
REFERENCES = {
    'bench': lambda levels, ko_takers: min(levels[ko_takers:] or levels),
    'ko_mean': lambda levels, ko_takers: sum(levels[:ko_takers]) / ko_takers,
    'party_mean': lambda levels, ko_takers: sum(levels) / len(levels),
    'ace': lambda levels, ko_takers: max(levels),
}
# Full-clear runs (modelled friendship) that vary one assumption.
SHARE_SENSITIVITY = {
    'as modelled': {},
    'no catches': {'catches': 0},
    f'{2 * CATCHES_PER_STAGE} catches per stage': {'catches': 2 * CATCHES_PER_STAGE},
    'no walking': {'walk_steps': 0},
    f'{2 * WALK_STEPS_PER_STAGE:,} steps per stage': {'walk_steps': 2 * WALK_STEPS_PER_STAGE},
    'every stage trainer +3': {'trainer_raise': 3},
    # B_UNEVOLVED_EXP_MULTIPLIER's 1.2x on the whole party: the bound for a
    # player who keeps every Pokemon from evolving (Everstone, cancelling).
    'whole party unevolved (1.2x)': {'unevolved': True},
}


def short(const):
    """SPECIES_MR_MIME -> Mr Mime, MOVE_ROCK_TOMB -> Rock Tomb."""
    return const.split('_', 1)[1].replace('_', ' ').title() if const else ''


def fmt_types(types):
    return '/'.join(short(t) for t in types)


# ---------------------------------------------------------------------------
# Story stages
# ---------------------------------------------------------------------------

def load_stages(path, trainers, repo):
    """Each stage's regular trainers (by map), bosses and maps.

    A trainer belongs to the first stage whose map globs match the map its
    first non-rematch battle script is on. Bosses and excluded ids are never
    regular trainers.
    """
    with open(path, encoding='utf-8') as f:
        cfg = json.load(f)
    fill = {'RIVAL': cfg.get('rival', 'MAY'), 'STARTER': cfg.get('starter', 'MUDKIP')}
    choices = {k: cfg.get('rival_variants', {}).get(k, [v]) for k, v in fill.items()}
    stages = cfg['stages']
    templates = [st.get('bosses', ()) for st in stages]
    for st, ts in zip(stages, templates):
        st['bosses'] = [b.format(**fill) for b in ts]
        st['regular'] = []
    staged = {b for st in stages for b in st['bosses']}
    for st, ts in zip(stages, templates):
        # The same fight's other rival and starter teams, which the model doesn't play.
        st['variants'] = {}
        for b, bid in zip(ts, st['bosses']):
            if '{' not in b:
                continue
            ids = {b.format(**dict(zip(choices, c))) for c in itertools.product(*choices.values())} - staged
            if ids:
                st['variants'][bid] = sorted(ids)
    # Variants are kept out of the regular trainers and overrides like the bosses.
    bosses = staged.union(*(ids for st in stages for ids in st['variants'].values()))
    missing = sorted(b for b in bosses if b not in trainers)
    if missing:
        raise SystemExit(f'{path}: unknown boss trainers {missing}')
    excluded = cfg.get('exclude', ())
    overrides = [t for st in stages for t in st.get('trainers', ())]
    bad = sorted(t for t in overrides if t not in trainers or t in bosses
                 or any(fnmatch.fnmatchcase(t, g) for g in excluded))
    if bad or len(overrides) != len(set(overrides)):
        raise SystemExit(f'{path}: bad stage trainer overrides {bad or overrides}')
    for tid, folder in G.map_trainers(repo).items():
        if tid in bosses or tid not in trainers or any(fnmatch.fnmatchcase(tid, g) for g in excluded):
            continue
        # A stage's ``trainers`` ids override their map's stage (Route 103's swimmers need Surf).
        i = next((k for k, st in enumerate(stages) if tid in st.get('trainers', ())), None)
        if i is None:
            i = G.stage_of(folder, stages)
        if i is not None:
            stages[i]['regular'].append(tid)
    return stages


# ---------------------------------------------------------------------------
# Census
# ---------------------------------------------------------------------------

def census(trainers):
    mons = [m for t in trainers.values() for m in t.mons]
    ai = collections.Counter(' / '.join(t.ai) or '(none)' for t in trainers.values())
    flags = collections.Counter(a for t in trainers.values() for a in t.ai)
    return {
        'trainers': len(trainers),
        'mons': len(mons),
        'mons_with_moves': sum(1 for m in mons if m.moves),
        'mons_default': sum(1 for m in mons if not m.moves),
        'trainers_check_bad_move': flags['Check Bad Move'],
        'trainers_basic_trainer': flags['Basic Trainer'],
        'trainers_no_ai': ai['(none)'],
        'ai_flag_counts': dict(flags.most_common()),
        'ai_sets': dict(ai.most_common(12)),
    }


# ---------------------------------------------------------------------------
# Default movesets
# ---------------------------------------------------------------------------

def attacks(gd, moves, ivs=None):
    """The damaging moves, as Move data resolved for these IVs (Hidden Power)."""
    return [mv for _, mv in attack_pairs(gd, moves, ivs)]


def attack_pairs(gd, moves, ivs=None):
    """[(move id, resolved Move)] of the damaging moves."""
    resolved = ((m, gd.move(m, ivs)) for m in moves if m in gd.moves)
    return [(m, mv) for m, mv in resolved if mv.attacking]


def has_stab(gd, species, moves, ivs=None):
    """A same-type damaging move. Fixed-damage moves (Seismic Toss, Night
    Shade) count as attacks but get no STAB bonus, so they don't count here."""
    types = gd.species[species].types
    return any(mv.type in types and not mv.fixed_damage for mv in attacks(gd, moves, ivs))


def best_power(gd, moves, ivs=None):
    return max((mv.power for mv in attacks(gd, moves, ivs)), default=0)


def default_flags(gd, species, level, van_moves, mod_moves, ivs=None):
    """Flags for one trainer Pokemon on default moves (see the README)."""
    v, m = gd['vanilla'], gd['modern']
    flags = []
    mod_attacks, van_attacks = attack_pairs(m, mod_moves, ivs), attacks(v, van_moves, ivs)
    if not mod_attacks:
        flags.append('no_attack')
        if van_attacks:
            flags.append('lost_all_attacks')
    elif len(mod_attacks) == 1 and len(van_attacks) >= 2:
        flags.append('one_attack')
    if has_stab(v, species, van_moves, ivs) and not has_stab(m, species, mod_moves, ivs):
        flags.append('lost_stab')
    strong = [mid for mid, mv in mod_attacks if mv.power >= ABOVE_BAND_POWER]
    above = [mv for mv in strong if (v.learn_level(species, mv) or 0) >= level + ABOVE_BAND_LEVELS]
    new = [mv for mv in strong if v.learn_level(species, mv) is None]
    if above:
        flags.append('above_band')
    if new:
        flags.append('new_strong')
    return flags, above + new


def raised_defaults(trainers, gd, raises):
    """Boss Pokemon on default moves whose team ``raises`` lifts: the modern
    default moveset and flags at the current and the raised level."""
    rows = []
    for tid, delta in raises.items():
        for mon in trainers[tid].mons:
            if mon.moves or not delta:
                continue
            row = {'trainer': tid, 'species': mon.species, 'levels': [mon.level, min(mon.level + delta, 100)]}
            for key, level in zip(('now', 'raised'), row['levels']):
                v, m = gd['vanilla'].default_moves(mon.species, level), gd['modern'].default_moves(mon.species, level)
                row[key] = {'moves': m, 'flags': default_flags(gd, mon.species, level, v, m, mon.ivs)[0]}
            rows.append(row)
    return rows


def default_movesets(trainers, gd, story):
    """Every trainer Pokemon on default moves, with both movesets and flags."""
    rows = []
    for t in trainers.values():
        for i, mon in enumerate(t.mons):
            v = gd['vanilla'].default_moves(mon.species, mon.level)
            m = gd['modern'].default_moves(mon.species, mon.level)
            row = {'trainer': t.id, 'slot': i, 'class': t.trainer_class, 'species': mon.species,
                   'level': mon.level, 'set_moves': bool(mon.moves), 'story_stage': story.get(t.id, ''),
                   'vanilla_default': v, 'modern_default': m, 'flags': [], 'above_band_moves': [], 'ivs': mon.ivs}
            if not mon.moves:
                row['flags'], row['above_band_moves'] = default_flags(gd, mon.species, mon.level, v, m, mon.ivs)
            rows.append(row)
    return rows


def summarize_defaults(rows, gd):
    d = [r for r in rows if not r['set_moves']]
    story = [r for r in d if r['story_stage'] != '']
    out = {'default_mons': len(d), 'story_default_mons': len(story)}
    out['identical'] = sum(1 for r in d if r['vanilla_default'] == r['modern_default'])
    out['same_moves_any_order'] = sum(1 for r in d if set(r['vanilla_default']) == set(r['modern_default']))
    shared = [len(set(r['vanilla_default']) & set(r['modern_default'])) for r in d]
    out['shared_moves_histogram'] = dict(sorted(collections.Counter(shared).items()))
    for scope, group in (('all', d), ('story', story)):
        c = collections.Counter(f for r in group for f in r['flags'])
        out[f'flags_{scope}'] = dict(sorted(c.items()))
    v, m = gd['vanilla'], gd['modern']
    out['mean_attacks'] = {
        'vanilla': round(sum(len(attacks(v, r['vanilla_default'], r['ivs'])) for r in d) / len(d), 2),
        'modern': round(sum(len(attacks(m, r['modern_default'], r['ivs'])) for r in d) / len(d), 2)}
    out['mean_best_power'] = {
        'vanilla': round(sum(best_power(v, r['vanilla_default'], r['ivs']) for r in d) / len(d), 1),
        'modern': round(sum(best_power(m, r['modern_default'], r['ivs']) for r in d) / len(d), 1)}
    out['best_power_up'] = sum(1 for r in d if best_power(m, r['modern_default'], r['ivs']) > best_power(v, r['vanilla_default'], r['ivs']))
    out['best_power_down'] = sum(1 for r in d if best_power(m, r['modern_default'], r['ivs']) < best_power(v, r['vanilla_default'], r['ivs']))
    by_species = collections.defaultdict(collections.Counter)
    for r in d:
        for f in r['flags']:
            by_species[f][r['species']] += 1
    out['top_species'] = {f: by_species[f].most_common(12) for f in sorted(by_species)}
    examples = {}
    for f in FLAGS:
        seen = {}
        for r in story or d:
            if f in r['flags']:
                key = (r['species'], r['level'])
                seen.setdefault(key, r)
        examples[f] = [{'species': k[0], 'level': k[1], 'trainer': r['trainer'], 'stage': r['story_stage'],
                        'vanilla': r['vanilla_default'], 'modern': r['modern_default'],
                        'above_band_moves': r['above_band_moves']}
                       for k, r in list(seen.items())[:12]]
    out['story_examples'] = examples
    return out


# ---------------------------------------------------------------------------
# Hand-written movesets
# ---------------------------------------------------------------------------

def attack_stat(gd, species, category):
    s = gd.species[species].stats
    return s['baseAttack'] if category == 'DAMAGE_CATEGORY_PHYSICAL' else s['baseSpAttack']


def handwritten_changes(trainers, gd, boss_ids):
    """Every attacking set move on a hand-written moveset whose type,
    category, power or accuracy differs between vanilla and modern."""
    v, m = gd['vanilla'], gd['modern']
    changes = []
    for t in trainers.values():
        for i, mon in enumerate(t.mons):
            for mv in mon.moves:
                a, b = v.move(mv, mon.ivs), m.move(mv, mon.ivs)
                if (not (a.attacking or b.attacking)
                        or (a.type, a.category, a.power, a.accuracy) == (b.type, b.category, b.power, b.accuracy)):
                    continue
                row = {'trainer': t.id, 'boss': t.id in boss_ids, 'slot': i, 'species': mon.species,
                       'level': mon.level, 'move': mv,
                       'type': [a.type, b.type], 'category': [a.category, b.category],
                       'power': [a.power, b.power], 'accuracy': [a.accuracy, b.accuracy]}
                # Fixed-damage moves (Night Shade, Sonic Boom) use no attacking stat.
                if (a.category != b.category and 'DAMAGE_CATEGORY_STATUS' not in (a.category, b.category)
                        and not (a.fixed_damage or b.fixed_damage)):
                    sa, sb = attack_stat(v, mon.species, a.category), attack_stat(m, mon.species, b.category)
                    row['stat'] = [sa, sb]
                    row['stat_shift'] = ('weaker' if sb < sa * (1 - STAT_SHIFT)
                                         else 'stronger' if sb > sa * (1 + STAT_SHIFT) else 'similar')
                changes.append(row)
    return changes


def summarize_handwritten(changes, trainers):
    mons_with_set = sum(1 for t in trainers.values() for mon in t.mons if mon.moves)
    flips = [c for c in changes if 'stat' in c]
    out = {
        'mons_with_set_moves': mons_with_set,
        'moves_changed': len(changes),
        'mons_with_category_flip': len({(c['trainer'], c['slot']) for c in flips}),
        'category_flips': len(flips),
        'flip_shift': dict(collections.Counter(c['stat_shift'] for c in flips)),
        'mons_with_flip_weaker': len({(c['trainer'], c['slot']) for c in flips if c['stat_shift'] == 'weaker'}),
        'type_changes': len([c for c in changes if c['type'][0] != c['type'][1]]),
        'power_changes': len([c for c in changes if c['power'][0] != c['power'][1]]),
        'accuracy_changes': len([c for c in changes if c['accuracy'][0] != c['accuracy'][1]]),
    }
    per_move = collections.defaultdict(collections.Counter)
    for c in changes:
        per_move[c['move']][c.get('stat_shift', 'data')] += 1
    out['per_move'] = {mv: dict(cnt) for mv, cnt in sorted(per_move.items(), key=lambda kv: -sum(kv[1].values()))}
    return out


def better_stat(stats):
    atk, spa = stats['baseAttack'], stats['baseSpAttack']
    if atk > spa * (1 + STAT_SHIFT):
        return 'physical'
    if spa > atk * (1 + STAT_SHIFT):
        return 'special'
    return 'mixed'


def split_fit(gd, species_list):
    """For each species: its better attacking stat, the Gen 3 category of each
    of its STAB types, and how its modern level-up STAB moves split."""
    v, m = gd['vanilla'], gd['modern']
    rows = []
    for sp in species_list:
        if sp not in m.species:
            continue
        cats = {t: short(v.type_categories.get(t, '')).replace('Category ', '').lower() for t in v.species[sp].types}
        # As in has_stab: no fixed-damage moves; Hidden Power's type depends on the IVs.
        stab = [mv for _, mv in m.learnset(sp) if mv in m.moves and m.moves[mv].attacking
                and not m.moves[mv].fixed_damage and m.moves[mv].effect != 'EFFECT_HIDDEN_POWER'
                and m.moves[mv].type in m.species[sp].types]
        stab = list(dict.fromkeys(stab))
        phys = sum(1 for mv in stab if m.moves[mv].category == 'DAMAGE_CATEGORY_PHYSICAL')
        rows.append({'species': sp, 'atk': m.species[sp].stats['baseAttack'], 'spa': m.species[sp].stats['baseSpAttack'],
                     'better': better_stat(m.species[sp].stats), 'vanilla_stab': cats,
                     'modern_types': list(m.species[sp].types),
                     'modern_stab_physical': phys, 'modern_stab_special': len(stab) - phys})
    return rows


# ---------------------------------------------------------------------------
# Type matchups of the bosses
# ---------------------------------------------------------------------------

def mon_moves(gd, mon):
    return mon.moves or gd.default_moves(mon.species, mon.level)


def best_vs(gd, moves, def_type, ivs=None):
    """The best type multiplier of the moves against one type; fixed-damage
    moves ignore the multiplier, so they don't count."""
    return max((G.effectiveness(gd.chart, mv.type, (def_type,)) for mv in attacks(gd, moves, ivs)
                if not mv.fixed_damage), default=None)


def boss_matchups(trainers, gd, boss_ids):
    """Per boss Pokemon: retyping, defensive changes per attacking type and
    the best multiplier its moves get against each single defending type."""
    v, m = gd['vanilla'], gd['modern']
    gen3 = sorted(G.GEN3_TYPES)
    out = {}
    for bid in boss_ids:
        rows = []
        for mon in trainers[bid].mons:
            tv, tm = v.species[mon.species].types, m.species[mon.species].types
            defense = {}
            for at in gen3 + ['TYPE_FAIRY']:
                a = G.effectiveness(v.chart, at, tv) if at in G.GEN3_TYPES else None
                b = G.effectiveness(m.chart, at, tm)
                if a != b and not (a is None and b == 1.0):
                    defense[at] = [a, b]
            mv_v, mv_m = mon_moves(v, mon), mon_moves(m, mon)
            offense = {}
            for dt in gen3 + ['TYPE_FAIRY']:
                a = best_vs(v, mv_v, dt, mon.ivs) if dt in G.GEN3_TYPES else None
                b = best_vs(m, mv_m, dt, mon.ivs)
                if a != b and not (a is None and b in (None, 1.0)):
                    offense[dt] = [a, b]
            rows.append({'species': mon.species, 'level': mon.level, 'set_moves': bool(mon.moves),
                         'types': [list(tv), list(tm)], 'defense': defense, 'offense': offense,
                         'moves': [mv_v, mv_m]})
        out[bid] = rows
    return out


# ---------------------------------------------------------------------------
# Level curve
# ---------------------------------------------------------------------------

def exp_for_level(growth, n):
    """gExperienceTables (only the growth rates the model uses)."""
    if n <= 1:
        return 0
    if growth == 'GROWTH_MEDIUM_SLOW':
        return (6 * n ** 3) // 5 - 15 * n * n + 100 * n - 140
    if growth == 'GROWTH_MEDIUM_FAST':
        return n ** 3
    if growth == 'GROWTH_FAST':
        return (4 * n ** 3) // 5
    if growth == 'GROWTH_SLOW':
        return (5 * n ** 3) // 4
    raise ValueError(growth)


@functools.cache
def exp_table(growth):
    return [exp_for_level(growth, n) for n in range(1, 101)]


def level_for_exp(growth, exp):
    return bisect.bisect_right(exp_table(growth), exp)


def scaling_factors(power=2.5, size=211):
    """sExperienceScalingFactors as (i^power)/4: the game's table at 2.5,
    a steeper level-gap penalty above it (#151)."""
    return [int(i ** power / 4) for i in range(size)]


def exp_award(gd, scaling, yield_, foe_level, getter_level, trainer, sent_in, sent_out=True, holders=0,
              affection=False, unevolved=False, share_fraction=0.5, overlevel_cutoff=None):
    """Cmd_getexp + ApplyExperienceMultipliers for one getter (no Lucky Egg
    or traded bonuses).

    ``sent_in`` is viaSentIn (party members that faced the foe), ``sent_out``
    whether the getter is one of them, and ``holders`` viaExpShare (members
    getting exp through an Exp. Share). The model only uses the Gen 6 Exp.
    Share, which makes every member a holder, so the getter holds it
    whenever ``holders`` is non-zero. ``affection``: the getter has 4+
    hearts, worth 4915/4096 (1.2x) under B_AFFECTION_MECHANICS.
    ``unevolved``: the getter is at or past its EVO_LEVEL level unevolved,
    another 4915/4096 (applied first) under B_UNEVOLVED_EXP_MULTIPLIER.

    Formula options the game doesn't have (#151): ``share_fraction``, the
    Gen 6+ Exp. Share bench share (the game's half; B_SPLIT_EXP < GEN_6
    ignores it), and
    ``overlevel_cutoff``, 1 exp for a getter more than that many levels
    above the foe. ``scaling`` can be any scaling_factors table."""
    scaled = gd.flag('B_SCALED_EXP >= GEN_5 && B_SCALED_EXP != GEN_6')
    calc = yield_ * foe_level // (5 if scaled else 7)
    if trainer and gd.flag('B_TRAINER_EXP_MULTIPLIER <= GEN_7'):
        calc = calc * 150 // 100
    if gd.flag('B_SPLIT_EXP < GEN_6'):
        # Half to the sent-in members, half split over every holder; a
        # sent-in holder gets both shares.
        sent_share = max(calc // 2 // sent_in, 1) if holders else max(calc // sent_in, 1)
        reward = (sent_share if sent_out else 0) + (max(calc // 2 // holders, 1) if holders else 0)
    elif sent_out:
        reward = calc
    else:
        reward = max(int(calc * share_fraction), 1) if holders and share_fraction else 0
    if not reward:
        return 0  # the game skips a getter that neither faced the foe nor holds a share
    if overlevel_cutoff is not None and getter_level > foe_level + overlevel_cutoff:
        return 1
    if unevolved and gd.flag('B_UNEVOLVED_EXP_MULTIPLIER >= GEN_6'):
        reward = reward * 4915 // 4096
    if affection and gd.flag('B_AFFECTION_MECHANICS == TRUE'):
        reward = reward * 4915 // 4096
    if scaled:
        reward = reward * scaling[foe_level * 2 + 10] // scaling[foe_level + getter_level + 10] + 1
    return reward


def friendship_gain(friendship, event):
    """sFriendshipEventModifiers: the gain for ``event`` at this friendship
    (bands 0-99, 100-199, 200+)."""
    return FRIENDSHIP_EVENTS[event][(friendship > 99) + (friendship > 199)]


class Party:
    """``affection``: 'none' (no 1.2x), 'always' (4 hearts from the start) or
    'friendship' (1.2x once a member's modelled friendship reaches 220).
    ``unevolved``: every member gets the unevolved 1.2x (kept from evolving).
    ``ko_takers``: with the Exp. Share, the KOs rotate over the first this
    many members (1: one lead and five benched, 6: the whole team in turn).
    ``share_fraction`` and ``overlevel_cutoff`` go to exp_award."""

    def __init__(self, size, growth='GROWTH_MEDIUM_SLOW', level=START_LEVEL, affection='none',
                 friendship=STANDARD_FRIENDSHIP, unevolved=False, ko_takers=1, share_fraction=0.5,
                 overlevel_cutoff=None):
        if affection not in AFFECTION:
            raise ValueError(affection)
        if not 1 <= ko_takers <= size:
            raise ValueError(ko_takers)
        self.growth = growth
        self.unevolved = unevolved
        self.ko_takers = ko_takers
        self.share_fraction = share_fraction
        self.overlevel_cutoff = overlevel_cutoff
        self.exp = [float(exp_for_level(growth, level))] * size
        self.friendship = [float(friendship)] * size
        self.affection = affection
        self.turn = 0

    def levels(self):
        return [level_for_exp(self.growth, int(e)) for e in self.exp]

    def has_affection(self, i):
        return self.affection == 'always' or (self.affection == 'friendship'
                                              and self.friendship[i] >= AFFECTION_FOUR_HEARTS)

    def befriend(self, event, times=1, chance=1.0, members=None):
        """AdjustFriendship for every member (or ``members``), ``times`` over;
        ``chance`` is the expected share of them that apply (walking: 50%)."""
        for i in range(len(self.friendship)) if members is None else members:
            f = self.friendship[i]
            for _ in range(times):
                f = min(f + chance * friendship_gain(f, event), MAX_FRIENDSHIP)
            self.friendship[i] = f

    def defeat(self, gd, scaling, foes, trainer, share):
        """One KO by a single sent-in member (round-robin over the party, or
        over the ``ko_takers`` with the Exp. Share), the rest of the party
        sharing through the Gen 6 Exp. Share when ``share``. ``foes`` is
        [(exp yield, level, weight)]: one foe, or a wild battle's
        rate-weighted average over its slots. Each level gained adds the
        level-up friendship."""
        lv = self.levels()
        ko = self.turn % (self.ko_takers if share else len(self.exp))
        self.turn += 1
        for i, level in enumerate(lv):
            if i != ko and not share:
                continue
            self.exp[i] += sum(w * exp_award(gd, scaling, y, foe_level, level, trainer, 1,
                                             sent_out=i == ko, holders=len(lv) if share else 0,
                                             affection=self.has_affection(i), unevolved=self.unevolved,
                                             share_fraction=self.share_fraction,
                                             overlevel_cutoff=self.overlevel_cutoff)
                               for y, foe_level, w in foes)
            self.befriend('level', level_for_exp(self.growth, int(self.exp[i])) - level, members=(i,))


def stage_slots(wild, stages, folders):
    """Stage index -> [(table field, slot, encounter rate)] over every table
    of the stage's maps (land, water, fishing, Rock Smash)."""
    by_id = {mid: f for f, mid in folders.items()}
    out = collections.defaultdict(list)
    for group in wild['wild_encounter_groups']:
        rates = {f['type']: f.get('encounter_rates') or () for f in group.get('fields', ())}
        for enc in group['encounters']:
            folder = by_id.get(enc.get('map'))
            if not folder:
                continue
            for field, table in enc.items():
                if not (isinstance(table, dict) and 'mons' in table):
                    continue
                i = G.stage_of(folder, stages, land=field == 'land_mons')
                if i is not None:
                    rate = rates.get(field, ())
                    for k, slot in enumerate(table['mons']):
                        out[i].append((field, slot, rate[k] if k < len(rate) else 0))
    return out


def land_foes(slots):
    """A stage's land slots as [(species, level, weight)], each slot's rate
    spread evenly over its level range."""
    foes = []
    for field, slot, rate in slots:
        if field == 'land_mons' and rate:
            levels = range(slot['min_level'], slot['max_level'] + 1)
            foes += [(slot['species'], lvl, rate / len(levels)) for lvl in levels]
    return foes


def wild_battle_foes(gd, slots):
    """A stage's average wild battle as Party.defeat foes: [(exp yield,
    level, share of the encounter rate)] over its land slots."""
    foes = land_foes(slots)
    total = sum(w for _, _, w in foes)
    return [(gd.species[sp].exp_yield, lvl, w / total) for sp, lvl, w in foes]


def cleared(regular, clear):
    """An evenly spread ``clear`` share of a stage's regular trainers."""
    return [t for k, t in enumerate(regular) if int((k + 1) * clear) > int(k * clear)]


def wild_availability(slots, stages, gd):
    """Per stage: species the restock added over the vanilla tables, the
    strongest of them by base stat total, and the Fairy types first met."""
    tables = {}
    for regime, by_stage in slots.items():
        tables[regime] = {}
        for i, stage_slots_ in by_stage.items():
            lowest = tables[regime].setdefault(i, {})
            for _, slot, _ in stage_slots_:
                lowest[slot['species']] = min(lowest.get(slot['species'], 100), slot['min_level'])
    m = gd['modern']
    rows = []
    seen = {r: set() for r in G.REGIMES}

    def bst(sp):
        return sum(m.species[sp].stats.values()) if sp in m.species else 0
    for i, st in enumerate(stages):
        here = tables['modern'].get(i, {})
        fairy = sorted(sp for sp in here if sp not in seen['modern']
                       and sp in m.species and 'TYPE_FAIRY' in m.species[sp].types)
        for r in G.REGIMES:
            seen[r] |= set(tables[r].get(i, {}))
        new_here = {sp: lvl for sp, lvl in here.items() if sp not in seen['vanilla']}
        rows.append({'stage': st['name'], 'vanilla_species': len(seen['vanilla']), 'modern_species': len(seen['modern']),
                     'new_species': len(new_here),
                     'strongest_new': sorted(((sp, bst(sp), lvl) for sp, lvl in new_here.items()),
                                             key=lambda x: (-x[1], x[0]))[:6],
                     'fairy_first': fairy})
    return rows


def level_curve(stages, trainers, gd, scaling, wilds, clear=1.0, wild_per_stage=0):
    """Party levels just before each boss under each party model: the ace's
    level for solo and share models (plus the bench mean for share), the
    party mean for rotation models."""
    rows = []
    parties = {name: Party(size) for name, (_, size, _) in PARTY_MODELS.items()}

    def fight(tid):
        for name, (regime, _, share) in PARTY_MODELS.items():
            d = gd[regime]
            for mon in trainers[tid].mons:
                parties[name].defeat(d, scaling, [(d.species[mon.species].exp_yield, mon.level, 1.0)], True, share)

    def wild_battles(i):
        """``wild_per_stage`` average wild battles: every land slot of the
        stage's maps, weighted by its encounter rate, KO'd by one member."""
        for name, (regime, _, share) in PARTY_MODELS.items():
            d = gd[regime]
            foes = wild_battle_foes(d, wilds.get(regime, {}).get(i, ()))
            for _ in range(wild_per_stage if foes else 0):
                parties[name].defeat(d, scaling, foes, False, share)

    for i, st in enumerate(stages):
        wild_battles(i)
        for tid in cleared(st['regular'], clear):
            fight(tid)
        for bid in st['bosses']:
            lv = [mon.level for mon in trainers[bid].mons]
            row = {'stage': st['name'], 'boss': bid, 'class': trainers[bid].trainer_class,
                   'boss_ace': max(lv), 'boss_mean': round(sum(lv) / len(lv), 1)}
            for name, (_, size, share) in PARTY_MODELS.items():
                levels = parties[name].levels()
                if share:
                    row[name] = levels[0]
                    row[name + '_bench'] = round(sum(levels[1:]) / (size - 1), 1)
                else:
                    row[name] = levels[0] if size == 1 else round(sum(levels) / size, 1)
            rows.append(row)
            fight(bid)
    return rows


def with_configs(gd, **values):
    """``gd`` with some config values replaced (data shared, flags recomputed)."""
    out = copy.copy(gd)
    out.defines = {**gd.defines, **values}
    out._flags = {}
    return out


def evolver(info, gd):
    """restock.SpeciesInfo.evolve as ``evolve(species, level, gender)``,
    kept to the species ``gd`` has."""
    @functools.lru_cache(maxsize=None)
    def evolve(species, level, gender=None):
        out = info.evolve(species, level, gender=gender)
        return out if out in gd.species else species
    return evolve


def team_ace(trainer):
    """A team's highest level."""
    return max(mon.level for mon in trainer.mons)


def land_mean(slots):
    """The encounter-weighted mean level of ``slots``' land tables, or None."""
    foes = land_foes(slots)
    total = sum(w for _, _, w in foes)
    return sum(lvl * w for _, lvl, w in foes) / total if total else None


def shifted_slots(slots, shift, evolve=None):
    """``slots`` ([(field, slot, rate)]) with every level ``shift`` higher,
    capped at 100. A raised slot's species evolves for its new min level
    (``evolve(species, level)``), as the restock does (#150)."""
    if not shift:
        return slots
    out = []
    for field, slot, rate in slots:
        lo, hi = (max(1, min(slot[k] + shift, 100)) for k in ('min_level', 'max_level'))
        species = evolve(slot['species'], lo) if evolve and shift > 0 else slot['species']
        out.append((field, {**slot, 'species': species, 'min_level': lo, 'max_level': hi}, rate))
    return out


def share_curve(*args, **kwargs):
    """share_run's boss rows."""
    return share_run(*args, **kwargs)[0]


def share_run(stages, trainers, gd, scaling, wilds, clear=1.0, affection='friendship',
              catches=CATCHES_PER_STAGE, walk_steps=WALK_STEPS_PER_STAGE, trainer_raise=0, raises=None,
              margin=None, unevolved=False, stage_raises=None, wild_offsets=None, trainer_gap=None,
              wild_gap=None, vanilla_wilds=None, evolve=None, ko_takers=1, boss_ref='bench',
              share_fraction=0.5, overlevel_cutoff=None, league_steps=True, wild_battles=0):
    """The share6 party (KO-taker plus five on the Gen 6 Exp. Share bench)
    just before each story boss, on ``gd``'s data and configs: (boss rows,
    stage rows).

    Each stage starts with ``walk_steps`` of walking, ``catches`` catches
    (wild exp at the stage's land-table average, when B_EXP_CATCH gives it)
    and ``wild_battles`` wild KOs at the same average, then its cleared
    trainers, then its bosses. A gym leader,
    Elite Four or Champion battle adds league friendship. ``raises`` adds
    levels to every Pokemon of a boss's team, ``stage_raises`` (stage name
    -> levels) and ``trainer_raise`` to every Pokemon of a stage's regular
    trainers. ``wild_offsets`` (stage name -> levels over the vanilla
    tables in ``vanilla_wilds``) moves the catches' levels; the difference
    between ``wilds`` and ``vanilla_wilds`` is what is already applied.
    ``evolve(species, level, gender)`` evolves the raised Pokemon (not
    EVOLVE_EXEMPT's teams) and the raised wild slots.

    With ``margin``, each boss is raised, when its ace is lower, to the
    reference level plus ``margin`` and then (``league_steps``) to
    LEAGUE_STEPS above the boss before it. With ``wild_gap``, each stage's
    wild offset puts its land average ``wild_gap`` below the reference at
    the stage's start; with ``trainer_gap``, each stage's raise is the
    smallest one that leaves its regular trainers' aces at most
    ``trainer_gap`` below the reference when fought, on average. All in one
    pass, so a raise counts toward the later stages' exp. ``unevolved``
    gives the whole party the unevolved 1.2x.

    The party (#151): the KOs rotate over ``ko_takers`` members (Party),
    and ``share_fraction`` and ``overlevel_cutoff`` change the exp
    (exp_award). ``boss_ref`` picks the reference level from REFERENCES;
    each row's ``bench`` is the lowest member off the KO rotation (the
    lowest member when all six take KOs), ``ref`` the reference level and
    ``levels`` every member's."""
    raises = dict(raises or {})
    stage_raises, wild_offsets = stage_raises or {}, wild_offsets or {}
    reference = REFERENCES[boss_ref]
    friendship = STANDARD_FRIENDSHIP if gd.flag('P_UPDATED_FRIENDSHIP >= GEN_8') else 70
    party = Party(6, affection=affection, friendship=friendship, unevolved=unevolved, ko_takers=ko_takers,
                  share_fraction=share_fraction, overlevel_cutoff=overlevel_cutoff)
    catch = catches if gd.flag('B_EXP_CATCH >= GEN_6') else 0
    rows, stage_rows = [], []

    def ref(p):
        return reference(p.levels(), ko_takers)

    def fight(p, tid, delta=0):
        for mon in trainers[tid].mons:
            level = min(mon.level + delta, 100)
            species = mon.species
            if delta > 0 and evolve and tid not in EVOLVE_EXEMPT:
                species = evolve(species, level, mon.gender)
            p.defeat(gd, scaling, [(gd.species[species].exp_yield, level, 1.0)], True, True)

    def fight_trainers(p, st, d):
        """The stage's cleared trainers: each one's reference - ace, and its ace."""
        gaps, aces = [], []
        for tid in cleared(st['regular'], clear):
            aces.append(min(team_ace(trainers[tid]) + trainer_raise + d, 100))
            gaps.append(ref(p) - aces[-1])
            fight(p, tid, trainer_raise + d)
        return gaps, aces

    def meets_gap(st, d):
        gaps, _ = fight_trainers(copy.deepcopy(party), st, d)
        return not gaps or sum(gaps) / len(gaps) <= trainer_gap

    for i, st in enumerate(stages):
        party.befriend('walk', walk_steps // 128, chance=0.5)
        start = ref(party)
        slots = wilds.get(i, ())
        base, now = land_mean((vanilla_wilds or {}).get(i, ())), land_mean(slots)
        applied = round(now - base) if base is not None and now is not None else 0
        if wild_gap is not None and base is not None:
            offset = max(0, round(start - wild_gap - base))
        else:
            offset = wild_offsets.get(st['name'], applied)
        here = shifted_slots(slots, offset - applied, evolve)
        foes = wild_battle_foes(gd, here)
        for _ in range((catch + wild_battles) if foes else 0):
            party.defeat(gd, scaling, foes, False, True)
        if trainer_gap is not None and st['regular']:
            d = next((d for d in range(100) if meets_gap(st, d)), 100)
        else:
            d = stage_raises.get(st['name'], 0)
        gaps, aces = fight_trainers(party, st, d)
        mean = land_mean(here)
        stage_rows.append({'stage': st['name'], 'start_bench': start, 'trainers': len(gaps),
                           'gap': round(sum(gaps) / len(gaps), 1) if gaps else None, 'raise': d,
                           'trainer_ace_mean': round(sum(aces) / len(aces), 1) if aces else None,
                           'wild_land_mean': round(mean, 1) if mean is not None else None,
                           'wild_offset': offset, 'wild_applied': applied})
        for bid in st['bosses']:
            levels = party.levels()
            level = reference(levels, ko_takers)
            base_ace = team_ace(trainers[bid])
            if margin is not None:
                raises[bid] = max(0, int(level + margin - base_ace + 0.5))
                if league_steps and bid in LEAGUE_STEPS:
                    prev, step = LEAGUE_STEPS[bid]
                    raises[bid] = max(raises[bid], team_ace(trainers[prev]) + raises.get(prev, 0) + step - base_ace)
            delta = raises.get(bid, 0)
            rows.append({'stage': st['name'], 'boss': bid, 'class': trainers[bid].trainer_class,
                         'base_ace': base_ace, 'raise': delta, 'boss_ace': min(base_ace + delta, 100),
                         'ace': levels[0], 'bench': REFERENCES['bench'](levels, ko_takers),
                         'ref': round(level, 1), 'levels': levels, 'friendship': int(party.friendship[-1])})
            if trainers[bid].trainer_class in CURVE_CLASSES:
                party.befriend('league')
            fight(party, bid, delta)
    return rows, stage_rows


def stage_trainer_levels(stages, trainers):
    """Per stage with regular trainers: how many, and the mean and highest
    of their aces (each trainer's highest level)."""
    rows = []
    for st in stages:
        aces = [team_ace(trainers[t]) for t in st['regular']]
        if aces:
            rows.append({'stage': st['name'], 'trainers': len(aces), 'mean_ace': round(sum(aces) / len(aces), 1),
                         'max_ace': max(aces)})
    return rows


def stage_variants(stages, trainers):
    """Staged boss -> {rival variant (the same fight's other rival and
    starter teams): its ace}."""
    return {bid: {v: team_ace(trainers[v]) for v in ids} for st in stages for bid, ids in st['variants'].items()}


def variant_raises(variants, trainers, raises):
    """The raise for each of ``variants`` (from stage_variants) that lifts
    its ace to its staged boss's raised ace."""
    out = {}
    for bid, aces in variants.items():
        target = min(team_ace(trainers[bid]) + raises.get(bid, 0), 100)
        for v, ace in aces.items():
            out[v] = max(0, target - ace)
    return out


def share_curves(stages, trainers, gd, scaling, wilds):
    """Per TRAINER_EXP setting: the share6 curve now (full and half clear,
    every AFFECTION bracket), the boss raises that meet TARGET_MARGIN on a
    full clear with modelled friendship (the rival variants' included), the
    curve after them, and how the full-clear bench (now) moves with
    SHARE_SENSITIVITY's assumptions."""
    out = {}
    variants = stage_variants(stages, trainers)
    for name, value in TRAINER_EXP.items():
        d = with_configs(gd, B_TRAINER_EXP_MULTIPLIER=value)

        def curves(raises):
            return {f'{clear_name} / {aff}': share_curve(stages, trainers, d, scaling, wilds, clear, aff, raises=raises)
                    for clear_name, clear in (('full', 1.0), ('half', 0.5)) for aff in AFFECTION}
        raises = {r['boss']: r['raise']
                  for r in share_curve(stages, trainers, d, scaling, wilds, margin=TARGET_MARGIN,
                                       league_steps=False)}  # #127's rule; the steps are an explorer knob
        raises.update(variant_raises(variants, trainers, raises))
        out[name] = {'now': curves(None), 'raises': raises, 'after': curves(raises),
                     'variants': variants,
                     'sensitivity': {label: share_curve(stages, trainers, d, scaling, wilds, **kw)
                                     for label, kw in SHARE_SENSITIVITY.items()}}
    return out


# ---------------------------------------------------------------------------
# Curve explorer (#151)
# ---------------------------------------------------------------------------

def curve_snapshot(stages, trainers, gd, scaling, wilds, info):
    """share_run's inputs as JSON data (output/curve_data.json), so the
    explorer runs the same model without the repo: the story stages and
    their trainers, the exp yields, the level evolutions, the scaling
    table, both regimes' land slots (the only ones share_run reads) and the
    config defines."""
    story = sorted({t for st in stages for t in st['regular'] + st['bosses']})
    return {
        'stages': [{k: st[k] for k in ('name', 'regular', 'bosses')} for st in stages],
        'trainers': {t: {'class': trainers[t].trainer_class,
                         'mons': [[m.species, m.level, m.gender] for m in trainers[t].mons]} for t in story},
        'exp_yield': {sp: s.exp_yield for sp, s in gd.species.items()},
        'alias': info.alias,
        'evolutions': {sp: lv for sp, evos in info.evos.items() if (lv := [e for e in evos if e[0] == 'EVO_LEVEL'])},
        'scaling': scaling,
        'wilds': {regime: {i: [(field, {k: slot[k] for k in ('species', 'min_level', 'max_level')}, rate)
                               for field, slot, rate in slots if field == 'land_mons']
                           for i, slots in sorted(by_stage.items())}
                  for regime, by_stage in wilds.items()},
        'defines': gd.defines,
    }


def load_snapshot(data):
    """curve_snapshot's data back as share_run's inputs: {stages, trainers,
    gd, scaling, wilds, evolve}, as explore_run takes them."""
    gd = G.GameData.from_parts(data['defines'], {sp: G.Species((), {}, y, '', '')
                                                 for sp, y in data['exp_yield'].items()})
    trainers = {t: G.Trainer(t, '', v['class'], [], False,
                             [G.TrainerMon(sp, level, [], gender=gender) for sp, level, gender in v['mons']])
                for t, v in data['trainers'].items()}
    info = G.R.SpeciesInfo.from_evolutions(data['alias'], data['evolutions'])
    wilds = {regime: {int(i): slots for i, slots in by_stage.items()} for regime, by_stage in data['wilds'].items()}
    return {'stages': data['stages'], 'trainers': trainers, 'gd': gd, 'scaling': data['scaling'],
            'wilds': wilds, 'evolve': evolver(info, gd)}


# The explorer's knobs and their defaults: the game as report.md models it
# (share6, full clear, modelled friendship, 1.5x off, today's levels).
EXPLORER_KNOBS = {
    'ko_takers': 1, 'boss_ref': 'bench', 'clear': 1.0, 'catches': CATCHES_PER_STAGE, 'wild_battles': 0,
    'walk_steps': WALK_STEPS_PER_STAGE, 'affection': 'friendship', 'trainer_exp': '1.5x off',
    'scaled_exp': True, 'scaling_power': 2.5, 'overlevel_cutoff': None, 'share_fraction': 0.5,
    'margin': None, 'league_steps': True, 'trainer_gap': None, 'wild_gap': None, 'evolve': True,
}


def explore_run(snap, knobs=None):
    """share_run for EXPLORER_KNOBS settings on ``snap`` (load_snapshot's
    inputs, or the same dict from the parsed repo): {knobs, bosses
    (share_run's rows plus a short name and every REFERENCES level), stages,
    lv100 (the first boss the party's highest member meets at 100, or
    None)}."""
    unknown = set(knobs or {}) - set(EXPLORER_KNOBS)
    if unknown:
        raise ValueError(f'unknown knobs {sorted(unknown)}')
    k = {**EXPLORER_KNOBS, **(knobs or {})}
    gd = with_configs(snap['gd'], B_TRAINER_EXP_MULTIPLIER=TRAINER_EXP[k['trainer_exp']],
                      B_SCALED_EXP='GEN_LATEST' if k['scaled_exp'] else 'GEN_6')
    # The game's own table at its exponent (scaling_factors matches it, tested).
    scaling = snap['scaling'] if k['scaling_power'] == 2.5 else scaling_factors(k['scaling_power'],
                                                                                   len(snap['scaling']))
    bosses, stage_rows = share_run(
        snap['stages'], snap['trainers'], gd, scaling, snap['wilds']['modern'], clear=k['clear'],
        affection=k['affection'], catches=k['catches'], walk_steps=k['walk_steps'], margin=k['margin'],
        trainer_gap=k['trainer_gap'], wild_gap=k['wild_gap'], vanilla_wilds=snap['wilds']['vanilla'],
        evolve=snap['evolve'] if k['evolve'] else None, ko_takers=k['ko_takers'], boss_ref=k['boss_ref'],
        share_fraction=k['share_fraction'], overlevel_cutoff=k['overlevel_cutoff'],
        league_steps=k['league_steps'], wild_battles=k['wild_battles'])
    for r in bosses:
        r['name'] = short(r['boss'])
        r['refs'] = {name: round(f(r['levels'], k['ko_takers']), 1) for name, f in REFERENCES.items()}
    return {'knobs': k, 'bosses': bosses, 'stages': stage_rows,
            'lv100': next((r['name'] for r in bosses if max(r['levels']) >= 100), None)}


def print_curve(res):
    """explore_run's result as text tables, for the ``curve`` command."""
    print(table(['boss', 'stage', 'boss ace (now)', 'raise', 'boss ace', 'party levels', 'reference'],
                [[r['name'], r['stage'], r['base_ace'], f"+{r['raise']}", r['boss_ace'],
                  ' '.join(map(str, r['levels'])), r['ref']] for r in res['bosses']]))
    print()
    print(table(['stage', 'reference at start', 'trainers', 'trainer raise', 'trainer ace mean', 'gap when fought',
                 'wild offset', 'wild land mean'],
                [[s['stage'], round(s['start_bench'], 1), s['trainers'], f"+{s['raise']}", s['trainer_ace_mean'],
                  s['gap'], s['wild_offset'], s['wild_land_mean']] for s in res['stages']]))
    print(f"\nLv 100 by: {res['lv100'] or '-'}")


def serve_explorer(port):
    """Serve tools/ on localhost (the explorer page fetches the tool's
    modules and curve_data.json) until interrupted."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=os.path.dirname(G.HERE))
    with http.server.ThreadingHTTPServer(('127.0.0.1', port), handler) as httpd:
        print(f'explorer: http://127.0.0.1:{httpd.server_address[1]}/rebalance/explorer/  (Ctrl-C to stop)')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


# ---------------------------------------------------------------------------
# TMs and economy
# ---------------------------------------------------------------------------

def tm_availability(repo, stages, gd):
    m = gd['modern']
    seen = {}
    for folder, items in G.map_tms(repo).items():
        i = G.stage_of(folder, stages)
        if i is None:
            continue
        for item, source in items:
            move = 'MOVE_' + item[len('ITEM_TM_'):]
            if move not in m.moves:
                continue
            key = item
            if key not in seen or seen[key]['stage_index'] > i:
                mv = m.moves[move]
                seen[key] = {'tm': item, 'move': move, 'stage_index': i, 'stage': stages[i]['name'],
                             'map': folder, 'source': source, 'power': mv.power,
                             'type': '' if mv.effect == 'EFFECT_HIDDEN_POWER' else mv.type,
                             'category': mv.category}
    return sorted(seen.values(), key=lambda r: (r['stage_index'], -r['power'], r['tm']))


def economy(stages, trainers, gd, class_money):
    out = {'items': {}, 'stage_money': []}
    for name in ECONOMY_ITEMS:
        item = 'ITEM_' + name
        row = {}
        for regime in G.REGIMES:
            d = gd[regime]
            f = d.items.get(item, {'price': 0, 'heal': None})
            sell = f['price'] // (4 if d.flag('I_SELL_VALUE_FRACTION >= GEN_9') else 2)  # ITEM_SELL_FACTOR
            row[regime] = {'price': f['price'], 'sell': sell, 'heal': f['heal']}
        out['items'][name] = row
    total = 0
    for st in stages:
        money = 0
        for tid in st['regular'] + st['bosses']:
            t = trainers[tid]
            base = class_money.get(t.trainer_class, 0) or 5
            money += 4 * t.mons[-1].level * base * (2 if t.double else 1)
        total += money
        out['stage_money'].append({'stage': st['name'], 'trainers': len(st['regular']) + len(st['bosses']),
                                   'money': money, 'cumulative': total})
    for regime in G.REGIMES:
        d = gd[regime]
        out[f'{regime}_flags'] = {k: d.defines.get(k) for k in ('I_PRICE', 'I_HEALTH_RECOVERY',
                                                               'I_SELL_VALUE_FRACTION', 'B_WHITEOUT_MONEY')}
    return out


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def table(headers, rows):
    lines = ['| ' + ' | '.join(headers) + ' |', '|' + '---|' * len(headers)]
    lines += ['| ' + ' | '.join(str(c) for c in r) + ' |' for r in rows]
    return '\n'.join(lines)


def moves_str(moves):
    return ', '.join(short(m) for m in moves) or '-'


def mult(x, type_):
    """A multiplier; None is Fairy's missing Gen 3 value, or no attacking move."""
    if x is None:
        return 'new' if type_ not in G.GEN3_TYPES else 'none'
    return f'{x:g}x'


def share_report(share, raised_defaults, stage_trainers):
    """The Exp. Share curve section (#127)."""
    names = list(TRAINER_EXP)
    league = [k for k, r in enumerate(next(iter(share.values()))['now']['full / none']) if r['class'] in CURVE_CLASSES]

    def brackets(curves, clear, k):
        return ' / '.join(str(curves[f'{clear} / {aff}'][k]['bench']) for aff in AFFECTION)

    def now_table(clear, keep):
        rows = []
        for k in keep:
            r = share[names[0]]['now'][f'{clear} / friendship'][k]
            row = [r['stage'], short(r['boss']), r['boss_ace']]
            for n in names:
                fr = share[n]['now'][f'{clear} / friendship'][k]
                row += [fr['ace'], brackets(share[n]['now'], clear, k), fr['friendship']]
            rows.append(row)
        headers = ['stage', 'boss', 'boss ace']
        for n in names:
            headers += [f'{n} KO-taker', f'{n} bench ({" / ".join(AFFECTION)})', f'{n} bench friendship']
        return table(headers, rows)

    everyone = range(len(share[names[0]]['now']['full / none']))
    out = ['## Exp. Share curve (#127)', '',
           'The share6 party on modern data: one Pokemon takes every KO (KO-taker) and five sit on the Gen 6 '
           'Exp. Share bench, all Medium Slow from level 5, before each story boss. "1.5x off" is '
           f'B_TRAINER_EXP_MULTIPLIER {TRAINER_EXP["1.5x off"]}, "1.5x on" {TRAINER_EXP["1.5x on"]} '
           '(Cmd_getexp gives the 1.5x for GEN_7 and earlier). Each stage adds '
           f'{WALK_STEPS_PER_STAGE:,} steps of walking and {CATCHES_PER_STAGE} catches at its land-table average '
           '(B_EXP_CATCH). Affection brackets: none; friendship (1.2x once the modelled friendship reaches '
           f'{AFFECTION_FOUR_HEARTS}: {STANDARD_FRIENDSHIP} at the start, level-ups, league battles and walking); '
           'always (4 hearts from the start). Bench friendship is the friendship bracket\'s. No Lucky Egg, traded '
           'or unevolved bonuses.', '',
           '### Now: full clear', '', now_table('full', everyone), '',
           '### Now: half clear (gym leaders, Elite Four, Champion)', '', now_table('half', league), '']

    rows = []
    for st in stage_trainers:
        k = next(k for k in everyone if share[names[0]]['now']['full / none'][k]['stage'] == st['stage'])
        rows.append([st['stage'], st['trainers'], st['mean_ace'], st['max_ace']]
                    + [share[n]['now']['full / friendship'][k]['bench'] for n in names])
    out += ['### Stage trainers against the bench', '',
            'Each stage\'s regular trainers by their highest-level Pokemon, against the full-clear bench '
            '(friendship) at the stage\'s first boss.', '',
            table(['stage', 'trainers', 'trainer ace mean', 'trainer ace max'] + [f'{n} bench' for n in names],
                  rows), '']

    rows = []
    for k in everyone:
        r = share[names[0]]['now']['full / none'][k]
        rows.append([r['stage'], short(r['boss']), r['base_ace']]
                    + [f"+{share[n]['raises'][r['boss']]} -> {r['base_ace'] + share[n]['raises'][r['boss']]}"
                       for n in names])
    out += ['### Proposed boss raises', '',
            f'Target: on a full clear with modelled friendship, each story boss\'s ace is {TARGET_MARGIN} level(s) '
            'above the bench. Bosses are only raised, every Pokemon of the team by the same amount, in story order '
            'so each raise counts toward the later stages\' exp. Raises are against the current trainers.party.', '',
            table(['stage', 'boss', 'ace now'] + [f'{n}: raise -> ace' for n in names], rows), '']

    variants = share[names[0]]['variants']
    if variants:
        def spread(values):
            return ' / '.join(str(v) for v in sorted(set(values)))
        rows = [[short(bid), len(aces), spread(aces.values())]
                + [spread(f"+{share[n]['raises'][v]} -> {ace + share[n]['raises'][v]}" for v, ace in aces.items())
                   for n in names]
                for bid, aces in variants.items()]
        out += ['The model plays one rival team per fight. The same fight\'s other rival and starter teams get '
                'the raise that lifts their ace to the staged team\'s raised ace:', '',
                table(['staged boss', 'other teams', 'ace now'] + [f'{n}: raise -> ace' for n in names], rows), '']

    for n in names:
        after = share[n]['after']
        rows, at_target, half_ok = [], 0, 0
        for k in everyone:
            fr, half = after['full / friendship'][k], after['half / friendship'][k]
            at_target += fr['boss_ace'] - fr['bench'] <= TARGET_MARGIN
            half_ok += k in league and half['boss_ace'] - half['bench'] <= HALF_CLEAR_GAP
            rows.append([fr['stage'], short(fr['boss']), fr['boss_ace'], fr['ace'], brackets(after, 'full', k),
                         fr['bench'] - fr['boss_ace'], brackets(after, 'half', k), half['bench'] - half['boss_ace']])
        out += [f'### After the {n} raises', '',
                f'Full clear: {at_target} of {len(rows)} bosses have the bench (friendship) within {TARGET_MARGIN} of '
                f'their ace; the others\' aces are already higher and aren\'t lowered. Half clear: {half_ok} of {len(league)} '
                f'gym leaders, Elite Four and Champion have the bench (friendship) within {HALF_CLEAR_GAP}.', '',
                table(['stage', 'boss', 'ace', 'KO-taker', f'full bench ({" / ".join(AFFECTION)})',
                       'full bench - ace', f'half bench ({" / ".join(AFFECTION)})', 'half bench - ace'], rows), '']

    rows = [[n, label] + [curve[k]['bench'] for k in league]
            for n in names for label, curve in share[n]['sensitivity'].items()]
    out += ['### Sensitivity (now, full clear, friendship bracket)', '',
            table(['setting', 'variant'] + [short(share[names[0]]['now']['full / none'][k]['boss']) for k in league],
                  rows), '']

    for n in names:
        rows = raised_defaults[n]
        changed = [r for r in rows if r['now'] != r['raised']]
        out += [f'### Default movesets of the raised boss Pokemon ({n})', '',
                f'{len(rows)} raised boss Pokemon are on default moves; {len(changed)} get a different moveset or '
                'flags at the raised level (the flags as in "Default movesets" below).', '']
        if changed:
            out += [table(['boss', 'species', 'lv', 'modern default now', 'raised', 'flags now -> raised'],
                          [[short(r['trainer']), short(r['species']), ' -> '.join(map(str, r['levels'])),
                            moves_str(r['now']['moves']), moves_str(r['raised']['moves']),
                            f"{' '.join(r['now']['flags']) or '-'} -> {' '.join(r['raised']['flags']) or '-'}"]
                           for r in changed]), '']
    return out


def write_report(path, res):
    c, d, h, curve = res['census'], res['defaults'], res['handwritten'], res['level_curve']
    out = ['# Rebalance measurements (#113)', '',
           'Generated by `tools/rebalance/rebalance.py`. "Vanilla" is this repo\'s data with the data and '
           'formula configs set to GEN_3; "modern" is the build as configured.', '']
    out += ['## Census', '',
            table(['measure', 'count'], [
                ['trainers in trainers.party', c['trainers']],
                ['trainer Pokemon', c['mons']],
                ['  with hand-written moves', c['mons_with_moves']],
                ['  on default (level-up) moves', c['mons_default']],
                ['trainers with Check Bad Move', c['trainers_check_bad_move']],
                ['trainers with Basic Trainer', c['trainers_basic_trainer']],
                ['trainers with no AI line', c['trainers_no_ai']],
                ['story trainers (stage maps + bosses)', res['story_trainers']],
            ]), '', 'AI flag sets (top 12):', '',
            table(['AI', 'trainers'], list(c['ai_sets'].items())), '', 'Story bosses by AI:', '',
            table(['AI', 'bosses'], [[ai, ', '.join(short(b) for b, a in res['boss_ai'].items() if a == ai)]
                                     for ai in dict.fromkeys(res['boss_ai'].values())]), '']

    out += ['## Level curve', '',
            'Party level just before each boss. Every party member is Medium Slow (the starters) and starts '
            f'at level {START_LEVEL}. solo: one Pokemon takes every KO. rotate4: four Pokemon take turns '
            '(mean level). share6: one Pokemon takes every KO and five sit on the bench with the Gen 6 '
            'Exp. Share (ace, then bench mean). No Lucky Egg, affection, traded or unevolved bonuses.', '']
    headers = ['stage', 'boss', 'boss ace', 'boss mean', 'vanilla solo', 'vanilla rotate4',
               'modern solo', 'modern rotate4', 'modern share6 ace', 'share6 bench']
    for i, (scenario, rows) in enumerate(curve.items()):
        if i:
            rows = [r for r in rows if r['class'] in CURVE_CLASSES]
        out += [f'### {scenario}' + ('' if not i else ' (gym leaders, Elite Four, Champion)'), '',
                table(headers, [[r['stage'], short(r['boss']), r['boss_ace'], r['boss_mean'], r['vanilla_solo'],
                                 r['vanilla_rotate4'], r['modern_solo'], r['modern_rotate4'], r['modern_share6'],
                                 r['modern_share6_bench']] for r in rows]), '']
    out += share_report(res['share_curve'], res['raised_defaults'], res['stage_trainers'])

    out += ['## Default movesets (Gen 3 vs Gen 9 learnsets)', '',
            table(['measure', 'value'], [
                ['trainer Pokemon on default moves', d['default_mons']],
                ['  of them on story trainers', d['story_default_mons']],
                ['identical moveset (same order)', d['identical']],
                ['same four moves in any order', d['same_moves_any_order']],
                ['moves shared with vanilla (0-4): count', d['shared_moves_histogram']],
                ['mean attacking moves vanilla -> modern',
                 f"{d['mean_attacks']['vanilla']} -> {d['mean_attacks']['modern']}"],
                ['mean best attack power vanilla -> modern',
                 f"{d['mean_best_power']['vanilla']} -> {d['mean_best_power']['modern']}"],
                ['best attack power up / down', f"{d['best_power_up']} / {d['best_power_down']}"],
            ]), '', 'Flags (all default Pokemon / story trainers only):', '',
            table(['flag', 'all', 'story'],
                  [[f, d['flags_all'].get(f, 0), d['flags_story'].get(f, 0)]
                   for f in FLAGS]), '']
    for f, rows in d['story_examples'].items():
        if not rows:
            continue
        out += [f'### {f} (story examples)', '',
                table(['species', 'lv', 'trainer', 'stage', 'vanilla', 'modern', 'strong moves flagged'],
                      [[short(r['species']), r['level'], short(r['trainer']), r['stage'],
                        moves_str(r['vanilla']), moves_str(r['modern']), moves_str(r['above_band_moves'])]
                       for r in rows]), '']
    out += ['### Most-flagged species (all default Pokemon)', '',
            table(['flag', 'species (count)'],
                  [[f, ', '.join(f'{short(s)} ({n})' for s, n in top)] for f, top in d['top_species'].items()]), '']

    out += ['## Hand-written movesets', '',
            table(['measure', 'value'], [
                ['trainer Pokemon with set moves', h['mons_with_set_moves']],
                ['attacking set moves whose data changed', h['moves_changed']],
                ['  category flips (physical <-> special)', h['category_flips']],
                ['  of them now on a weaker / similar / stronger stat',
                 f"{h['flip_shift'].get('weaker', 0)} / {h['flip_shift'].get('similar', 0)} / {h['flip_shift'].get('stronger', 0)}"],
                ['  Pokemon with at least one flip', h['mons_with_category_flip']],
                ['  Pokemon with a flip onto a weaker stat', h['mons_with_flip_weaker']],
                ['  type changes', h['type_changes']],
                ['  power changes', h['power_changes']],
                ['  accuracy changes', h['accuracy_changes']],
            ]), '', 'Changed attacking moves (set-move slots; weaker/similar/stronger: the category flipped onto that stat; data: only power, accuracy or type changed):', '',
            table(['move', 'slots'], [[short(mv), ', '.join(f'{k} {v}' for k, v in cnt.items())]
                                      for mv, cnt in h['per_move'].items()]), '']
    boss_flips = [x for x in res['handwritten_rows'] if x['boss'] and 'stat' in x]
    out += ['### Category flips on boss teams', '',
            table(['boss', 'species', 'lv', 'move', 'category', 'stat used', 'shift'],
                  [[short(x['trainer']), short(x['species']), x['level'], short(x['move']),
                    ' -> '.join(short(cat).replace('Category ', '') for cat in x['category']),
                    ' -> '.join(map(str, x['stat'])), x['stat_shift']] for x in boss_flips]), '']

    out += ['## Physical/special split: who fits their STAB now', '',
            'Better stat: Attack or Sp. Atk when one beats the other by 15%. Gen 3 STAB: the category each '
            'Gen 3 type forced. Modern STAB moves: distinct level-up STAB attacking moves by category.', '',
            table(['species', 'Atk / SpA', 'better', 'Gen 3 STAB', 'modern types', 'modern STAB moves phys / spec'],
                  [[short(r['species']), f"{r['atk']} / {r['spa']}", r['better'],
                    ', '.join(f'{short(t)} {c}' for t, c in r['vanilla_stab'].items()),
                    fmt_types(r['modern_types']), f"{r['modern_stab_physical']} / {r['modern_stab_special']}"]
                   for r in res['split_fit']]), '']

    out += ['## Boss type matchups', '',
            'Per boss Pokemon: retyping, defensive multipliers that changed (attacking type: vanilla -> modern), '
            'and the best multiplier its moves reach against single defending types where that changed. '
            'Fairy has no vanilla value ("new"); "none" means no attacking move.', '']
    for bid, rows in res['matchups'].items():
        lines = []
        for r in rows:
            parts = []
            if r['types'][0] != r['types'][1]:
                parts.append(f"retyped {fmt_types(r['types'][0])} -> {fmt_types(r['types'][1])}")
            for word, changes in (('takes', r['defense']), ('hits', r['offense'])):
                if changes:
                    parts.append(word + ' ' + ', '.join(f'{short(t)} {mult(a, t)}->{mult(b, t)}' for t, (a, b) in changes.items()))
            if parts:
                moves = '' if r['set_moves'] else ' (default moves)'
                lines.append(f"- {short(r['species'])} {r['level']}{moves}: " + '; '.join(parts))
        out += [f'### {short(bid)}', ''] + (lines or ['- no change']) + ['']

    out += ['## TMs by story stage', '',
            'First stage where each TM is on a stage map (ball, hidden item, mart list, script, or reward: a Trick House '
            'puzzle prize, filed under that puzzle). Hidden Power\'s type comes from the IVs. '
            'Reusable TMs mean one copy covers the whole party.', '',
            table(['stage', 'TM', 'type', 'power', 'category', 'map', 'source'],
                  [[r['stage'], short(r['move']), short(r['type']) or 'varies', {0: '-', 1: 'varies'}.get(r['power'], r['power']),
                    short(r['category']).replace('Category ', ''), r['map'], r['source']] for r in res['tms']]), '']

    out += ['## Wild Pokemon by story stage', '',
            'Species on the stage maps so far (every table), vanilla tables vs the restocked ones; the strongest '
            'restock additions of this stage by base stat total (lowest slot level); Fairy types first met here.', '',
            table(['stage', 'species so far vanilla / modern', 'new this stage', 'strongest new (BST, lv)', 'Fairy first met'],
                  [[r['stage'], f"{r['vanilla_species']} / {r['modern_species']}", r['new_species'],
                    ', '.join(f'{short(sp)} ({b}, {lv})' for sp, b, lv in r['strongest_new']) or '-',
                    ', '.join(short(sp) for sp in r['fairy_first']) or '-'] for r in res['wild']]), '']

    e = res['economy']
    out += ['## Economy', '',
            f"Configs: vanilla {e['vanilla_flags']}, modern {e['modern_flags']}.", '',
            table(['item', 'vanilla price', 'modern price', 'vanilla sell', 'modern sell', 'vanilla heal', 'modern heal',
                   'vanilla HP per 100', 'modern HP per 100'],
                  [[short('ITEM_' + n), r['vanilla']['price'], r['modern']['price'], r['vanilla']['sell'], r['modern']['sell'],
                    r['vanilla']['heal'] or '-', r['modern']['heal'] or '-',
                    round(100 * r['vanilla']['heal'] / r['vanilla']['price'], 1) if r['vanilla']['heal'] else '-',
                    round(100 * r['modern']['heal'] / r['modern']['price'], 1) if r['modern']['heal'] else '-']
                   for n, r in e['items'].items()]), '',
            'Prize money from a full clear of each stage (same in both: 4 x last Pokemon\'s level x class money, x2 in doubles):', '',
            table(['stage', 'trainers', 'money', 'cumulative'],
                  [[r['stage'], r['trainers'], r['money'], r['cumulative']] for r in e['stage_money']]), '']
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))


def write_csv(path, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['trainer', 'slot', 'class', 'species', 'level', 'set_moves', 'story_stage',
                    'vanilla_default', 'modern_default', 'flags', 'above_band_moves'])
        for r in rows:
            w.writerow([r['trainer'], r['slot'], r['class'], r['species'], r['level'], int(r['set_moves']),
                        r['story_stage'], ' '.join(r['vanilla_default']), ' '.join(r['modern_default']),
                        ' '.join(r['flags']), ' '.join(r['above_band_moves'])])


def load_wilds(repo, stages):
    """Per regime, each stage's wild slots. Vanilla meets the pre-restock
    tables (#28), modern the committed ones."""
    folders = G.map_folders(repo)
    wilds = {}
    for regime, path in (('vanilla', os.path.join(repo, VANILLA_WILD)),
                         ('modern', os.path.join(repo, 'src', 'data', 'wild_encounters.json'))):
        with open(path, encoding='utf-8') as f:
            wilds[regime] = stage_slots(json.load(f), stages, folders)
    return wilds


def analyze(repo, stages_path):
    gd = G.load(repo)
    trainers = G.parse_trainers(os.path.join(repo, 'src', 'data', 'trainers.party'))
    stages = load_stages(stages_path, trainers, repo)
    story = {tid: st['name'] for st in stages for tid in st['regular'] + st['bosses']}
    boss_ids = [b for st in stages for b in st['bosses']]
    scaling = G.parse_scaling_factors(repo)
    wilds = load_wilds(repo, stages)
    rows = default_movesets(trainers, gd, story)
    changes = handwritten_changes(trainers, gd, set(boss_ids))
    share = share_curves(stages, trainers, gd['modern'], scaling, wilds['modern'])
    return {
        'census': census(trainers),
        'story_trainers': len(story),
        'boss_ai': {b: ' / '.join(trainers[b].ai) or '(none)' for b in boss_ids},
        'defaults': summarize_defaults(rows, gd),
        'default_rows': rows,
        'handwritten': summarize_handwritten(changes, trainers),
        'handwritten_rows': changes,
        'matchups': boss_matchups(trainers, gd, boss_ids),
        'split_fit': split_fit(gd, SPLIT_WATCH),
        'level_curve': {name: level_curve(stages, trainers, gd, scaling, wilds, clear, wild)
                        for name, (clear, wild) in SCENARIOS.items()},
        'share_curve': share,
        'stage_trainers': stage_trainer_levels(stages, trainers),
        'raised_defaults': {name: raised_defaults(trainers, gd, sc['raises']) for name, sc in share.items()},
        'tms': tm_availability(repo, stages, gd),
        'wild': wild_availability(wilds, stages, gd),
        'economy': economy(stages, trainers, gd, G.parse_class_money(repo)),
        'curve_data': curve_snapshot(stages, trainers, gd['modern'], scaling, wilds, G.R.SpeciesInfo(repo)),
    }


def curve_main(argv):
    """``curve``: explore_run on curve_data.json for knob settings (JSON, as
    the explorer's settings box gives them), printed as tables."""
    p = argparse.ArgumentParser(prog='rebalance.py curve', description=curve_main.__doc__.split('\n')[0])
    p.add_argument('knobs', nargs='?', default='{}', help='knob settings as JSON, or a JSON file')
    p.add_argument('--data', default=os.path.join(DEFAULT_OUT_DIR, CURVE_DATA))
    args = p.parse_args(argv)
    knobs = args.knobs
    if os.path.isfile(knobs):
        with open(knobs, encoding='utf-8') as f:
            knobs = f.read()
    with open(args.data, encoding='utf-8') as f:
        snap = load_snapshot(json.load(f))
    print_curve(explore_run(snap, json.loads(knobs)))
    return 0


def explore_main(argv):
    """``explore``: serve the curve explorer (#151) on localhost."""
    p = argparse.ArgumentParser(prog='rebalance.py explore', description=explore_main.__doc__.split('\n')[0])
    p.add_argument('--port', type=int, default=8151)
    return serve_explorer(p.parse_args(argv).port)


SUBCOMMANDS = {'curve': curve_main, 'explore': explore_main}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] and argv[0] in SUBCOMMANDS:
        return SUBCOMMANDS[argv[0]](argv[1:])
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0],
                                epilog='Also: rebalance.py curve [KNOBS] and rebalance.py explore (the curve '
                                       'explorer, #151); each takes --help.')
    p.add_argument('--repo', default=G.REPO, help='repo root (default: this checkout)')
    p.add_argument('--stages', default=DEFAULT_STAGES, help='story stage file (default: story_stages.json)')
    p.add_argument('--out-dir', default=DEFAULT_OUT_DIR)
    args = p.parse_args(argv)
    res = analyze(args.repo, args.stages)
    os.makedirs(args.out_dir, exist_ok=True)
    write_report(os.path.join(args.out_dir, 'report.md'), res)
    write_csv(os.path.join(args.out_dir, 'trainer_mons.csv'), res['default_rows'])
    summary = {k: v for k, v in res.items() if k not in ('default_rows', 'handwritten_rows', 'curve_data')}
    with open(os.path.join(args.out_dir, 'summary.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write('\n')
    with open(os.path.join(args.out_dir, CURVE_DATA), 'w', encoding='utf-8') as f:
        json.dump(res['curve_data'], f, sort_keys=True, separators=(',', ':'))
        f.write('\n')
    print(f"wrote {args.out_dir}: {res['census']['mons']} trainer Pokemon, "
          f"{res['defaults']['default_mons']} on default moves, {len(res['matchups'])} bosses")
    return 0


if __name__ == '__main__':
    sys.exit(main())
