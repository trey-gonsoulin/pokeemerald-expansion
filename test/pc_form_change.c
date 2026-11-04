#include "global.h"
#include "pokemon.h"
#include "pokemon_storage_system.h"
#include "test/test.h"
#include "constants/form_change_types.h"
#include "constants/items.h"

// The stats a Pokémon like mon would have as species
static void ExpectStatsOf(struct Pokemon *mon, enum Species species)
{
    struct Pokemon expected = *mon;

    SetMonData(&expected, MON_DATA_SPECIES, &species);
    CalculateMonStats(&expected);
    EXPECT_EQ(GetMonData(mon, MON_DATA_SPECIES), species);
    for (enum Stat stat = STAT_HP; stat < NUM_STATS; stat++)
        EXPECT_EQ(GetMonData(mon, MON_DATA_MAX_HP + stat), GetMonData(&expected, MON_DATA_MAX_HP + stat));
}

TEST("PC form change: a party Pokemon withdrawn into another form takes its stats")
{
    struct Pokemon *mon = &gParties[B_TRAINER_PLAYER][1];

    ASSUME(GetSpeciesBaseSpeed(SPECIES_SHAYMIN_SKY) != GetSpeciesBaseSpeed(SPECIES_SHAYMIN_LAND));
    CreateMon(mon, SPECIES_SHAYMIN_SKY, 50, 0, OTID_STRUCT_PRESET(0));
    CalculateMonStats(mon);

    SetMonFormPSS(&mon->box, FORM_CHANGE_WITHDRAW);

    ExpectStatsOf(mon, SPECIES_SHAYMIN_LAND);
}

TEST("PC form change: a party Pokemon given a form item takes its form's stats")
{
    struct Pokemon *mon = &gParties[B_TRAINER_PLAYER][0];
    enum Item item = ITEM_GRISEOUS_CORE;

    ASSUME(GetSpeciesBaseAttack(SPECIES_GIRATINA_ORIGIN) != GetSpeciesBaseAttack(SPECIES_GIRATINA_ALTERED));
    CreateMon(mon, SPECIES_GIRATINA_ALTERED, 50, 0, OTID_STRUCT_PRESET(0));
    CalculateMonStats(mon);
    SetMonData(mon, MON_DATA_HELD_ITEM, &item);

    SetMonFormPSS(&mon->box, FORM_CHANGE_ITEM_HOLD);

    ExpectStatsOf(mon, SPECIES_GIRATINA_ORIGIN);
}
