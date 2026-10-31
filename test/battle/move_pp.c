#include "global.h"
#include "move.h"
#include "test/test.h"

TEST("Move PP: Psychic Fangs has 10 PP from Gen 7")
{
    ASSUME(B_UPDATED_MOVE_DATA >= GEN_7);
    EXPECT_EQ(GetMovePP(MOVE_PSYCHIC_FANGS), 10);
}

TEST("Move PP: Victory Dance has 10 PP from Gen 9")
{
    ASSUME(B_UPDATED_MOVE_DATA >= GEN_9);
    EXPECT_EQ(GetMovePP(MOVE_VICTORY_DANCE), 10);
}

TEST("Move PP: Bitter Malice has 10 PP from Gen 9")
{
    ASSUME(B_UPDATED_MOVE_DATA >= GEN_9);
    EXPECT_EQ(GetMovePP(MOVE_BITTER_MALICE), 10);
}
