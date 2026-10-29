#include "global.h"
#include "battle.h"
#include "party_menu.h"
#include "pokemon.h"
#include "test/test.h"

#define TEST_MENU_DIR_DOWN     1
#define TEST_MENU_DIR_UP      -1
#define TEST_MENU_DIR_RIGHT    2

static void SetTestPartySize(enum BattleTrainer trainer, u8 partySize)
{
    for (u32 i = 0; i < PARTY_SIZE; i++)
        ZeroMonData(&gParties[trainer][i]);

    for (u32 i = 0; i < partySize; i++)
        CreateMon(&gParties[trainer][i], SPECIES_WOBBUFFET, 50, 0, OTID_STRUCT_PRESET(0));

    gPartiesCount[trainer] = partySize;
}

TEST("Full multi partner party menu stops down navigation at partner party count")
{
    SetTestPartySize(B_TRAINER_PLAYER, PARTY_SIZE);
    SetTestPartySize(B_TRAINER_PARTNER, 2);
    gPartyMenu.layout = PARTY_LAYOUT_MULTI_FULL_PARTNER;

    EXPECT_EQ(Test_UpdatePartySelectionSingleLayout(1, TEST_MENU_DIR_DOWN, FALSE, 0), PARTY_SIZE + 1);
}

TEST("Full multi partner party menu allows down navigation through partner party count")
{
    SetTestPartySize(B_TRAINER_PLAYER, 2);
    SetTestPartySize(B_TRAINER_PARTNER, PARTY_SIZE);
    gPartyMenu.layout = PARTY_LAYOUT_MULTI_FULL_PARTNER;

    EXPECT_EQ(Test_UpdatePartySelectionSingleLayout(1, TEST_MENU_DIR_DOWN, FALSE, 0), 2);
}

TEST("Full multi partner party menu wraps cancel up to partner party count")
{
    SetTestPartySize(B_TRAINER_PLAYER, PARTY_SIZE);
    SetTestPartySize(B_TRAINER_PARTNER, 2);
    gPartyMenu.layout = PARTY_LAYOUT_MULTI_FULL_PARTNER;

    EXPECT_EQ(Test_UpdatePartySelectionSingleLayout(PARTY_SIZE + 1, TEST_MENU_DIR_UP, FALSE, 0), 1);
}

TEST("Party menu Switch resets the follower steps only when the leader changes")
{
    enum { LEAD_LIVE, LEAD_EGG, LEAD_FAINTED } lead = LEAD_LIVE;
    u32 slot1 = 0, slot2 = 0, steps;
    bool32 resets = FALSE;

    PARAMETRIZE { lead = LEAD_LIVE;    slot1 = 2; slot2 = 0; resets = TRUE; }
    PARAMETRIZE { lead = LEAD_LIVE;    slot1 = 0; slot2 = 3; resets = TRUE; }
    PARAMETRIZE { lead = LEAD_LIVE;    slot1 = 1; slot2 = 2; resets = FALSE; }
    PARAMETRIZE { lead = LEAD_LIVE;    slot1 = 0; slot2 = 0; resets = FALSE; }
    PARAMETRIZE { lead = LEAD_EGG;     slot1 = 1; slot2 = 2; resets = TRUE; }
    PARAMETRIZE { lead = LEAD_EGG;     slot1 = 2; slot2 = 3; resets = FALSE; }
    PARAMETRIZE { lead = LEAD_FAINTED; slot1 = 0; slot2 = 1; resets = FALSE; }

    SetTestPartySize(B_TRAINER_PLAYER, PARTY_SIZE);
    for (u32 i = 0; i < PARTY_SIZE; i++)
        CalculateMonStats(&gParties[B_TRAINER_PLAYER][i]); // CreateMon leaves HP at 0
    if (lead == LEAD_EGG)
    {
        bool32 isEgg = TRUE;
        SetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_IS_EGG, &isEgg);
    }
    else if (lead == LEAD_FAINTED)
    {
        u32 hp = 0;
        SetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_HP, &hp);
    }
    gFollowerSteps = 100;
    Test_SwapPlayerPartySlots(slot1, slot2);
    steps = gFollowerSteps;
    gFollowerSteps = 0;

    EXPECT_EQ(steps, resets ? 0 : 100);
}
