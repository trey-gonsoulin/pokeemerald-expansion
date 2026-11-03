#include "global.h"
#include "overworld.h"
#include "constants/maps.h"
#include "test/test.h"

// The warp setters stored x and y through s8 parameters, which cut off Route 111's and 119's
// rows past 127 and the Route 123 and Desert Underpass columns (#164).

TEST("Warp coordinates: SetWarpDestination keeps a row past 127")
{
    SetWarpDestination(MAP_GROUP(MAP_ROUTE119), MAP_NUM(MAP_ROUTE119), WARP_ID_NONE, 18, 135);
    ApplyCurrentWarp();
    EXPECT_EQ(gSaveBlock1Ptr->location.mapGroup, MAP_GROUP(MAP_ROUTE119));
    EXPECT_EQ(gSaveBlock1Ptr->location.mapNum, MAP_NUM(MAP_ROUTE119));
    EXPECT_EQ(gSaveBlock1Ptr->location.x, 18);
    EXPECT_EQ(gSaveBlock1Ptr->location.y, 135);
}

TEST("Warp coordinates: a fixed hole warp keeps a column past 127")
{
    SetFixedHoleWarp(MAP_GROUP(MAP_ROUTE123), MAP_NUM(MAP_ROUTE123), WARP_ID_NONE, -1, -1);
    SetWarpDestinationToFixedHoleWarp(135, 10);
    ApplyCurrentWarp();
    EXPECT_EQ(gSaveBlock1Ptr->location.x, 135);
    EXPECT_EQ(gSaveBlock1Ptr->location.y, 10);
}

TEST("Warp coordinates: the dynamic warp keeps the player's row past 127")
{
    gSaveBlock1Ptr->pos.x = 18;
    gSaveBlock1Ptr->pos.y = 135;
    SetDynamicWarp(0, MAP_GROUP(MAP_ROUTE111), MAP_NUM(MAP_ROUTE111), WARP_ID_NONE);
    EXPECT_EQ(gSaveBlock1Ptr->dynamicWarp.x, 18);
    EXPECT_EQ(gSaveBlock1Ptr->dynamicWarp.y, 135);
}

// What the setdynamicwarp and setescapewarp script commands call with their u16 coordinates
TEST("Warp coordinates: the dynamic and escape warps keep coordinates past 127")
{
    SetDynamicWarpWithCoords(0, MAP_GROUP(MAP_ROUTE123), MAP_NUM(MAP_ROUTE123), WARP_ID_NONE, 135, 10);
    SetEscapeWarp(MAP_GROUP(MAP_ROUTE119), MAP_NUM(MAP_ROUTE119), WARP_ID_NONE, 18, 135);
    EXPECT_EQ(gSaveBlock1Ptr->dynamicWarp.x, 135);
    EXPECT_EQ(gSaveBlock1Ptr->dynamicWarp.y, 10);
    EXPECT_EQ(gSaveBlock1Ptr->escapeWarp.x, 18);
    EXPECT_EQ(gSaveBlock1Ptr->escapeWarp.y, 135);
}

TEST("Warp coordinates: the dummy coordinates stay -1")
{
    SetWarpDestinationToMapWarp(MAP_GROUP(MAP_ROUTE119), MAP_NUM(MAP_ROUTE119), 0);
    ApplyCurrentWarp();
    EXPECT_EQ(gSaveBlock1Ptr->location.x, -1);
    EXPECT_EQ(gSaveBlock1Ptr->location.y, -1);
}
