"""Both unstarted non-BET clears must keep nfl_prop_% rows when executed.

Ported from the SQL-exec coverage on draft #814. The NFL→NHL fallthrough
skip (an NFL game `continue`s before the feature builder) stays pinned in
`tests/test_game_scorer_spares_nfl_props.py`. These tests execute the two
DELETE statements that remain after that skip.

The sweep is the statement that still sees an NFL game: the loop no longer
marks it `rescored`. The per-game DELETE is the statement that wiped
NFL_2026_02_NYG_LA on 2026-09-21 while the game still fell through to the
NHL feature builder. Both have to exclude `nfl_prop_%`.

Wind and opener are not `nfl_prop_%`, so their unsettled NONE rows are
still cleared. A BET is already spared by `signal_type != 'BET'`.

On SQL without `model_id NOT LIKE 'nfl_prop_%'` the nfl_prop NONE row is
deleted and these tests fail.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "models" / "scorer.py").read_text(encoding="utf-8")

# 6:06 PM ET on 2026-09-21. Kickoff 8:15 PM ET is still in the future.
NOW = "2026-09-21T22:06:00+00:00"
KICK = "2026-09-22T00:15:00+00:00"
GAME = "NFL_2026_02_NYG_LA"
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
    """The full-board sweep. `_scope()` and the rescored exclusion are
    empty when the pass has no subset and the loop did not re-score the
    game, which is the evening-refresh case for an NFL game the loop skips.
    """
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
    (GAME, "nfl_wind_totals", "NONE", None, None),
]

_KEPT = {
    ("nfl_prop_pass_yards", "NONE"),
    ("nfl_prop_receptions", "AVOID"),
    ("nfl_prop_market", "NONE"),
    ("nfl_prop_pass_yards", "BET"),
}

_CLEARED = {
    ("mlb_moneyline", "NONE"),
    ("nfl_opener_spread", "NONE"),
    ("nfl_wind_totals", "NONE"),
}


def _assert_split(left: list[tuple]) -> None:
    kept = {row[0:2] for row in left}
    for row in _KEPT:
        assert row in kept
    for row in _CLEARED:
        assert row not in kept


def test_sweep_keeps_unstarted_nfl_prop_nones_and_still_clears_game_nones():
    """The DELETE beside the 6:06 PM log line. A full-board pass has no
    subset and, for a game the loop did not re-score, no rescored exclusion.
    """
    _assert_split(_apply(_sweep_sql(), (DATE, HORIZON, NOW), _ROWS))


def test_per_game_clear_keeps_nfl_prop_rows_on_a_game_the_loop_reaches():
    """The per-game DELETE. After the NFL continue, today's MNF game does
    not reach it. The clause still has to be here: that is the statement
    that deleted the 93 and 95 NONE rows while the game fell through.
    """
    _assert_split(_apply(_per_game_sql(), (GAME,), _ROWS))


def test_both_clear_pins_are_on_the_pr_ci_subset():
    yml = (ROOT / ".github" / "workflows" / "pr-ci.yml").read_text(encoding="utf-8")
    assert "tests/test_nfl_prop_unstarted_clear.py" in yml
    assert "tests/test_game_scorer_spares_nfl_props.py" in yml
