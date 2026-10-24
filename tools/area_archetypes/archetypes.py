"""Archetype taxonomy and classification rules.

An archetype is ``<habitat>/<stage>``:

* ``habitat`` is the kind of place (route, forest, cave, sea, ...). Land-style
  tables (grass, rock smash, headbutt) get a land habitat; surf and fishing
  tables get a water habitat.
* ``stage`` is how far into a game the table sits, from its encounter levels.

So Kanto Route 1, Johto Route 29 and Hoenn Route 101 grass are all
``route/beginner``; Viridian Forest and Petalburg Woods are ``forest/beginner``.

Everything here is data plus small pure functions so the rules can be tuned
without touching the pipeline in ``area_archetypes.py``.
"""

import re

LAND_HABITATS = [
    'route',      # ordinary grassy route / field
    'forest',     # forests, woods, jungles, groves
    'meadow',     # flower fields, gardens, parks
    'cave',       # caves, tunnels, mines, cave dungeons
    'mountain',   # outdoor rocky slopes, canyons, cliffs, badlands
    'desert',     # sand deserts, dust bowls
    'volcanic',   # volcanoes, ash fields, magma
    'ice',        # snowfields and ice caves
    'marsh',      # swamps, marshes, moors, wetlands
    'beach',      # beaches, coasts, shores, island fringes
    'haunted',    # towers of the dead, cemeteries, abandoned/haunted buildings
    'urban',      # cities, sewers, power plants, factories, labs
    'ruins',      # ancient ruins, chambers, shrines, sacred towers
    'safari',     # safari-style preserves
]
WATER_HABITATS = [
    'sea',         # ocean routes, bays, coastal towns
    'freshwater',  # lakes, rivers, ponds
    'cave_water',  # water inside caves
    'underwater',  # dive / seaweed areas
]
HABITATS = LAND_HABITATS + WATER_HABITATS

# (stage, highest table level that still counts as that stage). A table's level
# is the encounter-weighted mean of its slots' (min + max) / 2.
STAGES = [
    ('beginner', 7),
    ('early', 17),
    ('mid', 30),
    ('late', 44),
    ('endgame', 999),
]
STAGE_NAMES = [s for s, _ in STAGES]


def stage_for_level(level):
    for stage, top in STAGES:
        if level <= top:
            return stage
    return STAGES[-1][0]


# Encounter method -> (method group, weight). Weight scales a method's slot
# rarities when it shares a group with other methods, so rare "spots", hordes
# and ambushes don't drown out the main grass table. Methods not listed are
# ignored (gifts, statics, raids, trades, roamers, scripted one-offs, SOS).
METHODS = {
    'walk': ('land', 1.0),
    'dark-grass': ('land', 1.0),
    'overworld': ('land', 1.0),
    'overworld-dirt': ('land', 1.0),
    'overworld-flying': ('land', 1.0),
    'wanderer': ('land', 1.0),
    'rough-terrain': ('land', 1.0),
    'yellow-flowers': ('land', 1.0),
    'purple-flowers': ('land', 1.0),
    'red-flowers': ('land', 1.0),
    'grass-spots': ('land', 0.25),
    'cave-spots': ('land', 0.25),
    'bridge-spots': ('land', 0.25),
    'horde': ('land', 0.25),
    'hidden-grotto': ('land', 0.25),
    'overworld-special': ('land', 0.25),
    'overworld-flying-special': ('land', 0.25),
    'ceiling-ambush': ('land', 0.25),
    'ground-ambush': ('land', 0.25),
    'sky-ambush': ('land', 0.25),
    'rustling-bush-ambush': ('land', 0.25),
    'trash-can-ambush': ('land', 0.25),
    'surf': ('surf', 1.0),
    'overworld-water': ('surf', 1.0),
    'wanderer-water': ('surf', 1.0),
    'surf-spots': ('surf', 0.25),
    'seaweed': ('underwater', 1.0),
    'old-rod': ('fish_old', 1.0),
    'good-rod': ('fish_good', 1.0),
    'super-rod': ('fish_super', 1.0),
    'super-rod-spots': ('fish_super', 0.25),
    'bubbling-spots': ('fish_super', 0.25),
    'rock-smash': ('rock_smash', 1.0),
    'headbutt': ('tree', 1.0),
    'headbutt-low': ('tree', 1.0),
    'headbutt-normal': ('tree', 1.0),
    'headbutt-high': ('tree', 1.0),
    'honey-tree': ('tree', 1.0),
    'berry-trees': ('tree', 0.25),
}
LAND_GROUPS = ['land', 'rock_smash', 'tree']
WATER_GROUPS = ['surf', 'fish_old', 'fish_good', 'fish_super']
METHOD_GROUPS = LAND_GROUPS + WATER_GROUPS

