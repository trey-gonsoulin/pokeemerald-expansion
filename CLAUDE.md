# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Emerald Plus is a personal fork of [rh-hideout/pokeemerald-expansion](https://github.com/rh-hideout/pokeemerald-expansion), a GBA ROM hack base built on pret's pokeemerald decompilation.

- `emerald-plus` (the default branch on `origin`) is the integration branch. Branch from it and merge into it.
- `master` mirrors upstream, and the `upstream` remote is rh-hideout. Don't commit to `master`.
- Commit messages are a plain imperative sentence with `(#N)` appended, e.g. `Remember debug menu cursor position (#9)`.

## Fork docs

The details of what the fork adds over upstream (`git diff origin/master...origin/emerald-plus --stat`) are in `docs/fork/`, which isn't loaded automatically. Before changing an area, grep these for its function, file or config: code that looks wrong or odd may be a deliberate fork change, with an owner's decision behind it.

- `docs/fork/carried-fixes.md`: every upstream bug the fork fixes, with its code, test and any gaps in coverage.
- `docs/fork/features.md`: config flips, prize swaps and fork features.
- `docs/fork/debug-menu.md`: the overworld debug menu.
- `docs/fork/balance.md`: the exp formula, story bosses, the level curve and wild tables.

When you change the fork, write the detail in the matching doc: a new carried fix is a new top-level bullet in `carried-fixes.md`, and a new feature gets a section in `features.md` and a line in the index below. Keep `CLAUDE.md` to what every session needs.

### Fork feature index

Details in `docs/fork/features.md` unless noted.

