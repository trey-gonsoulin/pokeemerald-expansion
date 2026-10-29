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
- Twenty-five carried upstream fixes. Upstream has none of them yet, so on every upstream sync check each one and drop it once upstream fixes the bug:
  - Exp from opponent B's Pokémon in two-trainer battles: `GetGivenExpMonsIndex` in `src/battle_util.c`. Covered by `test/battle/exp.c`.
  - Exp when the last foe faints from end-of-turn damage: the `ENDTURN_FAINTED_MON_ACTIONS` check in `DoEndTurnEffects`, `src/battle_end_turn.c`. Covered by `test/battle/exp.c`.
  - TV soft-lock when a regular show is on the air: `specialvar VAR_RESULT, GetSelectedTVShow` in `data/scripts/tv.inc` (10403ef6). No test.
  - Out-of-bounds `gBattleMons[MAX_BATTLERS_COUNT]` write when a sleep-curing item is used on a benched Pokémon: the `targetBattler != MAX_BATTLERS_COUNT` guard on the nightmare clear in `BS_ItemCureStatus`, `src/battle_script_commands.c`, and the `battler != MAX_BATTLERS_COUNT` guard on `PREPARE_MON_NICK_BUFFER` in `HealStatusConditions`, `src/pokemon.c` (#57). The `gBattleMons` guard element (#125) fails three benched-mon tests without the first guard: "Full Restore restores a party members HP…" and "Full Restore heals a party member…" in `test/battle/item_effect/heal_and_cure_status.c`, and "Sleep Clause: Sleep clause is deactivated when a benched sleeping mon is woken up by using an item" in `test/battle/sleep_clause.c`; nothing covers the second, which guards a read.
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
  - U-turn, Volt Switch, Flip Turn and Parting Shot from a user that can't switch (last mon, Battle Arena, Commander) end the action and skip the rest of move end: Pickpocket, Eject Pack, Destiny Bond and Charge expiry, and the per-move bits (a U-turn on the next turn deals no damage). `CanPivotUserSwitch` in `MoveEndHitEscape` and `TryEjectPack`, `src/battle_move_resolution.c`, runs the switch scripts only when the user can switch (#108). Covered for the last-mon and Commander cases by the "User that can't switch" tests in `test/battle/move_effect/hit_escape.c` and `parting_shot.c`, and by "Eject Pack activates if the Parting Shot user can't switch out" in `test/battle/hold_effect/eject_pack.c`. Nothing covers the Battle Arena.
  - The level-up banner is skipped for the player's benched Pokémon whose party index matches the in-game partner's active Pokémon (Gen 6 Exp. Share): `IsMonGettingExpSentOut`, used by `Cmd_drawlvlupbox`, goes through `GetBattlerFromPlayerPartyId`, `src/battle_script_commands.c` (#110). No test: nothing records the banner.
  - Heal Bell and Aromatherapy in a multi battle cure the partner's active mon in battle but not in its own party, so the status comes back on a reload, its status icon stays and Sleep Clause stays active: the `!BattlersShareParty` branch that sends the partner's controller the status update and calls `TryDeactivateSleepClause` in `Cmd_healpartystatus`, `src/battle_script_commands.c` (#111). Covered by the "Heal Bell in a multi battle cures ... party copy" tests in `test/battle/move_effect/heal_bell.c` and the multi Heal Bell test in `test/battle/sleep_clause.c`.
  - The follower Pokémon goes into its Poké Ball when an NPC moves in the script that continues after a talked-to trainer's battle (the Winstrates on Route 111, beaten and post-battle scripts): the `.if OW_FOLLOWERS_SCRIPT_MOVEMENT == FALSE` around the `clearflag FLAG_SAFE_FOLLOWER_MOVEMENT` in `EventSnippet_RevealTrainer`, `data/scripts/trainer_battle.inc`, and the flag restore in `MapHeaderRunScriptTypeKeepSafeFollower`, used by `RunOnResumeMapScript` and `RunOnReturnToFieldMapScript` (those map scripts' `end`s cleared it on the way back from the battle), `src/script.c` (#100). No test.
  - The follower Pokémon goes into its Poké Ball when a script moves an NPC after a `MSGBOX_SIGN` message (the Lilycove Museum 1F curator walking to the stairs, his `FaceExhibitHall` turns on 2F, the Battle Arena corridor attendant): the `.if OW_FOLLOWERS_SCRIPT_MOVEMENT == FALSE` around the `clearflag FLAG_SAFE_FOLLOWER_MOVEMENT` in `Std_MsgboxSign`, `data/scripts/std_msgbox.inc`. The same guard wraps the clears in the unreferenced legacy `EventScript_TryDoNormalTrainerBattle`, `EventScript_DoNoIntroTrainerBattle` and `EventScript_RevealTrainer`, `data/scripts/trainer_battle.inc` (#112). No test: `RUN_OVERWORLD_SCRIPT` loops forever on msgbox, so map scripts with text can't be tested.
  - `make -j` ran `mapjson groups` and `mapjson layouts` once per output, concurrently, each rewriting the same headers (upstream lists the outputs as ordinary targets of one rule, and make 3.81 has no grouped targets `&:`): the outputs, and the `heal_locations.json` that groups rewrites, depend on the gitignored stamps `.mapjson_groups.stamp` and `.mapjson_layouts.stamp` through empty recipes, in `map_data_rules.mk` (#120). No test: check that a cold `make -j16` log has one `mapjson groups` line.
  - `make check` exits 0 with a FAILED (or KNOWN_FAILING or EXPECT_FAIL test that passes) result when that test ran before "Tests resume after CRASH" on the same runner: the ROM restart resets the runner's exit code (`STATE_INIT` in `test/test_runner.c`), so hydra now also exits 1 on those counts, and exits 2 for a runner killed by a signal, whose remaining tests never report (end of `main`, `tools/mgba-rom-test-hydra/main.c`) (#73). No automated test: checked by hand with a failing test at the bottom of `test/test_test_runner.c` and a one-runner `make check`.
  - NPCs, trainers and berry trees on busy maps don't spawn because the follower Pokémon holds one of the 16 object slots (Route 123 berry grove, Lilycove Contest Hall, Mossdeep Gym): `GetAvailableObjectEventId` calls `TryEvictFollowerToFreeObject` when every slot is taken. That first removes the objects that left the view (the camera update spawns before it removes them), then despawns the follower unless a script is running or the field controls are locked. `TryRespawnEvictedFollower`, run by `UpdateObjectEventsForCameraUpdate`, brings it back through `UpdateFollowingPokemon` once a slot is free after the map objects in view have spawned. `sFollowerAwaitingSlot` (EWRAM, not saved) is also set when `UpdateFollowingPokemon` finds no slot on map load and cleared by `ResetObjectEvents`, all in `src/event_object_movement.c` (#114). Covered by `test/follower_object_slots.c`, which spawns objects directly: nothing tests map templates scrolling into view.
  - The HGSS Pokédex forms page (Start on the evolution page) wrote its form icons' sprite IDs to `gTasks[taskId].data[4 + n]`, past the task's 16 slots into the next task's `func` and data for a species with 12 or more other forms (Pikachu's 16 and Unown's 27, both wild in the fork), and its exits then destroyed sprites at the IDs read back from there: the IDs now go in `sFormScreenData.iconSpriteIds` (`FORMS_SCREEN_ICON_COUNT`, the 13 icons the page draws, `include/pokedex_common.h`), set by `PrintForms` and freed by `DestroyFormIcons`. Picking a form with A also left the icons and the cursor arrow allocated (it went straight to `Task_LoadInfoScreenWaitForFade`), so it now destroys the arrow and goes through `Task_SwitchScreensFromFormsScreen`, all in `src/pokedex_plus_hgss.c` (#70). `test/pokedex_plus_hgss.c` covers the icon IDs through the `TESTING` hook `Test_PrintAndDestroyFormIcons`; nothing covers the page's exits.
  - The party menu's Switch reset `gFollowerSteps` (the leader's steps that `IF_MIN_OVERWORLD_STEPS` evolutions such as Pawmo's count) from the previous switch's `slotId2`, before it was set: moving a Pokémon into the lead slot kept the old count, and cancelling a switch reset it. `SwapPlayerPartySlots`, which `SwitchPartyMon` now swaps through, resets it when the swap changes `GetFirstLiveMon()` (the leader the evolution check and the PC use, so an Egg or fainted mon in slot 0 isn't the leader), in `src/party_menu.c` (#141). `test/party_menu.c` covers it through the `TESTING` hook `Test_SwapPlayerPartySlots`; nothing covers the menu path that calls it.
- Overworld debug menu improvements. The engine is fork-owned, in `src/debug_menu_ui.c` (API in `include/debug_menu_ui.h`): odometer numeric input and its digit highlight, list paging, scroll arrows, the submenu path window and the menu-position restore. `src/debug.c` keeps the menus, their state (`sDebugMenuListData`) and the hooks that call the engine.
  - Name order (#12): on the species, item and move steps (`.names` on the `DebugSelectionStep`), Start jumps to the first name with the next initial letter, and Up/Down then step A-Z until another key turns it off. The first Start on each kind of step in a menu session sorts its range into `sDebugMenuListData->sortedNames[]` (`Debug_BuildNameOrder`: about 18 frames for the ~1,570 species, 9 for items or moves; scanning on every press took 4 frames per step), which `Debug_DestroyMenu_Leave` frees. Disabled species and unnamed items are left out. Covered by `test/debug_menu_ui.c`; the input handling in `src/debug.c` isn't.
  - Warp shows map.json names from `src/data/debug_map_names.h`, which `mapjson groups` generates (`generate_debug_map_names_text` in `tools/mapjson/mapjson.cpp`, a fork change to an upstream tool). It is indexed like `gMapGroups`, with NULL for the other game's groups, which the group step refuses. "Recent warps…" (first in Utilities) lists this session's last 8 destinations from EWRAM, and Warp starts from the newest (#13). LTO drops all of it from the release ROM.
  - Set Flag and Set Var show the flag's or var's constant name (without `FLAG_`/`VAR_`, "-" for one without a name) on the second line of Warp's 28-tile window, and Start gives name order on the flag and var ID steps (`DEBUG_STEP_NAMES_FLAGS`/`VARS`; `.names` is now 3 bits). The first Start on Set Flag sorts its 1,527 names in about 42 frames, Set Var's 256 in 3 (#14).
    - A trainer flag shows its trainer's class and name from `gTrainers` instead, such as "LEADER ROXANNE" (`Debug_CopyTrainerFlagName`, `src/debug_menu_ui.c`), and "-" for a trainer without a party (`TRAINER_NONE`) and the unused IDs from `TRAINERS_COUNT` on. Name order still skips the trainer flags (#136).
    - `tools/misc/make_debug_flag_var_names.py` generates the gitignored `src/data/debug_flag_var_names.h` from `flags.h`, `flags_frlg.h`, `vars.h`, `vars_frlg.h` (under `#if IS_FRLG`: `vars.h` includes it in every game) and the configs, whose flag aliases such as `I_EXP_SHARE_FLAG` (the fork's `FLAG_UNUSED_0x264`) are shown whole. Read the names through `Debug_GetFlagName`/`Debug_GetVarName` in `src/debug_menu_ui.c`.
    - The compiler computes the values (many need enums), so every entry is `#if defined(...)`-guarded and indexed through a macro that sends values outside the table to an unread last slot. Where names share a value, the last initializer wins (`-Woverride-init` is off in that header), and the generator orders the entries so that the first defined real name beats a config alias, which beats `UNUSED` placeholders and `_START`/`_END`/`_COUNT` markers.
    - Behind `DEBUG_FLAG_VAR_NAMES` (`include/config/debug.h`, TRUE): about 50 KB of the debug-menu ROM, none of the release ROM. Covered by `test/debug_menu_ui.c` and `python3 -m unittest discover -s tools/misc` (in CI); the picker display isn't.
- `tools/area_archetypes/`, a standalone Python tool (see below).
- Story boss levels raised for the Gen 6 Exp. Share (#127), levels only, in `src/data/trainers.party` and Steven's in `src/data/battle_partners.party`. These are fork data changes:
  - The owner's rule: balance with the Exp. Share on and the 1.5x trainer exp off, mainly by raising opponent levels, never with a level cap.
  - Each boss's ace sits 1 above the modelled Exp. Share bench on a full clear. The Elite Four step one level per fight, and Wallace sits 3 above Drake.
  - `tools/rebalance/` (standard library, imports the area_archetypes parsers) models the curve. `python3 tools/rebalance/rebalance.py` regenerates `output/report.md`, which CI checks for drift, so rerun it after any `trainers.party` change. `output/findings.md` is hand-written: the analysis, the targets and the owner's decisions. A rival level change has to go on all six teams of that fight (May or Brendan with each starter), and boss raises also move the Mossdeep partner battle and the post-game rematches.
- Story boss AI and moves, also fork data changes in `src/data/trainers.party`:
  - Smart AI (#129) on 92 teams: the gym leaders and their rematches, the Elite Four, Wallace, every May and Brendan team, Wally, Maxie, Archie, Tabitha, Matt, Shelly and the post-game Steven (Meteor Falls). Their `AI:` line is `AI_FLAG_SMART_TRAINER` (`include/constants/battle_ai.h`) spelled out without `Omniscient` and `Smart Tera`, then any flag the team already had (Winona's `Risky`, three `Force Setup First Turn`). Smart Tera keeps each mon's Tera Type, which lets the AI Terastallize while the player has no Tera Orb.
  - Four moves the physical/special split weakened, each now a same-type move on the stronger stat that the species learns here (#130): Wallace's Gyarados Hyper Beam -> Double-Edge, Phoebe's two Banette Shadow Ball -> Phantom Force, Glacia's first Sealeo Ice Ball -> Aurora Beam, Wattson's Voltorb Spark -> Charge Beam.

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
- CI: `.github/workflows/emerald-plus.yml` runs the full `make check`, both ROMs and the area_archetypes unittests on pushes to `emerald-plus` and `issue-*` and on PRs into `emerald-plus`. KNOWN_FAILING, TO_DO and ASSUMPTIONS_FAILED results don't fail it (upstream fails on skipped assumptions only in rh-hideout's own CI), but a KNOWN_FAILING test that passes does. The job times out after 60 min: the ROM's 60 s TIMEOUT (a Timer2 interrupt) can't catch every hang, and hydra itself has no timeout (#73). Upstream's `build.yml` doesn't run on fork pushes, but it does run on every PR.
- What a green `make check` doesn't prove (#73):
  - Headless tests skip every battle animation except Transform and Ally Switch, and record battle messages without drawing them.
  - The memory checks are heap corruption, leaked heap blocks and leaked tasks, plus a guard element (#125, a fork change): test builds give `gBattleMons`, `gBattlerPartyIndexes` and `gObjectEvents` one extra element (`+ TESTING` in their declarations), which `CB2_TestRunner` fills with 0xFF before each test and fails a test that passed (and was expected to) if any byte changed (`sGuardElements`, `test/test_runner.c`). It catches writes only, and only into the element just past the end: an out-of-bounds read (#57's `gBattlerPartyIndexes[4]`), a write further out, or one into any other static array (the per-battler `gBattleStruct` arrays included) still passes.
  - The ROM restart after "Tests resume after CRASH" resets that runner's exit code, so a failure that ran before it there doesn't fail the run by itself. Only tests defined below it in `test/test_test_runner.c` can hit this (that file runs first, and a file's tests run bottom up), and the fork's hydra now exits 1 on its counts instead (carried fix above).
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
