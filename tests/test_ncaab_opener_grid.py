"""The NCAAB opener grid: a bulk snapshot at every grid time before every tip.

WHY. The game-line purchase (mode `lines`) bought three kinds of hour: the
evening before, mid-morning, and the hour before each tip. A book that first
posts its line between two of those is dated only to the gap, and the gap is
over two hours for 42-68% of first spreads and totals, depending on the book
(opener-route design, 2026-10-30). The grid buys a snapshot every 60 or 30 minutes from 72
hours before each tip to the tip, so each book's first posted full-game line
is dated to the step. Nothing is queued: the spend needs mike's approval.

These pin what decides the spend (the grid, the two ledgers, the floor, the
ceiling), what is stored (never a quote already in `odds`), what a dry run may
do (nothing but read, on the read-only connection), and the job. The ledgers
and the read-back against a real Postgres are tests/test_ncaab_opener_grid_pg.py.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

import pytest

import tracking.job_queue as jq
from data.ingestors import ncaab_odds_history as h
from data.ingestors import odds_ingestor as oi
from tests.test_ncaab_odds_history import (GAMES, KSU_DUKE, REGISTRY, UK_DUKE, FakeConn,
                                           FakeMeter, ReplayConn, Resp, _event, _t,
                                           contract_process_events)


def _game(gid, tip, game_date=None):
    return {"game_id": gid, "game_date": game_date or tip[:10], "commence_time": tip,
            "home_espn_id": 96, "away_espn_id": 150}


# ── the grid ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("step,n", [(60, 72), (30, 144)])
def test_a_tip_on_the_hour_wants_every_grid_time_from_72_hours_before_up_to_it(step, n):
    plan = h.grid_plan([_game("g", "2025-11-20T17:00:00Z")], step, held=set())
    assert len(plan.window) == n and plan.pre == [] and len(plan.todo) == n
    assert plan.window[0] == _t("2025-11-17T17:00Z")
    assert plan.window[-1] == _t("2025-11-20T16:00Z") + timedelta(minutes=60 - step)


@pytest.mark.parametrize("step,first,last,n", [
    (60, "2025-11-17T02:00Z", "2025-11-20T01:00Z", 72),
    (30, "2025-11-17T01:30Z", "2025-11-20T01:00Z", 144),
])
def test_grid_times_are_on_the_clock_not_on_the_tip(step, first, last, n):
    """A 01:20Z tip: the grid is :00 (and :30), never :20. 01:00 is before the
    tip and wanted; 01:30 is after it and not. 72 hours before is 01:20 three
    days earlier, so the first wanted time is the next one on the clock."""
    plan = h.grid_plan([_game("g", "2025-11-20T01:20:00Z", "2025-11-19")], step, held=set())
    assert (plan.window[0], plan.window[-1], len(plan.window)) == (_t(first), _t(last), n)
    assert all(w.minute % step == 0 and w.second == 0 for w in plan.window)


def test_games_that_share_grid_times_share_the_snapshot():
    games = [_game("a", "2025-11-20T17:00:00Z"), _game("b", "2025-11-20T18:00:00Z")]
    assert len(h.grid_plan(games, 60, held=set()).window) == 73


def test_a_game_with_no_tip_adds_nothing():
    plan = h.grid_plan([_game("g", "2025-11-20T17:00:00Z"),
                        dict(_game("x", "2025-11-21T17:00:00Z"), commence_time=None)],
                       60, held=set())
    assert len(plan.window) == 72


def test_a_held_time_is_not_bought_again_but_still_counted_in_the_window():
    held = {_t("2025-11-19T22:00Z"), _t("2025-11-20T15:00Z")}
    plan = h.grid_plan([_game("g", "2025-11-20T17:00:00Z")], 60, held=held)
    assert len(plan.window) == 72 and len(plan.todo) == 70
    assert held.isdisjoint(plan.todo) and plan.window_held == 2


def test_a_half_hour_time_is_not_treated_as_already_bought_in_the_plan():
    """The ledger held 22:00. 22:30 is a different snapshot and is bought."""
    plan = h.grid_plan([_game("g", "2025-11-20T17:00:00Z")], 30, held={_t("2025-11-19T22:00Z")})
    assert _t("2025-11-19T22:30Z") in plan.todo and _t("2025-11-19T22:00Z") not in plan.todo
    assert len(plan.todo) == 143


@pytest.mark.parametrize("step,n", [(60, 168), (30, 336)])
def test_the_pre_start_window_runs_from_ten_days_to_72_hours_before_the_first_tip(step, n):
    games = [_game("first", "2025-11-03T13:00:00Z"), _game("later", "2025-11-10T17:00:00Z")]
    without = h.grid_plan(games, step, held=set())
    with_pre = h.grid_plan(games, step, held=set(), pre_start=True)
    assert without.pre == [] and len(with_pre.pre) == n
    assert with_pre.pre[0] == _t("2025-10-24T13:00Z")
    assert with_pre.pre[-1] == _t("2025-10-31T13:00Z") - timedelta(minutes=step)
    assert set(with_pre.pre).isdisjoint(with_pre.window)
    assert len(with_pre.todo) == len(without.todo) + n


def test_each_season_has_its_own_pre_start_window():
    games = [_game("s25", "2024-11-04T16:00:00Z"), _game("s26", "2025-11-03T13:00:00Z")]
    plan = h.grid_plan(games, 60, held=set(), pre_start=True)
    assert len(plan.pre) == 2 * 168


def test_the_grid_only_allows_60_or_30_minutes():
    with pytest.raises(ValueError):
        h.grid_plan([_game("g", "2025-11-20T17:00:00Z")], 15, held=set())


# ── the ledgers: the hour in the shared pull ledger, the half hour beside it ─
#
# odds_history_pulls is shared by every sport's history purchase and keyed on
# (sport, date, hour). The grid files a time on the hour there, exactly as
# every other purchase does, and a half hour in odds_history_fetches, keyed on
# the instant, the table the NBA purchase already files its off-the-hour
# fetches in. The shared key is never changed: under a four-column key, any
# older copy of a purchase whose ON CONFLICT names three columns pays for a
# snapshot, fails to ledger it, and rolls its rows back (the 2026-10-30
# review, reproduced on a scratch Postgres).

class GridDb:
    """An in-memory database for the grid's snapshots: the shared pull ledger
    {(sport, date, hour)}, the fetch ledger {(sport, instant)} and the `odds`
    rows stored, answering the statements _buy_snapshot sends."""

    def __init__(self, pulls=(), fetches=(), odds=None):
        self.pulls, self.fetches = set(pulls), set(fetches)
        self.odds = [] if odds is None else odds
        self.sql: list[tuple[str, object]] = []
        self.commits = 0
        self._ans: list = []

    def execute(self, sql, params=None):
        q = " ".join(sql.split())
        self.sql.append((q, params))
        self._ans = []
        if q.startswith("SELECT 1 FROM odds_history_pulls"):
            self._ans = [(1,)] if tuple(params[:3]) in self.pulls else []
        elif q.startswith("SELECT 1 FROM odds_history_fetches"):
            self._ans = [(1,)] if (params[0], params[1]) in self.fetches else []
        elif q.startswith("INSERT INTO odds_history_pulls"):
            self.pulls.add(tuple(params[:3]))
        elif q.startswith("INSERT INTO odds_history_fetches"):
            self.fetches.add((params[0], params[1]))
        elif "FROM odds WHERE" in q:
            source, gids, stamps = params
            self._ans = [tuple(r.get(c) for c in ("game_id", "market", "bookmaker", "snapshot_at",
                                                  *h._ROW_VALUES))
                         for r in self.odds if r.get("source") == source
                         and r["game_id"] in gids and r["snapshot_at"] in stamps]
        return self

    def executemany(self, sql, rows):
        self.sql.append((" ".join(sql.split()), list(rows)))

    def fetchone(self):
        return self._ans[0] if self._ans else None

    def fetchall(self):
        return self._ans

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def close(self):
        pass


def _snap(monkeypatch, db, when, events=(), keeper=None):
    monkeypatch.setattr(h, "_process_events", contract_process_events)
    monkeypatch.setattr(h, "_insert_odds", lambda c, rows: db.odds.extend(dict(r) for r in rows))
    meter = FakeMeter(lambda u, p: Resp(body={"timestamp": p["date"], "data": list(events)}))
    stats = defaultdict(int)
    tips = {g["game_id"]: g["commence_time"] for g in GAMES}
    ok = h._buy_snapshot(db, meter, tips, h.EventResolver(REGISTRY, GAMES), _t(when), stats,
                         keeper)
    return ok, meter, stats


def test_a_half_hour_is_ledgered_in_the_fetch_ledger_not_the_shared_pull_ledger(monkeypatch):
    """The ledger held 22:00. 22:30 is a different snapshot: it is bought, and
    its row goes to the fetch ledger, keyed on the instant."""
    db = GridDb(pulls={("NCAAB", "2025-11-19", 22)})
    ok, meter, stats = _snap(monkeypatch, db, "2025-11-19T22:30:00Z")
    assert ok and len(meter.calls) == 1 and stats.get("skipped_held", 0) == 0
    assert meter.calls[0][1]["date"] == "2025-11-19T22:30:00Z"
    assert db.pulls == {("NCAAB", "2025-11-19", 22)}                     # untouched
    assert db.fetches == {("NCAAB", _t("2025-11-19T22:30Z"))}
    (q, params), = [(q, p) for q, p in db.sql if q.startswith("INSERT INTO odds_history_fetches")]
    assert "ON CONFLICT (sport, requested_at)" in q and "opener_grid" in params
    assert not [q for q, _ in db.sql if q.startswith("INSERT INTO odds_history_pulls")]


def test_a_held_half_hour_is_not_bought_again(monkeypatch):
    db = GridDb(fetches={("NCAAB", _t("2025-11-19T22:30Z"))})
    ok, meter, stats = _snap(monkeypatch, db, "2025-11-19T22:30:00Z")
    assert ok and meter.calls == [] and stats["skipped_held"] == 1


def test_the_hour_is_held_and_ledgered_as_every_other_purchase_ledgers_it(monkeypatch):
    held = GridDb(pulls={("NCAAB", "2025-11-19", 22)})
    ok, meter, stats = _snap(monkeypatch, held, "2025-11-19T22:00:00Z")
    assert ok and meter.calls == [] and stats["skipped_held"] == 1
    assert held.sql[0][1] == ("NCAAB", "2025-11-19", 22)
    db = GridDb()
    ok, meter, _ = _snap(monkeypatch, db, "2025-11-19T22:00:00Z")
    assert ok and len(meter.calls) == 1 and db.fetches == set()
    (q, params), = [(q, p) for q, p in db.sql if q.startswith("INSERT INTO odds_history_pulls")]
    assert "ON CONFLICT (sport, snapshot_date, hour_utc) DO UPDATE" in q and "minute" not in q
    assert params == ("NCAAB", "2025-11-19", 22, 0)


def test_a_half_hour_row_does_not_read_as_the_hour_bought(monkeypatch):
    """The lines purchase wants 22:00; the grid holds only 22:30."""
    db = GridDb(fetches={("NCAAB", _t("2025-11-19T22:30Z"))})
    ok, meter, _ = _snap(monkeypatch, db, "2025-11-19T22:00:00Z")
    assert ok and len(meter.calls) == 1


def test_the_held_times_are_both_ledgers_read_on_the_instant():
    conn = FakeConn(answers={
        "FROM odds_history_pulls": [("2025-11-17", 22), ("2025-11-18", 15)],
        "FROM odds_history_fetches": [(_t("2025-11-17T22:30Z"),), (datetime(2025, 11, 18, 1, 30),)]})
    assert h._held_instants(conn) == {_t("2025-11-17T22:00Z"), _t("2025-11-18T15:00Z"),
                                      _t("2025-11-17T22:30Z"), _t("2025-11-18T01:30Z")}
    (_, params), = [(q, p) for q, p in conn.sql if "FROM odds_history_fetches" in q]
    assert params == ("NCAAB",)                                # never the NBA's fetches


def test_the_lines_plan_reads_both_ledgers(monkeypatch):
    conn = FakeConn(answers={"FROM odds_history_pulls": [("2025-11-18", 15)],
                             "FROM odds_history_fetches": [(_t("2025-11-17T22:30Z"),)]})
    monkeypatch.setattr(h, "_season_games", lambda c, a, b: [UK_DUKE])
    _, pairs, todo = h.plan_lines(conn, 2026, 2026)
    # D-1 22Z is wanted on the hour: the 22:30 row is a different snapshot
    assert _t("2025-11-17T22:00Z") in todo and _t("2025-11-18T15:00Z") not in todo


def test_the_shared_pull_ledger_keeps_its_key():
    """No migration and no DDL in this change touches odds_history_pulls: its
    key stays (sport, snapshot_date, hour_utc), production's, which every
    purchase's ON CONFLICT names."""
    import re

    from data.view_migrations import ACTIVE_MIGRATIONS, MIGRATIONS_DIR
    assert "PRIMARY KEY (sport, snapshot_date, hour_utc)\n" in oi.PULL_LEDGER_DDL
    assert "minute" not in oi.PULL_LEDGER_DDL
    assert h.PULL_LEDGER_COLS == ("sport", "snapshot_date", "hour_utc", "pulled_at", "rows")
    assert not (MIGRATIONS_DIR / "odds_history_pulls_minute_key_2026_10_30.sql").exists()
    touching = []
    for name in ACTIVE_MIGRATIONS:
        sql = (MIGRATIONS_DIR / name).read_text(encoding="utf-8")
        body = "\n".join(ln for ln in sql.splitlines() if not ln.lstrip().startswith("--"))
        if re.search(r"\bodds_history_pulls\b", body):
            touching.append(name)
    assert touching == []


