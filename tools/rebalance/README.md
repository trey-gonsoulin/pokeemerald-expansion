# Rebalance measurements

Measures how far Emerald's difficulty has drifted from vanilla now that the
game runs on the expansion's modern data and the fork's config flips (#113).
It reads the repo's own headers twice:

- **modern**: the build as configured (`include/config/*.h` as committed);
- **vanilla**: the same configs with the data and formula switches set to
  `GEN_3` (`VANILLA_OVERRIDES` in `gamedata.py`): Gen 3 learnsets, stats,
  types, exp yields, move data and types, the type-based physical/special
  rule, the Gen 3 type chart, the Gen 3 exp formula (/7, 1.5x for trainers,
  split, no scaling), IV-based Hidden Power power, and Gen 3 prices,
  healing and sell value. Vanilla wild
  Pokemon come from the pre-restock snapshot
  `tools/area_archetypes/output/wild_encounters.vanilla.json`.

```sh
python3 tools/rebalance/rebalance.py                  # writes tools/rebalance/output/
python3 tools/rebalance/rebalance.py explore          # the curve explorer (below)
python3 tools/rebalance/rebalance.py tune             # the over-level penalty against the solo grind budget
python3 -m unittest discover -s tools/rebalance       # tests
```

Standard library only; nothing in `src/` or `data/` is written. The
preprocessor helpers and the species_info macro expansion are imported from
`tools/area_archetypes/restock.py` (`parse_defines`, `active_lines`,
`species_entries`). The tests run on the small fake repo in `testdata/repo/`,
plus checks on the real repo: every trainer species and move in
`src/data/trainers.party` resolves under both regimes, every stage boss
exists, every map with trainers, TMs or wild Pokemon is in a stage or
in `unstaged`, and each Trick House puzzle sits after its badge gate.

## Outputs

- [`output/findings.md`](output/findings.md): the written-up findings and
  the proposed balance changes (#113). Hand-written from `report.md`, so
  update it by hand in the same commit whenever `report.md` changes.
- `output/report.md`: every table the findings use. Committed as a
  snapshot; rerun after upstream syncs or balance edits. CI reruns the
  script and fails if the committed `report.md` differs from its output.
- `output/trainer_mons.csv`: every trainer Pokemon with its vanilla and
  modern default moveset and its flags (gitignored).
- `output/summary.json`: the report's numbers, for scripts (gitignored).
- `output/curve_data.json`: the Exp. Share curve's inputs for the curve
  explorer (below). Committed, and CI checks it for drift like
  `report.md`.

## Curve explorer (#151)

```sh
python3 tools/rebalance/rebalance.py explore     # serves http://127.0.0.1:8151/rebalance/explorer/
python3 tools/rebalance/rebalance.py curve '{"full_margin": 10, "skip_margin": 15}'   # the same run as text
```

A page with sliders for the Exp. Share curve's knobs (`EXPLORER_KNOBS`)
and a chart of the levels before each story boss: the boss aces (with the
knobs and today's), the party (a reference level, its lowest and highest
member), the stage's route trainers' mean ace and its wild land average.
It runs this tool's own Python in the browser through Pyodide (loaded from
the jsDelivr CDN, so it needs internet), in a Web Worker. Nothing is parsed
there: `curve_snapshot` writes the parsed inputs to
`output/curve_data.json` (the story stages and trainers, the rematch ladders and theirs, exp yields, level
evolutions, each team Pokemon's devolve line, the scaling table, both regimes' land slots, the config
defines and the forced trainers), and `load_snapshot` rebuilds them for
`share_run`. A test checks that the committed snapshot gives the curve the
repo's own data gives. `explore_run` maps the knobs to `share_run`;
`curve` runs it from the command line on the settings JSON the page shows
(the knobs changed from the defaults, also kept in the page's URL).

The knobs:
- **Play style:** `ko_takers`, how many members rotate the KOs (1: one
  lead and five on the Exp. Share bench, the report's share6; 6: the whole
  team in turn), the share of route trainers fought, catches, wild KOs and
  steps per stage, and the affection bracket.
- **Exp formula:** the 1.5x trainer exp, level-scaled exp
  (`B_SCALED_EXP`; the fork runs Gen 6's flat exp since #350), and three
  options:
  - `scaling_power`: the scaling table is `floor(i^p / 4)`. It's 2.5 in
    upstream and 3.5 under `B_SCALED_EXP_STEEP` (#154, off since #350:
    it does nothing under flat exp).
  - `overlevel_cutoff`, `overlevel_width` and `overlevel_floor`: the
    over-level penalty (`Overlevel`). Above the foe's level, the exp falls
    on a logistic curve: fastest at the cutoff, over the width, then
    levelling out at the floor (percent of the exp, at least 1 exp). The
    cutoff and the width are in levels, or in percent of the foe's level
    with `overlevel_unit`. Without a width, the exp drops to the floor
    straight past the cutoff. In percent, `overlevel_min_level` counts a
    foe below that level as that level for the cutoff and width, so an
    early foe's cutoff is still a few levels. The fork's
    `B_EXP_OVERLEVEL_PENALTY` (#154, #189) is 30%, 8% and 40% since #350
    (`tune`, below; #189's were 15%, 4% and 10%), with a minimum level of
    17 (`B_EXP_OVERLEVEL_MIN_LEVEL`).
  - `share_fraction`: the Exp. Share bench's share, the game's half; not a
    game option.

  The defaults (`explorer_defaults`) are the game's configs.
- **Targets:** the party levels the rules measure against (`REFERENCES`:
  the bench, the KO-takers' mean, the party's mean, and `ace`, its highest
  member, which is the lead): `boss_ref` for the boss rules and `gap_ref`
  for the two gaps (#350, both the bench by default). Then #150's
  single-player boss margin (off: today's levels; the data now uses the
  two players' margins, below) with the Elite Four spacing
  (`LEAGUE_STEPS`), #150's route-trainer gap (`TRAINER_GAP`: each stage's
  ordinary trainers raised until their aces average that far below the
  gap reference when fought) and wild gap (the stage's land average that
  far below it at the stage's start, over the vanilla tables), and whether
  raised Pokemon evolve (`restock.SpeciesInfo.evolve`, `EVOLVE_GRACE`
  levels past a level evolution; `EVOLVE_EXEMPT`'s teams never do).
  `gap_unit` puts the margin and both gaps in percent of the reference
  instead of levels.
- **Two players (#350):** `full_margin` and `skip_margin` (percent of the
  ace, on and off together) replace the boss margin. Each staged boss's
  ace sits `full_margin` under the fight-everyone player's boss reference,
  or `skip_margin` over the skip-everything player's if that is lower. The
  skip player fights only `forced_trainers.json`'s FORCED trainers, the
  first of each choose-one group and the required bosses
  (`tools/forced_trainers` writes it), with the same walking, catches and
  wild battles. A boss it skips (the optional rivals) and the post-game
  take the full rule alone. `lower` lets the boss rules move levels down
  too (bosses, rival variants, the partner and the post-game) and the wild
  offsets fall to the vanilla tables at most, devolving lowered Pokemon to
  the form that fits (`devolver`); the stage's trainer shift only ever
  raises.
  - Why `gap_ref` is separate: the lead runs far ahead of the bench under
    the Exp. Share. With the gaps on the lead, route trainers 10% under it
    pay it more exp, which raises the next stage's trainers again, until
    it reaches 100 by Tabitha at Mossdeep. So the bosses measure on the
    lead (`boss_ref: "ace"`) and the gaps on the bench (`findings.md`
    section 18).
- **The post-game (#139):** after Wallace the chart goes on through the
  rematch rounds and Steven (`rematch_ladders` reads `gRematchTable` through
  `G.parse_rematches`):
  - **Rounds:** the gym leaders' ladders and Wally's (`POSTGAME_LADDERS`)
    are fought in rounds, `Rematch 2` being every ladder's first rematch.
    With a boss rule, each round's teams go to one ace, the rule's at the
    round's start, and at least 1 over their ladder's previous fight. Under
    #350's two players that is the fight-everyone rule alone (the lead /
    1.10), and with `lower` a round can go down; under #150's it was the
    margin over the reference.
  - **Steven:** `POSTGAME_FINAL` follows, at the same rule and at least
    `POSTGAME_FINAL_STEP` (3) over the last round's highest ace (94 since
    #350, 97 before). All of it is capped at 100.
  - **Ordinary trainers:** `rematch_step` raises their ladders
    (`rematch_raises`). Rematches unlock after Norman (`REMATCH_UNLOCK`, the
    game's `OW_REMATCH_BADGE_COUNT`) at any tier, so a ladder is levelled
    for the earliest stage it can be fought: the later of the first fight's
    stage and the one after Norman's. Its base is the higher of the first
    fight's ace and the route trainer gap below that stage's starting
    reference. Rematch n then sits `rematch_step` n times over the base
    (levels, or percent compounding, `gap_unit`), and at least 1 over the
    rematch before it.
  - Neither kind gives the story stages any exp: the story curve doesn't
    count rematches.

### Applying a curve (#150, #350)

```sh
python3 tools/rebalance/rebalance.py apply    # writes the data for curve_settings.json
python3 tools/rebalance/rebalance.py          # then refresh report.md and curve_data.json
```

`curve_settings.json` holds the explorer settings the data is built for
(the owner's choice: #350's two players, `findings.md` section 18, which
replaced section 8's). `apply` runs `explore_run` on the repo's own data
with them, through `apply_plan`, and writes:
- the level changes into `src/data/trainers.party`, for the staged bosses,
  their rival variants (to the boss's ace, `variant_raises`) and every
  regular trainer of each stage. `raise_party` moves every Pokemon of a
  team by the same amount, capped at 100; with `lower` (#350) a boss team
  can go down too, and a lowered Pokemon below its evolved form's level
  plus `EVOLVE_GRACE` devolves (`devolver`: the form that fits, else the
  nearest one the team doesn't have, else it stays). A raised Pokemon
  evolves through `evolve_team`, as the model's fights do: never on an
  `EVOLVE_EXEMPT` team,
  and on a boss's team (bosses and variants) not into a species the team
  already has;
- `PARTNER_FIGHTS`' partners (Steven at Mossdeep, to his foes' highest ace,
  up or down; partners don't evolve) into `src/data/battle_partners.party`;
- each stage's wild offset over the vanilla levels, for every table of its
  maps (a water table counts from `SURF_STAGE`), into
  `tools/area_archetypes/level_offsets.json`, through `restock --write`.
  Restock runs first, so a refused restock leaves nothing half written;
- the post-game rounds' teams and Steven (as bosses: no duplicate
  evolutions), and the ordinary trainers' rematch ladders (#139), into
  `src/data/trainers.party`;
- on every boss and rival team (`boss_teams`, raised or not), the
  evolutions that aren't by level (#181, `nonlevel_evolve_party`): a stone or
  other item, a trade, friendship, a map section, beauty or a move, once the
  Pokemon is `EVOLVE_GRACE` levels past the evolved form's `min_level`
  (`restock.SpeciesInfo.nonlevel_evolution`; `NONLEVEL_PREFER` picks a split's
  target). The highest level goes first and none evolves into a species the
  team has, so of two copies the ace evolves. A Pokemon the round devolved,
  or kept from devolving, is skipped. The report's "Evolutions that
  aren't by level" section lists the ones held back and the other trainers';
- in both `.party` files, a replacement for every set move a lowered
  Pokemon can no longer learn (#350, `rewrite_unlearnable`): #160's rule
  in `replacement_move`, the strongest legal attack, keeping the replaced
  move's type or the set's STAB, the best same-type level-up move at
  `LEVEL_UP_REPLACEMENT_LEVEL` (30) or below, never an HM, recharge,
  two-turn or self-KO move, and ties to STAB, then level up, then no
  drawback, then the name (`docs/fork/balance.md`).

`apply` prints every change: the teams moved, each devolution, each team
Pokemon kept from devolving, each #181 evolution and each move rewrite
("kept, fix by hand" when no legal attack qualifies). Review them before
committing. On data it already wrote it asks for nothing, which
`RealRepo.test_data_meets_the_curve_settings` checks. A round that evolves boss
Pokemon raises the exp curve, so `apply` goes again from the data it wrote
until a round evolves none (`APPLY_ROUNDS`). After a change to
`trainers.party`, the wild tables or the exp formula, rerun `apply` and
`rebalance.py` (or change the settings and do the same).
`apply` doesn't touch trainers outside the stages and the rematch table.
Hand-written movesets don't move with the levels: after a level change,
check the report's default-moveset flags and hand-write what they flag (#139
hand-wrote the flagged rematch sets, #159 the story ones, #161 the off-stage
ones, #350 Shelly's Weather Institute Mightyena). The tests check that every
set move is still learnable (#145).

The page's files are `explorer/index.html`, `app.js` (the controls and the
Chart.js chart), `worker.js` and `model.js` (the module list and the Python
bootstrap). The repo's `.gitignore` ignores `*.js`, so add new ones with
`git add -f`.

### Tuning the over-level penalty (#350)

```sh
python3 tools/rebalance/rebalance.py tune    # cutoffs 20-40 by 5, widths 4 6 8, floors 20-40 by 5
```

`tune` runs each penalty (`tune_penalty`) through `explore_run` with
`curve_settings.json` and `TUNE_KNOBS`: flat exp, the two players' margins
and `lower`, with `boss_ref` the lead and `gap_ref` the bench (see "Two
players" above for why the gaps stay on the bench). It then fights each
starter's solo walls
(`solo.py`) on that run's own curve: its boss teams, moved, evolved and
devolved as the run fights them, its wild tables and its exp. It prints the
table and the strictest candidate (the lowest floor, then cutoff, then width)
whose walls all fit `solo.GRIND_BUDGET`; an unwinnable wall fails the budget.
The budget leaves out the optional rival fights (`required: false` in
`forced_trainers.json`) and the walls the owner accepted (`solo.SOLO_OUTLIERS`:
Wallace for a solo Mudkip); the report still lists them, marked.
When none passes, it prints the closest ones and what fails. The sweep
behind the game's 30 / 8 / 40 is in `findings.md` section 18, and
`RealRepo.test_solo_walls_fit_the_grind_budget` pins the budget on the
committed data.

## What it measures

- **Census**: trainers, Pokemon, set vs default moves, AI flags, the AI of
  every story boss.
- **Level curve**: the party's level just before each story boss under five
  party models (`PARTY_MODELS`) and three scenarios (`SCENARIOS`: every
  trainer on the stage maps, every other one, and every one plus 20 average
  wild battles per stage). The exp formula is `Cmd_getexp` +
  `ApplyExperienceMultipliers` read from the configs (`exp_award`), checked
  against the expected values in `test/battle/exp.c`. It leaves out the
  Lucky Egg, traded, affection (`B_AFFECTION_MECHANICS` is TRUE, so a
  4-heart Pokemon gets 1.2x more in game) and unevolved bonuses.
- **Exp. Share curve** (#127): the share6 party on modern data before
  each story boss (`share_curve`), with `B_TRAINER_EXP_MULTIPLIER` at
  GEN_LATEST and at GEN_6 (`TRAINER_EXP`; `Cmd_getexp` gives the 1.5x for
  GEN_6 and earlier), on a full and a half clear, in three affection
  brackets (`AFFECTION`): none, modelled friendship, and 4 hearts from the
  start. Affection is `ApplyExperienceMultipliers`' 4915/4096 at 4+ hearts
  (friendship 220). The friendship model starts at 50
  (`P_UPDATED_FRIENDSHIP`) and adds `sFriendshipEventModifiers`' level-up
  and league-battle gains plus `WALK_STEPS_PER_STAGE` of walking (one +1 per
  128 steps, half the time). Each stage adds `CATCHES_PER_STAGE` catches
  (`B_EXP_CATCH`: a catch gives the exp of a KO) at its land-table average.
  The Lucky Egg, traded and unevolved bonuses (`B_UNEVOLVED_EXP_MULTIPLIER`
  is on, but only for a Pokemon kept from evolving) stay out. From that
  curve it proposes boss raises: every Pokemon of a story boss's team goes
  up by the same amount so its ace sits `TARGET_MARGIN` above the
  full-clear bench (modelled friendship), in story order, never lowered,
  and it reruns the curve and the default-moveset flags of the raised
  Pokemon with them. The model plays one rival team per fight; the
  others (`rival_variants` in `story_stages.json`) get the raise that
  brings their ace to the same level. A sensitivity table varies the
  catches, the walking, the stage trainers' levels and the unevolved 1.2x
  (the whole party, an upper bound).
- **Two players** (#350): per staged boss on today's levels
  (`curve_settings.json`'s knobs with the level rules off), the ace and the
  Exp. Share lead of a player who fights everyone and of one who skips
  everything (`two_players`), each in percent of the ace, flagging an
  outlier where the skip lead is more than `OUTLIER_SKIP` (25%) under; then
  the forced trainers the skip lead meets that far under. `OUTLIERS` lists
  the teams the owner accepted outside the rules, each with its side
  (`skip`, `full` or `forced`) and its numbers: the last three Elite Four
  fights and Wallace, which `LEAGUE_STEPS` lifts over the skip rule, and
  the forced Edwardo and Flint. The report marks them "accepted", and
  `RealRepo.test_both_players_meet_the_margins` exempts each on its side
  only and fails on a stale entry.
- **Solo walls** (#350, `solo.py`): per starter and staged boss, the
  starter line alone (its default moves plus the TMs open by then, picked
  for coverage; IV 15, full EVs spread evenly) against the boss team on
  `power.score` with the type chart. The wall is the lowest level that wins
  each one-on-one (healing between), the sweep the lowest that beats the
  team without healing, and the KOs the grind from the fight-everyone lead
  to the wall against the reachable wild Pokemon that takes the fewest
  (grass before Winona, Surf from her, no rods; max friendship, no Lucky
  Egg) under the game's exp configs; after Norman, also the battles against
  the strongest open rematch team. `solo.GRIND_BUDGET` (50 KOs) leaves out
  the optional rival fights (`required: false` in `forced_trainers.json`)
  and `solo.SOLO_OUTLIERS` (Wallace for a solo Mudkip, unwinnable by 100),
  both the owner's calls; the report marks them and leaves them out of each
  starter's worst wall. Tate and Liza's double battle is fought one-on-one.
- **Default movesets**: `GiveBoxMonInitialMoveset` (the last four distinct
  level-up moves, level-0 evolution moves skipped) under both learnsets, for
  every trainer Pokemon without set moves. Fixed-damage moves (Seismic
  Toss, Night Shade, Sonic Boom, Super Fang, OHKO moves, Counter:
  `FIXED_DAMAGE_EFFECTS` in `gamedata.py`) count as damaging moves but never
  as STAB, since their damage ignores the type bonus. Hidden Power takes its
  type, and in vanilla its power, from the Pokemon's IVs (trainers.party's
  `IVs:` line, trainerproc's default of 31). Flags:
  - `no_attack`: the modern set has no damaging move; `lost_all_attacks`
    when the vanilla set had one;
  - `one_attack`: one damaging move left where vanilla had two or more;
  - `lost_stab`: vanilla had a STAB damaging move, modern has none;
  - `above_band`: a modern damaging move of 70+ power that the Gen 3
    learnset teaches 10+ levels after the Pokemon's level;
  - `new_strong`: a modern damaging move of 70+ power that the Gen 3
    learnset doesn't teach at all.
- **Hand-written movesets**: every damaging set move whose type, category,
  power or accuracy changed. A category flip compares the base stat it uses
  now with the one it used in Gen 3 (weaker / similar / stronger at 15%).
  Fixed-damage moves use no attacking stat, so they are left out of the
  flips. Hidden Power is resolved from each Pokemon's IVs, as above.
- **Learnable set moves** (#145, a test, not a report section):
  `RealRepo.test_set_moves_are_learnable` fails on a set move in
  `trainers.party` or `battle_partners.party` that neither the species nor a
  pre-evolution learns as a level-up move at or below the slot's level, an
  evolution move (level 0), a teachable or an egg move (`learnable_moves`).
  The build generates the teachables header (gitignored), so
  `gamedata.move_lists` runs the same `tools/learnset_helpers` functions and
  reads their output instead of a header an older build left. `move_allowlist.json`
  lists any set move allowed to break the rule as trainer, species and move;
  the test also fails on an entry that no longer breaks it. It has been empty
  since #160 swapped the upstream Gen 3 moves it listed.
- **Split fit**: for the species in `SPLIT_WATCH`, the better attacking stat
  against the Gen 3 category of each STAB type and the split of its modern
  level-up STAB moves.
- **Boss type matchups**: per boss Pokemon, retypings, changed defensive
  multipliers and changed best offensive multipliers against single types.
- **Combat power estimate**: each story boss Pokemon's effective level
  (below), the team's strongest and mean against the Exp. Share bench, and
  the boss Pokemon `POWER_OUTLIER` (10%) or more off their level.
- **Matchup-relative strength**: each story boss against a stand-in for
  the player's team, per starter, with types (below).
- **TMs by stage**: the first story stage where each TM sits on a map
  (item ball, hidden item, mart list, script, or reward: a Trick House
  puzzle's prize, which the entrance and end rooms hand out, filed under
  that puzzle's map). Other script gates aren't modelled, so a script
  source can open later than its map's stage: Wattson's Thunderbolt gift
  needs New Mauville (the Game Corner sells it by Wattson anyway). Hidden
  Power's type is shown as "varies". Fixed-damage moves don't count toward
  the boss matchups' best multipliers or the split fit's STAB moves.
- **Wild Pokemon by stage**: species added by the restock, the strongest by
  base stat total, and the first Fairy types, over every table of the stage's
  maps (land, water, fishing, Rock Smash). Water tables count from
  `SURF_STAGE` (Winona's) at the earliest; when each rod becomes usable
  isn't modelled. The level curve's wild battles use the land tables only, with
  each slot's rate spread evenly over its level range.
- FRLG maps (`*_Frlg` folders) never belong to a stage.
- **Economy**: prices, sell values and healing of a basket of items, and the
  prize money of a full clear of each stage.

## Combat power estimate (prototype)

Level is a weak proxy for strength: at one level, base stats differ by
up to 3x, and a Pokemon stuck on 40-power moves fights far below one with
a strong same-type attack. `power.py` turns base stats, IVs and moves into
an **effective level**, the level of a typical Pokemon that would fare as
well one-on-one. It's a diagnostic in the report: nothing (`apply`, the
explorer, the curve's targets) reads it yet.

- **Reference** (`reference`): base `REFERENCE_BASE` (80) in every stat,
  IV `REFERENCE_IV` (15, a typical caught Pokemon), neutral nature, no
  EVs, no type. Its one attack hits the mean of the physical and the
  special damage, with an expected power (STAB, accuracy and strikes
  folded in) fitted by `fit_reference_power` to every trainer Pokemon's
  best move: `a + b ln(level)`, since move power climbs fast early and
  flattens late (about 51 at level 5, 92 at 25, 110 at 50, 124 at 85).
  The fit is in the report.
- **Trainer Pokemon** (`fighter`): its species' base stats and its
  `IVs:` line (trainerproc's 31s by default), neutral nature and no EVs
  (`trainers.party` sets none), and its set moves or default moveset.
- **Damage** (`expected_damage`, `move_power`): the damage formula
  without rounding, at the mean roll (0.925). Each side uses its best
  expected damage per turn, counting:
  - STAB, accuracy (0 never misses), and `strikeCount`, or 3.1 strikes for
    `multiHit` (3.0 before `B_MULTI_HIT_CHANCE` GEN_5);
  - the turns a move takes (`TURN_COST`): 2 for recharge (Hyper Beam, read
    from its nested `MOVE_EFFECT_RECHARGE`) and charging moves, 3 for
    Future Sight;
  - 60% of Water Spout's and Eruption's power (`HP_POWER_MEAN`);
  - Night Shade and Psywave as the user's level. Other fixed damage
    scores 0, as do moves that faint the user and attacks that need a
    state a straight fight doesn't have (`CONDITIONAL_EFFECTS`: Focus
    Punch, Dream Eater, Fake Out and the like).
- **Abilities**: `trainers.party` sets none, so only an ability the
  Pokemon is sure to have counts (`certain_ability`: both regular slots
  hold it). Huge Power and Pure Power double Attack, and Truant halves
  every attack.
- **Score** (`score`): the turns the foe needs to KO the Pokemon over the
  turns it needs to KO the foe, so 1 is an even fight. Each side's
  survival gets `SPEED_BONUS` (0.5) turns times its chance to move first.
  That chance rises smoothly with the speed ratio (`first_strike`: 10%
  faster is 72%), so the score has no jump at equal speed.
- **Effective level** (`effective_level`): bisection on the reference's
  level, against a reference foe at the Pokemon's own level, until the
  reference scores what the Pokemon does. The reference itself gets back
  exactly its own level. The range is 1-300, and a Pokemon with no scored
  attack gets none.

Left out: types (`score` counts them when given the type chart, for the
matchup model below), other abilities, held items,
status and stat moves, priority, critical hits and switching. The bench it
compares with is in levels, so it counts the player's party as typical
Pokemon (`findings.md` section 15).

## Matchup-relative strength (prototype)

The effective level scores a boss Pokemon against a typeless reference,
and the bench counts the player's team as typical Pokemon. `matchup.py`
scores each story boss against a stand-in for the team the player could
have by then, with types in play. Like the effective level, it's a
diagnostic in the report: nothing (`apply`, the explorer) reads it.

- **The stand-in team** (`stand_in_team`), per boss and starter, from
  `matchup_settings.json` (the owner's to change):
  - the starter line at the Exp. Share lead's level (the share curve's
    party before the boss, `POWER_BENCH`), evolved by level on time
    (`restock.SpeciesInfo.evolve` with no `EVOLVE_GRACE`);
  - up to `catches_per_stage` (3) catches per earlier stage, `team_size`
    (6) in all, at the bench's levels. The candidates are the species of
    the `fields` (land and water: the rods and Rock Smash aren't gated by
    stage yet) of the wild tables of the stages up to the boss's, each
    evolved by level for the bench's level. They're picked by base stat
    total, highest first, skipping any that shares a type with the team,
    then filling up with the rest; `exclude` drops species, and one with
    no scored attack (Abra, Wobbuffet) is skipped;
  - IVs `ivs` (15) in every stat, and up to `moves` (4) attacks
    (`pick_moves`) from its default moveset and the TMs on the maps of
    the stages before the boss's (`open_tms`: a boss's own stage hands
    its TMs out with the fight or after it) that its teachables hold,
    minus `tm_exclude_maps` (the Game Corner's, a coin grind). They're
    picked one at a time for the largest gain in its best damage summed
    over every defending type.
- **The rival teams follow the starter** (`starter_boss`):
  `TRAINER_MAY_RUSTBORO_TREECKO` is the team met after choosing Treecko.
- **The matrix** (`fight`): `power.score` with the type chart for every
  stand-in against every boss Pokemon, each side on its best move against
  that foe. Types also bring certain abilities' immunities
  (`ABILITY_IMMUNE`: Levitate, Flash Fire, Volt Absorb and the like, and
  Lightning Rod and Storm Drain from `B_REDIRECT_ABILITY_IMMUNITY` GEN_5).
  Night Shade keeps its fixed damage but misses a Normal type.
- **The readings**, per fight and starter:
  - **hardest**: the boss Pokemon whose best answer (the team's highest
    score against it) is lowest, with that answer and the stand-in that
    gives it;
  - **cover**: the boss Pokemon with an answer of `ANSWERED` (1) or more;
  - **lead**: the best answer to the boss's first Pokemon, which the AI
    always leads with, so no lead-choice game is needed;
  - and the fights with a boss Pokemon nothing answers, hardest first.
  The report also lists each stage's stand-in teams with their attacks.
- **Limits.** Every answer is a fresh one-on-one with free switching, so a
  stand-in that answers three boss Pokemon is counted three times at full
  HP: the readings flatter the team, and the ranking says more than the
  numbers. A double battle (Tate and Liza) is scored the same way. The
  stand-in is a guess: a real team varies more than any rule, and
  catching the strongest of every new type on every stage overstates a
  casual one. Everything `power.py` leaves out still stays out: other
  abilities, items, status, setup, stat drops after Overheat or Leaf
  Storm, and the AI's switching. Simulating battles (headless test-ROM
  battles, or Pokemon Showdown's damage calc) would cover them, at far
  more cost.
- **Next steps**, if it proves useful: gate the rods, Rock Smash and
  HM-only areas by stage; a reading that spends HP across the fight (an
  assignment of stand-ins to boss Pokemon); and a knob in the explorer
  or a target for `apply` once the owner trusts it.

## Story stages

`story_stages.json` lists Emerald's story in order. Each stage has map
globs (folder names under `data/maps/`; a map belongs to the first stage
that matches it) and the bosses fought at its end, in order. A trainer
belongs to the stage of the first map whose script battles it
(`trainerbattle_*`, rematches skipped). `rival` and `starter` pick the rival
battles (`TRAINER_{RIVAL}_ROUTE_103_{STARTER}`, default May with the player
on Mudkip), and `exclude` drops the other rival variants. Two optional
per-stage keys handle maps that open in parts: `land_maps` globs place a
map's land (grass) table in that stage ahead of its `maps` match, and
`trainers` ids override the stage of the map that battles them. Route 103
uses both: its grass is at the west end, by the first rival fight, so its
land table is in the Rival stage; the rest of the map (the east side,
reached from Route 110) is with Wattson, except the swimmers Isabelle and
Pete, who need Surf and sit with Winona. Its fishing table stays with
Wattson, and its water table counts from Winona's stage (`SURF_STAGE`), as
every water table does. Route 109's southern trainers need Surf too and sit
with Winona, and the Abandoned Ship's Dive-only hidden floor is with Juan. The stage split is approximate: water routes sit after
Norman (Surf), Dive and Sky Pillar with Juan, Meteor Falls 1F_2R and B1F
(Waterfall) with the Elite Four, and optional areas (Safari Zone, New
Mauville, Scorched Slab, routes 129-134) in the stage where they open. A
stage holds what the player can reach before its bosses, so each Trick
House puzzle sits in the stage after the badge it needs
(`Route110_TrickHouseEntrance/scripts.inc`): Puzzle 1 and the
entrance, corridor and end rooms with Wattson, Puzzle 2 (badge 3) with
Flannery, and so on up to Puzzle 7 (badge 8) with the Elite Four.
`unstaged` lists the maps that deliberately belong to no stage: post-game
areas (S.S. Tidal, Steven's cave, Altering and Artisan Caves, the Desert
Underpass, Marine Cave, Sealed Chamber, Trick House Puzzle 8), the Elite
Four rooms, whose trainers are bosses, and unused maps.
