#include "global.h"
#include "pokemon.h"
#include "pokedex_plus_hgss.h"
#include "sprite.h"
#include "task.h"
#include "test/test.h"

static u64 GetSpritesInUse(void)
{
    u32 i;
    u64 inUse = 0;

    for (i = 0; i < MAX_SPRITES; i++)
    {
        if (gSprites[i].inUse)
            inUse |= 1ull << i;
    }
    return inUse;
}

// Pikachu has 16 forms besides its own and Unown 27: more than the 13 icons
// the page draws before it scrolls, and more than the 11 task data slots after data[4].
TEST("HGSS forms page keeps its form icons inside its own task")
{
    enum Species species = SPECIES_NONE;
    u64 spritesInUse;
    u8 taskId, nextTaskId;
    struct Task nextTask;

    PARAMETRIZE { species = SPECIES_PIKACHU; }
    PARAMETRIZE { species = SPECIES_UNOWN; }

    taskId = CreateTask(TaskDummy, 0);
    nextTaskId = CreateTask(TaskDummy, 0);
    ASSUME(nextTaskId == taskId + 1);
    nextTask = gTasks[nextTaskId];
    spritesInUse = GetSpritesInUse();

    Test_PrintAndDestroyFormIcons(taskId, species);

    EXPECT(memcmp(&nextTask, &gTasks[nextTaskId], sizeof(nextTask)) == 0);
    EXPECT(GetSpritesInUse() == spritesInUse);
    DestroyTask(nextTaskId);
    DestroyTask(taskId);
}

// The page shows two rows of 7 cells, the first the current form's. The cursor
// on Pikachu's last form (cell 16, row 2) shows rows 1-2, cells 7-16; on Unown's
// (cell 27, row 3) rows 2-3, cells 14-27.
TEST("HGSS forms page scrolls its rows to the cursor")
{
    enum Species species = SPECIES_NONE;
    u8 menuPos = 0, expectedIcons = 0;
    u8 numIcons[2];
    bool8 currentIconHidden[2];
    u64 spritesInUse;
    u8 taskId;

    PARAMETRIZE { species = SPECIES_PIKACHU; menuPos = 16; expectedIcons = 10; }
    PARAMETRIZE { species = SPECIES_UNOWN; menuPos = 27; expectedIcons = 14; }

    taskId = CreateTask(TaskDummy, 0);
    spritesInUse = GetSpritesInUse();

    Test_ScrollFormIcons(taskId, species, menuPos, numIcons, currentIconHidden);

    EXPECT_EQ(numIcons[0], expectedIcons);
    EXPECT(currentIconHidden[0]);
    EXPECT_EQ(numIcons[1], 13);
    EXPECT(!currentIconHidden[1]);
    EXPECT(GetSpritesInUse() == spritesInUse);
    DestroyTask(taskId);
}

// Eevee's page has 10 rows and Milcery's 9: the most of any species, and
// more than arrowSpriteDist[10] fits, whose overflow lands in targetSpecies.
TEST("HGSS evolution page keeps its first rows' species")
{
    enum Species species = SPECIES_NONE;
    enum Species targetSpecies[2], expected[2];
    const struct Evolution *evolutions;
    u32 i, row;
    u8 taskId;

    PARAMETRIZE { species = SPECIES_EEVEE; }
    PARAMETRIZE { species = SPECIES_MILCERY; }

    evolutions = GetSpeciesEvolutions(species);
    for (i = 0, row = 0; row < ARRAY_COUNT(expected); i++)
    {
        ASSUME(evolutions[i].method != EVOLUTIONS_END);
        if (IsSpeciesEnabled(evolutions[i].targetSpecies))
            expected[row++] = evolutions[i].targetSpecies;
    }

    taskId = CreateTask(TaskDummy, 0);
    Test_PrintAndDestroyEvolutionPage(taskId, species, targetSpecies, ARRAY_COUNT(targetSpecies));
    DestroyTask(taskId);

    EXPECT_EQ(targetSpecies[0], expected[0]);
    EXPECT_EQ(targetSpecies[1], expected[1]);
}

// Raichu has two pre-evolutions, Combusken one, Torchic none and Eevee the
// most evolution icons.
TEST("HGSS evolution page frees every icon it draws")
{
    enum Species species = SPECIES_NONE;
    enum Species targetSpecies[1];
    u32 expectedIcons = 0;
    u64 spritesInUse;
    u8 taskId;

    PARAMETRIZE { species = SPECIES_RAICHU; expectedIcons = 3; }
    PARAMETRIZE { species = SPECIES_COMBUSKEN; expectedIcons = 3; }
    PARAMETRIZE { species = SPECIES_TORCHIC; expectedIcons = 3; }
    PARAMETRIZE { species = SPECIES_EEVEE; expectedIcons = 9; }

    taskId = CreateTask(TaskDummy, 0);
    spritesInUse = GetSpritesInUse();

    EXPECT_EQ(Test_PrintAndDestroyEvolutionPage(taskId, species, targetSpecies, ARRAY_COUNT(targetSpecies)), expectedIcons);
    EXPECT(GetSpritesInUse() == spritesInUse);
    DestroyTask(taskId);
}
