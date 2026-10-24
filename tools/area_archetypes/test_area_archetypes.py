"""Tests for the area archetype classifier.

    python3 -m unittest discover -s tools/area_archetypes

The end-to-end tests need the PokeAPI cache (`area_archetypes.py fetch`) and
are skipped without it.
"""

import os
import tempfile
import unittest

import archetypes as A
import area_archetypes as AA


class RuleTests(unittest.TestCase):
    def test_stage_bands(self):
        self.assertEqual(A.stage_for_level(3), 'beginner')
        self.assertEqual(A.stage_for_level(7), 'beginner')
        self.assertEqual(A.stage_for_level(12), 'early')
        self.assertEqual(A.stage_for_level(25), 'mid')
        self.assertEqual(A.stage_for_level(40), 'late')
        self.assertEqual(A.stage_for_level(60), 'endgame')

    def test_area_tokens_drop_neighbour_names(self):
        self.assertEqual(A.area_tokens('south-towards-viridian-city'), ['south'])
        self.assertEqual(A.area_tokens('violet-city-entrance'), [])
        self.assertEqual(A.area_tokens('hidden-grotto-mistralton-cave'), [])
        self.assertEqual(A.area_tokens('exterior-snowfall'), ['exterior', 'snowfall'])

    def test_land_keywords(self):
        cases = {
            'viridian-forest': 'forest',
            'petalburg-woods': 'forest',
            'granite-cave': 'cave',
            'mt-moon': 'cave',
            'pokemon-mansion': 'haunted',
            'desert-resort': 'desert',
            'great-marsh': 'marsh',
            'kanto-route-1': 'route',
        }
        for loc, hab in cases.items():
            with self.subTest(loc=loc):
                self.assertEqual(A.land_habitat(loc, '', {})[0], hab)

    def test_area_keyword_beats_location(self):
        self.assertEqual(A.land_habitat('johto-safari-zone', 'desert', {})[0], 'desert')
        self.assertEqual(A.land_habitat('mt-coronet', 'exterior-snowfall', {})[0], 'ice')
        self.assertEqual(A.land_habitat('kanto-route-2', 'south-towards-viridian-city', {})[0], 'route')

    def test_type_fallbacks(self):
        self.assertEqual(A.land_habitat('some-route', '', {'ice': 0.5})[0], 'ice')
        self.assertEqual(A.land_habitat('some-cave', '', {'ghost': 0.4})[0], 'haunted')
        self.assertEqual(A.land_habitat('some-tower', '', {'ghost': 0.3})[0], 'haunted')
        self.assertEqual(A.land_habitat('some-tower', '', {'normal': 0.6})[0], 'ruins')
        # Overrides are final.
        self.assertEqual(A.land_habitat('hoenn-route-121', '', {'ghost': 0.6})[0], 'route')

    def test_water_habitat(self):
        self.assertEqual(A.water_habitat('union-cave', '1f', {})[0], 'cave_water')
        self.assertEqual(A.water_habitat('kanto-sea-route-19', '', {})[0], 'sea')
        self.assertEqual(A.water_habitat('lake-verity', '', {})[0], 'freshwater')
        self.assertEqual(A.water_habitat('hoenn-route-124', 'underwater', {})[0], 'underwater')
        self.assertEqual(A.water_habitat('hoenn-route-105', '', {'tentacool': 0.6, 'wingull': 0.3})[0], 'sea')
        self.assertEqual(A.water_habitat('kanto-route-6', '', {'goldeen': 0.4, 'psyduck': 0.4})[0], 'freshwater')

    def test_emerald_location_matching(self):
        known = {'hoenn-route-101', 'kanto-sea-route-21', 'monean-chamber', 'tanoby-ruins',
                 'mt-ember', 'shoal-cave', 'kanto-victory-road-2', 'three-isle-port',
                 'kanto-altering-cave'}
        cases = {
            ('MAP_ROUTE101', 'hoenn'): 'hoenn-route-101',
            ('MAP_ROUTE21_NORTH', 'kanto'): 'kanto-sea-route-21',
            ('MAP_SEVEN_ISLAND_TANOBY_RUINS_MONEAN_CHAMBER', 'kanto'): 'monean-chamber',
            ('MAP_SEVEN_ISLAND_TANOBY_RUINS', 'kanto'): 'tanoby-ruins',
            ('MAP_MT_EMBER_RUBY_PATH_B1F', 'kanto'): 'mt-ember',
            ('MAP_SHOAL_CAVE_LOW_TIDE_ICE_ROOM', 'hoenn'): 'shoal-cave',
            ('MAP_VICTORY_ROAD_1F_FRLG', 'kanto'): 'kanto-victory-road-2',
            ('MAP_THREE_ISLAND_PORT', 'kanto'): 'three-isle-port',
            ('MAP_SIX_ISLAND_ALTERING_CAVE', 'kanto'): 'kanto-altering-cave',
        }
        for (map_const, region), want in cases.items():
            with self.subTest(map=map_const):
                self.assertEqual(AA.emerald_location(map_const, region, known), (want, True))
        self.assertEqual(AA.emerald_location('MAP_NOWHERE_1F', 'hoenn', known), ('nowhere-1f', False))


