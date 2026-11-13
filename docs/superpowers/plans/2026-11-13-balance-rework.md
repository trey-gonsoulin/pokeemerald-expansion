# Balance Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the level curve so skipping every skippable trainer leaves the lead about 15% under each boss, fighting every trainer leaves it about 10% over, and a solo starter that fights everyone needs at most 50 KOs at any wall. The exp formula becomes flat, with 1.5x trainer exp off and a softened over-level penalty.

**Architecture:** A new standard-library tool, `tools/forced_trainers`, classifies every story trainer as forced or skippable and writes `tools/rebalance/forced_trainers.json`. `tools/rebalance` then models two players in lockstep (fight everyone, skip everything), sets the bosses from both, can lower levels (devolving Pokémon and rewriting moves they can no longer learn), and reports and pins solo walls against a grind budget. The game side changes only config values in `include/config/battle.h`.

**Tech Stack:** Python 3 (standard library only), `unittest`, the pokeemerald-expansion C tests (`make check`), devkitARM through `.claude/build.sh`.

**Spec:** `docs/superpowers/specs/2026-11-13-balance-rework-design.md`

## Global Constraints

- **Targets (spec, Goals):**
  - fight everyone: lead at least **10%** over each staged boss's ace (`full_margin: 10`);
  - skip everything: at most **15%** under (`skip_margin: 15`);
  - solo grind budget: **50 KOs**;
  - outlier threshold: a skip-everything lead more than **25%** under an ace.
- **Boss ace** = min(full lead / 1.10, skip lead / 0.85), rounded half up. The other rules stay:
  - Elite Four `LEAGUE_STEPS`;
  - all six rival variants share levels;
  - Steven's Mossdeep partner follows his foes;
  - a staged boss's team keeps distinct species;
  - everything is capped at 100.
- **Unchanged rules:** `trainer_gap` 10% and `wild_gap` 20% under the fight-everyone reference; water tables from `SURF_STAGE`; post-game ladders by their existing rules.
- **Exp configs:**
  - `B_SCALED_EXP GEN_6`, `B_SCALED_EXP_STEEP FALSE`, `B_TRAINER_EXP_MULTIPLIER GEN_LATEST`;
  - `B_EXP_OVERLEVEL_CUTOFF`, `_WIDTH` and `_FLOOR` from Task 8's sweep (the trial is 30 / 6 / 30);
  - `B_EXP_OVERLEVEL_MIN_LEVEL` re-derived in Task 9;
  - no save-layout change.
- **Measured against:** the "lead" is the Exp. Share KO-taker, the highest member: `boss_ref: "ace"` in `curve_settings.json`, used by `full_margin` and `skip_margin`.
- **Tools:** Python standard library only, run from the repo root. Never edit generated outputs; rerun `python3 tools/rebalance/rebalance.py` and commit `output/` with every data change, since CI checks for drift.
- **Build and tests:** through `.claude/build.sh <worktree> rom|release|check [TESTS]`. Never put devkitARM on PATH by hand.
- **Commits:** a plain imperative sentence with ` (#N)` appended, where N is the rework's GitHub issue (Task 0). Work on branch `balance-rework`. PRs go into `emerald-plus`.
- **Style:** new tool files follow `tools/rebalance`: module docstrings, short function docstrings, no third-party imports. New explorer modules go in `explorer/model.js` `FILES`.

**Deviation from the spec's rollout:** the spec has four PRs, with the configs (PR 2) separate from the data (PR 3). That doesn't work: `RealRepo.test_data_meets_the_curve_settings` reads the game configs, so flipping them fails CI until the new curve is in the data. This plan ships three PRs:
1. tools and model, with no game change (Tasks 1–7);
2. configs, tests and the new curve data (Tasks 8–11);
3. docs (Task 12).

## Review Focus

