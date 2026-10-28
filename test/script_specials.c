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
static u16 GetSpeciesOfBoxMonInFirstSlot(enum Species species, bool8 isEgg)
{
    struct BoxPokemon *boxmon = GetBoxedMonPtr(0, 0);
    u16 result;

    CreateBoxMon(boxmon, species, 5, 0, OTID_STRUCT_PLAYER_ID);
    SetBoxMonData(boxmon, MON_DATA_IS_EGG, &isEgg);
    gSpecialVar_MonBoxId = 0;
    gSpecialVar_MonBoxPos = 0;
    gSpecialVar_0x8004 = PC_MON_CHOSEN;
    RUN_OVERWORLD_SCRIPT( specialvar VAR_RESULT, ScriptGetPartyMonSpecies; );
    result = VarGet(VAR_RESULT);

    // PC storage and the special vars aren't reset between tests.
    ZeroBoxMonData(boxmon);
    gSpecialVar_0x8004 = 0;
    return result;
}

TEST("Script specials: ScriptGetPartyMonSpecies reports an Egg chosen from the PC")
{
    ZeroPlayerPartyMons();
    EXPECT_EQ(GetSpeciesOfBoxMonInFirstSlot(SPECIES_WOBBUFFET, TRUE), SPECIES_EGG);
}

TEST("Script specials: ScriptGetPartyMonSpecies reports the species of a mon chosen from the PC")
{
    ZeroPlayerPartyMons();
    EXPECT_EQ(GetSpeciesOfBoxMonInFirstSlot(SPECIES_WOBBUFFET, FALSE), SPECIES_WOBBUFFET);
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
    gSpecialVar_0x8004 = 0;
    EXPECT_EQ(VarGet(VAR_RESULT), SPECIES_WYNAUT);
}

// Route117_OnTransition reads VAR_RESULT after this special to pick the daycare mons'
// movement types; getdaycaregfx leaves VAR_RESULT at 2 just before it. The expansion
// made the special write VAR_RESULT, and this pins that.
TEST("Script specials: SetDaycareCompatibilityString returns the compatibility score")
{
    ZeroPlayerPartyMons();
    RUN_OVERWORLD_SCRIPT(
        givemon SPECIES_WOBBUFFET, 100, gender=MON_MALE;
        givemon SPECIES_WOBBUFFET, 100, gender=MON_FEMALE;
    );
    StorePokemonInDaycare(&gParties[B_TRAINER_PLAYER][0], &gSaveBlock1Ptr->daycare.mons[0]);
    StorePokemonInDaycare(&gParties[B_TRAINER_PLAYER][0], &gSaveBlock1Ptr->daycare.mons[1]); // the party compacts
    RUN_OVERWORLD_SCRIPT(
        setvar VAR_RESULT, 2;
        special SetDaycareCompatibilityString;
    );
    // Same species, same Trainer ID.
    EXPECT_EQ(VarGet(VAR_RESULT), PARENTS_MED_COMPATIBILITY);
}
