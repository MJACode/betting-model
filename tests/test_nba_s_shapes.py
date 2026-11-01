"""The line-size shapes search (docs/nba_search_shapes.md): every rule the lab adds, on made-up games.

Each rule test here was watched failing with its rule broken once (the run is recorded in the doc's
section 15). Nothing here reads the research cache or a real result."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts import nba_game2_luck as L
from scripts import nba_game2_market as M
from scripts import nba_game2_projection as P
from scripts import nba_game2_verdict as V
from scripts import nba_game4_p2 as P2
from scripts import nba_game6_alt as A
from scripts import nba_game_harness as H
from scripts import nba_s_shapes as S

SHAPE_SEASON = 2024


@pytest.fixture(scope="module", autouse=True)
def coarse_tables():
    """A 0.05-point table in place of 0.01 here: the same arithmetic, five times faster to build."""
    step = H.ResidDist.STEP
    H.ResidDist.STEP = 0.05
    yield
    H.ResidDist.STEP = step


@pytest.fixture(scope="module")
def world():
    return S.synthetic_world()


@pytest.fixture(scope="module")
def built(world):
    return S.synthetic_groups(world)


def group(built, family, market=None, ref=None):
    for g in built["groups"]:
        if g.family == family and (market is None or g.market == market) \
                and (ref is None or g.axis.get("axis_ref") == ref):
            return g
    raise KeyError(family)


def close_frame(season, lines, resid_home):
    n = len(lines)
    return (pd.DataFrame({"game_id": [f"{season}_{i}" for i in range(n)], "season": season, "market": "spreads",
                          "close_line": lines, "close_fa": 0.5,
                          "close_at": pd.Timestamp("2024-01-01T00:00:00Z")}),
            pd.DataFrame({"game_id": [f"{season}_{i}" for i in range(n)], "season": season, "home_score": 100.0,
                          "away_score": 100.0 - np.asarray(lines, float) - np.asarray(resid_home, float)}))


def quote(game, book, line, a=-110.0, b=-110.0, market="spreads", season=2024):
    return {"game_id": game, "season": season, "market": market, "book": book, "line": line, "price_a": a,
            "price_b": b, "coherent": True}


# ── the size of the line and which shape a game reads ───────────────────────

def test_size_of_the_line_edges():
    assert A.spread_bucket([5.0, -5.0, 5.5, -5.5, 10.0, -10.0, 10.5, -10.5]).tolist() == [0, 0, 1, 1, 1, 1, 2, 2]


def test_the_home_number_names_the_favourite():
    rng = np.random.default_rng(1)
    r = rng.normal(0, 12, 900)
    c, g = close_frame(2023, np.r_[np.full(450, -12.5), np.full(450, 12.5)], r)
    d = A.spread_shapes(c, g, seasons=(SHAPE_SEASON,), min_prior=300)
    # a home number of -12.5: the home team is favoured
    assert A.game_sigma(SHAPE_SEASON, "spreads", -12.5, {}, {"spreads": d}) is d[(SHAPE_SEASON, 2, True)]
    assert A.game_sigma(SHAPE_SEASON, "spreads", 12.5, {}, {"spreads": d}) is d[(SHAPE_SEASON, 2, False)]


def test_an_away_favourite_reads_the_mirror():
    """A skewed shape: the home favourite and the away favourite of the same size must price as
    mirror images, or an away favourite's game is priced wrong."""
    rng = np.random.default_rng(2)
    fav_r = np.r_[np.abs(rng.normal(0, 16, 400)), -np.abs(rng.normal(0, 8, 400))]
    lines = np.r_[np.full(400, -12.5), np.full(400, 12.5)]
    r_home = np.r_[fav_r[:400], -fav_r[400:]]             # results toward the favourite, both venues
    c, g = close_frame(2023, lines, r_home)
    d = A.spread_shapes(c, g, seasons=(SHAPE_SEASON,), min_prior=300)
    home_fav, away_fav = d[(SHAPE_SEASON, 2, True)], d[(SHAPE_SEASON, 2, False)]
    w_h, _, _ = home_fav.probs(np.array([5.0]), np.array([0.5]))     # home centre +5, home above +0.5
    w_a, _, l_a = away_fav.probs(np.array([-5.0]), np.array([-0.5]))
    assert abs(w_h[0] - l_a[0]) < 1e-9, "the away favourite's shape is not the mirror of the home favourite's"
    assert abs(w_h[0] - w_a[0]) > 0.01, "the planted shape is not skewed, so this test tests nothing"


def test_a_level_line_and_no_number_read_the_one_shape():
    rng = np.random.default_rng(3)
    c, g = close_frame(2023, np.full(600, -2.5), rng.normal(0, 12, 600))
    d = A.spread_shapes(c, g, seasons=(SHAPE_SEASON,), min_prior=300)
    one = H.ResidDist(rng.normal(0, 12, 500), "one")
    sig = {(SHAPE_SEASON, "spreads"): one}
    assert (SHAPE_SEASON, 0, True) in d
    assert A.game_sigma(SHAPE_SEASON, "spreads", 0.0, sig, {"spreads": d}) is one
    assert A.game_sigma(SHAPE_SEASON, "spreads", np.nan, sig, {"spreads": d}) is one


def test_a_size_short_of_the_floor_reads_the_one_shape():
    rng = np.random.default_rng(4)
    c, g = close_frame(2023, np.full(299, -12.5), rng.normal(0, 12, 299))
    assert A.spread_shapes(c, g, seasons=(SHAPE_SEASON,), min_prior=S.MIN_PRIOR) == {}
    c2, g2 = close_frame(2023, np.full(300, -12.5), rng.normal(0, 12, 300))
    assert (SHAPE_SEASON, 2, True) in A.spread_shapes(c2, g2, seasons=(SHAPE_SEASON,), min_prior=S.MIN_PRIOR)
    assert S.MIN_PRIOR == 300