1. **Lowering a Pokémon whose pre-evolution isn't in `gd.species`, or that has none:** the species stays and only the level drops (never below 1). Test in Task 4.
2. **A boss that the skip-everything player never fights** (the optional Rustboro and Lilycove rivals): its ace comes from the fight-everyone rule alone, and its row's skip fields are `None`. Test in Task 3.
3. **Running `apply` twice:** the second run changes nothing. Lowering devolves, and the non-level evolve pass (#181) must not evolve those Pokémon straight back, because that oscillates. Test in Task 10.
4. **Rival variants after lowering:** all six teams of a rival fight end at the same levels even when only one devolves differently. Test in Task 10.
5. **Wild offsets lowered below vanilla:** an offset never goes under 0, so restock never writes a level under vanilla's or under 1. Test in Task 3.

---

## PR 1: Tools and model (no game or data change)

### Task 0: Open the issue

- [ ] **Step 1:** Ask the owner to approve opening a GitHub issue "Rework the balance around trainers fought" whose body links the spec. Once approved, run `gh issue create` and record its number N for every commit message.

### Task 1: `tools/forced_trainers`, the forced-trainer classifier

**Files:**
- Create: `tools/forced_trainers/engine.py`, `specs.py`, `classify.py`, `render.py` and `README.md`. They come from `tools/forced_trainers/prototype/`, with its hardcoded paths replaced by `G.REPO` (`tools/rebalance/gamedata.py`) and its debugging scripts other than `render.py` dropped.
- Create: `tools/forced_trainers/test_forced_trainers.py`, `tools/forced_trainers/testdata/` (fixture layouts)
- Create: `tools/rebalance/forced_trainers.json` (generated)
- Delete: `tools/forced_trainers/prototype/` except `model/` (Tasks 6–7 port that, then delete it)
- Modify: `.github/workflows/emerald-plus.yml` (run `python3 -m unittest discover -s tools/forced_trainers`)

**Interfaces:**
- Produces:
  - `classify.classify(repo: str) -> dict`, shaped as `{'regular': {trainer_id: {'stage', 'map', 'class': 'FORCED'|'AVOIDABLE'|'UNCERTAIN', 'reason', 'timing'?: bool, 'one_of'?: [ids]}}, 'bosses': {boss_id: {'stage', 'required': bool, 'reason'}}}`;
  - `classify.main(argv)`, which writes the file (`--check` exits 1 when the committed file differs);
  - `engine.Grid.from_layout(repo, layout_id) -> Grid`, `engine.sight_tiles(grid, obj) -> set[(x, y)]` and `engine.path_exists(grid, start, goals, blocked) -> bool`.

- [ ] **Step 1: Write the failing tests** in `test_forced_trainers.py`. Fixture layouts are tiny `map.bin` grids written by a helper in the test:
  - `test_trainer_seeing_across_the_only_corridor_is_forced`: a 1-wide corridor with a trainer facing across it gives `FORCED`.
  - `test_open_field_trainer_is_avoidable`: the same trainer on a 5-wide field gives `AVOIDABLE`.
  - `test_wall_blocks_sight`: no sight tiles beyond an impassable tile.
  - `test_turning_trainer_is_avoidable_by_timing`: `MOVEMENT_TYPE_ROTATE_*` in the corridor gives `AVOIDABLE` with `timing: True`.
  - `test_ledge_is_one_way`: a ledge path is walkable downward only.
  - `RealRepo.test_committed_file_is_current`: `classify(G.REPO) == json.load(forced_trainers.json)`.
  - `RealRepo.test_known_forced`: these are `FORCED`: `TRAINER_GRUNT_PETALBURG_WOODS`, `TRAINER_GRUNT_RUSTURF_TUNNEL`, `TRAINER_GRUNT_MUSEUM_1`, `TRAINER_GRUNT_MUSEUM_2`, `TRAINER_EDGAR`.
  - `RealRepo.test_optional_rivals`: `TRAINER_MAY_RUSTBORO_MUDKIP` and `TRAINER_MAY_LILYCOVE_MUDKIP` have `required: False`, and every other staged boss `True`.
- [ ] **Step 2:** Run `python3 -m unittest discover -s tools/forced_trainers`. Expected: it fails with ImportError.
- [ ] **Step 3:** Port the prototype into `engine.py` (grid, sight, BFS), `specs.py` (story paths per stage, HMs by stage, choose-one groups, script-forced calls with reasons) and `classify.py` (`classify` and `main`). The README carries the agent's method, its limits and the in-game check list: the Mauville and Lavaridge gyms, the patrollers (Jasmine, Sophie, Coby, Cale, Aqua grunts 1 and 4, Magma grunts 4 and 5), Fortree's gates and Mossdeep's spin tiles.
- [ ] **Step 4:** Run `python3 tools/forced_trainers/classify.py`, then the unittests. Expected: they pass, with counts of 46 forced, 388 avoidable and 35 uncertain, or a documented difference in the README.
- [ ] **Step 5:** Add the CI step. Commit: `Classify forced and skippable story trainers (#N)`.

### Task 2: Load the forced data and build the skip-everything stages

**Files:**
- Modify: `tools/rebalance/rebalance.py` (near `load_stages`)
- Test: `tools/rebalance/test_rebalance.py` (new class `TwoPlayers`), `tools/rebalance/testdata/forced_trainers.json` (fixture)

**Interfaces:**
- Produces:
  - `FORCED_TRAINERS = os.path.join(G.HERE, 'forced_trainers.json')`;
  - `Forced = namedtuple('Forced', 'trainers optional_bosses')` (both frozensets);
  - `load_forced(path: str) -> Forced`: FORCED trainers plus the first member of each `one_of` group;
  - `skip_stages(stages: list, forced: Forced) -> list`: deep copies with `regular` kept to `forced.trainers` and `bosses` without `forced.optional_bosses`.

- [ ] **Step 1: Write the failing tests:**
  - `test_load_forced_takes_one_of_each_group`: a fixture with group `[A, B]` and FORCED `C` gives `trainers == {A, C}`.
  - `test_skip_stages_drops_optional_bosses_and_skippable_trainers`.
  - `test_skip_stages_leaves_the_input_alone`.
- [ ] **Step 2:** Run `python3 -m unittest tools/rebalance/test_rebalance.py -k TwoPlayers`. Expected: it fails.
- [ ] **Step 3:** Implement the three definitions above.
- [ ] **Step 4:** Run it again. Expected: it passes.
- [ ] **Step 5:** Commit: `Load the forced trainers into the curve model (#N)`.

### Task 3: Two players in `share_run`, the boss rule and lowering

**Files:**
- Modify: `tools/rebalance/rebalance.py`: `share_run` (lines ~957–1111), `EXPLORER_KNOBS` and `explore_run`
- Test: `tools/rebalance/test_rebalance.py` (`TwoPlayers`)

**Interfaces:**
- Consumes: `Forced` and `skip_stages` (Task 2).
- Produces:
  - `share_run(..., skip=None, full_margin=None, skip_margin=None, lower=False)`:
    - `skip` is a `Forced`, or None for today's single player;
    - the margins are percent (`full_margin` also needs `relative_gaps`);
    - `lower` lets the boss raises, the per-stage trainer shift and the wild offset go negative (the wild offset floors at 0 over vanilla).
  - Each boss row gains `skip_levels` and `skip_ref` (None when that player skips the boss). Each stage row gains `skip_gap`.
  - `EXPLORER_KNOBS` gains `'full_margin': None`, `'skip_margin': None` and `'lower': False`. `explore_run` loads the forced data from `snap['forced']`, and `load_snapshot`/`curve_snapshot` carry it.

The rule, when both margins are set:

```python
target = full_ref * 100 / (100 + full_margin)
if skip_ref is not None:
    target = min(target, skip_ref * 100 / (100 - skip_margin))
ace = int(target + 0.5)  # then LEAGUE_STEPS as today
```

The skip party fights in lockstep. Each stage it takes the same walking, catches and wild battles as the full party. It fights the forced subset of that stage's trainers with the same shift `d`, and its bosses at the same raise, but only those it doesn't skip. `trainer_gap`'s search for `d` still measures the full party only. With `lower`, the search runs `d` over `range(-100, 100)`, from the most negative, and takes the first that meets the gap.

- [ ] **Step 1: Write the failing tests** (on the `testdata/repo` fixture through `repo_inputs`):
  - `test_without_skip_rows_match_today`: `share_run(..., skip=None)` rows equal today's output (snapshot the current rows in the test).
  - `test_boss_ace_is_the_lower_of_the_two_rules`: hand-checked numbers on a fixture boss.
  - `test_skipped_boss_uses_the_full_rule`: an optional boss row has `skip_ref is None`, and its ace equals `int(full_ref / 1.10 + 0.5)`.
  - `test_lower_lets_raises_go_negative`: a fixture boss above both targets gets a negative raise with `lower=True` and 0 with `lower=False`.
  - `test_wild_offset_never_below_vanilla`: with `lower=True` and a wild table already under the gap, the offset is `>= 0`.
- [ ] **Step 2:** Run `-k TwoPlayers`. Expected: the new tests fail.
- [ ] **Step 3:** Implement it in `share_run` and thread the knobs through `explore_run`.
- [ ] **Step 4:** Run the whole `tools/rebalance` suite. Expected: everything passes, and `RealRepo.test_data_meets_the_curve_settings` is unchanged because the new knobs are off.
- [ ] **Step 5:** Commit: `Model the skip-everything player beside the full clear (#N)`.

### Task 4: Devolve on lowering

**Files:**
- Modify: `tools/rebalance/rebalance.py`: `evolver`, `evolve_team`, `shifted_slots` and `raise_party`
- Test: `tools/rebalance/test_rebalance.py` (`RaiseParty`, `TwoPlayers`)

**Interfaces:**
- Produces:
  - `devolver(info, gd) -> devolve(species: str, level: int) -> str`, which is `info.devolve(species, level - EVOLVE_GRACE)` kept to `gd.species` (it returns the input species when the result isn't in `gd`);
  - `evolve_team(mons, delta, evolve, unique=False, devolve=None)`: with `delta < 0` and `devolve`, each Pokémon becomes `devolve(species, level + delta)`;
  - `shifted_slots(slots, shift, evolve=None, devolve=None)` does the same for wild slots, with levels floored at 1;
  - `raise_party(text, raises, evolve=None, unique=(), devolve=None)`: negative raises lower levels, floored at 1, and devolve; a team in `EVOLVE_EXEMPT` or a partner team never devolves either.

- [ ] **Step 1: Write the failing tests:**
  - `test_lowered_grovyle_devolves_below_grace`: Grovyle 18 lowered by 2 (to 16, under 16 + 3) becomes Treecko.
  - `test_lowered_grovyle_kept_at_grace`: Grovyle 22 lowered by 2 stays Grovyle.
  - `test_devolve_without_pre_evolution_keeps_species`: Review Focus 1.
  - `test_level_floor_is_1`.
  - `test_raise_party_lowers_text_and_reports_devolutions`: a fixture `.party` text gets the right `Level:` line and species line, and the report tuple lists the devolution.
- [ ] **Step 2:** Run `-k "RaiseParty or TwoPlayers"`. Expected: the new tests fail.
- [ ] **Step 3:** Implement `devolver` and pass `devolve` through `share_run`'s `fight`, through `repo_inputs` (as `'devolve'`) and through `apply_round`.
- [ ] **Step 4:** Run the whole suite. Expected: it passes.
- [ ] **Step 5:** Commit: `Devolve trainer and wild Pokemon when the curve lowers them (#N)`.

### Task 5: Rewrite unlearnable set moves automatically

**Files:**
- Modify: `tools/rebalance/rebalance.py` (beside `unlearnable_set_moves`, ~line 451)
- Test: `tools/rebalance/test_rebalance.py` (`MoveLegality`)

**Interfaces:**
- Consumes: `learnable_moves(gd, info, move_lists, species, level)` and `power.py`'s scoring.
- Produces:
  - `replacement_move(gd, info, move_lists, species, level, replaced, kept) -> str`, which applies #131/#160's rule:
    - the strongest legal attack at `level`, scored by `power.move_power` on the stat it uses;
    - when `kept` has no attack of `replaced`'s type and the species has one, a move of that type;
    - when the set would lose its STAB, a same-type move;
    - at level 30 or below, the best same-type level-up move ahead of a TM or egg move;
    - never a recharge, self-KO or two-turn move;
  - `rewrite_unlearnable(text, gd, info, move_lists) -> (text, [(team, species, old, new)])`, which rewrites each unlearnable set move in a `.party` text.

- [ ] **Step 1: Write the failing tests:**
  - `test_replacement_keeps_the_replaced_type` (#160's Madeline Camerupt case: Earth Power at 38);
  - `test_replacement_restores_stab`;
  - `test_replacement_prefers_level_up_at_30_or_below` (Roxanne's Geodude gets Bulldoze);
  - `test_rewrite_unlearnable_reports_each_change`.
- [ ] **Step 2:** Run `-k MoveLegality`. Expected: the new tests fail.
- [ ] **Step 3:** Implement both functions.
- [ ] **Step 4:** Run the whole suite. Expected: it passes, and on today's data `rewrite_unlearnable` changes nothing (the allowlist is empty since #160).
- [ ] **Step 5:** Commit: `Rewrite set moves a lowered Pokemon can no longer learn (#N)`.

### Task 6: Report the two players and the outliers, and add explorer sliders

**Files:**
- Modify: `tools/rebalance/rebalance.py`: `analyze`, `write_report`, `curve_snapshot`/`load_snapshot` and `print_curve`
- Modify: `tools/rebalance/explorer/app.js` (Targets group) and `explorer/model.js` (`FILES` gains `forced_trainers.json`)
- Test: `tools/rebalance/test_rebalance.py` (`Analysis`)

**Interfaces:**
- Produces:
  - `OUTLIER_SKIP = 25`;
  - report section `## Two players`, a table per staged boss: `boss | ace | full lead | % | skip lead | % | flag`, where the flag is `outlier` when `skip %` < −25.
- The explorer gets sliders `full_margin` (0–20%), `skip_margin` (0–30%) and `lower` (a checkbox), with help text from the spec.

- [ ] **Step 1: Write the failing tests:**
  - `test_report_has_two_players_section`;
  - `test_outlier_flag_at_25_percent`.
- [ ] **Step 2:** Run `-k Analysis`. Expected: they fail.
- [ ] **Step 3:** Implement it. Port `tools/forced_trainers/prototype/model/scenarios.py`'s table into `write_report`.
- [ ] **Step 4:** Run `python3 tools/rebalance/rebalance.py`, then the suite. Expected: they pass, and `output/report.md` gains the section, with Tabitha at Mt Chimney flagged at about −32%.
- [ ] **Step 5:** Commit `output/` with it: `Report the skip-everything player and its outliers (#N)`.

### Task 7: The solo walls report

**Files:**
- Create: `tools/rebalance/solo.py`, ported from `prototype/model/solo.py` and `grind.py`
- Modify: `tools/rebalance/rebalance.py` (`analyze` and `write_report`: section `## Solo walls`), `explorer/model.js` `FILES` (`solo.py`)
- Delete: `tools/forced_trainers/prototype/`
- Test: `tools/rebalance/test_rebalance.py` (new class `Solo`)

**Interfaces:**
- Consumes: `matchup.stand_in`, `matchup.open_tms`, `power.score`, `exp_award` and `Overlevel`.
- Produces:
  - `solo.SOLO_EVS = 85` (per stat) and `solo.GRIND_BUDGET = 50`;
  - `solo.wall_level(gd, species, foes, tm_moves, teachables, evolve, targets, ivs) -> int | None`: the lowest level, up to 100, at which `min(score) >= 1`;
  - `solo.sweep_level(...)`, with the same arguments: the lowest level at which `sum(1/score) <= 1`;
  - `solo.best_wild(gd, wilds, stage_index, surf_index) -> (yield, level, species)`: land tables only before `surf_index`, plus water from it;
  - `solo.grind_kos(gd, scaling, overlevel, start, target, foes, mult=1.2) -> int`;
  - `solo.solo_walls(trainers, gd, stages, rows, wilds, map_tms, teachables, evolve, scaling, overlevel, settings) -> list[dict]`, with keys `boss, starter, lead, wall, sweep, kos, source`.

- [ ] **Step 1: Write the failing tests:**
  - `test_wall_level_on_fixture` and `test_sweep_at_least_wall`;
  - `test_grind_kos_no_penalty_matches_closed_form`: no penalty and a fixture foe give the exp-table count;
  - `test_best_wild_ignores_water_before_surf`;
  - `test_report_has_solo_walls_section`.
- [ ] **Step 2:** Run `-k Solo`. Expected: they fail.
- [ ] **Step 3:** Implement it.
- [ ] **Step 4:** Run the report and the suite. Expected: they pass, and the report's worst wall today needs well over 50 KOs. That's expected: the budget test comes in Task 10.
- [ ] **Step 5:** Commit: `Report each starter's solo walls and their grind (#N)`. Open PR 1: tools and model, with no game change.

## PR 2: Exp formula and the new curve

### Task 8: Sweep the penalty against the budget

**Files:**
- Modify: `tools/rebalance/rebalance.py` (new subcommand `tune` in `SUBCOMMANDS`)
- Test: `tools/rebalance/test_rebalance.py` (`Solo`)

**Interfaces:**
- Produces: `tune_penalty(inputs, knobs, cutoffs, widths, floors) -> list[dict]`. Each candidate is run through `explore_run` with flat exp (`scaled_exp: False`), both margins and `lower`. Its result is the max fight-everyone solo `kos` and the full lead at Wallace. `tune` prints the **strictest** candidate whose max `kos <= 50` (the lowest floor, then the lowest cutoff) and its table.

- [ ] **Step 1:** Write `test_tune_picks_the_strictest_passing_candidate` on a fixture with a stubbed `solo_walls`.
- [ ] **Step 2:** Run it. Expected: it fails.
- [ ] **Step 3:** Implement it.
- [ ] **Step 4:** Run `python3 tools/rebalance/rebalance.py tune` over cutoffs 20–40 (step 5), widths 4, 6 and 8, and floors 20–40 (step 5). Record the chosen values and the table in the PR description. If no candidate passes, stop and report to the owner with the closest candidates, since that needs a decision.
- [ ] **Step 5:** Commit: `Add the penalty sweep against the solo grind budget (#N)`.

### Task 9: Flip the exp configs and fix the C tests

**Files:**
- Modify: `include/config/battle.h` (lines 18–26: values and comments)
- Modify: `test/battle/exp.c`, `test/battle/hold_effect/exp_share.c` and `test/battle/move_effect/embargo.c`, as needed
- Test: `tools/rebalance/test_rebalance.py` (`Exp`)

- [ ] **Step 1:** Write `Exp.test_early_exp_before_the_first_rival`: a level-5 Medium Slow starter reaches 7 in at most 8 Route 101 KOs under the game's configs. That's the #189 check, now under flat exp.
- [ ] **Step 2:** Set `B_SCALED_EXP GEN_6`, `B_SCALED_EXP_STEEP FALSE`, and the cutoff, width and floor from Task 8. Each comment cites `(#N)`. Keep `B_EXP_OVERLEVEL_MIN_LEVEL 17` unless Step 1 fails or Task 8 shows the next value down also passes the test; then set the lowest value that passes.
- [ ] **Step 3:** Run `.claude/build.sh <worktree> check`. For each failing test:
  - if it pins scaled-exp behaviour, add `WITH_CONFIG(CONFIG_SCALED_EXP, GEN_LATEST)` (the config's `config_changes.h` name);
  - if it pins a number the defaults produce, recompute it under the flat formula;
  - never loosen an assertion.

  Expected: no failures. `test_scaling_factors_are_the_games`'s `Overlevel` assertion takes the new values.
- [ ] **Step 4:** Run the `tools/rebalance` suite. Expected: everything passes except `RealRepo.test_data_meets_the_curve_settings`, which Task 10 fixes. Don't commit separately: Tasks 9 and 10 land together.

### Task 10: Apply the new curve

**Files:**
- Modify: `tools/rebalance/curve_settings.json`: add `"full_margin": 10`, `"skip_margin": 15`, `"lower": true`, `"boss_ref": "ace"`; drop `"margin"`
- Modify: `tools/rebalance/rebalance.py`: `apply_round`, `apply_plan` and `nonlevel_evolve_party`
- Regenerated: `src/data/trainers.party`, `src/data/battle_partners.party`, `src/data/wild_encounters.json`, `tools/area_archetypes/level_offsets.json` and `tools/rebalance/output/*`
- Test: `tools/rebalance/test_rebalance.py` (`RealRepo`, `RaiseParty`)

- [ ] **Step 1: Write the failing tests:**
  - `RealRepo.test_solo_walls_fit_the_grind_budget`: every fight-everyone solo `kos <= solo.GRIND_BUDGET`, with the 50-KO budget;
  - `RealRepo.test_both_players_meet_the_margins`: each staged boss, other than the bosses `OUTLIERS` lists (a dict in `rebalance.py`, filled by Step 5), has its full lead at least 10% over and its skip lead (when fought) at most 15% under;
  - `RaiseParty.test_apply_twice_changes_nothing` (Review Focus 3), on the fixture repo;
  - `RaiseParty.test_rival_variants_share_levels_after_lowering` (Review Focus 4).
- [ ] **Step 2:** Make `nonlevel_evolve_party` skip a Pokémon that this round devolved, and have `apply_round` call `rewrite_unlearnable` after `raise_party` and print its changes.
- [ ] **Step 3:** Run `python3 tools/rebalance/rebalance.py apply`, then `python3 tools/rebalance/rebalance.py`.
- [ ] **Step 4:** Hand-review:
  - `git diff --stat src/data`;
  - the printed devolutions and move rewrites (every rewrite is legal and keeps #160's rule);
  - the default-moveset flags `rebalance.py` raises, each hand-written by the same rule (`replacement_move`).
- [ ] **Step 5:** Read the report's `## Two players` outliers. For each, either smooth it by lowering that boss's team (the rule stays the curve's: add it to `OUTLIERS` with the decided ace) or accept it. Ask the owner about each outlier. Their calls go into `OUTLIERS` and Task 12's `findings.md` section.
- [ ] **Step 6:** Run the `tools/rebalance`, `tools/area_archetypes` and `tools/forced_trainers` suites, then `.claude/build.sh <worktree> check`, then `rom` and `release`. Expected: everything passes, with no new warnings.
- [ ] **Step 7:** Commit Tasks 9 and 10 together: `Flatten the exp formula and apply the two-player curve (#N)`. Open PR 2.

### Task 11: In-game playtest plan

**Files:**
- Create: `docs/fork/playtests/balance-rework.md`

- [ ] **Step 1:** Write the plan for the debug ROM. Each check gives a debug-menu setup (give Pokémon, set level, warp, set flags) and the expected result:
  1. Treecko alone at its Flannery wall level from the report wins with heals.
  2. Mudkip alone at the fight-everyone lead before the Route 119 rival, plus the report's KOs on the named wild species, gets past it.
  3. The spread at Roxanne, Norman and Juan, at the modelled skip and full leads.
  4. Each uncertain forced trainer from `tools/forced_trainers/README.md`.
- [ ] **Step 2:** Commit it with PR 2: `Write the balance rework playtest plan (#N)`.

## PR 3: Docs

### Task 12: Docs

**Files:**
- Modify: `docs/fork/balance.md` (rewrite the exp formula and level curve bullets; earlier decisions stay, marked as replaced by #N)
- Modify: `tools/rebalance/output/findings.md` (new section 18: the evidence tables, the decisions, the tuned penalty and the outlier calls)
- Modify: `tools/rebalance/README.md` (two players, `lower`, `tune`, `solo.py`)
- Modify: `CLAUDE.md`:
  - the index line for the exp formula and curve;
  - the Balance rule: after a data change, `apply` may lower levels and rewrite moves, so review its printed changes;
  - mention `tools/forced_trainers`.

- [ ] **Step 1:** Write them. Grep for stale mentions of steep scaling (`B_SCALED_EXP_STEEP`, "level^3.5") in `docs/` and `CLAUDE.md`, and fix each one.
- [ ] **Step 2:** Commit: `Document the two-player curve and flat exp (#N)`. Open PR 3.
