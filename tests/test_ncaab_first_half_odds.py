"""The live NCAAB first-half capture (data/ingestors/ncaab_first_half_odds.py)
and its schedule (scripts/ncaab_first_half_window.py).

No test here calls the Odds API: the event list and the event call are fakes
fed the feed's own payload shape, and the reads the fetch makes are patched.
The ledger's SQL, the decision reads and the card's write path run against a
real Postgres in tests/test_ncaab_first_half_spread_card_pg.py.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import data.ingestors.ncaab_first_half_odds as feed  # noqa: E402

UTC = timezone.utc
TIP = datetime(2026, 11, 11, 0, 0, tzinfo=UTC)          # 7pm ET on 2026-11-10
DATE = "2026-11-10"
GID = "NCAAB_2026-11-10_duke_kansas"
FEED_HOME, FEED_AWAY = "Kansas Jayhawks", "Duke Blue Devils"


# ── the schedule ─────────────────────────────────────────────────────────────

def test_nine_fetch_times_a_game_ending_ten_minutes_before_tip():
    s = feed.slots(DATE, TIP)
    assert [m for m, _ in s] == ["15z", "T-180", "T-120", "T-60", "T-50", "T-40", "T-30",
                                 "T-20", "T-10"]
    assert s[0][1] == datetime(2026, 11, 10, 15, 0, tzinfo=UTC)
    assert s[-1][1] == TIP - timedelta(minutes=10)
    assert len(s) * feed.MAX_CREDITS_PER_CALL == 36


def test_a_morning_tip_drops_the_15z_time_and_never_duplicates_one():
    tip = datetime(2026, 11, 10, 16, 0, tzinfo=UTC)       # 11am ET
    s = feed.slots(DATE, tip)
    assert len({t for _, t in s}) == len(s)
    assert all(t < tip for _, t in s)
    tip = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)
    assert "15z" not in [m for m, _ in feed.slots(DATE, tip)]


def test_a_time_is_due_once_it_passes_until_an_ok_call_lands_after_it():
    t10 = TIP - timedelta(minutes=10)
    assert feed.due_mark(DATE, TIP, t10 - timedelta(seconds=1), None) == ("T-20", t10 - timedelta(minutes=10))
    assert feed.due_mark(DATE, TIP, t10, None) == ("T-10", t10)
    # the -20 fetch does not satisfy -10
    assert feed.due_mark(DATE, TIP, t10 + timedelta(minutes=1), t10 - timedelta(minutes=9))[0] == "T-10"
    # a call that landed after it does
    assert feed.due_mark(DATE, TIP, t10 + timedelta(minutes=2), t10 + timedelta(seconds=5)) is None
    # a failed -10 stays due, minute after minute, until just before tip
    assert feed.due_mark(DATE, TIP, TIP - timedelta(minutes=1), None)[0] == "T-10"
    assert feed.due_mark(DATE, TIP, TIP - timedelta(seconds=20), None) is None
    assert feed.due_mark(DATE, TIP, TIP + timedelta(minutes=1), None) is None


def test_a_failed_history_fetch_waits_for_the_next_time_but_the_decision_is_retried():
    t20 = TIP - timedelta(minutes=20)
    failed = t20 + timedelta(seconds=3)
    # the -20 call failed: no second -20 call a minute later
    assert feed.due_mark(DATE, TIP, t20 + timedelta(minutes=1), None, failed) is None
    # the -10 time is due as usual
    assert feed.due_mark(DATE, TIP, TIP - timedelta(minutes=10), None, failed)[0] == "T-10"
    # a failed -10 call is retried the next minute
    t10 = TIP - timedelta(minutes=10)
    assert feed.due_mark(DATE, TIP, t10 + timedelta(minutes=1), None, t10 + timedelta(seconds=2))[0] == "T-10"


def test_nothing_is_due_before_the_first_time():
    assert feed.due_mark(DATE, TIP, datetime(2026, 11, 10, 14, 59, tzinfo=UTC), None) is None


# ── parsing ──────────────────────────────────────────────────────────────────

def _book(key, spreads=(), totals=(), h2h=None, tt=(), stamp="2026-11-10T23:49:00Z"):
    mk = []
    if h2h:
        mk.append({"key": "h2h_h1", "last_update": stamp, "outcomes": [
            {"name": FEED_HOME, "price": h2h[0], "link": f"{key}/ml/h"},
            {"name": FEED_AWAY, "price": h2h[1], "link": f"{key}/ml/a"}]})
    if spreads:
        outs = []
        for home_pt, hp, ap in spreads:
            outs += [{"name": FEED_HOME, "price": hp, "point": home_pt, "link": f"{key}/h/{home_pt}",
                      "sid": f"{key}-h"},
                     {"name": FEED_AWAY, "price": ap, "point": -home_pt, "link": f"{key}/a/{home_pt}",
                      "sid": f"{key}-a"}]
        mk.append({"key": "spreads_h1", "last_update": stamp, "outcomes": outs})
    if totals:
        outs = []
        for pt, op, up in totals:
            outs += [{"name": "Over", "price": op, "point": pt}, {"name": "Under", "price": up, "point": pt}]
        mk.append({"key": "totals_h1", "last_update": stamp, "outcomes": outs})
    if tt:
        outs = []
        for team, pt, op, up in tt:
            outs += [{"name": "Over", "description": team, "price": op, "point": pt},
                     {"name": "Under", "description": team, "price": up, "point": pt}]
        mk.append({"key": "team_totals", "last_update": stamp, "outcomes": outs})
    return {"key": key, "title": key, "last_update": stamp, "markets": mk}


FETCHED = datetime(2026, 11, 10, 23, 50, 5, tzinfo=UTC)


def test_the_spread_is_stored_as_the_home_number_with_home_and_away_prices():
    body = {"bookmakers": [_book("fanduel", spreads=[(-3.5, -110, -110)])]}
    main, alt, ages, mk = feed.event_rows(body, GID, FEED_HOME, FEED_AWAY, FETCHED)
    r = main[0]
    assert (r["market"], r["spread_home"], r["home_price"], r["away_price"]) == (
        "spreads_h1", -3.5, -110, -110)
    assert r["home_link"] == "fanduel/h/-3.5" and r["away_link"] == "fanduel/a/-3.5"
    assert (r["source"], r["snapshot_type"], r["snapshot_at"]) == (
        feed.SOURCE, "open", "2026-11-10T23:49:00Z")
    assert ages == {"fanduel": 1.1} and mk == {"spreads_h1"}


def test_a_flipped_event_is_parsed_in_espn_s_orientation():
    """The feed calls ESPN's away team home; the caller swaps the names, so the
    stored number is still ESPN's home number (CLAUDE.md 4)."""
    body = {"bookmakers": [_book("fanduel", spreads=[(-3.5, -110, -110)])]}
    main, *_ = feed.event_rows(body, GID, FEED_AWAY, FEED_HOME, FETCHED)
    assert main[0]["spread_home"] == 3.5


