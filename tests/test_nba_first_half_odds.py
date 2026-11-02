"""The live NBA first-half feed (data/ingestors/nba_first_half_odds.py): one
per-event call per planned game, stored before nba_first_half_total_luck decides.

No test here calls the Odds API: the event list and the event call are fakes fed
recorded-shape payloads, and the database is tests/test_nba_team_total_odds.FakeDB
extended by this model's two ledgers (H1DB). The one test that runs the team-total
feed beside this one patches both feeds' calls.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import data.ingestors.nba_first_half_odds as h1  # noqa: E402
import data.ingestors.nba_team_total_odds as ttfeed  # noqa: E402
from tests.test_nba_team_total_odds import (GID, UTC, Clock, FakeDB, FakeFeed, _Cur,  # noqa: E402
                                            book, et, event)

H1_DECISIONS = "nba_first_half_total_luck_decisions"


class H1DB(FakeDB):
    """FakeDB with this model's ledger and decisions table."""

    TABLES = FakeDB.TABLES + (h1.LEDGER_TABLE, H1_DECISIONS)

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if s.startswith(f"INSERT INTO {h1.LEDGER_TABLE}"):
            self._begin()
            self.log.append(("sql", s))
            self.pending.append((h1.LEDGER_TABLE, {**params, "fetch_at": self.txn_now}))
            return _Cur([])
        if s.startswith(f"INSERT INTO {H1_DECISIONS}"):
            self._begin()
            self.log.append(("sql", s))
            if any(r["game_id"] == params["game_id"] for r in self._all(H1_DECISIONS)):
                return _Cur([])
            self.pending.append((H1_DECISIONS, dict(params)))
            return _Cur([(params["game_id"],)])
        if f"FROM {h1.LEDGER_TABLE}" in s:
            self._begin()
            self.log.append(("sql", s))
            best: dict[str, datetime] = {}
            for r in self._select(h1.LEDGER_TABLE, s, params):
                if r["game_id"] is not None:
                    best[r["game_id"]] = max(best.get(r["game_id"], r["fetch_at"]), r["fetch_at"])
            return _Cur(best.items())
        if f"FROM {H1_DECISIONS}" in s:
            self._begin()
            self.log.append(("sql", s))
            return _Cur([(r["game_id"],) for r in self._select(H1_DECISIONS, s, params)])
        return super().execute(sql, params)


def h1_book(key, rungs, updated="2026-11-05T23:33:12Z", market_update=True):
    """A bookmaker block: `rungs` (line, over, under) of the first-half total."""
    outs = []
    for line, over, under in rungs:
        if over is not None:
            outs.append({"name": "Over", "price": over, "point": line,
                         "link": f"https://{key}/over/{line}", "sid": f"{key}-Over-{line}"})
        if under is not None:
            outs.append({"name": "Under", "price": under, "point": line,
                         "link": f"https://{key}/under/{line}", "sid": f"{key}-Under-{line}"})
    mk = {"key": "totals_h1", "outcomes": outs}
    if market_update:
        mk["last_update"] = updated
    return {"key": key, "title": key, "last_update": "2026-11-05T23:30:00Z", "markets": [mk]}


def install(f: FakeFeed, monkeypatch, db=None, module=h1):
    """Patch one feed module's two calls; with `db`, each is written to db.log."""
    def logged(fn, which):
        def call(*a, **k):
            if db is not None:
                db.log.append(("api", which))
            return fn(*a, **k)
        return call
    monkeypatch.setattr(module, "_list_events", logged(f.list_events, "events"))
    monkeypatch.setattr(module, "_get_event_odds", logged(f.event_odds, "event_odds"))


def world(monkeypatch, bodies=None, events=None, games=None, **kw):
    clock = Clock(et(2026, 11, 5, 18, 34, 0))
    db = H1DB(clock, games={GID: ("MIL", "BOS")} if games is None else games)
    f = FakeFeed(clock, [event()] if events is None else events,
                 {"ev-mil": [h1_book("fanduel", [(112.5, -115, -105)]),
                             h1_book("pinnacle", [(112.5, -108, -108)])]}
                 if bodies is None else bodies, **kw)
    install(f, monkeypatch, db)
    return clock, db, f


# ── parsing ──────────────────────────────────────────────────────────────────

def test_a_book_s_first_half_market_reads_its_line_and_prices():
    rows = h1.parse_first_half(h1_book("fanduel", [(112.5, -115, -105)])["markets"])
    assert len(rows) == 1
    r = rows[0]
    assert (r["market"], r["total_line"], r["over_price"], r["under_price"]) == (
        "totals_h1", 112.5, -115, -105)
    assert r["over_link"] == "https://fanduel/over/112.5" and r["under_sid"] == "fanduel-Under-112.5"


