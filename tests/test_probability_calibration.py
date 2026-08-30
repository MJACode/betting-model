"""The calibration layer: the parts that must not quietly go wrong.

Most of these pin REFUSALS. Publishing a map that does not hold is worse than
publishing none, because it trades a known bias for an unknown one — so the
module is built to decline, and these tests are what keep it declining.
"""
from __future__ import annotations

import numpy as np
import pytest

from models import probability_calibration as pc
from models.trainer import (_calibration_error_weighted, _mean_calibration_error,
                            calibration_metrics, poisson_probability_metrics)


# ── the map itself ───────────────────────────────────────────────────────────

def test_identity_when_there_is_no_map():
    for params in (None, {}, {"method": "unfitted"}):
        assert pc.apply_calibration(0.73, params) == 0.73


def test_the_map_is_symmetric_so_two_sides_still_sum_to_one():
    """Fitted on the preferred side only. Without the mirror, a prop's over and
    under would be two probabilities for one proposition that disagree."""
    params = {"method": "platt", "a": 0.8, "b": -0.4}
    for p in (0.55, 0.62, 0.7, 0.85, 0.95):
        assert pc.apply_calibration(p, params) + pc.apply_calibration(1 - p, params) \
            == pytest.approx(1.0, abs=1e-9)


def test_the_map_is_monotone():
    """A higher claim must not map below a lower one, or ranking breaks."""
    params = {"method": "platt", "a": 0.7, "b": -0.5}
    vals = [pc.apply_calibration(p, params) for p in np.linspace(0.5, 0.99, 40)]
    assert all(b >= a - 1e-12 for a, b in zip(vals, vals[1:]))


def test_platt_recovers_a_known_overconfidence():
    """A model claiming 0.75 that wins 0.60 must map ~0.75 -> ~0.60."""
    rng = np.random.RandomState(0)
    probs = list(np.full(4000, 0.75))
    wins = list(rng.binomial(1, 0.60, 4000))
    a, b = pc.fit_platt(probs, wins)
    assert pc.apply_calibration(0.75, {"method": "platt", "a": a, "b": b}) \
        == pytest.approx(0.60, abs=0.03)


def test_a_map_can_move_a_probability_upward():
    """batter_rbi claims 68.6% and wins 74.7%. Calibration is not a haircut."""
    rng = np.random.RandomState(1)
    probs = list(np.full(4000, 0.686))
    wins = list(rng.binomial(1, 0.747, 4000))
    a, b = pc.fit_platt(probs, wins)
    assert pc.apply_calibration(0.686, {"method": "platt", "a": a, "b": b}) > 0.70


# ── the refusals ─────────────────────────────────────────────────────────────

class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params=None):
        self._last = sql
        return self

    def fetchall(self):
        return self._rows


def test_a_model_with_too_few_graded_picks_is_not_fitted():
    conn = _FakeConn([(0.7, "WIN")] * (pc.MIN_GRADED - 1))
    rep = pc.fit_model(conn, "mlb_moneyline", "2026-04-14")
    assert rep["method"] is None and "identity map" in rep["note"]


def test_prob_only_models_are_never_fitted():
    """Their probability is the whole signal and is never compared to a price."""
    conn = _FakeConn([(0.7, "WIN")] * 500)
    rep = pc.fit_model(conn, "mlb_prop_batter_hr", "2026-04-14")
    assert rep["method"] is None and "prob-only" in rep["note"]


def test_a_map_that_does_not_help_out_of_sample_is_not_applied():
    """The gate that keeps mlb_moneyline unmapped: its map made the held-out
    half WORSE (5.2pp raw -> 7.2pp calibrated), so it must not ship."""
    rng = np.random.RandomState(3)
    # First half badly overconfident, second half honest — nothing stable to map.
    rows = ([(0.75, "WIN" if w else "LOSS") for w in rng.binomial(1, 0.50, 300)]
            + [(0.75, "WIN" if w else "LOSS") for w in rng.binomial(1, 0.75, 300)])
    rep = pc.fit_model(_FakeConn(rows), "mlb_moneyline", "2026-04-14")
    assert rep["method"] == "platt", "it should still FIT, so the numbers are visible"
    assert rep["applied"] is False
    assert "DOES NOT HELP" in rep["note"]


