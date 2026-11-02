#include "global.h"
#include "battle_setup.h"
#include "event_data.h"
#include "rematch_indicator.h"
#include "test/test.h"
#include "constants/rematches.h"

// The overworld rematch marker's decision (#207), on real map scripts.
extern const u8 Route102_EventScript_Calvin[];
extern const u8 Route102_EventScript_Rick[];
extern const u8 Route102_EventScript_LittleBoy[];
extern const u8 MtPyre_3F_EventScript_Gabrielle[];
extern const u8 PetalburgCity_Gym_EventScript_Norman[];
extern const u8 RustboroCity_Gym_EventScript_Roxanne[];

#if FREE_MATCH_CALL == FALSE

static enum RematchIndicator GetScriptRematchIndicator(const u8 *script)
{
    return GetRematchIndicator(GetRematchTableIdFromScript(script));
}

TEST("Rematch indicator: a trainerbattle script's trainer is ready while its rematch byte is set")
{
    EXPECT_EQ(GetRematchTableIdFromScript(Route102_EventScript_Calvin), REMATCH_CALVIN);
    SetTrainerFlag(TRAINER_CALVIN_1);
    FlagSet(TRAINER_REGISTERED_FLAGS_START + REMATCH_CALVIN);
    EXPECT_EQ(GetScriptRematchIndicator(Route102_EventScript_Calvin), REMATCH_INDICATOR_NONE);
    gSaveBlock1Ptr->trainerRematches[REMATCH_CALVIN] = 1;
    EXPECT_EQ(GetScriptRematchIndicator(Route102_EventScript_Calvin), REMATCH_INDICATOR_READY);
}

TEST("Rematch indicator: a vsseeker_rematchid script's trainer is ready while its rematch byte is set")
{
    EXPECT_EQ(GetRematchTableIdFromScript(PetalburgCity_Gym_EventScript_Norman), REMATCH_NORMAN);
    EXPECT_EQ(GetScriptRematchIndicator(PetalburgCity_Gym_EventScript_Norman), REMATCH_INDICATOR_NONE);
    gSaveBlock1Ptr->trainerRematches[REMATCH_NORMAN] = 2;
    EXPECT_EQ(GetScriptRematchIndicator(PetalburgCity_Gym_EventScript_Norman), REMATCH_INDICATOR_READY);
}

TEST("Rematch indicator: a gym leader is ready after the Hall of Fame sets the byte")
{
    SetTrainerFlag(TRAINER_ROXANNE_1);
    FlagSet(FLAG_HAS_MATCH_CALL);
    EXPECT_EQ(GetScriptRematchIndicator(RustboroCity_Gym_EventScript_Roxanne), REMATCH_INDICATOR_NONE);
    gSaveBlock1Ptr->trainerRematches[REMATCH_ROXANNE] = 1;
    EXPECT_EQ(GetScriptRematchIndicator(RustboroCity_Gym_EventScript_Roxanne), REMATCH_INDICATOR_READY);
}

TEST("Rematch indicator: not ready once the rematch byte is 0, even after the second team is beaten")
{
    FlagSet(FLAG_HAS_MATCH_CALL);
    FlagSet(TRAINER_REGISTERED_FLAGS_START + REMATCH_CALVIN);
    SetTrainerFlag(TRAINER_CALVIN_1);
    SetTrainerFlag(TRAINER_CALVIN_2);
    gSaveBlock1Ptr->trainerRematches[REMATCH_CALVIN] = 0;
    EXPECT_EQ(GetScriptRematchIndicator(Route102_EventScript_Calvin), REMATCH_INDICATOR_NONE);
}

TEST("Rematch indicator: a beaten trainer who registers when talked to is marked once the player has Match Call")
{
    SetTrainerFlag(TRAINER_CALVIN_1);
    EXPECT_EQ(GetScriptRematchIndicator(Route102_EventScript_Calvin), REMATCH_INDICATOR_NONE);
    FlagSet(FLAG_HAS_MATCH_CALL);
    EXPECT_EQ(GetScriptRematchIndicator(Route102_EventScript_Calvin), REMATCH_INDICATOR_UNREGISTERED);
    FlagSet(TRAINER_REGISTERED_FLAGS_START + REMATCH_CALVIN);
    EXPECT_EQ(GetScriptRematchIndicator(Route102_EventScript_Calvin), REMATCH_INDICATOR_NONE);
}

TEST("Rematch indicator: an unbeaten trainer isn't marked unregistered")
{
    FlagSet(FLAG_HAS_MATCH_CALL);
    EXPECT_EQ(GetScriptRematchIndicator(Route102_EventScript_Calvin), REMATCH_INDICATOR_NONE);
}

TEST("Rematch indicator: the ready marker wins over the unregistered one")
{
    FlagSet(FLAG_HAS_MATCH_CALL);
    SetTrainerFlag(TRAINER_CALVIN_1);
    gSaveBlock1Ptr->trainerRematches[REMATCH_CALVIN] = 1;
    EXPECT_EQ(GetScriptRematchIndicator(Route102_EventScript_Calvin), REMATCH_INDICATOR_READY);
}

TEST("Rematch indicator: trainers who don't register by talking aren't marked unregistered")
{
    FlagSet(FLAG_HAS_MATCH_CALL);
    SetTrainerFlag(TRAINER_GABRIELLE_1);
    SetTrainerFlag(TRAINER_ROXANNE_1);
    EXPECT_EQ(GetScriptRematchIndicator(MtPyre_3F_EventScript_Gabrielle), REMATCH_INDICATOR_NONE);
    EXPECT_EQ(GetScriptRematchIndicator(RustboroCity_Gym_EventScript_Roxanne), REMATCH_INDICATOR_NONE);
}

TEST("Rematch indicator: a trainer outside the rematch table and a non-trainer object aren't marked")
{
    FlagSet(FLAG_HAS_MATCH_CALL);
    SetTrainerFlag(TRAINER_RICK);
    EXPECT_EQ(GetRematchTableIdFromScript(Route102_EventScript_Rick), -1);
    EXPECT_EQ(GetRematchTableIdFromScript(Route102_EventScript_LittleBoy), -1);
    EXPECT_EQ(GetRematchTableIdFromScript(NULL), -1);
    EXPECT_EQ(GetRematchIndicator(-1), REMATCH_INDICATOR_NONE);
}

#endif // FREE_MATCH_CALL
