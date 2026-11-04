#include "global.h"
#include "dexnav.h"
#include "event_data.h"
#include "field_screen_effect.h"
#include "fieldmap.h"
#include "malloc.h"
#include "overworld.h"
#include "script.h"
#include "constants/maps.h"
#include "constants/metatile_behaviors.h"
#include "constants/region_map_sections.h"
#include "test/test.h"

// The fork turns the DexNav on with search levels (#203): they live in SaveBlock3,
// one byte per species, and decide the egg move, hidden ability and IV chances.
TEST("DexNav: raising the search level adds one to that species' saved level")
{
    gSaveBlock3Ptr->dexNavSearchLevels[SPECIES_ZIGZAGOON] = 4;
    gSaveBlock3Ptr->dexNavSearchLevels[SPECIES_WURMPLE] = 0;
    gMapHeader.regionMapSectionId = MAPSEC_ROUTE_101;
    gDexNavSpecies = SPECIES_ZIGZAGOON;

    TryIncrementSpeciesSearchLevel();

    EXPECT_EQ(gSaveBlock3Ptr->dexNavSearchLevels[SPECIES_ZIGZAGOON], 5);
    EXPECT_EQ(gSaveBlock3Ptr->dexNavSearchLevels[SPECIES_WURMPLE], 0);
    gDexNavSpecies = SPECIES_NONE;
}

TEST("DexNav: the search level stops at 255")
{
    gSaveBlock3Ptr->dexNavSearchLevels[SPECIES_ZIGZAGOON] = 255;
    gMapHeader.regionMapSectionId = MAPSEC_ROUTE_101;
    gDexNavSpecies = SPECIES_ZIGZAGOON;

    TryIncrementSpeciesSearchLevel();

    EXPECT_EQ(gSaveBlock3Ptr->dexNavSearchLevels[SPECIES_ZIGZAGOON], 255);
    gDexNavSpecies = SPECIES_NONE;
}

TEST("DexNav: a map load resets the chain and the step counter")
{
    gSaveBlock3Ptr->dexNavChain = 0;
    IncrementDexNavChain();
    IncrementDexNavChain();
    EXPECT_EQ(gSaveBlock3Ptr->dexNavChain, 2);
    VarSet(DN_VAR_STEP_COUNTER, 40);
    FlagClear(DN_FLAG_SEARCHING);

    ResetDexNavSearch();

    EXPECT_EQ(gSaveBlock3Ptr->dexNavChain, 0);
    EXPECT_EQ(VarGet(DN_VAR_STEP_COUNTER), 0);
}

// #210: Flash leaves flash level 1, whose lit circle (72 px around the player's
// tile's centre) still takes a search; a cave without Flash (level 7) doesn't.
TEST("DexNav: Flash's lit circle is light enough to search, an unlit cave isn't")
{
    SetFlashLevel(0);
    EXPECT(!IsDexNavSearchTooDark());
    SetFlashLevel(1);
    EXPECT(!IsDexNavSearchTooDark());
    SetFlashLevel(2);
    EXPECT(IsDexNavSearchTooDark());
    SetFlashLevel(gMaxFlashLevel - 1);
    EXPECT(IsDexNavSearchTooDark());
    SetFlashLevel(0);
}

// The patch goes only on tiles wholly inside the circle: 3 tiles out in a line
// or diagonally to (3, 2), not (3, 3) or 4 out.
TEST("DexNav: in Flash's light the patch tiles are the 45 wholly inside the circle")
{
    s32 dx, dy;
    u32 lit = 0;

    SetFlashLevel(1);
    for (dy = -5; dy <= 5; dy++)
    {
        for (dx = -5; dx <= 5; dx++)
        {
            if (IsDexNavTileLit(dx, dy))
                lit++;
        }
    }
    EXPECT_EQ(lit, 45);
    EXPECT(IsDexNavTileLit(3, 0));
    EXPECT(IsDexNavTileLit(-3, 2));
    EXPECT(IsDexNavTileLit(2, -3));
    EXPECT(!IsDexNavTileLit(3, 3));
    EXPECT(!IsDexNavTileLit(0, 4));
    EXPECT(!IsDexNavTileLit(-4, 0));
    SetFlashLevel(0);
}

