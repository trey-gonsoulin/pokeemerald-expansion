# Balance rework: a curve bracketed by trainers fought

Date: 2026-11-13. Status: approved in conversation (parts 1-3), awaiting the owner's review of this written spec.

## Why

A single-Pokémon run can't finish the game in practice. The one-on-one model (`power.score` with the type chart; a solo starter with its default moves, the open TMs and full EVs) puts a solo starter's worst walls 10-25 levels over today's curve from Wattson on, and the Elite Four and Wallace at about 95 to over 100. The over-level penalty (#154, #189) then makes closing those gaps cost 1,000-4,000 wild KOs. Today's curve is also tuned to one player only, the full clear, so nothing models a player who skips trainers.

## Goals

The owner's targets, as decided in conversation:

1. **One curve for everyone**, bracketed by how many trainers you fight, in classic RPG fashion:
   - **Skip every skippable trainer:** your lead sits about **15% under** each boss's ace (nearly unwinnable).
   - **Fight every trainer:** your lead sits about **10% over** each boss's ace (pretty easy).
2. **Lower the bosses** to fit, rather than pushing the full clear toward 100: a full clear still reaches Wallace in the high 80s, leaving room under 100 for the post-game rematch ladders and Steven.
3. **Solo grind budget:** a solo starter that fights every trainer gets past each of its walls with at most **50 KOs** of grinding (about half an hour).
4. **Exp formula:** flat (the Gen 6 formula, no level scaling), **1.5x trainer exp off**, and a **softened over-level penalty** (kept, so the full clear doesn't snowball).

The standing rules still hold: balance with the Exp. Share on, mainly through opponent levels, never with a level cap; a rival level change goes on all six teams of that fight.

## The evidence behind the choices

Today's data, modelled with both players (Exp. Share lead; full clear vs. forced trainers only):

| Boss (ace) | Fight everyone | Skip everything |
|---|---|---|
| Roxanne (16) | 16 (+0%) | 13 (-19%) |
| Wattson (26) | 26 (+0%) | 23 (-12%) |
| Tabitha, Mt Chimney (38) | 39 (+3%) | 26 (-32%) |
| Norman (41) | 43 (+5%) | 36 (-12%) |
| Winona (57) | 57 (+0%) | 46 (-19%) |
| Juan (76) | 76 (+0%) | 65 (-14%) |
| Wallace (86) | 84 (-2%) | 75 (-13%) |

The two ends sit 12-20 points apart, and the targets need 25 (about 23% of the full-clear level). Steep scaled exp (#154) is what keeps them close: an under-levelled Pokémon gets much more exp per KO, so the skip-everything player catches up. The 1.5x and a uniform raise of every regular trainer (+10% or +20%) widen the gap only a few points and lift the whole curve. Flat exp with a softened penalty (trial values: cutoff 30%, width 6, floor 30%) gives full-clear / skip-all leads of Roxanne 18/13, Wattson 28/22, Norman 46/32, Winona 62/41, Juan 83/58 and Wallace 89/67 (a 25% gap): the boss rule below then puts Wallace's ace near 81.

## Design

### 1. Forced trainers (new data and tool)

- `tools/forced_trainers/` (standard library): the grid search that classifies every story-stage regular trainer as FORCED, AVOIDABLE or UNCERTAIN.
  - Walkability comes from each layout's `map.bin` collision bits.
  - Sight lines cover every facing a trainer's movement type allows, stopped by walls, elevation and objects. A turning trainer is skippable by timing unless one tile is seen in every facing.
  - It searches for a path from each story area's entry to its exit (or to the leader) per stage, with the HMs available by then: Cut from Brawly, the bike from Wattson, Rock Smash from Flannery, Strength from Norman, Surf from Winona, Waterfall at the Elite Four.
  - Script-forced battles are classified by hand, with their reasons.
  - A README documents the method, its limits and the in-game checks.
- It writes `tools/rebalance/forced_trainers.json`: per trainer, its stage, map, class and reason; the choose-one groups (`one_of`); and the bosses, with `required: false` for the two optional rival fights (Rustboro and Lilycove, both YES/NO).
- First results: 46 forced, 388 avoidable and 35 uncertain of 469 regular trainers. The choose-one groups are Petalburg Gym (3 of 7, one per room), Weather Institute 1F (1 of 2) and Victory Road B1F (1 of 2).
- Uncertain trainers count as skippable, apart from one pick per choose-one group. They stay flagged for in-game checks: the Mauville and Lavaridge gyms, the patrolling trainers, Fortree's rotating gates and Mossdeep's spin tiles.

### 2. Two modelled players in `tools/rebalance`

- **Fight everyone:** today's full-clear model, covering every story trainer, both optional rivals, and the same wild battles, catches and walking.
- **Skip everything:** the FORCED trainers, the first member of each choose-one group, and the required bosses only. Wild battles, catches and walking are the same as the full clear.
- New `curve_settings.json` knobs, with matching explorer sliders:
  - `full_margin: 10` and `skip_margin: 15` (percent);
  - the over-level penalty's cutoff, width, floor and minimum level, which the explorer already has.

### 3. Level rules

- **Bosses:** each staged boss's ace becomes the lower of:
  - the fight-everyone lead / 1.10;
  - the skip-everything lead / 0.85.

  The gap is wider than 25 points in the middle of the game, and there the full-clear side wins, so a skip-all run gets harsher still. Bosses keep their other rules:
  - the Elite Four step one level per fight, and Wallace sits above Drake;
  - all six rival variants of a fight share its levels;
  - Steven's Mossdeep partner team follows its foes;
  - a staged boss's team keeps distinct species.
- **Regular trainers:** today's rule is unchanged. Each stage gets one uniform shift (forced and skippable alike), the smallest that leaves its trainers' aces an average of 10% (`trainer_gap`) under the fight-everyone lead when fought.
- **Wild tables:** today's rule is unchanged. Each stage's land average sits 20% (`wild_gap`) under the lead at the stage's start, and water tables count from Winona's stage.
- **Outliers:** the report flags any boss or forced trainer that a skip-everything lead meets more than 25% under its ace (today: Tabitha at Mt Chimney, -32%). Each flag is smoothed by hand or accepted, with the owner's call recorded in `findings.md`.
- **Post-game:** the rematch rounds, the ordinary rematch ladders (`rematch_step`) and Steven at Meteor Falls are regenerated by their existing rules from the new curve, capped at 100.

### 4. Exp formula (game configs, `include/config/battle.h`)

- `B_SCALED_EXP`: `GEN_LATEST` -> `GEN_6` (flat).
- `B_SCALED_EXP_STEEP`: `TRUE` -> `FALSE`. It does nothing without scaling. Its code and its "Exp formula:" tests stay, since they set their configs with `WITH_CONFIG`.
- `B_TRAINER_EXP_MULTIPLIER` stays `GEN_LATEST` (1.5x off).
- `B_EXP_OVERLEVEL_CUTOFF`, `_WIDTH` and `_FLOOR` take the values the solo-budget tuning (section 5) settles on, starting from 30 / 6 / 30. `B_EXP_OVERLEVEL_MIN_LEVEL` (17) is re-derived from the same early-game check (#189: Route 101 Pokémon have to give useful exp before the first rival fight).
- No save-layout change.

### 5. Solo report and the grind budget

- `rebalance.py`'s report gains a "Solo walls" section, ported from this conversation's scratch scripts:
  - per starter and story boss, the starter line alone (its default moves plus the TMs open by then, picked for coverage; IV 15, full EVs spread evenly) against the boss team on `power.score` with the type chart;
  - the level at which it wins each one-on-one (healing between Pokémon), and the level at which it sweeps the team without healing;
  - the grind from the fight-everyone lead to the one-on-one level: the KOs needed against the best wild Pokémon reachable by then (grass before Winona, Surf from Winona, no rods; DexNav can hunt a species), with max friendship and no Lucky Egg;
  - after Norman, the strongest rematch team too, counted in battles.
- The penalty values are tuned until no fight-everyone solo wall needs more than 50 KOs. A unittest pins this, so later curve or penalty changes can't quietly break the budget.
- Tate and Liza is a double battle and the model fights it one-on-one; the report says so.

### 6. `apply` lowers levels as well as raising them

Today `apply` only raises: bosses, regular trainers and wild offsets. The new curve lowers most bosses.

- **Bosses and trainers:** levels move to the target in either direction, from the current data. Hand-written movesets are kept.
- **Devolving:** a Pokémon lowered below its evolved form's evolution level plus `EVOLVE_GRACE` reverts to the pre-evolution that fits. The non-level evolutions (#181) revert by their own threshold the same way. A boss team still never ends up with duplicate species.
- **Moves:** set moves the lowered Pokémon can no longer learn are listed by `test_set_moves_are_learnable`. Each is rewritten by #131/#160's rule: the strongest legal attack at that level, keeping the replaced move's type when the set has no other move of it, and a same-type move where the set lost its STAB. Every flag `rebalance.py` raises on default movesets is hand-written as well.
- **Wild offsets:** these can fall too, through restock's `--levels`.
- `RealRepo.test_data_meets_the_curve_settings` keeps pinning the result. It checks that the data is the curve's fixed point, so the same test covers lowering.

### 7. Rollout

The work goes in four PRs into `emerald-plus`, each green on CI.

1. **Forced-trainer data and the two-player model.** `tools/forced_trainers/`, `forced_trainers.json`, the skip-everything scenario, the boss rule, the outlier and solo reports, and the explorer sliders. No game or data change: the new knobs default to today's behaviour until PR 3.
2. **Exp configs and tests.** The section 4 flips and the test updates: any test that relied on the default configs gets `WITH_CONFIG` or the flat formula's numbers. The full `make check` passes.
3. **The new curve in the data.** `apply` with lowering and the new `curve_settings.json`, the regenerated `trainers.party`, `battle_partners.party` and wild offsets, the moveset rewrites and the regenerated report.
4. **Docs.** `docs/fork/balance.md` rewritten for the formula and curve, a new `findings.md` section with these decisions and numbers, and the `CLAUDE.md` index line and rules updated. Earlier decisions stay recorded, marked as replaced.

The James Petalburg Woods Nincada fix (`worktree-soften-james-nincada`) stays its own small PR.

## Verification

- `python3 -m unittest discover -s tools/rebalance`, plus the new forced-trainer tests: one per classification method, on fixture maps.
- The full `make check`, and both ROMs (`rom`, `release`) with no new warnings.
- The regenerated report shows the targets at every staged boss: fight-everyone at least 10% over, skip-everything at most 15% under, apart from the recorded outliers. It also shows every fight-everyone solo wall within 50 KOs.
- An in-game playtest plan on the debug ROM:
  - a solo starter at three of its walls, set to the modelled level with the debug menu;
  - the spread at Roxanne, Norman and Juan;
  - the uncertain forced trainers (the Mauville and Lavaridge gyms, the patrols, Fortree and Mossdeep).

## Out of scope

- Opt-in difficulty modes or toggles (the owner chose one curve).
- Level caps (a standing rule).
- Restocking wild species (the committed wild species stay vanilla).
- Changes to the AI, boss movesets or evolutions beyond what lowering levels forces.