def test_the_fetch_ledger_is_created_and_locked_down_only_when_missing(monkeypatch):
    monkeypatch.setattr(h, "schema_is_current",
                        lambda conn, table, **kw: table != "odds_history_fetches")
    downs = []
    monkeypatch.setattr(h, "lock_down", lambda conn, table: downs.append(table))
    conn = FakeConn()
    h._ensure_tables(conn)
    assert [q for q, _ in conn.sql] == [" ".join(h.FETCH_LEDGER_DDL.split())]
    assert downs == ["odds_history_fetches"] and conn.commits == 1


# ── the replay maps feed times back on both ledgers ─────────────────────────

def test_the_replay_maps_a_feed_time_to_the_half_hour_that_was_bought():
    class GridReplayConn(ReplayConn):
        def execute(self, sql, params=None):
            if "FROM odds_history_fetches" in sql:
                self.sql.append((sql, params))
                self._ans = [(_t("2025-11-19T22:30Z"),)]
                return self
            return super().execute(sql, params)
    conn = GridReplayConn(ledger=[("2025-11-19", 22), ("2025-11-19", 23)])
    instants = h._ledger_instants(conn)
    assert instants == [_t("2025-11-19T22:00Z"), _t("2025-11-19T22:30Z"), _t("2025-11-19T23:00Z")]
    assert h.planned_instant(_t("2025-11-19T22:25:10Z"), instants) == _t("2025-11-19T22:30Z")


