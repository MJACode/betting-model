"""The game scorer's non-BET clear must not erase unsettled NFL props.

Measured 2026-09-21, NYG @ LA (game_date 2026-09-21, kickoff 00:15 UTC
on the 22nd). The NFL prop scorer wrote NONE rows all day. The evening
refresh's game scorer then logged "Cleared unsettled picks for games not
yet started" and picks_log showed 1,697 NFL NONE inserts followed by
1,697 deletes. config.MODELS has no NFL game model, so this loop never
re-inserts those rows. The next refresh deletes them again. Today goes
empty while the game has not kicked.

Two clears, both live with the lock on:
  * the per-game DELETE inside the scoring loop (an NFL game used to fall
    through to the NHL feature builder, which returns a dict, so the
    DELETE ran)
  * the housekeeping sweep after the loop, for games the loop did not
    re-score

BET rows are already spared (signal_type != 'BET'). The locked
exclusion is `model_id NOT LIKE 'nfl_prop_%'` on both clears (LIKE '_'
is one character, so this is the nfl_prop_ prefix, including
nfl_prop_market). An NFL game must not enter the loop: the NHL feature
builder returns a dict, the per-game DELETE would run, and `rescored`
would then hide the game from the sweep.
"""
from __future__ import annotations

from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "models" / "scorer.py").read_text(
    encoding="utf-8")


def _between(a: str, b: str) -> str:
    i = SRC.index(a)
    return SRC[i:SRC.index(b, i)]


def _run_scorer_body() -> str:
    return _between("def run_scorer(", "def _get_current_bankroll(")


def test_an_nfl_game_never_enters_the_per_game_clear():
    body = _run_scorer_body()
    loop = body[body.index("for game in games:"):body.index("ONE GAME = ONE TRANSACTION")]
    assert 'sport == "NFL"' in loop
    assert "continue" in loop.split('sport == "NFL"', 1)[1][:400]


def test_both_live_non_bet_clears_leave_nfl_rows():
    body = _run_scorer_body()
    per_game = _between("ONE GAME = ONE TRANSACTION",
                        "# Housekeeping for the pairs the lock deliberately leaves open.")
    sweep = _between("# Housekeeping for the pairs the lock deliberately leaves open.",
                     'logger.info(f"Cleared unsettled picks')
    for name, block in (("per-game", per_game), ("sweep", sweep)):
        assert "DELETE FROM picks" in block, name
        assert "signal_type != 'BET'" in block, name
        assert "model_id NOT LIKE 'nfl_prop_%'" in block, (
            f"the {name} clear still deletes unsettled nfl_prop_% rows "
            f"on a game that has not kicked")
