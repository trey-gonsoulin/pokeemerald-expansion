#include "global.h"
#include "decoration.h"
#include "event_object_movement.h"
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
