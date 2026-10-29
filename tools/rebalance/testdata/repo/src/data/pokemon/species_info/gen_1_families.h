#if P_FAMILY_RALTS
#define RALTS_FAMILY_TYPE2 (P_UPDATED_TYPES >= GEN_6 ? TYPE_FAIRY : TYPE_PSYCHIC)

    [SPECIES_RALTS] =
    {
        .baseHP        = 28,
        .baseAttack    = 25,
        .baseDefense   = 25,
        .baseSpeed     = 40,
        .baseSpAttack  = 45,
        .baseSpDefense = 35,
        .types = MON_TYPES(TYPE_PSYCHIC, RALTS_FAMILY_TYPE2),
        .expYield = (P_UPDATED_EXP_YIELDS >= GEN_5) ? 40 : 70,
        .growthRate = GROWTH_SLOW,
        .levelUpLearnset = sRaltsLevelUpLearnset,
    },
#endif //P_FAMILY_RALTS

    [SPECIES_SABLEYE] =
    {
        .baseHP        = 50,
        .baseAttack    = 90,
        .baseDefense   = 75,
        .baseSpeed     = 50,
        .baseSpAttack  = 60,
        .baseSpDefense = 65,
        .types = MON_TYPES(TYPE_DARK, TYPE_GHOST),
    #if P_UPDATED_EXP_YIELDS >= GEN_5
        .expYield = 133,
    #else
        .expYield = 98,
    #endif
        .growthRate = GROWTH_MEDIUM_SLOW,
        .levelUpLearnset = sSableyeLevelUpLearnset,
    },

#define KARP_TYPES { TYPE_WATER, TYPE_WATER }
    [SPECIES_MAGIKARP_NORMAL] =
    {
        .baseHP        = 20,
        .baseAttack    = 10,
        .baseDefense   = 55,
        .baseSpeed     = 80,
        .baseSpAttack  = 15,
        .baseSpDefense = 20,
        .types = KARP_TYPES,
        .expYield = 40,
        .growthRate = GROWTH_SLOW,
        .levelUpLearnset = sMagikarpLevelUpLearnset,
    },

    [SPECIES_MR_MIME] =
    {
        .baseHP        = 40,
        .baseAttack    = 45,
        .baseDefense   = 65,
        .baseSpeed     = 90,
        .baseSpAttack  = 100,
        .baseSpDefense = 120,
        .types = MON_TYPES(TYPE_PSYCHIC, P_UPDATED_TYPES >= GEN_6 ? TYPE_FAIRY : TYPE_PSYCHIC),
        .expYield = 161,
        .growthRate = GROWTH_MEDIUM_FAST,
        .levelUpLearnset = sMrMimeLevelUpLearnset,
    },
