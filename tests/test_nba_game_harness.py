"""scripts/nba_game_harness: the rules every cell of the second NBA game-market
search is graded under (docs/nba_models_2026.md §6.2), checked on small games
built by hand so each rule is pinned by its outcome, not by its code."""
import numpy as np
import pandas as pd
import pytest

from scripts import nba_game_harness as H

TIP = pd.Timestamp("2024-01-16T00:30:00Z")      # 7:30 ET on 2024-01-15


def _games():
    return pd.DataFrame([{"game_id": "G", "season": 2024, "game_date": "2024-01-15",
                          "tip": TIP, "home_team": "BOS", "away_team": "NYK",
                          "home_score": 110, "away_score": 100}])


def _fetches(*leads):
    return pd.DataFrame({"game_id": "G", "tip": TIP,
                         "fetch_at": [TIP - pd.Timedelta(minutes=m) for m in leads],
                         "lead_min": [float(m) for m in leads]})


def _q(book, market, fetch_lead, snap_lead, line, pa, pb):
    return {"game_id": "G", "season": 2024, "game_date": "2024-01-15", "tip": TIP,
            "market": market, "book": book,
            "fetch_at": TIP - pd.Timedelta(minutes=fetch_lead),
            "snapshot_at": TIP - pd.Timedelta(minutes=snap_lead),
            "line": line, "price_a": pa, "price_b": pb, "coherent": True}


def test_each_point_takes_the_newest_fetch_in_its_window_never_the_last_15_minutes():
    f = _fetches(570, 300, 210, 150, 90, 60, 30, 10)
    g = _games()
    got = {p: H.decision_times(f, g, p)["lead_min"].tolist() for p in ("B", "C", "D")}
    assert got == {"B": [210.0], "C": [60.0], "D": [60.0]}
    # nothing between 45 and 75 -> the game has no D decision at all
    assert H.decision_times(_fetches(90, 30, 10), g, "D").empty


def test_point_a_is_the_15z_fetch_on_the_eastern_game_date():
    # 15Z on 2024-01-15 is 570 minutes before a 00:30Z tip on the 16th
    t = H.decision_times(_fetches(600, 570, 300), _games(), "A")
    assert t["T"].tolist() == [pd.Timestamp("2024-01-15T15:00:00Z")]


def test_a_later_fetch_is_invisible_and_an_hour_old_quote_is_stale():
    q = pd.DataFrame([
        _q("fanduel", "spreads", 60, 66, -5.5, -110, -110),       # the fetch at T
        _q("fanduel", "spreads", 30, 64, -6.5, -110, -110),       # later fetch, older stamp
        _q("betmgm", "spreads", 150, 140, -5.0, -110, -110),      # 80 min before T: stale
        _q("caesars", "spreads", 90, 100, -5.0, -105, -115),      # 40 min before T: fresh
    ])
    t = pd.DataFrame({"game_id": ["G"], "T": [TIP - pd.Timedelta(minutes=60)]})
    v = H.visible(q, t).set_index("book")
    assert set(v.index) == {"fanduel", "caesars"}
    assert v.loc["fanduel", "line"] == -5.5


def test_a_push_returns_the_stake_and_leaves_the_denominator():
    g = _games()                                      # home by 10
    bets = pd.DataFrame([
        {"game_id": "G", "season": 2024, "game_date": "2024-01-15", "market": "spreads",
         "side": "home", "line": -10.0, "price": -110.0},       # push
        {"game_id": "G", "season": 2024, "game_date": "2024-01-15", "market": "spreads",
         "side": "home", "line": -9.5, "price": -110.0},        # win 1u, risk 1.1
    ])
    b = H.grade(bets, g)
    assert b["result"].tolist() == ["P", "W"]
    assert b["units"].tolist() == pytest.approx([0.0, 1.0])
    assert H.roi(b) == pytest.approx(1.0 / 1.1)
    assert H.roi(b, kept=True) == pytest.approx(1.0 / 2.2)


def test_the_spread_side_uses_the_home_number():
    # home margin ~ N(+8, 12): home -6.5 should be a favourite to cover,
    # away +6.5 (stored line still -6.5) the complement
    pw, pp = H.side_probs(np.array(["spreads", "spreads"]), np.array(["home", "away"]),
                          np.array([-6.5, -6.5]), mu=[8.0, 8.0], sigma=[12.0, 12.0])
    assert pw[0] > 0.5 and pw[0] + pw[1] == pytest.approx(1.0) and pp.tolist() == [0.0, 0.0]