# ── what is stored: each book's first quote and every change after it ───────

def _row(gid, home=-110, away=-110, spread=-4.5, market="spreads", book="fanduel", st="open"):
    return {"game_id": gid, "market": market, "bookmaker": book, "snapshot_type": st,
            "home_price": home, "away_price": away, "spread_home": spread}


def test_the_grid_stores_the_first_quote_and_each_change_not_the_repeats():
    k = h.ChangeKeeper()
    gid = UK_DUKE["game_id"]
    w = _t("2025-11-17T00:30Z")
    seq = [(_row(gid), True),                         # first sighting: the opener
           (_row(gid), False),                        # the same quote half an hour on
           (_row(gid, home=-115, away=-105), True),   # the price moved
           (_row(gid, home=-115, away=-105), False),
           (_row(gid, spread=-5.5), True),            # the line moved
           (_row(gid), True)]                         # and back: a change too
    assert [k.wanted(r, w) for r, _ in seq] == [want for _, want in seq]


def test_each_book_and_market_is_judged_on_its_own_quotes():
    k = h.ChangeKeeper()
    gid, w = UK_DUKE["game_id"], _t("2025-11-17T00:30Z")
    assert k.wanted(_row(gid, book="fanduel"), w) and k.wanted(_row(gid, book="pinnacle"), w)
    assert k.wanted(_row(gid, market="totals"), w)
    assert not k.wanted(_row(gid, book="pinnacle"), w)


