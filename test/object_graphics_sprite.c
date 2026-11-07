#include "global.h"
#include "decoration.h"
#include "event_object_movement.h"
#include "field_weather.h"
#include "palette.h"
#include "sprite.h"
#include "constants/decorations.h"
#include "constants/event_objects.h"
#include "test/test.h"

#define TEST_PALETTE_TAG 0x7104

TEST("Object graphics sprite: a caller's palette tag holds the object's palette")
{
    u32 objectTag = GetObjectEventGraphicsInfo(OBJ_EVENT_GFX_PICHU_DOLL)->paletteTag;
    u32 objectSpriteId, spriteId, objectSlot, slot;

    objectSpriteId = CreateObjectGraphicsSprite(OBJ_EVENT_GFX_PICHU_DOLL, SpriteCallbackDummy, 0, 0, 0);
    objectSlot = IndexOfSpritePaletteTag(objectTag);
    ASSUME(objectSpriteId != MAX_SPRITES);
    ASSUME(objectSlot != 0xFF);

    spriteId = CreateObjectGraphicsSpriteWithTag(OBJ_EVENT_GFX_PICHU_DOLL, SpriteCallbackDummy, 0, 0, 0, TEST_PALETTE_TAG);
    slot = IndexOfSpritePaletteTag(TEST_PALETTE_TAG);
    EXPECT_NE(spriteId, MAX_SPRITES);
    EXPECT_NE(slot, 0xFF);
    EXPECT_NE(slot, objectSlot);
    EXPECT_EQ((u32)gSprites[spriteId].oam.paletteNum, slot);
    EXPECT(memcmp(&gPlttBufferUnfaded[OBJ_PLTT_ID(slot)], &gPlttBufferUnfaded[OBJ_PLTT_ID(objectSlot)], PLTT_SIZE_4BPP) == 0);

    DestroySprite(&gSprites[spriteId]);
    DestroySprite(&gSprites[objectSpriteId]);
}

TEST("Object graphics sprite: a decoration icon's palette is freed by its tag")
{
    u32 objectTag = GetObjectEventGraphicsInfo(OBJ_EVENT_GFX_PICHU_DOLL)->paletteTag;
    u32 spriteId = AddDecorationIconObject(DECOR_PICHU_DOLL, 20, 84, 1, TEST_PALETTE_TAG, TEST_PALETTE_TAG);

    EXPECT_NE(spriteId, MAX_SPRITES);
    EXPECT_NE(IndexOfSpritePaletteTag(TEST_PALETTE_TAG), 0xFF);
    EXPECT_EQ(IndexOfSpritePaletteTag(objectTag), 0xFF);

    // As BuyMenuRemoveItemIcon does
    FreeSpriteTilesByTag(TEST_PALETTE_TAG);
    FreeSpritePaletteByTag(TEST_PALETTE_TAG);
    DestroySprite(&gSprites[spriteId]);
    EXPECT_EQ(IndexOfSpritePaletteTag(TEST_PALETTE_TAG), 0xFF);
    EXPECT_EQ(IndexOfSpritePaletteTag(objectTag), 0xFF);
}

TEST("Object graphics sprite: with no free palette slot a caller's tag falls back to the object's palette")
{
    u32 objectTag = GetObjectEventGraphicsInfo(OBJ_EVENT_GFX_PICHU_DOLL)->paletteTag;
    u32 objectSpriteId = CreateObjectGraphicsSprite(OBJ_EVENT_GFX_PICHU_DOLL, SpriteCallbackDummy, 0, 0, 0);
    u32 objectSlot = IndexOfSpritePaletteTag(objectTag);
    u32 spriteId, i;

    ASSUME(objectSpriteId != MAX_SPRITES);
    ASSUME(objectSlot != 0xFF);
    for (i = 0; IndexOfSpritePaletteTag(TAG_NONE) != 0xFF; i++)
        LoadSpritePaletteWithTag(gPlttBufferUnfaded, TEST_PALETTE_TAG + 1 + i);

    spriteId = CreateObjectGraphicsSpriteWithTag(OBJ_EVENT_GFX_PICHU_DOLL, SpriteCallbackDummy, 0, 0, 0, TEST_PALETTE_TAG);
    EXPECT_NE(spriteId, MAX_SPRITES);
    EXPECT_EQ(IndexOfSpritePaletteTag(TEST_PALETTE_TAG), 0xFF);
    EXPECT_EQ((u32)gSprites[spriteId].oam.paletteNum, objectSlot);

    DestroySprite(&gSprites[spriteId]);
    DestroySprite(&gSprites[objectSpriteId]);
}

TEST("Object graphics sprite: no palette tag keeps the object's own")
{
    u32 objectTag = GetObjectEventGraphicsInfo(OBJ_EVENT_GFX_PICHU_DOLL)->paletteTag;
    u32 spriteId = CreateObjectGraphicsSpriteWithTag(OBJ_EVENT_GFX_PICHU_DOLL, SpriteCallbackDummy, 0, 0, 0, TAG_NONE);

    EXPECT_NE(spriteId, MAX_SPRITES);
    EXPECT_NE(IndexOfSpritePaletteTag(objectTag), 0xFF);
    EXPECT_EQ((u32)gSprites[spriteId].oam.paletteNum, IndexOfSpritePaletteTag(objectTag));
    DestroySprite(&gSprites[spriteId]);
}