def test_another_market_in_the_same_book_is_not_read():
    b = h1_book("fanduel", [(112.5, -115, -105)])
    b["markets"].append({"key": "team_totals", "outcomes": [
        {"name": "Over", "description": "Milwaukee Bucks", "price": -110, "point": 113.5}]})
    b["markets"].append({"key": "totals_q1", "outcomes": [
        {"name": "Over", "price": -110, "point": 56.5}]})
    rows = h1.parse_first_half(b["markets"])
    assert [r["total_line"] for r in rows] == [112.5]


def test_each_book_s_main_number_is_filed_under_the_market_and_the_rest_under_the_alternate():
    """RULE (models/nba_book_numbers.split_main_rungs): closest to even keeps
    totals_h1, the rest go under totals_h1_alternate, a one-sided rung never main."""
    body = {"bookmakers": [h1_book("fanduel", [(110.5, -150, +120), (112.5, -112, -108),
                                               (114.5, +130, None)])]}
    main, alt, ages = h1.event_rows(body, GID, "open", et(2026, 11, 5, 18, 34, 0))
    assert [(r["market"], r["total_line"]) for r in main] == [("totals_h1", 112.5)]
    assert sorted((r["market"], r["total_line"]) for r in alt) == [
        ("totals_h1_alternate", 110.5), ("totals_h1_alternate", 114.5)]
    assert ages["fanduel"] == pytest.approx(0.8, abs=0.01)
    row = main[0]
    assert (row["game_id"], row["sport"], row["snapshot_type"], row["source"], row["bookmaker"]) == (
        GID, "NBA", "open", h1.SOURCE, "fanduel")
    assert row["snapshot_at"] == "2026-11-05T23:33:12Z"
    assert "home_price" in row and row["home_price"] is None


def test_a_book_outside_the_line_shop_is_not_stored():
    body = {"bookmakers": [h1_book("some_new_book", [(112.5, -110, -110)]),
                           h1_book("draftkings", [(112.5, -110, -110)])]}
    main, alt, _ = h1.event_rows(body, GID, "open", et(2026, 11, 5, 18, 34, 0))
    assert [r["bookmaker"] for r in main] == ["draftkings"] and alt == []


def test_with_no_market_stamp_the_book_s_own_then_the_fetch_time_is_the_snapshot():
    at = et(2026, 11, 5, 18, 34, 0)
    b = h1_book("fanduel", [(112.5, -110, -110)], market_update=False)
    main, _, _ = h1.event_rows({"bookmakers": [b]}, GID, "open", at)
    assert main[0]["snapshot_at"] == "2026-11-05T23:30:00Z"
    b.pop("last_update")
    main, _, _ = h1.event_rows({"bookmakers": [b]}, GID, "open", at)
    assert main[0]["snapshot_at"] == "2026-11-05T23:34:00Z"


# ── the fetch ────────────────────────────────────────────────────────────────

def test_it_asks_for_the_first_half_only_and_stores_before_the_decision(monkeypatch):
    """RULE: its OWN call, markets=totals_h1 alone: one model's market never rides
    the other's request."""
    clock, db, f = world(monkeypatch)
    out = h1.fetch_first_half([GID], "open", conn=db)
    calls = [c for c in f.calls if c[0] == "event_odds"]
    assert calls == [("event_odds", "ev-mil", ("totals_h1",))]
    assert out["fetched"] == [GID] and out["failed"] == []
    assert {r["market"] for r in db.rows["odds"]} == {"totals_h1"}
    assert {r["source"] for r in db.rows["odds"]} == {h1.SOURCE}
    assert {r["bookmaker"] for r in db.rows["odds"]} == {"fanduel", "pinnacle"}


def test_the_stored_rows_are_dated_by_the_response_not_the_read_before_it(monkeypatch):
    """RULE: created_at is the fetch instant. A read left open across the call
    would date every row to before its fetch."""
    clock, db, f = world(monkeypatch, call_s=7.0)
    start = clock()
    h1.fetch_first_half([GID], "open", conn=db)
    created = {r["created_at"] for r in db.rows["odds"]}
    assert len(created) == 1
    t = datetime.fromisoformat(created.pop().replace("+00", "+00:00"))
    assert t == start + timedelta(seconds=14)       # the event list, then the event call
    event_row = [r for r in db.rows[h1.LEDGER_TABLE] if r["endpoint"] == h1.EVENT_ODDS][0]
    assert event_row["fetch_at"] == t


