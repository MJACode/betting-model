"""scripts/nba_game2_market: families F2, F6a and F6d of the second NBA game
search (docs/nba_models_2026.md §6.3). Every feature rule and every leak guard
is pinned on small games built by hand, by its outcome rather than its code."""
import os

import numpy as np
import pandas as pd
import pytest

from scripts import nba_game_harness as H
from scripts import nba_game2_market as M

TIP = pd.Timestamp("2024-01-16T00:30:00Z")          # 7:30 ET on 2024-01-15

# Empirical pricing distributions for the tests: symmetric (r and -r), so a
# balanced price at a number solves to that number.
_R = np.random.default_rng(11).normal(0, 1, 1000)
EMP_SP = H.ResidDist(np.r_[_R, -_R] * 12.0, "test spreads")
EMP_TOT = H.ResidDist(np.r_[_R, -_R] * 18.0, "test totals")
EMP_TT = H.ResidDist(np.r_[_R, -_R] * 11.0, "test team totals")
SIG = {(s, m): d for s in (2024, 2025) for m, d in (("spreads", EMP_SP), ("totals", EMP_TOT))}
SIG_TT = {(2025, m): EMP_TT for m in M.TT_MARKETS}


def _game(gid, day, hs, aw, season=2024):
    tip = TIP + pd.Timedelta(days=day)
    return {"game_id": gid, "season": season,
            "game_date": (tip - pd.Timedelta(hours=5)).strftime("%Y-%m-%d"), "tip": tip,
            "home_team": f"H{gid}", "away_team": f"A{gid}", "home_score": hs, "away_score": aw}


def _q(g, book, market, lead, line, pa, pb, snap_lag=5):
    return {"game_id": g["game_id"], "season": g["season"], "game_date": g["game_date"],
            "tip": g["tip"], "market": market, "book": book,
            "fetch_at": g["tip"] - pd.Timedelta(minutes=lead),
            "snapshot_at": g["tip"] - pd.Timedelta(minutes=lead + snap_lag),
            "line": line, "price_a": float(pa), "price_b": float(pb), "coherent": True}


def _pe(g, book, market, lead, line, pa=-110, pb=-110):
    """A per-game purchase row: dated by its own snapshot (fetch_at = snapshot_at)."""
    t = g["tip"] - pd.Timedelta(minutes=lead)
    return {"game_id": g["game_id"], "season": g["season"], "game_date": g["game_date"],
            "tip": g["tip"], "market": market, "book": book, "fetch_at": t, "snapshot_at": t,
            "line": line, "price_a": float(pa), "price_b": float(pb), "coherent": True}


def _data(games, quotes):
    g = pd.DataFrame(games)
    q = pd.DataFrame(quotes)
    f = q[["game_id", "tip", "fetch_at"]].drop_duplicates(["game_id", "fetch_at"])
    f = f.assign(lead_min=(f["tip"] - f["fetch_at"]).dt.total_seconds() / 60.0)
    return H.Data(games=g, quotes=q, fetches=f.reset_index(drop=True))


# ── pricing: the empirical distributions ─────────────────────────────────────

def _close_frames(seasons=(2022, 2023, 2024), n=200, seed=3, sd=None):
    rng = np.random.default_rng(seed)
    close, games = [], []
    for s in seasons:
        for i in range(n):
            gid = f"{s}-{i}"
            close += [{"game_id": gid, "season": s, "market": "spreads", "close_line": -5.0},
                      {"game_id": gid, "season": s, "market": "totals", "close_line": 220.0}]
            e = rng.normal(0, (sd or {}).get(s, 10.0), 2)
            games.append({"game_id": gid, "season": s, "home_score": 112.5 + e[0],
                          "away_score": 107.5 + e[1]})
    return pd.DataFrame(close), pd.DataFrame(games)


