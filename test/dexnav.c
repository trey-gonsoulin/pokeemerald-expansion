#include "global.h"
#include "dexnav.h"
#include "event_data.h"
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
