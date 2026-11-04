"""scripts/nba_s_q1tt: first-quarter and first-half team totals
(docs/nba_search_q1tt.md). Every rule is pinned on small hand-built or
synthetic games by its outcome; each was watched failing once with its rule
broken. No real price is read and no real bet is graded."""
import numpy as np
import pandas as pd
import pytest

import models.nba_team_total_luck as tt
import models.nba_total_luck as tl
from scripts import nba_game4_p3 as P3
from scripts import nba_game_harness as H
from scripts import nba_s_q1tt as Q


@pytest.fixture(scope="module")
def ran():
    return Q.synthetic_run(n_placebo=2)


def _dist(sd=5.0, n=4000, seed=3):
    x = np.random.default_rng(seed).normal(0.0, sd, n)
    return H.ResidDist(np.concatenate([x, -x]), "symmetric test shape")


# ── the registered cells ────────────────────────────────────────────────────

def test_the_search_registers_26_cells_and_imports_the_live_rule():
    specs = Q.cell_specs()
    assert len(specs) == 26
    fam = pd.Series([s[0] for s in specs]).value_counts().to_dict()
    assert fam == {Q.FAM_SAME: 12, Q.FAM_CONS: 12, Q.FAM_B: 2}
    assert Q.EV_CUTS == (0.02, 0.04, 0.06)
    assert {s[1] for s in specs} == {"q1", "h1"}
    assert (Q.B_CUT, Q.B_SIDE, Q.B_MIN_GAMES) == (tt.GAP_CUT, tt.SIDE, tl.LIVE_MIN_GAMES)
    assert Q.GRADED == (2025, 2026) and Q.CHOOSE == P3.choosing(Q.GRADED) == (2025,)


def test_every_family_runs_through_the_harness_and_bets_in_both_periods(ran):
    for fam, rows in ran["rows"].items():
        t = pd.DataFrame(rows)
        assert len(t) == Q.EXPECTED_CELLS[fam] and set(t["family"]) == {fam}
        assert (t.groupby("period")["pool_n"].max() > 0).all()
        assert {f"band{i}_n" for i in range(4)} <= set(t.columns)
        assert all(len(r["placebo_rois"]) == 2 for r in rows)


# ── impossible numbers ──────────────────────────────────────────────────────

@pytest.mark.parametrize("market,period,line,keep", [
    ("team_totals_home", "q1", 38.5, True), ("team_totals_home", "h1", 38.5, False),
    ("team_totals_away", "q1", 44.5, False), ("team_totals_away", "h1", 44.5, True),
    ("team_totals_home", "q1", 9.5, False), ("team_totals_home", "h1", 95.5, False),
    ("spreads_q1", None, -5.5, True), ("spreads_q1", None, -22.5, False),
    ("totals_h1", None, 114.5, True), ("totals_h1", None, 57.5, False)])
def test_a_number_no_board_could_hang_is_dropped_by_its_period(market, period, line, keep):
    q = pd.DataFrame({"market": [market], "period": [period], "line": [line],
                      "price_a": [-110.0], "price_b": [-110.0]})
    got, dropped = Q.drop_impossible(q)
    assert (len(got) == 1) is keep
    assert (dropped == {}) is keep


# ── which number a book hangs ───────────────────────────────────────────────

def _games():
    return pd.DataFrame({"game_id": ["G1"], "season": [2025], "game_date": ["2025-01-10"],
                         "tip": [pd.Timestamp("2025-01-11 00:00", tz="UTC")], "home_team": ["AAA"],
                         "away_team": ["BBB"], "home_score": [110.0], "away_score": [100.0]})


def _raw(rows):
    base = {"game_id": "G1", "snapshot_type": "open", "snapshot_at": "2025-01-10T23:05:00Z",
            "source": Q.TT_SOURCE, "created_at": "2026-11-03"}
    return pd.DataFrame([{**base, **r} for r in rows])[Q.TT_COLS]