def test_market_prices_are_read_through_the_empirical_distribution():
    close, games = _close_frames()
    sig = M.market_pricing(close, games)
    for s in (2023, 2024):
        for m in ("spreads", "totals"):
            assert isinstance(sig[(s, m)], H.ResidDist)
    assert sig[(2024, "spreads")].n == 400                       # 2022 and 2023, not 2024


def test_the_win_probability_reads_the_empirical_shape_and_removes_the_tie_mass():
    # results land 4 above the centre 70% of the time and 9 below otherwise:
    # a bell curve would put P(home) near 0.5 at a centre of 0
    skew = H.ResidDist(np.r_[np.full(700, 4.0), np.full(300, -9.0)], "skew")
    assert M.p_home_from_margin([0.0], [skew])[0] == pytest.approx(0.7, abs=1e-9)
    p = M.p_home_from_margin([0.0, 4.0, -4.0], [EMP_SP] * 3)
    assert p[0] == pytest.approx(0.5, abs=1e-6)
    assert p[1] > 0.5 and p[1] + p[2] == pytest.approx(1.0, abs=1e-6)
    raw, _ = H.side_probs(np.array(["spreads"]), np.array(["home"]), np.array([0.0]),
                          mu=[4.0], sigma=np.array([EMP_SP], dtype=object))
    assert p[1] > raw[0]                       # the level-margin mass is shared out


def test_each_reference_reads_only_its_own_books():
    g1, g2 = _game("G1", 0, 110, 100), _game("G2", 0, 110, 100)
    vis = pd.DataFrame([_q(g1, "pinnacle", "spreads", 60, -5.0, -105, -105),
                        _q(g1, "fanduel", "spreads", 60, -7.0, -110, -110),
                        _q(g1, "betmgm", "spreads", 60, -9.0, -110, -110),
                        _q(g2, "fanduel", "spreads", 60, -3.0, -110, -110)])
    pin = M.reference_fair(vis, SIG, "pinnacle").set_index("game_id")
    con = M.reference_fair(vis, SIG, "consensus").set_index("game_id")
    assert list(pin.index) == ["G1"]                       # G2 has no Pinnacle number
    assert pin.loc["G1", "mu"] == pytest.approx(5.0, abs=1e-4)
    assert pin.loc["G1", "posted"] == -5.0
    assert con.loc["G1", "mu"] == pytest.approx(8.0, abs=1e-4)   # median of 7 and 9
    assert con.loc["G1", "posted"] == -8.0
    assert con.loc["G2", "mu"] == pytest.approx(3.0, abs=1e-4)
    assert isinstance(pin.loc["G1", "sigma"], H.ResidDist)


# ── F2: the favourite, read at T, bet on its real side ───────────────────────

def _f2_games():
    # G1: home is the favourite (home -5) and wins. G2: away is the favourite
    # (home +5) and wins. Fanduel prices the favourite at -180 in both.
    g1, g2 = _game("G1", 0, 110, 100), _game("G2", 1, 100, 110)
    q = [_q(g1, "pinnacle", "spreads", 120, -5.0, -105, -105),
         _q(g1, "fanduel", "h2h", 120, None, -180, 155),
         _q(g1, "pinnacle", "h2h", 120, None, -190, 165),
         _q(g2, "pinnacle", "spreads", 120, 5.0, -105, -105),
         _q(g2, "fanduel", "h2h", 120, None, 155, -180),
         _q(g2, "pinnacle", "h2h", 120, None, 165, -190),
         # Pinnacle's close (after T): both favourites shortened to -250
         _q(g1, "pinnacle", "h2h", 30, None, -250, 210),
         _q(g2, "pinnacle", "h2h", 30, None, 210, -250)]
    return _data([g1, g2], q)


