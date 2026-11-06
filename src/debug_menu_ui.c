// The fork's overworld debug-menu engine, used by src/debug.c. See include/debug_menu_ui.h.
// A release build (DEBUG_OVERWORLD_MENU off) keeps only the numeric input and its digit rendering,
// because the native party-menu debug entries (Set Friendship, Set Pokerus) run the selection engine.
#include "global.h"
#include "data.h"
#include "debug_menu_ui.h"
#include "list_menu.h"
#include "main.h"
#include "malloc.h"
#include "menu.h"
#include "string_util.h"
#include "task.h"
#include "text.h"
#include "window.h"


#define tInput      data[DEBUG_DATA_INPUT]
#define tDigit      data[DEBUG_DATA_DIGIT]
#define tInputStart data[DEBUG_DATA_INPUT_START]

const u8 *const gText_DigitIndicator[] =
{
    COMPOUND_STRING("{LEFT_ARROW}+1{RIGHT_ARROW}        "),
    COMPOUND_STRING("{LEFT_ARROW}+10{RIGHT_ARROW}       "),
    COMPOUND_STRING("{LEFT_ARROW}+100{RIGHT_ARROW}      "),
    COMPOUND_STRING("{LEFT_ARROW}+1000{RIGHT_ARROW}     "),
    COMPOUND_STRING("{LEFT_ARROW}+10000{RIGHT_ARROW}    "),
    COMPOUND_STRING("{LEFT_ARROW}+100000{RIGHT_ARROW}   "),
    COMPOUND_STRING("{LEFT_ARROW}+1000000{RIGHT_ARROW}  "),
    COMPOUND_STRING("{LEFT_ARROW}+10000000{RIGHT_ARROW} "),
};

// Hex inputs fit in a u16, so they have at most four digits
const u8 *const gText_HexDigitIndicator[] =
{
    COMPOUND_STRING("{LEFT_ARROW}+0x1{RIGHT_ARROW}      "),
    COMPOUND_STRING("{LEFT_ARROW}+0x10{RIGHT_ARROW}     "),
    COMPOUND_STRING("{LEFT_ARROW}+0x100{RIGHT_ARROW}    "),
    COMPOUND_STRING("{LEFT_ARROW}+0x1000{RIGHT_ARROW}   "),
};

static const s32 sPowersOfTen[] =
{
             1,
            10,
           100,
          1000,
         10000,
        100000,
       1000000,
      10000000,
     100000000,
    1000000000,
};

// Which way the last Debug_HandleInput_Numeric moved, for steps that skip invalid values
static EWRAM_DATA bool8 sNumericInputMovedDown = FALSE;

// *******************************
// Numeric input

// Digits shown for a numeric input up to max. Clamped to 1..ARRAY_COUNT(gText_DigitIndicator),
// so tDigit always indexes gText_DigitIndicator and sPowersOfTen (tv.c's CountDigits gives 0 for 0)
u32 Debug_CountDigits(u32 max)
{
    u32 digits = 1;
    while (digits < ARRAY_COUNT(gText_DigitIndicator) && max >= (u32)sPowersOfTen[digits])
        digits++;
    return digits;
}

// Hex digits shown for a numeric input up to max, clamped to 1..ARRAY_COUNT(gText_HexDigitIndicator)
u32 Debug_CountHexDigits(u32 max)
{
    u32 digits = 1;
    while (digits < ARRAY_COUNT(gText_HexDigitIndicator) && (max >> (4 * digits)) != 0)
        digits++;
    return digits;
}

// Starts a numeric input at input, with the ones digit highlighted
void Debug_StartNumericInput(u8 taskId, u32 input)
{
    gTasks[taskId].tInput = input;
    gTasks[taskId].tInputStart = input;
    gTasks[taskId].tDigit = 0;
    sNumericInputMovedDown = FALSE;
}

