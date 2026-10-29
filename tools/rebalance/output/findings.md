# Rebalance findings (#113)

**Levels:** sections 1-6 were measured at the story bosses' levels before #127 raised them (section 7). `report.md` now shows the raised levels, so its level-curve, default-moveset and boss tables differ from sections 1 and 2; section 7 gives the changes. `tools/rebalance/` is a standard-library script that reads this repo's data twice: once as built ("modern") and once with the data and formula configs at GEN_3 ("vanilla": Gen 3 learnsets, stats, types, yields, move data, the type-based physical/special rule, the Gen 3 chart, the Gen 3 exp formula, prices and healing). Vanilla wild Pokémon come from the pre-restock snapshot. Every number below comes from [`report.md`](report.md); run `python3 tools/rebalance/rebalance.py` to regenerate it, and the tests with `python3 -m unittest discover -s tools/rebalance`. CI runs them. This file is written by hand, so update it when the numbers move.

## Corrections to the issue's baselines
- trainers.party has **1,825** Pokémon, not 1,835: 436 with set moves and **1,389** on default moves. The extra 10 were the header comment's paragraphs; the generated `trainers.h` agrees.
- 640 trainers have exactly `Check Bad Move` and 173 exactly `Basic Trainer` (660 and 179 when counting any trainer whose AI includes the flag). 16 trainers have no AI line.
- 25 of the 30 story bosses run plain `Basic Trainer`.
- Since #129 all 30 story bosses, and the 91 boss teams in all (gym rematches, every rival team, Wally, Maxie, Archie, Tabitha, Matt and Shelly), run `Smart Trainer` without Omniscient and Smart Tera: `Basic Trainer / Smart Switching / Smart Mon Choices / PP Stall Prevention / Randomize Switchin`, plus any flag the team already had (Winona's `Risky`; `Force Setup First Turn` for Sidney, May's Rustboro Mudkip team and Brendan's Route 103 Treecko team). The counts above become 636 exactly `Check Bad Move` and 94 exactly `Basic Trainer` (654 and 185 counting any trainer whose AI includes the flag).

## 1. Level curve
Full clear of every trainer on each story stage's maps (500 story trainers), all members Medium Slow from level 5.
- **solo:** one Pokémon takes every KO.
- **rotate4:** four Pokémon take turns (party mean).
- **share6:** one Pokémon takes every KO, with five on the bench under the Gen 6 Exp. Share.

The exp math follows `Cmd_getexp` and is checked against `test/battle/exp.c`.

| boss | ace | vanilla solo | vanilla rotate4 | modern solo | modern rotate4 | share6 ace | share6 bench |
|---|---|---|---|---|---|---|---|
| Roxanne | 15 | 18 | 12.2 | 15 | 11.0 | 15 | 13.0 |
| Brawly | 19 | 22 | 14.8 | 18 | 13.2 | 18 | 16.0 |
| Wattson | 24 | 35 | 23.0 | 29 | 21.2 | 29 | 25.0 |
| Flannery | 29 | 48 | 31.2 | 38 | 27.5 | 38 | 32.0 |
| Norman | 31 | 49 | 32.0 | 39 | 28.8 | 39 | 34.0 |
| Winona | 33 | 59 | 38.5 | 47 | 34.2 | 47 | 40.0 |
| Tate and Liza | 42 | 70 | 45.5 | 55 | 40.2 | 55 | 47.0 |
| Juan | 46 | 77 | 50.0 | 61 | 44.2 | 61 | 52.0 |
| Sidney | 49 | 82 | 53.0 | 65 | 47.8 | 65 | 56.0 |
| Wallace | 58 | 84 | 54.0 | 67 | 49.0 | 67 | 58.0 |

