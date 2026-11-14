#include "global.h"
#include "exp_formula.h"
#include "test/battle.h"

WILD_BATTLE_TEST("Pokemon gain experience after catching a Pokemon (Gen6+)")
{
    u8 level = 0;
    u32 config = 0;

    PARAMETRIZE { level = MAX_LEVEL; config = GEN_5; }
    PARAMETRIZE { level = 50;        config = GEN_5; }
    PARAMETRIZE { level = 50;        config = GEN_6; }

    GIVEN {
        WITH_CONFIG(B_EXP_CATCH, config);
        PLAYER(SPECIES_WOBBUFFET) { Level(level); }
        OPPONENT(SPECIES_CATERPIE) { HP(1); }
    } WHEN {
        TURN { USE_ITEM(player, ITEM_ULTRA_BALL, WITH_RNG(RNG_BALLTHROW_SHAKE, 0)); }
    } SCENE {
        MESSAGE("You used Ultra Ball!");
        ANIMATION(ANIM_TYPE_SPECIAL, B_ANIM_BALL_THROW, player);
        if (level != MAX_LEVEL && config >= GEN_6) {
            EXPERIENCE_BAR(player);
        } else {
            NOT EXPERIENCE_BAR(player);
        }
    }
}

WILD_BATTLE_TEST("Higher leveled Pokemon give more exp", s32 exp)
{
    u8 level = 0;

    PARAMETRIZE { level = 5; }
    PARAMETRIZE { level = 10; }

    GIVEN {
        WITH_CONFIG(B_EXP_OVERLEVEL_PENALTY, FALSE);
        PLAYER(SPECIES_WOBBUFFET) { Level(20); }
        OPPONENT(SPECIES_CATERPIE) { Level(level); HP(1); }
    } WHEN {
        TURN { MOVE(player, MOVE_SCRATCH); }
    } SCENE {
        MESSAGE("Wobbuffet used Scratch!");
        MESSAGE("The wild Caterpie fainted!");
        EXPERIENCE_BAR(player, captureGainedExp: &results[i].exp);
    } FINALLY {
        EXPECT_GT(results[1].exp, results[0].exp);
    }
}

WILD_BATTLE_TEST("Lucky Egg boosts gained exp points by 50%", s32 exp)
{
    enum Item item = ITEM_NONE;

    PARAMETRIZE { item = ITEM_LUCKY_EGG; }
    PARAMETRIZE { item = ITEM_NONE; }

    GIVEN {
        WITH_CONFIG(B_EXP_OVERLEVEL_PENALTY, FALSE);
        PLAYER(SPECIES_WOBBUFFET) { Level(20); Item(item); }
        OPPONENT(SPECIES_CATERPIE) { Level(10); HP(1); }
    } WHEN {
        TURN { MOVE(player, MOVE_SCRATCH); }
    } SCENE {
        MESSAGE("Wobbuffet used Scratch!");
        MESSAGE("The wild Caterpie fainted!");
        EXPERIENCE_BAR(player, captureGainedExp: &results[i].exp);
    } FINALLY {
        EXPECT_MUL_EQ(results[1].exp, Q_4_12(1.5), results[0].exp);
    }
}

#if (B_SCALED_EXP == GEN_5 || B_SCALED_EXP >= GEN_7)

WILD_BATTLE_TEST("Exp is scaled to player and opponent's levels", s32 exp)
{
    u8 level = 0;

    PARAMETRIZE { level = 5; }
    PARAMETRIZE { level = 10; }

    GIVEN {
        WITH_CONFIG(B_EXP_OVERLEVEL_PENALTY, FALSE);
        PLAYER(SPECIES_WOBBUFFET) { Level(level); }
        OPPONENT(SPECIES_CATERPIE) { Level(5); HP(1); }
    } WHEN {
        TURN { MOVE(player, MOVE_SCRATCH); }
    } SCENE {
        MESSAGE("Wobbuffet used Scratch!");
        MESSAGE("The wild Caterpie fainted!");
        EXPERIENCE_BAR(player, captureGainedExp: &results[i].exp);
    } FINALLY {
        EXPECT_GT(results[0].exp, results[1].exp);
    }
}

#endif

WILD_BATTLE_TEST("Large exp gains are supported", s32 exp) // #1455
{
    u8 level = 0;

    PARAMETRIZE { level = 10; }
    PARAMETRIZE { level = 50; }
    PARAMETRIZE { level = MAX_LEVEL; }

    GIVEN {
        PLAYER(SPECIES_WOBBUFFET) { Level(1); Item(ITEM_LUCKY_EGG); OTName("Test"); } // OT Name is different so it gets more exp as a traded mon
        OPPONENT(SPECIES_BLISSEY) { Level(level); HP(1); }
    } WHEN {
        TURN { MOVE(player, MOVE_SCRATCH); }
    } SCENE {
        MESSAGE("Wobbuffet used Scratch!");
        MESSAGE("The wild Blissey fainted!");
        EXPERIENCE_BAR(player, captureGainedExp: &results[i].exp);
    } THEN {
        EXPECT(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_LEVEL) > 1);
        EXPECT(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP) > 1);
    } FINALLY {
        EXPECT_GT(results[1].exp, results[0].exp);
        EXPECT_GT(results[2].exp, results[1].exp);
    }
}

WILD_BATTLE_TEST("Transformed Pokemon gives the experience points of the copied species in Gen 3 and 4")
{
    u32 speciesExp = 0;
    u32 gen = 0;
    s32 gainedExp;

    for (u32 j = GEN_1; j <= GEN_LATEST; j++)
    {
        if (j == GEN_3 || j == GEN_4)
        {
            PARAMETRIZE(speciesExp = SPECIES_BLISSEY, gen = j);
        }
        else
        {
            PARAMETRIZE(speciesExp = SPECIES_DITTO, gen = j);
        }
    }

    GIVEN {
        WITH_CONFIG(B_SCALED_EXP, GEN_3);
        WITH_CONFIG(B_TRANSFORM_BATTLE_REWARDS, gen);
        PLAYER(SPECIES_BLISSEY) { Level(1); Moves(MOVE_MEMENTO);}
        OPPONENT(SPECIES_DITTO) { Level(7); Ability(ABILITY_IMPOSTER); }
    } WHEN {
        TURN { MOVE(opponent, MOVE_MEMENTO); }
    } SCENE {
        EXPERIENCE_BAR(player, captureGainedExp: &gainedExp);
    } THEN {
        EXPECT_EQ(gainedExp, gSpeciesInfo[speciesExp].expYield);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP), 1 + gSpeciesInfo[speciesExp].expYield);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_HP_EV), gSpeciesInfo[speciesExp].evYield_HP);
    }
}

