"""Tests for the area archetype classifier.

    python3 -m unittest discover -s tools/area_archetypes

FixtureBuildTests run the whole build on the small hand-written data set in
testdata/, so they need no pokesearch checkout. The end-to-end tests need the full
PokeAPI cache (`area_archetypes.py fetch`) and are skipped without it.
"""

import contextlib
import csv
import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

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
            with contextlib.redirect_stdout(cls.log), contextlib.redirect_stderr(cls.log):
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
        maps = json.loads(self.read_output('emerald_maps.json'))
        # The cache's provenance.json goes into both JSON outputs as is.
        with open(os.path.join(TESTDATA, 'pokeapi', AA.PROVENANCE_FILE), encoding='utf-8') as f:
            provenance = json.load(f)
        self.assertEqual(provenance['ref'], 'testdata')
        self.assertEqual(doc[AA.PROVENANCE_KEY], provenance)
        self.assertEqual(maps.pop(AA.PROVENANCE_KEY), provenance)
        self.assertEqual(maps.pop(AA.BASE_HASH_KEY), AA.load_base(os.path.join(TESTDATA, 'wild_encounters.json'))[1])
        self.assertEqual(maps, self.emerald)
        self.assertIn(f'PokeAPI ref testdata, fetched {provenance["fetched"]}', self.log.getvalue())
        rows = list(csv.DictReader(io.StringIO(self.read_output('area_classification.csv'))))
        self.assertEqual({(r['version_group'], r['location'], r['area'], r['method_group']): r['archetype']
                          for r in rows}, self.arch)
        self.assertIn('## underwater/mid', self.read_output('archetype_pools.md'))


