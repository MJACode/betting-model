"""Config and platform wiring for the in-play leader moneyline (config.py,
scheduler.py, the settlement and honest-probability paths).

The backtest the model went live on had NO price floor, NO EV floor and no
probability floor -- only the 0.02 edge. Every platform default that would
change that population is pinned here to not bind:
  * DEFAULT_MIN_ODDS (-200) would have cut the 167 bets to 67;
  * GLOBAL_MIN_EV (0.20) would have cut them to 69;
  * the promoted calibration map would replace the model's own probability.
conftest holds GLOBAL_MIN_EV at -1.0 for every test, so the floor tests here
put the LIVE number back (as tests/test_config.py does) or they prove nothing.
"""

from __future__ import annotations

import os

import pytest

import config
from nfl_live_leader import model as M

MID = "nfl_live_leader_ml"


def test_the_cut_is_the_backtests_and_matches_the_artifact():
    assert config.ACTION_THRESHOLDS[MID] == {"min_prob": 0.0, "min_edge": 0.02}
    assert config.MODEL_EDGE_THRESHOLDS[MID] == 0.02
    assert config.MODEL_PROB_THRESHOLDS[MID] == 0.0
    assert M.load_artifact().rule["edge_cut"] == config.ACTION_THRESHOLDS[MID]["min_edge"]


def test_the_action_threshold_key_is_on_one_line():
    """data.threshold_sync and the generated mobile/SQL mirrors read config;
    a reviewer greps for the key."""
    src = (config.ROOT / "config.py").read_text(encoding="utf-8")
    assert f'    "{MID}": {{"min_prob": 0.0, "min_edge": 0.02}},' in src


def test_the_ev_floor_cannot_bind_with_the_live_global_floor(monkeypatch):
    monkeypatch.setattr(config, "GLOBAL_MIN_EV", float(os.environ.get("GLOBAL_MIN_EV", "0.20")))
    assert config.min_ev_for(MID) == 0.02
    assert MID not in config.MODEL_MIN_EV
    # EV = edge x decimal >= edge for decimal >= 1, so edge >= 0.02 => EV >= 0.02.
    for american in (-4000, -1000, -500, -330, -200, -110, 100, 180):
        dec = float(M.am_to_dec(american))
        implied = 1 / dec
        ev = config.expected_value(implied + 0.02, american)
        assert ev >= config.min_ev_for(MID) - 1e-12, (american, ev)


def test_the_price_floor_is_minus_140():
    """mike, 2026-10-15 ET: "Floor is -140 for this model" (after a -980 bet)."""
    assert config.MODEL_MIN_ODDS[MID] == -140
    assert config.min_odds_for(MID) == -140


def test_the_loop_refuses_a_price_shorter_than_the_floor():
    """The gate the live loop consults after the rule says BET: -150 and
    -980 are refused (the game stays open and is tried again at its next
    slot), -140 and plus money pass."""
    from types import SimpleNamespace

    from nfl_live_leader import gameday as G

    for price in (-150, -980, -4000):
        why = G.platform_gates(SimpleNamespace(price=price, wp=0.99))
        assert why and "under the floor" in why, (price, why)
    for price in (-140, -110, 150):
        assert G.platform_gates(SimpleNamespace(price=price, wp=0.99)) is None, price


def test_it_decides_on_its_own_probability():
    from models.honest_ev import honest_probability

    assert MID in config.MODELS_ON_OWN_PROBABILITY
    for p in (0.55, 0.8, 0.97):
        assert honest_probability(MID, p) == p


def test_it_is_a_live_engine_model_that_settles_as_a_moneyline():
    from tracking.paper_tracker import _market_for_pick

    assert config.LIVE_MODELS[MID][:3] == ("NFL", "h2h", "engine")
    assert config.scoring_method(MID) == "engine"
    assert _market_for_pick(MID) == "h2h"
    assert MID not in config.RETIRED_MODELS and MID not in config.PAUSED_MODELS


def test_the_mlb_live_scorer_skips_it():
    """models/live_scorer.py iterates LIVE_MODELS and loads registry artifacts;
    an 'engine' entry must be skipped there or every MLB pass logs a miss."""
    src = (config.ROOT / "models" / "live_scorer.py").read_text(encoding="utf-8")
    assert 'if spec[2] == "engine":' in src


def test_the_scheduler_runs_the_loop_on_the_poller(monkeypatch):
    import importlib

    import scheduler

    importlib.reload(scheduler)
    assert scheduler.RUN_NFL_LIVE_LEADER is True                  # default ON
    assert "nfl_live_leader" in scheduler._POLLER_JOBS
    assert scheduler.RUN_NFL_LIVE is False                        # the retired worker stays off
    src = (config.ROOT / "scheduler.py").read_text(encoding="utf-8")
    assert '[sys.executable, "-m", "nfl_live_leader.gameday"]' in src
    assert 'id="nfl_live_leader"' in src

    from tracking.job_heartbeat import MAX_SILENCE
    assert MAX_SILENCE["nfl_live_leader"] >= 600        # clears the midnight-9am gap


def test_the_scheduler_flag_turns_it_off(monkeypatch):
    import importlib

    import scheduler

    # Any of the ways a person types "off" turns it off; only those do.
    for off in ("0", "false", "False", " off ", "NO"):
        monkeypatch.setenv("RUN_NFL_LIVE_LEADER", off)
        importlib.reload(scheduler)
        assert scheduler.RUN_NFL_LIVE_LEADER is False, off
    for on in ("1", "true", "yes"):
        monkeypatch.setenv("RUN_NFL_LIVE_LEADER", on)
        importlib.reload(scheduler)
        assert scheduler.RUN_NFL_LIVE_LEADER is True, on
    monkeypatch.delenv("RUN_NFL_LIVE_LEADER")
    importlib.reload(scheduler)


def test_a_loop_that_dies_fails_its_job(monkeypatch):
    """_run reports a crash as a return value. The job must raise on it, or a
    loop that dies on every launch reads as a healthy heartbeat."""
    import pytest

    import scheduler

    for outcome in ("fail", "timeout", "error"):
        monkeypatch.setattr(scheduler, "_run", lambda *a, **k: outcome)
        with pytest.raises(RuntimeError):
            scheduler.run_nfl_live_leader()
    monkeypatch.setattr(scheduler, "_run", lambda *a, **k: "ok")
    scheduler.run_nfl_live_leader()


def test_the_job_is_registered_once_with_its_cron(monkeypatch):
    import scheduler
    from tracking import job_heartbeat as jh

    # build_scheduler seeds a heartbeat row per watched job; on a machine with
    # a .env that is a production write, so it is stubbed out here.
    for fn in ("seed", "beat", "mark_disabled"):
        monkeypatch.setattr(jh, fn, lambda *a, **k: None)
    sched = scheduler.build_scheduler()
    jobs = {j.id: j for j in sched.get_jobs()}
    assert "nfl_live_leader" in jobs
    job = jobs["nfl_live_leader"]
    assert job.max_instances == 1
    trig = str(job.trigger)
    assert "hour='9-23'" in trig and "minute='*/10'" in trig, trig
