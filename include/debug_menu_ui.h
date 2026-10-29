#ifndef GUARD_DEBUG_MENU_UI_H
#define GUARD_DEBUG_MENU_UI_H

// The fork's overworld debug-menu engine (src/debug_menu_ui.c): numeric (odometer) input and
// its digit rendering, list paging, scroll arrows, the submenu path window and menu-position
// memory. src/debug.c owns the menus, their state and the task; these helpers take what they
// need as arguments, apart from the numeric input, which works on the task data slots below.

struct DebugMenuOption;
struct WindowTemplate;

// Sprite tags, kept together so a new one doesn't collide
#define DEBUG_ICON_TAG          0xFDF3 // src/debug.c's species/item/object icon
#define DEBUG_SCROLL_ARROW_TAG  0xFDF4

// Task data slots the numeric input reads and writes (src/debug.c's tInput, tDigit, tInputStart)
#define DEBUG_DATA_INPUT        3
#define DEBUG_DATA_DIGIT        4 // highlighted digit, counted from the ones place
#define DEBUG_DATA_INPUT_START  7 // value the input started from, for Select

// Numeric input values fit in a u16 (a max can be 0xFFFF), so read the s16 task field back as unsigned
#define DEBUG_TASK_INPUT(taskId) ((u16)gTasks[taskId].data[DEBUG_DATA_INPUT])

// Any button Debug_HandleInput_Numeric acts on
#define DEBUG_NUMERIC_INPUT_PRESSED() (JOY_REPEAT(DPAD_UP | DPAD_DOWN) || JOY_NEW(DPAD_LEFT | DPAD_RIGHT | L_BUTTON | R_BUTTON | SELECT_BUTTON))

// "<+1>" ... "<+10000000>", indexed by the highlighted digit
extern const u8 *const gText_DigitIndicator[];
// "<+0x1>" ... "<+0x1000>", for inputs dialed in hex
extern const u8 *const gText_HexDigitIndicator[];

// Where the cursor was in a menu, so returning to it lands on the same entry
struct DebugMenuPosition
{
    const struct DebugMenuOption *items;
    u16 scrollOffset;
    u16 selectedRow;
};

// Numeric input
u32 Debug_CountDigits(u32 max);
u32 Debug_CountHexDigits(u32 max);
void Debug_StartNumericInput(u8 taskId, u32 input);
void Debug_HandleInput_Numeric(u8 taskId, u32 min, u32 max, u32 digits, bool32 hex);
bool32 Debug_NumericInputMovedDown(void);
void Debug_InputToDecimalString(u8 *dest, u8 taskId, u32 digits);
void Debug_InputToHexString(u8 *dest, u8 taskId, u32 digits);

// List menus
s32 Debug_ListMenu_ProcessInput(u8 listTaskId);
u8 Debug_AddListScrollArrows(const struct WindowTemplate *listWindow, u32 totalItems, u32 maxShowed, u16 *scrollOffset);
void Debug_RemoveListScrollArrows(u8 *arrowsTaskId);
// Builds each level's name in gStringVar4, so it overwrites gStringVar4
u8 Debug_ShowPathWindow(const struct WindowTemplate *pathWindow, u32 levels, void (*getLevelName)(u8 *dest, u32 level));
void Debug_RestoreMenuPosition(struct DebugMenuPosition *position, const struct DebugMenuOption *items, u32 totalItems, u32 maxShowed, u16 *scrollOffset, u16 *selectedRow);

// Text
void Debug_PrintLinesToFit(u32 windowId, u32 fontId, u32 lineHeight, const u8 *const *lines, u32 count);
void Debug_CopyStringEndToFit(u8 *dest, u32 destSize, const u8 *src, u32 fontId, u32 widthPx);

#endif // GUARD_DEBUG_MENU_UI_H
