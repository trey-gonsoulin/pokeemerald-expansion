# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Emerald Plus is a personal fork of [rh-hideout/pokeemerald-expansion](https://github.com/rh-hideout/pokeemerald-expansion), a GBA ROM hack base built on pret's pokeemerald decompilation.

- `emerald-plus` (the default branch on `origin`) is the integration branch. Branch from it and merge into it.
- `master` mirrors upstream, and the `upstream` remote is rh-hideout. Don't commit to `master`.
- Commit messages are a plain imperative sentence with `(#N)` appended, e.g. `Remember debug menu cursor position (#9)`.

What the fork adds over upstream (`git diff origin/master...origin/emerald-plus --stat`):
- Personal-playthrough config flips in `include/config/` (reusable TMs, Gen 6 Exp. Share on `FLAG_UNUSED_0x264`, followers, HGSS Pokédex, IV/EV summary, forgettable HMs).
- Prize swaps so those config flips don't hand out useless items (#102, #103). These are fork changes, not upstream fixes:
  - With `I_EXP_SHARE_ITEM >= GEN_6`, the Lottery Corner 3-digit prize is a Lucky Egg instead of the key-item Exp. Share (`sLotteryPrizes`, `src/lottery_corner.c`). Covered by `test/lottery_corner.c`.
  - With reusable TMs, a TM the player already owns (bag or PC) becomes a PP Up: Trainer Hill's grand prize (`GiveChallengePrize`, `src/trainer_hill.c`, covered by `test/trainer_hill.c`) and the Game Corner TM prizes, which offer the PP Up for the same coins with a yes/no (`data/maps/MauvilleCity_GameCorner/scripts.inc`, no test).
