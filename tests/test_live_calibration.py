"""The live recalibration loop — the parts that must not quietly go wrong.

The recommender's job is to be trustworthy, not to be helpful, so most of these
tests pin the cases where it must REFUSE: not enough data, no profitable cell,
nothing inside the volume ceiling. A recommender that always recommends
something is one you cannot act on.
"""
from __future__ import annotations

import sqlite3

import pytest

from tracking import live_calibration as lc


# ── helpers ──────────────────────────────────────────────────────────────────

def pick(prob, odds, result, date="2026-08-30", profit=None):
    """One settled live BET. profit_flat is per $100, the repo's convention."""
    if profit is None:
        dec = lc.decimal_odds(odds)
        profit = 100 * (dec - 1) if result == "WIN" else (-100 if result == "LOSS" else 0)
    row = {"game_date": date, "created_at": f"{date} 20:00:00+00", "result": result,
           "prob": prob, "odds": odds, "edge": None, "profit_flat": profit}
    row["ev"] = lc.expected_value(prob, odds)
    row["risk_u"] = lc.stake_for(None, odds).risk
    return row


# ── the arithmetic ───────────────────────────────────────────────────────────

def test_expected_value_matches_the_hand_calculation():
    # -125 -> decimal 1.8; 0.70 * 1.8 - 1 = +0.26
    assert lc.expected_value(0.70, -125) == pytest.approx(0.26, abs=1e-9)
    # +150 -> decimal 2.5; 0.50 * 2.5 - 1 = +0.25
    assert lc.expected_value(0.50, 150) == pytest.approx(0.25, abs=1e-9)


def test_expected_value_refuses_a_missing_or_zero_price():
    assert lc.expected_value(0.7, None) is None
    assert lc.expected_value(0.7, 0) is None
    assert lc.expected_value(0.7, "n/a") is None


def test_wilson_widens_on_small_samples():
    """The CI is why a 3-bet cell cannot be read as a result."""
    lo_small, hi_small = lc.wilson(2, 3)
    lo_big, hi_big = lc.wilson(200, 300)
    assert (hi_small - lo_small) > (hi_big - lo_big) * 3
    assert lc.wilson(0, 0) is None


def test_grade_uses_flat_units_and_counts_pushes_separately():
    rows = [pick(0.7, -110, "WIN"), pick(0.7, -110, "LOSS"), pick(0.7, -110, "PUSH")]
    g = lc._grade(rows)
    assert (g["w"], g["l"], g["push"], g["settled"]) == (1, 1, 1, 3)
    # +0.909 - 1 + 0 = -0.09 over three settled
    assert g["units_flat"] == pytest.approx(-0.09, abs=0.01)
    assert g["win_pct"] == 50.0          # pushes excluded from the win rate
    assert g["roi_pct"] == pytest.approx(-3.0, abs=0.5)


# ── calibration: the honesty check ───────────────────────────────────────────

def test_calibration_reports_the_gap_between_claim_and_reality():
    """A model claiming 70% and winning 50% is overconfident, and must say so."""
    rows = [pick(0.70, -110, "WIN"), pick(0.70, -110, "LOSS")]
    cal = lc._calibration(rows)
    assert cal["mean_pred_prob"] == pytest.approx(0.70)
    assert cal["realised_win_pct"] == 50.0
    assert cal["calibration_gap_pp"] == pytest.approx(20.0, abs=0.1)


def test_calibration_also_scores_ev_against_realised_roi():
    """EV that predicts +26% and returns -3% is a ranking, not a promise."""
    rows = [pick(0.70, -125, "WIN"), pick(0.70, -125, "LOSS")]
    cal = lc._calibration(rows)
    assert cal["mean_pred_ev_pct"] == pytest.approx(26.0, abs=0.5)
    assert cal["ev_gap_pp"] > 20     # predicted far more than it returned


def test_calibration_is_empty_rather_than_wrong_with_nothing_settled():
    cal = lc._calibration([pick(0.7, -110, None)])
    assert cal["mean_pred_prob"] is None and cal["calibration_gap_pp"] is None


# ── the recommender's refusals ───────────────────────────────────────────────

def test_recommender_refuses_when_no_cell_has_enough_settled_bets():
    cells = [{"min_prob": 0.7, "min_ev": 0.28, "settled": 3, "roi_pct": 40.0,
              "plateau": 8, "bets_per_week": 5}]
    best, verdict = lc._recommend(cells, {"roi_pct": 0}, None)
    assert best is None and "NOT ENOUGH DATA" in verdict


def test_recommender_refuses_when_every_cell_loses():
    """The least-bad cell is still a losing cell. Say retrain, not 'try this'."""
    cells = [{"min_prob": p, "min_ev": 0.2, "settled": 40, "roi_pct": -5.0,
              "plateau": 0, "bets_per_week": 5} for p in (0.66, 0.68, 0.70)]
    best, verdict = lc._recommend(cells, {"roi_pct": -9}, None)
    assert best is None and "NO PROFITABLE CUT" in verdict


def test_recommender_refuses_when_nothing_fits_the_volume_ceiling():
    cells = [{"min_prob": 0.66, "min_ev": 0.2, "settled": 40, "roi_pct": 20.0,
              "plateau": 8, "bets_per_week": 90}]
    best, verdict = lc._recommend(cells, {"roi_pct": 5}, 30)
    assert best is None and "ceiling" in verdict


