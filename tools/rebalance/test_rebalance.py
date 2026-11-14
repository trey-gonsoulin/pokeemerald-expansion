"""Tests for tools/rebalance. Run from the repo root:

    python3 -m unittest discover -s tools/rebalance
"""

import contextlib
import copy
import fnmatch
import functools
import io
import json
import os
import re
import sys
import tempfile
import types
import unittest
import unittest.mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gamedata as G  # noqa: E402
import matchup as M  # noqa: E402
import power as P  # noqa: E402
import rebalance as RB  # noqa: E402
import solo as S  # noqa: E402

FIXTURE = os.path.join(G.HERE, 'testdata', 'repo')
FIXTURE_STAGES = os.path.join(G.HERE, 'testdata', 'stages.json')
# Names no fixture trainer, so its skip player fights the bosses alone and skips Leader X (#350).
FIXTURE_FORCED = os.path.join(G.HERE, 'testdata', 'forced_trainers.json')


def fake_regime(**overrides):
    """An object with GameData.flag for the given config values."""
    defines = G.R.parse_defines(FIXTURE)
    defines.update(overrides)
    return types.SimpleNamespace(flag=lambda expr: G.R.c_eval(expr, defines))


# The fixture's inputs without the real forced trainers, which name none of its trainers.
curve_inputs = functools.partial(RB.repo_inputs, forced_path=None)


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