// Up/Down turn only the highlighted digit, like a combination lock: 9 wraps to 0 and back with
// no carry into the other digits, and they repeat while held. A result past either end stops
// on min/max. L/R jump to min/max and Select goes back to the value the step started from.
// Left/Right move the highlight the way they point (tDigit counts from the ones place).
// With hex, the digits are base 16 (F wraps to 0), for inputs shown with Debug_InputToHexString.
void Debug_HandleInput_Numeric(u8 taskId, u32 min, u32 max, u32 digits, bool32 hex)
{
    u32 input = DEBUG_TASK_INPUT(taskId);

    sNumericInputMovedDown = FALSE;
    if (JOY_REPEAT(DPAD_UP | DPAD_DOWN))
    {
        u32 oldInput = input;
        u32 base = hex ? 16 : 10;
        u32 place = hex ? 1u << (4 * gTasks[taskId].tDigit) : (u32)sPowersOfTen[gTasks[taskId].tDigit];
        u32 digit = (input / place) % base;
        input -= digit * place;
        digit = (digit + (JOY_REPEAT(DPAD_UP) ? 1 : base - 1)) % base;
        input += digit * place;
        if (input > max)
            input = max;
        else if (input < min)
            input = min;
        // A digit wrap can move the value against the button (Up on a 9 goes down)
        sNumericInputMovedDown = input < oldInput;
    }
    else if (JOY_NEW(L_BUTTON))
    {
        input = min;
    }
    else if (JOY_NEW(R_BUTTON))
    {
        input = max;
        sNumericInputMovedDown = TRUE; // max can be invalid, so search down from there
    }
    else if (JOY_NEW(SELECT_BUTTON))
    {
        input = (u16)gTasks[taskId].tInputStart;
    }
    gTasks[taskId].tInput = input;

    if (JOY_NEW(DPAD_LEFT))
    {
        if (gTasks[taskId].tDigit < digits - 1)
            gTasks[taskId].tDigit += 1;
    }
    if (JOY_NEW(DPAD_RIGHT))
    {
        if (gTasks[taskId].tDigit > 0)
            gTasks[taskId].tDigit -= 1;
    }
}

// For steps that skip invalid values: which way Debug_HandleInput_Numeric just moved.
// R jumps to max, so it searches downwards from there.
bool32 Debug_NumericInputMovedDown(void)
{
    return sNumericInputMovedDown;
}

// Copies number to dest with the digit that Up/Down changes highlighted
static void Debug_HighlightInputDigit(u8 *dest, u8 taskId, const u8 *number)
{
    static const u8 sColor_Digit[] = _("{COLOR BLUE}{SHADOW LIGHT_BLUE}");
    static const u8 sColor_Default[] = _("{COLOR DARK_GRAY}{SHADOW LIGHT_GRAY}");
    u32 length, position;

    length = StringLength(number);
    if (gTasks[taskId].tDigit >= length)
    {
        StringCopy(dest, number);
        return;
    }
    position = length - 1 - gTasks[taskId].tDigit;
    dest = StringCopyN(dest, number, position);
    dest = StringCopy(dest, sColor_Digit);
    *dest++ = number[position];
    dest = StringCopy(dest, sColor_Default);
    StringCopy(dest, &number[position + 1]);
}

// Prints the numeric input with the digit that Up/Down changes highlighted
void Debug_InputToDecimalString(u8 *dest, u8 taskId, u32 digits)
{
    u8 number[12];
    ConvertIntToDecimalStringN(number, DEBUG_TASK_INPUT(taskId), STR_CONV_MODE_LEADING_ZEROS, digits);
    Debug_HighlightInputDigit(dest, taskId, number);
}

// Same in hex, without the 0x prefix, for inputs that Debug_HandleInput_Numeric dials in hex
void Debug_InputToHexString(u8 *dest, u8 taskId, u32 digits)
{
    u8 number[12];
    ConvertIntToHexStringN(number, DEBUG_TASK_INPUT(taskId), STR_CONV_MODE_LEADING_ZEROS, digits);
    Debug_HighlightInputDigit(dest, taskId, number);
}

