#include "global.h"
#include "battle.h"
#include "battle_arena.h"
#include "malloc.h"
#include "move.h"
#include "test/test.h"

enum ArenaStatMove
{
    ARENA_NOT_STAT_MOVE_FAILURE,
    ARENA_STAT_MOVE_CHANGED_NOTHING,         // statMoveChangedNothing, on the user's own pass
    ARENA_BOUNCED_STAT_MOVE_CHANGED_NOTHING, // the same on the bouncer's pass
    ARENA_BOUNCE_PASS,                       // the bouncer's pass, with only the user's own pass marked
};

// The Arena judges the attacker's move once, on its result against its target, as in Emerald
static s32 Test_ArenaStatMoveSkillPoints(enum BattlerId target, u32 resultFlags, bool32 attackerProtected, enum ArenaStatMove statMove)
{
    s32 points;

    gBattleStruct = AllocZeroed(sizeof(*gBattleStruct));
    memset(gProtectStructs, 0, sizeof(gProtectStructs));
    gBattlerTarget = target;
    gBattleStruct->moveResultFlags[target] = resultFlags;
    if (attackerProtected)
        gProtectStructs[B_BATTLER_0].protected = PROTECT_NORMAL;
    switch (statMove)
    {
    case ARENA_NOT_STAT_MOVE_FAILURE:
        break;
    case ARENA_STAT_MOVE_CHANGED_NOTHING:
        gBattleStruct->statMoveChangedNothing = TRUE;
        break;
    case ARENA_BOUNCED_STAT_MOVE_CHANGED_NOTHING:
        gBattleStruct->bouncedMoveIsUsed = TRUE;
        gBattleStruct->bouncedStatMoveChangedNothing = TRUE;
        break;
    case ARENA_BOUNCE_PASS:
        gBattleStruct->bouncedMoveIsUsed = TRUE;
        gBattleStruct->statMoveChangedNothing = TRUE;
        break;
    }

    BattleArena_AddSkillPoints(B_BATTLER_0);

    points = gBattleStruct->arenaSkillPoints[B_BATTLER_0];
    TRY_FREE_AND_SET_NULL(gBattleStruct);
    memset(gProtectStructs, 0, sizeof(gProtectStructs));
    gBattlerTarget = 0;
    return points;
}

static s32 Test_ArenaSkillPoints(enum BattlerId target, u32 resultFlags, bool32 attackerProtected)
{
    return Test_ArenaStatMoveSkillPoints(target, resultFlags, attackerProtected, ARENA_NOT_STAT_MOVE_FAILURE);
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
    EXPECT_EQ(Test_ArenaStatMoveSkillPoints(B_BATTLER_1, MOVE_RESULT_STAT_CHANGE_PREVENTED, FALSE, ARENA_STAT_MOVE_CHANGED_NOTHING), -2);
    EXPECT_EQ(Test_ArenaStatMoveSkillPoints(B_BATTLER_0, MOVE_RESULT_STAT_CHANGE_PREVENTED, FALSE, ARENA_STAT_MOVE_CHANGED_NOTHING), -2);
}

TEST("Battle Arena skill: a stat move whose other effect worked scores 1")
{
    // Defog clearing Spikes past Clear Body, Defense Curl at +6 that newly curls the user up
    EXPECT_EQ(Test_ArenaSkillPoints(B_BATTLER_1, MOVE_RESULT_STAT_CHANGE_PREVENTED, FALSE), 1);
    EXPECT_EQ(Test_ArenaSkillPoints(B_BATTLER_0, MOVE_RESULT_STAT_CHANGE_PREVENTED, FALSE), 1);
}

TEST("Battle Arena skill: a bounced stat move that changes nothing loses 2 for the bouncer")
{
    EXPECT_EQ(Test_ArenaStatMoveSkillPoints(B_BATTLER_1, MOVE_RESULT_STAT_CHANGE_PREVENTED, FALSE, ARENA_BOUNCED_STAT_MOVE_CHANGED_NOTHING), -2);
    EXPECT_EQ(Test_ArenaStatMoveSkillPoints(B_BATTLER_1, MOVE_RESULT_STAT_CHANGE_PREVENTED, FALSE, ARENA_BOUNCE_PASS), 1);
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
static s32 Test_ArenaAllBattlersSkillPoints(enum Move move, u32 foeResultFlags, u32 userResultFlags, bool32 statMoveChangedNothing)
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
    EXPECT_EQ(Test_ArenaAllBattlersSkillPoints(MOVE_PERISH_SONG, MOVE_RESULT_FAILED, 0, FALSE), 1);
}

TEST("Battle Arena skill: Perish Song that fails loses 2")
{
    ASSUME(GetMoveTarget(MOVE_PERISH_SONG) == TARGET_ALL_BATTLERS);
    EXPECT_EQ(Test_ArenaAllBattlersSkillPoints(MOVE_PERISH_SONG, MOVE_RESULT_FAILED, MOVE_RESULT_FAILED, FALSE), -2);
}

TEST("Battle Arena skill: Flower Shield that raises only the foe's Defense scores 1")
{
    ASSUME(GetMoveTarget(MOVE_FLOWER_SHIELD) == TARGET_ALL_BATTLERS);
    EXPECT_EQ(Test_ArenaAllBattlersSkillPoints(MOVE_FLOWER_SHIELD, MOVE_RESULT_ATTEMPT_STAT_CHANGE, MOVE_RESULT_STAT_CHANGE_PREVENTED, FALSE), 1);
}

TEST("Battle Arena skill: Flower Shield that raises no one's Defense loses 2")
{
    ASSUME(GetMoveTarget(MOVE_FLOWER_SHIELD) == TARGET_ALL_BATTLERS);
    EXPECT_EQ(Test_ArenaAllBattlersSkillPoints(MOVE_FLOWER_SHIELD, MOVE_RESULT_STAT_CHANGE_PREVENTED, MOVE_RESULT_STAT_CHANGE_PREVENTED, TRUE), -2);
}
