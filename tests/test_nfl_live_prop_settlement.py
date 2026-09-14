"""
The NFL live pass-attempts lane never graded a bet.

mike, 2026-09-13: "Is the live nfl prop model working". It was writing and
announcing BETs, but all five it had ever written were settled NO_ACTION at
0.0 units. Three separate faults, each enough on its own:

1. ROUTING. The prop settler picks up `nfl_prop_%`; the lane's model id is
   `nfl_live_prop`, which that pattern does not match. So the GAME settler took
   it, `_market_for_pick` fell back to 'h2h', an 'over' has no h2h meaning, and
   the row was stamped NO_ACTION the moment the game had a final. Burrow and
   Mayfield (TB @ CIN, 2026-09-13) were stamped at 16:25 ET with no box score
   in the table at all -- only the game path can do that.
2. NAME KEY. The lane stores player_key as "DRAKE MAYE"; the settler's actuals
   are keyed on norm_player_name, "drakemaye". The lookup missed every time.
3. DATE. The lane stamps game_date from the decision's UTC clock, so a
   Wednesday-night bet on NE @ SEA (2026-09-09) is dated 2026-09-10 and the
   settler, loading box scores for the pick's date only, never saw the game.

Real shapes: picks 1912001 (Maye Over 27.5, 33 attempts) and 1968512
(Stafford Over 34.5, 25 attempts). Every test here fails on the pre-fix code.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.db_setup import SCHEMA_SQL
from tracking import paper_tracker as pt


class _SqliteShim:
    def __init__(self, conn):
        self._c = conn

    def execute(self, sql, params=None):
        return self._c.execute(sql.replace("%s", "?"), params or [])

    def commit(self):
        self._c.commit()

    def rollback(self):
        self._c.rollback()


@pytest.fixture
def raw():
    c = sqlite3.connect(":memory:")
    c.executescript(SCHEMA_SQL)
    c.execute("ALTER TABLE picks ADD COLUMN player_id TEXT")
    c.execute("ALTER TABLE picks ADD COLUMN is_live BOOLEAN DEFAULT 0")
    yield c
    c.close()


@pytest.fixture
def conn(raw):
    return _SqliteShim(raw)


def _game(raw, gid, date, home, away, home_score, away_score):
    raw.execute("""INSERT INTO games (game_id, sport, season, game_date,
                   home_team, away_team, home_score, away_score, home_win)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (gid, "NFL", 2026, date, home, away, home_score, away_score,
                 int(home_score > away_score)))


def _live_bet(raw, gid, pick_date, player, line, odds):
    """The row nfl/live_model/pick_writer.build_pick writes."""
    key = " ".join(player.replace(".", "").replace("'", "").split()).upper()
    raw.execute("""INSERT INTO picks (game_id, model_id, sport, game_date,
                   pick_side, pick_label, model_probability, dk_implied_prob,
                   edge, dk_odds, scored_line, kelly_fraction, recommended_bet,
                   bankroll_at_pick, signal_type, prop_market, player_key,
                   player_id, is_live)
                   VALUES (?,'nfl_live_prop','NFL',?,'over',?,0.6003,0.5349,
                           0.0654,?,?,0.01,10.0,1000.0,'BET',
                           'player_pass_attempts',?,?,1)""",
                (gid, pick_date, f"{player} Over {line} Pass Attempts", odds,
                 line, key, key))
    return raw.execute("SELECT last_insert_rowid()").fetchone()[0]


def _box(raw, gid, date, player, team, attempts):
    raw.execute("""INSERT INTO nfl_player_game_log (player_id, player_name, team,
                   game_id, game_date, season, attempts)
                   VALUES (?,?,?,?,?,2026,?)""",
                (player.lower(), player, team, gid, date, attempts))


def _row(raw, pid):
    return raw.execute("SELECT result, profit_flat FROM picks WHERE pick_id = ?",
                       (pid,)).fetchone()


