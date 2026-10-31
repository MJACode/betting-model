"""nba_first_half_total_luck's window: what a tick plans, how it runs inside the
NBA totals window job, and why it is that job and not a new one.

The plan reads only; the job's steps are recorded, never run; no test calls the
Odds API. The timing rule itself is the team total's
(tests/test_nba_team_total_luck.py), imported by this model.
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

import data.ingestors.nba_first_half_odds as feed  # noqa: E402
import models.nba_first_half_total_luck as fh  # noqa: E402
import scripts.nba_first_half_total_luck_card as card  # noqa: E402
import scripts.nba_first_half_total_luck_window as h1w  # noqa: E402
import scripts.nba_pregame_window as pw  # noqa: E402
import scripts.nba_team_total_luck_window as ttw  # noqa: E402
from tests.test_nba_first_half_odds import H1DB  # noqa: E402
from tests.test_nba_team_total_odds import Clock, et  # noqa: E402

MODEL = fh.MODEL_ID
NOW = et(2026, 11, 5, 18, 0)


def _slate(**leads):
    return {g: {"home": "MIL", "away": "BOS", "game_date": "2026-11-05", "season": 2027,
                "tip": NOW + timedelta(minutes=m)} for g, m in leads.items()}


def _db(decided=(), bets=(), closes=(), tables=True):
    db = H1DB(Clock(NOW), tables=(card.DECISIONS_TABLE, feed.LEDGER_TABLE) if tables else ())
    db.rows[card.DECISIONS_TABLE] += [{"game_id": g} for g in decided]
    db.rows["picks"] += [{"game_id": g, "model_id": MODEL, "signal_type": "BET"} for g in bets]
    db.rows["picks"].append({"game_id": "G_OTHER_MODEL", "model_id": "nba_team_total_luck",
                             "signal_type": "BET"})
    db.rows[feed.LEDGER_TABLE] += [
        {"game_id": g, "endpoint": feed.EVENT_ODDS, "snapshot_type": "close", "ok": True,
         "fetch_at": NOW - timedelta(minutes=1)} for g in closes]
    return db


# ── the plan: reads only ─────────────────────────────────────────────────────

def test_the_plan_takes_exactly_the_undecided_games_45_to_56_minutes_out():
    """RULE: fetch for an undecided game whose tip is 45-56 minutes away, so the
    first fetch lands about 55-56 minutes out, beside the graded bets' 54.4. A
    decided game, or one holding a BET, is never fetched again."""
    games = _slate(G44=44, G45=45, G50=50, G56=56, G57=57, G_DONE=50, G_BET=52)
    p = h1w.plan(_db(decided={"G_DONE"}, bets={"G_BET"}), NOW, games=games)
    assert p.decide == ["G45", "G50", "G56"] and p.close == []


def test_the_close_is_planned_once_for_bet_games_12_to_25_minutes_out():
    """RULE: the closing snapshot is bought only for a game holding this model's
    BET, once, 12-25 minutes before tip (closing-line value measured, never a
    false zero). Another model's bet buys nothing here."""
    games = _slate(G12=12, G13=13, G20=20, G25=25, G26=26, G_NOBET=20, G_TAKEN=18,
                   G_OTHER_MODEL=20)
    db = _db(bets={"G12", "G13", "G20", "G25", "G26", "G_TAKEN"}, closes={"G_TAKEN"})
    assert h1w.plan(db, NOW, games=games).close == ["G13", "G20", "G25"]


def test_a_schedule_placeholder_with_no_teams_is_never_planned():
    games = _slate(G50=50, NBA_2026_12_04_nan_nan=50, G_CLOSE=20)
    games["NBA_2026_12_04_nan_nan"].update(home="NaN", away="NaN")
    games["G_CLOSE"].update(home="NaN")
    p = h1w.plan(_db(bets={"G_CLOSE"}), NOW, games=games)
    assert p.decide == ["G50"] and p.close == []


def test_the_plan_creates_no_table():
    """Every tick of every day runs the plan: it reads, and never writes DDL, even
    before the ledgers exist."""
    db = _db(tables=False)
    p = h1w.plan(db, NOW, games=_slate(G50=50, G20=20))
    assert p.decide == ["G50"]
    assert not any(e[0] == "sql" and e[1].startswith(("CREATE", "INSERT", "ALTER", "REVOKE"))
                   for e in db.log)