AI_DOUBLE_BATTLE_TEST("Both player Pokemon gain experience in double battles")
{
    GIVEN {
        PLAYER(SPECIES_WOBBUFFET) { Level(99); }
        PLAYER(SPECIES_DITTO) { Level(1); }
        OPPONENT(SPECIES_BRELOOM) { Moves(MOVE_MEMENTO); }
        OPPONENT(SPECIES_BRELOOM) { Moves(MOVE_CELEBRATE); }
    } WHEN {
        TURN { }
    } THEN {
        EXPECT(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP) > gExperienceTables[gSpeciesInfo[SPECIES_WOBBUFFET].growthRate][99]);
        EXPECT(GetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_LEVEL) > 1);
    }
}

AI_TWO_VS_ONE_BATTLE_TEST("Partner Pokemon do not gain experience")
{
    GIVEN {
        PLAYER(SPECIES_METAPOD) { Level(1); }
        PARTNER(SPECIES_DITTO) { Level(1); }
        OPPONENT(SPECIES_BRELOOM) { Moves(MOVE_MEMENTO); }
        OPPONENT(SPECIES_BRELOOM) { Moves(MOVE_CELEBRATE); }
    } WHEN {
        TURN { }
    } THEN {
        EXPECT_GT(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_LEVEL), 1);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PARTNER][0], MON_DATA_LEVEL), 1);
    }
}

AI_ONE_VS_TWO_BATTLE_TEST("Both opponent's Pokemon give experience in battle against two opponents")
{
    u32 expectedXp = 1; // level 1 xp
    expectedXp += gSpeciesInfo[SPECIES_WYNAUT].expYield * 100 / 7; // level (100) * scaling multipler (1 / 7)
    expectedXp += gSpeciesInfo[SPECIES_WOBBUFFET].expYield * 100 / 7;
    GIVEN {
        WITH_CONFIG(B_SCALED_EXP, GEN_3);
        WITH_CONFIG(B_UNEVOLVED_EXP_MULTIPLIER, GEN_3);
        PLAYER(SPECIES_METAPOD) { Level(1); Speed(3); }
        PLAYER(SPECIES_WOBBUFFET) { Level(100); Speed(3); }
        OPPONENT_B(SPECIES_WYNAUT) { Moves(MOVE_MEMENTO); Speed(2); }
        OPPONENT_B(SPECIES_WYNAUT) { Moves(MOVE_CELEBRATE); Speed(1); }
        OPPONENT_A(SPECIES_WOBBUFFET) { Moves(MOVE_MEMENTO); Speed(1); }
        OPPONENT_A(SPECIES_WOBBUFFET) { Moves(MOVE_CELEBRATE); Speed(1); }
    } WHEN {
        TURN { }
    } THEN {
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP), expectedXp);
    }
}

// "Exp award:" tests cover the fork's exp fixes (end-of-turn faints, opponent B's party) and the Gen 6 Exp. Share flag.
// Under WITH_EXP_AWARD_CONFIGS, every participant gains expYield * level / 7 (Cmd_getexp, no level scaling or bonus multipliers)
// and every Gen 6 Exp. Share mon gains half that (the over-level penalty off). Cmd_getexp also reads the raw B_SPLIT_EXP macro, hence the ASSUME.
#define WITH_EXP_AWARD_CONFIGS()                        \
    ASSUME(B_SPLIT_EXP >= GEN_6);                       \
    WITH_CONFIG(B_SPLIT_EXP, GEN_6);                    \
    WITH_CONFIG(B_SCALED_EXP, GEN_3);                   \
    WITH_CONFIG(B_EXP_OVERLEVEL_PENALTY, FALSE);        \
    WITH_CONFIG(B_UNEVOLVED_EXP_MULTIPLIER, GEN_3);     \
    WITH_CONFIG(B_TRAINER_EXP_MULTIPLIER, GEN_8)
#define EXP_YIELD(species, level) (gSpeciesInfo[species].expYield * (level) / 7)
#define EXP_AT_LEVEL(species, level) (gExperienceTables[gSpeciesInfo[species].growthRate][level])

AI_SINGLE_BATTLE_TEST("Exp award: a trainer's Pokemon gives 1.5x exp up to Gen 6 only (#140)")
{
    u32 gen = 0, expected = 0;
    PARAMETRIZE { gen = GEN_6; expected = EXP_YIELD(SPECIES_TREECKO, 15) * 150 / 100; }
    PARAMETRIZE { gen = GEN_7; expected = EXP_YIELD(SPECIES_TREECKO, 15); }
    PARAMETRIZE { gen = GEN_8; expected = EXP_YIELD(SPECIES_TREECKO, 15); }
    GIVEN {
        WITH_EXP_AWARD_CONFIGS();
        WITH_CONFIG(B_TRAINER_EXP_MULTIPLIER, gen);
        PLAYER(SPECIES_WOBBUFFET) { Level(15); }
        OPPONENT(SPECIES_TREECKO) { Level(15); HP(1); Moves(MOVE_CELEBRATE); }
    } WHEN {
        TURN { MOVE(player, MOVE_SCRATCH); }
    } SCENE {
        MESSAGE("The opposing Treecko fainted!");
        EXPERIENCE_BAR(player);
    } THEN {
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WOBBUFFET, 15) + expected);
    }
}