def _offers():
    rows = [
        # side, book, line, price, p_win
        ("home", "draftkings", -5.5, -110, 0.56),
        ("home", "fanduel", -4.5, -115, 0.60),     # better number, better EV
        ("home", "pinnacle", -4.5, 105, 0.60),     # never deciding
        ("away", "betmgm", -4.5, -250, 0.85),      # best EV of all, but below the -200 floor
    ]
    return pd.DataFrame([{"game_id": "G", "season": 2024, "game_date": "2024-01-15",
                          "T": TIP - pd.Timedelta(minutes=60), "market": "spreads",
                          "side": s, "book": b, "line": l, "price": float(p),
                          "p_win": w, "p_push": 0.0} for s, b, l, p, w in rows])


def test_the_best_ev_offer_wins_across_books_and_numbers_within_the_house_rules():
    pick = H.choose(_offers(), cut=0.0)
    assert len(pick) == 1 and pick.iloc[0]["book"] == "fanduel"
    dk = H.choose(_offers(), cut=0.0, books=("draftkings",))
    assert dk.iloc[0]["book"] == "draftkings"
    assert H.choose(_offers(), cut=0.20).empty


def test_bh_counts_the_untested_cells_in_m():
    p = {"a": 1e-6, "b": 2e-5, "c": 0.01}
    assert H.bh_pass(p, m_total=3) == {"a", "b", "c"}
    # at m = 4,172 the bar for rank 1 is 1.2e-5 and for rank 2 is 2.4e-5
    assert H.bh_pass(p, m_total=4172) == {"a", "b"}
    assert H.bh_pass({"a": 2e-5}, m_total=4172) == set()


def test_rows_join_their_fetch_on_created_at_and_strays_take_the_next_fetch():
    q = pd.DataFrame({"created_at": ["2026-10-15 22:59:14.314171+00", "2026-10-16 01:00:00+00"],
                      "snapshot_at": pd.to_datetime(["2024-01-15T22:54:00Z",
                                                     "2024-01-15T23:20:00Z"], utc=True)})
    led = pd.DataFrame({"requested_at": pd.to_datetime(["2024-01-15T23:00:00Z",
                                                        "2024-01-15T23:30:00Z"], utc=True),
                        "pulled_at": pd.to_datetime(["2026-10-15 22:59:14.314171+00",
                                                     "2026-10-17 00:00:00+00"], utc=True,
                                                    format="mixed")})
    out, notes = H.attach_fetch(q, led)
    assert out["fetch_at"].tolist() == [pd.Timestamp("2024-01-15T23:00:00Z"),
                                        pd.Timestamp("2024-01-15T23:30:00Z")]
    assert notes["rows_matched_on_created_at"] == 1 and notes["rows_placed_by_snapshot"] == 1


def test_an_unmatched_best_price_is_an_outlier_and_a_matched_one_is_not():
    off = _offers()
    off = off[off["book"] != "pinnacle"]
    bets = pd.DataFrame([off.iloc[1]])                          # fanduel -4.5 -115, alone at -4.5
    assert bool(H.outlier_flag(bets, off).iloc[0]) is True
    # a second deciding book (Caesars is williamhill_us in the feed), 5 cents worse
    twin = off.iloc[[1]].assign(book="williamhill_us", price=-120.0)
    assert bool(H.outlier_flag(bets, pd.concat([off, twin])).iloc[0]) is False


def test_the_bootstrap_is_seeded_and_refines_small_p(monkeypatch):
    rng = np.random.default_rng(0)
    days = pd.date_range("2025-10-21", periods=150).astype(str)
    b = pd.DataFrame({"game_date": np.repeat(days, 4), "units": 0.0, "risk": 1.1})
    b["units"] = np.where(rng.random(len(b)) < 0.75, 1.0, -1.1)     # a huge edge
    calls = []
    real = H.boot
    monkeypatch.setattr(H, "boot", lambda x, n=H.N_BOOT, seed=H.SEED: calls.append(n) or real(x, n, seed))
    assert H.p_one_sided(b) < H.P_REFINE_BELOW
    assert calls == [H.N_BOOT, H.P_REFINE_N]
    assert np.array_equal(real(b), real(b))


def test_the_arithmetic_checks_pass():
    H.check()


