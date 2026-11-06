#include "global.h"
#include "event_data.h"
#include "tv.h"
#include "constants/tv.h"
#include "test/test.h"

// EventScript_DoTVShow (data/scripts/tv.inc) calls DoTVShow until VAR_RESULT is TRUE,
// so a slot DoTVShow prints nothing for has to set it too, or the TV never turns off.
static bool32 DoTVShowOnSlot(u32 kind, bool32 active)
{
    TVShow saved = gSaveBlock1Ptr->tvShows[0];
    bool32 stillActive;

    gSaveBlock1Ptr->tvShows[0].common.kind = kind;
    gSaveBlock1Ptr->tvShows[0].common.active = active;
    gSpecialVar_0x8004 = 0;
    gSpecialVar_Result = FALSE;
    DoTVShow();
    stillActive = gSaveBlock1Ptr->tvShows[0].common.active;
    gSaveBlock1Ptr->tvShows[0] = saved;
    return stillActive;
}

TEST("TV show: an inactive slot ends the TV loop")
{
    DoTVShowOnSlot(TVSHOW_FAN_CLUB_LETTER, FALSE);
    EXPECT_EQ(gSpecialVar_Result, TRUE);
}

TEST("TV show: the dummied-out show ends the TV loop and goes off the air")
{
    bool32 stillActive = DoTVShowOnSlot(TVSHOW_DUMMY, TRUE);
    EXPECT_EQ(gSpecialVar_Result, TRUE);
    EXPECT_EQ(stillActive, FALSE);
}

// GetRandomActiveShowIdx picks the show EventScript_TryDoTVShow airs, and through
// FindAnyTVShowOnTheAir decides whether the TV screens flash.
static u32 PickShowWithOnlySlot0Active(u32 kind, bool32 *stillActive)
{
    TVShow saved[TV_SHOWS_COUNT];
    u32 picked;

    memcpy(saved, gSaveBlock1Ptr->tvShows, sizeof(saved));
    memset(gSaveBlock1Ptr->tvShows, 0, sizeof(saved));
    gSaveBlock1Ptr->tvShows[0].common.kind = kind;
    gSaveBlock1Ptr->tvShows[0].common.active = TRUE;
    picked = GetRandomActiveShowIdx();
    *stillActive = gSaveBlock1Ptr->tvShows[0].common.active;
    memcpy(gSaveBlock1Ptr->tvShows, saved, sizeof(saved));
    return picked;
}

TEST("TV show: the picker skips an active slot with no show to air and takes it off the air")
{
    u32 kind = 0;
    bool32 stillActive;
    PARAMETRIZE { kind = TVSHOW_OFF_AIR; }
    PARAMETRIZE { kind = TVSHOW_DUMMY; }
    PARAMETRIZE { kind = TVSHOW_LILYCOVE_CONTEST_LADY + 1; }
    PARAMETRIZE { kind = TVGROUP_NORMAL_END; }
    PARAMETRIZE { kind = TVGROUP_RECORD_MIX_END; }
    PARAMETRIZE { kind = TVSHOW_MASS_OUTBREAK + 1; }
    PARAMETRIZE { kind = 0xFF; }
    EXPECT_EQ(PickShowWithOnlySlot0Active(kind, &stillActive), 0xFF);
    EXPECT_EQ(stillActive, FALSE);
}

TEST("TV show: the picker finds an active show that airs")
{
    u32 kind = 0;
    bool32 stillActive;
    PARAMETRIZE { kind = TVSHOW_FAN_CLUB_LETTER; }
    PARAMETRIZE { kind = TVSHOW_LILYCOVE_CONTEST_LADY; }
    PARAMETRIZE { kind = TVSHOW_POKEMON_TODAY_CAUGHT; }
    PARAMETRIZE { kind = TVSHOW_SAFARI_FAN_CLUB; }
    EXPECT_EQ(PickShowWithOnlySlot0Active(kind, &stillActive), 0);
    EXPECT_EQ(stillActive, TRUE);
}

// Record mixing gives away the slot FindInactiveShowInArray finds, in every array it mixes
TEST("TV show: record mixing passes over an inactive slot with no show to air")
{
    TVShow shows[TV_SHOWS_COUNT];
    u32 kind = 0;
    PARAMETRIZE { kind = TVSHOW_OFF_AIR; }
    PARAMETRIZE { kind = TVSHOW_DUMMY; }
    PARAMETRIZE { kind = TVSHOW_LILYCOVE_CONTEST_LADY + 1; }
    PARAMETRIZE { kind = TVGROUP_NORMAL_END; }
    PARAMETRIZE { kind = TVGROUP_RECORD_MIX_END; }
    PARAMETRIZE { kind = TVSHOW_MASS_OUTBREAK + 1; }
    PARAMETRIZE { kind = TVGROUP_OUTBREAK_END; }
    memset(shows, 0, sizeof(shows));
    shows[NUM_NORMAL_TVSHOW_SLOTS].common.kind = kind;
    shows[NUM_NORMAL_TVSHOW_SLOTS + 1].common.kind = TVSHOW_FAN_CLUB_LETTER;
    EXPECT_EQ(Test_FindInactiveShowInArray(shows), NUM_NORMAL_TVSHOW_SLOTS + 1);
}

