#include "global.h"
#include "item.h"
#include "pokemon.h"
#include "pokemon_storage_system.h"
#include "test/test.h"
#include "constants/items.h"

static void CreateHoldingMon(struct Pokemon *mon, enum Item item)
{
    CreateMon(mon, SPECIES_WOBBUFFET, 50, 0, OTID_STRUCT_PRESET(0));
    SetMonData(mon, MON_DATA_HELD_ITEM, &item);
}

TEST("PC release: a party Pokemon under the cursor returns its held item")
{
    ASSUME(OW_PC_RELEASE_ITEM >= GEN_8);
    CreateHoldingMon(&gParties[B_TRAINER_PLAYER][0], ITEM_NONE);
    CreateHoldingMon(&gParties[B_TRAINER_PLAYER][1], ITEM_LEFTOVERS);

    Test_RemoveReleasedMon(NULL, TRUE, 1);

    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_SPECIES), SPECIES_NONE);
    EXPECT_EQ(CountTotalItemQuantityInBag(ITEM_LEFTOVERS), 1);
}

TEST("PC release: a box Pokemon under the cursor returns its held item")
{
    struct Pokemon mon;

    ASSUME(OW_PC_RELEASE_ITEM >= GEN_8);
    CreateHoldingMon(&mon, ITEM_LEFTOVERS);
    SetBoxMonAt(StorageGetCurrentBox(), 0, &mon.box);

    Test_RemoveReleasedMon(NULL, FALSE, 0);

    EXPECT_EQ(GetBoxMonDataAt(StorageGetCurrentBox(), 0, MON_DATA_SPECIES), SPECIES_NONE);
    EXPECT_EQ(CountTotalItemQuantityInBag(ITEM_LEFTOVERS), 1);
}

TEST("PC release: the Pokemon in the cursor's hand returns its held item")
{
    struct Pokemon mon;

    ASSUME(OW_PC_RELEASE_ITEM >= GEN_8);
    CreateHoldingMon(&mon, ITEM_LEFTOVERS);

    Test_RemoveReleasedMon(&mon, FALSE, 0);

    EXPECT_EQ(CountTotalItemQuantityInBag(ITEM_LEFTOVERS), 1);
}
