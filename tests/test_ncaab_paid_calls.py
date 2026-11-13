"""data/ingestors/ncaab_odds_history: paid calls side by side, the meter exact.

mike, 2026-11-02: "why taking so long ... I want it all done and go live now".
The opener grid and the first-half purchases send up to `concurrency` calls
at once (default 6, at most 10). These pin what must not change with it: the
ceiling and the floor are checked before EVERY call with the calls in flight
counted at their most, a 429 pauses every call and shrinks the number in
flight, and what is stored is what the one-at-a-time run stores.
"""
from __future__ import annotations

import random
import threading
import time as real_time

import pytest

import tracking.job_queue as jq
from data.ingestors import ncaab_odds_history as h
from tests.test_ncaab_derivative_gameday import EARLY, _world
from tests.test_ncaab_odds_history import (GAMES, KSU_DUKE, UK_DUKE, FakeConn, Resp, _event, _t,
                                           contract_process_events)
from tests.test_ncaab_opener_grid import GridDb, _grid_world


class Feed(h.PoolMeter):
    """A PoolMeter whose one HTTP line answers from `answer(url, params)`,
    holding each call `hold` seconds (or a random few ms with `jitter`) so
    calls overlap, and keeping a balance the way the feed does."""

    def __init__(self, answer=None, *, ceiling=10_000_000, floor=0, workers=6, balance=2_000_000,
                 cost=30, hold=0.0, jitter=False):
        super().__init__(ceiling, floor, workers)
        self.answer, self.balance, self.cost = answer, balance, cost
        self.hold, self.jitter = hold, jitter
        self.sent: list = []
        self.events: list = []
        self.live = self.peak = 0
        self._l = threading.Lock()
        self._rng = random.Random(7)

    def _send(self, url, params):
        with self._l:
            n = len(self.sent)
            self.sent.append((url, dict(params)))
            self.events.append(("send", n))
            self.live += 1
            self.peak = max(self.peak, self.live)
            pause = self._rng.uniform(0, 0.004) if self.jitter else self.hold
        real_time.sleep(pause)
        r = self.answer(url, params) if self.answer else Resp(body={}, last=str(self.cost))
        with self._l:
            self.balance -= int(r.headers.get("x-requests-last") or 0)
            r.headers["x-requests-remaining"] = str(self.balance)
            self.live -= 1
            self.events.append(("done", n))
        return r


def _jobs(n):
    return ((i, f"https://feed/{i}", {"i": i}) for i in range(n))


# ── the meter with calls in flight ───────────────────────────────────────────

def test_a_call_in_flight_counts_at_its_most_against_the_floor_and_the_ceiling():
    m = h.PoolMeter(ceiling=10_000, floor=1_000, workers=6)
    m.remaining = 1_100
    assert m.stop_reason(30) is None
    m.reserved = 60                                   # two snapshots in flight
    assert m.stop_reason(30) is None                  # 1,100 - 90 = 1,010
    m.reserved = 90
    assert "floor" in m.stop_reason(30)               # 1,100 - 120 = 980
    m.remaining, m.spent, m.reserved = 5_000_000, 9_940, 0
    assert m.stop_reason(30) is None                  # 9,940 + 30 = 9,970
    m.reserved = 60
    assert "ceiling" in m.stop_reason(30)             # 9,940 + 60 + 30 > 10,000


def test_calls_in_flight_can_never_take_the_balance_under_the_floor():
    """1,100 credits, a 1,000 floor, 30 a call, six at once: only three calls
    fit, since a fourth in flight could end the run at 980. Every answer is
    held 0.2 s, so all of them are in flight when the fourth is asked for."""
    feed = Feed(floor=1_000, balance=1_100, hold=0.2)
    feed.remaining = 1_100
    got = []
    why = h._paid_calls(feed, _jobs(10), 30, lambda k, r: got.append(k))
    assert "floor" in why
    assert len(feed.sent) == 3 and got == [0, 1, 2]
    assert feed.balance == 1_010 and feed.remaining == 1_010 >= feed.floor
    assert feed.reserved == 0 and feed.spent == 90


def test_calls_in_flight_can_never_take_the_spend_over_the_ceiling():
    feed = Feed(ceiling=100, hold=0.2)
    feed.remaining = 2_000_000
    why = h._paid_calls(feed, _jobs(10), 30, lambda k, r: None)
    assert "ceiling" in why and len(feed.sent) == 3 and feed.spent == 90 <= 100


