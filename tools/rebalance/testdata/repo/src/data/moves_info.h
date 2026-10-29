#include "constants/moves.h"

const struct MoveInfo gMovesInfo[MOVES_COUNT_ALL] =
{
    [MOVE_NONE] =
    {
        .power = 0,
        .type = TYPE_NORMAL,
        .accuracy = 0,
        .category = DAMAGE_CATEGORY_STATUS,
    },

    [MOVE_POUND] =
    {
        .power = 40,
        .type = TYPE_NORMAL,
        .accuracy = 100,
        .category = DAMAGE_CATEGORY_PHYSICAL,
    },

    [MOVE_GROWL] =
    {
        .power = 0,
        .type = TYPE_NORMAL,
        .accuracy = 100,
        .category = DAMAGE_CATEGORY_STATUS,
    },

    [MOVE_LEER] =
    {
        .power = 0,
        .type = TYPE_NORMAL,
        .accuracy = 100,
        .category = DAMAGE_CATEGORY_STATUS,
    },

    [MOVE_TELEPORT] =
    {
        .power = 0,
        .type = TYPE_PSYCHIC,
        .accuracy = 0,
        .category = DAMAGE_CATEGORY_STATUS,
    },

    [MOVE_BARRIER] =
    {
        .power = 0,
        .type = TYPE_PSYCHIC,
        .accuracy = 0,
        .category = DAMAGE_CATEGORY_STATUS,
    },

    [MOVE_SPLASH] =
    {
        .power = 0,
        .type = TYPE_NORMAL,
        .accuracy = 0,
        .category = DAMAGE_CATEGORY_STATUS,
    },

    [MOVE_CONFUSION] =
    {
        .power = 50,
        .type = TYPE_PSYCHIC,
        .accuracy = 100,
        .category = DAMAGE_CATEGORY_SPECIAL,
        .additionalEffects = ADDITIONAL_EFFECTS({
            .moveEffect = MOVE_EFFECT_CONFUSION,
            .chance = 10,
        }),
    },

    [MOVE_SCRATCH] =
    {
        .power = 40,
        .type = TYPE_NORMAL,
        .accuracy = 100,
        .category = DAMAGE_CATEGORY_PHYSICAL,
    },

    [MOVE_TACKLE] =
    {
        .power = B_UPDATED_MOVE_DATA >= GEN_7 ? 40 : 35,
        .type = TYPE_NORMAL,
    #if B_UPDATED_MOVE_DATA >= GEN_5
        .accuracy = 100,
    #else
        .accuracy = 95,
    #endif
        .category = DAMAGE_CATEGORY_PHYSICAL,
    },

    [MOVE_NIGHT_SHADE] =
    {
        .power = 1,
        .type = TYPE_GHOST,
        .accuracy = 100,
        .category = DAMAGE_CATEGORY_SPECIAL,
    },

    [MOVE_ASTONISH] =
    {
        .power = 30,
        .type = TYPE_GHOST,
        .accuracy = 100,
        .category = DAMAGE_CATEGORY_PHYSICAL,
    },

    [MOVE_FURY_SWIPES] =
    {
        .power = 18,
        .type = TYPE_NORMAL,
        .accuracy = 80,
        .category = DAMAGE_CATEGORY_PHYSICAL,
    },

    [MOVE_FEINT_ATTACK] =
    {
        .power = 60,
        .type = B_UPDATED_MOVE_TYPES >= GEN_2 ? TYPE_DARK : TYPE_NORMAL,
        .accuracy = 0,
        .category = DAMAGE_CATEGORY_PHYSICAL,
    },

    [MOVE_SHADOW_BALL] =
    {
        .power = 80,
        .type = TYPE_GHOST,
        .accuracy = 100,
        .category = DAMAGE_CATEGORY_SPECIAL,
    },

    [MOVE_SHADOW_CLAW] =
    {
        .power = 70,
        .type = TYPE_GHOST,
        .accuracy = 100,
        .category = DAMAGE_CATEGORY_PHYSICAL,
    },

    [MOVE_CHARM] =
    {
        .power = 0,
        .type = B_UPDATED_MOVE_TYPES >= GEN_6 ? TYPE_FAIRY : TYPE_NORMAL,
        .accuracy = 100,
        .category = DAMAGE_CATEGORY_STATUS,
    },
};