def test_the_main_number_is_the_rung_closest_to_even_ties_to_the_lower_and_one_sided_never():
    rows = [{"market": "team_totals_q1_home", "bookmaker": "hardrockbet", "total_line": ln,
             "over_price": po, "under_price": pu}
            for ln, po, pu in ((28.5, -185.0, 140.0), (29.5, -135.0, 105.0), (30.5, 100.0, -125.0),
                               (31.5, 130.0, -170.0), (32.5, 175.0, -225.0))]
    rows += [{"market": "team_totals_q1_home", "bookmaker": "draftkings", "total_line": 30.5,
              "over_price": 105.0, "under_price": -125.0},
             {"market": "team_totals_q1_home", "bookmaker": "fanduel", "total_line": 30.5,
              "over_price": -110.0, "under_price": -110.0},
             {"market": "team_totals_q1_home", "bookmaker": "fanduel", "total_line": 29.5,
              "over_price": -110.0, "under_price": -110.0},
             {"market": "team_totals_q1_home", "bookmaker": "betrivers", "total_line": 30.0,
              "over_price": -110.0, "under_price": np.nan},
             {"market": "team_totals_q1_home", "bookmaker": "betrivers", "total_line": 31.5,
              "over_price": 120.0, "under_price": -150.0}]
    q = Q.tt_quotes(_raw(rows), _games())
    times = H.per_event_times(q, "D")
    vis, n = Q.period_numbers(q, times)
    got = dict(zip(vis["book"], vis["line"]))
    assert got["hardrockbet"] == 30.5                        # the rung closest to even
    assert got["fanduel"] == 29.5                            # two even rungs: the lower one
    assert got["betrivers"] == 31.5                          # the one-sided 30.0 is never a main number
    assert set(H.offers(vis)["line"]) == {30.5, 29.5, 31.5}
    assert n["main_numbers"] == 4


def test_the_ladder_rule_drops_a_main_number_far_from_the_deciding_books_median():
    rows = [{"market": "team_totals_h1_away", "bookmaker": b, "total_line": ln,
             "over_price": -110.0, "under_price": -110.0}
            for b, ln in (("draftkings", 57.5), ("fanduel", 57.5), ("betrivers", 57.5), ("hardrockbet", 60.5))]
    q = Q.tt_quotes(_raw(rows), _games())
    vis, n = Q.period_numbers(q, H.per_event_times(q, "D"))
    assert set(vis["book"]) == {"draftkings", "fanduel", "betrivers"} and n["ladder_masked"] == 1


def test_one_periods_numbers_at_a_time():
    rows = [{"market": m, "bookmaker": "draftkings", "total_line": ln, "over_price": -110.0, "under_price": -110.0}
            for m, ln in (("team_totals_q1_home", 28.5), ("team_totals_h1_home", 57.5))]
    q = Q.tt_quotes(_raw(rows), _games())
    with pytest.raises(ValueError, match="one period"):
        Q.period_numbers(q, H.per_event_times(q, "D"))


def test_the_stored_name_survives_as_period_and_team():
    rows = [{"market": "team_totals_h1_away", "bookmaker": "draftkings", "total_line": 57.5,
             "over_price": -110.0, "under_price": -110.0}]
    q = Q.tt_quotes(_raw(rows), _games())
    assert q[["market", "period", "team", "tt_market"]].iloc[0].tolist() == [
        "team_totals_away", "h1", "away", "team_totals_h1_away"]


# ── the implied period points ───────────────────────────────────────────────

def _ref_quotes(rows):
    base = {"game_id": "G1", "season": 2025, "coherent": True}
    return pd.DataFrame([{**base, **r} for r in rows])


