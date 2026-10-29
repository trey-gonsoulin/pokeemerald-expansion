#define LEVEL_UP_MOVE(lvl, moveLearned) {.move = moveLearned, .level = lvl}
#define LEVEL_UP_END {.move = LEVEL_UP_MOVE_END, .level = 0}

static const struct LevelUpMove sNoneLevelUpLearnset[] = {
    LEVEL_UP_MOVE(1, MOVE_POUND),
    LEVEL_UP_END
};

#if P_FAMILY_RALTS
static const struct LevelUpMove sRaltsLevelUpLearnset[] = {
    LEVEL_UP_MOVE( 1, MOVE_GROWL),
    LEVEL_UP_MOVE( 5, MOVE_TELEPORT),
    LEVEL_UP_MOVE(12, MOVE_CONFUSION),
    LEVEL_UP_END
};
#endif //P_FAMILY_RALTS

static const struct LevelUpMove sSableyeLevelUpLearnset[] = {
    LEVEL_UP_MOVE( 1, MOVE_SCRATCH),
    LEVEL_UP_MOVE( 1, MOVE_LEER),
    LEVEL_UP_MOVE( 3, MOVE_ASTONISH),
    LEVEL_UP_MOVE(15, MOVE_SHADOW_CLAW),
    LEVEL_UP_MOVE(18, MOVE_SHADOW_BALL),
    LEVEL_UP_END
};

static const struct LevelUpMove sMagikarpLevelUpLearnset[] = {
    LEVEL_UP_MOVE( 1, MOVE_SPLASH),
    LEVEL_UP_MOVE(15, MOVE_TACKLE),
    LEVEL_UP_END
};

static const struct LevelUpMove sMrMimeLevelUpLearnset[] = {
    LEVEL_UP_MOVE( 0, MOVE_BARRIER),
    LEVEL_UP_MOVE( 1, MOVE_CONFUSION),
    LEVEL_UP_END
};
