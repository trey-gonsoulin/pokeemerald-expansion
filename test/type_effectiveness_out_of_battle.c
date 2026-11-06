#include "global.h"
#include "battle.h"
#include "battle_dome.h"
#include "battle_frontier.h"
#include "battle_util.h"
#include "event_data.h"
#include "frontier_util.h"
#include "malloc.h"
#include "test/test.h"
#include "constants/battle_frontier.h"
#include "constants/battle_frontier_mons.h"
#include "constants/trainers.h"

// The Battle Dome's tourney tree (GetWinningMove) and the overworld (GetOverworldTypeEffectiveness)
// score moves after a battle, when gBattleMons[0] is the player's last battler and gFieldStatuses
// may be left over: only the species' types and the given ability count.
static void SetStaleBattleState(enum Type type, u32 fieldStatuses)
{
    memset(&gBattleMons[B_BATTLER_0], 0, sizeof(gBattleMons[B_BATTLER_0]));
    gBattleMons[B_BATTLER_0].types[0] = type;
    gBattleMons[B_BATTLER_0].types[1] = type;
    gBattleMons[B_BATTLER_0].types[2] = TYPE_MYSTERY;
    gFieldStatuses = fieldStatuses;
}

static void ClearStaleBattleState(void)
{
    memset(&gBattleMons[B_BATTLER_0], 0, sizeof(gBattleMons[B_BATTLER_0]));
    gFieldStatuses = 0;
}

TEST("Out-of-battle type effectiveness: a Ground move doesn't affect a Flying type whatever the last battler was")
{
    SetStaleBattleState(TYPE_NORMAL, 0);
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_EARTHQUAKE, ABILITY_NONE, SPECIES_PIDGEY, ABILITY_KEEN_EYE), UQ_4_12(0.0));
    gBattleMons[B_BATTLER_0].volatiles.smackDown = TRUE;
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_EARTHQUAKE, ABILITY_NONE, SPECIES_PIDGEY, ABILITY_KEEN_EYE), UQ_4_12(0.0));
    ClearStaleBattleState();
}

TEST("Out-of-battle type effectiveness: leftover Gravity grounds neither a Flying type nor Levitate")
{
    SetStaleBattleState(TYPE_FLYING, STATUS_FIELD_GRAVITY);
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_EARTHQUAKE, ABILITY_NONE, SPECIES_PIDGEY, ABILITY_KEEN_EYE), UQ_4_12(0.0));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_EARTHQUAKE, ABILITY_NONE, SPECIES_GASTLY, ABILITY_LEVITATE), UQ_4_12(0.0));
    ClearStaleBattleState();
}

TEST("Out-of-battle type effectiveness: the last battler's Foresight doesn't let a Normal move hit a Ghost type")
{
    SetStaleBattleState(TYPE_NORMAL, 0);
    gBattleMons[B_BATTLER_0].volatiles.foresight = TRUE;
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_TACKLE, ABILITY_NONE, SPECIES_GASTLY, ABILITY_LEVITATE), UQ_4_12(0.0));
    ClearStaleBattleState();
}

TEST("Out-of-battle type effectiveness: the type chart and Freeze-Dry still apply")
{
    SetStaleBattleState(TYPE_NORMAL, 0);
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_EARTHQUAKE, ABILITY_NONE, SPECIES_SQUIRTLE, ABILITY_TORRENT), UQ_4_12(1.0));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_ICE_BEAM, ABILITY_NONE, SPECIES_SQUIRTLE, ABILITY_TORRENT), UQ_4_12(0.5));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_FREEZE_DRY, ABILITY_NONE, SPECIES_SQUIRTLE, ABILITY_TORRENT), UQ_4_12(2.0));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_ICE_BEAM, ABILITY_NONE, SPECIES_PIDGEY, ABILITY_KEEN_EYE), UQ_4_12(2.0));
    ClearStaleBattleState();
}