def test_a_ladder_keeps_the_main_number_under_the_market_and_files_the_rest():
    body = {"bookmakers": [_book("betmgm", spreads=[(-2.5, -135, +110), (-3.5, -110, -110),
                                                    (-4.5, +110, -135)],
                                 totals=[(70.5, -110, -110), (68.5, -140, +115)])]}
    main, alt, *_ = feed.event_rows(body, GID, FEED_HOME, FEED_AWAY, FETCHED)
    sp = [r for r in main if r["market"] == "spreads_h1"]
    assert len(sp) == 1 and sp[0]["spread_home"] == -3.5
    assert sorted(r["spread_home"] for r in alt if r["market"] == "spreads_h1_alternate") == [-4.5, -2.5]
    assert [r["total_line"] for r in main if r["market"] == "totals_h1"] == [70.5]


def test_all_four_markets_are_stored_and_only_line_shop_books():
    body = {"bookmakers": [
        _book("draftkings", spreads=[(-3.5, -110, -110)], totals=[(70.5, -110, -110)],
              h2h=(-160, +130), tt=[(FEED_HOME, 37.5, -110, -110), (FEED_AWAY, 33.5, -115, -105)]),
        _book("unknownbook", spreads=[(-3.5, -110, -110)])]}
    main, alt, ages, mk = feed.event_rows(body, GID, FEED_HOME, FEED_AWAY, FETCHED)
    assert mk == {"h2h_h1", "spreads_h1", "totals_h1", "team_totals"}
    by = {r["market"]: r for r in main}
    assert by["h2h_h1"]["home_price"] == -160 and by["h2h_h1"]["away_price"] == 130
    assert by["team_totals_home"]["total_line"] == 37.5 and by["team_totals_away"]["total_line"] == 33.5
    assert {r["bookmaker"] for r in main + alt} == {"draftkings"}


