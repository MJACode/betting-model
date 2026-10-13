"""The in-play leader moneyline's model and rule (nfl_live_leader/model.py).

What is pinned, and the failure each test exists for:
  * the artifact's golden grid IS wp_lookup -- a coefficient copied from a
    rounded printout, or a re-derived formula, moves an entry near the 0.02 cut;
  * the design matrix and the lookup are the backtest's own functions, bit for
    bit (scripts/nfl_edge_inplay_2025.py) -- the parity run depends on it;
  * every refusal in the rule: overtime, game over, outside 10:00, a lead
    outside 4-16 (wp_lookup CLIPS the lead index, so a 3-point lead would
    silently borrow the 4-point fit), no spread, no possession, no price;
  * the band sign: the platform stores the HOME handicap (negative = home
    favoured); the model was trained on the home EXPECTED MARGIN. A flipped
    sign swaps favourite and underdog and changes real decisions.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from nfl_live_leader import model as M


@pytest.fixture(scope="module")
def art():
    return M.load_artifact()


def _raw():
    return json.loads(M.ARTIFACT_PATH.read_text(encoding="utf-8"))


# ─── the artifact ─────────────────────────────────────────────────────────────

def test_artifact_identity_training_and_rule(art):
    d = _raw()
    assert d["identity"]["model_id"] == M.MODEL_ID
    assert d["training"]["seasons"] == list(range(2016, 2026))
    assert "IN-SAMPLE" in d["training"]["in_sample_note"]
    assert d["features"]["columns"] == list(M.COLUMNS)
    r = d["rule"]
    assert (r["period_max"], r["secs_max"], r["lead_min"], r["lead_max"], r["edge_cut"]) == \
        (4, 600, 4, 16, 0.02)
    assert r["venue"] == "draftkings" and r["min_price"] is None and r["max_price"] is None
    assert art.coefs.shape == (13, 6)


def test_coefficients_are_full_precision():
    """A 3-decimal printout flips entries near the cut; the artifact must carry
    the float64 itself (json writes repr(), which round-trips)."""
    vals = [v for L in range(4, 17) for v in _raw()["coefficients"][str(L)]]
    assert sum(1 for v in vals if round(v, 6) != v) >= 70, "coefficients look rounded"


def test_golden_grid_matches_wp_lookup(art):
    """13 leads x 10 clocks x ball x 3 bands, against the BACKTEST's wp_lookup and
    the scalar production wp(), to 1e-12."""
    from scripts.nfl_edge_inplay_2025 import wp_lookup as bt_wp_lookup

    grid = art.golden_grid
    secs = np.array(grid["secs"], float)
    assert list(secs) == [30.0 + 60 * i for i in range(10)]
    assert len(grid["rows"]) == 13 * 2 * 3
    for row in grid["rows"]:
        n = len(secs)
        bt = bt_wp_lookup(art.coefs, np.full(n, row["lead"]), np.full(n, row["ball"]),
                          np.full(n, row["band"]), secs)
        assert np.max(np.abs(bt - np.array(row["wp"]))) <= 1e-12, row
        for s, w in zip(secs, row["wp"]):
            assert abs(M.wp(art, row["lead"], s, row["ball"], row["band"]) - w) <= 1e-12


def test_design_and_lookup_are_the_backtests_bit_for_bit(art):
    from scripts.nfl_edge_inplay_2025 import wp_design as bt_design, wp_lookup as bt_lookup

    rng = np.random.default_rng(3)
    n = 5000
    lead = rng.integers(4, 17, n)
    ball = rng.integers(0, 2, n)
    band = rng.integers(0, 3, n)
    secs = rng.uniform(0, 600, n).round()
    assert np.array_equal(M.wp_design(secs, ball, band), bt_design(secs, ball, band))
    assert np.array_equal(M.wp_lookup(art.coefs, lead, ball, band, secs),
                          bt_lookup(art.coefs, lead, ball, band, secs))
    assert np.array_equal(M.am_to_dec([-4000, -330, -110, 100, 180]),
                          np.array([1.025, 1 + 100 / 330, 1 + 100 / 110, 2.0, 2.8]))


# ─── the rule ─────────────────────────────────────────────────────────────────

BASE = dict(period=4, secs=300, home_score=24, away_score=17, possession="away",
            spread_home=-3.0, home_price=-300, away_price=240)


def _d(art, **kw):
    args = dict(BASE)
    args.update(kw)
    return M.decide(art, **args)


def test_a_qualifying_state_bets_the_leader_at_its_price(art):
    d = _d(art, home_price=-150)
    assert d.bet and d.reason == "BET"
    assert d.side == "home" and d.lead == 7 and d.ball == 0 and d.band == M.BAND_BASE
    assert d.price == -150 and d.decimal == pytest.approx(1 + 100 / 150)
    assert d.implied == 1 / d.decimal                      # vig included, no de-vig
    assert d.wp == M.wp(art, 7, 300, 0, M.BAND_BASE)
    assert d.edge == d.wp - d.implied and d.edge >= 0.02


def test_the_cut_is_inclusive_and_binds(art):
    w = M.wp(art, 7, 300, 0, M.BAND_BASE)
    # A price whose implied probability sits just above and just below wp - 0.02.
    for target, expect in ((w - 0.02 - 1e-6, True), (w - 0.02 + 1e-6, False)):
        dec = 1 / target
        american = -100 / (dec - 1) if dec < 2 else 100 * (dec - 1)
        d = _d(art, home_price=american)
        assert d.bet is expect, (target, d)


@pytest.mark.parametrize("kw,reason", [
    (dict(period=5), "overtime"),
    (dict(final=True), "game over"),
    (dict(period=None), "period unknown"),
    (dict(secs=601), "secs 601 > 600"),
    (dict(secs=None), "clock unknown"),
    (dict(home_score=20, away_score=17), "lead 3 outside 4-16"),
    (dict(home_score=34, away_score=17), "lead 17 outside 4-16"),
    (dict(home_score=17, away_score=17), "lead 0 outside 4-16"),
    (dict(spread_home=None), "no pregame spread"),
    (dict(spread_home=float("nan")), "no pregame spread"),
    (dict(possession=None), "possession unknown"),
    (dict(possession="kickoff"), "possession unknown"),
    (dict(home_price=None), "no DraftKings price for the leader"),
])
def test_every_refusal(art, kw, reason):
    d = _d(art, **{"home_price": -150, **kw})
    assert not d.bet
    assert d.reason == reason


def test_600_seconds_and_both_lead_ends_are_inside(art):
    for kw in (dict(secs=600), dict(home_score=21, away_score=17),
               dict(home_score=33, away_score=17)):
        d = _d(art, home_price=-100000 + 1, **kw)   # a price no edge can clear
        assert d.reason == "edge below cut", (kw, d.reason)


def test_wp_refuses_a_lead_the_clip_would_borrow(art):
    for lead in (0, 3, 17, 30):
        with pytest.raises(ValueError):
            M.wp(art, lead, 300, 1, 1)


# ─── the band sign ────────────────────────────────────────────────────────────

def test_band_from_the_home_handicap():
    # Home favoured by 7 (spread_home -7): a HOME leader is the favourite, an
    # AWAY leader the underdog. Away favoured by 7 (spread_home +7): reversed.
    assert M.band_for(M.leader_expected_margin(-7.0, True)) == M.BAND_FAV
    assert M.band_for(M.leader_expected_margin(-7.0, False)) == M.BAND_DOG
    assert M.band_for(M.leader_expected_margin(7.0, True)) == M.BAND_DOG
    assert M.band_for(M.leader_expected_margin(7.0, False)) == M.BAND_FAV
    # The 3.5 edges are inclusive, exactly as leader_view's >= / <=.
    assert M.band_for(3.5) == M.BAND_FAV and M.band_for(-3.5) == M.BAND_DOG
    assert M.band_for(3.0) == M.BAND_BASE and M.band_for(-3.0) == M.BAND_BASE


def test_band_matches_training_leader_view_on_nflverse_sign():
    """Production converts spread_home -> spread_line = -spread_home. The band it
    reaches must equal the builder's leader_view on the same game."""
    import pandas as pd

    from scripts.build_nfl_live_leader_artifact import leader_view

    rows = []
    for spread_line in (-10.0, -3.5, -3.0, 0.0, 3.0, 3.5, 10.0):
        for home_sc, away_sc in ((24, 17), (17, 24)):
            rows.append({"home_sc": home_sc, "away_sc": away_sc, "home_ball": 1,
                         "spread_line": spread_line})
    df = pd.DataFrame(rows)
    lv = leader_view(df)
    for (_, r), (_, v) in zip(df.iterrows(), lv.iterrows()):
        prod = M.band_for(M.leader_expected_margin(-r.spread_line, r.home_sc > r.away_sc))
        assert prod == v.band, (r.to_dict(), prod, v.band)


def test_a_flipped_spread_sign_changes_the_decision(art):
    """A concrete state where the band decides the bet. Lead 7, 5:00 left,
    leader without the ball. With the leader the pregame favourite the model's
    probability is higher than with the leader the underdog; at a price between
    the two the decision flips with the sign."""
    fav = M.wp(art, 7, 300, 0, M.BAND_FAV)
    dog = M.wp(art, 7, 300, 0, M.BAND_DOG)
    assert fav - dog > 0.05
    implied = (fav + dog) / 2 - 0.02 + 0.01          # clears as fav, fails as dog
    dec = 1 / implied
    american = -100 / (dec - 1)
    home_fav = _d(art, spread_home=-7.0, home_price=american)   # home favoured by 7
    home_dog = _d(art, spread_home=+7.0, home_price=american)   # away favoured by 7
    assert home_fav.band == M.BAND_FAV and home_fav.bet
    assert home_dog.band == M.BAND_DOG and not home_dog.bet


def test_possession_is_the_leaders_ball_flag(art):
    with_ball = _d(art, possession="home", home_price=-150)
    without = _d(art, possession="away", home_price=-150)
    assert with_ball.ball == 1 and without.ball == 0
    assert with_ball.wp > without.wp
