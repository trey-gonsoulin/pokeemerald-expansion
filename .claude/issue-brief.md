# emerald-plus issue brief (address-issues-parallel)

Binding rules for workflow agents, on top of the repo CLAUDE.md.

## Repo
- The base branch is `emerald-plus` (origin's default). Branch from `origin/emerald-plus`. `master` mirrors upstream; never touch it.
- Commit messages are a plain imperative sentence with `(#N)` appended, e.g. `Keep the debug menu open when B leaves a short submenu (#31)`. Don't use `type(scope):` prefixes.
- Match the surrounding C style in `src/debug.c`: 4-space indent, braces on their own line, `static` helpers, and task-data `#define`s like tInput/tDigit.

## Build and tests
Use `.claude/build.sh`. It sets the devkitARM PATH and TOOLCHAIN, unsets the host compiler variables (`CPATH`, `LDFLAGS`, …), logs to `<worktree>/build/<target>.log`, and prints only the exit code plus unexpected errors and warnings. Pass your worktree's absolute path as the first argument. Run it as a plain command, not inside `cd …;` or `export …;` chains.

- `sh .claude/build.sh <worktree> src/debug.c` compiles one file. On a cold tree it builds the tools and generated sources too, in about 20 s. Use it for quick checks while iterating.
- `sh .claude/build.sh <worktree> rom` builds the ROM with the debug menu: about 1 min cold alone, about 4.5 min when four agents build at once. `… release` builds the ROM with the debug menus off.
- `sh .claude/build.sh <worktree> generated` builds the tools, then the generated headers. Plain `make generated` fails on a fresh worktree (`No rule to make target tools/mapjson/mapjson`), and `make tools` fails too. You only need this before a partial build that isn't a `src/*.c` file.
- **Implementers:** before you finish, both `rom` and `release` must exit 0 with no new warnings in the files you changed. If you change battle code or anything under `test/`, `sh .claude/build.sh <worktree> check` must also report 0 FAILED. If you change `tools/area_archetypes/`, run its unittests too.
- CI (`.github/workflows/emerald-plus.yml`) runs `check`, both ROMs and the area_archetypes unittests when your `issue-*` branch is pushed. Check it with `gh run list --branch issue-<N>`.
- **Reviewers:** don't rebuild the ROMs, because the implementer already did. Compile each changed `src/*.c` file in your own worktree with the single-file target.
- `… debug` builds the -Og/-g ROM and `… check ["TESTS prefix"]` runs the headless tests (it prints the failing tests, if any, and the FAILED/PASSED/TOTAL counts). Both link because build.sh unsets the host `CPATH`/`LDFLAGS`; that leak, not gcc 16.1, was the cause of #27. Always build through build.sh: a plain `make` from an agent shell inherits the leak, and the `unset …;` chain in CLAUDE.md's manual recipe is refused here. The debug build is written to `pokeemerald-debug.gba`/`.elf`, so it doesn't clobber the `rom` output. `make check` doesn't cover `src/debug.c`.

## Testing debug-menu changes
There are no automated tests for the debug menu.
- In the report, give a short in-game test plan the user can run in an emulator: steps and the expected result.
- Reason through task-scheduler and frame-order effects explicitly. In `src/task.c`, CreateTask reuses the first free slot, and RunTasks follows `.next` after each func returns.

## Gotchas (src/debug.c, src/debug_menu_ui.c)
- The generic menu engine (numeric input and digit rendering, paging, scroll arrows, path window, position restore) lives in `src/debug_menu_ui.c`, with its API in `include/debug_menu_ui.h` (#60). Put new generic UX there; `src/debug.c` keeps the menus, their state and the hooks. The header owns the numeric-input slots (`DEBUG_DATA_INPUT`/`DIGIT`/`INPUT_START`) and the sprite tags. Start an input with `Debug_StartNumericInput`, and print it with `Debug_InputToDecimalString`.
- Numeric inputs keep the value in s16 task data (`tInput`), but a max can be 0xFFFF. Every read, compare and clamp goes through u16/u32.
- Steps that skip invalid values (species) are bounded with a `maxFunc`. `IsSpeciesEnabled(SPECIES_EGG)` is TRUE, and SPECIES_EGG == NUM_SPECIES.
- Task data slots:
  - tMenuTaskId=0, tWindowId=1, tSubWindowId=2, tInput=3, tDigit=4, tSpriteId=5, tInputStart=7, tStepsDataCount=9 (the stepsData slot is derived by `DebugSelection_DataIndex`, never tracked by hand), tSubstep=10, tStep=11.
  - data[14]/[15] hold word args.
  - Free slots are scarce. Put extra state in `sDebugMenuListData`.
- Several branches may edit `src/debug.c` in parallel. Keep diffs to the functions your issue needs, with no drive-by reformatting.
- `src/debug.c` is about 5000 lines. Always `grep -n` first, then Read at most 150 lines at a time.

## Sandbox
- No `cd … && git`, shell loops, heredocs or `VAR=… cmd` prefixes.
- No shell variables in commands (`F=…; sed $F` gets refused): write the literal paths.
- Use `git -C <your worktree>`. Write files with the Write tool, then run a plain command.
