"""data/schedule_context: one reading of the stored schedule for every sport.

The rules pinned here are the repo's own: one game per team inside two days
for UFC, NCAAF and NFL; the series window for every other sport
(tracking.record_duplicates); a row no book ever priced is not a listing; a
past game with no result stops holding decisions after the sport's lookback.
The shapes are the measured ones (2026-10-20, read-only): the NCAAF night-game
stub beside CFBD's UTC-dated row, 'LIU Sharks' beside 'Long Island
University', the WNBA rows 17-41 hours from the real game with 0 odds rows,
and the NHL two-day check, whose behaviour must not change.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

import data.schedule_context as sc
from data.schedule_context import GameRow, RULES, team_view

NOW = datetime(2026, 10, 20, 20, 0, tzinfo=timezone.utc)


def _at(day: str, hour: int = 0) -> datetime:
    return datetime.fromisoformat(day).replace(hour=hour, tzinfo=timezone.utc)


def _row(gid, day, home, away, hour=0, score=None, priced=None):
    hs, as_ = (score if score else (None, None))
    return GameRow(gid, day, home, away, _at(day, hour), hs, as_, priced)


# ── what counts as one game ──────────────────────────────────────────────────

def test_the_ncaaf_stub_and_cfbds_utc_row_are_one_game():
    rows = [_row("NCAAF_2026-10-17_wisconsin_ucla", "2026-10-17", "UCLA", "Wisconsin", 23,
                 (31, 20)),
            _row("NCAAF_2026-10-18_wisconsin_ucla", "2026-10-18", "UCLA", "Wisconsin", 0)]
    (ev,) = sc.collapse(rows, "NCAAF")
    assert ev.scored and ev.first_day.isoformat() == "2026-10-17"
    assert ev.last_day.isoformat() == "2026-10-18"        # rest reads the later date


def test_an_opponent_spelled_two_ways_is_one_game_for_the_fbs_team():
    """Kansas vs 'LIU Sharks' (09-04, unscored) beside Kansas vs 'Long Island
    University' (09-05, final): the alias rule could not match them."""
    rows = [_row("NCAAF_2026-09-04_liu-sharks_kansas", "2026-09-04", "Kansas", "LIU Sharks"),
            _row("NCAAF_2026-09-05_long-island-university_kansas", "2026-09-05", "Kansas",
                 "Long Island University", 0, (51, 0))]
    (ev,) = sc.collapse(rows, "NCAAF")
    assert ev.scored


def test_series_games_a_day_apart_stay_two_games():
    rows = [_row("WNBA_2026-10-03_NY_ATL", "2026-10-03", "ATL", "NY", 1),
            _row("WNBA_2026-10-04_NY_ATL", "2026-10-04", "ATL", "NY", 18, (92, 88))]
    assert len(sc.collapse(rows, "WNBA")) == 2               # 17 hours apart


def test_series_twins_inside_the_window_are_one_game_unless_the_finals_differ():
    a = _row("MLB_2026-08-10_LAA_TOR", "2026-08-10", "TOR", "LAA", 23, (5, 3))
    b = GameRow("MLB_2026-08-11_LAA_TOR", "2026-08-11", "TOR", "LAA",
                _at("2026-08-10", 23), 5, 3)                 # the UTC-dated copy
    assert len(sc.collapse([a, b], "MLB")) == 1
    c = GameRow("MLB_2026-08-11_TOR_LAA", "2026-08-11", "LAA", "TOR",
                _at("2026-08-11", 2), 2, 7)
    assert len(sc.collapse([a, c], "MLB")) == 2              # a doubleheader under swapped ids


# ── one team's view ──────────────────────────────────────────────────────────

def test_a_game_still_to_be_played_is_pending_and_counts_for_rest():
    target = _row("NCAAF_2026-10-24_usc_wisconsin", "2026-10-24", "Wisconsin", "USC", 23)
    rows = [target,
            _row("NCAAF_2026-10-17_wisconsin_ucla", "2026-10-17", "UCLA", "Wisconsin", 23),
            _row("NCAAF_2026-10-03_michigan-state_wisconsin", "2026-10-03", "Wisconsin",
                 "Michigan State", 16, (21, 14))]
    v = team_view(rows, RULES["NCAAF"], "Wisconsin", target, _at("2026-10-17", 10))
    assert [s for _, s in v.pending] == [sc.UNPLAYED]
    assert v.rest_days == 7 and not v.back_to_back
    assert sc.pending_reason([("Wisconsin", v)]) == (
        "waiting for Wisconsin's 2026-10-17 game to be played and logged")


