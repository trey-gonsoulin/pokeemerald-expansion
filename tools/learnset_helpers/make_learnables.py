#!/usr/bin/env python3

"""
Usage: python3 make_learnables.py INPUTS_DIR OUTPUT_FILE

Build a primary store of learnable moves for each species based on input documents. This script
is meant to be run to generate a pre-processed store of data that should not change very much;
thus, it can safely be pre-computed in order to speed up incremental builds for end-users.
"""

from functools import reduce

import json
import pathlib
import re
import sys
import unicodedata

# za.json's entries that list one set of moves for forms the other games list apart (its SLOWBRO
# holds Galarian Slowbro's moves too, its HOOPA both forms'), so no one form can take them. Not
# ROTOM: its forms share one learnset.
ZA_MERGED_FORMS = {
    "AVALUGG", "FARFETCHD", "FLOETTE", "GOODRA", "HOOPA", "INDEEDEE", "MAROWAK", "MEOWSTIC", "MEOWTH",
    "MR_MIME", "PERSIAN", "QWILFISH", "RAICHU", "SLIGGOO", "SLOWBRO", "SLOWKING", "SLOWPOKE", "STUNFISK",
    "TOXTRICITY", "YAMASK",
}


# make_teachables looks species up by snake-case names such as MR_MIME; za.json names some with
# punctuation or accents.
def species_key(fname: pathlib.Path, species: str) -> str:
    name = species
    if not name.isascii():
        try:
            # UTF-8 read back as Latin-1 (FLABÃ©BÃ©)
            name = name.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        name = "".join(c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c))
    key = re.sub(r"[ .-]+", "_", name.upper().replace("'", "").replace("’", "")).strip("_")
    # Anything else (♀, ?) has no snake-case spelling to fall back on
    if not re.fullmatch(r"[A-Z0-9]+(_[A-Z0-9]+)*", key):
        print(f"{fname.name}: can't make a species name of {species!r}", file=sys.stderr)
        sys.exit(1)
    return key


def from_single(fname: pathlib.Path) -> dict[str, set[str]]:
    learnables: dict[str, set[str]] = {}
    skipped = ZA_MERGED_FORMS if fname.name == "za.json" else set()
    with open(fname, "r", encoding="utf-8") as fp:
        for species, by_method in json.load(fp).items():
            key = species_key(fname, species)
            if key in skipped:
                continue
            learnables.setdefault(key, set()).update(
                [level_up["Move"] for level_up in by_method["LevelMoves"]],
                by_method["TMMoves"], by_method["EggMoves"], by_method["TutorMoves"])
    return learnables


def from_batch(dir: pathlib.Path) -> dict[str, set[str]]:
    return reduce(
        lambda acc, single: {
            species: acc.get(species, set()) | single.get(species, set())
            for species in acc.keys() | single.keys()
        },
        map(from_single, dir.glob("*.json")),
        {},
    )


def main():
    if len(sys.argv) < 3:
        print("Missing required arguments", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        quit(1)

    INPUTS_DIR = pathlib.Path(sys.argv[1])
    OUTPUT_FILE = pathlib.Path(sys.argv[2])

    assert INPUTS_DIR.exists(), f"{INPUTS_DIR=} does not exist"
    assert INPUTS_DIR.is_dir(), f"{INPUTS_DIR=} is not a directory"
    assert OUTPUT_FILE.parent.exists(), f"parent of {OUTPUT_FILE=} does not exist"

    batch = {
        species: list(sorted(learnables))
        for species, learnables in from_batch(INPUTS_DIR).items()
    }
    with open(OUTPUT_FILE, "w") as fp:
        # from_batch's species come from a set union, whose order changes with the hash seed.
        json.dump(batch, fp, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