class MoveLegality(unittest.TestCase):
    """#145's learnable set moves, on a made-up Pichu line."""

    def setUp(self):
        sp = {name: G.Species((), {}, 0, '', f's{name}Learnset', f's{name}Teachables', f's{name}EggMoves')
              for name in ('Pichu', 'Pikachu', 'Raichu')}
        self.gd = G.GameData.from_parts({}, {f'SPECIES_{n.upper()}': s for n, s in sp.items()})
        self.gd.learnsets = {'sPichuLearnset': [(1, 'MOVE_CHARM'), (20, 'MOVE_NASTY_PLOT')],
                             'sPikachuLearnset': [(1, 'MOVE_GROWL'), (30, 'MOVE_SLAM')],
                             'sRaichuLearnset': [(0, 'MOVE_THUNDER_PUNCH'), (1, 'MOVE_GROWL')]}
        self.info = G.R.SpeciesInfo.from_evolutions({}, {})
        self.info.pre_evos = {'SPECIES_PIKACHU': [('SPECIES_PICHU', 'EVO_FRIENDSHIP', '0')],
                              'SPECIES_RAICHU': [('SPECIES_PIKACHU', 'EVO_ITEM', 'ITEM_THUNDER_STONE')]}
        self.lists = G.parse_move_lists('static const u16 sPichuTeachables[] = {\n    MOVE_SURF,\n'
                                        '    MOVE_UNAVAILABLE,\n};\nstatic const u16 sRaichuTeachables[] = '
                                        '{\n    MOVE_THUNDERBOLT,\n    MOVE_UNAVAILABLE,\n};\n'
                                        'static const u16 sPichuEggMoves[] = {\n    MOVE_VOLT_TACKLE,\n};\n')

    def test_parse_move_lists(self):
        self.assertEqual(self.lists['sPichuTeachables'], {'MOVE_SURF', 'MOVE_UNAVAILABLE'})

    def test_learnable_through_the_line_up_to_the_level(self):
        self.assertEqual(RB.evolution_line(self.info, 'SPECIES_RAICHU'),
                         ['SPECIES_RAICHU', 'SPECIES_PIKACHU', 'SPECIES_PICHU'])
        moves = RB.learnable_moves(self.gd, self.info, self.lists, 'SPECIES_RAICHU', 25)
        # Evolution and pre-evolution moves, and the line's teachables and egg moves; not Slam (level 30).
        self.assertLessEqual({'MOVE_THUNDER_PUNCH', 'MOVE_CHARM', 'MOVE_NASTY_PLOT', 'MOVE_SURF',
                              'MOVE_THUNDERBOLT', 'MOVE_VOLT_TACKLE'}, moves)
        self.assertNotIn('MOVE_SLAM', moves)
        # A pre-evolution can't learn its evolution's moves.
        self.assertNotIn('MOVE_THUNDERBOLT', RB.learnable_moves(self.gd, self.info, self.lists, 'SPECIES_PICHU', 50))

    def test_unlearnable_set_moves_once_per_team(self):
        teams = G.parse_trainers_text('=== TRAINER_A ===\nName: A\n\nRaichu\nLevel: 25\n- Slam\n- Thunder Punch\n'
                                      '\nRaichu\nLevel: 25\n- Slam\n')
        self.assertEqual(RB.unlearnable_set_moves(teams, self.gd, self.info, self.lists),
                         [('TRAINER_A', 'SPECIES_RAICHU', 'MOVE_SLAM')])

    def scored(self):
        """The Pichu line with stats and moves to score: an Electric Raichu with
        Attack 40 and Special Attack 90, Boomburst (Normal) from its teachables
        and Hyper Beam, Explosion and Sky Attack beside them."""
        for sp in self.gd.species.values():
            sp.types = ('TYPE_ELECTRIC',)
            sp.stats = {'baseAttack': 40, 'baseSpAttack': 90}
        phys, spec, status = 'DAMAGE_CATEGORY_PHYSICAL', 'DAMAGE_CATEGORY_SPECIAL', 'DAMAGE_CATEGORY_STATUS'
        self.gd.moves = {
            'MOVE_CHARM': G.Move('TYPE_FAIRY', 0, 100, status), 'MOVE_NASTY_PLOT': G.Move('TYPE_DARK', 0, 0, status),
            'MOVE_GROWL': G.Move('TYPE_NORMAL', 0, 100, status), 'MOVE_SLAM': G.Move('TYPE_NORMAL', 80, 75, phys),
            'MOVE_MEGA_KICK': G.Move('TYPE_NORMAL', 120, 75, phys),
            'MOVE_THUNDER_PUNCH': G.Move('TYPE_ELECTRIC', 75, 100, phys),
            'MOVE_THUNDERBOLT': G.Move('TYPE_ELECTRIC', 90, 100, spec),
            'MOVE_VOLT_TACKLE': G.Move('TYPE_ELECTRIC', 120, 100, phys),
            'MOVE_SURF': G.Move('TYPE_WATER', 90, 100, spec), 'MOVE_BOOMBURST': G.Move('TYPE_NORMAL', 140, 100, spec),
            'MOVE_HYPER_BEAM': G.Move('TYPE_NORMAL', 300, 100, spec, recharge=True),
            'MOVE_EXPLOSION': G.Move('TYPE_NORMAL', 250, 100, phys, explosion=True),
            'MOVE_SKY_ATTACK': G.Move('TYPE_FLYING', 500, 100, phys, 'EFFECT_TWO_TURNS_ATTACK')}
        self.lists['sRaichuTeachables'] |= {'MOVE_BOOMBURST', 'MOVE_HYPER_BEAM', 'MOVE_EXPLOSION', 'MOVE_SKY_ATTACK'}

    def replace(self, level, replaced, kept, species='SPECIES_RAICHU'):
        return RB.replacement_move(self.gd, self.info, self.lists, species, level, replaced, kept)

    def test_replacement_restores_stab(self):
        self.scored()
        # Boomburst (140 x 90) outscores Thunderbolt (90 x 1.5 x 90) while the set keeps its STAB...
        self.assertEqual(self.replace(50, 'MOVE_MEGA_KICK', ['MOVE_GROWL', 'MOVE_THUNDERBOLT']), 'MOVE_BOOMBURST')
        # ...but a set that would lose it takes the best Electric move.
        self.assertEqual(self.replace(50, 'MOVE_MEGA_KICK', ['MOVE_GROWL', 'MOVE_SURF']), 'MOVE_THUNDERBOLT')

    def test_replacement_is_never_a_recharge_self_ko_or_two_turn_move(self):
        self.scored()
        # Hyper Beam, Explosion and Sky Attack outscore Surf, the best of the rest.
        kept = ['MOVE_THUNDERBOLT', 'MOVE_BOOMBURST']
        self.assertEqual(self.replace(50, 'MOVE_MEGA_KICK', kept), 'MOVE_SURF')

    def test_replacement_is_never_an_hm_fixture(self):
        self.scored()
        self.lists[G.HM_LIST] = G.parse_hms('#define FOREACH_HM(F) \\\n    F(CUT) \\\n    F(SURF)\n\n'
                                            '#define FOREACH_TMHM(F) \\\n')
        self.assertEqual(self.lists[G.HM_LIST], {'MOVE_CUT', 'MOVE_SURF'})
        # Surf was the best of the rest; Volt Tackle is the best that isn't an HM.
        self.assertEqual(self.replace(50, 'MOVE_MEGA_KICK', ['MOVE_THUNDERBOLT', 'MOVE_BOOMBURST']),
                         'MOVE_VOLT_TACKLE')

    def test_replacement_prefers_level_up_at_30_or_below_fixture(self):
        self.scored()
        # Thunder Punch (on evolving) over the stronger Thunderbolt from the teachables, up to level 30.
        self.assertEqual(self.replace(30, 'MOVE_MEGA_KICK', ['MOVE_GROWL', 'MOVE_SURF']), 'MOVE_THUNDER_PUNCH')
        self.assertEqual(self.replace(31, 'MOVE_MEGA_KICK', ['MOVE_GROWL', 'MOVE_SURF']), 'MOVE_THUNDERBOLT')

    def test_rewrite_unlearnable_reports_each_change(self):
        self.scored()
        text = ('=== TRAINER_A ===\nName: A\n\nRaichu\nLevel: 25\n- Slam\n- Thunder Punch\n'
                '\nSparky (Raichu) (M) @ Oran Berry\nLevel: 50\nIVs: 0 HP / 0 Atk / 0 Def / 0 SpA / 0 SpD / 0 Spe\n'
                '- Growl  \n- Mega Kick\n- Surf\n\n=== TRAINER_B ===\nName: B\n\nPikachu\nLevel: 30\n- Slam\n')
        out, changes = RB.rewrite_unlearnable(text, self.gd, self.info, self.lists)
        # Slam at 25 keeps the set's STAB, and no other Electric move comes by level up: Boomburst.
        # The Mega Kick on a set without STAB: Thunderbolt. Pikachu's Slam at 30 is learnable.
        self.assertEqual(out, text.replace('- Slam\n- Thunder', '- Boomburst\n- Thunder')
                         .replace('- Mega Kick', '- Thunderbolt'))
        self.assertEqual(changes, [('TRAINER_A', 'SPECIES_RAICHU', 'MOVE_SLAM', 'MOVE_BOOMBURST'),
                                   ('TRAINER_A', 'SPECIES_RAICHU', 'MOVE_MEGA_KICK', 'MOVE_THUNDERBOLT')])


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
        # No width: full exp up to the cutoff, the floor past it (at least 1).
        hard = RB.Overlevel(5)
        self.assertEqual(award(25, overlevel=hard), award(25))
        self.assertEqual(award(26, overlevel=hard), 1)
        self.assertEqual(RB.Overlevel(5, floor=10).apply(1000, 20, 26), 100)
        # A getter that gets nothing still gets nothing, and one at or below the foe's level loses nothing.
        self.assertEqual(award(30, sent_out=False, overlevel=hard), 0)
        self.assertEqual(award(15, overlevel=RB.Overlevel(0, width=1)), award(15))
        # Percent of the foe's level: 25% above a level-20 foe is level 25.
        rel = RB.Overlevel(25, relative=True)
        self.assertEqual(award(25, overlevel=rel), award(25))
        self.assertEqual(award(26, overlevel=rel), 1)
        self.assertEqual(award(50, foe=40, overlevel=rel), award(50, foe=40))
        # The logistic: slow just above the foe, about half the way down at the cutoff, then the floor.
        soft = RB.Overlevel(3, width=1, floor=10)
        self.assertEqual(soft.apply(1000, 20, 21), 932)
        self.assertEqual(soft.apply(1000, 20, 23), 572)
        self.assertEqual(soft.apply(1000, 20, 40), 100)
        self.assertEqual(RB.Overlevel(3, width=1).apply(1000, 20, 40), 1)
        # The same cases as test/battle/exp.c's, at the game's 15 / 4 / 10%.
        game = RB.Overlevel(15, True, 4, 10)
        for foe, getter, exp in ((30, 30, 1000), (30, 31, 973), (30, 33, 816), (30, 35, 466), (30, 36, 305),
                                 (30, 40, 109), (20, 23, 560), (40, 46, 560), (20, 60, 100)):
            self.assertEqual(game.apply(1000, foe, getter), exp, (foe, getter))
        self.assertEqual(game.apply(0, 20, 60), 0)
        self.assertEqual(game.apply(5, 20, 60), 1)
        # Width 0: the floor straight past the cutoff.
        self.assertEqual(RB.Overlevel(15, True, 0, 10).apply(1000, 20, 23), 1000)
        self.assertEqual(RB.Overlevel(15, True, 0, 10).apply(1000, 20, 24), 100)
        # A minimum level: a foe below it counts as that level for the cutoff and width, so a level-3
        # foe's cutoff is 2.55 levels at 17 (0.45 without). At or above it, nothing changes.
        low = RB.Overlevel(15, True, 4, 10, 17)
        for foe, getter, exp in ((3, 3, 1000), (3, 4, 935), (3, 5, 737), (3, 6, 413), (3, 7, 198),
                                 (3, 10, 101), (17, 20, 413), (20, 23, 560), (30, 35, 466)):
            self.assertEqual(low.apply(1000, foe, getter), exp, (foe, getter))
        self.assertEqual(game.apply(1000, 3, 5), 100)
        self.assertEqual(RB.Overlevel(3, False, 1, 10, 17).apply(1000, 20, 23), soft.apply(1000, 20, 23))

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

    def test_trainer_bonus_up_to_gen6(self):
        # Cmd_getexp checks B_TRAINER_EXP_MULTIPLIER <= GEN_6 (#140).
        calc = 98 * 20 // 7
        for value, expected in (('GEN_6', calc * 150 // 100), ('GEN_7', calc), ('GEN_8', calc)):
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


def power_regime(species, moves):
    """An object with what power.py reads of GameData: species, move and flag."""
    return types.SimpleNamespace(species=species, move=lambda name, ivs=None: moves[name],
                                 flag=fake_regime().flag)


def power_species(base, types_=(), abilities=()):
    stats = dict.fromkeys(G.STAT_FIELDS, base) if isinstance(base, int) else base
    return G.Species(tuple(types_), stats, 0, '', '', abilities=tuple(abilities))


class Power(unittest.TestCase):
    """power.py's combat power estimate."""

    MOVES = {
        'MOVE_HIT': G.Move('TYPE_NORMAL', 80, 100, 'DAMAGE_CATEGORY_PHYSICAL'),
        'MOVE_SPECIAL': G.Move('TYPE_NORMAL', 80, 100, 'DAMAGE_CATEGORY_SPECIAL'),
        'MOVE_GROWL': G.Move('TYPE_NORMAL', 0, 100, 'DAMAGE_CATEGORY_STATUS'),
    }

    @staticmethod
    def flat(level):
        return 80

    def test_the_reference_fights_at_its_own_level(self):
        for level in (5, 30, 70, 100):
            self.assertAlmostEqual(P.effective_level(P.reference(level, self.flat), self.flat), level, places=3)

    def test_stats_follow_the_formula_unrounded(self):
        st = P.stats(dict.fromkeys(G.STAT_FIELDS, 80), dict.fromkeys(G.IV_STATS, 15), 50)
        self.assertEqual(st['hp'], 147.5)  # (2 * 80 + 15) * 50 / 100 + 50 + 10
        self.assertEqual(st['atk'], 92.5)

    def test_move_power_counts_stab_accuracy_strikes_and_turns(self):
        gd = fake_regime()
        hit = G.Move('TYPE_FIRE', 100, 100, 'DAMAGE_CATEGORY_SPECIAL')
        replace = G.dataclasses.replace
        self.assertEqual(P.move_power(gd, hit, ('TYPE_WATER',)), 100)
        self.assertEqual(P.move_power(gd, hit, ('TYPE_FIRE',)), 150)
        self.assertEqual(P.move_power(gd, replace(hit, accuracy=80), ()), 80)
        self.assertEqual(P.move_power(gd, replace(hit, accuracy=0), ()), 100)  # never misses
        self.assertEqual(P.move_power(gd, replace(hit, strikes=2), ()), 200)
        self.assertAlmostEqual(P.move_power(fake_regime(B_MULTI_HIT_CHANCE='GEN_5'), replace(hit, multi_hit=True), ()), 310)
        self.assertEqual(P.move_power(fake_regime(B_MULTI_HIT_CHANCE='GEN_3'), replace(hit, multi_hit=True), ()), 300)
        self.assertEqual(P.move_power(gd, replace(hit, recharge=True), ()), 50)
        self.assertEqual(P.move_power(gd, replace(hit, effect='EFFECT_SOLAR_BEAM'), ()), 50)
        self.assertAlmostEqual(P.move_power(gd, replace(hit, effect='EFFECT_FUTURE_SIGHT'), ()), 100 / 3)
        self.assertAlmostEqual(P.move_power(gd, replace(hit, effect='EFFECT_POWER_BASED_ON_USER_HP'), ()), 60)
        self.assertEqual(P.move_power(gd, replace(hit, explosion=True), ()), 0)
        self.assertEqual(P.move_power(gd, replace(hit, effect='EFFECT_OHKO'), ()), 0)

    def test_better_stats_and_moves_raise_the_effective_level(self):
        species = {'SPECIES_WEAK': power_species(50), 'SPECIES_REF': power_species(80),
                   'SPECIES_STRONG': power_species(110)}
        gd = power_regime(species, self.MOVES)
        ivs = dict.fromkeys(G.IV_STATS, 15)

        def eff(sp, moves=('MOVE_HIT',)):
            return P.effective_level(P.fighter(gd, sp, 40, list(moves), ivs), self.flat)
        self.assertAlmostEqual(eff('SPECIES_REF'), 40, places=3)
        self.assertLess(eff('SPECIES_WEAK'), 40)
        self.assertGreater(eff('SPECIES_STRONG'), 40)
        self.assertIsNone(eff('SPECIES_REF', ['MOVE_GROWL']))

    def test_certain_abilities_change_the_fight(self):
        species = {'SPECIES_PLAIN': power_species(80, abilities=('ABILITY_NONE',)),
                   'SPECIES_LOAFS': power_species(80, abilities=('ABILITY_TRUANT', 'ABILITY_NONE', 'ABILITY_NONE')),
                   'SPECIES_STRONG': power_species(80, abilities=('ABILITY_PURE_POWER', 'ABILITY_NONE', 'ABILITY_X')),
                   'SPECIES_MAYBE': power_species(80, abilities=('ABILITY_THICK_FAT', 'ABILITY_HUGE_POWER'))}
        gd = power_regime(species, self.MOVES)
        ivs = dict.fromkeys(G.IV_STATS, 15)
        self.assertIsNone(P.certain_ability(species['SPECIES_MAYBE']))  # the hidden slot doesn't count
        plain = P.fighter(gd, 'SPECIES_PLAIN', 40, ['MOVE_HIT'], ivs)
        self.assertEqual(P.fighter(gd, 'SPECIES_LOAFS', 40, ['MOVE_HIT'], ivs).attacks[0][1], plain.attacks[0][1] / 2)
        self.assertEqual(P.fighter(gd, 'SPECIES_STRONG', 40, ['MOVE_HIT'], ivs).stats['atk'], plain.stats['atk'] * 2)
        self.assertEqual(P.fighter(gd, 'SPECIES_STRONG', 40, ['MOVE_SPECIAL'], ivs).stats['spa'], plain.stats['spa'])
        self.assertEqual(P.fighter(gd, 'SPECIES_MAYBE', 40, ['MOVE_HIT'], ivs).stats, plain.stats)

    def test_first_strike_is_even_at_equal_speed_and_smooth(self):
        self.assertEqual(P.first_strike(100, 100), 0.5)
        self.assertAlmostEqual(P.first_strike(110, 100) + P.first_strike(100, 110), 1)
        self.assertTrue(0.5 < P.first_strike(101, 100) < P.first_strike(110, 100) < 1)

    def test_the_reference_power_fit_recovers_a_log_line(self):
        species = {'SPECIES_X': power_species(80)}
        moves = {f'MOVE_{lv}': G.Move('TYPE_NORMAL', round(10 + 20 * P.math.log(lv)), 100, 'DAMAGE_CATEGORY_PHYSICAL')
                 for lv in (5, 20, 50, 90)}
        mons = [(G.TrainerMon('SPECIES_X', lv, [f'MOVE_{lv}']), [f'MOVE_{lv}']) for lv in (5, 20, 50, 90)]
        power_fn, intercept, slope = P.fit_reference_power(power_regime(species, moves), mons)
        self.assertAlmostEqual(intercept, 10, delta=0.5)
        self.assertAlmostEqual(slope, 20, delta=0.2)
        self.assertEqual(power_fn(1), P.MIN_REFERENCE_POWER)

    def test_the_explorer_loads_every_local_module(self):
        """The explorer copies a fixed list of files into Pyodide (model.js
        FILES), so each local module rebalance.py imports must be in it."""
        with open(os.path.join(G.HERE, 'explorer', 'model.js'), encoding='utf-8') as f:
            listed = set(re.findall(r"'/tools/rebalance/(\w+)\.py'", f.read()))
        pending, seen = ['rebalance'], set()
        while pending:
            name = pending.pop()
            seen.add(name)
            with open(os.path.join(G.HERE, name + '.py'), encoding='utf-8') as f:
                for mod in re.findall(r'^import (\w+)', f.read(), re.M):
                    if os.path.exists(os.path.join(G.HERE, mod + '.py')) and mod not in seen:
                        pending.append(mod)
        self.assertLessEqual(seen, listed)

    def test_nested_tokens_are_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'moves_info.h')
            with open(path, 'w', encoding='utf-8') as f:
                f.write('    [MOVE_BEAM] =\n    {\n        .power = 150,\n'
                        '        .additionalEffects = ADDITIONAL_EFFECTS({\n'
                        '            .moveEffect = MOVE_EFFECT_RECHARGE,\n        }),\n    },\n'
                        '    [MOVE_TACKLE] =\n    {\n        .power = 40,\n    },\n')
            table = G.parse_table(path, G.regime_defines(FIXTURE)['modern'], 'MOVE', ('power',),
                                  nested=('MOVE_EFFECT_RECHARGE',))
        self.assertEqual(table, {'MOVE_BEAM': {'power': 150, 'MOVE_EFFECT_RECHARGE': True},
                                 'MOVE_TACKLE': {'power': 40}})


def matchup_regime(species, moves, defaults, chart):
    """power_regime plus what matchup.py reads: the type chart, the moves and default movesets."""
    gd = power_regime(species, moves)
    gd.chart, gd.moves = chart, moves
    gd.default_moves = lambda sp, level: list(defaults.get(sp, ()))
    return gd


class Matchup(unittest.TestCase):
    """matchup.py's stand-in team and fights, and power.py's typed score."""

    CHART = {'TYPE_WATER': {'TYPE_FIRE': 2.0, 'TYPE_GRASS': 0.5},
             'TYPE_GRASS': {'TYPE_WATER': 2.0, 'TYPE_FIRE': 0.5},
             'TYPE_FIRE': {'TYPE_GRASS': 2.0, 'TYPE_WATER': 0.5},
             'TYPE_GHOST': {'TYPE_NORMAL': 0.0}}
    MOVES = {
        'MOVE_SURF': G.Move('TYPE_WATER', 80, 100, 'DAMAGE_CATEGORY_SPECIAL'),
        'MOVE_WATER_GUN': G.Move('TYPE_WATER', 40, 100, 'DAMAGE_CATEGORY_SPECIAL'),
        'MOVE_LEAF': G.Move('TYPE_GRASS', 80, 100, 'DAMAGE_CATEGORY_SPECIAL'),
        'MOVE_EMBER': G.Move('TYPE_FIRE', 80, 100, 'DAMAGE_CATEGORY_SPECIAL'),
        'MOVE_QUAKE': G.Move('TYPE_GROUND', 100, 100, 'DAMAGE_CATEGORY_PHYSICAL'),
        'MOVE_NIGHT_SHADE': G.Move('TYPE_GHOST', 1, 100, 'DAMAGE_CATEGORY_SPECIAL', effect='EFFECT_LEVEL_DAMAGE'),
        'MOVE_GROWL': G.Move('TYPE_NORMAL', 0, 100, 'DAMAGE_CATEGORY_STATUS'),
    }
    IVS = dict.fromkeys(G.IV_STATS, 15)

    def regime(self, species, defaults=None):
        return matchup_regime(species, self.MOVES, defaults or {}, self.CHART)

    def test_the_typed_score_counts_the_chart_and_certain_immunities(self):
        gd = self.regime({'SPECIES_WATER': power_species(80, ('TYPE_WATER',)),
                          'SPECIES_FIRE': power_species(80, ('TYPE_FIRE',)),
                          'SPECIES_NORMAL': power_species(80, ('TYPE_NORMAL',)),
                          'SPECIES_FLOAT': power_species(80, ('TYPE_FIRE',), ('ABILITY_LEVITATE', 'ABILITY_NONE'))})
        water = P.fighter(gd, 'SPECIES_WATER', 50, ['MOVE_SURF'], self.IVS)
        fire = P.fighter(gd, 'SPECIES_FIRE', 50, ['MOVE_EMBER'], self.IVS)
        self.assertAlmostEqual(P.expected_damage(water, fire, self.CHART), 2 * P.expected_damage(water, fire))
        self.assertGreater(P.score(water, fire, self.CHART), P.score(water, fire))
        # Levitate is certain, so Ground does nothing to it, but only with the chart.
        quake = P.fighter(gd, 'SPECIES_NORMAL', 50, ['MOVE_QUAKE'], self.IVS)
        floater = P.fighter(gd, 'SPECIES_FLOAT', 50, ['MOVE_EMBER'], self.IVS)
        self.assertEqual(floater.immune, {'TYPE_GROUND'})
        self.assertEqual(P.expected_damage(quake, floater, self.CHART), 0)
        self.assertGreater(P.expected_damage(quake, floater), 0)
        # Night Shade does its level to anything it can hit, and nothing to a Normal type.
        shade = P.fighter(gd, 'SPECIES_FIRE', 50, ['MOVE_NIGHT_SHADE'], self.IVS)
        self.assertEqual(P.expected_damage(shade, water, self.CHART), 50)
        self.assertEqual(P.expected_damage(shade, quake, self.CHART), 0)

    def test_attacks_that_need_a_state_of_their_own_score_nothing(self):
        punch = G.Move('TYPE_FIGHTING', 150, 100, 'DAMAGE_CATEGORY_PHYSICAL', effect='EFFECT_FOCUS_PUNCH')
        self.assertEqual(P.move_power(fake_regime(), punch, ('TYPE_FIGHTING',)), 0)

    def test_moves_are_picked_for_coverage(self):
        gd = self.regime({'SPECIES_WATER': power_species(80, ('TYPE_WATER',))},
                         {'SPECIES_WATER': ['MOVE_WATER_GUN', 'MOVE_SURF', 'MOVE_GROWL']})
        targets = ['TYPE_FIRE', 'TYPE_GRASS', 'TYPE_WATER']
        # Surf (STAB) first; then Ember, which gains more on Grass than Leaf gains on Water.
        self.assertEqual(M.pick_moves(gd, 'SPECIES_WATER', 50, self.IVS, ['MOVE_LEAF', 'MOVE_EMBER'], 2, targets),
                         ['MOVE_SURF', 'MOVE_EMBER'])
        # No status moves, and never more than the attacks there are.
        self.assertEqual(sorted(M.pick_moves(gd, 'SPECIES_WATER', 50, self.IVS, [], 4, targets)),
                         ['MOVE_SURF', 'MOVE_WATER_GUN'])

    def team_regime(self):
        species = {'SPECIES_SEED': power_species(60, ('TYPE_GRASS',)),
                   'SPECIES_TREE': power_species(90, ('TYPE_GRASS',)),
                   'SPECIES_PUDDLE': power_species(40, ('TYPE_WATER',)),
                   'SPECIES_LAKE': power_species(85, ('TYPE_WATER',)),
                   'SPECIES_FIRE': power_species(70, ('TYPE_FIRE',)),
                   'SPECIES_GRASSY': power_species(100, ('TYPE_GRASS',)),
                   'SPECIES_BANNED': power_species(120, ('TYPE_NORMAL',)),
                   'SPECIES_MUTE': power_species(110, ('TYPE_NORMAL',))}
        defaults = {'SPECIES_TREE': ['MOVE_LEAF'], 'SPECIES_LAKE': ['MOVE_SURF'], 'SPECIES_FIRE': ['MOVE_EMBER'],
                    'SPECIES_GRASSY': ['MOVE_LEAF'], 'SPECIES_BANNED': ['MOVE_QUAKE'], 'SPECIES_MUTE': ['MOVE_GROWL']}
        return self.regime(species, defaults)

    @staticmethod
    def evolve(species, level):
        return {'SPECIES_SEED': 'SPECIES_TREE', 'SPECIES_PUDDLE': 'SPECIES_LAKE'}.get(species, species) \
            if level >= 16 else species

    def team(self, stage_index, **settings):
        settings = {'team_size': 6, 'catches_per_stage': 1, 'ivs': 15, 'moves': 4, 'exclude': ['SPECIES_BANNED'],
                    **settings}
        seen = {'SPECIES_PUDDLE', 'SPECIES_FIRE', 'SPECIES_GRASSY', 'SPECIES_BANNED', 'SPECIES_MUTE'}
        team = M.stand_in_team(self.team_regime(), settings, stage_index, [20, 18, 18, 18, 18, 18], 'SPECIES_SEED',
                               seen, [], {}, self.evolve, ['TYPE_FIRE', 'TYPE_GRASS', 'TYPE_WATER'])
        return [(p['species'], p['level']) for p in team]

    def test_the_stand_in_team_takes_new_types_first(self):
        # The starter at the lead's level, evolved; catches_per_stage per earlier stage, at the bench's.
        self.assertEqual(self.team(0), [('SPECIES_TREE', 20)])
        self.assertEqual(self.team(1), [('SPECIES_TREE', 20), ('SPECIES_LAKE', 18)])
        # Excluded and attackless species never go in; a type the team has waits for the fill-up.
        self.assertEqual(self.team(2), [('SPECIES_TREE', 20), ('SPECIES_LAKE', 18), ('SPECIES_FIRE', 18)])
        self.assertEqual(self.team(1, catches_per_stage=3),
                         [('SPECIES_TREE', 20), ('SPECIES_LAKE', 18), ('SPECIES_FIRE', 18), ('SPECIES_GRASSY', 18)])
        self.assertEqual(len(self.team(5, catches_per_stage=3, team_size=3)), 3)

    def test_fight_readings(self):
        gd = self.team_regime()
        team = [M.stand_in(gd, 'SPECIES_LAKE', 50, self.IVS, [], {}, 4, ['TYPE_FIRE'])]
        trainer = G.Trainer('TRAINER_X', 'X', 'Leader', [], False,
                            [G.TrainerMon('SPECIES_FIRE', 50, ['MOVE_EMBER']),
                             G.TrainerMon('SPECIES_TREE', 50, ['MOVE_LEAF'])])
        out = M.fight(gd, team, trainer)
        fire, tree = out['answers']
        self.assertGreater(fire['answer'], M.ANSWERED)
        self.assertLess(tree['answer'], M.ANSWERED)
        self.assertEqual((out['hardest'], out['lead'], out['coverage']), (tree, fire, 1))
        self.assertEqual(fire['by'], 'SPECIES_LAKE')

    def test_rival_teams_follow_the_starter(self):
        trainers = dict.fromkeys(('TRAINER_MAY_X_MUDKIP', 'TRAINER_MAY_X_TREECKO', 'TRAINER_LEADER'))
        starters = ('TREECKO', 'TORCHIC', 'MUDKIP')
        self.assertEqual(M.starter_boss('TRAINER_MAY_X_MUDKIP', 'TREECKO', starters, trainers), 'TRAINER_MAY_X_TREECKO')
        self.assertIsNone(M.starter_boss('TRAINER_MAY_X_MUDKIP', 'TORCHIC', starters, trainers))
        self.assertEqual(M.starter_boss('TRAINER_LEADER', 'TORCHIC', starters, trainers), 'TRAINER_LEADER')

    def test_open_tms_are_those_of_earlier_stages(self):
        map_tms = {'RouteA': [('ITEM_TM_LEAF', 'ball')], 'TownB': [('ITEM_TM_EMBER', 'script')],
                   'TownB_Corner': [('ITEM_TM_QUAKE', 'script')]}
        stages = [{'maps': ['RouteA']}, {'maps': ['TownB*']}, {'maps': ['Later']}]
        self.assertEqual(M.open_tms(map_tms, stages, 0, ()), [])
        self.assertEqual(M.open_tms(map_tms, stages, 1, ()), ['MOVE_LEAF'])
        self.assertEqual(M.open_tms(map_tms, stages, 2, ('TownB_Corner',)), ['MOVE_EMBER', 'MOVE_LEAF'])


class Analysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = RB.analyze(FIXTURE, FIXTURE_STAGES, FIXTURE_FORCED)

    def test_matchup_skips_starters_the_data_lacks(self):
        self.assertEqual(self.res['matchup'], {'starters': [], 'fights': []})

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
        self.assertTrue(on_cfg.flag('B_TRAINER_EXP_MULTIPLIER <= GEN_6'))
        self.assertFalse(gd.flag('B_TRAINER_EXP_MULTIPLIER <= GEN_6'))  # the original is untouched
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
        info = types.SimpleNamespace(evolve=lambda sp, lvl, gender=None, nonlevel=False: 'SPECIES_NOT_THERE' if lvl > 50 else sp)
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
                      {'overlevel_cutoff': 10, 'overlevel_unit': 'percent', 'overlevel_width': 5, 'overlevel_floor': 15,
                       'overlevel_min_level': 17, 'gap_unit': 'percent', 'margin': 5, 'trainer_gap': 10, 'wild_gap': 20}):
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
            self.assertIn('skip reference', text.getvalue())  # the data has the forced trainers (#350)
            knobs = os.path.join(out, 'knobs.json')
            with open(knobs, 'w', encoding='utf-8') as f:
                f.write('{"margin": 1}')
            text = io.StringIO()
            with contextlib.redirect_stdout(text):
                self.assertEqual(RB.main(['curve', knobs, '--data', data]), 0)
            self.assertIn('Lv 100 by: -', text.getvalue())

    def test_report_has_two_players_section(self):
        # The skip player passes the hiker by, so it meets the rival lower, and skips Leader X.
        rival, leader = self.res['two_players']
        self.assertEqual((rival['boss'], leader['boss']), ('TRAINER_RIVAL_A', 'TRAINER_LEADER_X'))
        self.assertLess(rival['skip'], rival['full'])
        self.assertEqual(rival['skip_pct'], round((rival['skip'] - rival['ace']) * 100 / rival['ace'], 1))
        self.assertIsNone(leader['skip'])
        self.assertIsNone(leader['skip_pct'])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'report.md')
            RB.write_report(path, self.res)
            with open(path, encoding='utf-8') as f:
                section = f.read().split('## Two players\n', 1)[1].split('\n## ', 1)[0]
        self.assertIn('| boss | ace | full lead | % | skip lead | % | flag |', section)
        pct = (rival['full'] - rival['ace']) * 100 / rival['ace']
        self.assertIn(f"| Rival A | {rival['ace']} | {rival['full']} | {pct:+.0f}% | {rival['skip']} |", section)
        self.assertIn(f"| Leader X | {leader['ace']} | {leader['full']} |", section)
        self.assertIn('| skipped | - |  |', section)

    def test_outlier_flag_at_25_percent(self):
        def row(bid, ace, full, skip, stage='One'):
            return {'stage': stage, 'boss': bid, 'boss_ace': ace, 'levels': [full, 1],
                    'skip_levels': None if skip is None else [skip, 1]}
        stages = [{'name': 'One', 'bosses': ['TRAINER_A', 'TRAINER_B', 'TRAINER_C', 'TRAINER_D']}]
        rows = RB.two_players([row('TRAINER_A', 100, 110, 75), row('TRAINER_B', 100, 110, 74),
                               row('TRAINER_C', 38, 39, 26), row('TRAINER_D', 20, 22, None),
                               row('TRAINER_STEVEN', 100, 90, 10, 'Post-game')], stages)
        self.assertEqual(RB.OUTLIER_SKIP, 25)
        self.assertEqual([r['boss'] for r in rows], ['TRAINER_A', 'TRAINER_B', 'TRAINER_C', 'TRAINER_D'])
        self.assertEqual([r['skip_pct'] for r in rows], [-25.0, -26.0, -31.6, None])
        self.assertEqual([r['full_pct'] for r in rows], [10.0, 10.0, 2.6, 10.0])
        # More than 25% under: -25% exactly is not flagged; Tabitha at Mt Chimney's -32% is.
        self.assertEqual([r['outlier'] for r in rows], [False, True, True, False])


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

    def test_nonlevel_evolve_party(self):
        party = ('=== TRAINER_C ===\nName: C\n\nDusclops\nLevel: 77\n\nBanette\nLevel: 78\n\n'
                 'Ghost (Dusclops) (F) @ Sitrus Berry\nLevel: 80\n\n'
                 '=== TRAINER_D ===\nName: D\n\nGolbat\nLevel: 60\n\n' + self.PARTY.split('*/\n', 1)[1])
        evolve = {('SPECIES_DUSCLOPS', 77): 'SPECIES_DUSKNOIR', ('SPECIES_DUSCLOPS', 80): 'SPECIES_DUSKNOIR',
                  ('SPECIES_GOLBAT', 60): 'SPECIES_CROBAT', ('SPECIES_RALTS', 16): 'SPECIES_KIRLIA',
                  ('SPECIES_MR_MIME', 40): 'SPECIES_MR_RIME'}

        def evolver(species, level, gender=None):
            return evolve.get((species, level), species)
        teams = {'TRAINER_C', 'TRAINER_WALLY_MAUVILLE', 'PARTNER_B'}
        text, evolved = RB.nonlevel_evolve_party(party, teams, evolver)
        # Of two copies the higher level evolves, keeping its nickname, gender and item; teams
        # outside ``teams``, EVOLVE_EXEMPT's and the partners keep theirs; levels never move.
        self.assertEqual(text, party.replace('Ghost (Dusclops) (F)', 'Ghost (Dusknoir) (F)'))
        self.assertEqual(evolved, [('TRAINER_C', 'SPECIES_DUSCLOPS', 'SPECIES_DUSKNOIR', 80)])
        self.assertEqual(RB.nonlevel_evolve_party(text, teams, evolver), (text, []))  # idempotent

    # Lowering (#350): a real SpeciesInfo, and a regime's species list.
    GD = types.SimpleNamespace(species={'SPECIES_TREECKO', 'SPECIES_GROVYLE', 'SPECIES_SCEPTILE', 'SPECIES_ARON'})

    @classmethod
    def setUpClass(cls):
        cls.info = G.R.SpeciesInfo(G.REPO)
        cls.devolve = staticmethod(RB.devolver(cls.info, cls.GD))

    def test_lowered_grovyle_devolves_below_grace(self):
        # Grovyle 18 lowered by 2 is 16, under 16 + EVOLVE_GRACE: Treecko.
        self.assertEqual(RB.evolve_team([('SPECIES_GROVYLE', 18, None)], -2, None, devolve=self.devolve),
                         ['SPECIES_TREECKO'])
        # Without devolve, a lowered team keeps its species.
        self.assertEqual(RB.evolve_team([('SPECIES_GROVYLE', 18, None)], -2, None), ['SPECIES_GROVYLE'])

    def test_lowered_grovyle_kept_at_grace(self):
        self.assertEqual(RB.evolve_team([('SPECIES_GROVYLE', 22, None)], -2, None, devolve=self.devolve),
                         ['SPECIES_GROVYLE'])
        self.assertEqual(self.devolve('SPECIES_GROVYLE', 19), 'SPECIES_GROVYLE')
        self.assertEqual(self.devolve('SPECIES_GROVYLE', 18), 'SPECIES_TREECKO')

    def test_devolve_without_pre_evolution_keeps_species(self):
        # Review Focus 1: no pre-evolution (Aron), or one the regime doesn't have: only the level drops.
        self.assertEqual(self.devolve('SPECIES_ARON', 1), 'SPECIES_ARON')
        no_treecko = RB.devolver(self.info, types.SimpleNamespace(species={'SPECIES_GROVYLE'}))
        self.assertEqual(no_treecko('SPECIES_GROVYLE', 5), 'SPECIES_GROVYLE')
        # The fitting base missing: the nearest form back up the line that the regime has.
        no_base = RB.devolver(self.info, types.SimpleNamespace(species={'SPECIES_GROVYLE', 'SPECIES_SCEPTILE'}))
        self.assertEqual(no_base('SPECIES_SCEPTILE', 5), 'SPECIES_GROVYLE')
        party ='=== TRAINER_C ===\nName: C\n\nAron\nLevel: 20\n\nGrovyle\nLevel: 20\n'
        text, devolved = RB.raise_party(party, {'TRAINER_C': -10}, devolve=no_treecko)
        self.assertEqual(text, party.replace('Level: 20', 'Level: 10'))
        self.assertEqual(devolved, [])

    def test_level_floor_is_1(self):
        party = '=== TRAINER_C ===\nName: C\n\nAron\nLevel: 5\n'
        self.assertEqual(RB.raise_party(party, {'TRAINER_C': -10}, devolve=self.devolve),
                         (party.replace('Level: 5', 'Level: 1'), []))
        # A lowered wild slot never devolves (restock doesn't).
        slots = [('land_mons', {'species': 'SPECIES_SCEPTILE', 'min_level': 3, 'max_level': 40}, 60)]
        self.assertEqual(RB.shifted_slots(slots, -10)[0][1],
                         {'species': 'SPECIES_SCEPTILE', 'min_level': 1, 'max_level': 30})
        seen = []
        RB.evolve_team([('SPECIES_ARON', 5, None)], -10, None,
                       devolve=lambda sp, level, taken=(): seen.append(level) or sp)
        self.assertEqual(seen, [1])

    def test_lowered_wild_offset_is_what_restock_writes(self):
        # Abandoned Ship's case: vanilla Tentacruel 20-30 and Tentacool 30-35. At +6 the Tentacool
        # evolved (36 >= 30 + 3); at +2 restock rebuilds from vanilla: Tentacool again, and the
        # vanilla Tentacruel stays one at 22, though below Tentacool's evolution level + grace.
        gd = types.SimpleNamespace(species={'SPECIES_TENTACOOL', 'SPECIES_TENTACRUEL'})
        vanilla = [('fishing_mons', {'species': 'SPECIES_TENTACRUEL', 'min_level': 20, 'max_level': 30}, 60),
                   ('fishing_mons', {'species': 'SPECIES_TENTACOOL', 'min_level': 30, 'max_level': 35}, 40)]
        evolve = RB.evolver(self.info, gd)
        for offset, want in ((6, ['SPECIES_TENTACRUEL', 'SPECIES_TENTACRUEL']),
                             (2, ['SPECIES_TENTACRUEL', 'SPECIES_TENTACOOL']),
                             (0, ['SPECIES_TENTACRUEL', 'SPECIES_TENTACOOL'])):
            got = RB.restocked_slots(vanilla, offset, evolve, gd.species)
            self.assertEqual([s['species'] for _, s, _ in got], want, offset)
            self.assertEqual([(f, s['min_level'], s['max_level'], r) for f, s, r in got],
                             [(f, s['min_level'] + offset, s['max_level'] + offset, r) for f, s, r in vanilla])
            # Pinned to restock's own shift_levels with the real SpeciesInfo.
            wild = {'wild_encounter_groups': [{'label': 'gWildMonHeaders', 'encounters': [
                {'map': 'MAP_X', 'fishing_mons': {'mons': [dict(s) for _, s, _ in vanilla]}}]}]}
            G.R.shift_levels(wild, {'MAP_X': {'fishing_mons': offset}}, self.info)
            self.assertEqual([s for _, s, _ in got], wild['wild_encounter_groups'][0]['encounters'][0]
                             ['fishing_mons']['mons'])
        self.assertEqual(vanilla[1][1]['min_level'], 30)  # vanilla untouched

    def test_raise_party_lowers_text_and_reports_devolutions(self):
        party = ('=== TRAINER_C ===\nName: C\n\nLeaf (Grovyle) (M) @ Oran Berry\nLevel: 18\n- Tackle\n\n'
                 'Aron\nLevel: 30\n\n'
                 '=== TRAINER_WALLY_MAUVILLE ===\nName: WALLY\n\nGrovyle\nLevel: 18\n\n'
                 '=== PARTNER_B ===\nName: B\n\nGrovyle\nLevel: 18\n')
        lower = {'TRAINER_C': -2, 'TRAINER_WALLY_MAUVILLE': -2, 'PARTNER_B': -2}
        text, devolved = RB.raise_party(party, lower, devolve=self.devolve)
        # The nickname, gender and item stay; EVOLVE_EXEMPT's and the partner's Grovyle only drop.
        self.assertEqual(text, party.replace('Leaf (Grovyle) (M)', 'Leaf (Treecko) (M)')
                         .replace('Level: 18', 'Level: 16').replace('Level: 30', 'Level: 28'))
        self.assertEqual(devolved, [('TRAINER_C', 'SPECIES_GROVYLE', 'SPECIES_TREECKO', 16)])
        self.assertEqual(G.parse_trainers_text(text)['TRAINER_C'].mons[0].species, 'SPECIES_TREECKO')

    def test_unique_team_never_devolves_into_a_duplicate(self):
        # A boss team keeps the species it would duplicate, and the report says so (before == after).
        party = '=== TRAINER_C ===\nName: C\n\nTreecko\nLevel: 10\n\nGrovyle\nLevel: 18\n'
        text, devolved = RB.raise_party(party, {'TRAINER_C': -2}, devolve=self.devolve, unique={'TRAINER_C'})
        self.assertEqual(text, party.replace('Level: 10', 'Level: 8').replace('Level: 18', 'Level: 16'))
        self.assertEqual(devolved, [('TRAINER_C', 'SPECIES_GROVYLE', 'SPECIES_GROVYLE', 16)])
        # The fitting form taken, an intermediate one that is free: Sceptile 10 beside Treecko is Grovyle.
        party = '=== TRAINER_C ===\nName: C\n\nTreecko\nLevel: 10\n\nSceptile\nLevel: 40\n'
        text, devolved = RB.raise_party(party, {'TRAINER_C': -30}, devolve=self.devolve, unique={'TRAINER_C'})
        self.assertEqual(text, '=== TRAINER_C ===\nName: C\n\nTreecko\nLevel: 1\n\nGrovyle\nLevel: 10\n')
        self.assertEqual(devolved, [('TRAINER_C', 'SPECIES_SCEPTILE', 'SPECIES_GROVYLE', 10)])
        # Two evolved Pokemon devolving to one base: the ace (Sceptile 40) takes it, as in
        # nonlevel_evolve_party, and the Grovyle has no other form, so it stays.
        party = '=== TRAINER_C ===\nName: C\n\nGrovyle\nLevel: 18\n\nSceptile\nLevel: 40\n'
        text, devolved = RB.raise_party(party, {'TRAINER_C': -30}, devolve=self.devolve, unique={'TRAINER_C'})
        self.assertEqual(text, '=== TRAINER_C ===\nName: C\n\nGrovyle\nLevel: 1\n\nTreecko\nLevel: 10\n')
        self.assertEqual(devolved, [('TRAINER_C', 'SPECIES_GROVYLE', 'SPECIES_GROVYLE', 1),
                                    ('TRAINER_C', 'SPECIES_SCEPTILE', 'SPECIES_TREECKO', 10)])
        # On a tie of levels the last slot goes first.
        party = '=== TRAINER_C ===\nName: C\n\nGrovyle\nLevel: 18\n\nGrovyle\nLevel: 18\n'
        text, _ = RB.raise_party(party, {'TRAINER_C': -2}, devolve=self.devolve, unique={'TRAINER_C'})
        self.assertEqual(text, '=== TRAINER_C ===\nName: C\n\nGrovyle\nLevel: 16\n\nTreecko\nLevel: 16\n')
        # Not a unique team: both devolve.
        _, devolved = RB.raise_party(party, {'TRAINER_C': -30}, devolve=self.devolve)
        self.assertEqual([d[2] for d in devolved], ['SPECIES_TREECKO', 'SPECIES_TREECKO'])

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

    def test_every_rival_fight_has_a_team_per_starter(self):
        """matchup.py swaps the starter suffix of the staged rival teams."""
        trainers = G.parse_trainers(os.path.join(G.REPO, 'src', 'data', 'trainers.party'))
        stages = RB.load_stages(RB.DEFAULT_STAGES, trainers, G.REPO)
        starters = M.load_settings()['starters']
        for bid in (b for st in stages for b in st['bosses']):
            for s in starters:
                self.assertIsNotNone(M.starter_boss(bid, s, starters, trainers), (bid, s))

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
        # The move and species fields power.py reads.
        self.assertTrue(m.moves['MOVE_HYPER_BEAM'].recharge)
        self.assertFalse(m.moves['MOVE_TACKLE'].recharge)
        self.assertEqual(m.moves['MOVE_DOUBLE_KICK'].strikes, 2)
        self.assertTrue(m.moves['MOVE_FURY_ATTACK'].multi_hit)
        self.assertTrue(m.moves['MOVE_EXPLOSION'].explosion)
        self.assertEqual(P.certain_ability(m.species['SPECIES_SLAKING']), 'ABILITY_TRUANT')
        self.assertIsNone(P.certain_ability(m.species['SPECIES_AZUMARILL']))
        # Fixed-damage moves are attacks but never STAB.
        self.assertTrue(RB.attacks(m, ['MOVE_SEISMIC_TOSS']))
        self.assertFalse(RB.has_stab(m, 'SPECIES_HARIYAMA', ['MOVE_SEISMIC_TOSS']))
        self.assertTrue(RB.has_stab(m, 'SPECIES_HARIYAMA', ['MOVE_ARM_THRUST']))

    def test_set_moves_are_learnable(self):
        """Every set move in trainers.party and battle_partners.party is one its Pokemon can learn
        (#145): a level-up move at or below its level, an evolution move, a teachable or an egg
        move, of the species or a pre-evolution. move_allowlist.json lists the upstream Gen 3
        moves that break the rule; an entry that no longer breaks it has to go."""
        gd = G.GameData(G.REPO, G.regime_defines(G.REPO)['modern'])
        teams = G.parse_trainers(os.path.join(G.REPO, 'src', 'data', 'trainers.party'))
        teams.update(G.parse_trainers(os.path.join(G.REPO, 'src', 'data', 'battle_partners.party')))
        bad = set(RB.unlearnable_set_moves(teams, gd, G.R.SpeciesInfo(G.REPO), G.move_lists(G.REPO)))
        with open(RB.MOVE_ALLOWLIST, encoding='utf-8') as f:
            allowed = {tuple(s) for group in json.load(f).values() for s in group['moves']}
        self.assertEqual(sorted(bad - allowed), [], 'set moves the Pokemon cannot learn')
        self.assertEqual(sorted(allowed - bad), [], 'allowlisted moves that are now learnable or gone')

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
        self.assertEqual(list(RB.LOGISTIC), G.parse_scaling_factors(G.REPO, 'sExpLogistic', 'exp_formula.c'))
        gd = G.load(G.REPO)
        self.assertEqual(RB.Overlevel.from_configs(gd['modern']), RB.Overlevel(15, True, 4, 10, 17))
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
        live = RB.repo_inputs(G.REPO, RB.DEFAULT_STAGES, G.R.SpeciesInfo(G.REPO))
        self.assertTrue(live['forced'])
        with open(os.path.join(RB.DEFAULT_OUT_DIR, RB.CURVE_DATA), encoding='utf-8') as f:
            snap = RB.load_snapshot(json.load(f))
        for knobs in ({}, {'ko_takers': 6, 'boss_ref': 'party_mean', 'margin': 1, 'trainer_gap': 5, 'wild_gap': 10},
                      {'scaled_exp': False, 'trainer_exp': '1.5x on', 'affection': 'always', 'wild_battles': 5},
                      {'margin': 5, 'gap_unit': 'percent', 'trainer_gap': 10, 'rematch_step': 5},
                      # #350: the two players, lowering (and devolving) the bosses and trainers.
                      {'full_margin': 10, 'skip_margin': 15, 'lower': True, 'gap_unit': 'percent',
                       'trainer_gap': 10, 'wild_gap': 20}):
            self.assertEqual(RB.explore_run(snap, knobs), RB.explore_run(live, knobs), knobs)

    def test_stage_bosses_exist(self):
        trainers = G.parse_trainers(os.path.join(G.REPO, 'src', 'data', 'trainers.party'))
        stages = RB.load_stages(RB.DEFAULT_STAGES, trainers, G.REPO)
        self.assertTrue(all(st['bosses'] for st in stages))

    def test_smart_ai_bosses_send_their_ace_last(self):
        """Every Smart Switching team (#129's bosses) holds back its ace (#144): Ace Pokemon, or
        Double Ace Pokemon for Tate and Liza, and the reserved last slots are the team's highest level.
        On a level tie the Magma or Aqua signature line goes last."""
        trainers = G.parse_trainers(os.path.join(G.REPO, 'src', 'data', 'trainers.party'))
        bosses = [t for t in trainers.values() if 'Smart Switching' in t.ai]
        self.assertTrue(bosses)
        for t in bosses:
            aces = 2 if 'Double Ace Pokemon' in t.ai else 1 if 'Ace Pokemon' in t.ai else 0
            self.assertTrue(aces, t.id)
            levels = [mon.level for mon in t.mons]
            self.assertEqual(min(levels[-aces:]), max(levels), t.id)
        for tid, ace in [('TRAINER_TABITHA_MT_CHIMNEY', 'SPECIES_CAMERUPT'),
                         ('TRAINER_SHELLY_WEATHER_INSTITUTE', 'SPECIES_SHARPEDO'),
                         ('TRAINER_SHELLY_SEAFLOOR_CAVERN', 'SPECIES_SHARPEDO')]:
            self.assertEqual(trainers[tid].mons[-1].species, ace, tid)

    def test_boss_teams_take_nonlevel_evolutions(self):
        """Every boss and rival team has taken the evolutions that aren't by level (#181), except
        where the team already has the species: Phoebe's lead Dusclops beside her Dusknoir ace,
        Glacia's Sealeo beside her Walrein, Drake's Shelgon beside his Salamence."""
        trainers = G.parse_trainers(os.path.join(G.REPO, 'src', 'data', 'trainers.party'))
        stages = RB.load_stages(RB.DEFAULT_STAGES, trainers, G.REPO)
        teams = set(RB.boss_teams(stages, RB.rematch_ladders(G.parse_rematches(G.REPO), stages, trainers)))
        info, gd = G.R.SpeciesInfo(G.REPO), G.load(G.REPO)['modern']
        rows = RB.nonlevel_candidates(trainers, teams, RB.evolver(info, gd), RB.evolver(info, gd, nonlevel=True))
        held = [r for r in rows if r['boss']]
        for r in held:
            self.assertIn(r['to'], [mon.species for mon in trainers[r['trainer']].mons], r)
        self.assertEqual(sorted((r['trainer'], r['species']) for r in held), [
            ('TRAINER_DRAKE', 'SPECIES_SHELGON'), ('TRAINER_GLACIA', 'SPECIES_SEALEO'),
            ('TRAINER_GLACIA', 'SPECIES_SEALEO'), ('TRAINER_PHOEBE', 'SPECIES_DUSCLOPS')])
        self.assertEqual(trainers['TRAINER_PHOEBE'].mons[-1].species, 'SPECIES_DUSKNOIR')

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


