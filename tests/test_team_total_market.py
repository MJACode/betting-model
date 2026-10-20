"""A team total settles on ONE team's points, and every server surface knows it.

nba_team_total_luck bets the HOME team's points, under (market key
'team_totals_home', the name the odds history already stores it under). Its
picks are not in config.MODELS, so each place that turns a model id into a
market has to name it, and each place that grades or labels a market has to
know what a team total is:

  * settlement (tracking/paper_tracker._compute_result): the team's own final,
    overtime included, as DraftKings settles a team total. Graded as a full-game
    total instead (home + away), every under is a loss: 134 of the 349 graded
    bets agree with that, against 349 of 349 on the home team's points
    (buildmap/grading.md 2.1, re-graded in Supabase).
  * the label (models/scorer._build_pick_label): "BOS @ MIL — MIL Team Total
    Under 115.5", so a reader cannot take it for a full-game total.
  * the line-movement check (models/scorer.check_line_movement): the SKIP on a
    line that moved against the bet reads team totals as well as totals.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import config  # noqa: E402
from data.db_setup import SCHEMA_SQL  # noqa: E402
from tracking import paper_tracker as pt  # noqa: E402

MODEL_ID = "nba_team_total_luck"
GAME_ID = "NBA_2026-04-04_SAS_DEN"


def _result(side, market, home, away, line, odds=-112, went_to_ot=0):
    """_compute_result in the argument order the settler calls it."""
    return pt._compute_result(side, market, home, away,
                              int(home > away), None, went_to_ot,
                              odds, None, line, 20.0)


# ── settlement ───────────────────────────────────────────────────────────────

def test_the_model_settles_on_the_home_team_s_points():
    assert MODEL_ID not in config.MODELS
    assert pt._RULE_MODEL_MARKETS[MODEL_ID] == "team_totals_home"
    assert pt._market_for_pick(MODEL_ID) == "team_totals_home"


def test_an_overtime_final_counts_and_a_full_game_total_would_not():
    """Home 110, away 100 after overtime, the home team's under 112.5: a WIN.
    The same pick graded as a full-game total reads 210 against 112.5 and
    loses, which is how every under would grade under 'totals'."""
    result, flat, kelly = _result("under", "team_totals_home", 110, 100, 112.5,
                                  odds=-112, went_to_ot=1)
    assert result == "WIN"
    assert flat == pytest.approx(round(100.0 * (100.0 / 112.0), 2))
    assert kelly == pytest.approx(round(20.0 * (100.0 / 112.0), 2))
    wrong, _, _ = _result("under", "totals", 110, 100, 112.5, went_to_ot=1)
    assert wrong == "LOSS"


@pytest.mark.parametrize("side,home,line,expected", [
    ("under", 114, 115.5, "WIN"),
    ("under", 117, 115.5, "LOSS"),
    ("over", 117, 115.5, "WIN"),
    ("over", 114, 115.5, "LOSS"),
    ("under", 112, 112.0, "PUSH"),    # a whole-number line, met exactly
    ("over", 112, 112.0, "PUSH"),
])
def test_the_home_team_s_points_against_the_line(side, home, line, expected):
    # The away score is far off either way, so a sum would grade differently.
    result, flat, _ = _result(side, "team_totals_home", home, 140, line)
    assert result == expected
    if expected == "PUSH":
        assert flat == 0.0
    if expected == "LOSS":
        assert flat == -100.0


def test_an_away_team_total_settles_on_the_away_team_s_points():
    assert _result("under", "team_totals_away", 130, 101, 104.5)[0] == "WIN"
    assert _result("under", "team_totals_away", 90, 108, 104.5)[0] == "LOSS"
    assert _result("over", "team_totals_away", 90, 104, 104.0)[0] == "PUSH"


def test_no_line_is_no_action_not_a_guess():
    assert _result("under", "team_totals_home", 110, 100, None)[0] == "NO_ACTION"


class _SqliteShim:
    """DBConnection stand-in: %s placeholders to sqlite's ?."""

    def __init__(self, conn):
        self._c = conn

    def execute(self, sql, params=None):
        return self._c.execute(sql.replace("%s", "?"), params or [])

    def commit(self):
        self._c.commit()


@pytest.fixture
def raw():
    c = sqlite3.connect(":memory:")
    c.executescript(SCHEMA_SQL)
    c.execute("ALTER TABLE picks ADD COLUMN player_id TEXT")
    c.execute("ALTER TABLE picks ADD COLUMN is_live BOOLEAN DEFAULT 0")
    # The stored final is overtime-inclusive: SAS @ DEN 2026-04-04 went to one
    # overtime and is stored 136-134 (36+29+27+32+12), as ESPN reports it.
    c.execute("""INSERT INTO games (game_id, sport, season, game_date, home_team,
                 away_team, home_score, away_score, home_win, went_to_ot,
                 commence_time)
                 VALUES (?, 'NBA', 2026, '2026-04-04', 'DEN', 'SAS', 136, 134, 1, 1,
                         '2026-04-05T00:00:00Z')""", (GAME_ID,))
    yield c
    c.close()


