"""Tests for tools/rebalance. Run from the repo root:

    python3 -m unittest discover -s tools/rebalance
"""

import contextlib
import copy
import fnmatch
import io
import json
import os
import re
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gamedata as G  # noqa: E402
import rebalance as RB  # noqa: E402

FIXTURE = os.path.join(G.HERE, 'testdata', 'repo')
FIXTURE_STAGES = os.path.join(G.HERE, 'testdata', 'stages.json')


def fake_regime(**overrides):
    """An object with GameData.flag for the given config values."""
    defines = G.R.parse_defines(FIXTURE)
    defines.update(overrides)
    return types.SimpleNamespace(flag=lambda expr: G.R.c_eval(expr, defines))


curve_inputs = RB.repo_inputs


class Expressions(unittest.TestCase):
    def setUp(self):
        self.d = G.regime_defines(FIXTURE)

    def test_ternary_picks_the_branch_per_regime(self):
        expr = '(P_UPDATED_EXP_YIELDS >= GEN_5) ? 133 : 98'
        self.assertEqual(G.c_value(expr, self.d['modern']), 133)
        self.assertEqual(G.c_value(expr, self.d['vanilla']), 98)

    def test_constant_branch_and_nested_ternary(self):
        self.assertEqual(G.c_value('B_UPDATED_MOVE_TYPES >= GEN_6 ? TYPE_FAIRY : TYPE_NORMAL', self.d['vanilla']),
                         'TYPE_NORMAL')
        self.assertEqual(G.c_value('GEN_3 ? (GEN_1 ? 1 : 2) : 3', self.d['modern']), 2)

    def test_arithmetic_with_a_macro_holding_a_ternary(self):
        d = dict(self.d['modern'], TREASURE_FACTOR='((I_SELL_VALUE_FRACTION >= GEN_9) ? 2 : 1)')
        self.assertEqual(G.c_value('10000 * TREASURE_FACTOR', d), 20000)

    def test_ternary_inside_arithmetic(self):
        self.assertEqual(G.c_value('2 * (B_UPDATED_MOVE_DATA >= GEN_6 ? 60 : 50)', self.d['modern']), 120)
        self.assertEqual(G.c_value('2 * (B_UPDATED_MOVE_DATA >= GEN_6 ? 60 : 50)', self.d['vanilla']), 100)

    def test_table_fields_inside_if_branches_and_nested_structs(self):
        text = ('const struct MoveInfo gMovesInfo[] =\n{\n'
                '    [MOVE_CRABHAMMER] =\n    {\n'
                '        .description = COMPOUND_STRING("{BRACE} text"),\n'
                '    #if B_UPDATED_MOVE_DATA >= GEN_5\n'
                '            .accuracy = 90,\n'
                '    #else\n'
                '            .accuracy = 85,\n'
                '    #endif\n'
                '        .additionalEffects = ADDITIONAL_EFFECTS({\n'
                '            .power = 1,\n'
                '        }),\n'
                '        .power = 100,\n'
                '    },\n'
                '    [MOVE_POUND] = { },\n'
                '        .power = 7,\n'
                '};\n')
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'moves_info.h')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(text)
            for regime, accuracy in (('modern', 90), ('vanilla', 85)):
                table = G.parse_table(path, self.d[regime], 'MOVE', ('accuracy', 'power'))
                self.assertEqual(table['MOVE_CRABHAMMER'], {'accuracy': accuracy, 'power': 100})
                self.assertEqual(table['MOVE_POUND'], {})

    def test_field_value_stops_at_the_top_level_comma(self):
        self.assertEqual(G.field_value('MON_TYPES(TYPE_A, TYPE_B), // x'), 'MON_TYPES(TYPE_A, TYPE_B)')


class Names(unittest.TestCase):
    def test_species_names_follow_trainerproc(self):
        self.assertEqual(G.species_constant('Mr. Mime'), 'SPECIES_MR_MIME')
        self.assertEqual(G.species_constant('Farfetch’d'), 'SPECIES_FARFETCHD')
        self.assertEqual(G.species_constant('Nidoran♀'), 'SPECIES_NIDORAN_F')
        self.assertEqual(G.species_constant('SPECIES_ABRA'), 'SPECIES_ABRA')

    def test_move_names_follow_trainerproc(self):
        self.assertEqual(G.constant('MOVE', 'Will-O-Wisp'), 'MOVE_WILL_O_WISP')
        self.assertEqual(G.constant('MOVE', "King's Shield"), 'MOVE_KINGS_SHIELD')
        self.assertEqual(G.constant('TRAINER_CLASS', 'Pkmn Trainer 1'), 'TRAINER_CLASS_PKMN_TRAINER_1')


class DefaultMoveset(unittest.TestCase):
    def test_last_four_distinct_moves(self):
        learnset = [(1, 'A'), (1, 'B'), (3, 'A'), (5, 'C'), (7, 'D'), (9, 'E'), (11, 'F')]
        self.assertEqual(G.default_moveset(learnset, 9), ['B', 'C', 'D', 'E'])
        self.assertEqual(G.default_moveset(learnset, 2), ['A', 'B'])

    def test_level_zero_evolution_moves_are_skipped(self):
        self.assertEqual(G.default_moveset([(0, 'EVO'), (1, 'A')], 50), ['A'])


class GameDataFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gd = G.load(FIXTURE)

    def test_types_through_family_macros(self):
        v, m = self.gd['vanilla'], self.gd['modern']
        self.assertEqual(v.species['SPECIES_RALTS'].types, ('TYPE_PSYCHIC',))
        self.assertEqual(m.species['SPECIES_RALTS'].types, ('TYPE_PSYCHIC', 'TYPE_FAIRY'))
        self.assertEqual(m.species['SPECIES_MAGIKARP_NORMAL'].types, ('TYPE_WATER',))  # { A, A } macro

    def test_aliases_resolve(self):
        self.assertIs(self.gd['modern'].species['SPECIES_MAGIKARP'], self.gd['modern'].species['SPECIES_MAGIKARP_NORMAL'])

    def test_exp_yield_under_if_blocks(self):
        self.assertEqual(self.gd['vanilla'].species['SPECIES_SABLEYE'].exp_yield, 98)
        self.assertEqual(self.gd['modern'].species['SPECIES_SABLEYE'].exp_yield, 133)

    def test_learnset_file_follows_the_config(self):
        self.assertEqual(self.gd['vanilla'].default_moves('SPECIES_RALTS', 7), ['MOVE_GROWL', 'MOVE_CONFUSION'])
        self.assertEqual(self.gd['modern'].default_moves('SPECIES_RALTS', 7), ['MOVE_GROWL', 'MOVE_TELEPORT'])

    def test_gen3_category_comes_from_the_type(self):
        v, m = self.gd['vanilla'], self.gd['modern']
        self.assertEqual(v.moves['MOVE_SHADOW_BALL'].category, 'DAMAGE_CATEGORY_PHYSICAL')
        self.assertEqual(m.moves['MOVE_SHADOW_BALL'].category, 'DAMAGE_CATEGORY_SPECIAL')
        self.assertEqual(v.moves['MOVE_FEINT_ATTACK'].category, 'DAMAGE_CATEGORY_SPECIAL')
        self.assertEqual(v.moves['MOVE_GROWL'].category, 'DAMAGE_CATEGORY_STATUS')

    def test_move_data_ternaries_and_if_blocks(self):
        self.assertEqual((self.gd['vanilla'].moves['MOVE_TACKLE'].power, self.gd['vanilla'].moves['MOVE_TACKLE'].accuracy), (35, 95))
        self.assertEqual((self.gd['modern'].moves['MOVE_TACKLE'].power, self.gd['modern'].moves['MOVE_TACKLE'].accuracy), (40, 100))
        self.assertEqual(self.gd['modern'].moves['MOVE_CHARM'].type, 'TYPE_FAIRY')

    def test_type_chart_steel_change(self):
        self.assertEqual(self.gd['vanilla'].chart['TYPE_GHOST']['TYPE_STEEL'], 0.5)
        self.assertEqual(self.gd['modern'].chart['TYPE_GHOST']['TYPE_STEEL'], 1.0)
        self.assertEqual(G.effectiveness(self.gd['modern'].chart, 'TYPE_FAIRY', ('TYPE_DARK', 'TYPE_GHOST')), 2.0)

    def test_items(self):
        v, m = self.gd['vanilla'].items, self.gd['modern'].items
        self.assertEqual((v['ITEM_HYPER_POTION']['price'], v['ITEM_HYPER_POTION']['heal']), (1200, 200))
        self.assertEqual((m['ITEM_HYPER_POTION']['price'], m['ITEM_HYPER_POTION']['heal']), (1500, 120))
        self.assertIsNone(m['ITEM_MAX_POTION']['heal'])
        self.assertEqual((v['ITEM_NUGGET']['price'], m['ITEM_NUGGET']['price']), (10000, 20000))


