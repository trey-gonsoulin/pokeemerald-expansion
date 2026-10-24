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
python3 tools/area_archetypes/area_archetypes.py restock # preview restocked wild_encounters.json
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

## Restocking `wild_encounters.json`

`restock` (in `restock.py`) puts the pools into the game. It reads
`output/archetype_pools.json` and `output/emerald_maps.json`, so it doesn't
need the PokeAPI cache. For each table of each selected map it:

1. Keeps the table's own species, scaled down to `1 - ratio` of the table.
2. Draws new species from the table's archetype pool, weighted by `share`
   and a seeded RNG, at most one per evolution line and none from a line the
   table already has. They share `ratio` of the table by pool share.
3. Hands out the slots from the highest rate down to whichever species is
   furthest below its share, so the most common species take the 20% (or 60%)
   slots. Below ratio 1, each of the table's own species keeps at least one
   slot; if they already fill every slot, the table is left alone.
4. Devolves each new species to the stage that fits its slot's max level,
   using the `.evolutions` in `src/data/pokemon/species_info/`. Level
   evolutions use their level; stone, trade and friendship evolutions count
   as `max(pre-evolution + 10, 30)`, except out of babies (Pichu -> Pikachu).
   The stage a species is devolved to must pass the same filters (deny,
   allow, gens...), or the species isn't drawn for that table: denying Zubat
   also keeps Golbat out of tables with low-level slots.

Slot counts, encounter rates and every slot's levels stay as they are. Only
species enabled by `include/config/species_enabled.h` (`P_GEN_*`,
`P_FAMILY_*`, regional forms...) are placed. Legendary, mythical, Ultra Beast
and Paradox species and battle-only forms are left out. Battle Pyramid/Pike
tables are never touched.

```sh
# Preview: writes tools/area_archetypes/restock/{wild_encounters.json,restock_report.md}
python3 tools/area_archetypes/area_archetypes.py restock
# Happy with the report? Overwrite src/data/wild_encounters.json, then build.
python3 tools/area_archetypes/area_archetypes.py restock --write
```

`restock_report.md` lists every changed table slot by slot (`=` = unchanged).
The same options and seed always give the same output.

| option | default | meaning |
|---|---|---|
| `--ratio R` | `0.5` | share of each table given to new species; `0` = unchanged, `1` = replace all |
| `--seed N` | `1` | RNG seed; each table also seeds from its label, so tables don't shift when others change |
| `--regions` | `hoenn` | `hoenn,kanto` to restock the FRLG tables too |
| `--gens 4-9` | all | generations new species may come from |
| `--gen-weight 4=2` | none | multiply a generation's draw weight ("favour Gen 4+"); repeatable |
| `--allow SPECIES,...` | none | draw new species only from these |
| `--deny SPECIES,...` | none | never place these, and drop them where they're native |
| `--allow-legendaries` | off | let legendaries etc. into the draw |
| `--no-regional-forms` | off | never draw Alolan, Galarian, Hisuian or Paldean forms |
| `--drop-rare-natives` | off | let a table's own rare species lose their only slot |
| `--new-species N` | scales | new species per table; default `round(own * R / (1 - R))`, or the own count at `R = 1` |
| `--config FILE` | none | JSON with any of the above (snake_case) plus per-map overrides; flags win |
| `--write` | off | also overwrite `src/data/wild_encounters.json` |

Per-map overrides go under `maps`, keyed by base label:

```json
{"ratio": 0.4, "gens": "4-9", "deny": ["SPECIES_ZUBAT"],
 "maps": {"gRoute101": {"ratio": 0.25},
          "gRoute130": {"skip": true},
          "gGraniteCave_1F": {"allow": ["SPECIES_ROGGENROLA", "SPECIES_WOOBAT"], "deny": ["SPECIES_ABRA"]}}}
```

A map's `allow` replaces the global list, its `deny` adds to it.

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
- `restock` reads `species_enabled.h` and the other config headers with a
  small `#if` evaluator, not the real preprocessor, and its non-level
  evolution levels are a heuristic. Check the report before `--write`.
