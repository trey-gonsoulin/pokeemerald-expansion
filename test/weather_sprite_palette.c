#include "global.h"
#include "field_effect.h"
#include "field_weather.h"
#include "palette.h"
#include "sprite.h"
#include "test/test.h"

#define TEST_PALETTE_TAG 0x7204

// Where a weather update for slot 0xFF lands, past the end of the buffer (an address for -Warray-bounds)
#define PAST_BUFFER ((const u16 *)((uintptr_t)gPlttBufferFaded + sizeof(u16) * OBJ_PLTT_ID(0xFF)))

static const u16 sTestPalette[16] = {0};
static const struct SpritePalette sTestSpritePalette = {sTestPalette, TEST_PALETTE_TAG};

static u8 sSavedState, sSavedFirstFrame;
static u16 sSavedColor;

static void FillEverySpritePaletteSlot(void)
{
    u32 i;

    for (i = 0; IndexOfSpritePaletteTag(TAG_NONE) != 0xFF; i++)
        LoadSpritePaletteWithTag(gPlttBufferUnfaded, TEST_PALETTE_TAG + 1 + i);
}

// Starts the first frame of a weather fade-in, which writes fadeDestColor over the whole slot, and returns that color
static u32 StartFadeIn(void)
{
    u32 fadeColor = ~PAST_BUFFER[0] & 0x7FFF;

    sSavedState = gWeatherPtr->palProcessingState;
    sSavedFirstFrame = gWeatherPtr->fadeInFirstFrame;
    sSavedColor = gWeatherPtr->fadeDestColor;
    gWeatherPtr->palProcessingState = WEATHER_PAL_STATE_SCREEN_FADING_IN;
    gWeatherPtr->fadeInFirstFrame = TRUE;
    gWeatherPtr->fadeDestColor = fadeColor;
    return fadeColor;
}

static void EndFadeIn(void)
{
    gWeatherPtr->palProcessingState = sSavedState;
    gWeatherPtr->fadeInFirstFrame = sSavedFirstFrame;
    gWeatherPtr->fadeDestColor = sSavedColor;
}

// Gives BG palette 15 (where slot 0xFF + 16 lands as a u8) a color map type other than the loaders', and returns the table
static const u8 *SetPalette15ColorMapType(void)
{
    ResetPreservedPalettesInWeather();
    return SetPaletteColorMapType(15, COLOR_MAP_CONTRAST);
}

// The reflection loaders (src/field_effect_helpers.c) and Mew's grass on Faraway Island (src/faraway_island.c) pass this
TEST("Weather sprite palette: a weather update for slot 0xFF writes nothing")
{
    u32 fadeColor = StartFadeIn();

    UpdateSpritePaletteWithWeather(0xFF, TRUE);
    EndFadeIn();

    EXPECT_NE((u32)PAST_BUFFER[0], fadeColor);
}

TEST("Weather sprite palette: with no free slot a field effect's faded palette changes no color map or fade")
{
    u32 fadeColor;
    const u8 *colorMapTypes;
    struct SpritePalette palette = sTestSpritePalette;

    FillEverySpritePaletteSlot();
    colorMapTypes = SetPalette15ColorMapType();

    fadeColor = StartFadeIn();
    FieldEffect_LoadFadedPalette(&palette, COLOR_MAP_DARK_CONTRAST);
    EndFadeIn();

    EXPECT_EQ(IndexOfSpritePaletteTag(TEST_PALETTE_TAG), 0xFF);
    EXPECT_NE((u32)PAST_BUFFER[0], fadeColor);
    EXPECT_EQ(colorMapTypes[15], COLOR_MAP_CONTRAST);
    ResetPreservedPalettesInWeather();
}

TEST("Weather sprite palette: with no free slot a field effect script's faded palette changes no color map or fade")
{
    u32 fadeColor;
    const u8 *colorMapTypes;
    uintptr_t palette = (uintptr_t)&sTestSpritePalette;
    // loadfadedpal's arguments: the palette's address, its color map type, then the next command's word
    u8 commands[9] = {palette, palette >> 8, palette >> 16, palette >> 24, COLOR_MAP_DARK_CONTRAST};
    u8 *script = commands;

    FillEverySpritePaletteSlot();
    colorMapTypes = SetPalette15ColorMapType();

    fadeColor = StartFadeIn();
    FieldEffectScript_LoadFadedPalette(&script);
    EndFadeIn();

    EXPECT_EQ(IndexOfSpritePaletteTag(TEST_PALETTE_TAG), 0xFF);
    EXPECT_NE((u32)PAST_BUFFER[0], fadeColor);
    EXPECT_EQ(colorMapTypes[15], COLOR_MAP_CONTRAST);
    EXPECT_EQ(script - commands, 5);
    ResetPreservedPalettesInWeather();
}