def test_one_connection_and_one_slate_read_plan_all_three_models(monkeypatch):
    """RULE: no new every-minute connection. All three models are planned on one
    connection and one slate read; each plan gets that same slate."""
    import scripts.nba_total_luck_card as tlcard
    import scripts.nba_total_luck_window as tlw
    opened, slates, got = [], [], {}
    games = _slate(G63=63, G50=50)
    db = _db()
    monkeypatch.setattr(pw, "get_connection", lambda: opened.append(1) or db)
    monkeypatch.setattr(tlcard, "slate", lambda conn, now, skipped=None, horizon_min=None:
                        slates.append(horizon_min) or games)
    monkeypatch.setattr(tlcard, "decided_games", lambda conn, ids: set())
    real = {"tl": tlw.plan, "tt": ttw.plan, "h1": h1w.plan}

    def wrap(name):
        def plan(conn, now, games=None):
            got[name] = games
            return real[name](conn, now, games)
        return plan
    monkeypatch.setattr(tlw, "plan", wrap("tl"))
    monkeypatch.setattr(ttw, "plan", wrap("tt"))
    monkeypatch.setattr(h1w, "plan", wrap("h1"))
    plan = pw.plan_tick(NOW)
    assert opened == [1] and slates == [66.0]
    assert got["tl"] is games and got["tt"] is games and got["h1"] is games
    assert plan.total_luck == ["G63"] and plan.first_half.decide == ["G50"]
    assert plan.team_total.decide == ["G50"] and plan.errors == {}
    assert plan


def test_the_shared_slate_reaches_this_window():
    assert pw.HORIZON_MIN >= fh.FETCH_LEAD_MIN[1] and pw.HORIZON_MIN >= h1w.CLOSE_LEAD_MIN[1]


def test_a_tick_with_nothing_due_for_any_model_is_false():
    assert not pw.PregamePlan()
    assert pw.PregamePlan(first_half=ttw.Plan(decide=["G"]))
    assert pw.PregamePlan(first_half=ttw.Plan(close=["G"]))


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


def test_a_first_half_tick_fetches_exactly_the_planned_games_then_decides(monkeypatch):
    ran, published = _tick(monkeypatch, pw.PregamePlan(first_half=ttw.Plan(decide=["G1", "G2"])))
    assert [r[0] for r in ran] == ["nba-first-half-total-luck-fetch", "nba-first-half-total-luck"]
    assert ran[0][1][-5:] == ["-m", "scripts.nba_first_half_total_luck_window", "--fetch",
                              "G1", "G2"]
    assert ran[1][1][-2:] == ["--step", "nba-first-half-total-luck"]
    assert all(kw.get("timeout") for _, _, kw in ran), "every step is bounded"
    assert published == ["nba-total-luck-window"]


def test_all_three_models_due_run_in_order_and_publish_once(monkeypatch):
    plan = pw.PregamePlan(total_luck=["GA"],
                          team_total=ttw.Plan(decide=["GB"], close=["GC"]),
                          first_half=ttw.Plan(decide=["GD"], close=["GE"]))
    ran, published = _tick(monkeypatch, plan)
    assert [r[0] for r in ran] == ["nba-total-luck-fetch", "nba-total-luck",
                                   "nba-team-total-luck-fetch", "nba-team-total-luck",
                                   "nba-team-total-luck-close",
                                   "nba-first-half-total-luck-fetch", "nba-first-half-total-luck",
                                   "nba-first-half-total-luck-close"]
    assert ran[-1][1][-4:] == ["-m", "scripts.nba_first_half_total_luck_window", "--close", "GE"]
    assert published == ["nba-total-luck-window"]


def test_a_close_alone_runs_only_the_close(monkeypatch):
    ran, _ = _tick(monkeypatch, pw.PregamePlan(first_half=ttw.Plan(close=["GC"])))
    assert [r[0] for r in ran] == ["nba-first-half-total-luck-close"]


def test_a_failed_team_total_step_does_not_stop_the_first_half_s_steps(monkeypatch):
    """RULE: each model's decision is its own. The team total's fetch failing, or
    its card, still runs the first half's fetch and card; the tick then fails, so
    the heartbeat records an error, after publishing."""
    plan = pw.PregamePlan(team_total=ttw.Plan(decide=["GB"]),
                          first_half=ttw.Plan(decide=["GD"]))
    import scheduler
    ran, published = [], []
    monkeypatch.setattr(pw, "plan_tick", lambda now=None: plan)
    monkeypatch.setattr(scheduler, "_run", lambda cmd, label, **kw: ran.append(label) or (
        "fail" if label.startswith("nba-team-total") else "ok"))
    monkeypatch.setattr(scheduler, "_publish_new_signals", published.append)
    with pytest.raises(RuntimeError, match="nba-team-total-luck-fetch"):
        scheduler.run_nba_total_luck_window()
    assert "nba-first-half-total-luck-fetch" in ran and "nba-first-half-total-luck" in ran
    assert published == ["nba-total-luck-window"]


