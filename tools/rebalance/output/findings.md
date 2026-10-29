# Rebalance findings (#113)

**No game data changed.** `tools/rebalance/` is a standard-library script that reads this repo's data twice: once as built ("modern") and once with the data and formula configs at GEN_3 ("vanilla": Gen 3 learnsets, stats, types, yields, move data, the type-based physical/special rule, the Gen 3 chart, the Gen 3 exp formula, prices and healing). Vanilla wild Pokémon come from the pre-restock snapshot. Every number below comes from [`report.md`](report.md); run `python3 tools/rebalance/rebalance.py` to regenerate it, and the tests with `python3 -m unittest discover -s tools/rebalance`. CI runs them. This file is written by hand, so update it when the numbers move.

## Corrections to the issue's baselines
- trainers.party has **1,825** Pokémon, not 1,835: 436 with set moves and **1,389** on default moves. The extra 10 were the header comment's paragraphs; the generated `trainers.h` agrees.
- 640 trainers have exactly `Check Bad Move` and 173 exactly `Basic Trainer` (660 and 179 when counting any trainer whose AI includes the flag). 16 trainers have no AI line.
- 25 of the 30 story bosses run plain `Basic Trainer`.

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
- Of 436 Pokémon, 426 damaging set moves changed data. 156 flipped physical/special: 35 now use a weaker stat, 61 a similar one and 60 a stronger one.
- 143 Pokémon have a flip, 31 of them onto a weaker stat. No damaging set move changed type.
- **Boss flips onto a weaker stat:**
  - Wallace's Gyarados: Hyper Beam, Atk 125 -> SpA 60;
  - Phoebe's two Banette: Shadow Ball, 115 -> 83;
  - Glacia's Sealeo: Ice Ball, 75 -> 60;
  - Wattson's Voltorb: Spark, 55 -> 30.
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
    - Norman's Vigoroth;
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

## Proposed balance changes (owner to accept or reject; each can be its own issue)
1. **Soft level cap at each gym ace** (config). Set `B_LEVEL_CAP_TYPE LEVEL_CAP_FLAG_LIST` and `B_EXP_CAP_TYPE EXP_CAP_SOFT`. `sLevelCapFlagMap` in `src/caps.c` already holds exactly the measured aces (15/19/24/29/31/33/42/46/58). Consider `B_RARE_CANDY_CAP` too.
2. **Boss AI to `Smart Trainer`** (data) for the gym leaders, the Elite Four, Wallace, and optionally the rivals and team leaders.
3. **Fix the four boss sets the split weakened** (data): Wallace's Gyarados Hyper Beam, Phoebe's Banettes' Shadow Ball (-> Shadow Claw), Glacia's Sealeo Ice Ball, Wattson's Voltorb Spark.
4. **Hand-write movesets for the story Pokémon that lost STAB or kept one attack** (43 and 59 slots; the list is in `output/trainer_mons.csv`). Start with the Makuhita/Hariyama line, the Museum Carvanha and Jeff's and Jace's Slugma.
5. **Review the 157 story slots with strong new default moves** route by route (they may be welcome). A trainers-only Gen 3 learnset would need code: `P_LVL_UP_LEARNSETS` is a single include.
6. **Optional `B_TRAINER_EXP_MULTIPLIER GEN_7`**, only if the Exp. Share isn't the intended way to play.
7. **One Steel or Poison coverage move each for Drake and Sidney**, whose whole teams are weak to Fairy (low priority).
8. **Sludge Bomb at Dewford:** move it later, or accept it (low priority).
9. **Economy:** leave it, or set `I_HEALTH_RECOVERY GEN_3` if late-game healing feels too expensive in a playtest.

Not proposed: reverting `P_LVL_UP_LEARNSETS` globally, which would also change every wild and player moveset.

**Caveats:**
- The full clear is an upper bound.
- The model has no catch exp. Affection (1.2x at 4 hearts, `B_AFFECTION_MECHANICS` TRUE), the Lucky Egg and traded bonuses would all push levels higher.
- The stages are approximate, and some TMs and wild slots open later than their map's stage. A stage holds what's reachable before its bosses, so each Trick House puzzle sits in the stage after the badge it needs (Puzzle 2, badge 3, with Flannery, up to Puzzle 7, badge 8, with the Elite Four), and Meteor Falls 1F_2R (Waterfall) is with the Elite Four. Route 103's grass counts from the first rival fight, its Surf-only swimmers from Winona. Post-game maps (`unstaged` in `story_stages.json`, including Trick House Puzzle 8) are left out.
- Spot-check Phoebe and Sidney against a Steel lead, Drake against a Fairy, and Wallace's Gyarados on the debug ROM before items 3 and 7.