def test_the_grid_never_stores_an_in_play_price():
    assert not h.ChangeKeeper().wanted(_row(UK_DUKE["game_id"], st="in_play"),
                                       _t("2025-11-19T01:00Z"))


# ── the purchase ─────────────────────────────────────────────────────────────

def _grid_world(monkeypatch, *, balance=2_000_000, games=(UK_DUKE,), held=()):
    monkeypatch.setattr(h, "check_precondition", lambda conn, seasons: {})
    monkeypatch.setattr(h, "check_process_events_contract", lambda: None)
    monkeypatch.setattr(h, "_ensure_tables", lambda conn: None)
    monkeypatch.setattr(h, "latest_remaining", lambda conn: balance)
    monkeypatch.setattr(h, "_season_games", lambda conn, a, b: list(games))
    monkeypatch.setattr(h, "_held_instants", lambda conn: set(held))
    monkeypatch.setattr(h, "_resolver", lambda conn, g: h.EventResolver(REGISTRY, g))


def test_the_floor_stops_the_grid_before_its_first_call(monkeypatch):
    """The meter learns the balance from a response, so without a reading the
    first call was unguarded. The balance on record is 300,010: one 30-credit
    snapshot would leave 299,980, under the 300,000 floor."""
    _grid_world(monkeypatch, balance=300_010)
    meter = FakeMeter(lambda u, p: pytest.fail("bought below the floor"),
                      ceiling=1_000_000, floor=300_000)
    out = h.buy_opener_grid(FakeConn(), meter, 2026, 2026, 30)
    assert meter.calls == [] and "floor" in out["stopped"]


