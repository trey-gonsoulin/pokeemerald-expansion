#include "global.h"
#include "battle.h"
#include "battle_arena.h"
#include "malloc.h"
#include "move.h"
#include "test/test.h"

// The Arena judges the attacker's move once, on its result against its target, as in Emerald
static s32 Test_ArenaSkillPoints(enum BattlerId target, u32 resultFlags, bool32 attackerProtected)
{
    s32 points;

    gBattleStruct = AllocZeroed(sizeof(*gBattleStruct));
    memset(gProtectStructs, 0, sizeof(gProtectStructs));
    gBattlersCount = 2;
    gBattlerTarget = target;
    gBattleStruct->moveResultFlags[target] = resultFlags;
    if (attackerProtected)
        gProtectStructs[B_BATTLER_0].protected = PROTECT_NORMAL;
    if (resultFlags & MOVE_RESULT_PROTECTED)
        gProtectStructs[B_BATTLER_1].protected = PROTECT_NORMAL;

    BattleArena_AddSkillPoints(B_BATTLER_0);

    points = gBattleStruct->arenaSkillPoints[B_BATTLER_0];
    TRY_FREE_AND_SET_NULL(gBattleStruct);
    memset(gProtectStructs, 0, sizeof(gProtectStructs));
    return points;
}

static s32 Test_ArenaSkillPointsForMove(u32 foeResultFlags, bool32 attackerProtected)
{
    return Test_ArenaSkillPoints(B_BATTLER_1, foeResultFlags, attackerProtected);
}

TEST("Battle Arena skill: a hit scores 1")
{
    EXPECT_EQ(Test_ArenaSkillPointsForMove(0, FALSE), 1);
}

TEST("Battle Arena skill: a super effective hit scores 2")
{
    EXPECT_EQ(Test_ArenaSkillPointsForMove(MOVE_RESULT_SUPER_EFFECTIVE, FALSE), 2);
}

TEST("Battle Arena skill: a not very effective hit loses 1")
{
    EXPECT_EQ(Test_ArenaSkillPointsForMove(MOVE_RESULT_NOT_VERY_EFFECTIVE, FALSE), -1);
}

TEST("Battle Arena skill: a miss loses 2")
{
    EXPECT_EQ(Test_ArenaSkillPointsForMove(MOVE_RESULT_MISSED, FALSE), -2);
}

TEST("Battle Arena skill: a move with no effect on the foe loses 2")
{
    EXPECT_EQ(Test_ArenaSkillPointsForMove(MOVE_RESULT_DOESNT_AFFECT_FOE, FALSE), -2);
}

TEST("Battle Arena skill: a move the foe protects from scores nothing")
{
    EXPECT_EQ(Test_ArenaSkillPointsForMove(MOVE_RESULT_PROTECTED, FALSE), 0);
}

TEST("Battle Arena skill: protecting itself scores nothing")
{
    EXPECT_EQ(Test_ArenaSkillPointsForMove(0, TRUE), 0);
}

TEST("Battle Arena skill: a move on the user scores 1")
{
    EXPECT_EQ(Test_ArenaSkillPoints(B_BATTLER_0, 0, FALSE), 1);
}

TEST("Battle Arena skill: a move on the user that fails loses 2")
{
    EXPECT_EQ(Test_ArenaSkillPoints(B_BATTLER_0, MOVE_RESULT_FAILED, FALSE), -2);
}