def test_f2_bets_the_favourite_on_its_real_side():
    rows, b = M.f2_cells(_f2_games(), "C", "pinnacle", SIG, runs=2)
    assert len(rows) == 12 and {r["side"] for r in rows} == {"fav", "dog"}
    assert {r["axis_ref"] for r in rows} == {"pinnacle"}
    fav0 = next(r for r in rows if r["side"] == "fav" and r["cut"] == 0.0)
    # both favourites bet at -180 (risk 1.8, win 1.0) and both win
    assert fav0["n_choose"] == 2 and fav0["units_choose"] == pytest.approx(2.0)
    # the harness sees the real sides: one home favourite, one away favourite
    assert fav0["share_home"] == 0.5 and fav0["share_fav"] == 1.0
    assert fav0["blind_fav"] == pytest.approx(2.0 / 3.6)
    # the one-side blind is the favourite on every game, not the home team
    assert fav0["blind_roi_choose"] == pytest.approx(2.0 / 3.6)
    # closing-line value is read on the real side's own close (-250 no-vig
    # 0.689 against a -180 bet: +0.072 per unit risked, both games)
    assert fav0["clv_n"] == 2 and fav0["clv_share_positive"] == 1.0
    assert fav0["clv_median"] == pytest.approx(0.0716, abs=5e-4)
    dog0 = next(r for r in rows if r["side"] == "dog" and r["cut"] == 0.0)
    assert dog0["n_choose"] == 0
    assert dog0["blind_roi_choose"] == pytest.approx(-1.0)
    # the model probability is the real home team's
    m = b["model"].set_index("game_id")["p_home"]
    assert m["G1"] > 0.5 > m["G2"]
    fav_offers = b["cand"]["fav"]
    picked = fav_offers[fav_offers["side"] == fav_offers["side_pick"]].set_index("game_id")
    assert picked["side"].to_dict() == {"G1": "home", "G2": "away"}


def test_the_favourite_is_read_at_T_not_from_a_later_fetch():
    g = _game("G", 0, 110, 100)
    q = [_q(g, "pinnacle", "spreads", 30, 5.0, -105, -105),     # later fetch: away favoured
         _q(g, "fanduel", "h2h", 30, None, 140, -160),
         _q(g, "pinnacle", "spreads", 120, -5.0, -105, -105),   # at T (C): home favoured
         _q(g, "fanduel", "h2h", 120, None, -180, 155)]
    b = M.f2_point(_data([g], q), "C", "pinnacle", SIG, runs=1)
    assert b["picks"].set_index("game_id").loc["G", "fav"] == "home"
    c = b["cand"]["fav"]
    fav = c[c["side"] == c["side_pick"]].set_index("side")
    assert fav.loc["home", "price"] == -180.0                     # the price at T


def test_the_f2_placebo_moves_the_favourites_probability_and_keeps_each_games_side():
    gs = [_game(f"G{i}", 0, 110, 100) for i in range(4)]
    lines = (-5.0, 3.0, -8.0, 6.5)
    q = []
    for g, ln in zip(gs, lines):
        q += [_q(g, "pinnacle", "spreads", 120, ln, -105, -105),
              _q(g, "fanduel", "h2h", 120, None, -130, 110)]
    b = M.f2_point(_data(gs, q), "C", "pinnacle", SIG, runs=8)
    own = b["picks"].set_index("game_id")["fav"].to_dict()
    assert own == {"G0": "home", "G1": "away", "G2": "home", "G3": "away"}
    def fav_p(c):
        x = c[c["side"] == c["side_pick"]]
        return x.set_index("game_id")["p_win"]
    real = fav_p(b["cand"]["fav"])
    moved = 0
    for pc in b["placebo"]["fav"]:
        assert pc.drop_duplicates("game_id").set_index("game_id")["side_pick"].to_dict() == own
        p = fav_p(pc)
        assert sorted(p.round(12)) == sorted(real.round(12))       # a permutation
        moved += not np.allclose(p.reindex(real.index), real)
    assert moved > 0