def test_the_floor_stops_the_grid_part_way(monkeypatch):
    _grid_world(monkeypatch, balance=300_100)
    left = iter([300_070, 300_040, 300_010])
    monkeypatch.setattr(h, "_process_events", contract_process_events)
    monkeypatch.setattr(h, "_insert_odds", lambda c, rows: None)
    meter = FakeMeter(lambda u, p: Resp(body={"data": []}, remaining=str(next(left))),
                      ceiling=1_000_000, floor=300_000)
    out = h.buy_opener_grid(FakeConn(), meter, 2026, 2026, 60)
    assert len(meter.calls) == 3 and out["calls"] == 3 and "floor" in out["stopped"]
    assert meter.remaining >= 300_000


def test_the_grid_refuses_to_start_without_a_balance_on_record(monkeypatch):
    _grid_world(monkeypatch, balance=None)
    meter = FakeMeter(lambda u, p: pytest.fail("bought with no balance known"))
    with pytest.raises(h.PreconditionError, match="balance"):
        h.buy_opener_grid(FakeConn(), meter, 2026, 2026, 30)


def test_the_ceiling_stops_the_grid(monkeypatch):
    _grid_world(monkeypatch)
    monkeypatch.setattr(h, "_process_events", contract_process_events)
    monkeypatch.setattr(h, "_insert_odds", lambda c, rows: None)
    meter = FakeMeter(lambda u, p: Resp(body={"data": []}), ceiling=90, floor=300_000)
    out = h.buy_opener_grid(FakeConn(), meter, 2026, 2026, 60)
    assert len(meter.calls) == 3 and "ceiling" in out["stopped"]


def test_the_grid_buys_what_the_ledger_lacks_newest_season_first_oldest_first(monkeypatch):
    held = {_t("2025-11-17T22:00Z")}
    _grid_world(monkeypatch, games=(UK_DUKE, KSU_DUKE, _game("old", "2024-12-01T17:00:00Z")),
                held=held)
    bought, keepers, takens = [], [], []
    monkeypatch.setattr(h, "_buy_snapshot",
                        lambda conn, meter, tips, resolver, when, stats, keeper=None, taken=None:
                        bought.append(when) or keepers.append(keeper) or takens.append(taken)
                        or True)
    h.buy_opener_grid(FakeConn(), FakeMeter(lambda u, p: Resp()), 2025, 2026, 60)
    want = h.grid_plan([UK_DUKE, KSU_DUKE, _game("old", "2024-12-01T17:00:00Z")], 60, held)
    assert sorted(bought) == sorted(want.todo) and _t("2025-11-17T22:00Z") not in bought
    s26 = [w for w in bought if w.year == 2025 and w.month >= 10]
    assert bought[:len(s26)] == sorted(s26)                 # 2025-26 first, oldest first
    assert bought[len(s26):] == sorted(bought[len(s26):])   # then 2024-25, oldest first
    assert all(isinstance(k, h.ChangeKeeper) for k in keepers)
    # one keeper and one read-back set a season, handed over together
    assert all(isinstance(t, set) for t in takens)
    assert len({id(k) for k in keepers}) == len({id(t) for t in takens}) == 2


# ── a quote already in `odds` is not stored again ───────────────────────────
#
# The keeper only knows what this run has seen. The game-line purchase stored
# its hours' quotes before the grid existed, the grid skips those hours as
# bought, and a stopped grid run restarts with a fresh keeper. So the grid
# reads `odds` back, the way the replay does, and stores only quotes that are
# not there: same game, market, book, feed time, prices and line.

UK_DUKE_EV = _event("e1", "Duke Blue Devils", "Kentucky Wildcats", "2025-11-19T00:30:00Z",
                    last_update="2025-11-17T20:12:00Z")


def _grid_at(monkeypatch, db, times, feed, insert=None):
    """buy_opener_grid over UK-Duke when only `times` are not yet bought;
    feed(date) is the slate the feed answers at that date."""
    window = h.grid_plan([UK_DUKE], 30, held=set()).window
    _grid_world(monkeypatch, games=(UK_DUKE,), held=set(window) - {_t(w) for w in times})
    monkeypatch.setattr(h, "_process_events", contract_process_events)
    monkeypatch.setattr(h, "_insert_odds",
                        insert or (lambda c, rows: db.odds.extend(dict(r) for r in rows)))
    meter = FakeMeter(lambda u, p: Resp(body={"timestamp": p["date"], "data": feed(p["date"])}),
                      ceiling=1_000_000, floor=0)
    out = h.buy_opener_grid(db, meter, 2026, 2026, 30)
    assert len(meter.calls) == len(times)
    return out


