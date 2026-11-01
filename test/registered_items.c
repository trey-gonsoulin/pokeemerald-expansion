#include "global.h"
#include "bag_holds_everything.h"
#include "event_data.h"
#include "item.h"
#include "load_save.h"
#include "registered_items.h"
#include "test/test.h"

static void ClearBagAndRegisteredItems(void)
{
    ClearBag();
    ClearRegisteredItems();
}

TEST("Register items: toggling adds in order and removing keeps the slots packed")
{
    ASSUME(I_REGISTERED_ITEMS_COUNT >= 3);
    ClearBagAndRegisteredItems();

    EXPECT(ToggleRegisteredItem(ITEM_MACH_BIKE));
    EXPECT(ToggleRegisteredItem(ITEM_OLD_ROD));
    EXPECT(ToggleRegisteredItem(ITEM_ITEMFINDER));
    EXPECT_EQ(CountRegisteredItems(), 3);
    EXPECT_EQ(gSaveBlock1Ptr->registeredItem, ITEM_MACH_BIKE);
    EXPECT_EQ(GetRegisteredItem(1), ITEM_OLD_ROD);
    EXPECT_EQ(GetRegisteredItem(2), ITEM_ITEMFINDER);

    EXPECT(ToggleRegisteredItem(ITEM_MACH_BIKE));
    EXPECT_EQ(CountRegisteredItems(), 2);
    EXPECT_EQ(gSaveBlock1Ptr->registeredItem, ITEM_OLD_ROD);
    EXPECT_EQ(GetRegisteredItem(1), ITEM_ITEMFINDER);
    EXPECT_EQ(GetRegisteredItem(2), ITEM_NONE);
    EXPECT(!IsItemRegistered(ITEM_MACH_BIKE));
}

TEST("Register items: registering past I_REGISTERED_ITEMS_COUNT is refused")
{
    static const u16 items[] = { ITEM_MACH_BIKE, ITEM_OLD_ROD, ITEM_GOOD_ROD, ITEM_SUPER_ROD, ITEM_ITEMFINDER, ITEM_WAILMER_PAIL };
    u32 i;

    ASSUME(I_REGISTERED_ITEMS_COUNT < ARRAY_COUNT(items));
    ClearBagAndRegisteredItems();

    for (i = 0; i < I_REGISTERED_ITEMS_COUNT; i++)
        EXPECT(ToggleRegisteredItem(items[i]));
    EXPECT(!ToggleRegisteredItem(items[i]));
    EXPECT_EQ(CountRegisteredItems(), I_REGISTERED_ITEMS_COUNT);
    EXPECT(!IsItemRegistered(items[i]));
    EXPECT_EQ(GetRegisteredItem(I_REGISTERED_ITEMS_COUNT - 1), items[I_REGISTERED_ITEMS_COUNT - 1]);
}

TEST("Register items: IsItemRegistered finds slot 0 and the extra slots")
{
    ASSUME(I_REGISTERED_ITEMS_COUNT >= 2);
    ClearBagAndRegisteredItems();

    EXPECT(!IsItemRegistered(ITEM_NONE));
    ToggleRegisteredItem(ITEM_ACRO_BIKE);
    ToggleRegisteredItem(ITEM_SUPER_ROD);
    EXPECT(IsItemRegistered(ITEM_ACRO_BIKE));
    EXPECT(IsItemRegistered(ITEM_SUPER_ROD));
    EXPECT(!IsItemRegistered(ITEM_GOOD_ROD));
    EXPECT(!IsItemRegistered(ITEM_NONE));
}