def test_a_level_reference_has_no_favourite():
    ref = pd.DataFrame({"game_id": ["a", "b", "c", "d", "e"],
                        "p_home": [0.6, 0.5, 0.4, 0.5 - 1e-12, 0.55],
                        "posted": [-2.0, -1.0, 2.0, -1.0, 0.0]})
    fav = M.favourite_home(ref)
    # b and d sit on 0.5 (d by float noise); e is posted level whatever its price
    assert fav.to_dict() == {"a": True, "c": False}


@pytest.mark.parametrize("pricing", [EMP_SP, 11.5], ids=["empirical", "sigma 11.5"])
def test_a_pick_em_spread_reaches_no_favourite_through_the_solver(pricing):
    # a: spread 0 at balanced prices (the solver lands within float noise of a
    # level margin); b: spread 0 at skewed prices (p_home off 0.5, still level
    # by the posted number); c: home -3, a favourite
    g = {k: _game(k, 0, 110, 100) for k in "abc"}
    vis = pd.DataFrame([_q(g["a"], "pinnacle", "spreads", 60, 0.0, -110, -110),
                        _q(g["b"], "pinnacle", "spreads", 60, 0.0, -115, -105),
                        _q(g["c"], "pinnacle", "spreads", 60, -3.0, -110, -110)])
    sig = {(2024, "spreads"): pricing}
    rf = M.reference_fair(vis, sig, "pinnacle")
    assert set(rf["game_id"]) == {"a", "b", "c"}
    assert abs(rf.set_index("game_id").loc["b", "p_home"] - 0.5) > 1e-3
    assert M.favourite_home(rf).to_dict() == {"c": True}


# ── F6a: the overtime tail ───────────────────────────────────────────────────

def _f6a_data():
    # every game: an over/under at fanduel; the spread varies
    gs = {k: _game(k, 0, 110, 108) for k in "abcdef"}
    sp = {"a": [("pinnacle", -2.0, -110, -110)],               # home by exactly 2
          "b": [("pinnacle", 2.0, -110, -110)],                # away by exactly 2
          "c": [("pinnacle", -2.0, -140, 120)],                # 2, priced like 3+
          "d": [("fanduel", -2.5, -110, -110), ("betmgm", -1.5, -110, -110)],  # median 2
          "e": [("pinnacle", -2.5, -110, -110)],               # outside 2
          "f": [("pinnacle", -1.0, -110, -110), ("fanduel", -4.0, -110, -110)]}  # Pinnacle's 1
    q = []
    for k, g in gs.items():
        q.append(_q(g, "fanduel", "totals", 120, 220.5, -110, -110))
        q += [_q(g, b, "spreads", 120, ln, pa, pb) for b, ln, pa, pb in sp[k]]
    return _data(list(gs.values()), q)


def test_f6a_reads_the_posted_spread_both_ways_and_not_a_solved_centre():
    b = M.f6a_point(_f6a_data(), "C", SIG, runs=1)
    st = b["cand"].drop_duplicates("game_id").set_index("game_id")["strength"]
    within = {k: set(st[st >= cut].index) for k, cut in zip(M.F6A_K, M.F6A_CUTS)}
    assert within[1] == {"f"}
    assert within[2] == {"a", "b", "c", "d", "f"}
    assert within[3] == set("abcdef")
    assert M.F6A_CUTS == (-1.0, -2.0, -3.0, -4.0)


def test_the_f6a_placebo_shuffles_strength_and_keeps_the_price():
    games = pd.DataFrame({"game_id": list("abcd"),
                          "game_date": ["2024-01-15"] * 3 + ["2024-01-16"]})
    neutral = pd.DataFrame({"game_id": list("abcd"), "market": "totals", "side": "over",
                            "price": [-110.0, -105.0, -115.0, -110.0], "ev": [-.05, -.03, -.06, -.05]})
    st = pd.DataFrame({"game_id": list("abcd"), "strength": [-1.0, -2.0, -3.0, -4.0]})
    moved = 0
    for r in range(20):
        p = M.f6a_placebo(neutral, st, games, r).set_index("game_id")
        assert p["price"].tolist() == neutral["price"].tolist()
        assert p["ev"].tolist() == neutral["ev"].tolist()
        assert p.loc["d", "strength"] == -4.0                    # alone on its date
        assert sorted(p.loc[list("abc"), "strength"]) == [-3.0, -2.0, -1.0]
        moved += p.loc["a", "strength"] != -1.0
    assert moved > 0


