"""The NHL shot and xG tables stopped because nothing called the ingestor.

Measured 2026-11-26: nhl_shot_events, nhl_team_game_xg and nhl_goalie_game_xg
end at 2026-10-12 (fetched 2026-10-14). The team log goes through 2026-11-25.
run() already skips a game it has stored. It had no schedule.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPE = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
SCHED = (ROOT / "scheduler.py").read_text(encoding="utf-8")
XG = (ROOT / "data" / "nhl_xg.py").read_text(encoding="utf-8")
AGG = (ROOT / "data" / "nhl_xg_aggregates.py").read_text(encoding="utf-8")


def test_shots_are_a_pipeline_step_before_the_health_check():
    choices = PIPE.split("choices=[", 1)[1].split("]", 1)[0]
    assert '"nhl-shots"' in choices
    assert '"moneypuck-nhl"' in choices
    assert 'results["nhl_shots"] = step_nhl_shots' in PIPE
    assert PIPE.index('results["nhl_shots"]') < PIPE.index('results["health_check"]')
    body = PIPE.split("def step_nhl_shots", 1)[1].split("\ndef ", 1)[0]
    assert "shot_run" in body
    assert "score_unscored" in body
    assert "apply_missing" in body
    assert "if failed:" in body
    assert "return False" in body


def test_moneypuck_runs_at_7_20_on_the_pipeline_service():
    ids = re.findall(r'^\s*id="([^"]+)"', SCHED, re.M)
    assert "moneypuck_nhl" in ids
    block = SCHED.split('id="moneypuck_nhl"', 1)[0]
    assert "hour=7, minute=20" in block[-400:]
    assert SCHED.index('id="pipeline_watch"') < SCHED.index('id="moneypuck_nhl"')
    import scheduler
    assert "moneypuck_nhl" in scheduler._PIPELINE_JOBS
    assert "moneypuck_nhl" not in scheduler._POLLER_JOBS
    assert "byom_nfl_refresh" in scheduler._PIPELINE_JOBS


def test_new_shots_are_scored_without_rewriting_stored_xg():
    assert "AND s.xg IS NULL" in XG
    assert "only_null" in XG
    assert "xg IS NULL AND event_type IN" in XG
    assert "blocked-shot" not in XG.split("UNSCORED_WHERE", 1)[1].split(")", 1)[0]
    assert "NOT EXISTS" in AGG
    assert "nhl_team_game_xg" in AGG


def test_a_two_day_lag_is_the_shot_check_and_a_longer_one_is_stale():
    from tracking.system_health import OK, STALE, feed_lag
    status, _ = feed_lag("nhl_shot_events", "2026-11-25", "2026-11-25")
    assert status == OK
    status, detail = feed_lag("nhl_shot_events", "2026-11-23", "2026-11-25")
    assert status == OK
    status, detail = feed_lag("nhl_shot_events", "2026-10-12", "2026-11-25")
    assert status == STALE
    assert "2026-10-12" in detail
    status, detail = feed_lag("moneypuck_team_games", None, "2026-11-25")
    assert status == STALE
    text = (ROOT / "tracking" / "system_health.py").read_text(encoding="utf-8")
    assert "nhl_shot_freshness" in text
    assert "moneypuck_freshness" in text
    assert "MoneyPuck.com" in text
