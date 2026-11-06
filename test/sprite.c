#include "global.h"
#include "decompress.h"
#include "main.h"
#include "malloc.h"
#include "random.h"
#include "sprite.h"
#include "test/test.h"

#define OAM_MATRIX_COUNT 32

EWRAM_DATA static u16 sSpritePriorities[MAX_SPRITES] = {0};
EWRAM_DATA static u8 sSpriteOrder[MAX_SPRITES] = {0};

static void Old_BuildOamBuffer(void);

static void ExpectEqOamBuffers(const struct OamData *oldOamBuffer, const struct OamData *newOamBuffer)
{
    u32 i;
    u32 matrices = 0;

    // Compare the non-matrix data.
    for (i = 0; i < gOamLimit; i++)
    {
        EXPECT(memcmp(&oldOamBuffer[i], &newOamBuffer[i], 6) == 0);
        if (newOamBuffer[i].affineMode & ST_OAM_AFFINE_ON_MASK)
            matrices |= 1 << newOamBuffer[i].matrixNum;
    }

    // Compare the matrix data.
    for (i = 0; i < OAM_MATRIX_COUNT; i++)
    {
        if (matrices & (1 << i))
        {
            u32 base = 4 * i;
            EXPECT_EQ(oldOamBuffer[base + 0].affineParam, newOamBuffer[base + 0].affineParam);
            EXPECT_EQ(oldOamBuffer[base + 1].affineParam, newOamBuffer[base + 1].affineParam);
            EXPECT_EQ(oldOamBuffer[base + 2].affineParam, newOamBuffer[base + 2].affineParam);
            EXPECT_EQ(oldOamBuffer[base + 3].affineParam, newOamBuffer[base + 3].affineParam);
        }
    }
}

static void ResetSpriteData_(void)
{
    u32 i;
    ResetSpriteData();
    for (i = 0; i < MAX_SPRITES; i++)
        sSpriteOrder[i] = i;
}

static void BenchmarkBuildOamBuffer(bool32 preSort)
{
    struct Benchmark oldBuildOamBuffer, newBuildOamBuffer;
    struct OamData *oldOamBuffer = Alloc(sizeof(gMain.oamBuffer));

    if (preSort)
        Old_BuildOamBuffer();
    BENCHMARK(&oldBuildOamBuffer)
    {
        Old_BuildOamBuffer();
    }
    memcpy(oldOamBuffer, gMain.oamBuffer, sizeof(gMain.oamBuffer));

    if (preSort)
        BuildOamBuffer();
    BENCHMARK(&newBuildOamBuffer)
    {
        BuildOamBuffer();
    }

    ExpectEqOamBuffers(oldOamBuffer, gMain.oamBuffer);
    EXPECT_FASTER(newBuildOamBuffer, oldBuildOamBuffer);
    Free(oldOamBuffer);
}

TEST("BuildOamBuffer faster with no sprites")
{
    ResetSpriteData_();
    BenchmarkBuildOamBuffer(FALSE);
}

// A file's tests run bottom up, so on one runner (`make check -j1 TESTS="BuildOamBuffer"`)
// this runs right after the next test, which ends with every sprite slot in use. The runner
// resets the sprites before each test (#272).
TEST("BuildOamBuffer: the next test starts with no sprite in use")
{
    u32 i, inUse = 0;

    for (i = 0; i < MAX_SPRITES; i++)
        inUse += gSprites[i].inUse;
    EXPECT_EQ(inUse, 0);
}

TEST("BuildOamBuffer faster with max sprites (equal y/subpriority)")
{
    u32 i;

    ResetSpriteData_();
    for (i = 0; i < MAX_SPRITES; i++)
        CreateSprite(&gDummySpriteTemplate, 0, 0, 0);
    BenchmarkBuildOamBuffer(FALSE);
}

TEST("BuildOamBuffer faster with max sprites (random y/subpriority)")
{
    u32 i;
    ResetSpriteData_();
    SeedRng(0);
    for (i = 0; i < MAX_SPRITES; i++)
        CreateSprite(&gDummySpriteTemplate, 0, Random() % 256, Random() % 256);
    BenchmarkBuildOamBuffer(FALSE);
}

TEST("BuildOamBuffer faster on already-sorted max sprites")
{
    u32 i;
    ResetSpriteData_();
    SeedRng(0);
    for (i = 0; i < MAX_SPRITES; i++)
        CreateSprite(&gDummySpriteTemplate, 0, Random() % 256, Random() % 256);
    BenchmarkBuildOamBuffer(TRUE);
}