def test_the_implied_points_read_the_spread_as_the_home_number():
    pricing = {(2025, "spreads_q1"): _dist(4.0), (2025, "totals_q1"): _dist(6.0)}
    v = _ref_quotes([{"book": "draftkings", "market": "spreads_q1", "line": -2.0, "price_a": -110.0, "price_b": -110.0},
                     {"book": "draftkings", "market": "totals_q1", "line": 58.0, "price_a": -110.0, "price_b": -110.0}])
    same, cons = Q.implied_numbers(Q.quote_centres(v, pricing), "q1")
    got = dict(zip(same["team"], same["mu"]))
    assert got["home"] == pytest.approx(30.0, abs=0.02) and got["away"] == pytest.approx(28.0, abs=0.02)
    v.loc[0, "line"] = 2.0                                   # now the home team is the underdog
    same, _ = Q.implied_numbers(Q.quote_centres(v, pricing), "q1")
    got = dict(zip(same["team"], same["mu"]))
    assert got["home"] == pytest.approx(28.0, abs=0.02) and got["away"] == pytest.approx(30.0, abs=0.02)


def test_a_lopsided_quote_states_its_centre_through_its_price():
    pricing = {(2025, "totals_q1"): _dist(6.0)}
    v = _ref_quotes([{"book": "betrivers", "market": "totals_q1", "line": 56.5, "price_a": -180.0, "price_b": 145.0}])
    mu = Q.quote_centres(v, pricing)["mu"].iloc[0]
    assert 57.0 < mu < 59.5                                  # above its own number, toward the favoured over


def test_the_consensus_is_the_median_of_the_deciding_books_centres_without_pinnacle():
    pricing = {(2025, "spreads_h1"): _dist(5.0), (2025, "totals_h1"): _dist(8.0)}
    rows = []
    for b, sp, to in (("draftkings", -3.0, 115.0), ("fanduel", -3.0, 116.0), ("betmgm", -4.0, 119.0),
                      ("pinnacle", -9.0, 130.0)):
        rows += [{"book": b, "market": "spreads_h1", "line": sp, "price_a": -110.0, "price_b": -110.0},
                 {"book": b, "market": "totals_h1", "line": to, "price_a": -110.0, "price_b": -110.0}]
    same, cons = Q.implied_numbers(Q.quote_centres(_ref_quotes(rows), pricing), "h1")
    got = dict(zip(cons["team"], cons["mu"]))
    assert got["home"] == pytest.approx((116.0 + 3.0) / 2.0, abs=0.03)
    assert got["away"] == pytest.approx((116.0 - 3.0) / 2.0, abs=0.03)
    assert "pinnacle" not in set(same["book"]) and len(same) == 6


# ── the result shape ────────────────────────────────────────────────────────

def _resid(seasons, sd_by_season, n=400):
    rng = np.random.default_rng(1)
    return pd.concat([pd.DataFrame({"season": s, "period": p, "kind": "implied",
                                    "resid": rng.normal(0.0, sd_by_season.get(s, 5.0), n)})
                      for s in seasons for p in Q.PERIODS], ignore_index=True)


def test_a_seasons_shape_reads_only_earlier_seasons_from_2020_21():
    r = _resid((2020, 2021, 2022, 2023, 2024, 2025), {2020: 60.0, 2025: 60.0})
    sh = Q.period_shapes(r, (2025,))
    assert sh[(2025, "q1")].sd < 6.0 and sh[(2025, "q1")].n == 4 * 400


def test_too_few_earlier_residuals_stops_with_no_fallback():
    r = _resid((2024, 2025), {}, n=300)
    with pytest.raises(RuntimeError, match="no fallback"):
        Q.period_shapes(r, (2025,))


