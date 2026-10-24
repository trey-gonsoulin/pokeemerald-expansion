# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Emerald Plus is a personal fork of [rh-hideout/pokeemerald-expansion](https://github.com/rh-hideout/pokeemerald-expansion), a GBA ROM hack base built on pret's pokeemerald decompilation.

- `emerald-plus` (the default branch on `origin`) is the integration branch. Branch from it and merge into it.
- `master` mirrors upstream, and the `upstream` remote is rh-hideout. Don't commit to `master`.
- Commit messages are a plain imperative sentence with `(#N)` appended, e.g. `Remember debug menu cursor position (#9)`.

What the fork adds over upstream (`git diff origin/master...origin/emerald-plus --stat`):
- Personal-playthrough config flips in `include/config/` (reusable TMs, Gen 6 Exp. Share on `FLAG_UNUSED_0x264`, followers, HGSS Pokédex, IV/EV summary, forgettable HMs).
- Two exp-gain fixes in battle code, covered by `test/battle/exp.c`.
- Overworld debug menu improvements in `src/debug.c`: memory, paging, scroll arrows, path title, faster numeric input.
- `tools/area_archetypes/`, a standalone Python tool (see below).

## Build

devkitARM lives at `/opt/devkitpro/devkitARM` and is **not** on PATH. `TOOLCHAIN=` alone isn't enough, because trainerproc header generation needs the bin dir on PATH:

```sh
export PATH=/opt/devkitpro/devkitARM/bin:$PATH
make -j16 generated TOOLCHAIN=/opt/devkitpro/devkitARM   # fresh checkout/worktree: run first, or data/battle_partners.h / debug_trainers.h race
make -j16 TOOLCHAIN=/opt/devkitpro/devkitARM             # pokeemerald.gba: debug menus ON
make -j16 release TOOLCHAIN=/opt/devkitpro/devkitARM     # pokeemerald-release.gba: debug menus OFF
```

- The debug menus are `DISABLED_ON_RELEASE` (`include/config/debug.h`), so plain `make` gives the ROM with the debug menus. In the overworld, open the menu by holding R and pressing Start.
- `make debug` (the -Og/-g build) fails to link with gcc 16.1 (#27). Use plain `make` instead.
- `make firered` / `make leafgreen` build other games through `GAME_VERSION`.
- Warnings that are expected and not regressions: pokedex.c stringop-overflow, LTO type mismatches and the RWX segment linker warning.

## Tests

```sh
make check -j16 TOOLCHAIN=/opt/devkitpro/devkitARM                    # all tests, headless via mgba-rom-test-hydra
make check -j16 TESTS="Lucky Egg" TOOLCHAIN=/opt/devkitpro/devkitARM        # tests whose name starts with the prefix
make pokeemerald-test.elf TESTS="Lucky Egg" TOOLCHAIN=/opt/devkitpro/devkitARM  # open in mGBA to watch them
```

- Tests live in `test/` (mostly battle mechanics). They use `ASSUMPTIONS` / `GIVEN` / `WHEN` / `SCENE` blocks; see `docs/tutorials/how_to_testing_system.md`.
- Name related tests with a shared prefix so `TESTS=` can select them.
- **Nothing covers `src/debug.c` or other overworld UI.** Verify those changes by building both ROMs (no new warnings in the changed file) and with a written in-game test plan.

Area archetypes tool (standard library only, run from the repo root):

```sh
python3 tools/area_archetypes/area_archetypes.py fetch     # once: PokeAPI CSVs -> .cache/
python3 tools/area_archetypes/area_archetypes.py build     # classify areas, write output/
python3 tools/area_archetypes/area_archetypes.py restock   # preview a restocked src/data/wild_encounters.json
python3 -m unittest discover -s tools/area_archetypes      # tests
```

`tools/area_archetypes/README.md` documents the archetype rules and the restock options.

## Architecture

- **C source and headers.** Game code is in `src/*.c` and headers in `include/`.
  - Feature toggles are all in `include/config/*.h`, as `#define`s compared with `GEN_X` constants or `TRUE`/`FALSE`.
  - Code reads them directly (`if (B_FOO >= GEN_6)`) rather than through `#ifdef`, so both branches keep compiling.
- **Data tables** are mostly C headers under `src/data/`, included into a single translation unit:
  - species: `src/data/pokemon/species_info/gen_N_families.h`;
  - items, moves, learnsets: elsewhere under `src/data/`.
  - Many species entries are built from macros, so line-based parsers have to expand them.
- **Generated data.** The build turns these into `.h`/`.inc` files with tools from `tools/`:
  - JSON through `jsonproc` (`json_data_rules.mk`): `src/data/wild_encounters.json`, region map, heal locations;
  - `*.party` trainer files (`src/data/trainers.party`, …) through `trainerproc` (`trainer_rules.mk`);
  - maps through `mapjson` (`map_data_rules.mk`): `data/maps/<Map>/map.json`, `data/maps/map_groups.json`, `data/layouts/layouts.json`.

  Edit the sources, never the generated outputs.
- **Event scripts** are assembly macros in `data/maps/<Map>/scripts.inc` and `data/scripts/`.
- **Tasks and callbacks.** Overworld UI such as the debug menu runs as tasks (`src/task.c`).
  - `CreateTask` takes the first free slot, and `RunTasks` follows `.next` after each func returns. So a task created in the same frame can run in that frame when it reuses an earlier slot.
  - Per-task state lives in `gTasks[id].data[0..15]` (s16), usually aliased with `#define tFoo data[N]`.

### `src/debug.c` gotchas
- Numeric inputs store the value in s16 task data (`tInput`), but a max can be 0xFFFF. Every read, compare and clamp has to go through u16/u32.
- Steps that skip invalid values (species) are bounded with a `maxFunc`, such as the last enabled species.
  - `IsSpeciesEnabled(SPECIES_EGG)` is TRUE, and `SPECIES_EGG == NUM_SPECIES`, so an upward search can land one past the max.
- Almost all of the task data slots are in use. Extra menu state goes in the heap-allocated `sDebugMenuListData`, which is freed on every exit path.

## Conventions (from `docs/STYLEGUIDE.md`)
- Naming:
  - functions and structs: PascalCase;
  - variables and fields: camelCase;
  - globals: `g` prefix; statics: `s` prefix;
  - macros and constants: CAPS_WITH_UNDERSCORES.
- Formatting: 4-space indent, braces on their own line.
- Be minimally invasive to upstream files. Put large new features in their own file, which keeps upstream merges clean.
- Anything that changes the save layout must sit behind a config that is off by default. Don't break existing saves.
- External data files should be JSON.
