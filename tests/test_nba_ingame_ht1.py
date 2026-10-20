"""HT-1, the halftime family (scripts/nba_ingame_ht1.py; docs/nba_models_2026.md
7.3, "How HT-1 is scored"), on synthetic rows.

What each test pins:
  - luck points: hot shooting is positive luck, at the registered arithmetic;
  - a team's rates come from its EARLIER games this season only;
  - the first half is periods 1-2, and a missed heave is in neither the
    attempts nor the rates (one definition for both);
  - the model for season S is fit on seasons before S; 2020-21 alone is fit on
    itself, and any other season with nothing earlier is refused;
  - the decision set: halftime stamps only, deciding books only, the quote AND
    its Pinnacle quote fresh, one purchase per game (the first);
  - a spread's centre is the home margin (home -3.5 at even money centres near
    +3.5), the strength is model minus that centre toward the home side, and
    the away side carries its negative;
  - the information test: a model that knows something gives an interval
    above zero, noise does not, and a market opens only when BOTH the choosing
    seasons and 2025-26 lie above zero;
  - the halftime distribution refuses a choosing season with too few earlier
    games (it would otherwise fall back to the season's own results).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts import nba_game_harness as H
from scripts import nba_ingame_ht1 as T


def test_hot_shooting_is_positive_luck_at_the_registered_arithmetic():
    # 10 of 20 threes at an expected 35% = 3 makes above: 9 points; 8 of 10 free throws at 80%: 0
    assert T.luck_points(10, 20, 8, 10, 0.35, 0.80) == pytest.approx(9.0)
    assert T.luck_points(4, 20, 6, 10, 0.35, 0.80) == pytest.approx(3 * (4 - 7) + (6 - 8))


def _halves(rows):
    base = {f"{p}_{c}_game": 0.0 for p in ("h", "a") for c in ("fg3a", "fg3m", "fta", "ftm")}
    return pd.DataFrame([{**base, **r} for r in rows])


def test_rates_come_only_from_earlier_games_this_season():
    games = pd.DataFrame({
        "game_id": ["g1", "g2", "g3"], "season": [2024, 2024, 2024],
        "game_date": ["2024-01-01", "2024-01-03", "2024-01-05"],
        "home_team": ["BOS", "BOS", "BOS"], "away_team": ["NYK", "MIA", "LAL"]})
    hv = _halves([
        {"game_id": "g1", "h_fg3a_game": 10, "h_fg3m_game": 5, "h_fta_game": 10, "h_ftm_game": 9},
        {"game_id": "g2", "h_fg3a_game": 10, "h_fg3m_game": 3, "h_fta_game": 10, "h_ftm_game": 7},
        {"game_id": "g3", "h_fg3a_game": 40, "h_fg3m_game": 40, "h_fta_game": 1, "h_ftm_game": 1}])
    r = T.rates_before(hv, games).set_index("game_id")
    assert np.isnan(r.loc["g1", "h_r3"]) and r.loc["g1", "h_n_before"] == 0
    assert r.loc["g2", "h_r3"] == pytest.approx(0.5) and r.loc["g2", "h_rft"] == pytest.approx(0.9)
    # g3's own 40 of 40 never enters its own rate
    assert r.loc["g3", "h_r3"] == pytest.approx(8 / 20) and r.loc["g3", "h_n_before"] == 2


def _plays(rows):
    cols = {"game_id": "G", "period": 1, "clock_s": 600.0, "team_side": "H", "points": 0, "fg3a": 0,
            "fg3m": 0, "heave3": 0, "fta": 0, "ftm": 0, "pf": 0}
    return pd.DataFrame([{**cols, **r} for r in rows])


def test_first_half_is_periods_one_and_two_and_a_heave_is_no_attempt():
    p = _plays([
        {"period": 1, "fg3a": 1, "fg3m": 1, "points": 3},
        {"period": 2, "clock_s": 1.0, "heave3": 1},              # a missed heave at the end of Q2
        {"period": 2, "clock_s": 200.0, "points": 2, "team_side": "A"},
        {"period": 3, "fg3a": 1, "points": 0},                    # after the half
    ])
    h = T.halves_from_plays(p).iloc[0]
    assert h["h_points_h1"] == 3 and h["h_fg3a_h1"] == 1
    assert h["h_fg3a_game"] == 2                                  # the heave is not an attempt anywhere
    assert h["a_points_q2l5"] == 2


def _train(rng, season, rest):
    n = 400
    x = pd.DataFrame({f: rng.normal(size=n) for f in T.FEATS["totals"]})
    return x.assign(season=season, h_pts=50.0, a_pts=50.0, h1_total=100.0, rest_totals=rest)


def test_the_model_for_a_season_is_fit_on_earlier_seasons_only():
    rng = np.random.default_rng(0)
    train = pd.concat([_train(rng, 2022, 120.0), _train(rng, 2023, 0.0)], ignore_index=True)
    test = _train(rng, 2023, np.nan).iloc[:5]
    num, info = T.model_numbers(train, test, "totals")
    assert np.allclose(num, 100.0 + 120.0, atol=1e-6)            # 2023's own rows played no part
    assert info[2023][0] == 400


def test_only_2020_21_may_be_fit_on_itself():
    rng = np.random.default_rng(1)
    reg = _train(rng, 2021, 90.0)
    num, info = T.model_numbers(reg, reg.iloc[:3], "totals")
    assert np.allclose(num, 190.0) and "own season" in info[2021][1]
    with pytest.raises(ValueError):
        T.model_numbers(_train(rng, 2023, 90.0), _train(rng, 2023, 90.0).iloc[:3], "totals")


FETCH = pd.Timestamp("2025-01-10T02:00:00Z")


def _quote(**kw):
    base = {"game_id": "G", "market": "totals", "book": "draftkings", "phase": "halftime",
            "coherent": True, "pin_fa": 0.5, "pts_since_stamp": 0.0, "fetch_at": FETCH,
            "stamp": FETCH - pd.Timedelta(minutes=5), "pin_stamp": FETCH - pd.Timedelta(minutes=5)}
    return {**base, **kw}


def _pin(**kw):
    return _quote(book="pinnacle", **kw)


def test_the_decision_set_is_fresh_halftime_deciding_quotes_from_the_first_purchase():
    later = FETCH + pd.Timedelta(minutes=10)
    q = pd.DataFrame([
        _pin(),
        _quote(book="draftkings"),                                          # kept
        _quote(book="fanduel", pts_since_stamp=2.0),                        # scored after its stamp
        _quote(book="betmgm", phase="live"),                                # not inside the break
        _quote(book="bovada"),                                              # never a deciding book
        _pin(game_id="G2", pts_since_stamp=1.0),                            # G2's Pinnacle is stale
        _quote(game_id="G2", book="draftkings"),
        _pin(fetch_at=later, stamp=later - pd.Timedelta(minutes=1)),
        _quote(book="betrivers", fetch_at=later, stamp=later - pd.Timedelta(minutes=1),
               pin_stamp=later - pd.Timedelta(minutes=1)),                  # a later purchase
    ])
    d = T.decision_quotes(q)
    assert sorted(zip(d["game_id"], d["book"])) == [("G", "draftkings")]


def _dist(seed=3, n=2000, sd=12.0):
    r = np.random.default_rng(seed).normal(0, sd, size=n)
    return H.ResidDist(np.concatenate([r, -r]), "test")          # symmetric: even money at the number


def test_a_spread_centre_is_the_home_margin_and_the_strength_points_home():
    dists = {(2024, "spreads"): _dist(), (2024, "totals"): _dist()}
    mu = T.centre(["spreads", "totals"], [-3.5, 220.5], [0.5, 0.5], [2024, 2024], dists)
    assert mu[0] == pytest.approx(3.5, abs=0.05) and mu[1] == pytest.approx(220.5, abs=0.05)
    dg = pd.DataFrame({"game_id": ["G"], "market": ["spreads"], "mu_model": [6.0], "mu_pin": [mu[0]]})
    sig = T.strength_signal(dg)
    from scripts.nba_game2_luck import side_strength
    off = pd.DataFrame({"game_id": ["G", "G"], "market": ["spreads", "spreads"], "side": ["home", "away"]})
    s = side_strength(off, sig).set_index("side")["strength"]
    assert s["home"] == pytest.approx(2.5, abs=0.05) and s["away"] == pytest.approx(-2.5, abs=0.05)
    # and a home -3.5 that wins by 5 is a win (the harness's settlement, the full-game score)
    g = H.grade(pd.DataFrame({"game_id": ["G"], "market": ["spreads"], "side": ["home"],
                              "line": [-3.5], "price": [-110.0]}),
                pd.DataFrame({"game_id": ["G"], "home_score": [105], "away_score": [100]}))
    assert g["result"].iloc[0] == "W"


def _info_rows(informative: bool, seasons=(2021, 2022, 2023, 2024, 2025, 2026), per_day=6,
               days=120, seed=5):
    rng = np.random.default_rng(seed)
    out = []
    for s in seasons:
        n = per_day * days
        signal = rng.normal(0, 4, size=n)
        noise = rng.normal(0, 12, size=n)
        mu_ref = 220.0 + rng.normal(0, 3, size=n)
        y = mu_ref + (signal if informative else 0.0) + noise
        mu_model = mu_ref + signal
        out.append(pd.DataFrame({"season": s, "game_date": np.repeat([f"{s}-{d}" for d in range(days)], per_day),
                                 "y": y, "mu_ref": mu_ref, "mu_model": mu_model}))
    return pd.concat(out, ignore_index=True)


def test_a_model_that_knows_something_gives_an_interval_above_zero():
    r = T.info_summary(T.mse_drop_rows(_info_rows(True)))
    assert r["choose"]["lo"] > 0 and r["confirm"]["lo"] > 0 and r["information"]
    assert r["beta"][2022] == pytest.approx(1.0, abs=0.2)


def test_the_combining_weight_for_a_season_is_fit_on_earlier_seasons_only():
    info = _info_rows(True, seasons=(2021,), days=600)
    noise = _info_rows(False, seasons=(2022, 2023), days=600, seed=9)
    d = T.mse_drop_rows(pd.concat([info, noise], ignore_index=True))
    beta = d.groupby("season")["beta"].first()
    assert beta[2022] == pytest.approx(1.0, abs=0.2)               # 2021 alone: its signal is real
    assert beta[2023] < 0.75                                       # 2022's noise now in the fit


def test_noise_gives_no_information():
    r = T.info_summary(T.mse_drop_rows(_info_rows(False)))
    assert not r["information"] and r["choose"]["lo"] < 0


def test_a_market_opens_only_when_both_intervals_lie_above_zero():
    d = T.mse_drop_rows(_info_rows(True))
    d.loc[d["season"] == 2026, "d"] = -d.loc[d["season"] == 2026, "d"].abs()   # 2025-26 says no
    r = T.info_summary(d)
    assert r["choose"]["lo"] > 0 and r["confirm"]["hi"] < 0 and not r["information"]


def test_the_halftime_distribution_refuses_a_choosing_season_without_enough_earlier_games():
    rng = np.random.default_rng(2)

    def rows(season, n):
        return pd.DataFrame({"season": season, "market": "totals", "pin_line": 220.5,
                             "final_home": 110 + rng.integers(-15, 15, n),
                             "final_away": 110 + rng.integers(-15, 15, n)})
    ok = pd.concat([rows(2021, 200), rows(2022, 200)], ignore_index=True)
    assert "(prior)" in T.ht_dists(ok, [2021, 2022])[(2022, "totals")].label
    thin = pd.concat([rows(2021, 100), rows(2022, 200)], ignore_index=True)
    with pytest.raises(ValueError):
        T.ht_dists(thin, [2021, 2022])