def test_the_stand_in_fills_only_seasons_without_period_prices_and_the_last_season_is_never_read():
    rows, close = [], []
    for s in range(2020, 2027):
        gid = f"G{s}"
        rows.append({"game_id": gid, "season": s, "home_q1": 30.0, "away_q1": 28.0, "home_h1": 58.0,
                     "away_h1": 55.0, "home_score": 115.0, "away_score": 110.0})
        close += [{"game_id": gid, "season": s, "market": "spreads", "close_line": -5.0},
                  {"game_id": gid, "season": s, "market": "totals", "close_line": 225.0}]
    gp = pd.DataFrame(rows)
    ci = {p: pd.DataFrame({"game_id": ["G2024", "G2024", "G2025", "G2025", "G2026", "G2026"],
                           "team": ["home", "away"] * 3, "mu": 1.0, "season": [2024, 2024, 2025, 2025, 2026, 2026]})
          for p in Q.PERIODS}
    r = Q.shape_residuals(gp, pd.DataFrame(close), ci)
    kinds = r.groupby("season")["kind"].first().to_dict()
    assert kinds == {2021: "stand_in", 2022: "stand_in", 2023: "stand_in", 2024: "implied", 2025: "implied"}
    q1 = r[(r["season"] == 2021) & (r["period"] == "q1")].sort_values("resid")["resid"].tolist()
    # home: 30 - (225 + 5) / 2 / 4 = 1.25; away: 28 - (225 - 5) / 2 / 4 = 0.5
    assert q1 == pytest.approx([0.5, 1.25])


# ── settlement ──────────────────────────────────────────────────────────────

def test_a_team_total_settles_on_that_teams_points_in_the_period():
    gp = pd.DataFrame({"game_id": ["G"], "season": [2025], "game_date": ["2025-01-10"],
                       "tip": [pd.Timestamp("2025-01-11", tz="UTC")], "home_team": ["AAA"], "away_team": ["BBB"],
                       "home_score": [110.0], "away_score": [108.0], "home_q1": [30.0], "away_q1": [25.0],
                       "home_h1": [55.0], "away_h1": [60.0]})
    b = pd.DataFrame({"game_id": "G", "market": ["team_totals_home", "team_totals_away"],
                      "side": ["over", "under"], "line": [29.5, 24.5], "price": [-110.0, -110.0]})
    assert H.grade(b, Q.period_games(gp, "q1"))["result"].tolist() == ["W", "L"]
    b2 = pd.DataFrame({"game_id": "G", "market": ["team_totals_away", "team_totals_home"],
                       "side": ["over", "under"], "line": [59.5, 55.0], "price": [-110.0, -110.0]})
    assert H.grade(b2, Q.period_games(gp, "h1"))["result"].tolist() == ["W", "P"]


def test_a_game_whose_periods_do_not_sum_to_the_final_is_left_out_and_counted():
    games = pd.DataFrame({"game_id": ["OK", "OT", "BAD"], "season": [2025] * 3,
                          "home_score": [110.0, 120.0, 100.0], "away_score": [100.0, 118.0, 99.0],
                          "went_to_ot": [0, 1, 0]})
    per = pd.DataFrame(
        [{"game_id": "OK", "period": i, "home_points": h, "away_points": a}
         for i, (h, a) in enumerate([(30, 25), (25, 25), (25, 25), (30, 25)], 1)]
        + [{"game_id": "OT", "period": i, "home_points": h, "away_points": a}
           for i, (h, a) in enumerate([(28, 27), (27, 27), (27, 27), (28, 29), (10, 8)], 1)]
        + [{"game_id": "BAD", "period": i, "home_points": h, "away_points": a}
           for i, (h, a) in enumerate([(25, 25), (25, 25), (25, 25), (24, 23)], 1)])
    table, bad = Q.settlement_check(games, per, (2025,))
    assert bad == ["BAD"] and int(table["sum_matches_final"].iloc[0]) == 2
    gp = H.with_periods(games.assign(game_date="2025-01-10", tip=pd.Timestamp("2025-01-11", tz="UTC"),
                                     home_team="A", away_team="B"), periods=per)
    pg = Q.period_games(gp, "q1").set_index("game_id")
    assert pg.loc["OT", "home_score"] == 28.0 and np.isnan(pg.loc["BAD", "home_score"])


# ── family B ────────────────────────────────────────────────────────────────