class Trainers(unittest.TestCase):
    def test_parse(self):
        tr = G.parse_trainers(os.path.join(FIXTURE, 'src', 'data', 'trainers.party'))
        self.assertEqual(list(tr), ['TRAINER_HIKER_A', 'TRAINER_RIVAL_A', 'TRAINER_SWIMMER_B', 'TRAINER_LEADER_X'])
        x = tr['TRAINER_LEADER_X']
        self.assertEqual([m.species for m in x.mons], ['SPECIES_SABLEYE', 'SPECIES_MR_MIME'])
        self.assertEqual(x.mons[0].moves, ['MOVE_SHADOW_BALL', 'MOVE_FEINT_ATTACK'])
        self.assertEqual(x.mons[0].item, 'ITEM_ORAN_BERRY')
        self.assertEqual(x.ai, ['Basic Trainer'])
        self.assertTrue(tr['TRAINER_SWIMMER_B'].double)

    def test_empty_header_field_keeps_the_next_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'trainers.party')
            with open(path, 'w', encoding='utf-8') as f:
                f.write('=== TRAINER_NONE ===\nName:\nClass: Hiker\nDouble Battle: Yes\n\nGeodude\nLevel: 5\n')
            t = G.parse_trainers(path)['TRAINER_NONE']
        self.assertEqual((t.name, t.trainer_class, t.double), ('', 'TRAINER_CLASS_HIKER', True))

    def test_frlg_maps_are_never_in_a_stage(self):
        stages = [{'maps': ['VictoryRoad_*']}]
        self.assertEqual(G.stage_of('VictoryRoad_1F', stages), 0)
        self.assertIsNone(G.stage_of('VictoryRoad_1F_Frlg', stages))

    def test_maps_skip_rematches(self):
        self.assertEqual(G.map_trainers(FIXTURE), {'TRAINER_HIKER_A': 'RouteA', 'TRAINER_RIVAL_A': 'RouteA',
                                                   'TRAINER_LEADER_X': 'TownA_Gym'})

    def test_tm_sources(self):
        self.assertEqual(sorted(G.map_tms(FIXTURE)['RouteA']),
                         [('ITEM_TM_SHADOW_BALL', 'ball'), ('ITEM_TM_SHADOW_CLAW', 'hidden')])
        self.assertEqual(sorted(G.map_tms(FIXTURE)['TownA_Gym']),
                         [('ITEM_TM_CHARM', 'mart'), ('ITEM_TM_SHADOW_BALL', 'script')])