def test_the_ledger_records_every_call_and_the_bill(monkeypatch):
    """RULE: credits_last is the feed's own x-requests-last for THAT call; a call
    that recorded none reads None, never an assumed cost."""
    clock, db, f = world(monkeypatch, last="3")
    out = h1.fetch_first_half([GID], "open", conn=db)
    rows = db.rows[h1.LEDGER_TABLE]
    assert [r["endpoint"] for r in rows] == [h1.EVENTS, h1.EVENT_ODDS]
    ev = rows[1]
    assert (ev["ok"], ev["game_id"], ev["event_id"], ev["credits_last"]) == (True, GID, "ev-mil", 3.0)
    assert (ev["rows_stored"], ev["main_rows"], ev["books"]) == (2, 2, "fanduel,pinnacle")
    assert out["credits"][GID] == 3.0 and out["credits"]["events"] == 0.0


def test_a_200_with_no_first_half_total_is_a_fetch(monkeypatch):
    """RULE: the game is decided with nothing offered, as the lab's one purchase
    would have been."""
    clock, db, f = world(monkeypatch, bodies={"ev-mil": []})
    out = h1.fetch_first_half([GID], "open", conn=db)
    assert out["fetched"] == [GID] and out["no_first_half"] == [GID] and out["failed"] == []
    assert db.rows["odds"] == []
    assert set(h1.fetches(db, [GID], "open")) == {GID}


@pytest.mark.parametrize("how", ["raises", "404_or_422"])
def test_a_failed_call_is_not_a_fetch(monkeypatch, how):
    """RULE: a call that raised, or an HTTP 404 or 422, stores nothing, is not a
    fetch, and the next tick asks again."""
    if how == "raises":
        clock, db, f = world(monkeypatch, fail={"ev-mil"})
    else:
        clock, db, f = world(monkeypatch, bodies={"other": []})
    out = h1.fetch_first_half([GID], "open", conn=db)
    assert out["failed"] == [GID] and out["fetched"] == []
    assert h1.fetches(db, [GID], "open") == {}
    row = [r for r in db.rows[h1.LEDGER_TABLE] if r["endpoint"] == h1.EVENT_ODDS][0]
    assert row["ok"] is False and row["detail"]


def test_only_the_named_games_are_bought(monkeypatch):
    """RULE: the event list is matched to the ids BEFORE any paid call. A game the
    list does not hold fails with no call; a game not in `games` is not asked."""
    games = {GID: ("MIL", "BOS"), "NBA_2026-11-05_LAL_NYK": ("NYK", "LAL")}
    clock, db, f = world(monkeypatch, games=games)
    out = h1.fetch_first_half([GID, "NBA_2026-11-05_LAL_NYK", "NBA_2026-11-05_XXX_YYY"],
                              "open", conn=db)
    assert out["not_in_games"] == ["NBA_2026-11-05_XXX_YYY"]
    assert out["failed"] == ["NBA_2026-11-05_LAL_NYK"]
    assert [c for c in f.calls if c[0] == "event_odds"] == [
        ("event_odds", "ev-mil", ("totals_h1",))]


def test_the_list_failing_fails_every_game_with_no_paid_call(monkeypatch):
    clock, db, f = world(monkeypatch)

    def boom(sport_key):
        raise RuntimeError("HTTP 500")
    monkeypatch.setattr(h1, "_list_events", boom)
    out = h1.fetch_first_half([GID], "open", conn=db)
    assert out["failed"] == [GID]
    assert not [c for c in f.calls if c[0] == "event_odds"]


def test_a_close_is_filed_close_and_only_an_ok_close_counts_as_taken(monkeypatch):
    clock, db, f = world(monkeypatch)
    h1.fetch_first_half([GID], "close", conn=db)
    assert {r["snapshot_type"] for r in db.rows["odds"]} == {"close"}
    assert h1.closes_taken(db, [GID]) == {GID} and h1.fetches(db, [GID], "open") == {}
    f.fail.add("ev-mil")
    clock2 = Clock(et(2026, 11, 5, 19, 10, 0))
    db2 = H1DB(clock2, games={GID: ("MIL", "BOS")})
    h1.fetch_first_half([GID], "close", conn=db2)
    assert h1.closes_taken(db2, [GID]) == set()


def test_an_unknown_snapshot_type_is_refused(monkeypatch):
    clock, db, f = world(monkeypatch)
    with pytest.raises(ValueError, match="snapshot_type"):
        h1.fetch_first_half([GID], "in_play", conn=db)


