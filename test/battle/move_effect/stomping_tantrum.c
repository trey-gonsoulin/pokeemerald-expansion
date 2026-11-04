#include "global.h"
#include "test/battle.h"

ASSUMPTIONS
{
    ASSUME(GetMoveEffect(MOVE_STOMPING_TANTRUM) == EFFECT_STOMPING_TANTRUM);
}

SINGLE_BATTLE_TEST("Stomping Tantrum will deal double damage if user flinched on the previous turn")
{
    s16 damage[3];
    GIVEN {
        PLAYER(SPECIES_WOBBUFFET);
        OPPONENT(SPECIES_WYNAUT);
        OPPONENT(SPECIES_WOBBUFFET);
    } WHEN {
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); SWITCH(opponent, 1); }
        TURN { MOVE(opponent, MOVE_FAKE_OUT); MOVE(player, MOVE_CELEBRATE); }
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
    } SCENE {
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[0]);

        ANIMATION(ANIM_TYPE_MOVE, MOVE_FAKE_OUT, opponent);
        NOT ANIMATION(ANIM_TYPE_MOVE, MOVE_CELEBRATE, player);

        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[1]);

        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[2]);
    } THEN {
        EXPECT_MUL_EQ(damage[0], Q_4_12(2.0), damage[1]);
        EXPECT_EQ(damage[0], damage[2]);
    }
}

SINGLE_BATTLE_TEST("Stomping Tantrum will deal double damage if user failed to attack due to paralysis")
{
    s16 damage[3];
    GIVEN {
        PLAYER(SPECIES_WOBBUFFET) { Speed(100); Item(ITEM_POTION); }
        OPPONENT(SPECIES_WOBBUFFET) { Speed(10); Item(ITEM_LUM_BERRY); }
    } WHEN {
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); MOVE(opponent, MOVE_THUNDER_WAVE); }
        TURN { MOVE(player, MOVE_CELEBRATE, WITH_RNG(RNG_PARALYSIS, TRUE)); MOVE(opponent, MOVE_TRICK); }
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
    } SCENE {
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[0]);
        ANIMATION(ANIM_TYPE_MOVE, MOVE_THUNDER_WAVE, opponent);

        ANIMATION(ANIM_TYPE_MOVE, MOVE_TRICK, opponent);

        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[1]);

        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[2]);
    } THEN {
        EXPECT_MUL_EQ(damage[0], Q_4_12(2.0), damage[1]);
        EXPECT_EQ(damage[0], damage[2]);
    }
}

SINGLE_BATTLE_TEST("Stomping Tantrum will not deal double damage if target protects")
{
    s16 damage[2];
    GIVEN {
        PLAYER(SPECIES_WOBBUFFET);
        OPPONENT(SPECIES_WOBBUFFET);
    } WHEN {
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
        TURN { MOVE(opponent, MOVE_PROTECT); MOVE(player, MOVE_STOMPING_TANTRUM); }
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
    } SCENE {
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[0]);

        ANIMATION(ANIM_TYPE_MOVE, MOVE_PROTECT, opponent);
        MESSAGE("The opposing Wobbuffet protected itself!");

        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[1]);
    } THEN {
        EXPECT_EQ(damage[0], damage[1]);
    }
}

SINGLE_BATTLE_TEST("Stomping Tantrum will deal double damage if user failed a Protect")
{
    s16 damage[2];
    GIVEN {
        PLAYER(SPECIES_WOBBUFFET);
        OPPONENT(SPECIES_WOBBUFFET);
    } WHEN {
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
        TURN { MOVE(player, MOVE_PROTECT); }
        TURN { MOVE(player, MOVE_PROTECT, WITH_RNG(RNG_PROTECT_FAIL, USHRT_MAX)); }
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
    } SCENE {
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[0]);

        ANIMATION(ANIM_TYPE_MOVE, MOVE_PROTECT, player);
        NOT ANIMATION(ANIM_TYPE_MOVE, MOVE_PROTECT, player);

        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[1]);
    } THEN {
        EXPECT_MUL_EQ(damage[0], Q_4_12(2.0), damage[1]);
    }
}

SINGLE_BATTLE_TEST("Stomping Tantrum will not deal double if it missed")
{
    s16 damage[2];
    GIVEN {
        PLAYER(SPECIES_WOBBUFFET);
        OPPONENT(SPECIES_WOBBUFFET) { Item(ITEM_BRIGHTPOWDER); }
    } WHEN {
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM, hit: FALSE); }
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
    } SCENE {
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[0]);
        MESSAGE("The opposing Wobbuffet avoided the attack!");
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[1]);
    } THEN {
        EXPECT_MUL_EQ(damage[0], Q_4_12(2.0), damage[1]);
    }
}

