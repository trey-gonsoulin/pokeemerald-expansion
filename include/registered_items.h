#ifndef GUARD_REGISTERED_ITEMS_H
#define GUARD_REGISTERED_ITEMS_H

enum Item GetRegisteredItem(u32 slot);
void SetRegisteredItem(u32 slot, enum Item item);
u32 CountRegisteredItems(void);
bool32 IsItemRegistered(enum Item item);
void ClearRegisteredItems(void);
bool32 ToggleRegisteredItem(enum Item item);
void RemoveUnownedRegisteredItems(void);
void SwapRegisteredBike(void);
void UseRegisteredItemsOnField(void);

#endif // GUARD_REGISTERED_ITEMS_H