def _quotes(rows) -> Counter:
    return Counter(h._row_key(r["game_id"], r["market"], r["bookmaker"], r["snapshot_at"],
                              *(r.get(c) for c in h._ROW_VALUES)) for r in rows)


def test_the_grid_does_not_store_again_a_quote_the_game_line_purchase_stored(monkeypatch):
    """The review's case (2026-10-30): the game-line purchase bought D-1 22Z
    and stored FanDuel's three quotes, each with a feed time of 20:12Z. The
    grid buys 22:30 with a fresh keeper and the feed still shows them. Before
    the read-back all three were stored a second time."""
    db = GridDb()
    ok, _, _ = _snap(monkeypatch, db, "2025-11-17T22:00:00Z", [UK_DUKE_EV], h.QuoteKeeper(GAMES))
    assert ok and len(db.odds) == 3
    out = _grid_at(monkeypatch, db, ["2025-11-17T22:30:00Z"], lambda d: [UK_DUKE_EV])
    assert len(db.odds) == 3 and set(_quotes(db.odds).values()) == {1}
    assert out["rows_already_stored"] == 3 and out.get("odds_rows", 0) == 0
    assert ("NCAAB", _t("2025-11-17T22:30Z")) in db.fetches     # ledgered: never bought again


def test_a_grid_run_resumed_after_a_stop_does_not_store_its_first_quotes_again(monkeypatch):
    db = GridDb()
    _grid_at(monkeypatch, db, ["2025-11-17T22:30:00Z"], lambda d: [UK_DUKE_EV])
    assert len(db.odds) == 3
    # a new run (a fresh keeper) after a stop; the feed still shows the same quotes
    _grid_at(monkeypatch, db, ["2025-11-17T23:00:00Z"], lambda d: [UK_DUKE_EV])
    assert len(db.odds) == 3 and set(_quotes(db.odds).values()) == {1}


def test_a_quote_that_moved_is_still_stored(monkeypatch):
    """The control: the read-back drops only identical quotes. At 23:00 the
    spread has moved (a new feed time); the moneyline and total have only a
    new feed time, so the keeper treats them as repeats."""
    moved = _event("e1", "Duke Blue Devils", "Kentucky Wildcats", "2025-11-19T00:30:00Z",
                   home_pt=-5.5, last_update="2025-11-17T22:41:00Z")
    db = GridDb()
    _grid_at(monkeypatch, db, ["2025-11-17T22:30:00Z", "2025-11-17T23:00:00Z"],
             lambda d: [UK_DUKE_EV] if d < "2025-11-17T22:45" else [moved])
    assert len(db.odds) == 4
    assert sorted(r["snapshot_at"] for r in db.odds if r["market"] == "spreads") == [
        "2025-11-17T20:12:00Z", "2025-11-17T22:41:00Z"]


@pytest.mark.parametrize("server_committed", [True, False])
def test_a_grid_commit_lost_in_flight_stores_each_quote_once(monkeypatch, server_committed):
    """data.db raises ConnectionLost at a COMMIT whose acknowledgement was
    lost, and _write_with_retry runs the unit again. The read-back is inside
    the unit, so whether or not the server committed, each quote is stored
    once and the ledger counts it."""
    from data.db import ConnectionLost
    from data.ingestors import nba_odds_history
    monkeypatch.setattr(nba_odds_history.time, "sleep", lambda s: None)
    db = GridDb()
    state = {"armed": False, "failed": False, "landed": 0}

    def insert(c, rows):
        db.odds.extend(dict(r) for r in rows)
        state["armed"] = True

    def commit():
        db.commits += 1
        if state["armed"] and not state["failed"]:
            state["failed"] = True
            if not server_committed:
                del db.odds[state["landed"]:]          # the server rolled the unit back
            raise ConnectionLost("connection lost at commit")
        state["landed"] = len(db.odds)
    monkeypatch.setattr(db, "commit", commit)
    out = _grid_at(monkeypatch, db, ["2025-11-17T22:30:00Z"], lambda d: [UK_DUKE_EV], insert)
    assert state["failed"] and len(db.odds) == 3 and set(_quotes(db.odds).values()) == {1}
    assert out["odds_rows"] == 3 and out.get("errors", 0) == 0
    ledgered = [p[-1] for q, p in db.sql if q.startswith("INSERT INTO odds_history_fetches")]
    assert ledgered and ledgered[-1] == 3                 # the rows this snapshot stored


