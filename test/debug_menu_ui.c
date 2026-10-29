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

static struct DebugNameOrder sTestOrder;

static const struct DebugNameOrder *BuildTestOrder(u32 min, u32 max)
{
    Debug_FreeNameOrder(&sTestOrder);
    Debug_BuildNameOrder(&sTestOrder, min, max, GetTestName);
    return &sTestOrder;
}

TEST("Name order sorts the named values A-Z ignoring case and accents")
{
    static const u16 sorted[] = {5, 1, 2, 8, 7, 3, 4, 0};
    const struct DebugNameOrder *order = BuildTestOrder(0, TEST_NAMES_MAX);
    EXPECT_EQ(order->count, ARRAY_COUNT(sorted));
    for (u32 i = 0; i < ARRAY_COUNT(sorted); i++)
        EXPECT_EQ(order->values[i], sorted[i]);
    Debug_FreeNameOrder(&sTestOrder);
}

TEST("Name order sorts an odd number of named values")
{
    // 7 names leave a short last run in every merge pass
    static const u16 sorted[] = {5, 1, 2, 7, 3, 4, 0};
    const struct DebugNameOrder *order = BuildTestOrder(0, 7);
    EXPECT_EQ(order->count, ARRAY_COUNT(sorted));
    for (u32 i = 0; i < ARRAY_COUNT(sorted); i++)
        EXPECT_EQ(order->values[i], sorted[i]);
    Debug_FreeNameOrder(&sTestOrder);
}

TEST("Name order steps A-Z, and wraps at the end")
{
    static const u8 steps[] = {5, 1, 2, 8, 7, 3, 4, 0, 5};
    const struct DebugNameOrder *order = BuildTestOrder(0, TEST_NAMES_MAX);
    for (u32 i = 0; i < ARRAY_COUNT(steps) - 1; i++)
        EXPECT_EQ(Debug_StepByName(order, steps[i], FALSE), steps[i + 1]);
    Debug_FreeNameOrder(&sTestOrder);
}

TEST("Name order steps back Z-A, and wraps at the start")
{
    static const u8 steps[] = {0, 4, 3, 7, 8, 2, 1, 5, 0};
    const struct DebugNameOrder *order = BuildTestOrder(0, TEST_NAMES_MAX);
    for (u32 i = 0; i < ARRAY_COUNT(steps) - 1; i++)
        EXPECT_EQ(Debug_StepByName(order, steps[i], TRUE), steps[i + 1]);
    Debug_FreeNameOrder(&sTestOrder);
}

TEST("Name order from a value without a name goes to the first or last name")
{
    const struct DebugNameOrder *order = BuildTestOrder(0, TEST_NAMES_MAX);
    EXPECT_EQ(Debug_StepByName(order, 6, FALSE), 5);
    EXPECT_EQ(Debug_StepByName(order, 6, TRUE), 0);
    Debug_FreeNameOrder(&sTestOrder);
}

TEST("Name order stays within min and max")
{
    const struct DebugNameOrder *order = BuildTestOrder(1, 4);
    EXPECT_EQ(Debug_StepByName(order, 4, FALSE), 1);
    EXPECT_EQ(Debug_StepByName(order, 1, TRUE), 4);
    EXPECT_EQ(Debug_NextNameInitial(order, 3), 1);
    Debug_FreeNameOrder(&sTestOrder);
}

TEST("Name order rebuilds only for another range")
{
    Debug_FreeNameOrder(&sTestOrder);
    Debug_BuildNameOrder(&sTestOrder, 1, 4, GetTestName);
    const u16 *values = sTestOrder.values;
    Debug_BuildNameOrder(&sTestOrder, 1, 4, GetTestName);
    EXPECT(sTestOrder.values == values);
    Debug_BuildNameOrder(&sTestOrder, 0, TEST_NAMES_MAX, GetTestName);
    EXPECT_EQ(sTestOrder.count, 8);
    Debug_FreeNameOrder(&sTestOrder);
    EXPECT(sTestOrder.values == NULL);
}

TEST("Name order letter jump cycles the initials that names start with")
{
    // From the name without a letter, A, E, F, Z and back to A
    static const u8 steps[] = {5, 1, 7, 3, 0, 1};
    const struct DebugNameOrder *order = BuildTestOrder(0, TEST_NAMES_MAX);
    for (u32 i = 0; i < ARRAY_COUNT(steps) - 1; i++)
        EXPECT_EQ(Debug_NextNameInitial(order, steps[i]), steps[i + 1]);
    EXPECT_EQ(Debug_NextNameInitial(order, 2), 7);
    EXPECT_EQ(Debug_NextNameInitial(order, 6), 1);
    Debug_FreeNameOrder(&sTestOrder);
}

TEST("Name order returns the value when nothing else has a name")
{
    const struct DebugNameOrder *order = BuildTestOrder(6, 6);
    EXPECT_EQ(order->count, 0);
    EXPECT_EQ(Debug_StepByName(order, 6, FALSE), 6);
    order = BuildTestOrder(5, 6);
    EXPECT_EQ(Debug_NextNameInitial(order, 5), 5);
    Debug_FreeNameOrder(&sTestOrder);
}