// *******************************
// Name order
// A sorted index, built once per range: scanning min..max on every press took about 4 frames
// for the ~1,570 species, so holding Up/Down lagged. Sorting them takes a few frames once.

// Ranges no longer than this are sorted by insertion
#define DEBUG_NAME_SORT_RUN 8

// Name order ignores case and the acute accent, so "Flabébé" sorts with the other Fs
static u32 Debug_FoldNameChar(u32 c)
{
    if (c >= CHAR_a && c <= CHAR_z)
        return c - CHAR_a + CHAR_A;
    if (c == CHAR_e_ACUTE || c == CHAR_E_ACUTE)
        return CHAR_E;
    return c;
}

// A character's place in name order, which fits in a u8: the end of a name (EOS) comes first, so
// a name sorts before the longer names it starts, then the folded characters
static u32 Debug_NameCharKey(u32 c)
{
    return c == EOS ? 0 : Debug_FoldNameChar(c) + 1;
}

// The letter a name starts with, 0 for A to 25 for Z, or -1 when it doesn't start with a letter
static s32 Debug_NameInitial(const u8 *name)
{
    u32 c = Debug_FoldNameChar(name[0]);
    return (c >= CHAR_A && c <= CHAR_Z) ? (s32)(c - CHAR_A) : -1;
}

// The values being sorted, with their names alongside
struct DebugNameSort
{
    u16 *values;
    const u8 **names; // names[i] is values[i]'s
    u8 keys[256]; // Debug_NameCharKey of each character, looked up rather than worked out
};

static void Debug_SwapSortedNames(struct DebugNameSort *sort, u32 i, u32 j)
{
    u16 value;
    const u8 *name;

    SWAP(sort->values[i], sort->values[j], value);
    SWAP(sort->names[i], sort->names[j], name);
}

// Whether position i sorts after name (value's), when both names start with the same depth
// characters. The same name sorts by value.
static bool32 Debug_SortsAfter(const struct DebugNameSort *sort, u32 i, const u8 *name, u32 value, u32 depth)
{
    const u8 *other = sort->names[i];

    for (;; depth++)
    {
        u32 otherKey = sort->keys[other[depth]], key = sort->keys[name[depth]];
        if (otherKey != key)
            return otherKey > key;
        if (key == 0)
            return sort->values[i] > value;
    }
}

// Sorts the count positions from start, whose names all start with the same depth characters,
// by insertion
static void Debug_InsertionSortByName(struct DebugNameSort *sort, u32 start, u32 count, u32 depth)
{
    for (u32 i = start + 1; i < start + count; i++)
    {
        u32 value = sort->values[i], j = i;
        const u8 *name = sort->names[i];

        for (; j > start && Debug_SortsAfter(sort, j - 1, name, value, depth); j--)
        {
            sort->values[j] = sort->values[j - 1];
            sort->names[j] = sort->names[j - 1];
        }
        sort->values[j] = value;
        sort->names[j] = name;
    }
}

