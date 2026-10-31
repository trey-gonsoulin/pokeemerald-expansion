#include "global.h"
#include "item.h"
#include "pokemon.h"
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
