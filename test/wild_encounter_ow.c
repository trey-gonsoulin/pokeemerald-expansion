#include "global.h"
#include "event_data.h"
#include "event_object_movement.h"
#include "sprite.h"
#include "wild_encounter_ow.h"
#include "constants/event_objects.h"
#include "test/test.h"

// After a step, fishing or Sweet Scent battle the last talked-to local ID matches no
// spawned object, so DespawnOWEOnBattleStart looked at gObjectEvents[OBJECT_EVENTS_COUNT]
// (#116). Test builds fill that guard element with 0xFF, which reads as an active OWE, so
// clearing it fails the test.
TEST("OWE battle start: an unspawned last talked-to object despawns nothing")
{
    // ResetObjectEvents creates the two reflection sprites, which a runner's earlier test
    // can leave no slot for (test/sprite.c's BuildOamBuffer tests leave every slot in use).
    ResetSpriteData();
    ResetObjectEvents();
    gSpecialVar_LastTalked = 1;
    EXPECT_EQ(GetObjectEventIdByLocalId(gSpecialVar_LastTalked), OBJECT_EVENTS_COUNT);

    DespawnOWEOnBattleStart();

    EXPECT_EQ(gSpecialVar_LastTalked, 1);
    gSpecialVar_LastTalked = LOCALID_NONE;
}