def test_family_b_reads_the_live_models_own_home_part():
    proj = pd.DataFrame({"game_id": ["G1", "G2"], "h_pace": [100.0, 98.0], "a_pace": [96.0, 102.0],
                         "a_drtg_adj": [110.0, 114.0], "a_drtg_raw": [113.0, 112.0]})
    s = Q.b_signal(proj)
    assert s["market"].tolist() == [tt.MARKET] * 2
    assert np.allclose(s["strength"], tt.home_part(proj)) and np.isclose(s["strength"].iloc[0], -2.94)


def test_the_periods_share_reads_only_earlier_seasons():
    gp = pd.DataFrame({"season": [2023, 2024, 2025], "home_q1": [30.0, 30.0, 90.0], "away_q1": [26.0, 26.0, 90.0],
                       "home_h1": [57.0, 57.0, 90.0], "away_h1": [55.0, 55.0, 90.0],
                       "home_score": [112.0, 112.0, 100.0], "away_score": [112.0, 112.0, 100.0]})
    assert Q.period_share(gp, "q1", 2025) == pytest.approx(56.0 / 224.0)


@pytest.fixture(scope="module")
def ran_live():
    """A synthetic world read the live decision function's way: player-shaped box
    rows, the lab's ratings built from the same rows, and an artifact of the
    world's own full-game team-total residuals (it only prices the offer)."""
    from scripts import nba_game2_market as M2
    from scripts import nba_game5 as G5
    w = G5.synthetic_world()
    box = Q.synthetic_box(w)
    raw = Q.synthetic_tt(w)
    prep = Q.build(w["games"], w["games_p"], w["close"], w["pe"], raw, tl.team_box(box, w["games"]),
                   say=lambda *_: None)
    res = M2.team_total_resid(w["close"], w["games"])
    art = {"kind": tt.ARTIFACT_KIND, "built_at": "synthetic test world",
           "tt_resid": [(int(s), float(r)) for s, r in zip(res["season"], res["resid"])]}
    return {"prep": prep, "raw": raw, "box": box, "art": art, "games": w["games"]}


def test_family_b_bets_exactly_the_games_the_live_decision_function_bets(ran_live):
    prep, games = ran_live["prep"], ran_live["games"]
    season = games.set_index("game_id")["season"]
    for p in Q.PERIODS:
        live = Q.live_rule_games(games, ran_live["raw"], ran_live["box"], ran_live["art"], prep["times"], p)
        b = Q._picks(prep["periods"][p]["cand_b"], Q.B_SIDE, Q.B_CUT, "strength")
        for s in Q.GRADED:
            mine = {g for g in b["game_id"] if season[g] == s}
            assert mine and mine == live[s], (p, s, sorted(mine ^ live[s])[:5])


# ── the placebo ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("fam", [Q.FAM_SAME, Q.FAM_CONS])
def test_the_array_placebo_equals_run_cells_frame_by_frame_path(ran, fam):
    prep = ran["prep"]
    pp = prep["periods"]["q1"]
    cand = pp["cands"][fam]
    pl = Q.a_placebo(cand, fam, pp["centres"], prep["dates"], prep["shapes"], "q1", (1, 2, 3))
    u, r = Q.graded_offers(cand, pp["dd"].games)
    cells = [(s, c) for s in Q.A_SIDES for c in Q.EV_CUTS]
    fast = pl.rois(u, r, cells, Q.CHOOSE)
    for i, seed in enumerate((1, 2, 3)):
        fr = pl.frame(seed)
        for side, cut in cells:
            g = H.grade(H.choose(fr, cut, sides=[side]), pp["dd"].games)
            g = g[g["season"].isin(Q.CHOOSE)]
            slow = H.roi(g) if len(g) else np.nan
            assert np.isclose(slow, fast[(side, cut)][i], equal_nan=True), (side, cut, seed)


