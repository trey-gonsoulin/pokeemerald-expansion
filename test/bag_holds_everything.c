#include "global.h"
#include "bag_holds_everything.h"
#include "event_data.h"
#include "item.h"
#include "player_pc.h"
#include "test/test.h"

// Fills ids with the first count items of the pocket, skipping skipItem; returns how many it found.
static u32 FindPocketItems(enum Pocket pocket, enum Item *ids, u32 count, enum Item skipItem)
{
    u32 found = 0;
    enum Item itemId;

    for (itemId = ITEM_NONE + 1; itemId < ITEMS_COUNT && found < count; itemId++)
    {
        if (GetItemPocket(itemId) == pocket && itemId != skipItem)
            ids[found++] = itemId;
    }
    return found;
}

static bool32 IsSlotArrayEmpty(const struct ItemSlot *slots, u32 count)
{
    u32 i;

    for (i = 0; i < count; i++)
    {
        if (slots[i].itemId != ITEM_NONE || slots[i].quantity != 0)
            return FALSE;
    }
    return TRUE;
}

TEST("Bag holds everything: the Items pocket holds BAG_ITEMS_ALL_COUNT kinds")
{
    enum Item ids[BAG_ITEMS_ALL_COUNT + 1];
    u32 i;

    ASSUME(I_BAG_HOLDS_EVERYTHING);
    ASSUME(FindPocketItems(POCKET_ITEMS, ids, ARRAY_COUNT(ids), ITEM_NONE) == ARRAY_COUNT(ids));
    ClearBag();

    EXPECT_EQ(gBagPockets[POCKET_ITEMS].itemSlots, gSaveBlock1Ptr->bagItems);
    EXPECT_EQ((u32)gBagPockets[POCKET_ITEMS].capacity, BAG_ITEMS_ALL_COUNT);
    for (i = 0; i < BAG_ITEMS_ALL_COUNT; i++)
        EXPECT(AddBagItem(ids[i], i % 7 + 1));
    EXPECT(!AddBagItem(ids[BAG_ITEMS_ALL_COUNT], 1));
    EXPECT(CheckBagHasItem(ids[BAG_ITEMS_ALL_COUNT - 1], 1));
    EXPECT(IsSlotArrayEmpty(gSaveBlock1Ptr->bag.items, BAG_ITEMS_COUNT));

    // Removing one from the middle compacts the pocket and frees a slot.
    EXPECT(RemoveBagItem(ids[100], 100 % 7 + 1));
    EXPECT_EQ(GetBagItemId(POCKET_ITEMS, 100), ids[101]);
    EXPECT_EQ(GetBagItemId(POCKET_ITEMS, BAG_ITEMS_ALL_COUNT - 1), ITEM_NONE);
    EXPECT(AddBagItem(ids[BAG_ITEMS_ALL_COUNT], 1));
    ClearBag();
}

