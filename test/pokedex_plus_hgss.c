#include "global.h"
#include "pokemon.h"
#include "pokedex_plus_hgss.h"
#include "sprite.h"
#include "task.h"
#include "test/test.h"

static u32 CountSpritesInUse(void)
{
    u32 i, count = 0;

    for (i = 0; i < MAX_SPRITES; i++)
    {
        if (gSprites[i].inUse)
            count++;
    }
    return count;
}

// Pikachu has 16 forms besides its own and Unown 27: more than the 13 icons
// the page draws, and more than the 11 task data slots after data[4].
TEST("HGSS forms page keeps its form icons inside its own task")
{
    enum Species species = SPECIES_NONE;
    u32 spritesInUse;
    u8 taskId, nextTaskId;
    struct Task nextTask;

    PARAMETRIZE { species = SPECIES_PIKACHU; }
    PARAMETRIZE { species = SPECIES_UNOWN; }

    taskId = CreateTask(TaskDummy, 0);
    nextTaskId = CreateTask(TaskDummy, 0);
    ASSUME(nextTaskId == taskId + 1);
    nextTask = gTasks[nextTaskId];
    spritesInUse = CountSpritesInUse();

    Test_PrintAndDestroyFormIcons(taskId, species);

    EXPECT(memcmp(&nextTask, &gTasks[nextTaskId], sizeof(nextTask)) == 0);
    EXPECT_EQ(CountSpritesInUse(), spritesInUse);
    DestroyTask(nextTaskId);
    DestroyTask(taskId);
}
