"""The anchored first-quarter props lab (docs/nba_search_q1anchor.md): the anchor is read from the proposition's own
fetch, the consensus needs three books and leaves Pinnacle out, kind C holds only propositions with no Pinnacle
quote, the share reads only earlier games, the fits never read a row with no share, and the 36 cells reach the
harness with the placebo's identity run equal to the real bets."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts import nba_prop_market_lab as ML
from scripts import nba_s_q1anchor as A

T1 = pd.Timestamp("2025-01-10T23:05:00Z")
T2 = pd.Timestamp("2025-01-10T23:40:00Z")
T3 = pd.Timestamp("2025-01-10T22:50:00Z")


def _qm(rows):
    return pd.DataFrame(rows, columns=["game_id", "player_id", "base", "T", "bookmaker", "mu"])


def test_a_proposition_takes_its_own_fetch_and_another_row_the_latest():
    qm = _qm([("G1", "p1", "player_points", T1, "pinnacle", 20.0),
              ("G1", "p1", "player_points", T2, "pinnacle", 24.0),
              ("G1", "p1", "player_rebounds", T1, "pinnacle", 8.0),
              ("G1", "p1", "player_rebounds", T2, "pinnacle", 9.0),
              ("G1", "p2", "player_points", T2, "pinnacle", 15.0)])
    anc = A.anchors(qm)
    # with_props stores T as naive UTC (its .values drop the zone); the full-game anchors carry UTC
    props = pd.DataFrame({"game_id": ["G1", "G1"], "player_id": ["p1", "p2"],
                          "market": ["player_points_q1", "player_points_q1"],
                          "T": pd.DatetimeIndex([T1, T3]).tz_convert(None).values})
    fit = pd.DataFrame({"game_id": ["G1", "G1", "G1"], "player_id": ["p1", "p1", "p2"],
                        "stat": ["points", "rebounds", "points"]})
    f = A.fit_anchors(fit, anc, props).set_index(["player_id", "stat"])
    assert f.loc[("p1", "points"), "mu_P"] == 20.0          # its own fetch, not the later 24
    assert f.loc[("p1", "rebounds"), "mu_P"] == 9.0         # no rebounds proposition: the latest fetch
    assert np.isnan(f.loc[("p2", "points"), "mu_P"])         # its own fetch holds no Pinnacle quote: no anchor
    assert bool(f.loc[("p1", "points"), "is_prop"]) and not bool(f.loc[("p1", "rebounds"), "is_prop"])


def test_the_consensus_needs_three_other_books_and_never_counts_pinnacle():
    key = ("G1", "p1", "player_points", T1)
    two = A.anchors(_qm([(*key, "pinnacle", 20.0), (*key, "fanduel", 18.0), (*key, "hardrockbet", 22.0)]))
    assert two.n_C.iloc[0] == 2 and np.isnan(two.mu_C.iloc[0]) and two.mu_P.iloc[0] == 20.0
    three = A.anchors(_qm([(*key, "pinnacle", 20.0), (*key, "fanduel", 18.0), (*key, "hardrockbet", 22.0),
                           (*key, "betmgm", 30.0)]))
    assert three.n_C.iloc[0] == 3 and three.mu_C.iloc[0] == 22.0     # the median of 18, 22, 30; Pinnacle left out


def _fits():
    return A.Fits(factor={}, alpha={(k, v, s, 2025): 0.0 for k in A.KINDS for v in A.VARIANTS for s in A.STATS},
                  maps={})


def test_kind_c_holds_only_propositions_with_no_pinnacle_quote():
    props = pd.DataFrame({"prop_id": [0, 1], "game_id": ["G1", "G1"], "player_id": ["p1", "p2"],
                          "market": ["player_points_q1"] * 2, "season": [2025, 2025]})
    f = pd.DataFrame({"game_id": ["G1", "G1"], "player_id": ["p1", "p2"], "stat": ["points", "points"],
                      "is_prop": [True, True], "mu_P": [20.0, np.nan],
                      "mu_consensus_model": [5.0, 4.0], "mu_pinnacle_model": [5.2, np.nan]})
    c = A.kind_props(props, f, _fits(), "consensus", "model").set_index("prop_id")
    assert not c.loc[0, "has_number"] and c.loc[1, "has_number"] and c.loc[1, "mu"] == 4.0
    p = A.kind_props(props, f, _fits(), "pinnacle", "model").set_index("prop_id")
    assert p.loc[0, "has_number"] and not p.loc[1, "has_number"]


def _pg(dates, q1_min, full_min, player="p1"):
    return pd.DataFrame({"player_id": player, "date": pd.to_datetime(dates), "q1_sec": np.array(q1_min) * 60.0,
                         "minutes": full_min, "court_ok": True})


def test_the_share_reads_only_earlier_games_and_needs_three():
    pg = _pg(["2025-01-01", "2025-01-03", "2025-01-05", "2025-01-07"], [9.0, 6.0, 12.0, 3.0],
             [36.0, 30.0, 40.0, 20.0])
    h = A.share_history(pg)
    t = A.shares(pd.DataFrame({"player_id": ["p1", "p1"], "date": pd.to_datetime(["2025-01-05", "2025-01-07"])}), h)
    assert t.n_sh.iloc[0] == 2 and np.isnan(t.share.iloc[0])     # the game of 01-05 itself is not read
    w = pd.Series([9.0, 6.0, 12.0]).ewm(halflife=A.HALF_LIFE).mean().iloc[-1]
    m = pd.Series([36.0, 30.0, 40.0]).ewm(halflife=A.HALF_LIFE).mean().iloc[-1]
    assert t.n_sh.iloc[1] == 3 and t.share.iloc[1] == pytest.approx(w / m)


def test_a_game_without_first_quarter_court_time_is_not_in_the_share():
    pg = _pg(["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04"], [9.0, 0.0, 9.0, 9.0],
             [36.0, 12.0, 36.0, 36.0])
    t = A.shares(pd.DataFrame({"player_id": ["p1"], "date": pd.to_datetime(["2025-01-05"])}), A.share_history(pg))
    assert t.n_sh.iloc[0] == 3 and t.share.iloc[0] == pytest.approx(0.25)


def test_the_fits_never_read_a_row_without_a_share():
    rows = []
    for i in range(40):
        rows.append({"season": 2024, "stat": "points", "y": 2.0, "ok_settled": True, "share": 0.25, "mu_P": 10.0,
                     "mu_C": 10.0})
        # a 2024 row with no share whose result would move the factor if it were read
        rows.append({"season": 2024, "stat": "points", "y": 50.0, "ok_settled": True, "share": np.nan,
                     "mu_P": 10.0, "mu_C": 10.0})
        rows.append({"season": 2025, "stat": "points", "y": 100.0, "ok_settled": True, "share": 0.25,
                     "mu_P": 10.0, "mu_C": 10.0})
    for s in ("rebounds", "assists"):
        for i in range(40):
            rows.append({"season": 2024, "stat": s, "y": 1.0, "ok_settled": True, "share": 0.25, "mu_P": 4.0,
                         "mu_C": 4.0})
            rows.append({"season": 2025, "stat": s, "y": 1.0, "ok_settled": True, "share": 0.25, "mu_P": 4.0,
                         "mu_C": 4.0})
    f, fits = A.means(pd.DataFrame(rows))
    assert fits.factor[("pinnacle", "model", "points", 2025)] == pytest.approx(0.8)     # 2 / (10 x 0.25)
    pts25 = f[(f.season == 2025) & (f.stat == "points")]
    assert np.allclose(pts25.mu_pinnacle_model, 2.0)                                   # 2025's own 100s never read
    assert np.isnan(f[f.share.isna()].mu_pinnacle_model).all()


def test_a_quote_mean_inverts_the_count_table():
    rng = np.random.default_rng(3)
    log = pd.DataFrame({"player_id": np.repeat(np.arange(30), 60), "season": 2024,
                        "minutes": 30.0, "points": rng.poisson(18.0, 1800), "rebounds": rng.poisson(6.0, 1800),
                        "assists": rng.poisson(4.0, 1800)})
    tab = ML.NBTable(ML.nb_alpha(log, "player_points", 2025), np.array([19.5]))
    p = float(tab.p_over(np.array([19.5]), np.array([20.0]))[0])
    q = pd.DataFrame({"base": ["player_points"], "season": [2025], "line": [19.5], "od": [1.0 / p],
                      "ud": [1.0 / (1.0 - p)]})
    assert A.quote_means(q, log).mu.iloc[0] == pytest.approx(20.0, abs=0.02)


def test_the_36_cells_reach_the_harness_and_the_placebo_identity_holds():
    out = A.synthetic_checks(n_placebo=1)
    assert out["synthetic_checks"] == "pass"
