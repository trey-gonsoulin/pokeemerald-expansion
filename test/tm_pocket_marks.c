#include "global.h"
#include "item.h"
#include "item_menu.h"
#include "party_menu.h"
#include "test/test.h"

// Every party slot holds the same Pokémon, so the mark doesn't depend on which one the Use was for
static void FillParty(u32 species, bool32 isEgg, enum Move knownMove)
{
    u32 i;

    ZeroPlayerPartyMons();
    for (i = 0; i < PARTY_SIZE; i++)
    {
        struct Pokemon *mon = &gParties[B_TRAINER_PLAYER][i];

        CreateMon(mon, species, 20, 0, OTID_STRUCT_PRESET(0));
        SetMonData(mon, MON_DATA_IS_EGG, &isEgg);
        if (knownMove != MOVE_NONE)
            SetMonMoveSlot(mon, knownMove, 0);
    }
}

static enum TMPocketMark GetMarkAt(u32 location, enum Item item)
{
    struct BagPosition savedPosition = gBagPosition;
    enum TMPocketMark mark;

    gBagPosition.location = location;
    mark = GetTMPocketMark(item);
    gBagPosition = savedPosition;
    return mark;
}

TEST("TM pocket marks: ABLE, NOT ABLE or LEARNED for the Pokémon, as the mart's ABLE count reads it")
{
    ASSUME(GetItemPocket(ITEM_TM_THUNDERBOLT) == POCKET_TM_HM);
    ASSUME(CanLearnTeachableMove(SPECIES_PIKACHU, MOVE_THUNDERBOLT));
    ASSUME(!CanLearnTeachableMove(SPECIES_MAGIKARP, MOVE_THUNDERBOLT));

    FillParty(SPECIES_PIKACHU, FALSE, MOVE_NONE);
    EXPECT_EQ(GetMarkAt(ITEMMENULOCATION_PARTY_USE, ITEM_TM_THUNDERBOLT), TM_POCKET_MARK_ABLE);
    FillParty(SPECIES_PIKACHU, FALSE, MOVE_THUNDERBOLT);
    EXPECT_EQ(GetMarkAt(ITEMMENULOCATION_PARTY_USE, ITEM_TM_THUNDERBOLT), TM_POCKET_MARK_LEARNED);
    FillParty(SPECIES_MAGIKARP, FALSE, MOVE_NONE);
    EXPECT_EQ(GetMarkAt(ITEMMENULOCATION_PARTY_USE, ITEM_TM_THUNDERBOLT), TM_POCKET_MARK_NOT_ABLE);
    FillParty(SPECIES_PIKACHU, TRUE, MOVE_NONE);
    EXPECT_EQ(GetMarkAt(ITEMMENULOCATION_PARTY_USE, ITEM_TM_THUNDERBOLT), TM_POCKET_MARK_NOT_ABLE);
}

TEST("TM pocket marks: only TMs and HMs in the bag opened from a Pokémon's Use")
{
    ASSUME(GetItemPocket(ITEM_POTION) != POCKET_TM_HM);
    FillParty(SPECIES_PIKACHU, FALSE, MOVE_NONE);
    EXPECT_EQ(GetMarkAt(ITEMMENULOCATION_PARTY_USE, ITEM_POTION), TM_POCKET_MARK_NONE);
    EXPECT_EQ(GetMarkAt(ITEMMENULOCATION_FIELD, ITEM_TM_THUNDERBOLT), TM_POCKET_MARK_NONE);
    EXPECT_EQ(GetMarkAt(ITEMMENULOCATION_PARTY, ITEM_TM_THUNDERBOLT), TM_POCKET_MARK_NONE);
    EXPECT_EQ(GetMarkAt(ITEMMENULOCATION_BATTLE, ITEM_TM_THUNDERBOLT), TM_POCKET_MARK_NONE);
}

TEST("TM pocket marks: every TM and HM name ends 2 px before the widest mark")
{
    u32 i;

    for (i = 1; i <= NUM_ALL_MACHINES; i++)
    {
        s32 gap = Test_GetTMPocketNameGap(GetTMHMItemId(i));
        EXPECT_GE(gap, 2);
    }
}
