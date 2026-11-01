#include "global.h"
#include "evolution_ready.h"
#include "item.h"
#include "pokemon.h"
#include "test/test.h"

// P_PARTY_EVOLUTION_MARKER's check (#204): the next level-up, or an evolution item in the bag
static struct Pokemon *CreateReadyCheckMon(enum Species species, u32 level, enum Item heldItem)
{
    struct Pokemon *mon = &gParties[B_TRAINER_PLAYER][0];

    ZeroPlayerPartyMons();
    ClearBag();
    CreateMon(mon, species, level, 0, OTID_STRUCT_PRESET(0));
    SetMonData(mon, MON_DATA_HELD_ITEM, &heldItem);
    return mon;
}

static void SetFriendship(struct Pokemon *mon, u32 friendship)
{
    SetMonData(mon, MON_DATA_FRIENDSHIP, &friendship);
}

TEST("Evolution ready: Golbat is ready from 160 friendship")
{
    struct Pokemon *golbat = CreateReadyCheckMon(SPECIES_GOLBAT, 30, ITEM_NONE);

    ASSUME(P_FRIENDSHIP_EVO_THRESHOLD >= GEN_8);
    SetFriendship(golbat, 159);
    EXPECT_EQ(CanPartyMonEvolveNow(golbat), FALSE);
    SetFriendship(golbat, 160);
    EXPECT_EQ(CanPartyMonEvolveNow(golbat), TRUE);
}

TEST("Evolution ready: an Everstone stops a level-up evolution")
{
    struct Pokemon *golbat = CreateReadyCheckMon(SPECIES_GOLBAT, 30, ITEM_EVERSTONE);

    SetFriendship(golbat, 255);
    EXPECT_EQ(CanPartyMonEvolveNow(golbat), FALSE);
}

TEST("Evolution ready: Eevee is ready with a Water Stone in the bag")
{
    struct Pokemon *eevee = CreateReadyCheckMon(SPECIES_EEVEE, 30, ITEM_NONE);

    EXPECT_EQ(CanPartyMonEvolveNow(eevee), FALSE);
    EXPECT(AddBagItem(ITEM_WATER_STONE, 1));
    EXPECT_EQ(CanPartyMonEvolveNow(eevee), TRUE);
}

TEST("Evolution ready: an Everstone stops an item evolution")
{
    struct Pokemon *pikachu = CreateReadyCheckMon(SPECIES_PIKACHU, 30, ITEM_EVERSTONE);

    EXPECT(AddBagItem(ITEM_THUNDER_STONE, 1));
    EXPECT_EQ(CanPartyMonEvolveNow(pikachu), FALSE);
}

TEST("Evolution ready: Charmander is ready at level 16, as after a cancelled evolution")
{
    struct Pokemon *charmander = CreateReadyCheckMon(SPECIES_CHARMANDER, 15, ITEM_NONE);

    EXPECT_EQ(CanPartyMonEvolveNow(charmander), FALSE);
    charmander = CreateReadyCheckMon(SPECIES_CHARMANDER, 16, ITEM_NONE);
    EXPECT_EQ(CanPartyMonEvolveNow(charmander), TRUE);
}

TEST("Evolution ready: trade evolutions, Eggs and empty slots aren't ready")
{
    struct Pokemon *mon = CreateReadyCheckMon(SPECIES_KADABRA, 30, ITEM_NONE);
    bool32 isEgg = TRUE;

    EXPECT_EQ(CanPartyMonEvolveNow(mon), FALSE);

    mon = CreateReadyCheckMon(SPECIES_CHARMANDER, 16, ITEM_NONE);
    SetMonData(mon, MON_DATA_IS_EGG, &isEgg);
    EXPECT_EQ(CanPartyMonEvolveNow(mon), FALSE);

    EXPECT_EQ(CanPartyMonEvolveNow(&gParties[B_TRAINER_PLAYER][1]), FALSE);
}

// A Gigantamax Pikachu can't evolve: the check that says so dropped the pending items too
TEST("Evolution ready: the check leaves a started evolution's items alone")
{
    struct Pokemon *onix = &gParties[B_TRAINER_PLAYER][1];
    struct Pokemon *pikachu = CreateReadyCheckMon(SPECIES_PIKACHU, 30, ITEM_NONE);
    enum Item metalCoat = ITEM_METAL_COAT;
    bool32 gigantamaxFactor = TRUE;

    SetMonData(pikachu, MON_DATA_GIGANTAMAX_FACTOR, &gigantamaxFactor);
    EXPECT(AddBagItem(ITEM_THUNDER_STONE, 1));
    CreateMon(onix, SPECIES_ONIX, 30, 0, OTID_STRUCT_PRESET(0));
    SetMonData(onix, MON_DATA_HELD_ITEM, &metalCoat);

    EXPECT_EQ(GetEvolutionTargetSpecies(onix, EVO_MODE_TRADE, ITEM_NONE, NULL, NULL, DO_EVO), SPECIES_STEELIX);
    EXPECT_EQ(CanPartyMonEvolveNow(pikachu), FALSE);
    EXPECT_EQ(CanPartyMonEvolveNow(onix), FALSE);

    ConsumeEvolutionItems(onix);
    EXPECT_EQ(GetMonData(onix, MON_DATA_HELD_ITEM), ITEM_NONE);
}
