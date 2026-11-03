#include "global.h"
#include "battle.h"
#include "battle_switch_summary.h"

// Emerald Plus (#200, B_SWITCH_SUMMARY_FIRST): A on a Pokémon in the battle party menu opens its summary
// (SUMMARY_MODE_BATTLE_SWITCH) instead of the SHIFT / SUMMARY / CANCEL window. It opens on the Info page, where A
// sends (#213). Start, on any page, closes it with gSummarySendOutRequested set too, and
// CB2_ReturnToPartyMenuFromSummaryScreen sends that Pokémon out.

const u8 gText_SummarySendOut[] = _("SEND OUT");
const u8 gText_SummaryStartSendOut[] = _("{START_BUTTON} SEND OUT"); // FONT_SMALL, as the summary's START RELEARN

bool32 ShouldOpenSummaryToSwitch(enum PartyMenuType menuType, u32 action, enum PartyMenuLayout layout, u32 battleTypeFlags)
{
    if (!B_SWITCH_SUMMARY_FIRST || menuType != PARTY_MENU_TYPE_IN_BATTLE)
        return FALSE;

    // Nothing can be sent from these, so they keep the SUMMARY / CANCEL window
    if ((battleTypeFlags & BATTLE_TYPE_ARENA) || layout == PARTY_LAYOUT_MULTI_FULL_PARTNER)
        return FALSE;

    switch (action)
    {
    case PARTY_ACTION_CHOOSE_MON:
    case PARTY_ACTION_SEND_OUT:
    case PARTY_ACTION_CANT_SWITCH:
    case PARTY_ACTION_ABILITY_PREVENTS:
        return TRUE;
    default:
        return FALSE;
    }
}
