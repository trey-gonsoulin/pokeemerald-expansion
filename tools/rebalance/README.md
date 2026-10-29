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
  Pokemon with them. A sensitivity table varies the catches, the walking
  and the stage trainers' levels.
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
  maps (land, water, fishing, Rock Smash). When Surf and each rod become
  usable isn't modelled, so water species show up before the player can
  reach them. The level curve's wild battles use the land tables only, with
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
Pete, who need Surf and sit with Winona. Its water and fishing tables stay
with Wattson. The stage split is approximate: water routes sit after
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
