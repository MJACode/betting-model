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
        head = sql.strip().upper()
        if head.startswith(("SAVEPOINT", "RELEASE SAVEPOINT", "ROLLBACK TO SAVEPOINT")):
            return _Rows([])
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


class _Aborting:
    """A SELECT failure aborts the transaction until ROLLBACK TO SAVEPOINT."""

    def __init__(self):
        self.aborted = False
        self.rolled_back = False

    def execute(self, sql, params=None):
        head = sql.strip().upper()
        if head.startswith("ROLLBACK TO SAVEPOINT"):
            self.aborted = False
            self.rolled_back = True
            return _Rows([])
        if head.startswith(("SAVEPOINT", "RELEASE SAVEPOINT")):
            return _Rows([])
        if sql.strip() == "SELECT 1":
            if self.aborted:
                raise RuntimeError("current transaction is aborted")
            return _Rows([])
        if self.aborted:
            raise RuntimeError("current transaction is aborted")
        self.aborted = True
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
            (WOFFORD, "2026-11-21", "Ole Miss", "Wofford", 12),
            (TENNESSEE, "2026-11-21", "Tennessee", "LSU", 12),
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
    conn = _Aborting()
    games = [_game(PHANTOM, "2026-11-21", "Ole Miss", "LSU")]
    kept, kept_odds = drop_ncaaf_unscheduled_opponents(
        conn, games, [_odds(PHANTOM)], observed_on="2025-12-01")
    assert kept == [] and kept_odds == []
    assert not conn.aborted and not conn.rolled_back
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
        [(canon, "2026-10-17", "Texas A&M", "The Citadel", 8)],
        {"The Citadel", "Texas A&M"},
    )
    games = [_game(alias, "2026-10-17", "Texas A&M", "Citadel Bulldogs")]
    kept, odds = drop_ncaaf_unscheduled_opponents(
        conn, games, [_odds(alias)], observed_on="2026-10-16")
    assert [g["game_id"] for g in kept] == [alias]
    assert [o["game_id"] for o in odds] == [alias]


def test_the_same_game_id_is_an_update_not_a_second_row():
    conn = _Conn(
        [(WOFFORD, "2026-11-21", "Ole Miss", "Wofford", 12)],
        {"Ole Miss", "Wofford"},
    )
    games = [_game(WOFFORD, "2026-11-21", "Ole Miss", "Wofford")]
    kept, _odds = drop_ncaaf_unscheduled_opponents(
        conn, games, [], observed_on="2026-11-15")
    assert [g["game_id"] for g in kept] == [WOFFORD]


def test_a_stored_live_mint_does_not_block_the_schedule_game():
    """week NULL is a mint. The odds upsert rewrites data_source to live
    and leaves week, so week is what marks the schedule. While the LSU
    mint is stored, the Wofford event must still be written."""
    conn = _Conn(
        [
            (PHANTOM, "2026-11-21", "Ole Miss", "LSU", None),
            (WOFFORD, "2026-11-21", "Ole Miss", "Wofford", 12),
        ],
        {"Ole Miss", "Wofford", "LSU"},
    )
    games = [
        _game(WOFFORD, "2026-11-21", "Ole Miss", "Wofford"),
        _game(PHANTOM, "2026-11-21", "Ole Miss", "LSU"),
    ]
    kept, odds = drop_ncaaf_unscheduled_opponents(
        conn, games, [_odds(WOFFORD), _odds(PHANTOM)], observed_on="2026-11-15")
    assert [g["game_id"] for g in kept] == [WOFFORD]
    assert [o["game_id"] for o in odds] == [WOFFORD]


def test_a_week_null_mint_alone_is_not_the_schedule():
    conn = _Conn(
        [(PHANTOM, "2026-11-21", "Ole Miss", "LSU", None)],
        {"Ole Miss", "Wofford", "LSU"},
    )
    games = [_game(WOFFORD, "2026-11-21", "Ole Miss", "Wofford")]
    kept, _odds = drop_ncaaf_unscheduled_opponents(
        conn, games, [], observed_on="2026-11-15")
    assert [g["game_id"] for g in kept] == [WOFFORD]


def test_a_schedule_read_failure_keeps_a_near_term_row_and_clears_the_abort():
    conn = _Aborting()
    games = [_game(PHANTOM, "2026-11-21", "Ole Miss", "LSU")]
    kept, _odds = drop_ncaaf_unscheduled_opponents(
        conn, games, [], observed_on="2026-11-15")
    assert kept == games
    assert conn.rolled_back and not conn.aborted
    conn.execute("SELECT 1")


def test_the_lead_window_is_off_when_no_snapshot_date_is_passed():
    """The live pass omits observed_on, so a line posted for next August
    is not dropped on the way in."""
    gid = "NCAAF_2027-08-30_wofford_ole-miss"
    games = [_game(gid, "2027-08-30", "Ole Miss", "Wofford")]
    kept, _odds = drop_ncaaf_unscheduled_opponents(
        _Conn([], {"Ole Miss", "Wofford"}), games, [])
    assert [g["game_id"] for g in kept] == [gid]


def test_other_sports_are_not_filtered():
    games = [_game("MLB_2027-08-01_NYM_LAD", "2027-08-01", "LAD", "NYM", sport="MLB")]
    kept, _odds = drop_ncaaf_unscheduled_opponents(
        None, games, [], observed_on="2026-11-15")
    assert kept == games


def test_the_lead_window_is_historical_only():
    hist = inspect.getsource(oi.run_historical_odds)
    rng = inspect.getsource(oi.run_historical_odds_range)
    live = inspect.getsource(oi.run_odds_ingestor)
    pre = inspect.getsource(oi.fetch_pregame_rows)
    assert "observed_on=snapshot_date" in hist
    assert "observed_on=day.isoformat()" in rng
    assert "observed_on" not in live
    assert "observed_on" not in pre
    script = Path("scripts/ncaaf_search/book_timing_snapshot.py").read_text(encoding="utf-8")
    assert "observed_on=args.date" in script
    for fn in (oi.fetch_pregame_rows, oi.run_odds_ingestor,
               oi.run_historical_odds, oi.run_historical_odds_range):
        body = inspect.getsource(fn)
        assert "drop_ncaaf_unscheduled_opponents(" in body, fn.__name__
        assert body.index("drop_ncaaf_unscheduled_opponents(") < body.index("_upsert_games("), fn.__name__
    script = Path("scripts/ncaaf_search/book_timing_snapshot.py").read_text(encoding="utf-8")
    assert script.index("drop_ncaaf_unscheduled_opponents(") < script.index("_upsert_games(")
