# forced_trainers

Which story trainers a player can skip. `classify.py` writes `tools/rebalance/forced_trainers.json`, which the balance rework's level curve reads: `regular[id].class` (`FORCED`, `AVOIDABLE` or `UNCERTAIN`), `regular[id].one_of` (a choose-one group) and `bosses[id].required`. Standard library only, run from the repo root:

```sh
python3 tools/forced_trainers/classify.py           # classify and write the JSON, print a per-stage summary
python3 tools/forced_trainers/classify.py --check   # exit 1 if the committed JSON is stale
python3 tools/forced_trainers/classify.py --verbose # also list every avoidable trainer
python3 tools/forced_trainers/render.py Route110 3  # draw a map (folder, stage 0-9, optional x0,y0,x1,y1)
python3 -m unittest discover -s tools/forced_trainers
```

Rerun it after a change to a story map, a trainer's script or object, `story_stages.json`, or `specs.py`. `RealRepo.test_committed_file_is_current` and CI fail when the JSON is stale.

## Method

- `engine.py` reads each map's layout (`map.bin`, tileset metatile behaviours), its objects and its warps. `sight_tiles` gives the tiles a trainer sees (its sight range along its facings, stopped by walls, objects and elevation changes), `path_exists` is a breadth-first walk (ledges one-way, water, bikes-only slopes and HM obstacles by the stage's HMs), and `world_search` is the same across the maps of one area, following warps.
- `specs.py` holds, per area, the maps searched together, the stage (which sets the HMs: Cut from Brawly, bike from Wattson, Rock Smash from Flannery, Strength from Norman, Surf from Winona, Waterfall at the Elite Four) and the story legs to walk (`pairs`), plus the scripted trainers (`script_tiles`, `MANUAL`), the optional maps and the boss notes.
- `classify.py` removes each trainer's sight from the grid in turn. If a story leg then has no path, the trainer is `FORCED`. Otherwise it removes every trainer but a small combination: when a combination is unavoidable and none is forced alone, those trainers are `UNCERTAIN` with `one_of` naming the group (Petalburg Gym, Weather Institute 1F, Victory Road B1F). A static trainer that turns (`MOVEMENT_TYPE_ROTATE_*`) is `AVOIDABLE` with `timing: true` when the player only slips past by timing its turns. A patrolling trainer whose patrol covers every path is `UNCERTAIN`.
- Bosses are `required: true` unless `specs.BOSS_NOTES` says the fight is optional. The Rustboro and Lilycove rival fights are optional (a YES/NO prompt), and all six variants of each (May or Brendan with each starter) get `required: false`.

## Counts

46 forced, 389 avoidable (including 29 only by timing) and 34 uncertain, of 469 regular trainers. The design spec's first-run count was 388 avoidable and 35 uncertain; the tool as ported puts one more in avoidable and one fewer in uncertain than that early run, and the committed file is the tool's output.

## Limits

- Sight is the static line of sight: it doesn't model a trainer walking toward the player, only the patrol range as a set of start tiles.
- Scripted triggers (coordinate events, forced scenes) are not read from the scripts. They are in `specs.py` by hand (`script_tiles`, `MANUAL`), so a new one has to be added there.
- A route is a pair of tiles per area. A story detour the specs don't list isn't searched.
- Strength boulders are assumed pushed out of the way in Seafloor Cavern and Victory Road, and darkness is ignored.

## In-game checks

The grid can't settle these; check them in the debug ROM before relying on the class:

- Mauville Gym and Lavaridge Gym: the beams, switches and warp pads change the route as you move.
- The patrollers: Jasmine, Sophie, Coby, Cale, Aqua grunts 1 and 4, Magma grunts 4 and 5.
- Fortree City's gates.
- Mossdeep Gym's spin tiles.
