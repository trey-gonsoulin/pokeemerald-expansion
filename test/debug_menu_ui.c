#include "global.h"
#include "debug_menu_ui.h"
#include "test/test.h"

// In name order: "10,000 Volt" (5), "abra" (1), "Abra" (2), "Abras" (8), "Ekans" (7),
// "Flabébé" (3), "Flabebe" (4), "Zubat" (0). Value 6 has no name.
static const u8 *const sTestNames[] =
{
    COMPOUND_STRING("Zubat"),
    COMPOUND_STRING("abra"),
    COMPOUND_STRING("Abra"),
    COMPOUND_STRING("Flabébé"),
    COMPOUND_STRING("Flabebe"),
    COMPOUND_STRING("10,000 Volt"),
    NULL,
    COMPOUND_STRING("Ekans"),
    COMPOUND_STRING("Abras"),
};

static const u8 *GetTestName(u32 value)
{
    return sTestNames[value];
}

#define TEST_NAMES_MAX (ARRAY_COUNT(sTestNames) - 1)

TEST("Name order steps A-Z ignoring case and accents, and wraps at the end")
{
    static const u8 order[] = {5, 1, 2, 8, 7, 3, 4, 0, 5};
    for (u32 i = 0; i < ARRAY_COUNT(order) - 1; i++)
        EXPECT_EQ(Debug_StepByName(order[i], 0, TEST_NAMES_MAX, GetTestName, FALSE), order[i + 1]);
}

TEST("Name order steps back Z-A, and wraps at the start")
{
    static const u8 order[] = {0, 4, 3, 7, 8, 2, 1, 5, 0};
    for (u32 i = 0; i < ARRAY_COUNT(order) - 1; i++)
        EXPECT_EQ(Debug_StepByName(order[i], 0, TEST_NAMES_MAX, GetTestName, TRUE), order[i + 1]);
}

TEST("Name order from a value without a name goes to the first or last name")
{
    EXPECT_EQ(Debug_StepByName(6, 0, TEST_NAMES_MAX, GetTestName, FALSE), 5);
    EXPECT_EQ(Debug_StepByName(6, 0, TEST_NAMES_MAX, GetTestName, TRUE), 0);
}

TEST("Name order stays within min and max")
{
    EXPECT_EQ(Debug_StepByName(4, 1, 4, GetTestName, FALSE), 1);
    EXPECT_EQ(Debug_StepByName(1, 1, 4, GetTestName, TRUE), 4);
    EXPECT_EQ(Debug_NextNameInitial(3, 1, 4, GetTestName), 1);
}

TEST("Name order letter jump cycles the initials that names start with")
{
    // From the name without a letter, A, E, F, Z and back to A
    static const u8 order[] = {5, 1, 7, 3, 0, 1};
    for (u32 i = 0; i < ARRAY_COUNT(order) - 1; i++)
        EXPECT_EQ(Debug_NextNameInitial(order[i], 0, TEST_NAMES_MAX, GetTestName), order[i + 1]);
    EXPECT_EQ(Debug_NextNameInitial(2, 0, TEST_NAMES_MAX, GetTestName), 7);
    EXPECT_EQ(Debug_NextNameInitial(6, 0, TEST_NAMES_MAX, GetTestName), 1);
}

TEST("Name order returns the value when nothing else has a name")
{
    EXPECT_EQ(Debug_StepByName(6, 6, 6, GetTestName, FALSE), 6);
    EXPECT_EQ(Debug_NextNameInitial(5, 5, 6, GetTestName), 5);
}