TEST("BuildOamBuffer faster with mix of sprites")
{
    u32 i;
    ResetSpriteData_();
    SeedRng(0);
    for (i = 0; i < MAX_SPRITES / 2; i++)
    {
        u32 spriteId = CreateSprite(&gDummySpriteTemplate, 0, Random() % 256, Random() % 256);
        gSprites[spriteId].invisible = Random() % 4 == 0;
    }
    BenchmarkBuildOamBuffer(FALSE);
}

#define TAG_TEST_SHEET 0x7000

static const u8 ALIGNED(4) sTestTile[TILE_SIZE_4BPP] = {0};

static u16 LoadTestSheet(u32 i)
{
    const struct SpriteSheet sheet = { .data = sTestTile, .size = TILE_SIZE_4BPP, .tag = TAG_TEST_SHEET + i };
    return LoadSpriteSheet(&sheet);
}

TEST("LoadSpriteSheet fails once every tile range slot is taken")
{
    // EXPECT_EQ evaluates its arguments again for the failure message, so load outside it.
    u32 i, tileStart;
    ResetSpriteData();
    for (i = 0; i < MAX_SPRITES; i++)
    {
        tileStart = LoadTestSheet(i);
        EXPECT_EQ(tileStart, i);
        EXPECT_EQ(GetSpriteTileStartByTag(TAG_TEST_SHEET + i), i);
    }

    // A 65th tag had no slot: it took tile 64 and wrote its range past sSpriteTileRangeTags.
    gLoadFail = FALSE;
    tileStart = LoadTestSheet(MAX_SPRITES);
    EXPECT_EQ(gLoadFail, TRUE);
    EXPECT_EQ(tileStart, 0);
    EXPECT_EQ(GetSpriteTileStartByTag(TAG_TEST_SHEET + MAX_SPRITES), TAG_NONE);

    // A freed slot takes the next sheet, at the first free tile.
    gLoadFail = FALSE;
    FreeSpriteTilesByTag(TAG_TEST_SHEET + 1);
    tileStart = LoadTestSheet(MAX_SPRITES);
    EXPECT_EQ(gLoadFail, FALSE);
    EXPECT_EQ(tileStart, 1);
    ResetSpriteData();
}

static const u8 ALIGNED(4) sTestTiles[2 * TILE_SIZE_4BPP] = {0};
static const u8 ALIGNED(4) sFilledTiles[2 * TILE_SIZE_4BPP] = { [0 ... 2 * TILE_SIZE_4BPP - 1] = 0xFF };

TEST("LoadSpriteSheet fails on an empty sheet")
{
    const struct SpriteSheet emptySheet = { .data = sTestTile, .size = 0, .tag = TAG_TEST_SHEET + 1 };
    u32 tileStart;
    ResetSpriteData();
    tileStart = LoadTestSheet(0);
    EXPECT_EQ(tileStart, 0);

    // AllocSpriteTiles(0) freed every tile, and the sheet registered the range {0, 0}.
    gLoadFail = FALSE;
    tileStart = LoadSpriteSheet(&emptySheet);
    EXPECT_EQ(gLoadFail, TRUE);
    EXPECT_EQ(tileStart, 0);
    EXPECT_EQ(GetSpriteTileStartByTag(TAG_TEST_SHEET + 1), TAG_NONE);

    // The first sheet keeps its tile, so the next one goes after it.
    gLoadFail = FALSE;
    tileStart = LoadTestSheet(2);
    EXPECT_EQ(gLoadFail, FALSE);
    EXPECT_EQ(tileStart, 1);
    ResetSpriteData();
}

TEST("LoadSpriteSheet gives a partial last tile a whole tile")
{
    const struct SpriteSheet subTileSheet = { .data = sTestTiles, .size = TILE_SIZE_4BPP / 2, .tag = TAG_TEST_SHEET + 1 };
    const struct SpriteSheet partialSheet = { .data = sTestTiles, .size = TILE_SIZE_4BPP * 3 / 2, .tag = TAG_TEST_SHEET + 2 };
    const struct SpriteSheet twoTileSheet = { .data = sTestTiles, .size = 2 * TILE_SIZE_4BPP, .tag = TAG_TEST_SHEET + 4 };
    u32 tileStart;
    ResetSpriteData();

    // A sheet of half a tile takes one tile (it failed through AllocSpriteTiles(0)).
    gLoadFail = FALSE;
    tileStart = LoadSpriteSheet(&subTileSheet);
    EXPECT_EQ(gLoadFail, FALSE);
    EXPECT_EQ(tileStart, 0);

    // A sheet of a tile and a half took one tile and copied its last half tile into the next sheet's.
    tileStart = LoadSpriteSheet(&partialSheet);
    EXPECT_EQ(gLoadFail, FALSE);
    EXPECT_EQ(tileStart, 1);
    tileStart = LoadTestSheet(3);
    EXPECT_EQ(tileStart, 3);

    // Freeing the sheet frees both of its tiles.
    FreeSpriteTilesByTag(TAG_TEST_SHEET + 2);
    tileStart = LoadSpriteSheet(&twoTileSheet);
    EXPECT_EQ(gLoadFail, FALSE);
    EXPECT_EQ(tileStart, 1);
    ResetSpriteData();
}

