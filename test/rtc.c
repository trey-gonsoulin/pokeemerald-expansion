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

TEST("RTC check: a day past the month's length is invalid")
{
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

// After SiiRtcProbe resets the RTC at boot, Continue resumes the in-game clock from the save's last
// berry tree update instead of leaving the local day far below VAR_DAYS (#231).
TEST("RTC reset: the local time resumes from the last berry tree update")
{
    struct Time difference;

    gSaveBlock2Ptr->lastBerryTreeUpdate.days = 9000;
    gSaveBlock2Ptr->lastBerryTreeUpdate.hours = 13;
    gSaveBlock2Ptr->lastBerryTreeUpdate.minutes = 45;
    gSaveBlock2Ptr->lastBerryTreeUpdate.seconds = 30;
    gSaveBlock2Ptr->localTimeOffset.days = 30000;
    VarSet(VAR_DAYS, 8999);

    ResumeTimeFromLastBerryTreeUpdate();
    RtcCalcLocalTime();
    CalcTimeDifference(&difference, &gSaveBlock2Ptr->lastBerryTreeUpdate, &gLocalTime);

    EXPECT_EQ(gLocalTime.days, 9000);
    EXPECT_EQ(difference.days, 0);
    EXPECT_EQ(difference.hours, 0);
    EXPECT_LE(difference.minutes, 1);
    EXPECT_EQ(VarGet(VAR_DAYS), 9000);
}