# ── F6d: one book against itself ─────────────────────────────────────────────

def test_each_book_moneyline_is_priced_on_its_own_spread():
    g = _game("G", 0, 110, 100)
    q = [_q(g, "fanduel", "spreads", 120, -3.0, -110, -110),
         _q(g, "fanduel", "h2h", 120, None, -150, 130),
         _q(g, "betmgm", "spreads", 120, -8.0, -110, -110),
         _q(g, "betmgm", "h2h", 120, None, -150, 130)]
    b = M.f6d_ml_point(_data([g], q), "C", SIG, runs=1)
    c = b["cand"]
    assert len(c) == 4                                           # 2 books x 2 sides, once each
    home = c[c["side"] == "home"].set_index("book")["p_win"]
    assert home["fanduel"] == pytest.approx(M.p_home_from_margin([3.0], [EMP_SP])[0], abs=1e-4)
    assert home["betmgm"] == pytest.approx(M.p_home_from_margin([8.0], [EMP_SP])[0], abs=1e-4)


def test_one_book_against_itself_takes_both_quotes_from_one_fetch():
    # fanduel's moneyline visible at T comes from the 150-minute fetch, its
    # spread from the 120-minute one: a possible line move, so fanduel is out.
    g = _game("G", 0, 110, 100)
    q = [_q(g, "fanduel", "spreads", 120, -3.0, -110, -110),
         _q(g, "fanduel", "h2h", 150, None, -150, 130),
         _q(g, "betmgm", "spreads", 120, -8.0, -110, -110),
         _q(g, "betmgm", "h2h", 120, None, -150, 130)]
    data = _data([g], q)
    t = H.decision_times(data.fetches, data.games, "C")
    assert (t["lead_min"] == 120.0).all()
    vis = H.visible(data.quotes, t)
    assert set(vis.loc[vis["market"] == "h2h", "book"]) == {"fanduel", "betmgm"}
    b = M.f6d_ml_point(data, "C", SIG, runs=1)
    assert set(b["cand"]["book"]) == {"betmgm"}


def _f6d_total_data(slate_leads=(70,)):
    g = _game("G", 0, 115, 110, season=2025)
    q = [_q(g, "fanduel", "totals", lead, 220.5, -110, -110) for lead in slate_leads]
    pe = pd.DataFrame([_pe(g, "fanduel", "team_totals_home", 62, 112.5),
                       _pe(g, "fanduel", "team_totals_away", 62, 107.5),
                       # bought 20 minutes out: outside D, and after T
                       _pe(g, "fanduel", "team_totals_home", 20, 120.5),
                       _pe(g, "fanduel", "team_totals_away", 20, 115.5)])
    return _data([g], q), pe


def test_the_own_total_is_the_two_team_totals_bought_in_D_and_in_hand_at_T():
    data, pe = _f6d_total_data()
    b = M.f6d_total_point(data, "D", SIG, SIG_TT, pe, runs=1)
    c = b["cand"]
    assert len(c) == 2 and set(c["side"]) == {"over", "under"}
    assert c["mu"].iloc[0] == pytest.approx(220.0, abs=1e-3)      # 112.5 + 107.5
    assert c["sigma"].iloc[0] is EMP_TOT                          # the full-game totals distribution
    # T is the team-total purchase (62 min out), later than the slate fetch (70)
    assert (b["times"]["T"] == data.games["tip"].iloc[0] - pd.Timedelta(minutes=62)).all()


