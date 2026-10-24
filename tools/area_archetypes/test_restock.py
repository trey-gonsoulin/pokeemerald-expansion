"""Tests for restocking wild_encounters.json from the archetype pools.

    python3 -m unittest discover -s tools/area_archetypes

These read the committed output/*.json and this repo's headers, so they don't
need the PokeAPI cache.
"""

import json
import os
import shutil
import tempfile
import unittest

import area_archetypes as AA
import restock as R

WILD = os.path.join(AA.REPO, 'src', 'data', 'wild_encounters.json')
POOLS = os.path.join(AA.DEFAULT_OUT, 'archetype_pools.json')
MAPS = os.path.join(AA.DEFAULT_OUT, 'emerald_maps.json')


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


class PreprocessorTests(unittest.TestCase):
    def test_c_eval(self):
        d = {'A': 'TRUE', 'B': 'FALSE', 'C': 'A', 'GEN_3': '2', 'GEN_5': '4', 'LVL': 'GEN_5'}
        self.assertEqual(R.c_eval('A', d), 1)
        self.assertEqual(R.c_eval('B', d), 0)
        self.assertEqual(R.c_eval('C && !B', d), 1)
        self.assertEqual(R.c_eval('B || UNKNOWN', d), 0)
        self.assertEqual(R.c_eval('LVL >= GEN_3', d), 1)
        self.assertEqual(R.c_eval('defined(B) // comment', d), 1)

    def test_function_like_macros_are_skipped(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, 'include', 'config'))
            with open(os.path.join(root, 'include', 'config', 'x.h'), 'w', encoding='utf-8') as f:
                f.write('#define MAX(a, b) ((a) > (b))\n#define GEN 9\n')
            self.assertEqual(R.parse_defines(root), {'GEN': '9'})


class SlotTests(unittest.TestCase):
    def test_most_common_species_take_the_high_rate_slots(self):
        rates = [20, 20, 10, 10, 10, 10, 5, 5, 4, 4, 1, 1]
        slots = R.assign_slots({'A': 0.5, 'B': 0.3, 'C': 0.2}, rates)
        self.assertEqual(len(slots), len(rates))
        self.assertEqual(slots[0], 'A')
        self.assertIn(slots[1], ('A', 'B'))
        got = {s: sum(r for r, x in zip(rates, slots) if x == s) for s in 'ABC'}
        self.assertEqual(got, {'A': 50, 'B': 30, 'C': 20})

    def test_ensure_gives_rare_species_a_slot(self):
        rates = [20, 20, 10, 10, 10, 10, 5, 5, 4, 4, 1, 1]
        targets = {'A': 0.6, 'B': 0.395, 'RARE': 0.005}
        self.assertNotIn('RARE', R.assign_slots(targets, rates))
        slots = R.assign_slots(targets, rates, ensure={'RARE'})
        self.assertEqual(slots.index('RARE'), 11)  # the last 1% slot
        self.assertEqual(slots[0], 'A')

    def test_weighted_sample_is_seeded(self):
        import random
        w = {f'S{i}': 1 + i for i in range(20)}
        a = R.weighted_sample(random.Random('x'), w, 5)
        self.assertEqual(a, R.weighted_sample(random.Random('x'), w, 5))
        self.assertEqual(len(set(a)), 5)


class SpeciesInfoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.info = R.SpeciesInfo(AA.REPO)

    def test_evolution_levels(self):
        i = self.info
        self.assertEqual(i.min_level('SPECIES_BULBASAUR'), 1)
        self.assertEqual(i.min_level('SPECIES_IVYSAUR'), 16)
        self.assertEqual(i.min_level('SPECIES_VENUSAUR'), 32)
        self.assertEqual(i.min_level('SPECIES_SHEDINJA'), 20)
        self.assertGreaterEqual(i.min_level('SPECIES_CROBAT'), R.NONLEVEL_EVO_FLOOR)
        self.assertEqual(i.min_level('SPECIES_PIKACHU'), 1)  # out of a baby: no floor

    def test_devolve(self):
        i = self.info
        self.assertEqual(i.devolve('SPECIES_VENUSAUR', 10), 'SPECIES_BULBASAUR')
        self.assertEqual(i.devolve('SPECIES_VENUSAUR', 20), 'SPECIES_IVYSAUR')
        self.assertEqual(i.devolve('SPECIES_GOLBAT', 22), 'SPECIES_GOLBAT')
        self.assertEqual(i.devolve('SPECIES_CROBAT', 25), 'SPECIES_GOLBAT')
        self.assertEqual(i.devolve('SPECIES_PIKACHU', 3), 'SPECIES_PIKACHU')

    def test_aliases_and_flags(self):
        self.assertIn('SPECIES_BURMY', self.info.enabled)  # = SPECIES_BURMY_PLANT
        self.assertIn('isRestrictedLegendary', self.info.flags_of('SPECIES_MEWTWO'))


