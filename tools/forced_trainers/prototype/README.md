# Prototype (throwaway)

Scratch scripts from the balance rework's design session (`docs/superpowers/specs/2026-11-13-balance-rework-design.md`), kept here so PR 1 can build the real tool from them. Not run by CI, not tested, and their paths are hardcoded for the session that wrote them.

- `classify.py` (with `engine.py` and `specs.py`): the forced-trainer grid search. It writes `trainers.json`, and `summary.txt` is its run summary. `dbg.py`, `dump.py`, `ports.py`, `pessimistic.py` and `render.py` are its debugging aids.
- `model/`: the curve explorations, run from the repo root.
  - `scenarios.py`: today's data with both players.
  - `grid.py` and `grid2.py`: the spread under 1.5x trainer exp, trainer raises, exp scaling and the penalty.
  - `solo.py`: each starter's solo wall levels.
  - `grind.py`: the KOs it takes to reach them.
  - They expect `trainers.json` at `../unavoidable/trainers.json`, relative to the script.
