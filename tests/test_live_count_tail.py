"""The count tail a live model is BET with, and the guard that stops a
map/artifact mismatch pricing silently.

WHY THE TAIL IS ON THE ARTIFACT. A Poisson head asserts Var(y|lambda) ==
lambda. mlb_live_total_runs' remaining-runs target does not: with an honestly
fit model the ratio is ~2.15 in-sample and ~2.41 on the 2025 holdout —
consistent across both, so a property of the count and not of the fit. A
Poisson tail on that data is ~2.2x too tight, which pushes every probability
toward its extreme. Claimed vs realised at the >=0.70 band it bets, 2025
holdout: +0.0586 under Poisson, -0.0095 under NB1
(docs/mlb_volume_efficiency.md §17).

`dispersion` is absent from every artifact trained before 2026-09-08, and
absent means Poisson — so the K-prop models, which share _poisson_over_prob,
keep exactly the behaviour they had.
"""

import numpy as np
import pytest
from scipy.stats import nbinom, poisson

from models.scorer import _count_over_prob, _nb1_over_prob, _poisson_over_prob


# ── the tail ─────────────────────────────────────────────────────────────────

def test_no_dispersion_is_exactly_the_old_poisson_behaviour():
    """The prop models pass no dispersion and must be bit-identical."""
    for lam, line in [(4.5, 4.5), (0.6, 0.5), (9.1, 7.5), (2.0, 5.5)]:
        assert _count_over_prob(lam, line) == _poisson_over_prob(lam, line)
        assert _count_over_prob(lam, line, None) == _poisson_over_prob(lam, line)
        assert _count_over_prob(lam, line, {}) == _poisson_over_prob(lam, line)


def test_nb1_has_the_mean_it_claims_and_a_wider_variance():
    """NB1 is (mean lam, variance lam*(1+alpha)). If the parameterisation is
    wrong the model still produces probabilities — just the wrong ones."""
    lam, alpha = 5.0, 1.25
    n, p = lam / alpha, 1.0 / (1.0 + alpha)
    assert nbinom.mean(n, p) == pytest.approx(lam, rel=1e-9)
    assert nbinom.var(n, p) == pytest.approx(lam * (1.0 + alpha), rel=1e-9)


def test_the_wider_tail_pulls_probabilities_toward_one_half():
    """This is the whole mechanism: an overconfident tail is what pushes
    states over the 0.70 floor, and widening it takes them back."""
    lam, alpha = 5.0, 1.25
    for line in (1.5, 2.5, 8.5, 9.5):
        p_pois = _poisson_over_prob(lam, line)
        p_nb = _nb1_over_prob(lam, line, alpha)
        assert abs(p_nb - 0.5) < abs(p_pois - 0.5), (
            f"line {line}: NB {p_nb:.4f} was not closer to 0.5 than "
            f"Poisson {p_pois:.4f}")


def test_an_unknown_family_refuses_to_price_rather_than_falling_back():
    """A fallback to Poisson would silently give a DIFFERENT bet than the
    artifact asked for. Stopping is the only safe answer."""
    with pytest.raises(ValueError, match="unknown dispersion family"):
        _count_over_prob(5.0, 4.5, {"family": "nb7", "alpha": 1.0})


def test_nb1_with_an_unusable_alpha_refuses_too():
    for bad in (0.0, -1.0, None):
        with pytest.raises(ValueError):
            _count_over_prob(5.0, 4.5, {"family": "nb1", "alpha": bad})


# ── the map/artifact guard ───────────────────────────────────────────────────

def _setup(monkeypatch, feat_cols):
    """A live game that reaches the scoring step, with a recording model."""
    from models import live_scorer

    monkeypatch.setattr(live_scorer, "_get_live_dk_odds",
                        lambda conn, gid, market: {
                            "total_line": 4.5, "over_price": -135,
                            "under_price": 110, "spread_home": None,
                            "over_link": None, "under_link": None})

    class _Clf:
        def __init__(self): self.calls = 0
        def predict(self, x):
            self.calls += 1
            self.last = x
            return np.array([5.0])

    clf = _Clf()
    game = {"game_id": "MLB_2026-09-08_LAA_BOS", "game_date": "2026-09-08",
            "home_team": "BOS", "away_team": "LAA", "season": 2026,
            "commence_time": "2026-09-08T23:10:00+00:00"}
    state = {"inning": 3, "inning_half": "top", "outs": 1,
             "bases_state": "000", "home_score": 1, "away_score": 0}
    pregame = {"pregame_total_line": 8.5, "wind_out_component": 0.0,
               "temp_f": 70.0, "is_dome_game": 0}

    class _Conn:
        def execute(self, *a, **k): return self
        def fetchone(self): return None
        def fetchall(self): return []

    live_scorer._score_live_model(
        _Conn(), "mlb_live_total_runs",
        {"feature_cols": feat_cols, "model": clf},
        game, state, pregame, 1000.0)
    return clf


def test_an_artifact_wanting_an_unmapped_column_is_never_scored(monkeypatch):
    """FAIL CLOSED. build_live_state_row fills the columns LIVE_FEATURE_MAP
    names; x is indexed by the ARTIFACT's feature_cols. A B13 artifact
    registered against a map that still lacks pregame_total_line would price
    every live pick with its most important non-clock feature NaN, silently.

    A dark model is visible to the live health check. A NaN bet is visible to
    nobody.

    THE ASSERTION IS THAT THE MODEL IS NEVER CALLED, not that no picks come
    back. The first version of this test asserted `picks == []` and passed with
    the guard deleted — the fixture returned [] at the odds check long before
    reaching the guard. That is CLAUDE.md §1b's "a guard that dead code can
    satisfy is not a guard", caught in the act. Call-count is the one signal
    that cannot be produced by a threshold, an edge cap or a missing price.
    """
    clf = _setup(monkeypatch,
                 ["inning", "outs", "a_column_the_map_does_not_have"])
    assert clf.calls == 0


def test_the_same_fixture_does_reach_the_model_when_the_map_agrees(monkeypatch):
    """The discriminator: same game, same odds, columns the map DOES supply."""
    from features.live_game_features import LIVE_FEATURE_MAP

    clf = _setup(monkeypatch, list(LIVE_FEATURE_MAP["mlb_live_total_runs"]))
    assert clf.calls == 1, (
        "the fixture stopped reaching the model — the guard test above is "
        "now vacuous")
    # and the anchor actually arrived, rather than arriving as NaN
    cols = list(LIVE_FEATURE_MAP["mlb_live_total_runs"])
    assert clf.last[0][cols.index("pregame_total_line")] == 8.5


def test_every_mapped_model_can_be_built_from_the_map():
    """The guard above only helps if the map genuinely supplies its own
    columns — a state column missing from state_features would trip it on
    every game."""
    from features.live_game_features import (
        LIVE_FEATURE_MAP, LIVE_STATE_FEATURES, build_live_state_row,
    )
    state = {"inning": 3, "inning_half": "top", "outs": 1,
             "bases_state": "101", "home_score": 2, "away_score": 1}
    for model_id, cols in LIVE_FEATURE_MAP.items():
        pregame = {c: 1.0 for c in cols if c not in LIVE_STATE_FEATURES}
        row = build_live_state_row(state, pregame, model_id)
        assert row is not None
        missing = [c for c in cols if c not in row]
        assert not missing, f"{model_id}: map does not supply {missing}"
