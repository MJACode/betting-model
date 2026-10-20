"""nba_team_total_luck's window: what a tick plans, how it runs inside the NBA
totals window job, and why it is that job and not a second one.

The plan reads only (tests/test_nba_team_total_odds.FakeDB stands in for the
database); the job's steps are recorded, never run; no test calls the Odds
API. The timing rule itself (45-66 minutes, five minutes fresh) is pinned in
tests/test_nba_team_total_luck.py.
"""
from __future__ import annotations

import os
import sys
from datetime import timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import data.ingestors.nba_team_total_odds as feed  # noqa: E402
import models.nba_team_total_luck as tt  # noqa: E402
import scripts.nba_pregame_window as pw  # noqa: E402
import scripts.nba_team_total_luck_window as ttw  # noqa: E402
from tests.test_nba_team_total_odds import Clock, FakeDB, et  # noqa: E402

MODEL = tt.MODEL_ID
NOW = et(2026, 11, 5, 18, 0)


def _slate(**leads):
    return {g: {"home": "MIL", "away": "BOS", "game_date": "2026-11-05", "season": 2027,
                "tip": NOW + timedelta(minutes=m)} for g, m in leads.items()}


def _db(decided=(), bets=(), closes=(), tables=True):
    db = FakeDB(Clock(NOW), tables=("nba_team_total_luck_decisions", feed.LEDGER_TABLE)
                if tables else ())
    db.rows["nba_team_total_luck_decisions"] += [{"game_id": g} for g in decided]
    db.rows["picks"] += [{"game_id": g, "model_id": MODEL, "signal_type": "BET"} for g in bets]
    db.rows["picks"].append({"game_id": "G_OTHER_MODEL", "model_id": "nba_total_luck",
                             "signal_type": "BET"})
    db.rows[feed.LEDGER_TABLE] += [
        {"game_id": g, "endpoint": feed.EVENT_ODDS, "snapshot_type": "close", "ok": True,
         "fetch_at": NOW - timedelta(minutes=1)} for g in closes]
    return db


# ── the plan: reads only ─────────────────────────────────────────────────────

def test_the_plan_takes_exactly_the_undecided_games_45_to_56_minutes_out():
    """RULE: fetch for an undecided game whose tip is 45-56 minutes away
    (FETCH_LEAD_MIN), so the first fetch lands about 55-56 minutes out, beside
    the graded bets' 54.3. A decided game, or one holding a BET, is never
    fetched again."""
    games = _slate(G44=44, G45=45, G50=50, G56=56, G57=57, G_DONE=50, G_BET=52)
    p = ttw.plan(_db(decided={"G_DONE"}, bets={"G_BET"}), NOW, games=games)
    assert p.decide == ["G45", "G50", "G56"] and p.close == []


def test_the_close_is_planned_once_for_bet_games_12_to_25_minutes_out():
    """RULE: the closing snapshot is bought only for a game holding this
    model's BET, once, 12-25 minutes before tip (CLV measured, never a false
    zero)."""
    games = _slate(G12=12, G13=13, G20=20, G25=25, G26=26, G_NOBET=20, G_TAKEN=18,
                   G_OTHER_MODEL=20)
    db = _db(bets={"G12", "G13", "G20", "G25", "G26", "G_TAKEN"}, closes={"G_TAKEN"})
    assert ttw.plan(db, NOW, games=games).close == ["G13", "G20", "G25"]


def test_a_schedule_placeholder_with_no_teams_is_never_planned():
    """The schedule lists NBA Cup knockout placeholders ('NaN' at home and
    away) as regular games at midnight Eastern. No feed event is that game,
    so planning it would fail its call on every tick of its window."""
    games = _slate(G50=50, NBA_2026_12_04_nan_nan=50, G_CLOSE=20)
    games["NBA_2026_12_04_nan_nan"].update(home="NaN", away="NaN")
    games["G_CLOSE"].update(home="NaN")
    db = _db(bets={"G_CLOSE"})
    p = ttw.plan(db, NOW, games=games)
    assert p.decide == ["G50"] and p.close == []


def test_the_plan_creates_no_table():
    """Every tick of every day runs the plan: it reads, and never writes DDL,
    even before the ledgers exist."""
    db = _db(tables=False)
    p = ttw.plan(db, NOW, games=_slate(G50=50, G20=20))
    assert p.decide == ["G50"]
    assert not any(e[0] == "sql" and e[1].startswith(("CREATE", "INSERT", "ALTER", "REVOKE"))
                   for e in db.log)