# Locations that aren't real places (event buckets) or only hold raid dens.
SKIP_LOCATION_PREFIXES = ('unknown-', 'dyna-tree-hill')

# ---------------------------------------------------------------------------
# Land habitat rules
# ---------------------------------------------------------------------------

# Ordered (habitat, tokens). A location/area identifier is split on '-' and the
# first rule with a matching token wins, so put more specific habitats first.
LAND_KEYWORD_RULES = [
    ('haunted', {'cemetery', 'graveyard', 'mansion', 'chateau', 'megamart'}),
    ('volcanic', {'volcano', 'fiery', 'magma', 'chimney', 'scorched', 'lava'}),
    ('ice', {'ice', 'icy', 'icefall', 'frost', 'frostpoint', 'snow', 'snowfall', 'blizzard',
             'snowslide', 'glacier', 'frigid', 'tundra', 'snowpoint', 'lanakila'}),
    ('desert', {'desert', 'sand', 'sandy', 'dunes', 'wasteland'}),
    ('marsh', {'marsh', 'marshland', 'swamp', 'wetland', 'wetlands', 'moor', 'bog'}),
    ('safari', {'safari'}),
    ('cave', {'cave', 'caves', 'cavern', 'tunnel', 'mine', 'well', 'underpass', 'mt',
              'victory', 'den', 'chasm'}),
    ('ruins', {'ruins', 'ruin', 'relic', 'chamber', 'alph', 'shrine', 'temple', 'pillar',
               'tower', 'dreamyard'}),
    ('forest', {'forest', 'woods', 'wood', 'grove', 'jungle', 'weald', 'tangle', 'bush'}),
    ('meadow', {'meadow', 'garden', 'flower', 'park', 'berry'}),
    ('beach', {'beach', 'beachfront', 'coast', 'shore', 'cape', 'bay', 'lagoon', 'island',
               'isle', 'resort'}),
    ('mountain', {'mountain', 'mount', 'canyon', 'cliff', 'crag', 'peak', 'summit', 'pass',
                  'slope', 'rocky', 'badlands', 'wilderness'}),
    ('urban', {'city', 'town', 'village', 'sewers', 'plant', 'ironworks', 'windworks',
               'factory', 'laboratory', 'lab', 'complex', 'storage', 'hotel', 'port'}),
]

# Sub-areas that are buildings inside a town rather than wild places.
SKIP_AREAS = {'gym'}

