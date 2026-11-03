#include "global.h"
#include "event_data.h"
#include "event_object_movement.h"
#include "wild_encounter_ow.h"
#include "test/test.h"

// After a step, fishing or Sweet Scent battle the last talked-to local ID matches no
// spawned object, so DespawnOWEOnBattleStart looked at gObjectEvents[OBJECT_EVENTS_COUNT]
// (#116). Test builds fill that guard element with 0xFF, which reads as an active OWE, so
// clearing it fails the test.
TEST("OWE battle start: an unspawned last talked-to object despawns nothing")
{
    ResetObjectEvents();
    gSpecialVar_LastTalked = 1;
    EXPECT_EQ(GetObjectEventIdByLocalId(gSpecialVar_LastTalked), OBJECT_EVENTS_COUNT);

    DespawnOWEOnBattleStart();

    EXPECT_EQ(gSpecialVar_LastTalked, 1);
}