def test_a_failed_first_half_step_does_not_stop_the_team_total_s_steps(monkeypatch):
    plan = pw.PregamePlan(team_total=ttw.Plan(decide=["GB"]),
                          first_half=ttw.Plan(decide=["GD"]))
    with pytest.raises(RuntimeError, match="nba-first-half-total-luck-fetch"):
        _tick(monkeypatch, plan, fail={"nba-first-half-total-luck-fetch"})


def test_a_failing_first_half_plan_still_runs_the_others_then_fails(monkeypatch):
    """RULE: the first half's plan raising must not stop the other two models'
    fetch and card. Their steps run and publish, then the tick raises."""
    import scheduler
    import scripts.nba_total_luck_card as tlcard
    games = _slate(G63=63, G50=50)
    db = _db()
    monkeypatch.setattr(pw, "get_connection", lambda: db)
    monkeypatch.setattr(tlcard, "slate", lambda conn, now, skipped=None, horizon_min=None: games)
    monkeypatch.setattr(tlcard, "decided_games", lambda conn, ids: set())

    def broken(conn, now, games=None):
        raise RuntimeError("first-half plan read failed")
    monkeypatch.setattr(h1w, "plan", broken)
    plan = pw.plan_tick(NOW)
    assert plan.total_luck == ["G63"] and plan.team_total.decide == ["G50"]
    assert plan.first_half == ttw.Plan() and set(plan.errors) == {MODEL}
    ran, published = [], []
    monkeypatch.setattr(pw, "plan_tick", lambda now=None: plan)
    monkeypatch.setattr(scheduler, "_run", lambda cmd, label, **kw: ran.append(label) or "ok")
    monkeypatch.setattr(scheduler, "_publish_new_signals", published.append)
    with pytest.raises(RuntimeError, match="nba_first_half_total_luck plan"):
        scheduler.run_nba_total_luck_window()
    assert "nba-total-luck" in ran and "nba-team-total-luck" in ran
    assert published == ["nba-total-luck-window"]


def test_a_fetch_with_a_failed_call_exits_non_zero_and_an_empty_one_does_not(monkeypatch):
    monkeypatch.setattr(h1w, "fetch", lambda ids, kind="open": {"failed": ["G1"]})
    monkeypatch.setattr(sys, "argv", ["nba_first_half_total_luck_window", "--fetch", "G1"])
    with pytest.raises(SystemExit) as e:
        h1w.main()
    assert e.value.code == 1
    seen = []
    monkeypatch.setattr(h1w, "fetch", lambda ids, kind="open": seen.append((ids, kind)) or
                        {"failed": [], "no_first_half": ["G1"]})
    h1w.main()
    monkeypatch.setattr(sys, "argv", ["nba_first_half_total_luck_window", "--close", "G2"])
    h1w.main()
    assert seen == [(["G1"], "open"), (["G2"], "close")]


def test_it_rides_the_nba_totals_window_job_and_adds_no_job(monkeypatch):
    """RULE: no new every-minute job. Each scheduled job's heartbeat opens a
    connection on every tick, so this model runs in the NBA totals window job."""
    import inspect

    import scheduler
    from tests.test_nba_prop_window import _jobs
    from tracking import job_heartbeat
    jobs = _jobs(monkeypatch)
    assert not [j for j in jobs if "first_half" in j], "a job of its own"
    src = inspect.getsource(scheduler.run_nba_total_luck_window)
    assert "scripts.nba_first_half_total_luck_window" in src
    assert job_heartbeat.MAX_SILENCE["nba_total_luck_window"] == 20


def test_the_step_is_on_the_pipeline_s_list():
    import inspect

    import run_pipeline
    src = inspect.getsource(run_pipeline)
    assert '"nba-first-half-total-luck": lambda: step_nba_first_half_total_luck' in src
    assert run_pipeline.step_nba_first_half_total_luck is not None
