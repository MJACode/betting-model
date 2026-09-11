"""The cut sweep's decision rule IS production's decision rule.

scripts/live_cut_sweep.decide re-implements classify_live_signal's arithmetic
with the thresholds as parameters, because the sweep has to vary them. A
re-implementation that drifts from the original produces a table about a rule
nobody runs -- CLAUDE.md 7's "same understanding, same blind spot". This pins
the two together on a grid of (prob, odds) that straddles every boundary:
the 0.20 cap, the prob floor, the edge floor and the EV floor.
"""

import itertools

import pytest

from models import live_scorer as ls
from scripts.live_cut_sweep import decide

MODEL = "mlb_live_total_runs"
PROBS = [0.55, 0.69, 0.70, 0.715, 0.72, 0.74, 0.76, 0.80, 0.90]
ODDS = [-160, -145, -130, -118, -110, -105, 100, 110, 130]
CUTS = [(0.70, 0.14, 0.32), (0.72, 0.14, 0.32), (0.74, 0.16, 0.36)]


@pytest.mark.parametrize("min_prob,min_edge,min_ev", CUTS)
def test_decide_agrees_with_classify_live_signal(monkeypatch, min_prob, min_edge, min_ev):
    monkeypatch.setitem(ls.MODEL_PROB_THRESHOLDS, MODEL, min_prob)
    monkeypatch.setitem(ls.MODEL_EDGE_THRESHOLDS, MODEL, min_edge)
    monkeypatch.setitem(ls.MODEL_MIN_EV, MODEL, min_ev)
    monkeypatch.setattr(ls, "_calibrated", lambda model_id, p: None)  # no map

    for prob, odds in itertools.product(PROBS, ODDS):
        implied = ls.american_to_implied_prob(odds)
        edge = prob - implied
        cand = {"prob": prob, "odds": float(odds), "edge": edge,
                "ev": ls.expected_value(prob, odds), "side": "over",
                "line": 8.5, "inning": 5, "snapshot_at": "t"}
        prod = ls.classify_live_signal(MODEL, prob, edge, odds) == "BET"
        mine = decide([cand], min_prob, min_edge, min_ev) is not None
        assert prod == mine, (
            f"prob={prob} odds={odds} edge={edge:+.3f}: production "
            f"{'BET' if prod else 'no'}, sweep {'BET' if mine else 'no'}")


def test_first_signal_lock_takes_the_earliest_qualifier():
    """One bet per game, the first that qualifies -- the sweep must not pick
    the best one, because production cannot see the future."""
    weak = {"prob": 0.705, "odds": -110.0, "edge": 0.181, "ev": 0.34, "side": "over",
            "line": 8.5, "inning": 3, "snapshot_at": "t1"}
    strong = {"prob": 0.78, "odds": -110.0, "edge": 0.256, "ev": 0.49, "side": "under",
              "line": 8.5, "inning": 7, "snapshot_at": "t2"}
    fine = {"prob": 0.76, "odds": -130.0, "edge": 0.195, "ev": 0.34, "side": "under",
            "line": 8.5, "inning": 8, "snapshot_at": "t3"}
    assert decide([weak, strong, fine], 0.70, 0.14, 0.32) is weak
    # `strong` is over the 0.20 cap and must be skipped, not taken
    assert decide([strong, fine], 0.70, 0.14, 0.32) is fine


def test_decide_caps_on_the_raw_edge_when_a_map_is_promoted(monkeypatch):
    """classify_live_signal caps BEFORE it maps; a recalibrated candidate must
    be capped on its raw edge, not the calibrated one."""
    from models.probability_calibration import apply_calibration
    params = {"method": "platt", "a": 0.8578, "b": -0.0787}   # the 2025 map
    monkeypatch.setitem(ls.MODEL_PROB_THRESHOLDS, MODEL, 0.62)
    monkeypatch.setitem(ls.MODEL_EDGE_THRESHOLDS, MODEL, 0.10)
    monkeypatch.setitem(ls.MODEL_MIN_EV, MODEL, 0.15)
    monkeypatch.setattr(ls, "_calibrated", lambda model_id, p: apply_calibration(p, params))
    monkeypatch.setattr(ls, "DECIDE_ON_CALIBRATED_PROB", True)

    for prob, odds in itertools.product(PROBS + [0.84, 0.88], ODDS + [-200, 150]):
        implied = ls.american_to_implied_prob(odds)
        raw_edge = prob - implied
        cal = apply_calibration(prob, params)
        cand = {"prob": cal, "odds": float(odds), "edge": cal - implied,
                "ev": ls.expected_value(cal, odds), "raw_edge": raw_edge, "raw_prob": prob,
                "side": "over", "line": 8.5, "inning": 5, "snapshot_at": "t"}
        prod = ls.classify_live_signal(MODEL, prob, raw_edge, odds) == "BET"
        mine = decide([cand], 0.62, 0.10, 0.15) is not None
        assert prod == mine, f"prob={prob} odds={odds} raw_edge={raw_edge:+.3f} cal={cal:.3f}"
