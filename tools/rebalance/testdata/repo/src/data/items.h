#define TREASURE_FACTOR ((I_SELL_VALUE_FRACTION >= GEN_9) ? 2 : 1)

const struct ItemInfo gItemsInfo[] =
{
    [ITEM_POTION] =
    {
        .name = ITEM_NAME("Potion"),
        .price = (I_PRICE >= GEN_7) ? 200 : 300,
        .holdEffectParam = 20,
        .effect = gItemEffect_Potion,
    },

    [ITEM_HYPER_POTION] =
    {
        .name = ITEM_NAME("Hyper Potion"),
        .price = (I_PRICE >= GEN_2 && I_PRICE <= GEN_6) ? 1200 : 1500,
        .effect = gItemEffect_HyperPotion,
    },

    [ITEM_MAX_POTION] =
    {
        .name = ITEM_NAME("Max Potion"),
        .price = 2500,
        .effect = gItemEffect_MaxPotion,
    },

    [ITEM_NUGGET] =
    {
        .name = ITEM_NAME("Nugget"),
        .price = 10000 * TREASURE_FACTOR,
    },
};