TEST("Out-of-battle type effectiveness: the Dome's absorbing abilities take the move")
{
    SetStaleBattleState(TYPE_NORMAL, 0);
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_THUNDERBOLT, ABILITY_NONE, SPECIES_JOLTEON, ABILITY_VOLT_ABSORB), UQ_4_12(0.0));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_THUNDER_WAVE, ABILITY_NONE, SPECIES_JOLTEON, ABILITY_VOLT_ABSORB), UQ_4_12(0.0));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_EARTHQUAKE, ABILITY_NONE, SPECIES_JOLTEON, ABILITY_VOLT_ABSORB), UQ_4_12(2.0));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_FLAMETHROWER, ABILITY_NONE, SPECIES_VULPIX, ABILITY_FLASH_FIRE), UQ_4_12(0.0));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_SURF, ABILITY_NONE, SPECIES_VULPIX, ABILITY_FLASH_FIRE), UQ_4_12(2.0));
    ClearStaleBattleState();
}

TEST("Out-of-battle type effectiveness: the Dome's Lightning Rod takes Electric moves from Gen 5")
{
    ASSUME(GetConfig(B_REDIRECT_ABILITY_IMMUNITY) >= GEN_5);
    SetStaleBattleState(TYPE_NORMAL, 0);
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_THUNDERBOLT, ABILITY_NONE, SPECIES_PIKACHU, ABILITY_LIGHTNING_ROD), UQ_4_12(0.0));
    ClearStaleBattleState();
}

TEST("Out-of-battle type effectiveness: the Dome's absorbing abilities don't take a move on the user or the field")
{
    ASSUME(GetMoveTarget(MOVE_CHARGE) == TARGET_USER);
    ASSUME(GetMoveTarget(MOVE_SUNNY_DAY) == TARGET_FIELD);
    SetStaleBattleState(TYPE_NORMAL, 0);
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_CHARGE, ABILITY_NONE, SPECIES_JOLTEON, ABILITY_VOLT_ABSORB), UQ_4_12(0.5));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_SUNNY_DAY, ABILITY_NONE, SPECIES_VULPIX, ABILITY_FLASH_FIRE), UQ_4_12(0.5));
    ClearStaleBattleState();
}

TEST("Out-of-battle type effectiveness: the Dome's other abilities leave the type chart alone")
{
    SetStaleBattleState(TYPE_NORMAL, 0);
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_THUNDERBOLT, ABILITY_NONE, SPECIES_JOLTEON, ABILITY_QUICK_FEET), UQ_4_12(0.5));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_FLAMETHROWER, ABILITY_NONE, SPECIES_VULPIX, ABILITY_DROUGHT), UQ_4_12(0.5));
    ClearStaleBattleState();
}

TEST("Out-of-battle type effectiveness: the overworld's Ground check doesn't read the last battler")
{
    struct Pokemon *mon = &gParties[B_TRAINER_PLAYER][0];

    CreateMon(mon, SPECIES_PIDGEY, 10, 0, OTID_STRUCT_PRESET(0));
    SetStaleBattleState(TYPE_NORMAL, 0);
    EXPECT_EQ(GetOverworldTypeEffectiveness(mon, TYPE_GROUND), UQ_4_12(0.0));
    ClearStaleBattleState();
    ZeroMonData(mon);
}

static void CreateMonWithFirstAbility(struct Pokemon *mon, enum Species species)
{
    u32 abilityNum = 0;

    CreateMon(mon, species, 10, 0, OTID_STRUCT_PRESET(0));
    SetMonData(mon, MON_DATA_ABILITY_NUM, &abilityNum);
}

