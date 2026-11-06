#include "global.h"
#include "event_data.h"
#include "item.h"
#include "item_use.h"
#include "overworld.h"
#include "pokemon.h"
#include "rtc.h"
#include "test/test.h"

// The evolution scene evolves the mon and then calls ConsumeEvolutionItems. Cancelling it
// with B never gets there, so the DO_EVO pass before it must leave the items alone.
static void CreatePartyMon(u32 slot, enum Species species, enum Item heldItem)
{
    CreateMon(&gParties[B_TRAINER_PLAYER][slot], species, 30, 0, OTID_STRUCT_PRESET(0));
    SetMonData(&gParties[B_TRAINER_PLAYER][slot], MON_DATA_HELD_ITEM, &heldItem);
}

TEST("Evolution items: a cancelled evolution keeps the held item and a completed one uses it")
{
    struct Pokemon *onix = &gParties[B_TRAINER_PLAYER][0];

    ZeroPlayerPartyMons();
    CreatePartyMon(0, SPECIES_ONIX, ITEM_METAL_COAT);

    EXPECT_EQ(GetEvolutionTargetSpecies(onix, EVO_MODE_TRADE, ITEM_NONE, NULL, NULL, DO_EVO), SPECIES_STEELIX);
    EXPECT_EQ(GetMonData(onix, MON_DATA_HELD_ITEM), ITEM_METAL_COAT);

    ConsumeEvolutionItems(onix);
    EXPECT_EQ(GetMonData(onix, MON_DATA_HELD_ITEM), ITEM_NONE);
}

TEST("Evolution items: a cancelled evolution keeps the bag items and a completed one uses them")
{
    struct Pokemon *gimmighoul = &gParties[B_TRAINER_PLAYER][0];
    bool32 canStopEvo = TRUE;

    ZeroPlayerPartyMons();
    ClearBag();
    CreatePartyMon(0, SPECIES_GIMMIGHOUL, ITEM_NONE);
    EXPECT(AddBagItem(ITEM_GIMMIGHOUL_COIN, 999));

    EXPECT_EQ(GetEvolutionTargetSpecies(gimmighoul, EVO_MODE_NORMAL, ITEM_NONE, NULL, &canStopEvo, DO_EVO), SPECIES_GHOLDENGO);
    EXPECT_EQ(canStopEvo, FALSE);
    EXPECT_EQ(CountTotalItemQuantityInBag(ITEM_GIMMIGHOUL_COIN), 999);

    ConsumeEvolutionItems(gimmighoul);
    EXPECT_EQ(CountTotalItemQuantityInBag(ITEM_GIMMIGHOUL_COIN), 0);
}

TEST("Evolution items: only the mon of the last evolution started uses its items")
{
    struct Pokemon *onix = &gParties[B_TRAINER_PLAYER][0];
    struct Pokemon *wobbuffet = &gParties[B_TRAINER_PLAYER][1];

    ZeroPlayerPartyMons();
    CreatePartyMon(0, SPECIES_ONIX, ITEM_METAL_COAT);
    CreatePartyMon(1, SPECIES_WOBBUFFET, ITEM_NONE);

    EXPECT_EQ(GetEvolutionTargetSpecies(onix, EVO_MODE_TRADE, ITEM_NONE, NULL, NULL, DO_EVO), SPECIES_STEELIX);
    ConsumeEvolutionItems(wobbuffet);
    EXPECT_EQ(GetMonData(onix, MON_DATA_HELD_ITEM), ITEM_METAL_COAT);

    // A later DO_EVO pass that finds no evolution drops the pending items.
    EXPECT_EQ(GetEvolutionTargetSpecies(wobbuffet, EVO_MODE_NORMAL, ITEM_NONE, NULL, NULL, DO_EVO), SPECIES_NONE);
    ConsumeEvolutionItems(onix);
    EXPECT_EQ(GetMonData(onix, MON_DATA_HELD_ITEM), ITEM_METAL_COAT);
}