# ── the command line and the dry run ────────────────────────────────────────

def _grid_cli(monkeypatch):
    called = []
    monkeypatch.setattr(h, "get_connection", lambda: FakeConn())
    monkeypatch.setattr(h, "_read_only_connection", lambda: FakeConn())
    monkeypatch.setattr(h, "persist_quota", lambda conn: called.append(("quota",)))
    monkeypatch.setattr(h, "buy_opener_grid",
                        lambda conn, m, a, b, step, pre_start=False:
                        called.append(("grid", a, b, step, pre_start, m.ceiling, m.floor)) or {})
    return called


def _no_writable_connection(monkeypatch):
    """A dry run reads on _read_only_connection, which the server refuses to
    write on; get_connection here fails the test."""
    monkeypatch.setattr(h, "get_connection",
                        lambda: pytest.fail("the dry run opened a writable connection"))


def test_a_grid_dry_run_buys_nothing_and_prints_the_count_and_the_credits(monkeypatch, capsys):
    called = _grid_cli(monkeypatch)
    _no_writable_connection(monkeypatch)
    conn = FakeConn()
    monkeypatch.setattr(h, "_read_only_connection", lambda: conn)
    monkeypatch.setattr(h, "check_precondition", lambda c, seasons: {2026: (6000, 6100)})
    monkeypatch.setattr(h, "_season_games", lambda c, a, b: [_game("g", "2025-11-20T17:00:00Z")])
    monkeypatch.setattr(h, "_held_instants", lambda c: {_t("2025-11-19T22:00Z")})
    monkeypatch.setattr(h.Meter, "get", lambda self, url, params: pytest.fail("a dry run called the feed"))
    for argv in (["--opener-grid", "--step", "30", "--seasons", "2026", "2026"],
                 ["--opener-grid", "--step", "30", "--seasons", "2026", "2026", "--dry-run"]):
        monkeypatch.setattr("sys.argv", ["x"] + argv)
        h.main()
        out = capsys.readouterr().out
        assert "144 grid times, 1 already bought, 143 to buy" in out
        assert "143 snapshots, ~4,290 credits" in out
    assert [c for c in called if c[0] != "quota"] == []
    assert not [q for q, _ in conn.sql if not q.lstrip().upper().startswith("SELECT")]


def test_a_grid_dry_run_counts_the_pre_start_window_apart(monkeypatch, capsys):
    _grid_cli(monkeypatch)
    _no_writable_connection(monkeypatch)
    monkeypatch.setattr(h, "check_precondition", lambda c, seasons: {})
    monkeypatch.setattr(h, "_season_games", lambda c, a, b: [_game("g", "2025-11-20T17:00:00Z")])
    monkeypatch.setattr(h, "_held_instants", lambda c: set())
    monkeypatch.setattr("sys.argv", ["x", "--opener-grid", "--step", "60", "--pre-start",
                                     "--seasons", "2026", "2026"])
    h.main()
    out = capsys.readouterr().out
    assert "72 grid times, 0 already bought, 72 to buy" in out
    assert "pre-start" in out and "168 grid times, 0 already bought, 168 to buy" in out
    assert "240 snapshots, ~7,200 credits" in out


GOOD_ARGV = ["--opener-grid", "--step", "30", "--seasons", "2021", "2026"]


@pytest.mark.parametrize("argv", [
    ["--opener-grid", "--seasons", "2021", "2026"],                                   # no step
    ["--opener-grid", "--step", "15", "--seasons", "2021", "2026"],
    ["--opener-grid", "--step", "30", "--seasons", "2021", "2026", "--apply",
     "--max-credits", "1000"],                                                        # no floor
    ["--opener-grid", "--step", "30", "--seasons", "2021", "2026", "--apply",
     "--max-credits", "1000", "--floor", "299999"],
    ["--opener-grid", "--lines", "--step", "30", "--seasons", "2021", "2026"],
    ["--lines", "--step", "30", "--seasons", "2021", "2026"],                         # step is the grid's
    ["--lines", "--pre-start", "--seasons", "2021", "2026"],
])
def test_a_grid_command_line_that_could_overspend_is_refused(monkeypatch, argv):
    called = _grid_cli(monkeypatch)
    assert h._parser().parse_args(GOOD_ARGV).opener_grid      # the control: a good one parses
    monkeypatch.setattr("sys.argv", ["x"] + argv)
    with pytest.raises(SystemExit):
        h.main()
    assert [c for c in called if c[0] != "quota"] == []


