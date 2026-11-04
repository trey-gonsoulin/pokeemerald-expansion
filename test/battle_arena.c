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
    gBattlerTarget = target;
    gBattleStruct->moveResultFlags[target] = resultFlags;
    if (attackerProtected)
        gProtectStructs[B_BATTLER_0].protected = PROTECT_NORMAL;

    BattleArena_AddSkillPoints(B_BATTLER_0);

    points = gBattleStruct->arenaSkillPoints[B_BATTLER_0];
    TRY_FREE_AND_SET_NULL(gBattleStruct);
    memset(gProtectStructs, 0, sizeof(gProtectStructs));
    gBattlerTarget = 0;
    return points;
}

TEST("Battle Arena skill: a hit scores 1")
{
    EXPECT_EQ(Test_ArenaSkillPoints(B_BATTLER_1, 0, FALSE), 1);
}

TEST("Battle Arena skill: a super effective hit scores 2")
{
    EXPECT_EQ(Test_ArenaSkillPoints(B_BATTLER_1, MOVE_RESULT_SUPER_EFFECTIVE, FALSE), 2);
}

TEST("Battle Arena skill: a not very effective hit loses 1")
{
    EXPECT_EQ(Test_ArenaSkillPoints(B_BATTLER_1, MOVE_RESULT_NOT_VERY_EFFECTIVE, FALSE), -1);
}

TEST("Battle Arena skill: a miss loses 2")
{
    EXPECT_EQ(Test_ArenaSkillPoints(B_BATTLER_1, MOVE_RESULT_MISSED, FALSE), -2);
}

TEST("Battle Arena skill: a move with no effect on the foe loses 2")
{
    EXPECT_EQ(Test_ArenaSkillPoints(B_BATTLER_1, MOVE_RESULT_DOESNT_AFFECT_FOE, FALSE), -2);
}

TEST("Battle Arena skill: a move the foe protects from scores nothing")
{
    EXPECT_EQ(Test_ArenaSkillPoints(B_BATTLER_1, MOVE_RESULT_PROTECTED, FALSE), 0);
}

TEST("Battle Arena skill: protecting itself scores nothing")
{
    EXPECT_EQ(Test_ArenaSkillPoints(B_BATTLER_1, 0, TRUE), 0);
}

TEST("Battle Arena skill: a stat move that changes nothing loses 2")
{
    EXPECT_EQ(Test_ArenaSkillPoints(B_BATTLER_1, MOVE_RESULT_STAT_CHANGE_PREVENTED, FALSE), -2);
    EXPECT_EQ(Test_ArenaSkillPoints(B_BATTLER_0, MOVE_RESULT_STAT_CHANGE_PREVENTED, FALSE), -2);
}

TEST("Battle Arena skill: a move on the user scores 1")
{
    EXPECT_EQ(Test_ArenaSkillPoints(B_BATTLER_0, 0, FALSE), 1);
}

TEST("Battle Arena skill: a move on the user that fails loses 2")
{
    EXPECT_EQ(Test_ArenaSkillPoints(B_BATTLER_0, MOVE_RESULT_FAILED, FALSE), -2);
}

// Perish Song lands on its user whatever the foe does, so the Arena judges it on the user's flags
static s32 Test_ArenaPerishSongSkillPoints(u32 foeResultFlags, u32 userResultFlags)
{
    s32 points;

    gBattleStruct = AllocZeroed(sizeof(*gBattleStruct));
    gCurrentMove = MOVE_PERISH_SONG;
    gBattlerTarget = B_BATTLER_1;
    gBattleStruct->moveResultFlags[B_BATTLER_1] = foeResultFlags;
    gBattleStruct->moveResultFlags[B_BATTLER_0] = userResultFlags;

    BattleArena_AddSkillPoints(B_BATTLER_0);

    points = gBattleStruct->arenaSkillPoints[B_BATTLER_0];
    TRY_FREE_AND_SET_NULL(gBattleStruct);
    gCurrentMove = MOVE_NONE;
    gBattlerTarget = 0;
    return points;
}

TEST("Battle Arena skill: Perish Song that a Soundproof foe blocks scores 1")
{
    ASSUME(GetMoveTarget(MOVE_PERISH_SONG) == TARGET_ALL_BATTLERS);
    EXPECT_EQ(Test_ArenaPerishSongSkillPoints(MOVE_RESULT_FAILED, 0), 1);
}

TEST("Battle Arena skill: Perish Song that fails loses 2")
{
    ASSUME(GetMoveTarget(MOVE_PERISH_SONG) == TARGET_ALL_BATTLERS);
    EXPECT_EQ(Test_ArenaPerishSongSkillPoints(MOVE_RESULT_FAILED, MOVE_RESULT_FAILED), -2);
}