# Manual habitat for places the keywords get wrong. Keys are PokeAPI location
# identifiers, or "location/area" for one sub-area. These are final: the
# type-based fallbacks below don't override them.
LAND_OVERRIDES = {
    # Kanto
    'kanto-power-plant': 'urban',
    'pokemon-tower': 'haunted',
    'lost-cave': 'haunted',
    'mt-ember': 'volcanic',
    'seafoam-islands': 'ice',
    'icefall-cave': 'ice',
    'memorial-pillar': 'route',
    'ruin-valley': 'route',
    'pattern-bush': 'forest',
    'water-path': 'route',
    'green-path': 'route',
    'kindle-road': 'route',
    'bond-bridge': 'route',
    'three-isle-port': 'route',
    'canyon-entrance': 'mountain',
    'sevault-canyon': 'mountain',
    'kanto-altering-cave': 'cave',
    'kanto-route-28': 'mountain',
    # Johto
    'burned-tower': 'haunted',
    'bell-tower': 'ruins',
    'sprout-tower': 'ruins',
    'national-park': 'meadow',
    'tohjo-falls': 'cave',
    'whirl-islands': 'cave',
    'dragons-den': 'cave',
    'mt-silver/outside': 'mountain',
    'mt-silver/mountainside': 'mountain',
    'mt-silver/top': 'mountain',
    'lake-of-rage': 'route',
    # Hoenn
    'hoenn-route-111': 'desert',
    'mirage-tower': 'desert',
    'desert-underpass': 'cave',
    'hoenn-route-112': 'mountain',
    'hoenn-route-113': 'volcanic',
    'hoenn-route-121': 'route',
    'hoenn-route-123': 'route',
    'hoenn-altering-cave': 'cave',
    'jagged-pass': 'volcanic',
    'mt-pyre': 'haunted',
    'meteor-falls': 'cave',
    'shoal-cave': 'ice',
    'sky-pillar': 'ruins',
    'new-mauville': 'urban',
    'mirage-island': 'route',
    'mirage-spot-island': 'route',
    'scorched-slab': 'cave',
    # Sinnoh
    'iron-island': 'cave',
    'oreburgh-gate': 'cave',
    'ravaged-path': 'cave',
    'stark-mountain': 'volcanic',
    'acuity-lakefront': 'ice',
    'lake-acuity': 'ice',
    'sinnoh-route-216': 'ice',
    'sinnoh-route-217': 'ice',
    'sinnoh-route-206': 'mountain',
    'sinnoh-route-207': 'mountain',
    'sinnoh-route-211': 'mountain',
    'sinnoh-route-210': 'route',
    'sinnoh-route-214': 'mountain',
    'sinnoh-route-227': 'volcanic',
    'sinnoh-route-228': 'desert',
    'sinnoh-route-212/south-towards-pastoria-city': 'marsh',
    'lost-tower': 'haunted',
    'old-chateau': 'haunted',
    'turnback-cave': 'cave',
    'trophy-garden': 'meadow',
    # Unova
    'celestial-tower': 'haunted',
    'strange-house': 'haunted',
    'cold-storage': 'urban',
    'dragonspiral-tower': 'ruins',
    'abundant-shrine': 'route',
    'guidance-chamber': 'cave',
    'trial-chamber': 'cave',
    'twist-mountain': 'cave',
    'reversal-mountain': 'cave',
    'glacier-room': 'cave',
    'iron-room': 'cave',
    'rocky-mountain-room': 'cave',
    'underground-ruins': 'cave',
    'unova-victory-road': 'cave',
    'unova-victory-road-2': 'cave',
    'relic-castle': 'ruins',
    'relic-passage': 'cave',
    'icirrus-city': 'marsh',
    'unova-route-4': 'desert',
    'unova-route-8': 'marsh',
    'driftveil-drawbridge': 'route',
    'marvelous-bridge': 'route',
    'village-bridge': 'route',
    # Kalos
    'kalos-route-4': 'meadow',
    'kalos-route-7': 'meadow',
    'kalos-route-9': 'desert',
    'kalos-route-13': 'desert',
    'kalos-route-14': 'marsh',
    'kalos-route-19': 'marsh',
    'kalos-route-20': 'forest',
    'lost-hotel': 'urban',
    'terminus-cave': 'cave',
    'pokemon-village': 'forest',
    # Alola
    'ten-carat-hill': 'cave',
    'memorial-hill': 'haunted',
    'thrifty-megamart': 'haunted',
    'exeggutor-island': 'route',
    'wela-volcano-park': 'volcanic',
    'poni-meadow': 'route',
    'paniola-ranch': 'route',
    # Galar
    'dusty-bowl': 'desert',
    'galar-route-6': 'desert',
    'galar-route-8/steamdrift-way': 'ice',
    'galar-route-9': 'beach',
    'giants-cap': 'mountain',
    'stony-wilderness': 'mountain',
    'path-to-the-peak': 'ice',
    'slippery-slope': 'ice',
    'motostoke': 'urban',
    'hulbury': 'urban',
    'motostoke-outskirts': 'route',
    'fields-of-honor': 'route',
    'watchtower-ruins': 'ruins',
}