class RealMoveReplacement(unittest.TestCase):
    """replacement_move on #160's worked examples (docs/fork/balance.md), and
    rewrite_unlearnable on the committed teams, in the real data."""

    @classmethod
    def setUpClass(cls):
        cls.gd = G.GameData(G.REPO, G.regime_defines(G.REPO)['modern'])
        cls.info = G.R.SpeciesInfo(G.REPO)
        cls.lists = G.move_lists(G.REPO)

    def replace(self, species, level, replaced, kept):
        return RB.replacement_move(self.gd, self.info, self.lists, species, level, replaced, kept)

    def test_replacement_keeps_the_replaced_type(self):
        # Madeline 2's Camerupt (Fire/Ground) loses Magnitude and keeps no other Ground attack:
        # the Earthquake TM outscores Earth Power (#160 hand-picked Earth Power here).
        self.assertEqual(self.replace('SPECIES_CAMERUPT', 38, 'MOVE_MAGNITUDE',
                                      ['MOVE_EMBER', 'MOVE_TACKLE', 'MOVE_SUNNY_DAY']), 'MOVE_EARTHQUAKE')
        # Braxton's Shiftry (Grass/Dark) loses Feint Attack: a Dark move, not a stronger Grass one.
        self.assertEqual(self.gd.moves[self.replace('SPECIES_SHIFTRY', 50, 'MOVE_FEINT_ATTACK',
                                                    ['MOVE_GIGA_DRAIN', 'MOVE_DOUBLE_TEAM', 'MOVE_SWAGGER'])].type,
                         'TYPE_DARK')

    def test_replacement_prefers_level_up_at_30_or_below(self):
        # Roxanne's Geodude 13: Bulldoze over the stronger Earthquake and Rock Slide TMs.
        self.assertEqual(self.replace('SPECIES_GEODUDE', 13, 'MOVE_ROCK_THROW',
                                      ['MOVE_TACKLE', 'MOVE_DEFENSE_CURL', 'MOVE_ROCK_TOMB']), 'MOVE_BULLDOZE')
        # Wattson's Voltorb and Magneton: Thunder Shock beats the physical Spark on their Special Attack.
        self.assertEqual(self.replace('SPECIES_VOLTORB', 22, 'MOVE_SELF_DESTRUCT',
                                      ['MOVE_ROLLOUT', 'MOVE_CHARGE_BEAM', 'MOVE_SHOCK_WAVE']), 'MOVE_THUNDER_SHOCK')
        self.assertEqual(self.replace('SPECIES_MAGNETON', 24, 'MOVE_SONIC_BOOM',
                                      ['MOVE_SUPERSONIC', 'MOVE_SHOCK_WAVE', 'MOVE_THUNDER_WAVE']),
                         'MOVE_THUNDER_SHOCK')

    def test_replacement_is_never_an_hm(self):
        # Lucas 2's Wailmer at 9 learns no Water move by level up: Water Pulse from the TMs, not Surf.
        self.assertEqual(self.replace('SPECIES_WAILMER', 9, 'MOVE_WATER_GUN', ['MOVE_SPLASH']), 'MOVE_WATER_PULSE')

    def test_rewrite_unlearnable_changes_nothing_today(self):
        """move_allowlist.json is empty since #160, so every committed set move is learnable."""
        for name in ('trainers.party', 'battle_partners.party'):
            with open(os.path.join(G.REPO, 'src', 'data', name), encoding='utf-8') as f:
                text = f.read()
            self.assertEqual(RB.rewrite_unlearnable(text, self.gd, self.info, self.lists), (text, []), name)