def test_one_connection_and_one_slate_read_plan_both_nba_totals_models(monkeypatch):
    """RULE: no second every-minute connection. Both NBA totals models are
    planned on one connection and one slate read; each model's plan gets that
    same slate."""
    import scripts.nba_total_luck_card as tlcard
    import scripts.nba_total_luck_window as tlw
    opened, slates, got = [], [], {}
    games = _slate(G63=63, G50=50)
    db = _db()
    monkeypatch.setattr(pw, "get_connection", lambda: opened.append(1) or db)
    monkeypatch.setattr(tlcard, "slate", lambda conn, now, skipped=None, horizon_min=None:
                        slates.append(horizon_min) or games)
    monkeypatch.setattr(tlcard, "decided_games", lambda conn, ids: set())
    real_tl, real_tt = tlw.plan, ttw.plan

    def tl_plan(conn, now, games=None):
        got["tl"] = games
        return real_tl(conn, now, games)

    def tt_plan(conn, now, games=None):
        got["tt"] = games
        return real_tt(conn, now, games)
    monkeypatch.setattr(tlw, "plan", tl_plan)
    monkeypatch.setattr(ttw, "plan", tt_plan)
    plan = pw.plan_tick(NOW)
    assert opened == [1] and slates == [66.0]
    assert got["tl"] is games and got["tt"] is games
    assert plan.total_luck == ["G63"] and plan.team_total.decide == ["G50"]


def test_the_shared_plan_skips_a_placeholder_for_both_nba_totals_models(monkeypatch):
    """RULE: on the scheduler's path (one slate read for both models), an NBA
    Cup placeholder with no teams is planned by neither model: one rule
    (scripts/nba_total_luck_window.has_teams), applied by each model's plan.
    Production holds three such games rows for 2026-27, each tipping at
    midnight Eastern (read 2026-10-20)."""
    import scripts.nba_total_luck_card as tlcard
    games = _slate(G63=63, G50=50)
    games["NBA_2026-12-04_nan_nan"] = {**games["G63"], "home": "NaN", "away": "NaN"}
    games["NBA_2026-12-05_nan_nan"] = {**games["G50"], "home": "NaN", "away": "NaN"}
    db = _db()
    monkeypatch.setattr(pw, "get_connection", lambda: db)
    monkeypatch.setattr(tlcard, "slate", lambda conn, now, skipped=None, horizon_min=None: games)
    monkeypatch.setattr(tlcard, "decided_games", lambda conn, ids: set())
    plan = pw.plan_tick(NOW)
    assert plan.errors == {}
    assert plan.total_luck == ["G63"]
    assert plan.team_total.decide == ["G50"] and plan.team_total.close == []


def test_the_shared_slate_reaches_both_windows():
    import scripts.nba_total_luck_window as tlw
    assert pw.HORIZON_MIN >= tlw.LOOK_AHEAD_MIN[1]
    assert pw.HORIZON_MIN >= tt.FETCH_LEAD_MIN[1] and pw.HORIZON_MIN >= ttw.CLOSE_LEAD_MIN[1]


# ── the window: one skipped tick cannot lose a game ──────────────────────────

def _job(monkeypatch):
    from tests.test_nba_prop_window import _jobs
    return _jobs(monkeypatch)["nba_total_luck_window"]


def _fires(job, start, end):
    from tests.test_nba_prop_window import _fires as fires
    return fires(job, start, end)


def test_the_decision_window_holds_at_least_two_of_the_job_s_ticks(monkeypatch):
    """RULE: the fetch window is at least two of the job's ticks wide and sits
    inside the card's decision window."""
    job = _job(monkeypatch)
    day = et(2026, 11, 5, 0, 0)
    fires = _fires(job, day, day + timedelta(hours=24) - timedelta(seconds=1))
    cadence = max((b - a).total_seconds() / 60 for a, b in zip(fires, fires[1:]))
    assert len(fires) == 1440 and cadence == 1.0
    lo, hi = tt.FETCH_LEAD_MIN
    assert hi - lo >= 2 * cadence
    assert tt.DECISION_LEAD_MIN[0] <= lo and hi < tt.DECISION_LEAD_MIN[1]