- **Half clear:** the share6 bench reaches 11 / 14 / 22 / 28 / 29 / 35 / 41 / 46 at the eight gyms and 51 at Wallace.
- **Wild battles:** twenty average wild battles per stage add at most 2 levels (3 for the vanilla solo ace by Phoebe).
- **Scaled exp works:** the solo ace ends at 67, against vanilla's 84.
- **Without the Exp. Share** the modern party trails vanilla by 1.2 to 5.8 levels at the gyms and the Champion (1.2 at Roxanne: 11.0 vs 12.2; 5.8 at Juan: 44.2 vs 50.0; 5.0 at Wallace: 49.0 vs 54.0), mostly because trainer battles lost their 1.5x.
- **The Exp. Share doesn't lift the ace**, which gets the same exp as solo. It lifts the bench: the five benched Pokémon finish level with Wallace's ace (58.0 vs 58), 4 levels above vanilla's rotating party (54.0). From Flannery to Juan they sit 3 to 7 levels above each gym ace, the widest gaps being Winona (+7) and Juan (+6).
- **The ace's lead:** in modern the ace is 8 to 15 levels above each gym ace from Flannery to Juan.

## 2. Default movesets (Gen 3 vs Gen 9)
- Of the 1,389 Pokémon on default moves (751 on story trainers), only 30 keep the same moveset, and 292 share no move with vanilla.
- They average 2.28 damaging moves (vanilla 2.09), and their best move's power averages 69.5 (vanilla 61.7). The best move got stronger for 679 and weaker for 248.

