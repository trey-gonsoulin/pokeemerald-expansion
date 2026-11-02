#include "global.h"
#include "battle_setup.h"
#include "event_data.h"
#include "event_object_movement.h"
#include "field_effect.h"
#include "field_weather.h"
#include "rematch_indicator.h"
#include "script.h"
#include "sprite.h"
#include "vs_seeker.h"
#include "constants/rematches.h"

// A Poké Ball over each trainer on screen whose rematch is ready (#207), the PokéNav Match Call
// list's ready icon. A grey one marks a beaten trainer that registers in Match Call when talked to.

#if FREE_MATCH_CALL == FALSE

#define TAG_REMATCH_INDICATOR 0x1020

// Above the top of the trainer's sprite: the ball is the middle 9 rows of the 16-row frame.
#define REMATCH_INDICATOR_Y_OFFSET -4

#define sObjectEventId data[0]

struct RematchIndicatorSlot
{
    u8 localId;
    u8 mapNum;
    u8 mapGroup;
    bool8 known;
    s8 tableId;
    u8 spriteId;
};

static EWRAM_DATA struct RematchIndicatorSlot sSlots[OBJECT_EVENTS_COUNT] = {0};

static const u32 sRematchIndicatorGfx[] = INCGFX_U32("graphics/field_effects/pics/rematch_indicator.png", ".4bpp");
static const u16 sRematchIndicatorPalette[] = INCGFX_U16("graphics/field_effects/pics/rematch_indicator.png", ".gbapal");

static const struct SpriteSheet sSpriteSheet_RematchIndicator =
{
    .data = sRematchIndicatorGfx, .size = sizeof(sRematchIndicatorGfx), .tag = TAG_REMATCH_INDICATOR
};

// Both variants share one palette, so the markers take at most one of the field's OBJ palettes.
static const struct SpritePalette sSpritePalette_RematchIndicator =
{
    .data = sRematchIndicatorPalette, .tag = TAG_REMATCH_INDICATOR
};

static const struct OamData sOamData_RematchIndicator =
{
    .affineMode = ST_OAM_AFFINE_OFF,
    .objMode = ST_OAM_OBJ_NORMAL,
    .bpp = ST_OAM_4BPP,
    .shape = SPRITE_SHAPE(8x16),
    .size = SPRITE_SIZE(8x16),
    .priority = 1,
};

static const union AnimCmd sAnim_Ready[] =
{
    ANIMCMD_FRAME(0, 0),
    ANIMCMD_END,
};

static const union AnimCmd sAnim_Unregistered[] =
{
    ANIMCMD_FRAME(2, 0),
    ANIMCMD_END,
};

static const union AnimCmd *const sAnims_RematchIndicator[] =
{
    [REMATCH_INDICATOR_READY - 1] = sAnim_Ready,
    [REMATCH_INDICATOR_UNREGISTERED - 1] = sAnim_Unregistered,
};

static void SpriteCB_RematchIndicator(struct Sprite *sprite)
{
}

static const struct SpriteTemplate sSpriteTemplate_RematchIndicator =
{
    .tileTag = TAG_REMATCH_INDICATOR,
    .paletteTag = TAG_REMATCH_INDICATOR,
    .oam = &sOamData_RematchIndicator,
    .anims = sAnims_RematchIndicator,
    .images = NULL,
    .affineAnims = gDummySpriteAffineAnimTable,
    .callback = SpriteCB_RematchIndicator,
};

// The trainers whose talk script registers them in Match Call once the player has it
// (IsTrainerRegistered, then a TryRegister script). The other route trainers register only
// right after their first battle; the gym leaders, Wally and the Elite Four never by talking.
// test/rematch_indicator.c checks this list against the scripts.
static bool32 RegistersWhenTalkedTo(s32 rematchTableId)
{
    switch (rematchTableId)
    {
    case REMATCH_CALVIN:  // Route 102
    case REMATCH_JAMES:   // Petalburg Woods
    case REMATCH_HALEY:   // Route 104
    case REMATCH_WINSTON: // Route 104
    case REMATCH_CINDY:   // Route 104
    case REMATCH_JERRY:   // Route 116
    case REMATCH_KAREN:   // Route 116
        return TRUE;
    default:
        return FALSE;
    }
}

// The rematch table entry of the trainer an object's script battles first, or -1.
s32 GetRematchTableIdFromScript(const u8 *script)
{
    if (script == NULL)
        return -1;
    return FirstBattleTrainerIdToRematchTableId(gRematchTable, GetTrainerFlagFromScript(script));
}

// Reads trainerRematches itself: ShouldTryRematchBattle stays TRUE for good once the second
// team is beaten (WasSecondRematchWon), while trainerbattle_rematch refuses a 0 byte.
enum RematchIndicator GetRematchIndicator(s32 rematchTableId)
{
    if (rematchTableId < 0 || rematchTableId >= REMATCH_TABLE_ENTRIES)
        return REMATCH_INDICATOR_NONE;
    if (gSaveBlock1Ptr->trainerRematches[rematchTableId] != 0)
        return REMATCH_INDICATOR_READY;
    if (RegistersWhenTalkedTo(rematchTableId)
     && FlagGet(FLAG_HAS_MATCH_CALL)
     && !FlagGet(TRAINER_REGISTERED_FLAGS_START + rematchTableId)
     && HasTrainerBeenFought(gRematchTable[rematchTableId].trainerIds[0]))
        return REMATCH_INDICATOR_UNREGISTERED;
    return REMATCH_INDICATOR_NONE;
}