def test_team_totals_never_reach_the_c_cells_and_the_empty_cell_still_grades():
    data, pe = _f6d_total_data(slate_leads=(90, 60))
    b = M.f6d_total_point(data, "C", SIG, SIG_TT, pe, runs=2)
    assert len(b["cand"]) == 0 and len(b["neutral"]) == 2
    rows = H.run_cells(data, "F6d", "C", b["cand"], b["neutral"], M.F6D_CUTS,
                       {"totals": ["over", "under"]}, placebo=b["placebo"],
                       choose_seasons=M.F6D_TT_CHOOSE)
    assert len(rows) == 4 and all(r["n_choose"] == 0 for r in rows)
    assert all(len(r["placebo_rois"]) == 2 for r in rows)


def test_the_team_total_gate_at_d_reads_the_team_total_purchases():
    # both games reach D on the slate (70 minutes out); only G bought its team
    # totals inside D, so the team-total cells reach D on 1 of 2 games
    g, g2 = _game("G", 0, 115, 110, season=2025), _game("G2", 1, 100, 104, season=2025)
    q = [_q(x, "fanduel", "totals", 70, 220.5, -110, -110) for x in (g, g2)]
    pe = pd.DataFrame([_pe(g, "fanduel", "team_totals_home", 62, 112.5),
                       _pe(g, "fanduel", "team_totals_away", 62, 107.5)])
    data = _data([g, g2], q)
    assert H.point_coverage(data, "D")[2025] == 1.0              # the slate alone would pass
    rows, _ = M.f6d_total_cells(data, "D", SIG, SIG_TT, pe, runs=1)
    assert len(rows) == 4
    assert all(r["gate_cov_2025"] == 0.5 and r["gate_dropped"] == "2025" for r in rows)
    assert all(r["choose_seasons"] == "" for r in rows)


def test_the_team_total_cells_decide_when_both_quotes_are_in_hand():
    tip = TIP
    sl = pd.DataFrame({"game_id": ["a", "b"], "T": [tip - pd.Timedelta(minutes=70),
                                                   tip - pd.Timedelta(minutes=50)]})
    pe = pd.DataFrame({"game_id": ["a", "c"], "T": [tip - pd.Timedelta(minutes=62),
                                                   tip - pd.Timedelta(minutes=63)]})
    t = M.combine_times(sl, pe).set_index("game_id")["T"]
    assert t["a"] == tip - pd.Timedelta(minutes=62)              # the later of 70 and 62
    assert t["b"] == tip - pd.Timedelta(minutes=50)
    assert t["c"] == tip - pd.Timedelta(minutes=63)


TT_N, TT_MIN = 120, 100          # games per season; earlier games a distribution needs


def _tt_frames():
    close, games = _close_frames(seasons=(2023, 2024, 2025), n=TT_N, sd={2025: 30.0})
    games = pd.concat([games, pd.DataFrame([{"game_id": "2026-0", "season": 2026,
                                             "home_score": 100, "away_score": 100}])],
                      ignore_index=True)
    return close, games


def test_the_team_total_distribution_is_the_spread_around_the_close_implied_team_total():
    close, games = _tt_frames()
    d = M.team_total_dist(close, games, min_games=TT_MIN)
    g23 = games[games["season"] == 2023]
    want = np.concatenate([g23["home_score"] - 112.5, g23["away_score"] - 107.5])
    dist = d[(2024, "team_totals_home")]
    assert isinstance(dist, H.ResidDist) and dist.n == len(want) == 2 * TT_N
    assert dist.sd == pytest.approx(want.std(), rel=1e-9)
    assert d[(2024, "team_totals_away")] is dist                  # home and away pooled


