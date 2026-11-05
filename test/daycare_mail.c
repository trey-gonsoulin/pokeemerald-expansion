#include "global.h"
#include "daycare.h"
#include "event_data.h"
#include "mail.h"
#include "string_util.h"
#include "test/test.h"

// Leaves a party Pokémon holding mail at the Day Care, in slot 0.
static void LeaveMonWithMailAtDaycare(const u8 *nickname, u8 language)
{
    struct Pokemon *mon = &gParties[B_TRAINER_PLAYER][0];

    ZeroPlayerPartyMons();
    ClearAllMail();
    // A slot's old bytes are not EOS (0x00 is a space)
    memset(&gSaveBlock1Ptr->daycare, 0, sizeof(gSaveBlock1Ptr->daycare));
    StringCopy(gSaveBlock2Ptr->playerName, COMPOUND_STRING("TREY"));

    CreateMon(mon, SPECIES_MASQUERAIN, 20, 0, OTID_STRUCT_PRESET(0));
    SetMonData(mon, MON_DATA_LANGUAGE, &language);
    SetMonData(mon, MON_DATA_NICKNAME, nickname);
    GiveMailToMonByItemId(mon, ITEM_ORANGE_MAIL);
    StorePokemonInDaycare(mon, &gSaveBlock1Ptr->daycare.mons[0]);
    gSpecialVar_0x8004 = 0;
}

TEST("Day Care mail: a 10-letter nickname keeps its terminator")
{
    LeaveMonWithMailAtDaycare(COMPOUND_STRING("MASQUERAIN"), GAME_LANGUAGE);

    EXPECT_EQ(StringCompare(gSaveBlock1Ptr->daycare.mons[0].mail.monName, COMPOUND_STRING("MASQUERAIN")), 0);
    EXPECT(!CheckDaycareMonReceivedMail());
}

TEST("Day Care mail: a 12-letter nickname is cut to 10 letters and received no mail")
{
    LeaveMonWithMailAtDaycare(COMPOUND_STRING("ABCDEFGHIJKL"), GAME_LANGUAGE);

    EXPECT_EQ(StringCompare(gSaveBlock1Ptr->daycare.mons[0].mail.monName, COMPOUND_STRING("ABCDEFGHIJ")), 0);
    EXPECT(!CheckDaycareMonReceivedMail());
}

TEST("Day Care mail: a short nickname received no mail")
{
    LeaveMonWithMailAtDaycare(COMPOUND_STRING("BUG"), GAME_LANGUAGE);

    EXPECT(!CheckDaycareMonReceivedMail());
}

TEST("Day Care mail: a Japanese nickname received no mail")
{
    LeaveMonWithMailAtDaycare(COMPOUND_STRING("ABCDE"), LANGUAGE_JAPANESE);

    // The stored name drops the Japanese control codes
    EXPECT_EQ(StringCompare(gSaveBlock1Ptr->daycare.mons[0].mail.monName, COMPOUND_STRING("ABCDE")), 0);
    EXPECT(!CheckDaycareMonReceivedMail());
}

TEST("Day Care mail: mail written for another Pokémon was received")
{
    LeaveMonWithMailAtDaycare(COMPOUND_STRING("MASQUERAIN"), GAME_LANGUAGE);
    StringCopy(gSaveBlock1Ptr->daycare.mons[0].mail.monName, COMPOUND_STRING("ZIGZAGOON"));

    EXPECT(CheckDaycareMonReceivedMail());
    EXPECT_EQ(StringCompare(gStringVar1, COMPOUND_STRING("MASQUERAIN")), 0);
    EXPECT_EQ(StringCompare(gStringVar3, COMPOUND_STRING("ZIGZAGOON")), 0);
}

TEST("Day Care mail: a 10-letter name saved without its terminator received no mail")
{
    u8 *monName;

    LeaveMonWithMailAtDaycare(COMPOUND_STRING("MASQUERAIN"), GAME_LANGUAGE);
    // Saves from before the fix hold the 10 letters and a stray byte
    monName = gSaveBlock1Ptr->daycare.mons[0].mail.monName;
    monName[VANILLA_POKEMON_NAME_LENGTH] = 0;

    EXPECT(!CheckDaycareMonReceivedMail());
}

TEST("Day Care mail: another Pokémon's 10-letter name saved without its terminator reads as 10 letters")
{
    u8 *monName;

    LeaveMonWithMailAtDaycare(COMPOUND_STRING("BUG"), GAME_LANGUAGE);
    monName = gSaveBlock1Ptr->daycare.mons[0].mail.monName;
    memcpy(monName, COMPOUND_STRING("TENTACRUEL"), VANILLA_POKEMON_NAME_LENGTH);
    monName[VANILLA_POKEMON_NAME_LENGTH] = 0;

    EXPECT(CheckDaycareMonReceivedMail());
    EXPECT_EQ(StringCompare(gStringVar3, COMPOUND_STRING("TENTACRUEL")), 0);
}