def test_the_placebo_respects_the_price_floor(ran):
    prep = ran["prep"]
    pp = prep["periods"]["q1"]
    cand = pp["cands"][Q.FAM_CONS].copy()
    lure = (cand["side"] == "over") & (cand["book"] == "draftkings")
    cand.loc[lure, "line"] = cand.loc[lure, "line"] - 5.0     # far below the centre: the best ev in its group
    cand.loc[lure, "price"] = -250.0                          # but under the -200 floor
    pl = Q.a_placebo(cand, Q.FAM_CONS, pp["centres"], prep["dates"], prep["shapes"], "q1", (1,))
    u, r = Q.graded_offers(cand, pp["dd"].games)
    fast = pl.rois(u, r, [("over", 0.02)], Q.CHOOSE)[("over", 0.02)][0]
    g = H.grade(H.choose(pl.frame(1), 0.02, sides=["over"]), pp["dd"].games)
    g = g[g["season"].isin(Q.CHOOSE)]
    assert np.isclose(fast, H.roi(g)) and (g["price"] >= H.PRICE_FLOOR).all()
    assert pl.chosen(1, "over", 0.02) == set(zip(H.choose(pl.frame(1), 0.02, sides=["over"])["game_id"],
                                                  H.choose(pl.frame(1), 0.02, sides=["over"])["market"]))


@pytest.mark.parametrize("fam", [Q.FAM_SAME, Q.FAM_CONS])
def test_a_placebo_with_nothing_moved_repeats_the_real_bets(ran, fam):
    prep = ran["prep"]
    pp = prep["periods"]["h1"]
    cand = pp["cands"][fam]
    pl = Q.a_placebo(cand, fam, pp["centres"], prep["dates"], prep["shapes"], "h1", (1,))
    for side in Q.A_SIDES:
        for cut in Q.EV_CUTS:
            real = H.choose(cand, cut, sides=[side])
            assert pl.chosen(None, side, cut) == set(zip(real["game_id"], real["market"]))


def test_the_placebo_moves_a_disagreement_within_the_date_the_team_role_and_the_book():
    cand = pd.DataFrame({
        "game_id": ["A", "A", "B", "C", "D"], "team": ["home", "away", "home", "home", "home"],
        "book": ["draftkings", "draftkings", "draftkings", "draftkings", "fanduel"],
        "side": "over", "market": ["team_totals_home", "team_totals_away", "team_totals_home",
                                   "team_totals_home", "team_totals_home"],
        "line": 28.5, "price": -110.0, "season": 2025, "mu": [29.0, 30.0, 31.0, 32.0, 33.0]})
    delta = pd.DataFrame({"game_id": ["A", "A", "B", "C", "D"], "team": ["home", "away", "home", "home", "home"],
                          "book": ["draftkings", "draftkings", "draftkings", "draftkings", "fanduel"],
                          "delta": [1.0, 2.0, 3.0, 4.0, 5.0]})
    dates = pd.Series({"A": "d1", "B": "d1", "C": "d2", "D": "d2"})
    base = np.full(5, 28.0)
    pl = Q.CentrePlacebo(cand, base, delta, ["game_id", "team", "book"], dates,
                         {(2025, "q1"): _dist()}, "q1", seeds=range(1, 40))
    assert np.allclose(pl.mu(None), base + [1.0, 2.0, 3.0, 4.0, 5.0])
    seen_swap = False
    for s in range(1, 40):
        src = pl.source(s)
        ids = list(pl.ids)
        assert {ids[src[ids.index("A")]], ids[src[ids.index("B")]]} == {"A", "B"}
        mu = pl.mu(s)
        if ids[src[ids.index("A")]] == "B":
            seen_swap = True
            assert mu[0] == 28.0 + 3.0                       # A's home offer takes B's home disagreement
            assert np.isnan(mu[1])                           # B has no away disagreement: unpriced
        if ids[src[ids.index("C")]] == "D":
            assert np.isnan(mu[3]) and np.isnan(mu[4])       # D's is at another book
    assert seen_swap


def test_the_placebo_is_a_null_on_synthetic_prices(ran):
    d = Q.placebo_null(ran["prep"], n_runs=5)
    assert len(d) == 26 and (d["share_differs"] > 0.3).all()


# ── the judge, the bets, the refusals ───────────────────────────────────────