def test_a_map_that_helps_is_applied():
    rng = np.random.RandomState(4)
    rows = [(0.75, "WIN" if w else "LOSS") for w in rng.binomial(1, 0.60, 600)]
    rep = pc.fit_model(_FakeConn(rows), "mlb_prop_pitcher_k", "2026-04-14")
    assert rep["applied"] is True and rep["helps"] is True


def test_the_fit_window_starts_at_the_active_version_not_paper_start():
    """A map fitted across a version swap describes a blend of the live model
    and its dead predecessor — it moved batter_tb from +4.6pp to +1.2pp."""
    assert pc._era_start("mlb_prop_batter_tb", "2026-06-21") == "2026-06-21"


def test_documented_contamination_windows_are_excluded():
    """mlb_over_under's NaN-line era and mlb_runline's frozen-bullpen era are
    not the model talking, so they must not be fitted as if they were."""
    assert pc._era_start("mlb_over_under", "2026-04-14") == "2026-07-05"
    assert pc._era_start("mlb_runline", "2026-04-14") == "2026-07-05"
    # A later retrain still wins over the repair date.
    assert pc._era_start("mlb_runline", "2026-08-23") == "2026-08-23"


def test_the_lockdown_names_the_roles_rather_than_public():
    joined = " ".join(pc.LOCKDOWN)
    assert "FROM anon" in joined and "FROM authenticated" in joined
    assert "FROM PUBLIC" not in joined


# ── the go-live gate ─────────────────────────────────────────────────────────

def test_the_actionable_metric_sees_what_the_legacy_one_dilutes():
    """A model 10pp off in a small high-confidence bin, well calibrated in a
    large one near 0.5 — which is every model measured on 2026-08-30."""
    y_prob = np.concatenate([np.full(5000, 0.50), np.full(400, 0.75)])
    y_true = np.concatenate([np.full(2500, 1.0), np.full(2500, 0.0),
                             np.full(260, 1.0), np.full(140, 0.0)])
    weighted = _calibration_error_weighted(y_true, y_prob)
    actionable = _calibration_error_weighted(y_true, y_prob, min_prob=0.72)
    assert weighted < 0.02, "the big honest bin drowns the error out"
    assert actionable == pytest.approx(0.10, abs=0.01), "the real error, undiluted"


def test_the_legacy_metric_is_unchanged():
    """Every historical model_registry.calibration_score was measured with it;
    redefining it in place would silently change what those rows mean."""
    y_prob = np.concatenate([np.full(100, 0.5), np.full(100, 0.8)])
    y_true = np.concatenate([np.full(50, 1.0), np.full(50, 0.0),
                             np.full(80, 1.0), np.full(20, 0.0)])
    # unweighted mean of |0.5-0.5| and |0.8-0.8| = 0
    assert _mean_calibration_error(y_true, y_prob) == pytest.approx(0.0, abs=1e-9)


def test_calibration_metrics_uses_the_models_own_threshold_as_the_floor():
    import config
    y_prob = np.full(400, 0.9)
    y_true = np.full(400, 1.0)
    out = calibration_metrics("mlb_moneyline", y_true, y_prob)
    assert out["cal_floor"] == config.MODEL_PROB_THRESHOLDS["mlb_moneyline"]
    assert set(out) >= {"cal_error", "cal_error_weighted", "cal_error_actionable"}


def test_the_poisson_gate_measures_the_probability_not_the_count_fit():
    """The defect it exists for: a Poisson model's COUNT fit can be excellent
    while the probability it bets — the tail at the live line — is 10pp off.
    That layer was never evaluated at training time."""
    rng = np.random.RandomState(0)
    mu = rng.uniform(1, 8, 3000)
    honest = poisson_probability_metrics(
        "mlb_live_total_runs", rng.poisson(mu).astype(float), mu)
    overdispersed = poisson_probability_metrics(
        "mlb_live_total_runs",
        rng.negative_binomial(3, 3 / (3 + mu)).astype(float), mu)
    assert honest["prob_cal_error_actionable"] < 0.02
    assert overdispersed["prob_cal_error_actionable"] > 0.05, (
        "an overdispersed reality priced with a Poisson tail must fail the gate")