TEST("Evolution items: an entry that matches only in part keeps the items and the cancel")
{
    static const struct EvolutionParam params[] =
    {
        {IF_HOLD_ITEM, ITEM_RAZOR_FANG},
        {IF_BAG_ITEM_COUNT, ITEM_POTION, 1},
        {IF_KNOWS_MOVE, MOVE_SKETCH},
        {CONDITIONS_END},
    };
    struct Pokemon *gligar = &gParties[B_TRAINER_PLAYER][0];
    bool32 canStopEvo = TRUE;

    ZeroPlayerPartyMons();
    ClearBag();
    CreatePartyMon(0, SPECIES_GLIGAR, ITEM_RAZOR_FANG);
    EXPECT(AddBagItem(ITEM_POTION, 1));

    EXPECT_EQ(DoesMonMeetAdditionalConditions(gligar, params, NULL, PARTY_SIZE, &canStopEvo, DO_EVO), FALSE);
    EXPECT_EQ(GetMonData(gligar, MON_DATA_HELD_ITEM), ITEM_RAZOR_FANG);
    EXPECT_EQ(CountTotalItemQuantityInBag(ITEM_POTION), 1);
    EXPECT_EQ(canStopEvo, TRUE);
}

// Platinum (pret/pokeplatinum Party_HasSpecies) reads MON_DATA_SPECIES, which is an Egg's
// own species, so a Remoraid Egg lets Mantyke evolve there too (#168).
TEST("Evolution party conditions: an Egg in the party counts, as in Platinum")
{
    struct Pokemon *mantyke = &gParties[B_TRAINER_PLAYER][0];
    bool32 isEgg = TRUE;

    ZeroPlayerPartyMons();
    CreatePartyMon(0, SPECIES_MANTYKE, ITEM_NONE);
    CreatePartyMon(1, SPECIES_REMORAID, ITEM_NONE);
    SetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_IS_EGG, &isEgg);

    EXPECT_EQ(GetEvolutionTargetSpecies(mantyke, EVO_MODE_NORMAL, ITEM_NONE, NULL, NULL, CHECK_EVO), SPECIES_MANTINE);
}

// The fork sells the Linking Cord at Lilycove (#208) for the trade evolutions that need
// no held item, and I_USE_EVO_HELD_ITEMS_FROM_BAG covers the ones that do.
TEST("Linking Cord: evolves a trade evolution from the bag, and nothing else")
{
    struct Pokemon *mon = &gParties[B_TRAINER_PLAYER][0];

    ZeroPlayerPartyMons();
    EXPECT_EQ(GetItemFieldFunc(ITEM_LINKING_CORD), ItemUseOutOfBattle_EvolutionStone);

    CreatePartyMon(0, SPECIES_KADABRA, ITEM_NONE);
    EXPECT_EQ(GetEvolutionTargetSpecies(mon, EVO_MODE_ITEM_USE, ITEM_LINKING_CORD, NULL, NULL, CHECK_EVO), SPECIES_ALAKAZAM);
    CreatePartyMon(0, SPECIES_GRAVELER, ITEM_NONE);
    EXPECT_EQ(GetEvolutionTargetSpecies(mon, EVO_MODE_ITEM_USE, ITEM_LINKING_CORD, NULL, NULL, CHECK_EVO), SPECIES_GOLEM);
    CreatePartyMon(0, SPECIES_ABRA, ITEM_NONE);
    EXPECT_EQ(GetEvolutionTargetSpecies(mon, EVO_MODE_ITEM_USE, ITEM_LINKING_CORD, NULL, NULL, CHECK_EVO), SPECIES_NONE);
}

