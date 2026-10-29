#define X UQ_4_12
#define ______ X(1.0) // Regular effectiveness.

#define STL_RS (B_UPDATED_TYPE_MATCHUPS >= GEN_6 ? X(1.0) : X(0.5))  // Ghost/Dark -> Steel

const uq4_12_t gTypeEffectivenessTable[NUMBER_OF_MON_TYPES][NUMBER_OF_MON_TYPES] =
{//                   None   Normal  Ghost   Steel  Psychic  Dark   Fairy   Water
    [TYPE_NONE]    = {______, ______, ______, ______, ______, ______, ______, ______},
    [TYPE_NORMAL]  = {______, ______, X(0.0), X(0.5), ______, ______, ______, ______},
    [TYPE_GHOST]   = {______, X(0.0), X(2.0), STL_RS, X(2.0), X(0.5), ______, ______},
    [TYPE_STEEL]   = {______, ______, ______, X(0.5), ______, ______, X(2.0), X(0.5)},
    [TYPE_PSYCHIC] = {______, ______, ______, X(0.5), X(0.5), X(0.0), ______, ______},
    [TYPE_DARK]    = {______, ______, X(2.0), STL_RS, X(2.0), X(0.5), X(0.5), ______},
    [TYPE_FAIRY]   = {______, ______, ______, X(0.5), ______, X(2.0), ______, ______},
    [TYPE_WATER]   = {______, ______, ______, ______, ______, ______, ______, X(0.5)},
};

#undef ______
#undef X

const struct TypeInfo gTypesInfo[NUMBER_OF_MON_TYPES] =
{
    [TYPE_NORMAL] =
    {
        .name = _("Normal"),
        .damageCategory = DAMAGE_CATEGORY_PHYSICAL,
    },
    [TYPE_GHOST] =
    {
        .name = _("Ghost"),
        .damageCategory = DAMAGE_CATEGORY_PHYSICAL,
    },
    [TYPE_STEEL] =
    {
        .name = _("Steel"),
        .damageCategory = DAMAGE_CATEGORY_PHYSICAL,
    },
    [TYPE_PSYCHIC] =
    {
        .name = _("Psychic"),
        .damageCategory = DAMAGE_CATEGORY_SPECIAL,
    },
    [TYPE_DARK] =
    {
        .name = _("Dark"),
        .damageCategory = DAMAGE_CATEGORY_SPECIAL,
    },
    [TYPE_FAIRY] =
    {
        .name = _("Fairy"),
        .damageCategory = DAMAGE_CATEGORY_SPECIAL,
    },
    [TYPE_WATER] =
    {
        .name = _("Water"),
        .damageCategory = DAMAGE_CATEGORY_SPECIAL,
    },
};
