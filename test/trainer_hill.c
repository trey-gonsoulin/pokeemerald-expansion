#include "global.h"
#include "event_data.h"
#include "item.h"
#include "trainer_hill.h"
#include "test/test.h"
#include "constants/trainer_hill.h"

#if FREE_TRAINER_HILL == FALSE
// A sub-12-minute Normal mode clear wins the TM Sunny Day grand prize
static void ClearNormalModeQuickly(void)
{
    FlagSet(FLAG_SYS_GAME_CLEAR);
    gSaveBlock1Ptr->trainerHill.mode = HILL_MODE_NORMAL;
    gSaveBlock1Ptr->trainerHill.timer = 0;
    gSaveBlock1Ptr->trainerHill.receivedPrize = FALSE;
    gSpecialVar_0x8004 = TRAINER_HILL_FUNC_GIVE_PRIZE;
    CallTrainerHillFunction();
}

TEST("Trainer Hill gives its TM grand prize when the player doesn't own it")
{
    ClearNormalModeQuickly();

    EXPECT_EQ(gSpecialVar_Result, 0);
    EXPECT(CheckBagHasItem(ITEM_TM_SUNNY_DAY, 1));
    EXPECT(!CheckBagHasItem(ITEM_PP_UP, 1));
}

// Separate tests rather than PARAMETRIZE: the save blocks are only cleared between tests
TEST("Trainer Hill gives a PP Up instead of a reusable TM in the bag")
{
    ASSUME(GetItemImportance(ITEM_TM_SUNNY_DAY));
    AddBagItem(ITEM_TM_SUNNY_DAY, 1);

    ClearNormalModeQuickly();

    EXPECT_EQ(gSpecialVar_Result, 0);
    EXPECT(CheckBagHasItem(ITEM_PP_UP, 1));
    EXPECT_EQ(CountTotalItemQuantityInBag(ITEM_TM_SUNNY_DAY), 1);
}

TEST("Trainer Hill gives a PP Up instead of a reusable TM in the PC")
{
    ASSUME(GetItemImportance(ITEM_TM_SUNNY_DAY));
    AddPCItem(ITEM_TM_SUNNY_DAY, 1);

    ClearNormalModeQuickly();

    EXPECT_EQ(gSpecialVar_Result, 0);
    EXPECT(CheckBagHasItem(ITEM_PP_UP, 1));
    EXPECT(!CheckBagHasItem(ITEM_TM_SUNNY_DAY, 1));
}
#endif // FREE_TRAINER_HILL
