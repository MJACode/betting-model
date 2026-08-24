"""
Pure-math tests for the NCAAF margin/total regression harness — the grading
conventions here are the same §29 conventions a sign bug once corrupted in the
runline views, so they are pinned before the harness ever sees real data.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.ncaaf_margin_eval import (  # noqa: E402
    BREAKEVEN, MARGIN_FEATURES, TOTAL_FEATURES,
    rmse, sweep_spread, sweep_total, verdict)


def test_market_numbers_are_not_regression_features():
    assert "spread_home" not in MARGIN_FEATURES
    assert "total_line" not in TOTAL_FEATURES


def test_spread_grading_home_and_away_sides():
    # Game 1: model says home by 10, spread home -3 (home favoured by 3),
    #   d = +7 → bet HOME -3; actual margin 7 → home covers → WIN.
    # Game 2: model says home by 1, spread home -6, d = -5 → bet AWAY +6;
    #   actual margin 3 → home wins by 3 but does NOT cover → away covers → WIN.
    # Game 3: model says home by 8, spread home -3, d = +5 → bet HOME -3;
    #   actual margin 2 → home fails to cover → LOSS.
    rows = sweep_spread(pred_margin=[10, 1, 8],
                        spread_home=[-3, -6, -3],
                        actual_margin=[7, 3, 2],
                        thresholds=[0, 5])
    at0 = rows[0]
    assert (at0["bets"], at0["wins"]) == (3, 2)
    at5 = rows[1]                      # all three have |d| >= 5
    assert (at5["bets"], at5["wins"]) == (3, 2)


def test_spread_push_excluded_from_record():
    # actual margin 3 vs home -3 → push: not a bet, not a loss.
    rows = sweep_spread([10], [-3], [3], thresholds=[0])
    assert rows[0]["bets"] == 0 and rows[0]["pushes"] == 1


def test_threshold_filters_small_disagreements():
    # d = +1 only — at threshold 3 no bet fires.
    rows = sweep_spread([4], [-3], [10], thresholds=[3])
    assert rows[0]["bets"] == 0


def test_total_grading_both_sides_and_push():
    # Over pick wins, under pick wins, push excluded.
    # Third game: the model DOES disagree (53 vs 50) but the game lands
    # exactly on the line — a selected bet that pushes.
    rows = sweep_total(pred_total=[60, 40, 53],
                       total_line=[52.5, 48.5, 50],
                       actual_total=[55, 41, 50],
                       thresholds=[0])
    assert (rows[0]["bets"], rows[0]["wins"], rows[0]["pushes"]) == (2, 2, 1)


def test_verdict_enforces_volume_and_breakeven():
    rows = [
        {"threshold": 1, "bets": 200, "wins": 100, "pushes": 0, "win_rate": 0.50},
        {"threshold": 5, "bets": 10, "wins": 9, "pushes": 0, "win_rate": 0.90},
    ]
    assert verdict(rows) is None          # 50% fails breakeven; 90% fails volume
    rows.append({"threshold": 3, "bets": 60, "wins": 33, "pushes": 0,
                 "win_rate": 33 / 60})
    best = verdict(rows)
    assert best is not None and best["threshold"] == 3
    assert 33 / 60 >= BREAKEVEN


def test_rmse():
    assert rmse([0, 0], [3, 4]) == pytest.approx((12.5) ** 0.5)


# ── Residual-ECDF probability + the scorer's margin branch ────────────────────

def test_margin_cover_prob_ecdf():
    from features.ncaaf_feature_engine import margin_cover_prob
    # Symmetric residuals: zero disagreement → ~0.5; monotone in d; clamped.
    r = sorted([-20, -10, -5, -1, 1, 5, 10, 20])
    assert margin_cover_prob(r, 0) == pytest.approx(0.5)
    assert margin_cover_prob(r, 6) > margin_cover_prob(r, 2) > 0.5
    assert margin_cover_prob(r, -6) < margin_cover_prob(r, -2) < 0.5
    assert margin_cover_prob(r, 1000) == 0.99      # clamped, never 1.0
    assert margin_cover_prob(r, -1000) == 0.01
    assert margin_cover_prob([], 5) == 0.5          # no residuals → agnostic


def test_scorer_routes_margin_artifact_through_residual_prob(monkeypatch):
    """
    End-to-end through score_game with a fake margin artifact: the probability
    must come from the residual ECDF at (pred_margin + spread_home), and the
    pick must flow through the stock spreads side-evaluation.
    """
    import models.scorer as sc
    from features.ncaaf_feature_engine import margin_cover_prob

    class _Reg:                        # predicts home by 10, always
        def predict(self, x):
            return [10.0]

    residuals = sorted(float(v) for v in range(-30, 31))   # wide, symmetric
    artifact = {"kind": "margin_regression", "model": _Reg(),
                "feature_cols": ["d_sp_overall", "d_travel_miles"],
                "residuals": residuals}

    monkeypatch.setattr(sc, "load_model", lambda mid: artifact)
    # DK: home -3.5 at -110 both sides → disagreement d = 10 + (-3.5) = 6.5
    monkeypatch.setattr(sc, "_get_dk_odds", lambda conn, gid, market: {
        "spread_home": -3.5, "home_price": -110, "away_price": -110,
        "total_line": None})
    monkeypatch.setattr(sc, "_get_public_betting",
                        lambda conn, gid, market, side: {
                            "public_bet_pct": None, "public_money_pct": None})

    features = {"d_sp_overall": 1.0, "d_travel_miles": None,
                "home_team": "Ohio State", "away_team": "Toledo",
                "game_date": "2026-09-05"}
    picks = sc.score_game(None, "NCAAF_2026-09-05_toledo_ohio-state",
                          "ncaaf_spread", features, bankroll=1000.0,
                          dry_run=True)

    expected_prob = margin_cover_prob(residuals, 6.5)
    assert expected_prob > 0.5
    home = [p for p in picks if p["pick_side"] == "home"]
    assert home, "home side pick row must be generated"
    # _make_pick rounds to 4 decimals — compare at that precision.
    assert home[0]["model_probability"] == pytest.approx(expected_prob, abs=1e-4)
    assert home[0]["scored_line"] == -3.5
    # d=6.5 with these residuals → prob ≈ 0.60 < the 0.63 bar → dead-zone NONE,
    # exactly the behavior the ±5.5-equivalent prob gate is meant to encode
    # once --fit sets the bar from the real residuals.
    assert home[0]["signal_type"] in ("BET", "NONE")


def test_scorer_margin_artifact_skips_without_a_dk_spread(monkeypatch):
    import models.scorer as sc

    artifact = {"kind": "margin_regression", "model": object(),
                "feature_cols": ["d_sp_overall"], "residuals": [0.0]}
    monkeypatch.setattr(sc, "load_model", lambda mid: artifact)
    monkeypatch.setattr(sc, "_get_dk_odds", lambda conn, gid, market: None)

    picks = sc.score_game(None, "NCAAF_2026-09-05_a_b", "ncaaf_spread",
                          {"d_sp_overall": 1.0, "home_team": "A",
                           "away_team": "B", "game_date": "2026-09-05"},
                          bankroll=1000.0, dry_run=True)
    assert picks == []


# ── Walk-forward ──────────────────────────────────────────────────────────────
# The single-holdout pass can only speak for one season, and 2023/2024 sit
# INSIDE that model's training window. Walk-forward is the honest multi-season
# record: each season predicted by a model fit only on prior seasons.

def test_walk_forward_never_trains_on_the_test_season_or_later(monkeypatch):
    import pandas as pd
    import numpy as np
    import scripts.ncaaf_margin_eval as ev

    rng = np.random.default_rng(3)
    frames = []
    for season in (2021, 2022, 2023, 2024):
        n = 200
        d = pd.DataFrame({c: rng.normal(size=n) for c in ev.MARGIN_FEATURES})
        d["_season"] = season
        d["_margin"] = 6 * d["d_sp_overall"] + rng.normal(0, 9, n)
        d["_spread_home"] = -(d["_margin"] + rng.normal(0, 4, n))
        d["_total"] = 50.0
        d["_total_line"] = 50.0
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)

    monkeypatch.setattr(ev, "build_frames", lambda seasons: df)

    seen_train_seasons = {}
    real_fit = ev._fit

    def spy_fit(X, y):
        # Record which seasons went into this fit via the row index.
        seen_train_seasons[len(seen_train_seasons)] = set(
            df.loc[X.index, "_season"].unique())
        return real_fit(X, y)

    monkeypatch.setattr(ev, "_fit", spy_fit)

    res = ev.walk_forward([2021, 2022, 2023, 2024], [2023, 2024], gate=3.0)

    assert [s["season"] for s in res["seasons"]] == [2023, 2024]
    # Fit 0 is for test season 2023 → may only see 2021-2022.
    assert seen_train_seasons[0] == {2021, 2022}
    # Fit 1 is for 2024 → may see 2021-2023, never 2024 itself.
    assert seen_train_seasons[1] == {2021, 2022, 2023}
    for s in res["seasons"]:
        assert max(s["train_seasons"]) < s["season"], "leak: trained on >= test season"


def test_walk_forward_skips_a_season_with_no_prior_data(monkeypatch):
    import pandas as pd
    import numpy as np
    import scripts.ncaaf_margin_eval as ev

    rng = np.random.default_rng(5)
    n = 120
    d = pd.DataFrame({c: rng.normal(size=n) for c in ev.MARGIN_FEATURES})
    d["_season"] = 2021
    d["_margin"] = rng.normal(0, 10, n)
    d["_spread_home"] = -d["_margin"]
    monkeypatch.setattr(ev, "build_frames", lambda seasons: d)

    # 2021 is the earliest season — nothing prior to train on, so it is skipped
    # rather than silently trained on itself.
    res = ev.walk_forward([2021], [2021], gate=3.0)
    assert res["seasons"] == []