class CacheTests(unittest.TestCase):
    """fetch copies pokesearch's CSVs atomically and records their provenance; build refuses a bad cache (#52)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        self.cache = shutil.copytree(os.path.join(TESTDATA, 'pokeapi'), os.path.join(self.tmp, 'cache'))
        self.pokesearch = os.path.join(self.tmp, 'pokesearch')
        self.make_pokesearch()

    def make_pokesearch(self):
        """A git checkout holding the fixture CSVs at POKEAPI_REF, in place of any before it."""
        shutil.rmtree(self.pokesearch, ignore_errors=True)
        self.source = shutil.copytree(os.path.join(TESTDATA, 'pokeapi'),
                                      os.path.join(self.pokesearch, AA.POKESEARCH_CSV_DIR))
        self.write_stamp(AA.POKEAPI_REF)
        git = ['git', '-C', self.pokesearch]
        env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        subprocess.run(git + ['init', '-q'], check=True, env=env)
        subprocess.run(git + ['-c', 'user.name=test', '-c', 'user.email=test@example.com', '-c', 'commit.gpgsign=false',
                              'commit', '-q', '--allow-empty', '-m', 'test'], check=True, env=env)
        self.sha = subprocess.run(git + ['rev-parse', 'HEAD'], check=True, env=env,
                                  capture_output=True, text=True).stdout.strip()

    def write_stamp(self, ref):
        with open(os.path.join(self.source, AA.POKESEARCH_STAMP), 'w', encoding='utf-8') as f:
            f.write(ref + '\n')

    def read_cache(self):
        files = {}
        for name in os.listdir(self.cache):
            with open(os.path.join(self.cache, name), 'rb') as f:
                files[name] = f.read()
        return files

    def csv_path(self, name):
        return os.path.join(self.cache, name + '.csv')

    def fetch(self, cache):
        with contextlib.redirect_stdout(io.StringIO()):
            AA.fetch(cache, self.pokesearch, os.path.join(self.tmp, 'out'))

    def write_committed(self, ref, **hashes):
        out = os.path.join(self.tmp, 'out')
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, 'archetype_pools.json'), 'w', encoding='utf-8') as f:
            json.dump({AA.PROVENANCE_KEY: {'ref': ref, 'csv_sha256': hashes}}, f)

    def assertExits(self, fn, *msg):
        with self.assertRaises(SystemExit) as cm:
            fn()
        for m in msg:
            self.assertIn(m, str(cm.exception))

    def test_fetch_copies_the_csvs_and_records_provenance(self):
        cache = os.path.join(self.tmp, 'fresh')
        # A table the build doesn't read, as pokesearch has, isn't copied.
        with open(os.path.join(self.source, 'moves.csv'), 'w', encoding='utf-8') as f:
            f.write('id\n1\n')
        self.fetch(cache)
        self.assertEqual(sorted(os.listdir(cache)),
                         sorted([n + '.csv' for n in AA.CSV_FILES] + [AA.PROVENANCE_FILE]))
        provenance = AA.load_provenance(cache)
        self.assertEqual(provenance['ref'], AA.POKEAPI_REF)
        self.assertEqual(provenance['pokesearch'], self.sha)
        self.assertRegex(provenance['fetched'], r'^\d{4}-\d\d-\d\d$')
        # The fixture's own record has the same hashes: they are the same files.
        with open(os.path.join(self.cache, AA.PROVENANCE_FILE), encoding='utf-8') as f:
            self.assertEqual(provenance['csv_sha256'], json.load(f)['csv_sha256'])

    def test_fetch_refuses_another_pokeapi_ref(self):
        before = self.read_cache()
        self.write_stamp('abc123')
        self.assertExits(lambda: self.fetch(self.cache), 'holds PokeAPI abc123', 'bump POKEAPI_REF')
        self.assertEqual(self.read_cache(), before)

    def test_fetch_refuses_a_bad_source_and_keeps_the_old_cache(self):
        def write_pokemon(body):
            with open(os.path.join(self.source, 'pokemon.csv'), 'wb') as f:
                f.write(body)

        cases = [(lambda: write_pokemon(b''), 'pokemon.csv is empty; run `python -m poke_extract.pokeapi`'),
                 (lambda: write_pokemon(b'wrong,columns\n1,2\n'), 'has no id, identifier, species_id column'),
                 (lambda: write_pokemon(b'id,identifier,species_id\n'), 'has no rows'),
                 (lambda: write_pokemon(b'id,identifier,species_id\n1,ivy\n'), 'line 2 is cut short'),
                 (lambda: write_pokemon(b'id,identifier,species_id\n1,\xff,1\n'), 'not a readable CSV'),
                 (lambda: os.remove(os.path.join(self.source, 'pokemon.csv')), 'No such file'),
                 (lambda: os.remove(os.path.join(self.source, AA.POKESEARCH_STAMP)), 'No such file'),
                 (lambda: shutil.rmtree(os.path.join(self.pokesearch, '.git')), 'not a git checkout')]
        before = self.read_cache()
        for spoil, msg in cases:
            with self.subTest(msg=msg):
                self.make_pokesearch()
                spoil()
                self.assertExits(lambda: self.fetch(self.cache), msg)
                # The CSVs read before the bad one aren't written either.
                self.assertEqual(self.read_cache(), before)

    def test_fetch_refuses_a_csv_the_committed_outputs_dont_record(self):
        # A truncation at a row boundary or an interrupted re-download, under a stamp that still matches.
        before = self.read_cache()
        self.write_committed(AA.POKEAPI_REF, pokemon='0' * 64)
        self.assertExits(lambda: self.fetch(self.cache), 'pokemon.csv is not the file', AA.POKESEARCH_STAMP)
        self.assertEqual(self.read_cache(), before)

    def test_fetch_takes_new_hashes_once_the_ref_is_bumped(self):
        self.write_committed('older-ref', pokemon='0' * 64)
        self.fetch(self.cache)
        self.assertEqual(AA.load_provenance(self.cache)['ref'], AA.POKEAPI_REF)

    def test_fetch_uses_the_pokesearch_and_out_options(self):
        cache = os.path.join(self.tmp, 'fresh')
        self.write_committed(AA.POKEAPI_REF, pokemon='0' * 64)
        args = ['fetch', '--pokesearch', self.pokesearch, '--cache', cache]
        self.assertExits(lambda: AA.main(args + ['--out', os.path.join(self.tmp, 'out')]), 'is not the file')
        with contextlib.redirect_stdout(io.StringIO()):
            AA.main(args + ['--out', os.path.join(self.tmp, 'other')])
        self.assertEqual(AA.load_provenance(cache)['pokesearch'], self.sha)

    def test_fetch_refuses_a_dir_inside_another_checkout(self):
        self.assertExits(lambda: AA.pokesearch_sha(os.path.join(self.pokesearch, 'data')), 'not a git checkout')

    def test_write_atomic_keeps_the_old_file_on_a_failure(self):
        path = os.path.join(self.tmp, 'file')
        AA.write_atomic(path, b'old')
        with mock.patch.object(AA.os, 'replace', side_effect=OSError('disk full')), self.assertRaises(OSError):
            AA.write_atomic(path, b'new')
        with open(path, 'rb') as f:
            self.assertEqual(f.read(), b'old')
        self.assertFalse(os.path.exists(path + '.tmp'))
        AA.write_atomic(path, b'new')
        with open(path, 'rb') as f:
            self.assertEqual(f.read(), b'new')
        self.assertFalse(os.path.exists(path + '.tmp'))

    def test_load_provenance_refuses_an_edited_cache(self):
        with open(self.csv_path('pokemon'), 'a', encoding='utf-8') as f:
            f.write('9999,edited,1\n')
        self.assertExits(lambda: AA.load_provenance(self.cache), 'pokemon.csv is not the file fetch recorded')
        full = {'ref': 'x', 'pokesearch': 'y', 'fetched': 'z', 'csv_sha256': {}}
        for content in ['{"ref": "x"', '[]', '{"ref": "x"}', json.dumps({**full, 'csv_sha256': []}),
                        json.dumps({**full, 'ref': None})] + [
                            json.dumps({k: v for k, v in full.items() if k != key}) for key in full]:
            with self.subTest(content=content):
                with open(os.path.join(self.cache, AA.PROVENANCE_FILE), 'w', encoding='utf-8') as f:
                    f.write(content)
                self.assertExits(lambda: AA.load_provenance(self.cache), 'is not a fetch record')

    def test_load_provenance_warns_on_another_ref(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            AA.load_provenance(self.cache)
        self.assertIn(f'holds PokeAPI testdata, not POKEAPI_REF {AA.POKEAPI_REF}', err.getvalue())

    def test_read_csv_refuses_a_bad_file(self):
        for content, msg in [('', 'is empty'),
                             ('id,identifier\n1,red\n', 'has no species_id column'),
                             ('id,identifier,species_id\n', 'has no rows'),
                             ('id,identifier,species_id\n1,ivy\n', 'line 2 is cut short')]:
            with self.subTest(msg=msg):
                with open(self.csv_path('pokemon'), 'w', encoding='utf-8') as f:
                    f.write(content)
                self.assertExits(lambda: AA.read_csv(self.cache, 'pokemon'), 'pokemon.csv', msg)
        os.remove(self.csv_path('pokemon'))
        self.assertExits(lambda: AA.read_csv(self.cache, 'pokemon'), 'No such file', 'fetch` first')

    def build(self, out):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            AA.build(self.cache, out, AA.REPO, base=os.path.join(TESTDATA, 'wild_encounters.json'))

    def test_build_writes_nothing_from_a_bad_cache(self):
        out = os.path.join(self.tmp, 'out')
        os.remove(os.path.join(self.cache, AA.PROVENANCE_FILE))
        self.assertExits(lambda: self.build(out), 'records no PokeAPI ref')
        self.assertFalse(os.path.exists(out))
        # An empty CSV recorded as such still fails, before anything is written.
        open(self.csv_path('encounters'), 'w').close()
        with open(os.path.join(TESTDATA, 'pokeapi', AA.PROVENANCE_FILE), encoding='utf-8') as f:
            provenance = json.load(f)
        provenance['csv_sha256']['encounters'] = hashlib.sha256(b'').hexdigest()
        with open(os.path.join(self.cache, AA.PROVENANCE_FILE), 'w', encoding='utf-8') as f:
            json.dump(provenance, f)
        self.assertExits(lambda: self.build(out), 'encounters.csv is empty')
        self.assertFalse(os.path.exists(out))

    def test_pokesearch_only_applies_to_fetch(self):
        with contextlib.redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit):
            AA.main(['build', '--pokesearch', self.pokesearch, '--cache', self.cache, '--out', self.tmp])
        self.assertIn('--pokesearch only applies to fetch', err.getvalue())


def map_labels(path):
    with open(path, encoding='utf-8') as f:
        wild = json.load(f)
    return sorted(e['base_label'] for e in AA.map_headers(wild)['encounters'])


class CommittedOutputTests(unittest.TestCase):
    """output/ stays in step with the maps in src/data/wild_encounters.json."""

    def test_vanilla_snapshot_has_every_wild_map(self):
        self.assertEqual(map_labels(AA.VANILLA_WILD), map_labels(AA.SRC_WILD),
                         'output/wild_encounters.vanilla.json is stale; refresh it with '
                         'area_archetypes.py baseline, then run build')

    def test_emerald_maps_has_every_snapshot_map(self):
        with open(os.path.join(AA.DEFAULT_OUT, 'emerald_maps.json'), encoding='utf-8') as f:
            emerald = json.load(f)
        emerald.pop(AA.PROVENANCE_KEY)
        emerald.pop(AA.BASE_HASH_KEY)
        self.assertEqual(sorted(emerald), map_labels(AA.VANILLA_WILD),
                         'output/emerald_maps.json is stale; run area_archetypes.py build')

    def test_emerald_maps_records_the_snapshot_hash(self):
        with open(os.path.join(AA.DEFAULT_OUT, 'emerald_maps.json'), encoding='utf-8') as f:
            recorded = json.load(f)[AA.BASE_HASH_KEY]
        self.assertEqual(recorded, AA.load_base(AA.VANILLA_WILD)[1],
                         'output/emerald_maps.json is stale; run area_archetypes.py build')

    def test_outputs_record_the_pinned_ref(self):
        recorded = []
        for name in ('archetype_pools.json', 'emerald_maps.json'):
            with open(os.path.join(AA.DEFAULT_OUT, name), encoding='utf-8') as f:
                recorded.append(json.load(f)[AA.PROVENANCE_KEY])
        self.assertEqual(recorded[0], recorded[1])
        self.assertEqual(recorded[0]['ref'], AA.POKEAPI_REF,
                         'output/ was built from another PokeAPI ref than POKEAPI_REF; fetch, then build')
        self.assertRegex(recorded[0]['pokesearch'], r'^[0-9a-f]{40}$')
        self.assertEqual(set(recorded[0]['csv_sha256']), set(AA.CSV_FILES))


@unittest.skipUnless(os.path.exists(os.path.join(AA.DEFAULT_CACHE, AA.PROVENANCE_FILE)),
                     'PokeAPI cache missing, or fetched before #52; run area_archetypes.py fetch')
class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.out.cleanup)
        try:
            _, _, tables, cls.pools, cls.emerald = AA.build(AA.DEFAULT_CACHE, cls.out.name, AA.REPO)
        except SystemExit as e:  # keep a stale cache from ending the whole test run
            raise RuntimeError(f'build exited: {e}') from e
        cls.arch = {(t.vg, t.location, t.area, t.group): t.archetype for t in tables}

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