TEST("LoadSpriteSheet leaves the tile after a partial last tile alone")
{
    const struct SpriteSheet partialSheet = { .data = sFilledTiles, .size = TILE_SIZE_4BPP * 3 / 2, .tag = TAG_TEST_SHEET + 2 };
    const u8 *nextTile = (const u8 *)OBJ_VRAM0 + TILE_SIZE_4BPP;
    u32 i, tileStart, changedBytes = 0;
    ResetSpriteData();
    LoadTestSheet(0);
    LoadTestSheet(1);
    FreeSpriteTilesByTag(TAG_TEST_SHEET);

    // The sheet took the one free tile, 0, and its last half tile went into the zeroed tile 1.
    tileStart = LoadSpriteSheet(&partialSheet);
    for (i = 0; i < TILE_SIZE_4BPP; i++)
    {
        if (nextTile[i] != 0)
            changedBytes++;
    }
    EXPECT_EQ(changedBytes, 0);
    EXPECT_EQ(tileStart, 2);
    ResetSpriteData();
}

TEST("LoadSpriteSheetByTemplate fails on an offset past the sheet")
{
    static const struct SpriteFrameImage image[] = { { sTestTile, TILE_SIZE_4BPP } };
    struct SpriteTemplate template = gDummySpriteTemplate;
    u32 tileStart;
    template.tileTag = TAG_TEST_SHEET;
    template.images = image;
    ResetSpriteData();

    // The copy's size, sheet size less offset, wrapped to about 4 GB.
    gLoadFail = FALSE;
    tileStart = LoadSpriteSheetByTemplate(&template, 0, TILE_SIZE_4BPP + 1);
    EXPECT_EQ(gLoadFail, TRUE);
    EXPECT_EQ(tileStart, 0);
    EXPECT_EQ(GetSpriteTileStartByTag(TAG_TEST_SHEET), TAG_NONE);

    // A negative offset is past the sheet too, once the u32 parameter takes it.
    gLoadFail = FALSE;
    tileStart = LoadSpriteSheetByTemplate(&template, 0, -1);
    EXPECT_EQ(gLoadFail, TRUE);
    EXPECT_EQ(GetSpriteTileStartByTag(TAG_TEST_SHEET), TAG_NONE);

    // An offset of the whole sheet copies nothing but still loads it.
    gLoadFail = FALSE;
    tileStart = LoadSpriteSheetByTemplate(&template, 0, TILE_SIZE_4BPP);
    EXPECT_EQ(gLoadFail, FALSE);
    EXPECT_EQ(tileStart, 0);
    EXPECT_EQ(GetSpriteTileStartByTag(TAG_TEST_SHEET), 0);
    ResetSpriteData();
}

TEST("LoadCompressedSpriteSheetByTemplate loads an uncompressed sheet whole after its offset")
{
    // 0xFF reads as smol mode 15, which IsCompressedData takes as uncompressed.
    static const struct SpriteFrameImage image[] = { { sFilledTiles, sizeof(sFilledTiles) } };
    struct SpriteTemplate template = gDummySpriteTemplate;
    const u8 *sheetTiles = (const u8 *)OBJ_VRAM0 + TILE_SIZE_4BPP;
    u32 tileStart;
    template.tileTag = TAG_TEST_SHEET;
    template.images = image;
    ResetSpriteData();
    CpuFill16(0, (void *)OBJ_VRAM0, 3 * TILE_SIZE_4BPP);

    // The offset is a blank first tile, so the sheet takes three tiles and its two go after it.
    gLoadFail = FALSE;
    tileStart = LoadCompressedSpriteSheetByTemplate(&template, TILE_SIZE_4BPP);
    EXPECT_EQ(gLoadFail, FALSE);
    EXPECT_EQ(tileStart, 0);
    EXPECT(memcmp((const u8 *)OBJ_VRAM0, sTestTile, TILE_SIZE_4BPP) == 0);
    EXPECT(memcmp(sheetTiles, sFilledTiles, sizeof(sFilledTiles)) == 0);
    EXPECT_EQ(LoadTestSheet(1), 3);
    ResetSpriteData();
}

