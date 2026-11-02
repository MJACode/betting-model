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


def test_all_three_models_due_each_run_their_own_steps_in_order_and_publish_once(monkeypatch):
    plan = pw.PregamePlan(total_luck=["GA"],
                          team_total=ttw.Plan(decide=["GB"], close=["GC"]),
                          first_half=ttw.Plan(decide=["GD"], close=["GE"]))
    ran, published = _tick(monkeypatch, plan)
    labels = [r[0] for r in ran]
    assert [x for x in labels if x.startswith("nba-total-luck")] == [
        "nba-total-luck-fetch", "nba-total-luck"]
    assert [x for x in labels if x.startswith("nba-team-total-luck")] == [
        "nba-team-total-luck-fetch", "nba-team-total-luck", "nba-team-total-luck-close"]
    assert [x for x in labels if x.startswith("nba-first-half-total-luck")] == [
        "nba-first-half-total-luck-fetch", "nba-first-half-total-luck",
        "nba-first-half-total-luck-close"]
    close = next(r for r in ran if r[0] == "nba-first-half-total-luck-close")
    assert close[1][-4:] == ["-m", "scripts.nba_first_half_total_luck_window", "--close", "GE"]
    assert published == ["nba-total-luck-window"]


def test_the_report_of_a_failed_tick_lists_the_models_in_one_order(monkeypatch):
    """The steps finish in any order; what the heartbeat records does not move."""
    plan = pw.PregamePlan(total_luck=["GA"], team_total=ttw.Plan(decide=["GB"]),
                          first_half=ttw.Plan(decide=["GD"]))
    with pytest.raises(RuntimeError) as e:
        _tick(monkeypatch, plan, fail={"nba-first-half-total-luck", "nba-total-luck"})
    message = str(e.value)
    assert message.index("'nba-total-luck'") < message.index("'nba-first-half-total-luck'")


# ── a slow card holds nobody else's look at the game ─────────────────────────

def test_one_model_s_card_does_not_hold_another_model_s_fetch(monkeypatch):
    """RULE: the models run side by side. Run one after the other, the first-half
    fetch waited for the team-total card, which the worker killed at its 180-second
    limit on 60 of 74 attempts from 2026-10-24 to 10-31. Here the team-total card
    holds until the first half's fetch has started: one after the other, it never
    does."""
    import threading

    import scheduler
    first_half_fetched = threading.Event()
    seen = {}

    def run(cmd, label, **kw):
        if label == "nba-first-half-total-luck-fetch":
            first_half_fetched.set()
        if label == "nba-team-total-luck":
            seen["started_while_the_card_ran"] = first_half_fetched.wait(timeout=3)
        return "ok"
    monkeypatch.setattr(pw, "plan_tick", lambda now=None: pw.PregamePlan(
        team_total=ttw.Plan(decide=["G"]), first_half=ttw.Plan(decide=["G"])))
    monkeypatch.setattr(scheduler, "_run", run)
    monkeypatch.setattr(scheduler, "_publish_new_signals", lambda label: None)
    scheduler.run_nba_total_luck_window()
    assert seen == {"started_while_the_card_ran": True}


FETCH_S, PUBLISH_S = 3.0, 2.0     # the worker's logs, 2026-10-30: 1.9-3.3 s; 2 s


