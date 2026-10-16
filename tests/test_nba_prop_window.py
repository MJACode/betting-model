"""The NBA prop window job: every game reached inside its decision window.

nba_prop_market decides a game only 45-70 minutes before tip, once. The refresh
passes ran hourly at :17 until 5pm ET, so no pass landed 45-70 minutes before a
tip at 1:00pm, 3:30pm or 6:00pm ET -- 177 of 1,206 games in 2026-27 could never
be decided. mike, 2026-10-16: "run the fucking thing more often ... we're not
leaving our games." The answer is a five-minute job, 24x7, that fetches props
for EXACTLY the games about to enter their window, runs the card and the
closing snapshot, and publishes -- and spends nothing when no game is near.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

ET = ZoneInfo("America/New_York")


# ── the fetch: exactly the listed games ──────────────────────────────────────

def test_the_prop_fetch_never_buys_a_game_it_was_not_given(monkeypatch):
    """only_game_ids is applied BEFORE the paid per-event call; with it unset
    every caller fetches every game, as before."""
    import data.ingestors.prop_odds_ingestor as ing

    events = [
        {"id": "ev-lal", "home_team": "Los Angeles Lakers", "away_team": "Golden State Warriors",
         "commence_time": "2026-10-22T02:00:00Z", "game_date": "2026-10-21"},
        {"id": "ev-bos", "home_team": "Boston Celtics", "away_team": "New York Knicks",
         "commence_time": "2026-10-21T23:30:00Z", "game_date": "2026-10-21"},
    ]

    class _R:
        def __init__(self, rows=None):
            self._rows = rows or []

        def fetchall(self):
            return self._rows

        def fetchone(self):
            return None

    class _Conn:
        def execute(self, sql, params=None):
            if "FROM games" in sql:
                return _R([(g,) for g in params[0]])
            return _R()

        def executemany(self, sql, rows):
            pass

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    def _go(**kw):
        fetched: list[str] = []
        monkeypatch.setattr(ing, "get_connection", lambda: _Conn())
        monkeypatch.setattr(ing, "persist_quota", lambda c: None)
        monkeypatch.setattr(ing, "alt_markets_due", lambda *a, **k: False)
        monkeypatch.setattr(ing, "_get_events", lambda *a, **k: events)
        monkeypatch.setattr(ing, "_get_event_props",
                            lambda eid, markets, sport_key=None: fetched.append(eid) or [])
        monkeypatch.setattr(ing.time, "sleep", lambda s: None)
        ing.run_prop_odds_ingestor(target_date="2026-10-21", sport="NBA", days_ahead=1, **kw)
        return fetched

    assert _go(only_game_ids=["NBA_2026-10-21_NYK_BOS"]) == ["ev-bos"]
    assert _go(only_game_ids=[]) == []
    assert _go() == ["ev-lal", "ev-bos"]                    # every other caller: unchanged


# ── the plan: what a tick will do ────────────────────────────────────────────

NOW = datetime(2026, 10, 21, 22, 0, tzinfo=timezone.utc)      # 6:00pm ET


def _t(minutes: int) -> str:
    return (NOW + timedelta(minutes=minutes)).isoformat()


class _PlanConn:
    """Answers the slate, the decisions ledger, the picks guard, the close
    ingestor's bet games and its closes-taken read."""

    def __init__(self, slate_rows, decided=(), taken=(), bet_rows=(), closes=()):
        self.slate_rows, self.decided, self.taken = slate_rows, set(decided), set(taken)
        self.bet_rows, self.closes = list(bet_rows), set(closes)

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if "FROM games g LEFT JOIN nba_schedule" in s:
            self._rows = list(self.slate_rows)
        elif "FROM nba_prop_market_decisions" in s:
            self._rows = [(g,) for g in params[0] if g in self.decided]
        elif "SELECT DISTINCT game_id FROM picks" in s:
            self._rows = [(g,) for g in params[1] if g in self.taken]
        elif "FROM picks p JOIN games g" in s:
            self._rows = list(self.bet_rows)
        elif "FROM player_prop_odds" in s:
            self._rows = [(g,) for g in params[0] if g in self.closes]
        else:
            self._rows = []
        return self

    def fetchall(self):
        return self._rows


