"""The "not yet started" sweeps must not delete picks on a collapsed
doubleheader row, and never a pick whose own game has started.

THE CASE (2026-09-25, read from prod picks_log / live_game_state). BAL@NYY
game 1 and game 2 shared one games row, MLB_2026-09-25_BAL_NYY. Game 1 went
'Final' at 22:54:55Z (BAL 10, NYY 2) and that final was on the row; the row's
commence_time had been re-stamped to game 2's 23:30Z. The moneyline NONE pair
2911172 / 2911173 (game_time 23:30Z, created 23:08:21Z) was deleted at
23:29:22.988391Z -- 7:29 PM ET -- by the non-BET housekeeping sweep in
models/scorer.run_scorer ("Cleared unsettled picks for games not yet
started"), because 23:30 > now. Non-BET rows are deleted and re-scored every
pass by design, but the scoring loop reads only games with home_score IS
NULL, so this row was never re-scored and the pair never came back (no
mlb_moneyline row exists on that id afterwards).

The fix adds two guards to every such sweep: the games row must not carry a
final, and the pick's OWN game_time must be in the future. The tests run the
exact statements from models/scorer.py on SQLite.
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.db_setup import SCHEMA_SQL  # noqa: E402

SRC = (ROOT / "models" / "scorer.py").read_text(encoding="utf-8")
DATE = "2026-09-25"
HORIZON = "2026-10-02"
AT_7_29_PM_ET = "2026-09-25T23:29:22.988391+00:00"
PICK_GUARD = "AND (game_time IS NULL OR game_time > %s)"
ROW_GUARD = "AND home_score IS NULL"


def _sql_between(start: str, end: str) -> str:
    i = SRC.index(start)
    block = SRC[i:SRC.index(end, i)]
    return re.search(r'"""(.*?)"""', block, re.S).group(1)


def non_bet_sweep() -> str:
    return _sql_between(
        "# Housekeeping for the pairs the lock deliberately leaves open.",
        'logger.info(f"Cleared unsettled picks')


def unpriced_bet_sweep() -> str:
    return _sql_between(
        "# Scoped to games that have not started, so nothing settleable is ever",
        "locked_pairs: set[tuple] = set()")


def _before_the_fix(sql: str) -> str:
    """The statement as it ran at 23:29:22Z: neither guard."""
    out = sql.replace(PICK_GUARD, "").replace(ROW_GUARD, "")
    assert out != sql
    return out


@pytest.fixture
def db():
    c = sqlite3.connect(":memory:")
    c.executescript(SCHEMA_SQL)
    for col in ("player_id TEXT", "is_live BOOLEAN DEFAULT 0"):
        try:
            c.execute(f"ALTER TABLE picks ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass
    yield c
    c.close()


def _game(db, gid, commence, home_score=None, away_score=None):
    db.execute("""INSERT INTO games (game_id, sport, season, game_date,
                  home_team, away_team, commence_time, home_score, away_score)
                  VALUES (?, 'MLB', 2026, ?, 'NYY', 'BAL', ?, ?, ?)""",
               (gid, DATE, commence, home_score, away_score))


def _pick(db, gid, game_time, signal="NONE", side="home", dk_odds=-107.0,
          created="2026-09-25T23:08:21+00:00", pick_id=None):
    db.execute("""INSERT INTO picks (pick_id, game_id, model_id, sport,
                  game_date, game_time, pick_side, pick_label,
                  model_probability, dk_implied_prob, edge, dk_odds,
                  kelly_fraction, recommended_bet, bankroll_at_pick,
                  signal_type, created_at)
                  VALUES (?, ?, 'mlb_moneyline', 'MLB', ?, ?, ?, 'NYY ML',
                          0.5, 0.5, 0.0, ?, 0.0, 0.0, 1000.0, ?, ?)""",
               (pick_id, gid, DATE, game_time, side, dk_odds, signal, created))
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def _run(db, sql, params):
    db.execute(sql.replace("%s", "?"), params)


def _alive(db, pid) -> bool:
    return db.execute("SELECT 1 FROM picks WHERE pick_id = ?",
                      (pid,)).fetchone() is not None


def _collapsed_row(db):
    """MLB_2026-09-25_BAL_NYY at 23:29Z: game 1's final, game 2's start."""
    _game(db, "MLB_2026-09-25_BAL_NYY", "2026-09-25T23:30:00+00:00", 2, 10)


# ── the non-BET sweep (the one that deleted 2911172) ──────────────────────────

def test_both_guards_are_in_the_live_sweeps():
    for name, sql in (("non-BET", non_bet_sweep()),
                      ("unpriced BET", unpriced_bet_sweep())):
        assert PICK_GUARD in sql, name
        assert ROW_GUARD in sql, name


def test_2911172_is_reproduced_by_the_statement_as_it_ran(db):
    _collapsed_row(db)
    a = _pick(db, "MLB_2026-09-25_BAL_NYY", "2026-09-25T23:30:00+00:00",
              pick_id=2911172)
    b = _pick(db, "MLB_2026-09-25_BAL_NYY", "2026-09-25T23:30:00+00:00",
              side="away", pick_id=2911173)
    _run(db, _before_the_fix(non_bet_sweep()), (DATE, HORIZON, AT_7_29_PM_ET))
    assert not _alive(db, a) and not _alive(db, b)


def test_2911172_survives_the_fixed_sweep(db):
    _collapsed_row(db)
    a = _pick(db, "MLB_2026-09-25_BAL_NYY", "2026-09-25T23:30:00+00:00",
              pick_id=2911172)
    b = _pick(db, "MLB_2026-09-25_BAL_NYY", "2026-09-25T23:30:00+00:00",
              side="away", pick_id=2911173)
    _run(db, non_bet_sweep(), (AT_7_29_PM_ET, DATE, HORIZON, AT_7_29_PM_ET))
    assert _alive(db, a) and _alive(db, b)


def test_a_pick_whose_own_game_started_is_never_deleted_as_not_started(db):
    """Game 1 in progress, no final yet, row commence re-stamped to game 2's
    23:30Z: the game-1 pick (game_time 20:05Z) is past its start at 21:00Z."""
    _game(db, "MLB_2026-09-25_BAL_NYY", "2026-09-25T23:30:00+00:00")
    pid = _pick(db, "MLB_2026-09-25_BAL_NYY", "2026-09-25T20:05:00+00:00",
                created="2026-09-25T14:00:00+00:00")
    now = "2026-09-25T21:00:00+00:00"
    _run(db, _before_the_fix(non_bet_sweep()), (DATE, HORIZON, now))
    assert not _alive(db, pid)                       # what it used to do
    pid = _pick(db, "MLB_2026-09-25_BAL_NYY", "2026-09-25T20:05:00+00:00",
                created="2026-09-25T14:00:00+00:00")
    _run(db, non_bet_sweep(), (now, DATE, HORIZON, now))
    assert _alive(db, pid)


def test_a_game_two_pick_on_its_own_id_is_still_refreshed(db):
    """With the _G2 id, game 2's row has no final and its own start: its
    pregame NONE rows are still cleared for re-scoring, as designed."""
    _game(db, "MLB_2026-09-25_BAL_NYY", "2026-09-25T20:05:00+00:00", 2, 10)
    _game(db, "MLB_2026-09-25_BAL_NYY_G2", "2026-09-25T23:30:00+00:00")
    g2 = _pick(db, "MLB_2026-09-25_BAL_NYY_G2", "2026-09-25T23:30:00+00:00")
    g1 = _pick(db, "MLB_2026-09-25_BAL_NYY", "2026-09-25T20:05:00+00:00",
               created="2026-09-25T14:00:00+00:00")
    _run(db, non_bet_sweep(), (AT_7_29_PM_ET, DATE, HORIZON, AT_7_29_PM_ET))
    assert not _alive(db, g2)
    assert _alive(db, g1)


def test_a_bet_is_never_touched_by_the_non_bet_sweep(db):
    _game(db, "MLB_2026-09-25_BAL_NYY_G2", "2026-09-25T23:30:00+00:00")
    pid = _pick(db, "MLB_2026-09-25_BAL_NYY_G2", "2026-09-25T23:30:00+00:00",
                signal="BET")
    _run(db, non_bet_sweep(), (AT_7_29_PM_ET, DATE, HORIZON, AT_7_29_PM_ET))
    assert _alive(db, pid)


# ── the unpriced-BET sweep (same shape, same guards) ──────────────────────────

def test_unpriced_bet_on_a_collapsed_row_with_a_final_survives(db):
    _collapsed_row(db)
    pid = _pick(db, "MLB_2026-09-25_BAL_NYY", "2026-09-25T23:30:00+00:00",
                signal="BET", dk_odds=None)
    _run(db, _before_the_fix(unpriced_bet_sweep()), (DATE, AT_7_29_PM_ET))
    assert not _alive(db, pid)                       # what it used to do
    pid = _pick(db, "MLB_2026-09-25_BAL_NYY", "2026-09-25T23:30:00+00:00",
                signal="BET", dk_odds=None)
    _run(db, unpriced_bet_sweep(), (DATE, AT_7_29_PM_ET, AT_7_29_PM_ET))
    assert _alive(db, pid)


def test_unpriced_bet_on_a_game_not_started_is_still_released(db):
    _game(db, "MLB_2026-09-25_BAL_NYY_G2", "2026-09-25T23:30:00+00:00")
    pid = _pick(db, "MLB_2026-09-25_BAL_NYY_G2", "2026-09-25T23:30:00+00:00",
                signal="BET", dk_odds=None)
    _run(db, unpriced_bet_sweep(), (DATE, AT_7_29_PM_ET, AT_7_29_PM_ET))
    assert not _alive(db, pid)


def test_the_lock_off_sweeps_carry_the_same_guards():
    """The broad same-day delete and the UFC look-ahead only run with
    LOCK_GAME_PICKS_AT_FIRST_RUN off, but they delete BETs too."""
    body = SRC[SRC.index("if not LOCK_GAME_PICKS_AT_FIRST_RUN:"):
               SRC.index("all_picks = []")]
    stmts = re.findall(r'"""(.*?)"""', body, re.S)
    deletes = [s for s in stmts if "DELETE FROM picks" in s]
    assert len(deletes) == 2
    for sql in deletes:
        assert PICK_GUARD in sql and ROW_GUARD in sql
