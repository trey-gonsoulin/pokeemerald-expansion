#include "global.h"
#include "registered_items.h"
#include "event_object_lock.h"
#include "event_object_movement.h"
#include "event_scripts.h"
#include "field_effect.h"
#include "field_player_avatar.h"
#include "item.h"
#include "item_icon.h"
#include "item_menu.h"
#include "list_menu.h"
#include "main.h"
#include "menu.h"
#include "script.h"
#include "script_menu.h"
#include "sound.h"
#include "sprite.h"
#include "task.h"
#include "window.h"
#include "constants/songs.h"

// I_REGISTERED_ITEMS_COUNT: slot 0 is the save's registeredItem, as in Gen 3, and the others are in the bytes
// of the old Items pocket that I_BAG_HOLDS_EVERYTHING frees (zeroed when a save is converted, and in a new game).
// The slots stay packed from 0, in the order the items were registered.
#if I_REGISTERED_ITEMS_COUNT > 1
#if !I_BAG_HOLDS_EVERYTHING
#error "I_REGISTERED_ITEMS_COUNT above 1 needs I_BAG_HOLDS_EVERYTHING: the extra slots take the old Items pocket's bytes"
#endif
STATIC_ASSERT(sizeof(((struct Bag *)0)->extraRegisteredItems) <= sizeof(((struct Bag *)0)->items), ExtraRegisteredItemsFitInOldItemsPocket);
STATIC_ASSERT(offsetof(struct Bag, keyItems) == sizeof(struct ItemSlot) * BAG_ITEMS_COUNT, ExtraRegisteredItemsKeepBagLayout);
#endif
STATIC_ASSERT(I_REGISTERED_ITEMS_COUNT >= 1, RegisteredItemsCountAtLeastOne);

#define TAG_REGISTERED_ITEM_ICON 5501

#define tListTaskId data[0]
#define tWindowId   data[1]
#define tReady      data[2]

static EWRAM_DATA enum Item sLastRegisteredItemUsed = ITEM_NONE;
static EWRAM_DATA struct ListMenuItem sMenuItems[I_REGISTERED_ITEMS_COUNT] = {0};
static EWRAM_DATA u8 sIconSpriteId = 0;
static EWRAM_DATA u8 sIconX = 0;
static EWRAM_DATA u8 sIconY = 0;

static const struct ListMenuTemplate sRegisteredItemsListTemplate =
{
    .item_X = 8,
    .upText_Y = 1,
    .cursorPal = 2,
    .fillValue = 1,
    .cursorShadowPal = 3,
    .lettersSpacing = 1,
    .scrollMultiple = LIST_NO_MULTIPLE_SCROLL,
    .fontId = FONT_NORMAL,
};

static u16 *GetRegisteredItemSlot(u32 slot)
{
#if I_REGISTERED_ITEMS_COUNT > 1
    if (slot != 0)
        return &gSaveBlock1Ptr->bag.extraRegisteredItems[slot - 1];
#endif
    return &gSaveBlock1Ptr->registeredItem;
}

enum Item GetRegisteredItem(u32 slot)
{
    if (slot >= I_REGISTERED_ITEMS_COUNT)
        return ITEM_NONE;
    return *GetRegisteredItemSlot(slot);
}

void SetRegisteredItem(u32 slot, enum Item item)
{
    if (slot < I_REGISTERED_ITEMS_COUNT)
        *GetRegisteredItemSlot(slot) = item;
}

u32 CountRegisteredItems(void)
{
    u32 count = 0;

    while (count < I_REGISTERED_ITEMS_COUNT && GetRegisteredItem(count) != ITEM_NONE)
        count++;
    return count;
}

static s32 FindRegisteredItemSlot(enum Item item)
{
    u32 i;

    for (i = 0; i < I_REGISTERED_ITEMS_COUNT && GetRegisteredItem(i) != ITEM_NONE; i++)
    {
        if (GetRegisteredItem(i) == item)
            return i;
    }
    return -1;
}

bool32 IsItemRegistered(enum Item item)
{
    return FindRegisteredItemSlot(item) >= 0;
}

