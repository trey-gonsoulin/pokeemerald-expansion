#include "global.h"
#include "event_object_movement.h"
#include "fieldmap.h"
#include "pokemon.h"
#include "script.h"
#include "sprite.h"
#include "constants/event_objects.h"
#include "test/overworld_script.h"
#include "test/test.h"

// The follower Pokémon takes one of the OBJECT_EVENTS_COUNT object slots. A map object
// that finds all of them taken evicts the follower, which comes back once one frees (#114).

static void SetUpFollowerSlotsTest(void)
{
    ResetSpriteData();
    FreeAllSpritePalettes();
    ResetObjectEvents();
    ScriptContext_Init(); // No script running, as when walking around
    ZeroPlayerPartyMons();
    RUN_OVERWORLD_SCRIPT( givemon SPECIES_PIKACHU, 5; );
}

static u8 SpawnTestNpc(u8 localId)
{
    return SpawnSpecialObjectEventParameterized(OBJ_EVENT_GFX_BOY_1, MOVEMENT_TYPE_FACE_DOWN, localId,
                                                gSaveBlock1Ptr->pos.x + MAP_OFFSET + 1 + localId % 8,
                                                gSaveBlock1Ptr->pos.y + MAP_OFFSET + 1 + localId / 8, 3);
}

// Spawns OBJECT_EVENTS_COUNT NPCs, enough to take every slot, and returns the first one's object ID
static u8 FillObjectSlotsWithTestNpcs(void)
{
    u32 i;
    u8 firstNpc = SpawnTestNpc(1);

    for (i = 2; i <= OBJECT_EVENTS_COUNT; i++)
        SpawnTestNpc(i);
    return firstNpc;
}

static void CleanUpFollowerSlotsTest(void)
{
    ResetObjectEvents();
    ZeroPlayerPartyMons();
}

TEST("Follower object slots: a map object evicts the follower when every slot is taken")
{
    u32 i;

    SetUpFollowerSlotsTest();
    UpdateFollowingPokemon();
    EXPECT(GetFollowerObject() != NULL);
    for (i = 1; i < OBJECT_EVENTS_COUNT; i++)
        EXPECT_NE(SpawnTestNpc(i), OBJECT_EVENTS_COUNT);
    EXPECT(GetFollowerObject() != NULL);

    EXPECT_NE(SpawnTestNpc(OBJECT_EVENTS_COUNT), OBJECT_EVENTS_COUNT);
    EXPECT(GetFollowerObject() == NULL);
    CleanUpFollowerSlotsTest();
}

TEST("Follower object slots: the follower keeps its slot while a script runs")
{
    u32 i;

    SetUpFollowerSlotsTest();
    UpdateFollowingPokemon();
    for (i = 1; i < OBJECT_EVENTS_COUNT; i++)
        SpawnTestNpc(i);

    LockPlayerFieldControls();
    EXPECT_EQ(SpawnTestNpc(OBJECT_EVENTS_COUNT), OBJECT_EVENTS_COUNT);
    UnlockPlayerFieldControls();
    EXPECT(GetFollowerObject() != NULL);
    CleanUpFollowerSlotsTest();
}

TEST("Follower object slots: an evicted follower comes back once a slot frees")
{
    u8 firstNpc;

    SetUpFollowerSlotsTest();
    UpdateFollowingPokemon();
    firstNpc = FillObjectSlotsWithTestNpcs();
    EXPECT(GetFollowerObject() == NULL);

    UpdateObjectEventsForCameraUpdate(0, 0);
    EXPECT(GetFollowerObject() == NULL);

    RemoveObjectEvent(&gObjectEvents[firstNpc]);
    UpdateObjectEventsForCameraUpdate(0, 0);
    EXPECT(GetFollowerObject() != NULL);
    CleanUpFollowerSlotsTest();
}

TEST("Follower object slots: a follower that found no slot on map load spawns once one frees")
{
    u8 firstNpc;

    SetUpFollowerSlotsTest();
    firstNpc = FillObjectSlotsWithTestNpcs();
    UpdateFollowingPokemon();
    EXPECT(GetFollowerObject() == NULL);

    RemoveObjectEvent(&gObjectEvents[firstNpc]);
    UpdateObjectEventsForCameraUpdate(0, 0);
    EXPECT(GetFollowerObject() != NULL);
    CleanUpFollowerSlotsTest();
}

TEST("Follower object slots: an evicted follower stays away while the field controls are locked")
{
    u8 firstNpc;

    SetUpFollowerSlotsTest();
    UpdateFollowingPokemon();
    firstNpc = FillObjectSlotsWithTestNpcs();
    RemoveObjectEvent(&gObjectEvents[firstNpc]);

    LockPlayerFieldControls();
    UpdateObjectEventsForCameraUpdate(0, 0);
    EXPECT(GetFollowerObject() == NULL);
    UnlockPlayerFieldControls();

    UpdateObjectEventsForCameraUpdate(0, 0);
    EXPECT(GetFollowerObject() != NULL);
    CleanUpFollowerSlotsTest();
}

TEST("Follower object slots: an object that left the view frees its slot before the follower is evicted")
{
    u32 i;

    SetUpFollowerSlotsTest();
    UpdateFollowingPokemon();
    // Out of view, as when the camera update spawns before it removes the objects that left
    SpawnSpecialObjectEventParameterized(OBJ_EVENT_GFX_BOY_1, MOVEMENT_TYPE_FACE_DOWN, 1,
                                         gSaveBlock1Ptr->pos.x + MAP_OFFSET + 30,
                                         gSaveBlock1Ptr->pos.y + MAP_OFFSET, 3);
    for (i = 2; i < OBJECT_EVENTS_COUNT; i++)
        SpawnTestNpc(i);

    EXPECT_NE(SpawnTestNpc(OBJECT_EVENTS_COUNT), OBJECT_EVENTS_COUNT);
    EXPECT(GetFollowerObject() != NULL);
    CleanUpFollowerSlotsTest();
}

TEST("Follower object slots: the follower doesn't come back after a map load")
{
    SetUpFollowerSlotsTest();
    UpdateFollowingPokemon();
    FillObjectSlotsWithTestNpcs();
    EXPECT(GetFollowerObject() == NULL);

    // A fresh map with no follower, such as a Fly arrival, which removes it on purpose
    ResetObjectEvents();
    UpdateObjectEventsForCameraUpdate(0, 0);
    EXPECT(GetFollowerObject() == NULL);
    CleanUpFollowerSlotsTest();
}
