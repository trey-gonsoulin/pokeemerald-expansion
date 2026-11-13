"""Map grid, trainer sight lines and avoidance search for Emerald story maps."""
import collections
import functools
import glob
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'rebalance'))
import gamedata as G  # noqa: E402

REPO = G.REPO
DIRS = {'down': (0, 1), 'up': (0, -1), 'left': (-1, 0), 'right': (1, 0)}

Tables = collections.namedtuple('Tables', 'mb tilesets layouts folder_of')


def _mb_names(repo):
    """The MB_* behaviour names, in enum order (a metatile attribute's low byte indexes them)."""
    names = []
    inside = False
    with open(os.path.join(repo, 'include/constants/metatile_behaviors.h'), encoding='utf-8') as f:
        for line in f:
            if line.startswith('enum'):
                inside = True
                continue
            if inside:
                m = re.match(r'\s*(MB_\w+)', line)
                if m:
                    names.append(m[1])
                if line.startswith('}'):
                    break
    return names


def _tileset_paths(repo):
    """Tileset symbol -> path of its metatile attribute file."""
    attr_path = {}
    with open(os.path.join(repo, 'src/data/tilesets/metatiles.h'), encoding='utf-8') as f:
        for line in f:
            m = re.search(r'gMetatileAttributes_(\w+)\[\]\s*=\s*INCBIN_U16\("([^"]+)"', line)
            if m:
                attr_path[m[1]] = m[2]
    out = {}
    cur = None
    with open(os.path.join(repo, 'src/data/tilesets/headers.h'), encoding='utf-8') as f:
        for line in f:
            m = re.match(r'const struct Tileset (gTileset_\w+)', line)
            if m:
                cur = m[1]
            m = re.search(r'\.metatileAttributes = gMetatileAttributes_(\w+)', line)
            if m and cur:
                out[cur] = attr_path[m[1]]
    return out


@functools.lru_cache(maxsize=None)
def tables(repo):
    """The repo's behaviour names, tileset attribute paths, layouts by id and map folder by map id."""
    with open(os.path.join(repo, 'data/layouts/layouts.json'), encoding='utf-8') as f:
        layouts = {l['id']: l for l in json.load(f)['layouts'] if 'id' in l}
    folder_of = {}
    for path in glob.glob(os.path.join(repo, 'data/maps/*/map.json')):
        with open(path, encoding='utf-8') as f:
            folder_of[json.load(f)['id']] = os.path.basename(os.path.dirname(path))
    return Tables(_mb_names(repo), _tileset_paths(repo), layouts, folder_of)


FOLDER_OF = tables(REPO).folder_of