# ── the market's fair line, the placebo, and one whole cell ──────────────────

def _vis(rows):
    return pd.DataFrame([{"game_id": g, "season": 2024, "game_date": "2024-01-15", "tip": TIP,
                          "market": m, "book": b, "line": l, "price_a": a, "price_b": bb,
                          "coherent": True, "T": TIP - pd.Timedelta(minutes=60)}
                         for g, m, b, l, a, bb in rows])


def test_market_fair_prefers_pinnacle_and_falls_back_to_the_book_median():
    sig = {(2024, "spreads"): 12.0}
    v = _vis([("G", "spreads", "pinnacle", -5.0, -105, -105),
              ("G", "spreads", "fanduel", -7.0, -110, -110),
              ("G2", "spreads", "fanduel", -3.0, -110, -110),
              ("G2", "spreads", "betmgm", -4.0, -110, -110),
              ("G2", "h2h", "fanduel", None, -150, 130)])
    f = H.market_fair(v, sig).set_index(["game_id", "market"])
    # an even no-vig price at -5 puts the home margin's centre at +5
    assert f.loc[("G", "spreads"), "ref"] == "pinnacle"
    assert f.loc[("G", "spreads"), "mu"] == pytest.approx(5.0, abs=1e-6)
    assert f.loc[("G2", "spreads"), "ref"] == "consensus"
    assert f.loc[("G2", "spreads"), "mu"] == pytest.approx(3.5, abs=1e-6)
    ph = f.loc[("G2", "h2h"), "p_home"]
    assert 0.55 < ph < 0.6


def test_the_placebo_moves_parameters_only_between_games_on_the_same_date():
    games = pd.DataFrame({"game_id": ["a", "b", "c"],
                          "game_date": ["2024-01-15", "2024-01-15", "2024-01-16"]})
    fair = pd.DataFrame({"game_id": ["a", "b", "c"], "market": "spreads",
                         "mu": [1.0, 2.0, 3.0], "sigma": 12.0, "p_home": np.nan})
    seen = set()
    for seed in range(20):
        sh = H.shuffle_within_date(fair, games, np.random.default_rng(seed)).set_index("game_id")
        assert sh.loc["c", "mu"] == 3.0                  # alone on its date
        assert {sh.loc["a", "mu"], sh.loc["b", "mu"]} == {1.0, 2.0}
        seen.add(sh.loc["a", "mu"])
    assert seen == {1.0, 2.0}


def test_one_whole_cell_grades_a_model_bet_against_its_blind_side():
    # two games; the model is sure the home side covers -4.5 in both; the
    # home team covers in G (by 10) and not in G2 (by 2)
    games = pd.DataFrame([
        {"game_id": "G", "season": 2024, "game_date": "2024-01-15", "tip": TIP,
         "home_team": "BOS", "away_team": "NYK", "home_score": 110, "away_score": 100},
        {"game_id": "G2", "season": 2024, "game_date": "2024-01-16", "tip": TIP + pd.Timedelta(days=1),
         "home_team": "LAL", "away_team": "DEN", "home_score": 102, "away_score": 100}])
    q = pd.DataFrame([_q("fanduel", "spreads", 60, 66, -4.5, -110, -110),
                      _q("draftkings", "spreads", 60, 66, -4.5, -112, -108)])
    q2 = q.assign(game_id="G2", game_date="2024-01-16", tip=TIP + pd.Timedelta(days=1),
                  fetch_at=q["fetch_at"] + pd.Timedelta(days=1),
                  snapshot_at=q["snapshot_at"] + pd.Timedelta(days=1))
    quotes = pd.concat([q, q2], ignore_index=True)
    f = quotes[["game_id", "tip", "fetch_at"]].drop_duplicates()
    f = f.assign(lead_min=(f["tip"] - f["fetch_at"]).dt.total_seconds() / 60)
    data = H.Data(games=games, quotes=quotes, fetches=f)
    t, off = H.point_offers(data, "D")
    assert len(t) == 2
    model = pd.DataFrame({"game_id": ["G", "G2"], "market": "spreads", "mu": [9.0, 9.0],
                          "sigma": 12.0, "p_home": np.nan})
    cand = H.fair_offers(off, model)
    neutral = H.fair_offers(off, H.market_fair(H.visible(quotes, t), {(2024, "spreads"): 12.0}))
    rows = H.run_cells(data, "test", "D", cand, neutral, cuts=[0.0, 0.5],
                       sides_by_market={"spreads": ["home"]})
    r0, r1 = rows
    assert r0["n_choose"] == 2 and r1["n_choose"] == 0
    # best price is fanduel -110 on both: +1 unit then -1.1 units
    assert r0["units_choose"] == pytest.approx(1.0 - 1.1)
    assert r0["dk_n_choose"] == 2
    assert r0["blind_roi_choose"] == pytest.approx((1.0 - 1.1) / 2.2)


