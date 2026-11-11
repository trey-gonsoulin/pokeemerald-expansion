"""Roll a random party of six Pokemon the player can get in Emerald Plus.

Every species the game hands out by normal means (wild tables, gifts, eggs,
static encounters, in-game trades, evolution and breeding) gets its earliest
source, placed on the story stages of tools/rebalance/story_stages.json. A
party is six different evolution families, each reported as the family
member that can be had first, with where and how. Standard library only.

    python3 tools/random_party/random_party.py                 # starter + five others
    python3 tools/random_party/random_party.py --no-starter --legendaries --seed 7
    python3 tools/random_party/random_party.py --list          # every obtainable family
"""

import argparse
import collections
import fnmatch
import json
import os
import random
import re
import sys
from typing import NamedTuple

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(HERE, '..', 'rebalance'))

import gamedata as G  # noqa: E402
import restock as R  # noqa: E402  (gamedata puts tools/area_archetypes on the path)

SOURCES = os.path.join(HERE, 'sources.json')
STAGES = os.path.join(HERE, '..', 'rebalance', 'story_stages.json')
PARTY_SIZE = 6
POSTGAME = 'post-game'

# Evolution conditions the player can always meet sooner or later (friendship,
# time, gender, personality, stats, nature, a move, Pokeblocks, the weather,
# the party, battle feats). IF_HOLD_ITEM needs the item; IF_REGION and
# IF_NOT_REGION are checked against Hoenn; the rest (a map outside Hoenn, a
# trade partner, Leader's Crest kills) can't be met.
FREE_CONDITIONS = frozenset((
    'IF_GENDER', 'IF_TIME', 'IF_NOT_TIME', 'IF_MIN_FRIENDSHIP', 'IF_ATK_GT_DEF', 'IF_ATK_EQ_DEF',
    'IF_ATK_LT_DEF', 'IF_PID_UPPER_MODULO_10_GT', 'IF_PID_UPPER_MODULO_10_LT', 'IF_PID_MODULO_100_GT',
    'IF_PID_MODULO_100_EQ', 'IF_AMPED_NATURE', 'IF_LOW_KEY_NATURE', 'IF_KNOWS_MOVE', 'IF_KNOWS_MOVE_TYPE',
    'IF_MIN_BEAUTY', 'IF_SPECIES_IN_PARTY', 'IF_TYPE_IN_PARTY', 'IF_WEATHER', 'IF_MIN_OVERWORLD_STEPS',
    'IF_USED_MOVE_X_TIMES', 'IF_CRITICAL_HITS_GE', 'IF_RECOIL_DAMAGE_GE', 'IF_CURRENT_DAMAGE_GE'))
# Evolution methods that are a level-up or battle (with FREE_CONDITIONS),
# an item, a trade or Shedinja's split. The rest (Alcremie's spin, the
# scripted Kubfu and Galarian scroll ones) never happen in Hoenn.
LEVEL_METHODS = frozenset(('EVO_LEVEL', 'EVO_LEVEL_BATTLE_ONLY', 'EVO_BATTLE_END'))
TABLE_NAMES = {'land_mons': 'grass', 'water_mons': 'surfing', 'rock_smash_mons': 'Rock Smash',
               'old_rod': 'Old Rod', 'good_rod': 'Good Rod', 'super_rod': 'Super Rod'}


class Source(NamedTuple):
    """How a species (or an item) is first had: ``key`` sorts by stage, then
    by the map's place in the stage; ``how`` and ``where`` are for people."""
    key: tuple
    how: str
    where: str = ''
    direct: bool = True  # caught or given as this species, not evolved or bred


def pretty_map(folder):
    """Route110_TrickHousePuzzle2 -> Route 110 Trick House Puzzle 2."""
    words = re.sub(r'(?<=[a-z])(?=[A-Z0-9])|(?<=[0-9])(?=[A-Z][a-z])', ' ', folder)
    return re.sub(r'\s*_\s*', ' ', words).replace('Pokemon', 'Pokémon').strip()


def species_name(sp):
    return sp.removeprefix('SPECIES_').replace('_', ' ').title()


