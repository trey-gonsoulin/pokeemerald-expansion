"""Tests for tools/rebalance. Run from the repo root:

    python3 -m unittest discover -s tools/rebalance
"""

import contextlib
import io
import os
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
        self.assertEqual(RB.exp_award(d, self.scaling, 39, 10, 25, False, 1, share_bench=True), gain // 2)

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

    def test_growth(self):
        self.assertEqual(RB.exp_for_level('GROWTH_MEDIUM_SLOW', 5), 135)
        self.assertEqual(RB.level_for_exp('GROWTH_MEDIUM_SLOW', 135), 5)
        self.assertEqual(RB.level_for_exp('GROWTH_MEDIUM_SLOW', 134), 4)
        self.assertEqual(RB.level_for_exp('GROWTH_MEDIUM_FAST', 10 ** 7), 100)

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
            self.assertEqual(sorted(os.listdir(out)), ['report.md', 'summary.json', 'trainer_mons.csv'])
            with open(os.path.join(out, 'report.md'), encoding='utf-8') as f:
                self.assertIn('### Leader X', f.read())


@unittest.skipUnless(os.path.exists(os.path.join(G.REPO, 'src', 'data', 'trainers.party')), 'needs the repo')
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

    def test_stage_bosses_exist(self):
        trainers = G.parse_trainers(os.path.join(G.REPO, 'src', 'data', 'trainers.party'))
        stages = RB.load_stages(RB.DEFAULT_STAGES, trainers, G.REPO)
        self.assertTrue(all(st['bosses'] for st in stages))


if __name__ == '__main__':
    unittest.main()
