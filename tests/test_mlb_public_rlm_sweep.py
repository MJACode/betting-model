"""Public RLM sweep: post-start splits are dropped; strategies grade DK prices."""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

import tracking.job_queue as jq
from scripts import mlb_public_rlm_sweep as rlm

ROOT = Path(__file__).resolve().parents[1]
DECLARED_KEY = "mlb-public-rlm-sweep-2026-09-16"


def _row(**kw):
    base = dict(
        game_id="G1", game_date="2026-06-15", market="totals",
        home_score=3.0, away_score=2.0,
        tix_home=None, money_home=None, tix_away=None, money_away=None,
        tix_over=80.0, money_over=55.0, tix_under=20.0, money_under=45.0,
        home_price=None, away_price=None, spread_home=None, total_line=8.5,
        over_price=-110.0, under_price=-110.0,
        pin_home=None, pin_away=None, pin_spread=None, pin_total=8.5,
        pin_over=100.0, pin_under=-120.0,
    )
    base.update(kw)
    return base


def test_post_start_snapshot_is_not_pregame():
    from features.feature_engine import _is_pregame_snapshot
    commence = "2026-06-15T23:05:00+00:00"
    assert _is_pregame_snapshot("2026-06-15T22:00:00+00:00", commence) is True
    assert _is_pregame_snapshot("2026-06-16T01:00:00+00:00", commence) is False


def test_fade_public_over_bets_the_under_at_the_dk_price():
    rows = [_row()]
    got = rlm.collect_public_strategies(rows)
    picks = got["fade_public_over_tix_70"]
    assert len(picks) == 1
    date, _edge, price, won, book = picks[0]
    assert date == "2026-06-15"
    assert price == -110.0
    assert book == "draftkings"
    assert won is True  # 5 runs under 8.5
    assert "control_always_under" in got
    assert got["control_always_over"][0][3] is False


def test_fade_over_does_not_fire_below_the_ticket_floor():
    rows = [_row(tix_over=60.0)]
    got = rlm.collect_public_strategies(rows)
    assert got.get("fade_public_over_tix_65", []) == []
    assert got.get("fade_public_over_tix_70", []) == []
    for k, v in got.items():
        if k.startswith("fade_public_over"):
            assert v == []


def test_classic_fade_fav_rl_needs_tickets_and_money():
    row = _row(
        market="spreads", total_line=None, over_price=None, under_price=None,
        spread_home=-1.5, home_price=-150.0, away_price=130.0,
        tix_home=90.0, money_home=30.0, tix_away=10.0, money_away=70.0,
        tix_over=None, money_over=None, home_score=2.0, away_score=5.0,
        pin_total=None, pin_over=None, pin_under=None, pin_spread=-1.5,
        pin_home=-140.0, pin_away=120.0,
    )
    got = rlm.collect_public_strategies([row])
    picks = got["fade_public_fav_rl_tix70_money45"]
    assert len(picks) == 1
    # Home is the public fav −1.5; fade is away. Away won 5-2, covers +1.5.
    assert picks[0][3] is True
    assert picks[0][2] == 130.0


def test_hybrid_requires_pin_lean_under_on_the_same_total():
    # Pin -120 under is the lean; public over 80% tickets → hybrid fires.
    got = rlm.collect_public_strategies([_row()])
    assert len(got["hybrid_fade_over_70_pin_lean_under"]) == 1
    # Flip Pin to over-lean: hybrid must refuse.
    over_lean = _row(pin_over=-130.0, pin_under=110.0)
    got2 = rlm.collect_public_strategies([over_lean])
    assert "hybrid_fade_over_70_pin_lean_under" not in got2


def test_steam_follow_bets_the_direction_of_the_move():
    row = dict(game_id="G1", game_date="2026-04-10", move=0.5,
               line=8.5, over_price=-110.0, under_price=-110.0,
               home_score=6.0, away_score=4.0)
    got = rlm.collect_steam([row])
    follow = got["steam_follow_0.5"]
    fade = got["steam_fade_0.5"]
    assert follow[0][3] is True   # 10 > 8.5, followed over
    assert fade[0][3] is False


def test_job_type_is_registered_and_drops_command():
    assert "mlb_public_rlm_sweep" in jq.JOBS
    _, validate = jq.JOBS["mlb_public_rlm_sweep"]
    got = validate({"date_from": "2026-05-31", "command": "rm -rf /"})
    assert got["date_from"] == "2026-05-31"
    assert "command" not in got
    assert got["steam"] is False
    src = inspect.getsource(jq._job_mlb_public_rlm_sweep)
    assert "PAUSED_MODELS" not in src
    assert "ACTION_THRESHOLDS" not in src
    assert "scripts.mlb_public_rlm_sweep" in src


def test_the_declared_key_is_present_and_valid():
    entries = json.loads((ROOT / "jobs" / "declared_jobs.json").read_text(
        encoding="utf-8"))
    match = [e for e in entries if e["key"] == DECLARED_KEY]
    assert match, f"declared_jobs.json missing {DECLARED_KEY}"
    job = match[0]
    assert job["job_type"] == "mlb_public_rlm_sweep"
    assert job["requested_by"] == "mike"
    assert "ONE-SHOT" in job["note"]
    _, validate = jq.JOBS["mlb_public_rlm_sweep"]
    cleaned = validate(job.get("args") or {})
    assert cleaned["date_from"] == "2026-05-31"
    assert cleaned["steam"] is True