def test_the_grid_runs_with_its_ceiling_and_floor(monkeypatch):
    called = _grid_cli(monkeypatch)
    monkeypatch.setattr("sys.argv", ["x", "--opener-grid", "--step", "30", "--pre-start",
                                     "--seasons", "2021", "2026", "--apply",
                                     "--max-credits", "500000", "--floor", "300000"])
    h.main()
    assert called == [("grid", 2021, 2026, 30, True, 500_000, 300_000), ("quota",)]


# ── the worker job: built, not queued ───────────────────────────────────────

def test_the_grid_is_a_job_mode_with_its_own_ceiling():
    mode = jq.NCAAB_ODDS_HISTORY_MODES["opener_grid"]
    assert mode["seasons"] == (2021, 2026) and mode["argv"] == ["--opener-grid"]
    # the 30-minute grid with the pre-start window, 2021-2026: 38,028 snapshots at
    # 30 credits (1,140,840), plus room for calls billed above 30 (job 805227's
    # 7,403 snapshots averaged 30.56 in api_call_log)
    assert mode["cap"] == 1_170_000


@pytest.mark.parametrize("args,argv", [
    ({"mode": "opener_grid", "step_min": 60, "max_credits": 450_000, "floor": 300_000},
     ["--opener-grid", "--seasons", "2021", "2026", "--step", "60", "--apply",
      "--max-credits", "450000", "--floor", "300000"]),
    ({"mode": "opener_grid", "step_min": 30, "pre_start": True, "seasons": [2024, 2026],
      "max_credits": 1_170_000, "floor": 400_000},
     ["--opener-grid", "--seasons", "2024", "2026", "--step", "30", "--pre-start", "--apply",
      "--max-credits", "1170000", "--floor", "400000"]),
    ({"mode": "opener_grid", "step_min": 30, "dry_run": True},
     ["--opener-grid", "--seasons", "2021", "2026", "--step", "30", "--dry-run"]),
])
def test_the_grid_job_runs_the_command_line(monkeypatch, args, argv):
    seen = []
    monkeypatch.setattr(jq, "_run_script_main", lambda mod, a: seen.append((mod, a)) or "ok")
    jq._job_ncaab_odds_history(**jq._validate_ncaab_odds_history(args))
    assert seen == [("data.ingestors.ncaab_odds_history", argv)]


GOOD_JOB = {"mode": "opener_grid", "step_min": 30, "max_credits": 100_000, "floor": 300_000}


@pytest.mark.parametrize("args", [
    {"mode": "opener_grid", "max_credits": 100_000, "floor": 300_000},               # no step
    {"mode": "opener_grid", "step_min": 15, "max_credits": 100_000, "floor": 300_000},
    {"mode": "opener_grid", "step_min": True, "max_credits": 100_000, "floor": 300_000},
    {"mode": "opener_grid", "step_min": 30, "max_credits": 1_170_001, "floor": 300_000},
    {"mode": "opener_grid", "step_min": 30, "max_credits": 100_000, "floor": 299_999},
    {"mode": "opener_grid", "step_min": 30, "max_credits": 100_000},
    {"mode": "opener_grid", "step_min": 30, "max_credits": 100_000, "floor": 300_000,
     "seasons": [2015, 2026]},
    {"mode": "opener_grid", "step_min": 30, "max_credits": 100_000, "floor": 300_000,
     "seasons": [2026, 2024]},
    {"mode": "opener_grid", "step_min": 30, "max_credits": 100_000, "floor": 300_000,
     "pre_start": "yes"},
    {"mode": "opener_grid", "step_min": 30, "dry_run": True, "max_credits": 100_000},
    {"mode": "opener_grid", "step_min": 30, "dry_run": "yes"},
    {"mode": "lines", "max_credits": 100_000, "floor": 300_000, "step_min": 30},
])
def test_a_grid_job_outside_its_scope_is_refused(args):
    assert jq._validate_ncaab_odds_history(dict(GOOD_JOB))   # the control: the good one passes
    with pytest.raises(ValueError):
        jq._validate_ncaab_odds_history(args)


def test_the_grid_is_not_queued():
    """Built, not run: the spend needs mike's approval before a worker_jobs
    row or a declared job exists."""
    import json
    from pathlib import Path
    assert "opener_grid" in jq.NCAAB_ODDS_HISTORY_MODES
    entries = json.loads((Path(__file__).resolve().parent.parent / "jobs" /
                          "declared_jobs.json").read_text(encoding="utf-8"))
    assert not [e for e in entries if e.get("job_type") == "ncaab_odds_history"
                and e["args"].get("mode") == "opener_grid"]