WILD_BATTLE_TEST("Exp award: a wild Pokemon gives no 1.5x exp in Gen 6 (#140)")
{
    GIVEN {
        WITH_EXP_AWARD_CONFIGS();
        WITH_CONFIG(B_TRAINER_EXP_MULTIPLIER, GEN_6);
        PLAYER(SPECIES_WOBBUFFET) { Level(15); }
        OPPONENT(SPECIES_TREECKO) { Level(15); HP(1); Moves(MOVE_CELEBRATE); }
    } WHEN {
        TURN { MOVE(player, MOVE_SCRATCH); }
    } SCENE {
        MESSAGE("The wild Treecko fainted!");
        EXPERIENCE_BAR(player);
    } THEN {
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WOBBUFFET, 15) + EXP_YIELD(SPECIES_TREECKO, 15));
    }
}

AI_SINGLE_BATTLE_TEST("Exp award: Pokemon gain experience once when the opponent's last Pokemon faints from end-of-turn damage")
{
    u32 status, playerSpeed;
    PARAMETRIZE { status = STATUS1_POISON; playerSpeed = 1; }
    PARAMETRIZE { status = STATUS1_POISON; playerSpeed = 100; }
    PARAMETRIZE { status = STATUS1_BURN;   playerSpeed = 1; }
    PARAMETRIZE { status = STATUS1_BURN;   playerSpeed = 100; }
    GIVEN {
        WITH_EXP_AWARD_CONFIGS();
        PLAYER(SPECIES_WOBBUFFET) { Level(15); Speed(playerSpeed); }
        OPPONENT(SPECIES_TREECKO) { Level(15); HP(1); Speed(50); Status1(status); Moves(MOVE_CELEBRATE); }
    } WHEN {
        TURN { MOVE(player, MOVE_CELEBRATE); }
    } SCENE {
        MESSAGE("The opposing Treecko fainted!");
        EXPERIENCE_BAR(player);
        NOT EXPERIENCE_BAR(player);
    } THEN {
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WOBBUFFET, 15) + EXP_YIELD(SPECIES_TREECKO, 15));
    }
}

WILD_BATTLE_TEST("Exp award: Pokemon gain experience once when the wild Pokemon faints from end-of-turn damage")
{
    u32 status;
    PARAMETRIZE { status = STATUS1_POISON; }
    PARAMETRIZE { status = STATUS1_BURN; }
    GIVEN {
        WITH_EXP_AWARD_CONFIGS();
        PLAYER(SPECIES_WOBBUFFET) { Level(15); }
        OPPONENT(SPECIES_TREECKO) { Level(15); HP(1); Status1(status); Moves(MOVE_CELEBRATE); }
    } WHEN {
        TURN { MOVE(player, MOVE_CELEBRATE); }
    } SCENE {
        MESSAGE("The wild Treecko fainted!");
        EXPERIENCE_BAR(player);
        NOT EXPERIENCE_BAR(player);
    } THEN {
        EXPECT_EQ(gBattleOutcome, B_OUTCOME_WON);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WOBBUFFET, 15) + EXP_YIELD(SPECIES_TREECKO, 15));
    }
}

AI_DOUBLE_BATTLE_TEST("Exp award: Both player Pokemon gain experience once from each opponent fainting from end-of-turn damage")
{
    GIVEN {
        WITH_EXP_AWARD_CONFIGS();
        PLAYER(SPECIES_WOBBUFFET) { Level(20); }
        PLAYER(SPECIES_WYNAUT) { Level(20); }
        OPPONENT(SPECIES_TREECKO) { Level(10); HP(1); Status1(STATUS1_POISON); Moves(MOVE_CELEBRATE); }
        OPPONENT(SPECIES_MUDKIP) { Level(12); HP(1); Status1(STATUS1_POISON); Moves(MOVE_CELEBRATE); }
    } WHEN {
        TURN { MOVE(playerLeft, MOVE_CELEBRATE); MOVE(playerRight, MOVE_CELEBRATE); }
    } SCENE {
        MESSAGE("The opposing Treecko fainted!");
        MESSAGE("The opposing Mudkip fainted!");
    } THEN {
        u32 gain = EXP_YIELD(SPECIES_TREECKO, 10) + EXP_YIELD(SPECIES_MUDKIP, 12);
        EXPECT_EQ(gBattleOutcome, B_OUTCOME_WON);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WOBBUFFET, 20) + gain);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WYNAUT, 20) + gain);
    }
}

AI_SINGLE_BATTLE_TEST("Exp award: No experience is given when the player's last Pokemon faints from end-of-turn damage")
{
    u32 opponentFaints;
    PARAMETRIZE { opponentFaints = FALSE; }
    PARAMETRIZE { opponentFaints = TRUE; }
    GIVEN {
        WITH_EXP_AWARD_CONFIGS();
        PLAYER(SPECIES_WOBBUFFET) { Level(15); HP(1); Speed(1); Status1(STATUS1_POISON); }
        OPPONENT(SPECIES_TREECKO) { Level(15); HP(1); Speed(50); Status1(opponentFaints ? STATUS1_POISON : STATUS1_NONE); Moves(MOVE_CELEBRATE); }
        OPPONENT(SPECIES_WOBBUFFET) { Speed(50); Moves(MOVE_CELEBRATE); }
    } WHEN {
        TURN { MOVE(player, MOVE_CELEBRATE); }
    } SCENE {
        if (opponentFaints)
            MESSAGE("The opposing Treecko fainted!");
        NOT EXPERIENCE_BAR(player);
        MESSAGE("Wobbuffet fainted!");
        NONE_OF {
            MESSAGE("Wobbuffet fainted!");
            EXPERIENCE_BAR(player);
        }
    } THEN {
        // The opposing Treecko faints first, but the battle is lost by the time the fainted mons are handled,
        // and the fainted Wobbuffet gets no exp for it.
        EXPECT_EQ(gBattleOutcome, B_OUTCOME_LOST);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_OPPONENT_A][0], MON_DATA_HP) == 0, opponentFaints);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WOBBUFFET, 15));
    }
}

