"""Tests for the area archetype classifier.

    python3 -m unittest discover -s tools/area_archetypes

FixtureBuildTests run the whole build on the small hand-written data set in
testdata/, so they need no network. The end-to-end tests need the full
PokeAPI cache (`area_archetypes.py fetch`) and are skipped without it.
"""

import contextlib
import csv
import io
import json
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

    def test_regional_forms_count_as_their_form_generation(self):
        self.assertEqual(AA.introduced_gen('SPECIES_RATTATA_ALOLA', 1), 7)
        self.assertEqual(AA.introduced_gen('SPECIES_ZIGZAGOON_GALAR', 3), 8)
        self.assertEqual(AA.introduced_gen('SPECIES_DARMANITAN_GALAR_ZEN', 5), 8)
        self.assertEqual(AA.introduced_gen('SPECIES_SNEASEL_HISUI', 2), 8)
        self.assertEqual(AA.introduced_gen('SPECIES_TAUROS_PALDEA_COMBAT', 1), 9)
        self.assertEqual(AA.introduced_gen('SPECIES_RATTATA', 1), 1)
        self.assertEqual(AA.introduced_gen('SPECIES_GALARIAN_TEST', 4), 4)  # whole tokens only

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


TESTDATA = os.path.join(AA.HERE, 'testdata')


