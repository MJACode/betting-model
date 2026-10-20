"""scripts/nba_game_harness on the first-half, first-quarter and team-total
markets (docs/nba_models_2026.md §8): each settles on what the books settle it
on, a level period voids a two-way moneyline, and every pricing step names the
sides and the home number per market. Small games built by hand; each fixture
gives a different answer if the market were settled on the wrong score."""
import numpy as np
import pandas as pd
import pytest

from scripts import nba_game_harness as H

TIP = pd.Timestamp("2024-01-16T00:30:00Z")


def _per(game_id, home, away):
    return [{"game_id": game_id, "period": i + 1, "home_points": h, "away_points": a}
            for i, (h, a) in enumerate(zip(home, away))]


# H:   first quarter home +10 (30-20), first half home -5 (50-55), final 110-100
# OT:  first quarter and first half level (25-25, 55-55), 100-100 after four, 110-105
# BAD: periods add to 99-90 against a stored 100-90
PERIODS = pd.DataFrame(_per("H", [30, 20, 30, 30], [20, 35, 20, 25])
                       + _per("OT", [25, 30, 20, 25, 10], [25, 30, 25, 20, 5])
                       + _per("BAD", [25, 25, 25, 24], [20, 20, 25, 25]))
FINALS = {"H": (110, 100), "OT": (110, 105), "BAD": (100, 90)}


def _games(ids=("H", "OT", "BAD")):
    rows = []
    for i, g in enumerate(ids):
        tip = TIP + pd.Timedelta(days=i)
        rows.append({"game_id": g, "season": 2024, "game_date": str((tip - pd.Timedelta(hours=5)).date()),
                     "tip": tip, "home_team": "BOS", "away_team": "NYK",
                     "home_score": float(FINALS[g][0]), "away_score": float(FINALS[g][1])})
    return pd.DataFrame(rows)


def _graded_games(ids=("H", "OT", "BAD")):
    return H.with_periods(_games(ids), periods=PERIODS)


def _bets(rows):
    return pd.DataFrame([{"game_id": g, "season": 2024, "game_date": "2024-01-15", "market": m,
                          "side": s, "line": l, "price": float(p)} for g, m, s, l, p in rows])


def _results(rows, games=None):
    return H.grade(_bets(rows), _graded_games() if games is None else games)["result"].tolist()


# ── settlement ──────────────────────────────────────────────────────────────

def test_the_first_half_settles_on_the_first_two_quarters_never_the_final():
    # home trails the first half by 5 but wins the game by 10 and the quarter by 10
    got = _results([("H", "spreads_h1", "home", -1.5, -110),
                    ("H", "spreads_h1", "away", -1.5, -110),
                    ("H", "h2h_h1", "home", np.nan, -110),
                    ("H", "h2h_h1", "away", np.nan, -110),
                    ("H", "totals_h1", "under", 105.5, -110),     # 105 scored
                    ("H", "totals_h1", "over", 105.0, -110)])
    assert got == ["L", "W", "L", "W", "W", "P"]


def test_the_first_quarter_settles_on_the_first_quarter_alone():
    got = _results([("H", "spreads_q1", "home", -2.5, -110),      # +10 in the quarter
                    ("H", "h2h_q1", "home", np.nan, -110),
                    ("H", "h2h_q1", "away", np.nan, -110),
                    ("H", "totals_q1", "under", 50.5, -110),      # 50 scored
                    ("H", "totals_q1", "over", 50.0, -110)])
    assert got == ["W", "W", "L", "W", "P"]


def test_a_team_total_settles_on_that_teams_own_score_overtime_included():
    # OT: 100-100 after four quarters, 110-105 after overtime
    got = _results([("OT", "team_totals_home", "over", 107.5, -110),   # 110, not 100, not 105
                    ("OT", "team_totals_home", "under", 107.5, -110),
                    ("OT", "team_totals_away", "over", 106.5, -110),   # 105, not 110, not 215
                    ("OT", "team_totals_away", "under", 106.5, -110),
                    ("OT", "team_totals_away", "over", 105.0, -110),
                    ("OT", "totals", "over", 207.5, -110),             # the full game counts overtime too
                    ("OT", "totals_h1", "over", 109.5, -110)])         # 55-55 at the half
    assert got == ["W", "L", "L", "W", "P", "W", "W"]


