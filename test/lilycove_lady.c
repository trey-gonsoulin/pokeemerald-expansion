#include "global.h"
#include "event_data.h"
#include "item.h"
#include "string_util.h"
#include "test/test.h"

// Specials, declared in no header
void BufferQuizPrizeName(void);
void BufferQuizPrizeItem(void);

static void SetQuizPrize(enum Item prize)
{
    gSaveBlock1Ptr->lilycoveLady.quiz.prize = prize;
}

static void ExpectQuizPrize(enum Item expected)
{
    u8 name[ITEM_NAME_LENGTH + 1];

    gSpecialVar_0x8005 = ITEM_NONE;
    BufferQuizPrizeItem();
    EXPECT_EQ(gSpecialVar_0x8005, expected);

    BufferQuizPrizeName();
    CopyItemName(expected, name);
    EXPECT_EQ(StringCompare(gStringVar1, name), 0);
}

TEST("Quiz Lady prize: a TM the player doesn't own is given as is")
{
    SetQuizPrize(ITEM_TM_HYPER_BEAM);
    ExpectQuizPrize(ITEM_TM_HYPER_BEAM);
}

// Separate tests rather than PARAMETRIZE: the save blocks are only cleared between tests
TEST("Quiz Lady prize: a reusable TM in the bag becomes a PP Up")
{
    ASSUME(GetItemImportance(ITEM_TM_HYPER_BEAM));
    AddBagItem(ITEM_TM_HYPER_BEAM, 1);
    SetQuizPrize(ITEM_TM_HYPER_BEAM);
    ExpectQuizPrize(ITEM_PP_UP);
}

TEST("Quiz Lady prize: a reusable TM in the PC becomes a PP Up")
{
    ASSUME(GetItemImportance(ITEM_TM_HYPER_BEAM));
    AddPCItem(ITEM_TM_HYPER_BEAM, 1);
    SetQuizPrize(ITEM_TM_HYPER_BEAM);
    ExpectQuizPrize(ITEM_PP_UP);
}

TEST("Quiz Lady prize: an owned item that isn't important is given as is")
{
    ASSUME(!GetItemImportance(ITEM_RARE_CANDY));
    AddBagItem(ITEM_RARE_CANDY, 1);
    SetQuizPrize(ITEM_RARE_CANDY);
    ExpectQuizPrize(ITEM_RARE_CANDY);
}