def _passing_row(ran):
    r = dict(ran["rows"][Q.FAM_CONS][0])
    r.update({"placebo_rois": [0.0] * 200, "pool_n": 260, "pool_ci95_lo": 0.01, "pool_roi": 0.06,
              "roi_choose": 0.08, "pool_seasons_counted": 2, "pool_seasons_positive": 2,
              "n_2025": 120, "roi_2025": 0.08, "n_confirm": 140, "roi_confirm": 0.04,
              "pool_share_over": 0.5, "pool_share_home": np.nan, "pool_share_fav": np.nan,
              **{f"band{i}_n": 0 for i in range(5)}})
    return r


def test_the_judge_needs_both_seasons_positive(ran):
    r = _passing_row(ran)
    c = Q.judge_table(pd.DataFrame([r]))
    assert bool(c["house5_passes"].iloc[0]) and bool(c["passes"].iloc[0])
    r.update({"roi_confirm": -0.02, "pool_seasons_positive": 1})
    c = Q.judge_table(pd.DataFrame([r]))
    assert bool(c["house5_passes"].iloc[0])                  # the verdict's bar 3 lets one of two lose
    assert not bool(c["passes"].iloc[0]) and c["reading"].iloc[0] == "fails"


def test_the_judge_reads_the_cells_file_full_writes(ran, tmp_path):
    from scripts import nba_game2_luck as L
    from scripts import nba_game2_verdict as V
    good = _passing_row(ran)
    rows = [{**r, "placebo_rois": [0.0] * 200} for r in ran["rows"][Q.FAM_CONS][1:]] + [good]
    L.write_cells(rows, tmp_path / f"cells_{Q.FAM_CONS}.parquet")
    back = V.load_cells(tmp_path)
    assert {f"n_{Q.CHOOSE[0]}", f"roi_{Q.CHOOSE[0]}", "n_confirm", "roi_confirm"} <= set(back.columns)
    c = Q.judge_table(back)
    assert len(c) == len(rows) and c["reading"].notna().all()
    me = c["period"].eq(good["period"]) & c["cut"].eq(good["cut"]) & c["side"].eq(good["side"])
    assert int(me.sum()) == 1 and bool(c.loc[me, "passes"].iloc[0])


def test_a_thin_cell_reads_too_few_games_to_tell(ran):
    r = _passing_row(ran)
    r["pool_n"] = 150
    assert Q.judge_table(pd.DataFrame([r]))["reading"].iloc[0] == "too few games to tell"


def test_bets_are_saved_with_the_period_and_no_shape_column(ran, tmp_path, monkeypatch):
    monkeypatch.setenv(Q.BETS_ENV, str(tmp_path))
    before = set(tmp_path.glob("*.parquet"))
    Q.emit_b(ran["prep"], "q1", n_placebo=0)
    Q.tag_bets(tmp_path, Q.FAM_B, Q.B_LABEL["q1"], "q1", before)
    files = sorted(tmp_path.glob("*.parquet"))
    assert files
    b = pd.read_parquet(files[0])
    assert set(b["period"]) == {"q1"} and set(b["tt_market"]) == {"team_totals_q1_home"}
    assert "sigma" not in b.columns and len(b)


def test_full_refuses_without_the_go_flag_and_folders(tmp_path, monkeypatch):
    for k in (Q.GO_ENV, Q.RESULTS_ENV, Q.BETS_ENV):
        monkeypatch.delenv(k, raising=False)
    why = Q.refuse_full(tmp_path, tmp_path)
    assert any(Q.GO_ENV in w for w in why) and any(Q.RESULTS_ENV in w for w in why)
    assert any(Q.BETS_ENV in w for w in why) and any(Q.TT_FILE in w for w in why)


def test_a_graded_run_refuses_team_totals_in_another_season(ran):
    prep = dict(ran["prep"])
    assert Q.coverage_refusals(prep) == []
    prep["found"] = (2024, 2025, 2026)
    assert any("grades exactly" in w for w in Q.coverage_refusals(prep))