def test_a_level_first_half_or_first_quarter_voids_the_moneyline_and_leaves_the_denominator():
    # OT is level after one quarter (25-25) and after two (55-55)
    b = H.grade(_bets([("OT", "h2h_h1", "home", np.nan, -110),
                       ("OT", "h2h_h1", "away", np.nan, -110),
                       ("OT", "h2h_q1", "home", np.nan, 150),
                       ("OT", "h2h_q1", "away", np.nan, -180),
                       ("OT", "spreads_h1", "home", 0.5, -110),            # +0.5 on a level half covers
                       ("OT", "h2h", "home", np.nan, -110)]), _graded_games())
    assert b["result"].tolist() == ["P", "P", "P", "P", "W", "W"]
    void = b.iloc[:4]
    assert void["units"].tolist() == [0.0] * 4 and void["risk"].tolist() == [0.0] * 4
    assert void["risk_kept"].tolist() == pytest.approx([1.1, 1.1, 1 / 1.5, 1.8])
    two = b.iloc[[0, 1, 4]]
    assert H.roi(two) == pytest.approx(1.0 / 1.1)
    assert H.roi(two, kept=True) == pytest.approx(1.0 / 3.3)


def test_a_period_spread_takes_the_home_number():
    # home +10 in the first quarter of H; spread_home is the HOME number for the period
    got = _results([("H", "spreads_q1", "home", -9.5, -110),
                    ("H", "spreads_q1", "away", -9.5, -110),
                    ("H", "spreads_q1", "home", -10.0, -110),
                    ("H", "spreads_q1", "away", -10.0, -110),
                    ("H", "spreads_h1", "away", 4.5, -110)])          # home +4.5 loses the half by 5
    assert got == ["W", "L", "P", "P", "W"]
    assert H.threshold(["spreads_h1", "spreads_q1", "totals_q1", "team_totals_home", "spreads"],
                       [-3.5, 2.0, 50.5, 112.5, -6.0]).tolist() == [3.5, -2.0, 50.5, 112.5, 6.0]
    # the home half margin centred on +2: home -3.5 needs a 4-point half, so it is the underdog
    pw, pp = H.side_probs(np.array(["spreads_h1", "spreads_h1"]), np.array(["home", "away"]),
                          np.array([-3.5, -3.5]), mu=[2.0, 2.0], sigma=[7.0, 7.0])
    assert pw[0] < 0.5 and pw[0] + pw[1] == pytest.approx(1.0) and pp.tolist() == [0.0, 0.0]


def test_a_game_whose_periods_do_not_add_up_is_never_graded_on_them():
    g = _graded_games()
    assert g.set_index("game_id")["home_h1"].isna().to_dict() == {"H": False, "OT": False, "BAD": True}
    with pytest.raises(ValueError, match="no settling score"):
        H.grade(_bets([("BAD", "spreads_h1", "home", -1.5, -110)]), g)
    # its team total settles on the stored final, which needs no period
    assert _results([("BAD", "team_totals_home", "over", 99.5, -110)], g) == ["W"]
    # a game missing its second quarter is not trusted either
    gap = H.with_periods(_games(("H",)), periods=PERIODS[~((PERIODS["game_id"] == "H")
                                                           & (PERIODS["period"] == 2))])
    assert gap["home_q1"].isna().all()


def test_a_period_bet_needs_the_period_scores_and_a_full_game_bet_does_not():
    with pytest.raises(KeyError, match="with_periods"):
        H.grade(_bets([("H", "totals_q1", "over", 49.5, -110)]), _games())
    assert H.grade(_bets([("H", "spreads", "home", -9.5, -110)]), _games())["result"].tolist() == ["W"]
    with pytest.raises(KeyError, match="unknown market"):
        H.grade(_bets([("H", "alternate_spreads_h1", "home", -1.5, -110)]), _graded_games())


# ── pricing: sides, the market's fair line, favourites, twins ───────────────

def _vis(rows, season=2024):
    return pd.DataFrame([{"game_id": g, "season": season, "game_date": "2024-01-15", "tip": TIP,
                          "market": m, "book": b, "line": l, "price_a": a, "price_b": bb,
                          "coherent": True, "T": TIP - pd.Timedelta(minutes=60),
                          "fetch_at": TIP - pd.Timedelta(minutes=60),
                          "snapshot_at": TIP - pd.Timedelta(minutes=61)}
                         for g, m, b, l, a, bb in rows])


DERIV_VIS = [("H", "h2h_q1", "fanduel", np.nan, -150, 130),
             ("H", "spreads_h1", "pinnacle", -3.0, -105, -105),
             ("H", "spreads_h1", "fanduel", -3.5, -105, -115),
             ("H", "totals_h1", "pinnacle", 110.5, -105, -105),
             ("H", "team_totals_home", "fanduel", 112.5, -110, -110),
             ("H", "team_totals_away", "betmgm", 108.5, -120, 100)]


