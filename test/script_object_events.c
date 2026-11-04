#include "global.h"
#include "event_data.h"
#include "event_object_movement.h"
#include "event_scripts.h"
#include "fieldmap.h"
#include "script.h"
#include "sprite.h"
#include "task.h"
#include "constants/event_objects.h"
#include "test/overworld_script.h"
#include "test/test.h"

// Script commands on an object that isn't spawned (flag-hidden, off the window, or left
// without a slot on a full map, #114) found no slot, and indexed gObjectEvents with
// OBJECT_EVENTS_COUNT (#115). Test builds fill that guard element with 0xFF and fail a
// test that changes it.

#define LOCALID_TEST_NPC 1
#define LOCALID_UNSPAWNED 2

static u8 SetUpScriptObjectTest(bool32 spawnNpc)
{
    ResetSpriteData();
    FreeAllSpritePalettes();
    ResetObjectEvents();
    if (!spawnNpc)
        return OBJECT_EVENTS_COUNT;
    return SpawnSpecialObjectEventParameterized(OBJ_EVENT_GFX_BOY_1, MOVEMENT_TYPE_FACE_DOWN, LOCALID_TEST_NPC,
                                                gSaveBlock1Ptr->pos.x + MAP_OFFSET + 1,
                                                gSaveBlock1Ptr->pos.y + MAP_OFFSET, 3);
}

static void CleanUpScriptObjectTest(void)
{
    ResetTasks(); // The movement task of an applymovement that started one
    ResetObjectEvents();
}

TEST("Script object events: applymovement on an object that isn't spawned writes nothing")
{
    SetUpScriptObjectTest(FALSE);
    EXPECT_EQ(GetObjectEventIdByLocalId(LOCALID_UNSPAWNED), OBJECT_EVENTS_COUNT);

    RUN_OVERWORLD_SCRIPT( applymovement LOCALID_UNSPAWNED, Common_Movement_FaceDown; );

    CleanUpScriptObjectTest();
}

TEST("Script object events: applymovement clears a spawned object's direction overwrite")
{
    u8 npc = SetUpScriptObjectTest(TRUE);
    EXPECT_NE(npc, OBJECT_EVENTS_COUNT);
    gObjectEvents[npc].directionOverwrite = DIR_NORTH;

    RUN_OVERWORLD_SCRIPT( applymovement LOCALID_TEST_NPC, Common_Movement_FaceDown; );

    EXPECT_EQ((enum Direction)gObjectEvents[npc].directionOverwrite, DIR_NONE);
    CleanUpScriptObjectTest();
}

// test/ has no `map` macro (asm/macros/map.inc), so these spell applymovementat out
TEST("Script object events: applymovementat on an object that isn't spawned writes nothing")
{
    SetUpScriptObjectTest(FALSE);

    RUN_OVERWORLD_SCRIPT(
        .byte SCR_OP_APPLYMOVEMENTAT; .2byte LOCALID_UNSPAWNED; .4byte Common_Movement_FaceDown; .byte 0, 0;
    );

    CleanUpScriptObjectTest();
}

TEST("Script object events: applymovementat leaves the same local ID on another map alone")
{
    u8 npc = SetUpScriptObjectTest(TRUE);
    EXPECT_NE(npc, OBJECT_EVENTS_COUNT);
    gObjectEvents[npc].directionOverwrite = DIR_NORTH;
    EXPECT_NE(gObjectEvents[npc].mapNum, 0xFF);

    RUN_OVERWORLD_SCRIPT(
        .byte SCR_OP_APPLYMOVEMENTAT; .2byte LOCALID_TEST_NPC; .4byte Common_Movement_FaceDown; .byte 0xFF, 0xFF;
    );

    EXPECT_EQ((enum Direction)gObjectEvents[npc].directionOverwrite, DIR_NORTH);
    CleanUpScriptObjectTest();
}

TEST("Script object events: facetogether with an object that isn't spawned turns nothing")
{
    u8 npc = SetUpScriptObjectTest(TRUE);
    EXPECT_NE(npc, OBJECT_EVENTS_COUNT);
    gObjectEvents[npc].facingDirection = DIR_SOUTH;

    RUN_OVERWORLD_SCRIPT( facetogether LOCALID_UNSPAWNED, LOCALID_TEST_NPC; );

    EXPECT_EQ((enum Direction)gObjectEvents[npc].facingDirection, DIR_SOUTH);
    CleanUpScriptObjectTest();
}

TEST("Script object events: getobjectfacingdirection gives DIR_NONE for an object that isn't spawned")
{
    SetUpScriptObjectTest(FALSE);
    VarSet(VAR_RESULT, DIR_NORTH);

    RUN_OVERWORLD_SCRIPT( getobjectfacingdirection LOCALID_UNSPAWNED, VAR_RESULT; );

    EXPECT_EQ(VarGet(VAR_RESULT), DIR_NONE);
    CleanUpScriptObjectTest();
}