class TwoPlayers(unittest.TestCase):
    FORCED = FIXTURE_FORCED

    @staticmethod
    def stages():
        return [
            {'name': 'One', 'regular': ['TRAINER_A', 'TRAINER_B', 'TRAINER_C'], 'bosses': ['TRAINER_RIVAL_A']},
            {'name': 'Two', 'regular': ['TRAINER_D', 'TRAINER_E'], 'bosses': ['TRAINER_LEADER_X']},
        ]

    def test_load_forced_takes_one_of_each_group(self):
        forced = RB.load_forced(self.FORCED)
        self.assertEqual(forced.trainers, frozenset({'TRAINER_A', 'TRAINER_C'}))
        self.assertEqual(forced.optional_bosses, frozenset({'TRAINER_LEADER_X'}))

    def test_skip_stages_drops_optional_bosses_and_skippable_trainers(self):
        out = RB.skip_stages(self.stages(), RB.load_forced(self.FORCED))
        self.assertEqual([st['regular'] for st in out], [['TRAINER_A', 'TRAINER_C'], []])
        self.assertEqual([st['bosses'] for st in out], [['TRAINER_RIVAL_A'], []])

    def test_skip_stages_leaves_the_input_alone(self):
        stages = self.stages()
        RB.skip_stages(stages, RB.load_forced(self.FORCED))
        self.assertEqual(stages, self.stages())

    # The fixture's story: stage One has the hiker (ace 20) and the rival
    # (ace 5), stage Two Leader X (ace 20).
    NONE_FORCED = RB.Forced(frozenset(), frozenset())
    HIKER_FORCED = RB.Forced(frozenset({'TRAINER_HIKER_A'}), frozenset())
    LEADER_OPTIONAL = RB.Forced(frozenset(), frozenset({'TRAINER_LEADER_X'}))
    MARGINS = {'full_margin': 10, 'skip_margin': 15}

    @classmethod
    def setUpClass(cls):
        cls.inputs = curve_inputs(FIXTURE, FIXTURE_STAGES)

    def run_share(self, wilds=None, **kw):
        inp = self.inputs
        return RB.share_run(inp['stages'], inp['trainers'], inp['gd'], inp['scaling'],
                            wilds or inp['wilds']['modern'], vanilla_wilds=inp['wilds']['vanilla'], **kw)

    def test_without_skip_rows_match_today(self):
        # share_run's rows before the skip player (#350), snapshotted.
        def boss(stage, bid, cls, base, raise_, ace, bench, ref, levels, friendship):
            return {'stage': stage, 'boss': bid, 'class': f'TRAINER_CLASS_{cls}', 'base_ace': base,
                    'raise': raise_, 'boss_ace': base + raise_, 'ace': max(levels), 'bench': bench,
                    'ref': ref, 'levels': levels, 'friendship': friendship}

        def stage(name, start, n, gap, raise_, mean, land, offset):
            return {'stage': name, 'start_ref': start, 'trainers': n, 'gap': gap, 'raise': raise_,
                    'trainer_ace_mean': mean, 'wild_land_mean': land, 'wild_offset': offset, 'wild_applied': 0}
        rows = self.run_share(skip=None, margin=5, relative_gaps=True, trainer_gap=10, wild_gap=20, wild_battles=6)
        self.assertEqual(rows, (
            [boss('One', 'TRAINER_RIVAL_A', 'PKMN_TRAINER_1', 5, 7, 12, 11, 11, [13, 11, 11, 11, 11, 11], 96),
             boss('Two', 'TRAINER_LEADER_X', 'LEADER', 20, 0, 13, 11, 11, [13, 11, 11, 11, 11, 11], 112)],
            [stage('One', 5, 1, -185.7, 0, 20.0, 4.0, 0), stage('Two', 11, 0, None, 0, None, None, 0)]))
        rows = self.run_share(margin=1, trainer_gap=-20, wild_gap=0, ko_takers=3, boss_ref='ko_mean',
                              gap_ref='ko_mean')
        self.assertEqual(rows, (
            [boss('One', 'TRAINER_RIVAL_A', 'PKMN_TRAINER_1', 5, 9, 14, 12, 12.7, [12, 14, 12, 12, 12, 12], 101),
             boss('Two', 'TRAINER_LEADER_X', 'LEADER', 20, 0, 15, 12, 13.7, [13, 15, 13, 12, 12, 12], 117)],
            [stage('One', 5.0, 1, -20.0, 6, 26.0, 5.0, 1),
             stage('Two', 13.666666666666666, 0, None, 0, None, None, 0)]))

    def test_boss_ace_is_the_lower_of_the_two_rules(self):
        rows, st = self.run_share(skip=self.NONE_FORCED, lower=True, **self.MARGINS)
        rival, leader = rows
        # The skip player passes the hiker by, so it meets the rival (and then
        # Leader X) lower: its reference / 0.85 is the lower rule at both.
        # The rival: 11 / 1.10 = 10, 5 / 0.85 = 5.9 -> 6.
        self.assertEqual((rival['ref'], rival['skip_ref']), (11, 5))
        self.assertEqual(rival['skip_levels'], [6, 5, 5, 5, 5, 5])
        self.assertEqual(rival['boss_ace'], min(int(11 / 1.10 + 0.5), int(5 / 0.85 + 0.5)))
        self.assertEqual((rival['boss_ace'], rival['raise']), (6, 1))
        # Leader X: 11 / 1.10 = 10, 6 / 0.85 = 7.1 -> 7.
        self.assertEqual((leader['ref'], leader['skip_ref'], leader['boss_ace']), (11, 6, 7))
        self.assertEqual(st[0]['skip_gap'], None)  # no forced trainer to fight
        # The full player's rule wins once the skip player fights the hiker too
        # (at the same shift, so the same gap: the two are level until then).
        rows, st = self.run_share(skip=self.HIKER_FORCED, lower=True, **self.MARGINS)
        self.assertEqual(rows[0]['skip_levels'], rows[0]['levels'])
        self.assertEqual(rows[0]['boss_ace'], 10)  # 11 / 0.85 = 12.9 is the higher
        self.assertEqual(st[0]['skip_gap'], st[0]['gap'])
        # One raise per boss: both players fight the same team.
        self.assertEqual(rows[1]['skip_levels'], rows[1]['levels'])

    def test_skipped_boss_uses_the_full_rule(self):
        rows, _ = self.run_share(skip=self.LEADER_OPTIONAL, lower=True, **self.MARGINS)
        leader = rows[1]
        self.assertIsNone(leader['skip_ref'])
        self.assertIsNone(leader['skip_levels'])
        self.assertEqual(leader['boss_ace'], int(leader['ref'] / 1.10 + 0.5))
        self.assertIsNotNone(rows[0]['skip_ref'])
        # Without skip at all, the full rule alone.
        rows, _ = self.run_share(lower=True, **self.MARGINS)
        self.assertEqual([r['boss_ace'] for r in rows], [int(r['ref'] / 1.10 + 0.5) for r in rows])
        with self.assertRaises(ValueError):
            self.run_share(full_margin=10)

    def test_forced_trainer_outliers(self):
        # The skip player fights the forced hiker (ace 20) at 6, after the stage's catches.
        _, st = self.run_share(skip=self.HIKER_FORCED)
        self.assertEqual(st[0]['skip_trainers'], [{'trainer': 'TRAINER_HIKER_A', 'ace': 20, 'lead': 6}])
        self.assertEqual(st[1]['skip_trainers'], [])
        self.assertNotIn('skip_trainers', self.run_share()[1][0])  # no skip player, no list
        self.assertEqual(RB.forced_outliers(st), [{'trainer': 'TRAINER_HIKER_A', 'stage': 'One', 'ace': 20,
                                                   'skip': 6, 'skip_pct': -70.0}])
        # More than OUTLIER_SKIP percent under, as for the bosses: -25% exactly is not flagged.
        rows = [{'stage': 'One', 'skip_trainers': [{'trainer': 'TRAINER_A', 'ace': 100, 'lead': 75},
                                                   {'trainer': 'TRAINER_B', 'ace': 100, 'lead': 74}]}]
        self.assertEqual([r['trainer'] for r in RB.forced_outliers(rows)], ['TRAINER_B'])
        self.assertEqual(RB.forced_outliers([{'stage': 'One'}]), [])
        section = '\n'.join(RB.two_players_report([], RB.forced_outliers(st)))
        self.assertIn('| trainer | stage | ace | skip lead | % |', section)
        self.assertIn('| Hiker A | One | 20 | 6 | -70% |', section)
        section = '\n'.join(RB.two_players_report([], []))
        self.assertIn(f'No forced trainer is met more than {RB.OUTLIER_SKIP}% under its ace.', section)

    def test_lower_lets_raises_go_negative(self):
        # Leader X (ace 20) is above both targets.
        lowered, _ = self.run_share(skip=self.NONE_FORCED, lower=True, **self.MARGINS)
        kept, _ = self.run_share(skip=self.NONE_FORCED, **self.MARGINS)
        self.assertEqual((lowered[1]['raise'], lowered[1]['boss_ace']), (7 - 20, 7))
        self.assertEqual((kept[1]['raise'], kept[1]['boss_ace']), (0, 20))
        # A given stage shift can still lower its trainers.
        _, above = self.run_share(stage_raises={'One': -16})
        self.assertGreater(above[0]['gap'], 0)

    def test_trainer_shift_never_lowers(self):
        # The hiker (ace 20) is fought at reference 5, far over a gap of 0, but the
        # trainer rule only ever raises (#350: today's rule), with lower or without.
        for lower in (True, False):
            _, st = self.run_share(trainer_gap=0, lower=lower, **self.MARGINS)
            self.assertEqual(st[0]['raise'], 0, lower)
            self.assertLess(st[0]['gap'], 0)

    def test_gaps_measure_on_gap_ref_and_margins_on_boss_ref(self):
        def run(**kw):
            bosses, st = self.run_share(trainer_gap=0, wild_gap=0, margin=0, **kw)
            return ([(r['boss_ace'], r['ref']) for r in bosses],
                    [(s['raise'], s['wild_offset'], s['start_ref'], s['gap']) for s in st])
        bench_bosses, bench_gaps = run()
        ace_bosses, ace_gaps = run(gap_ref='ace')
        # boss_ref moves the bosses only (#350), gap_ref the trainer and wild gaps only.
        self.assertEqual(run(boss_ref='ace')[1], bench_gaps)
        self.assertNotEqual(run(boss_ref='ace')[0], bench_bosses)
        self.assertEqual(ace_bosses, bench_bosses)
        self.assertNotEqual(ace_gaps, bench_gaps)
        self.assertEqual(run(boss_ref='ace', gap_ref='ace'), (run(boss_ref='ace')[0], ace_gaps))
        # Both default to the bench, in share_run and the explorer.
        self.assertEqual(run(boss_ref='bench', gap_ref='bench'), (bench_bosses, bench_gaps))
        self.assertEqual((RB.EXPLORER_KNOBS['boss_ref'], RB.EXPLORER_KNOBS['gap_ref']), ('bench', 'bench'))
        res = RB.explore_run(self.inputs, {'trainer_gap': 0, 'wild_gap': 0, 'margin': 0, 'gap_ref': 'ace'})
        self.assertEqual([(s['raise'], s['wild_offset'], s['start_ref'], s['gap']) for s in res['stages']], ace_gaps)

    def test_wild_offset_never_below_vanilla(self):
        raised = {i: RB.shifted_slots(s, 6) for i, s in self.inputs['wilds']['modern'].items()}
        _, st = self.run_share(raised, wild_gap=100, lower=True)
        self.assertEqual((st[0]['wild_applied'], st[0]['wild_offset']), (6, 0))
        _, st = self.run_share(raised, wild_gap=100)
        self.assertEqual(st[0]['wild_offset'], 6)
        _, st = self.run_share(wild_gap=100, lower=True)
        self.assertEqual(st[0]['wild_offset'], 0)

    @staticmethod
    def recording_devolve(seen):
        """A devolve that turns Sableye into Magikarp and records its calls."""
        def devolve(species, level, taken=()):
            seen.append((species, level))
            return 'SPECIES_MAGIKARP' if species == 'SPECIES_SABLEYE' else species
        return devolve

    def test_lowered_teams_devolve_in_the_model(self):
        seen = []
        rows, st = self.run_share(lower=True, stage_raises={'One': -15}, devolve=self.recording_devolve(seen),
                                  **self.MARGINS)
        plain, _ = self.run_share(lower=True, stage_raises={'One': -15}, **self.MARGINS)
        # The hiker's stage shift (-15): Ralts 7 -> 1, Sableye 20 -> 5; Leader X lowered to its ace.
        self.assertEqual(st[0]['raise'], -15)
        self.assertIn(('SPECIES_RALTS', 1), seen)
        self.assertIn(('SPECIES_SABLEYE', 5), seen)
        self.assertIn(('SPECIES_SABLEYE', rows[1]['boss_ace']), seen)
        # The devolved Magikarp gives less exp than the Sableye.
        self.assertLess(sum(rows[0]['levels']), sum(plain[0]['levels']))
        # A lowered wild table is rebuilt from vanilla, as restock writes it, and never devolved:
        # tables raised 6 with their Magikarp evolved into Sableye come back as vanilla's Magikarp.
        raised = {i: RB.shifted_slots(s, 6, lambda sp, lvl: 'SPECIES_SABLEYE')
                  for i, s in self.inputs['wilds']['vanilla'].items()}
        self.assertIn('SPECIES_SABLEYE', {slot['species'] for s in raised.values() for _, slot, _ in s})
        seen.clear()
        lowered = self.run_share(raised, wild_gap=100, lower=True, devolve=self.recording_devolve(seen))
        self.assertEqual(seen, [])
        vanilla = self.run_share(self.inputs['wilds']['vanilla'], wild_gap=100, lower=True)
        self.assertEqual(lowered[0], vanilla[0])
        self.assertNotEqual(self.run_share(raised, wild_gap=100)[0], vanilla[0])
        # Without lower nothing goes down, so nothing devolves.
        seen.clear()
        self.run_share(trainer_gap=0, devolve=self.recording_devolve(seen), **self.MARGINS)
        self.assertEqual(seen, [])

    def test_explore_run_devolves_with_evolve_on(self):
        seen = []
        live = dict(self.inputs, devolve=self.recording_devolve(seen))
        RB.explore_run(live, {**self.MARGINS, 'lower': True, 'evolve': False})
        self.assertEqual(seen, [])
        RB.explore_run(live, {**self.MARGINS, 'lower': True})
        self.assertTrue(any(sp == 'SPECIES_SABLEYE' for sp, _ in seen))
        self.assertIsNone(curve_inputs(FIXTURE, FIXTURE_STAGES)['devolve'])

    def lowering_plan(self, lower):
        """apply_plan on the fixture with Leader X's fight given a rival
        variant two levels lower (Leader Y) and a partner (ace 40)."""
        trainers = dict(self.inputs['trainers'])
        variant = copy.deepcopy(trainers['TRAINER_LEADER_X'])
        partner = copy.deepcopy(trainers['TRAINER_LEADER_X'])
        for mon in variant.mons:
            mon.level -= 2
        for mon in partner.mons:
            mon.level += 20
        trainers['TRAINER_LEADER_Y'] = variant
        stages = copy.deepcopy(self.inputs['stages'])
        stages[1]['variants'] = {'TRAINER_LEADER_X': ['TRAINER_LEADER_Y']}
        inputs = dict(self.inputs, trainers=trainers, stages=stages)
        with open(os.path.join(FIXTURE, RB.VANILLA_WILD), encoding='utf-8') as f:
            wild = json.load(f)
        with unittest.mock.patch.dict(RB.PARTNER_FIGHTS, {'PARTNER_X': ('TRAINER_LEADER_X',)}, clear=True):
            return RB.apply_plan(inputs, {**self.MARGINS, 'lower': lower, 'evolve': False},
                                 {'PARTNER_X': partner}, wild, G.map_folders(FIXTURE))['raises']

    def test_rival_variants_and_partners_follow_a_lowered_boss(self):
        raises = self.lowering_plan(True)
        ace = 20 + raises['TRAINER_LEADER_X']
        self.assertLess(ace, 18)
        # The variant (ace 18) and the partner (ace 40) end at the lowered boss's ace.
        self.assertEqual(18 + raises['TRAINER_LEADER_Y'], ace)
        self.assertEqual(40 + raises['PARTNER_X'], ace)
        # Without lower, today's: never below their own levels.
        raises = self.lowering_plan(False)
        self.assertNotIn('TRAINER_LEADER_X', raises)
        self.assertEqual(raises['TRAINER_LEADER_Y'], 2)
        self.assertNotIn('PARTNER_X', raises)

    def test_explore_run_takes_the_forced_data_from_the_snapshot(self):
        for key, value in (('full_margin', None), ('skip_margin', None), ('lower', False)):
            self.assertIs(RB.EXPLORER_KNOBS[key], value)
        live = dict(self.inputs, forced=self.NONE_FORCED)
        data = json.loads(json.dumps(RB.curve_snapshot(
            *(live[k] for k in ('stages', 'trainers', 'gd', 'scaling', 'wilds')),
            G.R.SpeciesInfo.from_evolutions({}, {}), live['postgame'], forced=live['forced'])))
        snap = RB.load_snapshot(data)
        self.assertEqual(snap['forced'], self.NONE_FORCED)
        knobs = {**self.MARGINS, 'lower': True, 'evolve': False}
        self.assertEqual(RB.explore_run(snap, knobs), RB.explore_run(live, knobs))
        res = RB.explore_run(snap, knobs)
        self.assertEqual([r['skip_ref'] for r in res['bosses']], [5, 6])
        # Without the forced data, no skip player.
        self.assertNotIn('forced', RB.curve_snapshot(
            *(live[k] for k in ('stages', 'trainers', 'gd', 'scaling', 'wilds')),
            G.R.SpeciesInfo.from_evolutions({}, {}), live['postgame']))
        self.assertNotIn('skip_ref', RB.explore_run(self.inputs, knobs)['bosses'][0])

    def test_snapshot_devolves_as_the_repo_inputs(self):
        # The fixture has no evolutions: give Sableye a line (Ralts, Magikarp at 8, Sableye at 15).
        info = G.R.SpeciesInfo.from_evolutions({}, {
            'SPECIES_RALTS': [('EVO_LEVEL', '8', 'SPECIES_MAGIKARP', [])],
            'SPECIES_MAGIKARP': [('EVO_LEVEL', '15', 'SPECIES_SABLEYE', [])]})
        live = curve_inputs(FIXTURE, FIXTURE_STAGES, info, forced_path=FIXTURE_FORCED)
        data = json.loads(json.dumps(RB.curve_snapshot(
            *(live[k] for k in ('stages', 'trainers', 'gd', 'scaling', 'wilds')), info, live['postgame'],
            forced=live['forced'])))
        self.assertEqual(data['devolve_lines'], {
            'SPECIES_MAGIKARP': [['SPECIES_MAGIKARP', 8], ['SPECIES_RALTS', 1]],
            'SPECIES_SABLEYE': [['SPECIES_SABLEYE', 15], ['SPECIES_MAGIKARP', 8], ['SPECIES_RALTS', 1]]})
        snap = RB.load_snapshot(data)
        for level in range(1, 25):
            for species in ('SPECIES_SABLEYE', 'SPECIES_MAGIKARP', 'SPECIES_MR_MIME'):
                for taken in ((), {'SPECIES_RALTS'}):
                    self.assertEqual(snap['devolve'](species, level, taken), live['devolve'](species, level, taken),
                                     (species, level, taken))
        # apply's path (repo_inputs) and the explorer's give the same rows, lowered and devolved.
        for knobs in ({**self.MARGINS, 'lower': True}, {**self.MARGINS, 'lower': True, 'trainer_gap': 0}):
            self.assertEqual(RB.explore_run(snap, knobs), RB.explore_run(live, knobs), knobs)
        # Leader X lowered (20 -> 10) devolves its Sableye into a Ralts (10 less EVOLVE_GRACE is under 8) the
        # same way on both paths.
        self.assertEqual(RB.explore_run(snap, knobs)['bosses'][1]['boss_ace'], 10)
        for inputs in (snap, live):
            self.assertEqual(RB.team_species(inputs['trainers']['TRAINER_LEADER_X'], -10, inputs['evolve'],
                                             inputs['devolve'], True), ['SPECIES_RALTS', 'SPECIES_MR_MIME'])