def test_offers_name_the_sides_of_every_derivative_market():
    off = H.offers(_vis(DERIV_VIS))
    sides = off.groupby("market")["side"].apply(lambda s: tuple(sorted(set(s)))).to_dict()
    assert sides == {"h2h_q1": ("away", "home"), "spreads_h1": ("away", "home"),
                     "totals_h1": ("over", "under"), "team_totals_home": ("over", "under"),
                     "team_totals_away": ("over", "under")}
    tt = off[(off["market"] == "team_totals_away")].set_index("side")["price"]
    assert tt.to_dict() == {"over": -120, "under": 100}
    with pytest.raises(KeyError, match="unknown market"):
        H.offers(_vis([("H", "alternate_totals_h1", "fanduel", 110.5, -110, -110)]))


def test_the_markets_fair_line_prices_derivative_markets_on_their_own_numbers():
    sig = {(2024, m): 7.0 for m in ("spreads_h1", "totals_h1", "team_totals_home", "team_totals_away")}
    f = H.market_fair(_vis(DERIV_VIS), sig).set_index("market")
    # an even no-vig price at home -3 puts the home half margin's centre at +3
    assert f.loc["spreads_h1", "ref"] == "pinnacle"
    assert f.loc["spreads_h1", "mu"] == pytest.approx(3.0, abs=1e-6)
    assert f.loc["totals_h1", "mu"] == pytest.approx(110.5, abs=1e-6)
    assert f.loc["team_totals_home", "mu"] == pytest.approx(112.5, abs=1e-6)
    ph = f.loc["h2h_q1", "p_home"]
    assert 0.55 < ph < 0.6 and np.isnan(f.loc["h2h_q1", "mu"])
    assert np.isnan(f.loc["spreads_h1", "p_home"])
    cand = H.fair_offers(H.offers(_vis(DERIV_VIS)), f.reset_index()).set_index(["market", "book", "side"])
    assert cand.loc[("h2h_q1", "fanduel", "home"), "p_win"] == pytest.approx(ph)
    # home -3 is a whole number: a 3-point half pushes
    assert cand.loc[("spreads_h1", "pinnacle", "home"), "p_push"] > 0.02
    assert cand.loc[("spreads_h1", "fanduel", "home"), "p_push"] == 0.0


def test_the_favourite_comes_from_period_moneylines_and_spreads_never_from_a_total():
    neutral = pd.DataFrame({"game_id": ["a", "b", "c", "d"],
                            "market": ["h2h_q1", "spreads_h1", "totals_h1", "team_totals_home"],
                            "mu": [np.nan, -2.0, 110.0, 112.0], "p_home": [0.6, np.nan, np.nan, np.nan]})
    f = H.fav_sides(neutral).set_index("game_id")
    assert f["fav"].to_dict() == {"a": "home", "b": "away"}


def test_a_period_moneyline_twin_at_another_book_is_not_an_outlier():
    off = pd.DataFrame([{"game_id": "H", "market": "h2h_h1", "side": "home", "book": b, "line": np.nan,
                         "price": p} for b, p in (("fanduel", -110.0), ("betmgm", -112.0))])
    assert bool(H.outlier_flag(off.iloc[[0]], off).iloc[0]) is False


def test_a_period_moneyline_still_on_offer_at_the_next_fetch_is_counted():
    q = pd.DataFrame([{"game_id": "H", "season": 2024, "game_date": "2024-01-15", "tip": TIP,
                       "market": "h2h_q1", "book": "fanduel", "line": np.nan,
                       "fetch_at": TIP - pd.Timedelta(minutes=m), "snapshot_at": TIP - pd.Timedelta(minutes=m + 1),
                       "price_a": -110.0, "price_b": -110.0, "coherent": True} for m in (120, 60)])
    f = q[["game_id", "tip", "fetch_at"]].assign(lead_min=[120.0, 60.0])
    data = H.Data(games=_graded_games(("H",)), quotes=q, fetches=f)
    bet = pd.DataFrame([{"game_id": "H", "market": "h2h_q1", "book": "fanduel", "side": "home",
                         "line": np.nan, "price": -110.0, "T": TIP - pd.Timedelta(minutes=120)}])
    assert H.next_fetch_check(bet, data).tolist() == [True]