// A win decided at the end of the turn now runs ENDTURN_DYNAMAX (the fork's jump lands on ENDTURN_FAINTED_MON_ACTIONS, just before it),
// so the Dynamaxed winner reverts once. A win decided by a move skips the end-of-turn events, so nothing reverts on screen.
// Player Dynamax is off in-game (B_FLAG_DYNAMAX_BATTLE is 0 and there is no Dynamax Band), but tests skip those checks.
AI_SINGLE_BATTLE_TEST("Exp award: Dynamax ends once after an end-of-turn win, and not after a win by a move")
{
    u32 endTurnFaint;
    PARAMETRIZE { endTurnFaint = FALSE; }
    PARAMETRIZE { endTurnFaint = TRUE; }
    GIVEN {
        PLAYER(SPECIES_WOBBUFFET) { Level(50); Speed(100); }
        OPPONENT(SPECIES_TREECKO) { Level(15); HP(1); Speed(50); Status1(endTurnFaint ? STATUS1_POISON : STATUS1_NONE); Moves(MOVE_CELEBRATE); }
    } WHEN {
        TURN { MOVE(player, endTurnFaint ? MOVE_CELEBRATE : MOVE_SCRATCH, gimmick: GIMMICK_DYNAMAX); }
    } SCENE {
        ANIMATION(ANIM_TYPE_GENERAL, B_ANIM_DYNAMAX_GROWTH, player);
        MESSAGE("The opposing Treecko fainted!");
        EXPERIENCE_BAR(player);
        if (endTurnFaint)
            ANIMATION(ANIM_TYPE_GENERAL, B_ANIM_FORM_CHANGE, player);
        NONE_OF {
            ANIMATION(ANIM_TYPE_GENERAL, B_ANIM_FORM_CHANGE, player);
            EXPERIENCE_BAR(player);
        }
    } THEN {
        EXPECT_EQ(gBattleOutcome, B_OUTCOME_WON);
    }
}

WILD_BATTLE_TEST("Exp award: Gen 6 Exp. Share gives the rest of the team half experience and prints its message once")
{
    GIVEN {
        ASSUME(I_EXP_SHARE_FLAG > TEMP_FLAGS_END);
        WITH_EXP_AWARD_CONFIGS();
        FLAG_SET(I_EXP_SHARE_FLAG);
        PLAYER(SPECIES_WOBBUFFET) { Level(20); }
        PLAYER(SPECIES_WYNAUT) { Level(20); }
        PLAYER(SPECIES_WYNAUT) { Level(25); }
        OPPONENT(SPECIES_CATERPIE) { Level(10); HP(1); }
    } WHEN {
        TURN { MOVE(player, MOVE_SCRATCH); }
    } SCENE {
        MESSAGE("The wild Caterpie fainted!");
        EXPERIENCE_BAR(player);
        MESSAGE("The rest of your team gained Exp. Points thanks to the Exp. Share!");
        NOT MESSAGE("The rest of your team gained Exp. Points thanks to the Exp. Share!");
    } THEN {
        u32 gain = EXP_YIELD(SPECIES_CATERPIE, 10);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WOBBUFFET, 20) + gain);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WYNAUT, 20) + gain / 2);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][2], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WYNAUT, 25) + gain / 2);
    }
}

AI_SINGLE_BATTLE_TEST("Exp award: Gen 6 Exp. Share gives experience once when the opponent's last Pokemon faints from end-of-turn damage")
{
    GIVEN {
        ASSUME(I_EXP_SHARE_FLAG > TEMP_FLAGS_END);
        WITH_EXP_AWARD_CONFIGS();
        FLAG_SET(I_EXP_SHARE_FLAG);
        PLAYER(SPECIES_WOBBUFFET) { Level(15); }
        PLAYER(SPECIES_WYNAUT) { Level(15); }
        OPPONENT(SPECIES_TREECKO) { Level(15); HP(1); Status1(STATUS1_POISON); Moves(MOVE_CELEBRATE); }
    } WHEN {
        TURN { MOVE(player, MOVE_CELEBRATE); }
    } SCENE {
        MESSAGE("The opposing Treecko fainted!");
        EXPERIENCE_BAR(player);
        MESSAGE("The rest of your team gained Exp. Points thanks to the Exp. Share!");
        NONE_OF {
            MESSAGE("The rest of your team gained Exp. Points thanks to the Exp. Share!");
            EXPERIENCE_BAR(player);
        }
    } THEN {
        u32 gain = EXP_YIELD(SPECIES_TREECKO, 15);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WOBBUFFET, 15) + gain);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WYNAUT, 15) + gain / 2);
    }
}

AI_ONE_VS_TWO_BATTLE_TEST("Exp award: Every Pokemon of opponent B gives experience in battle against two opponents")
{
    u32 koBoth;
    PARAMETRIZE { koBoth = FALSE; }
    PARAMETRIZE { koBoth = TRUE; }
    GIVEN {
        WITH_EXP_AWARD_CONFIGS();
        PLAYER(SPECIES_WOBBUFFET) { Level(20); Speed(100); }
        PLAYER(SPECIES_WYNAUT) { Level(20); Speed(100); }
        OPPONENT_A(SPECIES_WOBBUFFET) { Level(10); Speed(50); Moves(MOVE_CELEBRATE); }
        OPPONENT_B(SPECIES_CATERPIE) { Level(10); HP(1); Speed(50); Moves(MOVE_CELEBRATE); }
        OPPONENT_B(SPECIES_CATERPIE) { Level(10); HP(1); Speed(50); Moves(MOVE_CELEBRATE); }
    } WHEN {
        TURN { MOVE(playerLeft, MOVE_SCRATCH, target: opponentRight); MOVE(playerRight, MOVE_CELEBRATE); }
        if (koBoth)
            TURN { MOVE(playerLeft, MOVE_SCRATCH, target: opponentRight); MOVE(playerRight, MOVE_CELEBRATE); }
    } THEN {
        u32 gain = EXP_YIELD(SPECIES_CATERPIE, 10) * (koBoth ? 2 : 1);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WOBBUFFET, 20) + gain);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WYNAUT, 20) + gain);
    }
}