void ClearRegisteredItems(void)
{
    u32 i;

    for (i = 0; i < I_REGISTERED_ITEMS_COUNT; i++)
        SetRegisteredItem(i, ITEM_NONE);
}

static void RemoveRegisteredItemSlot(u32 slot)
{
    u32 count = CountRegisteredItems();

    for (; slot + 1 < count; slot++)
        SetRegisteredItem(slot, GetRegisteredItem(slot + 1));
    SetRegisteredItem(count - 1, ITEM_NONE);
}

// Registers the item, or deselects it if it's registered. Returns FALSE when every slot is taken.
bool32 ToggleRegisteredItem(enum Item item)
{
    s32 slot = FindRegisteredItemSlot(item);
    u32 count;

    if (slot >= 0)
    {
        RemoveRegisteredItemSlot(slot);
        return TRUE;
    }
    count = CountRegisteredItems();
    if (count == I_REGISTERED_ITEMS_COUNT)
        return FALSE;
    SetRegisteredItem(count, item);
    return TRUE;
}

void RemoveUnownedRegisteredItems(void)
{
    u32 i, count = CountRegisteredItems(), kept = 0;

    for (i = 0; i < count; i++)
    {
        enum Item item = GetRegisteredItem(i);

        if (CheckBagHasItem(item, 1))
            SetRegisteredItem(kept++, item);
    }
    for (; kept < count; kept++)
        SetRegisteredItem(kept, ITEM_NONE);
}

// The Mauville Bike Shop's swap moves a registered bike's slot to the other bike
void SwapRegisteredBike(void)
{
    u32 i;

    for (i = 0; i < I_REGISTERED_ITEMS_COUNT; i++)
    {
        switch (GetRegisteredItem(i))
        {
        case ITEM_MACH_BIKE:
            SetRegisteredItem(i, ITEM_ACRO_BIKE);
            break;
        case ITEM_ACRO_BIKE:
            SetRegisteredItem(i, ITEM_MACH_BIKE);
            break;
        default:
            break;
        }
    }
}

#define tUsingRegisteredKeyItem data[3] // See usage in item_use.c

// The caller has locked the field controls
static void UseRegisteredItem(enum Item item)
{
    u8 taskId;

    sLastRegisteredItemUsed = item;
    gSpecialVar_ItemId = item;
    taskId = CreateTask(GetItemFieldFunc(item), 8);
    gTasks[taskId].tUsingRegisteredKeyItem = TRUE;
}

#undef tUsingRegisteredKeyItem

static void ShowRegisteredItemIcon(enum Item item)
{
    sIconSpriteId = AddItemIconSprite(TAG_REGISTERED_ITEM_ICON, TAG_REGISTERED_ITEM_ICON, item);
    if (sIconSpriteId != MAX_SPRITES)
    {
        gSprites[sIconSpriteId].oam.priority = 0;
        gSprites[sIconSpriteId].x = sIconX;
        gSprites[sIconSpriteId].y = sIconY;
    }
}

static void HideRegisteredItemIcon(void)
{
    // Frees the tiles and palette only if no object event uses them
    if (sIconSpriteId != MAX_SPRITES)
        FieldEffectFreeGraphicsResources(&gSprites[sIconSpriteId]);
    sIconSpriteId = MAX_SPRITES;
}

static void RegisteredItemsMenu_MoveCursor(s32 itemIndex, bool8 onInit, struct ListMenu *list)
{
    if (!onInit)
        PlaySE(SE_SELECT);
    HideRegisteredItemIcon();
    ShowRegisteredItemIcon(GetRegisteredItem(itemIndex));
}

static void CloseRegisteredItemsMenu(u8 taskId)
{
    s16 *data = gTasks[taskId].data;

    HideRegisteredItemIcon();
    DestroyListMenuTask(tListTaskId, NULL, NULL);
    ClearStdWindowAndFrame(tWindowId, TRUE);
    RemoveWindow(tWindowId);
    DestroyTask(taskId);
}

