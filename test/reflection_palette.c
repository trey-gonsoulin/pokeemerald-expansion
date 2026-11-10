#include "global.h"
#include "event_object_movement.h"
#include "field_effect_helpers.h"
#include "field_weather.h"
#include "palette.h"
#include "sprite.h"
#include "constants/event_objects.h"
#include "test/test.h"

#define TEST_PALETTE_TAG 0x7304
#define TEST_OBJECT_EVENT_ID 1

static struct ObjectEvent sSavedObjectEvent;

static void FillEverySpritePaletteSlot(void)
{
    u32 i;

    for (i = 0; IndexOfSpritePaletteTag(TAG_NONE) != 0xFF; i++)
        LoadSpritePaletteWithTag(gPlttBufferUnfaded, TEST_PALETTE_TAG + 1 + i);
}

// Creates an object event with a reflection (not on a bridge) and returns the reflection's sprite ID.
// With fillSlots, every palette slot left after the object's own is full when the reflection loads.
static u32 SetUpObjectWithReflection(u32 *mainSpriteId, bool32 fillSlots)
{
    struct ObjectEvent *objectEvent = &gObjectEvents[TEST_OBJECT_EVENT_ID];
    s32 reflectionSpriteId;

    ResetPreservedPalettesInWeather();
    *mainSpriteId = CreateObjectGraphicsSprite(OBJ_EVENT_GFX_PICHU_DOLL, SpriteCallbackDummy, 0, 0, 0);
    gSprites[*mainSpriteId].data[0] = TEST_OBJECT_EVENT_ID; // sReflectionObjEventId

    sSavedObjectEvent = *objectEvent;
    memset(objectEvent, 0, sizeof(*objectEvent));
    objectEvent->active = TRUE;
    objectEvent->hasReflection = TRUE;
    objectEvent->localId = 1;
    objectEvent->graphicsId = OBJ_EVENT_GFX_PICHU_DOLL;
    objectEvent->spriteId = *mainSpriteId;

    if (fillSlots)
        FillEverySpritePaletteSlot();
    // CreateCopySpriteAt takes the last free sprite
    for (reflectionSpriteId = MAX_SPRITES - 1; gSprites[reflectionSpriteId].inUse; reflectionSpriteId--)
        ;
    SetUpReflection(objectEvent, &gSprites[*mainSpriteId], FALSE);
    return reflectionSpriteId;
}

static void TearDownObjectWithReflection(u32 mainSpriteId, u32 reflectionSpriteId)
{
    if (gSprites[reflectionSpriteId].inUse)
        DestroySprite(&gSprites[reflectionSpriteId]);
    DestroySprite(&gSprites[mainSpriteId]);
    gObjectEvents[TEST_OBJECT_EVENT_ID] = sSavedObjectEvent;
    ResetPreservedPalettesInWeather();
}

TEST("Reflection palette: with no free slot a reflection's retry leaves the borrowed last slot loaded")
{
    u32 mainSpriteId, reflectionSpriteId, lastSlotTag, reflectionSlot, reflectionSlotTag;

    reflectionSpriteId = SetUpObjectWithReflection(&mainSpriteId, TRUE);
    lastSlotTag = GetSpritePaletteTagByPaletteNum(15); // No sprite uses it yet
    ASSUME(gSprites[reflectionSpriteId].inUse);
    ASSUME(gSprites[reflectionSpriteId].oam.paletteNum == 15);

    gSprites[reflectionSpriteId].callback(&gSprites[reflectionSpriteId]);
    reflectionSlot = gSprites[reflectionSpriteId].oam.paletteNum;
    reflectionSlotTag = GetSpritePaletteTagByPaletteNum(15);
    TearDownObjectWithReflection(mainSpriteId, reflectionSpriteId);

    EXPECT_EQ(reflectionSlot, 15);
    EXPECT_EQ(reflectionSlotTag, lastSlotTag);
}

TEST("Reflection palette: with no free slot a reflection reloads its own slot when its object's palette changes")
{
    u32 mainSpriteId, reflectionSpriteId, ownSlot, otherSlot, reflectionSlot, reflectionSlotTag;

    reflectionSpriteId = SetUpObjectWithReflection(&mainSpriteId, FALSE);
    ASSUME(gSprites[reflectionSpriteId].inUse);
    ownSlot = gSprites[reflectionSpriteId].oam.paletteNum;
    ASSUME(ownSlot != gSprites[mainSpriteId].oam.paletteNum);
    FillEverySpritePaletteSlot();
    otherSlot = IndexOfSpritePaletteTag(TEST_PALETTE_TAG + 1);
    ASSUME(otherSlot != 0xFF);

    gSprites[mainSpriteId].oam.paletteNum = otherSlot;
    gSprites[reflectionSpriteId].callback(&gSprites[reflectionSpriteId]);
    reflectionSlot = gSprites[reflectionSpriteId].oam.paletteNum;
    reflectionSlotTag = GetSpritePaletteTagByPaletteNum(ownSlot);
    TearDownObjectWithReflection(mainSpriteId, reflectionSpriteId);

    EXPECT_EQ(reflectionSlot, ownSlot);
    EXPECT_EQ(reflectionSlotTag, TEST_PALETTE_TAG + 1 + 0x0800); // PAL_TAG_REFLECTION_OFFSET
}