// A cave (Granite Cave's map type) at the given Flash level, with the player at
// map grid (x, y), MAP_OFFSET included: the start-of-search pick, and the tile
// it picked in *x, *y. The map is all tall grass, or only (grassX, grassY) when
// grassX isn't negative. The globals are restored before the caller's EXPECTs.
static bool32 Test_DexNavPickTileOnGrid(s32 width, s32 height, s16 playerX, s16 playerY, s32 grassX, s32 grassY, u8 flashLevel, s16 *x, s16 *y)
{
    static const u16 behaviors[] = {MB_TALL_GRASS, MB_NORMAL};
    static const u16 border[] = {1, 1, 1, 1};
    const struct Tileset tileset = {.metatileAttributes = behaviors};
    const struct MapLayout layout = {.width = width, .height = height, .border = border, .primaryTileset = &tileset};
    const struct MapLayout *savedLayout = gMapHeader.mapLayout;
    struct BackupMapLayout savedGrid = gBackupMapLayout;
    struct WarpData savedLocation = gSaveBlock1Ptr->location;
    struct Coords16 savedPos = gSaveBlock1Ptr->pos;
    bool32 picked;
    s32 i;

    gMapHeader.mapLayout = &layout;
    gBackupMapLayout.width = width;
    gBackupMapLayout.height = height;
    gBackupMapLayout.map = AllocZeroed(width * height * sizeof(u16));
    if (grassX >= 0)
    {
        for (i = 0; i < width * height; i++)
            gBackupMapLayout.map[i] = 1;
        gBackupMapLayout.map[grassY * width + grassX] = 0;
    }
    gSaveBlock1Ptr->location.mapGroup = MAP_GROUP(MAP_GRANITE_CAVE_1F);
    gSaveBlock1Ptr->location.mapNum = MAP_NUM(MAP_GRANITE_CAVE_1F);
    gSaveBlock1Ptr->pos.x = playerX - MAP_OFFSET;
    gSaveBlock1Ptr->pos.y = playerY - MAP_OFFSET;
    SetFlashLevel(flashLevel);

    picked = Test_DexNavPickLandTile(x, y);

    SetFlashLevel(0);
    Free(gBackupMapLayout.map);
    gBackupMapLayout = savedGrid;
    gSaveBlock1Ptr->pos = savedPos;
    gSaveBlock1Ptr->location = savedLocation;
    gMapHeader.mapLayout = savedLayout;
    return picked;
}

// A tall grass cave lit by Flash: whether the patch lands in the lit circle
static bool32 Test_DexNavPickTileOnMap(s32 width, s32 height, s16 playerX, s16 playerY)
{
    s16 x, y;

    return Test_DexNavPickTileOnGrid(width, height, playerX, playerY, -1, -1, 1, &x, &y)
        && IsDexNavTileLit(x - playerX, y - playerY);
}

// Upstream kept the candidate tiles in u8, so past x or y 255 the patch went
// 256 tiles back (#214).
TEST("DexNav: the patch lands by the player past map x or y 255")
{
    EXPECT(Test_DexNavPickTileOnMap(264, 16, 260, 8));
    EXPECT(Test_DexNavPickTileOnMap(16, 264, 8, 260));
}

// Upstream's cave chance, Random() % scale < 1, keeps scale in a u8, which
// wraps: 440 - 4 / 2 - 2 * (44 + 47) is 256, so with the player at (40, 47) the
// tile 4 to the right had a scale of 0 and divided by zero (#224). Treated as 1,
// it always takes the patch.
TEST("DexNav: a cave tile whose chance wraps to 0 always takes the patch")
{
    s16 x, y;

    EXPECT(Test_DexNavPickTileOnGrid(64, 64, 40, 47, 44, 47, 0, &x, &y));
    EXPECT_EQ(x, 44);
    EXPECT_EQ(y, 47);
}

