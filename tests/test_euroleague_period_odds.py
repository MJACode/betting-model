"""The live EuroLeague period-and-full-game feed (data/ingestors/euroleague_period_odds.py)
and its window (scripts/euroleague_pregame_window.py).

No test here calls the Odds API: the event list and the event call are fakes
fed the feed's own payload shape, and the reads the fetch makes are patched.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import config  # noqa: E402
import data.ingestors.euroleague_period_odds as feed  # noqa: E402
from data.ingestors import euroleague_period_history as eph  # noqa: E402

UTC = timezone.utc
TIP = datetime(2026, 11, 20, 19, 0, tzinfo=UTC)
GID = "EUROLEAGUE_E2026_120"
FEED_HOME, FEED_AWAY = "Real Madrid", "Panathinaikos"


# ── the schedule ─────────────────────────────────────────────────────────────

def test_three_fetch_times_and_the_decision_one_is_ten_minutes_before_tip():
    s = feed.slots(TIP)
    assert [m for m, _ in s] == ["T-60", "T-10", "T-2"]
    assert dict(s)["T-10"] == TIP - timedelta(minutes=10)
    assert feed.DECISION_MARK == "T-10"


def test_the_decision_time_is_retried_and_the_others_are_one_attempt():
    t10 = TIP - timedelta(minutes=10)
    assert feed.due_mark(TIP, t10, None) == ("T-10", t10)
    # a failed -10 call is called again a minute later
    assert feed.due_mark(TIP, t10 + timedelta(minutes=1), None, t10 + timedelta(seconds=2))[0] == "T-10"
    # an ok call after it settles it
    assert feed.due_mark(TIP, t10 + timedelta(minutes=2), t10 + timedelta(seconds=4)) is None
    # a failed -60 call waits for the next time
    t60 = TIP - timedelta(minutes=60)
    assert feed.due_mark(TIP, t60 + timedelta(minutes=1), None, t60 + timedelta(seconds=3)) is None
    # nothing within 30 seconds of the tip, or after it
    assert feed.due_mark(TIP, TIP - timedelta(seconds=20), None) is None
    assert feed.due_mark(TIP, TIP + timedelta(minutes=1), None) is None
    assert feed.due_mark(TIP, t60 - timedelta(minutes=1), None) is None


def test_every_market_the_rules_read_is_asked_at_the_period_books():
    for m in ("h2h_h1", "totals_q1", "alternate_totals", "h2h", "spreads", "totals"):
        assert m in feed.API_MARKETS
    assert feed.books_param() == ",".join(config.EUROLEAGUE_PERIOD_BOOKMAKERS)
    assert len(config.EUROLEAGUE_PERIOD_BOOKMAKERS) <= 10      # one region
    assert feed.MAX_CREDITS_PER_CALL == len(feed.API_MARKETS)


def test_the_source_is_not_the_purchases_and_the_prune_protects_it():
    from data import prune_odds
    assert feed.SOURCE != eph.SOURCE
    assert feed.SOURCE in prune_odds.PROTECTED_SOURCES


# ── parsing ──────────────────────────────────────────────────────────────────

def _market(key, outcomes, stamp="2026-11-20T18:49:00Z"):
    return {"key": key, "last_update": stamp, "outcomes": outcomes}


def _body(home=FEED_HOME, away=FEED_AWAY, stamp="2026-11-20T18:49:00Z"):
    return {"id": "ev1", "home_team": home, "away_team": away, "bookmakers": [
        {"key": "fanduel", "markets": [
            _market("h2h_h1", [{"name": home, "price": -150}, {"name": away, "price": 125}], stamp),
            _market("totals_q1", [{"name": "Over", "point": 41.5, "price": -112},
                                  {"name": "Under", "point": 41.5, "price": -108},
                                  {"name": "Over", "point": 44.5, "price": 150},
                                  {"name": "Under", "point": 44.5, "price": -190}], stamp),
            _market("spreads", [{"name": home, "point": -4.5, "price": -110},
                                {"name": away, "point": 4.5, "price": -110}], stamp)]},
        {"key": "pinnacle", "markets": [
            _market("alternate_totals", [{"name": "Over", "point": 160.5, "price": -120},
                                         {"name": "Under", "point": 160.5, "price": 104},
                                         {"name": "Over", "point": 161.5, "price": 102},
                                         {"name": "Under", "point": 161.5, "price": -118}], stamp)]},
        {"key": "caesars", "markets": [_market("h2h", [{"name": home, "price": -200},
                                                       {"name": away, "price": 170}], stamp)]},
    ]}


FETCHED = datetime(2026, 11, 20, 18, 50, 5, tzinfo=UTC)


def test_the_purchases_parsing_the_main_number_and_this_feeds_source():
    rows, mkts, books, main = feed.event_rows(_body(), GID, FEED_HOME, FEED_AWAY, FETCHED, TIP)
    by = {(r["bookmaker"], r["market"], r.get("total_line") or r.get("spread_home")): r for r in rows}
    assert by[("fanduel", "totals_q1", 41.5)]["over_price"] == -112
    assert ("fanduel", "totals_q1_alternate", 44.5) in by
    assert by[("fanduel", "spreads", -4.5)]["home_price"] == -110
    assert {r["source"] for r in rows} == {feed.SOURCE}
    assert {r["snapshot_type"] for r in rows} == {"open"}
    assert "caesars" not in books                  # not a period book
    assert {"h2h_h1", "totals_q1", "spreads", "alternate_totals"} <= mkts
    assert main == len([r for r in rows if not r["market"].endswith("_alternate")
                        and not r["market"].startswith("alternate_")])


def test_a_flipped_event_is_parsed_in_euroleagues_orientation():
    # the feed calls PAN home; EuroLeague's home club is MAD: the caller swaps the names
    rows, *_ = feed.event_rows(_body(home=FEED_AWAY, away=FEED_HOME), GID, FEED_HOME, FEED_AWAY, FETCHED, TIP)
    h1 = next(r for r in rows if r["market"] == "h2h_h1")
    # FEED_HOME (MAD) was offered at +125 in the flipped body
    assert (h1["home_price"], h1["away_price"]) == (125, -150)
    sp = next(r for r in rows if r["market"] == "spreads")
    assert sp["spread_home"] == 4.5


def test_a_quote_updated_after_the_tip_is_not_stored():
    rows, *_ = feed.event_rows(_body(stamp="2026-11-20T19:00:30Z"), GID, FEED_HOME, FEED_AWAY, FETCHED, TIP)
    assert rows == []


# ── the fetch, with every outside call faked ─────────────────────────────────

class FakeConn:
    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


class World:
    def __init__(self, monkeypatch, *, now, games=None, events=None, bodies=None, left=4_000_000,
                 burn=120_000, last=None):
        self.ledger, self.stored, self.calls = [], [], []
        games = {GID: {"game_date": "2026-11-20", "tip": TIP, "home": "MAD", "away": "PAN"}} \
            if games is None else games
        self.events = [{"id": "ev1", "home_team": FEED_HOME, "away_team": FEED_AWAY,
                        "commence_time": "2026-11-20T19:00:00Z"}] if events is None else events
        self.bodies = {"ev1": _body()} if bodies is None else bodies
        m = monkeypatch
        m.setattr(feed, "ensure_ledger", lambda conn: None)
        m.setattr(feed, "_known_games", lambda conn, ids: {g: v for g, v in games.items() if g in ids})
        m.setattr(feed, "last_fetches", lambda conn, ids, ok_only=True: dict(last or {}))
        m.setattr(feed.odds_quota, "latest_remaining", lambda conn: left)
        m.setattr(feed.odds_quota, "daily_burn", lambda conn: burn)
        m.setattr(feed, "persist_quota", lambda conn: None)
        m.setattr(feed.et, "make_resolver", lambda conn, d, days_back=1, days_fwd=3: (
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

    def _event(self, key, ev, markets, bookmakers=None):
        self.calls.append(("event", ev, tuple(markets), bookmakers))
        b = self.bodies.get(ev)
        if isinstance(b, Exception):
            raise b
        return b

    def _ledger(self, conn, requested_at, endpoint, mark, **kw):
        self.ledger.append({"endpoint": endpoint, "mark": mark, **kw})

    def run(self, ids=(GID,)):
        return feed.fetch_periods(list(ids), conn=FakeConn(), now=self.now)


def test_a_due_game_is_bought_once_at_the_period_books_and_ledgered(monkeypatch):
    w = World(monkeypatch, now=TIP - timedelta(minutes=10))
    out = w.run()
    assert out["fetched"] == [GID] and not out["failed"]
    ev = [c for c in w.calls if c[0] == "event"]
    assert len(ev) == 1 and ev[0][3] == feed.books_param() and ev[0][2] == tuple(feed.API_MARKETS)
    ok = [r for r in w.ledger if r["endpoint"] == feed.EVENT_ODDS]
    assert len(ok) == 1 and ok[0]["ok"] and ok[0]["mark"] == "T-10" and ok[0]["game_id"] == GID
    assert w.stored and {r["game_id"] for r in w.stored} == {GID}


def test_the_decision_fetch_goes_first(monkeypatch):
    g2 = "EUROLEAGUE_E2026_121"
    games = {GID: {"game_date": "2026-11-20", "tip": TIP, "home": "MAD", "away": "PAN"},
             g2: {"game_date": "2026-11-20", "tip": TIP + timedelta(minutes=50), "home": "OLY", "away": "ZAL"}}
    events = [{"id": "ev1", "home_team": FEED_HOME, "away_team": FEED_AWAY, "commence_time": "x"},
              {"id": "ev2", "home_team": "Olympiacos", "away_team": "Žalgiris", "commence_time": "x"}]
    w = World(monkeypatch, now=TIP - timedelta(minutes=10), games=games, events=events,
              bodies={"ev1": {"bookmakers": []}, "ev2": {"bookmakers": []}})
    monkeypatch.setattr(feed.et, "make_resolver", lambda conn, d, days_back=1, days_fwd=3: (
        lambda h, a, ct: (GID, False) if h == FEED_HOME else (g2, False)))
    out = w.run([g2, GID])
    assert [c[1] for c in w.calls if c[0] == "event"] == ["ev1", "ev2"]
    assert out["marks"] == {GID: "T-10", g2: "T-60"}
    assert out["no_markets"] == [GID, g2] and not out["failed"]


def test_a_game_the_feed_does_not_list_fails_and_buys_nothing(monkeypatch):
    w = World(monkeypatch, now=TIP - timedelta(minutes=10), events=[])
    out = w.run()
    assert out["failed"] == [GID] and [c[0] for c in w.calls] == ["events"]
    assert w.ledger[-1]["ok"] is False


def test_a_refused_or_broken_call_fails(monkeypatch):
    w = World(monkeypatch, now=TIP - timedelta(minutes=10), bodies={"ev1": None})
    assert w.run()["failed"] == [GID]
    w = World(monkeypatch, now=TIP - timedelta(minutes=10), bodies={"ev1": RuntimeError("timeout")})
    out = w.run()
    assert out["failed"] == [GID] and not w.stored and "call failed" in w.ledger[-1]["detail"]


def test_a_game_about_to_tip_is_never_called(monkeypatch):
    w = World(monkeypatch, now=TIP - timedelta(seconds=10))
    out = w.run()
    assert out["started"] == [GID] and w.calls == []


def test_under_the_balance_floor_nothing_is_bought_and_the_run_fails(monkeypatch):
    w = World(monkeypatch, now=TIP - timedelta(minutes=10), left=100_000, burn=120_000)
    out = w.run()
    assert out["failed"] == [GID] and "refused" in out and w.calls == []
    assert w.ledger[0]["ok"] is False and "not bought" in w.ledger[0]["detail"]
    w = World(monkeypatch, now=TIP - timedelta(minutes=10), left=120_001, burn=120_000)
    assert w.run()["fetched"] == [GID]
    monkeypatch.setenv("EUROLEAGUE_PERIOD_RESERVE_DAYS", "2")
    w = World(monkeypatch, now=TIP - timedelta(minutes=10), left=200_000, burn=120_000)
    assert w.run()["failed"] == [GID]


def test_the_switches_stop_the_fetch(monkeypatch):
    from scripts import euroleague_pregame_window as win
    called = []
    monkeypatch.setattr(feed, "fetch_periods", lambda ids: called.append(ids) or {})
    monkeypatch.setenv("RUN_EUROLEAGUE_PERIOD_FEED", "0")
    win.main(["--fetch", GID])
    monkeypatch.setenv("RUN_EUROLEAGUE_PERIOD_FEED", "1")
    monkeypatch.setenv("RUN_EUROLEAGUE_PREGAME", "0")
    win.main(["--fetch", GID])
    assert called == []
    assert not win.plan_tick()           # no connection opened: get_connection would raise
