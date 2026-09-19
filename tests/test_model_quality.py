"""Model-quality monitor: concentration / fade detectors and job wiring.

The failure this exists for is a model booking a correlated slate — e.g.
`mlb_total_public_fade` writing a card of unders — that ops health never
sees because every feed is fresh. Detectors are pure so the all-unders
case is pinned without a database.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

import tracking.job_queue as jq
import tracking.model_quality as mq
from data.db_setup import SCHEMA_SQL

ROOT = Path(__file__).resolve().parents[1]


class _Shim:
    def __init__(self, path):
        self._c = sqlite3.connect(path)

    def execute(self, sql, params=()):
        return self._c.execute(sql, tuple(params) if params is not None else ())

    def commit(self):
        self._c.commit()

    def rollback(self):
        self._c.rollback()

    def close(self):
        self._c.close()


def _insert_open_bet(c, *, model_id, sport, game_id, pick_side,
                     game_date, public_bet_pct=75.0):
    c.execute("""
        INSERT INTO picks (
            game_id, model_id, sport, game_date, pick_side, pick_label,
            model_probability, dk_implied_prob, edge, kelly_fraction,
            recommended_bet, bankroll_at_pick, signal_type, public_bet_pct
        ) VALUES (?, ?, ?, ?, ?, ?, 0.55, 0.50, 0.05, 0.01, 100, 1000,
                  'BET', ?)
    """, (game_id, model_id, sport, game_date, pick_side,
          f"{pick_side} {game_id}", public_bet_pct))


def _bet(model_id="mlb_total_public_fade", sport="MLB", game_id="g1",
         pick_side="under", public_bet_pct=72.0, recommended_bet=100.0):
    return {
        "model_id": model_id,
        "sport": sport,
        "game_id": game_id,
        "pick_side": pick_side,
        "public_bet_pct": public_bet_pct,
        "public_money_pct": public_bet_pct,
        "recommended_bet": recommended_bet,
        "is_live": False,
    }


def _fade_slate(n=8, side="under", model_id="mlb_total_public_fade",
                sport="MLB"):
    return [
        _bet(model_id=model_id, sport=sport, game_id=f"{sport}_{i}",
             pick_side=side, public_bet_pct=75.0)
        for i in range(n)
    ]


# ── one-sided / concentration ────────────────────────────────────────────────

def test_all_unders_public_fade_slate_is_crit():
    """The case the monitor was asked to catch: fade model, all unders."""
    finding = mq.detect_slate_concentration(_fade_slate(8))
    assert finding is not None
    assert finding["status"] == mq.FLAGGED
    assert finding["severity"] == mq.CRIT
    assert finding["metrics"]["majority_side"] == "under"
    assert finding["metrics"]["share"] == 1.0
    assert finding["metrics"]["n_bets"] == 8
    assert "under" in finding["detail"]


def test_all_unders_public_fade_risk_is_crit():
    finding = mq.detect_public_fade_risk(_fade_slate(8))
    assert finding is not None
    assert finding["status"] == mq.FLAGGED
    assert finding["severity"] == mq.CRIT
    assert finding["metrics"]["fade_style"] is True
    assert finding["metrics"]["majority_side"] == "under"


def test_a_mixed_slate_is_ok():
    picks = (
        _fade_slate(4, side="under", model_id="mlb_over_under")
        + _fade_slate(4, side="over", model_id="mlb_over_under")
    )
    # rewrite game ids so they stay unique
    for i, p in enumerate(picks):
        p["game_id"] = f"MLB_{i}"
        p["public_bet_pct"] = 50.0
    conc = mq.detect_slate_concentration(picks)
    assert conc["status"] == mq.OK
    fade = mq.detect_public_fade_risk(picks)
    assert fade["status"] == mq.OK


def test_all_home_ncaaf_slate_is_flagged_without_mlb_hardcoding():
    picks = _fade_slate(8, side="home", model_id="ncaaf_spread", sport="NCAAF")
    for p in picks:
        p["public_bet_pct"] = 50.0
    finding = mq.detect_slate_concentration(picks)
    assert finding["status"] == mq.FLAGGED
    assert finding["metrics"]["majority_side"] == "home"


def test_thin_slate_is_not_a_finding():
    assert mq.detect_slate_concentration(_fade_slate(3)) is None
    assert mq.detect_public_fade_risk(_fade_slate(3)) is None


def test_unanimous_but_small_slate_is_warn_not_crit():
    """5 unanimous BETs / 5 games: large enough to name, not yet CRIT."""
    finding = mq.detect_slate_concentration(_fade_slate(5))
    assert finding["status"] == mq.FLAGGED
    assert finding["severity"] == mq.WARN


def test_majority_share_warns_when_not_unanimous():
    picks = _fade_slate(7, side="under", model_id="mlb_over_under")
    picks.append(_bet(model_id="mlb_over_under", game_id="MLB_x",
                      pick_side="over", public_bet_pct=50.0))
    finding = mq.detect_slate_concentration(picks)
    assert finding["status"] == mq.FLAGGED
    assert finding["severity"] == mq.WARN
    assert finding["metrics"]["majority_side"] == "under"


def test_side_aliases_collapse_to_the_same_direction():
    picks = [
        _bet(game_id=f"g{i}", pick_side=side)
        for i, side in enumerate(["u", "UNDER", "under", "U", "under"])
    ]
    finding = mq.detect_slate_concentration(picks)
    assert finding["metrics"]["majority_side"] == "under"
    assert finding["metrics"]["share"] == 1.0


# ── public-fade classification ───────────────────────────────────────────────

def test_fade_in_the_model_id_is_sport_agnostic():
    assert mq.is_fade_style_model("mlb_total_public_fade")
    assert mq.is_fade_style_model("nfl_spread_public_fade")
    assert not mq.is_fade_style_model("mlb_over_under")


def test_low_public_pct_on_the_pick_side_counts_as_a_fade():
    pick = _bet(model_id="mlb_over_under", public_bet_pct=28.0)
    assert mq.is_public_fade_pick(pick)


def test_high_public_pct_on_a_fade_publisher_counts_as_a_fade():
    """mlb_total_public_fade stamps the OVER ticket pile, not the under side."""
    pick = _bet(model_id="mlb_total_public_fade", public_bet_pct=78.0)
    assert mq.is_public_fade_pick(pick)


# ── CLV / ROI / volume (synthetic) ───────────────────────────────────────────

def test_clv_clear_negative_vs_baseline_is_flagged():
    recent = [{"clv_method": "no_vig", "clv_pct": -2.5,
               "clv_beat_close": False} for _ in range(20)]
    baseline = [{"clv_method": "no_vig", "clv_pct": 1.0,
                 "clv_beat_close": True} for _ in range(20)]
    finding = mq.detect_clv_degradation(recent, baseline)
    assert finding["status"] == mq.FLAGGED
    assert finding["severity"] == mq.CRIT


def test_raw_one_sided_clv_is_ignored():
    recent = [{"clv_method": "raw_one_sided", "clv_pct": -9.0,
               "clv_beat_close": False} for _ in range(30)]
    assert mq.detect_clv_degradation(recent, recent) is None


def test_roi_collapse_is_crit_when_hit_rate_dies():
    recent = [{"result": "LOSS", "profit_flat": -100.0, "dk_odds": -110}
              for _ in range(25)]
    baseline = [{"result": "WIN", "profit_flat": 91.0, "dk_odds": -110}
                for _ in range(25)]
    finding = mq.detect_roi_collapse(recent, baseline)
    assert finding["status"] == mq.FLAGGED
    assert finding["severity"] == mq.CRIT


def test_roi_ignores_unpriced_profit_flat():
    """profit_flat fabricates -110 when the price is missing (§6)."""
    recent = [{"result": "LOSS", "profit_flat": -100.0, "dk_odds": None}
              for _ in range(25)]
    assert mq.detect_roi_collapse(recent, []) is None


def test_volume_spike_vs_median():
    today = _fade_slate(12, model_id="mlb_moneyline")
    history = [(2, 2.0)] * 10
    finding = mq.detect_volume_spike(today, history)
    assert finding["status"] == mq.FLAGGED
    assert finding["severity"] == mq.CRIT
    assert finding["metrics"]["n_today"] == 12


def test_volume_without_history_is_skipped_not_flagged():
    today = _fade_slate(12, model_id="brand_new_model")
    finding = mq.detect_volume_spike(today, [])
    assert finding["status"] == mq.SKIPPED


# ── job / pipeline wiring ────────────────────────────────────────────────────

def test_model_quality_is_a_registered_job_type():
    assert "model_quality" in jq.JOBS


def test_the_runner_calls_run_model_quality():
    fn, _ = jq.JOBS["model_quality"]
    import inspect
    src = inspect.getsource(fn)
    assert "run_model_quality" in src


def test_no_run_date_means_the_module_resolves_it():
    _, validate = jq.JOBS["model_quality"]
    assert validate({}) == {}
    assert validate({"run_date": None}) == {}
    assert validate({"run_date": ""}) == {}


def test_an_explicit_run_date_must_be_a_real_iso_date():
    _, validate = jq.JOBS["model_quality"]
    assert validate({"run_date": "2026-09-19"}) == {"run_date": "2026-09-19"}
    for bad in ("nope", "2026-13-01", "09/19/2026"):
        with pytest.raises(ValueError):
            validate({"run_date": bad})


def test_the_validator_drops_unknown_args():
    _, validate = jq.JOBS["model_quality"]
    assert validate({"run_date": "2026-09-19", "command": "rm -rf /"}) == {
        "run_date": "2026-09-19"}


def test_declared_bootstrap_job_is_present_and_validates():
    declared = json.loads(
        (ROOT / "jobs" / "declared_jobs.json").read_text(encoding="utf-8"))
    keys = [j["key"] for j in declared if j["job_type"] == "model_quality"]
    assert "model-quality-bootstrap-2026-09-19" in keys
    job = next(j for j in declared if j["key"] == keys[0])
    _, validate = jq.JOBS["model_quality"]
    validate(dict(job.get("args") or {}))


def test_pipeline_step_never_fails_on_crit(monkeypatch):
    import run_pipeline

    def fake(run_date):
        return {"ok": False, "crit": 2, "warn": 1, "results": []}

    monkeypatch.setattr(mq, "run_model_quality", fake)
    monkeypatch.setattr("tracking.model_quality.run_model_quality", fake)
    assert run_pipeline.step_model_quality("2026-09-19") is True


def test_pipeline_step_never_fails_on_exception(monkeypatch):
    import run_pipeline

    def boom(run_date):
        raise RuntimeError("db down")

    monkeypatch.setattr("tracking.model_quality.run_model_quality", boom)
    assert run_pipeline.step_model_quality("2026-09-19") is True


def test_dispatch_table_and_daily_both_call_the_step():
    src = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
    table = src[src.index("step_fns = {"):src.index("success = _timed_step")]
    assert '"model-quality":' in table
    assert "step_model_quality(run_date)" in table
    daily = [ln for ln in src.splitlines() if 'results["model_quality"]' in ln]
    assert daily == [
        '    results["model_quality"] = step_model_quality(run_date)'
    ]


def test_scheduler_registers_the_11am_job():
    src = (ROOT / "scheduler.py").read_text(encoding="utf-8")
    assert 'id="model_quality"' in src
    assert "run_model_quality_job" in src
    assert "hour=11" in src
    assert "RUN_MODEL_QUALITY" in src


def test_nothing_autopauses():
    src = (ROOT / "tracking" / "model_quality.py").read_text(encoding="utf-8")
    assert "PAUSED_MODELS" not in src
    assert "model_auto_pauses" not in src


def test_run_persists_all_unders_fade_slate_as_crit(monkeypatch):
    """End-to-end on SQLite: the fade all-unders card lands FLAGGED/CRIT."""
    path = tempfile.mktemp(suffix=".db")
    raw = sqlite3.connect(path)
    raw.executescript(SCHEMA_SQL)
    for i in range(8):
        _insert_open_bet(
            raw, model_id="mlb_total_public_fade", sport="MLB",
            game_id=f"MLB_2026-09-19_T{i}_T{i+1}",
            pick_side="under", game_date="2026-09-19",
            public_bet_pct=74.0,
        )
    raw.commit()
    raw.close()
    monkeypatch.setattr(mq, "get_connection", lambda: _Shim(path))
    out = mq.run_model_quality("2026-09-19")
    by_check = {
        (r["check_name"], r["model_key"]): r
        for r in out["results"]
    }
    conc = by_check[(mq.SLATE_CONCENTRATION, "mlb_total_public_fade")]
    fade = by_check[(mq.PUBLIC_FADE_RISK, "mlb_total_public_fade")]
    assert conc["status"] == mq.FLAGGED and conc["severity"] == mq.CRIT
    assert fade["status"] == mq.FLAGGED and fade["severity"] == mq.CRIT
    assert out["crit"] >= 2
    persisted = _Shim(path).execute("""
        SELECT status, severity FROM model_quality_checks
        WHERE run_date = '2026-09-19'
          AND model_key = 'mlb_total_public_fade'
          AND check_name = 'slate_concentration'
    """).fetchone()
    assert persisted == (mq.FLAGGED, mq.CRIT)


def test_meta_steps_exclude_model_quality():
    """A future refresh-pass wiring must not loop the way health-check did."""
    import re
    health = (ROOT / "tracking" / "system_health.py").read_text(encoding="utf-8")
    m = re.search(r"_META_STEPS = \{([^}]*)\}", health)
    assert m
    names = set(re.findall(r'"([^"]+)"', m.group(1)))
    assert "model-quality" in names
