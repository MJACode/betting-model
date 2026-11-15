"""Odds ingest must not mint a second NCAAF games row for one home date.

Measured 2026-11-15. The Odds API historical snapshot at
2025-12-01T16:55:37Z (odds_history_pulls: snapshot_date 2025-12-01, hour 17,
pulled 2026-11-14 21:58:14Z) contained:

    2026-11-21T17:00:00Z  LSU Tigers @ Ole Miss Rebels

ESPN's 2026 Ole Miss schedule has Wofford at that kickoff and LSU at Ole
Miss on 2026-09-19, final. CFBD's row is NCAAF_2026-11-21_wofford_ole-miss.
The historical writer minted NCAAF_2026-11-21_lsu_ole-miss beside it, with
no odds and no picks, and ncaaf_game_identity went STALE.

The check is right. The schedule opponent is Wofford. An unresolved Odds
API spelling (Citadel Bulldogs vs The Citadel) is a different fault and
still mints, because those odds have to land until the alias map exists.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from data.ingestors.odds_ingestor import (
    NCAAF_ODDS_MAX_LEAD_DAYS,
    drop_ncaaf_unscheduled_opponents,
)
from data.ingestors import odds_ingestor as oi


PHANTOM = "NCAAF_2026-11-21_lsu_ole-miss"
WOFFORD = "NCAAF_2026-11-21_wofford_ole-miss"
TENNESSEE = "NCAAF_2026-11-21_lsu_tennessee"


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, games, schools):
        self.games = list(games)
        self.schools = set(schools)

    def execute(self, sql, params=None):
        if "FROM ncaaf_teams" in sql:
            wanted = set(params[0])
            return _Rows([(s,) for s in sorted(self.schools & wanted)])
        if "FROM games" in sql:
            dates, homes = set(params[0]), set(params[1])
            return _Rows([
                g for g in self.games
                if g[1] in dates and g[2] in homes
            ])
        raise AssertionError(sql)


class _Boom:
    def execute(self, *args, **kwargs):
        raise RuntimeError("schedule unreadable")


def _game(gid, gdate, home, away, sport="NCAAF"):
    return {
        "game_id": gid, "sport": sport, "game_date": gdate,
        "home_team": home, "away_team": away,
    }


def _odds(gid, market="h2h"):
    return {"game_id": gid, "market": market}


def _schedule():
    return _Conn(
        games=[
            (WOFFORD, "2026-11-21", "Ole Miss", "Wofford"),
            (TENNESSEE, "2026-11-21", "Tennessee", "LSU"),
        ],
        schools={"Ole Miss", "Wofford", "LSU", "Tennessee", "The Citadel",
                 "Texas A&M"},
    )


def test_the_measured_lsu_mint_is_dropped_and_its_odds_with_it():
    games = [
        _game(PHANTOM, "2026-11-21", "Ole Miss", "LSU"),
        _game(TENNESSEE, "2026-11-21", "Tennessee", "LSU"),
    ]
    odds = [_odds(PHANTOM), _odds(TENNESSEE), _odds(TENNESSEE, "spreads")]
    kept, kept_odds = drop_ncaaf_unscheduled_opponents(
        _schedule(), games, odds, observed_on="2026-11-15")
    assert [g["game_id"] for g in kept] == [TENNESSEE]
    assert [o["game_id"] for o in kept_odds] == [TENNESSEE, TENNESSEE]


def test_a_year_ahead_event_is_dropped_from_the_snapshot_that_carried_it():
    """355 days from 2025-12-01 to 2026-11-21. No schedule read required."""
    games = [_game(PHANTOM, "2026-11-21", "Ole Miss", "LSU")]
    kept, odds = drop_ncaaf_unscheduled_opponents(
        _Boom(), games, [_odds(PHANTOM)], observed_on="2025-12-01")
    assert kept == [] and odds == []
    assert NCAAF_ODDS_MAX_LEAD_DAYS < 355


def test_a_bowl_listed_inside_the_lead_window_is_kept():
    """2026-01-19 is 49 days after 2025-12-01. The window exists for the
    year-ahead event, not for the postseason."""
    gid = "NCAAF_2026-01-19_indiana_miami"
    games = [_game(gid, "2026-01-19", "Miami", "Indiana")]
    kept, _odds = drop_ncaaf_unscheduled_opponents(
        _Conn([], {"Miami", "Indiana"}), games, [], observed_on="2025-12-01")
    assert [g["game_id"] for g in kept] == [gid]


def test_an_unresolved_alias_still_mints():
    """Citadel Bulldogs is not ncaaf_teams.school. Dropping it would throw
    away the odds the alias migration later moves onto The Citadel."""
    alias = "NCAAF_2026-10-17_citadel-bulldogs_texas-a-m"
    canon = "NCAAF_2026-10-17_the-citadel_texas-a-m"
    conn = _Conn(
        [(canon, "2026-10-17", "Texas A&M", "The Citadel")],
        {"The Citadel", "Texas A&M"},
    )
    games = [_game(alias, "2026-10-17", "Texas A&M", "Citadel Bulldogs")]
    kept, odds = drop_ncaaf_unscheduled_opponents(
        conn, games, [_odds(alias)], observed_on="2026-10-16")
    assert [g["game_id"] for g in kept] == [alias]
    assert [o["game_id"] for o in odds] == [alias]


def test_the_same_game_id_is_an_update_not_a_second_row():
    conn = _Conn(
        [(WOFFORD, "2026-11-21", "Ole Miss", "Wofford")],
        {"Ole Miss", "Wofford"},
    )
    games = [_game(WOFFORD, "2026-11-21", "Ole Miss", "Wofford")]
    kept, _odds = drop_ncaaf_unscheduled_opponents(
        conn, games, [], observed_on="2026-11-15")
    assert [g["game_id"] for g in kept] == [WOFFORD]


def test_a_schedule_read_failure_keeps_a_near_term_row():
    games = [_game(PHANTOM, "2026-11-21", "Ole Miss", "LSU")]
    kept, _odds = drop_ncaaf_unscheduled_opponents(
        _Boom(), games, [], observed_on="2026-11-15")
    assert kept == games


def test_other_sports_are_not_filtered():
    games = [_game("MLB_2027-08-01_NYM_LAD", "2027-08-01", "LAD", "NYM", sport="MLB")]
    kept, _odds = drop_ncaaf_unscheduled_opponents(
        _Boom(), games, [], observed_on="2026-11-15")
    assert kept == games


def test_every_games_writer_filters_before_the_upsert():
    for fn in (oi.fetch_pregame_rows, oi.run_odds_ingestor,
               oi.run_historical_odds, oi.run_historical_odds_range):
        body = inspect.getsource(fn)
        assert "drop_ncaaf_unscheduled_opponents(" in body, fn.__name__
        assert body.index("drop_ncaaf_unscheduled_opponents(") < body.index("_upsert_games("), fn.__name__
    script = Path("scripts/ncaaf_search/book_timing_snapshot.py").read_text(encoding="utf-8")
    assert script.index("drop_ncaaf_unscheduled_opponents(") < script.index("_upsert_games(")
