"""The NCAAB in-play model's pure decision path: prices, settlement, phases,
the walk-forward guard, the first-fetch spend and the outlier filter."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from models import ncaab_live_ig as M


def test_spread_probabilities_use_the_home_number():
    # home -5.5, model margin mean +10 with almost no spread: home covers
    pw, pp = M.side_probs(["spreads", "spreads"], ["home", "away"], [-5.5, -5.5], [10, 10], [1e-6, 1e-6])
    assert pw[0] == pytest.approx(1.0) and pw[1] == pytest.approx(0.0) and pp[0] == 0
    # an integer line pushes when the margin lands on it
    pw, pp = M.side_probs(["spreads"], ["home"], [-5.0], [5.0], [1e-6])
    assert pp[0] == pytest.approx(1.0)


def test_moneyline_has_no_push_and_sums_to_one():
    pw_h, pp = M.side_probs(["h2h"], ["home"], [np.nan], [0.0], [8.0])
    pw_a, _ = M.side_probs(["h2h"], ["away"], [np.nan], [0.0], [8.0])
    assert pp[0] == 0 and pw_h[0] + pw_a[0] == pytest.approx(1.0) and pw_h[0] == pytest.approx(0.5)


def test_totals_over_and_under():
    pw_o, _ = M.side_probs(["totals"], ["over"], [140.5], [150.0], [1e-6])
    pw_u, _ = M.side_probs(["totals"], ["under"], [140.5], [150.0], [1e-6])
    assert pw_o[0] == pytest.approx(1.0) and pw_u[0] == pytest.approx(0.0)


def test_settle_signs_on_the_home_number():
    # home -5.5 (scored_line is the HOME number); home wins by 3: away covers
    res = M.settle(["spreads", "spreads", "totals", "h2h"], ["away", "home", "under", "home"],
                   [-5.5, -5.5, 150.5, np.nan], [73, 73, 73, 73], [70, 70, 70, 70])
    assert list(res) == ["W", "L", "W", "W"]
    assert list(M.settle(["spreads"], ["home"], [-3.0], [73], [70])) == ["P"]


def test_units_are_one_to_win_risk_capped_at_three():
    u, r = M.units(["W", "L", "W", "L", "P"], [-150, -150, 150, -400, -110])
    assert r[0] == pytest.approx(1.5) and u[0] == pytest.approx(1.0)
    assert u[1] == pytest.approx(-1.5)
    assert r[2] == pytest.approx(2 / 3) and u[2] == pytest.approx(1.0)  # +150: 0.667 risk wins 1
    assert r[3] == pytest.approx(3.0)                                   # -400 would need 4: capped
    assert u[4] == 0


def _state(period, clock_s, type_text="JumpShot", h=40, a=35):
    return pd.DataFrame({"period": [period], "clock_s": [clock_s], "type_text": [type_text],
                         "h_pts": [h], "a_pts": [a]})


def test_phases():
    def ph(*a, **k):
        return M.phase_of(M.state_columns(_state(*a, **k)))[0]
    assert ph(1, 600) == "H1"
    assert ph(1, 0, "End Period") == "H2"           # the halftime break
    assert ph(2, 900) == "H2"
    assert ph(2, M.H2_MIN_SECS_LEFT - 1) == ""      # the last two minutes are neither
    assert ph(3, 200) == ""                         # overtime is neither


def _train(seasons):
    rng = np.random.default_rng(0)
    n = 400
    df = pd.DataFrame({"season": np.repeat(seasons, n // len(seasons)),
                       "f": rng.uniform(0.05, 1, n), "half_left": rng.uniform(0, 1, n),
                       "m": rng.normal(0, 8, n), "t": rng.uniform(0, 140, n),
                       "mu_pre": rng.normal(3, 8, n), "T_pre": rng.normal(140, 8, n),
                       "h_tf": rng.integers(0, 12, n), "a_tf": rng.integers(0, 12, n),
                       "secs_left": rng.uniform(0, 2400, n)})
    df["final_margin"] = df["m"] + df["f"] * df["mu_pre"] + rng.normal(0, 3, n)
    df["final_total"] = df["t"] + df["f"] * df["T_pre"] + rng.normal(0, 5, n)
    return M.features(df)


def test_walk_forward_refuses_its_own_season():
    with pytest.raises(ValueError):
        M.StateModel("margin").fit(_train([2024, 2025]), 2025)
    m = M.StateModel("margin").fit(_train([2023, 2024]), 2025)
    back = M.StateModel.from_dict(m.to_dict())
    x = _train([2023])
    assert np.allclose(m.predict(x)[0], back.predict(x)[0])


def test_choose_spends_the_rule_when_the_best_offer_misses_the_cut():
    off = pd.DataFrame({"game_id": ["g", "g", "g"], "rule": ["spreads_H1"] * 3,
                        "book": ["fanduel", "draftkings", "pinnacle"], "price": [-110, -110, 120],
                        "ev": [0.03, 0.03, 0.30]})
    d = M.choose(off, 0.05, ("draftkings", "fanduel"))
    # pinnacle is not a deciding book; the best allowed offer (a tie, to the
    # earlier book) misses the cut and comes back as a spent decision
    assert len(d) == 1 and d.iloc[0]["book"] == "draftkings" and not d.iloc[0]["bet"]
    assert M.choose(off, 0.02, ("draftkings", "fanduel")).iloc[0]["bet"]


def test_price_floor_and_the_dead_zone_prices_are_refused():
    q = pd.DataFrame({"game_id": ["g"], "market": ["h2h"], "book": ["fanduel"],
                      "home_price": [-250.0], "away_price": [50.0], "spread_home": [np.nan],
                      "total_line": [np.nan], "over_price": [np.nan], "under_price": [np.nan]})
    off = M.offers_from_quotes(q)
    assert off["price"].tolist() == [-250.0]                       # +50 is not a price
    off = off.assign(rule="h2h_H1", ev=0.5)
    assert len(M.choose(off, 0.0, ("fanduel",))) == 0              # -250 is under the -200 floor


def test_outlier_quote_is_dropped_against_the_other_books():
    q = pd.DataFrame({"game_id": ["g"] * 4, "market": ["totals"] * 4, "fetch_at": [1] * 4,
                      "book": ["a", "b", "c", "d"], "total_line": [150.5, 151.5, 150.5, 159.0],
                      "spread_home": [np.nan] * 4, "home_price": [np.nan] * 4,
                      "away_price": [np.nan] * 4})
    assert M.drop_outliers(q)["book"].tolist() == ["a", "b", "c"]


def test_feed_typos_are_dropped_by_the_ncaab_guard_before_anything_reads_them():
    # the two measured typos: DraftKings' 1465.0 total and Hard Rock's -200000
    q = pd.DataFrame({"game_id": ["g"] * 4, "market": ["totals", "totals", "spreads", "h2h"],
                      "book": list("abcd"), "total_line": [1465.0, 146.5, np.nan, np.nan],
                      "over_price": [-110, -110, np.nan, np.nan],
                      "under_price": [-110, -110, np.nan, np.nan],
                      "spread_home": [np.nan, np.nan, -5.5, np.nan],
                      "home_price": [np.nan, np.nan, -110, -200000],
                      "away_price": [np.nan, np.nan, -110, 4000]})
    ok, bad = M.in_bounds(q)
    assert ok["book"].tolist() == ["b", "c"] and bad["book"].tolist() == ["a", "d"]


def test_a_spread_or_total_at_a_junk_price_is_not_an_offer():
    q = pd.DataFrame({"game_id": ["g", "g"], "market": ["spreads", "totals"], "book": ["a", "b"],
                      "home_price": [4500.0, np.nan], "away_price": [-110.0, np.nan],
                      "spread_home": [-12.5, np.nan], "total_line": [np.nan, 133.5],
                      "over_price": [np.nan, 2200.0], "under_price": [np.nan, -115.0]})
    off = M.offers_from_quotes(q)
    assert sorted(off["price"].tolist()) == [-115.0, -110.0]