def test_the_poisson_gate_reports_the_models_own_floor():
    rng = np.random.RandomState(0)
    mu = rng.uniform(1, 8, 800)
    out = poisson_probability_metrics("mlb_live_total_runs",
                                      rng.poisson(mu).astype(float), mu)
    assert out["prob_cal_floor"] == pytest.approx(0.70)


# ── stamping ─────────────────────────────────────────────────────────────────

def test_stamping_never_raises_and_falls_back_to_the_raw_number():
    """A calibration failure must not be able to stop a pick being written."""
    from models.scorer import _calibrated
    assert _calibrated(None, 0.7) is None
    assert _calibrated("mlb_moneyline", None) is None
    assert _calibrated("a-model-that-does-not-exist", 0.66) == 0.66


def test_the_decision_path_never_reads_the_calibrated_number():
    """PHASE 1 is display-only. Every threshold in config.py was swept on RAW
    probabilities; applying the map to the decision without re-cutting would
    take mlb_moneyline from ~2 picks a week to none."""
    from pathlib import Path
    src = (Path(__file__).parent.parent / "models/scorer.py").read_text(encoding="utf-8")
    body = src[src.index("def _make_pick"):src.index("def _insert_picks")]
    assert "model_probability_cal" not in body, (
        "the signal/edge/Kelly path must not see the calibrated probability")


def test_applied_is_a_column_not_a_json_substring_match():
    """The LIKE this replaced was a live bug, not a style point.

    data.db passes params through psycopg2 whenever they are not None, and an
    empty tuple counts — so a literal % in the SQL becomes a format placeholder,
    the query raises, and monitoring/store._rows swallows it and returns [].
    The dashboard silently reported every model as unmapped.
    """
    assert "applied" in pc.DDL and "BOOLEAN" in pc.DDL
    import inspect
    src = inspect.getsource(pc.load_calibrations)
    # The column name is now interpolated (promoted vs applied), so assert on
    # the absence of the pattern that broke rather than an exact literal.
    assert "LIKE" not in src
    assert "promoted" in src and "applied" in src

    from monitoring import store
    store_src = inspect.getsource(store.model_calibration)
    assert "LIKE" not in store_src, (
        "a % literal in a store query is swallowed by _rows and returns []")


def test_the_daily_fit_writes_a_candidate_and_never_moves_a_live_cut():
    """Phase 2 makes the map a DECISION input, so a nightly refit would be a
    model update on a cron — a section 1b violation built into the pipeline.
    The scorer reads `promoted`; the fit writes `applied`; moving one to the
    other is a deliberate act."""
    import inspect
    persist_src = inspect.getsource(pc.persist)
    assert "promoted" not in persist_src.split("ON CONFLICT")[1].split("promoted_a")[0]         or "DELIBERATELY not updated" in persist_src, (
        "the daily upsert must not touch the promoted columns")
    load_src = inspect.getsource(pc.load_calibrations)
    assert 'promoted_only: bool = True' in load_src, (
        "the scorer's default must be the promoted map, not today's candidate")


def test_promote_refuses_a_map_the_fit_did_not_endorse():
    src = __import__("inspect").getsource(pc.promote)
    assert "WHERE applied" in src, (
        "a map that made the held-out half worse must not be promotable by hand")


def test_the_inverse_map_round_trips():
    """A cut chosen in calibrated space has an exact raw-space equivalent, which
    is what let the swept cuts ship before the decision flip did."""
    params = {"method": "platt", "a": 0.76, "b": 0.47}
    for v in (0.52, 0.60, 0.75, 0.90):
        assert pc.invert_calibration(pc.apply_calibration(v, params), params)             == pytest.approx(v, abs=1e-9)
    # identity when there is no map
    assert pc.invert_calibration(0.66, None) == 0.66