class FixtureBuildTests(unittest.TestCase):
    """The whole build on testdata/: a hand-written PokeAPI CSV set and Emerald map list.

    Two version groups (red-blue, emerald) and five locations, plus rows each
    build_tables filter should drop: an unlisted method (gift), a rarity-0
    slot, a skipped area (gym) and a skipped location (unknown-*). The
    species constants come from this repo's species.h.
    """

    @classmethod
    def setUpClass(cls):
        cls.out = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.out.cleanup)
        cls.log = io.StringIO()
        try:
            with contextlib.redirect_stdout(cls.log):
                _, cls.smap, tables, cls.pools, cls.emerald = AA.build(
                    os.path.join(TESTDATA, 'pokeapi'), cls.out.name, AA.REPO,
                    base=os.path.join(TESTDATA, 'wild_encounters.json'))
        except SystemExit as e:  # keep a broken fixture from ending the whole test run
            raise RuntimeError(f'build exited: {e}') from e
        cls.arch = {(t.vg, t.location, t.area, t.group): t.archetype for t in tables}

    def read_output(self, name):
        with open(os.path.join(self.out.name, name), encoding='utf-8') as f:
            return f.read()

    def test_species_map(self):
        # A form with no constant of its own falls back to its species; the
        # lowest pokemon id is the one a constant maps back to.
        self.assertEqual(self.smap.to_const['10901'], 'SPECIES_TENTACOOL')
        self.assertEqual(self.smap.from_const['SPECIES_TENTACOOL'], '72')
        self.assertEqual(self.smap.unmapped, {'fixture-unmapped'})

    def test_tables_and_archetypes(self):
        self.assertEqual(self.arch, {
            ('red-blue', 'kanto-route-1', '', 'land'): 'route/beginner',
            ('red-blue', 'viridian-forest', '', 'land'): 'forest/beginner',
            ('emerald', 'hoenn-route-101', '', 'land'): 'route/beginner',
            ('emerald', 'hoenn-route-105', '', 'surf'): 'sea/mid',
            ('emerald', 'hoenn-route-105', '', 'fish_old'): 'sea/early',
            ('emerald', 'hoenn-route-105', 'underwater', 'surf'): 'underwater/mid',
            ('emerald', 'hoenn-route-124', 'underwater', 'surf'): 'underwater/mid',
        })

    def test_pools(self):
        self.assertEqual({a: set(p) for a, p in self.pools.items()}, {
            'route/beginner': {'land'},
            'forest/beginner': {'land'},
            'sea/mid': {'surf'},
            'sea/early': {'fish_old'},
            'underwater/mid': {'surf'},
        })
        for arch, groups in self.pools.items():
            for group, entries in groups.items():
                with self.subTest(arch=arch, group=group):
                    # Viridian Forest's third is a form with no SPECIES_ constant,
                    # which pools leave out.
                    want = 2 / 3 if arch == 'forest/beginner' else 1.0
                    self.assertAlmostEqual(sum(e['share'] for e in entries), want, places=3)
        self.assertIn('wild forms with no SPECIES_ constant (left out of pools): fixture-unmapped',
                      self.log.getvalue())
        # Each version group counts equally: red-blue's route 1 (both versions)
        # and emerald's route 101 each contribute half.
        route = {e['species']: e for e in self.pools['route/beginner']['land']}
        self.assertEqual({sp: e['share'] for sp, e in route.items()},
                         {'SPECIES_PIDGEY': 0.3, 'SPECIES_POOCHYENA': 0.3,
                          'SPECIES_RATTATA': 0.2, 'SPECIES_WURMPLE': 0.2})
        self.assertEqual(route['SPECIES_PIDGEY'], {
            'species': 'SPECIES_PIDGEY', 'share': 0.3, 'games': 1, 'introduced_gen': 1,
            'types': ['normal', 'flying'], 'levels': [2, 4]})
        fish = {e['species']: e['share'] for e in self.pools['sea/early']['fish_old']}
        self.assertEqual(fish, {'SPECIES_MAGIKARP': 0.7, 'SPECIES_TENTACOOL': 0.3})

    def test_emerald_maps(self):
        fields = {label: {k: m[k]['archetype'] for k in AA.EMERALD_FIELDS if k in m}
                  for label, m in self.emerald.items()}
        self.assertEqual(fields, {
            'gRoute101': {'land_mons': 'route/beginner'},
            'gRoute1_FireRed': {'land_mons': 'route/beginner'},
            'gPetalburgWoods': {'land_mons': 'forest/beginner'},
            'gRoute105': {'water_mons': 'sea/mid'},
            'gUnderwater_Route124': {'water_mons': 'underwater/mid'},
            'gRoute124': {'water_mons': 'sea/mid'},
            # Its land table has no species the fixture knows, so it's dropped.
            'gLilycoveCity': {'water_mons': 'sea/mid'},
            'gGraniteCave_1F': {'rock_smash_mons': 'cave/early'},
        })
        # Super rod only has a species the fixture doesn't know.
        self.assertEqual(self.emerald['gRoute105']['fishing_mons'], {
            'old_rod': {'archetype': 'sea/beginner', 'pool': 'fish_old', 'level': 5.0},
            'good_rod': {'archetype': 'sea/early', 'pool': 'fish_good', 'level': 10.0},
        })

    def test_emerald_location_and_region(self):
        where = {label: (m['location'], m['matched_pokeapi'], m['region'])
                 for label, m in self.emerald.items()}
        self.assertEqual(where['gRoute101'], ('hoenn-route-101', True, 'hoenn'))
        self.assertEqual(where['gRoute1_FireRed'], ('kanto-route-1', True, 'kanto'))
        self.assertEqual(where['gPetalburgWoods'], ('petalburg-woods', False, 'hoenn'))
        self.assertEqual(where['gUnderwater_Route124'], ('hoenn-route-124', True, 'hoenn'))

    def test_emerald_water_reasons(self):
        reason = {label: m['reason']['water'] for label, m in self.emerald.items()}
        self.assertEqual(reason['gRoute105'], 'pokeapi-majority:hoenn-route-105')
        self.assertEqual(reason['gUnderwater_Route124'], 'area:underwater')
        # Route 124's only PokeAPI water table is underwater, which doesn't vote,
        # so its surface water falls back to the rules.
        self.assertEqual(reason['gRoute124'], 'species:marine1.00>fresh0.00')
        self.assertEqual(reason['gLilycoveCity'], 'species:marine1.00>fresh0.00')
        self.assertIsNone(reason['gRoute101'])
        self.assertEqual(self.emerald['gLilycoveCity']['reason']['land'], 'keyword:lilycove-city')

    def test_written_outputs(self):
        doc = json.loads(self.read_output('archetype_pools.json'))
        # A list, so the archetype order (habitat, then stage) is checked too.
        self.assertEqual([(a, v['generations'], v['sources']) for a, v in doc['archetypes'].items()], [
            ('route/beginner', [1, 3], ['emerald:hoenn-route-101', 'red-blue:kanto-route-1']),
            ('forest/beginner', [1], ['red-blue:viridian-forest']),
            ('sea/early', [3], ['emerald:hoenn-route-105']),
            ('sea/mid', [3], ['emerald:hoenn-route-105']),
            ('underwater/mid', [3], ['emerald:hoenn-route-105', 'emerald:hoenn-route-124']),
        ])
        self.assertEqual({a: v['pools'] for a, v in doc['archetypes'].items()}, self.pools)
        self.assertEqual(json.loads(self.read_output('emerald_maps.json')), self.emerald)
        rows = list(csv.DictReader(io.StringIO(self.read_output('area_classification.csv'))))
        self.assertEqual({(r['version_group'], r['location'], r['area'], r['method_group']): r['archetype']
                          for r in rows}, self.arch)
        self.assertIn('## underwater/mid', self.read_output('archetype_pools.md'))


def map_labels(path):
    with open(path, encoding='utf-8') as f:
        wild = json.load(f)
    group = next(g for g in wild['wild_encounter_groups'] if g['label'] == 'gWildMonHeaders')
    return sorted(e['base_label'] for e in group['encounters'])


class CommittedOutputTests(unittest.TestCase):
    """output/ stays in step with the maps in src/data/wild_encounters.json."""

    def test_vanilla_snapshot_has_every_wild_map(self):
        self.assertEqual(map_labels(AA.VANILLA_WILD), map_labels(AA.SRC_WILD),
                         'output/wild_encounters.vanilla.json is stale; refresh it with '
                         'area_archetypes.py baseline, then run build')

    def test_emerald_maps_has_every_snapshot_map(self):
        with open(os.path.join(AA.DEFAULT_OUT, 'emerald_maps.json'), encoding='utf-8') as f:
            emerald = json.load(f)
        self.assertEqual(sorted(emerald), map_labels(AA.VANILLA_WILD),
                         'output/emerald_maps.json is stale; run area_archetypes.py build')


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
