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

static void FillEverySpritePaletteSlot(void)
{
    u32 i;

    for (i = 0; IndexOfSpritePaletteTag(TAG_NONE) != 0xFF; i++)
        LoadSpritePaletteWithTag(gPlttBufferUnfaded, TEST_PALETTE_TAG + 1 + i);
}

// Sets up the first frame of a weather fade-in, which writes fadeDestColor over the whole slot
static void StartFadeIn(u32 fadeColor)
{
    gWeatherPtr->palProcessingState = WEATHER_PAL_STATE_SCREEN_FADING_IN;
    gWeatherPtr->fadeInFirstFrame = TRUE;
    gWeatherPtr->fadeDestColor = fadeColor;
}

// Gives palette 15 (where slot 0xFF + 16 lands as a u8) a color map type other than the loaders', and returns the table
static const u8 *SetPalette15ColorMapType(void)
{
    SetPaletteColorMapType(15, COLOR_MAP_NONE);
    return SetPaletteColorMapType(15, COLOR_MAP_CONTRAST);
}

// The reflection loaders (src/field_effect_helpers.c) and Mew's grass on Faraway Island (src/faraway_island.c) pass this
TEST("Weather sprite palette: a weather update for slot 0xFF writes nothing")
{
    u32 fadeColor = ~PAST_BUFFER[0] & 0x7FFF;
    u8 savedState = gWeatherPtr->palProcessingState;
    u8 savedFirstFrame = gWeatherPtr->fadeInFirstFrame;
    u16 savedColor = gWeatherPtr->fadeDestColor;

    StartFadeIn(fadeColor);
    UpdateSpritePaletteWithWeather(0xFF, TRUE);
    gWeatherPtr->palProcessingState = savedState;
    gWeatherPtr->fadeInFirstFrame = savedFirstFrame;
    gWeatherPtr->fadeDestColor = savedColor;

    EXPECT_NE((u32)PAST_BUFFER[0], fadeColor);
}

TEST("Weather sprite palette: with no free slot a field effect's faded palette changes no color map or fade")
{
    u32 fadeColor = ~PAST_BUFFER[0] & 0x7FFF;
    u8 savedState = gWeatherPtr->palProcessingState;
    u8 savedFirstFrame = gWeatherPtr->fadeInFirstFrame;
    u16 savedColor = gWeatherPtr->fadeDestColor;
    const u8 *colorMapTypes;
    struct SpritePalette palette = sTestSpritePalette;

    FillEverySpritePaletteSlot();
    colorMapTypes = SetPalette15ColorMapType();

    StartFadeIn(fadeColor);
    FieldEffect_LoadFadedPalette(&palette, COLOR_MAP_DARK_CONTRAST);
    gWeatherPtr->palProcessingState = savedState;
    gWeatherPtr->fadeInFirstFrame = savedFirstFrame;
    gWeatherPtr->fadeDestColor = savedColor;

    EXPECT_EQ(IndexOfSpritePaletteTag(TEST_PALETTE_TAG), 0xFF);
    EXPECT_NE((u32)PAST_BUFFER[0], fadeColor);
    EXPECT_EQ(colorMapTypes[15], COLOR_MAP_CONTRAST);
    ResetPaletteColorMapType(15);
}

TEST("Weather sprite palette: with no free slot a field effect script's faded palette changes no color map or fade")
{
    u32 fadeColor = ~PAST_BUFFER[0] & 0x7FFF;
    u8 savedState = gWeatherPtr->palProcessingState;
    u8 savedFirstFrame = gWeatherPtr->fadeInFirstFrame;
    u16 savedColor = gWeatherPtr->fadeDestColor;
    const u8 *colorMapTypes;
    uintptr_t palette = (uintptr_t)&sTestSpritePalette;
    // loadfadedpal's arguments: the palette's address, its color map type, then the next command's word
    u8 commands[9] = {palette, palette >> 8, palette >> 16, palette >> 24, COLOR_MAP_DARK_CONTRAST};
    u8 *script = commands;

    FillEverySpritePaletteSlot();
    colorMapTypes = SetPalette15ColorMapType();

    StartFadeIn(fadeColor);
    FieldEffectScript_LoadFadedPalette(&script);
    gWeatherPtr->palProcessingState = savedState;
    gWeatherPtr->fadeInFirstFrame = savedFirstFrame;
    gWeatherPtr->fadeDestColor = savedColor;

    EXPECT_EQ(IndexOfSpritePaletteTag(TEST_PALETTE_TAG), 0xFF);
    EXPECT_NE((u32)PAST_BUFFER[0], fadeColor);
    EXPECT_EQ(colorMapTypes[15], COLOR_MAP_CONTRAST);
    EXPECT_EQ(script - commands, 5);
    ResetPaletteColorMapType(15);
}
