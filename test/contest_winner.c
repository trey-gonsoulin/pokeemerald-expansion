#include "global.h"
#include "contest.h"
#include "string_util.h"
#include "constants/contest.h"
#include "test/test.h"

static void SetUpContestWinner(const u8 *nickname, bool32 isShiny)
{
    s32 i;

    memset(gContestMons, 0, sizeof(gContestMons));
    for (i = 0; i < CONTESTANT_COUNT; i++)
        gContestFinalStandings[i] = i;
    gContestPlayerMonIndex = 0;
    gLinkContestFlags = 0;
    gSpecialVar_ContestCategory = CONTEST_CATEGORY_COOL;
    gSpecialVar_ContestRank = CONTEST_RANK_NORMAL;

    gContestMons[0].species = SPECIES_MASQUERAIN;
    StringCopy(gContestMons[0].nickname, nickname);
    StringCopy(gContestMons[0].trainerName, COMPOUND_STRING("TREY"));
    gContestMons[0].isShiny = isShiny;
    gContestMons[0].personality = 0x12345678;

    // A slot's old bytes are not EOS (0x00 is a space)
    memset(gSaveBlock1Ptr->contestWinners, 0, sizeof(gSaveBlock1Ptr->contestWinners));
    memset(&gCurContestWinner, 0, sizeof(gCurContestWinner));
}

TEST("Contest winner: a 10-letter name keeps its terminator in the Contest Hall")
{
    u8 id;

    SetUpContestWinner(COMPOUND_STRING("MASQUERAIN"), FALSE);
    SaveContestWinner(CONTEST_RANK_NORMAL);

    id = GetContestWinnerSaveIdx(CONTEST_RANK_NORMAL, FALSE);
    EXPECT_EQ(StringCompare(gSaveBlock1Ptr->contestWinners[id].monName, COMPOUND_STRING("MASQUERAIN")), 0);
}

TEST("Contest winner: a 12-letter nickname is cut to 10 letters for the Museum")
{
    u8 id;

    SetUpContestWinner(COMPOUND_STRING("ABCDEFGHIJKL"), FALSE);
    SaveContestWinner(CONTEST_SAVE_FOR_MUSEUM);

    id = GetContestWinnerSaveIdx(CONTEST_SAVE_FOR_MUSEUM, FALSE);
    EXPECT_EQ(StringCompare(gSaveBlock1Ptr->contestWinners[id].monName, COMPOUND_STRING("ABCDEFGHIJ")), 0);
}

TEST("Contest winner: the artist's painting keeps a 10-letter name's terminator")
{
    SetUpContestWinner(COMPOUND_STRING("MASQUERAIN"), FALSE);
    SaveContestWinner(CONTEST_SAVE_FOR_ARTIST);

    EXPECT_EQ(StringCompare(gCurContestWinner.monName, COMPOUND_STRING("MASQUERAIN")), 0);
}

TEST("Contest winner: a shiny winner stays shiny in the Contest Hall and the Museum")
{
    u8 id;

    SetUpContestWinner(COMPOUND_STRING("MASQUERAIN"), TRUE);
    SaveContestWinner(CONTEST_RANK_NORMAL);
    id = GetContestWinnerSaveIdx(CONTEST_RANK_NORMAL, FALSE);
    EXPECT(gSaveBlock1Ptr->contestWinners[id].isShiny);

    SaveContestWinner(CONTEST_SAVE_FOR_MUSEUM);
    id = GetContestWinnerSaveIdx(CONTEST_SAVE_FOR_MUSEUM, FALSE);
    EXPECT(gSaveBlock1Ptr->contestWinners[id].isShiny);
}

TEST("Contest winner: a winner that isn't shiny doesn't keep the old slot's shiny flag")
{
    u8 id;

    SetUpContestWinner(COMPOUND_STRING("MASQUERAIN"), FALSE);
    id = GetContestWinnerSaveIdx(CONTEST_SAVE_FOR_MUSEUM, FALSE);
    gSaveBlock1Ptr->contestWinners[id].isShiny = TRUE;
    SaveContestWinner(CONTEST_SAVE_FOR_MUSEUM);

    EXPECT(!gSaveBlock1Ptr->contestWinners[id].isShiny);
}
