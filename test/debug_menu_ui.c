#include "global.h"
#include "constants/characters.h"
#include "debug_menu_ui.h"
#include "string_util.h"
#include "test/test.h"
#include "text.h"

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

static const u8 *GetTestName(u8 *buffer, u32 value)
{
    return sTestNames[value];
}

// The same names, the odd values' built in the buffer as a trainer flag's are
static const u8 *GetBuiltTestName(u8 *buffer, u32 value)
{
    if (value % 2 == 0 || sTestNames[value] == NULL)
        return sTestNames[value];
    StringCopy(buffer, sTestNames[value]);
    return buffer;
}

#define TEST_NAMES_MAX (ARRAY_COUNT(sTestNames) - 1)

static struct DebugNameOrder sTestOrder;

// Name order's rules, written out plainly: case and the acute accent fold, a name sorts before
// the longer names it starts, and the same name sorts by value
static u32 FoldTestChar(u32 c)
{
    if (c >= CHAR_a && c <= CHAR_z)
        return c - CHAR_a + CHAR_A;
    return (c == CHAR_e_ACUTE || c == CHAR_E_ACUTE) ? CHAR_E : c;
}

static bool32 SortsBefore(DebugNameFunc getName, u32 a, u32 b)
{
    u8 bufferA[DEBUG_NAME_BUFFER_SIZE], bufferB[DEBUG_NAME_BUFFER_SIZE];
    const u8 *nameA = getName(bufferA, a), *nameB = getName(bufferB, b);

    for (u32 i = 0; ; i++)
    {
        if (nameA[i] == EOS || nameB[i] == EOS)
            return nameA[i] != nameB[i] ? nameA[i] == EOS : a < b;
        if (FoldTestChar(nameA[i]) != FoldTestChar(nameB[i]))
            return FoldTestChar(nameA[i]) < FoldTestChar(nameB[i]);
    }
}

// Every named value in first..last is in order, once, and each sorts before the next
static void ExpectNameOrder(const struct DebugNameOrder *order, u32 first, u32 last, DebugNameFunc getName)
{
    u8 buffer[DEBUG_NAME_BUFFER_SIZE];
    u32 named = 0;

    for (u32 i = first; i <= last; i++)
        named += getName(buffer, i) != NULL;
    EXPECT_EQ(order->count, named);
    for (u32 i = 1; i < order->count; i++)
    {
        bool32 sorted = SortsBefore(getName, order->values[i - 1], order->values[i]);
        if (!sorted)
            Test_MgbaPrintf("values %d and %d at %d are out of order", order->values[i - 1], order->values[i], i);
        EXPECT(sorted);
    }
}

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

TEST("Name order sorts names built in the buffer")
{
    static const u16 sorted[] = {5, 1, 2, 8, 7, 3, 4, 0};
    Debug_FreeNameOrder(&sTestOrder);
    Debug_BuildNameOrder(&sTestOrder, 0, TEST_NAMES_MAX, GetBuiltTestName);
    EXPECT_EQ(sTestOrder.count, ARRAY_COUNT(sorted));
    for (u32 i = 0; i < ARRAY_COUNT(sorted); i++)
        EXPECT_EQ(sTestOrder.values[i], sorted[i]);
    // The order looks names up again later, through the buffer
    EXPECT_EQ(Debug_NextNameInitial(&sTestOrder, 1), 7);
    EXPECT_EQ(Debug_NextNameInitial(&sTestOrder, 7), 3);
    Debug_FreeNameOrder(&sTestOrder);
}

// Long shared prefixes, names that start others and repeated names, as the flag names have
static const u8 *const sPrefixNames[] =
{
    COMPOUND_STRING("HIDE_ROUTE_101_BOY"),
    COMPOUND_STRING("HIDE_ROUTE_10"),
    COMPOUND_STRING("hide_route_101"),
    COMPOUND_STRING("HIDDEN_ITEM_ROUTE_101"),
    COMPOUND_STRING("HIDE_ROUTE_101"),
    COMPOUND_STRING("HIDE_ROUTE_1"),
    COMPOUND_STRING("HIDE_ROUTE_101_GIRL"),
    COMPOUND_STRING("Flabébé"),
    COMPOUND_STRING("FLABEBE"),
    COMPOUND_STRING("HIDE"),
    COMPOUND_STRING("_UNDERSCORE"),
};