class Game:
    """The species, items and story stages the tool reads from the repo."""

    def __init__(self, repo=REPO, sources_path=SOURCES, stages_path=STAGES):
        self.repo = repo
        with open(sources_path, encoding='utf-8') as f:
            self.src = json.load(f)
        with open(stages_path, encoding='utf-8') as f:
            self.stages = json.load(f)['stages']
        self.stage_names = [st['name'] for st in self.stages] + [POSTGAME]
        self.defines = R.parse_defines(repo)
        self.info = R.SpeciesInfo(repo)
        texts, _ = R.species_entries(repo, self.defines)
        self.texts = {sp: t for sp, t in texts.items() if sp in self.info.enabled}
        self.names = {sp: (m[1] if (m := re.search(r'\.speciesName\s*=\s*_\("([^"]*)"\)', t)) else species_name(sp))
                      for sp, t in self.texts.items()}
        self.folders = G.map_folders(repo)

    # -- stages ---------------------------------------------------------

    def stage_index(self, name):
        return self.stage_names.index(name)

    def map_key(self, folder, land=False):
        """(stage, order in the stage) of a map, None when it isn't in
        Emerald (FRLG) or only an event ticket opens it. A map in no stage
        is post-game."""
        if folder.endswith('_Frlg') or any(fnmatch.fnmatchcase(folder, g) for g in self.src['deny_maps']):
            return None
        override = self.src['map_overrides'].get(folder)
        if override:
            return (self.stage_index(override['stage']), 0)
        i = G.stage_of(folder, self.stages, land)
        if i is None:
            return (len(self.stages), 0)
        globs = self.stages[i]['maps']
        return (i, next((k for k, g in enumerate(globs) if fnmatch.fnmatchcase(folder, g)), 0))

    def where(self, folder):
        override = self.src['map_overrides'].get(folder)
        name = pretty_map(folder)
        return f'{name} ({override["note"]})' if override and override.get('note') else name

    def stage_label(self, key):
        name = self.stage_names[key[0]]
        return 'post-game' if name == POSTGAME else f'before {name}'

    # -- species facts --------------------------------------------------

    def field(self, sp, name):
        m = re.search(r'\.%s\s*=\s*([^\n]*)' % name, self.texts.get(self.info.canon(sp), ''))
        return m[1] if m else ''

    def flags(self, sp):
        return self.info.flags_of(sp)

    def is_legendary(self, sp):
        return bool(self.flags(sp) & R.LEGENDARY_FLAGS)

    def can_breed(self, sp):
        return 'EGG_GROUP_NO_EGGS_DISCOVERED' not in self.field(sp, 'eggGroups')

    def needs_ditto(self, sp):
        g = self.field(sp, 'genderRatio')
        return 'MON_GENDERLESS' in g or 'MON_MALE' in g

    def held_items(self, sp):
        return [m[1] for f in ('itemCommon', 'itemRare')
                if (m := re.match(r'(ITEM_\w+)', self.field(sp, f))) and m[1] != 'ITEM_NONE']

    def egg_species(self, sp):
        """The species an egg of ``sp`` hatches as: the bottom of its line."""
        seen = {self.info.canon(sp)}
        while True:
            pres = [s for s, method, _ in self.info.pre_evos.get(self.info.canon(sp), ())
                    if method != 'EVO_SPLIT_FROM_EVO' and s not in seen]
            if not pres:
                return sp
            sp = pres[0]
            seen.add(sp)

    def incense_babies(self):
        """Baby -> incense item, when the config still wants one held."""
        if R.c_eval(self.defines.get('P_INCENSE_BREEDING', 'GEN_LATEST'), self.defines) >= R.c_eval('GEN_9', self.defines):
            return {}
        with open(os.path.join(self.repo, 'src', 'daycare.c'), encoding='utf-8') as f:
            return {baby: item for _, item, baby in
                    re.findall(r'\{\s*(SPECIES_\w+),\s*(ITEM_\w+),\s*(SPECIES_\w+)\s*\}', f.read())}

    # -- direct sources -------------------------------------------------

    def wild_sources(self):
        """(species, Source) for every wild slot of an Emerald map."""
        with open(os.path.join(self.repo, 'src', 'data', 'wild_encounters.json'), encoding='utf-8') as f:
            wild = json.load(f)
        by_id = {mid: f for f, mid in self.folders.items()}
        gates = {k: self.stage_index(v) for k, v in self.src['table_gates'].items()}
        for group in wild['wild_encounter_groups']:
            if group.get('label') != 'gWildMonHeaders':
                continue
            rods = {}
            for fld in group.get('fields', ()):
                for rod, slots in (fld.get('groups') or {}).items():
                    rods.update({k: rod for k in slots})
            for enc in group['encounters']:
                folder = by_id.get(enc.get('map'))
                if not folder or any(fnmatch.fnmatchcase(enc.get('base_label', ''), g)
                                     for g in self.src['deny_wild_labels']):
                    continue
                for table, data in enc.items():
                    if not isinstance(data, dict) or 'mons' not in data:
                        continue
                    key = self.map_key(folder, land=table == 'land_mons')
                    if key is None:
                        continue
                    for k, slot in enumerate(data['mons']):
                        kind = rods.get(k, table) if table == 'fishing_mons' else table
                        gate = gates.get(kind)
                        k2 = max(key, (gate, 0)) if gate is not None else key
                        yield slot['species'], Source(k2, f'wild, {TABLE_NAMES[kind]}', self.where(folder))

    def script_sources(self):
        """(species, Source) for gifts, eggs and static encounters in the
        Emerald maps' scripts, and (given, requested, Source) trades."""
        gifts, trades = [], []
        trade_table = self.trade_table()
        for folder in sorted(self.folders):
            path = os.path.join(self.repo, 'data', 'maps', folder, 'scripts.inc')
            key = self.map_key(folder)
            if key is None or not os.path.exists(path):
                continue
            with open(path, encoding='utf-8') as f:
                text = f.read()
            for cmd, sp in re.findall(r'^\s*(givemon|giveegg|setwildbattle)\s+(SPECIES_\w+)', text, re.M):
                how = {'givemon': 'gift', 'giveegg': 'gift egg', 'setwildbattle': 'static encounter'}[cmd]
                gifts.append((sp, Source(key, how, self.where(folder))))
            for t in re.findall(r'\b(INGAME_TRADE_\w+)', text):
                if t in trade_table:
                    given, wanted = trade_table[t]
                    trades.append((given, wanted, Source(key, f'in-game trade for {self.names.get(wanted, wanted)}',
                                                         self.where(folder))))
        for e in self.src['extra']:
            gifts.append((e['species'], Source((self.stage_index(e['stage']), 0), e['method'], e['where'])))
        return gifts, trades

    def trade_table(self):
        with open(os.path.join(self.repo, 'src', 'data', 'trade.h'), encoding='utf-8') as f:
            text = f.read()
        out = {}
        for m in re.finditer(r'\[(INGAME_TRADE_\w+)\]\s*=\s*\{(.*?)\n    \}', text, re.S):
            given = re.search(r'\.species\s*=\s*(SPECIES_\w+)', m[2])
            wanted = re.search(r'\.requestedSpecies\s*=\s*(SPECIES_\w+)', m[2])
            if given and wanted:
                out[m[1]] = (given[1], wanted[1])
        return out

    def item_sources(self):
        """Item -> earliest Source among item balls, hidden items, marts and
        scripted gifts in the Emerald maps."""
        out = {}

        def offer(item, src):
            if item not in out or src.key < out[item].key:
                out[item] = src
        for folder in sorted(self.folders):
            key = self.map_key(folder)
            if key is None:
                continue
            base = os.path.join(self.repo, 'data', 'maps', folder)
            with open(os.path.join(base, 'map.json'), encoding='utf-8') as f:
                data = json.load(f)
            for obj in data.get('object_events') or ():
                item = obj.get('trainer_sight_or_berry_tree_id', '')
                if item.startswith('ITEM_'):
                    offer(item, Source(key, 'item ball', self.where(folder)))
            for bg in data.get('bg_events') or ():
                if str(bg.get('item', '')).startswith('ITEM_'):
                    offer(bg['item'], Source(key, 'hidden item', self.where(folder)))
            path = os.path.join(base, 'scripts.inc')
            if os.path.exists(path):
                with open(path, encoding='utf-8') as f:
                    text = f.read()
                for item in re.findall(r'^\s*\.2byte\s+(ITEM_\w+)', text, re.M):
                    offer(item, Source(key, 'shop', self.where(folder)))
                for item in re.findall(r'^\s*(?:giveitem|finditem|additem)\s+(ITEM_\w+)', text, re.M):
                    offer(item, Source(key, 'gift', self.where(folder)))
        return out


