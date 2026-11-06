#include "global.h"
#include "event_data.h"
#include "field_player_avatar.h"
#include "item.h"
#include "item_use.h"
#include "overworld.h"
#include "party_menu.h"
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

static bool32 SpeciesLearnsMove(enum Species species, enum Move move)
{
    const struct LevelUpMove *learnset = GetSpeciesLevelUpLearnset(species);

    for (u32 i = 0; learnset[i].move != LEVEL_UP_MOVE_END; i++)
    {
        if (learnset[i].move == move)
            return TRUE;
    }
    return SpeciesHasEggMove(species, move) || CanLearnTeachableMove(species, move);
}

// The species, or one of its pre-evolutions, can learn the move by level up, as an egg move, or
// from a TM or tutor of this build.
static bool32 LineLearnsMove(enum Species species, enum Move move)
{
    for (; species != SPECIES_NONE; species = GetSpeciesPreEvolution(species))
    {
        if (SpeciesLearnsMove(species, move))
            return TRUE;
    }
    return FALSE;
}

// Dipplin evolves while it knows Dragon Cheer, which Scarlet and Violet teach only by TM (#167).
TEST("Known-move evolution: every move an evolution needs can be learned by the line")
{
    enum Species unreachable = SPECIES_NONE;

    for (enum Species species = SPECIES_NONE + 1; species < NUM_SPECIES && unreachable == SPECIES_NONE; species++)
    {
        if (!IsSpeciesEnabled(species))
            continue;

        const struct Evolution *evolutions = GetSpeciesEvolutions(species);

        if (evolutions == NULL)
            continue;
        for (u32 i = 0; evolutions[i].method != EVOLUTIONS_END; i++)
        {
            const struct EvolutionParam *params = evolutions[i].params;

            for (u32 j = 0; params != NULL && params[j].condition != CONDITIONS_END; j++)
            {
                if (params[j].condition == IF_KNOWS_MOVE && !LineLearnsMove(species, params[j].arg1))
                    unreachable = species;
            }
        }
    }
    EXPECT_EQ(unreachable, SPECIES_NONE);
}

TEST("Known-move evolution: Dipplin learns Dragon Cheer on evolving and then evolves into Hydrapple")
{
    struct Pokemon *dipplin = &gParties[B_TRAINER_PLAYER][0];
    enum Move move = MOVE_NONE;

    ASSUME(IsSpeciesEnabled(SPECIES_DIPPLIN));
    ZeroPlayerPartyMons();
    CreatePartyMon(0, SPECIES_DIPPLIN, ITEM_NONE);
    EXPECT_EQ(GetEvolutionTargetSpecies(dipplin, EVO_MODE_NORMAL, ITEM_NONE, NULL, NULL, CHECK_EVO), SPECIES_NONE);

    // The moves the evolution scene teaches on becoming Dipplin, into an empty moveset.
    for (u32 i = 0; i < MAX_MON_MOVES; i++)
        SetMonData(dipplin, MON_DATA_MOVE1 + i, &move);
    for (bool32 firstMove = TRUE; MonTryLearningNewMoveEvolution(dipplin, firstMove) != 0; firstMove = FALSE)
        ;
    EXPECT(MonKnowsMove(dipplin, MOVE_DRAGON_CHEER));
    EXPECT_EQ(GetEvolutionTargetSpecies(dipplin, EVO_MODE_NORMAL, ITEM_NONE, NULL, NULL, CHECK_EVO), SPECIES_HYDRAPPLE);
}

// Under the Gen 7 and Gen 8+ times the evening is its own time of day, but a time-based
// evolution counts it as day: Sword and Shield evolve by day from 6:00 to 19:59 and by night
// from 20:00 (Bulbapedia's Time-based Evolution), Sun and Moon by night from 18:00, and only
// Dusk Lycanroc and Rainbow Swirl Alcremie take the evening itself. So a day evolution checks
// NOT Night (which takes the morning too) and a night one the night alone (#290).
TEST("Night evolution evening: every time condition counts the morning and the evening as day")
{
    u32 species, i, j;

    for (species = 0; species < NUM_SPECIES; species++)
    {
        const struct Evolution *evolutions = gSpeciesInfo[species].evolutions;

        for (i = 0; evolutions != NULL && evolutions[i].method != EVOLUTIONS_END; i++)
        {
            for (j = 0; evolutions[i].params != NULL && evolutions[i].params[j].condition != CONDITIONS_END; j++)
            {
                if (evolutions[i].params[j].condition == IF_TIME)
                    EXPECT(evolutions[i].params[j].arg1 == TIME_NIGHT || evolutions[i].params[j].arg1 == TIME_EVENING);
                else if (evolutions[i].params[j].condition == IF_NOT_TIME)
                    EXPECT_EQ(evolutions[i].params[j].arg1, TIME_NIGHT);
            }
        }
    }
}