static const u8 *GetPrefixName(u8 *buffer, u32 value)
{
    return value % 7 == 3 ? NULL : sPrefixNames[(value * 5) % ARRAY_COUNT(sPrefixNames)];
}

TEST("Name order sorts many names that share long prefixes")
{
    Debug_FreeNameOrder(&sTestOrder);
    Debug_BuildNameOrder(&sTestOrder, 0, 199, GetPrefixName);
    ExpectNameOrder(&sTestOrder, 0, 199, GetPrefixName);
    // The same name sorts by value: 7 is hide_route_101 and 14 HIDE_ROUTE_101, the next one
    // (3 has no name)
    EXPECT_EQ(Debug_StepByName(&sTestOrder, 7, FALSE), 14);
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

static bool32 NameIs(const u8 *name, const u8 *expected)
{
    return name != NULL && StringCompare(name, expected) == 0;
}

TEST("Flag and var names: flags show the constant name without FLAG_")
{
    EXPECT(NameIs(Debug_GetFlagName(FLAG_BADGE05_GET), COMPOUND_STRING("BADGE05_GET")));
    EXPECT(NameIs(Debug_GetFlagName(FLAG_SYS_POKEDEX_GET), COMPOUND_STRING("SYS_POKEDEX_GET")));
    // A range marker that is a flag of its own still shows
    EXPECT(NameIs(Debug_GetFlagName(FLAG_SYS_TV_START), COMPOUND_STRING("SYS_TV_START")));
    EXPECT(NameIs(Debug_GetFlagName(FLAG_UNUSED_0x265), COMPOUND_STRING("UNUSED_0x265")));
}

TEST("Flag and var names: a config that names an unused flag shows instead of UNUSED")
{
    EXPECT(NameIs(Debug_GetFlagName(FLAG_UNUSED_0x264), COMPOUND_STRING("I_EXP_SHARE_FLAG")));
    // A real name still beats a config's
    EXPECT(NameIs(Debug_GetFlagName(B_FLAG_BADGE_BOOST_ATTACK), COMPOUND_STRING("BADGE01_GET")));
}

TEST("Flag and var names: the first defined real name shows where names share a flag")
{
    // FLAG_TEMP_SKIP_GABBY_INTERVIEW and others alias the temp flags after them
    EXPECT(NameIs(Debug_GetFlagName(FLAG_TEMP_1), COMPOUND_STRING("TEMP_1")));
    // The range marker FLAG_HIDDEN_ITEMS_START is defined first, but the hidden item is a real name
    EXPECT(NameIs(Debug_GetFlagName(FLAG_HIDDEN_ITEMS_START), COMPOUND_STRING("HIDDEN_ITEM_LAVARIDGE_TOWN_ICE_HEAL")));
}

TEST("Flag and var names: NULL outside the flags and for trainer flags")
{
    EXPECT(Debug_GetFlagName(0) == NULL);
    EXPECT(Debug_GetFlagName(FLAGS_COUNT) == NULL);
    EXPECT(Debug_GetFlagName(SPECIAL_FLAGS_START) == NULL);
    EXPECT(Debug_GetFlagName(TRAINER_FLAGS_START + 1) == NULL);
    EXPECT(Debug_GetFlagName(FLAGS_COUNT - 1) != NULL);
}

// The test ROM links test/battle/trainer_control.party as gTrainers, not the game's trainers:
// trainer 1 is RED and 2 is LEAF (both Rival, "{PKMN} TRAINER"), and the IDs after its 17 trainers
// are zero-filled: no party, and no EOS in the name
TEST("Flag and var names: trainer flags show the trainer's class and name")
{
    u8 name[DEBUG_NAME_BUFFER_SIZE];

    EXPECT(Debug_CopyTrainerFlagName(name, TRAINER_FLAGS_START + 1));
    EXPECT(NameIs(name, COMPOUND_STRING("{PKMN} TRAINER RED")));
    EXPECT(Debug_CopyTrainerFlagName(name, TRAINER_FLAGS_START + 2));
    EXPECT(NameIs(name, COMPOUND_STRING("{PKMN} TRAINER LEAF")));
}

TEST("Flag and var names: no trainer for TRAINER_NONE, trainers without a party, unused trainer IDs and other flags")
{
    u8 name[DEBUG_NAME_BUFFER_SIZE];

    name[0] = EOS;
    EXPECT(!Debug_CopyTrainerFlagName(name, TRAINER_FLAGS_START + TRAINER_NONE));
    EXPECT(!Debug_CopyTrainerFlagName(name, TRAINER_FLAGS_START + TRAINERS_COUNT - 1)); // zero-filled here, a real trainer in the game
    EXPECT(!Debug_CopyTrainerFlagName(name, TRAINER_FLAGS_START + TRAINERS_COUNT));
    EXPECT(!Debug_CopyTrainerFlagName(name, TRAINER_FLAGS_END));
    EXPECT(!Debug_CopyTrainerFlagName(name, TRAINER_FLAGS_END + 1));
    EXPECT(!Debug_CopyTrainerFlagName(name, TRAINER_FLAGS_START - 1));
    EXPECT(!Debug_CopyTrainerFlagName(name, FLAG_BADGE05_GET));
    EXPECT_EQ(name[0], EOS);
    // Constant names are unchanged around the trainer flags
    EXPECT(NameIs(Debug_GetFlagName(FLAG_BADGE05_GET), COMPOUND_STRING("BADGE05_GET")));
    EXPECT(Debug_GetFlagName(TRAINER_FLAGS_START + TRAINER_ROXANNE_1) == NULL);
}

TEST("Flag and var names: vars show the constant name without VAR_, NULL outside VARS_START..VARS_END")
{
    EXPECT(NameIs(Debug_GetVarName(VARS_START), COMPOUND_STRING("TEMP_0")));
    EXPECT(NameIs(Debug_GetVarName(VAR_TEMP_1), COMPOUND_STRING("TEMP_1")));
    EXPECT(NameIs(Debug_GetVarName(VAR_ICE_STEP_COUNT), COMPOUND_STRING("ICE_STEP_COUNT")));
    EXPECT(Debug_GetVarName(VARS_START - 1) == NULL);
    EXPECT(Debug_GetVarName(VARS_END + 1) == NULL);
    EXPECT(Debug_GetVarName(VAR_RESULT) == NULL);
}

TEST("Flag and var names: name order sorts them, trainer flags included")
{
    struct DebugNameOrder order = {0};

    Debug_BuildNameOrder(&order, FLAG_TEMP_1, FLAGS_COUNT - 1, Debug_GetFlagDisplayName);
    ExpectNameOrder(&order, FLAG_TEMP_1, FLAGS_COUNT - 1, Debug_GetFlagDisplayName);
    EXPECT_GT(order.count, 1000);
    EXPECT_EQ(Debug_StepByName(&order, FLAG_BADGE01_GET, FALSE), FLAG_BADGE02_GET);
    EXPECT_EQ(Debug_StepByName(&order, FLAG_BADGE02_GET, TRUE), FLAG_BADGE01_GET);
    // The test trainers 3 and 10 are both "{PKMN} TRAINER Test1", and LEAF (2) sorts before RED (1)
    EXPECT_EQ(Debug_StepByName(&order, TRAINER_FLAGS_START + 3, FALSE), TRAINER_FLAGS_START + 10);
    EXPECT_EQ(Debug_StepByName(&order, TRAINER_FLAGS_START + 2, FALSE), TRAINER_FLAGS_START + 1);
    // {PKMN} isn't a letter, so the letter jump goes from a trainer to the first A name
    EXPECT_EQ(Debug_NextNameInitial(&order, TRAINER_FLAGS_START + 1), Debug_NextNameInitial(&order, 0));
    Debug_FreeNameOrder(&order);

    Debug_BuildNameOrder(&order, VARS_START, VARS_END, Debug_GetVarDisplayName);
    ExpectNameOrder(&order, VARS_START, VARS_END, Debug_GetVarDisplayName);
    EXPECT_GT(order.count, 200);
    Debug_FreeNameOrder(&order);
}

// The label width the list fits a debug menu label to (sDebugMenuWindowTemplateMain's 16 tiles less item_X)
#define SUBMENU_LABEL_LIST_WIDTH 120

static u32 GetSubMenuArrowWidth(u32 fontId)
{
    static const u8 arrow[] = {CHAR_RIGHT_ARROW, EOS};
    return GetStringWidth(fontId, arrow, 0);
}

TEST("Submenu label: text that ends by the arrow's x keeps the menu font")
{
    static const u8 text[] = _("Set time of day…");
    u8 label[32];

    ASSUME(GetStringWidth(FONT_NORMAL, text, 0) <= DEBUG_SUBMENU_ARROW_X);
    Debug_CopySubMenuLabel(label, ARRAY_COUNT(label), text, FONT_NORMAL);
    EXPECT_EQ(StringLength(label), StringLength(text) + 4);
    EXPECT_EQ(StringCompareN(label, text, StringLength(text)), 0);
    EXPECT_EQ(GetStringWidth(FONT_NORMAL, label, 0), DEBUG_SUBMENU_ARROW_X + GetSubMenuArrowWidth(FONT_NORMAL));
}

TEST("Submenu label: text past the arrow's x drops to a narrower font and keeps the arrow in line")
{
    u8 text[24];
    u8 label[32];
    u32 length = 0;
    u32 labelWidth;

    // Text between the arrow's x and the list's width, which the list would leave in FONT_NORMAL
    while (length < ARRAY_COUNT(text) - 1)
    {
        text[length++] = CHAR_a;
        text[length] = EOS;
        if (GetStringWidth(FONT_NORMAL, text, 0) > DEBUG_SUBMENU_ARROW_X)
            break;
    }
    ASSUME(GetStringWidth(FONT_NORMAL, text, 0) > DEBUG_SUBMENU_ARROW_X);
    ASSUME(GetStringWidth(FONT_NORMAL, text, 0) <= SUBMENU_LABEL_LIST_WIDTH);
    ASSUME(GetStringWidth(FONT_NARROW, text, 0) <= DEBUG_SUBMENU_ARROW_X);

    Debug_CopySubMenuLabel(label, ARRAY_COUNT(label), text, FONT_NORMAL);
    EXPECT_EQ(label[0], EXT_CTRL_CODE_BEGIN);
    EXPECT_EQ(label[1], EXT_CTRL_CODE_FONT);
    EXPECT_EQ(label[2], FONT_NARROW);
    // The arrow starts at its x, in the menu font, and the list keeps the menu font for the label
    labelWidth = GetStringWidth(FONT_NORMAL, label, 0);
    EXPECT_EQ(labelWidth, DEBUG_SUBMENU_ARROW_X + GetSubMenuArrowWidth(FONT_NORMAL));
    EXPECT_EQ(GetFontIdToFit(label, FONT_NORMAL, 0, SUBMENU_LABEL_LIST_WIDTH), FONT_NORMAL);
}

TEST("Submenu label: text too long for the buffer is cut off before the arrow")
{
    static const u8 text[] = _("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
    u8 label[32];
    u32 length;

    ASSUME(StringLength(text) > ARRAY_COUNT(label));
    // What is left of the text still runs past the arrow's x, so the label takes its font codes too
    Debug_CopySubMenuLabel(label, ARRAY_COUNT(label), text, FONT_NORMAL);
    length = StringLength(label);
    EXPECT_EQ(length, ARRAY_COUNT(label) - 1);
    EXPECT_EQ(label[length - 1], CHAR_RIGHT_ARROW);
}
