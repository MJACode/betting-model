"""The NBA totals window job: every nba_total_luck game decided on a fetch 60-66
minutes before tip, in a job of its own.

Riding the refresh pass, the card had one look per game: the pass exactly 60
minutes out. The scheduler skips a tick while the previous pass is still
running, and 27 of the 504 evening ticks over 2026-10-03..16 never started
(production pipeline_runs, read 2026-10-17), so a game whose deciding tick was
skipped was never priced. This job runs every minute, fetches the NBA board
only when an undecided game is 61-66 minutes from tip, runs the card on that
fetch and publishes. The timing rule itself is pinned in
tests/test_nba_total_luck.py.
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
UTC = timezone.utc


def _et(y, m, d, hh, mm, ss=0):
    return datetime(y, m, d, hh, mm, ss, tzinfo=ET).astimezone(UTC)


# ── the plan: one read, no API call ──────────────────────────────────────────

def test_the_plan_lists_exactly_the_undecided_games_61_to_66_minutes_out(monkeypatch):
    import scripts.nba_total_luck_card as card
    import scripts.nba_total_luck_window as win
    now = _et(2026, 11, 5, 18, 0)
    games = {g: {"home": "H", "away": "A", "game_date": "2026-11-05", "season": 2027,
                 "tip": now + timedelta(minutes=m)}
             for g, m in (("G60", 60), ("G61", 61), ("G66", 66), ("G67", 67), ("G_DONE", 64))}
    seen = {}

    def fake_slate(conn, n, skipped=None, horizon_min=None):
        seen["horizon"] = horizon_min
        return {g: v for g, v in games.items()
                if v["tip"] <= n + timedelta(minutes=horizon_min)}
    monkeypatch.setattr(card, "slate", fake_slate)
    monkeypatch.setattr(card, "decided_games", lambda conn, ids: {"G_DONE"} & set(ids))
    assert win.plan(object(), now) == ["G61", "G66"]
    assert seen["horizon"] == win.LOOK_AHEAD_MIN[1]


def test_the_plan_creates_no_table(monkeypatch):
    """Every tick of every day runs the plan: it reads, it never writes DDL."""
    import scripts.nba_total_luck_card as card
    import scripts.nba_total_luck_window as win
    monkeypatch.setattr(card, "ensure_decisions_table",
                        lambda conn: (_ for _ in ()).throw(AssertionError("DDL in the plan")))
    monkeypatch.setattr(card, "slate", lambda *a, **k: {})
    assert win.plan(object(), _et(2026, 11, 5, 18, 0)) == []


# ── the tick ─────────────────────────────────────────────────────────────────

def _tick(monkeypatch, due, result="ok"):
    import scheduler
    import scripts.nba_pregame_window as pw
    ran, published = [], []
    # One planning read for both NBA totals models (scripts/nba_pregame_window);
    # nba_team_total_luck has nothing due here.
    monkeypatch.setattr(pw, "plan_tick", lambda now=None: pw.PregamePlan(total_luck=due))
    monkeypatch.setattr(scheduler, "_run",
                        lambda cmd, label, **kw: ran.append((label, cmd, kw)) or
                        (result if label == "nba-total-luck-fetch" else "ok"))
    monkeypatch.setattr(scheduler, "_publish_new_signals", published.append)
    scheduler.run_nba_total_luck_window()
    return ran, published


def test_a_tick_with_nothing_due_spends_nothing(monkeypatch):
    ran, published = _tick(monkeypatch, [])
    assert ran == [] and published == []


def test_a_tick_fetches_then_decides_then_publishes_each_step_bounded(monkeypatch):
    ran, published = _tick(monkeypatch, ["G1", "G2"])
    assert [label for label, _, _ in ran] == ["nba-total-luck-fetch", "nba-total-luck"]
    assert ran[0][1][-3:] == ["-m", "scripts.nba_total_luck_window", "--fetch"]
    assert ran[1][1][-2:] == ["--step", "nba-total-luck"]
    assert all(kw.get("timeout") for _, _, kw in ran), "every step is bounded (see _run)"
    assert published == ["nba-total-luck-window"]


def test_a_failed_step_is_recorded_as_an_error_after_publishing(monkeypatch):
    import scheduler
    import scripts.nba_pregame_window as pw
    published = []
    monkeypatch.setattr(pw, "plan_tick", lambda now=None: pw.PregamePlan(total_luck=["G1"]))
    monkeypatch.setattr(scheduler, "_run", lambda cmd, label, **kw:
                        "timeout" if label == "nba-total-luck-fetch" else "ok")
    monkeypatch.setattr(scheduler, "_publish_new_signals", published.append)
    with pytest.raises(RuntimeError, match="nba-total-luck-fetch"):
        scheduler.run_nba_total_luck_window()
    assert published == ["nba-total-luck-window"]


def test_a_fetch_that_stored_nothing_exits_non_zero(monkeypatch):
    """The ingestor logs a failed call and returns; the step must not read as ok."""
    import scripts.nba_total_luck_window as win
    monkeypatch.setattr(win, "fetch", lambda now=None: {"odds_rows": 0})
    monkeypatch.setattr(sys, "argv", ["nba_total_luck_window", "--fetch"])
    with pytest.raises(SystemExit) as e:
        win.main()
    assert e.value.code == 1
    monkeypatch.setattr(win, "fetch", lambda now=None: {"odds_rows": 240})
    win.main()


def test_the_fetch_is_the_refresh_pass_s_own_nba_fetch(monkeypatch):
    import data.ingestors.odds_ingestor as ing
    import scripts.nba_total_luck_window as win
    calls = []
    monkeypatch.setattr(ing, "run_odds_ingestor", lambda **kw: calls.append(kw) or {"odds_rows": 1})
    win.fetch(_et(2026, 11, 5, 23, 55))           # 23:55 ET: the ET date, not the UTC one
    assert calls == [{"sport": "NBA", "snapshot_type": "open", "target_date": "2026-11-05"}]


# ── the job ──────────────────────────────────────────────────────────────────

def _jobs(monkeypatch):
    from tests.test_nba_prop_window import _jobs as jobs     # one copy of the helper
    return jobs(monkeypatch)


def test_the_job_runs_every_minute_on_the_pipeline_service_and_is_watched(monkeypatch):
    import scheduler
    from tracking.job_heartbeat import MAX_SILENCE
    job = _jobs(monkeypatch)["nba_total_luck_window"]
    assert job.name.startswith("NBA totals window")
    assert job.max_instances == 1 and job.misfire_grace_time <= 60
    assert "nba_total_luck_window" in scheduler._PIPELINE_JOBS
    assert "nba_total_luck_window" not in scheduler._POLLER_JOBS
    assert MAX_SILENCE["nba_total_luck_window"] == 20