// Sorts like Debug_InsertionSortByName, by multikey quicksort (Bentley and Sedgewick): it splits
// the names by the character at depth, then sorts the ones that share it from the next character
// on. So it reads the long prefixes that flag names share (HIDE_, HIDDEN_ITEM_) once per split,
// where a merge sort of whole names read them on every comparison: the 1,527 flag names took
// about 42 frames that way. It recurses into the two smaller parts and goes on with the largest,
// which keeps the recursion within log2(count) levels.
static void Debug_SortByName(struct DebugNameSort *sort, u32 start, u32 count, u32 depth)
{
    while (count > DEBUG_NAME_SORT_RUN)
    {
        // The median of three characters, so that names already in order split in the middle
        u32 a = sort->keys[sort->names[start][depth]];
        u32 b = sort->keys[sort->names[start + count / 2][depth]];
        u32 c = sort->keys[sort->names[start + count - 1][depth]];
        u32 pivot = max(min(a, b), min(max(a, b), c));
        u32 below = start, i = start, above = start + count;

        // [start, below) sort before pivot, [below, i) have it and [above, start + count) sort after it
        while (i < above)
        {
            u32 key = sort->keys[sort->names[i][depth]];
            if (key < pivot)
                Debug_SwapSortedNames(sort, below++, i++);
            else if (key > pivot)
                Debug_SwapSortedNames(sort, i, --above);
            else
                i++;
        }

        u32 starts[3] = {start, below, above};
        u32 counts[3] = {below - start, above - below, start + count - above};
        u32 depths[3] = {depth, depth + 1, depth};
        // Names that all end at depth are the same name, which sort by value
        if (pivot == 0)
        {
            Debug_InsertionSortByName(sort, below, above - below, depth);
            counts[1] = 0;
        }
        u32 largest = (counts[0] >= counts[1] && counts[0] >= counts[2]) ? 0 : (counts[1] >= counts[2] ? 1 : 2);
        for (u32 part = 0; part < ARRAY_COUNT(counts); part++)
        {
            if (part != largest)
                Debug_SortByName(sort, starts[part], counts[part], depths[part]);
        }
        start = starts[largest];
        count = counts[largest];
        depth = depths[largest];
    }
    Debug_InsertionSortByName(sort, start, count, depth);
}

// Sorts the values in first..last that have a name (getName returns NULL for the ones name order
// leaves out, such as disabled species) into order->values. Does nothing when order already
// holds that range; Debug_FreeNameOrder frees it. Alloc never returns NULL (it stops the game).
void Debug_BuildNameOrder(struct DebugNameOrder *order, u32 first, u32 last, DebugNameFunc getName)
{
    u32 count = 0, builtSize = 0;
    u8 buffer[DEBUG_NAME_BUFFER_SIZE];
    struct DebugNameSort sort;

    if (order->values != NULL && order->getName == getName && order->first == first && order->last == last)
        return;
    Debug_FreeNameOrder(order);
    order->getName = getName;
    order->first = first;
    order->last = last;
    order->values = sort.values = Alloc((last - first + 1) * sizeof(u16));
    // The names, looked up once, only while sorting. A name built in buffer (a trainer flag's)
    // is marked with buffer's address at first, and copied once the space they take is known.
    sort.names = Alloc((last - first + 1) * sizeof(*sort.names));
    for (u32 i = first; i <= last; i++)
    {
        const u8 *name = getName(buffer, i);
        if (name == NULL)
            continue;
        if (name == buffer)
            builtSize += StringLength(buffer) + 1;
        sort.names[count] = name;
        sort.values[count++] = i;
    }
    u8 *builtNames = builtSize != 0 ? Alloc(builtSize) : NULL;
    u8 *builtEnd = builtNames;
    for (u32 i = 0; i < count; i++)
    {
        if (sort.names[i] == buffer)
        {
            sort.names[i] = builtEnd;
            builtEnd = StringCopy(builtEnd, getName(buffer, sort.values[i])) + 1;
        }
    }
    for (u32 c = 0; c < ARRAY_COUNT(sort.keys); c++)
        sort.keys[c] = Debug_NameCharKey(c);
    Debug_SortByName(&sort, 0, count, 0);
    order->count = count;
    Free(sort.names);
    TRY_FREE_AND_SET_NULL(builtNames);
}

void Debug_FreeNameOrder(struct DebugNameOrder *order)
{
    TRY_FREE_AND_SET_NULL(order->values);
    order->count = 0;
}

// value's position in order, or -1 when value has no name
static s32 Debug_FindInNameOrder(const struct DebugNameOrder *order, u32 value)
{
    for (u32 i = 0; i < order->count; i++)
    {
        if (order->values[i] == value)
            return i;
    }
    return -1;
}