def evolution_needs(game, method, param, conds):
    """The items an evolution needs, or None if it can't happen in Emerald Plus."""
    items = []
    for cond, value in conds:
        if cond == 'IF_HOLD_ITEM':
            items.append(value)
        elif cond == 'IF_REGION' and value != 'REGION_HOENN' or cond == 'IF_NOT_REGION' and value == 'REGION_HOENN':
            return None
        elif cond not in FREE_CONDITIONS | {'IF_REGION', 'IF_NOT_REGION'}:
            return None
    if method in LEVEL_METHODS or method == 'EVO_SPLIT_FROM_EVO':
        return items
    if method == 'EVO_ITEM':
        return items + [param]
    if method == 'EVO_TRADE':
        # I_USE_EVO_HELD_ITEMS_FROM_BAG: a trade item works from the bag like
        # a stone; a trade without one needs the Linking Cord (#208).
        from_bag = items and R.c_eval(game.defines.get('I_USE_EVO_HELD_ITEMS_FROM_BAG', 'FALSE'), game.defines)
        return items if from_bag else items + ['ITEM_LINKING_CORD']
    return None


def item_name(item):
    return item.removeprefix('ITEM_').replace('_', ' ').title()


def obtainable(game):
    """Species -> its earliest Source, found by relaxing evolution, breeding,
    trades and wild held items until nothing gets earlier."""
    best = {}
    items = game.item_sources()

    def offer(table, thing, src):
        if thing not in table or (src.key, not src.direct) < (table[thing].key, not table[thing].direct):
            table[thing] = src
            return True
        return False

    gifts, trades = game.script_sources()
    for sp, src in list(game.wild_sources()) + gifts:
        offer(best, game.info.canon(sp), src)
    start = game.map_key(game.src['starter_map'])
    starters = {game.info.canon(s) for s in game.src['starters']}
    for sp in starters:
        best[sp] = Source(start, 'starter', 'Professor Birch on Route 101')
    daycare = game.map_key(game.src['daycare_map'])
    incense = game.incense_babies()

    changed = True
    while changed:
        changed = False
        for given, wanted, src in trades:
            if wanted in best:
                changed |= offer(best, given, src._replace(key=max(src.key, best[wanted].key)))
        for sp, src in list(best.items()):
            if src.direct and src.how.startswith('wild'):
                for item in game.held_items(sp):
                    changed |= offer(items, item, Source(src.key, f'held by wild {game.names.get(sp, sp)}', src.where))
            for method, param, target, conds in game.info.evos.get(sp, ()):
                needs = evolution_needs(game, method, param, conds)
                if needs is None or any(i not in items for i in needs):
                    continue
                key = max([src.key] + [items[i].key for i in needs])
                how = f'evolve {game.names.get(sp, sp)}' + (f' ({", ".join(map(item_name, needs))})' if needs else '')
                changed |= offer(best, game.info.canon(target), Source(key, how, src.where, direct=False))
            egg = game.egg_species(sp)
            if egg != sp and game.can_breed(sp) and daycare:
                need = [incense[egg]] if egg in incense else []
                if game.needs_ditto(sp):
                    if game.src['ditto'] not in best:
                        continue
                    need_key = [best[game.src['ditto']].key]
                else:
                    need_key = []
                if any(i not in items for i in need):
                    continue
                key = max([src.key, daycare] + need_key + [items[i].key for i in need])
                how = f'breed {game.names.get(sp, sp)} at the Day Care' + (f' ({item_name(need[0])})' if need else '')
                changed |= offer(best, game.info.canon(egg), Source(key, how, game.where(game.src['daycare_map']),
                                                                     direct=False))
    return {sp: src for sp, src in best.items() if sp in game.info.enabled}