def test_a_family_can_choose_on_fewer_seasons():
    games = pd.DataFrame([{"game_id": f"G{s}", "season": s, "game_date": f"{s - 1}-12-01",
                           "tip": pd.Timestamp(f"{s - 1}-12-02T00:00:00Z"), "home_team": "BOS",
                           "away_team": "NYK", "home_score": 110, "away_score": 100}
                          for s in (2022, 2024, 2026)])
    bets = pd.DataFrame([{"game_id": f"G{s}", "season": s, "game_date": f"{s - 1}-12-01",
                          "T": pd.Timestamp(f"{s - 1}-12-01T23:00:00Z"), "market": "h2h",
                          "side": "home", "line": np.nan, "book": "fanduel", "price": -110.0}
                         for s in (2022, 2024, 2026)])
    g = H.grade(bets, games)
    data = H.Data(games=games, quotes=pd.DataFrame(columns=["game_id", "market", "book", "snapshot_at",
                                                            "fetch_at", "line", "price_a", "price_b",
                                                            "coherent"]),
                  fetches=pd.DataFrame(columns=["game_id", "tip", "fetch_at", "lead_min"]))
    assert H.cell_report(g, data)["choose"]["bets"] == 2
    r = H.cell_report(g, data, choose_seasons=(2024, 2025))
    assert r["choose"]["bets"] == 1 and r["confirm"]["bets"] == 1


def test_a_per_game_purchase_is_dated_by_its_own_stamp(tmp_path):
    games = _games()
    rows = [{"game_id": "G", "market": "team_totals_home", "bookmaker": "fanduel",
             "snapshot_type": "open", "snapshot_at": (TIP - pd.Timedelta(minutes=m)).isoformat(),
             "source": H.PER_EVENT_SOURCE, "created_at": "2026-10-16 00:00:00+00",
             "home_price": None, "away_price": None, "spread_home": None, "total_line": 112.5,
             "over_price": -110.0, "under_price": -110.0} for m in (65, 20)]
    pd.DataFrame(rows).to_parquet(tmp_path / "nba_odds.parquet")
    pe = H.load_per_event(games, cache=tmp_path)
    assert (pe["fetch_at"] == pe["snapshot_at"]).all() and len(pe) == 2
    t = H.per_event_times(pe, "D")
    # 65 minutes out is inside 45-75; 20 minutes out is not a D decision
    assert t["lead_min"].tolist() == [65.0]


def test_a_per_game_side_takes_each_games_side_pick_and_settles_on_the_real_side():
    # G: the rule says away; G2: the rule says home; G3: no side at all
    off = pd.concat([_offers().assign(game_id=g) for g in ("G", "G2", "G3")], ignore_index=True)
    off = off[(off["book"] == "fanduel") | (off["side"] == "away")]
    off.loc[off["side"] == "away", "price"] = -110.0
    off["side_pick"] = off["game_id"].map({"G": "away", "G2": "home"})
    pick = H.choose(off, cut=-np.inf, sides=["fade"]).set_index("game_id")
    assert pick["side"].to_dict() == {"G": "away", "G2": "home"}
    # a real side still means that side, side_pick or not
    assert set(H.choose(off, cut=-np.inf, sides=["home"])["side"]) == {"home"}
    games = pd.concat([_games(), _games().assign(game_id="G2")], ignore_index=True)
    g = H.grade(pick.reset_index(), games).set_index("game_id")
    # home won by 10: away +4.5 loses, home -4.5 covers
    assert g["result"].to_dict() == {"G": "L", "G2": "W"}
    with pytest.raises(KeyError):
        H.choose(off.drop(columns="side_pick"), cut=-np.inf, sides=["fade"])


# ── the empirical distribution, the D gate, bar 9 by real side, stale caches ──

