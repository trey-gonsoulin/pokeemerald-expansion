#include "global.h"
#include "battle.h"
#include "battle_util.h"
#include "malloc.h"
#include "test/test.h"

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
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_EARTHQUAKE, SPECIES_PIDGEY, ABILITY_KEEN_EYE), UQ_4_12(0.0));
    gBattleMons[B_BATTLER_0].volatiles.smackDown = TRUE;
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_EARTHQUAKE, SPECIES_PIDGEY, ABILITY_KEEN_EYE), UQ_4_12(0.0));
    ClearStaleBattleState();
}

TEST("Out-of-battle type effectiveness: leftover Gravity grounds neither a Flying type nor Levitate")
{
    SetStaleBattleState(TYPE_FLYING, STATUS_FIELD_GRAVITY);
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_EARTHQUAKE, SPECIES_PIDGEY, ABILITY_KEEN_EYE), UQ_4_12(0.0));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_EARTHQUAKE, SPECIES_GASTLY, ABILITY_LEVITATE), UQ_4_12(0.0));
    ClearStaleBattleState();
}

TEST("Out-of-battle type effectiveness: the last battler's Foresight doesn't let a Normal move hit a Ghost type")
{
    SetStaleBattleState(TYPE_NORMAL, 0);
    gBattleMons[B_BATTLER_0].volatiles.foresight = TRUE;
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_TACKLE, SPECIES_GASTLY, ABILITY_LEVITATE), UQ_4_12(0.0));
    ClearStaleBattleState();
}

TEST("Out-of-battle type effectiveness: the type chart and Freeze-Dry still apply")
{
    SetStaleBattleState(TYPE_NORMAL, 0);
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_EARTHQUAKE, SPECIES_SQUIRTLE, ABILITY_TORRENT), UQ_4_12(1.0));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_ICE_BEAM, SPECIES_SQUIRTLE, ABILITY_TORRENT), UQ_4_12(0.5));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_FREEZE_DRY, SPECIES_SQUIRTLE, ABILITY_TORRENT), UQ_4_12(2.0));
    EXPECT_EQ(CalcPartyMonTypeEffectivenessMultiplier(MOVE_ICE_BEAM, SPECIES_PIDGEY, ABILITY_KEEN_EYE), UQ_4_12(2.0));
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

    // A hurt last battler would make Volt Absorb heal it through gBattleStruct (NULL outside a
    // battle), and Flash Fire sets the battle message chooser.
    gBattleStruct = AllocZeroed(sizeof(*gBattleStruct));
    SetStaleBattleState(TYPE_NORMAL, 0);
    gBattleMons[B_BATTLER_0].hp = 1;
    gBattleMons[B_BATTLER_0].maxHP = 100;
    gBattleCommunication[MULTISTRING_CHOOSER] = 0xFF;

    CreateMonWithFirstAbility(mon, SPECIES_JOLTEON);
    EXPECT_EQ(GetMonAbility(mon), ABILITY_VOLT_ABSORB);
    EXPECT_EQ(GetOverworldTypeEffectiveness(mon, TYPE_ELECTRIC), UQ_4_12(0.0));
    EXPECT_EQ(GetOverworldTypeEffectiveness(mon, TYPE_GROUND), UQ_4_12(2.0));
    CreateMonWithFirstAbility(mon, SPECIES_VULPIX);
    EXPECT_EQ(GetMonAbility(mon), ABILITY_FLASH_FIRE);
    EXPECT_EQ(GetOverworldTypeEffectiveness(mon, TYPE_FIRE), UQ_4_12(0.0));
    EXPECT_EQ(GetOverworldTypeEffectiveness(mon, TYPE_WATER), UQ_4_12(2.0));

    EXPECT_EQ(gBattleStruct->passiveHpUpdate[B_BATTLER_0], 0);
    EXPECT_EQ(gBattleCommunication[MULTISTRING_CHOOSER], 0xFF);
    EXPECT(!gBattleMons[B_BATTLER_0].volatiles.flashFireBoosted);

    gBattleCommunication[MULTISTRING_CHOOSER] = 0;
    Free(gBattleStruct);
    gBattleStruct = savedBattleStruct;
    ClearStaleBattleState();
    ZeroMonData(mon);
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