def families(game, species):
    """Union the species into evolution families: root -> [members]."""
    parent = {sp: sp for sp in species}

    def find(sp):
        while parent[sp] != sp:
            parent[sp] = parent[parent[sp]]
            sp = parent[sp]
        return sp
    for sp in species:
        for _, _, target, _ in game.info.evos.get(sp, ()):
            target = game.info.canon(target)
            if target in parent:
                parent[find(target)] = find(sp)
    out = collections.defaultdict(list)
    for sp in species:
        out[find(sp)].append(sp)
    return out


class Family(NamedTuple):
    members: tuple  # every obtainable member, earliest first
    first: str  # the member that can be had first
    source: Source
    legendary: bool
    starter: bool


def family_table(game, best):
    """Every obtainable evolution family, each with the member to report."""
    starters = {game.info.canon(s) for s in game.src['starters']}
    out = []
    for members in families(game, sorted(best)).values():
        members.sort(key=lambda sp: (best[sp].key, not best[sp].direct, game.info.min_level(sp), sp))
        out.append(Family(tuple(members), members[0], best[members[0]],
                          any(game.is_legendary(sp) for sp in members), bool(starters & set(members))))
    return sorted(out, key=lambda f: (f.source.key, f.first))


def roll(game, table, rng, starter=True, legendaries=False, postgame=True, size=PARTY_SIZE):
    """[(family, rolled species)]: a random starter (if ``starter``) and
    random other families, each family as likely as any other."""
    pool = [f for f in table if not f.starter and (legendaries or not f.legendary)
            and (postgame or f.source.key[0] < game.stage_index(POSTGAME))]
    party = []
    if starter:
        party.append(rng.choice([f for f in table if f.starter]))
    if len(pool) < size - len(party):
        raise SystemExit(f'only {len(pool)} families fit those options')
    party += rng.sample(pool, size - len(party))
    return [(f, rng.choice(f.members)) for f in party]