def test_shapes_read_only_earlier_seasons():
    """Changing the graded season's own results changes nothing in its shape; changing an earlier
    season's does. Both for the market's shape and the projection's."""
    rng = np.random.default_rng(5)
    r = rng.normal(0, 12, 400)
    c1, g1 = close_frame(2023, np.full(400, -2.5), r)
    c2, g2 = close_frame(2024, np.full(400, -2.5), r)
    c, g = pd.concat([c1, c2], ignore_index=True), pd.concat([g1, g2], ignore_index=True)
    base = A.spread_shapes(c, g, seasons=(2024,), min_prior=300)[(2024, 0, True)]
    g_this = g.copy()
    g_this.loc[g_this["season"] == 2024, "home_score"] += 30.0
    same = A.spread_shapes(c, g_this, seasons=(2024,), min_prior=300)[(2024, 0, True)]
    assert np.array_equal(base.win_half, same.win_half)
    proj = pd.DataFrame({"game_id": c["game_id"], "season": c["season"], "margin": 2.5})
    cons = pd.Series(np.full(800, -2.5), index=c["game_id"].to_numpy())
    own = S.own_error_shapes(proj, cons, g, seasons=(2024,), min_prior=300)[(2024, 0, True)]
    own_this = S.own_error_shapes(proj, cons, g_this, seasons=(2024,), min_prior=300)[(2024, 0, True)]
    assert np.array_equal(own.win_half, own_this.win_half), "the projection's shape read its own season"
    g_prev = g.copy()
    g_prev.loc[g_prev["season"] == 2023, "home_score"] += rng.normal(0, 8, 400)
    moved = S.own_error_shapes(proj, cons, g_prev, seasons=(2024,), min_prior=300)[(2024, 0, True)]
    assert not np.array_equal(own.win_half, moved.win_half), "this test's earlier season moved nothing"


def test_the_projection_shape_matches_spread_shapes():
    """With the projection set to the closing number's own margin, the two must be the same tables:
    same buckets, same sign, same mirror."""
    rng = np.random.default_rng(6)
    lines = rng.choice([-2.5, 2.5, -7.5, 7.5, -12.5, 12.5], 2400)
    c, g = close_frame(2023, lines, rng.normal(0, 12, 2400))
    mk = A.spread_shapes(c, g, seasons=(SHAPE_SEASON,), min_prior=300)
    proj = pd.DataFrame({"game_id": c["game_id"], "season": c["season"], "margin": -c["close_line"]})
    cons = pd.Series(c["close_line"].to_numpy(), index=c["game_id"].to_numpy())
    own = S.own_error_shapes(proj, cons, g, seasons=(SHAPE_SEASON,), min_prior=300)
    assert set(mk) == set(own) and len(mk) == 6
    for k in mk:
        assert np.allclose(mk[k].win_whole, own[k].win_whole), k


def test_the_projection_shape_is_not_moved_by_a_filtered_index():
    rng = np.random.default_rng(7)
    c, g = close_frame(2023, np.full(400, -2.5), rng.normal(0, 12, 400))
    proj = pd.DataFrame({"game_id": c["game_id"], "season": c["season"], "margin": rng.normal(3, 2, 400)})
    cons = pd.Series(np.full(400, -2.5), index=c["game_id"].to_numpy())
    a = S.own_error_shapes(proj, cons, g, seasons=(SHAPE_SEASON,), min_prior=300)[(SHAPE_SEASON, 0, True)]
    shifted = proj.copy()
    shifted.index = np.arange(len(proj)) + 1000
    b = S.own_error_shapes(shifted, cons, g, seasons=(SHAPE_SEASON,), min_prior=300)[(SHAPE_SEASON, 0, True)]
    assert np.array_equal(a.win_half, b.win_half)


# ── the one-shape arm is the original pricing ───────────────────────────────

def test_the_one_shape_arm_is_market_fair_number_for_number(built):
    vis = built["extras"]["C"]["vis"]
    a = S.shaped_fair(vis, built["one"])
    b = H.market_fair(vis, built["one"].sig)
    x = a.merge(b, on=["game_id", "market"], suffixes=("", "_h"))
    assert len(x) == len(a) == len(b)
    assert np.allclose(x["mu"].astype(float), x["mu_h"].astype(float), equal_nan=True, atol=1e-9)
    assert np.allclose(x["p_home"].astype(float), x["p_home_h"].astype(float), equal_nan=True)
    assert (x["ref"] == x["ref_h"]).all()


def test_the_line_size_arm_is_not_the_one_shape_arm(built):
    vis = built["extras"]["C"]["vis"]
    sp = vis[vis["market"] == "spreads"]
    a = S.shaped_fair(sp, built["line"]).set_index("game_id")["mu"].astype(float)
    b = S.shaped_fair(sp, built["one"]).set_index("game_id")["mu"].astype(float)
    assert (np.abs(a - b.reindex(a.index)) > 1e-6).mean() > 0.5


def test_every_quote_on_a_game_reads_one_shape():
    """With no Pinnacle quote the game's number is the deciding books' median. Books at -10 and -10.5
    straddle a size edge; all of them must read the shape of that median, not each its own."""
    rng = np.random.default_rng(8)
    lines = rng.choice([-7.5, -12.5], 1600)
    c, g = close_frame(2023, lines, rng.normal(0, 12, 1600))
    shapes = A.spread_shapes(c, g, seasons=(SHAPE_SEASON,), min_prior=300)
    one = H.ResidDist(rng.normal(0, 12, 500), "one")
    pr = S.Pricing("line", {(SHAPE_SEASON, "spreads"): one}, {"spreads": shapes})
    v = pd.DataFrame([quote("g", "draftkings", -10.0), quote("g", "fanduel", -10.5), quote("g", "betmgm", -10.5)])
    f = S.shaped_fair(v, pr)
    assert f.loc[0, "sigma"] is shapes[(SHAPE_SEASON, 2, True)]   # the median, -10.5, is over 10
    assert f.loc[0, "ref"] == "consensus"
    v2 = pd.DataFrame([quote("g", "draftkings", -10.0), quote("g", "fanduel", -10.0), quote("g", "betmgm", -10.5)])
    assert S.shaped_fair(v2, pr).loc[0, "sigma"] is shapes[(SHAPE_SEASON, 1, True)]
    v3 = pd.DataFrame([quote("g", "pinnacle", -12.5), quote("g", "fanduel", -10.0)])
    assert S.shaped_fair(v3, pr).loc[0, "sigma"] is shapes[(SHAPE_SEASON, 2, True)]


