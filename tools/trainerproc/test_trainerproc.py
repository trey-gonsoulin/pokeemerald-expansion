"""Tests for trainerproc's range and size checks (#255).

Builds the tool with its own Makefile, then runs it on crafted .party text
(read from stdin, written to stdout), as the build does after cpp.

Run from the repo root: python3 -m unittest discover -s tools/trainerproc
"""

import pathlib
import subprocess
import unittest

TOOL_DIR = pathlib.Path(__file__).resolve().parent
TOOL = TOOL_DIR / "trainerproc"
SOURCE_PATH = "test.party"


def setUpModule():
    subprocess.run(["make", "-C", str(TOOL_DIR)], check=True, capture_output=True)


def run_tool(source):
    return subprocess.run(
        [str(TOOL), "-o", "-", "-i", SOURCE_PATH, "-"],
        input=source.encode(),
        capture_output=True,
    )


def trainer(*mons, fields=""):
    header = "=== TRAINER_TEST ===\nName: Test\nPic: Hiker\n" + fields + "\n"
    return header + "\n".join(mons)


def mon(*attributes, species="Geodude"):
    return species + "\n" + "".join(a + "\n" for a in attributes)


class TrainerprocTestCase(unittest.TestCase):
    def assertAccepted(self, source):
        result = run_tool(source)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        return result.stdout.decode()

    def assertRejected(self, source, message, line):
        result = run_tool(source)
        stderr = result.stderr.decode()
        self.assertEqual(result.returncode, 1, stderr)
        self.assertIn("error: " + message, stderr)
        self.assertIn("%s:%d: " % (SOURCE_PATH, line), stderr)


class Valid(TrainerprocTestCase):
    def test_minimal_trainer(self):
        out = self.assertAccepted(trainer(mon("Level: 5")))
        self.assertIn(".lvl = 5,", out)
        self.assertIn(".partySize = 1,", out)


class Level(TrainerprocTestCase):
    def test_bounds_are_accepted(self):
        self.assertIn(".lvl = 1,", self.assertAccepted(trainer(mon("Level: 1"))))
        self.assertIn(".lvl = 100,", self.assertAccepted(trainer(mon("Level: 100"))))

    def test_out_of_range_is_rejected(self):
        for value in ("0", "101", "255", "300", "99999999999999999999"):
            with self.subTest(value=value):
                self.assertRejected(trainer(mon("Level: " + value)), "level must be from 1 to 100", 6)

    def test_sign_is_rejected(self):
        for value in ("-5", "+5"):
            with self.subTest(value=value):
                self.assertRejected(trainer(mon("Level: " + value)), "invalid integer", 6)

    def test_pragma_default_level(self):
        self.assertIn(".lvl = 50,", self.assertAccepted("#pragma trainerproc level 50\n" + trainer(mon())))
        self.assertRejected("#pragma trainerproc level 101\n" + trainer(mon()), "level must be from 1 to 100", 1)

    def test_pragma_at_end_without_newline_fails_cleanly(self):
        # Used to read past the buffer (strtol on a buffer with no terminator).
        result = run_tool("#pragma trainerproc level 50")
        self.assertEqual(result.returncode, 1, result.stderr.decode())
        self.assertIn("expected newline", result.stderr.decode())


class IVs(TrainerprocTestCase):
    def test_31_is_accepted(self):
        out = self.assertAccepted(trainer(mon("IVs: 31 HP / 0 Atk / 0 Def / 0 SpA / 0 SpD / 0 Spe")))
        self.assertIn("TRAINER_PARTY_IVS(31, 0, 0, 0, 0, 0)", out)

    def test_32_is_rejected(self):
        # 32 HP would read as 0 HP and 1 Atk in TRAINER_PARTY_IVS's 5-bit fields.
        self.assertRejected(trainer(mon("IVs: 0 HP / 32 Atk")), "IVs must be from 0 to 31", 6)

    def test_long_digit_string_is_rejected(self):
        self.assertRejected(trainer(mon("IVs: 99999999999999999999 HP")), "IVs must be from 0 to 31", 6)

    def test_pragma_ivs(self):
        self.assertRejected(
            "#pragma trainerproc ivs 32 HP / 31 Atk / 31 Def / 31 SpA / 31 SpD / 31 Spe\n" + trainer(mon()),
            "IVs must be from 0 to 31", 1)