TEST("Linking Cord: trade held items are used from the bag like stones")
{
    struct Pokemon *onix = &gParties[B_TRAINER_PLAYER][0];

    ZeroPlayerPartyMons();
    EXPECT_EQ(GetItemType(ITEM_METAL_COAT), ITEM_USE_PARTY_MENU);
    EXPECT_EQ(GetItemFieldFunc(ITEM_METAL_COAT), ItemUseOutOfBattle_EvolutionStone);

    CreatePartyMon(0, SPECIES_ONIX, ITEM_NONE);
    EXPECT_EQ(GetEvolutionTargetSpecies(onix, EVO_MODE_ITEM_USE, ITEM_METAL_COAT, NULL, NULL, CHECK_EVO), SPECIES_STEELIX);
}

// Milcery's day spins checked IF_TIME TIME_DAY, so no entry matched in the morning
// (6-10 under the Gen 8+ times), though Sword and Shield count it as day (#169). They
// now match anything but the night and the evening, which Rainbow Swirl keeps.
static enum Species GetMilcerySpinEvolution(u32 hours, u16 spin)
{
    struct Pokemon *milcery = &gParties[B_TRAINER_PLAYER][0];
    enum Species targetSpecies;

    ZeroPlayerPartyMons();
    CreatePartyMon(0, SPECIES_MILCERY, ITEM_STRAWBERRY_SWEET);
    SetTimeOfDay(hours);
    gSpecialVar_0x8000 = spin;
    targetSpecies = GetEvolutionTargetSpecies(milcery, EVO_MODE_OVERWORLD_SPECIAL, ITEM_NONE, NULL, NULL, CHECK_EVO);
    SetTimeOfDay(0);
    return targetSpecies;
}

TEST("Milcery morning: a day spin evolves Milcery in the morning too")
{
    u32 hours = 0;
    enum TimeOfDay timeOfDay = TIME_MORNING;

    PARAMETRIZE { hours = MORNING_HOUR_BEGIN; timeOfDay = TIME_MORNING; }
    PARAMETRIZE { hours = DAY_HOUR_BEGIN; timeOfDay = TIME_DAY; }

    SetTimeOfDay(hours);
    EXPECT_EQ(GetTimeOfDay(), timeOfDay);
    SetTimeOfDay(0);
    EXPECT_EQ(GetMilcerySpinEvolution(hours, SPIN_CW_SHORT), SPECIES_ALCREMIE_STRAWBERRY_VANILLA_CREAM);
    EXPECT_EQ(GetMilcerySpinEvolution(hours, SPIN_CCW_SHORT), SPECIES_ALCREMIE_STRAWBERRY_RUBY_CREAM);
    EXPECT_EQ(GetMilcerySpinEvolution(hours, SPIN_CCW_LONG), SPECIES_ALCREMIE_STRAWBERRY_RUBY_SWIRL);
    EXPECT_EQ(GetMilcerySpinEvolution(hours, SPIN_CW_LONG), SPECIES_ALCREMIE_STRAWBERRY_CARAMEL_SWIRL);
}

TEST("Milcery morning: the day spins leave the evening and the night alone")
{
    ASSUME(EVENING_HOUR_BEGIN != EVENING_HOUR_END);
    EXPECT_EQ(GetMilcerySpinEvolution(EVENING_HOUR_BEGIN, SPIN_EITHER), SPECIES_ALCREMIE_STRAWBERRY_RAINBOW_SWIRL);
    EXPECT_NE(GetMilcerySpinEvolution(EVENING_HOUR_BEGIN, SPIN_CW_SHORT), SPECIES_ALCREMIE_STRAWBERRY_VANILLA_CREAM);
    EXPECT_EQ(GetMilcerySpinEvolution(NIGHT_HOUR_BEGIN + 1, SPIN_CW_SHORT), SPECIES_ALCREMIE_STRAWBERRY_MATCHA_CREAM);
    EXPECT_EQ(GetMilcerySpinEvolution(NIGHT_HOUR_BEGIN + 1, SPIN_CCW_LONG), SPECIES_ALCREMIE_STRAWBERRY_MINT_CREAM);
}
