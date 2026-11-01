#include "global.h"
#include "party_menu.h"
#include "shop.h"
#include "string_util.h"
#include "strings.h"
#include "text.h"
#include "test/test.h"

TEST("Mart TM marks: the ABLE count leaves out Eggs and Pokémon that know the move or can't learn it")
{
    struct Pokemon *party = gParties[B_TRAINER_PLAYER];
    bool32 isEgg = TRUE;
    u32 partyCount = 0;

    ASSUME(CanLearnTeachableMove(SPECIES_PIKACHU, MOVE_THUNDERBOLT));
    ASSUME(!CanLearnTeachableMove(SPECIES_MAGIKARP, MOVE_THUNDERBOLT));
    ZeroPlayerPartyMons();
    CreateMon(&party[0], SPECIES_PIKACHU, 5, 0, OTID_STRUCT_PRESET(0));
    SetMonData(&party[0], MON_DATA_IS_EGG, &isEgg);
    CreateMon(&party[1], SPECIES_PIKACHU, 20, 0, OTID_STRUCT_PRESET(0));
    CreateMon(&party[2], SPECIES_PIKACHU, 20, 0, OTID_STRUCT_PRESET(0));
    SetMonMoveSlot(&party[2], MOVE_THUNDERBOLT, 0);
    CreateMon(&party[3], SPECIES_MAGIKARP, 20, 0, OTID_STRUCT_PRESET(0));

    EXPECT_EQ(GetTeachMoveStatus(&party[0], MOVE_THUNDERBOLT), CANNOT_LEARN_MOVE_IS_EGG);
    EXPECT_EQ(GetTeachMoveStatus(&party[1], MOVE_THUNDERBOLT), CAN_LEARN_MOVE);
    EXPECT_EQ(GetTeachMoveStatus(&party[2], MOVE_THUNDERBOLT), ALREADY_KNOWS_MOVE);
    EXPECT_EQ(GetTeachMoveStatus(&party[3], MOVE_THUNDERBOLT), CANNOT_LEARN_MOVE);
    EXPECT_EQ(CountPartyMonsAbleToLearn(MOVE_THUNDERBOLT, &partyCount), 1);
    EXPECT_EQ(partyCount, 3);
}

TEST("Mart TM marks: the ABLE count fits the IN BAG count's window")
{
    ConvertIntToDecimalStringN(gStringVar1, PARTY_SIZE, STR_CONV_MODE_LEFT_ALIGN, 1);
    ConvertIntToDecimalStringN(gStringVar2, PARTY_SIZE, STR_CONV_MODE_LEFT_ALIGN, 1);
    StringExpandPlaceholders(gStringVar4, gText_AbleVar1OfVar2);
    EXPECT_LE(GetStringWidth(FONT_NORMAL, gStringVar4, 0), SHOP_IN_BAG_HOVER_WIDTH * 8);
}
