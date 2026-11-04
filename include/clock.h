#ifndef GUARD_CLOCK_H
#define GUARD_CLOCK_H

// TODO: time of day and seconds in a day defines

void InitTimeBasedEvents(void);
void DoTimeBasedEvents(void);
void TryResumeTimeAfterRtcReset(void);
void FormChangeTimeUpdate();
void UpdateDailySeed(void);
void DoDailyEvents(u32 daysSince); //Should only be called outside of clock.c for debug purposes

#if TESTING
void Test_ResumeTimeFromLastBerryTreeUpdate(void);
#endif

#endif // GUARD_CLOCK_H
