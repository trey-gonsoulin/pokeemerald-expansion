#include "global.h"
#include "test/battle.h"

// In a multi battle the partner has its own party, so a party index the
// player picks for an item must never be matched against the partner's battler.

MULTI_BATTLE_TEST("Multi battle item use: Potion on a benched mon heals that mon, not the partner")
{
    GIVEN {
        ASSUME(gItemsInfo[ITEM_POTION].battleUsage == EFFECT_ITEM_RESTORE_HP);
        PLAYER(SPECIES_WOBBUFFET);
        PLAYER(SPECIES_WYNAUT) { HP(50); MaxHP(100); }
        PARTNER(SPECIES_WOBBUFFET);
        PARTNER(SPECIES_WOBBUFFET) { HP(50); MaxHP(100); }
        OPPONENT_A(SPECIES_WOBBUFFET);
        OPPONENT_B(SPECIES_WOBBUFFET);
    } WHEN {
        TURN { SWITCH(playerRight, 1); }
        TURN { USE_ITEM(playerLeft, ITEM_POTION, partyIndex: 1); }
    } THEN {
        EXPECT_EQ(gBattlerPartyIndexes[B_BATTLER_2], 1);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_HP), 70);
    }
}

MULTI_BATTLE_TEST("Multi battle item use: Revive on a benched mon doesn't send it into the partner's empty slot")
{
    GIVEN {
        ASSUME(gItemsInfo[ITEM_REVIVE].battleUsage == EFFECT_ITEM_REVIVE);
        PLAYER(SPECIES_WOBBUFFET);
        PLAYER(SPECIES_WYNAUT) { HP(0); }
        PARTNER(SPECIES_WOBBUFFET) { HP(1); }
        OPPONENT_A(SPECIES_WOBBUFFET);
        OPPONENT_B(SPECIES_WOBBUFFET);
    } WHEN {
        TURN { MOVE(opponentLeft, MOVE_SCRATCH, target: playerRight); }
        TURN { USE_ITEM(playerLeft, ITEM_REVIVE, partyIndex: 1); }
        TURN { }
    } THEN {
        EXPECT_NE(GetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_HP), 0);
        EXPECT(gAbsentBattlerFlags & (1u << B_BATTLER_2));
    }
}

MULTI_BATTLE_TEST("Multi battle item use: Antidote on a benched mon doesn't cure the partner")
{
    GIVEN {
        ASSUME(gItemsInfo[ITEM_ANTIDOTE].battleUsage == EFFECT_ITEM_CURE_STATUS);
        PLAYER(SPECIES_WOBBUFFET);
        PLAYER(SPECIES_WYNAUT) { Status1(STATUS1_POISON); }
        PARTNER(SPECIES_WOBBUFFET);
        PARTNER(SPECIES_WOBBUFFET) { Status1(STATUS1_POISON); }
        OPPONENT_A(SPECIES_WOBBUFFET);
        OPPONENT_B(SPECIES_WOBBUFFET);
    } WHEN {
        TURN { SWITCH(playerRight, 1); }
        TURN { USE_ITEM(playerLeft, ITEM_ANTIDOTE, partyIndex: 1); }
    } THEN {
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_STATUS), STATUS1_NONE);
        EXPECT_EQ(playerRight->status1, STATUS1_POISON);
    }
}

MULTI_BATTLE_TEST("Multi battle item use: Ether on a benched mon doesn't change the partner's PP")
{
    GIVEN {
        ASSUME(gItemsInfo[ITEM_ETHER].battleUsage == EFFECT_ITEM_RESTORE_PP);
        // USE_ITEM looks the move up on the item user, so it needs Scratch in the same slot.
        PLAYER(SPECIES_WOBBUFFET) { Moves(MOVE_CELEBRATE, MOVE_SCRATCH); }
        PLAYER(SPECIES_WYNAUT) { MovesWithPP({MOVE_CELEBRATE, 10}, {MOVE_SCRATCH, 0}); }
        PARTNER(SPECIES_WOBBUFFET);
        PARTNER(SPECIES_WOBBUFFET) { MovesWithPP({MOVE_CELEBRATE, 10}, {MOVE_SCRATCH, 5}); }
        OPPONENT_A(SPECIES_WOBBUFFET);
        OPPONENT_B(SPECIES_WOBBUFFET);
    } WHEN {
        TURN { SWITCH(playerRight, 1); }
        TURN { USE_ITEM(playerLeft, ITEM_ETHER, partyIndex: 1, move: MOVE_SCRATCH); MOVE(playerRight, MOVE_CELEBRATE); }
    } THEN {
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_PP2), 10);
        EXPECT_EQ(playerRight->pp[1], 5);
    }
}