def test_one_shape_f2_is_the_original_reference(built):
    vis = built["extras"]["C"]["vis"]
    off = H.offers(vis)
    off = off[off["market"] == "h2h"]
    for ref in S.F2_REFS:
        got = S.f2_arm(vis, off, built["one"], ref)
        orig = M.reference_fair(vis, built["one"].sig, ref)
        fav = M.favourite_home(orig)
        p = orig.set_index("game_id").loc[fav.index, "p_home"].astype(float)
        mine = got["base"].drop_duplicates("game_id").set_index("game_id")["p_home"].astype(float)
        assert np.allclose(mine.reindex(p.index), p, atol=1e-9), ref


def test_one_shape_own_book_is_the_original(built):
    vis = built["extras"]["C"]["vis"]
    a, b = S.own_book_fairs(vis, built["one"]), M.own_book_ml_fair(vis, built["one"].sig)
    assert set(a) == set(b) and len(a) >= 3
    for book in a:
        x = a[book].merge(b[book], on="game_id", suffixes=("", "_o"))
        assert len(x) == len(a[book]) and np.allclose(x["p_home"], x["p_home_o"], atol=1e-9), book


def test_one_shape_projection_is_the_original(world, built):
    data, base = world["data"], world["base"]
    proj = base[["game_id", "season", "margin", "total"]]
    dist = P.projection_dist(data.games, proj)
    cons = pd.Series(-proj["margin"].to_numpy(), index=proj["game_id"].to_numpy())
    a = S.own_fair(proj, dist, {}, cons)
    b = P.fair_frame(proj, dist)
    b = b[b["market"].isin(S.MARKETS)]
    x = a.merge(b, on=["game_id", "market"], suffixes=("", "_o"))
    assert len(x) == len(a) == len(b)
    assert np.allclose(x["mu"].astype(float), x["mu_o"].astype(float), equal_nan=True)
    assert np.allclose(x["p_home"].astype(float), x["p_home_o"].astype(float), equal_nan=True, atol=1e-9)


# ── the mechanism ───────────────────────────────────────────────────────────

def test_a_big_underdog_reads_a_smaller_chance_under_its_own_shape(built):
    """Section 10.7's reason for this search: one shape overstates a big underdog's outright chance."""
    gap = S.underdog_gap(built["extras"]["C"]["vis"], built["line"], built["one"])
    assert gap["games"] > 50, "the synthetic world holds too few big lines to test this"
    assert gap["line_mean"] < gap["one_mean"] - 0.01, gap


def test_the_synthetic_world_holds_what_the_checks_claim(world):
    data = world["data"]
    assert set(data.quotes["market"]) == {"h2h", "spreads"}
    pin = data.quotes[(data.quotes["market"] == "spreads") & (data.quotes["book"] == H.SHARP)]
    assert set(A.spread_bucket(pin["line"])) == {0, 1, 2}
    assert (pin["line"] == 0.0).any(), "no level line"
    assert (pin["line"] < 0).any() and (pin["line"] > 0).any()
    assert data.games["season"].nunique() == 6
    assert (data.games["home_score"] != data.games["away_score"]).all()


# ── numbers that cannot be read ─────────────────────────────────────────────

def test_the_rule_drops_a_flipped_spread_and_keeps_the_rest():
    v = pd.DataFrame([quote("g", "draftkings", -3.5), quote("g", "fanduel", 3.5), quote("g", "betmgm", -3.5),
                      quote("g", "betrivers", -4.0), quote("g", "pinnacle", -3.5)])
    assert S.impossible_mask(v).tolist() == [False, True, False, False, False]


def test_the_rule_reads_pinnacle_too():
    v = pd.DataFrame([quote("g", "draftkings", 10.5), quote("g", "fanduel", 10.5), quote("g", "betmgm", 10.0),
                      quote("g", "pinnacle", 5.5)])
    assert S.impossible_mask(v).tolist() == [False, False, False, True]


def test_the_rule_stops_at_two_and_a_half_points():
    v = pd.DataFrame([quote("g", "draftkings", -3.0), quote("g", "fanduel", -3.0), quote("g", "betmgm", -3.0),
                      quote("g", "betrivers", -5.5), quote("g", "pinnacle", 0.0)])
    assert S.impossible_mask(v).tolist() == [False, False, False, False, True]


def test_the_rule_reads_a_moneyline_in_win_chance():
    ml = dict(market="h2h", line=np.nan)
    v = pd.DataFrame([quote("g", "draftkings", a=-150.0, b=130.0, **ml), quote("g", "fanduel", a=-150.0, b=130.0, **ml),
                      quote("g", "betmgm", a=-155.0, b=135.0, **ml), quote("g", "pinnacle", a=135.0, b=-155.0, **ml)])
    assert S.impossible_mask(v).tolist() == [False, False, False, True]


def test_the_rule_needs_three_books():
    v = pd.DataFrame([quote("g", "draftkings", -3.5), quote("g", "fanduel", -3.5), quote("g", "pinnacle", 8.0)])
    assert not S.impossible_mask(v).any()


def test_the_rule_is_read_by_position_on_a_filtered_frame():
    v = pd.DataFrame([quote("x", "draftkings", 2.0), quote("g", "draftkings", -3.5), quote("g", "fanduel", 3.5),
                      quote("g", "betmgm", -3.5), quote("g", "betrivers", -3.5)])
    f = v[v["game_id"] == "g"]                     # the labels now start at 1
    assert S.impossible_mask(f).tolist() == [False, True, False, False]
    assert S.clean(f)["book"].tolist() == ["draftkings", "betmgm", "betrivers"]


def test_the_planted_bad_numbers_never_reach_an_offer(built):
    vis = built["extras"]["C"]["vis"]
    assert not S.impossible_mask(vis).any()
    sp = vis[(vis["market"] == "spreads") & vis["book"].isin(H.BETTABLE)]
    assert (sp.groupby("game_id")["line"].max() - sp.groupby("game_id")["line"].min()).max() <= 2 * S.MAX_SPREAD_GAP
    dropped = pd.concat(built["ledger"], ignore_index=True)
    assert set(dropped["book"]) >= {"fanduel", "pinnacle"}, "the world's bad rows were not what the rule dropped"
    assert set(dropped["market"]) == {"h2h", "spreads"}


