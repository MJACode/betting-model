"""The NCAAB opener grid: a bulk snapshot at every grid time before every tip.

WHY. The game-line purchase (mode `lines`) bought three kinds of hour: the
evening before, mid-morning, and the hour before each tip. A book that first
posts its line between two of those is dated only to the gap, and the gap is
over two hours for 42-68% of first spreads and totals, depending on the book
(opener-route design, 2026-10-30). The grid buys a snapshot every 60 or 30 minutes from 72
hours before each tip to the tip, so each book's first posted full-game line
is dated to the step. Nothing is queued: the spend needs mike's approval.

These pin what decides the spend (the grid, the ledger key with minutes, the
floor, the ceiling), what a dry run may do (nothing but read), and the job.
The ledger re-key against a real Postgres is
tests/test_odds_history_pulls_minute_key_pg.py.
"""
from __future__ import annotations

from collections import defaultdict
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


# ── the ledger key gains minutes ─────────────────────────────────────────────

class LedgerConn(FakeConn):
    """A FakeConn whose pull ledger answers the held check by its parameters:
    a three-parameter (hour-keyed) check matches any minute in that hour, the
    way an hour-only key reads a half-hour row."""

    def __init__(self, ledger):
        super().__init__()
        self.ledger = set(ledger)              # {(date, hour, minute)}

    def fetchone(self):
        q, params = self.sql[-1]
        if q.startswith("SELECT 1 FROM odds_history_pulls"):
            sport, d, hour, *minute = params
            hit = any(r[0] == d and r[1] == hour and (not minute or r[2] == minute[0])
                      for r in self.ledger)
            return (1,) if hit else None
        return None


def _buy(monkeypatch, conn, when, events=(), keeper=None):
    monkeypatch.setattr(h, "_process_events", contract_process_events)
    monkeypatch.setattr(h, "_insert_odds", lambda c, rows: None)
    meter = FakeMeter(lambda u, p: Resp(body={"timestamp": "x", "data": list(events)}))
    stats = defaultdict(int)
    tips = {g["game_id"]: g["commence_time"] for g in GAMES}
    ok = h._buy_snapshot(conn, meter, tips, h.EventResolver(REGISTRY, GAMES), _t(when),
                         stats, keeper)
    return ok, meter, stats


def test_a_half_hour_time_is_not_treated_as_already_bought(monkeypatch):
    conn = LedgerConn({("2025-11-19", 22, 0)})
    ok, meter, stats = _buy(monkeypatch, conn, "2025-11-19T22:30:00Z")
    assert ok and len(meter.calls) == 1 and stats.get("skipped_held", 0) == 0
    assert meter.calls[0][1]["date"] == "2025-11-19T22:30:00Z"
    (q, params), = [(q, p) for q, p in conn.sql if q.startswith("INSERT INTO odds_history_pulls")]
    assert "minute_utc" in q and params[:4] == ("NCAAB", "2025-11-19", 22, 30)


def test_the_hour_itself_is_still_held(monkeypatch):
    conn = LedgerConn({("2025-11-19", 22, 0)})
    ok, meter, stats = _buy(monkeypatch, conn, "2025-11-19T22:00:00Z")
    assert ok and meter.calls == [] and stats["skipped_held"] == 1
    assert conn.sql[0][1] == ("NCAAB", "2025-11-19", 22, 0)        # checked on its minute


def test_a_half_hour_row_does_not_read_as_the_hour_bought(monkeypatch):
    """The lines purchase wants 22:00; the grid holds only 22:30."""
    conn = LedgerConn({("2025-11-19", 22, 30)})
    ok, meter, stats = _buy(monkeypatch, conn, "2025-11-19T22:00:00Z")
    assert ok and len(meter.calls) == 1


def test_the_lines_plan_reads_the_ledger_with_its_minutes(monkeypatch):
    conn = FakeConn(answers={"FROM odds_history_pulls": [("2025-11-17", 22, 30),
                                                          ("2025-11-18", 15, 0)]})
    monkeypatch.setattr(h, "_season_games", lambda c, a, b: [UK_DUKE])
    _, pairs, todo = h.plan_lines(conn, 2026, 2026)
    # D-1 22Z is wanted on the hour: the 22:30 row is a different snapshot
    assert _t("2025-11-17T22:00Z") in todo and _t("2025-11-18T15:00Z") not in todo


def test_every_ledger_writer_names_the_constraint_not_three_columns():
    """Once the key has four columns, ON CONFLICT (sport, snapshot_date,
    hour_utc) matches no constraint and the write raises after the paid call.
    The constraint's name is the same before and after the migration."""
    import inspect

    from data.ingestors import nba_odds_history
    for mod in (h, nba_odds_history, oi):
        src = inspect.getsource(mod)
        assert "ON CONFLICT (sport, snapshot_date, hour_utc)" not in src, mod.__name__
        assert "ON CONFLICT ON CONSTRAINT odds_history_pulls_pkey" in src, mod.__name__