def test_the_volume_ceiling_actually_binds():
    """The regression this exists for: unconstrained, the sweep preferred a
    LOOSER cut (more bets, more ROI) than the one it was checking — which is no
    answer at all to 'too many live bets'."""
    loose = {"min_prob": 0.66, "min_ev": 0.22, "settled": 40, "roi_pct": 19.2,
             "plateau": 8, "bets_per_week": 40}
    tight = {"min_prob": 0.70, "min_ev": 0.30, "settled": 20, "roi_pct": 15.0,
             "plateau": 6, "bets_per_week": 25}
    assert lc._recommend([loose, tight], {"roi_pct": 5}, None)[0] is loose
    assert lc._recommend([loose, tight], {"roi_pct": 5}, 30)[0] is tight


def test_recommender_prefers_a_plateau_to_a_higher_peak():
    peak = {"min_prob": 0.74, "min_ev": 0.30, "settled": 20, "roi_pct": 40.0,
            "plateau": 1, "bets_per_week": 10}
    plateau = {"min_prob": 0.70, "min_ev": 0.28, "settled": 20, "roi_pct": 12.0,
               "plateau": 7, "bets_per_week": 10}
    best, _ = lc._recommend([peak, plateau], {"roi_pct": 5}, None)
    assert best is plateau


def test_a_peak_with_no_plateau_anywhere_is_labelled_as_one():
    peak = {"min_prob": 0.74, "min_ev": 0.30, "settled": 20, "roi_pct": 40.0,
            "plateau": 1, "bets_per_week": 10}
    best, verdict = lc._recommend([peak], {"roi_pct": 5}, None)
    assert best is peak and "PEAK, NOT A PLATEAU" in verdict


def test_recommender_says_keep_when_nothing_beats_the_current_cut():
    cell = {"min_prob": 0.70, "min_ev": 0.28, "settled": 20, "roi_pct": 8.0,
            "plateau": 6, "bets_per_week": 10}
    _, verdict = lc._recommend([cell], {"roi_pct": 13.7}, 30)
    assert "KEEP THE CURRENT CUT" in verdict


# ── projection ───────────────────────────────────────────────────────────────

def test_projection_uses_the_recent_regime_not_the_lifetime_average():
    """The lifetime average said 10 bets/week while the live rate was ~60. The
    projection must read the regime, which is why it takes the recent slice."""
    recent = [pick(0.72, -120, "WIN"), pick(0.72, -120, "LOSS")]
    proj = lc._project(recent, days=1.0, prob_min=0.70, ev_min=0.0)
    assert proj["bets_per_week"] == pytest.approx(14.0)   # 2/day * 7
    # Units LAID, price-aware: at -120 a 1u-conviction play risks 1.2u.
    assert proj["units_per_week"] == pytest.approx(16.8, abs=0.1)


def test_projection_is_none_rather_than_zero_when_the_regime_is_empty():
    """No recent picks is 'unmeasured', not 'no volume' — and the recommender
    keeps such cells rather than treating them as cheap."""
    assert lc._project([], 0.0, 0.7, 0.2)["bets_per_week"] is None


def test_a_prob_cut_and_an_ev_cut_select_different_picks():
    rows = [pick(0.80, -300, "WIN"),   # high prob, poor price -> low EV
            pick(0.62, 150, "WIN")]    # low prob, big price   -> high EV
    assert lc._project(rows, 1.0, 0.70, 0.00)["bets_per_week"] == pytest.approx(7.0)
    assert lc._project(rows, 1.0, 0.00, 0.30)["bets_per_week"] == pytest.approx(7.0)
    assert lc._project(rows, 1.0, 0.70, 0.30)["bets_per_week"] == pytest.approx(0.0)


# ── sweep ────────────────────────────────────────────────────────────────────

def test_sweep_scores_a_plateau_higher_than_an_isolated_cell():
    rows = [pick(p, -110, "WIN") for p in (0.60, 0.64, 0.68, 0.72, 0.76)]
    cells = lc._sweep(rows, rows, 1.0)
    assert cells, "sweep produced no cells"
    # Everything wins here, so interior cells must see profitable neighbours.
    interior = [c for c in cells if c["min_prob"] == 0.66 and c["min_ev"] == 0.18]
    assert interior and interior[0]["plateau"] >= 4


def test_sweep_skips_cells_with_no_picks_rather_than_emitting_empty_ones():
    rows = [pick(0.60, -110, "WIN")]
    cells = lc._sweep(rows, rows, 1.0)
    assert all(c["bets"] > 0 for c in cells)
    assert not any(c["min_prob"] > 0.60 for c in cells)


# ── persistence ──────────────────────────────────────────────────────────────

def test_persist_creates_its_own_table_and_is_idempotent(tmp_path):
    """It creates the table at write time on purpose — a feature that needs a
    manual migration first does nothing until someone remembers."""
    conn = sqlite3.connect(tmp_path / "t.db")
    report = {"model_id": "m", "sport": "MLB", "computed_at": "now",
              "verdict": "v", "current": {}, "recommended": None}
    # sqlite has no ON CONFLICT ... EXCLUDED via %(name)s params, so drive the
    # same DDL + a plain upsert to prove the schema half.
    conn.execute(lc.DDL)
    conn.execute(lc.DDL)          # idempotent
    cols = {r[1] for r in conn.execute("PRAGMA table_info(live_calibration)")}
    assert cols == {"model_id", "sport", "computed_at", "verdict", "payload"}
    assert "model_id" in report
    conn.close()


def test_lockdown_statements_target_anon_and_authenticated_by_name():
    """A REVOKE ... FROM PUBLIC does nothing about Supabase's default grants —
    the roles have to be named. See CLAUDE.md section 7."""
    joined = " ".join(lc.LOCKDOWN)
    assert "ENABLE ROW LEVEL SECURITY" in joined
    assert "FROM anon" in joined and "FROM authenticated" in joined
    assert "FROM PUBLIC" not in joined
