# Rebalance measurements

Measures how far Emerald's difficulty has drifted from vanilla now that the
game runs on the expansion's modern data and the fork's config flips (#113).
It reads the repo's own headers twice:

- **modern**: the build as configured (`include/config/*.h` as committed);
- **vanilla**: the same configs with the data and formula switches set to
  `GEN_3` (`VANILLA_OVERRIDES` in `gamedata.py`): Gen 3 learnsets, stats,
  types, exp yields, move data and types, the type-based physical/special
  rule, the Gen 3 type chart, the Gen 3 exp formula (/7, 1.5x for trainers,
  split, no scaling), and Gen 3 prices, healing and sell value. Vanilla wild
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
plus two checks that every trainer species and move in the real
`src/data/trainers.party` resolves under both regimes.

## Outputs

- `output/report.md`: every table the findings use. Committed as a
  snapshot; rerun after upstream syncs or balance edits.
- `output/trainer_mons.csv`: every trainer Pokemon with its vanilla and
  modern default moveset and its flags (gitignored).
- `output/summary.json`: the report's numbers, for scripts (gitignored).

The written-up findings and the proposed balance changes are in the
closing comment of issue #113.

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
- **Default movesets**: `GiveBoxMonInitialMoveset` (the last four distinct
  level-up moves, level-0 evolution moves skipped) under both learnsets, for
  every trainer Pokemon without set moves. Flags:
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
  Fixed-damage moves (power 1) are left out of the flips.
- **Split fit**: for the species in `SPLIT_WATCH`, the better attacking stat
  against the Gen 3 category of each STAB type and the split of its modern
  level-up STAB moves.
- **Boss type matchups**: per boss Pokemon, retypings, changed defensive
  multipliers and changed best offensive multipliers against single types.
- **TMs by stage**: the first story stage where each TM sits on a map
  (item ball, hidden item, mart list or script). A script source can be gated
  later than its map's stage (Wattson's Thunderbolt needs New Mauville).
- **Wild Pokemon by stage**: species added by the restock, the strongest by
  base stat total, and the first Fairy types. Rods and Surf aren't modelled.
- **Economy**: prices, sell values and healing of a basket of items, and the
  prize money of a full clear of each stage.

## Story stages

`story_stages.json` lists Emerald's story in order. Each stage has map
globs (folder names under `data/maps/`; a map belongs to the first stage
that matches it) and the bosses fought at its end, in order. A trainer
belongs to the stage of the first map whose script battles it
(`trainerbattle_*`, rematches skipped). `rival` and `starter` pick the rival
battles (`TRAINER_{RIVAL}_ROUTE_103_{STARTER}`, default May with the player
on Mudkip), and `exclude` drops the other rival variants. The stage split
is approximate: water routes sit after Norman (Surf), Route 103 east with
Wattson, and optional areas (Trick House, Safari Zone, routes 129-134) in
the stage where they open.