def test_a_store_that_fails_rolls_back_and_is_not_a_fetch(monkeypatch):
    clock, db, f = world(monkeypatch)

    def boom(conn, rows):
        raise RuntimeError("db went away")
    monkeypatch.setattr(h1, "_insert_odds", boom)
    out = h1.fetch_first_half([GID], "open", conn=db)
    assert out["failed"] == [GID] and h1.fetches(db, [GID], "open") == {}


# ── each model's decision is its own ─────────────────────────────────────────

@pytest.mark.parametrize("first_half_body", [[], None, "raises"])
def test_a_first_half_that_comes_back_empty_or_fails_does_not_touch_the_team_total(
        monkeypatch, first_half_body):
    """RULE: a 200 with no first-half total, a refused call and a failed call
    leave the team-total model's fetch, rows and ledger standing."""
    clock = Clock(et(2026, 11, 5, 18, 34, 0))
    db = H1DB(clock, games={GID: ("MIL", "BOS")})
    tt_f = FakeFeed(clock, [event()], {"ev-mil": [book("fanduel", [(113.5, -115, -105)])]})
    fail = {"ev-mil"} if first_half_body == "raises" else set()
    h1_bodies = {} if first_half_body is None else {"ev-mil": first_half_body or []}
    h1_f = FakeFeed(clock, [event()], h1_bodies, fail=fail)
    install(tt_f, monkeypatch, db, module=ttfeed)
    install(h1_f, monkeypatch, db, module=h1)
    assert ttfeed.fetch_team_totals([GID], "open", conn=db)["fetched"] == [GID]
    h1.fetch_first_half([GID], "open", conn=db)
    assert set(ttfeed.fetches(db, [GID], "open")) == {GID}
    assert {r["market"] for r in db.rows["odds"]} == {"team_totals_home"}
    assert all(r["game_id"] != GID or r["endpoint"] == ttfeed.EVENT_ODDS
               for r in db.rows[ttfeed.LEDGER_TABLE] if r["game_id"])


@pytest.mark.parametrize("team_total_body", [[], None, "raises"])
def test_a_team_total_that_comes_back_empty_or_fails_does_not_touch_the_first_half(
        monkeypatch, team_total_body):
    """RULE, the reverse: the team-total model's bad call leaves the first half's
    fetch standing, so its card can decide."""
    clock = Clock(et(2026, 11, 5, 18, 34, 0))
    db = H1DB(clock, games={GID: ("MIL", "BOS")})
    fail = {"ev-mil"} if team_total_body == "raises" else set()
    tt_bodies = {} if team_total_body is None else {"ev-mil": team_total_body or []}
    tt_f = FakeFeed(clock, [event()], tt_bodies, fail=fail)
    h1_f = FakeFeed(clock, [event()], {"ev-mil": [h1_book("fanduel", [(112.5, -115, -105)])]})
    install(tt_f, monkeypatch, db, module=ttfeed)
    install(h1_f, monkeypatch, db, module=h1)
    ttfeed.fetch_team_totals([GID], "open", conn=db)
    assert h1.fetch_first_half([GID], "open", conn=db)["fetched"] == [GID]
    assert set(h1.fetches(db, [GID], "open")) == {GID}
    assert {r["market"] for r in db.rows["odds"]} == {"totals_h1"}


def test_each_model_reads_its_own_ledger():
    """The card decides on this ledger's newest ok row; the team-total card on
    its own. Two tables, two sources."""
    assert h1.LEDGER_TABLE != ttfeed.LEDGER_TABLE and h1.SOURCE != ttfeed.SOURCE


# ── the rows' keepers ────────────────────────────────────────────────────────

def test_the_prune_protects_this_source_by_its_writer_s_own_name():
    """RULE: the prune's keepers are one row per (game, market, book): they would
    delete the decision fetch a close follows, and a close the record reads."""
    from data.prune_odds import PROTECTED_SOURCES
    assert h1.SOURCE in PROTECTED_SOURCES


def test_the_source_is_not_the_purchase_s_marker():
    """nba_odds_history treats a row whose source starts with its own marker as
    already bought, and the lab's loader reads that source as a purchase."""
    from data.ingestors.nba_odds_history import DERIV_SOURCE
    assert not h1.SOURCE.startswith(DERIV_SOURCE)


def test_both_tables_are_worker_only():
    """RULE: the app never reads the ledgers; a new table on an exposed schema is
    locked down by name."""
    from data.anon_readable import WORKER_ONLY_TABLES
    assert {h1.LEDGER_TABLE, H1_DECISIONS} <= set(WORKER_ONLY_TABLES)


def test_the_utc_helper_is_the_one_the_team_total_feed_uses():
    assert h1._z is ttfeed._z and h1._when is ttfeed._when and h1.event_ids is ttfeed.event_ids
    assert UTC is not None