def test_played_but_not_in_the_log_is_pending():
    target = _row("NCAAF_2026-10-24_usc_wisconsin", "2026-10-24", "Wisconsin", "USC", 23)
    prev = _row("NCAAF_2026-10-17_wisconsin_ucla", "2026-10-17", "UCLA", "Wisconsin", 23,
                (31, 20))
    v = team_view([target, prev], RULES["NCAAF"], "Wisconsin", target, NOW,
                  logged=lambda team, ev: False)
    assert [s for _, s in v.pending] == [sc.UNLOGGED]
    v = team_view([target, prev], RULES["NCAAF"], "Wisconsin", target, NOW,
                  logged=lambda team, ev: True)
    assert v.pending == [] and v.rest_days == 7


def test_a_past_game_that_never_got_a_result_stops_holding_after_the_lookback():
    target = _row("NCAAF_2026-10-24_x_kansas", "2026-10-24", "Kansas", "X", 18)
    dead = _row("NCAAF_2026-10-05_y_kansas", "2026-10-05", "Kansas", "Y", 18)   # 15 days ago
    real = _row("NCAAF_2026-10-17_z_kansas", "2026-10-17", "Kansas", "Z", 18, (30, 10))
    v = team_view([target, dead, real], RULES["NCAAF"], "Kansas", target, NOW)
    assert v.pending == [] and len(v.gaps) == 1
    assert v.previous.first_day.isoformat() == "2026-10-17"
    recent = _row("NCAAF_2026-10-17_y_kansas", "2026-10-17", "Kansas", "Y", 18)
    v = team_view([target, recent], RULES["NCAAF"], "Kansas", target, NOW)
    assert [s for _, s in v.pending] == [sc.UNSCORED]       # inside the lookback: wait


def test_a_wnba_row_no_book_priced_is_ignored_and_a_priced_one_is_not():
    target = _row("WNBA_2026-10-24_GSV_ATL", "2026-10-24", "ATL", "GSV", 0)
    other = _row("WNBA_2026-10-22_GSV_ATL", "2026-10-22", "ATL", "GSV", 0, priced=False)
    v = team_view([target, other], RULES["WNBA"], "ATL", target, NOW)
    assert v.pending == [] and v.previous is None
    other = _row("WNBA_2026-10-22_GSV_ATL", "2026-10-22", "ATL", "GSV", 0, priced=True)
    v = team_view([target, other], RULES["WNBA"], "ATL", target, NOW)
    assert [s for _, s in v.pending] == [sc.UNPLAYED] and v.rest_days == 2


def test_a_ufc_fight_is_done_once_its_card_is_in_the_fight_log():
    """Cancelled bouts never reach the log; the card's presence is the test."""
    target = _row("UFC_2026-10-24_b_a", "2026-10-24", "a", "b", 20)
    prev = _row("UFC_2026-06-20_c_a", "2026-06-20", "c", "a", 20, priced=True)
    rules = RULES["UFC"]
    v = team_view([target, prev], rules, "a", target, NOW, logged=lambda t, ev: False)
    assert [s for _, s in v.pending] == [sc.UNLOGGED]
    v = team_view([target, prev], rules, "a", target, NOW, logged=lambda t, ev: True)
    assert v.pending == []


def test_the_counts_around_a_game():
    target = _row("WNBA_2026-10-10_A_B", "2026-10-10", "B", "A", 0)
    rows = [target,
            _row("WNBA_2026-10-09_A_C", "2026-10-09", "C", "A", 0, (1, 2)),
            _row("WNBA_2026-10-07_A_D", "2026-10-07", "D", "A", 0, (1, 2)),
            _row("WNBA_2026-09-20_A_E", "2026-09-20", "E", "A", 0, (1, 2)),
            _row("WNBA_2026-10-12_A_F", "2026-10-12", "F", "A", 0, priced=True)]
    v = team_view(rows, RULES["WNBA"], "A", target, _at("2026-10-09", 6))
    assert v.back_to_back and v.rest_days == 1
    assert v.games_in_last(4) == 2 and v.games_in_last(30) == 3
    assert v.next_game.first_day.isoformat() == "2026-10-12"


# ── the NHL check: its behaviour, exactly ────────────────────────────────────

def _stale_teams_before(conn, logs, game_date):
    """models/nhl_moneyline_anchored.stale_teams as it was on 10acee3f."""
    d = datetime.fromisoformat(str(game_date)[:10])
    lo = (d - timedelta(days=2)).strftime("%Y-%m-%d")
    recent = conn.execute(
        "SELECT game_id, home_team, away_team FROM games WHERE sport = 'NHL' "
        "AND game_date >= %s AND game_date < %s", (lo, d.strftime("%Y-%m-%d"))).fetchall()
    logged = set(logs["team"].game_id)
    return {t for gid, h, a in recent if gid not in logged for t in (h, a)}


