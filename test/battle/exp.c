#include "global.h"
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

WILD_BATTLE_TEST("Exp formula: the over-level penalty halves the exp every B_EXP_OVERLEVEL_HALVING percent past the cutoff (#154)", s32 exp)
{
    u32 foe = 0, getter = 0, penalty = FALSE, halving = 5;

    PARAMETRIZE { foe = 20; getter = 22; penalty = FALSE; }
    PARAMETRIZE { foe = 20; getter = 22; penalty = TRUE; }
    PARAMETRIZE { foe = 20; getter = 23; penalty = FALSE; }
    PARAMETRIZE { foe = 20; getter = 23; penalty = TRUE; }
    PARAMETRIZE { foe = 20; getter = 24; penalty = FALSE; }
    PARAMETRIZE { foe = 20; getter = 24; penalty = TRUE; }
    PARAMETRIZE { foe = 40; getter = 45; penalty = FALSE; }
    PARAMETRIZE { foe = 40; getter = 45; penalty = TRUE; }
    PARAMETRIZE { foe = 20; getter = 23; penalty = TRUE; halving = 0; }

    GIVEN {
        WITH_CONFIG(B_EXP_OVERLEVEL_PENALTY, penalty);
        WITH_CONFIG(B_EXP_OVERLEVEL_CUTOFF, 10);
        WITH_CONFIG(B_EXP_OVERLEVEL_HALVING, halving);
        PLAYER(SPECIES_WOBBUFFET) { Level(getter); }
        OPPONENT(SPECIES_CATERPIE) { Level(foe); HP(1); }
    } WHEN {
        TURN { MOVE(player, MOVE_SCRATCH); }
    } SCENE {
        MESSAGE("Wobbuffet used Scratch!");
        MESSAGE("The wild Caterpie fainted!");
        EXPERIENCE_BAR(player, captureGainedExp: &results[i].exp);
    } FINALLY {
        EXPECT_EQ(results[1].exp, results[0].exp);               // at the cutoff, 10% above the foe
        EXPECT_EQ(results[3].exp, results[2].exp / 2);           // 5% past it: one halving
        EXPECT_EQ(results[5].exp, results[4].exp / 4);           // 10% past it: two
        EXPECT_EQ(results[7].exp, results[6].exp * 2896 / 4096); // 2.5% past it: 2^(-8/16)
        EXPECT_EQ(results[8].exp, 1);                            // halving 0: 1 exp past the cutoff
    }
}