# Type-share fallbacks: (habitat, applies-to base habitats, test on type shares).
# Applied in order, after keywords, unless an override decided the habitat.
TYPE_FALLBACKS = [
    ('ice', {'route', 'mountain', 'beach', 'cave', 'urban', 'meadow'},
     lambda t: t.get('ice', 0) >= 0.30),
    ('haunted', {'route', 'cave', 'urban', 'ruins'},
     lambda t: t.get('ghost', 0) >= 0.30),
    ('volcanic', {'route', 'mountain', 'cave'},
     lambda t: t.get('fire', 0) >= 0.25),
    ('mountain', {'route'},
     lambda t: t.get('rock', 0) + t.get('ground', 0) >= 0.45),
]

# Tower-style ruins full of ghosts are haunted (Pokemon Tower, Lost Tower...).
RUINS_TO_HAUNTED_GHOST_SHARE = 0.25


def tokens(identifier):
    return [t for t in re.split(r'[-_\s]+', identifier.lower()) if t]


def area_tokens(area):
    """Tokens of a sub-area name that describe the area itself.

    Many sub-areas are named after a neighbour ("south-towards-viridian-city",
    "violet-city-entrance", "hidden-grotto-mistralton-cave"); those neighbour
    names say nothing about the area's habitat, so they're dropped.
    """
    toks = tokens(area or '')
    if 'towards' in toks:
        return toks[:toks.index('towards')]
    if len(toks) > 1 and toks[-1] == 'entrance':
        return []
    if toks[:2] == ['hidden', 'grotto']:
        return []
    return toks


def keyword_habitat(toks, rules=LAND_KEYWORD_RULES):
    toks = set(toks)
    for habitat, words in rules:
        if toks & words:
            return habitat
    return None


def land_habitat(location, area, type_shares):
    """Habitat for a location's land-style tables.

    ``type_shares`` maps type name -> share of the location's land encounters.
    Returns ``(habitat, reason)``; reason says which rule fired, for auditing.
    """
    for key in (f'{location}/{area}' if area else None, location):
        if key and key in LAND_OVERRIDES:
            return LAND_OVERRIDES[key], f'override:{key}'

    # Sub-area names ("desert", "forest", "exterior-snowfall") beat the parent
    # location's name: the HGSS Safari Zone, Giant Chasm's forest, Mt. Coronet.
    habitat = keyword_habitat(area_tokens(area))
    reason = f'area-keyword:{area}'
    if habitat is None:
        habitat = keyword_habitat(tokens(location))
        reason = f'keyword:{location}'
    if habitat is None:
        habitat, reason = 'route', 'default'

    if habitat == 'ruins' and type_shares.get('ghost', 0) >= RUINS_TO_HAUNTED_GHOST_SHARE:
        return 'haunted', reason + '+ghost'
    for fallback, bases, test in TYPE_FALLBACKS:
        if habitat in bases and test(type_shares):
            return fallback, f'{reason}+types->{fallback}'
    return habitat, reason


# ---------------------------------------------------------------------------
# Water habitat rules
# ---------------------------------------------------------------------------

CAVE_WATER_TOKENS = {'cave', 'caves', 'cavern', 'tunnel', 'mine', 'well', 'mt', 'den',
                     'victory', 'chasm', 'seafoam', 'whirl', 'tohjo', 'meteor', 'origin',
                     'seafloor', 'shoal', 'icefall'}
SEA_TOKENS = {'sea', 'ocean', 'bay', 'beach', 'beachfront', 'coast', 'shore', 'cape',
              'lagoon', 'island', 'islands', 'isle', 'harbor', 'port', 'resort', 'ship',
              'anne', 'labyrinth'}
