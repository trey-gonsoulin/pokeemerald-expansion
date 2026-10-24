# Area archetypes

Classifies every wild-encounter area in the main-series games (Gens 1-8, via
[PokeAPI](https://github.com/PokeAPI/pokeapi)'s data dump) into an
**archetype**, then pools the species from every game that share an archetype.
Kanto Route 1, Johto Route 29 and Hoenn Route 101 all become `route/beginner`;
Viridian Forest, Ilex Forest, Petalburg Woods and Santalune Forest become
`forest/beginner`. The `route/beginner` pool then holds Rattata, Pidgey,
Zigzagoon, Bidoof, Patrat, Lillipup, Skwovet... with how common each one is.

```sh
python3 tools/area_archetypes/area_archetypes.py fetch   # once: PokeAPI CSVs -> .cache/
python3 tools/area_archetypes/area_archetypes.py build   # classify + write output/
python3 -m unittest discover -s tools/area_archetypes    # tests
```

Standard library only.

## Archetypes

An archetype is `<habitat>/<stage>`, assigned per encounter table, meaning one
game's grass, surf, rod, rock smash or headbutt list for one area.

**Habitat** is the kind of place:

| land tables (grass, rock smash, trees) | water tables (surf, fishing) |
|---|---|
| `route` `forest` `meadow` `cave` `mountain` `desert` `volcanic` `ice` `marsh` `beach` `haunted` `urban` `ruins` `safari` | `sea` `freshwater` `cave_water` `underwater` |

The rules live in `archetypes.py` and run in this order:
1. Manual `LAND_OVERRIDES` / `WATER_OVERRIDES`.
2. Keywords in the sub-area name ("desert", "exterior-snowfall"), then the
   location name ("woods", "cave", "cemetery").
3. Type-mix fallbacks: a "route" that's 30%+ Ice is `ice`; a "cave" that's 30%+
   Ghost is `haunted`.
4. For water whose name says nothing, salt-water vs. fresh-water species
   (Tentacool/Wingull vs. Goldeen/Poliwag).

**Stage** comes from the table's encounter-weighted level:

| stage | levels |
|---|---|
| `beginner` | up to 7 |
| `early` | 8-17 |
| `mid` | 18-30 |
| `late` | 31-44 |
| `endgame` | 45+ |

Stage is set per table, not per place. Unova Route 1's grass is
`route/beginner` while its post-game surfing is `freshwater/endgame`, and
Pinwheel Forest is `forest/early` in BW but `forest/endgame` in BW2.

## Output (`output/`)

- **`archetype_pools.json`**: for each archetype, its source locations and one
  pool per method group (`land`, `rock_smash`, `tree`, `surf`, `fish_old`,
  `fish_good`, `fish_super`). Each pool entry looks like:
  ```json
  {"species": "SPECIES_CATERPIE", "share": 0.17, "games": 4,
   "introduced_gen": 1, "types": ["bug"], "levels": [3, 5]}
  ```
  - `share` is the species' average fraction of encounters. Every game counts
    equally, every location within a game counts equally, and every floor
    within a location counts equally, so a nine-room cave or SwSh's huge
    table count doesn't drown out Red/Blue.
  - `games` is how many version groups have the species in that archetype.
  - Species names are this repo's `SPECIES_*` constants, regional forms
    included (`SPECIES_DIGLETT_ALOLA`).
- **`archetype_pools.md`**: the top 15 of every pool, for skimming.
- **`emerald_maps.json`**: an archetype for every table of every map in
  `src/data/wild_encounters.json`, keyed by base label. Each fishing rod gets
  its own entry. Example:
  ```json
  "gPetalburgWoods": {"map": "MAP_PETALBURG_WOODS", "location": "petalburg-woods",
    "land_mons": {"archetype": "forest/beginner", "pool": "land", "level": 5.2}}
  ```
  To restock a map, look up its archetype and draw from
  `archetype_pools.json` → `archetypes[archetype].pools[pool]`.
- **`area_classification.csv`**: every source table with its archetype, level,
  the rule that fired, and its top species. Use it to audit and tune the rules.

## Limitations

Tracked as issues on the
[fork](https://github.com/trey-gonsoulin/pokeemerald-expansion/issues?q=label%3Aarea-archetypes):

- PokeAPI has no wild encounter data for Scarlet/Violet
  ([#1](https://github.com/trey-gonsoulin/pokeemerald-expansion/issues/1)),
  Legends: Arceus or BDSP
  ([#2](https://github.com/trey-gonsoulin/pokeemerald-expansion/issues/2)).
  Gen 9 species only appear if a covered game has them in the wild.
- ORAS and Sun/Moon data is partial; many ORAS tables are one-species stubs
  ([#3](https://github.com/trey-gonsoulin/pokeemerald-expansion/issues/3)).
- Stage bands are absolute levels, so a game with a steep level curve (BW2,
  SwSh DLC) puts more tables in `late`/`endgame`
  ([#4](https://github.com/trey-gonsoulin/pokeemerald-expansion/issues/4)).
- 17 archetypes draw on 3 or fewer locations. If a pool is thin, merge it with
  the neighbouring stage
  ([#5](https://github.com/trey-gonsoulin/pokeemerald-expansion/issues/5)).
- Encounter conditions (time of day, season, weather, swarms) are summed, so
  e.g. SwSh Giant's Cap mixes snow-weather Vanillite into `mountain`
  ([#6](https://github.com/trey-gonsoulin/pokeemerald-expansion/issues/6)).
- Gifts, statics, raids, roamers, trades and SOS allies are excluded. Hordes,
  shaking grass/rippling water "spots", ambushes and flower patches are kept
  but weighted at ¼ inside their table
  ([#7](https://github.com/trey-gonsoulin/pokeemerald-expansion/issues/7)).
- Nothing writes the pools back into `wild_encounters.json` yet
  ([#8](https://github.com/trey-gonsoulin/pokeemerald-expansion/issues/8)).