def test_the_settler_writes_the_home_team_s_result(raw):
    """End to end through _settle_game_picks: the substring that hands a
    'totals' market its line (paper_tracker, `"totals" in market`) also hands
    one to 'team_totals_home'. Under 138.5 wins on 136; as a full-game total
    (270) it would have lost."""
    raw.execute("""INSERT INTO picks (game_id, model_id, sport, game_date,
                   pick_side, pick_label, model_probability, dk_implied_prob,
                   edge, dk_odds, scored_line, kelly_fraction, recommended_bet,
                   bankroll_at_pick, signal_type)
                   VALUES (?, ?, 'NBA', '2026-04-04', 'under',
                           'SAS @ DEN — DEN Team Total Under 138.5', 0.62, 0.53,
                           0.09, -112, 138.5, 0.02, 20.0, 1000.0, 'BET')""",
                (GAME_ID, MODEL_ID))
    pt._settle_game_picks(_SqliteShim(raw), "2026-04-04", "2026-04-05T12:00:00Z")
    result, flat = raw.execute(
        "SELECT result, profit_flat FROM picks WHERE model_id = ?",
        (MODEL_ID,)).fetchone()
    assert result == "WIN"
    assert flat == pytest.approx(round(100.0 * (100.0 / 112.0), 2))


def test_the_opening_signal_shadow_track_grades_it_the_same_way(raw):
    """tracking/opening_signals settles its copy of every BET through the same
    market and result functions; its record feeds the free pick and the public
    parlay record, so it must not stamp the pick NO_ACTION."""
    from tracking.opening_signals import settle_opening_signals
    raw.execute("""INSERT INTO opening_signals (lock_key, game_id, model_id, sport,
                   game_date, pick_side, pick_label, model_probability, dk_odds,
                   scored_line, recommended_bet, locked_at)
                   VALUES (?, ?, ?, 'NBA', '2026-04-04', 'under',
                           'SAS @ DEN — DEN Team Total Under 138.5', 0.62, NULL,
                           138.5, 20.0, '2026-04-04T23:05:00Z')""",
                (f"{GAME_ID}:{MODEL_ID}", GAME_ID, MODEL_ID))
    settle_opening_signals(_SqliteShim(raw), "2026-04-04", "2026-04-05T12:00:00Z")
    assert raw.execute("SELECT result FROM opening_signals").fetchone()[0] == "WIN"


# ── the label ────────────────────────────────────────────────────────────────

def test_the_label_names_the_team_and_says_team_total():
    from models.scorer import _build_pick_label
    from tracking.pick_integrity import pick_problems
    home = _build_pick_label("under", "MIL", "BOS", "team_totals_home", 115.5)
    # The em dash (U+2014) of the NFL opener's "TB @ CAR — CAR -3 (...)".
    assert home == "BOS @ MIL — MIL Team Total Under 115.5"
    assert pick_problems(home, "under", 115.5, MODEL_ID, "MIL", "BOS") == []
    away = _build_pick_label("over", "MIL", "BOS", "team_totals_away", 104.5)
    assert away == "BOS @ MIL — BOS Team Total Over 104.5"


def test_the_full_game_total_label_is_unchanged():
    from models.scorer import _build_pick_label
    assert _build_pick_label("over", "BOS", "NYK", "totals", 225.5) == "BOS vs NYK Over 225.5"


# ── the line-movement check ──────────────────────────────────────────────────

class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _PickConn:
    """check_line_movement's one query, answered with the market its CASE
    maps the model to (pinned by test_rule_model_markets_everywhere.py)."""

    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=None):
        return _Rows(self.rows)


@pytest.mark.parametrize("market", ["team_totals_home", "totals"])
def test_a_line_that_dropped_under_an_under_is_a_skip(monkeypatch, market):
    """Under 115.5, the line now 114.5 at the same price: the bet is a point
    worse, which the check calls SKIP for a full-game total and must call SKIP
    for a team total too (it printed nothing, because the price had not moved)."""
    import models.scorer as sc
    monkeypatch.setattr(sc, "_get_dk_odds", lambda conn, gid, mkt: (
        {"total_line": 114.5, "under_price": -112, "over_price": -108}
        if mkt == market else None))
    conn = _PickConn([(1, "BOS @ MIL — MIL Team Total Under 115.5", "under",
                       MODEL_ID, "NBA_2026-11-01_BOS_MIL", -112, 115.5, market)])
    warnings = sc.check_line_movement(conn, "2026-11-01")
    assert [w["status"] for w in warnings] == ["SKIP"]
    assert "worse for Under" in warnings[0]["detail"]


def test_the_first_five_totals_are_not_newly_line_checked(monkeypatch):
    """The SKIP names its markets, so widening it to team totals does not
    reach the MLB first-five totals, which it never covered."""
    import models.scorer as sc
    monkeypatch.setattr(sc, "_get_dk_odds", lambda conn, gid, mkt: (
        {"total_line": 3.5, "under_price": -110}))
    conn = _PickConn([(2, "NYY vs BOS Under 4.5 F5", "under", "mlb_f5_over_under",
                       "MLB_2026-07-01_BOS_NYY", -110, 4.5, "totals_1st_5_innings")])
    assert sc.check_line_movement(conn, "2026-07-01") == []