def _game(gid, minutes, game_type="regular"):
    return (gid, "LAL", "GSW", "2026-10-21", 2027, _t(minutes), _t(minutes), game_type)


def _plan(conn, monkeypatch):
    import scripts.nba_prop_market_card as card
    import scripts.nba_prop_window as win
    monkeypatch.setattr(card, "ensure_decisions_table", lambda c: None)
    return win.plan(conn, NOW)


def test_the_plan_takes_games_40_to_75_minutes_out_not_yet_decided(monkeypatch):
    conn = _PlanConn([_game("AT39", 39), _game("AT40", 40), _game("AT58", 58),
                      _game("AT75", 75), _game("AT76", 76), _game("DONE", 55),
                      _game("BET", 60), _game("CUP", 55, "cup_final")],
                     decided={"DONE"}, taken={"BET"})
    p = _plan(conn, monkeypatch)
    assert p.decide == ["AT40", "AT58", "AT75"] and p.close == []


def test_the_plan_owes_a_close_with_no_game_to_decide(monkeypatch):
    """A bet game 12-25 minutes from tip gets its closing snapshot even on a
    tick with nothing to decide; one already closed, or outside 12-25, does not."""
    bets = [("CLOSE", "player_points", "LAL", "GSW", "2026-10-21", _t(20), _t(20)),
            ("TAKEN", "player_points", "LAL", "GSW", "2026-10-21", _t(15), _t(15)),
            ("EARLY", "player_points", "LAL", "GSW", "2026-10-21", _t(30), _t(30)),
            ("LATE", "player_points", "LAL", "GSW", "2026-10-21", _t(10), _t(10))]
    p = _plan(_PlanConn([], bet_rows=bets, closes={"TAKEN"}), monkeypatch)
    assert p.decide == [] and p.close == ["CLOSE"]


# ── the tick ─────────────────────────────────────────────────────────────────

def _tick(monkeypatch, plan):
    import scheduler
    import scripts.nba_prop_window as win
    ran, published = [], []
    monkeypatch.setattr(win, "plan_tick", lambda now=None: plan)
    monkeypatch.setattr(scheduler, "_run",
                        lambda cmd, label, **kw: ran.append((label, cmd, kw)) or "ok")
    monkeypatch.setattr(scheduler, "_publish_new_signals", published.append)
    scheduler.run_nba_prop_window()
    return ran, published


def test_a_tick_with_nothing_near_spends_nothing(monkeypatch):
    import scripts.nba_prop_window as win
    ran, published = _tick(monkeypatch, win.Plan(decide=[], close=[]))
    assert ran == [] and published == []


def test_a_tick_fetches_exactly_the_window_games_then_decides_closes_and_publishes(monkeypatch):
    import scripts.nba_prop_window as win
    ran, published = _tick(monkeypatch, win.Plan(decide=["G1", "G2"], close=["G0"]))
    assert [label for label, _, _ in ran] == ["nba-prop-window-fetch", "nba-prop-market",
                                              "nba-prop-close"]
    fetch_cmd = ran[0][1]
    assert fetch_cmd[-3:] == ["--fetch", "G1", "G2"]
    assert ran[1][1][-2:] == ["--step", "nba-prop-market"]
    assert ran[2][1][-2:] == ["--step", "nba-prop-close"]
    assert all(kw.get("timeout") for _, _, kw in ran), "every step is bounded (see _run)"
    assert sum(kw["timeout"] for _, _, kw in ran) <= 300, "the three fit inside one tick"
    assert published == ["nba-prop-window"]


def test_a_tick_with_only_a_close_due_does_not_return_early(monkeypatch):
    import scripts.nba_prop_window as win
    ran, published = _tick(monkeypatch, win.Plan(decide=[], close=["G0"]))
    assert [label for label, _, _ in ran] == ["nba-prop-close"]
    assert published == ["nba-prop-window"]