def test_the_team_total_distribution_uses_only_earlier_seasons():
    close, games = _tt_frames()
    d = M.team_total_dist(close, games, min_games=TT_MIN)
    assert (2023, "team_totals_home") not in d                    # nothing earlier
    assert d[(2025, "team_totals_home")].sd < 12.0                # 2025's own SD is 30
    g2 = games.copy()
    g2.loc[g2["season"] == 2025, "home_score"] += 50.0            # change 2025's results
    d2 = M.team_total_dist(close, g2, min_games=TT_MIN)
    assert np.array_equal(d2[(2025, "team_totals_home")].win_half, d[(2025, "team_totals_home")].win_half)
    assert not np.array_equal(d2[(2026, "team_totals_home")].win_half,
                              d[(2026, "team_totals_home")].win_half)
    # the default asks for 300 earlier games: 2024 (120 earlier) and 2025 (240) get none
    assert set(M.team_total_dist(close, games)) == {(2026, m) for m in M.TT_MARKETS}


# ── run guards, the cell list, population ────────────────────────────────────

def test_full_refuses_without_the_owners_go_flag():
    with pytest.raises(SystemExit):
        M.go_guard(True, {})
    with pytest.raises(SystemExit):
        M.go_guard(True, {"NBA_GAME2_GO": "yes"})
    M.go_guard(True, {"NBA_GAME2_GO": "1"})
    M.go_guard(False, {})


def test_smoke_reads_2020_21_only():
    assert M.seasons_for("smoke") == [2021]
    assert M.seasons_for("full") is None


def _stale_cache(path, priced=(2021,)):
    """Games in every season 2021-2026; quotes (all matched to a purchase) only
    in `priced`."""
    path.mkdir(parents=True, exist_ok=True)
    seasons = M.FULL_SEASONS
    pd.DataFrame([{"game_id": f"G{s}", "sport": "NBA", "season": s, "game_date": f"{s - 1}-12-01",
                   "home_team": "BOS", "away_team": "NYK", "home_score": 110.0, "away_score": 100.0,
                   "commence_time": f"{s - 1}-12-02T00:00:00Z"} for s in seasons]
                 ).to_parquet(path / "nba_games.parquet")
    pd.DataFrame([{"game_id": f"G{s}", "market": "h2h", "bookmaker": "fanduel",
                   "snapshot_type": "open", "snapshot_at": f"{s - 1}-12-01T22:55:00Z",
                   "source": "odds_api_historical", "created_at": f"2026-10-10 0{i}:00:00+00",
                   "home_price": -150.0, "away_price": 130.0, "spread_home": None,
                   "total_line": None, "over_price": None, "under_price": None}
                  for i, s in enumerate(priced)]).to_parquet(path / "nba_odds.parquet")
    pd.DataFrame({"requested_at": pd.to_datetime([f"{s - 1}-12-01T23:00:00Z" for s in priced], utc=True),
                  "pulled_at": pd.to_datetime([f"2026-10-10 0{i}:00:00+00" for i, _ in enumerate(priced)],
                                              utc=True),
                  "rows": 1, "why": "hourly"}).to_parquet(path / "nba_fetch_ledger.parquet")


