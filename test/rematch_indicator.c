#include "global.h"
#include "battle_setup.h"
#include "event_data.h"
#include "overworld.h"
#include "rematch_indicator.h"
#include "script.h"
#include "test/test.h"
#include "constants/rematches.h"
#include "constants/script_commands.h"

typedef u16 (*SpecialFunc)(void);
extern const SpecialFunc gSpecials[];
#define SPECIAL_REQUESTS_EFFECTS 0x2000000 // the ROM_SIZE that def_special's requests_effects adds
bool32 IsTrainerRegistered(void);

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

// The script's `specialvar VAR_RESULT, <func>` in [start, start + length)
static const u8 *FindSpecialVarResult(const u8 *start, u32 length, void *func)
{
    u32 i;

    for (i = 0; i < length; i++)
    {
        const u8 *cmd = start + i;
        if (cmd[0] == SCR_OP_SPECIALVAR && cmd[1] == (VAR_RESULT & 0xFF) && cmd[2] == (VAR_RESULT >> 8)
         && ((u32)gSpecials[cmd[3] | (cmd[4] << 8)] & ~SPECIAL_REQUESTS_EFFECTS) == (u32)func)
            return cmd;
    }
    return NULL;
}

// The first-fight script of a table entry, on the entry's map
static const u8 *FindRematchTrainerScript(s32 rematchTableId)
{
    const struct MapHeader *mapHeader = Overworld_GetMapHeaderByGroupAndId(gRematchTable[rematchTableId].mapGroup, gRematchTable[rematchTableId].mapNum);
    u32 i;

    for (i = 0; i < mapHeader->events->objectEventCount; i++)
    {
        const u8 *script = mapHeader->events->objectEvents[i].script;
        if (GetRematchTableIdFromScript(script) == rematchTableId)
            return script;
    }
    return NULL;
}

// RegistersWhenTalkedTo lists the trainers by hand: this pins it to the scripts, whose talk path
// after the trainerbattle checks ShouldTryRematchBattle and then IsTrainerRegistered.
TEST("Rematch indicator: the unregistered marker goes on exactly the trainers whose talk script registers them")
{
    s32 i;

    FlagSet(FLAG_HAS_MATCH_CALL);
    for (i = 0; i < REMATCH_SPECIAL_TRAINER_START; i++)
    {
        const u8 *script = FindRematchTrainerScript(i);
        const u8 *rematchCheck;
        bool32 registersOnTalk;
        enum RematchIndicator indicator;

        EXPECT(script != NULL);
        rematchCheck = FindSpecialVarResult(script, 64, ShouldTryRematchBattle);
        EXPECT(rematchCheck != NULL);
        registersOnTalk = FindSpecialVarResult(rematchCheck, 32, IsTrainerRegistered) != NULL;
        SetTrainerFlag(gRematchTable[i].trainerIds[0]);
        indicator = GetRematchIndicator(i);
        EXPECT_EQ(indicator, registersOnTalk ? REMATCH_INDICATOR_UNREGISTERED : REMATCH_INDICATOR_NONE);
    }
}

#endif // FREE_MATCH_CALL
