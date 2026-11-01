#include "global.h"
#include "party_menu.h"
#include "test/test.h"

TEST("Use item from party menu: takes the items that target a Pokémon, outside the Key Items")
{
    enum Item item = ITEM_NONE;
    bool32 expected = TRUE;

    PARAMETRIZE { item = ITEM_POTION; }
    PARAMETRIZE { item = ITEM_ANTIDOTE; }
    PARAMETRIZE { item = ITEM_REVIVE; }
    PARAMETRIZE { item = ITEM_ORAN_BERRY; }
    PARAMETRIZE { item = ITEM_ADAMANT_MINT; }
    PARAMETRIZE { item = ITEM_ABILITY_CAPSULE; }
    PARAMETRIZE { item = ITEM_RARE_CANDY; }
    PARAMETRIZE { item = ITEM_HP_UP; }
    PARAMETRIZE { item = ITEM_FIRE_STONE; }
    PARAMETRIZE { item = ITEM_ETHER; }
    PARAMETRIZE { item = ITEM_TM01; }
    PARAMETRIZE { item = ITEM_REPEL; expected = FALSE; }
    PARAMETRIZE { item = ITEM_ESCAPE_ROPE; expected = FALSE; }
    PARAMETRIZE { item = ITEM_POKE_BALL; expected = FALSE; }
    PARAMETRIZE { item = ITEM_LEFTOVERS; expected = FALSE; }
    PARAMETRIZE { item = ITEM_MACH_BIKE; expected = FALSE; }
    PARAMETRIZE { item = ITEM_DNA_SPLICERS; expected = FALSE; }
    PARAMETRIZE { item = ITEM_BLACK_FLUTE; expected = FALSE; }
    PARAMETRIZE { item = ITEM_RED_FLUTE; expected = FALSE; }
    PARAMETRIZE { item = ITEM_PERSIM_BERRY; expected = FALSE; }
    PARAMETRIZE { item = ITEM_ENIGMA_BERRY_E_READER; expected = FALSE; }

    EXPECT_EQ(CanUseItemOnChosenPartyMon(item), expected);
}