SINGLE_BATTLE_TEST("Stomping Tantrum will deal double damage if user was immune to previous move")
{
    s16 damage[2];
    GIVEN {
        PLAYER(SPECIES_WOBBUFFET);
        OPPONENT(SPECIES_PIDGEY);
        OPPONENT(SPECIES_WOBBUFFET);
    } WHEN {
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); SWITCH(opponent, 1); }
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); SWITCH(opponent, 0); }
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); SWITCH(opponent, 1); }
    } SCENE {
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[0]);
        MESSAGE("It doesn't affect the opposing Pidgey…");
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[1]);
    } THEN {
        EXPECT_MUL_EQ(damage[0], Q_4_12(2.0), damage[1]);
    }
}

DOUBLE_BATTLE_TEST("Stomping Tantrum will not deal double damage if spread moved failed one target")
{
    s16 damage[2];
    GIVEN {
        ASSUME(GetMoveTarget(MOVE_EARTHQUAKE) == TARGET_FOES_AND_ALLY);
        PLAYER(SPECIES_WOBBUFFET);
        PLAYER(SPECIES_WOBBUFFET);
        OPPONENT(SPECIES_WOBBUFFET);
        OPPONENT(SPECIES_PIDGEY);
    } WHEN {
        TURN { MOVE(playerLeft, MOVE_STOMPING_TANTRUM, target: opponentLeft); }
        TURN { MOVE(playerLeft, MOVE_EARTHQUAKE); }
        TURN { MOVE(playerLeft, MOVE_STOMPING_TANTRUM, target: opponentLeft); }
    } SCENE {
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, playerLeft);
        HP_BAR(opponentLeft, captureDamage: &damage[0]);

        ANIMATION(ANIM_TYPE_MOVE, MOVE_EARTHQUAKE, playerLeft);

        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, playerLeft);
        HP_BAR(opponentLeft, captureDamage: &damage[1]);
    } THEN {
        EXPECT_EQ(damage[0], damage[1]);
    }
}

SINGLE_BATTLE_TEST("Stomping Tantrum will deal double damage if hit into an immunity ability")
{
    s16 damage[2];
    GIVEN {
        ASSUME(GetMoveEffect(MOVE_ELECTRIFY) == EFFECT_ELECTRIFY);
        PLAYER(SPECIES_WOBBUFFET);
        OPPONENT(SPECIES_ELECTIVIRE) { Ability(ABILITY_MOTOR_DRIVE); }
    } WHEN {
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
        TURN { MOVE(opponent, MOVE_ELECTRIFY); MOVE(player, MOVE_STOMPING_TANTRUM); }
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
    } SCENE {
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[0]);
        ANIMATION(ANIM_TYPE_MOVE, MOVE_ELECTRIFY, opponent);
        NOT ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        ABILITY_POPUP(opponent, ABILITY_MOTOR_DRIVE);
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[1]);
    } THEN {
        EXPECT_MUL_EQ(damage[0], Q_4_12(2.0), damage[1]);
    }
}

SINGLE_BATTLE_TEST("Stomping Tantrum will deal double damage if Belly Drum failed at half HP")
{
    s16 damage[2];
    GIVEN {
        ASSUME(GetMoveEffect(MOVE_BELLY_DRUM) == EFFECT_BELLY_DRUM);
        PLAYER(SPECIES_WOBBUFFET) { MaxHP(100); HP(50); }
        OPPONENT(SPECIES_WOBBUFFET);
    } WHEN {
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
        TURN { MOVE(player, MOVE_BELLY_DRUM); }
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
    } SCENE {
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[0]);
        MESSAGE("But it failed!");
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[1]);
    } THEN {
        EXPECT_MUL_EQ(damage[0], Q_4_12(2.0), damage[1]);
    }
}

SINGLE_BATTLE_TEST("Stomping Tantrum will deal double damage if Charge failed")
{
    s16 damage[2];
    GIVEN {
        ASSUME(GetMoveEffect(MOVE_CHARGE) == EFFECT_CHARGE);
        PLAYER(SPECIES_WOBBUFFET);
        OPPONENT(SPECIES_WOBBUFFET);
    } WHEN {
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
        // Charge fails only when it is already active and Sp. Def can't rise
        TURN { MOVE(player, MOVE_AMNESIA); }
        TURN { MOVE(player, MOVE_AMNESIA); }
        TURN { MOVE(player, MOVE_AMNESIA); }
        TURN { MOVE(player, MOVE_CHARGE); }
        TURN { MOVE(player, MOVE_CHARGE); }
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
    } SCENE {
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[0]);
        ANIMATION(ANIM_TYPE_MOVE, MOVE_CHARGE, player);
        MESSAGE("But it failed!");
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[1]);
    } THEN {
        EXPECT_MUL_EQ(damage[0], Q_4_12(2.0), damage[1]);
    }
}

