#include "global.h"
#include "test/battle.h"

// With I_EXP_SHARE_ITEM >= GEN_6 the Exp. Share is a key item that can't be given to a Pokemon,
// but a Pokemon that already holds one still gets the hold effect.
// In these wild battles under WITH_EXP_SHARE_CONFIGS, every participant gains expYield * level / 7 (Cmd_getexp,
// no level scaling, over-level penalty, unevolved or affection boost) and every Exp. Share mon gains half that.
// Cmd_getexp reads the raw B_SPLIT_EXP macro when it decides whether a sent-in holder also gets the share, hence the ASSUME.
#define WITH_EXP_SHARE_CONFIGS()                        \
    ASSUME(B_SPLIT_EXP >= GEN_6);                       \
    WITH_CONFIG(B_SPLIT_EXP, GEN_6);                    \
    WITH_CONFIG(B_SCALED_EXP, GEN_3);                   \
    WITH_CONFIG(B_EXP_OVERLEVEL_PENALTY, FALSE);        \
    WITH_CONFIG(B_UNEVOLVED_EXP_MULTIPLIER, GEN_3);     \
    WITH_CONFIG(B_AFFECTION_MECHANICS, FALSE)
#define EXP_YIELD(species, level) (gSpeciesInfo[species].expYield * (level) / 7)
#define EXP_AT_LEVEL(species, level) (gExperienceTables[gSpeciesInfo[species].growthRate][level])

WILD_BATTLE_TEST("Exp Share(held) gives Experience to mons which did not participate in battle")
{
    enum Item item = ITEM_NONE;

    PARAMETRIZE { item = ITEM_NONE; }
    PARAMETRIZE { item = ITEM_EXP_SHARE; }

    GIVEN {
        PLAYER(SPECIES_WOBBUFFET);
        PLAYER(SPECIES_WYNAUT) { Level(40); Item(item); }
        OPPONENT(SPECIES_CATERPIE) { Level(10); HP(1); }
    } WHEN {
        TURN { MOVE(player, MOVE_SCRATCH); }
    } SCENE {
        MESSAGE("Wobbuffet used Scratch!");
        MESSAGE("The wild Caterpie fainted!");
        // This message should appear only for gen6> exp share.
        NOT MESSAGE("The rest of your team gained Exp. Points thanks to the Exp. Share!");
    } THEN {
        if (item == ITEM_EXP_SHARE)
            EXPECT_GT(GetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_EXP), gExperienceTables[gSpeciesInfo[SPECIES_WYNAUT].growthRate][40]);
        else
            EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_EXP), gExperienceTables[gSpeciesInfo[SPECIES_WYNAUT].growthRate][40]);
    }
}

WILD_BATTLE_TEST("Exp Share(held) gives a benched holder half the experience and nothing to the rest of the bench")
{
    GIVEN {
        WITH_EXP_SHARE_CONFIGS();
        PLAYER(SPECIES_WOBBUFFET) { Level(20); }
        PLAYER(SPECIES_WYNAUT) { Level(20); Item(ITEM_EXP_SHARE); }
        PLAYER(SPECIES_WYNAUT) { Level(25); }
        OPPONENT(SPECIES_CATERPIE) { Level(10); HP(1); }
    } WHEN {
        TURN { MOVE(player, MOVE_SCRATCH); }
    } SCENE {
        MESSAGE("The wild Caterpie fainted!");
        NOT MESSAGE("The rest of your team gained Exp. Points thanks to the Exp. Share!");
    } THEN {
        u32 gain = EXP_YIELD(SPECIES_CATERPIE, 10);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WOBBUFFET, 20) + gain);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WYNAUT, 20) + gain / 2);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][2], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WYNAUT, 25));
    }
}

WILD_BATTLE_TEST("Exp Share(held) gives no extra experience to a holder that was sent in")
{
    GIVEN {
        WITH_EXP_SHARE_CONFIGS();
        PLAYER(SPECIES_WOBBUFFET) { Level(20); Item(ITEM_EXP_SHARE); }
        PLAYER(SPECIES_WYNAUT) { Level(20); }
        OPPONENT(SPECIES_CATERPIE) { Level(10); HP(1); }
    } WHEN {
        TURN { MOVE(player, MOVE_SCRATCH); }
    } SCENE {
        MESSAGE("The wild Caterpie fainted!");
        NOT MESSAGE("The rest of your team gained Exp. Points thanks to the Exp. Share!");
    } THEN {
        u32 gain = EXP_YIELD(SPECIES_CATERPIE, 10);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WOBBUFFET, 20) + gain);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WYNAUT, 20));
    }
}

WILD_BATTLE_TEST("Exp Share(held) with the Gen 6 Exp. Share on gives every mon the same experience as without the held item")
{
    GIVEN {
        ASSUME(I_EXP_SHARE_FLAG > TEMP_FLAGS_END);
        ASSUME(EXP_YIELD(SPECIES_CATERPIE, 10) / 2 == 27);
        WITH_EXP_SHARE_CONFIGS();
        FLAG_SET(I_EXP_SHARE_FLAG);
        PLAYER(SPECIES_WOBBUFFET) { Level(20); Item(ITEM_EXP_SHARE); }
        PLAYER(SPECIES_WYNAUT) { Level(20); Item(ITEM_EXP_SHARE); }
        PLAYER(SPECIES_WYNAUT) { Level(25); }
        OPPONENT(SPECIES_CATERPIE) { Level(10); HP(1); }
    } WHEN {
        TURN { MOVE(player, MOVE_SCRATCH); }
    } SCENE {
        MESSAGE("The wild Caterpie fainted!");
        EXPERIENCE_BAR(player);
        // The benched holder prints its own "gained" message, so the team message comes from the other benched mon.
        MESSAGE("Wynaut gained 27 Exp. Points!");
        MESSAGE("The rest of your team gained Exp. Points thanks to the Exp. Share!");
        NOT MESSAGE("The rest of your team gained Exp. Points thanks to the Exp. Share!");
    } THEN {
        u32 gain = EXP_YIELD(SPECIES_CATERPIE, 10);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WOBBUFFET, 20) + gain);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WYNAUT, 20) + gain / 2);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][2], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WYNAUT, 25) + gain / 2);
    }
}
