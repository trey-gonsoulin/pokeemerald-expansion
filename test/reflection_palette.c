#include "global.h"
#include "event_object_movement.h"
#include "field_effect_helpers.h"
#include "field_weather.h"
#include "palette.h"
#include "sprite.h"
#include "constants/event_objects.h"
#include "constants/metatile_behaviors.h"
#include "test/test.h"

#define TEST_PALETTE_TAG 0x7304
#define TEST_OBJECT_EVENT_ID 1
#define HIGH_BRIDGE_PAL_TAG 0x3010 // src/field_effect_helpers.c

static struct ObjectEvent sSavedObjectEvent;

static void FillEverySpritePaletteSlot(void)
{
    u32 i;

    for (i = 0; IndexOfSpritePaletteTag(TAG_NONE) != 0xFF; i++)
        LoadSpritePaletteWithTag(gPlttBufferUnfaded, TEST_PALETTE_TAG + 1 + i);
}

// Creates an object event with a reflection and returns the reflection's sprite ID.
// With fillSlots, every palette slot left after the object's own is full when the reflection loads.
static u32 SetUpObjectWithReflection(u32 *mainSpriteId, bool32 fillSlots, bool32 onHighBridge)
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
    if (onHighBridge)
        objectEvent->currentMetatileBehavior = MB_BRIDGE_OVER_POND_HIGH;

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

    reflectionSpriteId = SetUpObjectWithReflection(&mainSpriteId, TRUE, FALSE);
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

    reflectionSpriteId = SetUpObjectWithReflection(&mainSpriteId, FALSE, FALSE);
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

TEST("Reflection palette: a high bridge reflection keeps the bridge palette")
{
    u32 mainSpriteId, reflectionSpriteId, reflectionSlot, bridgeSlot;

    reflectionSpriteId = SetUpObjectWithReflection(&mainSpriteId, FALSE, TRUE);
    ASSUME(gSprites[reflectionSpriteId].inUse);

    gSprites[reflectionSpriteId].callback(&gSprites[reflectionSpriteId]);
    reflectionSlot = gSprites[reflectionSpriteId].oam.paletteNum;
    bridgeSlot = IndexOfSpritePaletteTag(HIGH_BRIDGE_PAL_TAG);
    TearDownObjectWithReflection(mainSpriteId, reflectionSpriteId);

    EXPECT_NE(bridgeSlot, 0xFF);
    EXPECT_EQ(reflectionSlot, bridgeSlot);
}

TEST("Reflection palette: with no free slot a high bridge reflection loads the bridge palette once a slot frees")
{
    u32 mainSpriteId, reflectionSpriteId, lastSlotTag, borrowedSlot, borrowedSlotTag, reflectionSlot, bridgeSlot;
    s32 reflectionOffset, bridgeOffset;

    reflectionSpriteId = SetUpObjectWithReflection(&mainSpriteId, TRUE, TRUE);
    lastSlotTag = GetSpritePaletteTagByPaletteNum(15); // No sprite uses it yet
    ASSUME(gSprites[reflectionSpriteId].inUse);
    ASSUME(gSprites[reflectionSpriteId].oam.paletteNum == 15);

    // While the slots stay full, the retry leaves the borrowed slot loaded
    gSprites[reflectionSpriteId].callback(&gSprites[reflectionSpriteId]);
    borrowedSlot = gSprites[reflectionSpriteId].oam.paletteNum;
    borrowedSlotTag = GetSpritePaletteTagByPaletteNum(15);

    FreeSpritePaletteByTag(TEST_PALETTE_TAG + 1);
    gSprites[reflectionSpriteId].callback(&gSprites[reflectionSpriteId]);
    reflectionSlot = gSprites[reflectionSpriteId].oam.paletteNum;
    bridgeSlot = IndexOfSpritePaletteTag(HIGH_BRIDGE_PAL_TAG);
    reflectionOffset = gSprites[reflectionSpriteId].y - gSprites[mainSpriteId].y;
    bridgeOffset = GetObjectEventGraphicsInfo(OBJ_EVENT_GFX_PICHU_DOLL)->height - 2 + 44; // BRIDGE_TYPE_POND_HIGH
    TearDownObjectWithReflection(mainSpriteId, reflectionSpriteId);

    EXPECT_EQ(borrowedSlot, 15);
    EXPECT_EQ(borrowedSlotTag, lastSlotTag);
    EXPECT_NE(bridgeSlot, 0xFF);
    EXPECT_EQ(reflectionSlot, bridgeSlot);
    EXPECT_EQ(reflectionOffset, bridgeOffset);
}

TEST("Reflection palette: with no free slot a high bridge reflection's retry leaves the borrowed last slot's fade alone")
{
    u32 mainSpriteId, reflectionSpriteId, i, changedColors = 0;
    u16 lastSlotColors[16];
    u8 savedState, savedFirstFrame;
    u16 savedColor;

    reflectionSpriteId = SetUpObjectWithReflection(&mainSpriteId, TRUE, TRUE);
    ASSUME(gSprites[reflectionSpriteId].inUse);
    ASSUME(gSprites[reflectionSpriteId].oam.paletteNum == 15);
    CpuCopy16(&gPlttBufferFaded[OBJ_PLTT_ID(15)], lastSlotColors, sizeof(lastSlotColors));

    // The first frame of a weather fade-in writes fadeDestColor over the whole slot it updates
    savedState = gWeatherPtr->palProcessingState;
    savedFirstFrame = gWeatherPtr->fadeInFirstFrame;
    savedColor = gWeatherPtr->fadeDestColor;
    gWeatherPtr->palProcessingState = WEATHER_PAL_STATE_SCREEN_FADING_IN;
    gWeatherPtr->fadeInFirstFrame = TRUE;
    gWeatherPtr->fadeDestColor = ~lastSlotColors[0] & 0x7FFF;

    // The retry's palette load fails again, and the weather update must not land on the borrowed slot 15
    gSprites[reflectionSpriteId].callback(&gSprites[reflectionSpriteId]);
    for (i = 0; i < 16; i++)
    {
        if (gPlttBufferFaded[OBJ_PLTT_ID(15) + i] != lastSlotColors[i])
            changedColors++;
    }

    gWeatherPtr->palProcessingState = savedState;
    gWeatherPtr->fadeInFirstFrame = savedFirstFrame;
    gWeatherPtr->fadeDestColor = savedColor;
    TearDownObjectWithReflection(mainSpriteId, reflectionSpriteId);

    EXPECT_EQ(changedColors, 0);
}