class Exp(unittest.TestCase):
    """Cmd_getexp, checked against the expected values in test/battle/exp.c."""

    @classmethod
    def setUpClass(cls):
        cls.scaling = G.parse_scaling_factors(FIXTURE)

    def test_gen6_exp_share_bench_gets_half(self):
        # "Gen 6 Exp. Share gives the rest of the team half experience":
        # B_SPLIT_EXP GEN_6, B_SCALED_EXP GEN_3, gain = yield * level / 7.
        d = fake_regime(B_SCALED_EXP='GEN_3', B_SPLIT_EXP='GEN_6')
        gain = 39 * 10 // 7
        self.assertEqual(RB.exp_award(d, self.scaling, 39, 10, 20, False, 1), gain)
        self.assertEqual(RB.exp_award(d, self.scaling, 39, 10, 20, False, 1, holders=6), gain)
        self.assertEqual(RB.exp_award(d, self.scaling, 39, 10, 25, False, 1, sent_out=False, holders=6), gain // 2)
        self.assertEqual(RB.exp_award(d, self.scaling, 39, 10, 25, False, 1, sent_out=False), 0)

    def test_gen3_split_with_exp_share(self):
        # Cmd_getexp before Gen 6: half over the sent-in members, half over
        # every holder, and a sent-in holder gets both.
        d = fake_regime(B_SCALED_EXP='GEN_3', B_SPLIT_EXP='GEN_3')
        calc = 98 * 20 // 7
        self.assertEqual(RB.exp_award(d, self.scaling, 98, 20, 20, False, 1, holders=6), calc // 2 + calc // 2 // 6)
        self.assertEqual(RB.exp_award(d, self.scaling, 98, 20, 20, False, 1, sent_out=False, holders=6), calc // 2 // 6)

    def test_gen3_trainer_bonus_and_split(self):
        d = fake_regime(B_SCALED_EXP='GEN_3', B_SPLIT_EXP='GEN_3', B_TRAINER_EXP_MULTIPLIER='GEN_3')
        calc = 98 * 20 // 7 * 150 // 100
        self.assertEqual(RB.exp_award(d, self.scaling, 98, 20, 20, True, 1), calc)
        self.assertEqual(RB.exp_award(d, self.scaling, 98, 20, 20, True, 2), calc // 2)

    def test_scaled_exp(self):
        d = fake_regime()
        # Same level: the scaling factors cancel, leaving yield * level / 5 + 1.
        self.assertEqual(RB.exp_award(d, self.scaling, 39, 5, 5, False, 1), 39 + 1)
        # "Exp is scaled to player and opponent's levels": a higher getter gets less.
        self.assertGreater(RB.exp_award(d, self.scaling, 39, 5, 5, False, 1),
                           RB.exp_award(d, self.scaling, 39, 5, 10, False, 1))

    def test_affection_boost_before_scaling(self):
        # ApplyExperienceMultipliers: 4+ hearts give 4915/4096, before the level scaling.
        d = fake_regime(B_SCALED_EXP='GEN_3', B_SPLIT_EXP='GEN_6', B_AFFECTION_MECHANICS='TRUE')
        gain = 39 * 10 // 7
        self.assertEqual(RB.exp_award(d, self.scaling, 39, 10, 20, False, 1, affection=True), gain * 4915 // 4096)
        self.assertEqual(RB.exp_award(d, self.scaling, 39, 10, 25, False, 1, sent_out=False, holders=6,
                                      affection=True), gain // 2 * 4915 // 4096)
        off = fake_regime(B_SCALED_EXP='GEN_3', B_SPLIT_EXP='GEN_6', B_AFFECTION_MECHANICS='FALSE')
        self.assertEqual(RB.exp_award(off, self.scaling, 39, 10, 20, False, 1, affection=True), gain)
        scaled = fake_regime(B_AFFECTION_MECHANICS='TRUE')
        self.assertEqual(RB.exp_award(scaled, self.scaling, 39, 5, 5, False, 1, affection=True),
                         39 * 4915 // 4096 + 1)

    def test_unevolved_boost_before_affection(self):
        # ApplyExperienceMultipliers: the unevolved 4915/4096, then affection's, each rounded down.
        d = fake_regime(B_SCALED_EXP='GEN_3', B_SPLIT_EXP='GEN_6', B_AFFECTION_MECHANICS='TRUE')
        gain = 39 * 10 // 7
        self.assertEqual(RB.exp_award(d, self.scaling, 39, 10, 20, False, 1, unevolved=True), gain * 4915 // 4096)
        self.assertEqual(RB.exp_award(d, self.scaling, 39, 10, 20, False, 1, affection=True, unevolved=True),
                         gain * 4915 // 4096 * 4915 // 4096)
        off = fake_regime(B_SCALED_EXP='GEN_3', B_SPLIT_EXP='GEN_6', B_UNEVOLVED_EXP_MULTIPLIER='GEN_5')
        self.assertEqual(RB.exp_award(off, self.scaling, 39, 10, 20, False, 1, unevolved=True), gain)

    def test_share_fraction(self):
        # #151's bench share: the game's half takes the integer path, others
        # round down (at least 1), 0 gives the bench nothing; the KO-taker's
        # exp doesn't change.
        d = fake_regime(B_SCALED_EXP='GEN_3', B_SPLIT_EXP='GEN_6')
        calc = 98 * 20 // 7

        def bench(**kw):
            return RB.exp_award(d, self.scaling, 98, 20, 25, False, 1, sent_out=False, holders=6, **kw)
        self.assertEqual(bench(share_fraction=0.5), bench())
        self.assertEqual(bench(), calc // 2)
        self.assertEqual(bench(share_fraction=0.25), int(calc * 0.25))
        self.assertEqual(bench(share_fraction=0), 0)
        # 180 * 0.35 is 62.99999... in floats: the share is exact, 63.
        self.assertEqual(RB.exp_award(d, self.scaling, 90, 14, 25, False, 1, sent_out=False, holders=6,
                                      share_fraction=0.35), 63)
        self.assertEqual(RB.exp_award(d, self.scaling, 1, 2, 25, False, 1, sent_out=False, holders=6,
                                      share_fraction=0.1), 1)
        self.assertEqual(RB.exp_award(d, self.scaling, 98, 20, 25, False, 1, holders=6, share_fraction=0), calc)

    def test_overlevel(self):
        d = fake_regime()

        def award(getter, foe=20, **kw):
            return RB.exp_award(d, self.scaling, 98, foe, getter, False, 1, **kw)
        hard = RB.Overlevel(5)
        self.assertEqual(award(25, overlevel=hard), award(25))
        self.assertEqual(award(26, overlevel=hard), 1)
        # A getter that gets nothing still gets nothing.
        self.assertEqual(award(30, sent_out=False, overlevel=hard), 0)
        # Percent of the foe's level: 25% above a level-20 foe is level 25.
        rel = RB.Overlevel(25, relative=True)
        self.assertEqual(award(25, overlevel=rel), award(25))
        self.assertEqual(award(26, overlevel=rel), 1)
        self.assertEqual(award(50, foe=40, overlevel=rel), award(50, foe=40))
        # The falloff halves the exp every halflife levels past the cutoff, down to 1.
        soft = RB.Overlevel(5, halflife=2)
        self.assertEqual(award(25, overlevel=soft), award(25))
        self.assertEqual(award(27, overlevel=soft), award(27) * 2048 // 4096)
        self.assertEqual(award(29, overlevel=soft), award(29) * 1024 // 4096)
        self.assertEqual(award(26, overlevel=soft), award(26) * 2896 // 4096)  # 4096 / sqrt(2)
        self.assertEqual(award(100, overlevel=soft), 1)
        # In percent: 10% of the foe's level per halving, past 25% above it.
        soft_rel = RB.Overlevel(25, relative=True, halflife=10)
        self.assertEqual(award(27, overlevel=soft_rel), award(27) * 2048 // 4096)
        self.assertEqual(soft_rel.apply(1000, 40, 54), 500)
        # The same cases as test/battle/exp.c's: deep halvings keep their 16ths, no exp stays none.
        game = RB.Overlevel(10, True, 5)
        self.assertEqual(game.apply(1000, 40, 55), 1000 * 2896 >> 17)  # 5.5 halvings
        self.assertEqual(game.apply(1000, 20, 60), 1)
        self.assertEqual(game.apply(0, 20, 60), 0)
        self.assertEqual(RB.Overlevel(10, True).apply(1000, 20, 23), 1)

    def test_scaling_factors(self):
        # The fixture copies the game's table, which is (i^2.5)/4.
        self.assertEqual(RB.scaling_factors(2.5, len(self.scaling)), self.scaling)
        d = fake_regime()
        steep = RB.scaling_factors(3.5)
        # The factors cancel at an equal level, at any power.
        self.assertEqual(RB.exp_award(d, steep, 98, 20, 20, False, 1),
                         RB.exp_award(d, self.scaling, 98, 20, 20, False, 1))
        # A steeper curve pays an over-levelled getter less and an under-levelled one more.
        self.assertLess(RB.exp_award(d, steep, 98, 20, 30, False, 1), RB.exp_award(d, self.scaling, 98, 20, 30, False, 1))
        self.assertGreater(RB.exp_award(d, steep, 98, 20, 10, False, 1),
                           RB.exp_award(d, self.scaling, 98, 20, 10, False, 1))

    def test_ko_rotation(self):
        # Unscaled exp, so who takes the KO doesn't change what a KO gives:
        # rotating over all six spreads the same total evenly.
        d = fake_regime(B_SCALED_EXP='GEN_3')
        one, six = RB.Party(6), RB.Party(6, ko_takers=6)
        for p in (one, six):
            for _ in range(12):
                p.defeat(d, self.scaling, [(98, 20, 1.0)], True, True)
        self.assertEqual(sum(one.exp), sum(six.exp))
        self.assertEqual(len(set(six.exp)), 1)
        self.assertGreater(one.exp[0], one.exp[1])
        self.assertEqual(len(set(one.exp[1:])), 1)
        four = RB.Party(6, ko_takers=4)
        for _ in range(4):
            four.defeat(d, self.scaling, [(98, 20, 1.0)], True, True)
        self.assertEqual(len(set(four.exp[:4])), 1)
        self.assertGreater(four.exp[0], four.exp[4])
        for bad in (0, 7):
            with self.assertRaises(ValueError):
                RB.Party(6, ko_takers=bad)

    def test_references(self):
        levels = [30, 28, 26, 25, 25, 24]
        ref = {name: f(levels, 2) for name, f in RB.REFERENCES.items()}
        self.assertEqual(ref, {'bench': 24, 'ko_mean': 29, 'party_mean': 26.333333333333332, 'ace': 30})
        self.assertEqual(RB.REFERENCES['bench'](levels, 6), 24)
        self.assertEqual(RB.REFERENCES['bench']([30, 25, 25, 25, 25, 25], 1), 25)

    def test_trainer_bonus_up_to_gen7(self):
        # Cmd_getexp checks B_TRAINER_EXP_MULTIPLIER <= GEN_7.
        calc = 98 * 20 // 7
        for value, expected in (('GEN_6', calc * 150 // 100), ('GEN_7', calc * 150 // 100), ('GEN_8', calc)):
            d = fake_regime(B_SCALED_EXP='GEN_3', B_SPLIT_EXP='GEN_6', B_TRAINER_EXP_MULTIPLIER=value)
            self.assertEqual(RB.exp_award(d, self.scaling, 98, 20, 20, True, 1), expected, value)

    def test_friendship_events(self):
        self.assertEqual([RB.friendship_gain(f, 'level') for f in (50, 99, 100, 199, 200)], [5, 5, 3, 3, 2])
        self.assertEqual([RB.friendship_gain(f, 'league') for f in (0, 150, 250)], [3, 2, 1])
        party = RB.Party(2, friendship=98)
        party.befriend('walk', 4, chance=0.5)
        self.assertEqual(party.friendship, [100.0, 100.0])
        party.befriend('league')
        self.assertEqual(party.friendship, [102.0, 102.0])
        party.friendship = [254.0, 0.0]
        party.befriend('level')
        self.assertEqual(party.friendship, [255.0, 5.0])

    def test_level_ups_add_friendship_and_unlock_affection(self):
        d = fake_regime(B_SCALED_EXP='GEN_3', B_SPLIT_EXP='GEN_6', B_AFFECTION_MECHANICS='TRUE')
        party = RB.Party(1, friendship=50, affection='friendship')
        # 101 exp takes a Medium Slow level 5 (135) to level 7 (236): two level-ups.
        party.defeat(d, self.scaling, [(101, 7, 1.0)], False, False)
        self.assertEqual((party.levels(), party.friendship), ([7], [60.0]))
        self.assertFalse(party.has_affection(0))
        party.friendship = [220.0]
        self.assertTrue(party.has_affection(0))
        self.assertTrue(RB.Party(1, affection='always').has_affection(0))
        self.assertFalse(RB.Party(1, friendship=255, affection='none').has_affection(0))
        with self.assertRaises(ValueError):
            RB.Party(1, affection='sometimes')

    def test_growth(self):
        self.assertEqual(RB.exp_for_level('GROWTH_MEDIUM_SLOW', 5), 135)
        self.assertEqual(RB.level_for_exp('GROWTH_MEDIUM_SLOW', 135), 5)
        self.assertEqual(RB.level_for_exp('GROWTH_MEDIUM_SLOW', 134), 4)
        self.assertEqual(RB.level_for_exp('GROWTH_MEDIUM_FAST', 10 ** 7), 100)

    def test_land_foes_spread_each_slot_over_its_levels(self):
        slots = [('land_mons', {'species': 'A', 'min_level': 2, 'max_level': 3}, 60),
                 ('water_mons', {'species': 'B', 'min_level': 5, 'max_level': 5}, 40)]
        self.assertEqual(RB.land_foes(slots), [('A', 2, 30.0), ('A', 3, 30.0)])

    def test_cleared_share(self):
        self.assertEqual(len(RB.cleared(list(range(10)), 0.5)), 5)
        self.assertEqual(RB.cleared(['a', 'b'], 1.0), ['a', 'b'])


class Analysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = RB.analyze(FIXTURE, FIXTURE_STAGES)

    def test_census_skips_comment_paragraphs(self):
        c = self.res['census']
        self.assertEqual((c['trainers'], c['mons'], c['mons_with_moves'], c['mons_default']), (4, 6, 1, 5))
        self.assertEqual((c['trainers_check_bad_move'], c['trainers_basic_trainer'], c['trainers_no_ai']), (1, 1, 2))
        self.assertEqual(self.res['story_trainers'], 3)  # the hiker, the rival boss and the leader

    def test_default_flags(self):
        rows = {(r['trainer'], r['slot']): r for r in self.res['default_rows']}
        ralts = rows[('TRAINER_HIKER_A', 0)]
        self.assertEqual(ralts['flags'], ['no_attack', 'lost_all_attacks', 'lost_stab'])
        sableye = rows[('TRAINER_HIKER_A', 1)]
        self.assertEqual(sableye['modern_default'], ['MOVE_LEER', 'MOVE_ASTONISH', 'MOVE_SHADOW_CLAW', 'MOVE_SHADOW_BALL'])
        self.assertEqual(sableye['flags'], ['above_band', 'new_strong'])
        self.assertEqual(sableye['above_band_moves'], ['MOVE_SHADOW_BALL', 'MOVE_SHADOW_CLAW'])
        self.assertEqual(rows[('TRAINER_LEADER_X', 0)]['flags'], [])  # set moves aren't flagged
        d = self.res['defaults']
        self.assertEqual(d['identical'], 3)
        self.assertEqual(d['flags_all'], {'above_band': 1, 'lost_all_attacks': 1, 'lost_stab': 1,
                                          'new_strong': 1, 'no_attack': 3})
        self.assertEqual(d['flags_story']['no_attack'], 2)  # the swimmer is only on a rematch script

    def test_handwritten_category_flips(self):
        flips = {c['move']: c for c in self.res['handwritten_rows']}
        self.assertEqual(flips['MOVE_SHADOW_BALL']['stat'], [90, 60])
        self.assertEqual(flips['MOVE_SHADOW_BALL']['stat_shift'], 'weaker')
        self.assertEqual(flips['MOVE_FEINT_ATTACK']['stat_shift'], 'stronger')
        h = self.res['handwritten']
        self.assertEqual((h['category_flips'], h['mons_with_category_flip'], h['mons_with_flip_weaker']), (2, 1, 1))

    def test_boss_matchups(self):
        sableye, mime = self.res['matchups']['TRAINER_LEADER_X']
        self.assertEqual(sableye['offense']['TYPE_STEEL'], [0.5, 1.0])
        self.assertEqual(sableye['defense']['TYPE_FAIRY'], [None, 2.0])
        self.assertEqual(mime['types'], [['TYPE_PSYCHIC'], ['TYPE_PSYCHIC', 'TYPE_FAIRY']])
        self.assertEqual(mime['defense']['TYPE_DARK'], [2.0, 1.0])  # Fairy now resists Dark

    def test_level_curve(self):
        rows = self.res['level_curve']['full clear']
        self.assertEqual([r['boss'] for r in rows], ['TRAINER_RIVAL_A', 'TRAINER_LEADER_X'])
        first, leader = rows
        # Only the hiker's two Pokemon stand before the rival.
        self.assertGreater(first['vanilla_solo'], RB.START_LEVEL)
        self.assertGreaterEqual(leader['modern_share6'], leader['modern_share6_bench'])
        wild = self.res['level_curve']['full clear + 20 wild battles per stage']
        self.assertGreaterEqual(wild[1]['modern_solo'], leader['modern_solo'])

    def test_share_curve(self):
        gd = G.load(FIXTURE)['modern']
        trainers = G.parse_trainers(os.path.join(FIXTURE, 'src', 'data', 'trainers.party'))
        stages = RB.load_stages(FIXTURE_STAGES, trainers, FIXTURE)
        scaling = G.parse_scaling_factors(FIXTURE)
        wilds = RB.load_wilds(FIXTURE, stages)['modern']

        def curve(d=gd, **kw):
            return RB.share_curve(stages, trainers, d, scaling, wilds, **kw)
        # Catch exp only counts when B_EXP_CATCH gives it (the fixture's wild
        # Pokemon are far below the party, so it takes many to gain a level).
        base = curve(catches=0)[0]['bench']
        self.assertGreater(curve(catches=100)[0]["bench"], base)
        self.assertEqual(curve(RB.with_configs(gd, B_EXP_CATCH='GEN_5'), catches=100)[0]['bench'], base)
        on_cfg = RB.with_configs(gd, B_TRAINER_EXP_MULTIPLIER='GEN_6')
        self.assertTrue(on_cfg.flag('B_TRAINER_EXP_MULTIPLIER <= GEN_7'))
        self.assertFalse(gd.flag('B_TRAINER_EXP_MULTIPLIER <= GEN_7'))  # the original is untouched
        # Margin raises: each boss's ace ends margin above the bench, never lowered.
        rows = curve(margin=2)
        for r in rows:
            self.assertEqual(r['boss_ace'], max(r['base_ace'], r['bench'] + 2))
        again = curve(raises={r['boss']: r['raise'] for r in rows})
        self.assertEqual([r['boss_ace'] for r in again], [r['boss_ace'] for r in rows])
        self.assertEqual(curve(margin=-100)[0]['raise'], 0)
        # The 1.5x and affection only add exp.
        on = curve(RB.with_configs(gd, B_TRAINER_EXP_MULTIPLIER='GEN_6'), affection='always')
        self.assertGreaterEqual(on[-1]['bench'], curve(affection='none')[-1]['bench'])
        self.assertGreaterEqual(curve(unevolved=True)[-1]['bench'], curve()[-1]['bench'])
        # Only default-move Pokemon of a raised team are listed (the leader's Sableye has set moves).
        rows = RB.raised_defaults(trainers, G.load(FIXTURE), {'TRAINER_LEADER_X': 5, 'TRAINER_RIVAL_A': 0})
        self.assertEqual([(r['species'], r['levels']) for r in rows], [('SPECIES_MR_MIME', [15, 20])])
        self.assertEqual(RB.stage_trainer_levels(stages, trainers),
                         [{'stage': 'One', 'trainers': 1, 'mean_ace': 20.0, 'max_ace': 20}])
        share = self.res['share_curve']
        self.assertEqual(sorted(share), sorted(RB.TRAINER_EXP))
        self.assertEqual(len(share['1.5x off']['now']), 2 * len(RB.AFFECTION))

    def test_trainer_and_wild_gaps(self):
        inputs = curve_inputs(FIXTURE, FIXTURE_STAGES)
        stages, trainers, gd, scaling, wilds = (inputs[k] for k in ('stages', 'trainers', 'gd', 'scaling', 'wilds'))

        def run(**kw):
            return RB.share_run(stages, trainers, gd, scaling, wilds['modern'], vanilla_wilds=wilds['vanilla'], **kw)
        # The smallest stage raise that leaves the hiker's ace at least 20 above
        # the bench when fought (the fixture party starts 15 below it).
        _, st = run(trainer_gap=-20)
        one = st[0]
        self.assertEqual((one['stage'], one['trainers']), ('One', 1))
        self.assertGreater(one['raise'], 0)
        self.assertLessEqual(one['gap'], -20)
        _, lower = run(stage_raises={'One': one['raise'] - 1})
        self.assertGreater(lower[0]['gap'], -20)
        self.assertEqual(lower[0]['trainer_ace_mean'], 20 + one['raise'] - 1)
        self.assertEqual(run(trainer_gap=100)[1][0]['raise'], 0)  # already met
        self.assertEqual(st[1]['raise'], 0)  # stage Two has no regular trainers
        # The wild offset is over the vanilla tables: the restocked Ralts slot's levels are vanilla's, so 0 applied.
        _, st = run(wild_gap=0)
        self.assertEqual(st[0]['wild_applied'], 0)
        self.assertEqual(st[0]['wild_offset'], max(0, round(st[0]['start_ref'] - RB.land_mean(wilds['vanilla'][0]))))
        self.assertEqual(run(wild_gap=100)[1][0]['wild_offset'], 0)
        # Tables a restock already raised (6 over vanilla here) are never lowered toward the gap.
        raised = {i: RB.shifted_slots(s, 6) for i, s in wilds['modern'].items()}
        _, st = RB.share_run(stages, trainers, gd, scaling, raised, vanilla_wilds=wilds['vanilla'], wild_gap=100)
        self.assertEqual((st[0]['wild_applied'], st[0]['wild_offset']), (6, 6))
        self.assertEqual(st[0]['wild_land_mean'], round(RB.land_mean(raised[0]), 1))
        # Every reference: the margin puts each boss's ace that far above it.
        for name, f in RB.REFERENCES.items():
            rows, _ = run(margin=1, boss_ref=name, ko_takers=3)
            for r in rows:
                self.assertEqual(len(r['levels']), 6)
                self.assertEqual(r['ref'], round(f(r['levels'], 3), 1))
                self.assertEqual(r['boss_ace'], max(r['base_ace'], int(f(r['levels'], 3) + 1.5)), name)
        # Relative gaps: percent of the reference instead of levels.
        rows, _ = run(margin=10, relative_gaps=True)
        for r in rows:
            self.assertEqual(r['boss_ace'], max(r['base_ace'], int(r['bench'] * 1.1 + 0.5)))
        _, st = run(trainer_gap=-400, relative_gaps=True)
        self.assertGreater(st[0]['raise'], 0)
        self.assertLessEqual(st[0]['gap'], -400)
        _, lower = run(stage_raises={'One': st[0]['raise'] - 1}, relative_gaps=True)
        self.assertGreater(lower[0]['gap'], -400)
        _, st = run(wild_gap=20, relative_gaps=True)
        self.assertEqual(st[0]['wild_offset'],
                         max(0, round(st[0]['start_ref'] * 0.8 - RB.land_mean(wilds['vanilla'][0]))))
        # More wild KOs only add exp.
        self.assertGreaterEqual(run(wild_battles=20)[0][-1]['bench'], run()[0][-1]['bench'])

    def test_shifted_slots_and_evolver(self):
        slots = [('land_mons', {'species': 'SPECIES_RALTS', 'min_level': 3, 'max_level': 98}, 60)]
        evolve = {('SPECIES_RALTS', 13): 'SPECIES_KIRLIA'}
        out = RB.shifted_slots(slots, 10, lambda sp, lvl: evolve.get((sp, lvl), sp))
        self.assertEqual(out[0][1], {'species': 'SPECIES_KIRLIA', 'min_level': 13, 'max_level': 100})
        self.assertIs(RB.shifted_slots(slots, 0), slots)
        down = RB.shifted_slots(slots, -5, lambda sp, lvl: 'SPECIES_KIRLIA')
        self.assertEqual(down[0][1], {'species': 'SPECIES_RALTS', 'min_level': 1, 'max_level': 93})
        # evolver keeps a species the regime doesn't have from replacing one it has.
        info = types.SimpleNamespace(evolve=lambda sp, lvl, gender=None: 'SPECIES_NOT_THERE' if lvl > 50 else sp)
        gd = G.load(FIXTURE)['modern']
        self.assertEqual(RB.evolver(info, gd)('SPECIES_RALTS', 60), 'SPECIES_RALTS')

    def test_snapshot_round_trip(self):
        # The explorer's data gives what the parsed repo gives.
        info = G.R.SpeciesInfo.from_evolutions({'SPECIES_ALIAS': 'SPECIES_RALTS'}, {
            'SPECIES_RALTS': [('EVO_LEVEL', '9', 'SPECIES_SABLEYE', []), ('EVO_ITEM', 'ITEM_X', 'SPECIES_MR_MIME', [])],
            'SPECIES_MAGIKARP': [('EVO_ITEM', 'ITEM_X', 'SPECIES_MR_MIME', [])]})
        live = curve_inputs(FIXTURE, FIXTURE_STAGES, info)
        data = json.loads(json.dumps(RB.curve_snapshot(*(live[k] for k in ('stages', 'trainers', 'gd', 'scaling',
                                                                              'wilds')), info, live['postgame'])))
        self.assertEqual(data['evolutions'], {'SPECIES_RALTS': [['EVO_LEVEL', '9', 'SPECIES_SABLEYE', []]]})
        self.assertEqual(sorted(data['trainers']), ['TRAINER_HIKER_A', 'TRAINER_LEADER_X', 'TRAINER_RIVAL_A'])
        self.assertEqual(data['defines']['B_SCALED_EXP'], live['gd'].defines['B_SCALED_EXP'])
        self.assertIn('GEN_LATEST', data['defines'])
        snap = RB.load_snapshot(data)
        self.assertEqual(snap['evolve']('SPECIES_ALIAS', 20), 'SPECIES_SABLEYE')
        self.assertEqual(snap['evolve']('SPECIES_RALTS', 11), 'SPECIES_RALTS')
        for knobs in ({}, {'margin': 1, 'trainer_gap': 0, 'wild_gap': 0, 'ko_takers': 6, 'boss_ref': 'party_mean'},
                      {'scaled_exp': False, 'trainer_exp': '1.5x on', 'share_fraction': 0.25, 'evolve': False},
                      {'scaling_power': 3.0, 'overlevel_cutoff': 2, 'clear': 0.5, 'wild_battles': 4},
                      {'overlevel_cutoff': 10, 'overlevel_unit': 'percent', 'overlevel_halflife': 15,
                       'gap_unit': 'percent', 'margin': 5, 'trainer_gap': 10, 'wild_gap': 20}):
            self.assertEqual(RB.explore_run(snap, knobs), RB.explore_run(live, knobs), knobs)
        got = RB.explore_run(snap, {'ko_takers': 6})
        self.assertEqual(got['bosses'][0]['name'], 'Rival A')
        self.assertEqual(got['bosses'][0]['refs']['bench'], min(got['bosses'][0]['levels']))
        with self.assertRaises(ValueError):
            RB.explore_run(snap, {'no_such_knob': 1})
        with self.assertRaises(ValueError):
            RB.explore_run(snap, {'gap_unit': 'pct'})

    def test_rival_variants_share_the_raise(self):
        trainers = G.parse_trainers(os.path.join(FIXTURE, 'src', 'data', 'trainers.party'))
        with open(FIXTURE_STAGES, encoding='utf-8') as f:
            cfg = json.load(f)
        cfg['rival_variants'] = {'STARTER': ['A', 'B']}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'stages.json')
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f)
            with self.assertRaises(SystemExit):  # TRAINER_RIVAL_B isn't in trainers.party
                RB.load_stages(path, trainers, FIXTURE)
            # A variant team two levels lower is raised to the staged team's raised ace.
            variant = copy.deepcopy(trainers['TRAINER_RIVAL_A'])
            for mon in variant.mons:
                mon.level -= 2
            trainers['TRAINER_RIVAL_B'] = variant
            stages = RB.load_stages(path, trainers, FIXTURE)
            # A variant is no stage trainer override, even when no exclude glob covers it.
            cfg['exclude'] = []
            cfg['stages'][1]['trainers'] = ['TRAINER_RIVAL_B']
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f)
            with self.assertRaises(SystemExit):
                RB.load_stages(path, trainers, FIXTURE)
        self.assertEqual(stages[0]['variants'], {'TRAINER_RIVAL_A': ['TRAINER_RIVAL_B']})
        self.assertEqual(stages[1]['variants'], {})
        variants = RB.stage_variants(stages, trainers)
        self.assertEqual(variants, {'TRAINER_RIVAL_A': {'TRAINER_RIVAL_B': 3}})
        self.assertEqual(RB.variant_raises(variants, trainers, {'TRAINER_RIVAL_A': 3}), {'TRAINER_RIVAL_B': 5})
        self.assertEqual(RB.variant_raises(variants, trainers, {}), {'TRAINER_RIVAL_B': 2})
        self.assertEqual(RB.variant_raises(variants, trainers, {'TRAINER_RIVAL_A': 200}), {'TRAINER_RIVAL_B': 97})

    def test_tms_and_wilds(self):
        tms = {r['tm']: r for r in self.res['tms']}
        self.assertEqual(tms['ITEM_TM_SHADOW_BALL']['stage'], 'One')  # the ball on RouteA beats the gym gift
        self.assertEqual(tms['ITEM_TM_CHARM']['source'], 'mart')
        one = self.res['wild'][0]
        self.assertEqual((one['vanilla_species'], one['modern_species'], one['new_species']), (1, 2, 1))
        self.assertEqual(one['fairy_first'], ['SPECIES_RALTS'])

    def test_economy(self):
        e = self.res['economy']
        self.assertEqual(e['items']['POTION']['vanilla'], {'price': 300, 'sell': 150, 'heal': 20})
        self.assertEqual(e['items']['POTION']['modern'], {'price': 200, 'sell': 50, 'heal': 20})
        # Hiker: 4 * 20 * 10; rival: 4 * 5 * 5. Leader: 4 * 15 * 25.
        self.assertEqual([s['money'] for s in e['stage_money']], [800 + 100, 1500])

    def test_main_writes_outputs(self):
        with tempfile.TemporaryDirectory() as out, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(RB.main(['--repo', FIXTURE, '--stages', FIXTURE_STAGES, '--out-dir', out]), 0)
            self.assertEqual(sorted(os.listdir(out)), ['curve_data.json', 'report.md', 'summary.json',
                                                       'trainer_mons.csv'])
            with open(os.path.join(out, 'report.md'), encoding='utf-8') as f:
                self.assertIn('### Leader X', f.read())
            data = os.path.join(out, 'curve_data.json')
            text = io.StringIO()
            with contextlib.redirect_stdout(text):
                self.assertEqual(RB.main(['curve', '{"ko_takers": 6}', '--data', data]), 0)
            self.assertIn('Leader X', text.getvalue())
            knobs = os.path.join(out, 'knobs.json')
            with open(knobs, 'w', encoding='utf-8') as f:
                f.write('{"margin": 1}')
            text = io.StringIO()
            with contextlib.redirect_stdout(text):
                self.assertEqual(RB.main(['curve', knobs, '--data', data]), 0)
            self.assertIn('Lv 100 by: -', text.getvalue())


def team(tid, cls, *levels, species='SPECIES_SABLEYE'):
    return G.Trainer(tid, '', cls, [], False, [G.TrainerMon(species, lv, []) for lv in levels])


class Postgame(unittest.TestCase):
    """#139: the post-game rounds and the regular rematch ladders."""

    def test_rematch_ladders(self):
        stages = [{'name': 'A', 'regular': ['TRAINER_HIKER_1'], 'bosses': ['TRAINER_LEADER_1']}]
        rematches = {
            'TRAINER_HIKER_1': [['TRAINER_HIKER_1', 'TRAINER_HIKER_2', 'TRAINER_HIKER_3', 'TRAINER_HIKER_3']],
            'TRAINER_SIDNEY': [['TRAINER_SIDNEY'] * 5],
            'TRAINER_WALLY_VR_2': [['TRAINER_WALLY_VR_2', 'TRAINER_WALLY_VR_3']],
            'TRAINER_LEADER_1': [['TRAINER_LEADER_1', 'TRAINER_LEADER_2']],
            'TRAINER_OFF_1': [['TRAINER_OFF_1', 'TRAINER_OFF_2']],
        }
        self.assertEqual(RB.rematch_ladders(rematches, stages, {'TRAINER_STEVEN': None}), {
            'boss': [['TRAINER_WALLY_VR_1', 'TRAINER_WALLY_VR_2', 'TRAINER_WALLY_VR_3'],
                     ['TRAINER_LEADER_1', 'TRAINER_LEADER_2']],
            'final': ['TRAINER_STEVEN'],
            'regular': [['TRAINER_HIKER_1', 'TRAINER_HIKER_2', 'TRAINER_HIKER_3']],
            'unstaged': ['TRAINER_OFF_1']})

    def test_rounds(self):
        inputs = curve_inputs(FIXTURE, FIXTURE_STAGES)
        stages, gd, scaling, wilds = (inputs[k] for k in ('stages', 'gd', 'scaling', 'wilds'))
        trainers = dict(inputs['trainers'])
        for t in (team('TRAINER_LEADER_X_2', 'Leader', 10, 12), team('TRAINER_LEADER_X_3', 'Leader', 99),
                  team('TRAINER_W_2', 'Rival', 5), team('TRAINER_S', 'Champion', 30, 31)):
            trainers[t.id] = t
        postgame = {'boss': [['TRAINER_LEADER_X', 'TRAINER_LEADER_X_2', 'TRAINER_LEADER_X_3'],
                             ['TRAINER_RIVAL_A', 'TRAINER_W_2']], 'final': ['TRAINER_S']}

        def run(**kw):
            return RB.share_run(stages, trainers, gd, scaling, wilds['modern'], **kw)[0]
        story = run(margin=1)
        rows = run(margin=1, postgame=postgame)
        self.assertEqual(rows[:len(story)], story)
        post = rows[len(story):]
        self.assertEqual([(r['stage'], r['boss']) for r in post],
                         [('Rematch 2', 'TRAINER_LEADER_X_2'), ('Rematch 2', 'TRAINER_W_2'),
                          ('Rematch 3', 'TRAINER_LEADER_X_3'), ('Post-game', 'TRAINER_S')])
        leader = story[-1]['boss_ace']
        # One ace per round, set at its start (the margin rule), at least 1 over the ladder's last fight.
        ace = max(int(post[0]['ref'] + 1.5), leader + 1)
        self.assertEqual([post[0]['boss_ace'], post[1]['boss_ace']], [ace, int(post[0]['ref'] + 1.5)])
        self.assertEqual(post[0]['raise'], ace - 12)
        self.assertEqual(post[2]['boss_ace'], 99)  # already above its target: never lowered
        self.assertEqual(post[2]['raise'], 0)
        self.assertEqual(post[3]['boss_ace'], 100)  # 3 over the last round's 99, capped at 100
        self.assertTrue(all(r['raise'] >= 0 for r in post))
        # Without margin the rounds are fought at their own levels (or ``raises``).
        plain = run(postgame=postgame, raises={'TRAINER_S': 2})[len(story):]
        self.assertEqual([r['raise'] for r in plain], [0, 0, 0, 2])

    def test_regular_rematch_raises(self):
        stages = [{'name': 'A', 'regular': ['T_EARLY'], 'bosses': [RB.REMATCH_UNLOCK]},
                  {'name': 'B', 'regular': ['T_LATE'], 'bosses': []}]
        stage_rows = [{'stage': 'A', 'raise': 2, 'start_ref': 20}, {'stage': 'B', 'raise': 3, 'start_ref': 40}]
        trainers = {t.id: t for t in (team('T_EARLY', 'Hiker', 10), team('E2', 'Hiker', 12), team('E3', 'Hiker', 50),
                                      team('E4', 'Hiker', 8, 10), team('T_LATE', 'Hiker', 60),
                                      team('L2', 'Hiker', 99), team('L3', 'Hiker', 50))}
        ladders = [['T_EARLY', 'E2', 'E3', 'E4'], ['T_LATE', 'L2', 'L3']]
        rows = RB.rematch_raises(ladders, stages, stage_rows, trainers, 10, gap=10, relative=True)
        got = {r['trainer']: (r['stage'], r['base'], r['tier'], r['ace'], r['raise']) for r in rows}
        # The early ladder can first be fought after REMATCH_UNLOCK's stage: its base is B's start
        # reference 10% lower (36, over its first fight's raised 12), then 10% a tier (40, 44 -> 50:
        # never lowered, 48 -> 51: 1 over the tier before).
        self.assertEqual(got['E2'], ('B', 36, 2, 40, 28))
        self.assertEqual(got['E3'], ('B', 36, 3, 50, 0))
        self.assertEqual(got['E4'], ('B', 36, 4, 51, 41))
        # The late one from its first fight's raised ace (63); 100 at most.
        self.assertEqual(got['L2'], ('B', 63, 2, 99, 0))
        self.assertEqual(got['L3'], ('B', 63, 3, 100, 50))
        # In levels: the first fight's raised ace plus the step per tier.
        rows = RB.rematch_raises(ladders[:1], stages, stage_rows, trainers, 3)
        self.assertEqual([(r['ace'], r['raise']) for r in rows], [(15, 3), (50, 0), (51, 41)])


@unittest.skipUnless(os.path.exists(os.path.join(G.REPO, 'src', 'data', 'trainers.party')), 'needs the repo')
class RaiseParty(unittest.TestCase):
    PARTY = """/* a comment */
=== TRAINER_A ===
Name: A
Class: Hiker

Nick (Aron) (F) @ Oran Berry
Level: 33
- Tackle

Zubat
Level: 98

=== TRAINER_WALLY_MAUVILLE ===
Name: WALLY

Ralts (M)
Level: 16

=== PARTNER_B ===
Name: B

Mr. Mime
Level: 40

Aron
"""

    def test_raise_party(self):
        evolve = {('SPECIES_ARON', 38): 'SPECIES_LAIRON', ('SPECIES_RALTS', 21): 'SPECIES_KIRLIA',
                  ('SPECIES_MR_MIME', 45): 'SPECIES_MR_RIME'}
        seen = []

        def evolver(species, level, gender=None):
            seen.append((species, level, gender))
            return evolve.get((species, level), species)
        text, evolved = RB.raise_party(self.PARTY, {'TRAINER_A': 5, 'TRAINER_WALLY_MAUVILLE': 5, 'PARTNER_B': 5},
                                       evolver)
        # The nickname, gender and item stay; levels cap at 100; EVOLVE_EXEMPT's Ralts and the
        # partner only rise; a Pokemon without a Level line (100) keeps it.
        self.assertEqual(text, self.PARTY.replace('Nick (Aron) (F)', 'Nick (Lairon) (F)')
                         .replace('Level: 33', 'Level: 38').replace('Level: 98', 'Level: 100')
                         .replace('Level: 16', 'Level: 21').replace('Level: 40', 'Level: 45'))
        self.assertEqual(evolved, [('TRAINER_A', 'SPECIES_ARON', 'SPECIES_LAIRON', 38)])
        self.assertIn(('SPECIES_ARON', 38, 'MON_FEMALE'), seen)
        # A species name with punctuation is replaced whole, and parses back.
        mime = self.PARTY.replace('=== PARTNER_B ===', '=== TRAINER_B ===')
        text, _ = RB.raise_party(mime, {'TRAINER_B': 5}, evolver)
        self.assertIn('Mr Rime\nLevel: 45', text)
        self.assertEqual(G.parse_trainers_text(text)['TRAINER_B'].mons[0].species, 'SPECIES_MR_RIME')
        # A boss's team (unique) doesn't evolve into a species it already has.
        boss = '=== TRAINER_C ===\nName: C\n\nAron\nLevel: 33\n\nLairon\nLevel: 40\n'
        self.assertEqual(RB.raise_party(boss, {'TRAINER_C': 5}, evolver, {'TRAINER_C'})[1], [])
        self.assertEqual(len(RB.raise_party(boss, {'TRAINER_C': 5}, evolver)[1]), 1)
        # Teams not in raises, and a raise of 0, change nothing.
        self.assertEqual(RB.raise_party(self.PARTY, {'TRAINER_B': 3}, evolver)[0], self.PARTY)
        self.assertEqual(RB.raise_party(self.PARTY, {'TRAINER_A': 0}, evolver), (self.PARTY, []))

    def test_party_species_name(self):
        self.assertEqual(RB.party_species_name('SPECIES_KIRLIA'), 'Kirlia')
        self.assertEqual(RB.party_species_name('SPECIES_MR_MIME'), 'Mr Mime')
        self.assertEqual(G.species_constant(RB.party_species_name('SPECIES_FARFETCHD')), 'SPECIES_FARFETCHD')


class RealRepo(unittest.TestCase):
    """The parsers resolve every trainer Pokemon and move in the real data."""

    def test_every_trainer_species_and_move_resolves(self):
        gd = G.load(G.REPO)
        trainers = G.parse_trainers(os.path.join(G.REPO, 'src', 'data', 'trainers.party'))
        for regime, d in gd.items():
            for t in trainers.values():
                for mon in t.mons:
                    self.assertIn(mon.species, d.species, (regime, t.id))
                    self.assertTrue(d.learnset(mon.species), (regime, mon.species))
                    for mv in mon.moves + d.default_moves(mon.species, mon.level):
                        self.assertIn(mv, d.moves, (regime, t.id, mv))

    def test_move_and_item_details(self):
        gd = G.load(G.REPO)
        v, m = gd['vanilla'], gd['modern']
        # Sitrus Berry: the #if in item_effects.h picks 30 HP in Gen 3, a quarter later.
        self.assertEqual(v.items['ITEM_SITRUS_BERRY']['heal'], 30)
        self.assertIsNone(m.items['ITEM_SITRUS_BERRY']['heal'])
        # Hidden Power: all-0 IVs give Fighting (30 power in Gen 3), all-31 Dark (70).
        zero = dict.fromkeys(G.IV_STATS, 0)
        self.assertEqual(G.hidden_power(zero, v), ('TYPE_FIGHTING', 30))
        self.assertEqual(G.hidden_power(G.DEFAULT_IVS, v), ('TYPE_DARK', 70))
        self.assertEqual(G.hidden_power(zero, m), ('TYPE_FIGHTING', 60))
        self.assertEqual(v.move('MOVE_HIDDEN_POWER', zero).category, 'DAMAGE_CATEGORY_PHYSICAL')
        # Fixed-damage moves are attacks but never STAB.
        self.assertTrue(RB.attacks(m, ['MOVE_SEISMIC_TOSS']))
        self.assertFalse(RB.has_stab(m, 'SPECIES_HARIYAMA', ['MOVE_SEISMIC_TOSS']))
        self.assertTrue(RB.has_stab(m, 'SPECIES_HARIYAMA', ['MOVE_ARM_THRUST']))

    def test_trick_house_prizes_are_filed_under_their_puzzle(self):
        tms = G.map_tms(G.REPO)
        self.assertIn(('ITEM_TM_TAUNT', 'reward'), tms['Route110_TrickHousePuzzle5'])
        self.assertFalse(any(item == 'ITEM_TM_TAUNT' for f in ('Route110_TrickHouseEnd', 'Route110_TrickHouseEntrance')
                             for item, _ in tms.get(f, ())))

    def test_data_meets_the_curve_settings(self):
        """The committed levels are what `rebalance.py apply` writes for curve_settings.json (#150):
        the model with those settings asks for no raise and the committed wild offsets. After a
        trainers.party, wild or exp-formula change, rerun apply (or change the settings)."""
        with open(RB.CURVE_SETTINGS, encoding='utf-8') as f:
            knobs = json.load(f)
        inputs = RB.repo_inputs(G.REPO, info=G.R.SpeciesInfo(G.REPO))
        partners = G.parse_trainers(os.path.join(G.REPO, 'src', 'data', 'battle_partners.party'))
        with open(os.path.join(G.REPO, RB.VANILLA_WILD), encoding='utf-8') as f:
            wild = json.load(f)
        plan = RB.apply_plan(inputs, knobs, partners, wild, G.map_folders(G.REPO))
        self.assertEqual(plan['raises'], {})
        with open(os.path.join(G.REPO, RB.LEVEL_OFFSETS), encoding='utf-8') as f:
            self.assertEqual(plan['wild'], json.load(f))

    def test_scaling_factors_are_the_games(self):
        self.assertEqual(RB.scaling_factors(2.5), G.parse_scaling_factors(G.REPO))
        # #154's tables: the model computes the game's steep scaling and over-level penalty.
        self.assertEqual(RB.scaling_factors(3.5),
                         G.parse_scaling_factors(G.REPO, 'gExperienceScalingFactorsSteep', 'exp_formula.c'))
        self.assertEqual(list(RB.HALVING_FRACTIONS), G.parse_scaling_factors(G.REPO, 'sExpHalvingFractions',
                                                                              'exp_formula.c'))
        gd = G.load(G.REPO)
        self.assertEqual(RB.Overlevel.from_configs(gd['modern']), RB.Overlevel(10, True, 5))
        self.assertIsNone(RB.Overlevel.from_configs(gd['vanilla']))
        self.assertEqual(RB.game_scaling(gd['modern'], RB.scaling_factors(2.5)), RB.scaling_factors(3.5))

    def test_rematch_ladders(self):
        rematches = G.parse_rematches(G.REPO)
        self.assertEqual(rematches['TRAINER_ROSE_1'], [[f'TRAINER_ROSE_{n}' for n in range(1, 6)]])
        trainers = G.parse_trainers(os.path.join(G.REPO, 'src', 'data', 'trainers.party'))
        self.assertTrue(all(t in trainers for rows in rematches.values() for ids in rows for t in ids))
        # #139: the eight gym leaders' and Wally's post-game ladders, and every regular ladder staged.
        ladders = RB.rematch_ladders(rematches, RB.load_stages(RB.DEFAULT_STAGES, trainers, G.REPO), trainers)
        self.assertEqual([lad[1] for lad in ladders['boss']],
                         ['TRAINER_WALLY_VR_2'] + [f'TRAINER_{n}_2' for n in (
                             'ROXANNE', 'BRAWLY', 'WATTSON', 'FLANNERY', 'NORMAN', 'WINONA', 'TATE_AND_LIZA', 'JUAN')])
        self.assertEqual((len(ladders['regular']), ladders['unstaged']), (64, []))
        self.assertEqual(ladders['final'], ['TRAINER_STEVEN'])
        # REMATCH_UNLOCK is the leader whose badge reaches OW_REMATCH_BADGE_COUNT (in gym order).
        with open(os.path.join(G.REPO, 'include', 'config', 'overworld.h'), encoding='utf-8') as f:
            count = int(re.search(r'#define OW_REMATCH_BADGE_COUNT\s+(\d+)', f.read())[1])
        leaders = ['ROXANNE', 'BRAWLY', 'WATTSON', 'FLANNERY', 'NORMAN', 'WINONA', 'TATE_AND_LIZA', 'JUAN']
        self.assertEqual(RB.REMATCH_UNLOCK, f'TRAINER_{leaders[count - 1]}_1')

    def test_committed_curve_data_runs_the_repo_model(self):
        """output/curve_data.json (the explorer's data) gives the curve the
        repo's own data gives: rerun rebalance.py after a data change."""
        live = curve_inputs(G.REPO, RB.DEFAULT_STAGES, G.R.SpeciesInfo(G.REPO))
        with open(os.path.join(RB.DEFAULT_OUT_DIR, RB.CURVE_DATA), encoding='utf-8') as f:
            snap = RB.load_snapshot(json.load(f))
        for knobs in ({}, {'ko_takers': 6, 'boss_ref': 'party_mean', 'margin': 1, 'trainer_gap': 5, 'wild_gap': 10},
                      {'scaled_exp': False, 'trainer_exp': '1.5x on', 'affection': 'always', 'wild_battles': 5},
                      {'margin': 5, 'gap_unit': 'percent', 'trainer_gap': 10, 'rematch_step': 5}):
            self.assertEqual(RB.explore_run(snap, knobs), RB.explore_run(live, knobs), knobs)

    def test_stage_bosses_exist(self):
        trainers = G.parse_trainers(os.path.join(G.REPO, 'src', 'data', 'trainers.party'))
        stages = RB.load_stages(RB.DEFAULT_STAGES, trainers, G.REPO)
        self.assertTrue(all(st['bosses'] for st in stages))

    def test_every_map_with_trainers_tms_or_wild_has_a_stage(self):
        with open(RB.DEFAULT_STAGES, encoding='utf-8') as f:
            cfg = json.load(f)
        with open(os.path.join(G.REPO, 'src', 'data', 'wild_encounters.json'), encoding='utf-8') as f:
            wild_ids = {e.get('map') for g in json.load(f)['wild_encounter_groups'] for e in g['encounters']}
        folders = set(G.map_trainers(G.REPO).values()) | set(G.map_tms(G.REPO))
        folders |= {f for f, mid in G.map_folders(G.REPO).items() if mid in wild_ids}
        missing = sorted(f for f in folders
                         if not f.endswith('_Frlg') and G.stage_of(f, cfg['stages']) is None
                         and not any(fnmatch.fnmatchcase(f, g) for g in cfg['unstaged']))
        self.assertEqual(missing, [])

    def test_trick_house_puzzles_follow_their_badge_gates(self):
        """A puzzle that needs badge N sits in the stage after gym leader N's; the game-clear one in none."""
        with open(RB.DEFAULT_STAGES, encoding='utf-8') as f:
            cfg = json.load(f)
        leaders = ['ROXANNE', 'BRAWLY', 'WATTSON', 'FLANNERY', 'NORMAN', 'WINONA', 'TATE_AND_LIZA', 'JUAN']
        badge_stage = {n: next(i for i, st in enumerate(cfg['stages']) if f'TRAINER_{name}_1' in st['bosses'])
                       for n, name in enumerate(leaders, 1)}
        path = os.path.join(G.REPO, 'data', 'maps', 'Route110_TrickHouseEntrance', 'scripts.inc')
        with open(path, encoding='utf-8') as f:
            gates = dict(re.findall(r'CheckReadyForPuzzle(\d)::\s*call_if_unset (\w+)', f.read()))
        self.assertEqual(sorted(gates), [str(n) for n in range(2, 9)])
        self.assertEqual(G.stage_of('Route110_TrickHousePuzzle1', cfg['stages']),
                         G.stage_of('Route110', cfg['stages']))
        for puzzle, flag in gates.items():
            folder = f'Route110_TrickHousePuzzle{puzzle}'
            badge = re.fullmatch(r'FLAG_BADGE0(\d)_GET', flag)
            if badge:
                self.assertEqual(G.stage_of(folder, cfg['stages']), badge_stage[int(badge.group(1))] + 1, folder)
            else:
                self.assertEqual(flag, 'FLAG_SYS_GAME_CLEAR')
                self.assertIsNone(G.stage_of(folder, cfg['stages']), folder)
                self.assertTrue(any(fnmatch.fnmatchcase(folder, g) for g in cfg['unstaged']), folder)


if __name__ == '__main__':
    unittest.main()