- Config flips (`include/config/`): reusable TMs, Gen 6 Exp. Share on `FLAG_UNUSED_0x264`, followers, HGSS Pokédex, IV/EV summary, forgettable HMs, and the QoL set (#202).
- DexNav (#203, #210, `include/config/dexnav.h`, `src/dexnav.c`), including the search in a cave lit by Flash; R+Start always opens the debug menu in the debug ROM.
- Trade evolutions solo (#208): `I_USE_EVO_HELD_ITEMS_FROM_BAG`, Linking Cord at the Lilycove store.
- Prize swaps (#102, #103, #253, #263): Lucky Egg for the Exp. Share, PP Up for an owned TM (`IsPrizeAlreadyOwned`, `src/item.c`).
- HGSS Pokédex info page cry (#180, `src/pokedex_plus_hgss.c`).
- Boxes from the party menu (#185, `OW_PC_ANYWHERE`).
- Field moves with only the badge (#186, `OW_FIELD_MOVES_WITHOUT_MON`, `src/field_move.c`).
- Bag holds everything, no PC Item Storage (#187, `I_BAG_HOLDS_EVERYTHING`, `src/bag_holds_everything.c`).
- Use in the party menu's Item submenu and TM pocket marks (#193, #194, `I_USE_ITEM_FROM_PARTY_MENU`).
- Mart Buy list: IN BAG, ABLE x/y, OWNED (#195, #205, `src/shop.c`).
- Party menu evolution marker (#204, #211, #216, `P_PARTY_EVOLUTION_MARKER`, `src/evolution_ready.c`).
- Skills page while forgetting a move (#199, `src/pokemon_summary_screen.c`).
- Six key items on Select (#206, `I_REGISTERED_ITEMS_COUNT`, `src/registered_items.c`).
- Summary first when switching in battle (#200, #213, `B_SWITCH_SUMMARY_FIRST`, `src/battle_switch_summary.c`).
- Rematch ball over trainers (#207, `src/rematch_indicator.c`).
- Debug menu (`src/debug_menu_ui.c`; `docs/fork/debug-menu.md`).
- Exp formula (#154, #189, `src/exp_formula.c`), boss levels, AI, moves and evolutions and the owner's level curve (`tools/rebalance`, `tools/area_archetypes`; `docs/fork/balance.md`).

### Rules that apply across changes

- **Turned down by the owner, so don't re-propose:** `OW_SHOW_ITEM_DESCRIPTIONS`, `B_SHOW_TYPES`, `B_HP_PERCENTAGE_DISPLAY`, `B_FAST_INTRO_NO_SLIDE`, `TEXT_SPEED_INSTANT`, `AUTO_SCROLL_TEXT`, `P_ENABLE_MOVE_RELEARNERS`.
- **Balance:** the owner balances with the Exp. Share on and the 1.5x trainer exp off, mainly by raising opponent levels, never with a level cap.
  - After a `trainers.party`, wild-table or exp-formula change, rerun `python3 tools/rebalance/rebalance.py apply`, then `python3 tools/rebalance/rebalance.py`, and commit the data with the regenerated outputs. CI checks for drift, and `RealRepo.test_data_meets_the_curve_settings` fails when the data no longer meets the settings.
  - Hand-written movesets don't move with level changes: after a raise, hand-write what `rebalance.py` flags.
  - A rival level change has to go on all six teams of that fight (May or Brendan with each starter).
- **Save room:** SaveBlock3 is at 1576 of 1624 bytes (`test/save.c` pins it), so `OW_ITEM_DESCRIPTIONS_FIRST_TIME`'s 110 bytes don't fit and a large upstream species addition would trip the `src/save.c` assert.
- **Exp tests:** a test that measures exp across a level gap needs the over-level penalty off with `WITH_CONFIG`, as `WITH_EXP_AWARD_CONFIGS` does.
- **Script tests:** `RUN_OVERWORLD_SCRIPT` can't run msgbox scripts, so a map script with text can't be tested.
- **Upstream sync:** check each carried fix and drop it once upstream has it; refresh the wild baseline if upstream changed it (`tools/area_archetypes/README.md`); update `.claude/build.sh`'s allowlist for moved warning lines; rerun the Set Flag heap probe if upstream adds many flags or trainers (`docs/fork/debug-menu.md`).

## Build

devkitARM lives at `/opt/devkitpro/devkitARM` and is **not** on PATH. `TOOLCHAIN=` alone isn't enough, because trainerproc header generation needs the bin dir on PATH.

The owner's shell exports `CPATH` (macOS SDK headers) and `LDFLAGS` (Homebrew). `arm-none-eabi-gcc` honours `CPATH`, so unset the host compiler variables first. Otherwise the GBA code compiles against Darwin's libc headers with `_FORTIFY_SOURCE`: `make debug` and `make check` then fail to link, and the ROM bytes depend on the shell. (The Makefile overrides `LDFLAGS`/`CPPFLAGS` but appends to `CFLAGS`, and the host tool builds may read any of them, so unset the whole set.)

```sh
export PATH=/opt/devkitpro/devkitARM/bin:$PATH
unset CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH OBJC_INCLUDE_PATH LIBRARY_PATH LDFLAGS CFLAGS CPPFLAGS
make -j16 TOOLCHAIN=/opt/devkitpro/devkitARM                       # pokeemerald.gba: debug menus ON
make -j16 release TOOLCHAIN=/opt/devkitpro/devkitARM               # pokeemerald-release.gba: debug menus OFF
make -j16 build/emerald/src/debug.o TOOLCHAIN=/opt/devkitpro/devkitARM  # compile one file (~20 s cold)
```

- These all work on a fresh checkout or worktree, because they build the tools and generated sources first.
  - `make generated` and `make tools` don't: `generated` skips the tool prebuild, so a cold run fails with `No rule to make target tools/mapjson/mapjson`.
  - To get the generated headers alone, run `make -j16 -f make_tools.mk` first.
- `.claude/build.sh <worktree> [rom|release|debug|check [TESTS]|generated|src/x.c]` wraps all of this. It sets PATH, unsets the host compiler variables, logs to `build/`, and prints only the exit code, errors and unexpected warnings, and how many expected warning lines it filtered. For `check` it also prints the failing tests and the counts per result.

- The debug menus are `DISABLED_ON_RELEASE` (`include/config/debug.h`), so plain `make` gives the ROM with the debug menus. In the overworld, open the menu by holding R and pressing Start.
- `make debug` (the -Og/-g build) links once the env is clean. Its old link failure (#27: undefined `__getreent`, `_getpid_r`, `_kill_r`, `_write_r`) came from the `CPATH` leak, not gcc 16.1.
- `make firered` / `make leafgreen` build other games through `GAME_VERSION`.
- Warnings that are expected and not regressions (build.sh allowlists each one as a whole-line match, mostly exact text, so a new warning in the same file still shows; it matches `error:` and `warning:` in any case):
  - `release` only, from the LTO link: pokedex.c:4507 stringop-overflow (x6), mystery_gift_client.c:102 stringop-overread, and the `-Wlto-type-mismatch` on intro_frlg.c:249 (`gMultiBootProgram_PokemonColosseum_Start`) and faraway_island.h:4 (`GetMewMoveDirection`). The LTO assembler also prints 6 `<temp>.s: Warning: section .rodata.compound_string.<hash> size (0x..) is not a multiple of its entry size 0x..` lines; the temp file names and hashes change every build, so build.sh matches those by pattern and reports the count when a successful build has some but not exactly 6.
  - Every ROM build: the RWX segment linker warning. Plain `make`, `debug` and `check` emit only this one (plus the tool and asset ones below on a cold tree).
  - Tool and asset builds: json.hpp `-Wdeprecated-literal-operator` and `libpng warning: bKGD: invalid index` (under -j one can share a line with another or with a make recipe, which build.sh also filters).

## Tests

Run these in the same shell setup as the build (devkitARM on PATH, host compiler variables unset), or use `.claude/build.sh <worktree> check ["Lucky Egg"]`.

```sh
make check -j16 TOOLCHAIN=/opt/devkitpro/devkitARM                    # all tests, headless via mgba-rom-test-hydra
make check -j16 TESTS="Lucky Egg" TOOLCHAIN=/opt/devkitpro/devkitARM        # tests whose name starts with the prefix
make pokeemerald-test.elf TESTS="Lucky Egg" TOOLCHAIN=/opt/devkitpro/devkitARM  # open in mGBA to watch them
```

- Tests live in `test/` (mostly battle mechanics). They use `ASSUMPTIONS` / `GIVEN` / `WHEN` / `SCENE` blocks; see `docs/tutorials/how_to_testing_system.md`.
- Name related tests with a shared prefix so `TESTS=` can select them.
- CI: `.github/workflows/emerald-plus.yml` runs the full `make check`, both ROMs and the area_archetypes unittests on pushes to `emerald-plus` and `issue-*` and on PRs into `emerald-plus`. KNOWN_FAILING, TO_DO and ASSUMPTIONS_FAILED results don't fail it (upstream fails on skipped assumptions only in rh-hideout's own CI), but a KNOWN_FAILING test that passes does. The job times out after 60 min, a backstop now that hydra stops a runner that makes no progress for 300 s (#73, #124): the ROM's 60 s TIMEOUT (a Timer2 interrupt) can't catch every hang. Upstream's `build.yml` doesn't run on fork pushes, but it does run on every PR.
- What a green `make check` doesn't prove (#73):
  - Headless tests skip every battle animation except Transform and Ally Switch, and record battle messages without drawing them.
  - The memory checks are heap corruption, leaked heap blocks and leaked tasks, plus a guard element (#125, a fork change): test builds give `gBattleMons`, `gBattlerPartyIndexes` and `gObjectEvents` one extra element (`+ TESTING` in their declarations), which `CB2_TestRunner` fills with 0xFF before each test and fails a test that passed (and was expected to) if any byte changed (`sGuardElements`, `test/test_runner.c`). It catches writes only, and only into the element just past the end: an out-of-bounds read (#57's `gBattlerPartyIndexes[4]`), a write further out, or one into any other static array (the per-battler `gBattleStruct` arrays included) still passes.
  - The ROM restart after "Tests resume after CRASH" resets that runner's exit code, so a failure that ran before it there doesn't fail the run by itself. Only tests defined below it in `test/test_test_runner.c` can hit this (that file runs first, and a file's tests run bottom up), and the fork's hydra now exits 1 on its counts instead (`docs/fork/carried-fixes.md`).
- **Nothing covers `src/debug.c` or other overworld UI.** Verify those changes by building both ROMs (no new warnings in the changed file) and with a written in-game test plan.

Area archetypes tool (standard library only, run from the repo root):

```sh
python3 tools/area_archetypes/area_archetypes.py fetch     # once: PokeAPI CSVs at POKEAPI_REF (--ref) -> .cache/
python3 tools/area_archetypes/area_archetypes.py build     # classify areas, write output/
python3 tools/area_archetypes/area_archetypes.py restock   # preview a restocked src/data/wild_encounters.json
python3 tools/area_archetypes/area_archetypes.py baseline --wild <upstream copy>  # refresh output/wild_encounters.vanilla.json after upstream changes it (README)
python3 -m unittest discover -s tools/area_archetypes      # tests
```

`tools/area_archetypes/README.md` documents the archetype rules and the restock options. The committed wild species are vanilla, with only the level offsets applied (`docs/fork/balance.md`, "Wild tables").

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

### `src/debug.c` and `src/debug_menu_ui.c` gotchas
- Put new generic menu UX in `src/debug_menu_ui.c`, not inline in `src/debug.c`. Its helpers take the window template, counts and state pointers as arguments. The numeric input is the exception: it works on the task data slots `DEBUG_DATA_INPUT`/`DIGIT`/`INPUT_START` from `include/debug_menu_ui.h`, which `src/debug.c` names `tInput`/`tDigit`/`tInputStart`.
- Numeric inputs store the value in s16 task data (`tInput`), but a max can be 0xFFFF. Every read, compare and clamp has to go through u16/u32: read it with `DEBUG_TASK_INPUT`, print it with `Debug_InputToDecimalString` (not `ConvertIntToDecimalStringN` on `tInput`, which loses the digit highlight and the u16 read), and size it with the bounded `Debug_CountDigits`. A selection step with `.hex = TRUE` (the Var ID, #36) is dialed in hex instead: print it with `Debug_InputToHexString` and `gText_HexDigitIndicator`.
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
