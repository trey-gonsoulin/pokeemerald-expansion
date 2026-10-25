"""Tests for restocking wild_encounters.json from the archetype pools.

    python3 -m unittest discover -s tools/area_archetypes

These read the committed output/*.json and this repo's headers, so they don't
need the PokeAPI cache.
"""

import argparse
import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest

import area_archetypes as AA
import restock as R

WILD = AA.VANILLA_WILD
POOLS = os.path.join(AA.DEFAULT_OUT, 'archetype_pools.json')
MAPS = os.path.join(AA.DEFAULT_OUT, 'emerald_maps.json')
TESTDATA = os.path.join(AA.HERE, 'testdata')


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
        # No-eggs species that aren't babies keep the floor.
        self.assertGreaterEqual(i.min_level('SPECIES_NIDOQUEEN'), R.NONLEVEL_EVO_FLOOR)
        self.assertGreaterEqual(i.min_level('SPECIES_GHOLDENGO'), R.NONLEVEL_EVO_FLOOR)

    def test_devolve(self):
        i = self.info
        self.assertEqual(i.devolve('SPECIES_VENUSAUR', 10), 'SPECIES_BULBASAUR')
        self.assertEqual(i.devolve('SPECIES_VENUSAUR', 20), 'SPECIES_IVYSAUR')
        self.assertEqual(i.devolve('SPECIES_GOLBAT', 22), 'SPECIES_GOLBAT')
        self.assertEqual(i.devolve('SPECIES_CROBAT', 25), 'SPECIES_GOLBAT')
        self.assertEqual(i.devolve('SPECIES_PIKACHU', 3), 'SPECIES_PIKACHU')

    def test_species_built_from_macros(self):
        i = self.info
        self.assertEqual(i.min_level('SPECIES_SPEWPA'), 9)  # SPEWPA_SPECIES_INFO(...)
        self.assertEqual(i.canon(i.devolve('SPECIES_SPEWPA', 5)), i.canon('SPECIES_SCATTERBUG'))
        self.assertEqual(i.canon(i.devolve('SPECIES_FLOETTE', 5)), i.canon('SPECIES_FLABEBE'))
        self.assertIn('isMythical', i.flags_of('SPECIES_ARCEUS_FIRE'))  # ARCEUS_SPECIES_INFO(...)

    def test_aliases_and_flags(self):
        self.assertIn('SPECIES_BURMY', self.info.enabled)  # = SPECIES_BURMY_PLANT
        self.assertIn('isRestrictedLegendary', self.info.flags_of('SPECIES_MEWTWO'))

    def test_regional_forms_count_as_their_form_generation(self):
        i = self.info
        self.assertEqual(i.gen_of('SPECIES_RATTATA'), 1)
        self.assertEqual(i.gen_of('SPECIES_RATTATA_ALOLA'), 7)
        self.assertEqual(i.gen_of('SPECIES_SANDSLASH_ALOLA'), 7)  # in no pool
        self.assertEqual(i.gen_of('SPECIES_MEOWTH_GALAR'), 8)
        self.assertEqual(i.gen_of('SPECIES_SNEASEL_HISUI'), 8)
        self.assertEqual(i.gen_of('SPECIES_WOOPER_PALDEA'), 9)

    def test_pools_tag_regional_forms_like_their_flags(self):
        """build's name-based tag agrees with species_info's REGIONAL_FLAGS."""
        pools = R.load_json(POOLS)
        tagged = {e['species']: e['introduced_gen'] for a in pools['archetypes'].values()
                  for p in a['pools'].values() for e in p}
        forms = {sp: gen for sp, gen in tagged.items() if self.info.flags_of(sp) & R.REGIONAL_FLAGS}
        self.assertGreaterEqual(len(forms), 20)
        for sp, gen in forms.items():
            self.assertEqual(gen, self.info.gen_of(sp), sp)
        self.assertEqual({sp for sp in tagged if AA.REGIONAL_FORM_RE.search(sp)}, set(forms))


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

    def test_devolves_against_the_slot_min_level(self):
        # A 5-25 slot can roll L5, where Noctowl isn't attainable yet.
        pool = [{'species': 'SPECIES_NOCTOWL', 'share': 1.0, 'introduced_gen': 2}]
        wide = [{'species': 'SPECIES_NONE', 'min_level': 5, 'max_level': 25}] * 2
        self.assertEqual(R.restock_table(wide, [70, 30], pool, self.info, R.Settings(ratio=1.0), 'gX', 'land_mons'),
                         ['SPECIES_HOOTHOOT', 'SPECIES_HOOTHOOT'])
        # So a denied Hoothoot keeps Noctowl out of it too.
        self.assertIsNone(R.restock_table(wide, [70, 30], pool, self.info,
                                          R.Settings(ratio=1.0, deny={'SPECIES_HOOTHOOT'}), 'gX', 'land_mons'))

    def test_deny_covers_devolved_stages(self):
        pool = [{'species': 'SPECIES_NOCTOWL', 'share': 1.0, 'introduced_gen': 2}]
        low = [{'species': 'SPECIES_NONE', 'min_level': 5, 'max_level': 5}] * 2
        high = [{'species': 'SPECIES_NONE', 'min_level': 25, 'max_level': 25}] * 2
        deny = R.Settings(ratio=1.0, deny={'SPECIES_HOOTHOOT'})
        # Noctowl would become Hoothoot at L5, so it isn't drawn at all.
        self.assertIsNone(R.restock_table(low, [70, 30], pool, self.info, deny, 'gX', 'land_mons'))
        self.assertEqual(R.restock_table(high, [70, 30], pool, self.info, deny, 'gX', 'land_mons'),
                         ['SPECIES_NOCTOWL', 'SPECIES_NOCTOWL'])
        # Same for allow lists and gens.
        allow = R.Settings(ratio=1.0, allow={'SPECIES_NOCTOWL'})
        self.assertIsNone(R.restock_table(low, [70, 30], pool, self.info, allow, 'gX', 'land_mons'))
        self.info.gen['SPECIES_HOOTHOOT'] = 1
        gens = R.Settings(ratio=1.0, gens={2})
        self.assertIsNone(R.restock_table(low, [70, 30], pool, self.info, gens, 'gX', 'land_mons'))

    def test_denied_natives_go_even_when_nothing_is_added(self):
        mons = [{'species': 'SPECIES_HOOTHOOT', 'min_level': 5, 'max_level': 5},
                {'species': 'SPECIES_NOCTOWL', 'min_level': 25, 'max_level': 25}]
        for settings in (R.Settings(ratio=0, deny={'SPECIES_NOCTOWL'}),
                         R.Settings(ratio=1.0, deny={'SPECIES_NOCTOWL'})):  # empty pool
            self.assertEqual(R.restock_table(mons, [70, 30], [], self.info, settings, 'gX', 'land_mons'),
                             ['SPECIES_HOOTHOOT', 'SPECIES_HOOTHOOT'])
        self.assertIsNone(R.restock_table(mons, [70, 30], [], self.info,
                                          R.Settings(deny={'SPECIES_NOCTOWL'}, maps={'gX': {'skip': True}}),
                                          'gX', 'land_mons'))

    def test_all_natives_denied_and_nothing_to_draw_warns(self):
        mons = [{'species': 'SPECIES_NOCTOWL', 'min_level': 25, 'max_level': 25}] * 2
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertIsNone(R.restock_table(mons, [70, 30], [], self.info,
                                              R.Settings(deny={'SPECIES_NOCTOWL'}), 'gX', 'land_mons'))
        self.assertIn('gX land_mons: every native is denied', err.getvalue())


class RestockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.info = R.SpeciesInfo(AA.REPO)
        cls.wild = R.load_json(WILD)
        cls.maps = R.load_json(MAPS)
        cls.pools = R.load_json(POOLS)
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
                    self.assertTrue(self.info.min_level(sp) <= s['levels'][0]
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
                if sl['after'] not in natives:
                    # Devolved stages are filtered by gen too.
                    self.assertIn(gen_of.get(sl['after'], self.info.gen_of(sl['after'])), (4, 5), sl)

    def test_deny_is_never_placed_through_devolution(self):
        deny = R.parse_species_list(['RATTATA,EKANS,KRABBY,ZUBAT,MAGIKARP,HOOTHOOT,POLIWAG'])
        for ratio in (0.5, 1.0):
            new, _ = R.restock(self.wild, self.maps, self.pools, self.info, R.Settings(ratio=ratio, deny=deny))
            placed = {m['species'] for e in new['wild_encounter_groups'][0]['encounters']
                      if self.maps[e['base_label']]['region'] == 'hoenn'
                      for f in R.TABLE_FIELDS + ('fishing_mons',) if f in e for m in e[f]['mons']}
            self.assertFalse(placed & deny, ratio)

    def test_regional_forms_can_be_excluded(self):
        _, changes = R.restock(self.wild, self.maps, self.pools, self.info,
                               R.Settings(ratio=1.0, no_regional_forms=True))
        for ch in changes:
            natives = {sl['before'] for sl in ch['slots']}
            for sl in ch['slots']:
                if sl['after'] not in natives:
                    self.assertFalse(self.info.flags_of(sl['after']) & R.REGIONAL_FLAGS, sl)

    def test_gens_use_the_regional_form_generation(self):
        def added(settings):
            _, changes = R.restock(self.wild, self.maps, self.pools, self.info, settings)
            slots = [sl for ch in changes for sl in ch['slots']]
            return {sl['after'] for sl in slots} - {sl['before'] for sl in slots}

        early = added(R.Settings(ratio=1.0, gens={1, 2, 3}))
        self.assertTrue(early)
        self.assertFalse({sp for sp in early if self.info.flags_of(sp) & R.REGIONAL_FLAGS})
        # Alolan forms are Gen 7, and so are their devolved stages (Raticate -> Rattata).
        alola = added(R.Settings(ratio=1.0, gens={7}))
        self.assertIn('SPECIES_RATTATA_ALOLA', alola)
        self.assertTrue(all(self.info.gen_of(sp) == 7 for sp in alola), alola)

    def test_gen_weight_boosts_regional_forms(self):
        pool = [{'species': 'SPECIES_ZIGZAGOON_GALAR', 'share': 0.5, 'introduced_gen': 8},
                {'species': 'SPECIES_ZIGZAGOON', 'share': 0.5, 'introduced_gen': 3}]
        got = R.candidates(pool, self.info, R.Settings(gen_weight={8: 2}), set(), set(), set(), [5])
        self.assertEqual(got, {'SPECIES_ZIGZAGOON_GALAR': 1.0, 'SPECIES_ZIGZAGOON': 0.5})


def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def run_quietly(argv):
    with contextlib.redirect_stdout(io.StringIO()):
        return R.main(argv)


def first_stamp(path):
    return R.load_json(path)[AA.RESTOCK_STAMP]


class CliTests(unittest.TestCase):
    def test_writes_preview_and_report_without_touching_src(self):
        with tempfile.TemporaryDirectory() as tmp:
            wild = os.path.join(tmp, 'wild_encounters.json')
            out = os.path.join(tmp, 'out')
            src = read(AA.SRC_WILD)
            run_quietly(['--wild', wild, '--out-dir', out, '--ratio', '0.25', '--seed', '7'])
            self.assertFalse(os.path.exists(wild))
            self.assertEqual(read(AA.SRC_WILD), src)
            self.assertTrue(os.path.exists(os.path.join(out, 'restock_report.md')))
            preview = os.path.join(out, 'wild_encounters.json')
            run_quietly(['--wild', wild, '--out-dir', out, '--ratio', '0.25', '--seed', '7', '--write'])
            self.assertEqual(read(preview), read(wild))

    def test_rerunning_write_does_not_compound(self):
        with tempfile.TemporaryDirectory() as tmp:
            wild = os.path.join(tmp, 'wild_encounters.json')
            out = os.path.join(tmp, 'out')
            first, _ = run_quietly(['--wild', wild, '--out-dir', out, '--write'])
            written = read(wild)
            again, _ = run_quietly(['--wild', wild, '--out-dir', out, '--write'])
            self.assertEqual(again, first)
            self.assertEqual(read(wild), written)
            self.assertIn(AA.RESTOCK_STAMP, first)

    def test_restocked_base_is_refused_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            wild = os.path.join(tmp, 'wild_encounters.json')
            out = os.path.join(tmp, 'out')
            run_quietly(['--wild', wild, '--out-dir', out, '--write'])
            with self.assertRaises(SystemExit):
                run_quietly(['--base', wild, '--out-dir', out])
            forced, _ = run_quietly(['--base', wild, '--out-dir', out, '--force'])
            self.assertEqual(forced[AA.RESTOCK_STAMP]['base_restocked_by'], first_stamp(wild))
            with self.assertRaises(SystemExit):
                AA.refresh_baseline(wild, os.path.join(tmp, 'base.json'))
            self.assertFalse(os.path.exists(os.path.join(tmp, 'base.json')))

    def test_write_refuses_to_drop_non_species_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            wild = os.path.join(tmp, 'wild_encounters.json')
            out = os.path.join(tmp, 'out')
            edited = R.load_json(WILD)
            edited['wild_encounter_groups'][0]['encounters'].pop()
            R.dump_wild(edited, wild)
            with self.assertRaises(SystemExit):
                run_quietly(['--wild', wild, '--out-dir', out, '--write'])
            self.assertEqual(R.load_json(wild), edited)
            run_quietly(['--wild', wild, '--out-dir', out, '--write', '--force'])
            self.assertEqual(R.skeleton(R.load_json(wild)), R.skeleton(R.load_json(WILD)))

    def test_baseline_copies_a_vanilla_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = os.path.join(tmp, 'base.json')
            with contextlib.redirect_stdout(io.StringIO()):
                AA.main(['baseline', '--wild', WILD, '--base', base])
            self.assertEqual(read(base), read(WILD))

    def test_labels_missing_from_maps_are_reported(self):
        maps = R.load_json(MAPS)
        del maps['gRoute101']
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            R.restock(R.load_json(WILD), maps, R.load_json(POOLS), R.SpeciesInfo(AA.REPO), R.Settings())
        self.assertIn('gRoute101', err.getvalue())

    def test_unknown_per_map_species_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = os.path.join(tmp, 'cfg.json')
            with open(cfg, 'w', encoding='utf-8') as f:
                json.dump({'maps': {'gRoute101': {'deny': ['NOT_A_MON']}}}, f)
            with self.assertRaises(SystemExit):
                R.main(['--config', cfg, '--out-dir', os.path.join(tmp, 'out')])

    def restock_error(self, argv=(), config=None):
        """main()'s usage error for argv (plus a --config with ``config``), with no output written."""
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, 'out')
            argv = list(argv) + ['--out-dir', out]
            if config is not None:
                argv += ['--config', os.path.join(tmp, 'cfg.json')]
                with open(argv[-1], 'w', encoding='utf-8') as f:
                    json.dump(config, f)
            err = io.StringIO()
            with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
                run_quietly(argv)
            self.assertEqual(cm.exception.code, 2)
            self.assertFalse(os.path.exists(out))
            return err.getvalue()

    def test_unknown_config_keys_are_rejected(self):
        self.assertIn("unknown key 'ration'", self.restock_error(config={'ration': 0.0}))
        self.assertIn("unknown key 'allow-legendaries'", self.restock_error(config={'allow-legendaries': True}))
        self.assertIn("gRoute101: unknown per-map key 'gens'",
                      self.restock_error(config={'maps': {'gRoute101': {'gens': '9'}}}))
        self.assertIn("unknown key 'force'", self.restock_error(config={'force': True}))  # command line only

    def test_unknown_map_labels_and_regions_are_rejected(self):
        self.assertIn('gRoute1O1', self.restock_error(config={'maps': {'gRoute1O1': {'skip': True}}}))
        self.assertIn('unknown region: hoen', self.restock_error(config={'regions': 'hoen'}))
        self.assertIn('unknown region: jotho', self.restock_error(['--regions', 'hoenn,jotho']))

    def test_empty_regions_are_rejected(self):
        self.assertIn('regions: empty', self.restock_error(['--regions', '']))
        self.assertIn('regions: empty', self.restock_error(['--regions', ' , ']))
        self.assertIn('regions: empty', self.restock_error(config={'regions': []}))

    def test_reversed_gens_ranges_are_rejected(self):
        self.assertEqual(R.parse_gens('4-9, 1'), {1, 4, 5, 6, 7, 8, 9})
        self.assertEqual(R.parse_gens('5-5'), {5})
        with self.assertRaisesRegex(ValueError, "empty generation range '9-4'"):
            R.parse_gens('1,9-4')
        self.assertIn("got '9-4' (empty generation range '9-4')", self.restock_error(['--gens', '9-4']))
        self.assertIn("gens: expected generations like '4-9' or a list of numbers, got '1,9-4' (empty",
                      self.restock_error(config={'gens': '1,9-4'}))
        self.assertIn("(not a generation or range: '4-x')", self.restock_error(['--gens', '4-x']))

    def test_empty_or_unmatched_gens_are_rejected(self):
        # Leaving gens out is the only way to ask for every generation.
        self.assertIn("got '' (no generations; leave gens out", self.restock_error(['--gens', '']))
        self.assertIn("got ' , ' (no generations", self.restock_error(['--gens', ' , ']))
        self.assertIn('gens: expected generations', self.restock_error(config={'gens': ''}))
        self.assertIn('got [] (no generations', self.restock_error(config={'gens': []}))
        # A set with no pool species would restock nothing, and --write would revert to vanilla.
        self.assertIn('gens: 10,11,12 matches no pool species', self.restock_error(['--gens', '10-12']))
        self.assertIn('gens: 0 matches no pool species', self.restock_error(config={'gens': [0]}))

    def test_bad_option_values_are_rejected(self):
        for config, message in (({'gens': 4}, 'gens:'), ({'gens': '4-x'}, 'gens:'),
                                ({'ratio': 1.5}, 'ratio:'), ({'ratio': '0.5'}, 'ratio:'),
                                ({'seed': True}, 'seed:'), ({'gen_weight': {'four': 2}}, 'gen_weight:'),
                                ({'allow_legendaries': 1}, 'allow_legendaries:'),
                                ({'maps': {'gRoute101': {'ratio': -1}}}, 'gRoute101: ratio:'),
                                ({'maps': {'gRoute101': True}}, 'gRoute101:'), ([], 'JSON object')):
            with self.subTest(config=config):
                self.assertIn(message, self.restock_error(config=config))
        for argv, message in ((['--gen-weight', '4'], 'expected GEN=FACTOR'), (['--ratio', '2'], '--ratio'),
                              (['--new-species', '-1'], '--new-species'), (['--gens', 'x'], '--gens')):
            with self.subTest(argv=argv):
                self.assertIn(message, self.restock_error(argv))

    def test_flags_and_config_merge_into_settings(self):
        args = argparse.ArgumentParser()
        R.add_options(args)
        cfg, errors = R.parse_keys({'ratio': 0.4, 'gens': [4, 5], 'gen_weight': {'4': 2, '5': 3},
                                    'deny': 'zubat', 'allow_legendaries': True,
                                    'maps': {'gRoute101': {'ratio': 0.25, 'allow': ['ODDISH']}}},
                                   R.CONFIG_OPTIONS, 'key')
        self.assertEqual(errors, [])
        s = R.settings_from(args.parse_args(['--seed', '7', '--gen-weight', '5=0.5', '--deny', 'golbat']), cfg)
        self.assertEqual((s.ratio, s.seed, s.gens, s.gen_weight, s.deny, s.allow_legendaries),
                         (0.4, 7, {4, 5}, {4: 2.0, 5: 0.5}, {'SPECIES_GOLBAT'}, True))
        self.assertEqual(s.for_map('gRoute101'),
                         R.MapSettings(0.25, {'SPECIES_ODDISH'}, {'SPECIES_GOLBAT'}, None, False))
        self.assertEqual(R.settings_from(args.parse_args([]), {}), R.Settings())

    def test_species_list_accepts_a_string(self):
        self.assertEqual(R.parse_species_list('ZUBAT, golbat'), {'SPECIES_ZUBAT', 'SPECIES_GOLBAT'})

    def test_restock_must_be_the_first_argument(self):
        with self.assertRaises(SystemExit):
            AA.main(['--out', os.devnull, 'restock'])

    def test_round_trip_formatting(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'w.json')
            R.dump_wild(R.load_json(WILD), path)
            with open(WILD, encoding='utf-8') as f, open(path, encoding='utf-8') as g:
                self.assertEqual(f.read(), g.read())

    def test_committed_wild_encounters_is_the_default_restock(self):
        # Since #28 src/data/wild_encounters.json is `restock --write` with the defaults. restock
        # reads only committed files, so this needs no PokeAPI cache.
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, 'out')
            run_quietly(['--out-dir', out])
            self.assertTrue(read(os.path.join(out, 'wild_encounters.json')) == read(AA.SRC_WILD),
                            f'{AA.SRC_WILD} is no longer what the default restock gives. If the change '
                            f'is intended, rerun `python3 tools/area_archetypes/area_archetypes.py '
                            f'restock --write` and commit the result.')


