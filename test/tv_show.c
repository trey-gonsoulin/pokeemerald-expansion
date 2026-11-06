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

TEST("TV show: the dummied-out show ends the TV loop")
{
    DoTVShowOnSlot(TVSHOW_DUMMY, TRUE);
    EXPECT_EQ(gSpecialVar_Result, TRUE);
}

TEST("TV show: an active slot of an unknown kind ends the TV loop and goes off the air")
{
    // TVGROUP_NORMAL_END only marks the end of the normal shows' range: no show has that kind
    bool32 stillActive = DoTVShowOnSlot(TVGROUP_NORMAL_END, TRUE);
    EXPECT_EQ(gSpecialVar_Result, TRUE);
    EXPECT_EQ(stillActive, FALSE);
}
