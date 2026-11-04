#include "global.h"
#include "battle.h"
#include "battle_util.h"
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
