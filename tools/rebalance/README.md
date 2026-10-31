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
python3 tools/rebalance/rebalance.py curve '{"ko_takers": 6, "margin": 1}'   # the same run as text
```

A page with sliders for the Exp. Share curve's knobs (`EXPLORER_KNOBS`)
and a chart of the levels before each story boss: the boss aces (with the
knobs and today's), the party (a reference level, its lowest and highest
member), the stage's route trainers' mean ace and its wild land average.
It runs this tool's own Python in the browser through Pyodide (loaded from
the jsDelivr CDN, so it needs internet), in a Web Worker. Nothing is parsed
there: `curve_snapshot` writes the parsed inputs to
`output/curve_data.json` (the story stages and trainers, the rematch ladders and theirs, exp yields, level
evolutions, the scaling table, both regimes' land slots and the config
defines), and `load_snapshot` rebuilds them for
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
  (`B_SCALED_EXP`), and three options:
  - `scaling_power`: the scaling table is `floor(i^p / 4)`. It's 2.5 in
    upstream and 3.5 under the fork's `B_SCALED_EXP_STEEP` (#154).
  - `overlevel_cutoff`: 1 exp past that many levels above the foe, or
    percent of its level with `overlevel_unit`. With `overlevel_halflife`
    the exp instead halves every that many levels or percent past the
    cutoff (`Overlevel`). The fork's `B_EXP_OVERLEVEL_PENALTY` (#154) is
    10% and 5%.
  - `share_fraction`: the Exp. Share bench's share, the game's half; not a
    game option.

  The defaults (`explorer_defaults`) are the game's configs.
- **Targets:** the party level everything measures against (`REFERENCES`:
  the bench, the KO-takers' mean, the party's mean, its highest member),
  the boss margin (off: today's levels) with the Elite Four spacing
  (`LEAGUE_STEPS`), #150's route-trainer gap (`TRAINER_GAP`: each stage's
  ordinary trainers raised until their aces average that far below the
  reference when fought) and wild gap (the stage's land average that far
  below the reference at its start, over the vanilla tables), and whether
  raised Pokemon evolve (`restock.SpeciesInfo.evolve`, `EVOLVE_GRACE`
  levels past a level evolution; `EVOLVE_EXEMPT`'s teams never do).
  `gap_unit` puts the margin and both gaps in percent of the reference
  instead of levels.
- **The post-game (#139):** after Wallace the chart goes on through the
  rematch rounds and Steven (`rematch_ladders` reads `gRematchTable` through
  `G.parse_rematches`):
  - **Rounds:** the gym leaders' ladders and Wally's (`POSTGAME_LADDERS`)
    are fought in rounds, `Rematch 2` being every ladder's first rematch.
    With the margin, each round's teams go up to one ace, the margin over
    the reference at the round's start, and at least 1 over their ladder's
    previous fight.
  - **Steven:** `POSTGAME_FINAL` follows, at the margin and at least
    `POSTGAME_FINAL_STEP` (3) over the last round's highest ace. All of it
    is capped at 100.
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

### Applying a curve (#150)

```sh
python3 tools/rebalance/rebalance.py apply    # writes the data for curve_settings.json
python3 tools/rebalance/rebalance.py          # then refresh report.md and curve_data.json
```

`curve_settings.json` holds the explorer settings the data is built for
(the owner's choice, `findings.md` section 8). `apply` runs `explore_run` on
the repo's own data with them, through `apply_plan`, and writes:
- the raises into `src/data/trainers.party`, for the staged bosses, their
  rival variants (to the boss's ace, `variant_raises`) and every regular
  trainer of each stage. `raise_party` raises every Pokemon of a team by
  the same amount, capped at 100. A raised Pokemon evolves through
  `evolve_team`, as the model's fights do: never on an `EVOLVE_EXEMPT` team,
  and on a boss's team (bosses and variants) not into a species the team
  already has;
- `PARTNER_FIGHTS`' partners (Steven at Mossdeep, to his foes' highest ace;
  partners don't evolve) into `src/data/battle_partners.party`;
- each stage's wild offset over the vanilla levels, for every table of its
  maps (a water table counts from `SURF_STAGE`), into
  `tools/area_archetypes/level_offsets.json`, through `restock --write`.
  Restock runs first, so a refused restock leaves nothing half written;
- the post-game rounds' teams and Steven (as bosses: no duplicate
  evolutions), and the ordinary trainers' rematch ladders (#139), into
  `src/data/trainers.party`.

It only raises. On data it already wrote it asks for nothing, which
`RealRepo.test_data_meets_the_curve_settings` checks. After a change to
`trainers.party`, the wild tables or the exp formula, rerun `apply` and
`rebalance.py` (or change the settings and do the same).
`apply` doesn't touch trainers outside the stages and the rematch table. Hand-written
movesets don't move with the levels: after a raise, check the report's
default-moveset flags (#139 hand-wrote the flagged rematch sets, #159 the
story ones, #161 the off-stage ones), and after lowering a level run the tests, which check that every
set move is still learnable (#145).

The page's files are `explorer/index.html`, `app.js` (the controls and the
Chart.js chart), `worker.js` and `model.js` (the module list and the Python
bootstrap). The repo's `.gitignore` ignores `*.js`, so add new ones with
`git add -f`.

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
  GEN_7 and earlier), on a full and a half clear, in three affection
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
  lists the upstream Gen 3 moves that break the rule as trainer, species and
  move, by cause; the test also fails on an entry that no longer breaks it, so
  the list only shrinks.
- **Split fit**: for the species in `SPLIT_WATCH`, the better attacking stat
  against the Gen 3 category of each STAB type and the split of its modern
  level-up STAB moves.
- **Boss type matchups**: per boss Pokemon, retypings, changed defensive
  multipliers and changed best offensive multipliers against single types.
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