AI_ONE_VS_TWO_BATTLE_TEST("Exp award: Gen 6 Exp. Share gives experience once for every Pokemon of opponent B")
{
    u32 koBoth;
    PARAMETRIZE { koBoth = FALSE; }
    PARAMETRIZE { koBoth = TRUE; }
    GIVEN {
        ASSUME(I_EXP_SHARE_FLAG > TEMP_FLAGS_END);
        WITH_EXP_AWARD_CONFIGS();
        FLAG_SET(I_EXP_SHARE_FLAG);
        PLAYER(SPECIES_WOBBUFFET) { Level(20); Speed(100); }
        PLAYER(SPECIES_WYNAUT) { Level(20); Speed(100); }
        PLAYER(SPECIES_WYNAUT) { Level(25); Speed(100); }
        OPPONENT_A(SPECIES_WOBBUFFET) { Level(10); Speed(50); Moves(MOVE_CELEBRATE); }
        OPPONENT_B(SPECIES_CATERPIE) { Level(10); HP(1); Speed(50); Moves(MOVE_CELEBRATE); }
        OPPONENT_B(SPECIES_CATERPIE) { Level(10); HP(1); Speed(50); Moves(MOVE_CELEBRATE); }
    } WHEN {
        TURN { MOVE(playerLeft, MOVE_SCRATCH, target: opponentRight); MOVE(playerRight, MOVE_CELEBRATE); }
        if (koBoth)
            TURN { MOVE(playerLeft, MOVE_SCRATCH, target: opponentRight); MOVE(playerRight, MOVE_CELEBRATE); }
    } SCENE {
        MESSAGE("The rest of your team gained Exp. Points thanks to the Exp. Share!");
        if (koBoth)
            MESSAGE("The rest of your team gained Exp. Points thanks to the Exp. Share!");
        NOT MESSAGE("The rest of your team gained Exp. Points thanks to the Exp. Share!");
    } THEN {
        u32 kos = koBoth ? 2 : 1;
        u32 gain = EXP_YIELD(SPECIES_CATERPIE, 10);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WOBBUFFET, 20) + gain * kos);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WYNAUT, 20) + gain * kos);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][2], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WYNAUT, 25) + (gain / 2) * kos);
    }
}

// The fainted foe's givenExpMons bit stayed set after Revival Blessing, so its second faint gave nothing.
AI_SINGLE_BATTLE_TEST("Exp award: A foe revived by Revival Blessing gives experience again when it faints again")
{
    GIVEN {
        WITH_EXP_AWARD_CONFIGS();
        PLAYER(SPECIES_WOBBUFFET) { Level(20); Speed(100); }
        OPPONENT(SPECIES_WYNAUT) { Level(10); HP(1); Speed(50); Moves(MOVE_CELEBRATE); }
        OPPONENT(SPECIES_PICHU) { Level(10); HP(1); Speed(50); Moves(MOVE_REVIVAL_BLESSING); }
    } WHEN {
        TURN { MOVE(player, MOVE_DRAGON_RAGE); }
        TURN { MOVE(player, MOVE_CELEBRATE); }
        TURN { MOVE(player, MOVE_DRAGON_RAGE); }
        TURN { MOVE(player, MOVE_DRAGON_RAGE); }
    } SCENE {
        MESSAGE("Wynaut was revived and is ready to fight again!");
    } THEN {
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WOBBUFFET, 20) + EXP_YIELD(SPECIES_WYNAUT, 10) * 2 + EXP_YIELD(SPECIES_PICHU, 10));
    }
}

// Opponent B's bits are givenExpMons[1], which the revive has to clear rather than opponent A's.
AI_ONE_VS_TWO_BATTLE_TEST("Exp award: A foe of opponent B revived by Revival Blessing gives experience again when it faints again")
{
    GIVEN {
        WITH_EXP_AWARD_CONFIGS();
        PLAYER(SPECIES_WOBBUFFET) { Level(20); Speed(100); }
        PLAYER(SPECIES_WYNAUT) { Level(20); Speed(100); }
        OPPONENT_A(SPECIES_WOBBUFFET) { Level(10); Speed(50); Moves(MOVE_CELEBRATE); }
        OPPONENT_B(SPECIES_WYNAUT) { Level(10); HP(1); Speed(50); Moves(MOVE_CELEBRATE); }
        OPPONENT_B(SPECIES_PICHU) { Level(10); HP(1); Speed(50); Moves(MOVE_REVIVAL_BLESSING); }
    } WHEN {
        TURN { MOVE(playerLeft, MOVE_DRAGON_RAGE, target: opponentRight); MOVE(playerRight, MOVE_CELEBRATE); }
        TURN { MOVE(playerLeft, MOVE_CELEBRATE); MOVE(playerRight, MOVE_CELEBRATE); }
        TURN { MOVE(playerLeft, MOVE_DRAGON_RAGE, target: opponentRight); MOVE(playerRight, MOVE_CELEBRATE); }
        TURN { MOVE(playerLeft, MOVE_DRAGON_RAGE, target: opponentRight); MOVE(playerRight, MOVE_CELEBRATE); }
    } SCENE {
        MESSAGE("Wynaut was revived and is ready to fight again!");
    } THEN {
        u32 gain = EXP_YIELD(SPECIES_WYNAUT, 10) * 2 + EXP_YIELD(SPECIES_PICHU, 10);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WOBBUFFET, 20) + gain);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WYNAUT, 20) + gain);
    }
}

// Reviving the fainted partner sends it straight back out, the other way the revived foe can faint again.
AI_DOUBLE_BATTLE_TEST("Exp award: A foe's partner revived onto the field by Revival Blessing gives experience again when it faints again")
{
    GIVEN {
        WITH_EXP_AWARD_CONFIGS();
        PLAYER(SPECIES_WOBBUFFET) { Level(20); Speed(100); }
        PLAYER(SPECIES_WYNAUT) { Level(20); Speed(100); }
        OPPONENT(SPECIES_WYNAUT) { Level(10); HP(1); Speed(50); Moves(MOVE_CELEBRATE); }
        OPPONENT(SPECIES_PICHU) { Level(10); HP(1); Speed(50); Moves(MOVE_REVIVAL_BLESSING); }
    } WHEN {
        TURN { MOVE(playerLeft, MOVE_DRAGON_RAGE, target: opponentLeft); MOVE(playerRight, MOVE_CELEBRATE); }
        TURN { MOVE(playerLeft, MOVE_DRAGON_RAGE, target: opponentLeft); MOVE(playerRight, MOVE_DRAGON_RAGE, target: opponentRight); }
    } SCENE {
        MESSAGE("The opposing Wynaut fainted!");
        MESSAGE("Wynaut was revived and is ready to fight again!");
        MESSAGE("The opposing Wynaut fainted!");
    } THEN {
        u32 gain = EXP_YIELD(SPECIES_WYNAUT, 10) * 2 + EXP_YIELD(SPECIES_PICHU, 10);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WOBBUFFET, 20) + gain);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WYNAUT, 20) + gain);
    }
}