# ── the fetch, with every outside call faked ─────────────────────────────────

class FakeConn:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def close(self):
        pass


class World:
    def __init__(self, monkeypatch, *, now, games=None, events=None, bodies=None, left=4_000_000,
                 burn=120_000, last=None):
        self.ledger, self.stored, self.calls = [], [], []
        games = {GID: {"game_date": DATE, "tip": TIP, "home": "Kansas", "away": "Duke"}} \
            if games is None else games
        self.events = [{"id": "ev1", "home_team": FEED_HOME, "away_team": FEED_AWAY,
                        "commence_time": "2026-11-11T00:00:00Z"}] if events is None else events
        self.bodies = {"ev1": {"bookmakers": [_book("fanduel", spreads=[(-3.5, -110, -110)])]}} \
            if bodies is None else bodies
        m = monkeypatch
        m.setattr(feed, "ensure_ledger", lambda conn: None)
        m.setattr(feed, "_known_games", lambda conn, ids: {g: v for g, v in games.items() if g in ids})
        m.setattr(feed, "last_fetches", lambda conn, ids, now=None, ok_only=True: dict(last or {}))
        m.setattr(feed.odds_quota, "latest_remaining", lambda conn: left)
        m.setattr(feed.odds_quota, "daily_burn", lambda conn: burn)
        m.setattr(feed, "persist_quota", lambda conn: None)
        m.setattr(feed.ncaab_teams, "make_resolver",
                  lambda conn, d, days_back=1, days_fwd=2: (
                      lambda h, a, ct: (GID, False) if (h, a) == (FEED_HOME, FEED_AWAY)
                      else (GID, True) if (h, a) == (FEED_AWAY, FEED_HOME) else None))
        m.setattr(feed, "_list_events", self._list)
        m.setattr(feed, "_get_event_odds", self._event)
        m.setattr(feed, "_insert_odds", lambda conn, rows: self.stored.extend(rows))
        m.setattr(feed, "_ledger_row", self._ledger)
        self.now = now

    def _list(self, key):
        self.calls.append(("events", key))
        return self.events

    def _event(self, key, ev, markets):
        self.calls.append(("event", ev, tuple(markets)))
        b = self.bodies.get(ev)
        if isinstance(b, Exception):
            raise b
        return b

    def _ledger(self, conn, requested_at, endpoint, mark, **kw):
        self.ledger.append({"endpoint": endpoint, "mark": mark, **kw})

    def run(self, ids=(GID,)):
        return feed.fetch_first_half(list(ids), conn=FakeConn(), now=self.now)


def test_a_due_game_is_bought_once_with_all_four_markets_and_ledgered(monkeypatch):
    w = World(monkeypatch, now=TIP - timedelta(minutes=10))
    out = w.run()
    assert out["fetched"] == [GID] and not out["failed"]
    assert w.calls == [("events", "basketball_ncaab"),
                       ("event", "ev1", ("h2h_h1", "spreads_h1", "totals_h1", "team_totals"))]
    ok = [r for r in w.ledger if r["endpoint"] == feed.EVENT_ODDS]
    assert len(ok) == 1 and ok[0]["ok"] and ok[0]["mark"] == "T-10" and ok[0]["game_id"] == GID
    assert [r["spread_home"] for r in w.stored] == [-3.5]


