#include "global.h"
#include "evolution_ready.h"
#include "item.h"
#include "item_use.h"
#include "pokemon.h"
#include "sprite.h"

// P_PARTY_EVOLUTION_MARKER: the party menu's up arrow on a Pokémon that can evolve now.

#define TAG_EVOLUTION_READY 55121

static const u32 sEvolutionReadyGfx[] = INCGFX_U32("graphics/party_menu/evolution_ready.png", ".4bpp");
static const u16 sEvolutionReadyPalette[] = INCGFX_U16("graphics/party_menu/evolution_ready.png", ".gbapal");

static const struct OamData sOamData_EvolutionReady =
{
    .affineMode = ST_OAM_AFFINE_OFF,
    .objMode = ST_OAM_OBJ_NORMAL,
    .bpp = ST_OAM_4BPP,
    .shape = SPRITE_SHAPE(8x8),
    .size = SPRITE_SIZE(8x8),
    .priority = 1,
};

static const struct SpriteSheet sSpriteSheet_EvolutionReady =
{
    .data = sEvolutionReadyGfx, .size = sizeof(sEvolutionReadyGfx), .tag = TAG_EVOLUTION_READY
};

static const struct SpritePalette sSpritePalette_EvolutionReady =
{
    .data = sEvolutionReadyPalette, .tag = TAG_EVOLUTION_READY
};

static const struct SpriteTemplate sSpriteTemplate_EvolutionReady =
{
    .tileTag = TAG_EVOLUTION_READY,
    .paletteTag = TAG_EVOLUTION_READY,
    .oam = &sOamData_EvolutionReady,
    .anims = gDummySpriteAnimTable,
    .images = NULL,
    .affineAnims = gDummySpriteAffineAnimTable,
    .callback = SpriteCallbackDummy,
};

// TRUE if the mon evolves on its next level-up (friendship, a held item, the time and the
// other conditions included, or a level evolution cancelled with B), or with an evolution item
// in the bag. Trade, spin, script, battle-end and battle-only evolutions don't count: the party
// menu can't start them. Only CHECK_EVO passes, so nothing is recorded for ConsumeEvolutionItems.
bool32 CanPartyMonEvolveNow(struct Pokemon *mon)
{
    u32 i;
    enum Species species = GetMonData(mon, MON_DATA_SPECIES);
    const struct Evolution *evolutions;

    if (species == SPECIES_NONE || GetMonData(mon, MON_DATA_IS_EGG))
        return FALSE;

    if (GetEvolutionTargetSpecies(mon, EVO_MODE_NORMAL, ITEM_NONE, NULL, NULL, CHECK_EVO) != SPECIES_NONE)
        return TRUE;

    evolutions = GetSpeciesEvolutions(species);
    if (evolutions == NULL)
        return FALSE;

    // The bag uses an item on a Pokémon only through this field function: without
    // I_USE_EVO_HELD_ITEMS_FROM_BAG, a Metal Coat's EVO_ITEM entry can't be reached
    for (i = 0; evolutions[i].method != EVOLUTIONS_END; i++)
    {
        if (evolutions[i].method == EVO_ITEM
         && GetItemFieldFunc(evolutions[i].param) == ItemUseOutOfBattle_EvolutionStone
         && CheckBagHasItem(evolutions[i].param, 1)
         && GetEvolutionTargetSpecies(mon, EVO_MODE_ITEM_USE, evolutions[i].param, NULL, NULL, CHECK_EVO) != SPECIES_NONE)
            return TRUE;
    }
    return FALSE;
}

// The marker (the caller sets its visibility), or SPRITE_NONE if there's no sprite, tile or palette room for it
u8 CreateEvolutionReadyMarkerSprite(s16 x, s16 y)
{
    u32 spriteId;

    // Load the sheet once: LoadSpriteSheet doesn't check for its tag
    if (GetSpriteTileStartByTag(TAG_EVOLUTION_READY) == 0xFFFF)
        LoadSpriteSheet(&sSpriteSheet_EvolutionReady);
    if (GetSpriteTileStartByTag(TAG_EVOLUTION_READY) == 0xFFFF)
        return SPRITE_NONE;
    if (LoadSpritePalette(&sSpritePalette_EvolutionReady) == 0xFF)
        return SPRITE_NONE;

    spriteId = CreateSpriteUnchecked(&sSpriteTemplate_EvolutionReady, x, y, 0);
    return spriteId == MAX_SPRITES ? SPRITE_NONE : spriteId;
}