def test_the_empirical_model_matches_the_normal_one_on_normal_residuals():
    rng = np.random.default_rng(3)
    r = np.round(rng.normal(0, 12, 8000) * 2) / 2           # half-point residuals
    dist = H.ResidDist(r, "test")
    mu = np.array([0.0, 3.3, -5.1, 7.9])
    for t in (np.array([0.5, 2.5, -4.5, 8.5]), np.array([0.0, 3.0, -5.0, 8.0])):
        we, pe, _ = dist.probs(mu, t)
        wn, pn, _ = H.probs_at(mu, np.full(4, 12.0), t)
        assert np.allclose(we, wn, atol=0.015) and np.allclose(pe, pn, atol=0.01)


def test_whole_lines_carry_push_mass_and_half_lines_none():
    dist = H.ResidDist(np.random.default_rng(1).normal(0, 12, 5000), "t")
    _, p_whole, _ = dist.probs(np.array([0.3]), np.array([0.0]))
    _, p_half, _ = dist.probs(np.array([0.3]), np.array([0.5]))
    assert 0.015 < p_whole[0] < 0.05 and p_half[0] == 0.0


def test_a_skewed_distribution_is_not_read_as_normal():
    # results land 4 above the centre 70% of the time and 9 below otherwise
    dist = H.ResidDist(np.r_[np.full(700, 4.0), np.full(300, -9.0)], "skew")
    w, _, _ = dist.probs(np.array([0.0]), np.array([0.5]))
    assert w[0] == pytest.approx(0.70, abs=1e-6)


def test_the_centre_solver_inverts_either_model():
    dist = H.ResidDist(np.random.default_rng(2).normal(0, 12, 8000), "t")
    sig = np.array([dist, dist, 12.0, 12.0], dtype=object)
    t = np.array([-4.5, 6.0, -4.5, 6.0])
    p = np.array([0.6, 0.35, 0.6, 0.35])
    mu = H.solve_any(t, p, sig)
    w, _, l = H.probs_any(mu, sig, t)
    assert np.allclose(w / (w + l), p, atol=1e-4)


def test_the_placebo_moves_a_distribution_by_reference():
    d1, d2 = (H.ResidDist(np.random.default_rng(i).normal(0, 12, 500), f"d{i}") for i in (1, 2))
    games = pd.DataFrame({"game_id": ["a", "b"], "game_date": ["2024-01-15"] * 2})
    fair = pd.DataFrame({"game_id": ["a", "b"], "market": "spreads", "mu": [1.0, 2.0],
                         "sigma": pd.Series([d1, d2], dtype=object), "p_home": np.nan})
    for seed in range(10):
        sh = H.shuffle_within_date(fair, games, np.random.default_rng(seed)).set_index("game_id")
        assert {id(sh.loc["a", "sigma"]), id(sh.loc["b", "sigma"])} == {id(d1), id(d2)}
        assert sh["mu"].dtype == float
        # a game's centre and its distribution travel together
        assert (sh.loc["a", "mu"] == 1.0) == (sh.loc["a", "sigma"] is d1)


def _cov_data(reached_2022, n=40):
    """Games in 2022 and 2023; D reached on `reached_2022` of 2022's n, all of 2023's."""
    rows, fetch = [], []
    for s in (2022, 2023):
        for i in range(n):
            gid = f"{s}_{i}"
            tip = pd.Timestamp(f"{s - 1}-12-01T00:00:00Z") + pd.Timedelta(days=i)
            rows.append({"game_id": gid, "season": s, "game_date": str((tip - pd.Timedelta(hours=5)).date()),
                         "tip": tip, "home_team": "BOS", "away_team": "NYK",
                         "home_score": 100, "away_score": 90})
            lead = 60 if (s == 2023 or i < reached_2022) else 90
            fetch.append({"game_id": gid, "tip": tip, "fetch_at": tip - pd.Timedelta(minutes=lead),
                          "lead_min": float(lead)})
    return H.Data(games=pd.DataFrame(rows), quotes=pd.DataFrame(), fetches=pd.DataFrame(fetch))


def test_a_season_short_of_95_percent_at_d_is_not_chosen_on():
    data = _cov_data(reached_2022=37)                       # 92.5%
    cov = H.point_coverage(data, "D")
    assert cov[2022] == pytest.approx(0.925) and cov[2023] == 1.0
    assert H.gated_seasons(cov, (2022, 2023), "D") == ((2023,), [2022])
    # the gate is the D point's alone
    assert H.gated_seasons(cov, (2022, 2023), "C") == ((2022, 2023), [])
    assert H.gated_seasons(H.point_coverage(_cov_data(38), "D"), (2022, 2023), "D")[1] == []