def test_the_close_residual_settles_each_market_on_its_own_scores():
    close = pd.DataFrame({"game_id": ["H", "H", "OT", "H", "H"], "season": 2024,
                          "market": ["spreads_h1", "totals_q1", "team_totals_away", "spreads", "h2h_q1"],
                          "close_line": [-3.0, 48.5, 101.5, -4.5, np.nan]})
    r = H.close_resid(close, _graded_games())
    assert r["market"].tolist() == ["spreads_h1", "totals_q1", "team_totals_away", "spreads"]
    # half margin -5 with home -3; quarter 50 on 48.5; away 105 on 101.5; game +10 with home -4.5
    assert r["resid"].tolist() == pytest.approx([-8.0, 1.5, 3.5, 5.5])


# ── loading, and one whole derivative cell ──────────────────────────────────

def test_a_graded_derivative_load_refuses_a_season_it_does_not_price(tmp_path):
    games = pd.DataFrame([{"game_id": f"G{s}", "season": s, "game_date": f"{s - 1}-12-01",
                           "tip": pd.Timestamp(f"{s - 1}-12-02T00:30:00Z")} for s in (2025, 2026)])
    rows = [{"game_id": "G2025", "market": m, "bookmaker": "fanduel", "snapshot_type": "open",
             "snapshot_at": "2024-12-01T23:30:00Z", "source": H.PER_EVENT_SOURCE,
             "created_at": "2026-10-16 00:00:00+00", "home_price": None, "away_price": None,
             "spread_home": None, "total_line": 110.5, "over_price": -110.0, "under_price": -110.0}
            for m in ("totals_h1", "alternate_totals_h1")]
    pd.DataFrame(rows).to_parquet(tmp_path / "nba_odds.parquet")
    with pytest.raises(RuntimeError, match="too few games"):
        H.load_per_event(games, cache=tmp_path, require_seasons=(2025, 2026))
    pe = H.load_per_event(games, cache=tmp_path, require_seasons=(2025,))
    assert pe["market"].tolist() == ["totals_h1"]


def test_one_derivative_cell_is_graded_on_the_period_scores_with_the_void():
    games = _graded_games(("H", "OT"))
    rows = []
    for g, tip in zip(games["game_id"], games["tip"]):
        at = tip - pd.Timedelta(minutes=60)
        base = {"game_id": g, "season": 2024, "game_date": games.set_index("game_id").loc[g, "game_date"],
                "tip": tip, "book": "fanduel", "snapshot_at": at, "fetch_at": at, "coherent": True}
        rows.append({**base, "market": "spreads_h1", "line": -1.5 if g == "H" else 0.5,
                     "price_a": -110.0, "price_b": -110.0})
        rows.append({**base, "market": "h2h_h1", "line": np.nan, "price_a": -110.0, "price_b": -110.0})
    pe = pd.DataFrame(rows)
    f = pe[["game_id", "tip", "fetch_at"]].drop_duplicates()
    f = f.assign(lead_min=(f["tip"] - f["fetch_at"]).dt.total_seconds() / 60)
    data = H.Data(games=games, quotes=pe, fetches=f)
    t = H.per_event_times(pe, "D")
    vis = H.visible(pe, t)
    off = H.offers(vis)
    model = pd.DataFrame({"game_id": ["H", "OT", "H", "OT"],
                          "market": ["spreads_h1", "spreads_h1", "h2h_h1", "h2h_h1"],
                          "mu": [6.0, 6.0, np.nan, np.nan], "sigma": [7.0, 7.0, np.nan, np.nan],
                          "p_home": [np.nan, np.nan, 0.7, 0.7]})
    cand = H.fair_offers(off, model)
    neutral = H.fair_offers(off, H.market_fair(vis, {(2024, "spreads_h1"): 7.0}))
    got = {r["market"]: r for r in H.run_cells(
        data, "T", "D", cand, neutral, cuts=[0.0],
        sides_by_market={"spreads_h1": ["home"], "h2h_h1": ["home"]}, times=t)}
    # spreads: H's home -1.5 loses a half lost by 5; OT's home +0.5 covers a level half
    assert got["spreads_h1"]["n_choose"] == 2
    assert got["spreads_h1"]["units_choose"] == pytest.approx(1.0 - 1.1)
    # moneyline: H's home loses the half; OT's level half is void, stake back
    assert got["h2h_h1"]["n_choose"] == 2
    assert got["h2h_h1"]["units_choose"] == pytest.approx(-1.1)
    assert got["h2h_h1"]["roi_choose"] == pytest.approx(-1.0)
    assert got["h2h_h1"]["roi_kept_choose"] == pytest.approx(-0.5)
