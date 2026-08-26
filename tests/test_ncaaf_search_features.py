"""
Leakage + correctness tests for the NCAAF search feature layer.

The tests that matter here are the leakage ones. A leaky opponent adjustment
produces a beautiful backtest and no money, and it is invisible in aggregate
metrics — so it gets pinned directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.ncaaf_search.features import (  # noqa: E402
    fit_opponent_adjustment, build_adjusted_ratings, blended_rating,
    rolling_variants, features_for, FEATURE_GROUPS, MARKET_ONLY,
    MIN_PRIOR_GAMES,
)


def _synth(n_weeks: int = 8, seed: int = 0) -> pd.DataFrame:
    """
    Synthetic season with KNOWN team strengths, so the ridge has a ground
    truth to recover. Team i has offence strength i/10.
    """
    rng = np.random.default_rng(seed)
    teams = [f"T{i}" for i in range(10)]
    rows = []
    gid = 0
    for w in range(1, n_weeks + 1):
        order = list(rng.permutation(teams))
        for pair_i, (a, b) in enumerate(zip(order[::2], order[1::2])):
            gid += 1
            # Alternate which side hosts. Without this, home assignment
            # correlates with team strength by chance at small n and the HFA
            # term absorbs that imbalance -- which is a property of the
            # fixture, not of the estimator.
            if pair_i % 2 == 1:
                a, b = b, a
            sa, sb = int(a[1:]) / 10.0, int(b[1:]) / 10.0
            for team, opp, is_home, s_off, s_def in (
                (a, b, 1, sa, sb), (b, a, 0, sb, sa)
            ):
                rows.append({
                    "game_id": f"G{gid}", "team": team, "opponent": opp,
                    "season": 2021, "week": w, "game_date": f"2021-09-{w:02d}",
                    "is_home": is_home, "is_neutral_site": 0,
                    "points_per_play": 0.4 + s_off - 0.5 * s_def
                                       + 0.05 * is_home + rng.normal(0, 0.02),
                })
    return pd.DataFrame(rows)


# ── Leakage ───────────────────────────────────────────────────────────────────

def test_ratings_never_use_the_week_they_rate():
    """
    THE leakage test. For every (season, week) cut, the fit must be built only
    from games strictly before that week. We prove it by mutating a later week
    to absurd values and asserting earlier cuts are byte-identical.
    """
    df = _synth()
    base = build_adjusted_ratings(df, metrics=["points_per_play"])

    poisoned = df.copy()
    late = poisoned["week"] >= 5
    poisoned.loc[late, "points_per_play"] = 999.0
    after = build_adjusted_ratings(poisoned, metrics=["points_per_play"])

    for (season, week, metric), r in base.items():
        if week <= 5:           # cut at week 5 uses weeks < 5 only
            r2 = after[(season, week, metric)]
            assert r.offense == pytest.approx(r2.offense, abs=1e-9), (
                f"cut (season={season}, week={week}) changed when week>=5 was "
                "poisoned — the adjustment is leaking future games")
            assert r.hfa == pytest.approx(r2.hfa, abs=1e-9)


def test_later_cuts_do_change_when_poisoned():
    """Control for the test above: if nothing changed anywhere, it proves nothing."""
    df = _synth()
    base = build_adjusted_ratings(df, metrics=["points_per_play"])
    poisoned = df.copy()
    poisoned.loc[poisoned["week"] >= 5, "points_per_play"] = 999.0
    after = build_adjusted_ratings(poisoned, metrics=["points_per_play"])

    changed = [k for k, r in base.items()
               if k[1] > 5 and after[k].offense != pytest.approx(r.offense, abs=1e-9)]
    assert changed, "poisoning later weeks changed no later cut — test is inert"


def test_rolling_variants_shift_so_a_game_never_sees_itself():
    df = _synth(n_weeks=6)
    out = rolling_variants(df, metrics=["points_per_play"], half_lives=(4.0,))

    first = out[out["prior_games"] == 0]
    assert first["points_per_play__std"].isna().all(), (
        "a team's first game has no prior games; its rolling mean must be NaN")

    merged = out.merge(df[["game_id", "team", "points_per_play"]],
                       on=["game_id", "team"])
    second = merged[merged["prior_games"] == 1]
    for _, r in second.iterrows():
        assert r["points_per_play__std"] != pytest.approx(r["points_per_play"]), (
            "second game's prior mean equals its own value — not shifted")


# ── Correctness ───────────────────────────────────────────────────────────────

def test_ridge_recovers_known_ordering():
    """Ridge shrinks magnitudes, so assert ORDER, not exact values."""
    df = _synth(n_weeks=10, seed=3)
    r = fit_opponent_adjustment(df, "points_per_play")
    assert r is not None
    got = [t for t, _ in sorted(r.offense.items(), key=lambda kv: kv[1])]
    truth = [f"T{i}" for i in range(10)]
    corr = np.corrcoef([truth.index(t) for t in got], range(10))[0, 1]
    assert corr > 0.85, f"recovered offence order barely correlates (r={corr:.2f})"


def test_hfa_is_positive_and_neutral_site_excluded():
    df = _synth(n_weeks=20, seed=5)
    hfa = fit_opponent_adjustment(df, "points_per_play").hfa
    assert hfa > 0, f"known +0.05 home effect recovered as {hfa:.4f}"

    neutral = df.copy()
    neutral["is_neutral_site"] = 1
    r = fit_opponent_adjustment(neutral, "points_per_play")
    assert abs(r.hfa) < 0.02, "neutral-site games must not contribute HFA"


def test_confounded_home_assignment_plus_heavy_alpha_corrupts_hfa():
    """
    The real, verified failure mode -- and the reason RIDGE_ALPHA is not a
    magic constant.

    HFA is only identified when home assignment is roughly independent of team
    strength. Break that (host the stronger team every week) and crush the team
    coefficients, and the unpenalised HFA column absorbs the strength imbalance
    instead of measuring home advantage.

    The SIGN of the corruption follows the direction of the imbalance -- home
    teams stronger inflates HFA, home teams weaker inverts it -- so the stable
    property to assert is DISTANCE FROM TRUTH, not direction. (An earlier
    version of this test asserted a direction and was wrong for exactly that
    reason.)

    Balanced hosting alone protects the estimate (see the test above), so this
    is an identification property, not an estimator bug. It is pinned because
    real schedules are not perfectly balanced and early-season cuts are the
    small-n, heavy-shrinkage regime where it bites.
    """
    TRUE_HFA = 0.05
    df = _synth(n_weeks=10, seed=5).copy()
    strength = df["team"].str[1:].astype(int)
    opp_strength = df["opponent"].str[1:].astype(int)
    df["is_home"] = (strength > opp_strength).astype(int)   # force the confound

    sane = fit_opponent_adjustment(df, "points_per_play", alpha=0.01).hfa
    crushed = fit_opponent_adjustment(df, "points_per_play", alpha=500.0).hfa

    assert abs(crushed - TRUE_HFA) > abs(sane - TRUE_HFA), (
        f"heavy shrinkage under confounded hosting should move HFA further "
        f"from truth (sane={sane:.4f}, crushed={crushed:.4f}, true={TRUE_HFA})")
    assert abs(crushed - TRUE_HFA) > 0.2, (
        f"expected gross corruption under this fixture, got {crushed:.4f}")


def test_returns_none_below_min_prior_games():
    df = _synth(n_weeks=8).head(MIN_PRIOR_GAMES - 1)
    assert fit_opponent_adjustment(df, "points_per_play") is None


def test_blend_weights_move_from_prior_to_current():
    adj = {(2022, 5, "m"): type("R", (), {"offense": {"A": 1.0}, "defense": {}})()}
    prev = {(2021, "m"): type("R", (), {"offense": {"A": 0.0}, "defense": {}})()}

    at0 = blended_rating(adj, prev, 2022, 5, "m", "A", "off", games_played=0)
    at4 = blended_rating(adj, prev, 2022, 5, "m", "A", "off", games_played=4)
    at12 = blended_rating(adj, prev, 2022, 5, "m", "A", "off", games_played=12)

    assert at0 == pytest.approx(0.0), "no games played -> pure prior season"
    assert at4 == pytest.approx(0.5), "g=k -> even blend"
    assert at12 > at4 > at0, "weight must move toward the current season"


def test_blend_falls_back_when_one_side_missing():
    adj = {(2022, 5, "m"): type("R", (), {"offense": {"A": 1.0}, "defense": {}})()}
    assert blended_rating(adj, {}, 2022, 5, "m", "A", "off", 3) == pytest.approx(1.0)
    prev = {(2021, "m"): type("R", (), {"offense": {"A": 0.7}, "defense": {}})()}
    assert blended_rating({}, prev, 2022, 5, "m", "A", "off", 3) == pytest.approx(0.7)
    assert blended_rating({}, {}, 2022, 5, "m", "A", "off", 3) is None


# ── Registry ──────────────────────────────────────────────────────────────────

def test_market_only_baseline_has_no_team_strength_features():
    """The sanity baseline must contain the line and nothing predictive of teams."""
    banned = ("adj_", "epa", "success", "explos", "havoc", "talent",
              "returning", "sp_", "srs")
    for c in MARKET_ONLY:
        assert not any(b in c for b in banned), f"{c} is not market-only"


def test_features_for_dedupes_and_preserves_order():
    got = features_for(["D_market", "D_market", "F_situ"])
    assert len(got) == len(set(got))
    assert got[0] == FEATURE_GROUPS["D_market"][0]


def test_every_group_is_non_empty_and_registered():
    for g, cols in FEATURE_GROUPS.items():
        assert cols, f"group {g} is empty"