def _decided_by(tip, ticks, skip=(), lag_s=10.0):
    """The ticks: plan (the game in FETCH_LEAD_MIN), fetch (lands `lag_s`
    later), card (timing on that fetch, 20 s on). -> the lead of the fetch
    that decided, or None."""
    lo, hi = tt.FETCH_LEAD_MIN
    for i, t in enumerate(ticks):
        if i in skip or not lo <= tt.lead_minutes(tip, t) <= hi:
            continue
        fetch = t + timedelta(seconds=lag_s)
        if tt.timing(tip, fetch, fetch + timedelta(seconds=20)) == "decide":
            return tt.lead_minutes(tip, fetch)
    return None


@pytest.mark.parametrize("hh,mm", [(12, 0), (13, 0), (15, 30), (19, 0), (19, 30), (22, 10)])
def test_every_tip_is_decided_near_the_graded_lead_and_a_skipped_tick_loses_nothing(
        monkeypatch, hh, mm):
    """RULE: the first tick in the window decides, on a fetch 54-56 minutes
    out -- beside the graded bets' 54.3-54.4 -- even when the full-game model's
    steps ran first in the same tick (a fetch 90 s late); with that tick
    skipped, the next one decides."""
    tip = et(2026, 11, 5, hh, mm)
    ticks = _fires(_job(monkeypatch), tip - timedelta(minutes=120), tip)
    first = _decided_by(tip, ticks)
    assert first is not None and 54.0 <= first <= 56.0, first
    late = _decided_by(tip, ticks, lag_s=90.0)
    assert late is not None and 54.0 <= late <= 56.0, late
    window = [i for i, t in enumerate(ticks)
              if tt.FETCH_LEAD_MIN[0] <= tt.lead_minutes(tip, t) <= tt.FETCH_LEAD_MIN[1]]
    assert _decided_by(tip, ticks, skip=window[:1]) is not None
    assert _decided_by(tip, ticks, skip=window) is None


# ── the tick, inside the NBA totals window job ───────────────────────────────

def _tick(monkeypatch, plan, fail=()):
    import scheduler
    ran, published = [], []
    monkeypatch.setattr(pw, "plan_tick", lambda now=None: plan)
    monkeypatch.setattr(scheduler, "_run", lambda cmd, label, **kw:
                        ran.append((label, cmd, kw)) or ("fail" if label in fail else "ok"))
    monkeypatch.setattr(scheduler, "_publish_new_signals", published.append)
    scheduler.run_nba_total_luck_window()
    return ran, published


def test_a_team_total_tick_fetches_exactly_the_planned_games_then_decides(monkeypatch):
    ran, published = _tick(monkeypatch, pw.PregamePlan(team_total=ttw.Plan(decide=["G1", "G2"])))
    assert [r[0] for r in ran] == ["nba-team-total-luck-fetch", "nba-team-total-luck"]
    assert ran[0][1][-5:] == ["-m", "scripts.nba_team_total_luck_window", "--fetch", "G1", "G2"]
    assert ran[1][1][-2:] == ["--step", "nba-team-total-luck"]
    assert all(kw.get("timeout") for _, _, kw in ran), "every step is bounded"
    assert published == ["nba-total-luck-window"]


def test_both_models_due_run_the_full_game_model_first_and_publish_once(monkeypatch):
    plan = pw.PregamePlan(total_luck=["GA"],
                          team_total=ttw.Plan(decide=["GB"], close=["GC"]))
    ran, published = _tick(monkeypatch, plan)
    assert [r[0] for r in ran] == ["nba-total-luck-fetch", "nba-total-luck",
                                   "nba-team-total-luck-fetch", "nba-team-total-luck",
                                   "nba-team-total-luck-close"]
    assert ran[-1][1][-4:] == ["-m", "scripts.nba_team_total_luck_window", "--close", "GC"]
    assert published == ["nba-total-luck-window"]


def test_a_close_alone_runs_only_the_close(monkeypatch):
    ran, _ = _tick(monkeypatch, pw.PregamePlan(team_total=ttw.Plan(close=["GC"])))
    assert [r[0] for r in ran] == ["nba-team-total-luck-close"]


def test_an_idle_tick_spends_nothing(monkeypatch):
    ran, published = _tick(monkeypatch, pw.PregamePlan())
    assert ran == [] and published == []


def test_a_failed_team_total_step_is_an_error_after_publishing(monkeypatch):
    with pytest.raises(RuntimeError, match="nba-team-total-luck-fetch"):
        _tick(monkeypatch, pw.PregamePlan(team_total=ttw.Plan(decide=["G1"])),
              fail={"nba-team-total-luck-fetch"})