TEST("Out-of-battle type effectiveness: the overworld's absorbing abilities don't touch battle state")
{
    struct Pokemon *mon = &gParties[B_TRAINER_PLAYER][0];
    struct BattleStruct *savedBattleStruct = gBattleStruct;
    u8 savedChooser = gBattleCommunication[MULTISTRING_CHOOSER];
    enum Ability voltAbsorb, flashFire;
    uq4_12_t electric, ground, fire, water;
    s32 heal;
    u8 chooser;
    bool32 flashFireBoosted;

    // A hurt last battler would make Volt Absorb heal it through gBattleStruct (NULL outside a
    // battle), and Flash Fire sets the battle message chooser. Everything is read and restored
    // before the first EXPECT, which ends the test when it fails.
    gBattleStruct = AllocZeroed(sizeof(*gBattleStruct));
    SetStaleBattleState(TYPE_NORMAL, 0);
    gBattleMons[B_BATTLER_0].hp = 1;
    gBattleMons[B_BATTLER_0].maxHP = 100;
    gBattleCommunication[MULTISTRING_CHOOSER] = 0xFF;

    CreateMonWithFirstAbility(mon, SPECIES_JOLTEON);
    voltAbsorb = GetMonAbility(mon);
    electric = GetOverworldTypeEffectiveness(mon, TYPE_ELECTRIC);
    ground = GetOverworldTypeEffectiveness(mon, TYPE_GROUND);
    CreateMonWithFirstAbility(mon, SPECIES_VULPIX);
    flashFire = GetMonAbility(mon);
    fire = GetOverworldTypeEffectiveness(mon, TYPE_FIRE);
    water = GetOverworldTypeEffectiveness(mon, TYPE_WATER);

    heal = gBattleStruct->passiveHpUpdate[B_BATTLER_0];
    chooser = gBattleCommunication[MULTISTRING_CHOOSER];
    flashFireBoosted = gBattleMons[B_BATTLER_0].volatiles.flashFireBoosted;

    gBattleCommunication[MULTISTRING_CHOOSER] = savedChooser;
    Free(gBattleStruct);
    gBattleStruct = savedBattleStruct;
    ClearStaleBattleState();
    ZeroMonData(mon);

    EXPECT_EQ(voltAbsorb, ABILITY_VOLT_ABSORB);
    EXPECT_EQ(electric, UQ_4_12(0.0));
    EXPECT_EQ(ground, UQ_4_12(2.0));
    EXPECT_EQ(flashFire, ABILITY_FLASH_FIRE);
    EXPECT_EQ(fire, UQ_4_12(0.0));
    EXPECT_EQ(water, UQ_4_12(2.0));
    EXPECT_EQ(heal, 0);
    EXPECT_EQ(chooser, 0xFF);
    EXPECT(!flashFireBoosted);
}

TEST("Out-of-battle type effectiveness: the overworld's Ground check counts Levitate")
{
    struct Pokemon *mon = &gParties[B_TRAINER_PLAYER][0];

    CreateMonWithFirstAbility(mon, SPECIES_GASTLY);
    EXPECT_EQ(GetMonAbility(mon), ABILITY_LEVITATE);
    EXPECT_EQ(GetOverworldTypeEffectiveness(mon, TYPE_GROUND), UQ_4_12(0.0));
    EXPECT_EQ(GetOverworldTypeEffectiveness(mon, TYPE_PSYCHIC), UQ_4_12(2.0));
    ZeroMonData(mon);
}

TEST("Out-of-battle type effectiveness: the Dome's Soundproof, Bulletproof and Wind Rider block their moves")
{
    ASSUME(IsSoundMove(MOVE_HYPER_VOICE));
    ASSUME(IsBallisticMove(MOVE_SLUDGE_BOMB));
    ASSUME(IsWindMove(MOVE_HURRICANE));
    SetStaleBattleState(TYPE_NORMAL, 0);
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_HYPER_VOICE, ABILITY_NONE, SPECIES_VOLTORB, ABILITY_SOUNDPROOF), UQ_4_12(0.0));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_TACKLE, ABILITY_NONE, SPECIES_VOLTORB, ABILITY_SOUNDPROOF), UQ_4_12(1.0));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_SLUDGE_BOMB, ABILITY_NONE, SPECIES_CHESPIN, ABILITY_BULLETPROOF), UQ_4_12(0.0));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_SLUDGE_BOMB, ABILITY_NONE, SPECIES_CHESPIN, ABILITY_OVERGROW), UQ_4_12(2.0));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_HURRICANE, ABILITY_NONE, SPECIES_BRAMBLEGHAST, ABILITY_WIND_RIDER), UQ_4_12(0.0));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_AIR_SLASH, ABILITY_NONE, SPECIES_BRAMBLEGHAST, ABILITY_WIND_RIDER), UQ_4_12(2.0));
    ClearStaleBattleState();
}