def test_while_the_balance_is_unknown_one_call_at_a_time():
    """No balance on record: the first call goes alone, and the rest wait for
    its answer to learn the balance before any two run side by side."""
    feed = Feed(hold=0.05)
    assert feed.remaining is None
    h._paid_calls(feed, _jobs(8), 30, lambda k, r: None)
    assert feed.events[:2] == [("send", 0), ("done", 0)]
    assert feed.peak > 1                              # then side by side


def test_answers_are_handled_in_the_order_asked_and_on_the_calling_thread():
    feed = Feed(jitter=True)
    feed.remaining = 2_000_000
    seen = []
    h._paid_calls(feed, _jobs(40), 30,
                  lambda k, r: seen.append((k, threading.current_thread() is threading.main_thread())))
    assert [k for k, _ in seen] == list(range(40)) and all(main for _, main in seen)
    assert 1 < feed.peak <= 6


def test_a_plain_meter_makes_its_calls_one_at_a_time():
    from tests.test_ncaab_odds_history import FakeMeter
    m = FakeMeter(lambda u, p: Resp(last="30"), ceiling=10_000, floor=0)
    got = []
    assert h._paid_calls(m, _jobs(3), 30, lambda k, r: got.append(k)) is None
    assert got == [0, 1, 2] and len(m.calls) == 3


def test_the_concurrency_setting_is_bounded():
    with pytest.raises(ValueError):
        h.PoolMeter(1, 0, workers=11)
    with pytest.raises(ValueError):
        h.PoolMeter(1, 0, workers=0)
    assert h.DEFAULT_CONCURRENCY == jq.NCAAB_ODDS_HISTORY_DEFAULT_CONCURRENCY == 6
    assert h.MAX_CONCURRENCY == jq.NCAAB_ODDS_HISTORY_MAX_CONCURRENCY == 10


# ── a 429 ────────────────────────────────────────────────────────────────────

class _Clock:
    """time for the module: the real monotonic clock, a sleep that is recorded."""

    def __init__(self):
        self.slept: list[float] = []
        self._l = threading.Lock()

    @staticmethod
    def monotonic():
        return real_time.monotonic()

    def sleep(self, s):
        with self._l:
            self.slept.append(s)


def _throttled_feed(n429, last_429="0", **kw):
    count = {"n": 0}
    lock = threading.Lock()

    def answer(url, params):
        with lock:
            k = count["n"]
            count["n"] += 1
        if k < n429:
            return Resp(status=429, body={}, last=last_429)
        return Resp(body={"ok": True}, last="30")
    return Feed(answer, **kw)


