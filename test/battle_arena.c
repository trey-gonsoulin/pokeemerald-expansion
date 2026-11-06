#include "global.h"
#include "battle.h"
#include "battle_arena.h"
#include "malloc.h"
#include "move.h"
#include "test/test.h"

// The Arena judges the attacker's (battler 0's) move once, on its result against its target, as in Emerald.
// statMoveChangedNothing marks the battlers whose stat move changed nothing, as StatChangeBeforeChange does.
static s32 Test_ArenaStatMoveSkillPoints(enum BattlerId target, u32 resultFlags, bool32 attackerProtected, u32 statMoveChangedNothing)
{
    s32 points;

    gBattleStruct = AllocZeroed(sizeof(*gBattleStruct));
    memset(gProtectStructs, 0, sizeof(gProtectStructs));
    gBattlerTarget = target;
    gBattleStruct->moveResultFlags[target] = resultFlags;
    gBattleStruct->statMoveChangedNothing = statMoveChangedNothing;
    if (attackerProtected)
        gProtectStructs[B_BATTLER_0].protected = PROTECT_NORMAL;

    BattleArena_AddSkillPoints(B_BATTLER_0);

    points = gBattleStruct->arenaSkillPoints[B_BATTLER_0];
    TRY_FREE_AND_SET_NULL(gBattleStruct);
    memset(gProtectStructs, 0, sizeof(gProtectStructs));
    gBattlerTarget = 0;
    return points;
}

static s32 Test_ArenaSkillPoints(enum BattlerId target, u32 resultFlags, bool32 attackerProtected)
{
    return Test_ArenaStatMoveSkillPoints(target, resultFlags, attackerProtected, 0);
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
    // Growl at -6, Swords Dance at +6
    EXPECT_EQ(Test_ArenaStatMoveSkillPoints(B_BATTLER_1, MOVE_RESULT_STAT_CHANGE_PREVENTED, FALSE, 1u << B_BATTLER_0), -2);
    EXPECT_EQ(Test_ArenaStatMoveSkillPoints(B_BATTLER_0, MOVE_RESULT_STAT_CHANGE_PREVENTED, FALSE, 1u << B_BATTLER_0), -2);
}

TEST("Battle Arena skill: a stat move whose other effect worked scores 1")
{
    // Defog clearing Spikes past Clear Body, Defense Curl at +6 that newly curls the user up
    EXPECT_EQ(Test_ArenaSkillPoints(B_BATTLER_1, MOVE_RESULT_STAT_CHANGE_PREVENTED, FALSE), 1);
    EXPECT_EQ(Test_ArenaSkillPoints(B_BATTLER_0, MOVE_RESULT_STAT_CHANGE_PREVENTED, FALSE), 1);
}

TEST("Battle Arena skill: a stat move that changes nothing loses 2 only for the battler that used it")
{
    // Battler 0 bounced battler 1's Growl back at -6, or battler 1's own stat move changed nothing
    EXPECT_EQ(Test_ArenaStatMoveSkillPoints(B_BATTLER_1, MOVE_RESULT_STAT_CHANGE_PREVENTED, FALSE, 1u << B_BATTLER_0), -2);
    EXPECT_EQ(Test_ArenaStatMoveSkillPoints(B_BATTLER_1, MOVE_RESULT_STAT_CHANGE_PREVENTED, FALSE, 1u << B_BATTLER_1), 1);
}

TEST("Battle Arena skill: a move on the user scores 1")
{
    EXPECT_EQ(Test_ArenaSkillPoints(B_BATTLER_0, 0, FALSE), 1);
}

TEST("Battle Arena skill: a move on the user that fails loses 2")
{
    EXPECT_EQ(Test_ArenaSkillPoints(B_BATTLER_0, MOVE_RESULT_FAILED, FALSE), -2);
}

// A move on every battler worked if it worked on anyone, so the Arena judges it on a battler it worked on
static s32 Test_ArenaAllBattlersSkillPoints(enum Move move, u32 foeResultFlags, u32 userResultFlags, u32 statMoveChangedNothing)
{
    s32 points;

    gBattleStruct = AllocZeroed(sizeof(*gBattleStruct));
    gBattleStruct->statMoveChangedNothing = statMoveChangedNothing;
    gBattlersCount = 2;
    gBattleMons[B_BATTLER_0].hp = gBattleMons[B_BATTLER_1].hp = 1;
    gCurrentMove = move;
    gBattlerTarget = B_BATTLER_1;
    gBattleStruct->moveResultFlags[B_BATTLER_1] = foeResultFlags;
    gBattleStruct->moveResultFlags[B_BATTLER_0] = userResultFlags;

    BattleArena_AddSkillPoints(B_BATTLER_0);

    points = gBattleStruct->arenaSkillPoints[B_BATTLER_0];
    TRY_FREE_AND_SET_NULL(gBattleStruct);
    gBattleMons[B_BATTLER_0].hp = gBattleMons[B_BATTLER_1].hp = 0;
    gBattlersCount = 0;
    gCurrentMove = MOVE_NONE;
    gBattlerTarget = 0;
    return points;
}

TEST("Battle Arena skill: Perish Song that a Soundproof foe blocks scores 1")
{
    ASSUME(GetMoveTarget(MOVE_PERISH_SONG) == TARGET_ALL_BATTLERS);
    EXPECT_EQ(Test_ArenaAllBattlersSkillPoints(MOVE_PERISH_SONG, MOVE_RESULT_FAILED, 0, 0), 1);
}

TEST("Battle Arena skill: Perish Song that fails loses 2")
{
    ASSUME(GetMoveTarget(MOVE_PERISH_SONG) == TARGET_ALL_BATTLERS);
    EXPECT_EQ(Test_ArenaAllBattlersSkillPoints(MOVE_PERISH_SONG, MOVE_RESULT_FAILED, MOVE_RESULT_FAILED, 0), -2);
}

TEST("Battle Arena skill: Flower Shield that raises only the foe's Defense scores 1")
{
    ASSUME(GetMoveTarget(MOVE_FLOWER_SHIELD) == TARGET_ALL_BATTLERS);
    EXPECT_EQ(Test_ArenaAllBattlersSkillPoints(MOVE_FLOWER_SHIELD, MOVE_RESULT_ATTEMPT_STAT_CHANGE, MOVE_RESULT_STAT_CHANGE_PREVENTED, 0), 1);
}

TEST("Battle Arena skill: Flower Shield that raises no one's Defense loses 2")
{
    ASSUME(GetMoveTarget(MOVE_FLOWER_SHIELD) == TARGET_ALL_BATTLERS);
    EXPECT_EQ(Test_ArenaAllBattlersSkillPoints(MOVE_FLOWER_SHIELD, MOVE_RESULT_STAT_CHANGE_PREVENTED, MOVE_RESULT_STAT_CHANGE_PREVENTED, 1u << B_BATTLER_0), -2);
}