class Solo(unittest.TestCase):
    """solo.py: each starter's solo walls and the grind to them (#350)."""

    IVS = dict.fromkeys(G.IV_STATS, 15)
    TARGETS = ['TYPE_FIRE', 'TYPE_GRASS', 'TYPE_WATER']

    @staticmethod
    def regime():
        species = {'SPECIES_SEED': power_species(60, ('TYPE_GRASS',)),
                   'SPECIES_TREE': power_species(90, ('TYPE_GRASS',)),
                   'SPECIES_LAKE': power_species(85, ('TYPE_WATER',)),
                   'SPECIES_FIRE': power_species(70, ('TYPE_FIRE',)),
                   'SPECIES_FLASH': power_species(70, ('TYPE_FIRE',), ('ABILITY_FLASH_FIRE', 'ABILITY_NONE'))}
        defaults = {'SPECIES_SEED': ['MOVE_LEAF'], 'SPECIES_TREE': ['MOVE_LEAF'], 'SPECIES_LAKE': ['MOVE_SURF'],
                    'SPECIES_FIRE': ['MOVE_EMBER'], 'SPECIES_FLASH': ['MOVE_EMBER']}
        return matchup_regime(species, Matchup.MOVES, defaults, Matchup.CHART)

    @staticmethod
    def evolve(species, level):
        return 'SPECIES_TREE' if species == 'SPECIES_SEED' and level >= 16 else species

    @staticmethod
    def foes(gd, *mons):
        return [P.fighter(gd, sp, lv, gd.default_moves(sp, lv), None) for sp, lv in mons]

    def args(self, gd, foes, species='SPECIES_SEED'):
        return gd, species, foes, [], {}, self.evolve, self.TARGETS, self.IVS

    def scores(self, gd, level, foes, species='SPECIES_SEED'):
        me = S.solo_fighter(gd, species, level, [], {}, self.evolve, self.TARGETS, self.IVS)
        return [P.score(me, foe, gd.chart) for foe in foes]

    def test_solo_fighter_has_full_evs_spread_evenly(self):
        gd = self.regime()
        self.assertEqual((S.SOLO_EVS, S.GRIND_BUDGET), (85, 50))
        me = S.solo_fighter(gd, 'SPECIES_SEED', 40, [], {}, self.evolve, self.TARGETS, self.IVS)
        bare = P.fighter(gd, 'SPECIES_TREE', 40, ['MOVE_LEAF'], self.IVS)  # evolved for its level
        self.assertEqual(me.attacks, bare.attacks)
        for stat, value in bare.stats.items():
            self.assertAlmostEqual(me.stats[stat], value + 85 // 4 * 40 / 100, msg=stat)

    def test_wall_level_on_fixture(self):
        gd = self.regime()
        foes = self.foes(gd, ('SPECIES_LAKE', 30), ('SPECIES_FIRE', 25))
        wall = S.wall_level(*self.args(gd, foes))
        # The lowest level that wins each one-on-one (healing in between).
        self.assertGreaterEqual(min(self.scores(gd, wall, foes)), 1)
        self.assertLess(min(self.scores(gd, wall - 1, foes)), 1)
        self.assertEqual(wall, 31)
        # Nothing it has hurts a Flash Fire Pokemon: unwinnable up to 100.
        self.assertIsNone(S.wall_level(*self.args(gd, self.foes(gd, ('SPECIES_FLASH', 5)), 'SPECIES_FIRE')))

    def test_sweep_at_least_wall(self):
        gd = self.regime()
        foes = self.foes(gd, ('SPECIES_LAKE', 30), ('SPECIES_FIRE', 25), ('SPECIES_LAKE', 28))
        wall, sweep = S.wall_level(*self.args(gd, foes)), S.sweep_level(*self.args(gd, foes))
        self.assertGreater(sweep, wall)
        # The lowest level whose turns against each, 1/score, add up to at most one fight.
        self.assertLessEqual(sum(1 / s for s in self.scores(gd, sweep, foes)), 1)
        self.assertGreater(sum(1 / s for s in self.scores(gd, sweep - 1, foes)), 1)
        self.assertEqual(S.sweep_level(*self.args(gd, foes), start=wall), sweep)
        self.assertIsNone(S.sweep_level(*self.args(gd, self.foes(gd, ('SPECIES_FLASH', 5)), 'SPECIES_FIRE')))

    def test_grind_kos_no_penalty_matches_closed_form(self):
        gd = fake_regime(B_SCALED_EXP='GEN_6')  # flat: yield * level / 7, whatever the getter's level
        scaling = G.parse_scaling_factors(FIXTURE)
        need = RB.exp_for_level('GROWTH_MEDIUM_SLOW', 30) - RB.exp_for_level('GROWTH_MEDIUM_SLOW', 20)
        per_ko = 150 * 25 // 7 * 4915 // 4096  # max friendship's affection, 1.2x
        self.assertEqual(S.grind_kos(gd, scaling, None, 20, 30, [(150, 25)]), -(-need // per_ko))
        self.assertEqual(S.grind_kos(gd, scaling, None, 20, 30, [(150, 25)], mult=1.0), -(-need // (150 * 25 // 7)))
        self.assertEqual(S.grind_kos(gd, scaling, None, 30, 30, [(150, 25)]), 0)
        # A team is fought whole: the count is a multiple of its size.
        self.assertEqual(S.grind_kos(gd, scaling, None, 20, 30, [(150, 25)] * 3) % 3, 0)
        # The over-level penalty makes it longer.
        self.assertGreater(S.grind_kos(gd, scaling, RB.Overlevel(10, True, 4, 10, 0), 20, 30, [(150, 25)]),
                           S.grind_kos(gd, scaling, None, 20, 30, [(150, 25)]))

    def test_best_wild_ignores_water_before_surf(self):
        gd = types.SimpleNamespace(species={'SPECIES_LAND': G.Species((), {}, 100, '', ''),
                                            'SPECIES_SWIM': G.Species((), {}, 150, '', ''),
                                            'SPECIES_ROD': G.Species((), {}, 250, '', '')})

        def slot(species, level):
            return {'species': species, 'min_level': level - 2, 'max_level': level}
        wilds = {0: [('land_mons', slot('SPECIES_LAND', 10), 20)],
                 2: [('water_mons', slot('SPECIES_SWIM', 30), 60), ('fishing_mons', slot('SPECIES_ROD', 40), 60),
                     ('land_mons', slot('SPECIES_LAND', 20), 20)]}
        # Grass only before Surf, at each slot's highest level (DexNav can hunt it); never rods.
        self.assertEqual(S.best_wild(gd, wilds, 1, 2), (100, 10, 'SPECIES_LAND'))
        self.assertEqual(S.best_wild(gd, wilds, 2, 3), (100, 20, 'SPECIES_LAND'))
        self.assertEqual(S.best_wild(gd, wilds, 2, 2), (150, 30, 'SPECIES_SWIM'))
        self.assertEqual(S.best_wild(gd, wilds, 2, None), (100, 20, 'SPECIES_LAND'))

    def test_best_wild_takes_the_fewest_kos_under_the_penalty(self):
        gd = fake_regime(B_SCALED_EXP='GEN_6')
        gd.species = {'SPECIES_RICH': G.Species((), {}, 250, '', ''), 'SPECIES_PEER': G.Species((), {}, 150, '', '')}
        scaling = G.parse_scaling_factors(FIXTURE)
        penalty = RB.Overlevel(10, True, 4, 10, 0)

        def slot(species, level):
            return {'species': species, 'min_level': level, 'max_level': level}
        wilds = {0: [('land_mons', slot('SPECIES_RICH', 20), 20), ('land_mons', slot('SPECIES_PEER', 30), 20)]}

        def cost(foe):
            return S.grind_kos(gd, scaling, penalty, 30, 40, [foe])
        # Rich's yield x level (5000) beats Peer's (4500), but a climb from 30 sits far over it.
        self.assertEqual(S.best_wild(gd, wilds, 0, None), (250, 20, 'SPECIES_RICH'))
        self.assertLess(cost((150, 30)), cost((250, 20)))
        self.assertEqual(S.best_wild(gd, wilds, 0, None, cost), (150, 30, 'SPECIES_PEER'))
        # Without the penalty Rich takes fewer KOs again; at no climb (every cost 0), yield x level decides.
        self.assertEqual(S.best_wild(gd, wilds, 0, None, lambda foe: S.grind_kos(gd, scaling, None, 30, 40, [foe])),
                         (250, 20, 'SPECIES_RICH'))
        self.assertEqual(S.best_wild(gd, wilds, 0, None, lambda foe: 0), (250, 20, 'SPECIES_RICH'))
        # A source that gives no exp (None) is never picked over one that does.
        self.assertEqual(S.best_wild(gd, wilds, 0, None, lambda foe: None if foe[0] == 250 else 99),
                         (150, 30, 'SPECIES_PEER'))

    def test_boss_foes_evolve_and_devolve_with_the_curve(self):
        gd = self.regime()
        seen = []

        def evolve(species, level, gender=None):
            return 'SPECIES_TREE' if species == 'SPECIES_SEED' and level >= 16 else species

        def devolve(species, level, taken=()):
            seen.append((species, level, taken))
            return 'SPECIES_SEED' if species == 'SPECIES_TREE' and level < 18 else species
        boss = G.Trainer('TRAINER_B', '', 'Leader', [], False, [G.TrainerMon('SPECIES_TREE', 30, []),
                                                                 G.TrainerMon('SPECIES_SEED', 12, [])])
        # Lowered 15 (ace 15): the Tree devolves for its level, as the run and apply do.
        self.assertEqual(S.boss_foes(gd, boss, 15, evolve, devolve),
                         self.foes(gd, ('SPECIES_SEED', 15), ('SPECIES_SEED', 1)))
        # A boss team keeps distinct species: the Tree is the highest, so it goes first.
        self.assertEqual(seen[0], ('SPECIES_TREE', 15, frozenset({'SPECIES_TREE', 'SPECIES_SEED'})))
        # Raised 5 (ace 35): the Seed at 17 would evolve, but the team has a Tree already.
        self.assertEqual(S.boss_foes(gd, boss, 35, evolve, devolve),
                         self.foes(gd, ('SPECIES_TREE', 35), ('SPECIES_SEED', 17)))
        lone = G.Trainer('TRAINER_C', '', 'Leader', [], False, [G.TrainerMon('SPECIES_SEED', 12, [])])
        self.assertEqual(S.boss_foes(gd, lone, 17, evolve, devolve), self.foes(gd, ('SPECIES_TREE', 17)))
        # Without the evolutions, only the levels move.
        self.assertEqual(S.boss_foes(gd, boss, 15), self.foes(gd, ('SPECIES_TREE', 15), ('SPECIES_SEED', 1)))

    def test_solo_walls_on_the_fixture(self):
        inp = curve_inputs(FIXTURE, FIXTURE_STAGES)
        gd, stages, wilds = inp['gd'], inp['stages'], inp['wilds']['modern']
        rows = RB.explore_run(inp)['bosses']
        settings = {'starters': {'A': 'SPECIES_SABLEYE'}, 'ivs': 15, 'moves': 4, 'tm_exclude_maps': []}
        scaling = RB.game_scaling(gd, inp['scaling'])
        out = S.solo_walls(inp['trainers'], gd, stages, rows, wilds, {}, {}, lambda sp, lv: sp, scaling, None,
                           settings)
        self.assertEqual([(r['boss'], r['starter']) for r in out], [('TRAINER_RIVAL_A', 'A'), ('TRAINER_LEADER_X', 'A')])
        names = [st['name'] for st in stages]
        for r, row in zip(out, rows):
            self.assertLessEqual({'boss', 'starter', 'lead', 'wall', 'sweep', 'kos', 'source'}, set(r))
            self.assertEqual((r['lead'], r['ace']), (row['levels'][0], row['boss_ace']))
            self.assertLessEqual(r['wall'], r['sweep'])
            y, level, species = S.best_wild(gd, wilds, names.index(r['stage']), None)
            self.assertEqual(r['source'], [species, level])
            self.assertEqual(r['kos'], 0 if r['wall'] <= r['lead'] else
                             S.grind_kos(gd, scaling, None, r['lead'], r['wall'], [(y, level)],
                                         growth=gd.species['SPECIES_SABLEYE'].growth))
            self.assertIsNone(r['battles'])  # no rematches before Norman
        # Leader X's Sableye is 20 and the lead far lower: a grind.
        self.assertGreater(out[1]['kos'], 0)
        self.assertEqual([r['exempt'] for r in out], [None, None])
        # The optional fights and SOLO_OUTLIERS are marked outside the budget.
        with unittest.mock.patch.dict(S.SOLO_OUTLIERS, {('TRAINER_RIVAL_A', 'A'): 'test'}):
            marked = S.solo_walls(inp['trainers'], gd, stages, rows, wilds, {}, {}, lambda sp, lv: sp, scaling, None,
                                  settings, optional=frozenset({'TRAINER_LEADER_X'}))
        self.assertEqual([r['exempt'] for r in marked], [S.ACCEPTED, S.OPTIONAL])
        self.assertEqual(S.SOLO_OUTLIERS, {('TRAINER_WALLACE', 'MUDKIP'): 'owner accepted, #350'})

    TUNE = {'cutoffs': (20, 30), 'widths': (4, 6), 'floors': (20, 30)}
    TUNE_BASE = {'trainer_gap': 10, 'wild_gap': 0, 'gap_unit': 'percent'}  # raises stage One's wild table 1

    @staticmethod
    def fake_walls(calls):
        """solo_walls for tune_penalty: its KOs set by the penalty. Floor
        20 takes 60 KOs (over the budget), except cutoff 20 width 4's 10,
        which has an unwinnable wall too; floor 30 takes 45 at cutoff 30 or
        width 6, else 55."""
        def walls(trainers, gd, stages, rows, wilds, map_tms, teachables, evolve, scaling, overlevel, settings,
                  **kw):
            calls.append(dict(kw, rows=rows, wilds=wilds, gd=gd, scaling=scaling, overlevel=overlevel,
                              evolve=evolve, settings=settings))
            c, w, f = overlevel.cutoff, overlevel.width, overlevel.floor
            if f == 20:
                kos = 10 if (c, w) == (20, 4) else 60
            else:
                kos = 45 if c == 30 or w == 6 else 55
            out = [{'boss': 'TRAINER_LEADER_X', 'starter': 'A', 'lead': 10, 'wall': 30, 'sweep': 31, 'kos': kos,
                    'source': ['SPECIES_SABLEYE', 9]},
                   {'boss': 'TRAINER_RIVAL_A', 'starter': 'B', 'lead': 5, 'wall': 6, 'sweep': 6, 'kos': 3,
                    'source': ['SPECIES_MAGIKARP', 5]}]
            if (c, w, f) == (20, 4, 20):
                out.append({'boss': 'TRAINER_LEADER_X', 'starter': 'B', 'lead': 10, 'wall': None, 'sweep': None,
                            'kos': None, 'source': None})
            # Outside the budget: an optional fight's 500 KOs and an accepted unwinnable wall.
            out += [{'boss': 'TRAINER_RIVAL_A', 'starter': 'A', 'lead': 5, 'wall': 40, 'sweep': 41, 'kos': 500,
                     'source': ['SPECIES_MAGIKARP', 5], 'exempt': S.OPTIONAL},
                    {'boss': 'TRAINER_LEADER_X', 'starter': 'C', 'lead': 10, 'wall': None, 'sweep': None,
                     'kos': None, 'source': None, 'exempt': S.ACCEPTED}]
            return out
        return walls

    def tune(self, calls):
        inp = dict(curve_inputs(FIXTURE, FIXTURE_STAGES),
                   solo={'map_tms': {}, 'teachables': {}, 'settings': {'starters': {}}, 'evolve': self.evolve})
        with unittest.mock.patch.object(S, 'solo_walls', self.fake_walls(calls)):
            return inp, RB.tune_penalty(inp, self.TUNE_BASE, **self.TUNE)

    def candidate_knobs(self, cutoff, width, floor):
        return {**self.TUNE_BASE, **RB.TUNE_KNOBS, 'overlevel_cutoff': cutoff, 'overlevel_unit': 'percent',
                'overlevel_width': width, 'overlevel_floor': floor}

    def test_tune_picks_the_strictest_passing_candidate(self):
        inp, out = self.tune([])
        self.assertEqual(len(out), 8)
        by = {(r['cutoff'], r['width'], r['floor']): r for r in out}
        self.assertEqual(set(by), {(c, w, f) for c in (20, 30) for w in (4, 6) for f in (20, 30)})
        self.assertEqual(by[(30, 4, 30)]['max_kos'], 45)
        self.assertTrue(by[(30, 4, 30)]['passes'])
        self.assertFalse(by[(20, 4, 30)]['passes'])  # 55 KOs
        # An unwinnable wall fails the budget whatever the KOs, and is listed apart.
        low = by[(20, 4, 20)]
        self.assertEqual((low['max_kos'], low['passes']), (10, False))
        self.assertEqual([(r['boss'], r['starter']) for r in low['unwinnable']], [('TRAINER_LEADER_X', 'B')])
        # The exempt walls (an optional fight, an accepted outlier) count for nothing, but stay in walls.
        self.assertEqual(len(by[(30, 4, 30)]['walls']), 4)
        self.assertNotIn('C', by[(30, 4, 30)]['worst'])
        # Each starter's worst wall.
        self.assertEqual({s: r['kos'] for s, r in by[(30, 4, 30)]['worst'].items()}, {'A': 45, 'B': 3})
        # The strictest: the lowest floor, then cutoff, then width. Passing: (30, 4, 30), (20, 6, 30), (30, 6, 30).
        chosen = RB.pick_penalty(out)
        self.assertEqual((chosen['cutoff'], chosen['width'], chosen['floor']), (20, 6, 30))
        self.assertIsNone(RB.pick_penalty([r for r in out if not r['passes']]))
        # The full-clear lead at the last staged boss (Wallace in the game) comes from the candidate's own run.
        run = RB.explore_run(inp, self.candidate_knobs(20, 6, 30))
        final = [r for r in run['bosses'] if r['boss'] == 'TRAINER_LEADER_X'][0]
        self.assertEqual(chosen['final_lead'], final['levels'][0])

    def test_tune_fights_each_candidates_own_curve(self):
        calls = []
        inp, _ = self.tune(calls)
        self.assertEqual(len(calls), 8)
        self.assertEqual((RB.TUNE_KNOBS['scaled_exp'], RB.TUNE_KNOBS['full_margin'], RB.TUNE_KNOBS['skip_margin'],
                          RB.TUNE_KNOBS['lower'], RB.TUNE_KNOBS['boss_ref']), (False, 10, 15, True, 'ace'))
        min_level = RB.explorer_defaults(inp['gd'])['overlevel_min_level']
        modern, vanilla = inp['wilds']['modern'], inp['wilds']['vanilla']
        for call in calls:
            o = call['overlevel']
            self.assertEqual(o, RB.Overlevel(o.cutoff, True, o.width, o.floor, min_level))
            run = RB.explore_run(inp, self.candidate_knobs(o.cutoff, o.width, o.floor))
            # The boss rows (levels, raises) are the candidate's run's.
            self.assertEqual(call['rows'], run['bosses'])
            # Its wild tables are the run's, as restock writes them for its offsets.
            for i, s in enumerate(run['stages']):
                self.assertEqual(call['wilds'].get(i, []), RB.run_wilds(
                    modern.get(i, ()), vanilla.get(i, ()), s['wild_offset'], s['wild_applied'], None,
                    inp['gd'].species), i)
        self.assertTrue(any(s['wild_offset'] != s['wild_applied'] for s in run['stages']))
        self.assertNotEqual(calls[0]['wilds'], dict(modern))
        call = calls[0]
        # The candidate's exp: flat, 1.5x trainer exp as the knobs say.
        self.assertFalse(call['gd'].flag('B_SCALED_EXP >= GEN_5 && B_SCALED_EXP != GEN_6'))
        self.assertEqual(call['gd'].defines['B_TRAINER_EXP_MULTIPLIER'], RB.TRAINER_EXP['1.5x off'])
        # The bosses evolve and devolve as the run's teams do; the player's line evolves on time.
        self.assertIs(call['evolve'], self.evolve)
        self.assertIs(call['foe_evolve'], inp['evolve'])
        self.assertIs(call['foe_devolve'], inp['devolve'])
        # The fixture's inputs have no forced data: no optional fights.
        self.assertEqual(call['optional'], frozenset())
        forced = RB.Forced(frozenset(), frozenset({'TRAINER_LEADER_X'}))
        calls.clear()
        with unittest.mock.patch.object(S, 'solo_walls', self.fake_walls(calls)):
            RB.tune_penalty(dict(inp, forced=forced), self.TUNE_BASE, [20], [4], [20])
        self.assertEqual(calls[0]['optional'], forced.optional_bosses)

    def test_tune_prints_the_table_and_the_choice(self):
        _, out = self.tune([])
        text = '\n'.join(RB.tune_report(out))
        self.assertIn('| cutoff | width | floor | max KOs | unwinnable | full lead at Leader X | passes |', text)
        self.assertIn('| 20 | 4 | 20 | 10 | 1 |', text)
        self.assertIn('Chosen: cutoff 20, width 6, floor 30: max 45 KOs', text)
        self.assertIn('  A worst wall: Leader X, 45 KOs from 10 to 30 on Sableye 9', text)
        # None passes: the closest, by unwinnable walls then KOs, with what fails and by how much.
        failing = [r for r in out if not r['passes']]
        none = RB.tune_report(failing)
        start = none.index('No candidate passes the 50-KO budget. Closest:')
        self.assertTrue(none[start + 1].startswith('cutoff 20, width 4, floor 30: max 55 KOs'))
        self.assertIn('  Over the 50-KO budget: Leader X (A) 55 (+5)', none)
        self.assertEqual(sum(line.startswith('cutoff ') for line in none[start:]), RB.TUNE_CLOSEST)
        alone = RB.tune_report([r for r in failing if r['unwinnable']])
        self.assertIn('  Unwinnable: Leader X (B)', alone)

    def test_report_has_solo_walls_section(self):
        def row(boss, starter, ace, lead, wall, sweep, kos, battles=None, rematch=None, exempt=None):
            return {'stage': 'S', 'boss': boss, 'starter': starter, 'ace': ace,
                    'double': boss == 'TRAINER_TATE_AND_LIZA_1', 'lead': lead, 'wall': wall, 'sweep': sweep,
                    'kos': kos, 'source': ['SPECIES_WAILMER', 35], 'battles': battles, 'rematch': rematch,
                    'exempt': exempt}
        res = RB.analyze(FIXTURE, FIXTURE_STAGES, FIXTURE_FORCED)
        # The fixture has none of the real starters: no rows.
        self.assertEqual(res['solo_walls'], [])
        res['solo_walls'] = [
            row('TRAINER_ROXANNE_1', 'TREECKO', 15, 16, 12, 14, 0),
            row('TRAINER_TATE_AND_LIZA_1', 'TREECKO', 42, 44, 60, 70, 80, 9, 'TRAINER_ROSE_5'),
            row('TRAINER_WALLACE', 'TREECKO', 58, 60, 70, 80, 30, 4, 'TRAINER_ROSE_5'),
            row('TRAINER_ROXANNE_1', 'MUDKIP', 15, 16, 10, 12, 0),
            row('TRAINER_MAY_LILYCOVE_MUDKIP', 'MUDKIP', 50, 55, 91, 99, 600, exempt=S.OPTIONAL),
            row('TRAINER_WALLACE', 'MUDKIP', 58, 60, None, None, None, exempt=S.ACCEPTED),
            row('TRAINER_ROXANNE_1', 'TORCHIC', 15, 16, 20, 22, 40),
            row('TRAINER_WALLACE', 'TORCHIC', 58, 60, None, None, None)]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'report.md')
            RB.write_report(path, res)
            with open(path, encoding='utf-8') as f:
                section = f.read().split('## Solo walls\n', 1)[1].split('\n## ', 1)[0]
        self.assertIn('Tate and Liza is a double battle', section)
        self.assertIn('### Treecko line', section)
        self.assertIn('### Mudkip line', section)
        self.assertIn('### Torchic line', section)
        self.assertIn('| boss | ace | lead | wall | sweep | KOs | source |', section)
        self.assertIn('| Roxanne 1 | 15 | 16 | 12 | 14 | 0 | Wailmer 35 |', section)
        self.assertIn('| Tate And Liza 1 (double) | 42 | 44 | 60 | 70 | 80 | Wailmer 35; 9 battles vs Rose 5 |',
                      section)
        self.assertIn('| Wallace | 58 | 60 | unwinnable | - | - | Wailmer 35 |', section)
        self.assertIn('Worst wall: Tate And Liza 1 (80 KOs to level 60).', section)
        # Mudkip: its optional fight and its accepted outlier are marked and outside its worst wall.
        self.assertIn('| May Lilycove Mudkip (optional, not budgeted) | 50 | 55 | 91 | 99 | 600 | Wailmer 35 |',
                      section)
        self.assertIn('| Wallace (accepted outlier) | 58 | 60 | unwinnable | - | - | Wailmer 35 |', section)
        self.assertIn('Worst wall: none above the lead.', section)
        self.assertIn('It leaves out the optional rival fights', section)
        self.assertIn('Worst wall: Wallace (unwinnable); then Roxanne 1 (40 KOs to level 20).', section)


if __name__ == '__main__':
    unittest.main()