def describe(game, fam, rolled=None):
    src = fam.source
    line = f'{game.names[fam.first]:<12} {game.stage_label(src.key):<26} {src.how}'
    if src.where:
        line += f' - {src.where}'
    if rolled and rolled != fam.first:
        line += f'  [rolled {game.names[rolled]}]'
    return line


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('--no-starter', dest='starter', action='store_false',
                   help='six non-starter families instead of a random Hoenn starter and five others')
    p.add_argument('--legendaries', action='store_true', help='let legendaries obtainable in normal play in')
    p.add_argument('--no-postgame', dest='postgame', action='store_false',
                   help="leave out families that can't be had before the Hall of Fame")
    p.add_argument('--seed', type=int, help='seed the roll, to repeat it')
    p.add_argument('--list', action='store_true', help='print every obtainable family instead of rolling')
    args = p.parse_args(argv)

    game = Game()
    table = family_table(game, obtainable(game))
    if args.list:
        for fam in table:
            others = ', '.join(game.names[sp] for sp in fam.members[1:])
            tags = ''.join(t for t, on in ((' [starter]', fam.starter), (' [legendary]', fam.legendary)) if on)
            print(describe(game, fam) + tags + (f'\n{"":13}also: {others}' if others else ''))
        print(f'\n{len(table)} families')
        return
    seed = args.seed if args.seed is not None else random.randrange(1 << 31)
    party = roll(game, table, random.Random(seed), args.starter, args.legendaries, args.postgame)
    print(f'Random party (seed {seed}; starter {"on" if args.starter else "off"}, '
          f'legendaries {"on" if args.legendaries else "off"}, post-game {"on" if args.postgame else "off"}):\n')
    for n, (fam, rolled) in enumerate(sorted(party, key=lambda p: p[0].source.key), 1):
        print(f'{n}. {describe(game, fam, rolled)}')


if __name__ == '__main__':
    main()