TEST("Out-of-battle type effectiveness: the Dome's Good as Gold blocks status moves aimed at it")
{
    ASSUME(GetMoveCategory(MOVE_THUNDER_WAVE) == DAMAGE_CATEGORY_STATUS);
    ASSUME(GetMoveTarget(MOVE_CHARGE) == TARGET_USER);
    SetStaleBattleState(TYPE_NORMAL, 0);
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_THUNDER_WAVE, ABILITY_NONE, SPECIES_GHOLDENGO, ABILITY_GOOD_AS_GOLD), UQ_4_12(0.0));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_THUNDERBOLT, ABILITY_NONE, SPECIES_GHOLDENGO, ABILITY_GOOD_AS_GOLD), UQ_4_12(1.0));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_CHARGE, ABILITY_NONE, SPECIES_GHOLDENGO, ABILITY_GOOD_AS_GOLD), UQ_4_12(1.0));
    ClearStaleBattleState();
}

TEST("Out-of-battle type effectiveness: the Dome's Mold Breaker, Teravolt and Turboblaze get past the target's ability")
{
    SetStaleBattleState(TYPE_NORMAL, 0);
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_EARTHQUAKE, ABILITY_MOLD_BREAKER, SPECIES_GASTLY, ABILITY_LEVITATE), UQ_4_12(2.0));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_THUNDERBOLT, ABILITY_TERAVOLT, SPECIES_JOLTEON, ABILITY_VOLT_ABSORB), UQ_4_12(0.5));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_HYPER_VOICE, ABILITY_TURBOBLAZE, SPECIES_VOLTORB, ABILITY_SOUNDPROOF), UQ_4_12(1.0));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_X_SCISSOR, ABILITY_MOLD_BREAKER, SPECIES_SHEDINJA, ABILITY_WONDER_GUARD), UQ_4_12(0.5));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_X_SCISSOR, ABILITY_NONE, SPECIES_SHEDINJA, ABILITY_WONDER_GUARD), UQ_4_12(0.0));
    ClearStaleBattleState();
}

TEST("Out-of-battle type effectiveness: the Dome's Mycelium Might gets past the target's ability on status moves only")
{
    ASSUME(GetMoveCategory(MOVE_THUNDER_WAVE) == DAMAGE_CATEGORY_STATUS);
    SetStaleBattleState(TYPE_NORMAL, 0);
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_THUNDER_WAVE, ABILITY_MYCELIUM_MIGHT, SPECIES_GHOLDENGO, ABILITY_GOOD_AS_GOLD), UQ_4_12(1.0));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_HYPER_VOICE, ABILITY_MYCELIUM_MIGHT, SPECIES_VOLTORB, ABILITY_SOUNDPROOF), UQ_4_12(0.0));
    ClearStaleBattleState();
}

TEST("Out-of-battle type effectiveness: the Dome's moves that ignore abilities get past the target's ability")
{
    ASSUME(MoveIgnoresTargetAbility(MOVE_SUNSTEEL_STRIKE));
    SetStaleBattleState(TYPE_NORMAL, 0);
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_SUNSTEEL_STRIKE, ABILITY_NONE, SPECIES_SHEDINJA, ABILITY_WONDER_GUARD), UQ_4_12(1.0));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_IRON_HEAD, ABILITY_NONE, SPECIES_SHEDINJA, ABILITY_WONDER_GUARD), UQ_4_12(0.0));
    ClearStaleBattleState();
}

TEST("Out-of-battle type effectiveness: the Dome's move on every battler reaches the target's ability, except Good as Gold")
{
    ASSUME(GetMoveTarget(MOVE_PERISH_SONG) == TARGET_ALL_BATTLERS);
    ASSUME(IsSoundMove(MOVE_PERISH_SONG));
    ASSUME(GetMoveTarget(MOVE_FLOWER_SHIELD) == TARGET_ALL_BATTLERS);
    ASSUME(GetMoveCategory(MOVE_FLOWER_SHIELD) == DAMAGE_CATEGORY_STATUS);
    SetStaleBattleState(TYPE_NORMAL, 0);
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_PERISH_SONG, ABILITY_NONE, SPECIES_VOLTORB, ABILITY_SOUNDPROOF), UQ_4_12(0.0));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_PERISH_SONG, ABILITY_NONE, SPECIES_VOLTORB, ABILITY_STATIC), UQ_4_12(1.0));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_FLOWER_SHIELD, ABILITY_NONE, SPECIES_GHOLDENGO, ABILITY_GOOD_AS_GOLD), UQ_4_12(0.5));
    ClearStaleBattleState();
}

