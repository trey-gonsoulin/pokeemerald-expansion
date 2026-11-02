#ifndef GUARD_REMATCH_INDICATOR_H
#define GUARD_REMATCH_INDICATOR_H

enum RematchIndicator
{
    REMATCH_INDICATOR_NONE,
    REMATCH_INDICATOR_READY,
    REMATCH_INDICATOR_UNREGISTERED,
};

s32 GetRematchTableIdFromScript(const u8 *script);
enum RematchIndicator GetRematchIndicator(s32 rematchTableId);
void UpdateRematchIndicators(void);

#endif // GUARD_REMATCH_INDICATOR_H
