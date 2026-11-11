# Random party

Rolls a random party of six Pokémon the player can get in Emerald Plus, for
challenge runs and variety. Standard library only; it reads the repo and
writes nothing.

```sh
python3 tools/random_party/random_party.py                  # a random Hoenn starter + five others
python3 tools/random_party/random_party.py --no-starter     # six non-starter families
python3 tools/random_party/random_party.py --legendaries    # Regis, Rayquaza, Kyogre... can be rolled
python3 tools/random_party/random_party.py --no-postgame    # only what's had before the Hall of Fame
python3 tools/random_party/random_party.py --even-families  # each family as likely, not each species
python3 tools/random_party/random_party.py --seed 42        # repeat a roll (each roll prints its seed)
python3 tools/random_party/random_party.py --list           # every obtainable family, earliest first
python3 -m unittest discover -s tools/random_party          # tests
```

```
1. Treecko      before Rival (Route 103)   starter - Professor Birch on Route 101
2. Wingull      before Rival (Route 103)   wild, grass - Route 103
3. Tentacool    before Brawly              wild, Old Rod - Dewford Town
4. Tropius      before Winona              wild, grass - Route 119
5. Clamperl     before Juan                wild, surfing - Underwater Route 126
6. Mareep       post-game                  wild, grass - Safari Zone Southeast  [rolled Ampharos]
```

The six are different evolution families. Every obtainable species is as
likely to be rolled as any other, so a line with more obtainable members
(Wurmple's five) comes up more often than a single-stage one (Sableye);
`--even-families` gives each family the same odds instead. Each
is shown as the family member that can be had first, with its earliest
source; `[rolled X]` names the member the dice picked when it isn't that one.
"before Roxanne" means reachable before that stage's boss fights, on the
stages of `tools/rebalance/story_stages.json`; maps in no stage are post-game.

## What counts as obtainable

- **Wild:** every table of `src/data/wild_encounters.json` on an Emerald map
  (not `*_Frlg`). Surf and Rock Smash wait for their badge and the rods for
  where they're given (`table_gates` in `sources.json`). Since the fork raises
  wild levels, some tables hold only the evolved form (Shelgon, Dusclops), so
  that's what the family reports.
- **Scripts:** `givemon`, `giveegg` and `setwildbattle` with a species constant
  in the Emerald maps' `scripts.inc`, and their in-game trades (`src/data/trade.h`),
  which wait for the species they ask for.
- **Evolution:** level-ups and battle conditions always count; an item
  evolution needs the item from an Emerald map (ball, hidden item, shop,
  script gift) or held by a wild Pokémon; a trade evolution needs the Linking
  Cord unless its held item works from the bag (`I_USE_EVO_HELD_ITEMS_FROM_BAG`).
  Evolutions tied to another region or map, or to an unreachable trigger, don't.
- **Breeding** at the Route 117 Day Care gives the bottom of the line (babies
  need incense only while `P_INCENSE_BREEDING` is below Gen 9); genderless and
  male-only parents wait for Ditto.
- **Hand-kept** (`sources.json`): the starters, Feebas, the roaming Latias and
  Latios, stage overrides for the fossils, the Johto starters and the Regis, and
  the event-ticket maps and Mystery Gift Altering Cave tables, which never count.

Mass outbreaks (`src/mass_outbreak.c`) are left out: they only bring Seedot,
Nuzleaf and Skitty, which are wild anyway.