def test_an_unreadable_close_leaves_the_shapes(world):
    close, dropped = S.clean_close(world["data"])
    assert len(dropped) > 0 and set(dropped["market"]) == {"h2h", "spreads"}
    key = set(zip(dropped["game_id"], dropped["market"]))
    assert not key & set(zip(close["game_id"], close["market"]))


# ── what no shape reaches ───────────────────────────────────────────────────

def test_same_number_bets_cannot_move(built):
    t = built["extras"]["C"]["times"]
    a = P2.same_number_cand(S.p2_point(built["q_main"], built["q_same"], t, built["line"]))
    b = P2.same_number_cand(S.p2_point(built["q_main"], built["q_same"], t, built["one"]))
    key = ["game_id", "market", "book", "side", "line", "price"]
    x = a.sort_values(key).reset_index(drop=True)
    y = b.sort_values(key).reset_index(drop=True)
    assert len(x) > 100 and (x["game_id"] == y["game_id"]).all()
    assert np.allclose(x["ev"].astype(float), y["ev"].astype(float))


def test_p1_moneyline_reads_no_shape(world, built):
    t = built["extras"]["C"]["times"]
    from models.nba_book_numbers import visible_numbers
    vis = S.clean(visible_numbers(world["data"].quotes, t))
    a, b = S.shaped_fair(vis, built["line"]), S.shaped_fair(vis, built["one"])
    a, b = a[a["market"] == "h2h"].set_index("game_id"), b[b["market"] == "h2h"].set_index("game_id")
    assert len(a) > 50 and np.allclose(a["p_home"].astype(float), b["p_home"].reindex(a.index).astype(float))


def test_the_one_shape_arm_changes_off_number_prices_not_gaps(built):
    g = group(built, S.FAM_P2)
    a = g.line["home"].sort_values(["game_id", "book", "side"]).reset_index(drop=True)
    b = g.one["home"].sort_values(["game_id", "book", "side"]).reset_index(drop=True)
    assert len(a) == len(b) > 100
    assert np.allclose(a["strength"].astype(float), b["strength"].astype(float))
    assert np.abs(a["ev"].astype(float) - b["ev"].astype(float)).max() > 1e-4, "the shape priced nothing"


# ── the fast chooser and placebo against the harness ────────────────────────

def test_fast_choice_is_h_choose_with_ties_floor_and_books():
    rows = []
    for g in ("a", "b", "c"):
        rows += [{"game_id": g, "market": "h2h", "season": 2024, "side": "home", "line": np.nan, "book": bk, "price": p}
                 for bk, p in (("fanduel", 120.0), ("draftkings", 120.0), ("betmgm", 110.0),
                               ("pinnacle", 500.0), ("betrivers", -500.0))]
    pool = pd.DataFrame(rows)
    games = pd.DataFrame({"game_id": ["a", "b", "c"], "season": 2024, "home_score": [110.0, 90.0, 100.0],
                          "away_score": [100.0, 100.0, 90.0]})
    fast = S.Fast(pool, {"home": (pool["side"] == "home").to_numpy()}, games, (2024,))
    ev = np.where(pool["price"] > 0, 0.05, 0.9)   # the -500 offer has the top EV but is under the floor
    ev[(pool["book"] == "pinnacle").to_numpy()] = 0.7   # the next best, and never a deciding price
    ev[pool.index[(pool["game_id"] == "c")]] = np.nan
    chosen = fast.at_cut(ev, fast.best(ev, "home"), 0.0)
    h = H.choose(pool.assign(ev=ev, p_win=0.5, p_push=0.0), 0.0, sides=["home"])
    assert set(pool.loc[chosen, "game_id"]) == set(h["game_id"]) == {"a", "b"}
    # the 0.05 tie goes to the earlier book, as the harness does; Pinnacle never
    assert pool.loc[chosen, "book"].tolist() == h["book"].tolist()
    assert set(h["book"]) == {H.BETTABLE[min(H.BOOK_RANK["fanduel"], H.BOOK_RANK["draftkings"])]}


def test_fast_real_choice_is_the_harness_choice_on_every_family(world, built):
    games = world["data"].games
    assert {g.family for g in built["groups"]} == set(S.FAMILIES)
    for g in built["groups"]:
        fast = S.Fast(g.pool, g.masks, games, H.CHOOSE)
        spec = S.build_spec(g)
        real = (S.run_model if isinstance(spec, S.Model) else S.run_gap)(fast, spec, g.cuts, None)
        for lab in g.labels:
            for k, cut in enumerate(g.cuts):
                h = S.pick(g.line[lab], cut, lab, g.strength)
                got = g.pool.iloc[real[(lab, k)]]
                assert set(zip(h["game_id"], h["book"], h["side"])) == set(zip(got["game_id"], got["book"], got["side"])), \
                    (g.name(), lab, cut)
                roi = H.roi(H.grade(h, games)[lambda b: b["season"].isin(H.CHOOSE)]) if len(h) else np.nan
                mine = fast.roi(real[(lab, k)])
                assert (np.isnan(roi) and np.isnan(mine)) or abs(roi - mine) < 1e-9, (g.name(), lab, cut)


def slow_placebo_roi(g, spec, games, seed, lab, cut):
    """The harness's route for one placebo run: price the moved numbers through H.fair_offers, choose
    and grade with the harness. What fast_placebo must equal."""
    v = spec.values_at(spec.perm(seed))
    keys = g.pool.iloc[pd.DataFrame({"k": spec.key}).drop_duplicates("k").index]
    moved = g.pool.drop(columns=["ev"]).copy()
    if spec.kind == "ml":
        moved["p_home"] = S._expit(v)[spec.key]
    else:
        moved["mu"] = v[spec.key]
    pw, pp = H.side_probs(moved["market"].to_numpy(), moved["side"].to_numpy(), moved["line"].to_numpy(),
                          mu=moved["mu"].to_numpy(float), sigma=moved["sigma"].to_numpy(dtype=object),
                          p_home=moved["p_home"].to_numpy(float))
    c = H.with_ev(moved.assign(p_win=pw, p_push=pp))
    b = H.grade(H.choose(c[g.masks[lab]], cut, sides=None), games)
    b = b[b["season"].isin(H.CHOOSE)]
    assert len(keys) == len(spec.value)
    return H.roi(b) if len(b) else np.nan


