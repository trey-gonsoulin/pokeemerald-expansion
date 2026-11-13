"""Tests for tools/forced_trainers. Run from the repo root:

    python3 -m unittest discover -s tools/forced_trainers
"""

import json
import os
import re
import struct
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'rebalance'))

import classify  # noqa: E402
import engine  # noqa: E402
import gamedata as G  # noqa: E402
import rebalance as RB  # noqa: E402

FLOOR, LEDGE = 0, 1  # metatile ids of the fixture tileset: MB_NORMAL and MB_JUMP_SOUTH


def make_repo(root, rows):
    """A minimal repo whose one layout, LAYOUT_TEST, draws rows: '.' floor, '#' wall, 'v' ledge
    (a one-way jump south). Returns the repo path."""
    files = {
        'include/constants/metatile_behaviors.h': 'enum\n{\n    MB_NORMAL,\n    MB_JUMP_SOUTH,\n};\n',
        'src/data/tilesets/metatiles.h':
            'const u16 gMetatileAttributes_Test[] = INCBIN_U16("data/tilesets/test/metatile_attributes.bin");\n',
        'src/data/tilesets/headers.h':
            'const struct Tileset gTileset_Test =\n{\n    .metatileAttributes = gMetatileAttributes_Test,\n};\n',
        'data/layouts/layouts.json': json.dumps({'layouts': [{
            'id': 'LAYOUT_TEST', 'width': len(rows[0]), 'height': len(rows),
            'primary_tileset': 'gTileset_Test', 'secondary_tileset': 'gTileset_None',
            'blockdata_filepath': 'data/layouts/Test/map.bin'}]}),
    }
    for path, text in files.items():
        os.makedirs(os.path.join(root, os.path.dirname(path)), exist_ok=True)
        with open(os.path.join(root, path), 'w', encoding='utf-8') as f:
            f.write(text)
    os.makedirs(os.path.join(root, 'data/tilesets/test'), exist_ok=True)
    with open(os.path.join(root, 'data/tilesets/test/metatile_attributes.bin'), 'wb') as f:
        f.write(struct.pack('<2H', 0, 1))
    blocks = []
    for row in rows:
        for c in row:
            blocks.append({'.': FLOOR, '#': (1 << 10) | FLOOR, 'v': (1 << 10) | LEDGE}[c])
    os.makedirs(os.path.join(root, 'data/layouts/Test'), exist_ok=True)
    with open(os.path.join(root, 'data/layouts/Test/map.bin'), 'wb') as f:
        f.write(struct.pack('<%dH' % len(blocks), *blocks))
    return root


def trainer(x, y, movement='MOVEMENT_TYPE_FACE_RIGHT', sight=3):
    return {'x': x, 'y': y, 'movement_type': movement, 'trainer_sight_or_berry_tree_id': str(sight),
            'trainer_type': 'TRAINER_TYPE_NORMAL', 'elevation': 0}


def verdict(grid, obj, start, goal):
    """FORCED or AVOIDABLE (and whether only by timing) for one trainer on one route, as classify
    judges it: static trainers that turn can be slipped past by timing."""
    here = {(obj['x'], obj['y'])}
    if engine.path_exists(grid, start, {goal}, here | engine.sight_tiles(grid, obj)):
        return 'AVOIDABLE', False
    turning = len(engine.facing_dirs(obj['movement_type'])) > 1
    if turning and engine.path_exists(grid, start, {goal}, here | engine.sight_tiles(grid, obj, timed=True)):
        return 'AVOIDABLE', True
    return 'FORCED', False


class Fixtures(unittest.TestCase):
    def grid(self, rows):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = make_repo(tmp.name, rows)
        return engine.Grid.from_layout(repo, 'LAYOUT_TEST')

    def test_trainer_seeing_across_the_only_corridor_is_forced(self):
        grid = self.grid(['#.#',
                          '#.#',
                          '..#',
                          '#.#',
                          '#.#'])
        obj = trainer(0, 2)
        self.assertEqual(engine.sight_tiles(grid, obj), {(1, 2)})
        self.assertEqual(verdict(grid, obj, (1, 0), (1, 4)), ('FORCED', False))

    def test_open_field_trainer_is_avoidable(self):
        grid = self.grid(['.....',
                          '.....',
                          '.....',
                          '.....',
                          '.....'])
        obj = trainer(0, 2)
        self.assertEqual(verdict(grid, obj, (1, 0), (1, 4)), ('AVOIDABLE', False))

    def test_wall_blocks_sight(self):
        grid = self.grid(['....#...'])
        self.assertEqual(engine.sight_tiles(grid, trainer(0, 0, sight=7)), {(1, 0), (2, 0), (3, 0)})

    def test_turning_trainer_is_avoidable_by_timing(self):
        grid = self.grid(['#.#',
                          '#.#',
                          '..#',
                          '#.#',
                          '#.#'])
        obj = trainer(0, 2, 'MOVEMENT_TYPE_ROTATE_CLOCKWISE', sight=1)
        self.assertEqual(engine.sight_tiles(grid, obj), {(1, 2)})
        self.assertEqual(engine.sight_tiles(grid, obj, timed=True), set())
        self.assertEqual(verdict(grid, obj, (1, 0), (1, 4)), ('AVOIDABLE', True))

    def test_ledge_is_one_way(self):
        grid = self.grid(['.',
                          'v',
                          '.'])
        self.assertTrue(engine.path_exists(grid, (0, 0), {(0, 2)}, set()))
        self.assertFalse(engine.path_exists(grid, (0, 2), {(0, 0)}, set()))


class RealRepo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = classify.classify(G.REPO)

    def test_committed_file_is_current(self):
        with open(classify.OUTPUT, encoding='utf-8') as f:
            self.assertEqual(self.data, json.load(f), 'rerun python3 tools/forced_trainers/classify.py')

    def test_known_forced(self):
        for tid in ('TRAINER_GRUNT_PETALBURG_WOODS', 'TRAINER_GRUNT_RUSTURF_TUNNEL', 'TRAINER_GRUNT_MUSEUM_1',
                    'TRAINER_GRUNT_MUSEUM_2', 'TRAINER_EDGAR'):
            self.assertEqual(self.data['regular'][tid]['class'], 'FORCED', tid)

    def test_optional_rivals(self):
        """All six May/Brendan x starter teams of the Rustboro and Lilycove fights are skippable."""
        optional = {b for b in self.data['bosses'] if re.match(r'TRAINER_(MAY|BRENDAN)_(RUSTBORO|LILYCOVE)_', b)}
        self.assertEqual(len(optional), 12)
        for b, entry in self.data['bosses'].items():
            self.assertEqual(entry['required'], b not in optional, b)

    def test_every_staged_boss_is_classified(self):
        trainers = G.parse_trainers(os.path.join(G.REPO, 'src', 'data', 'trainers.party'))
        stages = RB.load_stages(os.path.join(G.HERE, 'story_stages.json'), trainers, G.REPO)
        for st in stages:
            for b in st['bosses']:
                self.assertEqual(self.data['bosses'][b]['stage'], st['name'], b)
            for t in st['regular']:
                self.assertIn(self.data['regular'][t]['class'], ('FORCED', 'AVOIDABLE', 'UNCERTAIN'), t)

    def test_choose_one_groups_name_real_trainers(self):
        for tid, entry in self.data['regular'].items():
            for other in entry.get('one_of', ()):
                self.assertIn(other, self.data['regular'], tid)

    def test_other_repo_is_refused(self):
        with self.assertRaises(ValueError):
            classify.classify(os.path.join(G.REPO, 'tools'))


if __name__ == '__main__':
    unittest.main()