static void Task_RegisteredItemsMenu(u8 taskId)
{
    s16 *data = gTasks[taskId].data;
    s32 input;

    // The task first runs in the frame of the Select press that opened the menu
    if (!tReady)
    {
        tReady = TRUE;
        return;
    }

    // Select again steps down the list, and wraps
    if (JOY_NEW(SELECT_BUTTON))
    {
        struct ListMenu *list = (struct ListMenu *)gTasks[tListTaskId].data;
        u16 selected;

        ListMenuGetCurrentItemArrayId(tListTaskId, &selected);
        if (selected + 1 < list->template.totalItems)
            ListMenuChangeSelectionFull(list, TRUE, TRUE, 1, TRUE);
        else
            ListMenuChangeSelectionFull(list, TRUE, TRUE, selected, FALSE);
        return;
    }

    input = ListMenu_ProcessInput(tListTaskId);
    switch (input)
    {
    case LIST_NOTHING_CHOSEN:
        break;
    case LIST_CANCEL:
        PlaySE(SE_SELECT);
        CloseRegisteredItemsMenu(taskId);
        ScriptUnfreezeObjectEvents();
        UnlockPlayerFieldControls();
        break;
    default:
        PlaySE(SE_SELECT);
        CloseRegisteredItemsMenu(taskId);
        UseRegisteredItem(GetRegisteredItem(input));
        break;
    }
}

// A small menu in the top-right corner: the registered items' names, and the highlighted one's icon to their right
static void OpenRegisteredItemsMenu(u32 count)
{
    u32 i, textWidth, windowLeft, windowWidth, cursor = 0;
    s32 width = 0;
    u8 taskId, windowId;

    for (i = 0; i < count; i++)
    {
        enum Item item = GetRegisteredItem(i);

        sMenuItems[i].name = GetItemName(item);
        sMenuItems[i].id = i;
        width = DisplayTextAndGetWidth(sMenuItems[i].name, width);
        if (item == sLastRegisteredItemUsed)
            cursor = i;
    }
    textWidth = ConvertPixelWidthToTileWidth(width);
    windowWidth = textWidth + 3;
    windowLeft = DISPLAY_TILE_WIDTH - 2 - windowWidth; // The frame's left column; its right one is the screen's last
    sIconX = (windowLeft + 1 + textWidth) * 8 + 12;
    sIconY = 8 + count * 8;
    sIconSpriteId = MAX_SPRITES;

    PlaySE(SE_WIN_OPEN);
    LoadMessageBoxAndBorderGfx();
    windowId = CreateWindowFromRect(windowLeft, 0, windowWidth, count * 2);
    SetStandardWindowBorderStyle(windowId, FALSE);

    gMultiuseListMenuTemplate = sRegisteredItemsListTemplate;
    gMultiuseListMenuTemplate.windowId = windowId;
    gMultiuseListMenuTemplate.items = sMenuItems;
    gMultiuseListMenuTemplate.totalItems = count;
    gMultiuseListMenuTemplate.maxShowed = count;
    gMultiuseListMenuTemplate.moveCursorFunc = RegisteredItemsMenu_MoveCursor;

    taskId = CreateTask(Task_RegisteredItemsMenu, 8);
    gTasks[taskId].tWindowId = windowId;
    gTasks[taskId].tListTaskId = ListMenuInit(&gMultiuseListMenuTemplate, 0, cursor);
    CopyWindowToVram(windowId, COPYWIN_FULL);
}

// Select in the field (UseRegisteredKeyItemOnField): uses the registered item, or with several opens a menu of them
void UseRegisteredItemsOnField(void)
{
    u32 count;

    RemoveUnownedRegisteredItems();
    count = CountRegisteredItems();
    if (count == 0)
    {
        ScriptContext_SetupScript(EventScript_SelectWithoutRegisteredItem);
        return;
    }

    LockPlayerFieldControls();
    FreezeObjectEvents();
    PlayerFreeze();
    StopPlayerAvatar();
    if (count == 1)
        UseRegisteredItem(GetRegisteredItem(0));
    else
        OpenRegisteredItemsMenu(count);
}