@pytest.mark.parametrize("family,market,ref", [(S.FAM_F2, None, "pinnacle"), (S.FAM_F1, "spreads", None),
                                               (S.FAM_F1, "h2h", None), (S.FAM_P1, None, None), (S.FAM_F6D, None, None)])
def test_fast_placebo_equals_the_harness_route(world, built, family, market, ref):
    games = world["data"].games
    g = group(built, family, market, ref)
    spec = S.build_spec(g)
    fast = S.Fast(g.pool, g.masks, games, H.CHOOSE)
    got = S.fast_placebo(fast, spec, g.cuts, seeds=(1, 2))
    for lab in g.labels:
        for k, cut in enumerate(g.cuts):
            for i, seed in enumerate((1, 2)):
                slow = slow_placebo_roi(g, spec, games, seed, lab, cut)
                mine = got[(lab, k)][i]
                assert (np.isnan(slow) and np.isnan(mine)) or abs(slow - mine) < 1e-9, (family, lab, cut, seed)


def test_fast_gap_placebo_equals_the_original_placebo(world, built):
    games = world["data"].games
    g = group(built, S.FAM_P2)
    spec = S.build_spec(g)
    fast = S.Fast(g.pool, g.masks, games, H.CHOOSE)
    got = S.fast_placebo(fast, spec, g.cuts, seeds=(1, 2))
    for i, seed in enumerate((1, 2)):
        c = P2.off_number_placebo(g.pool, seed)
        for lab in g.labels:
            for k, cut in enumerate(g.cuts):
                b = H.grade(S.pick(c, cut, lab, "strength"), games)
                b = b[b["season"].isin(H.CHOOSE)]
                slow = H.roi(b) if len(b) else np.nan
                mine = got[(lab, k)][i]
                assert (np.isnan(slow) and np.isnan(mine)) or abs(slow - mine) < 1e-9, (lab, cut, seed)


def test_the_identity_repeats_the_real_numbers(world, built):
    for g in built["groups"]:
        spec = S.build_spec(g)
        if not isinstance(spec, S.Model):
            continue
        ev = spec.ev(spec.values_at(np.arange(len(spec.value))))
        real = g.pool["ev"].to_numpy(float)
        ok = np.isfinite(real) & np.isfinite(ev)
        assert ok.mean() > 0.95, g.name()
        # a win chance inside the log-odds clip is the one place the fast route may round
        inside = (g.pool["p_win"].to_numpy(float) > 2 * S.P_CLIP) & (g.pool["p_win"].to_numpy(float) < 1 - 2 * S.P_CLIP)
        assert (ok & inside).mean() > 0.9, g.name()
        assert np.abs(ev[ok & inside] - real[ok & inside]).max() < 1e-9, g.name()


def test_the_placebo_moves_opinions_only_within_a_date_and_keeps_the_market():
    groups = [np.array([0, 1, 2]), np.array([3, 4])]
    for seed in range(1, 20):
        perm = S.permute_within(groups, 5, seed)
        assert set(perm[:3]) == {0, 1, 2} and set(perm[3:]) == {3, 4}
    spec = S.Model("spread", np.arange(5), np.array([10.0, 20.0, 30.0, 40.0, 50.0]), np.array([9.0, 18.0, 27.0, 36.0, 45.0]),
                   np.ones(5), groups, np.ones(5, bool), np.full(5, 2.0), np.zeros(5), [])
    v = spec.values_at(np.array([1, 0, 2, 3, 4]))
    # game 0 keeps its own market number 9 and takes game 1's disagreement of 2
    assert v[0] == 11.0 and v[1] == 19.0 and v[2] == 30.0


def test_every_book_reads_the_same_other_game_in_a_run():
    """§10.1: one shuffle of games per date. A game a book does not price leaves it no opinion."""
    pool = pd.DataFrame({"game_id": ["a", "a", "b", "b", "c"], "book": ["x", "y", "x", "y", "x"],
                         "game_date": ["d"] * 5, "p_home": [.5, .6, .5, .6, .5], "market": ["h2h"] * 5,
                         "side": ["home"] * 5, "price": [100.0] * 5, "line": [np.nan] * 5})
    market = pool[["game_id", "book"]].assign(p_home=.5)
    spec = S.build_model(pool, market, ("game_id", "book"), "ml", by_book=True)
    keys = pool[["game_id", "book"]].drop_duplicates().reset_index(drop=True)
    seen = set()
    for seed in range(1, 30):
        perm = spec.perm(seed)
        moved = {}
        for k, p in enumerate(perm):
            if p < 0:
                assert keys.loc[k, "book"] == "y", "only book y lacks a game"
                continue
            assert keys.loc[p, "book"] == keys.loc[k, "book"], "a book keeps its own numbers"
            moved.setdefault(keys.loc[k, "game_id"], set()).add(keys.loc[p, "game_id"])
        assert all(len(v) == 1 for v in moved.values()), "one game reads one other game, at every book"
        seen |= {(g, next(iter(v))) for g, v in moved.items()}
    assert len(seen) > 3, "the shuffle moves"
    v = spec.values_at(np.array([-1, 1, 2, 3, 4]))
    assert np.isnan(v[0]) and np.isfinite(v[1:]).all()


def test_a_placebo_keyed_by_book_bets_about_as_often_as_the_real_rule():
    """One shuffle per date keeps the bet rate; a shuffle per book more than doubled it (§10.1)."""
    rng = np.random.default_rng(3)
    rows = []
    for d in range(120):
        for g in range(8):
            shift = rng.normal(0, .25)
            for b in range(6):
                rows.append({"game_id": f"g{d}_{g}", "book": f"b{b}", "game_date": f"d{d}",
                             "p_home": float(S._expit(shift + rng.normal(0, .01))), "market": "h2h", "side": "home",
                             "price": 100.0, "line": np.nan})
    pool = pd.DataFrame(rows)
    market = pool[["game_id", "book"]].assign(p_home=.5)
    spec = S.build_model(pool, market, ("game_id", "book"), "ml", by_book=True)
    ev_real = spec.ev(spec.values_at(np.arange(len(spec.value))))
    real = pd.Series(ev_real >= .1).groupby(pool["game_id"].to_numpy()).any().sum()
    for seed in range(1, 6):
        run = pd.Series(spec.ev(spec.values_at(spec.perm(seed))) >= .1).groupby(pool["game_id"].to_numpy()).any().sum()
        assert abs(run - real) <= .2 * real, (seed, real, run)


