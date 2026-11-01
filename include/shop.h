#ifndef GUARD_SHOP_H
#define GUARD_SHOP_H

// Tiles of the Buy list's bag count window, between the item icon and the item list
#define SHOP_IN_BAG_HOVER_WIDTH 9

extern struct ItemSlot gMartPurchaseHistory[3];

void CreatePokemartMenu(const u16 *itemsForSale);
void CreateDecorationShop1Menu(const u16 *itemsForSale);
void CreateDecorationShop2Menu(const u16 *itemsForSale);
void CB2_ExitSellMenu(void);

#endif // GUARD_SHOP_H