// The position of the first name in order that starts with letter (0 for A) or a later one, or
// order->count when none does. Folded first characters only grow along the order, so it
// looks up about log2(count) names, each of which may build a trainer flag's.
static u32 Debug_FindNameInitial(const struct DebugNameOrder *order, u32 letter)
{
    u8 buffer[DEBUG_NAME_BUFFER_SIZE];
    u32 low = 0, high = order->count;

    while (low < high)
    {
        u32 mid = (low + high) / 2;
        if (Debug_NameCharKey(order->getName(buffer, order->values[mid])[0]) < CHAR_A + letter + 1)
            low = mid + 1;
        else
            high = mid;
    }
    // Past Z come the names that start with something other than a letter
    if (low < order->count && Debug_NameInitial(order->getName(buffer, order->values[low])) < 0)
        return order->count;
    return low;
}

// The value after value in name order (with previous, the one before it). Past the last name it
// wraps to the first. From a value without a name it goes to the first (or last) name.
// Returns value when the order is empty.
u32 Debug_StepByName(const struct DebugNameOrder *order, u32 value, bool32 previous)
{
    s32 pos = Debug_FindInNameOrder(order, value);

    if (order->count == 0)
        return value;
    if (previous)
        pos = (pos <= 0 ? order->count : pos) - 1;
    else
        pos = (pos < 0 || pos == order->count - 1) ? 0 : pos + 1;
    return order->values[pos];
}

// The first value in name order whose name starts with a later letter than value's name, so
// repeated calls cycle A to Z, skipping letters no name starts with, and wrap from Z back to A.
// Names that don't start with a letter are skipped. Returns value when no name starts with a letter.
u32 Debug_NextNameInitial(const struct DebugNameOrder *order, u32 value)
{
    u8 buffer[DEBUG_NAME_BUFFER_SIZE];
    s32 initial = Debug_FindInNameOrder(order, value) >= 0 ? Debug_NameInitial(order->getName(buffer, value)) : -1;
    u32 pos = Debug_FindNameInitial(order, initial + 1);

    if (pos == order->count)
        pos = Debug_FindNameInitial(order, 0);
    return pos < order->count ? order->values[pos] : value;
}

// *******************************
// Flag and var names

#include "data/debug_flag_var_names.h"

// A flag's constant name without FLAG_ (or a config's, such as I_EXP_SHARE_FLAG, for an unused
// flag), or NULL for a flag with no name (a trainer's) or with DEBUG_FLAG_VAR_NAMES off. Where
// names share a flag, tools/misc/make_debug_flag_var_names.py picks the one shown.
const u8 *Debug_GetFlagName(u32 flag)
{
    if (!DEBUG_FLAG_VAR_NAMES || flag == 0 || flag >= FLAGS_COUNT)
        return NULL;
    return sDebugFlagNames[flag];
}

// A var's constant name without VAR_, or NULL like Debug_GetFlagName. Only VARS_START..VARS_END.
const u8 *Debug_GetVarName(u32 varId)
{
    if (!DEBUG_FLAG_VAR_NAMES || varId < VARS_START || varId > VARS_END)
        return NULL;
    return sDebugVarNames[varId - VARS_START];
}

STATIC_ASSERT(DEBUG_NAME_BUFFER_SIZE >= sizeof(gTrainerClasses[0].name) + 1 + TRAINER_NAME_LENGTH + 1, DebugTrainerFlagNameSize);

// For a trainer flag, copies the trainer's class and name ("LEADER ROXANNE") into dest, which holds
// DEBUG_NAME_BUFFER_SIZE, and returns TRUE. Returns FALSE and leaves dest alone with
// DEBUG_FLAG_VAR_NAMES off, for any other flag, and for a trainer without a party: TRAINER_NONE, and
// IDs left out of the table (zero-filled, so the name has no EOS). IDs from TRAINERS_COUNT are unused.
bool32 Debug_CopyTrainerFlagName(u8 *dest, u32 flag)
{
    u32 trainerId = flag - TRAINER_FLAGS_START;

    if (!DEBUG_FLAG_VAR_NAMES || flag < TRAINER_FLAGS_START || trainerId >= TRAINERS_COUNT
     || GetTrainerPartySizeFromId(trainerId) == 0)
        return FALSE;
    dest = StringCopy(dest, GetTrainerClassNameFromId(trainerId));
    *dest++ = CHAR_SPACE;
    StringCopyN(dest, GetTrainerNameFromId(trainerId), TRAINER_NAME_LENGTH + 1);
    dest[TRAINER_NAME_LENGTH] = EOS;
    return TRUE;
}