TEST("Night evolution evening: Eevee and Sneasel evolve by day in the evening and by night after it")
{
    struct Pokemon *mon = &gParties[B_TRAINER_PLAYER][0];
    u32 friendship = MAX_FRIENDSHIP;

    ASSUME(EVENING_HOUR_BEGIN != EVENING_HOUR_END);
    ZeroPlayerPartyMons();
    CreatePartyMon(0, SPECIES_EEVEE, ITEM_NONE);
    SetMonData(mon, MON_DATA_FRIENDSHIP, &friendship);
    SetMonMoveSlot(mon, MOVE_TACKLE, 0);
    for (u32 i = 1; i < MAX_MON_MOVES; i++)
        SetMonMoveSlot(mon, MOVE_NONE, i);

    SetTimeOfDay(EVENING_HOUR_BEGIN);
    EXPECT_EQ(GetTimeOfDay(), TIME_EVENING);
    EXPECT_EQ(GetEvolutionTargetSpecies(mon, EVO_MODE_NORMAL, ITEM_NONE, NULL, NULL, CHECK_EVO), SPECIES_ESPEON);
    SetTimeOfDay(MORNING_HOUR_BEGIN);
    EXPECT_EQ(GetEvolutionTargetSpecies(mon, EVO_MODE_NORMAL, ITEM_NONE, NULL, NULL, CHECK_EVO), SPECIES_ESPEON);
    SetTimeOfDay(NIGHT_HOUR_BEGIN);
    EXPECT_EQ(GetEvolutionTargetSpecies(mon, EVO_MODE_NORMAL, ITEM_NONE, NULL, NULL, CHECK_EVO), SPECIES_UMBREON);

    CreatePartyMon(0, SPECIES_SNEASEL, ITEM_NONE);
    SetTimeOfDay(EVENING_HOUR_BEGIN);
    EXPECT_EQ(GetEvolutionTargetSpecies(mon, EVO_MODE_ITEM_USE, ITEM_RAZOR_CLAW, NULL, NULL, CHECK_EVO), SPECIES_NONE);
    SetTimeOfDay(NIGHT_HOUR_BEGIN);
    EXPECT_EQ(GetEvolutionTargetSpecies(mon, EVO_MODE_ITEM_USE, ITEM_RAZOR_CLAW, NULL, NULL, CHECK_EVO), SPECIES_WEAVILE);
    SetTimeOfDay(0);
}

// gSpecialVar_0x8001 is the long spin in the direction of a 10-second spin (SPIN_EITHER),
// which CanTriggerSpinEvolution sets and GetEvolutionTargetSpecies falls back to (#289).
static enum Species GetMilcerySpinEvolutionWithFallback(enum Item sweet, u32 hours, u16 spin, u16 longSpin)
{
    struct Pokemon *milcery = &gParties[B_TRAINER_PLAYER][0];
    enum Species targetSpecies;

    ZeroPlayerPartyMons();
    CreatePartyMon(0, SPECIES_MILCERY, sweet);
    SetTimeOfDay(hours);
    gSpecialVar_0x8000 = spin;
    gSpecialVar_0x8001 = longSpin;
    targetSpecies = GetEvolutionTargetSpecies(milcery, EVO_MODE_OVERWORLD_SPECIAL, ITEM_NONE, NULL, NULL, CHECK_EVO);
    EXPECT_EQ(gSpecialVar_0x8000, spin);
    gSpecialVar_0x8000 = 0;
    gSpecialVar_0x8001 = 0;
    SetTimeOfDay(0);
    return targetSpecies;
}

static enum Species GetMilcerySpinEvolution(enum Item sweet, u32 hours, u16 spin)
{
    return GetMilcerySpinEvolutionWithFallback(sweet, hours, spin, SPIN_NONE);
}

// Milcery's day spins checked IF_TIME TIME_DAY, so no entry matched in the morning
// (6-10 under the Gen 8+ times), though Sword and Shield count it as day (#169). They
// now check NOT Night, as the other day evolutions do, which takes the evening too (#290).
TEST("Milcery morning: every day spin evolves Milcery in the morning and the evening too")
{
    static const u16 daySpins[] = { SPIN_CW_SHORT, SPIN_CCW_SHORT, SPIN_CW_LONG, SPIN_CCW_LONG };
    enum Item sweet = ITEM_NONE;
    enum TimeOfDay timeOfDay;
    u32 i;

    for (i = ITEM_STRAWBERRY_SWEET; i <= ITEM_RIBBON_SWEET; i++)
        PARAMETRIZE { sweet = i; }

    ASSUME(MORNING_HOUR_BEGIN != MORNING_HOUR_END);
    ASSUME(EVENING_HOUR_BEGIN != EVENING_HOUR_END);
    SetTimeOfDay(MORNING_HOUR_BEGIN);
    timeOfDay = GetTimeOfDay();
    SetTimeOfDay(0);
    EXPECT_EQ(timeOfDay, TIME_MORNING);

    for (i = 0; i < ARRAY_COUNT(daySpins); i++)
    {
        enum Species daySpecies = GetMilcerySpinEvolution(sweet, DAY_HOUR_BEGIN, daySpins[i]);

        EXPECT_NE(daySpecies, SPECIES_NONE);
        EXPECT_NE(daySpecies, GetMilcerySpinEvolution(sweet, NIGHT_HOUR_BEGIN, daySpins[i]));
        EXPECT_EQ(GetMilcerySpinEvolution(sweet, MORNING_HOUR_BEGIN, daySpins[i]), daySpecies);
        EXPECT_EQ(GetMilcerySpinEvolution(sweet, EVENING_HOUR_BEGIN, daySpins[i]), daySpecies);
    }
}