// Tournament ID 0 is a facility trainer with three Porygon2 (Psychic, Thunderbolt, Ice Beam,
// Recover) and ID 1 the loser. A Frontier Brain's DOME_MONS hold its species IDs.
static u16 GetDomeWinningMoveAgainst(u16 loserTrainerId, const u16 *loserMons)
{
    u32 i;

    gSaveBlock2Ptr->frontier.domeTrainers[0].trainerId = 0;
    gSaveBlock2Ptr->frontier.domeTrainers[1].trainerId = loserTrainerId;
    for (i = 0; i < FRONTIER_PARTY_SIZE; i++)
    {
        gSaveBlock2Ptr->frontier.domeMonIds[0][i] = FRONTIER_MON_PORYGON2_4;
        gSaveBlock2Ptr->frontier.domeMonIds[1][i] = loserMons[i];
    }
    // Round 1, so no earlier round's winning move is skipped.
    return Test_GetWinningMove(0, 1, 1);
}

TEST("Out-of-battle type effectiveness: the Dome's winning move against a losing Frontier Brain reads its Pokemon by species")
{
    u16 savedFacility = VarGet(VAR_FRONTIER_FACILITY);
    u8 savedLvlMode = gSaveBlock2Ptr->frontier.lvlMode;
    u16 brainSpecies[FRONTIER_PARTY_SIZE];
    const u16 sameSpeciesMons[FRONTIER_PARTY_SIZE] = {FRONTIER_MON_SWAMPERT_1, FRONTIER_MON_SALAMENCE_1, FRONTIER_MON_CHARIZARD_1};
    u32 i;

    VarSet(VAR_FRONTIER_FACILITY, FRONTIER_FACILITY_DOME);
    gSaveBlock2Ptr->frontier.lvlMode = FRONTIER_LVL_50;
    SetFacilityPtrsGetLevel();
    for (i = 0; i < FRONTIER_PARTY_SIZE; i++)
        brainSpecies[i] = GetFrontierBrainMonSpecies(i);
    ASSUME(brainSpecies[0] == SPECIES_SWAMPERT);
    ASSUME(brainSpecies[1] == SPECIES_SALAMENCE);
    ASSUME(brainSpecies[2] == SPECIES_CHARIZARD);
    for (i = 0; i < FRONTIER_PARTY_SIZE; i++)
        ASSUME(gFacilityTrainerMons[sameSpeciesMons[i]].species == brainSpecies[i]);
    // The facility mons at the Brain's species IDs: Omastar, Medicham and Magikarp.
    ASSUME(gFacilityTrainerMons[SPECIES_SWAMPERT].species == SPECIES_OMASTAR);
    ASSUME(gFacilityTrainerMons[SPECIES_SALAMENCE].species == SPECIES_MEDICHAM);
    ASSUME(gFacilityTrainerMons[SPECIES_CHARIZARD].species == SPECIES_MAGIKARP);

    // Ice Beam: 1x on Swampert and Charizard, 4x on Salamence. Thunderbolt wins on the
    // facility mons at those indexes (2x on Omastar and Magikarp).
    EXPECT_EQ(GetDomeWinningMoveAgainst(TRAINER_FRONTIER_BRAIN, brainSpecies), MOVE_ICE_BEAM);
    EXPECT_EQ(GetDomeWinningMoveAgainst(1, sameSpeciesMons), MOVE_ICE_BEAM);
    EXPECT_EQ(GetDomeWinningMoveAgainst(1, brainSpecies), MOVE_THUNDERBOLT);

    VarSet(VAR_FRONTIER_FACILITY, savedFacility);
    gSaveBlock2Ptr->frontier.lvlMode = savedLvlMode;
}