SINGLE_BATTLE_TEST("Stomping Tantrum will not deal double damage if Perish Song only affected the user")
{
    s16 damage[2];
    GIVEN {
        ASSUME(GetMoveEffect(MOVE_PERISH_SONG) == EFFECT_PERISH_SONG);
        PLAYER(SPECIES_WOBBUFFET);
        OPPONENT(SPECIES_EXPLOUD) { Ability(ABILITY_SOUNDPROOF); }
    } WHEN {
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
        TURN { MOVE(player, MOVE_PERISH_SONG); }
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
    } SCENE {
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[0]);
        ANIMATION(ANIM_TYPE_MOVE, MOVE_PERISH_SONG, player);
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[1]);
    } THEN {
        EXPECT_EQ(damage[0], damage[1]);
    }
}

SINGLE_BATTLE_TEST("Stomping Tantrum will deal double damage if Perish Song failed")
{
    s16 damage[2];
    GIVEN {
        ASSUME(GetMoveEffect(MOVE_PERISH_SONG) == EFFECT_PERISH_SONG);
        PLAYER(SPECIES_WOBBUFFET);
        OPPONENT(SPECIES_EXPLOUD) { Ability(ABILITY_SOUNDPROOF); }
    } WHEN {
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
        TURN { MOVE(player, MOVE_PERISH_SONG); }
        TURN { MOVE(player, MOVE_PERISH_SONG); }
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
    } SCENE {
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[0]);
        ANIMATION(ANIM_TYPE_MOVE, MOVE_PERISH_SONG, player);
        MESSAGE("But it failed!");
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[1]);
    } THEN {
        EXPECT_MUL_EQ(damage[0], Q_4_12(2.0), damage[1]);
    }
}

SINGLE_BATTLE_TEST("Stomping Tantrum will not deal double damage if Flower Shield only raised the user's Defense")
{
    s16 damage[2];
    GIVEN {
        ASSUME(GetMoveEffect(MOVE_FLOWER_SHIELD) == EFFECT_FLOWER_SHIELD);
        ASSUME(GetMoveTarget(MOVE_FLOWER_SHIELD) == TARGET_ALL_BATTLERS);
        PLAYER(SPECIES_TANGELA);
        OPPONENT(SPECIES_WOBBUFFET);
    } WHEN {
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
        TURN { MOVE(player, MOVE_FLOWER_SHIELD); }
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
    } SCENE {
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[0]);
        ANIMATION(ANIM_TYPE_MOVE, MOVE_FLOWER_SHIELD, player);
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[1]);
    } THEN {
        EXPECT_EQ(damage[0], damage[1]);
    }
}

SINGLE_BATTLE_TEST("Stomping Tantrum will deal double damage if Teatime failed")
{
    s16 damage[2];
    GIVEN {
        ASSUME(GetMoveEffect(MOVE_TEATIME) == EFFECT_TEATIME);
        ASSUME(GetMoveTarget(MOVE_TEATIME) == TARGET_ALL_BATTLERS);
        PLAYER(SPECIES_WOBBUFFET);
        OPPONENT(SPECIES_WOBBUFFET);
    } WHEN {
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
        TURN { MOVE(player, MOVE_TEATIME); }
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
    } SCENE {
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[0]);
        MESSAGE("But it failed!");
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[1]);
    } THEN {
        EXPECT_MUL_EQ(damage[0], Q_4_12(2.0), damage[1]);
    }
}

SINGLE_BATTLE_TEST("Stomping Tantrum will not deal double damage if Attract worked but the foe's Destiny Knot failed")
{
    s16 damage[2];
    GIVEN {
        ASSUME(GetMoveEffect(MOVE_ATTRACT) == EFFECT_ATTRACT);
        PLAYER(SPECIES_WOBBUFFET) { Gender(MON_MALE); Speed(5); }
        OPPONENT(SPECIES_WOBBUFFET) { Gender(MON_FEMALE); Item(ITEM_DESTINY_KNOT); Speed(10); }
    } WHEN {
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
        TURN { MOVE(opponent, MOVE_ATTRACT); MOVE(player, MOVE_ATTRACT, WITH_RNG(RNG_INFATUATION, FALSE)); }
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM, WITH_RNG(RNG_INFATUATION, FALSE)); }
    } SCENE {
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[0]);
        ANIMATION(ANIM_TYPE_MOVE, MOVE_ATTRACT, player);
        ANIMATION(ANIM_TYPE_GENERAL, B_ANIM_HELD_ITEM_EFFECT, opponent);
        MESSAGE("But it failed!");
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[1]);
    } THEN {
        EXPECT_EQ(damage[0], damage[1]);
    }
}