TEST("Milcery evening: a 10-second spin gives Rainbow Swirl in the evening alone")
{
    ASSUME(EVENING_HOUR_BEGIN != EVENING_HOUR_END);
    EXPECT_EQ(GetMilcerySpinEvolution(ITEM_STRAWBERRY_SWEET, EVENING_HOUR_BEGIN, SPIN_EITHER), SPECIES_ALCREMIE_STRAWBERRY_RAINBOW_SWIRL);
    EXPECT_EQ(GetMilcerySpinEvolutionWithFallback(ITEM_STRAWBERRY_SWEET, EVENING_HOUR_BEGIN, SPIN_EITHER, SPIN_CCW_LONG), SPECIES_ALCREMIE_STRAWBERRY_RAINBOW_SWIRL);
    EXPECT_EQ(GetMilcerySpinEvolution(ITEM_STRAWBERRY_SWEET, EVENING_HOUR_BEGIN, SPIN_CCW_LONG), SPECIES_ALCREMIE_STRAWBERRY_RUBY_SWIRL);
    EXPECT_EQ(GetMilcerySpinEvolution(ITEM_STRAWBERRY_SWEET, EVENING_HOUR_BEGIN, SPIN_CW_SHORT), SPECIES_ALCREMIE_STRAWBERRY_VANILLA_CREAM);
    EXPECT_EQ(GetMilcerySpinEvolution(ITEM_STRAWBERRY_SWEET, NIGHT_HOUR_BEGIN, SPIN_CW_SHORT), SPECIES_ALCREMIE_STRAWBERRY_MATCHA_CREAM);
    EXPECT_EQ(GetMilcerySpinEvolution(ITEM_STRAWBERRY_SWEET, NIGHT_HOUR_BEGIN, SPIN_EITHER), SPECIES_NONE);
    EXPECT_EQ(GetMilcerySpinEvolution(ITEM_STRAWBERRY_SWEET, DAY_HOUR_BEGIN, SPIN_EITHER), SPECIES_NONE);
}

// A 10-second spin was SPIN_EITHER alone, which only Rainbow Swirl takes, so outside the
// evening it evolved nothing, where a 5-second spin the same way gave the long-spin form;
// Serebii gives Rainbow Swirl as the one rule past 10 s, so the others take any spin past 5 s.
TEST("Milcery long spin: a 10-second spin gives the long-spin form outside the evening")
{
    EXPECT_EQ(GetMilcerySpinEvolutionWithFallback(ITEM_STRAWBERRY_SWEET, DAY_HOUR_BEGIN, SPIN_EITHER, SPIN_CCW_LONG), SPECIES_ALCREMIE_STRAWBERRY_RUBY_SWIRL);
    EXPECT_EQ(GetMilcerySpinEvolutionWithFallback(ITEM_STRAWBERRY_SWEET, MORNING_HOUR_BEGIN, SPIN_EITHER, SPIN_CW_LONG), SPECIES_ALCREMIE_STRAWBERRY_CARAMEL_SWIRL);
    EXPECT_EQ(GetMilcerySpinEvolutionWithFallback(ITEM_STRAWBERRY_SWEET, NIGHT_HOUR_BEGIN, SPIN_EITHER, SPIN_CCW_LONG), SPECIES_ALCREMIE_STRAWBERRY_MINT_CREAM);
    EXPECT_EQ(GetMilcerySpinEvolutionWithFallback(ITEM_STRAWBERRY_SWEET, NIGHT_HOUR_BEGIN, SPIN_EITHER, SPIN_CW_LONG), SPECIES_ALCREMIE_STRAWBERRY_LEMON_CREAM);
}

TEST("Milcery long spin: CanTriggerSpinEvolution keeps a 10-second spin's direction")
{
    Test_SetFinishedSpin(60 * 10, FALSE);
    EXPECT(CanTriggerSpinEvolution());
    EXPECT_EQ(gSpecialVar_0x8000, SPIN_EITHER);
    EXPECT_EQ(gSpecialVar_0x8001, SPIN_CCW_LONG);

    Test_SetFinishedSpin(60 * 10 - 1, TRUE);
    EXPECT(CanTriggerSpinEvolution());
    EXPECT_EQ(gSpecialVar_0x8000, SPIN_CW_LONG);
    EXPECT_EQ(gSpecialVar_0x8001, SPIN_NONE);

    Test_SetFinishedSpin(60 * 5 - 1, TRUE);
    EXPECT(CanTriggerSpinEvolution());
    EXPECT_EQ(gSpecialVar_0x8000, SPIN_CW_SHORT);
    EXPECT_EQ(gSpecialVar_0x8001, SPIN_NONE);
    gSpecialVar_0x8000 = 0;
}
