#ifndef GUARD_BATTLE_SWITCH_SUMMARY_H
#define GUARD_BATTLE_SWITCH_SUMMARY_H

#include "party_menu.h"

extern const u8 gText_SummarySendOut[];
extern const u8 gText_SummaryStartSendOut[];

bool32 ShouldOpenSummaryToSwitch(enum PartyMenuType menuType, u32 action, enum PartyMenuLayout layout, u32 battleTypeFlags);

#endif // GUARD_BATTLE_SWITCH_SUMMARY_H