def test_the_game_path_leaves_a_live_prop_bet_alone(raw, conn):
    _game(raw, "NFL_2026_01_TB_CIN", "2026-09-13", "CIN", "TB", 33, 27)
    pid = _live_bet(raw, "NFL_2026_01_TB_CIN", "2026-09-13", "Joe Burrow", 34.5, -130.0)
    pt._settle_game_picks(conn, "2026-09-13", "TS")
    assert _row(raw, pid) == (None, None)


def test_the_game_window_is_not_stretched_by_a_live_prop_bet(raw, conn):
    _game(raw, "NFL_2026_01_TB_CIN", "2026-06-01", "CIN", "TB", 33, 27)
    _live_bet(raw, "NFL_2026_01_TB_CIN", "2026-06-01", "Joe Burrow", 34.5, -130.0)
    assert pt._game_settle_window_days(conn, "2026-09-13") == pt._GAME_SETTLE_WINDOW_DAYS


def test_the_prop_window_reaches_a_stranded_live_prop_bet(raw, conn):
    _game(raw, "NFL_2026_01_TB_CIN", "2026-06-01", "CIN", "TB", 33, 27)
    _live_bet(raw, "NFL_2026_01_TB_CIN", "2026-06-01", "Joe Burrow", 34.5, -130.0)
    assert pt._prop_settle_window_days(conn, "2026-09-13") > pt._PROP_SETTLE_WINDOW_DAYS


def test_a_same_day_live_bet_grades_against_pass_attempts(raw, conn):
    """Stafford, pick 1968512: game and pick both 2026-09-10 in the table's
    terms once dated by kickoff. Only the routing and the name key are in play."""
    _game(raw, "NFL_2026_01_SF_LA", "2026-09-10", "LA", "SF", 7, 27)
    _box(raw, "NFL_2026_01_SF_LA", "2026-09-10", "Matthew Stafford", "LA", 25)
    pid = _live_bet(raw, "NFL_2026_01_SF_LA", "2026-09-10", "Matthew Stafford", 34.5, -130.0)
    pt._settle_prop_picks(conn, "2026-09-10", "TS")
    assert _row(raw, pid) == ("LOSS", -100.0)


def test_an_evening_bet_dated_the_next_utc_day_still_finds_its_box_score(raw, conn):
    """Maye, pick 1912001: kicked off 2026-09-09 ET, bet stamped 2026-09-10 UTC."""
    _game(raw, "NFL_2026_01_NE_SEA", "2026-09-09", "SEA", "NE", 13, 10)
    _box(raw, "NFL_2026_01_NE_SEA", "2026-09-09", "Drake Maye", "NE", 33)
    pid = _live_bet(raw, "NFL_2026_01_NE_SEA", "2026-09-10", "Drake Maye", 27.5, -115.0)
    pt._settle_prop_picks(conn, "2026-09-10", "TS")
    result, flat = _row(raw, pid)
    assert result == "WIN" and flat == pytest.approx(86.96, abs=0.01)


def test_a_final_with_no_box_score_yet_waits(raw, conn):
    """Burrow and Mayfield today: final in, player log not. Neither path may
    stamp anything; the next pass after the log lands grades it."""
    _game(raw, "NFL_2026_01_TB_CIN", "2026-09-13", "CIN", "TB", 33, 27)
    pid = _live_bet(raw, "NFL_2026_01_TB_CIN", "2026-09-13", "Baker Mayfield", 31.5, -115.0)
    pt._settle_game_picks(conn, "2026-09-13", "TS")
    pt._settle_prop_picks(conn, "2026-09-13", "TS")
    assert _row(raw, pid) == (None, None)


def test_a_neighbouring_days_game_does_not_grade_the_wrong_player(raw, conn):
    """Widening the box-score load by a day must stay keyed on game_id: the same
    QB in a different game is not this bet's actual."""
    _game(raw, "NFL_2026_01_NE_SEA", "2026-09-09", "SEA", "NE", 13, 10)
    _box(raw, "NFL_2026_02_NE_MIA", "2026-09-10", "Drake Maye", "NE", 50)
    pid = _live_bet(raw, "NFL_2026_01_NE_SEA", "2026-09-10", "Drake Maye", 27.5, -115.0)
    pt._settle_prop_picks(conn, "2026-09-10", "TS")
    assert _row(raw, pid) == (None, None)
