#include "global.h"
#include "event_data.h"
#include "item.h"
#include "test/overworld_script.h"
#include "test/test.h"

// The rule Trainer Hill, the Game Corner and the Quiz Lady share (#263)

TEST("Owned prize: a TM the player doesn't own stays the prize")
{
    EXPECT(!IsPrizeAlreadyOwned(ITEM_TM_THUNDERBOLT));
    EXPECT_EQ(GetPrizeOrPPUpIfOwned(ITEM_TM_THUNDERBOLT), ITEM_TM_THUNDERBOLT);
}

TEST("Owned prize: a reusable TM in the bag becomes a PP Up")
{
    ASSUME(GetItemImportance(ITEM_TM_THUNDERBOLT));
    AddBagItem(ITEM_TM_THUNDERBOLT, 1);

    EXPECT(IsPrizeAlreadyOwned(ITEM_TM_THUNDERBOLT));
    EXPECT_EQ(GetPrizeOrPPUpIfOwned(ITEM_TM_THUNDERBOLT), ITEM_PP_UP);
}

TEST("Owned prize: a reusable TM in the PC becomes a PP Up")
{
    ASSUME(GetItemImportance(ITEM_TM_THUNDERBOLT));
    AddPCItem(ITEM_TM_THUNDERBOLT, 1);

    EXPECT_EQ(GetPrizeOrPPUpIfOwned(ITEM_TM_THUNDERBOLT), ITEM_PP_UP);
}

TEST("Owned prize: an owned item that isn't important stays the prize")
{
    ASSUME(!GetItemImportance(ITEM_POTION));
    AddBagItem(ITEM_POTION, 1);

    EXPECT_EQ(GetPrizeOrPPUpIfOwned(ITEM_POTION), ITEM_POTION);
}

TEST("Owned prize: the Game Corner's special reads the prize in VAR_0x8004")
{
    ASSUME(GetItemImportance(ITEM_TM_ICE_BEAM));

    gSpecialVar_0x8004 = ITEM_TM_ICE_BEAM;
    RUN_OVERWORLD_SCRIPT( specialvar VAR_RESULT, ScriptIsPrizeAlreadyOwned; );
    EXPECT_EQ(gSpecialVar_Result, FALSE);

    AddBagItem(ITEM_TM_ICE_BEAM, 1);
    gSpecialVar_0x8004 = ITEM_TM_ICE_BEAM;
    RUN_OVERWORLD_SCRIPT( specialvar VAR_RESULT, ScriptIsPrizeAlreadyOwned; );
    EXPECT_EQ(gSpecialVar_Result, TRUE);
}
