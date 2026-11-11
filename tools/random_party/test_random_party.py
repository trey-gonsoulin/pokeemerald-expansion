"""Tests for random_party.py, on the repo's own data (about a second to load)."""

import collections
import io
import random
import unittest
from contextlib import redirect_stdout

import random_party as RP


class PrettyMap(unittest.TestCase):
    def test_splits_words_and_numbers(self):
        self.assertEqual(RP.pretty_map('Route110_TrickHousePuzzle2'), 'Route 110 Trick House Puzzle 2')
        self.assertEqual(RP.pretty_map('GraniteCave_B1F'), 'Granite Cave B1F')
        self.assertEqual(RP.pretty_map('Route117_PokemonDayCare'), 'Route 117 Pokémon Day Care')


class RealRepo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = RP.Game()
        cls.best = RP.obtainable(cls.game)
        cls.table = RP.family_table(cls.game, cls.best)
        cls.by_member = {sp: fam for fam in cls.table for sp in fam.members}

    def family(self, name):
        return self.by_member['SPECIES_' + name]

    def stage(self, fam):
        return self.game.stage_names[fam.source.key[0]]

    def test_babies_report_the_catchable_parent(self):
        pika = self.family('PICHU')
        self.assertEqual(pika.first, 'SPECIES_PIKACHU')
        self.assertIn('Safari Zone', pika.source.where)
        self.assertIn('SPECIES_RAICHU', pika.members)

    def test_a_gift_egg_beats_the_later_parent(self):
        fam = self.family('WOBBUFFET')
        self.assertEqual(fam.first, 'SPECIES_WYNAUT')
        self.assertEqual((fam.source.how, fam.source.where), ('gift egg', 'Lavaridge Town'))

    def test_land_tables_say_grass_cave_or_indoors(self):
        self.assertEqual(self.best['SPECIES_ZIGZAGOON'].how, 'wild, grass')
        self.assertEqual(self.best['SPECIES_GEODUDE'].how, 'wild, cave')
        self.assertEqual(self.best['SPECIES_DUSCLOPS'].how, 'wild, indoors')

    def test_evolved_forms_report_their_base(self):
        fam = self.family('CROBAT')
        self.assertEqual(fam.first, 'SPECIES_ZUBAT')
        self.assertEqual(self.stage(fam), 'Brawly')

    def test_only_evolved_in_the_wild_reports_the_evolved_catch(self):
        # The fork's raised wild levels evolve Bagon into Shelgon; Bagon only hatches.
        fam = self.family('BAGON')
        self.assertEqual(fam.first, 'SPECIES_SHELGON')
        self.assertTrue(self.best['SPECIES_BAGON'].how.startswith('breed Shelgon'))

    def test_a_trade_waits_for_the_species_it_asks_for(self):
        # Pacifidlog's Horsea wants a Bagon, which hatches from Shelgon past Victory
        # Road, so breeding Route 132's Seadra gives Horsea first.
        _, trades = self.game.script_sources()
        horsea = [src for given, _, src in trades if given == 'SPECIES_HORSEA']
        self.assertEqual(self.game.stage_names[max(horsea[0].key, self.best['SPECIES_BAGON'].key)[0]],
                         'Elite Four')
        self.assertEqual(self.stage(self.family('HORSEA')), 'Juan')
        self.assertEqual(self.best['SPECIES_HORSEA'].how, 'breed Seadra at the Day Care')
        self.assertEqual(self.best['SPECIES_MEOWTH'].how, 'in-game trade for Skitty')

    def test_item_evolutions_need_an_obtainable_item(self):
        self.assertIn('SPECIES_VILEPLUME', self.best)  # Leaf Stone
        self.assertIn('SPECIES_ALAKAZAM', self.best)  # Linking Cord
        self.assertNotIn('SPECIES_FROSLASS', self.best)  # Dawn Stone isn't in Hoenn
        self.assertNotIn('SPECIES_RAICHU_ALOLA', self.best)  # Alola only

    def test_no_frlg_event_or_debug_species(self):
        for sp in ('MEWTWO', 'EEVEE', 'SNORLAX', 'MEW', 'DEOXYS', 'LUGIA', 'JIRACHI', 'BULBASAUR'):
            self.assertNotIn('SPECIES_' + sp, self.best, sp)

    def test_post_game_sources(self):
        for sp in ('BELDUM', 'CHIKORITA', 'KYOGRE', 'DITTO', 'MEOWTH'):
            self.assertEqual(self.stage(self.family(sp)), RP.POSTGAME, sp)
        self.assertEqual(self.stage(self.family('REGICE')), 'Juan')

    def test_starters_are_their_own_families(self):
        starters = [f for f in self.table if f.starter]
        self.assertEqual(sorted(f.first for f in starters),
                         ['SPECIES_MUDKIP', 'SPECIES_TORCHIC', 'SPECIES_TREECKO'])

    def test_roll_with_starter(self):
        for seed in range(50):
            party = RP.roll(self.game, self.table, random.Random(seed))
            fams = [f for f, _ in party]
            self.assertEqual(len(set(fams)), RP.PARTY_SIZE)
            self.assertEqual(sum(f.starter for f in fams), 1)
            self.assertFalse(any(f.legendary for f in fams))
            for fam, rolled in party:
                self.assertIn(rolled, fam.members)

    def test_roll_options(self):
        rolls = [RP.roll(self.game, self.table, random.Random(seed), starter=False, legendaries=True,
                         postgame=False) for seed in range(200)]
        fams = [f for party in rolls for f, _ in party]
        self.assertFalse(any(f.starter for f in fams))
        self.assertFalse(any(self.stage(f) == RP.POSTGAME for f in fams))
        self.assertTrue(any(f.legendary for f in fams))

    def test_longer_lines_come_up_more_unless_even(self):
        def count(even):
            seen = collections.Counter()
            for seed in range(2000):
                party = RP.roll(self.game, self.table, random.Random(seed), starter=False, even=even)
                seen.update(f.first for f, _ in party)
            return seen['SPECIES_WURMPLE'] / seen['SPECIES_SABLEYE']  # five members to one
        self.assertGreater(count(False), 3)
        self.assertLess(count(True), 1.5)

    def test_same_seed_same_party(self):
        out = []
        for _ in range(2):
            buf = io.StringIO()
            with redirect_stdout(buf):
                RP.main(['--seed', '42'])
            out.append(buf.getvalue())
        self.assertEqual(out[0], out[1])
        self.assertEqual(out[0].count('\n'), RP.PARTY_SIZE + 2)


if __name__ == '__main__':
    unittest.main()