def test_a_failed_step_is_recorded_as_an_error_after_publishing(monkeypatch):
    import scheduler
    import scripts.nba_prop_window as win
    published = []
    monkeypatch.setattr(win, "plan_tick", lambda now=None: win.Plan(decide=["G1"], close=[]))
    monkeypatch.setattr(scheduler, "_run",
                        lambda cmd, label, **kw: "timeout" if label == "nba-prop-window-fetch" else "ok")
    monkeypatch.setattr(scheduler, "_publish_new_signals", published.append)
    with pytest.raises(RuntimeError, match="nba-prop-window-fetch"):
        scheduler.run_nba_prop_window()
    assert published == ["nba-prop-window"]


# ── the schedule reaches every tip ───────────────────────────────────────────

def _jobs(monkeypatch):
    import scheduler
    from tracking import job_heartbeat as jh
    monkeypatch.setattr(jh, "seed", lambda jid: None)
    monkeypatch.setattr(jh, "mark_disabled", lambda jid, *a, **k: None)
    # tests/test_service_role_split.py reloads scheduler under other roles;
    # this file asserts the single-container schedule whatever ran before.
    monkeypatch.setattr(scheduler, "SERVICE_ROLE", "all")
    return {j.id: j for j in scheduler.build_scheduler().get_jobs()}


def _fires(job, start, end):
    out, prev, t = [], None, start
    while True:
        nxt = job.trigger.get_next_fire_time(prev, t)
        if nxt is None or nxt > end:
            return out
        out.append(nxt)
        prev, t = nxt, nxt + timedelta(seconds=1)


@pytest.mark.parametrize("hh,mm", [(13, 0), (15, 30), (18, 0), (19, 0)])
def test_every_tip_time_gets_a_look_inside_its_window(monkeypatch, hh, mm):
    import models.nba_prop_market as mk
    import scripts.nba_prop_window as win
    tip = datetime(2026, 10, 21, hh, mm, tzinfo=ET)
    jobs = _jobs(monkeypatch)
    job = jobs["nba_prop_window"]
    lo, hi = mk.DECISION_WINDOW_MIN
    leads = [(tip - f).total_seconds() / 60 for f in
             _fires(job, tip - timedelta(minutes=hi), tip - timedelta(minutes=lo))]
    assert leads, f"no window tick lands {lo}-{hi} minutes before a {hh}:{mm:02d} ET tip"
    # and the tick at that moment would put the game in its fetch list
    assert all(win.LOOK_AHEAD_MIN[0] <= x <= win.LOOK_AHEAD_MIN[1] for x in leads)


@pytest.mark.parametrize("hh,mm", [(13, 0), (15, 30), (18, 0)])
def test_the_refresh_passes_alone_reached_none_of_these_tips(monkeypatch, hh, mm):
    """Why the job exists: the hourly :17 passes and the evening ten-minute
    passes put no look 45-70 minutes before these tips."""
    import models.nba_prop_market as mk
    tip = datetime(2026, 10, 21, hh, mm, tzinfo=ET)
    lo, hi = mk.DECISION_WINDOW_MIN
    jobs = _jobs(monkeypatch)
    for jid in ("hourly_refresh", "overnight_refresh", "evening_refresh"):
        assert _fires(jobs[jid], tip - timedelta(minutes=hi), tip - timedelta(minutes=lo)) == [], jid


def test_the_window_job_is_every_five_minutes_on_the_pipeline_service(monkeypatch):
    import scheduler
    from tracking.job_heartbeat import MAX_SILENCE
    job = _jobs(monkeypatch)["nba_prop_window"]
    day = datetime(2026, 10, 21, 0, 0, tzinfo=ET)
    fires = _fires(job, day, day + timedelta(hours=24) - timedelta(seconds=1))
    assert len(fires) == 288, "every five minutes, around the clock"
    assert "nba_prop_window" in scheduler._PIPELINE_JOBS
    assert "nba_prop_window" not in scheduler._POLLER_JOBS
    assert MAX_SILENCE["nba_prop_window"] == 30