def test_the_ledger_ddl_keys_on_the_minute():
    assert "minute_utc" in oi.PULL_LEDGER_DDL
    assert "PRIMARY KEY (sport, snapshot_date, hour_utc, minute_utc)" in oi.PULL_LEDGER_DDL
    assert "minute_utc" in h.PULL_LEDGER_COLS


def test_the_migration_is_one_block_and_runs_on_the_worker_pass():
    from data.view_migrations import ACTIVE_MIGRATIONS, MIGRATIONS_DIR
    name = h.MINUTE_KEY_MIGRATION.name
    assert name in ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS[-1] == "published_record_units_2026_10_16.sql"
    sql = (MIGRATIONS_DIR / name).read_text(encoding="utf-8")
    body = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
    assert body.strip().startswith("DO $$") and body.strip().endswith("END $$;")
    assert body.count("$$") == 2
    assert "DEFAULT 0" in body and "odds_history_pulls_pkey" in body


# ── the replay maps feed times back on the same key ─────────────────────────

def test_the_replay_maps_a_feed_time_to_the_half_hour_that_was_bought():
    conn = ReplayConn(ledger=[("2025-11-19", 22, 0), ("2025-11-19", 22, 30),
                              ("2025-11-19", 23, 0)])
    instants = h._ledger_instants(conn)
    assert instants == [_t("2025-11-19T22:00Z"), _t("2025-11-19T22:30Z"), _t("2025-11-19T23:00Z")]
    assert h.planned_instant(_t("2025-11-19T22:25:10Z"), instants) == _t("2025-11-19T22:30Z")


def test_the_ledger_reads_hour_rows_before_the_migration_lands():
    """A dry run on the worker can run before the migration pass: a ledger
    with no minute column reads every row as minute 0."""
    class OldLedger(ReplayConn):
        tried: list = []

        def execute(self, sql, params=None):
            self.tried.append(sql)
            if "minute_utc" in sql:
                raise RuntimeError('column "minute_utc" does not exist')
            return super().execute(sql, params)
    conn = OldLedger(ledger=[("2025-11-19", 22), ("2025-11-20", 15)])
    instants = h._ledger_instants(conn)
    assert instants == [_t("2025-11-19T22:00Z"), _t("2025-11-20T15:00Z")]
    assert "minute_utc" in conn.tried[0]                 # the minute is asked for first


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

def _grid_world(monkeypatch, *, balance=2_000_000, keyed=True, games=(UK_DUKE,), held=()):
    monkeypatch.setattr(h, "check_precondition", lambda conn, seasons: {})
    monkeypatch.setattr(h, "check_process_events_contract", lambda: None)
    monkeypatch.setattr(h, "_ensure_tables", lambda conn: None)
    monkeypatch.setattr(h, "_ledger_keyed_by_minute", lambda conn: keyed)
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


def test_the_grid_refuses_an_hour_keyed_ledger(monkeypatch):
    """A half-hour row under the old key would overwrite that hour's row and
    never read as bought: every re-run would pay for it again."""
    _grid_world(monkeypatch, keyed=False)
    meter = FakeMeter(lambda u, p: pytest.fail("bought into an hour-keyed ledger"))
    with pytest.raises(h.PreconditionError, match="minute"):
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
    bought, keepers = [], []
    monkeypatch.setattr(h, "_buy_snapshot",
                        lambda conn, meter, tips, resolver, when, stats, keeper=None:
                        bought.append(when) or keepers.append(keeper) or True)
    h.buy_opener_grid(FakeConn(), FakeMeter(lambda u, p: Resp()), 2025, 2026, 60)
    want = h.grid_plan([UK_DUKE, KSU_DUKE, _game("old", "2024-12-01T17:00:00Z")], 60, held)
    assert sorted(bought) == sorted(want.todo) and _t("2025-11-17T22:00Z") not in bought
    s26 = [w for w in bought if w.year == 2025 and w.month >= 10]
    assert bought[:len(s26)] == sorted(s26)                 # 2025-26 first, oldest first
    assert bought[len(s26):] == sorted(bought[len(s26):])   # then 2024-25, oldest first
    assert all(isinstance(k, h.ChangeKeeper) for k in keepers)


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


def test_a_grid_dry_run_buys_nothing_and_prints_the_count_and_the_credits(monkeypatch, capsys):
    called = _grid_cli(monkeypatch)
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
