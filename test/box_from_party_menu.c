#include "global.h"
#include "event_data.h"
#include "pokemon_storage_system.h"
#include "test/test.h"
#include "constants/map_types.h"
#include "constants/maps.h"
#include "constants/region_map_sections.h"

TEST("Box from party menu: opens only after Lanette and where it's allowed")
{
    u32 mapsec = MAPSEC_PETALBURG_CITY, mapType = MAP_TYPE_CITY, map = MAP_PETALBURG_CITY;
    bool32 metLanette = TRUE, expected = TRUE, result;
    u8 savedMapsec = gMapHeader.regionMapSectionId;
    u8 savedMapType = gMapHeader.mapType;
    struct WarpData savedLocation = gSaveBlock1Ptr->location;
    bool32 savedFlag = FlagGet(FLAG_RECEIVED_DOLL_LANETTE);

    PARAMETRIZE { }
    PARAMETRIZE { metLanette = FALSE; expected = FALSE; }
    PARAMETRIZE { mapsec = MAPSEC_SAFARI_ZONE; }
    PARAMETRIZE { mapsec = MAPSEC_BATTLE_FRONTIER; expected = FALSE; }
    PARAMETRIZE { mapsec = MAPSEC_TRAINER_HILL; expected = FALSE; }
    PARAMETRIZE { mapsec = MAPSEC_UNDERWATER_124; mapType = MAP_TYPE_UNDERWATER; expected = FALSE; }
    PARAMETRIZE { mapsec = MAPSEC_EVER_GRANDE_CITY; map = MAP_EVER_GRANDE_CITY_POKEMON_LEAGUE_1F; }
    PARAMETRIZE { mapsec = MAPSEC_EVER_GRANDE_CITY; map = MAP_EVER_GRANDE_CITY_SIDNEYS_ROOM; expected = FALSE; }
    PARAMETRIZE { mapsec = MAPSEC_EVER_GRANDE_CITY; map = MAP_EVER_GRANDE_CITY_HALL_OF_FAME; expected = FALSE; }

    if (metLanette)
        FlagSet(FLAG_RECEIVED_DOLL_LANETTE);
    else
        FlagClear(FLAG_RECEIVED_DOLL_LANETTE);
    gMapHeader.regionMapSectionId = mapsec;
    gMapHeader.mapType = mapType;
    gSaveBlock1Ptr->location.mapGroup = MAP_GROUP(map);
    gSaveBlock1Ptr->location.mapNum = MAP_NUM(map);

    result = CanOpenBoxFromPartyMenu();

    gMapHeader.regionMapSectionId = savedMapsec;
    gMapHeader.mapType = savedMapType;
    gSaveBlock1Ptr->location = savedLocation;
    if (savedFlag)
        FlagSet(FLAG_RECEIVED_DOLL_LANETTE);
    else
        FlagClear(FLAG_RECEIVED_DOLL_LANETTE);

    EXPECT_EQ(result, expected);
}
