#ifndef GUARD_BATTLE_SWITCH_SUMMARY_H
#define GUARD_BATTLE_SWITCH_SUMMARY_H

#include "party_menu.h"

extern const u8 gText_SummarySendOut[];

bool32 ShouldOpenSummaryToSwitch(enum PartyMenuType menuType, u32 action, enum PartyMenuLayout layout, u32 battleTypeFlags);
u32 GetSwitchSummaryPage(void);
void RememberSwitchSummaryPage(u32 page);

#endif // GUARD_BATTLE_SWITCH_SUMMARY_H
