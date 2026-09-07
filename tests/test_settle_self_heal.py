"""
Settlement reaches every stranded pick, not just the last fortnight.

mike, 2026-09-07: *"why are there unsettled picks across the board? they
should be settled ... what causes unsettled picks"*. Sixteen BETs with a
game_date before today had no result. Each fell through a FIXED window:

* ATL ML F5, 2026-06-16 (pick 304636): both F5 scores in the games row, but
  the final landed on 2026-09-01 -- after the 14-day game-level window had
  closed over June. The prop path had a self-healing probe; the game path
  did not.
* 2026-07-12, five prop BETs: all 15 games that day have no final and no box
  score. `settle_picks` fetches finals for the trailing 5 days only, so a
  day the fetch missed ages out and stays PENDING for good.
* SF@ATL 2026-06-16, two prop BETs: scored, but no player_game_log rows and
  nothing that would ever fetch them -- the daily game-log step ingests
  yesterday only.
* NYM@LAD 2026-04-16 and CLE@CIN 2026-07-27: no final, the other games that
  day all scored. A game not played on its date never settles.

Every test here fails on the pre-2026-09-07 code, and each says how.
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
    """Minimal DBConnection stand-in: converts %s placeholders to sqlite's ?."""

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


def _game(raw, gid, date, home="ATL", away="SF", home_score=None,
          away_score=None, f5=(None, None), sport="MLB"):
    raw.execute("""INSERT INTO games (game_id, sport, season, game_date,
                   home_team, away_team, home_score, away_score, home_win,
                   home_score_f5, away_score_f5)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (gid, sport, int(date[:4]), date, home, away, home_score,
                 away_score,
                 None if home_score is None else int(home_score > away_score),
                 f5[0], f5[1]))


def _pick(raw, gid, date, model, *, side="home", sport="MLB", signal="BET",
          result=None, odds=-166.0, line=None):
    raw.execute("""INSERT INTO picks (game_id, model_id, sport, game_date,
                   pick_side, pick_label, model_probability, dk_implied_prob,
                   edge, dk_odds, scored_line, kelly_fraction, recommended_bet,
                   bankroll_at_pick, signal_type, result)
                   VALUES (?,?,?,?,?,?,0.6,0.5,0.1,?,?,0.02,20.0,1000.0,?,?)""",
                (gid, model, sport, date, side, f"{model} {side}", odds, line,
                 signal, result))
    return raw.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── the game-level window heals like the prop window ─────────────────────────

def test_the_game_window_reaches_the_oldest_scored_unsettled_bet(raw, conn):
    _game(raw, "MLB_2026-06-16_SF_ATL", "2026-06-16", home_score=2, away_score=7)
    _pick(raw, "MLB_2026-06-16_SF_ATL", "2026-06-16", "mlb_f5_moneyline")
    # 2026-06-16 .. 2026-09-06 inclusive is 83 days
    assert pt._game_settle_window_days(conn, "2026-09-06") == 83


def test_the_game_window_stays_fixed_when_nothing_is_stranded(raw, conn):
    assert pt._game_settle_window_days(conn, "2026-09-06") == pt._GAME_SETTLE_WINDOW_DAYS


def test_the_game_window_ignores_prop_ufc_and_golf_picks(raw, conn):
    """Those settle through their own paths; a stranded prop must not widen
    the game-level loop."""
    _game(raw, "MLB_2026-06-16_SF_ATL", "2026-06-16", home_score=2, away_score=7)
    _pick(raw, "MLB_2026-06-16_SF_ATL", "2026-06-16", "mlb_prop_batter_hr")
    _pick(raw, "MLB_2026-06-16_SF_ATL", "2026-06-16", "ufc_moneyline")
    _pick(raw, "MLB_2026-06-16_SF_ATL", "2026-06-16", "golf_outright")
    assert pt._game_settle_window_days(conn, "2026-09-06") == pt._GAME_SETTLE_WINDOW_DAYS


def test_the_game_window_ignores_unscored_games(raw, conn):
    """No final, nothing to grade - the window must not stretch for it."""
    _game(raw, "MLB_2026-07-12_COL_SF", "2026-07-12", home="SF", away="COL")
    _pick(raw, "MLB_2026-07-12_COL_SF", "2026-07-12", "mlb_over_under", line=8.5)
    assert pt._game_settle_window_days(conn, "2026-09-06") == pt._GAME_SETTLE_WINDOW_DAYS


def test_the_game_window_is_capped(raw, conn):
    _game(raw, "MLB_2024-04-01_SF_ATL", "2024-04-01", home_score=2, away_score=7)
    _pick(raw, "MLB_2024-04-01_SF_ATL", "2024-04-01", "mlb_moneyline")
    assert pt._game_settle_window_days(conn, "2026-09-06") == pt._GAME_SETTLE_MAX_HEAL_DAYS


def test_the_stranded_f5_pick_actually_grades(raw, conn):
    """The production case end to end: pick 304636's shape. On the pre-fix
    code the 14-day loop never visits 2026-06-16 and the row stays NULL."""
    _game(raw, "MLB_2026-06-16_SF_ATL", "2026-06-16",
          home_score=2, away_score=7, f5=(2, 5))
    pid = _pick(raw, "MLB_2026-06-16_SF_ATL", "2026-06-16", "mlb_f5_moneyline")
    pt._settle_game_picks_window(conn, "2026-09-06", "2026-09-07T12:00:00-04:00")
    result, flat = raw.execute(
        "SELECT result, profit_flat FROM picks WHERE pick_id = ?", (pid,)).fetchone()
    assert result == "LOSS" and flat == -100.0


# ── old unscored dates are fetched again ─────────────────────────────────────

def test_unscored_dates_with_pending_bets_are_found_oldest_first(raw, conn):
    _game(raw, "MLB_2026-07-12_COL_SF", "2026-07-12", home="SF", away="COL")
    _pick(raw, "MLB_2026-07-12_COL_SF", "2026-07-12", "mlb_prop_pitcher_walks")
    _game(raw, "MLB_2026-04-16_NYM_LAD", "2026-04-16", home="LAD", away="NYM")
    _pick(raw, "MLB_2026-04-16_NYM_LAD", "2026-04-16", "mlb_over_under", line=7.5)
    assert pt._unscored_mlb_dates_with_pending_bets(conn, "2026-09-06") == \
        ["2026-04-16", "2026-07-12"]


def test_dates_inside_the_per_pass_fetch_window_are_left_to_it(raw, conn):
    _game(raw, "MLB_2026-09-04_SF_ATL", "2026-09-04")
    _pick(raw, "MLB_2026-09-04_SF_ATL", "2026-09-04", "mlb_moneyline")
    assert pt._unscored_mlb_dates_with_pending_bets(conn, "2026-09-06") == []


def test_settled_scored_and_non_mlb_rows_do_not_trigger_a_fetch(raw, conn):
    _game(raw, "MLB_2026-07-01_SF_ATL", "2026-07-01", home_score=1, away_score=0)
    _pick(raw, "MLB_2026-07-01_SF_ATL", "2026-07-01", "mlb_moneyline")
    _game(raw, "MLB_2026-07-02_SF_ATL", "2026-07-02")
    _pick(raw, "MLB_2026-07-02_SF_ATL", "2026-07-02", "mlb_moneyline", result="WIN")
    _game(raw, "NCAAF_2026-07-03_a_b", "2026-07-03", sport="NCAAF")
    _pick(raw, "NCAAF_2026-07-03_a_b", "2026-07-03", "ncaaf_spread", sport="NCAAF")
    assert pt._unscored_mlb_dates_with_pending_bets(conn, "2026-09-06") == []


# ── scored games with no box score get one fetched ───────────────────────────

def test_a_scored_game_whose_props_have_no_box_score_is_found(raw, conn):
    _game(raw, "MLB_2026-06-16_SF_ATL", "2026-06-16", home_score=2, away_score=7)
    _pick(raw, "MLB_2026-06-16_SF_ATL", "2026-06-16", "mlb_prop_batter_hr", side="over", line=0.5)
    assert pt._scored_mlb_dates_missing_game_log(conn, "2026-09-06") == ["2026-06-16"]


def test_a_game_with_any_box_score_row_is_not_refetched(raw, conn):
    """A logged game with the player absent is a DNP, which the prop settler
    already handles as NO_ACTION -- refetching it would loop forever."""
    _game(raw, "MLB_2026-06-16_SF_ATL", "2026-06-16", home_score=2, away_score=7)
    _pick(raw, "MLB_2026-06-16_SF_ATL", "2026-06-16", "mlb_prop_batter_hr", side="over", line=0.5)
    raw.execute("INSERT INTO player_game_log (player_id, player_name, team, "
                "player_type, game_id, game_date, season) VALUES (?,?,?,?,?,?,?)",
                ("1", "Someone", "SF", "batter", "MLB_2026-06-16_SF_ATL",
                 "2026-06-16", 2026))
    assert pt._scored_mlb_dates_missing_game_log(conn, "2026-09-06") == []


# ── postponed games settle NO_ACTION instead of never ────────────────────────

class _FakeStatsapi:
    def __init__(self, games):
        self.games = games

    def schedule(self, date, sportId=1):     # noqa: N803 - statsapi's signature
        return self.games


def _use_statsapi(monkeypatch, games):
    monkeypatch.setattr(pt, "STATSAPI_AVAILABLE", True)
    monkeypatch.setattr(pt, "statsapi", _FakeStatsapi(games), raising=False)


def test_a_postponed_game_voids_its_pending_bets(raw, conn, monkeypatch):
    _use_statsapi(monkeypatch, [{"status": "Postponed", "home_id": 119, "away_id": 121}])
    _game(raw, "MLB_2026-04-16_NYM_LAD", "2026-04-16", home="LAD", away="NYM")
    pid = _pick(raw, "MLB_2026-04-16_NYM_LAD", "2026-04-16", "mlb_over_under",
                side="under", line=7.5)
    assert pt._void_postponed_mlb_picks(conn, "2026-04-16", "TS", today="2026-09-07") == 1
    result, flat, kelly, at, note = raw.execute(
        "SELECT result, profit_flat, profit_kelly, settled_at, condition_note "
        "FROM picks WHERE pick_id = ?", (pid,)).fetchone()
    assert (result, flat, kelly, at) == ("NO_ACTION", 0, 0, "TS")
    assert "postponed" in note


def test_a_final_game_is_never_voided(raw, conn, monkeypatch):
    _use_statsapi(monkeypatch, [{"status": "Final", "home_id": 119, "away_id": 121}])
    _game(raw, "MLB_2026-04-16_NYM_LAD", "2026-04-16", home="LAD", away="NYM")
    pid = _pick(raw, "MLB_2026-04-16_NYM_LAD", "2026-04-16", "mlb_over_under", line=7.5)
    assert pt._void_postponed_mlb_picks(conn, "2026-04-16", "TS", today="2026-09-07") == 0
    assert raw.execute("SELECT result FROM picks WHERE pick_id = ?", (pid,)).fetchone()[0] is None


def test_a_recent_postponement_waits_for_a_same_day_resumption(raw, conn, monkeypatch):
    _use_statsapi(monkeypatch, [{"status": "Postponed", "home_id": 119, "away_id": 121}])
    _game(raw, "MLB_2026-09-06_NYM_LAD", "2026-09-06", home="LAD", away="NYM")
    _pick(raw, "MLB_2026-09-06_NYM_LAD", "2026-09-06", "mlb_over_under", line=7.5)
    assert pt._void_postponed_mlb_picks(conn, "2026-09-06", "TS", today="2026-09-07") == 0


def test_a_doubleheader_row_with_a_final_keeps_its_picks_grading(raw, conn, monkeypatch):
    """Game 2 postponed, game 1 played: same game_id, and game 1's final is in
    the row. The void must not touch a row that has a score."""
    _use_statsapi(monkeypatch, [{"status": "Final", "home_id": 119, "away_id": 121},
                                {"status": "Postponed", "home_id": 119, "away_id": 121}])
    _game(raw, "MLB_2026-04-16_NYM_LAD", "2026-04-16", home="LAD", away="NYM",
          home_score=4, away_score=2)
    pid = _pick(raw, "MLB_2026-04-16_NYM_LAD", "2026-04-16", "mlb_over_under", line=7.5)
    assert pt._void_postponed_mlb_picks(conn, "2026-04-16", "TS", today="2026-09-07") == 0
    assert raw.execute("SELECT result FROM picks WHERE pick_id = ?", (pid,)).fetchone()[0] is None


def test_no_statsapi_means_no_void(raw, conn, monkeypatch):
    monkeypatch.setattr(pt, "STATSAPI_AVAILABLE", False)
    _game(raw, "MLB_2026-04-16_NYM_LAD", "2026-04-16", home="LAD", away="NYM")
    _pick(raw, "MLB_2026-04-16_NYM_LAD", "2026-04-16", "mlb_over_under", line=7.5)
    assert pt._void_postponed_mlb_picks(conn, "2026-04-16", "TS", today="2026-09-07") == 0


# ── the heal is wired into settle_picks ──────────────────────────────────────

def test_settle_picks_calls_the_heal_and_the_ncaaf_mirror():
    src = Path(pt.__file__).read_text(encoding="utf-8")
    body = src[src.index("def settle_picks("):src.index("def print_performance_summary(")]
    assert "_heal_stranded_mlb(conn, game_date, settled_at)" in body
    assert "mirror_stored_finals(conn, game_date)" in body
    assert "_void_postponed_mlb_picks(conn, _d, settled_at)" in body


# ── NFL props are the prop settler's, not the game path's ────────────────────

def test_an_nfl_prop_pick_on_a_scored_game_is_left_for_the_prop_settler(raw, conn):
    """Found while tracing the unsettled picks: nfl_prop_% joined the prop
    settler without joining the game path's exclusion list. Eighteen NFL prop
    BETs were queued for 2026-09-13; on the first Sunday with finals the game
    path would run first, map them to 'h2h' and stamp NO_ACTION - and the prop
    settler only touches result IS NULL, so they would never have graded."""
    _game(raw, "NFL_2026_01_TB_CIN", "2026-09-13", home="CIN", away="TB",
          home_score=27, away_score=20, sport="NFL")
    pid = _pick(raw, "NFL_2026_01_TB_CIN", "2026-09-13", "nfl_prop_rec_yards",
                side="over", sport="NFL", line=62.5)
    pt._settle_game_picks(conn, "2026-09-13", "TS")
    assert raw.execute("SELECT result FROM picks WHERE pick_id = ?",
                       (pid,)).fetchone()[0] is None