// The same bit stayed set after the trainer AI's Revive or Max Revive (BS_ItemRestoreHP).
AI_SINGLE_BATTLE_TEST("Exp award: A foe revived by the trainer's Revive gives experience again when it faints again")
{
    GIVEN {
        WITH_EXP_AWARD_CONFIGS();
        VAR_SET(TESTING_VAR_AI_TRAINER_ITEM, ITEM_REVIVE);
        PLAYER(SPECIES_WOBBUFFET) { Level(20); Speed(100); }
        OPPONENT(SPECIES_WYNAUT) { Level(10); HP(1); Speed(50); Moves(MOVE_CELEBRATE); }
        OPPONENT(SPECIES_PICHU) { Level(10); HP(1); Speed(50); Moves(MOVE_CELEBRATE); }
    } WHEN {
        TURN { MOVE(player, MOVE_DRAGON_RAGE); }
        TURN { MOVE(player, MOVE_CELEBRATE); }
        TURN { MOVE(player, MOVE_DRAGON_RAGE); }
        TURN { MOVE(player, MOVE_DRAGON_RAGE); }
    } SCENE {
        MESSAGE("Wynaut had its HP restored.");
    } THEN {
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WOBBUFFET, 20) + EXP_YIELD(SPECIES_WYNAUT, 10) * 2 + EXP_YIELD(SPECIES_PICHU, 10));
    }
}

// Opponent B's Pokemon use the trainer's items too, and the revive has to clear opponent B's bits.
AI_ONE_VS_TWO_BATTLE_TEST("Exp award: A foe of opponent B revived by a Max Revive gives experience again when it faints again")
{
    GIVEN {
        WITH_EXP_AWARD_CONFIGS();
        VAR_SET(TESTING_VAR_AI_TRAINER_ITEM, ITEM_MAX_REVIVE);
        PLAYER(SPECIES_WOBBUFFET) { Level(20); Speed(100); }
        PLAYER(SPECIES_WYNAUT) { Level(20); Speed(100); }
        OPPONENT_A(SPECIES_WOBBUFFET) { Level(10); Speed(50); Moves(MOVE_CELEBRATE); }
        OPPONENT_B(SPECIES_WYNAUT) { Level(10); HP(1); MaxHP(40); Speed(50); Moves(MOVE_CELEBRATE); }
        OPPONENT_B(SPECIES_PICHU) { Level(10); HP(1); Speed(50); Moves(MOVE_CELEBRATE); }
    } WHEN {
        TURN { MOVE(playerLeft, MOVE_DRAGON_RAGE, target: opponentRight); MOVE(playerRight, MOVE_CELEBRATE); }
        TURN { MOVE(playerLeft, MOVE_CELEBRATE); MOVE(playerRight, MOVE_CELEBRATE); }
        TURN { MOVE(playerLeft, MOVE_DRAGON_RAGE, target: opponentRight); MOVE(playerRight, MOVE_CELEBRATE); }
        TURN { MOVE(playerLeft, MOVE_DRAGON_RAGE, target: opponentRight); MOVE(playerRight, MOVE_CELEBRATE); }
    } SCENE {
        MESSAGE("Wynaut had its HP restored.");
    } THEN {
        u32 gain = EXP_YIELD(SPECIES_WYNAUT, 10) * 2 + EXP_YIELD(SPECIES_PICHU, 10);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WOBBUFFET, 20) + gain);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WYNAUT, 20) + gain);
    }
}

// The partner's replacement has party index 1 in its own party, which used to mark the player's benched second Pokemon as sent in.
AI_TWO_VS_ONE_BATTLE_TEST("Exp award: The partner's replacement does not give experience to the player's benched Pokemon")
{
    GIVEN {
        WITH_EXP_AWARD_CONFIGS();
        PLAYER(SPECIES_WOBBUFFET) { Level(50); Speed(50); }
        PLAYER(SPECIES_WYNAUT) { Level(20); Speed(50); }
        PARTNER(SPECIES_WOBBUFFET) { Level(50); Speed(100); Moves(MOVE_MEMENTO); }
        PARTNER(SPECIES_WOBBUFFET) { Level(50); Speed(100); Moves(MOVE_CELEBRATE); }
        OPPONENT(SPECIES_TREECKO) { Level(10); HP(1); Speed(10); Moves(MOVE_CELEBRATE); }
        OPPONENT(SPECIES_TREECKO) { Level(10); Speed(10); Moves(MOVE_CELEBRATE); }
        OPPONENT(SPECIES_TREECKO) { Level(10); Speed(10); Moves(MOVE_CELEBRATE); }
    } WHEN {
        TURN { MOVE(playerLeft, MOVE_CELEBRATE); MOVE(playerRight, MOVE_MEMENTO, target: opponentRight); SEND_OUT(playerRight, 1); }
        TURN { MOVE(playerLeft, MOVE_SCRATCH, target: opponentLeft); MOVE(playerRight, MOVE_CELEBRATE); }
    } SCENE {
        MESSAGE("The opposing Treecko fainted!");
    } THEN {
        EXPECT_EQ(gBattlerPartyIndexes[GetBattlerAtPosition(B_POSITION_PLAYER_RIGHT)], 1);
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WOBBUFFET, 50) + EXP_YIELD(SPECIES_TREECKO, 10));
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_EXP), EXP_AT_LEVEL(SPECIES_WYNAUT, 20));
    }
}