def _attrs(repo, tileset):
    with open(os.path.join(repo, tables(repo).tilesets[tileset]), 'rb') as f:
        data = f.read()
    return [v & 0xFF for v in struct.unpack('<%dH' % (len(data) // 2), data)]


@functools.lru_cache(maxsize=None)
def script_trainers(repo):
    """Script label -> trainer ids of its first trainerbattle (all maps + data/scripts)."""
    out = {}
    files = glob.glob(os.path.join(repo, 'data/maps/*/scripts.inc')) + glob.glob(os.path.join(repo, 'data/scripts/*.inc'))
    for path in files:
        label = None
        with open(path, encoding='utf-8') as f:
            for line in f:
                m = re.match(r'(\w+)::', line)
                if m:
                    label = m[1]
                    continue
                m = re.match(r'\s*trainerbattle(\w*)\s', line)
                if m and label and label not in out and 'rematch' not in m[1]:
                    t = re.findall(r'\bTRAINER_(?!NONE\b)\w+', line)
                    if t:
                        out[label] = t
    return out


SCRIPT_TRAINERS = script_trainers(REPO)

WATER = {'MB_POND_WATER', 'MB_INTERIOR_DEEP_WATER', 'MB_DEEP_WATER', 'MB_SOOTOPOLIS_DEEP_WATER', 'MB_OCEAN_WATER',
         'MB_NO_SURFACING', 'MB_FAST_WATER', 'MB_EASTWARD_CURRENT', 'MB_WESTWARD_CURRENT', 'MB_NORTHWARD_CURRENT',
         'MB_SOUTHWARD_CURRENT', 'MB_UNUSED_SOOTOPOLIS_DEEP_WATER', 'MB_UNUSED_SOOTOPOLIS_DEEP_WATER_2',
         'MB_WATER_DOOR', 'MB_WATER_SOUTH_ARROW_WARP', 'MB_SEAWEED', 'MB_DEEP_SOUTH_WARP'}
BIKE = {'MB_MUDDY_SLOPE', 'MB_BUMPY_SLOPE', 'MB_CRACKED_FLOOR', 'MB_ISOLATED_VERTICAL_RAIL',
        'MB_ISOLATED_HORIZONTAL_RAIL', 'MB_VERTICAL_RAIL', 'MB_HORIZONTAL_RAIL'}
SPECIAL = {'MB_ICE', 'MB_SPIN_RIGHT', 'MB_SPIN_LEFT', 'MB_SPIN_UP', 'MB_SPIN_DOWN', 'MB_THIN_ICE', 'MB_CRACKED_ICE',
           'MB_EASTWARD_CURRENT', 'MB_WESTWARD_CURRENT', 'MB_NORTHWARD_CURRENT', 'MB_SOUTHWARD_CURRENT',
           'MB_MOSSDEEP_GYM_WARP', 'MB_AQUA_HIDEOUT_WARP', 'MB_LAVARIDGE_GYM_B1F_WARP', 'MB_LAVARIDGE_GYM_1F_WARP',
           'MB_SECRET_BASE_SPIN_MAT'}
JUMP = {'MB_JUMP_EAST': 'right', 'MB_JUMP_WEST': 'left', 'MB_JUMP_NORTH': 'up', 'MB_JUMP_SOUTH': 'down'}
# Behaviour on the tile being left / entered that blocks the move.
LEAVE_BLOCK = {'right': {'MB_IMPASSABLE_EAST', 'MB_IMPASSABLE_NORTHEAST', 'MB_IMPASSABLE_SOUTHEAST', 'MB_IMPASSABLE_WEST_AND_EAST'},
               'left': {'MB_IMPASSABLE_WEST', 'MB_IMPASSABLE_NORTHWEST', 'MB_IMPASSABLE_SOUTHWEST', 'MB_IMPASSABLE_WEST_AND_EAST'},
               'up': {'MB_IMPASSABLE_NORTH', 'MB_IMPASSABLE_NORTHEAST', 'MB_IMPASSABLE_NORTHWEST', 'MB_IMPASSABLE_SOUTH_AND_NORTH'},
               'down': {'MB_IMPASSABLE_SOUTH', 'MB_IMPASSABLE_SOUTHEAST', 'MB_IMPASSABLE_SOUTHWEST', 'MB_IMPASSABLE_SOUTH_AND_NORTH'}}
OPP = {'right': 'left', 'left': 'right', 'up': 'down', 'down': 'up'}

# Abilities by stage index (0 Rival .. 9 Elite Four).
STAGE_NAMES = ['Rival (Route 103)', 'Roxanne', 'Brawly', 'Wattson', 'Flannery', 'Norman', 'Winona', 'Tate and Liza', 'Juan', 'Elite Four']


def abilities(stage_idx):
    return {'cut': stage_idx >= 2, 'bike': stage_idx >= 3, 'rocksmash': stage_idx >= 4, 'strength': stage_idx >= 5,
            'surf': stage_idx >= 6, 'waterfall': stage_idx >= 9}


def facing_dirs(mt):
    m = mt.replace('MOVEMENT_TYPE_', '')
    if any(k in m for k in ('LOOK_AROUND', 'WANDER_AROUND', 'ROTATE', 'COPY_PLAYER', 'WALK_SEQUENCE', 'BURIED')):
        return list(DIRS)
    if 'DISGUISE' in m:
        return ['down']
    if m.startswith('WANDER_'):
        m = m[len('WANDER_'):]
    out = [d for d in DIRS if re.search(r'(^|_)%s(_|$)' % d.upper(), m)]
    return out or list(DIRS)


class Grid:
    """A layout's tiles: collision, elevation, metatile behaviour name and metatile id by (x, y)."""

    def __init__(self, repo, layout_id):
        t = tables(repo)
        lay = t.layouts[layout_id]
        self.w, self.h = w, h = lay['width'], lay['height']
        with open(os.path.join(repo, lay['blockdata_filepath']), 'rb') as f:
            blocks = struct.unpack('<%dH' % (w * h), f.read())
        primary, secondary = lay['primary_tileset'], lay['secondary_tileset']
        prim = _attrs(repo, primary)
        sec = _attrs(repo, secondary) if secondary in t.tilesets else []
        self.coll, self.elev, self.mb, self.mid = {}, {}, {}, {}
        self.switch_to = {}
        self.warps = []
        for i, b in enumerate(blocks):
            x, y = i % w, i // w
            mid = b & 0x3FF
            beh = prim[mid] if mid < 512 else (sec[mid - 512] if mid - 512 < len(sec) else 0)
            self.coll[x, y] = (b >> 10) & 3
            self.mid[x, y] = mid
            self.elev[x, y] = b >> 12
            self.mb[x, y] = t.mb[beh] if beh < len(t.mb) else 'MB_?'

    @classmethod
    def from_layout(cls, repo, layout_id):
        """The grid of a layouts.json entry (its map.bin and tilesets)."""
        return cls(repo, layout_id)

    def inb(self, p):
        return 0 <= p[0] < self.w and 0 <= p[1] < self.h


def moves(o):
    """True for an object that walks around (so the player can meet it away from its start tile)."""
    mt = o['movement_type']
    return 'WANDER' in mt or ('WALK' in mt and 'IN_PLACE' not in mt)


def sight_tiles(grid, o, blocked=(), timed=False):
    """Tiles from which trainer object o would see the player. Default: conservative union over every
    facing and position. timed=True: for a static trainer that turns, only the tiles it sees in
    every facing (what a player timing its turns can't slip past). Sight stops at walls, at tiles
    in blocked (objects) and at a change of elevation."""
    rng = int(o.get('trainer_sight_or_berry_tree_id') or 0)
    te = o.get('elevation', 0)
    buried = o.get('trainer_type') == 'TRAINER_TYPE_BURIED'
    dirs = list(DIRS) if buried else facing_dirs(o['movement_type'])
    rx, ry = o.get('movement_range_x', 0), o.get('movement_range_y', 0)
    walks = moves(o)
    starts = [(o['x'] + dx, o['y'] + dy) for dx in range(-rx, rx + 1) for dy in range(-ry, ry + 1)] if walks else [(o['x'], o['y'])]
    tiles = set()
    per_dir = []
    for s in starts:
        if not grid.inb(s):
            continue
        for d in dirs:
            line = set()
            dx, dy = DIRS[d]
            for i in range(1, rng + 1):
                p = (s[0] + dx * i, s[1] + dy * i)
                if not grid.inb(p) or grid.coll[p] or (p in blocked and p != (o['x'], o['y'])):
                    break
                e = grid.elev[p]
                if te not in (0, 15) and e not in (0, 15) and e != te:
                    break
                line.add(p)
            per_dir.append(line)
        if walks:
            tiles.add(s)
    if timed and not walks and not buried and len(dirs) > 1:
        return tiles | (set.intersection(*per_dir) if per_dir else set())
    return tiles | set().union(*per_dir)


def path_exists(grid, start, goals, blocked):
    """True if the player can walk from start to any of goals on this one grid, never stepping on a
    tile in blocked. All HMs count as usable; ledges are one-way."""
    ab = {k: True for k in abilities(9)}
    return world_search({'': grid}, {('', start)}, {('', g) for g in goals}, set(), ab,
                        {('', b) for b in blocked}, {'': set()})


class Map(Grid):
    """A map folder: its grid plus connections, warps, objects and the trainers on them."""

    def __init__(self, folder):
        self.folder = folder
        with open(os.path.join(REPO, 'data/maps', folder, 'map.json'), encoding='utf-8') as f:
            self.j = json.load(f)
        super().__init__(REPO, self.j['layout'])
        self.conns = {c['direction']: c['map'] for c in self.j.get('connections') or []}
        self.conn_list = [(c['direction'], c['map'], int(c['offset'])) for c in self.j.get('connections') or []]
        self.warps = self.j.get('warp_events') or []
        self.objects = self.j.get('object_events') or []
        self.trainers = collections.defaultdict(list)  # trainer id -> objects
        for o in self.objects:
            if o.get('type') == 'clone':
                continue
            ts = SCRIPT_TRAINERS.get(o.get('script'))
            if ts and o.get('trainer_type', 'TRAINER_TYPE_NONE') != 'TRAINER_TYPE_NONE':
                for t in ts:
                    self.trainers[t].append(o)
            elif ts:
                for t in ts:
                    self.trainers[t].append(dict(o, talk_only=True))

    def obj_tiles(self, ab):
        """Tiles blocked by objects: every trainer (they never leave), static NPCs without a flag,
        HM obstacles not yet usable, berry trees."""
        out = set()
        for o in self.objects:
            if o.get('type') == 'clone':
                continue
            g, mt, flag = o['graphics_id'], o.get('movement_type', ''), str(o.get('flag', '0'))
            p = (o['x'], o['y'])
            if o.get('script') in SCRIPT_TRAINERS:
                out.add(p)
            elif g == 'OBJ_EVENT_GFX_CUTTABLE_TREE':
                if not ab['cut']:
                    out.add(p)
            elif g == 'OBJ_EVENT_GFX_BREAKABLE_ROCK':
                if not ab['rocksmash']:
                    out.add(p)
            elif g == 'OBJ_EVENT_GFX_PUSHABLE_BOULDER':
                if not ab['strength']:
                    out.add(p)
            elif g == 'OBJ_EVENT_GFX_BERRY_TREE':
                out.add(p)
            elif g == 'OBJ_EVENT_GFX_ITEM_BALL':
                pass
            elif flag in ('0', '') and ('FACE' in mt or mt in ('MOVEMENT_TYPE_NONE',) or 'IN_PLACE' in mt):
                out.add(p)
        return out

    def sight(self, tid, objs_blocked, timed=False):
        """Tiles from which trainer tid would see the player (see sight_tiles), over all its objects."""
        tiles = set()
        for o in self.trainers[tid]:
            if not o.get('talk_only'):
                tiles |= sight_tiles(self, o, objs_blocked, timed)
        return tiles

    def kind(self, tid):
        """'fixed' (one facing, or buried), 'turning' (static, several facings) or 'moving'."""
        k = 'fixed'
        for o in self.trainers[tid]:
            if o.get('talk_only'):
                continue
            if moves(o):
                return 'moving'
            if o.get('trainer_type') != 'TRAINER_TYPE_BURIED' and len(facing_dirs(o['movement_type'])) > 1:
                k = 'turning'
        return k

    def warp_tiles(self, pred):
        return {(w['x'], w['y']) for i, w in enumerate(self.warps) if pred(i, w)}


def world_search(maps, sources, targets, edge_exits, ab, forbidden, objs):
    """BFS over (folder, (x, y), elev, surfing) across the given maps (folder -> Map), following warps
    between them. sources/targets/forbidden: sets of (folder, (x, y)); edge_exits: set of (folder, dir);
    objs: folder -> blocked tiles. True if a target is reachable."""
    warp_at = {}
    for f, m in maps.items():
        for w in m.warps:
            df = FOLDER_OF.get(w['dest_map'])
            try:
                wid = int(w['dest_warp_id'])
            except ValueError:
                continue
            if df in maps and wid < len(maps[df].warps):
                dw = maps[df].warps[wid]
                warp_at[f, (w['x'], w['y'])] = (df, (dw['x'], dw['y']))
            else:
                warp_at.setdefault((f, (w['x'], w['y'])), None)
    q = collections.deque()
    seen = set()

    def push(f, p, e, surf):
        st = (f, p, e, surf)
        if st not in seen:
            seen.add(st)
            q.append(st)

    for f, s in sources:
        m = maps[f]
        if (f, s) in forbidden or not m.inb(s):
            continue
        water = m.mb[s] in WATER
        if water and not ab['surf']:
            continue
        push(f, s, m.elev[s] if m.elev[s] != 15 else 3, water)
    while q:
        f, p, e, surf = q.popleft()
        m = maps[f]
        if (f, p) in targets:
            return True
        ob = objs[f]
        for d, (dx, dy) in DIRS.items():
            t = (p[0] + dx, p[1] + dy)
            if not m.inb(t):
                if (f, p, d) in edge_exits:
                    return True
                continue
            if (f, t) in targets and ((f, t) in warp_at or m.coll[t] or t in ob):
                return True
            if m.mb[p] in LEAVE_BLOCK[d] or m.mb[t] in LEAVE_BLOCK[OPP[d]]:
                continue
            if t in ob:
                continue
            if JUMP.get(m.mb[t]) == d:
                land = (t[0] + dx, t[1] + dy)
                if m.inb(land) and not m.coll[land] and land not in ob and (f, land) not in forbidden:
                    push(f, land, m.elev[land] if m.elev[land] != 15 else e, False)
                continue
            if (f, t) in forbidden:
                continue
            beh = m.mb[t]
            if (f, t) in warp_at:
                dest = warp_at[f, t]
                if dest is not None and (dest[0], dest[1]) not in forbidden:
                    dm = maps[dest[0]]
                    de = dm.elev[dest[1]]
                    push(dest[0], dest[1], de if de != 15 else 3, dm.mb[dest[1]] in WATER)
                if m.coll[t]:
                    continue
            if m.coll[t]:
                continue
            if beh == 'MB_WATERFALL' and not ab['waterfall']:
                continue
            water = beh in WATER or beh == 'MB_WATERFALL'
            if water and not ab['surf']:
                continue
            if beh in BIKE and not ab['bike']:
                continue
            if water != surf:
                ne = m.elev[t] if m.elev[t] != 15 else e
            else:
                te = m.elev[t]
                if e not in (0, 15) and te not in (0, 15) and te != e:
                    continue
                ne = te if te != 15 else e
            push(f, t, ne, water)
            if t in m.switch_to:
                push(m.switch_to[t], t, ne, water)
    return False


# Mauville Gym: MauvilleGymSetDefaultBarriers (src/field_specials.c) swaps every beam on/off.
_MG = dict(FloorTile=0x21A, GH1_Off=0x230, GH1_On=0x220, GH2_Off=0x231, GH2_On=0x221, GH3_Off=0x238, GH3_On=0x228,
           GH4_Off=0x239, GH4_On=0x229, GV1_On=0x240, GV2_On=0x248, PB_Off=0x243, PB_On=0x242, PT_Off=0x251,
           PT_On=0x250, RH1_Off=0x232, RH1_On=0x222, RH2_Off=0x233, RH2_On=0x223, RH3_Off=0x23A, RH3_On=0x22A,
           RH4_Off=0x23B, RH4_On=0x22B, RV1_On=0x241, RV2_On=0x249)


def mauville_gym_toggle(m):
    g = _MG
    rules = {g['GH1_On']: (g['GH1_Off'], 0), g['GH2_On']: (g['GH2_Off'], 0), g['GH3_On']: (g['GH3_Off'], 0),
             g['GH4_On']: (g['GH4_Off'], 0), g['GH1_Off']: (g['GH1_On'], 0), g['GH2_Off']: (g['GH2_On'], 0),
             g['GH3_Off']: (g['GH3_On'], 1), g['GH4_Off']: (g['GH4_On'], 1),
             g['RH1_On']: (g['RH1_Off'], 0), g['RH2_On']: (g['RH2_Off'], 0), g['RH3_On']: (g['RH3_Off'], 0),
             g['RH4_On']: (g['RH4_Off'], 0), g['RH1_Off']: (g['RH1_On'], 0), g['RH2_Off']: (g['RH2_On'], 0),
             g['RH3_Off']: (g['RH3_On'], 1), g['RH4_Off']: (g['RH4_On'], 1),
             g['GV1_On']: (g['PB_On'], 1), g['GV2_On']: (g['FloorTile'], 0), g['RV1_On']: (g['PB_Off'], 1),
             g['RV2_On']: (g['FloorTile'], 0), g['PB_On']: (g['GV1_On'], 1), g['PB_Off']: (g['RV1_On'], 1),
             g['PT_Off']: (g['PT_On'], 1), g['PT_On']: (g['PT_Off'], 0)}
    for y in range(5, 17):
        for x in range(0, 9):
            t = m.mid[x, y]
            if t == g['FloorTile']:
                if m.mid.get((x, y - 1)) == g['GV1_On']:
                    m.mid[x, y], m.coll[x, y] = g['GV2_On'], 1
                elif m.mid.get((x, y - 1)) == g['RV1_On']:
                    m.mid[x, y], m.coll[x, y] = g['RV2_On'], 1
                # (the C code turns any other floor tile into a red beam too, but only beam
                # columns have FloorTile in this range)
            elif t in rules:
                m.mid[x, y], m.coll[x, y] = rules[t]
