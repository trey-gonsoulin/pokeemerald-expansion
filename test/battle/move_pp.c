#include "global.h"
#include "move.h"
#include "test/test.h"

TEST("Move PP: Psychic Fangs has 10 PP from Gen 7")
{
    EXPECT_EQ(GetMovePP(MOVE_PSYCHIC_FANGS), B_UPDATED_MOVE_DATA >= GEN_7 ? 10 : 15);
}

TEST("Move PP: Victory Dance has 10 PP from Gen 9")
{
    EXPECT_EQ(GetMovePP(MOVE_VICTORY_DANCE), B_UPDATED_MOVE_DATA >= GEN_9 ? 10 : 20);
}

TEST("Move PP: Bitter Malice has 10 PP from Gen 9")
{
    EXPECT_EQ(GetMovePP(MOVE_BITTER_MALICE), B_UPDATED_MOVE_DATA >= GEN_9 ? 10 : 15);
}