def test_the_favourite_comes_from_the_market_fair_line():
    neutral = pd.DataFrame({"game_id": ["a", "b", "c", "d"], "market": ["h2h", "h2h", "spreads", "spreads"],
                            "mu": [np.nan, np.nan, 3.0, 0.0], "p_home": [0.62, 0.40, np.nan, np.nan]})
    f = H.fav_sides(neutral).set_index("game_id")
    assert f.loc["a", "fav"] == "home" and f.loc["b", "fav"] == "away" and f.loc["c", "fav"] == "home"
    assert "d" not in f.index                                # a level line has no favourite


def test_bar_9_compares_a_one_sided_cell_with_that_side_over_its_own_population():
    off = _offers()
    off = off[off["book"].isin(["fanduel", "draftkings"])]
    away = off.iloc[[1]].assign(side="away", price=-105.0, p_win=0.40)
    off = pd.concat([off, away], ignore_index=True).assign(mu=4.0, p_home=np.nan)
    pop_other = off.assign(game_id="OUTSIDE")
    nm = pd.concat([off, pop_other], ignore_index=True)
    games = pd.concat([_games(), _games().assign(game_id="OUTSIDE", home_score=90)], ignore_index=True)
    b = H.blind_by_real_side(nm, {"G"}, games, seasons=(2024,))
    # only G is in the population: home covers -4.5 there (by 10), so blind home wins
    assert b["home"] > 0 and b["fav"] == b["home"] and b["away"] < 0
    bets = H.grade(H.choose(off, -np.inf, sides=["home"]), _games())
    sh = H.real_side_shares(bets, off)
    assert sh["home"] == 1.0 and sh["fav"] == 1.0


def test_bar_9_runs_for_a_rule_whose_frame_carries_its_per_game_side():
    # A rule that bets a different side in each game ("against", "fade")
    # passes a frame with side_pick as `neutral`, because blind_side needs it.
    # The favourite / underdog blind bet must still run on it, and must take
    # the MARKET's favourite (home here, mu = 4), never the rule's pick (away).
    off = _offers()
    off = off[off["book"].isin(["fanduel", "draftkings"])]
    away = off.iloc[[1]].assign(side="away", price=-105.0, p_win=0.40)
    off = pd.concat([off, away], ignore_index=True).assign(mu=4.0, p_home=np.nan, side_pick="away")
    b = H.blind_by_real_side(off, {"G"}, _games(), seasons=(2024,))
    assert b["fav"] == b["home"] > 0 and b["dog"] == b["away"] < 0
    # and the whole cell runs: run_cells takes the rule's frame as both inputs
    data = H.Data(games=_games(), quotes=pd.DataFrame(), fetches=_fetches(60))
    rows = H.run_cells(data, "R", "C", off.assign(strength=1.0), off.assign(strength=1.0),
                       cuts=(1.0,), sides_by_market={"spreads": ["against"]}, strength="strength")
    assert rows[0]["blind_fav"] == b["fav"] and rows[0]["n_choose"] == 1


def _stale_cache(tmp_path, odds_seasons, ledger):
    games = pd.DataFrame([{"game_id": f"G{s}", "sport": "NBA", "season": s, "game_date": f"{s - 1}-12-01",
                           "home_team": "BOS", "away_team": "NYK", "home_score": 110.0, "away_score": 100.0,
                           "commence_time": f"{s - 1}-12-02T00:00:00Z"} for s in (2022, 2023)])
    games.to_parquet(tmp_path / "nba_games.parquet")
    pd.DataFrame([{"game_id": f"G{s}", "market": "h2h", "bookmaker": "fanduel",
                   "snapshot_type": "open", "snapshot_at": f"{s - 1}-12-01T22:55:00Z",
                   "source": "odds_api_historical", "created_at": f"2026-10-1{s - 2016} 00:00:00+00",
                   "home_price": -150.0, "away_price": 130.0, "spread_home": None,
                   "total_line": None, "over_price": None, "under_price": None}
                  for s in odds_seasons]).to_parquet(tmp_path / "nba_odds.parquet")
    pd.DataFrame({"requested_at": pd.to_datetime([r[0] for r in ledger], utc=True),
                  "pulled_at": pd.to_datetime([r[1] for r in ledger], utc=True),
                  "rows": 1, "why": "hourly"}).to_parquet(tmp_path / "nba_fetch_ledger.parquet")


