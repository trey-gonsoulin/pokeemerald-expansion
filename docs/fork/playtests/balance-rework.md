# Playtest plan: balance rework (#350)

In-game checks for the level curve applied in #350. One tester, one sitting per section. Every number comes from `tools/rebalance/output/report.md` ("Two players" and "Solo walls"); if the data changes, rerun `python3 tools/rebalance/rebalance.py` and update the numbers here. The report models fights one-on-one on `power.score`, so a result a level or two off is noise. A clear miss means the curve or the model is wrong: write down the species, level and moves you used.

## Before you start

Play the debug ROM (plain `make`, `pokeemerald.gba`). In the overworld, hold R and press Start to open the menu (`docs/fork/debug-menu.md`). Menu names below are the main menu's: Utilities, Party, Give X, Trainers, Flags & Vars.

Common setup:

- Flags & Vars: "Toggle All badges" and "Toggle Fly Flags". The menu sets all eight badges at once, so a fight that needs fewer is still run with all eight. Set Flag XYZ and Set Var XYZ cover any story flag a map or event needs.
- Party, "Clear Party", then Give X, "Pokémon (Complex)" for the player's Pokémon. It has steps for species, level, nature, moves, IVs and EVs: use IVs 15 and EVs spread evenly (the model's player). "Pokémon (Basic)" (species and level) is enough where moves don't matter.
- Give X, "Give item XYZ…" for TMs and heal items; "Max Money" for shopping.
- Utilities, "Warp to map warp…" or "Recent warps…" to reach a map. Party, "Heal party" stands in for a Pokémon Centre.
- Trainers: set "Trainer 1" to the boss, then "Try Battle" fights it where you stand, without the walk. Use it for the leader and rival fights below.
- "Toggle Encounter OFF" while you walk, back on to grind.

What the menu can't do:

- It can't set a Pokémon's experience points. A given Pokémon is a fresh level-N with nothing banked towards N+1, and a level reached by grinding has to be ground.
- It can't pick which TMs the model assumed. The report says the moves are the default set plus the TMs open by then "picked for coverage" and doesn't list them. Give the line's default set and a coverage TM or two by your own judgement, and write down what you chose.
- "Edit Pokemon" has no level step: give the Pokémon at the level you want.

## 1. Solo walls

The report's "Solo walls" gives, per starter and boss: lead (the fight-everyone lead), wall (lowest level that wins one-on-one, healing between Pokémon), sweep (lowest that wins without healing) and the KOs needed to grind from the lead to the wall on the named wild species. The budget is 50 KOs. The starter is the only Pokémon that fights, so "healing between Pokémon" can't be tested with a single mon. Give it a spare Pokémon to be sent out as a sacrificial lead if you want to heal between boss Pokémon, or use potions as the heals. For a sweep use no healing at all.

### 1a. Treecko line at Flannery

Report: Flannery 1, ace 32, lead 44, wall 45, sweep 54, 18 KOs, source Pelipper 29. Her team: Numel 27, Slugma 27, Camerupt 29, Torkoal 32.

Setup:

1. Clear Party; give Treecko's line at its form for level 44 (Sceptile) with default moves and a TM or two.
2. Toggle All badges. Warp to `LavaridgeTown`.

Do:

1. Trainers: Trainer 1 Flannery 1, Try Battle, with the level-44 lead. Note the result.
2. Grind 18 KOs on Pelipper 29 (a Pelipper from the wild tables open by Flannery: use the encounters on the maps in `src/data/wild_encounters.json`, with "Encounter OFF" off), or give a fresh level-45 Pokémon instead. Fight again at 45.
3. Give a level-54 one and fight with no heals.

Expected:

- 45 wins with heals.
- 44 is one under the wall, so it may lose.
- 54 sweeps the four without a heal.
- The grind from 44 reaches 45 in about 18 KOs, and the exp isn't wasted at the over-level penalty.

### 1b. Mudkip line before the Route 119 rival

Report: May Route 119 Mudkip, ace 45, lead 62, wall 62, sweep 64, 0 KOs. Source Azumarill 42. Her team: Magcargo 43, Ludicolo 43, Sceptile 45.

Setup: Clear Party; give Swampert at level 62 with default moves and a TM or two. Toggle All badges. Warp to `Route119`.

Do: Trainers: Trainer 1 May Route 119 Mudkip, Try Battle. Repeat with a level-61 Pokémon and a level-64 one with no heals.

Expected: 62 wins with heals (the lead is the wall, so no grinding); 61 loses or only just wins; 64 sweeps. The Azumarill 42 source, if you grind anyway, should give no more than a handful of KOs per level here.

### 1c. Worst walls

Each starter's worst budgeted wall. Same method as 1a, with the fight at the wall and at the lead.