def test_s_p1_reads_no_home_road_count(monkeypatch):
    """§10.1: above zero only on a neutral site's designated home team, so it is read as 0."""
    seen = {}
    monkeypatch.setattr(S.P1, "model_rows", lambda *a: pd.DataFrame({"h_road_no": [0.0, 1.0, 3.0], "a_road_no": [1.0, 2.0, 0.0]}))

    def stop(rows, *a, **k):
        seen["rows"] = rows.copy()
        raise KeyboardInterrupt
    monkeypatch.setattr(S.P1, "walk_forward", stop)
    with pytest.raises(KeyboardInterrupt):
        S.p1_cand(pd.DataFrame({"market": []}), None, None, None, "spreads", 10)
    assert seen["rows"]["h_road_no"].eq(0.0).all()
    assert seen["rows"]["a_road_no"].tolist() == [1.0, 2.0, 0.0], "the away team's road count is real"


def test_the_favourite_keeps_its_side_when_the_opinion_moves():
    """F2: a disagreement that favours the favourite stays with the favourite on the other game,
    whichever venue that favourite is at."""
    spec = S.Model("ml", np.arange(2), np.array([1.0, -1.2]), np.array([0.8, -0.8]), np.array([1.0, -1.0]),
                   [np.array([0, 1])], np.ones(2, bool), np.full(2, 2.0), np.zeros(2), [])
    v = spec.values_at(np.array([1, 0]))
    # game 0's home favourite takes game 1's +0.4 for its away favourite: home log-odds 0.8 + 0.4
    # game 1's away favourite takes game 0's +0.2: home log-odds -0.8 - 0.2
    assert np.allclose(v, [1.2, -1.0])


def test_the_placebo_is_a_null_on_made_up_games(world, built):
    games = world["data"].games
    for g in built["groups"]:
        fast = S.Fast(g.pool, g.masks, games, H.CHOOSE)
        d = S.differ_shares(fast, S.build_spec(g), g.cuts, seeds=(1, 2, 3))
        d = d[d["placebo_bets_per_run"] >= 20]
        if len(d):
            assert d["differ_offer"].mean() > 0.3, (g.name(), d.to_dict("records"))


def test_the_placebo_reads_the_seasons_the_cell_reads(world, built):
    """At D the harness drops a choosing season reached on under 95% of its games, from the cell's own
    return. A placebo that kept it would be compared with a return over different seasons."""
    from dataclasses import replace
    data = world["data"]
    g = group(built, S.FAM_P2)
    assert S.placebo_seasons(data, g, H.CHOOSE) == tuple(H.CHOOSE)
    season = data.games.set_index("game_id")["season"]
    short = g.times[season.reindex(g.times["game_id"]).to_numpy() != H.CHOOSE[1]]
    d = replace(g, point=H.GATE_POINT, times=short)
    kept = S.placebo_seasons(data, d, H.CHOOSE)
    assert H.CHOOSE[1] not in kept and len(kept) == len(H.CHOOSE) - 1
    row = H.run_cells(S.slim(data, g.market, short), g.family, H.GATE_POINT, g.line[g.labels[0]], g.neutral_line[g.labels[0]],
                      [g.cuts[0]], {g.market: [g.labels[0]]}, close=built["close"], sig=built["line"].sig, strength=g.strength,
                      times=short)[0]
    assert row["choose_seasons"] == ",".join(str(x) for x in kept)
    fast = S.Fast(g.pool, g.masks, data.games, kept)
    assert not fast.choosing[g.pool["season"].to_numpy() == H.CHOOSE[1]].any()


def test_two_hundred_runs_seeds_one_to_two_hundred():
    assert S.N_PLACEBO == 200 and S.SEEDS == tuple(range(1, 201))


# ── the cells and the verdict ───────────────────────────────────────────────

def test_the_registered_cells():
    plan = S.cell_plan()
    assert len(plan) == S.EXPECTED_CELLS == 256
    by = pd.Series([c[0] for c in plan]).value_counts().to_dict()
    assert by == {"S_F2": 96, "S_F6d": 8, "S_F1": 96, "S_P1": 24, "S_P2": 32}
    assert len(S.control_plan()) == 88
    assert S.EV_CUTS == P.FAMILIES["F1"]["cuts"] == M.F2_CUTS
    assert S.F6D_CUTS == M.F6D_CUTS and S.GAP_CUTS == P2.CUTS["off_number"] and S.SAME_CUTS == P2.CUTS["same_number"]
    from scripts import nba_game4_p1 as P1
    assert S.P1_CUTS == P1.CUTS and S.POINTS_P1 == P1.FULL_POINTS and S.POINTS_ALL == P2.FULL_POINTS == M.F2_POINTS
    assert S.POINTS_F6D == M.F6D_POINTS


def test_the_doc_registers_what_the_lab_runs():
    text = (Path(__file__).resolve().parents[1] / "docs" / "nba_search_shapes.md").read_text(encoding="utf-8")
    for needle in ("**256**", "2.5 points", "0.08", "3 or more", "300 earlier games", "seeds 1 to 200", "6.4"):
        assert needle in text, needle
    assert S.MAX_SPREAD_GAP == 2.5 and S.MAX_ML_GAP == 0.08 and S.MIN_BOOKS == 3


def test_the_verdict_judges_a_cell_and_refuses_another_placebo_count(world, built, tmp_path):
    data = world["data"]
    g = group(built, S.FAM_P2)
    rows = S.run_group(S.slim(data, g.market, g.times), g, built["close"], built["line"].sig, data.games, "line", seeds=(1, 2))
    twins = S.run_group(S.slim(data, g.market, g.times), g, built["close"], built["line"].sig, data.games, "one", seeds=(1, 2))
    assert {r["family"] for r in twins} == {S.oneshape(S.FAM_P2)}
    assert all(r["placebo_rois"] == [] for r in twins)
    S.write_rows(rows + twins, tmp_path)
    cells = V.load_cells(tmp_path)
    assert len(cells) == 2 * len(rows)
    v = V.house_verdict_bands(cells, n_placebo=2)
    assert set(v["family"]) == {S.FAM_P2}, "a control was judged"
    assert v["house5_passes"].dtype == bool and {"band0_n", "band0_roi"} <= set(v.columns)
    with pytest.raises(ValueError):
        V.house_verdict_bands(cells)                # 2 placebo runs, the bars fix 200


