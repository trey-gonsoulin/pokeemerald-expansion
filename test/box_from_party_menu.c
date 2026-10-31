#include "global.h"
#include "event_data.h"
#include "pokemon_storage_system.h"
#include "test/test.h"
#include "constants/map_types.h"
#include "constants/region_map_sections.h"

TEST("Box from party menu: opens only after Lanette and where it's allowed")
{
    u32 mapsec = MAPSEC_PETALBURG_CITY, mapType = MAP_TYPE_CITY;
    bool32 metLanette = TRUE, expected = TRUE;
    u8 savedMapsec = gMapHeader.regionMapSectionId;
    u8 savedMapType = gMapHeader.mapType;

    PARAMETRIZE { }
    PARAMETRIZE { metLanette = FALSE; expected = FALSE; }
    PARAMETRIZE { mapsec = MAPSEC_SAFARI_ZONE; }
    PARAMETRIZE { mapsec = MAPSEC_BATTLE_FRONTIER; expected = FALSE; }
    PARAMETRIZE { mapsec = MAPSEC_TRAINER_HILL; expected = FALSE; }
    PARAMETRIZE { mapsec = MAPSEC_UNDERWATER_124; mapType = MAP_TYPE_UNDERWATER; expected = FALSE; }

    if (metLanette)
        FlagSet(FLAG_SYS_PC_LANETTE);
    else
        FlagClear(FLAG_SYS_PC_LANETTE);
    gMapHeader.regionMapSectionId = mapsec;
    gMapHeader.mapType = mapType;

    EXPECT_EQ(CanOpenBoxFromPartyMenu(), expected);

    gMapHeader.regionMapSectionId = savedMapsec;
    gMapHeader.mapType = savedMapType;
    FlagClear(FLAG_SYS_PC_LANETTE);
}