SINGLE_BATTLE_TEST("Stomping Tantrum will not deal double damage if Attract worked but Oblivious stopped the foe's Destiny Knot")
{
    s16 damage[4];
    GIVEN {
        ASSUME(GetMoveEffect(MOVE_ATTRACT) == EFFECT_ATTRACT);
        PLAYER(SPECIES_SLOWPOKE) { Gender(MON_MALE); Ability(ABILITY_OBLIVIOUS); Speed(10); }
        OPPONENT(SPECIES_WOBBUFFET) { Gender(MON_FEMALE); Item(ITEM_DESTINY_KNOT); Speed(5); }
    } WHEN {
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); MOVE(opponent, MOVE_STOMPING_TANTRUM); }
        TURN { MOVE(player, MOVE_ATTRACT); MOVE(opponent, MOVE_CELEBRATE, WITH_RNG(RNG_INFATUATION, FALSE)); }
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); MOVE(opponent, MOVE_STOMPING_TANTRUM, WITH_RNG(RNG_INFATUATION, FALSE)); }
    } SCENE {
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[0]);
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, opponent);
        HP_BAR(player, captureDamage: &damage[2]);
        ANIMATION(ANIM_TYPE_MOVE, MOVE_ATTRACT, player);
        ABILITY_POPUP(player, ABILITY_OBLIVIOUS);
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[1]);
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, opponent);
        HP_BAR(player, captureDamage: &damage[3]);
    } THEN {
        EXPECT_EQ(damage[0], damage[1]);
        EXPECT_EQ(damage[2], damage[3]); // The foe's Destiny Knot left the battlers swapped through the move's end
    }
}

SINGLE_BATTLE_TEST("Stomping Tantrum will not deal double damage after Snatch stole a move")
{
    s16 damage[2];
    GIVEN {
        ASSUME(GetMoveEffect(MOVE_SNATCH) == EFFECT_SNATCH);
        PLAYER(SPECIES_WOBBUFFET);
        OPPONENT(SPECIES_WOBBUFFET);
    } WHEN {
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
        TURN { MOVE(player, MOVE_SNATCH); MOVE(opponent, MOVE_AMNESIA); }
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
    } SCENE {
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[0]);
        ANIMATION(ANIM_TYPE_MOVE, MOVE_SNATCH, player);
        ANIMATION(ANIM_TYPE_MOVE, MOVE_AMNESIA, player);
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[1]);
    } THEN {
        EXPECT_EQ(damage[0], damage[1]);
    }
}

SINGLE_BATTLE_TEST("Stomping Tantrum will not deal double damage after the user's move was snatched")
{
    s16 damage[2];
    GIVEN {
        ASSUME(GetMoveEffect(MOVE_SNATCH) == EFFECT_SNATCH);
        PLAYER(SPECIES_WOBBUFFET) { Speed(10); }
        OPPONENT(SPECIES_WOBBUFFET) { Speed(5); }
    } WHEN {
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); MOVE(opponent, MOVE_CELEBRATE); }
        TURN { MOVE(opponent, MOVE_SNATCH); MOVE(player, MOVE_AMNESIA); }
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); MOVE(opponent, MOVE_CELEBRATE); }
    } SCENE {
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[0]);
        ANIMATION(ANIM_TYPE_MOVE, MOVE_SNATCH, opponent);
        ANIMATION(ANIM_TYPE_MOVE, MOVE_AMNESIA, opponent);
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[1]);
    } THEN {
        EXPECT_EQ(damage[0], damage[1]);
    }
}

SINGLE_BATTLE_TEST("Stomping Tantrum will not deal double damage after Magic Coat bounced the user's move")
{
    s16 damage[2];
    GIVEN {
        ASSUME(GetMoveEffect(MOVE_MAGIC_COAT) == EFFECT_MAGIC_COAT);
        PLAYER(SPECIES_WOBBUFFET);
        OPPONENT(SPECIES_WOBBUFFET);
    } WHEN {
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
        TURN { MOVE(opponent, MOVE_MAGIC_COAT); MOVE(player, MOVE_SWEET_SCENT); }
        TURN { MOVE(player, MOVE_STOMPING_TANTRUM); }
    } SCENE {
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[0]);
        ANIMATION(ANIM_TYPE_MOVE, MOVE_MAGIC_COAT, opponent);
        ANIMATION(ANIM_TYPE_MOVE, MOVE_SWEET_SCENT, opponent);
        ANIMATION(ANIM_TYPE_MOVE, MOVE_STOMPING_TANTRUM, player);
        HP_BAR(opponent, captureDamage: &damage[1]);
    } THEN {
        EXPECT_EQ(damage[0], damage[1]);
    }
}
