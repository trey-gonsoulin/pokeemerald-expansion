#include "global.h"
#include "event_data.h"
#include "tv.h"
#include "constants/tv.h"
#include "test/test.h"

// EventScript_DoTVShow (data/scripts/tv.inc) calls DoTVShow until VAR_RESULT is TRUE,
// so a slot DoTVShow prints nothing for has to set it too, or the TV never turns off.
static void DoTVShowOnSlot(u32 kind, bool32 active)
{
    gSaveBlock1Ptr->tvShows[0].common.kind = kind;
    gSaveBlock1Ptr->tvShows[0].common.active = active;
    gSpecialVar_0x8004 = 0;
    gSpecialVar_Result = FALSE;
    DoTVShow();
}

TEST("TV show: an inactive slot ends the TV loop")
{
    TVShow saved = gSaveBlock1Ptr->tvShows[0];
    DoTVShowOnSlot(TVSHOW_FAN_CLUB_LETTER, FALSE);
    gSaveBlock1Ptr->tvShows[0] = saved;
    EXPECT_EQ(gSpecialVar_Result, TRUE);
}

TEST("TV show: an active slot of an unknown kind ends the TV loop")
{
    TVShow saved = gSaveBlock1Ptr->tvShows[0];
    DoTVShowOnSlot(TVSHOW_LILYCOVE_CONTEST_LADY + 1, TRUE);
    gSaveBlock1Ptr->tvShows[0] = saved;
    EXPECT_EQ(gSpecialVar_Result, TRUE);
}