class ConfigTests(unittest.TestCase):
    """A family disabled by P_GEN_* / P_FAMILY_* config is never placed."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        for d in ('include/config', 'include/constants', 'src/data/pokemon/species_info'):
            os.makedirs(os.path.join(root, d))
        files = {
            'include/config/species_enabled.h':
                '#define P_GEN_1_POKEMON FALSE\n#define P_GEN_2_POKEMON TRUE\n'
                '#define P_FAMILY_ODDISH P_GEN_1_POKEMON\n#define P_FAMILY_HOOTHOOT P_GEN_2_POKEMON\n',
            'include/constants/species.h':
                'enum {\n    SPECIES_NONE = 0,\n    SPECIES_ODDISH = 43,\n    SPECIES_HOOTHOOT = 163,\n'
                '    SPECIES_NOCTOWL = 164,\n};\n',
            'src/data/pokemon/species_info/gen_1_families.h':
                '#if P_FAMILY_ODDISH\n    [SPECIES_ODDISH] =\n    {\n    },\n#endif\n',
            'src/data/pokemon/species_info/gen_2_families.h':
                '#if P_FAMILY_HOOTHOOT\n    [SPECIES_HOOTHOOT] =\n    {\n'
                '        .evolutions = EVOLUTION({EVO_LEVEL, 20, SPECIES_NOCTOWL}),\n    },\n'
                '    [SPECIES_NOCTOWL] =\n    {\n    },\n#endif\n',
        }
        for path, text in files.items():
            with open(os.path.join(root, path), 'w', encoding='utf-8') as f:
                f.write(text)
        self.info = R.SpeciesInfo(root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_disabled_family(self):
        self.assertEqual(self.info.enabled, {'SPECIES_HOOTHOOT', 'SPECIES_NOCTOWL'})
        pool = [{'species': 'SPECIES_ODDISH', 'share': 0.9, 'introduced_gen': 1},
                {'species': 'SPECIES_NOCTOWL', 'share': 0.1, 'introduced_gen': 2}]
        mons = [{'species': 'SPECIES_NONE', 'min_level': 5, 'max_level': 5}] * 2
        new = R.restock_table(mons, [70, 30], pool, self.info, R.Settings(ratio=1.0), 'gX', 'land_mons')
        self.assertEqual(new, ['SPECIES_HOOTHOOT', 'SPECIES_HOOTHOOT'])  # Noctowl devolved at L5
        # Nothing to place: leave the table alone instead of failing.
        self.assertIsNone(R.restock_table(mons, [70, 30], pool, self.info,
                                          R.Settings(ratio=1.0, new_species=0), 'gX', 'land_mons'))


class RestockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.info = R.SpeciesInfo(AA.REPO)
        cls.wild = load(WILD)
        cls.maps = load(MAPS)
        cls.pools = load(POOLS)
        cls.runs = {ratio: R.restock(cls.wild, cls.maps, cls.pools, cls.info, R.Settings(ratio=ratio))
                    for ratio in (0.0, 0.5, 1.0)}

    def assertSameShape(self, before, after):
        """Same maps, tables, slot counts, rates and levels; only species differ."""
        self.assertEqual(len(before['wild_encounter_groups']), len(after['wild_encounter_groups']))
        for gb, ga in zip(before['wild_encounter_groups'], after['wild_encounter_groups']):
            self.assertEqual({k: v for k, v in gb.items() if k != 'encounters'},
                             {k: v for k, v in ga.items() if k != 'encounters'})
            self.assertEqual(len(gb['encounters']), len(ga['encounters']))
            for eb, ea in zip(gb['encounters'], ga['encounters']):
                self.assertEqual(eb.keys(), ea.keys())
                for field in eb:
                    if not isinstance(eb[field], dict):
                        self.assertEqual(eb[field], ea[field])
                        continue
                    self.assertEqual(eb[field]['encounter_rate'], ea[field]['encounter_rate'])
                    self.assertEqual(len(eb[field]['mons']), len(ea[field]['mons']))
                    for mb, ma in zip(eb[field]['mons'], ea[field]['mons']):
                        self.assertEqual((mb['min_level'], mb['max_level']),
                                         (ma['min_level'], ma['max_level']))
                        self.assertIn(ma['species'], self.info.constants)
                        self.assertIn(ma['species'], self.info.enabled)

    def test_shape_and_species_preserved(self):
        for ratio, (new, _) in self.runs.items():
            with self.subTest(ratio=ratio):
                self.assertSameShape(self.wild, new)

    def test_ratio_zero_changes_nothing(self):
        new, changes = self.runs[0.0]
        self.assertEqual(new, self.wild)
        self.assertEqual(changes, [])

    def test_restocks_hoenn_only_by_default(self):
        new, changes = self.runs[0.5]
        self.assertGreater(len(changes), 100)
        regions = {self.maps[c['label']]['region'] for c in changes}
        self.assertEqual(regions, {'hoenn'})
        group = new['wild_encounter_groups'][0]
        before = {e['base_label']: e for e in self.wild['wild_encounter_groups'][0]['encounters']}
        for enc in group['encounters']:
            if self.maps[enc['base_label']]['region'] != 'hoenn':
                self.assertEqual(enc, before[enc['base_label']])
        for g in range(1, len(new['wild_encounter_groups'])):  # Battle Pyramid/Pike
            self.assertEqual(new['wild_encounter_groups'][g], self.wild['wild_encounter_groups'][g])

    def test_mix_keeps_natives_and_adds_new_species(self):
        _, changes = self.runs[0.5]
        ch = next(c for c in changes if c['label'] == 'gRoute101' and c['table'] == 'land_mons')
        before = {s['before'] for s in ch['slots']}
        after = {s['after'] for s in ch['slots']}
        self.assertTrue(before & after)
        self.assertTrue(after - before)
        new_share = sum(s['rate'] for s in ch['slots'] if s['after'] not in before)
        self.assertAlmostEqual(new_share, 50, delta=10)

    def test_every_native_keeps_a_slot(self):
        _, changes = self.runs[0.5]
        for ch in changes:
            self.assertLessEqual({s['before'] for s in ch['slots']}, {s['after'] for s in ch['slots']},
                                 (ch['label'], ch['table']))

    def test_new_species_fit_slot_levels(self):
        for _, changes in (self.runs[0.5], self.runs[1.0]):
            for ch in changes:
                natives = {s['before'] for s in ch['slots']}
                for s in ch['slots']:
                    sp = s['after']
                    if sp in natives:
                        continue
                    self.assertTrue(self.info.min_level(sp) <= s['levels'][1]
                                    or not self.info.pre_evos.get(self.info.canon(sp)), (ch['label'], s))
                    self.assertFalse(self.info.flags_of(sp) & set(R.LEGENDARY_FLAGS), sp)

    def test_high_rate_slots_get_the_most_common_species(self):
        # Compared by evolution line: devolving can split one pick across stages
        # (Golbat at L22, Zubat at L20) or merge it into another.
        _, changes = self.runs[1.0]
        for ch in changes:
            base = self.info.family
            shares = R.species_shares([dict(s, after=base(s['after'])) for s in ch['slots']], 'after')
            top = max(ch['slots'], key=lambda s: s['rate'])['rate']
            first = base(next(s for s in ch['slots'] if s['rate'] == top)['after'])
            self.assertEqual(shares[first], max(shares.values()), ch['label'])

    def test_deterministic_and_seeded(self):
        again, _ = R.restock(self.wild, self.maps, self.pools, self.info, R.Settings(ratio=0.5))
        self.assertEqual(again, self.runs[0.5][0])
        other, _ = R.restock(self.wild, self.maps, self.pools, self.info, R.Settings(ratio=0.5, seed=99))
        self.assertNotEqual(other, self.runs[0.5][0])

    def test_filters(self):
        s = R.Settings(ratio=1.0, gens={4, 5}, deny={'SPECIES_ZUBAT'},
                       maps={'gRoute101': {'skip': True}, 'gRoute102': {'ratio': 0}})
        _, changes = R.restock(self.wild, self.maps, self.pools, self.info, s)
        gen_of = {e['species']: e['introduced_gen'] for a in self.pools['archetypes'].values()
                  for p in a['pools'].values() for e in p}
        labels = {c['label'] for c in changes}
        self.assertNotIn('gRoute101', labels)
        self.assertNotIn('gRoute102', labels)
        for ch in changes:
            natives = {sl['before'] for sl in ch['slots']}
            for sl in ch['slots']:
                self.assertNotEqual(sl['after'], 'SPECIES_ZUBAT')
                if sl['after'] not in natives and sl['after'] in gen_of:
                    # Devolved species can be from an older gen (Budew -> Roselia's line).
                    self.assertTrue(gen_of[sl['after']] in (4, 5) or
                                    self.info.devolve(sl['after'], 100) != sl['after'], sl)


class CliTests(unittest.TestCase):
    def test_writes_preview_and_report_without_touching_src(self):
        with tempfile.TemporaryDirectory() as tmp:
            wild = os.path.join(tmp, 'wild_encounters.json')
            shutil.copy(WILD, wild)
            out = os.path.join(tmp, 'out')
            R.main(['--wild', wild, '--out-dir', out, '--ratio', '0.25', '--seed', '7'])
            with open(WILD, encoding='utf-8') as f, open(wild, encoding='utf-8') as g:
                self.assertEqual(f.read(), g.read())
            self.assertTrue(os.path.exists(os.path.join(out, 'restock_report.md')))
            preview = os.path.join(out, 'wild_encounters.json')
            R.main(['--wild', wild, '--out-dir', out, '--ratio', '0.25', '--seed', '7', '--write'])
            with open(preview, encoding='utf-8') as f, open(wild, encoding='utf-8') as g:
                self.assertEqual(f.read(), g.read())

    def test_unknown_per_map_species_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = os.path.join(tmp, 'cfg.json')
            with open(cfg, 'w', encoding='utf-8') as f:
                json.dump({'maps': {'gRoute101': {'deny': ['NOT_A_MON']}}}, f)
            with self.assertRaises(SystemExit):
                R.main(['--config', cfg, '--out-dir', os.path.join(tmp, 'out')])

    def test_round_trip_formatting(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'w.json')
            R.dump_wild(load(WILD), path)
            with open(WILD, encoding='utf-8') as f, open(path, encoding='utf-8') as g:
                self.assertEqual(f.read(), g.read())


if __name__ == '__main__':
    unittest.main()