def test_a_graded_load_refuses_a_season_the_cache_does_not_price(tmp_path):
    # every stored row matches its purchase, but 2023 has no rows at all
    _stale_cache(tmp_path, (2022,), [("2021-12-01T23:00:00Z", "2026-10-16 00:00:00+00")])
    with pytest.raises(RuntimeError, match="too few games"):
        H.load(cache=tmp_path, require_seasons=(2022, 2023))
    d = H.load(cache=tmp_path, require_seasons=(2022,))
    assert d.notes["games_priced_share"] == {2022: 1.0, 2023: 0.0}


def test_a_graded_load_refuses_rows_that_match_no_purchase(tmp_path):
    # both seasons priced, but 2023's row matches no purchase record: it is
    # only placed by its stamp, which is what a stale ledger looks like
    _stale_cache(tmp_path, (2022, 2023), [("2021-12-01T23:00:00Z", "2026-10-16 00:00:00+00"),
                                          ("2022-12-01T23:00:00Z", "2026-10-30 00:00:00+00")])
    with pytest.raises(RuntimeError, match="no purchase"):
        H.load(cache=tmp_path, require_seasons=(2022, 2023))
    assert H.load(cache=tmp_path).notes["placed_by_snapshot_share"] == 0.5


def test_a_past_average_miss_does_not_move_the_centre():
    # earlier seasons missed by +5 on average; the distribution keeps their
    # spread, not the miss, so the centre stays where the model put it
    dist = H.ResidDist(np.random.default_rng(4).normal(5.0, 12.0, 8000), "biased")
    w, _, _ = dist.probs(np.array([0.0]), np.array([0.5]))
    wn, _, _ = H.probs_at(np.array([0.0]), np.array([12.0]), np.array([0.5]))
    assert abs(w[0] - wn[0]) < 0.02 and abs(dist.mean - 5.0) < 0.5


def test_a_cell_reports_its_pooled_walk_forward_and_writes_its_bets(tmp_path, monkeypatch):
    # the two-game fixture from the whole-cell test, run with the bet write-out on
    monkeypatch.setenv("NBA_GAME2_BETS", str(tmp_path))
    games = pd.DataFrame([
        {"game_id": "G", "season": 2024, "game_date": "2024-01-15", "tip": TIP,
         "home_team": "BOS", "away_team": "NYK", "home_score": 110, "away_score": 100},
        {"game_id": "G2", "season": 2026, "game_date": "2024-01-16", "tip": TIP + pd.Timedelta(days=1),
         "home_team": "LAL", "away_team": "DEN", "home_score": 102, "away_score": 100}])
    q = pd.DataFrame([_q("fanduel", "spreads", 60, 66, -4.5, -110, -110)])
    q2 = q.assign(game_id="G2", season=2026, tip=TIP + pd.Timedelta(days=1),
                  fetch_at=q["fetch_at"] + pd.Timedelta(days=1),
                  snapshot_at=q["snapshot_at"] + pd.Timedelta(days=1))
    quotes = pd.concat([q, q2], ignore_index=True)
    f = quotes[["game_id", "tip", "fetch_at"]].drop_duplicates()
    f = f.assign(lead_min=(f["tip"] - f["fetch_at"]).dt.total_seconds() / 60)
    data = H.Data(games=games, quotes=quotes, fetches=f)
    t, off = H.point_offers(data, "D")
    model = pd.DataFrame({"game_id": ["G", "G2"], "market": "spreads", "mu": [9.0, 9.0],
                          "sigma": 12.0, "p_home": np.nan})
    cand = H.fair_offers(off, model)
    r = H.run_cells(data, "test", "D", cand, cand, cuts=[0.0], sides_by_market={"spreads": ["home"]})[0]
    # 2024 is a choosing season and 2026 the confirmation: pooled, both count
    assert r["n_choose"] == 1 and r["n_confirm"] == 1 and r["pool_n"] == 2
    assert r["pool_units"] == pytest.approx(1.0 - 1.1)
    assert r["pool_seasons_counted"] == 0               # neither season has 30 bets
    files = list(tmp_path.glob("bets_test_D_spreads_*.parquet"))
    assert len(files) == 1 and len(pd.read_parquet(files[0])) == 2
