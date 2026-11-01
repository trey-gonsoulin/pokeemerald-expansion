#include "global.h"
#include "bag_holds_everything.h"
#include "event_data.h"
#include "item.h"

// I_BAG_HOLDS_EVERYTHING: a save from before it keeps the Items pocket in bag.items, and
// ramScript's bytes where the pocket now lives. Move the pocket there, then empty Item Storage
// into the bag. Whatever the bag can't take stays in Item Storage, which the PC then still shows.
void ConvertSaveForBagHoldsEverything(void)
{
#if I_BAG_HOLDS_EVERYTHING
    u32 i;
    struct ItemSlot *pcItems = gSaveBlock1Ptr->pcItems;

    if (FlagGet(I_BAG_CONVERTED_FLAG))
        return;

    // The slots move as they are: their quantities are already under the save's key
    memset(gSaveBlock1Ptr->bagItems, 0, sizeof(gSaveBlock1Ptr->bagItems));
    memcpy(gSaveBlock1Ptr->bagItems, gSaveBlock1Ptr->bag.items, sizeof(gSaveBlock1Ptr->bag.items));
    memset(gSaveBlock1Ptr->bag.items, 0, sizeof(gSaveBlock1Ptr->bag.items));

    for (i = 0; i < PC_ITEMS_COUNT; i++)
    {
        if (pcItems[i].itemId != ITEM_NONE && AddBagItem(pcItems[i].itemId, pcItems[i].quantity))
        {
            pcItems[i].itemId = ITEM_NONE;
            pcItems[i].quantity = 0;
        }
    }
    CompactPCItems();
    FlagSet(I_BAG_CONVERTED_FLAG);
#endif
}
