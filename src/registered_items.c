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
#include "main.h"
#include "menu.h"
#include "script.h"
#include "script_menu.h"
#include "sound.h"
#include "sprite.h"
#include "string_util.h"
#include "task.h"
#include "text.h"
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
STATIC_ASSERT(I_REGISTERED_ITEMS_COUNT >= 1 && I_REGISTERED_ITEMS_COUNT <= 9, RegisteredItemsCountIsOneDigit); // The selector prints "n/N"

#define TAG_REGISTERED_ITEM_ICON 5501
#define SELECTOR_SHOW_DELAY      12 // Frames Select is held before the selector shows
#define SELECTOR_TEXT_X          28 // The icon takes the window's first 24 pixels
#define SELECTOR_HEIGHT          4  // Tiles: the name, then the arrows and position

enum {
    SELECTOR_HOLDING, // Select held: the D-pad rotates, and a release without rotating uses the item
    SELECTOR_OPEN,    // Released after rotating: Select or A uses the item, B closes
};

#define tState        data[0]
#define tSlot         data[1]
#define tCount        data[2]
#define tWindowId     data[3]
#define tHeldFrames   data[4]
#define tRotated      data[5]
#define tIconSpriteId data[6]

static EWRAM_DATA enum Item sLastRegisteredItemUsed = ITEM_NONE;

static const u8 sText_SelectorPosition[] = _("{LEFT_ARROW}{STR_VAR_1}/{STR_VAR_2}{RIGHT_ARROW}");

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

static void BufferSelectorPosition(u32 slot, u32 count)
{
    ConvertIntToDecimalStringN(gStringVar1, slot + 1, STR_CONV_MODE_LEFT_ALIGN, 1);
    ConvertIntToDecimalStringN(gStringVar2, count, STR_CONV_MODE_LEFT_ALIGN, 1);
    StringExpandPlaceholders(gStringVar4, sText_SelectorPosition);
}

static void HideSelectorIcon(s16 *data)
{
    // Frees the tiles and palette only if no object event uses them
    if (tIconSpriteId != MAX_SPRITES)
        FieldEffectFreeGraphicsResources(&gSprites[tIconSpriteId]);
    tIconSpriteId = MAX_SPRITES;
}

// The selector, in the top-right corner like the start menu: one item at a time, its icon, name and position
static void DrawSelector(s16 *data)
{
    enum Item item = GetRegisteredItem(tSlot);
    u32 i, width, left;

    if (tWindowId == WINDOW_NONE)
    {
        // Wide enough for every name, so the window keeps its size as it rotates
        BufferSelectorPosition(tCount - 1, tCount);
        width = GetStringWidth(FONT_NORMAL, gStringVar4, 0);
        for (i = 0; i < tCount; i++)
            width = max(width, GetStringWidth(FONT_NORMAL, GetItemName(GetRegisteredItem(i)), 0));
        width = (SELECTOR_TEXT_X + width + 4 + 7) / 8;
        left = DISPLAY_TILE_WIDTH - 2 - width; // The frame's left column; its right one is the screen's last

        PlaySE(SE_WIN_OPEN);
        LoadMessageBoxAndBorderGfx();
        tWindowId = CreateWindowFromRect(left, 0, width, SELECTOR_HEIGHT);
        SetStandardWindowBorderStyle(tWindowId, FALSE);
    }

    FillWindowPixelBuffer(tWindowId, PIXEL_FILL(1));
    AddTextPrinterParameterized(tWindowId, FONT_NORMAL, GetItemName(item), SELECTOR_TEXT_X, 1, TEXT_SKIP_DRAW, NULL);
    BufferSelectorPosition(tSlot, tCount);
    AddTextPrinterParameterized(tWindowId, FONT_NORMAL, gStringVar4, SELECTOR_TEXT_X, 17, TEXT_SKIP_DRAW, NULL);
    CopyWindowToVram(tWindowId, COPYWIN_FULL);

    HideSelectorIcon(data);
    tIconSpriteId = AddItemIconSprite(TAG_REGISTERED_ITEM_ICON, TAG_REGISTERED_ITEM_ICON, item);
    if (tIconSpriteId != MAX_SPRITES)
    {
        gSprites[tIconSpriteId].oam.priority = 0;
        gSprites[tIconSpriteId].x = (GetWindowAttribute(tWindowId, WINDOW_TILEMAP_LEFT) * 8) + 12;
        gSprites[tIconSpriteId].y = 8 + SELECTOR_HEIGHT * 4;
    }
}

static void CloseSelector(u8 taskId)
{
    s16 *data = gTasks[taskId].data;

    if (tWindowId != WINDOW_NONE)
    {
        HideSelectorIcon(data);
        ClearStdWindowAndFrame(tWindowId, TRUE);
        RemoveWindow(tWindowId);
    }
    DestroyTask(taskId);
}

static void UseSelectedItem(u8 taskId)
{
    enum Item item = GetRegisteredItem(gTasks[taskId].tSlot);

    CloseSelector(taskId);
    UseRegisteredItem(item);
}

// Right or Down shows the next item, Left or Up the previous one, and both wrap
static bool32 TryRotateSelector(s16 *data)
{
    if (JOY_NEW(DPAD_RIGHT | DPAD_DOWN))
        tSlot = (tSlot + 1) % tCount;
    else if (JOY_NEW(DPAD_LEFT | DPAD_UP))
        tSlot = (tSlot + tCount - 1) % tCount;
    else
        return FALSE;
    PlaySE(SE_SELECT);
    DrawSelector(data);
    return TRUE;
}

// Works like the battle's last-used Ball (B_LAST_USED_BALL_CYCLE): a tap of Select uses the item shown, which starts
// as the last one used, and holding Select while pressing the D-pad rotates to another without using it
static void Task_RegisteredItemSelector(u8 taskId)
{
    s16 *data = gTasks[taskId].data;

    if (JOY_NEW(B_BUTTON))
    {
        PlaySE(SE_SELECT);
        CloseSelector(taskId);
        ScriptUnfreezeObjectEvents();
        UnlockPlayerFieldControls();
        return;
    }

    switch (tState)
    {
    case SELECTOR_HOLDING:
        if (!JOY_HELD(SELECT_BUTTON))
        {
            if (tRotated)
                tState = SELECTOR_OPEN;
            else
                UseSelectedItem(taskId);
        }
        else if (TryRotateSelector(data))
        {
            tRotated = TRUE;
        }
        else if (tWindowId == WINDOW_NONE && ++tHeldFrames >= SELECTOR_SHOW_DELAY)
        {
            DrawSelector(data);
        }
        break;
    case SELECTOR_OPEN:
        if (JOY_NEW(A_BUTTON))
        {
            PlaySE(SE_SELECT);
            UseSelectedItem(taskId);
        }
        else if (JOY_NEW(SELECT_BUTTON))
        {
            tState = SELECTOR_HOLDING;
            tRotated = FALSE;
        }
        else
        {
            TryRotateSelector(data);
        }
        break;
    }
}

static void StartRegisteredItemSelector(u32 count)
{
    u8 taskId = CreateTask(Task_RegisteredItemSelector, 8);
    s16 *data = gTasks[taskId].data;
    s32 slot = FindRegisteredItemSlot(sLastRegisteredItemUsed);

    tState = SELECTOR_HOLDING;
    tSlot = slot >= 0 ? slot : 0;
    tCount = count;
    tWindowId = WINDOW_NONE;
    tIconSpriteId = MAX_SPRITES;
}

// Select in the field (UseRegisteredKeyItemOnField): uses the registered item, or with several starts the selector
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
        StartRegisteredItemSelector(count);
}