// Upstream compared the tile with every object slot's coordinates, active or
// not, so a despawned object's stale ones kept the patch off its tile (#225).
TEST("DexNav: only an active object keeps the patch off its tile")
{
    struct ObjectEvent *object = &gObjectEvents[OBJECT_EVENTS_COUNT - 1];
    struct ObjectEvent savedObject = *object;
    bool32 pickedPastInactive, pickedPastActive;
    s16 x, y;

    object->active = FALSE;
    object->currentCoords.x = 43;
    object->currentCoords.y = 47;
    pickedPastInactive = Test_DexNavPickTileOnGrid(64, 64, 40, 47, 43, 47, 1, &x, &y)
                      && x == 43 && y == 47;
    object->active = TRUE;
    pickedPastActive = Test_DexNavPickTileOnGrid(64, 64, 40, 47, 43, 47, 1, &x, &y);
    *object = savedObject;

    EXPECT(pickedPastInactive);
    EXPECT(!pickedPastActive);
}

// In the debug ROM R+Start opens the debug menu, so R searches on its release,
// and not if Start came while it was held; otherwise R searches when pressed.
// One string per run of frames: 'R' pressed, 'r' held, 'S' Start while R is
// held, 's' Start between tiles, '-' nothing held, 'm' nothing held between tiles,
// 'L' nothing held while a script holds the field.
static u32 Test_DexNavSearchLockedFrame(void)
{
    u32 searched;

    LockPlayerFieldControls();
    searched = IsDexNavSearchButtonPressed(FALSE, 0, 0, TRUE);
    UnlockPlayerFieldControls();
    return searched;
}

static u32 Test_DexNavSearchFrame(char frame)
{
    switch (frame)
    {
    case 'R': return IsDexNavSearchButtonPressed(TRUE, R_BUTTON, R_BUTTON, TRUE);
    case 'r': return IsDexNavSearchButtonPressed(FALSE, 0, R_BUTTON, TRUE);
    case 'S': return IsDexNavSearchButtonPressed(FALSE, START_BUTTON, R_BUTTON | START_BUTTON, TRUE);
    case 's': return IsDexNavSearchButtonPressed(FALSE, START_BUTTON, R_BUTTON | START_BUTTON, FALSE);
    case 'm': return IsDexNavSearchButtonPressed(FALSE, 0, 0, FALSE);
    case 'L': return Test_DexNavSearchLockedFrame();
    default:  return IsDexNavSearchButtonPressed(FALSE, 0, 0, TRUE);
    }
}

// The frames on which a search starts, as a bit mask
static u32 Test_DexNavSearchFrames(const char *frames)
{
    u32 i, searched = 0;

    for (i = 0; frames[i] != '\0'; i++)
        searched |= Test_DexNavSearchFrame(frames[i]) << i;
    return searched;
}

TEST("DexNav: R+Start doesn't start a search in the debug ROM")
{
    bool32 onRelease = DEBUG_OVERWORLD_MENU && !DEBUG_OVERWORLD_IN_MENU && (DEBUG_OVERWORLD_HELD_KEYS & R_BUTTON);
    u32 tap, startWhileHeld, startBetweenTiles, releaseBetweenTiles, releaseInScript;

    tap = Test_DexNavSearchFrames("Rr--");
    startWhileHeld = Test_DexNavSearchFrames("RrSr--");
    startBetweenTiles = Test_DexNavSearchFrames("Rrsr--");
    releaseBetweenTiles = Test_DexNavSearchFrames("Rrmm--");
    releaseInScript = Test_DexNavSearchFrames("RrL--");

    if (onRelease)
    {
        EXPECT_EQ(tap, 1 << 2);
        EXPECT_EQ(startWhileHeld, 0);
        EXPECT_EQ(startBetweenTiles, 0);
        EXPECT_EQ(releaseBetweenTiles, 1 << 4);
        EXPECT_EQ(releaseInScript, 0);
    }
    else
    {
        EXPECT_EQ(tap, 1 << 0);
        EXPECT_EQ(startWhileHeld, 1 << 0);
        EXPECT_EQ(startBetweenTiles, 1 << 0);
        EXPECT_EQ(releaseBetweenTiles, 1 << 0);
        EXPECT_EQ(releaseInScript, 1 << 0);
    }
}