@unittest.skipUnless(os.path.exists(os.path.join(AA.DEFAULT_CACHE, 'encounters.csv')),
                     'PokeAPI cache missing; run area_archetypes.py fetch')
class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = tempfile.TemporaryDirectory()
        _, _, tables, cls.pools, cls.emerald = AA.build(AA.DEFAULT_CACHE, cls.out.name, AA.REPO)
        cls.arch = {(t.vg, t.location, t.area, t.group): t.archetype for t in tables}

    @classmethod
    def tearDownClass(cls):
        cls.out.cleanup()

    def assertArchetype(self, vg, location, area, group, want):
        self.assertEqual(self.arch[(vg, location, area, group)], want, (vg, location, area, group))

    def test_beginner_routes(self):
        self.assertArchetype('red-blue', 'kanto-route-1', '', 'land', 'route/beginner')
        self.assertArchetype('gold-silver', 'johto-route-29', '', 'land', 'route/beginner')
        self.assertArchetype('emerald', 'hoenn-route-101', '', 'land', 'route/beginner')
        self.assertArchetype('diamond-pearl', 'sinnoh-route-201', '', 'land', 'route/beginner')
        self.assertArchetype('sword-shield', 'galar-route-1', '', 'land', 'route/beginner')

    def test_beginner_forests(self):
        self.assertArchetype('red-blue', 'viridian-forest', '', 'land', 'forest/beginner')
        self.assertArchetype('emerald', 'petalburg-woods', '', 'land', 'forest/beginner')
        self.assertArchetype('x-y', 'santalune-forest', '', 'land', 'forest/beginner')

    def test_caves_and_water(self):
        self.assertArchetype('red-blue', 'mt-moon', '1f', 'land', 'cave/early')
        self.assertArchetype('emerald', 'granite-cave', '1f', 'land', 'cave/early')
        self.assertArchetype('emerald', 'hoenn-route-105', '', 'surf', 'sea/mid')
        self.assertArchetype('gold-silver', 'union-cave', '1f', 'surf', 'cave_water/mid')
        self.assertArchetype('emerald', 'hoenn-route-124', 'underwater', 'surf', 'underwater/mid')

    def test_pools_span_generations_and_use_species_constants(self):
        land = self.pools['forest/beginner']['land']
        species = {e['species'] for e in land}
        self.assertIn('SPECIES_CATERPIE', species)
        self.assertIn('SPECIES_WURMPLE', species)
        self.assertGreaterEqual(len({e['introduced_gen'] for e in land}), 4)
        self.assertAlmostEqual(sum(e['share'] for e in land), 1.0, delta=0.05)

    def test_emerald_maps(self):
        self.assertEqual(self.emerald['gRoute101']['land_mons']['archetype'], 'route/beginner')
        self.assertEqual(self.emerald['gPetalburgWoods']['land_mons']['archetype'], 'forest/beginner')
        self.assertEqual(self.emerald['gRoute111']['land_mons']['archetype'].split('/')[0], 'desert')
        self.assertEqual(self.emerald['gUnderwater_Route124']['water_mons']['archetype'].split('/')[0],
                         'underwater')
        self.assertTrue(all(m['matched_pokeapi'] for m in self.emerald.values()))


if __name__ == '__main__':
    unittest.main()
