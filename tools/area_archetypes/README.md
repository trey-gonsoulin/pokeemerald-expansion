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
python3 tools/area_archetypes/area_archetypes.py baseline # refresh the vanilla snapshot (see below)
python3 -m unittest discover -s tools/area_archetypes    # tests
```

Standard library only. The tests run the whole build on the tiny hand-written
PokeAPI CSV set in `testdata/`, so they need no network; the end-to-end tests
on the full data run only once `fetch` has filled `.cache/`.

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
  - `introduced_gen` is the generation the species debuted in. For a
    regional form it's the form's generation, not its base species':
    Alola 7, Galar and Hisui 8, Paldea 9 (`SPECIES_DIGLETT_ALOLA` is 7).
- **`archetype_pools.md`**: the top 15 of every pool, for skimming.
- **`emerald_maps.json`**: an archetype for every table of every map in
  the vanilla baseline (`wild_encounters.vanilla.json`, see
  [The vanilla baseline](#the-vanilla-baseline)), keyed by base label. Each
  fishing rod gets its own entry. Example:
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
4. Devolves each new species to the stage that fits its slot's min level, so
   it is attainable at every level the slot can roll (Wooper, not Quagsire,
   in a 5-35 slot), using the `.evolutions` in `src/data/pokemon/species_info/`. Level
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
# Happy with the report? Overwrite src/data/wild_encounters.json, then build the ROM.
python3 tools/area_archetypes/area_archetypes.py restock --write
# Tune the options and rerun; each run starts again from the vanilla baseline.
python3 tools/area_archetypes/area_archetypes.py restock --ratio 0.4 --write
```

`restock_report.md` lists every changed table slot by slot (`=` = unchanged).

The committed `src/data/wild_encounters.json` is the default restock (#28):
`python3 tools/area_archetypes/area_archetypes.py restock --write`, with no
flags or `--config` (ratio 0.5, seed 1, Hoenn only). Rerun that command to
regenerate it, for example after refreshing the baseline. A unittest fails
when the committed file is no longer what that command gives (#96), so a
change to `restock.py`, the pools or the baseline also commits the
regenerated table.

### The vanilla baseline

`restock` never takes natives from `src/data/wild_encounters.json`. They (and the
report's "before" column) come from `--base`, by default
`output/wild_encounters.vanilla.json`, a committed copy of the unrestocked
file. `build` classifies the same file into `emerald_maps.json`. So rerunning
`restock --write` with new options replaces the last restock instead of
restocking it again, and `build` gives the same maps after a restock as
before. The same base, options and seed always give the same output.

Every file `restock` writes (the preview and `--write`) carries a top-level
`restocked_by` stamp with the base's SHA-256, the seed and the ratio. The game
build ignores it. `restock --base`, `build --base` and `baseline` refuse a
stamped file unless `--force`, so a restocked file can't become the baseline
by mistake. A tool that rewrites the file, such as Porymap, may drop the stamp,
and then nothing can tell it from vanilla: once a restock is committed,
refresh the baseline from upstream's copy (below). `restock --write` also refuses, unless `--force`, when the file it would
overwrite differs from the base in anything but species (an upstream merge
since the last `baseline`, or a hand edit), since the write would lose it.
A run with a ratio above 0 that changes no table (the allow/deny lists, gens or
the other filters leave nothing to draw) warns, and with `--write` it refuses
unless `--force`, since the write would put the vanilla tables back. A ratio of
0 changes nothing on purpose and writes without a warning.

Refresh the snapshot when upstream changes `src/data/wild_encounters.json`,
then rerun `build` and `restock --write`:

```sh
# src/data/wild_encounters.json is restocked (committed since #28): take upstream's copy.
git show upstream/master:src/data/wild_encounters.json > /tmp/wild_encounters.json
python3 tools/area_archetypes/area_archetypes.py baseline --wild /tmp/wild_encounters.json
```

| option | default | meaning |
|---|---|---|
| `--ratio R` | `0.5` | share of each table given to new species; `0` = unchanged, `1` = replace all |
| `--seed N` | `1` | RNG seed; each table also seeds from its label, so tables don't shift when others change |
| `--regions` | `hoenn` | `hoenn,kanto` to restock the FRLG tables too |
| `--gens 4-9` | all | generations new species may come from; a regional form counts as the generation its form debuted in (Alola 7, Galar and Hisui 8, Paldea 9), so `--gens 1-3` leaves out Alolan Rattata |
| `--gen-weight 4=2` | none | multiply a generation's draw weight ("favour Gen 4+"); repeatable |
| `--allow SPECIES,...` | none | draw new species only from these |
| `--deny SPECIES,...` | none | never place these, and drop them where they're native |
| `--allow-legendaries` | off | let legendaries etc. into the draw |
| `--no-regional-forms` | off | never draw Alolan, Galarian, Hisuian or Paldean forms |
| `--drop-rare-natives` | off | let a table's own rare species lose their only slot |
| `--new-species N` | scales | new species per table; default `round(own * R / (1 - R))`, or the own count at `R = 1` |
| `--config FILE` | none | JSON with any of the options above (snake_case, `--ratio` through `--new-species`) plus per-map overrides; flags win |
| `--base FILE` | `output/wild_encounters.vanilla.json` | vanilla file the natives come from |
| `--wild FILE` | `src/data/wild_encounters.json` | file `--write` overwrites; not a source of natives |
| `--write` | off | also overwrite `--wild` |
| `--force` | off | accept a `--base` that `restock` wrote, `--write` over a `--wild` that differs from it in more than species, and `--write` a run that changed nothing |

Per-map overrides go under `maps`, keyed by base label:

```json
{"ratio": 0.4, "gens": "4-9", "deny": ["SPECIES_ZUBAT"],
 "maps": {"gRoute101": {"ratio": 0.25},
          "gRoute130": {"skip": true},
          "gGraniteCave_1F": {"allow": ["SPECIES_ROGGENROLA", "SPECIES_WOOBAT"], "deny": ["SPECIES_ABRA"]}}}
```

A map takes `ratio`, `allow`, `deny`, `new_species` and `skip`; `gens` and
`gen_weight` are global only. A map's `allow` replaces the global list, its
`deny` adds to it. Denied natives are dropped even at ratio 0 or when nothing
can be drawn (the table's other species take their slots); only `skip` leaves
a map exactly as it is. A table whose natives are all denied, with nothing
left to draw, has nothing to fill its slots with: it is left as it is, with
a warning.

`restock` checks the config before it writes anything, and stops with an error
on an unknown key (top-level or per-map), a label that isn't a
`gWildMonHeaders` base label in `--base`, a region that isn't in
`emerald_maps.json`, an unknown species, a `gens` set with no pool species,
or a value of the wrong type: `ratio`
is a number from 0 to 1, `seed` and `new_species` whole numbers, `gens` a
non-empty string like `"4-9"` or list of numbers (leave it out for every
generation), `gen_weight` an object like
`{"4": 2}`, `regions`, `allow` and `deny` a comma-separated string or a list
of strings, and the switches `true` or `false`.

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