def _window(monkeypatch, cards):
    """The REAL tick through one game's window, on a clock: each step advances its
    own thread's time by a stated duration, a tick lasts as long as its slowest
    thread plus publishing, and the next tick starts on the next cron minute after it
    ends (max_instances=1 skips the ones during it). `cards` is {"team": (seconds,
    outcome), "first": ...}. -> ({model: minutes before tip of each fetch}, {model:
    what the model's own timing rule said of the fetch when its card read it})."""
    import math
    import threading
    from datetime import datetime, timezone

    import scheduler
    tip = datetime(2026, 11, 6, 2, 0, tzinfo=timezone.utc)
    lead = lambda t: (tip - t).total_seconds() / 60.0  # noqa: E731
    tick = {"at": tip - timedelta(minutes=70)}
    decided, fetched = set(), {}
    fetches, timings = {"team": [], "first": []}, {"team": [], "first": []}

    def plan(now=None):
        lo, hi = fh.FETCH_LEAD_MIN
        out = pw.PregamePlan()
        if lo <= lead(tick["at"]) <= hi:
            if "team" not in decided:
                out.team_total = ttw.Plan(decide=["G"])
            if "first" not in decided:
                out.first_half = ttw.Plan(decide=["G"])
        tick["spent"] = {}
        # Holds each model's first step until the others have started, so each is
        # on a thread of its own. One after the other, it gives up and they share one.
        due = sum(bool(p.decide) for p in (out.team_total, out.first_half))
        tick["met"] = threading.Barrier(due) if due else None
        return out

    def run(cmd, label, cwd=None, env=None, timeout=None):
        me = threading.get_ident()
        model = "team" if "team-total" in label else "first"
        if label.endswith("-fetch"):
            try:
                tick["met"].wait(timeout=1.0)
            except threading.BrokenBarrierError:
                pass
        at = tick["at"] + timedelta(seconds=tick["spent"].get(me, 0.0))
        if label.endswith("-fetch"):
            fetches[model].append(round(lead(at), 1))
            fetched[model] = at
            tick["spent"][me] = tick["spent"].get(me, 0.0) + FETCH_S
            return "ok"
        seconds, outcome = cards[model]
        timings[model].append(fh.timing(tip, fetched[model], at))
        tick["spent"][me] = tick["spent"].get(me, 0.0) + min(seconds, timeout)
        if outcome == "ok":
            decided.add(model)
        return outcome
    monkeypatch.setattr(pw, "plan_tick", plan)
    monkeypatch.setattr(scheduler, "_run", run)
    monkeypatch.setattr(scheduler, "_publish_new_signals", lambda label: None)
    while lead(tick["at"]) > 30:
        try:
            scheduler.run_nba_total_luck_window()
        except RuntimeError:
            pass
        took = max(tick["spent"].values(), default=None)
        end = tick["at"] + timedelta(seconds=0 if took is None else took + PUBLISH_S)
        tick["at"] = datetime.fromtimestamp(
            math.floor(end.timestamp() / 60 + 1e-9) * 60 + 60, tz=timezone.utc)
    return fetches, timings


def test_both_cards_killed_at_their_limit_still_leave_each_model_three_attempts(monkeypatch):
    """RULE: the attempts a window gives a model do not depend on another model's
    card. 56, 52 and 48 minutes before tip are what the team-total model has had
    alone, and what the worker's logs show for it (01:04, 01:08 and 01:12Z on a
    02:00Z tip, 2026-10-30). One after the other, each model got two: the team total
    56 and 49 minutes out, the first half 53 and 46."""
    killed = (180.0, "timeout")
    fetches, timings = _window(monkeypatch, {"team": killed, "first": killed})
    assert fetches == {"team": [56.0, 52.0, 48.0], "first": [56.0, 52.0, 48.0]}
    assert set(timings["first"]) == {"decide"} and set(timings["team"]) == {"decide"}


@pytest.mark.parametrize("cards, attempts", [
    ({"team": (180.0, "timeout"), "first": (111.0, "ok")},
     {"team": [56.0, 52.0, 48.0], "first": [56.0]}),
    ({"team": (84.0, "ok"), "first": (180.0, "timeout")},
     {"team": [56.0], "first": [56.0, 52.0, 48.0]}),
    ({"team": (84.0, "ok"), "first": (84.0, "ok")}, {"team": [56.0], "first": [56.0]}),
    ({"team": (114.0, "fail"), "first": (114.0, "fail")},
     {"team": [56.0, 54.0, 52.0, 50.0, 48.0, 46.0], "first": [56.0, 54.0, 52.0, 50.0, 48.0, 46.0]}),
])
def test_one_model_s_outcome_never_changes_the_other_s_attempts(monkeypatch, cards, attempts):
    fetches, _ = _window(monkeypatch, cards)
    assert fetches == attempts


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
