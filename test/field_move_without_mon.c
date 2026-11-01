#include "global.h"
#include "event_data.h"
#include "field_move.h"
#include "field_player_avatar.h"
#include "field_screen_effect.h"
#include "overworld.h"
#include "test/test.h"

// The lead stands in only with OW_FIELD_MOVES_WITHOUT_MON
#define LEAD(slot) (OW_FIELD_MOVES_WITHOUT_MON ? (slot) : PARTY_SIZE)

enum { MON_NONE, MON_PLAIN, MON_KNOWER, MON_EGG_KNOWER, MON_FAINTED };

static void SetUpFieldMoveParty(const u8 *kinds, enum Move move)
{
    for (u32 i = 0; i < PARTY_SIZE; i++)
    {
        struct Pokemon *mon = &gParties[B_TRAINER_PLAYER][i];
        bool32 isEgg = TRUE;
        u32 hp = 0;

        ZeroMonData(mon);
        if (kinds[i] == MON_NONE)
            continue;
        CreateMon(mon, SPECIES_WOBBUFFET, 50, 0, OTID_STRUCT_PRESET(0));
        CalculateMonStats(mon); // CreateMon leaves HP at 0
        if (kinds[i] == MON_KNOWER || kinds[i] == MON_EGG_KNOWER)
            SetMonMoveSlot(mon, move, 0);
        if (kinds[i] == MON_EGG_KNOWER)
            SetMonData(mon, MON_DATA_IS_EGG, &isEgg);
        if (kinds[i] == MON_FAINTED)
            SetMonData(mon, MON_DATA_HP, &hp);
    }
    gPartiesCount[B_TRAINER_PLAYER] = CalculatePlayerPartyCount();
}

static void SetFlagTo(u32 flag, bool32 set)
{
    if (set)
        FlagSet(flag);
    else
        FlagClear(flag);
}

TEST("Field move without mon: travel HMs fall back to the lead once the badge is earned")
{
    u8 kinds[PARTY_SIZE] = {MON_PLAIN, MON_PLAIN, MON_PLAIN};
    enum FieldMove fieldMove = FIELD_MOVE_CUT;
    u32 badge = FLAG_BADGE01_GET, expected = LEAD(0), result;
    bool32 hasBadge = TRUE, savedBadge;

    PARAMETRIZE { }
    PARAMETRIZE { kinds[2] = MON_KNOWER; expected = 2; }
    PARAMETRIZE { kinds[2] = MON_KNOWER; hasBadge = FALSE; expected = 2; }
    PARAMETRIZE { hasBadge = FALSE; expected = PARTY_SIZE; }
    PARAMETRIZE { kinds[0] = MON_FAINTED; expected = LEAD(1); }
    PARAMETRIZE { kinds[0] = MON_EGG_KNOWER; expected = LEAD(1); }
    PARAMETRIZE { kinds[0] = MON_EGG_KNOWER; kinds[2] = MON_KNOWER; expected = 2; }
    PARAMETRIZE { fieldMove = FIELD_MOVE_SURF; badge = FLAG_BADGE05_GET; }
    PARAMETRIZE { fieldMove = FIELD_MOVE_DIVE; badge = FLAG_BADGE07_GET; }
    PARAMETRIZE { fieldMove = FIELD_MOVE_DIVE; badge = FLAG_BADGE07_GET; hasBadge = FALSE; expected = PARTY_SIZE; }
    PARAMETRIZE { fieldMove = FIELD_MOVE_SECRET_POWER; expected = PARTY_SIZE; }
    PARAMETRIZE { fieldMove = FIELD_MOVE_DIG; expected = PARTY_SIZE; }
    PARAMETRIZE { fieldMove = FIELD_MOVE_SWEET_SCENT; expected = PARTY_SIZE; }
    PARAMETRIZE { fieldMove = FIELD_MOVE_SECRET_POWER; kinds[1] = MON_KNOWER; expected = 1; }

    SetUpFieldMoveParty(kinds, FieldMove_GetMoveId(fieldMove));
    savedBadge = FlagGet(badge);
    SetFlagTo(badge, hasBadge);

    result = GetFieldMoveUserSlot(fieldMove);

    SetFlagTo(badge, savedBadge);

    EXPECT_EQ(result, expected);
}

TEST("Field move without mon: Surf is offered with the Balance Badge and no Surfer")
{
    u8 kinds[PARTY_SIZE] = {MON_PLAIN};
    bool32 hasBadge = TRUE, savedBadge = FlagGet(FLAG_BADGE05_GET), result;

    PARAMETRIZE { }
    PARAMETRIZE { hasBadge = FALSE; }

    SetUpFieldMoveParty(kinds, MOVE_SURF);
    SetFlagTo(FLAG_BADGE05_GET, hasBadge);

    result = PartyHasMonWithSurf();

    SetFlagTo(FLAG_BADGE05_GET, savedBadge);

    EXPECT_EQ(result, OW_FIELD_MOVES_WITHOUT_MON && hasBadge);
}

TEST("Field move without mon: caves are lit on entry with the Knuckle Badge")
{
    bool32 hasBadge = TRUE, cave = TRUE;
    bool32 savedBadge = FlagGet(FLAG_BADGE02_GET), savedFlash = FlagGet(FLAG_SYS_USE_FLASH);
    bool8 savedCave = gMapHeader.cave;
    u8 savedLevel = gSaveBlock1Ptr->flashLevel, level, expected;

    PARAMETRIZE { expected = OW_FIELD_MOVES_WITHOUT_MON ? 1 : gMaxFlashLevel - 1; }
    PARAMETRIZE { hasBadge = FALSE; expected = gMaxFlashLevel - 1; }
    PARAMETRIZE { cave = FALSE; expected = 0; }

    SetFlagTo(FLAG_BADGE02_GET, hasBadge);
    FlagClear(FLAG_SYS_USE_FLASH);
    gMapHeader.cave = cave;

    SetDefaultFlashLevel();
    level = gSaveBlock1Ptr->flashLevel;

    gMapHeader.cave = savedCave;
    gSaveBlock1Ptr->flashLevel = savedLevel;
    SetFlagTo(FLAG_SYS_USE_FLASH, savedFlash);
    SetFlagTo(FLAG_BADGE02_GET, savedBadge);

    EXPECT_EQ(level, expected);
}