def test_bets_are_written_without_pricing_objects(world, built, tmp_path, monkeypatch):
    data = world["data"]
    g = group(built, S.FAM_P1)
    monkeypatch.setenv(S.BETS_ENV, str(tmp_path))
    S.run_group(S.slim(data, g.market, g.times), g, built["close"], built["line"].sig, data.games, "line", seeds=(1,))
    files = list((tmp_path / S.FAM_P1).glob("bets_*.parquet"))
    assert files, "no bets were written"
    b = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    assert "sigma" not in b and "units" in b and len(b)
    assert not [c for c in b.columns if b[c].map(lambda v: isinstance(v, H.ResidDist)).any()]


def test_the_slim_quotes_change_no_report(world, built):
    """H.run_cells reads the quotes only for "still offered at the next fetch". The one fetch's quotes
    handed to it must give that report exactly."""
    data = world["data"]
    for g in (group(built, S.FAM_F2, ref="pinnacle"), group(built, S.FAM_P1), group(built, S.FAM_P2)):
        b = S.pick(g.line[g.labels[0]], g.cuts[0], g.labels[0], g.strength)
        assert len(b) > 20, g.name()
        full = H.next_fetch_check(b, data)
        mine = H.next_fetch_check(b, S.slim(data, g.market, g.times))
        assert full.any(), "nothing was still offered, so this test tests nothing"
        assert full.equals(mine), g.name()
        assert len(S.slim(data, g.market, g.times).quotes) < len(data.quotes[data.quotes["market"] == g.market]) / 3


def test_the_slim_quotes_read_the_first_later_fetch(world):
    """At point C the next fetch is this world's last, so the test above cannot tell the first later
    fetch from the last. At point A three fetches follow, and only the first is the report's."""
    data = world["data"]
    t = H.decision_times(data.fetches, data.games, "A")
    off = H.offers(H.visible(data.quotes, t))
    b = off[(off["market"] == "spreads") & (off["book"] == "draftkings") & (off["side"] == "home")].reset_index(drop=True)
    assert len(b) > 100
    later = t.merge(data.fetches[["game_id", "fetch_at"]], on="game_id")
    later = later[later["fetch_at"] > later["T"]].groupby("game_id").size()
    assert later.min() >= 2, "one later fetch cannot tell first from last"
    full = H.next_fetch_check(b, data)
    mine = H.next_fetch_check(b, S.slim(data, "spreads", t))
    assert full.any(), "nothing was still offered, so this test tests nothing"
    assert full.equals(mine)


def test_the_compare_table_counts_both_arms(world, built):
    g = group(built, S.FAM_F2, ref="pinnacle")
    rows = S.compare_group(g, world["data"].games)
    assert len(rows) == len(g.labels) * len(g.cuts)
    for r in rows:
        assert r["n_same_bet"] + r["n_games_only_line"] + r["n_games_other_offer"] == r["n_line"]
        assert r["n_same_bet"] + r["n_games_only_one"] + r["n_games_other_offer"] == r["n_one"]
    assert sum(r["n_line"] - r["n_same_bet"] for r in rows) > 0, "the shape moved no bet in this world"
    no_grade = S.compare_group(g, None)
    assert "units_line" not in no_grade[0]


def test_the_shares_say_what_an_independent_shuffle_would_show(world, built):
    g = group(built, S.FAM_F2, ref="pinnacle")
    fast = S.Fast(g.pool, g.masks, world["data"].games, H.CHOOSE)
    spec = S.build_spec(g)
    d = S.differ_shares(fast, spec, g.cuts, seeds=(1, 2, 3))
    assert d["differ_game_if_independent"].between(0.0, 1.0).all() and d["differ_game"].between(0.0, 1.0).all()
    r = d[d["label"] == "dog"].iloc[0]
    games = len(np.unique(fast.gid[fast.idx["dog"]]))
    assert r["differ_game_if_independent"] == pytest.approx(1.0 - r["real_bets"] / games)
    # the shuffle really moves: a date holds 8 games here, so about one opinion in eight stays
    assert S.kept_own_share(spec, (1, 2, 3)) == pytest.approx(1.0 / 8.0, abs=0.05)


# ── no grade in the smoke run; the refusals ─────────────────────────────────

def test_the_smoke_work_never_reads_a_real_result(world, built, monkeypatch):
    data = world["data"]
    fake = S.scrambled(data.games)
    assert not np.array_equal(fake["home_score"].to_numpy(), data.games["home_score"].to_numpy())
    seen = []
    real_grade = H.grade

    def spy(bets, games):
        seen.append(games)
        return real_grade(bets, games)
    monkeypatch.setattr(H, "grade", spy)
    g = group(built, S.FAM_F2, ref="pinnacle")
    got = S.smoke_group(g, data, fake, built["close"], built["line"].sig)
    assert seen and all(x["home_score"].equals(fake["home_score"]) for x in seen), "a real result was graded"
    assert got["timing"]["one_run_s"] >= 0 and len(got["counts"]) == 12 and len(got["top"]) == 6
    assert 0.0 <= got["timing"]["kept_own"] < 0.5, "most opinions stayed on their own game"
    seen.clear()
    timed = S.time_group(data, g, built["close"], built["line"].sig, fake)
    assert seen and all(x["home_score"].equals(fake["home_score"]) for x in seen), "the timing pass graded a real result"
    assert timed["line_cell_s"] > 0 and timed["one_cell_s"] > 0 and timed["cells"] == 12


def test_the_timing_pass_writes_no_bets(world, built, tmp_path, monkeypatch):
    data = world["data"]
    monkeypatch.setenv(S.BETS_ENV, str(tmp_path))
    g = group(built, S.FAM_P2)
    S.time_group(data, g, built["close"], built["line"].sig, S.scrambled(data.games))
    assert not list(tmp_path.rglob("*.parquet")), "scrambled scores reached the bets folder"
    assert S.os.environ[S.BETS_ENV] == str(tmp_path)


