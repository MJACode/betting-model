"""The evening refresh must not wipe pre-kick NFL prop NONE/AVOID rows.

MNF 2026-09-21 (NYG@LA). nfl-prop-scoring had written 1697 NFL NONE rows
through ~5:26 PM ET and 0 BETs. The 6:06 PM ET evening refresh logged
"Cleared unsettled picks for games not yet started" and those rows were
deleted. refresh_pass runs run_scorer and does not re-run nfl-prop-scoring,
so nothing put them back.

run_scorer clears unsettled non-BET rows for games that have not started.
That clear is two statements:

* the per-game DELETE, for a game the loop reaches;
* the housekeeping sweep beside the log line, for every other unstarted
  game in the look-ahead window.

An NFL game on today's slate reaches the per-game DELETE: the sport falls
through to the NHL feature builder, which returns a dict, MODELS has no NFL
game model, and the DELETE still runs. The game is then added to `rescored`,
so the sweep's `NOT IN rescored` never sees those rows. Future NFL dates are
not in the loop at all, so only the sweep touches them. Both statements have
to exclude nfl_prop_%.

This test executes those two statements. On the pre-fix SQL the nfl_prop
NONE row is deleted and the test fails.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "models" / "scorer.py").read_text(
    encoding="utf-8")

# 6:06 PM ET on 2026-09-21. Kickoff 8:15 PM ET is still in the future.
NOW = "2026-09-21T22:06:00+00:00"
KICK = "2026-09-22T00:15:00+00:00"
GAME = "NFL_2026_NYG_LA"
DATE = "2026-09-21"
HORIZON = "2026-09-28"


def _between(start: str, end: str) -> str:
    i = SRC.index(start)
    return SRC[i:SRC.index(end, i)]


def _first_sql(block: str) -> str:
    return re.search(r'"""(.*?)"""', block, re.S).group(1)


def _per_game_sql() -> str:
    block = _between(
        "ONE GAME = ONE TRANSACTION",
        "for model_id in relevant_models:",
    )
    return _first_sql(block)


def _sweep_sql() -> str:
    block = _between(
        "# Housekeeping for the pairs the lock deliberately leaves open.",
        'logger.info(f"Cleared unsettled picks',
    )
    return _first_sql(block)


def _apply(sql: str, params: tuple, rows: list[tuple]) -> list[tuple]:
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE picks (
            pick_id INTEGER PRIMARY KEY,
            game_id TEXT,
            model_id TEXT,
            signal_type TEXT,
            result TEXT,
            is_live INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE games (
            game_id TEXT,
            game_date TEXT,
            commence_time TEXT
        )
    """)
    conn.execute(
        "INSERT INTO games (game_id, game_date, commence_time) VALUES (?, ?, ?)",
        (GAME, DATE, KICK),
    )
    conn.executemany(
        "INSERT INTO picks (game_id, model_id, signal_type, result, is_live) "
        "VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.execute(sql.replace("%s", "?"), params)
    return conn.execute(
        "SELECT model_id, signal_type FROM picks ORDER BY model_id, signal_type"
    ).fetchall()


_ROWS = [
    (GAME, "nfl_prop_pass_yards", "NONE", None, None),
    (GAME, "nfl_prop_receptions", "AVOID", None, None),
    (GAME, "nfl_prop_market", "NONE", None, None),
    (GAME, "nfl_prop_pass_yards", "BET", None, None),
    (GAME, "mlb_moneyline", "NONE", None, None),
    (GAME, "nfl_opener_spread", "NONE", None, None),
]


def test_sweep_keeps_unstarted_nfl_prop_nones_and_still_clears_game_nones():
    """The DELETE beside the 6:06 PM log line. A full-board pass has no
    subset and, for a game the loop did not re-score, no rescored exclusion.
    """
    left = _apply(
        _sweep_sql(),
        (DATE, HORIZON, NOW),
        _ROWS,
    )
    kept = {row[0:2] for row in left}
    assert ("nfl_prop_pass_yards", "NONE") in kept
    assert ("nfl_prop_receptions", "AVOID") in kept
    assert ("nfl_prop_market", "NONE") in kept
    assert ("nfl_prop_pass_yards", "BET") in kept
    assert ("mlb_moneyline", "NONE") not in kept


def test_per_game_clear_keeps_nfl_prop_rows_on_a_game_the_loop_reaches():
    """Today's MNF game is in the scoring loop. The per-game DELETE runs,
    then the game is marked rescored and the sweep skips it. Excluding
    nfl_prop_% only on the sweep would not have saved these rows.
    """
    left = _apply(_per_game_sql(), (GAME,), _ROWS)
    kept = {row[0:2] for row in left}
    assert ("nfl_prop_pass_yards", "NONE") in kept
    assert ("nfl_prop_receptions", "AVOID") in kept
    assert ("nfl_prop_market", "NONE") in kept
    assert ("nfl_prop_pass_yards", "BET") in kept
    assert ("mlb_moneyline", "NONE") not in kept