class EVs(TrainerprocTestCase):
    def test_full_spread_is_accepted(self):
        out = self.assertAccepted(trainer(mon("EVs: 252 HP / 252 Atk / 6 Def")))
        self.assertIn("TRAINER_PARTY_EVS(252, 252, 6, 0, 0, 0)", out)

    def test_255_is_accepted(self):
        # The game's cap is 255 before P_EV_CAP GEN_6, a config the tool can't read.
        self.assertIn("TRAINER_PARTY_EVS(255, 0, 0, 0, 0, 0)", self.assertAccepted(trainer(mon("EVs: 255 HP"))))

    def test_over_255_is_rejected(self):
        self.assertRejected(trainer(mon("EVs: 256 HP")), "EVs must be from 0 to 255", 6)

    def test_over_510_in_total_is_rejected(self):
        self.assertRejected(trainer(mon("EVs: 252 HP / 252 Atk / 7 Def")), "EVs must total at most 510", 6)


class Happiness(TrainerprocTestCase):
    def test_bounds_are_accepted(self):
        self.assertIn(".friendship = 0,", self.assertAccepted(trainer(mon("Happiness: 0"))))
        self.assertIn(".friendship = 255,", self.assertAccepted(trainer(mon("Happiness: 255"))))

    def test_out_of_range_is_rejected(self):
        self.assertRejected(trainer(mon("Happiness: 256")), "happiness must be from 0 to 255", 6)
        self.assertRejected(trainer(mon("Happiness: -1")), "invalid integer", 6)


class DynamaxLevel(TrainerprocTestCase):
    def test_bounds(self):
        self.assertIn(".dynamaxLevel = 10,", self.assertAccepted(trainer(mon("Dynamax Level: 10"))))
        self.assertRejected(trainer(mon("Dynamax Level: 11")), "Dynamax level must be from 0 to 10", 6)


class TeraType(TrainerprocTestCase):
    def test_alone_is_written(self):
        self.assertIn(".teraType = TYPE_FIRE,", self.assertAccepted(trainer(mon("Tera Type: Fire"))))

    def test_with_dynamax_is_rejected(self):
        # Used to be dropped silently.
        for gimmick in ("Dynamax Level: 5", "Gigantamax: Yes", "Gigantamax: No"):
            with self.subTest(gimmick=gimmick):
                self.assertRejected(
                    trainer(mon(gimmick, "Tera Type: Fire")),
                    "'Tera Type' can't go with 'Dynamax Level' or 'Gigantamax'", 7)


class PartySize(TrainerprocTestCase):
    def test_six_pokemon_are_accepted(self):
        self.assertIn(".partySize = 6,", self.assertAccepted(trainer(*[mon()] * 6)))

    def test_seventh_pokemon_without_party_size_is_rejected(self):
        # The 7th Pokemon's header is on line 17 (4 header lines, then 2 lines per Pokemon).
        self.assertRejected(trainer(*[mon()] * 7), "more than 6 Pokemon without 'Party Size'", 17)

    def test_pool_may_hold_more(self):
        out = self.assertAccepted(trainer(*[mon()] * 7, fields="Party Size: 6\n"))
        self.assertIn(".partySize = 6,", out)
        self.assertIn(".poolSize = 7,", out)

    def test_party_size_out_of_range_is_rejected(self):
        for value in ("0", "7"):
            with self.subTest(value=value):
                self.assertRejected(
                    trainer(*[mon()] * 8, fields="Party Size: " + value + "\n"),
                    "party size must be from 1 to 6", 4)


class Lists(TrainerprocTestCase):
    def test_four_items_are_accepted(self):
        self.assertAccepted(trainer(mon(), fields="Items: Potion / Potion / Potion / Potion\n"))

    def test_fifth_item_is_rejected(self):
        # Used to write past items[4].
        self.assertRejected(
            trainer(mon(), fields="Items: Potion / Potion / Potion / Potion / Potion\n"),
            "too many items (at most 4)", 4)

    def test_too_many_ai_flags_are_rejected(self):
        flags = " / ".join(["Check Bad Move"] * 65)
        self.assertRejected(trainer(mon(), fields="AI: " + flags + "\n"), "too many AI flags (at most 64)", 4)

    def test_too_many_starting_statuses_are_rejected(self):
        statuses = " / ".join(["Electric Terrain"] * 65)
        self.assertRejected(
            trainer(mon(), fields="Starting Status: " + statuses + "\n"),
            "too many starting statuses (at most 64)", 4)

    def test_too_many_tags_are_rejected(self):
        self.assertRejected(trainer(mon("Tags: " + " / ".join(["Lead"] * 33))), "too many tags (at most 32)", 6)


class Output(TrainerprocTestCase):
    def test_stdout_output(self):
        # '-o -' used to set the input FILE to stdout and write through NULL.
        self.assertIn("[TRAINER_TEST] =", self.assertAccepted(trainer(mon())))


if __name__ == "__main__":
    unittest.main()