TEST("CreateSpriteUnchecked fails on an empty untagged frame")
{
    static const struct SpriteFrameImage emptyImage[] = { { sTestTile, 0 } };
    struct SpriteTemplate template = gDummySpriteTemplate;
    u32 spriteId, tileStart;
    template.tileTag = TAG_NONE;
    template.images = emptyImage;
    ResetSpriteData();
    tileStart = LoadTestSheet(0);
    EXPECT_EQ(tileStart, 0);

    // AllocSpriteTiles(0) freed every tile and gave the sprite tile 0.
    // CreateSprite would stop the test on the failure (fatal_assertf).
    spriteId = CreateSpriteUnchecked(&template, 0, 0, 0);
    EXPECT_EQ(spriteId, MAX_SPRITES);

    tileStart = LoadTestSheet(1);
    EXPECT_EQ(tileStart, 1);
    ResetSpriteData();
}

TEST("CreateSpriteUnchecked gives an untagged frame's partial last tile a whole tile")
{
    static const struct SpriteFrameImage partialImage[] = { { sTestTiles, TILE_SIZE_4BPP * 3 / 2 } };
    struct SpriteTemplate template = gDummySpriteTemplate;
    u32 spriteId, tileStart;
    template.tileTag = TAG_NONE;
    template.images = partialImage;
    ResetSpriteData();
    tileStart = LoadTestSheet(0);
    EXPECT_EQ(tileStart, 0);

    // The frame took one tile, and its copy ran half a tile into the next sheet's.
    spriteId = CreateSpriteUnchecked(&template, 0, 0, 0);
    EXPECT_LT(spriteId, MAX_SPRITES);
    tileStart = gSprites[spriteId].oam.tileNum;
    EXPECT_EQ(tileStart, 1);
    tileStart = LoadTestSheet(1);
    EXPECT_EQ(tileStart, 3);

    // DestroySprite frees both of its tiles.
    DestroySprite(&gSprites[spriteId]);
    tileStart = LoadTestSheet(2);
    EXPECT_EQ(tileStart, 1);
    tileStart = LoadTestSheet(3);
    EXPECT_EQ(tileStart, 2);
    ResetSpriteData();
}

// Old implementation.

#define UBFIX

static void UpdateOamCoords(void)
{
    u8 i;
    for (i = 0; i < MAX_SPRITES; i++)
    {
        struct Sprite *sprite = &gSprites[i];
        if (sprite->inUse && !sprite->invisible)
        {
            if (sprite->coordOffsetEnabled)
            {
                sprite->oam.x = sprite->x + sprite->x2 + sprite->centerToCornerVecX + gSpriteCoordOffsetX;
                sprite->oam.y = sprite->y + sprite->y2 + sprite->centerToCornerVecY + gSpriteCoordOffsetY;
            }
            else
            {
                sprite->oam.x = sprite->x + sprite->x2 + sprite->centerToCornerVecX;
                sprite->oam.y = sprite->y + sprite->y2 + sprite->centerToCornerVecY;
            }
        }
    }
}

static void BuildSpritePriorities(void)
{
    u16 i;
    for (i = 0; i < MAX_SPRITES; i++)
    {
        struct Sprite *sprite = &gSprites[i];
        u16 priority = sprite->subpriority | (sprite->oam.priority << 8);
        sSpritePriorities[i] = priority;
    }
}

