#include "global.h"
#include "overworld.h"
#include "test/test.h"
#include "constants/game_stat.h"

bool8 Script_StorytellerInitializeRandomStat(void);

TEST("Storyteller: a new tale is the one game stat that qualifies")
{
    u32 i, stat;
    PARAMETRIZE { stat = GAME_STAT_STARTED_TRENDS; }
    PARAMETRIZE { stat = GAME_STAT_ENTERED_HOT_SPRINGS; }

    memset(&gSaveBlock1Ptr->oldMan.storyteller, 0, sizeof(gSaveBlock1Ptr->oldMan.storyteller));
    ResetGameStats();
    SetGameStat(stat, 5);

    EXPECT(Script_StorytellerInitializeRandomStat());
    EXPECT_EQ(gSaveBlock1Ptr->oldMan.storyteller.gameStatIDs[0], stat);
    for (i = 1; i < NUM_STORYTELLER_TALES; i++)
        EXPECT_EQ(gSaveBlock1Ptr->oldMan.storyteller.gameStatIDs[i], 0);
}
