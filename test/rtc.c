#include "global.h"
#include "clock.h"
#include "event_data.h"
#include "rtc.h"
#include "test/test.h"

// RtcCheckInfo took the 24th hour and the 60th minute and second, and read sNumDaysInMonths at
// month - 1 for a month it had already found bad (#234). The values are BCD, as the chip gives them.
static u16 CheckRtc(u8 year, u8 month, u8 day, u8 hour, u8 minute, u8 second)
{
    struct SiiRtcInfo rtc = {
        .year = year,
        .month = month,
        .day = day,
        .hour = hour,
        .minute = minute,
        .second = second,
        .status = SIIRTCINFO_24HOUR,
    };
    return RtcCheckInfo(&rtc);
}

TEST("RTC check: the last hour, minute and second of a day are valid")
{
    EXPECT_EQ(CheckRtc(0x24, 0x12, 0x31, 0x23, 0x59, 0x59), 0);
    EXPECT_EQ(CheckRtc(0x24, 0x02, 0x29, 0x00, 0x00, 0x00), 0);
}

TEST("RTC check: hour 24, minute 60 and second 60 are invalid")
{
    EXPECT_EQ(CheckRtc(0x24, 0x01, 0x01, 0x24, 0x00, 0x00), RTC_ERR_INVALID_HOUR);
    EXPECT_EQ(CheckRtc(0x24, 0x01, 0x01, 0x00, 0x60, 0x00), RTC_ERR_INVALID_MINUTE);
    EXPECT_EQ(CheckRtc(0x24, 0x01, 0x01, 0x00, 0x00, 0x60), RTC_ERR_INVALID_SECOND);
}

TEST("RTC check: day 0 and a day past the month's length are invalid")
{
    EXPECT_EQ(CheckRtc(0x24, 0x03, 0x00, 0x00, 0x00, 0x00), RTC_ERR_INVALID_DAY);
    EXPECT_EQ(CheckRtc(0x23, 0x02, 0x29, 0x00, 0x00, 0x00), RTC_ERR_INVALID_DAY);
    EXPECT_EQ(CheckRtc(0x24, 0x04, 0x31, 0x00, 0x00, 0x00), RTC_ERR_INVALID_DAY);
}

TEST("RTC check: a bad month doesn't check the day against a month length")
{
    // Month 0 read sNumDaysInMonths[-1], 0x13 its [12] and a non-BCD 0x1A its [254]
    EXPECT_EQ(CheckRtc(0x24, 0x00, 0x01, 0x00, 0x00, 0x00), RTC_ERR_INVALID_MONTH);
    EXPECT_EQ(CheckRtc(0x24, 0x13, 0x01, 0x00, 0x00, 0x00), RTC_ERR_INVALID_MONTH);
    EXPECT_EQ(CheckRtc(0x24, 0x1A, 0x01, 0x00, 0x00, 0x00), RTC_ERR_INVALID_MONTH);
    EXPECT_EQ(CheckRtc(0x24, 0x1A, 0x1A, 0x00, 0x00, 0x00), RTC_ERR_INVALID_MONTH | RTC_ERR_INVALID_DAY);
}

TEST("RTC check: a bad month counts no days past December")
{
    // A non-BCD month reads as 0xFF, which summed 254 entries of sNumDaysInMonths (#237)
    u16 dayCount = ConvertDateToDayCount(0, 13, 1);
    EXPECT_EQ(dayCount, 367);
    EXPECT_EQ(ConvertDateToDayCount(0, 14, 1), dayCount);
    EXPECT_EQ(ConvertDateToDayCount(0, 0xFF, 1), dayCount);
}