static void SortSprites(void)
{
    u8 i;
    for (i = 1; i < MAX_SPRITES; i++)
    {
        u8 j = i;
        struct Sprite *sprite1 = &gSprites[sSpriteOrder[i - 1]];
        struct Sprite *sprite2 = &gSprites[sSpriteOrder[i]];
        u16 sprite1Priority = sSpritePriorities[sSpriteOrder[i - 1]];
        u16 sprite2Priority = sSpritePriorities[sSpriteOrder[i]];
        s16 sprite1Y = sprite1->oam.y;
        s16 sprite2Y = sprite2->oam.y;

        if (sprite1Y >= DISPLAY_HEIGHT)
            sprite1Y = sprite1Y - 256;

        if (sprite2Y >= DISPLAY_HEIGHT)
            sprite2Y = sprite2Y - 256;

        if (sprite1->oam.affineMode == ST_OAM_AFFINE_DOUBLE
         && sprite1->oam.size == ST_OAM_SIZE_3)
        {
            u32 shape = sprite1->oam.shape;
            if (shape == ST_OAM_SQUARE || shape == ST_OAM_V_RECTANGLE)
            {
                if (sprite1Y > 128)
                    sprite1Y = sprite1Y - 256;
            }
        }

        if (sprite2->oam.affineMode == ST_OAM_AFFINE_DOUBLE
         && sprite2->oam.size == ST_OAM_SIZE_3)
        {
            u32 shape = sprite2->oam.shape;
            if (shape == ST_OAM_SQUARE || shape == ST_OAM_V_RECTANGLE)
            {
                if (sprite2Y > 128)
                    sprite2Y = sprite2Y - 256;
            }
        }

        while (j > 0
            && ((sprite1Priority > sprite2Priority)
             || (sprite1Priority == sprite2Priority && sprite1Y < sprite2Y)))
        {
            u8 temp = sSpriteOrder[j];
            sSpriteOrder[j] = sSpriteOrder[j - 1];
            sSpriteOrder[j - 1] = temp;

            // UB: If j equals 1, then j-- makes j equal 0.
            // Then, sSpriteOrder[-1] gets accessed below.
            // Although this doesn't result in a bug in the ROM,
            // the behavior is undefined.
            j--;
#ifdef UBFIX
            if (j == 0)
                break;
#endif

            sprite1 = &gSprites[sSpriteOrder[j - 1]];
            sprite2 = &gSprites[sSpriteOrder[j]];
            sprite1Priority = sSpritePriorities[sSpriteOrder[j - 1]];
            sprite2Priority = sSpritePriorities[sSpriteOrder[j]];
            sprite1Y = sprite1->oam.y;
            sprite2Y = sprite2->oam.y;

            if (sprite1Y >= DISPLAY_HEIGHT)
                sprite1Y = sprite1Y - 256;

            if (sprite2Y >= DISPLAY_HEIGHT)
                sprite2Y = sprite2Y - 256;

            if (sprite1->oam.affineMode == ST_OAM_AFFINE_DOUBLE
             && sprite1->oam.size == ST_OAM_SIZE_3)
            {
                u32 shape = sprite1->oam.shape;
                if (shape == ST_OAM_SQUARE || shape == ST_OAM_V_RECTANGLE)
                {
                    if (sprite1Y > 128)
                        sprite1Y = sprite1Y - 256;
                }
            }

            if (sprite2->oam.affineMode == ST_OAM_AFFINE_DOUBLE
             && sprite2->oam.size == ST_OAM_SIZE_3)
            {
                u32 shape = sprite2->oam.shape;
                if (shape == ST_OAM_SQUARE || shape == ST_OAM_V_RECTANGLE)
                {
                    if (sprite2Y > 128)
                        sprite2Y = sprite2Y - 256;
                }
            }
        }
    }
}

static void CopyMatricesToOamBuffer(void)
{
    u8 i;
    for (i = 0; i < OAM_MATRIX_COUNT; i++)
    {
        u32 base = 4 * i;
        gMain.oamBuffer[base + 0].affineParam = gOamMatrices[i].a;
        gMain.oamBuffer[base + 1].affineParam = gOamMatrices[i].b;
        gMain.oamBuffer[base + 2].affineParam = gOamMatrices[i].c;
        gMain.oamBuffer[base + 3].affineParam = gOamMatrices[i].d;
    }
}

static void AddSpritesToOamBuffer(void)
{
    u8 i = 0;
    u8 oamIndex = 0;

    while (i < MAX_SPRITES)
    {
        struct Sprite *sprite = &gSprites[sSpriteOrder[i]];
        if (sprite->inUse && !sprite->invisible && AddSpriteToOamBuffer(sprite, &oamIndex))
            return;
        i++;
    }

    while (oamIndex < gOamLimit)
    {
        gMain.oamBuffer[oamIndex] = gDummyOamData;
        oamIndex++;
    }
}

static void Old_BuildOamBuffer(void)
{
    u8 temp;
    UpdateOamCoords();
    BuildSpritePriorities();
    SortSprites();
    temp = gMain.oamLoadDisabled;
    gMain.oamLoadDisabled = TRUE;
    AddSpritesToOamBuffer();
    CopyMatricesToOamBuffer();
    gMain.oamLoadDisabled = temp;
    //sShouldProcessSpriteCopyRequests = TRUE;
}