TEST("Object graphics sprite: with no free palette slot a dynamic palette shares the last slot without a weather update")
{
    // Where the weather update would write for a failed load's 0xFF, past the end of the buffer (an address for -Warray-bounds)
    const u16 *pastBuffer = (const u16 *)((uintptr_t)gPlttBufferFaded + sizeof(u16) * OBJ_PLTT_ID(0xFF));
    u16 pastBufferBefore[16];
    u32 i, spriteId, lastSlotTag;
    u8 savedState = gWeatherPtr->palProcessingState;
    u8 savedFirstFrame = gWeatherPtr->fadeInFirstFrame;
    u16 savedColor = gWeatherPtr->fadeDestColor;

    for (i = 0; IndexOfSpritePaletteTag(TAG_NONE) != 0xFF; i++)
        LoadSpritePaletteWithTag(gPlttBufferUnfaded, TEST_PALETTE_TAG + 1 + i);
    lastSlotTag = GetSpritePaletteTagByPaletteNum(15);
    memcpy(pastBufferBefore, pastBuffer, sizeof(pastBufferBefore));

    gWeatherPtr->palProcessingState = WEATHER_PAL_STATE_SCREEN_FADING_IN;
    gWeatherPtr->fadeInFirstFrame = TRUE;
    gWeatherPtr->fadeDestColor = ~pastBufferBefore[0];
    spriteId = CreateObjectGraphicsSprite(OBJ_EVENT_GFX_SPECIES(BULBASAUR), SpriteCallbackDummy, 0, 0, 0);
    gWeatherPtr->palProcessingState = savedState;
    gWeatherPtr->fadeInFirstFrame = savedFirstFrame;
    gWeatherPtr->fadeDestColor = savedColor;

    EXPECT(memcmp(pastBufferBefore, pastBuffer, sizeof(pastBufferBefore)) == 0);
    EXPECT_NE(spriteId, MAX_SPRITES);
    EXPECT_EQ((u32)gSprites[spriteId].oam.paletteNum, 15);
    EXPECT_EQ((u32)GetSpritePaletteTagByPaletteNum(15), lastSlotTag);

    DestroySprite(&gSprites[spriteId]);
}

// Debug_CreateTrainerIcon (src/debug.c) relies on the next two to free only a species palette the icon loaded.
TEST("Object graphics sprite: a dynamic palette loads into the first free slot under its species tag")
{
    u32 freeSlot = IndexOfSpritePaletteTag(TAG_NONE);
    u32 spriteId = CreateObjectGraphicsSpriteWithTag(OBJ_EVENT_GFX_SPECIES(BULBASAUR), SpriteCallbackDummy, 0, 0, 0, TEST_PALETTE_TAG);
    u32 speciesTag = GetSpritePaletteTagByPaletteNum(freeSlot);

    EXPECT_NE(spriteId, MAX_SPRITES);
    EXPECT_EQ((u32)gSprites[spriteId].oam.paletteNum, freeSlot);
    EXPECT_NE(speciesTag, TAG_NONE);
    EXPECT_NE(speciesTag, TEST_PALETTE_TAG);
    EXPECT_EQ(IndexOfSpritePaletteTag(TEST_PALETTE_TAG), 0xFF);

    FreeSpritePaletteByTag(speciesTag);
    DestroySprite(&gSprites[spriteId]);
    EXPECT_EQ(IndexOfSpritePaletteTag(speciesTag), 0xFF);
}

TEST("Object graphics sprite: an already loaded dynamic palette leaves the first free slot empty")
{
    u32 followerSpriteId = CreateObjectGraphicsSprite(OBJ_EVENT_GFX_SPECIES(BULBASAUR), SpriteCallbackDummy, 0, 0, 0);
    u32 followerSlot, freeSlot, spriteId;

    ASSUME(followerSpriteId != MAX_SPRITES);
    followerSlot = gSprites[followerSpriteId].oam.paletteNum;
    freeSlot = IndexOfSpritePaletteTag(TAG_NONE);

    spriteId = CreateObjectGraphicsSpriteWithTag(OBJ_EVENT_GFX_SPECIES(BULBASAUR), SpriteCallbackDummy, 0, 0, 0, TEST_PALETTE_TAG);
    EXPECT_NE(spriteId, MAX_SPRITES);
    EXPECT_EQ((u32)gSprites[spriteId].oam.paletteNum, followerSlot);
    EXPECT_EQ(GetSpritePaletteTagByPaletteNum(freeSlot), TAG_NONE);

    DestroySprite(&gSprites[spriteId]);
    DestroySprite(&gSprites[followerSpriteId]);
}