class FixtureRestockTests(unittest.TestCase):
    def test_rerunning_write_changes_nothing(self):
        """restock --write twice on the testdata/ fixture build: the second run is a no-op (#43, #90)."""
        fixture = os.path.join(TESTDATA, 'wild_encounters.json')
        with tempfile.TemporaryDirectory() as tmp:
            build = os.path.join(tmp, 'build')
            with contextlib.redirect_stdout(io.StringIO()):
                AA.build(os.path.join(TESTDATA, 'pokeapi'), build, AA.REPO, base=fixture)
            base = shutil.copy(fixture, os.path.join(tmp, 'base.json'))
            wild = shutil.copy(fixture, os.path.join(tmp, 'wild.json'))
            # The fixture tables have two slots: they only change once natives can lose theirs.
            argv = ['--base', base, '--wild', wild, '--out-dir', os.path.join(tmp, 'out'), '--write',
                    '--drop-rare-natives', '--pools', os.path.join(build, 'archetype_pools.json'),
                    '--maps', os.path.join(build, 'emerald_maps.json')]
            first, changes = run_quietly(argv)
            self.assertTrue(changes)
            written = read(wild)
            again, changes_again = run_quietly(argv)
            self.assertEqual((again, changes_again), (first, changes))
            self.assertEqual(read(wild), written)
            self.assertEqual(read(base), read(fixture))


if __name__ == '__main__':
    unittest.main()