FRESH_TOKENS = {'lake', 'lakeside', 'lakefront', 'river', 'riverbank', 'pond', 'falls',
                'spring', 'marsh', 'swamp', 'wetland', 'wetlands', 'moor', 'garden',
                'park', 'hill', 'forest', 'woods'}

WATER_OVERRIDES = {
    'seafoam-islands': 'cave_water',
    'whirl-islands': 'cave_water',
    'meteor-falls': 'cave_water',
    'tohjo-falls': 'cave_water',
    'dragons-den': 'cave_water',
    'abandoned-ship': 'sea',
    'hoenn-route-124/underwater': 'underwater',
    'hoenn-route-126/underwater': 'underwater',
}

# Species (PokeAPI species identifiers) that only make sense in salt water, and
# ones typical of fresh water. Used when a water table's name says neither.
MARINE_SPECIES = {
    'tentacool', 'tentacruel', 'shellder', 'cloyster', 'krabby', 'kingler', 'horsea',
    'seadra', 'kingdra', 'staryu', 'starmie', 'lapras', 'seel', 'dewgong', 'wingull',
    'pelipper', 'mantine', 'mantyke', 'remoraid', 'octillery', 'corsola', 'chinchou',
    'lanturn', 'qwilfish', 'carvanha', 'sharpedo', 'wailmer', 'wailord', 'relicanth',
    'luvdisc', 'clamperl', 'huntail', 'gorebyss', 'spheal', 'finneon', 'lumineon',
    'frillish', 'jellicent', 'alomomola', 'shellos', 'gastrodon', 'skrelp', 'dragalge',
    'clauncher', 'clawitzer', 'binacle', 'barbaracle', 'mareanie', 'toxapex',
    'wishiwashi', 'pyukumuku', 'bruxish', 'dhelmise', 'arrokuda', 'barraskewda',
    'pincurchin', 'cramorant', 'tirtouga', 'carracosta', 'omanyte', 'kabuto',
}
FRESHWATER_SPECIES = {
    'goldeen', 'seaking', 'poliwag', 'poliwhirl', 'poliwrath', 'politoed', 'psyduck',
    'golduck', 'slowpoke', 'slowbro', 'marill', 'azumarill', 'wooper', 'quagsire',
    'lotad', 'lombre', 'ludicolo', 'barboach', 'whiscash', 'corphish', 'crawdaunt',
    'surskit', 'masquerain', 'feebas', 'milotic', 'buizel', 'floatzel', 'bidoof',
    'bibarel', 'basculin', 'ducklett', 'swanna', 'tympole', 'palpitoad', 'seismitoad',
    'dewpider', 'araquanid', 'chewtle', 'drednaw', 'dratini', 'dragonair', 'azurill',
    'stunfisk',
}


def water_habitat(location, area, species_shares, land_hab=None):
    """Habitat for a location's surf/fishing tables.

    ``species_shares`` maps species identifier -> share of the location's water
    encounters. ``land_hab`` is the location's land habitat, if known.
    """
    for key in (f'{location}/{area}' if area else None, location):
        if key and key in WATER_OVERRIDES:
            return WATER_OVERRIDES[key], f'override:{key}'
    if area == 'underwater':
        return 'underwater', 'area:underwater'
    toks = set(tokens(location)) | set(area_tokens(area))
    if toks & CAVE_WATER_TOKENS or land_hab == 'cave':
        return 'cave_water', 'keyword:cave'
    if toks & SEA_TOKENS:
        return 'sea', 'keyword:sea'
    if toks & FRESH_TOKENS:
        return 'freshwater', 'keyword:fresh'
    marine = sum(v for k, v in species_shares.items() if k in MARINE_SPECIES)
    fresh = sum(v for k, v in species_shares.items() if k in FRESHWATER_SPECIES)
    if marine > fresh:
        return 'sea', f'species:marine{marine:.2f}>fresh{fresh:.2f}'
    return 'freshwater', f'species:marine{marine:.2f}<=fresh{fresh:.2f}'