| starter | boss | ace | lead | wall | sweep | KOs and source | boss team |
|---|---|---|---|---|---|---|---|
| Treecko | May Route 110 Treecko | 25 | 28 | 31 | 33 | 49, Plusle 15 | |
| Mudkip | May Route 110 Mudkip | 25 | 28 | 29 | 30 | 15, Plusle 15 | Wingull 23, Slugma 23, Grovyle 25 |
| Torchic | Wallace | 79 | 89 | 92 | - | 49, Aggron 65 (17 battles vs Gabrielle 5) | |

- The Treecko row (49 of 50 KOs) is the one to feel: it should take the budget and no more, and be tolerable as a grind. Warp to `Route110`.
- The Torchic row is the endgame. Run it last, if at all. Its team isn't listed in this plan: read it from `src/data/trainers.party` (`TRAINER_WALLACE`).
- Mudkip's Wallace has no winning level in the model ("unwinnable", an accepted outlier). Fight him with a high-level Mudkip to see how hard it really is.

## 2. The spread at Roxanne, Norman and Juan

The "Two players" table models the Exp. Share lead just before a boss for a player who fights everyone (full) and one who skips every trainer they can (skip).

| boss | ace | full lead | % | skip lead | % |
|---|---|---|---|---|---|
| Roxanne 1 | 15 | 18 | +20% | 13 | -13% |
| Norman 1 | 36 | 45 | +25% | 31 | -14% |
| Juan 1 | 67 | 83 | +24% | 57 | -15% |

Teams:

- Roxanne: Geodude 12, Geodude 12, Nosepass 15.
- Norman: Spinda 32, Vigoroth 32, Linoone 34, Slaking 36.
- Juan: Luvdisc 62, Whiscash 62, Walrein 64, Crawdaunt 64, Kingdra 67.

Setup (per boss and lead):

1. Clear Party. Give the lead's Pokémon at the lead level and two or three others a few levels under it, to stand in for the Exp. Share bench. Use fully evolved forms where the level allows, with default moves.
2. Toggle All badges. Warp to the gym (`RustboroCity_Gym`, `PetalburgCity_Gym`, `SootopolisCity_Gym_1F`), or use Trainers, Try Battle where you stand.

Do: fight the boss from the full lead, then from the skip lead.

Expected:

- Full lead: wins with a comfortable margin, with the lead at about the +20% to +25% over the ace.
- Skip lead: a hard fight, 13% to 15% under the ace. It should be winnable with the team and items, not hopeless. A fight that can't be won at the skip lead with a reasonable team is a finding.
- The skip lead is never above the full lead, and both are within a level or two of the table.

## 3. Uncertain forced trainers

`tools/forced_trainers/README.md` lists what the grid can't settle. Walk each from the entrance to the target, trying to avoid every trainer, and record whether you can. Class and stage per trainer are in `tools/rebalance/forced_trainers.json`. Leave "Trainer See OFF" and "Collision OFF" off, so sight and walls work as in the game. Save at each entrance and reload to retry.

Setup for all: Toggle All badges, then warp to the map below and save.

1. Mauville Gym (`MauvilleCity_Gym`): the beams, switches and warp pads change the route as you move. Walk from the door to Wattson and list the trainers you can't avoid.
2. Lavaridge Gym (`LavaridgeTown_Gym_1F`, `LavaridgeTown_Gym_B1F`): the warp pads change the route. Same check to Flannery.
3. Jasmine on Route 110 (`Route110`; the Cycling Road is closed, no bike): a patroller. Pass her from the south end to the north by timing. Skippable or forced?
4. Sophie and Coby on Route 113 (`Route113`): patrollers. Pass from east to west.
5. Cale on Route 121 (`Route121`): a patroller. Pass from west to east.
6. Aqua grunts 1 and 4 (`AquaHideout_1F`, `AquaHideout_B2F`): patrollers between the entrance and Matt. Reach Matt without fighting either?
7. Magma grunts 4 and 5 (`MagmaHideout_2F_1R`): patrollers between the entrance and Maxie. Same check.
8. Fortree Gym's gates (`FortreeCity_Gym`): Jared, Ashley, Humberto, Darius. The rotating gates aren't modelled. Reach Winona and note which of the four you can skip.
9. Mossdeep Gym's spin tiles (`MossdeepCity_Gym`): Virgil, Blake, Hannah, Samantha, Maura, Sylvia, Nate, Macey, Clifford, Nicholas, Kathleen. The spin tiles and switches aren't modelled. Reach Tate and Liza and note which of the eleven you must fight.

Expected: each result confirms the committed class (UNCERTAIN trainers come out as skippable or forced) or doesn't. A trainer you can skip that the tool calls FORCED, or one you must fight that it calls AVOIDABLE, changes the skip leads in "Two players": report it and fix `tools/forced_trainers/specs.py`.

The choose-one groups (Petalburg Gym's three tiers, Weather Institute 1F's grunts 1 and 4, Victory Road B1F's Samuel and Shannon) are in the model already. A quick walk through each is worth it: exactly one trainer per tier is forced and you pick which.

## Recording results

For each check, note the species, level, moves, whether it won, and for walls the KOs used. A result more than a level or two off the report, a skip lead with no workable route, or a forced-trainer class that turns out wrong goes into #350.