TEST("TV show: record mixing finds an inactive show that airs")
{
    TVShow shows[TV_SHOWS_COUNT];
    u32 kind = 0;
    PARAMETRIZE { kind = TVSHOW_FAN_CLUB_LETTER; }
    PARAMETRIZE { kind = TVSHOW_LILYCOVE_CONTEST_LADY; }
    PARAMETRIZE { kind = TVSHOW_POKEMON_TODAY_CAUGHT; }
    PARAMETRIZE { kind = TVSHOW_MASS_OUTBREAK; }
    memset(shows, 0, sizeof(shows));
    shows[NUM_NORMAL_TVSHOW_SLOTS].common.kind = kind;
    EXPECT_EQ(Test_FindInactiveShowInArray(shows), NUM_NORMAL_TVSHOW_SLOTS);
    shows[NUM_NORMAL_TVSHOW_SLOTS].common.active = TRUE;
    EXPECT_EQ(Test_FindInactiveShowInArray(shows), -1);
}

TEST("TV show: record mixing deletes the slots with no show to air before sending")
{
    TVShow saved[TV_SHOWS_COUNT];
    TVShow *shows = gSaveBlock1Ptr->tvShows;

    memcpy(saved, shows, sizeof(saved));
    memset(shows, 0, sizeof(saved));
    shows[0].common.kind = TVSHOW_DUMMY;
    shows[1].common.kind = TVSHOW_FAN_CLUB_LETTER;
    shows[1].common.active = TRUE;
    shows[2].common.active = TRUE; // kind 0 still on the air
    shows[NUM_NORMAL_TVSHOW_SLOTS].common.kind = TVGROUP_RECORD_MIX_END;
    shows[NUM_NORMAL_TVSHOW_SLOTS].common.active = TRUE;
    shows[NUM_NORMAL_TVSHOW_SLOTS + 1].common.kind = TVSHOW_MASS_OUTBREAK + 1;
    shows[NUM_NORMAL_TVSHOW_SLOTS + 2].common.kind = TVSHOW_BRAVO_TRAINER_BATTLE_TOWER_PROFILE;
    shows[NUM_NORMAL_TVSHOW_SLOTS + 3].common.kind = TVSHOW_MASS_OUTBREAK;
    shows[TV_SHOWS_COUNT - 1].common.kind = TVSHOW_DUMMY; // the show being made isn't sent as a show
    DeleteUnairableTVShows();
    // What's left is compacted, as GetRandomActiveShowIdx stops at the first empty mix slot
    EXPECT_EQ(shows[0].common.kind, TVSHOW_FAN_CLUB_LETTER);
    EXPECT_EQ(shows[0].common.active, TRUE);
    EXPECT_EQ(shows[1].common.kind, TVSHOW_OFF_AIR);
    EXPECT_EQ(shows[2].common.kind, TVSHOW_OFF_AIR);
    EXPECT_EQ(shows[2].common.active, FALSE);
    EXPECT_EQ(shows[NUM_NORMAL_TVSHOW_SLOTS].common.kind, TVSHOW_BRAVO_TRAINER_BATTLE_TOWER_PROFILE);
    EXPECT_EQ(shows[NUM_NORMAL_TVSHOW_SLOTS + 1].common.kind, TVSHOW_MASS_OUTBREAK);
    EXPECT_EQ(shows[NUM_NORMAL_TVSHOW_SLOTS + 2].common.kind, TVSHOW_OFF_AIR);
    EXPECT_EQ(shows[NUM_NORMAL_TVSHOW_SLOTS + 3].common.kind, TVSHOW_OFF_AIR);
    EXPECT_EQ(shows[TV_SHOWS_COUNT - 1].common.kind, TVSHOW_DUMMY);
    memcpy(shows, saved, sizeof(saved));
}

TEST("TV show: an active slot of an unknown kind ends the TV loop and goes off the air")
{
    // TVGROUP_NORMAL_END only marks the end of the normal shows' range: no show has that kind
    bool32 stillActive = DoTVShowOnSlot(TVGROUP_NORMAL_END, TRUE);
    EXPECT_EQ(gSpecialVar_Result, TRUE);
    EXPECT_EQ(stillActive, FALSE);
}