// The name Set Flag shows, and orders by: a trainer flag's trainer, built in buffer (which holds
// DEBUG_NAME_BUFFER_SIZE), or else Debug_GetFlagName's
const u8 *Debug_GetFlagDisplayName(u8 *buffer, u32 flag)
{
    return Debug_CopyTrainerFlagName(buffer, flag) ? buffer : Debug_GetFlagName(flag);
}

// The name Set Var shows, and orders by: Debug_GetVarName's (buffer is unused)
const u8 *Debug_GetVarDisplayName(u8 *buffer, u32 varId)
{
    return Debug_GetVarName(varId);
}

// *******************************
// List menus

// ListMenu_ProcessInput plus L/R paging and wrapping between the first and last entries.
// L/R only act on a new press: R is often still held from the R+Start combo that opens the menu.
s32 Debug_ListMenu_ProcessInput(u8 listTaskId)
{
    struct ListMenu *list = (void *)gTasks[listTaskId].data;
    u32 lastIndex = list->template.totalItems - 1;
    u32 index = list->scrollOffset + list->selectedRow;

    if (JOY_NEW(A_BUTTON | B_BUTTON) || lastIndex == 0)
        return ListMenu_ProcessInput(listTaskId);

    if (JOY_NEW(DPAD_UP) && index == 0)
        ListMenuChangeSelection(list, TRUE, lastIndex, TRUE);
    else if (JOY_NEW(DPAD_DOWN) && index == lastIndex)
        ListMenuChangeSelection(list, TRUE, lastIndex, FALSE);
    else if (JOY_NEW(L_BUTTON))
        ListMenuChangeSelection(list, TRUE, list->template.maxShowed, FALSE);
    else if (JOY_NEW(R_BUTTON))
        ListMenuChangeSelection(list, TRUE, list->template.maxShowed, TRUE);
    else
        return ListMenu_ProcessInput(listTaskId);
    return LIST_NOTHING_CHOSEN;
}

// Scroll arrows centered over a list window, on its top and bottom frame, that follow *scrollOffset.
// Returns their task, or TASK_NONE when all the entries fit on one page.
u8 Debug_AddListScrollArrows(const struct WindowTemplate *listWindow, u32 totalItems, u32 maxShowed, u16 *scrollOffset)
{
    if (totalItems <= maxShowed)
        return TASK_NONE;

    return AddScrollIndicatorArrowPairParameterized(SCROLL_ARROW_UP,
        listWindow->tilemapLeft * 8 + listWindow->width * 4,
        listWindow->tilemapTop * 8 - 4,
        (listWindow->tilemapTop + listWindow->height) * 8 + 4,
        totalItems - maxShowed, DEBUG_SCROLL_ARROW_TAG, DEBUG_SCROLL_ARROW_TAG,
        scrollOffset);
}

void Debug_RemoveListScrollArrows(u8 *arrowsTaskId)
{
    if (*arrowsTaskId != TASK_NONE)
    {
        RemoveScrollIndicatorArrowPair(*arrowsTaskId);
        *arrowsTaskId = TASK_NONE;
    }
}

// Shows the submenu path, one indented line per level from getLevelName(dest, 1..levels).
// Returns the window, or WINDOW_NONE for the main menu (no levels).
u8 Debug_ShowPathWindow(const struct WindowTemplate *pathWindow, u32 levels, void (*getLevelName)(u8 *dest, u32 level))
{
    struct WindowTemplate template = *pathWindow;
    u8 windowId;

    if (levels == 0)
        return WINDOW_NONE;

    template.height = 2 * levels;
    windowId = AddWindow(&template);
    DrawStdWindowFrame(windowId, FALSE);
    FillWindowPixelBuffer(windowId, PIXEL_FILL(1));
    for (u32 i = 1; i <= levels; i++)
    {
        u32 indent = (i - 1) * 4;
        getLevelName(gStringVar4, i);
        // A line too long for the window drops to a narrower font instead of clipping
        u32 fontId = GetFontIdToFit(gStringVar4, FONT_NARROW, 0, WindowWidthPx(windowId) - indent);
        AddTextPrinterParameterized(windowId, fontId, gStringVar4, indent, (i - 1) * 16, 0, NULL);
    }
    CopyWindowToVram(windowId, COPYWIN_FULL);
    return windowId;
}

