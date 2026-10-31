#include "global.h"
#include "test/battle.h"
#include "constants/characters.h"

// The AI uses Dynamax or Tera unless the mon's Dynamax level is BLOCK_AI_DYNAMAX or its Tera Type
// is TYPE_MYSTERY (ShouldTrainerBattlerUseGimmick). Mons made from data with no gimmick settings
// have to say so, or they get CreateMon's defaults: Dynamax level 0 and one of the species' types.

static void ExpectGimmicksBlocked(struct Pokemon *mon)
{
    EXPECT_EQ(GetMonData(mon, MON_DATA_DYNAMAX_LEVEL), BLOCK_AI_DYNAMAX);
    EXPECT_EQ(GetMonData(mon, MON_DATA_TERA_TYPE), TYPE_MYSTERY);
}

TEST("Gimmick intent: Battle Tower record and Apprentice mons don't Dynamax or Terastallize")
{
    struct Pokemon mon;
    struct BattleTowerPokemon towerMon = {0};
    struct Apprentice apprentice = {0};

    towerMon.species = SPECIES_WOBBUFFET;
    towerMon.level = 50;
    towerMon.moves[0] = MOVE_CELEBRATE;
    towerMon.nickname[0] = EOS;

    CreateBattleTowerMon(&mon, &towerMon);
    ExpectGimmicksBlocked(&mon);

    CreateBattleTowerMon_HandleLevel(&mon, &towerMon, TRUE);
    ExpectGimmicksBlocked(&mon);

    apprentice.lvlMode = 1;
    apprentice.party[0].species = SPECIES_WOBBUFFET;
    apprentice.party[0].moves[0] = MOVE_CELEBRATE;
    apprentice.language = GAME_LANGUAGE;
    CreateApprenticeMon(&mon, &apprentice, 0);
    ExpectGimmicksBlocked(&mon);
}

// A wild Pokémon picks a gimmick only through the AI (a roamer that can't flee, or WE_SMART_WILD_AI_FLAG),
// which tests don't run, so this asks ShouldTrainerBattlerUseGimmick directly. The opponent's gimmick
// is recorded for the test runner, which answers for trainer battlers in tests.
WILD_BATTLE_TEST("Gimmick intent: a wild Pokémon doesn't Terastallize or Dynamax")
{
    enum Gimmick gimmick;
    PARAMETRIZE { gimmick = GIMMICK_TERA; }
    PARAMETRIZE { gimmick = GIMMICK_DYNAMAX; }
    GIVEN {
        PLAYER(SPECIES_WOBBUFFET);
        OPPONENT(SPECIES_WOBBUFFET);
    } WHEN {
        TURN { MOVE(opponent, MOVE_CELEBRATE, gimmick: gimmick); }
    } THEN {
        EXPECT(!(gBattleTypeFlags & BATTLE_TYPE_TRAINER));
        EXPECT(!ShouldTrainerBattlerUseGimmick(GetBattlerAtPosition(B_POSITION_OPPONENT_LEFT), gimmick));
    }
}