static s32 GetObjectEventRematchTableId(u32 objectEventId)
{
    struct ObjectEvent *objectEvent = &gObjectEvents[objectEventId];
    struct RematchIndicatorSlot *slot = &sSlots[objectEventId];

    if (!slot->known
     || slot->localId != objectEvent->localId
     || slot->mapNum != objectEvent->mapNum
     || slot->mapGroup != objectEvent->mapGroup)
    {
        const struct ObjectEventTemplate *template = GetObjectEventTemplateByLocalIdAndMap(objectEvent->localId, objectEvent->mapNum, objectEvent->mapGroup);

        slot->localId = objectEvent->localId;
        slot->mapNum = objectEvent->mapNum;
        slot->mapGroup = objectEvent->mapGroup;
        slot->tableId = GetRematchTableIdFromScript(template != NULL ? template->script : NULL);
        slot->known = TRUE;
    }
    return slot->tableId;
}

// The slot's marker, unless a sprite reset (battle, menu) or a reused ID took it.
static struct Sprite *GetIndicatorSprite(u32 objectEventId)
{
    struct Sprite *sprite;

    if (sSlots[objectEventId].spriteId >= MAX_SPRITES)
        return NULL;
    sprite = &gSprites[sSlots[objectEventId].spriteId];
    if (!sprite->inUse || sprite->callback != SpriteCB_RematchIndicator || sprite->sObjectEventId != objectEventId)
        return NULL;
    return sprite;
}

static void RemoveIndicator(u32 objectEventId)
{
    struct Sprite *sprite = GetIndicatorSprite(objectEventId);

    if (sprite != NULL)
        FieldEffectFreeGraphicsResources(sprite);
    sSlots[objectEventId].spriteId = MAX_SPRITES;
}

static struct Sprite *CreateIndicator(u32 objectEventId)
{
    u32 spriteId;

    if (GetSpriteTileStartByTag(TAG_REMATCH_INDICATOR) == 0xFFFF
     && LoadSpriteSheet(&sSpriteSheet_RematchIndicator) == 0)
        return NULL;
    if (IndexOfSpritePaletteTag(TAG_REMATCH_INDICATOR) == 0xFF)
    {
        u32 paletteNum = LoadSpritePalette(&sSpritePalette_RematchIndicator);

        if (paletteNum == 0xFF)
        {
            FieldEffectFreeTilesIfUnused(GetSpriteTileStartByTag(TAG_REMATCH_INDICATOR));
            return NULL;
        }
        SetPaletteColorMapType(paletteNum + 16, COLOR_MAP_DARK_CONTRAST);
        UpdateSpritePaletteWithWeather(paletteNum, TRUE);
    }

    spriteId = CreateSpriteAtEndUnchecked(&sSpriteTemplate_RematchIndicator, 0, 0, 0x53);
    if (spriteId == MAX_SPRITES)
    {
        FieldEffectFreeTilesIfUnused(GetSpriteTileStartByTag(TAG_REMATCH_INDICATOR));
        FieldEffectFreePaletteIfUnused(IndexOfSpritePaletteTag(TAG_REMATCH_INDICATOR));
        return NULL;
    }
    gSprites[spriteId].coordOffsetEnabled = TRUE;
    gSprites[spriteId].sObjectEventId = objectEventId;
    sSlots[objectEventId].spriteId = spriteId;
    return &gSprites[spriteId];
}

static void UpdateIndicator(u32 objectEventId, bool32 fieldLocked)
{
    struct ObjectEvent *objectEvent = &gObjectEvents[objectEventId];
    enum RematchIndicator indicator = REMATCH_INDICATOR_NONE;
    struct Sprite *sprite, *objectSprite;

    if (!fieldLocked && objectEvent->active && !objectEvent->isPlayer && objectEvent->spriteId < MAX_SPRITES)
        indicator = GetRematchIndicator(GetObjectEventRematchTableId(objectEventId));
    if (indicator == REMATCH_INDICATOR_NONE)
    {
        RemoveIndicator(objectEventId);
        return;
    }

    sprite = GetIndicatorSprite(objectEventId);
    if (sprite == NULL && (sprite = CreateIndicator(objectEventId)) == NULL)
        return;
    if (sprite->animNum != indicator - 1)
    {
        StartSpriteAnim(sprite, indicator - 1);
        AnimateSprite(sprite); // AnimateSprites has run this frame
    }

    // The trainer's priority, so a bridge or roof that hides the trainer hides the ball too
    objectSprite = &gSprites[objectEvent->spriteId];
    sprite->oam.priority = objectSprite->oam.priority;
    sprite->x = objectSprite->x;
    sprite->y = objectSprite->y + objectSprite->centerToCornerVecY + REMATCH_INDICATOR_Y_OFFSET;
    sprite->x2 = objectSprite->x2;
    sprite->y2 = objectSprite->y2;
    sprite->invisible = objectSprite->invisible;
}

// Runs once per overworld frame, after the camera has moved the object sprites. A script
// holding the field (a cutscene, a battle starting, a menu) removes every marker.
void UpdateRematchIndicators(void)
{
    u32 i;
    bool32 fieldLocked = ArePlayerFieldControlsLocked();

    for (i = 0; i < OBJECT_EVENTS_COUNT; i++)
        UpdateIndicator(i, fieldLocked);
}

#else

s32 GetRematchTableIdFromScript(const u8 *script)
{
    return -1;
}

enum RematchIndicator GetRematchIndicator(s32 rematchTableId)
{
    return REMATCH_INDICATOR_NONE;
}

void UpdateRematchIndicators(void)
{
}

#endif // FREE_MATCH_CALL
