#include "global.h"
#include "test/test.h"
#include "battle.h"
#include "battle_message.h"
#include "malloc.h"
#include "move.h"
#include "string_util.h"
#include "constants/characters.h"
#include "constants/moves.h"

TEST("Battle Message: B_LAST_MOVE names an originally used Z-Move or Max Move")
{
    enum Move move = MOVE_NONE;
    u8 str[32], expected[32];
    u32 i;

    PARAMETRIZE { move = MOVE_BREAKNECK_BLITZ; }
    PARAMETRIZE { move = MOVE_MAX_STRIKE; }
    PARAMETRIZE { move = MOVE_TACKLE; }

    gBattleStruct = AllocZeroed(sizeof(*gBattleStruct));
    gBattleMsgDataPtr = AllocZeroed(sizeof(*gBattleMsgDataPtr));
    gBattleStruct->stringMoveType = TYPE_NORMAL;
    gBattleMsgDataPtr->originallyUsedMove = move;
    gBattleMsgDataPtr->currentMove = MOVE_POUND;
    BattleStringExpandPlaceholders(COMPOUND_STRING("{B_LAST_MOVE}"), str, sizeof(str));
    FREE_AND_SET_NULL(gBattleMsgDataPtr);
    FREE_AND_SET_NULL(gBattleStruct);

    // The expansion turns the name's spaces into non-breaking ones.
    StringCopy(expected, GetMoveName(move));
    for (i = 0; expected[i] != EOS; i++)
    {
        if (expected[i] == CHAR_SPACE)
            expected[i] = CHAR_NBSP;
    }
    EXPECT_EQ(StringCompare(str, expected), 0);
}
