"""Alternate game lines for the betslip edit sheet.

The bulk odds call stays h2h/spreads/totals. alternate_spreads and
alternate_totals are additional markets: one row per rung, on the events
that call already listed. The 30-second poller does not fetch them. The
latest_odds change that keeps every rung is hand-applied, not in
ACTIVE_MIGRATIONS.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

from data.ingestors.odds_ingestor import (
    ALT_GAME_LINE_MARKETS,
    _fetch_alternate_game_lines,
    _parse_alternate_spread_rows,
    _parse_alternate_total_rows,
    _process_events,
)


# Two hours from now: inside the per-pass 24-hour window (Matt, 2026-10-29,
# option B). A fixed far-future date would now be correctly skipped.
_SOON = (datetime.now(timezone.utc) + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _event(markets):
    return {
        "id": "evt-1",
        "commence_time": _SOON,
        "home_team": "Los Angeles Dodgers",
        "away_team": "New York Yankees",
        "bookmakers": [{
            "key": "draftkings",
            "markets": markets,
        }],
    }


def test_a_spread_ladder_is_one_row_per_home_number_with_links():
    rows = _parse_alternate_spread_rows([
        {"name": "Los Angeles Dodgers", "price": -110, "point": -1.5, "link": "H15", "sid": "S15"},
        {"name": "New York Yankees", "price": -110, "point": 1.5, "link": "A15", "sid": "T15"},
        {"name": "Los Angeles Dodgers", "price": 120, "point": -3.5, "link": "H35", "sid": "S35"},
        {"name": "New York Yankees", "price": -140, "point": 3.5, "link": "A35", "sid": "T35"},
        # One side only: not a line.
        {"name": "Los Angeles Dodgers", "price": 200, "point": -7.5, "link": "H75"},
    ], "Los Angeles Dodgers")
    by_point = {r["spread_home"]: r for r in rows}
    assert set(by_point) == {-1.5, -3.5}
    assert by_point[-1.5]["home_link"] == "H15" and by_point[-1.5]["away_sid"] == "T15"
    assert by_point[-3.5]["away_price"] == -140 and by_point[-3.5]["home_price"] == 120


def test_a_total_ladder_keeps_a_rung_only_when_both_sides_are_priced():
    rows = _parse_alternate_total_rows([
        {"name": "Over", "price": -105, "point": 8.5, "link": "O85", "sid": "OS"},
        {"name": "Under", "price": -115, "point": 8.5, "link": "U85", "sid": "US"},
        {"name": "Over", "price": 130, "point": 9.5, "link": "O95"},
    ])
    assert len(rows) == 1
    assert rows[0]["total_line"] == 8.5
    assert rows[0]["over_link"] == "O85" and rows[0]["under_sid"] == "US"


def test_process_events_stores_each_rung_and_still_one_main_spread():
    markets = [
        {"key": "spreads", "last_update": "2026-10-30T12:00:00Z", "outcomes": [
            {"name": "Los Angeles Dodgers", "price": -110, "point": -1.5},
            {"name": "New York Yankees", "price": -110, "point": 1.5},
        ]},
        {"key": "alternate_spreads", "last_update": "2026-10-30T12:00:00Z", "outcomes": [
            {"name": "Los Angeles Dodgers", "price": -110, "point": -1.5},
            {"name": "New York Yankees", "price": -110, "point": 1.5},
            {"name": "Los Angeles Dodgers", "price": 100, "point": -2.5},
            {"name": "New York Yankees", "price": -120, "point": 2.5},
        ]},
        {"key": "alternate_totals", "last_update": "2026-10-30T12:00:00Z", "outcomes": [
            {"name": "Over", "price": -110, "point": 8.5},
            {"name": "Under", "price": -110, "point": 8.5},
            {"name": "Over", "price": -105, "point": 9.5},
            {"name": "Under", "price": -115, "point": 9.5},
        ]},
    ]
    _games, odds = _process_events([_event(markets)], "MLB", "open", "2026-10-30T12:00:00Z")
    spreads = [r for r in odds if r["market"] == "spreads"]
    alt_s = sorted(r["spread_home"] for r in odds if r["market"] == "alternate_spreads")
    alt_t = sorted(r["total_line"] for r in odds if r["market"] == "alternate_totals")
    assert len(spreads) == 1 and spreads[0]["spread_home"] == -1.5
    assert alt_s == [-2.5, -1.5]
    assert alt_t == [8.5, 9.5]


class _Conn:
    def execute(self, *a, **k):
        return self

    def executemany(self, *a, **k):
        return None

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


def test_the_live_pass_asks_for_alternates_on_the_bulk_events_only(monkeypatch):
    import data.ingestors.odds_ingestor as oi

    asked = []
    monkeypatch.setattr(oi, "get_connection", lambda: _Conn())
    monkeypatch.setattr(oi, "persist_quota", lambda conn: None)
    monkeypatch.setattr(oi, "REQUEST_SLEEP", 0)
    monkeypatch.delenv("FETCH_F5_LIVE", raising=False)
    monkeypatch.setattr(oi, "_list_events", lambda sport_key: [])
    monkeypatch.setattr(oi, "_get_odds", lambda sport_key, markets: [_event([])] if sport_key == "baseball_mlb" else [])

    def fake_event(sport_key, event_id, markets, bookmakers=None):
        asked.append((event_id, list(markets)))
        return None

    monkeypatch.setattr(oi, "_get_event_odds", fake_event)
    oi.run_odds_ingestor(sport="MLB")
    assert asked == [("evt-1", list(ALT_GAME_LINE_MARKETS))]


def test_ufc_and_the_pregame_poller_do_not_ask(monkeypatch):
    import data.ingestors.odds_ingestor as oi

    asked = []
    monkeypatch.setattr(oi, "get_connection", lambda: _Conn())
    monkeypatch.setattr(oi, "persist_quota", lambda conn: None)
    monkeypatch.setattr(oi, "REQUEST_SLEEP", 0)
    monkeypatch.setattr(oi, "_list_events", lambda sport_key: [])
    monkeypatch.setattr(oi, "_known_fighter_slugs", lambda conn: set())
    monkeypatch.setattr(oi, "_process_events", lambda *a, **k: ([], []))
    monkeypatch.setattr(oi, "_get_odds", lambda sport_key, markets: [_event([])])

    def fake_event(sport_key, event_id, markets, bookmakers=None):
        asked.append(list(markets))
        return None

    monkeypatch.setattr(oi, "_get_event_odds", fake_event)
    oi.run_odds_ingestor(sport="UFC")
    oi.fetch_pregame_rows(["MLB"])
    assert all("alternate_spreads" not in m for m in asked)


def test_a_started_game_is_not_asked(monkeypatch):
    import data.ingestors.odds_ingestor as oi

    monkeypatch.setattr(oi, "REQUEST_SLEEP", 0)
    seen = []
    monkeypatch.setattr(oi, "_get_event_odds", lambda sport_key, event_id, markets, bookmakers=None: seen.append(event_id) or None)
    started = dict(_event([]), id="gone", commence_time="2020-01-01T00:00:00Z")
    _fetch_alternate_game_lines(
        "baseball_mlb", "MLB", [_event([]), started, {"id": "nodate"}],
        "open", "t")
    # An undatable event is not bought since the 24-hour window (2026-10-29):
    # every event is a paid call, and one we cannot date we cannot bound.
    assert seen == ["evt-1"]


def test_only_games_inside_the_window_are_asked_each_pass(monkeypatch):
    import data.ingestors.odds_ingestor as oi

    monkeypatch.setattr(oi, "REQUEST_SLEEP", 0)
    monkeypatch.delenv("ALT_GAME_LINES_WINDOW_HOURS", raising=False)
    seen = []
    monkeypatch.setattr(oi, "_get_event_odds", lambda sport_key, event_id, markets, bookmakers=None: seen.append(event_id) or None)
    now = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)
    at = lambda h: (now + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ")
    evs = [dict(_event([]), id="in23", commence_time=at(23)),
           dict(_event([]), id="out25", commence_time=at(25))]
    _fetch_alternate_game_lines("baseball_mlb", "MLB", evs, "open", "t", now=now)
    assert seen == ["in23"]
    monkeypatch.setenv("ALT_GAME_LINES_WINDOW_HOURS", "0")      # 0 = no window
    seen.clear()
    _fetch_alternate_game_lines("baseball_mlb", "MLB", evs, "open", "t", now=now)
    assert seen == ["in23", "out25"]


def test_the_pass_meters_the_credits_the_feed_reports(monkeypatch):
    import data.ingestors.odds_ingestor as oi
    from data.ingestors import odds_quota

    monkeypatch.setattr(oi, "REQUEST_SLEEP", 0)
    stamps = iter([{"last": 2}, {"last": 2}, None])
    current = {"v": None}

    def fake_event(sport_key, event_id, markets, bookmakers=None):
        current["v"] = next(stamps)
        return None

    monkeypatch.setattr(oi, "_get_event_odds", fake_event)
    monkeypatch.setattr(odds_quota, "latest", lambda: current["v"])
    evs = [dict(_event([]), id=f"e{i}") for i in range(3)]
    meter: dict = {}
    _fetch_alternate_game_lines("baseball_mlb", "MLB", evs, "open", "t", meter=meter)
    # Calls 1 and 2 each report 2; call 3 reports nothing new.
    assert meter == {"calls": 3, "credits": 4.0, "unreported": 1}


def test_the_pass_refreshes_the_ladder_the_app_reads(monkeypatch):
    """A real pass, network faked: the rows it bought and its meter reach
    store_pass_ladders, and a fetch that raises is still handed over so its
    billed calls are ledgered (review of #1093, L2 and L4)."""
    import data.ingestors.odds_ingestor as oi
    import data.ingestors.alt_game_lines as agl

    monkeypatch.setattr(oi, "get_connection", lambda: _Conn())
    monkeypatch.setattr(oi, "persist_quota", lambda conn: None)
    monkeypatch.setattr(oi, "REQUEST_SLEEP", 0)
    monkeypatch.delenv("FETCH_F5_LIVE", raising=False)
    monkeypatch.delenv("FETCH_ALT_GAME_LINES", raising=False)
    monkeypatch.setattr(oi, "_list_events", lambda sport_key: [])
    monkeypatch.setattr(oi, "_get_odds", lambda sport_key, markets: [_event([])] if sport_key == "baseball_mlb" else [])
    monkeypatch.setattr(oi, "_get_event_odds", lambda *a, **k: None)
    handed = []
    monkeypatch.setattr(agl, "store_pass_ladders",
                        lambda conn, sport, rows, meter, asked_at: handed.append((sport, list(rows), dict(meter))))
    oi.run_odds_ingestor(sport="MLB")
    assert [(sp, rows, m.get("calls")) for sp, rows, m in handed] == [("MLB", [], 1)]

    handed.clear()
    def boom(*a, **k):
        raise RuntimeError("feed down")
    monkeypatch.setattr(oi, "_fetch_alternate_game_lines", boom)
    oi.run_odds_ingestor(sport="MLB")
    assert handed and handed[0][1] == [] and "feed down" in handed[0][2]["error"]


def test_the_env_flag_skips_the_alternate_fetch(monkeypatch):
    import data.ingestors.odds_ingestor as oi

    asked = []
    monkeypatch.setenv("FETCH_ALT_GAME_LINES", "0")
    monkeypatch.setattr(oi, "get_connection", lambda: _Conn())
    monkeypatch.setattr(oi, "persist_quota", lambda conn: None)
    monkeypatch.setattr(oi, "REQUEST_SLEEP", 0)
    monkeypatch.delenv("FETCH_F5_LIVE", raising=False)
    monkeypatch.setattr(oi, "_list_events", lambda sport_key: [])
    monkeypatch.setattr(oi, "_get_odds", lambda sport_key, markets: [_event([])] if sport_key == "baseball_mlb" else [])
    monkeypatch.setattr(oi, "_get_event_odds", lambda *a, **k: asked.append(a) or None)
    oi.run_odds_ingestor(sport="MLB")
    assert asked == []


def test_board_reads_do_not_take_the_ladder():
    from pathlib import Path
    text = (Path(__file__).resolve().parent.parent / "mobile" / "src" / "lib" / "queries.ts").read_text(encoding="utf-8")
    assert text.count(".in('market', [...MAIN_GAME_ODDS_MARKETS])") >= 6
    start = text.index("const MAIN_GAME_ODDS_MARKETS")
    block = text[start:text.index("] as const", start)]
    assert "alternate_spreads" not in block and "alternate_totals" not in block
    for name in ("h2h", "spreads", "totals", "h2h_3way", "team_totals_home", "h2h_1st_5_innings"):
        assert f"'{name}'" in block


def test_fetch_uses_the_events_it_is_given_and_not_the_season_list(monkeypatch):
    import data.ingestors.odds_ingestor as oi

    monkeypatch.setattr(oi, "REQUEST_SLEEP", 0)
    monkeypatch.setattr(oi, "_list_events", lambda sport_key: (_ for _ in ()).throw(AssertionError("season list")))
    seen = []

    def fake_event(sport_key, event_id, markets, bookmakers=None):
        seen.append(event_id)
        return None

    monkeypatch.setattr(oi, "_get_event_odds", fake_event)
    rows = _fetch_alternate_game_lines(
        "baseball_mlb", "MLB", [_event([]), {"commence_time": "2026-10-30T23:00:00Z"}],
        "open", "2026-10-30T12:00:00Z")
    assert seen == ["evt-1"]
    assert rows == []


def test_the_ladder_migration_is_hand_applied():
    from data.view_migrations import ACTIVE_MIGRATIONS
    name = "alternate_game_lines_latest_odds_2026_10_29.sql"
    assert name not in ACTIVE_MIGRATIONS
    # The live pass calls the fetcher. The poller does not.
    import data.ingestors.odds_ingestor as oi
    assert "_fetch_alternate_game_lines" in inspect.getsource(oi.run_odds_ingestor)
    assert "_fetch_alternate_game_lines" not in inspect.getsource(oi.fetch_pregame_rows)


def test_pr_ci_runs_verify_line_legs():
    """The script exits 1 on a failure. The pytest job does not npm ci, so
    the mobile-tsc job is the gate, same as verify_paused_catalog."""
    from pathlib import Path
    text = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "pr-ci.yml").read_text(encoding="utf-8")
    assert "npx tsx scripts/verify_line_legs.ts" in text
    assert "npx tsx scripts/verify_paused_catalog.ts" in text
