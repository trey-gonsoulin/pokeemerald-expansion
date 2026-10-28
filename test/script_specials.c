#include "global.h"
#include "daycare.h"
#include "event_data.h"
#include "pokemon.h"
#include "pokemon_storage_system.h"
#include "constants/party_menu.h"
#include "test/overworld_script.h"
#include "test/test.h"

// The Name Rater, the Battle Frontier breeder (Lounge1) and the Nature Girl (Lounge5)
// pick a mon with chooseboxmon, which can return a PC box mon, then check it for an Egg.
static void PutBoxMonInFirstSlot(enum Species species, bool8 isEgg)
{
    struct BoxPokemon *boxmon = GetBoxedMonPtr(0, 0);

    CreateBoxMon(boxmon, species, 5, 0, OTID_STRUCT_PLAYER_ID);
    SetBoxMonData(boxmon, MON_DATA_IS_EGG, &isEgg);
    gSpecialVar_MonBoxId = 0;
    gSpecialVar_MonBoxPos = 0;
    gSpecialVar_0x8004 = PC_MON_CHOSEN;
}

TEST("Script specials: ScriptGetPartyMonSpecies reports an Egg chosen from the PC")
{
    ZeroPlayerPartyMons();
    PutBoxMonInFirstSlot(SPECIES_WOBBUFFET, TRUE);
    RUN_OVERWORLD_SCRIPT( specialvar VAR_RESULT, ScriptGetPartyMonSpecies; );
    EXPECT_EQ(VarGet(VAR_RESULT), SPECIES_EGG);
}

TEST("Script specials: ScriptGetPartyMonSpecies reports the species of a mon chosen from the PC")
{
    ZeroPlayerPartyMons();
    PutBoxMonInFirstSlot(SPECIES_WOBBUFFET, FALSE);
    RUN_OVERWORLD_SCRIPT( specialvar VAR_RESULT, ScriptGetPartyMonSpecies; );
    EXPECT_EQ(VarGet(VAR_RESULT), SPECIES_WOBBUFFET);
}

TEST("Script specials: ScriptGetPartyMonSpecies still reads a party slot")
{
    ZeroPlayerPartyMons();
    RUN_OVERWORLD_SCRIPT(
        givemon SPECIES_WOBBUFFET, 5;
        givemon SPECIES_WYNAUT, 5;
    );
    gSpecialVar_0x8004 = 1;
    RUN_OVERWORLD_SCRIPT( specialvar VAR_RESULT, ScriptGetPartyMonSpecies; );
    EXPECT_EQ(VarGet(VAR_RESULT), SPECIES_WYNAUT);
}

// Route117_OnTransition reads VAR_RESULT after this special to pick the daycare mons'
// movement types; getdaycaregfx leaves VAR_RESULT at 2 just before it.
TEST("Script specials: SetDaycareCompatibilityString returns the compatibility score")
{
    ZeroPlayerPartyMons();
    RUN_OVERWORLD_SCRIPT(
        givemon SPECIES_WOBBUFFET, 100, gender=MON_MALE;
        givemon SPECIES_WOBBUFFET, 100, gender=MON_FEMALE;
    );
    StorePokemonInDaycare(&gParties[B_TRAINER_PLAYER][0], &gSaveBlock1Ptr->daycare.mons[0]);
    StorePokemonInDaycare(&gParties[B_TRAINER_PLAYER][1], &gSaveBlock1Ptr->daycare.mons[1]);
    RUN_OVERWORLD_SCRIPT(
        setvar VAR_RESULT, 2;
        special SetDaycareCompatibilityString;
    );
    EXPECT_EQ(VarGet(VAR_RESULT), GetDaycareCompatibilityScore(&gSaveBlock1Ptr->daycare));
    EXPECT_NE(VarGet(VAR_RESULT), 2);
}