- Fifteen carried upstream fixes. Upstream has none of them yet, so on every upstream sync check each one and drop it once upstream fixes the bug:
  - Exp from opponent B's Pokémon in two-trainer battles: `GetGivenExpMonsIndex` in `src/battle_util.c`. Covered by `test/battle/exp.c`.
  - Exp when the last foe faints from end-of-turn damage: the `ENDTURN_FAINTED_MON_ACTIONS` check in `DoEndTurnEffects`, `src/battle_end_turn.c`. Covered by `test/battle/exp.c`.
  - TV soft-lock when a regular show is on the air: `specialvar VAR_RESULT, GetSelectedTVShow` in `data/scripts/tv.inc` (10403ef6). No test.
  - Out-of-bounds `gBattleMons[MAX_BATTLERS_COUNT]` write when a sleep-curing item is used on a benched Pokémon: the `targetBattler != MAX_BATTLERS_COUNT` guard on the nightmare clear in `BS_ItemCureStatus`, `src/battle_script_commands.c`, and the `battler != MAX_BATTLERS_COUNT` guard on `PREPARE_MON_NICK_BUFFER` in `HealStatusConditions`, `src/pokemon.c` (#57). `test/battle/item_effect/heal_and_cure_status.c` runs the benched path, but nothing on GBA can detect the stray write.
  - Sleep Clause stays active after a sleep-curing item is used on a benched sleeper: the `TryDeactivateSleepClause` call for a benched target (`targetBattler == MAX_BATTLERS_COUNT`) in `BS_ItemCureStatus`, `src/battle_script_commands.c` (#98). Covered by the benched-mon item test in `test/battle/sleep_clause.c`.
  - A move the player's Pokémon learns on level up also lands on the in-game partner's active Pokémon with the same party index (multi battles such as Steven's): the `GetBattlerTrainer(battler) == B_TRAINER_PLAYER` checks in `Cmd_handlelearnnewmove` and `Cmd_yesnoboxlearnmove`, `src/battle_script_commands.c` (#64). `test/battle/exp.c` covers the first; tests always decline the forget-a-move prompt, so nothing covers the second.
  - Exp for the player's benched Pokémon whose party index matches the in-game partner's active Pokémon (the partner's party indexes were OR'ed into the player's sent-in bits): the `GetBattlerTrainer(...) == B_TRAINER_PLAYER` checks in `ResetSentPokesToOpponentValue`, `OpponentSwitchInResetSentPokesToOpponentValue` and `UpdateSentPokesToOpponentValue`, `src/battle_util.c` (#64). Covered by `test/battle/exp.c`.
  - The level-up animation and healthbox refresh land on the in-game partner's active Pokémon when its party index matches the levelling player Pokémon: `IsMonOnPartnerBattler` in `src/battle_controller_player.c`, used by `Task_GiveExpToMon`, `Task_LaunchLvlUpAnim` and `Task_UpdateLvlInHealthbox` (#64). Covered by `test/battle/exp.c`.
  - Roar, Whirlwind, Dragon Tail and Red Card fail against the in-game partner's or opponent B's Pokémon in multi battles (they searched party slots 3-5, but each trainer's Pokémon now start at slot 0 of its own party): the party range and `BattlersShareParty` check in `Cmd_forcerandomswitch`, `src/battle_script_commands.c` (#64). Covered by the multi battle tests in `test/battle/move_effect/roar.c`.
  - Name Rater, Frontier breeder and Nature Girl accept an Egg picked from the PC: `ScriptGetPartyMonSpecies` in `src/field_specials.c` reads the mon through `GetSelectedBoxMonFromPcOrParty`, not `gParties[...][gSpecialVar_0x8004]`, which is out of bounds for `PC_MON_CHOSEN` (#66). Covered by `test/script_specials.c`.
  - Multi battle items used on a benched mon act on the partner's battler when the party indexes match: `IsItemTargetActivePartner` (a `BattlersShareParty` check) in `BS_ItemRestoreHP`, `BS_ItemCureStatus` and `BS_ItemRestorePP`, plus the `BattlersShareParty` guard on the absent-partner Revive send-out, `src/battle_script_commands.c` (#65). Covered by `test/battle/item_effect/multi_battle_party.c`.
  - Revival Blessing in a multi battle sends the partner's battler out again: the `BattlersShareParty` guard in `BS_TryRevivalBlessing`, `src/battle_script_commands.c` (#65). Covered by the multi test in `test/battle/move_effect/revival_blessing.c`.
  - Poke Flute soft-lock in single battles: the `position < gBattlersCount` loop bound in `BS_CheckPokeFlute`, `src/battle_script_commands.c` (#65). Covered by the single-battle test in `test/battle/item_effect/poke_flute.c`.
  - X items used from the bag are checked against the wrong party slot: `CannotUseItemFromBagInBattle` in `src/item_use.c`, called by `ItemUseInBattle_BagMenu` (#65). Covered by the bag tests in `test/battle/item_effect/increase_stat.c`.
  - Heal Bell (Gen 6+ Soundproof rule) in a multi battle skips the user's benched mon at the partner's party index when the partner's active mon has Soundproof: the `BattlersShareParty` check on `isDoublesPartner` in `Cmd_healpartystatus`, `src/battle_script_commands.c` (#65). Covered by the "Heal Bell in a multi battle" tests in `test/battle/move_effect/heal_bell.c`.
  - U-turn, Volt Switch, Flip Turn and Parting Shot from a user that can't switch (last mon, Battle Arena, Commander) end the action and skip the rest of move end: Pickpocket, Destiny Bond and Charge expiry, and the per-move bits (a U-turn on the next turn deals no damage). `CanPivotUserSwitch` in `MoveEndHitEscape`, `src/battle_move_resolution.c`, runs the switch scripts only when the user can switch (#108). Covered by the "User that can't switch" tests in `test/battle/move_effect/hit_escape.c` and `parting_shot.c`.
- Overworld debug menu improvements. The engine is fork-owned, in `src/debug_menu_ui.c` (API in `include/debug_menu_ui.h`): odometer numeric input and its digit highlight, list paging, scroll arrows, the submenu path window and the menu-position restore. `src/debug.c` keeps the menus, their state (`sDebugMenuListData`) and the hooks that call the engine.
- `tools/area_archetypes/`, a standalone Python tool (see below).

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
- Warnings that are expected and not regressions (build.sh allowlists each exact line, so a new warning in the same file still shows):
  - `release` only, from the LTO link: pokedex.c:4507 stringop-overflow (x6), mystery_gift_client.c:102 stringop-overread, and the `-Wlto-type-mismatch` on intro_frlg.c:249 (`gMultiBootProgram_PokemonColosseum_Start`) and faraway_island.h:4 (`GetMewMoveDirection`).
  - Every ROM build: the RWX segment linker warning. Plain `make`, `debug` and `check` emit only this one (plus the tool and asset ones below on a cold tree).
  - Tool and asset builds: json.hpp `-Wdeprecated-literal-operator` and `libpng warning: bKGD: invalid index`.

## Tests

Run these in the same shell setup as the build (devkitARM on PATH, host compiler variables unset), or use `.claude/build.sh <worktree> check ["Lucky Egg"]`.

```sh
make check -j16 TOOLCHAIN=/opt/devkitpro/devkitARM                    # all tests, headless via mgba-rom-test-hydra
make check -j16 TESTS="Lucky Egg" TOOLCHAIN=/opt/devkitpro/devkitARM        # tests whose name starts with the prefix
make pokeemerald-test.elf TESTS="Lucky Egg" TOOLCHAIN=/opt/devkitpro/devkitARM  # open in mGBA to watch them
```

- Tests live in `test/` (mostly battle mechanics). They use `ASSUMPTIONS` / `GIVEN` / `WHEN` / `SCENE` blocks; see `docs/tutorials/how_to_testing_system.md`.
- Name related tests with a shared prefix so `TESTS=` can select them.
- CI: `.github/workflows/emerald-plus.yml` runs the full `make check`, both ROMs and the area_archetypes unittests on pushes to `emerald-plus` and `issue-*` and on PRs into `emerald-plus`. KNOWN_FAILING tests don't fail it. Upstream's `build.yml` doesn't run on fork pushes, but it does run on every PR.
- **Nothing covers `src/debug.c` or other overworld UI.** Verify those changes by building both ROMs (no new warnings in the changed file) and with a written in-game test plan.

Area archetypes tool (standard library only, run from the repo root):

```sh
python3 tools/area_archetypes/area_archetypes.py fetch     # once: PokeAPI CSVs -> .cache/
python3 tools/area_archetypes/area_archetypes.py build     # classify areas, write output/
python3 tools/area_archetypes/area_archetypes.py restock   # preview a restocked src/data/wild_encounters.json
python3 tools/area_archetypes/area_archetypes.py baseline --wild <upstream copy>  # refresh output/wild_encounters.vanilla.json after upstream changes it (README)
python3 -m unittest discover -s tools/area_archetypes      # tests
```

`tools/area_archetypes/README.md` documents the archetype rules and the restock options. `build` and `restock` read the committed vanilla snapshot, never the live `src/data/wild_encounters.json`, so `restock --write` reruns don't compound.

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
- Numeric inputs store the value in s16 task data (`tInput`), but a max can be 0xFFFF. Every read, compare and clamp has to go through u16/u32: read it with `DEBUG_TASK_INPUT`, print it with `Debug_InputToDecimalString` (not `ConvertIntToDecimalStringN` on `tInput`, which loses the digit highlight and the u16 read), and size it with the bounded `Debug_CountDigits`.
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