def test_full_refuses_a_cache_that_misses_a_season_before_grading(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    _stale_cache(cache)
    res = tmp_path / "res"
    monkeypatch.setattr(H, "CACHE", cache)
    monkeypatch.setenv("NBA_GAME2_GO", "1")
    monkeypatch.setenv("NBA_GAME2_RESULTS", str(res))
    with pytest.raises(RuntimeError, match="too few games"):
        M.run("full", runs=1)
    assert not list(res.glob("cells_*.parquet"))
    # a cache priced in every season loads
    _stale_cache(cache, priced=M.FULL_SEASONS)
    d = M.load_for("full", cache)
    assert set(d.notes["games_priced_share"]) == set(M.FULL_SEASONS)


def test_the_shared_cache_is_never_written_or_linked(tmp_path, monkeypatch):
    shared = tmp_path / "shared"
    shared.mkdir()
    for f in ("nba_games.parquet", "nba_odds.parquet"):
        (shared / f).write_bytes(b"x" * 10)
    ledger = tmp_path / "ledger.parquet"
    ledger.write_bytes(b"L")
    before = {p.name: p.stat().st_mtime_ns for p in shared.iterdir()}
    monkeypatch.setattr(H, "CACHE", shared)
    with pytest.raises(SystemExit):                               # --full needs the real ledger
        M.cache_for("full", ledger, tmp_path / "res")
    ov = M.cache_for("smoke", ledger, tmp_path / "res")
    assert ov != shared and (ov / "nba_fetch_ledger.parquet").exists()
    assert not os.path.samefile(ov / "nba_odds.parquet", shared / "nba_odds.parquet")
    assert {p.name: p.stat().st_mtime_ns for p in shared.iterdir()} == before
    (shared / "nba_fetch_ledger.parquet").write_bytes(b"L")
    assert M.cache_for("full", None, tmp_path / "res") == shared


def test_the_cells_are_exactly_section_6_3s():
    assert M.F2_POINTS == ("A", "B", "C", "D")
    assert M.F2_CUTS == (0.0, 0.01, 0.02, 0.03, 0.05, 0.08)
    assert M.F2_REFS == ("pinnacle", "consensus")
    assert M.F2_SIDES == ("fav", "dog")
    assert M.F6A_POINTS == ("B", "C") and M.F6A_K == (1, 2, 3, 4)
    assert M.F6D_POINTS == ("C", "D") and M.F6D_CUTS == (0.01, 0.03)
    assert M.F6D_TT_CHOOSE == (2025,)
    assert M.EXPECTED_CELLS == {"F2": 96, "F6a": 8, "F6d": 16}
    assert M.PLACEBO_RUNS == 20
    row = {"point": "A", "market": "h2h", "side": "fav", "cut": 0.0, "axis_ref": "pinnacle"}
    with pytest.raises(AssertionError):
        M.check_cells("F2", [row] * 96)                           # duplicates
    with pytest.raises(AssertionError):
        M.check_cells("F6a", [dict(row, cut=float(i)) for i in range(7)])


def test_placebo_rois_are_written_as_a_list_of_doubles(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq
    rows = [{"point": "B", "market": "totals", "side": "over", "cut": -float(k), "cut_index": k - 1,
             "placebo_rois": [np.nan] * 20} for k in M.F6A_K]
    rows += [dict(r, point="C") for r in rows]
    # every placebo ROI NaN (no placebo run bet on a choosing season)
    path = tmp_path / "c.parquet"
    M.write_cells(M.check_cells("F6a", rows), path)
    assert pq.read_schema(path).field("placebo_rois").type == pa.list_(pa.float64())
    back = pd.read_parquet(path)["placebo_rois"]
    assert all(len(v) == 20 and not np.isfinite(v).any() for v in back)
    # values survive, an empty list included
    rows[0]["placebo_rois"], rows[1]["placebo_rois"] = [0.1, np.nan, -0.2], []
    M.write_cells(M.check_cells("F6a", rows), path)
    back = pd.read_parquet(path)["placebo_rois"]
    assert np.allclose(back.iloc[0], [0.1, np.nan, -0.2], equal_nan=True) and len(back.iloc[1]) == 0


def test_population_reads_each_seasons_bets_from_its_own_count():
    row = {"side": "over", "cut_index": 0, "cut": 0.01, "n_2021": 3, "n_2022": 4,
           "n_2023": 5, "n_2024": 6, "n_2025": 7, "n_confirm": 8}
    assert [M._season_bets(row, s) for s in range(2021, 2027)] == [3, 4, 5, 6, 7, 8]
    games = pd.DataFrame({"game_id": ["a", "b", "c"], "season": [2021, 2026, 2026]})
    built = {"times": pd.DataFrame({"game_id": ["a", "b"]}), "priced": {"a", "b"},
             "modelled": {"b"}}
    pop = pd.DataFrame(M.population_rows("F6d", "D", "totals", games, built, [row]))
    p26 = pop[pop["season"] == 2026].iloc[0]
    assert (p26["games"], p26["games_at_point"], p26["games_priced"], p26["games_model"],
            p26["bets"]) == (2, 1, 1, 1, 8)