def test_the_projection_counts_every_stage():
    stage = {"load_s": 100.0, "groups_s": 200.0}
    per = pd.DataFrame({"family": ["S_F2", "S_F2", "S_P2"], "market": ["h2h", "h2h", "spreads"], "cells": [12, 12, 8],
                        "build_s": [1.0, 1.0, 2.0], "one_run_s": [0.05, 0.05, 0.1]})
    whole = pd.DataFrame({"family": ["S_F2", "S_P2"], "market": ["h2h", "spreads"], "cells": [12, 8], "line_cell_s": [5.0, 3.0],
                          "one_cell_s": [4.0, 2.0], "compare_s": [6.0, 3.0]})
    got = S.projected_full(stage, per, whole, S.CONTROLS_AT_TIMED_POINT * 2.0)
    assert got["registered_cells_s"] == 12 * 5.0 * 2 + 8 * 3.0
    assert got["twins_s"] == 12 * 4.0 * 2 + 8 * 2.0
    assert got["placebo_200_runs_s"] == (0.05 * 200 + 1.0) * 2 + 0.1 * 200 + 2.0
    assert got["compare_s"] == 15.0 and got["controls_s"] == 88 * 2.0
    assert got["projected_full_s"] == 300.0 + 144.0 + 112.0 + 44.0 + 15.0 + 176.0
    with pytest.raises(AssertionError):
        S.projected_full(stage, per, whole[whole["family"] == "S_F2"], 1.0)


def test_a_saved_projection_from_other_times_is_not_used():
    t = pd.Timestamp("2024-01-02 15:00", tz="UTC")
    times = pd.DataFrame({"game_id": ["a", "b", "c"], "T": [t, t, t]})
    frame = pd.DataFrame({"game_id": ["a", "b"], "T": [t, t], "margin": [1.0, 2.0]})
    assert S.frame_matches(frame, times)
    assert not S.frame_matches(frame.assign(T=[t, t + pd.Timedelta(minutes=30)]), times)
    assert not S.frame_matches(pd.concat([frame, frame.assign(game_id="d")], ignore_index=True), times)


def test_a_p_stays_at_the_interval_resamples(monkeypatch):
    """Section 9.1 reads the interval, never a p. A strongly positive cell must not pay for 400,000."""
    monkeypatch.setattr(H, "P_REFINE_BELOW", H.P_REFINE_BELOW)
    S.reports_without_refined_p()
    calls = []
    real = H.boot
    monkeypatch.setattr(H, "boot", lambda b, n=H.N_BOOT, seed=H.SEED: calls.append(n) or real(b, n=n, seed=seed))
    b = pd.DataFrame({"game_date": [f"2024-01-{d:02d}" for d in range(1, 29)], "units": 1.0, "risk": 1.0})
    assert H.p_one_sided(b) == 0.0
    assert calls == [H.N_BOOT]


def test_the_bars_read_no_p(world, built, tmp_path):
    data = world["data"]
    g = group(built, S.FAM_P2)
    S.write_rows(S.run_group(S.slim(data, g.market, g.times), g, built["close"], built["line"].sig, data.games, "line", seeds=(1, 2)), tmp_path)
    cells = V.load_cells(tmp_path)
    cells = cells.assign(pool_n=1000)       # past the first bar, so a bar reading a p would show
    a = V.house_verdict_bands(cells.assign(p_confirm=0.0, p_choose=0.0), n_placebo=2)
    b = V.house_verdict_bands(cells.assign(p_confirm=1.0, p_choose=1.0), n_placebo=2)
    assert a[V.FIFTH_BARS].any().any(), "no bar holds here, so this test tests nothing"
    assert a[V.FIFTH_BARS].equals(b[V.FIFTH_BARS])


def test_every_family_reaches_the_verdict(world, built, tmp_path):
    data = world["data"]
    rows = []
    for fam, m, ref in ((S.FAM_F2, None, "pinnacle"), (S.FAM_F2, None, "consensus"), (S.FAM_F6D, None, None),
                        (S.FAM_F1, "h2h", None), (S.FAM_F1, "spreads", None), (S.FAM_P1, None, None), (S.FAM_P2, None, None)):
        g = group(built, fam, m, ref)
        rows += S.run_group(S.slim(data, g.market, g.times), g, built["close"], built["line"].sig, data.games, "line", seeds=(1, 2))
    S.write_rows(rows, tmp_path)
    v = V.house_verdict_bands(V.load_cells(tmp_path), n_placebo=2)
    assert set(v["family"]) == set(S.FAMILIES) and len(v) == len(rows)
    f2 = v[v["family"] == S.FAM_F2]
    assert set(f2["side"]) == {"fav", "dog"} and set(f2["axis_ref"]) == {"pinnacle", "consensus"}
    # the blind bet the fourth bar reads exists on a label that is not a real side
    assert f2["pool_share_fav"].notna().any() and f2["blind_pool_fav"].notna().any()
    assert all(len(x) == 2 for x in v["placebo_rois"])
    for fam, x in v.groupby("family"):
        assert x["band0_n"].notna().all() and (x["band0_n"] > 0).any(), f"{fam} has no bands"


def test_the_groups_emit_the_registered_cells_at_every_point(world):
    built_all = S.synthetic_groups(world, points=S.POINTS_ALL)
    assert S.groups_plan(built_all["groups"]) == set(S.cell_plan())


def test_full_refuses_without_its_settings(tmp_path):
    (tmp_path / P.LEDGER_FILE).write_bytes(b"")
    (tmp_path / P.STINTS_FILE).write_bytes(b"")
    why = S.refuse_full(tmp_path, env={})
    assert len(why) == 3 and all(any(k in w for w in why) for k in (S.GO_ENV, S.RESULTS_ENV, S.BETS_ENV))
    res = tmp_path / "results"
    res.mkdir()
    ok = {S.GO_ENV: "1", S.RESULTS_ENV: str(res), S.BETS_ENV: str(res / "bets")}
    assert S.refuse_full(tmp_path, env=ok) == []
    (res / "cells_F7.parquet").write_bytes(b"")
    assert any("another search" in w for w in S.refuse_full(tmp_path, env=ok))
    assert S.refuse_full(tmp_path / "nowhere", env=ok)


def test_synthetic_checks_pass(world, built):
    assert S.synthetic_checks(world=world, built=built)["synthetic_checks"] == "pass"