// A failed SiiRtcProbe (RTC_INIT_ERROR) read the chip anyway and showed no message (#237)
TEST("RTC error: a failed probe reads the dummy date and keeps the clock")
{
    struct SiiRtcInfo rtc;
    struct Time offset;
    bool32 hasError;
    u16 status = RtcGetErrorStatus();

    Test_RtcSetErrorStatus(RTC_INIT_ERROR);
    FlagSet(FLAG_SYS_CLOCK_SET);
    gSaveBlock2Ptr->localTimeOffset.days = -100;
    offset = gSaveBlock2Ptr->localTimeOffset;

    hasError = RtcHasError();
    RtcGetInfo(&rtc);
    TryResumeTimeAfterRtcReset();
    Test_RtcSetErrorStatus(status);

    EXPECT(hasError);
    EXPECT_EQ(rtc.year, 0);
    EXPECT_EQ(rtc.month, MONTH_JAN);
    EXPECT_EQ(rtc.day, 1);
    EXPECT_EQ(gSaveBlock2Ptr->localTimeOffset.days, offset.days);
    EXPECT_EQ(gSaveBlock2Ptr->localTimeOffset.hours, offset.hours);
    EXPECT_EQ(gSaveBlock2Ptr->localTimeOffset.minutes, offset.minutes);
}

// TryDecrementTimeOfDay stepped back into a time of day the generation skips, which
// GenConfigTimeOfDay moved forward again, so Left on the Pokédex area screen stuck (#233)
TEST("RTC time of day: decrementing skips the times of day the generation doesn't have")
{
    EXPECT_EQ(Test_TryDecrementTimeOfDay(TIME_DAY, GEN_3), TIME_NIGHT);
    EXPECT_EQ(Test_TryDecrementTimeOfDay(TIME_NIGHT, GEN_3), TIME_DAY);
    EXPECT_EQ(Test_TryDecrementTimeOfDay(TIME_NIGHT, GEN_4), TIME_DAY);
    EXPECT_EQ(Test_TryDecrementTimeOfDay(TIME_DAY, GEN_4), TIME_MORNING);
    EXPECT_EQ(Test_TryDecrementTimeOfDay(TIME_MORNING, GEN_4), TIME_NIGHT);
    EXPECT_EQ(Test_TryDecrementTimeOfDay(TIME_NIGHT, GEN_2), TIME_DAY);
    EXPECT_EQ(Test_TryDecrementTimeOfDay(TIME_NIGHT, GEN_LATEST), TIME_EVENING);
    EXPECT_EQ(Test_TryDecrementTimeOfDay(TIME_MORNING, GEN_LATEST), TIME_NIGHT);
}

// After SiiRtcProbe resets the RTC, Continue resumes the in-game clock from the save's last berry
// tree update instead of leaving the local time far behind it (#231).
static void ExpectLocalTimeAtLastBerryTreeUpdate(void)
{
    struct Time difference;

    RtcCalcLocalTime();
    CalcTimeDifference(&difference, &gSaveBlock2Ptr->lastBerryTreeUpdate, &gLocalTime);
    EXPECT_EQ(difference.days, 0);
    EXPECT_EQ(difference.hours, 0);
    EXPECT_LE(difference.minutes, 1);
}

static void SetLastBerryTreeUpdate(s16 days, s8 hours, s8 minutes, s8 seconds)
{
    gSaveBlock2Ptr->lastBerryTreeUpdate.days = days;
    gSaveBlock2Ptr->lastBerryTreeUpdate.hours = hours;
    gSaveBlock2Ptr->lastBerryTreeUpdate.minutes = minutes;
    gSaveBlock2Ptr->lastBerryTreeUpdate.seconds = seconds;
}

TEST("RTC reset: the local time resumes from the last berry tree update")
{
    SetLastBerryTreeUpdate(9000, 23, 59, 50);
    gSaveBlock2Ptr->localTimeOffset.days = 30000;
    // UpdatePerDay already ran for day 9001, less than a minute after the berry update
    VarSet(VAR_DAYS, 9001);

    Test_ResumeTimeFromLastBerryTreeUpdate();

    ExpectLocalTimeAtLastBerryTreeUpdate();
    EXPECT_EQ(VarGet(VAR_DAYS), 9001);
}

TEST("RTC reset: Continue resumes a local time whose day went negative")
{
    SetLastBerryTreeUpdate(9000, 13, 45, 30);
    FlagSet(FLAG_SYS_CLOCK_SET);
    RtcCalcLocalTimeOffset(-100, 0, 0, 0);

    TryResumeTimeAfterRtcReset();

    ExpectLocalTimeAtLastBerryTreeUpdate();
}
