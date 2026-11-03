#include "global.h"
#include "battle_switch_summary.h"
#include "text.h"
#include "test/test.h"
#include "constants/party_menu.h"

TEST("Switch summary first: opens for the battle switch actions only")
{
    u32 menuType = PARTY_MENU_TYPE_IN_BATTLE, action = PARTY_ACTION_CHOOSE_MON, layout = PARTY_LAYOUT_SINGLE, flags = 0;
    bool32 expected = TRUE;

    PARAMETRIZE { }
    PARAMETRIZE { action = PARTY_ACTION_SEND_OUT; }
    PARAMETRIZE { action = PARTY_ACTION_CANT_SWITCH; }
    PARAMETRIZE { action = PARTY_ACTION_ABILITY_PREVENTS; }
    PARAMETRIZE { layout = PARTY_LAYOUT_DOUBLE; flags = BATTLE_TYPE_DOUBLE; }
    PARAMETRIZE { layout = PARTY_LAYOUT_MULTI; flags = BATTLE_TYPE_DOUBLE | BATTLE_TYPE_MULTI | BATTLE_TYPE_INGAME_PARTNER; }
    PARAMETRIZE { layout = PARTY_LAYOUT_MULTI_FULL; flags = BATTLE_TYPE_DOUBLE | BATTLE_TYPE_MULTI; }
    PARAMETRIZE { layout = PARTY_LAYOUT_MULTI_FULL_PARTNER; flags = BATTLE_TYPE_DOUBLE | BATTLE_TYPE_MULTI; expected = FALSE; }
    PARAMETRIZE { flags = BATTLE_TYPE_ARENA; expected = FALSE; }
    PARAMETRIZE { action = PARTY_ACTION_CHOOSE_FAINTED_MON; expected = FALSE; }
    PARAMETRIZE { action = PARTY_ACTION_USE_ITEM; expected = FALSE; }
    PARAMETRIZE { action = PARTY_ACTION_SEND_MON_TO_BOX; expected = FALSE; }
    PARAMETRIZE { menuType = PARTY_MENU_TYPE_FIELD; expected = FALSE; }
    PARAMETRIZE { menuType = PARTY_MENU_TYPE_CHOOSE_HALF; expected = FALSE; }

    EXPECT_EQ(ShouldOpenSummaryToSwitch(menuType, action, layout, flags), expected && B_SWITCH_SUMMARY_FIRST);
}

TEST("Switch summary first: SEND OUT fits the Info page prompt beside the A icon")
{
    // ShowUtilityPrompt right-aligns the text in 62 px and puts the 16 px A icon before it
    EXPECT_LE(GetStringWidth(FONT_NORMAL, gText_SummarySendOut, 0) + 16, 62);
}

TEST("Switch summary first: START SEND OUT fits the Skills page prompt and the move pages' strip")
{
    // ShowUtilityPrompt right-aligns it in the 64 px header prompt window; UpdateRelearnPrompt in the 88 px strip
    EXPECT_LE(GetStringWidth(FONT_SMALL, gText_SummaryStartSendOut, 0), 64);
}