// The partner's first Pokemon has party index 0 too, so matching on gBattlerPartyIndexes alone handed it the move as well.
// The forget-a-move path (Cmd_yesnoboxlearnmove) had the same check, but tests always decline to learn there.
AI_TWO_VS_ONE_BATTLE_TEST("Exp award: A move learned on level up is not given to the partner's Pokemon")
{
    GIVEN {
        PLAYER(SPECIES_CATERPIE) { Level(8); Moves(MOVE_TACKLE); }
        PARTNER(SPECIES_WOBBUFFET) { Level(8); Moves(MOVE_CELEBRATE); }
        OPPONENT(SPECIES_BRELOOM) { Level(15); Moves(MOVE_MEMENTO); }
        OPPONENT(SPECIES_BRELOOM) { Level(15); Moves(MOVE_CELEBRATE); }
    } WHEN {
        TURN { }
    } THEN {
        enum BattlerId player = GetBattlerAtPosition(B_POSITION_PLAYER_LEFT);
        enum BattlerId partner = GetBattlerAtPosition(B_POSITION_PLAYER_RIGHT);
        u32 playerKnows = 0, partnerKnows = 0;
        for (u32 i = 0; i < MAX_MON_MOVES; i++)
        {
            playerKnows += gBattleMons[player].moves[i] == MOVE_BUG_BITE;
            partnerKnows += gBattleMons[partner].moves[i] == MOVE_BUG_BITE;
        }
        EXPECT_EQ(gBattlerPartyIndexes[partner], 0);
        EXPECT_EQ(playerKnows, 1);
        EXPECT_EQ(partnerKnows, 0);
    }
}

// The partner's first Pokemon has party index 0 too, so the player controller used to play the
// level-up animation on it and refresh its healthbox with the player's Pokemon.
AI_TWO_VS_ONE_BATTLE_TEST("Exp award: The level-up animation plays on the player's Pokemon, not the partner's")
{
    GIVEN {
        PLAYER(SPECIES_CATERPIE) { Level(5); Moves(MOVE_TACKLE); }
        PARTNER(SPECIES_WOBBUFFET) { Level(50); Moves(MOVE_CELEBRATE); }
        OPPONENT(SPECIES_TREECKO) { Level(20); HP(1); Moves(MOVE_CELEBRATE); }
        OPPONENT(SPECIES_TREECKO) { Level(20); Moves(MOVE_CELEBRATE); }
    } WHEN {
        TURN { MOVE(playerLeft, MOVE_TACKLE, target: opponentLeft); }
    } SCENE {
        MESSAGE("The opposing Treecko fainted!");
        ANIMATION(ANIM_TYPE_SPECIAL, B_ANIM_LVL_UP, playerLeft);
    } THEN {
        EXPECT_EQ(gBattlerPartyIndexes[GetBattlerAtPosition(B_POSITION_PLAYER_RIGHT)], 0);
        EXPECT_GT(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_LEVEL), 5);
    }
}

WILD_BATTLE_TEST("Exp formula: steep scaling gives less from lower-level foes, more from higher-level ones, the same at equal levels (#154)", s32 exp)
{
    u32 level = 0, steep = FALSE;

    PARAMETRIZE { level = 10; steep = FALSE; }
    PARAMETRIZE { level = 10; steep = TRUE; }
    PARAMETRIZE { level = 30; steep = FALSE; }
    PARAMETRIZE { level = 30; steep = TRUE; }
    PARAMETRIZE { level = 5;  steep = FALSE; }
    PARAMETRIZE { level = 5;  steep = TRUE; }

    GIVEN {
        WITH_CONFIG(B_SCALED_EXP, GEN_LATEST);
        WITH_CONFIG(B_SCALED_EXP_STEEP, steep);
        WITH_CONFIG(B_EXP_OVERLEVEL_PENALTY, FALSE);
        PLAYER(SPECIES_WOBBUFFET) { Level(level); }
        OPPONENT(SPECIES_CATERPIE) { Level(10); HP(1); }
    } WHEN {
        TURN { MOVE(player, MOVE_SCRATCH); }
    } SCENE {
        MESSAGE("Wobbuffet used Scratch!");
        MESSAGE("The wild Caterpie fainted!");
        EXPERIENCE_BAR(player, captureGainedExp: &results[i].exp);
    } FINALLY {
        EXPECT_EQ(results[1].exp, results[0].exp);
        EXPECT_LT(results[3].exp, results[2].exp);
        EXPECT_GT(results[5].exp, results[4].exp);
    }
}

TEST("Exp formula: the over-level penalty follows a logistic curve down to its floor (#189)")
{
    // The same cases as tools/rebalance's test_overlevel, at the configs' 30 / 8 / 40% (#350).
    // Retuning the configs fails here: update these cases and the model's with them.
    EXPECT_EQ(B_EXP_OVERLEVEL_CUTOFF, 30);
    EXPECT_EQ(B_EXP_OVERLEVEL_WIDTH, 8);
    EXPECT_EQ(B_EXP_OVERLEVEL_FLOOR, 40);
    EXPECT_EQ(B_EXP_OVERLEVEL_MIN_LEVEL, 7);
    EXPECT_EQ(ApplyOverlevelPenalty(1000, 30, 30), 1000); // full exp at the foe's level
    EXPECT_EQ(ApplyOverlevelPenalty(1000, 30, 25), 1000); // and below it
    EXPECT_EQ(ApplyOverlevelPenalty(1000, 30, 31), 992);  // slowly at first
    EXPECT_EQ(ApplyOverlevelPenalty(1000, 30, 33), 967);
    EXPECT_EQ(ApplyOverlevelPenalty(1000, 30, 36), 877);
    EXPECT_EQ(ApplyOverlevelPenalty(1000, 30, 39), 707);  // fastest around the cutoff
    EXPECT_EQ(ApplyOverlevelPenalty(1000, 30, 42), 536);
    EXPECT_EQ(ApplyOverlevelPenalty(1000, 30, 50), 406);
    EXPECT_EQ(ApplyOverlevelPenalty(1000, 20, 26), 707);  // the cutoff, in percent of the foe's level
    EXPECT_EQ(ApplyOverlevelPenalty(1000, 40, 52), 707);
    EXPECT_EQ(ApplyOverlevelPenalty(1000, 20, 60), 400);  // the floor
    EXPECT_EQ(ApplyOverlevelPenalty(5, 20, 60), 2);       // 40% of 5
    EXPECT_EQ(ApplyOverlevelPenalty(0, 20, 60), 0);       // no exp stays no exp
    EXPECT_EQ(ApplyOverlevelPenalty(1000, 3, 4), 938);    // below the minimum level, the foe counts as level 7:
    EXPECT_EQ(ApplyOverlevelPenalty(1000, 3, 5), 733);    // the cutoff is 2.1 levels, not 0.9
    EXPECT_EQ(ApplyOverlevelPenalty(1000, 3, 6), 502);
    EXPECT_EQ(ApplyOverlevelPenalty(1000, 3, 7), 420);
    EXPECT_EQ(ApplyOverlevelPenalty(1000, 3, 10), 400);
    EXPECT_EQ(ApplyOverlevelPenalty(1000, 7, 9), 733);    // at the minimum level, the same as 2 over a level-3 foe
}

