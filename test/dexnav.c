#include "global.h"
#include "dexnav.h"
#include "event_data.h"
#include "field_screen_effect.h"
#include "overworld.h"
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

// In the debug ROM R+Start opens the debug menu, so R searches on its release,
// and not if Start came while it was held; otherwise R searches when pressed.
TEST("DexNav: R+Start doesn't start a search in the debug ROM")
{
    bool32 onRelease = DEBUG_OVERWORLD_MENU && !DEBUG_OVERWORLD_IN_MENU && (DEBUG_OVERWORLD_HELD_KEYS & R_BUTTON);

    // R alone
    EXPECT_EQ(IsDexNavSearchButtonPressed(R_BUTTON, R_BUTTON), !onRelease);
    EXPECT(!IsDexNavSearchButtonPressed(0, R_BUTTON));
    EXPECT_EQ(IsDexNavSearchButtonPressed(0, 0), onRelease);
    EXPECT(!IsDexNavSearchButtonPressed(0, 0));

    // R, then Start while R is held
    EXPECT_EQ(IsDexNavSearchButtonPressed(R_BUTTON, R_BUTTON), !onRelease);
    EXPECT(!IsDexNavSearchButtonPressed(START_BUTTON, R_BUTTON | START_BUTTON));
    EXPECT(!IsDexNavSearchButtonPressed(0, 0));
}
