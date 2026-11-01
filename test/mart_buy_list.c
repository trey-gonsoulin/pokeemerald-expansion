#include "global.h"
#include "item.h"
#include "shop.h"
#include "string_util.h"
#include "strings.h"
#include "text.h"
#include "test/test.h"

// The Buy list prints the highlighted item's bag count right-aligned in
// WIN_IN_BAG_HOVER (src/shop.c), which starts where the item icon ends.
TEST("Mart Buy list: the IN BAG count fits right of the item icon")
{
    ConvertIntToDecimalStringN(gStringVar1, 9999, STR_CONV_MODE_RIGHT_ALIGN, MAX_ITEM_DIGITS + 1);
    StringExpandPlaceholders(gStringVar4, gText_InBagVar1);
    EXPECT_LE(GetStringWidth(FONT_NORMAL, gStringVar4, 0), SHOP_IN_BAG_HOVER_WIDTH * 8);
}