// Gives the saved position if it belongs to the same menu and still fits it, else the top.
// A different menu takes over the position, which then starts at the top.
void Debug_RestoreMenuPosition(struct DebugMenuPosition *position, const struct DebugMenuOption *items, u32 totalItems, u32 maxShowed, u16 *scrollOffset, u16 *selectedRow)
{
    u32 maxScroll = (totalItems > maxShowed) ? totalItems - maxShowed : 0;
    u32 index = position->scrollOffset + position->selectedRow;

    *scrollOffset = 0;
    *selectedRow = 0;
    if (position->items != items || totalItems == 0)
    {
        position->items = items;
        return;
    }
    if (index >= totalItems)
        index = totalItems - 1;
    // The saved row is below the page height, so this keeps the entry on screen
    *scrollOffset = min(position->scrollOffset, maxScroll);
    *selectedRow = index - *scrollOffset;
}

// *******************************
// Text

// Prints the lines lineHeight apart. A line too long for the window drops to a narrower font instead of clipping.
void Debug_PrintLinesToFit(u32 windowId, u32 fontId, u32 lineHeight, const u8 *const *lines, u32 count)
{
    for (u32 i = 0; i < count; i++)
    {
        u32 fitFontId = GetFontIdToFit(lines[i], fontId, 0, WindowWidthPx(windowId));
        AddTextPrinterParameterized(windowId, fitFontId, lines[i], 0, i * lineHeight, 0, NULL);
    }
}

// Copies src, or for a src too long for dest or too wide for widthPx in fontId,
// a leading ellipsis and as much of the end of src as fits.
void Debug_CopyStringEndToFit(u8 *dest, u32 destSize, const u8 *src, u32 fontId, u32 widthPx)
{
    u32 length = StringLength(src);
    u32 skip;

    if (length < destSize && GetStringWidth(fontId, src, 0) <= widthPx)
    {
        StringCopy(dest, src);
        return;
    }
    // The ellipsis, src from skip on and the EOS fill at most destSize
    skip = length + 2 > destSize ? length + 2 - destSize : 1;
    dest[0] = CHAR_ELLIPSIS;
    StringCopy(&dest[1], &src[skip]);
    while (skip < length && GetStringWidth(fontId, dest, 0) > widthPx)
        StringCopy(&dest[1], &src[++skip]);
}

// Copies text, in a narrower font than fontId if it would run past DEBUG_SUBMENU_ARROW_X,
// then the arrow at that x in fontId. The list fits a label by its whole width, which here
// is at least the arrow's x plus the arrow, so it can't fit the text alone (#88).
// Text past destSize - DEBUG_SUBMENU_LABEL_EXTRA - 1 bytes is cut off.
void Debug_CopySubMenuLabel(u8 *dest, u32 destSize, const u8 *text, u32 fontId)
{
    u32 length = min(StringLength(text), destSize - DEBUG_SUBMENU_LABEL_EXTRA - 1);
    u8 *end;

    memcpy(dest, text, length);
    dest[length] = EOS;
    end = WrapFontIdToFit(dest, &dest[length], fontId, DEBUG_SUBMENU_ARROW_X);
    end[0] = EXT_CTRL_CODE_BEGIN;
    end[1] = EXT_CTRL_CODE_CLEAR_TO;
    end[2] = DEBUG_SUBMENU_ARROW_X;
    end[3] = CHAR_RIGHT_ARROW;
    end[4] = EOS;
}