TEST("Register items: SwapRegisteredBike swaps a bike in an extra slot")
{
    ASSUME(I_REGISTERED_ITEMS_COUNT >= 3);
    ClearBagAndRegisteredItems();

    ToggleRegisteredItem(ITEM_OLD_ROD);
    ToggleRegisteredItem(ITEM_MACH_BIKE);
    ToggleRegisteredItem(ITEM_ITEMFINDER);
    SwapRegisteredBike();
    EXPECT_EQ(GetRegisteredItem(0), ITEM_OLD_ROD);
    EXPECT_EQ(GetRegisteredItem(1), ITEM_ACRO_BIKE);
    EXPECT_EQ(GetRegisteredItem(2), ITEM_ITEMFINDER);
    SwapRegisteredBike();
    EXPECT_EQ(GetRegisteredItem(1), ITEM_MACH_BIKE);
}

TEST("Register items: RemoveUnownedRegisteredItems drops items no longer in the bag")
{
    ASSUME(I_REGISTERED_ITEMS_COUNT >= 4);
    ClearBagAndRegisteredItems();

    AddBagItem(ITEM_GOOD_ROD, 1);
    AddBagItem(ITEM_WAILMER_PAIL, 1);
    ToggleRegisteredItem(ITEM_MACH_BIKE);
    ToggleRegisteredItem(ITEM_GOOD_ROD);
    ToggleRegisteredItem(ITEM_ITEMFINDER);
    ToggleRegisteredItem(ITEM_WAILMER_PAIL);
    RemoveUnownedRegisteredItems();
    EXPECT_EQ(CountRegisteredItems(), 2);
    EXPECT_EQ(GetRegisteredItem(0), ITEM_GOOD_ROD);
    EXPECT_EQ(GetRegisteredItem(1), ITEM_WAILMER_PAIL);
    EXPECT_EQ(GetRegisteredItem(2), ITEM_NONE);
}

TEST("Register items: a save with only registeredItem set reads as one registered item")
{
    ClearBagAndRegisteredItems();

    gSaveBlock1Ptr->registeredItem = ITEM_MACH_BIKE;
    EXPECT_EQ(CountRegisteredItems(), 1);
    EXPECT(IsItemRegistered(ITEM_MACH_BIKE));
    EXPECT(ToggleRegisteredItem(ITEM_OLD_ROD));
    EXPECT_EQ(gSaveBlock1Ptr->registeredItem, ITEM_MACH_BIKE);
    EXPECT_EQ(GetRegisteredItem(1), ITEM_OLD_ROD);
}

TEST("Register items: an old save's Items pocket isn't read as registered items once converted")
{
    ASSUME(I_REGISTERED_ITEMS_COUNT >= 2);
    ASSUME(I_BAG_HOLDS_EVERYTHING);
    ClearBagAndRegisteredItems();

    // Before the conversion, the extra slots' bytes hold the old Items pocket
    gSaveBlock1Ptr->registeredItem = ITEM_MACH_BIKE;
    gSaveBlock1Ptr->bag.items[0] = (struct ItemSlot) { ITEM_POTION, 3 };
    gSaveBlock1Ptr->bag.items[1] = (struct ItemSlot) { ITEM_ANTIDOTE, 5 };
    FlagClear(I_BAG_CONVERTED_FLAG);

    ConvertSaveForBagHoldsEverything();

    EXPECT_EQ(CountRegisteredItems(), 1);
    EXPECT_EQ(GetRegisteredItem(0), ITEM_MACH_BIKE);
    EXPECT(!IsItemRegistered(ITEM_POTION));
}

TEST("Register items: the link bag backup restores every slot together")
{
    ASSUME(I_REGISTERED_ITEMS_COUNT >= 2);
    ClearBagAndRegisteredItems();

    ToggleRegisteredItem(ITEM_MACH_BIKE);
    ToggleRegisteredItem(ITEM_OLD_ROD);
    LoadPlayerBag();
    ToggleRegisteredItem(ITEM_MACH_BIKE);
    SavePlayerBag();
    EXPECT_EQ(CountRegisteredItems(), 2);
    EXPECT_EQ(GetRegisteredItem(0), ITEM_MACH_BIKE);
    EXPECT_EQ(GetRegisteredItem(1), ITEM_OLD_ROD);
}
