#include "global.h"
#include "event_data.h"
#include "lottery_corner.h"
#include "pokemon.h"
#include "test/test.h"

TEST("Lottery Corner 3-digit prize is a Lucky Egg with the Gen 6 Exp. Share")
{
    ASSUME(I_EXP_SHARE_ITEM >= GEN_6);
    ZeroPlayerPartyMons();
    // The last three digits of the OT ID match the winning number, the fourth doesn't
    CreateMon(&gParties[B_TRAINER_PLAYER][0], SPECIES_WOBBUFFET, 5, 0, OTID_STRUCT_PRESET(345));
    gSpecialVar_Result = 12345;

    PickLotteryCornerTicket();

    EXPECT_EQ(gSpecialVar_0x8004, 2);
    EXPECT_EQ(gSpecialVar_0x8005, ITEM_LUCKY_EGG);
}