TEST("Bag holds everything: an old save's Items pocket and Item Storage move into the bag once")
{
    u32 savedKey = gSaveBlock2Ptr->encryptionKey;
    u16 key = 0xA5C3;
    u32 i;

    ASSUME(I_BAG_HOLDS_EVERYTHING);
    ASSUME(GetItemPocket(ITEM_ANTIDOTE) == POCKET_ITEMS);
    ASSUME(GetItemPocket(ITEM_POTION) == POCKET_ITEMS);
    ASSUME(GetItemPocket(ITEM_GREAT_BALL) == POCKET_POKE_BALLS);
    ASSUME(GetItemPocket(ITEM_TM05) == POCKET_TM_HM);
    ASSUME(GetItemPocket(ITEM_ORAN_BERRY) == POCKET_BERRIES);

    // An old save: the Items pocket in bag.items under the save's key, ramScript's bytes where the pocket now lives,
    // and Item Storage unkeyed.
    gSaveBlock2Ptr->encryptionKey = key;
    ClearBag();
    memset(gSaveBlock1Ptr->pcItems, 0, sizeof(gSaveBlock1Ptr->pcItems));
    memset(gSaveBlock1Ptr->bagItems, 0xAB, sizeof(gSaveBlock1Ptr->bagItems));
    gSaveBlock1Ptr->bag.items[0] = (struct ItemSlot) { ITEM_ANTIDOTE, 7 ^ key };
    gSaveBlock1Ptr->bag.items[1] = (struct ItemSlot) { ITEM_POTION, 3 ^ key };
    gSaveBlock1Ptr->pcItems[0] = (struct ItemSlot) { ITEM_ORAN_BERRY, 6 };
    gSaveBlock1Ptr->pcItems[1] = (struct ItemSlot) { ITEM_POTION, 10 };
    gSaveBlock1Ptr->pcItems[2] = (struct ItemSlot) { ITEM_GREAT_BALL, 4 };
    gSaveBlock1Ptr->pcItems[3] = (struct ItemSlot) { ITEM_TM05, 1 };
    FlagClear(I_BAG_CONVERTED_FLAG);

    ConvertSaveForBagHoldsEverything();

    EXPECT(FlagGet(I_BAG_CONVERTED_FLAG));
    EXPECT_EQ(GetBagItemId(POCKET_ITEMS, 0), ITEM_ANTIDOTE);
    EXPECT_EQ(GetBagItemQuantity(POCKET_ITEMS, 0), 7);
    EXPECT_EQ(GetBagItemId(POCKET_ITEMS, 1), ITEM_POTION);
    EXPECT_EQ(GetBagItemQuantity(POCKET_ITEMS, 1), 13);
    for (i = 2; i < BAG_ITEMS_ALL_COUNT; i++)
        EXPECT_EQ(GetBagItemId(POCKET_ITEMS, i), ITEM_NONE);
    EXPECT_EQ(CountTotalItemQuantityInBag(ITEM_GREAT_BALL), 4);
    EXPECT_EQ(CountTotalItemQuantityInBag(ITEM_TM05), 1);
    EXPECT_EQ(CountTotalItemQuantityInBag(ITEM_ORAN_BERRY), 6);
    EXPECT(IsSlotArrayEmpty(gSaveBlock1Ptr->bag.items, BAG_ITEMS_COUNT));
    EXPECT_EQ(CountUsedPCItemSlots(), 0);

    // A second run changes nothing.
    gSaveBlock1Ptr->pcItems[0] = (struct ItemSlot) { ITEM_POTION, 2 };
    ConvertSaveForBagHoldsEverything();
    EXPECT_EQ(CountTotalItemQuantityInBag(ITEM_POTION), 13);
    EXPECT_EQ(gSaveBlock1Ptr->pcItems[0].itemId, ITEM_POTION);

    ClearBag();
    memset(gSaveBlock1Ptr->pcItems, 0, sizeof(gSaveBlock1Ptr->pcItems));
    gSaveBlock2Ptr->encryptionKey = savedKey;
}

TEST("Bag holds everything: what the bag can't take stays in Item Storage")
{
    enum Item balls[BAG_POKEBALLS_COUNT + 1];

    ASSUME(I_BAG_HOLDS_EVERYTHING);
    ASSUME(FindPocketItems(POCKET_POKE_BALLS, balls, ARRAY_COUNT(balls), ITEM_NONE) == ARRAY_COUNT(balls));
    ClearBag();
    memset(gSaveBlock1Ptr->pcItems, 0, sizeof(gSaveBlock1Ptr->pcItems));
    for (u32 i = 0; i < BAG_POKEBALLS_COUNT; i++)
        EXPECT(AddBagItem(balls[i], 1));
    gSaveBlock1Ptr->pcItems[0] = (struct ItemSlot) { ITEM_POTION, 5 };
    gSaveBlock1Ptr->pcItems[1] = (struct ItemSlot) { balls[BAG_POKEBALLS_COUNT], 2 };
    FlagClear(I_BAG_CONVERTED_FLAG);

    ConvertSaveForBagHoldsEverything();

    EXPECT_EQ(CountTotalItemQuantityInBag(ITEM_POTION), 5);
    EXPECT_EQ(gSaveBlock1Ptr->pcItems[0].itemId, balls[BAG_POKEBALLS_COUNT]);
    EXPECT_EQ(gSaveBlock1Ptr->pcItems[0].quantity, 2);
    EXPECT_EQ(CountUsedPCItemSlots(), 1);

    ClearBag();
    memset(gSaveBlock1Ptr->pcItems, 0, sizeof(gSaveBlock1Ptr->pcItems));
}

TEST("Bag holds everything: a new game's Potion goes in the bag")
{
    ASSUME(I_BAG_HOLDS_EVERYTHING);
    ClearBag();
    FlagClear(I_BAG_CONVERTED_FLAG);

    NewGameInitPCItems();

    EXPECT_EQ(CountTotalItemQuantityInBag(ITEM_POTION), 1);
    EXPECT_EQ(CountUsedPCItemSlots(), 0);
    EXPECT(FlagGet(I_BAG_CONVERTED_FLAG));
    ClearBag();
}