| flag (all / story) | |
|---|---|
| no damaging move | 15 / 9 (the 9 story slots are Magikarp, Silcoon and Cascoon, as in vanilla; 6 of the 15 are the rematch-only Pokémon below) |
| lost every damaging move | 6 / 0 (rematch-only: Jeffrey 4/5's Surskit, Isaac 2's Mightyena, Kira and Dan 2's Illumise) |
| one damaging move left | 132 / 59 |
| lost STAB | 85 / 43 |
| 70+ power move Gen 3 teaches 10+ levels later | 39 / 14 |
| 70+ power move Gen 3 never teaches | 429 / 157 |

- **Lost STAB in story fights:**
  - the Museum grunts' Carvanha (Bite becomes Poison Fang);
  - the Makuhita and Hariyama of Yuji, Fredrick, Zander and Atsushi (Vital Throw, Arm Thrust and Fake Out become Bulk Up, Belly Drum and Detect);
  - Jeff's and Jace's Slugma (no Ember);
  - Kindra's and Tammy's Duskull (Astonish becomes Night Shade, fixed damage);
  - Xatu, Spoink and Kecleon.
- **One damaging move left:** Shannon's Claydol is down to Self-Destruct.
- **The bigger drift is power.** Examples:
  - Austina's Marill 26 gets Bounce, Aqua Tail and Play Rough;
  - Declan's Gyarados 34 gets Waterfall, Crunch and Aqua Tail;
  - the Space Center grunt's Numel 32 gets Lava Plume and Earth Power;
  - Marcel's Shiftry 29 gets Hurricane.

## 3. Hand-written movesets
- Of 436 Pokémon, 421 damaging set moves changed data. 151 flipped physical/special: 30 now use a weaker stat, 61 a similar one and 60 a stronger one.
- 139 Pokémon have a flip, 26 of them onto a weaker stat. No damaging set move changed type.
- **Boss flips onto a weaker stat** (fixed by #130; before it the counts above were 426, 156, 35 / 61 / 60, 143 and 31). Each move became a same-type move on the stronger stat that the species learns in this build (level-up or the Emerald TM/tutor list; Shadow Claw and Giga Impact aren't on it):
  - Wallace's Gyarados: Hyper Beam, Atk 125 -> SpA 60, now Double-Edge (tutor, physical 120);
  - Phoebe's two Banette: Shadow Ball, 115 -> 83, now Phantom Force (level 53, physical 90);
  - Glacia's Sealeo: Ice Ball, 75 -> 60, now Aurora Beam (level 28, special 65);
  - Wattson's Voltorb: Spark, 55 -> 30, now Charge Beam (level 16, special 50, raises Sp. Atk).
  - No rematch team has the same Pokémon with the same move: Wattson's rematches carry Electrode without Spark, and the Elite Four and Wallace have no rematch teams.
- **Boss flips onto a stronger stat:**
  - Drake: Salamence's Dragon Claw and Crunch 110 -> 135, Flygon's Crunch 80 -> 100, Shelgon's Dragon Claw 60 -> 95;
  - Norman: Slaking's Feint Attack 95 -> 160;
  - Juan's Crawdaunt: Crabhammer 90 -> 120;
  - Sidney's Mightyena: Crunch 60 -> 90;
  - Wally's Magneton: Tri Attack 60 -> 120.
- **Player-side split fit:**
  - Sharpedo, Crawdaunt, Mightyena, Absol, Salamence, Flygon and Breloom gain the most.
  - Swampert (6 of its 7 level-up STAB moves are special, on Atk 110) and Gyarados (4 of 6 special, on Atk 125) still lean on the wrong stat.

## 4. Type matchups
- **Steel no longer resists Ghost and Dark.**
  - These now hit Steel neutrally where their best move was resisted:
    - Phoebe's Dusclops 48, Banette 49 and Sableye;
    - both of Glacia's Glalie;
    - Sidney's Mightyena and Cacturne;
    - Norman's Vigoroth and Slaking;
    - the Magma and Aqua Mightyena and Golbat lines.
  - Player Steel types lose their safe switch against Phoebe and Sidney.
  - Wattson's and Wally's Magneton and Winona's Skarmory now take neutral damage from Ghost and Dark.
- **Fairy:**
  - Weak to it: all of Sidney's, Drake's and Brawly's teams, plus Juan's Crawdaunt and Kingdra.
  - Wally's Ralts and Gardevoir become Psychic/Fairy: immune to Dragon, no longer weak to Bug or Dark, newly weak to Poison and Steel.
  - Flannery's team resists Fairy.
  - The player meets wild Fairy types early: Ralts and Marill by Roxanne, Jigglypuff by Flannery, Snubbull by Tate and Liza, Mawile by Juan (Cave of Origin, then Victory Road). No TM teaches a Fairy move.
- Roxanne and Tate and Liza are unchanged.

## 5. Player side
**TMs by the first stage they appear on** (reusable, so one copy covers the party; 49 of the 50, all but Snatch, which is on the post-game S.S. Tidal). Every damaging TM is listed; of the status TMs only Rain Dance and Sunny Day are (the rest are in `report.md`):
- Roxanne: Rock Tomb, Bullet Seed (25 power).
- Brawly: Sludge Bomb (90, Dewford Hall) and Steel Wing.
- Wattson: Thunderbolt, Flamethrower, Ice Beam and Psychic (Game Corner), Secret Power, Hidden Power, Shock Wave, Thief.
  - The Game Corner sells Thunderbolt, Flamethrower and Ice Beam (4,000 coins each) and Psychic (3,500). Coins cost 1,000 per 50, so that is 70,000-80,000 money per TM and 310,000 for all four (15,500 coins), against 44,560 from a full clear by Wattson and 107,496 by Flannery.
  - Wattson's own Thunderbolt gift needs New Mauville.
- Flannery: Focus Punch, Overheat, Iron Tail, Dig, Return.
- Norman: Facade (Petalburg Gym).
- Winona: Aerial Ace, plus Rain Dance and Sunny Day (Scorched Slab).
- Tate and Liza: the Lilycove mart's Hyper Beam, Fire Blast, Thunder and Blizzard, plus Shadow Ball, Solar Beam and Giga Drain.
- Juan: Earthquake, Brick Break, Water Pulse, Frustration.
- Elite Four: Dragon Claw (Meteor Falls B1F, after Waterfall).

The early outlier is a team-wide 90-power Sludge Bomb before Brawly.

**Wild Pokémon:** the restock roughly doubles what's catchable: 41 vs 21 species by Roxanne, 73 vs 35 by Wattson, 150 vs 70 by Winona, 242 vs 130 at the end. The strongest additions:
- Solrock (460) by Brawly;
- Shuckle by Flannery;
- Sigilyph (490) and Gible by Norman;
- Druddigon (485) on Sky Pillar by Juan, and Cloyster (525) in Meteor Falls B1F at the end;
- mostly water species otherwise: Basculin, Clawitzer, Lanturn, Gyarados.

Rod and Surf gating isn't modelled.

## 6. Economy
Prize money is unchanged: 11,524 by Roxanne, 44,560 by Wattson, 120,964 by Norman, 403,044 by Juan.

| item | vanilla price / HP | modern price / HP |
|---|---|---|
| Potion | 300 / 20 | 200 / 20 |
| Super Potion | 700 / 50 | 700 / 60 |
| Hyper Potion | 1200 / 200 | 1500 / 120 |
| Fresh Water | 200 / 50 | 200 / 30 |
| Revive | 1500 | 2000 |
| Ultra Ball | 1200 | 800 |

- Early healing is cheaper. Late healing costs about twice as much per HP.
- Items sell for 1/4 instead of 1/2, but treasures doubled in price: a Nugget still sells for 5,000 and a Star Piece for 6,000 (vanilla 4,900).
- The Escape Rope is a free key item, and a whiteout costs a badge-based amount.
- **Verdict:** money gets tight only with bulk Hyper Potions, Revives or Game Corner TMs.

## 7. Exp. Share curve and boss levels (#127)
The owner's baseline (#113): the Gen 6 Exp. Share on; balance by raising opponent levels, lower ordinary trainers only carefully, never a level cap; evaluate the 1.5x trainer exp; include catch exp and affection; leave the Lucky Egg and traded bonuses out. Numbers are from `report.md`, "Exp. Share curve (#127)".

**Model** (share6: one KO-taker, five on the bench, Medium Slow from 5; modern data):
- **1.5x:** `B_TRAINER_EXP_MULTIPLIER` GEN_LATEST (off, as built) and GEN_6 (on). Upstream's `Cmd_getexp` checks `<= GEN_7`, so GEN_7 also turns it on, against its config comment.
- **Catch exp** (`B_EXP_CATCH`, on): 3 catches per stage at the stage's land-table average. A catch runs `getexp` like a KO, so the active Pokémon gets full exp and the bench half.
- **Affection** (`B_AFFECTION_MECHANICS` TRUE): 4915/4096 at 4+ hearts (friendship 220), applied before the level scaling, as in `ApplyExperienceMultipliers`. Three brackets: none, modelled friendship, and 4 hearts from the start. The friendship model starts at 50 (`P_UPDATED_FRIENDSHIP`) and adds +5/+3/+2 per level (bands 0-99/100-199/200+), +3/+2/+1 per gym, Elite Four or Champion battle, and 4,096 steps of walking per stage (+1 per 128 steps, half the time). The bench reaches 220 by Flannery under both settings.
- **Left out:** the Lucky Egg, traded Pokémon, Soothe Bell and Luxury Ball.
- **Unevolved 1.2x, a sensitivity row only (owner to confirm):** `B_UNEVOLVED_EXP_MULTIPLIER` is on (GEN_LATEST). `ApplyExperienceMultipliers` gives 4915/4096 to a Pokémon at or past its `EVO_LEVEL` level that hasn't evolved, before the affection bonus. A party that evolves on time never gets it, so the baseline leaves it out. Keeping evolutions back (an Everstone, cancelling) is a player choice, like the Lucky Egg. The "whole party unevolved (1.2x)" row in the sensitivity table is a loose upper bound: it gives the 1.2x at every level, also below any evolution level, so it overstates the early stages. It lifts the bench 1 level early and 3 by Wallace (62 -> 65 with 1.5x off and the levels applied).
- **Checks:** the new math is unit-tested against the code: affection before scaling, the `<= GEN_7` trainer check, the friendship bands and caps, and level-up friendship. `test/battle/exp.c` covers catch exp only as "exp is given" (Gen 6+), with the same `getexp` path the model uses.

**What the extra terms add** (full clear, bench before Wallace, now):
- Catches add 0-1 level anywhere. The wild Pokémon are far below the party, so the scaled formula pays little for them.
- Affection adds about 2 levels late (Wallace: 58 with none, 60 with friendship, 60 always), and no walking or twice as much moves it by at most 2.
- The 1.5x adds 6 (Wallace bench 60 -> 66 with friendship; the KO-taker 70 -> 77).
- With no catches and no affection the curve matches #113's share6 bench (58 at Wallace).

**Step 2, targets (owner to confirm):**
- **Full clear:** each story boss's ace sits 1 level above the Exp. Share bench (`TARGET_MARGIN` 1), with modelled friendship. After the raises the bench sits against each raised boss's ace at -1 to -4 with no affection, -1 with friendship, and -1 to +1 with 4 hearts from the start. The KO-taker ends 0 (Roxanne) to 9-10 (the Elite Four and Champion; 10-11 with 1.5x on) levels above.
- **Half clear:** the bench at most 8 below each gym leader, Elite Four member and Champion (`HALF_CLEAR_GAP`).
- **Why these margins:** the half-clear bench trails the full-clear one by 4-7 levels late, so no single boss level is within 1 of one and within a few levels of the other. A margin of 0 would put the "always" bracket up to 2 above the ace. A margin of 2 or more would leave a half-clear party 9-10 levels short.
- **Rule:** bosses are only raised, never lowered. Every Pokémon on the team goes up by the same amount, which keeps the team's spread. The raises go in story order, so each one counts toward the later stages' exp.
- Roxanne and Brawly already sit 2-3 above the bench and stay as they are.

**Step 3, proposed levels** (raise on every Pokémon of the team -> new ace; ace now in brackets):

| boss | 1.5x off | 1.5x on |
|---|---|---|
| Rival, Route 103 (5) | +1 -> 6 | +1 -> 6 |
| Roxanne (15), Brawly (19) | +0 | +0 |
| Rival, Rustboro (15) | +2 -> 17 | +3 -> 18 |
| Rival, Route 110 (20) | +6 -> 26 | +8 -> 28 |
| Wally, Mauville (16) | +10 -> 26 | +13 -> 29 |
| Wattson (24) | +2 -> 26 | +5 -> 29 |
| Tabitha, Mt. Chimney (22) | +11 -> 33 | +15 -> 37 |
| Maxie, Mt. Chimney (25) | +9 -> 34 | +13 -> 38 |
| Flannery (29) | +5 -> 34 | +9 -> 38 |
| Norman (31) | +5 -> 36 | +9 -> 40 |
| Rival, Route 119 (31) | +11 -> 42 | +16 -> 47 |
| Shelly, Weather Institute (28) | +15 -> 43 | +19 -> 47 |
| Winona (33) | +10 -> 43 | +15 -> 48 |
| Rival, Lilycove (34) | +16 -> 50 | +21 -> 55 |
| Tabitha, Magma Hideout (33) | +17 -> 50 | +23 -> 56 |
| Maxie, Magma Hideout (39) | +12 -> 51 | +17 -> 56 |
| Matt (34) | +17 -> 51 | +23 -> 57 |
| Tate and Liza (42) | +9 -> 51 | +15 -> 57 |
| Tabitha, Mossdeep (40) | +16 -> 56 | +21 -> 61 |
| Maxie, Mossdeep (44) | +12 -> 56 | +18 -> 62 |
| Shelly, Seafloor Cavern (37) | +19 -> 56 | +25 -> 62 |
| Archie (43) | +13 -> 56 | +20 -> 63 |
| Juan (46) | +11 -> 57 | +17 -> 63 |
| Wally, Victory Road (45) | +15 -> 60 | +22 -> 67 |
| Sidney (49) | +12 -> 61 | +19 -> 68 |
| Phoebe (51) | +11 -> 62 | +18 -> 69 |
| Glacia (53) | +9 -> 62 | +16 -> 69 |
| Drake (55) | +8 -> 63 | +15 -> 70 |
| Wallace (58) | +5 -> 63 | +13 -> 71 |

Each rival row goes on all six teams of that fight: May or Brendan, with each starter counter. The model plays May's team for a Mudkip player (`story_stages.json`), and the other five have the same levels, so they get the same raise (`rival_variants`; "Proposed boss raises" in `report.md` lists them).

- **Rerun with the raises** ("After the ... raises" in `report.md`): on a full clear the bench is 1 below the ace at 28 of 30 bosses (1.5x off) and 29 of 30 (1.5x on). The exceptions are Brawly, and Roxanne with 1.5x off, whose aces are already higher. On a half clear it is 3 to 8 below every gym leader, Elite Four member and Champion in both settings, so both meet the targets. With the owner's Elite Four and Champion spacing (below) applied, `report.md` counts 25 of 30 within 1 on a full clear (Glacia, Drake and Wallace now sit above the rule) and 12 of 13 within 8 on a half clear (Wallace is 9).
- **The raised bosses feed the curve:** with them the bench before Wallace is 62 (off) or 70 (on), not 60 or 66.
- **The Elite Four bunch up under the margin rule:** with 1.5x off it gives 61/62/62/63 and Wallace 63, because the bench gains little between their fights. Keeping their original steps (2-3 levels apart: 61/63/65/67, Wallace 70) would put Wallace 8 above the full-clear bench and 13 above the half-clear one.
- **Owner's decision (2026-10-29): the final challenge sits a little higher.** Levels matter less this high, so the Elite Four step one level per fight and Wallace sits 3 above Drake: Sidney 61, Phoebe 62, Glacia 63 (+1 over the rule), Drake 64 (+1), Wallace 66 (+3). With 1.5x off and modelled friendship the full-clear bench is 1 / 1 / 2 / 2 / 4 below them and the KO-taker 7-9 above; the half-clear bench is 7 / 8 / 8 / 8 / 9 below, so Wallace goes one level past the half-clear target.
- **Recommendation: 1.5x off** (as built). It needs smaller raises (Wallace +5 vs +13; the Magma and Aqua bosses +9 to +19 vs +13 to +25) and ends at 63 rather than 71. Fewer raised Pokémon pass their evolution level (34 vs 41, rival teams included, below). It also keeps the un-raised route trainers closer: the 1.5x lifts the bench another 1-6 levels above each stage's trainers (4-6 from Flannery on). The 1.5x-on table meets the same targets if the owner prefers it.
- **Stage trainers stay as they are:** each stage's regular trainers average 3 (Brawly) to 18 (Juan) levels below the full-clear bench ("Stage trainers against the bench"). Raising them doesn't close that gap, because their extra exp lifts the bench too: every stage trainer +3 moves the bench +1 to +3 (+2 to +3 from Wattson on; Juan 54 -> 57, Wallace 60 -> 62, 1.5x off). Lowering them (the secondary lever) would widen the gap. So the curve rests on the bosses alone. The routes being easy for an Exp. Share party is the cost of that baseline, and only a playtest can say how it feels.
- **Wild tables: no change needed for the curve.** Catches move it by at most 1 level. Higher wild levels would make wild Pokémon more of a threat, not change the curve, so that belongs to the restock (#4/#5), which owns `src/data/wild_encounters.json`.
- **Under-evolved after the raise** (levels only, no species swaps; species at or past their `EVO_LEVEL` level only after the raise, 1.5x off; a one-off check of the species_info `EVOLUTION` entries, not in `report.md`). 34 Pokémon, 28 of them on the rival teams:
  - Wally, Mauville: Ralts 26 (evolves at 20);
  - Tabitha, Mt. Chimney: Numel 33 (33);
  - Shelly, Weather Institute: Carvanha 43 (30);
  - Winona: Swablu 39 (35);
  - Tabitha, Magma Hideout: Numel 43;
  - Juan: Sealeo 54 (44);
  - Rival, Rustboro (each of the 8 is on a May and a Brendan team): the starter counter at 17 (Treecko, Torchic or Mudkip, 16), and Lotad 15 (14) on the Treecko-player teams;
  - Rival, Route 119: Slugma 40 (38) on the Mudkip- and Torchic-player teams (4), and the starter at 42 (36: Grovyle, Combusken or Marshtomp, 6);
  - Rival, Lilycove: the same as Route 119, at 48 and 50 (10).

  1.5x on (41) adds Wingull 26 (25) on four Route 110 rival teams, Numel (Flannery's and a second of Tabitha's) and Norman's Vigoroth 36 (36). Evolving them is a follow-up for #131/#132.
- **Default movesets change with the levels** (the last four level-up moves). 43 raised boss Pokémon are on default moves (the gym leaders and Elite Four all have set moves), and 42 of them get a different set under 1.5x off ("Default movesets of the raised boss Pokemon" in `report.md`). New flags:
  - Lost STAB: May's Route 110 Slugma (Ember drops out).
  - One damaging move left and lost STAB: the Mightyena of Maxie (Magma Hideout) and Matt.
  - New strong moves: 15 slots, up from 9 (Liquidation on Carvanha and Sharpedo, Outrage on Tropius, Sucker Punch and Play Rough on Mightyena, Giga Drain and Leaf Blade on Grovyle).

  The other 25 rival teams add 65 Pokémon on default moves, and 52 of them get a different set (the 1.5x-off list in `report.md` at the commit before the levels commit, "Give the other rival and starter teams ..."):
  - Lost STAB: the Route 110 Slugma on the Brendan-Mudkip, Brendan-Torchic and May-Torchic teams (Ember drops out, as on May's Mudkip team), and the Route 110 Combusken 26 on both Treecko-player teams (Flame Charge drops out; Slash also puts it above the band).
  - New strong moves: 15 more Pokémon (Giga Drain on the Route 110 Grovyle, Rock Slide on the Route 110 Marshtomp, Giga Drain on Lombre, Lava Plume on Slugma, Outrage on Tropius).

  #131 and #132 should work from that list once the levels land. The full-game flag table in "Default movesets" updates with them too.

**Applied** (owner's choice, 2026-10-29: 1.5x off, these targets): `src/data/trainers.party` has the 1.5x-off column, plus the owner's Elite Four and Champion spacing above: levels only, 165 Pokémon on 53 teams (the 28 raised bosses, 100 Pokémon, and the other 25 rival teams, 65), with `B_TRAINER_EXP_MULTIPLIER` unchanged. The numbers above (and in the table) are from before the raises. `report.md` now measures the raised data:
- Its "Proposed boss raises" show +0 for 1.5x off. The 1.5x-on column is now relative to the applied levels (Juan +6 -> 63, Wallace +5 -> 71), and its after-raise curve is unchanged.
- Its "Default movesets of the raised boss Pokemon" lists none for 1.5x off.
- Its story flags in "Default movesets" moved from 9 / 59 / 43 / 14 / 157 (no attack / one attack / lost STAB / above band / new strong) to 9 / 61 / 46 / 12 / 163. The story counts leave out the five rival teams the model doesn't play; over every trainer they moved from 15 / 132 / 85 / 39 / 429 to 15 / 134 / 91 / 32 / 447.
- The #113 level curve's boss aces are the raised ones.

**Side effects of the applied levels:**
- **Steven in the Mossdeep Space Center multi battle** (`PARTNER_STEVEN`, `src/data/battle_partners.party`): Maxie and Tabitha went from aces 44/40 to 56/56. The owner wants helper NPCs to rise with the challenge, so Steven goes +12, from 42-44 to 54-56 (ace 56, level with the foes). The model doesn't cover partners.
- **Post-game rematches now sit below some first fights (not changed here):** Tate and Liza's rematch 2 has ace 50 against 51 for the first fight, Juan's rematches 2 and 3 have 51 and 56 against 57, and Wally's Victory Road rematches 2-5 have 48-57 against 60. The rematches are outside the story model. Lifting each rematch ladder above its raised first fight is a follow-up.

## Proposed balance changes (owner to accept or reject; each can be its own issue)
1. **Soft level cap at each gym ace** (config). Set `B_LEVEL_CAP_TYPE LEVEL_CAP_FLAG_LIST` and `B_EXP_CAP_TYPE EXP_CAP_SOFT`. `sLevelCapFlagMap` in `src/caps.c` already holds exactly the measured aces (15/19/24/29/31/33/42/46/58). Consider `B_RARE_CANDY_CAP` too.
2. **Boss AI to `Smart Trainer`** (data) for the gym leaders, the Elite Four, Wallace, and optionally the rivals and team leaders. Done in #129 for all of them, without Omniscient and Smart Tera (see "Corrections").
3. **Fix the four boss sets the split weakened** (data): Wallace's Gyarados Hyper Beam, Phoebe's Banettes' Shadow Ball (-> Shadow Claw), Glacia's Sealeo Ice Ball, Wattson's Voltorb Spark. Done in #130 with Double-Edge, Phantom Force, Aurora Beam and Charge Beam (section 3).
4. **Hand-write movesets for the story Pokémon that lost STAB or kept one attack** (43 and 59 slots; the list is in `output/trainer_mons.csv`). Start with the Makuhita/Hariyama line, the Museum Carvanha and Jeff's and Jace's Slugma.
5. **Review the 157 story slots with strong new default moves** route by route (they may be welcome). A trainers-only Gen 3 learnset would need code: `P_LVL_UP_LEARNSETS` is a single include.
6. **Optional `B_TRAINER_EXP_MULTIPLIER GEN_6`** to restore the 1.5x (GEN_7 also restores it: `Cmd_getexp` checks `<= GEN_7`), only if the Exp. Share isn't the intended way to play. Evaluated with the Exp. Share in section 7.
7. **One Steel or Poison coverage move each for Drake and Sidney**, whose whole teams are weak to Fairy (low priority).
8. **Sludge Bomb at Dewford:** move it later, or accept it (low priority).
9. **Economy:** leave it, or set `I_HEALTH_RECOVERY GEN_3` if late-game healing feels too expensive in a playtest.

Not proposed: reverting `P_LVL_UP_LEARNSETS` globally, which would also change every wild and player moveset.

**Caveats:**
- The full clear is an upper bound.
- Sections 1-6 have no catch exp or affection (1.2x at 4 hearts, `B_AFFECTION_MECHANICS` TRUE); section 7 adds both. The Lucky Egg and traded bonuses push levels higher still.
- The stages are approximate, and some TMs and wild slots open later than their map's stage. A stage holds what's reachable before its bosses, so each Trick House puzzle sits in the stage after the badge it needs (Puzzle 2, badge 3, with Flannery, up to Puzzle 7, badge 8, with the Elite Four), and Meteor Falls 1F_2R (Waterfall) is with the Elite Four. Route 103's grass counts from the first rival fight, its Surf-only swimmers from Winona. Post-game maps (`unstaged` in `story_stages.json`, including Trick House Puzzle 8) are left out.
- Spot-check Phoebe and Sidney against a Steel lead, Drake against a Fairy, and Wallace's Gyarados on the debug ROM before items 3 and 7.
