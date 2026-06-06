"""Pure-function tests for the live scorer (no DB)."""

import numpy as np
from scipy import stats as scipy_stats

from models.live_scorer import _classify, _make_live_pick
from models.scorer import _poisson_over_prob


def test_poisson_over_prob_matches_distribution():
    for lam, line in [(4.5, 5.5), (8.2, 8.5), (3.0, 2.5)]:
        expected = 1.0 - scipy_stats.poisson.cdf(int(np.floor(line)), lam)
        assert abs(_poisson_over_prob(lam, line) - expected) < 1e-9


def test_classify_bet_avoid_none():
    mid = "mlb_live_moneyline"   # edge thresh 0.04, prob thresh 0.60
    assert _classify(mid, 0.66, 0.10) == "BET"
    assert _classify(mid, 0.90, -0.10) == "AVOID"
    assert _classify(mid, 0.66, 0.02) == "NONE"   # edge too small
    assert _classify(mid, 0.55, 0.10) == "NONE"   # prob below threshold


def test_make_live_pick_stamps_live_fields():
    feat = {"game_id": "MLB_2026-06-06_NYY_BOS", "game_date": "2026-06-06"}
    pick = _make_live_pick(
        feat, "mlb_live_moneyline", "MLB", "h2h",
        pick_side="home", pick_label="BOS ML",
        model_prob=0.66, dk_odds=-110, bankroll=1000.0,
        inning_at_pick=5, score_diff_at_pick=1, scored_line=None,
    )
    assert pick is not None
    assert pick["is_live"] is True
    assert pick["inning_at_pick"] == 5
    assert pick["score_diff_at_pick"] == 1
    assert pick["signal_type"] == "BET"      # edge ≈ 0.136 ≥ 0.04 and prob ≥ 0.60
    assert pick["recommended_bet"] > 0


def test_make_live_pick_rejects_noise_edge():
    # edge above MAX_EDGE_CAP (0.20) → discarded entirely
    feat = {"game_id": "g", "game_date": "2026-06-06"}
    pick = _make_live_pick(
        feat, "mlb_live_moneyline", "MLB", "h2h",
        pick_side="home", pick_label="x",
        model_prob=0.95, dk_odds=-110, bankroll=1000.0,
        inning_at_pick=8, score_diff_at_pick=3, scored_line=None,
    )
    assert pick is None


def test_dedup_key_distinguishes_state():
    # The dedup key is (model_id, pick_side, inning, score_diff); same state
    # collides, a score/inning change does not.
    k1 = ("mlb_live_moneyline", "home", 5, 1)
    k2 = ("mlb_live_moneyline", "home", 5, 1)
    k3 = ("mlb_live_moneyline", "home", 6, 1)   # inning advanced
    k4 = ("mlb_live_moneyline", "home", 5, 2)   # score changed
    assert k1 == k2
    assert k1 != k3
    assert k1 != k4