def test_a_429_pauses_every_call_is_retried_and_shrinks_the_calls_in_flight(monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(h, "time", clock)
    feed = _throttled_feed(2)
    feed.remaining = 2_000_000
    got = []
    assert h._paid_calls(feed, _jobs(5), 30, lambda k, r: got.append((k, r.status_code))) is None
    assert got == [(i, 200) for i in range(5)]       # every call answered in the end
    assert feed.rate_limited == 2 and feed.window == 4
    assert max(clock.slept) > 1.5                    # the shared pause (2 s, then 4 s)
    assert feed.spent == 150                         # a 429 bills nothing


def test_a_429_that_billed_is_not_retried_and_retries_run_out(monkeypatch):
    monkeypatch.setattr(h, "time", _Clock())
    billed = _throttled_feed(1, last_429="30", workers=1)
    r = billed.get("https://feed/x", {})
    assert r.status_code == 429 and len(billed.sent) == 1 and billed.spent == 30
    endless = _throttled_feed(10_000, workers=1)
    f = endless.fetch("https://feed/x", {})
    assert f.response.status_code == 429 and len(f.attempts) == h.PoolMeter.RETRY_429 + 1


def test_the_run_reports_its_429s(monkeypatch):
    monkeypatch.setattr(h, "time", _Clock())
    _grid_world(monkeypatch, games=(UK_DUKE,))
    monkeypatch.setattr(h, "_process_events", contract_process_events)
    monkeypatch.setattr(h, "_insert_odds", lambda c, rows: None)
    feed = _throttled_feed(3)
    out = h.buy_opener_grid(GridDb(), feed, 2026, 2026, 60)
    assert out["rate_limited_429"] == 3 and out["concurrency"] == 6
    assert out["calls"] == len(h.grid_plan([UK_DUKE], 60, set()).todo)


# ── the same stored, side by side or one at a time ──────────────────────────

def _slate(date):
    """A feed whose UK-Duke spread moves every hour and whose KSU-Duke total
    moves every half hour, plus one listing that resolves onto no game."""
    hour, minute = int(date[11:13]), int(date[14:16])
    uk = _event("e1", "Duke Blue Devils", "Kentucky Wildcats", "2025-11-19T00:30:00Z",
                home_pt=-4.5 - (hour % 3) * 0.5, last_update=date)
    ksu = _event("e2", "Kansas State Wildcats", "Duke Blue Devils", "2025-11-20T17:00:00Z",
                 home_pt=1.5 + (minute // 30), book="draftkings", last_update=date)
    moose = _event("e9", "Mystery Moose", "Duke Blue Devils", "2025-11-19T01:00:00Z")
    return [uk, ksu, moose]


def _grid_run(monkeypatch, workers):
    db = GridDb()
    _grid_world(monkeypatch, games=(UK_DUKE, KSU_DUKE))
    monkeypatch.setattr(h, "_process_events", contract_process_events)
    monkeypatch.setattr(h, "_insert_odds", lambda c, rows: db.odds.extend(dict(r) for r in rows))
    feed = Feed(lambda u, p: Resp(body={"timestamp": p["date"], "data": _slate(p["date"])},
                                  last="30"), workers=workers, jitter=True)
    out = h.buy_opener_grid(db, feed, 2026, 2026, 30)
    writes = [(q, p) for q, p in db.sql if q.startswith("INSERT")]
    return db, out, feed, writes


def test_the_grid_stores_the_same_side_by_side_as_one_at_a_time(monkeypatch):
    one_db, one, one_feed, one_writes = _grid_run(monkeypatch, 1)
    six_db, six, six_feed, six_writes = _grid_run(monkeypatch, 6)
    assert six_feed.peak > 1 and one_feed.peak == 1
    assert one["calls"] == six["calls"] == len(one_feed.sent) == len(six_feed.sent) > 100
    assert six_db.odds == one_db.odds and len(one_db.odds) > 0      # same rows, same order
    assert six_writes == one_writes                                  # odds, raw events, ledger
    assert six_db.fetches == one_db.fetches and six_db.pulls == one_db.pulls
    drop = {"concurrency", "rate_limited_429"}
    assert {k: v for k, v in six.items() if k not in drop} == \
        {k: v for k, v in one.items() if k not in drop}
    assert six_feed.spent == one_feed.spent == 30 * one["calls"]


def test_a_time_the_ledger_holds_by_the_time_it_is_asked_for_is_not_bought(monkeypatch):
    """A rerun of a stopped grid job (a redeploy kills it, the queue reclaims
    it): its plan skips every time either ledger holds, and each time is read
    against the ledger again just before its call, the half hours in the fetch
    ledger and the hours in the pull ledger."""
    _grid_world(monkeypatch, games=(UK_DUKE,), held=())          # the plan holds nothing
    monkeypatch.setattr(h, "_process_events", contract_process_events)
    monkeypatch.setattr(h, "_insert_odds", lambda c, rows: None)
    half, hour = _t("2025-11-17T22:30:00Z"), _t("2025-11-17T23:00:00Z")
    db = GridDb(pulls={("NCAAB", "2025-11-17", 23)}, fetches={("NCAAB", half)})
    feed = Feed(lambda u, p: Resp(body={"timestamp": p["date"], "data": []}, last="30"))
    out = h.buy_opener_grid(db, feed, 2026, 2026, 30)
    asked = {p["date"] for _, p in feed.sent}
    assert h._stamp(half) not in asked and h._stamp(hour) not in asked
    assert out["skipped_held"] == 2
    assert out["calls"] == len(h.grid_plan([UK_DUKE], 30, set()).todo) - 2


def test_the_first_half_purchase_stores_the_same_side_by_side(monkeypatch):
    def run(workers):
        inserted, answer, _ = _world(monkeypatch, GAMES + [EARLY])
        feed = Feed(answer, workers=workers, jitter=True)
        out = h.buy_derivatives(FakeConn(), feed, 2026, 2026, "tip60")
        return inserted, out, feed
    one_rows, one, one_feed = run(1)
    six_rows, six, six_feed = run(6)
    assert six_rows == one_rows and len(one_rows) > 0
    drop = {"concurrency", "rate_limited_429"}
    assert {k: v for k, v in six.items() if k not in drop} == \
        {k: v for k, v in one.items() if k not in drop}
    assert sorted(p.get("date") for _, p in six_feed.sent) == \
        sorted(p.get("date") for _, p in one_feed.sent)


def test_the_first_half_purchase_holds_the_floor_with_calls_in_flight(monkeypatch):
    """The listing (1 credit) and then three games at 40 each, six at once,
    with 1,100 credits over a 1,000 floor: two games fit (1,099 - 80 =
    1,019); a third in flight could end at 979."""
    _, answer, _ = _world(monkeypatch, GAMES + [EARLY])
    feed = Feed(answer, floor=1_000, balance=1_100, hold=0.2)
    out = h.buy_derivatives(FakeConn(), feed, 2026, 2026, "tip60")
    assert "floor" in out["stopped"]
    assert feed.balance >= 1_000 and feed.remaining >= 1_000
    assert sum(1 for u, _ in feed.sent if "/events/" in u) == 2
    assert out["left_unbought"] == 1


# ── the worker job ───────────────────────────────────────────────────────────

# job 936020's stored args (worker_jobs, 2026-11-02), as the main session read them
RUNNING_GRID_JOB = {"mode": "opener_grid", "floor": 300000, "dry_run": False,
                    "seasons": [2021, 2026], "step_min": 30, "pre_start": False,
                    "max_credits": 1100000}


def _argv(monkeypatch, args):
    seen = []
    monkeypatch.setattr(jq, "_run_script_main", lambda mod, argv: seen.append(argv) or "ok")
    jq._job_ncaab_odds_history(**jq._validate_ncaab_odds_history(dict(args)))
    assert len(seen) == 1
    return seen[0]


def test_the_running_grid_job_reruns_at_the_default_concurrency(monkeypatch):
    """A redeploy kills job 936020 and the queue runs it again with its stored
    args, which name no concurrency: the rerun goes six at a time."""
    argv = _argv(monkeypatch, RUNNING_GRID_JOB)
    assert argv == ["--opener-grid", "--seasons", "2021", "2026", "--step", "30",
                    "--concurrency", "6", "--apply", "--max-credits", "1100000",
                    "--floor", "300000"]
    a = h._parser().parse_args(argv)
    assert a.concurrency == 6 and a.opener_grid and a.step == 30 and not a.pre_start


@pytest.mark.parametrize("args,n", [
    ({**RUNNING_GRID_JOB, "concurrency": 10}, "10"),
    ({"mode": "deriv_close", "max_credits": 800_000, "floor": 300_000, "concurrency": 3}, "3"),
    ({"mode": "deriv_open", "max_credits": 800_000, "floor": 300_000}, "6"),
    ({"mode": "deriv_15z_test", "max_credits": 2_500, "floor": 300_000, "concurrency": 1}, "1"),
])
def test_a_job_can_name_its_concurrency(monkeypatch, args, n):
    argv = _argv(monkeypatch, args)
    assert argv[argv.index("--concurrency") + 1] == n


@pytest.mark.parametrize("args", [
    {**RUNNING_GRID_JOB, "concurrency": 11},
    {**RUNNING_GRID_JOB, "concurrency": 0},
    {**RUNNING_GRID_JOB, "concurrency": True},
    {**RUNNING_GRID_JOB, "concurrency": "6"},
    {"mode": "opener_grid", "step_min": 30, "dry_run": True, "concurrency": 6},
    {"mode": "lines", "max_credits": 100_000, "floor": 300_000, "concurrency": 6},
    {"mode": "probe", "max_credits": 200, "floor": 300_000, "concurrency": 6},
    {"mode": "deriv_15z", "dry_run": True, "concurrency": 6},
])
def test_a_concurrency_outside_its_bounds_or_its_modes_is_refused(args):
    with pytest.raises(ValueError):
        jq._validate_ncaab_odds_history(args)


@pytest.mark.parametrize("argv", [
    ["--opener-grid", "--step", "30", "--seasons", "2021", "2026", "--concurrency", "11"],
    ["--derivatives", "close", "--seasons", "2024", "2026", "--concurrency", "0"],
])
def test_a_command_line_concurrency_outside_its_bounds_is_refused(monkeypatch, argv):
    monkeypatch.setattr(h, "get_connection", lambda: pytest.fail("connected"))
    monkeypatch.setattr(h, "_read_only_connection", lambda: pytest.fail("connected"))
    monkeypatch.setattr("sys.argv", ["x"] + argv)
    with pytest.raises(SystemExit):
        h.main()