def test_the_decision_fetches_go_first(monkeypatch):
    g2 = "NCAAB_2026-11-10_iona_yale"
    games = {GID: {"game_date": DATE, "tip": TIP, "home": "Kansas", "away": "Duke"},
             g2: {"game_date": DATE, "tip": TIP + timedelta(minutes=10), "home": "Yale", "away": "Iona"}}
    events = [{"id": "ev1", "home_team": FEED_HOME, "away_team": FEED_AWAY, "commence_time": "x"},
              {"id": "ev2", "home_team": "Yale Bulldogs", "away_team": "Iona Gaels", "commence_time": "x"}]
    w = World(monkeypatch, now=TIP - timedelta(minutes=10), games=games, events=events,
              bodies={"ev1": {"bookmakers": []}, "ev2": {"bookmakers": []}})
    monkeypatch.setattr(feed.ncaab_teams, "make_resolver", lambda conn, d, days_back=1, days_fwd=2: (
        lambda h, a, ct: (GID, False) if h == FEED_HOME else (g2, False)))
    out = w.run([g2, GID])
    # g2 tips 10 minutes later and is due only its -20 call: the decision call goes first
    assert [c[1] for c in w.calls if c[0] == "event"] == ["ev1", "ev2"]
    assert out["marks"] == {GID: "T-10", g2: "T-20"}
    # an answer with no first-half market is still a fetch, not a failure
    assert out["no_first_half"] == [GID, g2] and not out["failed"]


def test_a_game_the_feed_does_not_list_fails_and_buys_nothing(monkeypatch):
    w = World(monkeypatch, now=TIP - timedelta(minutes=10), events=[])
    out = w.run()
    assert out["failed"] == [GID]
    assert [c[0] for c in w.calls] == ["events"]
    assert w.ledger[-1]["ok"] is False


def test_a_refused_or_broken_call_fails_and_the_next_tick_tries_again(monkeypatch):
    w = World(monkeypatch, now=TIP - timedelta(minutes=10), bodies={"ev1": None})
    assert w.run()["failed"] == [GID]
    w = World(monkeypatch, now=TIP - timedelta(minutes=10), bodies={"ev1": RuntimeError("timeout")})
    out = w.run()
    assert out["failed"] == [GID] and not w.stored
    assert "call failed" in w.ledger[-1]["detail"]


def test_a_tipped_game_is_never_called(monkeypatch):
    w = World(monkeypatch, now=TIP - timedelta(seconds=10))
    out = w.run()
    assert out["started"] == [GID] and w.calls == []


def test_under_the_balance_floor_nothing_is_bought_and_the_run_fails(monkeypatch):
    w = World(monkeypatch, now=TIP - timedelta(minutes=10), left=100_000, burn=120_000)
    out = w.run()
    assert out["failed"] == [GID] and "refused" in out and w.calls == []
    assert w.ledger[0]["ok"] is False and "not bought" in w.ledger[0]["detail"]


def test_above_the_floor_every_planned_game_is_bought(monkeypatch):
    """The floor keeps the account off zero; it is not a spending limit."""
    w = World(monkeypatch, now=TIP - timedelta(minutes=10), left=120_001, burn=120_000)
    assert w.run()["fetched"] == [GID]
    w = World(monkeypatch, now=TIP - timedelta(minutes=10), left=50, burn=None)
    assert w.run()["fetched"] == [GID]          # no burn on record: no floor


def test_the_reserve_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("NCAAB_FIRST_HALF_RESERVE_DAYS", "2")
    assert feed.reserve_days() == 2.0
    monkeypatch.setenv("NCAAB_FIRST_HALF_RESERVE_DAYS", "junk")
    assert feed.reserve_days() == 1.0


def test_the_kill_switch_stops_the_plan_and_the_fetch(monkeypatch):
    from scripts import ncaab_first_half_window as win
    monkeypatch.setenv("RUN_NCAAB_FIRST_HALF", "0")
    assert not win.enabled()
    assert not win.plan_tick()           # no connection opened: get_connection would raise
    called = []
    monkeypatch.setattr(feed, "fetch_first_half", lambda ids: called.append(ids) or {})
    win.main(["--fetch", GID])
    assert called == []


def test_the_source_is_not_the_purchase_s():
    from data.ingestors import ncaab_odds_history as hist
    assert feed.SOURCE not in (hist.NCAAB_DERIV_CLOSE_SOURCE, hist.NCAAB_DERIV_OPEN_SOURCE)
    assert feed.API_MARKETS == hist.DERIV_MARKETS