WILD_BATTLE_TEST("Exp formula: the over-level penalty applies its configs in battle (#189)", s32 exp)
{
    u32 foe = 0, getter = 0, penalty = FALSE, width = 4, floorPercent = 10, minLevel = 17;

    PARAMETRIZE { foe = 30; getter = 30; penalty = FALSE; }
    PARAMETRIZE { foe = 30; getter = 30; penalty = TRUE; }
    PARAMETRIZE { foe = 30; getter = 31; penalty = FALSE; }
    PARAMETRIZE { foe = 30; getter = 31; penalty = TRUE; }
    PARAMETRIZE { foe = 20; getter = 23; penalty = FALSE; }
    PARAMETRIZE { foe = 20; getter = 23; penalty = TRUE; }
    PARAMETRIZE { foe = 20; getter = 60; penalty = FALSE; }
    PARAMETRIZE { foe = 20; getter = 60; penalty = TRUE; }
    PARAMETRIZE { foe = 20; getter = 23; penalty = TRUE; width = 0; }
    PARAMETRIZE { foe = 20; getter = 24; penalty = FALSE; }
    PARAMETRIZE { foe = 20; getter = 24; penalty = TRUE; width = 0; }
    PARAMETRIZE { foe = 20; getter = 60; penalty = TRUE; floorPercent = 0; }
    PARAMETRIZE { foe = 3; getter = 5; penalty = FALSE; }
    PARAMETRIZE { foe = 3; getter = 5; penalty = TRUE; }
    PARAMETRIZE { foe = 3; getter = 5; penalty = TRUE; minLevel = 0; }

    GIVEN {
        WITH_CONFIG(B_EXP_OVERLEVEL_PENALTY, penalty);
        WITH_CONFIG(B_EXP_OVERLEVEL_CUTOFF, 15);
        WITH_CONFIG(B_EXP_OVERLEVEL_WIDTH, width);
        WITH_CONFIG(B_EXP_OVERLEVEL_FLOOR, floorPercent);
        WITH_CONFIG(B_EXP_OVERLEVEL_MIN_LEVEL, minLevel);
        PLAYER(SPECIES_WOBBUFFET) { Level(getter); }
        OPPONENT(SPECIES_BLISSEY) { Level(foe); HP(1); }
    } WHEN {
        TURN { MOVE(player, MOVE_SCRATCH); }
    } SCENE {
        MESSAGE("Wobbuffet used Scratch!");
        MESSAGE("The wild Blissey fainted!");
        EXPERIENCE_BAR(player, captureGainedExp: &results[i].exp);
    } FINALLY {
        EXPECT_EQ(results[1].exp, results[0].exp);                  // full exp at the foe's level
        EXPECT_LT(results[3].exp, results[2].exp);                  // 3% over: a little less
        EXPECT_GE(results[3].exp * 100, results[2].exp * 96);
        EXPECT_GE(results[5].exp * 100, results[4].exp * 50);       // the cutoff: about half
        EXPECT_LE(results[5].exp * 100, results[4].exp * 60);
        EXPECT_EQ(results[7].exp, results[6].exp / 10);             // 200% over: the floor
        EXPECT_EQ(results[8].exp, results[4].exp);                  // width 0: full exp up to the cutoff,
        EXPECT_EQ(results[10].exp, results[9].exp / 10);            // the floor past it
        EXPECT_EQ(results[11].exp, 1);                              // floor 0: at least 1
        EXPECT_GE(results[13].exp * 1000, results[12].exp * 730);  // 2 over a level-3 foe: 73.7% with the
        EXPECT_LE(results[13].exp * 1000, results[12].exp * 740);  // minimum level (FINALLY runs with the last configs),
        EXPECT_LE(results[14].exp * 100, results[12].exp * 11);    // the floor without it
    }
}

WILD_BATTLE_TEST("Exp formula: the over-level penalty also applies to the Gen 6 Exp. Share bench (#154)", s32 benchExp)
{
    u32 penalty = FALSE;

    PARAMETRIZE { penalty = FALSE; }
    PARAMETRIZE { penalty = TRUE; }

    GIVEN {
        ASSUME(I_EXP_SHARE_FLAG > TEMP_FLAGS_END);
        ASSUME(B_SPLIT_EXP >= GEN_6);
        WITH_CONFIG(B_SPLIT_EXP, GEN_6);
        WITH_CONFIG(B_EXP_OVERLEVEL_PENALTY, penalty);
        FLAG_SET(I_EXP_SHARE_FLAG);
        PLAYER(SPECIES_WOBBUFFET) { Level(20); }
        PLAYER(SPECIES_WYNAUT) { Level(23); }
        OPPONENT(SPECIES_CATERPIE) { Level(20); HP(1); }
    } WHEN {
        TURN { MOVE(player, MOVE_SCRATCH); }
    } SCENE {
        MESSAGE("The wild Caterpie fainted!");
    } THEN {
        results[i].benchExp = GetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_EXP) - EXP_AT_LEVEL(SPECIES_WYNAUT, 23);
    } FINALLY {
        EXPECT_GT(results[0].benchExp, 1);
        EXPECT_LT(results[1].benchExp, results[0].benchExp);
        EXPECT_EQ(results[1].benchExp, ApplyOverlevelPenalty(results[0].benchExp, 20, 23)); // the bench Wynaut is 15% over
    }
}