class _NhlConn:
    """A games table, filtered by date the way the query asks."""

    def __init__(self, rows):
        self.rows, self.calls = rows, []

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), tuple(params)))
        lo, hi = params[-2], params[-1]
        rows = [(g, h, a) for g, d, h, a in self.rows if lo <= d < hi]

        class _R:
            def fetchall(self_inner):
                return rows
        return _R()


def test_nhl_stale_teams_answers_exactly_as_before():
    import models.nhl_moneyline_anchored as anc
    rows = [("NHL_2026-10-15_BOS_TOR", "2026-10-15", "TOR", "BOS"),     # logged
            ("NHL_2026-10-15_STL_OTT", "2026-10-15", "OTT", "STL"),     # not logged
            ("NHL_2026-10-14_ANA_LAK", "2026-10-14", "LAK", "ANA"),     # not logged, unscored
            ("NHL_2026-10-15_BOS_TOR_x", "2026-10-15", "TOR", "BOS"),   # a twin id, not logged
            ("NHL_2026-10-13_SEA_VAN", "2026-10-13", "VAN", "SEA"),     # outside the window
            ("NHL_2026-10-16_CHI_DAL", "2026-10-16", "DAL", "CHI")]     # the day itself
    logs = {"team": pd.DataFrame({"game_id": ["NHL_2026-10-15_BOS_TOR"]})}
    for day in ("2026-10-16", "2026-10-15", "2026-10-17", "2026-10-14"):
        want = _stale_teams_before(_NhlConn(rows), logs, day)
        conn = _NhlConn(rows)
        assert anc.stale_teams(conn, logs, day) == want, day
        assert conn.calls[0][1][-2:] == (
            (datetime.fromisoformat(day) - timedelta(days=2)).strftime("%Y-%m-%d"), day)
    assert anc.stale_teams(_NhlConn(rows), logs, "2026-10-16") == {
        "OTT", "STL", "LAK", "ANA", "TOR", "BOS"}


# ── rest at kickoff equals what training reads, on a played history ─────────

def test_rest_at_kickoff_equals_the_training_value_on_a_played_season():
    """Training (features/ncaaf_feature_engine bulk path, wnba likewise) takes
    the latest SCORED games row before the game. On a season where every game
    has been played, the schedule read must give the same number for every
    game: with the night-game twin unscored (as in 2015-2025), an opponent
    spelled two ways, and a listing that never happened."""
    import sqlite3
    from features.ncaaf_feature_engine import _rest_days
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE games (game_id TEXT, sport TEXT, game_date TEXT, home_team TEXT, "
              "away_team TEXT, commence_time TEXT, home_score REAL, away_score REAL)")
    rows = [  # (game_id, date, home, away, start, scored)
        ("NCAAF_2025-08-30_a_t", "2025-08-30", "T", "A", "2025-08-30T17:00:00Z", True),
        ("NCAAF_2025-09-06_b_t", "2025-09-06", "T", "B", "2025-09-06T00:30:00Z", True),   # CFBD UTC
        ("NCAAF_2025-09-05_b_t", "2025-09-05", "T", "B", "2025-09-06T00:30:00Z", False),  # feed ET
        ("NCAAF_2025-09-13_c-x_t", "2025-09-13", "T", "C X", "2025-09-13T17:00:00Z", False),
        ("NCAAF_2025-09-13_c_t", "2025-09-13", "T", "C", "2025-09-13T17:00:00Z", True),
        ("NCAAF_2025-09-27_d_t", "2025-09-27", "D", "T", "2025-09-27T17:00:00Z", True),
        ("NCAAF_2025-10-04_e_t", "2025-10-04", "T", "E", "2025-10-04T17:00:00Z", True),
        ("NCAAF_2025-12-06_t_z", "2025-12-06", "Z", "T", "2025-12-06T17:00:00Z", False),  # never played
        ("NCAAF_2026-08-29_f_t", "2026-08-29", "T", "F", "2026-08-29T17:00:00Z", True),
    ]
    for gid, d, h, a, start, scored in rows:
        c.execute("INSERT INTO games VALUES (?, 'NCAAF', ?, ?, ?, ?, ?, ?)",
                  (gid, d, h, a, start, 21 if scored else None, 14 if scored else None))
    played = sorted(d for _, d, _, _, _, s in rows if s)
    later = datetime(2027, 1, 1, tzinfo=timezone.utc)
    for gid, d, *_rest, scored in rows:
        if not scored:
            continue
        assert sc.rest_days_as_of_kickoff(c, "NCAAF", "T", gid, d, now=later) == \
            _rest_days(played, d), gid