def test_a_fetch_with_a_failed_call_exits_non_zero_and_an_empty_one_does_not(monkeypatch):
    monkeypatch.setattr(ttw, "fetch", lambda ids, kind="open": {"failed": ["G1"]})
    monkeypatch.setattr(sys, "argv", ["nba_team_total_luck_window", "--fetch", "G1"])
    with pytest.raises(SystemExit) as e:
        ttw.main()
    assert e.value.code == 1
    seen = []
    monkeypatch.setattr(ttw, "fetch", lambda ids, kind="open": seen.append((ids, kind)) or
                        {"failed": [], "no_team_total": ["G1"]})
    ttw.main()
    monkeypatch.setattr(sys, "argv", ["nba_team_total_luck_window", "--close", "G2"])
    ttw.main()
    assert seen == [(["G1"], "open"), (["G2"], "close")]


def test_it_rides_the_nba_totals_window_job_and_adds_no_job(monkeypatch):
    """RULE: no second every-minute job. Each scheduled job's heartbeat opens
    a connection on every tick (scheduler._with_heartbeat ->
    tracking/job_heartbeat.beat), so this model runs in the NBA totals window
    job, whose id, cadence and watch are the full-game model's."""
    import inspect

    import scheduler
    from tests.test_nba_prop_window import _jobs
    from tracking import job_heartbeat
    jobs = _jobs(monkeypatch)
    assert not [j for j in jobs if "team_total" in j], "a job of its own"
    assert "beat(jid" in inspect.getsource(scheduler.build_scheduler)
    assert "get_connection()" in inspect.getsource(job_heartbeat.beat)
    src = inspect.getsource(scheduler.run_nba_total_luck_window)
    assert "scripts.nba_team_total_luck_window" in src
    assert job_heartbeat.MAX_SILENCE["nba_total_luck_window"] == 20


# ── one model's plan cannot stop the other ───────────────────────────────────

def test_a_failing_team_total_plan_still_runs_the_full_game_model_then_fails(monkeypatch):
    """RULE: the team-total plan raising (a bad read of its ledgers or picks)
    must not stop nba_total_luck's fetch and card. Its steps run and publish,
    then the tick raises, so the heartbeat records an error. Watched failing
    when one expression built both plans."""
    import scheduler
    import scripts.nba_total_luck_card as tlcard
    games = _slate(G63=63, G50=50)
    db = _db()
    monkeypatch.setattr(pw, "get_connection", lambda: db)
    monkeypatch.setattr(tlcard, "slate", lambda conn, now, skipped=None, horizon_min=None: games)
    monkeypatch.setattr(tlcard, "decided_games", lambda conn, ids: set())

    def broken(conn, now, games=None):
        raise RuntimeError("team-total plan read failed")
    monkeypatch.setattr(ttw, "plan", broken)
    plan = pw.plan_tick(NOW)
    assert plan.total_luck == ["G63"] and plan.team_total == ttw.Plan()
    assert set(plan.errors) == {"nba_team_total_luck"} and plan
    ran, published = [], []
    monkeypatch.setattr(pw, "plan_tick", lambda now=None: plan)
    monkeypatch.setattr(scheduler, "_run", lambda cmd, label, **kw: ran.append(label) or "ok")
    monkeypatch.setattr(scheduler, "_publish_new_signals", published.append)
    with pytest.raises(RuntimeError, match="nba_team_total_luck plan"):
        scheduler.run_nba_total_luck_window()
    assert ran == ["nba-total-luck-fetch", "nba-total-luck"]
    assert published == ["nba-total-luck-window"]


def test_a_failing_plan_with_nothing_else_due_is_still_an_error(monkeypatch):
    """A plan that raised on a tick with nothing else due is not an idle
    tick: it raises, and nothing is fetched or published."""
    import scheduler
    plan = pw.PregamePlan(errors={"nba_total_luck": "RuntimeError('x')"})
    assert plan
    ran, published = [], []
    monkeypatch.setattr(pw, "plan_tick", lambda now=None: plan)
    monkeypatch.setattr(scheduler, "_run", lambda cmd, label, **kw: ran.append(label) or "ok")
    monkeypatch.setattr(scheduler, "_publish_new_signals", published.append)
    with pytest.raises(RuntimeError, match="nba_total_luck plan"):
        scheduler.run_nba_total_luck_window()
    assert ran == [] and published == []
