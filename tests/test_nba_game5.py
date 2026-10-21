"""scripts/nba_game5: the fifth NBA search -- team first-quarter and first-half
tendencies (F7) and the early season (F8) -- and section 9's bars in
scripts/nba_game2_verdict (docs/nba_models_2026.md section 9). Every rule is
pinned on small hand-built or synthetic games by its outcome; each test was
watched failing once with the rule it guards broken. No real price is read."""
import os

import numpy as np
import pandas as pd
import pytest

import models.nba_total_luck as tl
from scripts import nba_game2_verdict as V
from scripts import nba_game4_p3 as P3
from scripts import nba_game5 as G
from scripts import nba_game_harness as H


@pytest.fixture(scope="module")
def ran():
    w = G.synthetic_world()
    return w, G.run_world(w, n_placebo=2, k={"q1": 40.0, "h1": 40.0})


# ── the registered cells ────────────────────────────────────────────────────

def test_section_9_registers_54_cells_48_period_tendency_and_6_early_season():
    specs = G.cell_specs()
    assert len(specs) == 54
    f7 = [s for s in specs if s[0] == "F7"]
    f8 = [s for s in specs if s[0] == "F8"]
    assert len(f7) == 48 and len(f8) == 6
    assert {m for _, m, *_ in f7} == {"h2h_q1", "spreads_q1", "totals_q1", "h2h_h1", "spreads_h1", "totals_h1"}
    assert G.f7_cuts("spreads_h1") == (0.5, 1.0, 1.5, 2.0) and G.f7_cuts("totals_q1") == (0.25, 0.5, 0.75, 1.0)
    assert G.f7_cuts("h2h_q1") == (0.02, 0.04, 0.06, 0.08)
    assert {(m, s, c) for _, m, s, _, c, _ in f8} == {("totals", "over", 3.0), ("team_totals_home", "under", 2.0)}
    assert sorted({b for *_, b in f8}) == [5.0, 10.0, 20.0]


def test_every_cell_and_control_runs_through_the_harness_and_bets(ran):
    _, out = ran
    assert {f: len(r) for f, r in out["rows"].items()} == {"F7": 48, "control_F7_league": 48, "F8": 6}
    by = pd.DataFrame(out["rows"]["F7"]).groupby("market")["pool_n"].sum()
    assert (by > 0).all(), by.to_dict()
    assert sum(r["pool_n"] for r in out["rows"]["F8"]) > 0
    assert {r["family"] for r in out["rows"]["control_F7_league"]} == {"control_F7_league"}


# ── F7: the shares ──────────────────────────────────────────────────────────

def _tp_rows():
    """Team X: home games in 2022 (two seasons back), 2023 (last season) and
    2024 before, on and after the target date, and one away game in 2024."""
    def r(season, date, venue, own, opp):
        return {"game_id": f"{season}{date}{venue}", "season": season, "game_date": date, "team": "X",
                "venue": venue, "own_f": 100.0, "opp_f": 100.0, "own_q1": own, "opp_q1": opp,
                "own_h1": 2 * own, "opp_h1": 2 * opp, "n": 1.0}
    return pd.DataFrame([r(2022, "2022-01-01", "home", 40.0, 40.0),
                         r(2023, "2023-01-01", "home", 30.0, 20.0),
                         r(2024, "2023-12-01", "home", 26.0, 22.0),
                         r(2024, "2024-01-10", "home", 50.0, 50.0),     # the target's own date
                         r(2024, "2024-02-01", "home", 50.0, 50.0),
                         r(2024, "2023-12-05", "away", 45.0, 45.0)])


def test_a_share_reads_last_season_and_this_season_before_the_date_at_that_venue_only():
    t = pd.DataFrame([{"season": 2024, "game_date": "2024-01-10", "team": "X", "venue": "home"}])
    w = G.window_sums(_tp_rows(), t).iloc[0]
    assert w["w_n"] == 2.0                          # 2023's home game + 2023-12-01; not 2022, the date, later, away
    assert w["w_own_q1"] == 56.0 and w["w_opp_q1"] == 42.0 and w["w_own_f"] == 200.0


def test_shrinkage_is_n_share_plus_k_league_over_n_plus_k():
    got = G.shrink([30.0], [100.0], [10.0], [25.0], [100.0], 30.0)
    assert got[0] == pytest.approx((10 * 0.30 + 30 * 0.25) / 40)
    assert G.shrink([30.0], [100.0], [0.0], [25.0], [100.0], 30.0)[0] == pytest.approx(0.25)
    assert G.shrink([30.0], [100.0], [10.0], [25.0], [100.0], np.inf)[0] == pytest.approx(0.25)


def test_the_shrinkage_fit_reads_no_season_after_its_last_and_takes_the_smallest_error():
    w = G.synthetic_world()
    gp = w["games_p"]
    k1, t1 = G.fit_shrinkage(gp, (2021, 2022, 2023))
    late = gp["season"] >= 2024
    gp2 = gp.copy()
    gp2.loc[late, ["home_q1", "home_h1"]] = gp2.loc[late, ["home_q1", "home_h1"]] * 3.0
    k2, t2 = G.fit_shrinkage(gp2, (2021, 2022, 2023))
    assert k1 == k2
    pd.testing.assert_frame_equal(t1, t2)
    for p in G.PERIODS:
        tp = t1[t1["period"] == p]
        assert k1[p] == float(tp.loc[tp["sse"].idxmin(), "k"])


def test_each_teams_difference_from_the_league_is_added_once():
    sh = pd.DataFrame({"s_home_q1": [0.27], "a_away_q1": [0.26], "L_home_q1": [0.25],
                       "s_away_q1": [0.24], "a_home_q1": [0.23], "L_away_q1": [0.25]})
    hp, ap = G.period_points([110.0], [100.0], sh, "q1")
    assert hp[0] == pytest.approx(110.0 * (0.27 + 0.26 - 0.25))
    assert ap[0] == pytest.approx(100.0 * (0.24 + 0.23 - 0.25))
    hl, al = G.period_points([110.0], [100.0], sh, "q1", league_only=True)
    assert hl[0] == pytest.approx(110.0 * 0.25) and al[0] == pytest.approx(100.0 * 0.25)


def test_the_projection_splits_the_markets_full_game_numbers_into_team_points():
    full = pd.DataFrame({"game_id": ["G"], "M": [6.0], "Tot": [226.0]})
    sh = pd.DataFrame({"game_id": ["G"], "season": [2025],
                       **{f"{c}_{v}_{p}": [0.25] for p in G.PERIODS for v in ("home", "away")
                          for c in ("s", "a", "L")}})
    sh["s_home_q1"] = 0.27
    pr = G.f7_projection(full, sh).iloc[0]
    assert pr["total_q1"] == pytest.approx(116.0 * 0.27 + 110.0 * 0.25)     # home 116, away 110
    assert pr["margin_q1"] == pytest.approx(116.0 * 0.27 - 110.0 * 0.25)
    assert pr["total_h1"] == pytest.approx(226.0 * 0.25)


def test_the_full_game_numbers_are_the_markets_fair_centres_with_the_home_margin_signed():
    tip = pd.Timestamp("2025-01-16T00:30:00Z")
    at = tip - pd.Timedelta(minutes=55)
    q = pd.DataFrame([{"game_id": "G", "season": 2025, "game_date": "2025-01-15", "tip": tip,
                       "market": m, "book": "pinnacle", "snapshot_at": at, "fetch_at": at,
                       "line": line, "price_a": -110.0, "price_b": -110.0, "coherent": True}
                      for m, line in (("spreads", -5.5), ("totals", 224.5))])
    sig = {(2025, "spreads"): 12.0, (2025, "totals"): 18.0}
    f = G.full_game_numbers(q, sig).iloc[0]
    assert f["M"] == pytest.approx(5.5, abs=0.05) and f["Tot"] == pytest.approx(224.5, abs=0.05)


def test_the_full_game_number_counts_a_fetch_under_an_hour_old_whatever_the_books_own_stamp():
    """Section 9.3's added line: a purchase 64 minutes before tip reads the slate
    fetch 120 minutes before tip (56 minutes old) though the book last updated
    it 70 minutes before T; a fetch after T is never read."""
    tip = pd.Timestamp("2025-01-16T00:30:00Z")
    T = tip - pd.Timedelta(minutes=64)

    def q(fetch_min, snap_min, line):
        return {"game_id": "G", "season": 2025, "game_date": "2025-01-15", "tip": tip, "market": "totals",
                "book": "pinnacle", "fetch_at": T - pd.Timedelta(minutes=fetch_min),
                "snapshot_at": T - pd.Timedelta(minutes=snap_min), "line": line,
                "price_a": -110.0, "price_b": -110.0, "coherent": True}
    quotes = pd.DataFrame([q(56, 70, 224.5), q(-4, -2, 230.5)])     # the second is after T
    times = pd.DataFrame({"game_id": ["G"], "T": [T]})
    assert H.visible(quotes, times).empty                           # the harness's own rule
    v = G.full_game_visible(quotes, times)
    assert v["line"].tolist() == [224.5]


# ── F7: the gap, the moneyline and the placebo ──────────────────────────────

def test_the_gap_is_against_the_period_markets_fair_centre_and_every_book_carries_it(ran):
    _, out = ran
    proj = G.f7_projection(out["full"], out["sh"])
    strength, _ = G.f7_signals(proj, out["period_fair"], out["pricing"])
    pf = out["period_fair"].set_index(["game_id", "market"])["mu"]
    x = strength[strength["market"] == "totals_q1"].head(20)
    pr = proj.set_index("game_id")["total_q1"]
    for r in x.itertuples():
        assert r.strength == pytest.approx(pr[r.game_id] - pf[(r.game_id, "totals_q1")])
    cand = out["cand"]["F7"]["totals_q1"]
    one = cand.groupby(["game_id", "side"])["strength"].nunique()
    assert (one == 1).all()                      # a soft book's own number never moves the gap
    s = cand[cand["side"] == "over"].groupby("game_id")["strength"].first()
    u = cand[cand["side"] == "under"].groupby("game_id")["strength"].first()
    assert np.allclose(s.reindex(u.index), -u)


def test_the_period_moneyline_removes_the_tie_mass_through_the_period_spread_pricing(ran):
    _, out = ran
    proj = G.f7_projection(out["full"], out["sh"])
    _, ml = G.f7_signals(proj, out["period_fair"], out["pricing"])
    r = ml[ml["market"] == "h2h_q1"].iloc[0]
    pr = proj.set_index("game_id").loc[r["game_id"]]
    dist = out["pricing"][(int(pr["season"]), "spreads_q1")]
    w, push, lo = dist.probs(np.array([pr["margin_q1"]]), np.array([0.0]))
    assert push[0] > 0.01                                       # a level quarter is possible
    assert r["p_home"] == pytest.approx(w[0] / (w[0] + lo[0]))
    assert r["p_home"] != pytest.approx(w[0])


def test_the_placebo_moves_team_shares_within_a_date_and_keeps_each_games_own_numbers(ran):
    w, out = ran
    sh = out["sh"]
    runs = G.share_shuffles(sh, out["dd"].games, seeds=(1, 2))
    dates = out["dd"].games.set_index("game_id")["game_date"]
    for r in runs:
        assert (r["game_id"] == sh["game_id"]).all() and (r["season"] == sh["season"]).all()
        a = sh.assign(d=sh["game_id"].map(dates)).groupby("d")["s_home_q1"].apply(sorted)
        b = r.assign(d=r["game_id"].map(dates)).groupby("d")["s_home_q1"].apply(sorted)
        assert a.to_dict() == b.to_dict()
        # one game's shares move together
        j = int(np.argmax(r["s_home_q1"].to_numpy() != sh["s_home_q1"].to_numpy()))
        src = sh.index[sh["s_home_q1"] == r["s_home_q1"].iloc[j]][0]
        for c in G.SHARE_COLS:
            assert r[c].iloc[j] == sh.loc[src, c]
    assert (runs[0]["s_home_q1"] != sh["s_home_q1"]).any()
    assert G.N_PLACEBO == 200 and G.PLACEBO_SEEDS[0] == 1 and G.PLACEBO_SEEDS[-1] == 200


def test_the_control_uses_the_leagues_share_for_every_team(ran):
    _, out = ran
    a = G.f7_projection(out["full"], out["sh"], league_only=True)
    sh = out["sh"].copy()
    for c in G.SHARE_COLS:
        sh[c] = 0.5 + np.random.default_rng(0).normal(0, 0.05, len(sh))    # team shares play no part
    b = G.f7_projection(out["full"], sh, league_only=True)
    pd.testing.assert_frame_equal(a, b)
    team = G.f7_projection(out["full"], out["sh"])
    assert not np.allclose(team["total_q1"], a["total_q1"])


# ── bands ───────────────────────────────────────────────────────────────────

def test_the_bands_are_the_one_below_the_cut_and_each_from_the_cut_up():
    c = (0.5, 1.0, 1.5, 2.0)
    assert G.band_bounds(c, 0) == [(0.0, 0.5), (0.5, 1.0), (1.0, 1.5), (1.5, 2.0), (2.0, np.inf)]
    assert G.band_bounds(c, 2) == [(1.0, 1.5), (1.5, 2.0), (2.0, np.inf)]
    assert G.band_bounds(G.F8_EDGES, G.F8_EDGES.index(3.0)) == [(2.0, 3.0), (3.0, 4.0), (4.0, np.inf)]
    assert G.band_bounds(G.F8_EDGES, G.F8_EDGES.index(2.0)) == [(1.0, 2.0), (2.0, 3.0), (3.0, 4.0), (4.0, np.inf)]


def test_the_bands_from_the_cut_partition_the_cells_own_bets(ran):
    _, out = ran
    cells = pd.DataFrame(out["rows"]["F7"])
    for _, r in cells.iterrows():
        up = sum(r[f"band{i}_n"] for i in range(1, r["band_slots"]))
        assert up == r["pool_n"], (r["market"], r["side"], r["cut"])
        units = sum(np.nan_to_num(r[f"band{i}_units"]) for i in range(1, r["band_slots"]))
        assert units == pytest.approx(r["pool_units"])
    # the band below cut k is cut k-1's own first band
    by = {(r["market"], r["side"], r["cut_index"]): r for _, r in cells.iterrows()}
    for (m, s, k), r in by.items():
        if k > 0:
            assert r["band0_n"] == by[(m, s, k - 1)]["band1_n"]


def test_a_season_the_coverage_gate_drops_is_out_of_the_bands_too():
    """2023-24 purchases on fewer than 95% of games: the harness drops that
    choosing season at D, from the cell and so from its bands."""
    w = G.synthetic_world()
    g24 = w["games"].loc[w["games"]["season"] == 2024, "game_id"]
    w["pe"] = w["pe"][~w["pe"]["game_id"].isin(set(g24.iloc[: len(g24) // 10 + 1]))]
    out = G.run_world(w, n_placebo=0, k={"q1": 40.0, "h1": 40.0})
    cells = pd.DataFrame(out["rows"]["F7"])
    assert set(cells["pool_seasons"]) == {"2025,2026"} and set(cells["gate_dropped"]) == {"2024"}
    for _, r in cells.iterrows():
        assert sum(r[f"band{i}_n"] for i in range(1, r["band_slots"])) == r["pool_n"]


# ── section 9's bars in the verdict ─────────────────────────────────────────

def _cell(k, **over):
    row = {"family": "F7", "point": "D", "market": "totals_q1", "side": "over", "cut_index": k,
           "cut": (0.25, 0.5, 0.75, 1.0)[k], "pool_n": 600, "pool_units": 40.0, "pool_roi": 0.06,
           "pool_ci95_lo": 0.01, "pool_ci95_hi": 0.11, "pool_seasons_counted": 3,
           "pool_seasons_positive": 3, "pool_share_home": np.nan, "pool_share_fav": np.nan,
           "pool_share_over": 1.0, "blind_pool_over": -0.04, "blind_pool_under": -0.03,
           "roi_choose": 0.06, "placebo_rois": [0.0] * 200, "band_slots": 5}
    for i in range(5):
        row.update({f"band{i}_n": 100, f"band{i}_roi": 0.05, f"band{i}_units": 5.0,
                    f"band{i}_lo": 0.0, f"band{i}_hi": 1.0})
    row.update(over)
    return row


def _grid(**mid):
    return pd.DataFrame([_cell(0), _cell(1, **mid), _cell(2)])


def _mid(v):
    return v[v["cut_index"] == 1].iloc[0]


def test_section_9_passes_a_cell_whose_every_band_is_positive():
    assert bool(_mid(V.house_verdict_bands(_grid()))["house5_passes"]) is True


def test_a_losing_band_below_the_cut_fails_a_cell_its_nested_neighbours_pass():
    g = _grid(band0_roi=-0.06)
    assert bool(_mid(V.house_verdict(g))["house_passes"]) is True           # the fourth search's bar
    m = _mid(V.house_verdict_bands(g))
    assert bool(m["house5_passes"]) is False and m["house5_failed"] == "h5_bands"


def test_a_losing_band_above_the_cut_fails_too_and_a_thin_band_is_not_judged():
    assert _mid(V.house_verdict_bands(_grid(band3_roi=-0.01)))["house5_failed"] == "h5_bands"
    m = _mid(V.house_verdict_bands(_grid(band3_roi=-0.5, band3_n=29)))
    assert bool(m["house5_passes"]) is True


def test_section_9_refuses_any_placebo_count_but_200():
    g = _grid()
    g["placebo_rois"] = [[0.0] * 20] * 3
    with pytest.raises(ValueError, match="200"):
        V.house_verdict_bands(g)
    g["placebo_rois"] = [[0.0] * 200] * 3
    V.house_verdict_bands(g)


def test_the_other_house_bars_still_apply():
    assert _mid(V.house_verdict_bands(_grid(pool_n=199)))["house5_failed"] == "h1_bets"
    assert _mid(V.house_verdict_bands(_grid(placebo_rois=[0.3] * 200)))["house5_failed"] == "h6_placebo"


def test_the_synthetic_cells_read_through_section_9s_verdict(ran):
    _, out = ran
    cells = pd.DataFrame(out["rows"]["F7"] + out["rows"]["F8"] + out["rows"]["control_F7_league"])
    v = V.house_verdict_bands(cells, n_placebo=2)       # the synthetic run has 2; the real one 200
    assert len(v) == 102 and set(v["family"]) == {"F7", "F8", "control_F7_league"}   # section 9.8
    f7 = v[v["family"] == "F7"].set_index(["market", "side", "cut_index"])
    ctl = v[v["family"] == "control_F7_league"].set_index(["market", "side", "cut_index"])
    pd.testing.assert_series_equal(f7["control_pool_roi"], ctl.loc[f7.index, "pool_roi"], check_names=False)
    assert f7["beats_control"].notna().all()
    assert v.loc[v["family"] != "F7", "beats_control"].isna().all()


# ── section 9.8: the control judged, empty placebo runs, credit ─────────────

def test_a_placebo_run_with_no_bet_counts_as_a_return_of_0(tmp_path):
    """Ten runs bet and returned +10%; 190 placed no bet. Dropping the empty
    runs put the 95th percentile at +10% and failed a +6% cell; counted as 0
    they put it at 0.5%. The count of 200 survives the parquet round trip."""
    from scripts import nba_game2_luck as L
    g = _grid(placebo_rois=[0.10] * 10 + [np.nan] * 190)
    L.write_cells(g.to_dict("records"), tmp_path / "cells.parquet")
    back = pd.read_parquet(tmp_path / "cells.parquet")
    m = _mid(V.house_verdict_bands(back))
    assert m["placebo_empty_runs"] == 190
    assert m["placebo_p95"] == pytest.approx(0.005)
    assert bool(m["h6_placebo"]) is True and bool(m["house5_passes"]) is True
    m = _mid(V.house_verdict_bands(_grid(placebo_rois=[0.10] * 20 + [np.nan] * 180)))
    assert m["placebo_p95"] == pytest.approx(0.10) and bool(m["h6_placebo"]) is False


def test_the_control_is_judged_with_its_own_placebo_and_the_same_run_count(ran):
    _, out = ran
    ctl = pd.DataFrame(out["rows"]["control_F7_league"])
    assert (ctl["placebo_rois"].apply(len) == 2).all()            # the synthetic run's 2
    assert ctl["placebo_rois"].apply(lambda v: np.isfinite(np.asarray(v, float)).any()).any()
    cells = pd.DataFrame(out["rows"]["F7"] + out["rows"]["control_F7_league"])
    v = V.house_verdict_bands(cells, n_placebo=2)
    assert (v["family"] == "control_F7_league").sum() == 48
    assert set(V.house_verdict(cells)["family"]) == {"F7"}        # the fourth search's verdict: unchanged
    cells.loc[cells["family"] == "control_F7_league", "placebo_rois"] = pd.Series(
        [[0.0] * 20] * 48, index=cells.index[cells["family"] == "control_F7_league"])
    with pytest.raises(ValueError, match="placebo count"):
        V.house_verdict_bands(cells, n_placebo=2)


def test_the_control_placebo_shuffles_its_gap_within_a_date_and_market_from_each_games_centre(ran, monkeypatch):
    _, out = ran
    games, pf = out["dd"].games, out["period_fair"]
    proj = G.f7_projection(out["full"], out["sh"], league_only=True)
    strength, ml = G.f7_signals(proj, pf, out["pricing"])
    dates = games.set_index("game_id")["game_date"]

    def by_date(s):
        x = s.assign(d=s["game_id"].map(dates), v=np.round(s["strength"].to_numpy(float), 9))
        return x.groupby(["d", "market"])["v"].apply(sorted).to_dict()

    runs = G.control_shuffles(proj, pf, games, seeds=(1, 2))
    for r in runs:
        assert (r["game_id"] == proj["game_id"]).all() and (r["season"] == proj["season"]).all()
        s2, ml2 = G.f7_signals(r, pf, out["pricing"])
        assert by_date(s2) == by_date(strength)                    # the same gaps on each date and market
        # the shuffled margin is the game's OWN period spread centre plus a gap; the
        # moneyline is priced from it through the period spread market's pricing
        fair = pf[pf["market"] == "spreads_q1"].set_index("game_id")["mu"]
        x = r.set_index("game_id")
        gap = s2[s2["market"] == "spreads_q1"].set_index("game_id")["strength"]
        assert np.allclose(x.loc[gap.index, "margin_q1"], fair.loc[gap.index] + gap)
        one = ml2[ml2["market"] == "h2h_q1"].iloc[0]
        dist = out["pricing"][(int(x.loc[one["game_id"], "season"]), "spreads_q1")]
        w, _, lo = dist.probs(np.array([x.loc[one["game_id"], "margin_q1"]]), np.array([0.0]))
        assert one["p_home"] == pytest.approx(w[0] / (w[0] + lo[0]))
    s1, _ = G.f7_signals(runs[0], pf, out["pricing"])
    k = ["game_id", "market"]
    moved = s1.merge(strength, on=k, suffixes=("", "_real"))
    assert not np.allclose(moved["strength"], moved["strength_real"])   # it does move them
    seen = []
    real = G.control_shuffles
    monkeypatch.setattr(G, "control_shuffles", lambda *a, **kw: seen.append(a[3]) or real(*a, **kw))
    G.emit_f7(out["dd"], out["times"], out["off"], out["neutral"], out["full"], out["sh"], pf,
              out["pricing"], (2024, 2025), 2, league_only=True)
    assert seen == [(1, 2)]                                        # seeds 1.. as F7's


def test_an_f7_cell_is_credited_to_team_tendencies_only_when_it_beats_its_control():
    f7 = _grid()
    for ctl_roi, credited in ((0.08, False), (0.04, True), (np.nan, True)):
        ctl = _grid(pool_roi=ctl_roi).assign(family="control_F7_league")
        v = V.house_verdict_bands(pd.concat([f7, ctl], ignore_index=True))
        m = v[(v["family"] == "F7") & (v["cut_index"] == 1)].iloc[0]
        assert bool(m["house5_passes"]) is True
        assert bool(m["beats_control"]) is credited and bool(m["credited"]) is credited
    m = _mid(V.house_verdict_bands(f7))                  # no control in the cells: never credited
    assert bool(m["house5_passes"]) is True and bool(m["credited"]) is False


# ── F8: the early season ────────────────────────────────────────────────────

def _tb_rows(season, team, dates, opp3m):
    return [{"game_id": f"{team}{season}{d}", "season": season, "game_date": d, "team": team,
             "opp": "Z", "pts": 110.0, "fg3m": 12.0, "fg3a": 34.0, "ftm": 17.0, "fta": 22.0,
             "opp_pts": 100.0 + opp3m, "opp_fg3m": opp3m, "opp_fg3a": 34.0, "opp_ftm": 17.0,
             "opp_fta": 22.0, "poss": 100.0} for d in dates]


def _blend_world():
    """Team A: 2023 opponents hit 16 threes a game (hot), 2024 opponents 10."""
    rows = (_tb_rows(2023, "A", [f"2023-01-{i:02d}" for i in range(1, 21)], 16.0)
            + _tb_rows(2023, "B", [f"2023-01-{i:02d}" for i in range(1, 21)], 12.0)
            + _tb_rows(2024, "A", [f"2023-11-{i:02d}" for i in range(1, 16)], 10.0)
            + _tb_rows(2024, "B", [f"2023-11-{i:02d}" for i in range(1, 16)], 12.0))
    return pd.DataFrame(rows)


def test_last_seasons_rating_is_its_whole_regular_season_filed_under_the_next():
    tb = _blend_world()
    e = G.season_end_ratings(tb).set_index(["season", "team"])
    full = tl.as_of_ratings(tb, pd.DataFrame({"season": [2023], "team": ["A"], "game_date": ["2023-02-01"]}))
    assert e.loc[(2024, "A"), "drtg_raw_prev"] == pytest.approx(full["drtg_raw"].iloc[0])
    assert e.loc[(2024, "A"), "drtg_raw_prev"] == pytest.approx(116.0)          # all 20 games
    assert (2023, "A") not in e.index


@pytest.mark.parametrize("n_before,k", [(0, 5.0), (4, 5.0), (12, 10.0)])
def test_the_blend_is_n_this_season_plus_k_last_season_over_n_plus_k(n_before, k):
    tb = _blend_world()
    date = f"2023-11-{n_before + 1:02d}"
    games = pd.DataFrame([{"game_id": "T", "season": 2024, "game_date": date, "home_team": "A", "away_team": "B"}])
    b = G.blended_ratings(tb, games, k).set_index("team").loc["A"]
    cur = tl.as_of_ratings(tb, pd.DataFrame({"season": [2024], "team": ["A"], "game_date": [date]})).iloc[0]
    prev = G.season_end_ratings(tb).set_index(["season", "team"]).loc[(2024, "A")]
    assert b["n"] == n_before
    for c in ("drtg_adj", "drtg_raw", "pace"):
        want = prev[f"{c}_prev"] if n_before == 0 else (n_before * cur[c] + k * prev[f"{c}_prev"]) / (n_before + k)
        assert b[c] == pytest.approx(want)


def test_with_no_weight_on_last_season_the_gap_is_the_live_models():
    w = G.synthetic_world()
    g = w["data"].games[w["data"].games["season"] == 2024]
    live = tl.f4_projections(g, w["tb"]).set_index("game_id")
    r = G.blended_ratings(w["tb"], g, 0.0)
    mine = tl.project_ratings(tl.pair_ratings(g.assign(season=g["season"].astype(int)), r)).set_index("game_id")
    common = live.index.intersection(mine.index)
    assert len(common) > 50
    assert np.allclose(live.loc[common, "gap_total"], mine.loc[common, "gap_total"])


def _uneven_world():
    """The synthetic world with team T0's games of each season's first three
    days removed, so on a given date two teams can have played different
    numbers of games (in the full world every team plays every day)."""
    w = G.synthetic_world()
    g = w["data"].games
    day = g["game_id"].str.split("_").str[1].astype(int)
    drop = set(g.loc[(day < 3) & ((g["home_team"] == "T0") | (g["away_team"] == "T0")), "game_id"])
    return g[~g["game_id"].isin(drop)].reset_index(drop=True), w["tb"][~w["tb"]["game_id"].isin(drop)]


def test_the_early_population_is_games_where_either_team_has_fewer_than_10():
    games, tb = _uneven_world()
    proj = G.f8_projection(tb, games, 10.0)
    assert len(proj) and ((proj["h_n"] < 10) | (proj["a_n"] < 10)).all()
    one_early = (proj["h_n"] < 10) != (proj["a_n"] < 10)
    assert one_early.any()                       # one team past 10 games, the other not: still early
    early = G.early_games(tb, games)
    with_prev = early[early["season"] > early["season"].min()]
    assert set(proj["game_id"]) == set(with_prev["game_id"])     # every one gets a number


def test_f8_bets_the_over_on_the_full_gap_and_the_under_on_the_home_part(ran):
    w, out = ran
    proj = G.f8_projection(w["tb"], w["data"].games, 10.0)
    tot = G.f8_signal(proj, "totals").set_index("game_id")["strength"]
    home = G.f8_signal(proj, "team_totals_home").set_index("game_id")["strength"]
    p = proj.set_index("game_id")
    assert np.allclose(tot, p.loc[tot.index, "gap_total"])
    pace = 0.5 * (p["h_pace"] + p["a_pace"]) / 100.0
    assert np.allclose(home, (pace * (p["a_drtg_adj"] - p["a_drtg_raw"])).loc[home.index])
    rows = {(r["market"], r["axis_blend"]): r for r in out["rows"]["F8"]}
    assert rows[("totals", 10.0)]["side"] == "over" and rows[("totals", 10.0)]["cut"] == 3.0
    assert rows[("team_totals_home", 10.0)]["side"] == "under" and rows[("team_totals_home", 10.0)]["cut"] == 2.0
    cand = out["cand"]["F8"][("team_totals_home", 10.0)]
    u = cand[cand["side"] == "under"].groupby("game_id")["strength"].first()
    assert np.allclose(u, -home.loc[u.index])
    assert rows[("totals", 10.0)]["band0_lo"] == 2.0 and rows[("team_totals_home", 10.0)]["band0_lo"] == 1.0


def test_the_f8_placebo_moves_the_gap_within_a_date_with_seeds_1_to_200(ran):
    w, out = ran
    proj = G.f8_projection(w["tb"], w["data"].games, 10.0)
    s = G.f8_signal(proj, "totals")
    a, b = G.gap_shuffles(s, w["data"].games, seeds=(1,))[0], H.shuffle_within_date(
        s[["game_id", "market", "strength"]], w["data"].games, np.random.default_rng(1))
    pd.testing.assert_frame_equal(a, b)
    dates = w["data"].games.set_index("game_id")["game_date"]
    x = s.assign(d=s["game_id"].map(dates)).groupby("d")["strength"].apply(sorted).to_dict()
    y = a.assign(d=a["game_id"].map(dates)).groupby("d")["strength"].apply(sorted).to_dict()
    assert x == y


# ── the refactor of the live model and the refusals ─────────────────────────

def test_the_live_models_projection_is_the_split_pieces_with_the_10_game_rule():
    g, tb = _uneven_world()
    r = tl.as_of_ratings(tb, tl.team_targets(g))
    x = tl.pair_ratings(g, r)
    assert (((x["h_n"] == 9) & (x["a_n"] >= 10)) | ((x["a_n"] == 9) & (x["h_n"] >= 10))).any()
    want = tl.project_ratings(x[(x["h_n"] >= 10) & (x["a_n"] >= 10)])
    pd.testing.assert_frame_equal(tl.f4_projections(g, tb), want)


def test_full_refuses_without_the_go_a_results_folder_or_a_bets_folder_before_reading(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise AssertionError("read data before refusing")
    monkeypatch.setattr(H, "load", boom)
    monkeypatch.setattr(H, "load_per_event", boom)
    (tmp_path / "nba_fetch_ledger.parquet").write_bytes(b"")
    monkeypatch.delenv("NBA_GAME2_GO", raising=False)
    monkeypatch.setenv("NBA_GAME2_RESULTS", str(tmp_path / "out"))
    monkeypatch.setenv("NBA_GAME2_BETS", str(tmp_path / "bets"))
    with pytest.raises(SystemExit):
        G.full(tmp_path, out=tmp_path / "out")
    assert not (tmp_path / "out").exists()
    monkeypatch.setenv("NBA_GAME2_GO", "1")
    assert G.refuse_full(tmp_path) == []
    for env in ("NBA_GAME2_RESULTS", "NBA_GAME2_BETS"):
        monkeypatch.delenv(env)
        assert any(env in w for w in G.refuse_full(tmp_path))
        monkeypatch.setenv(env, str(tmp_path / env))


def test_full_refuses_a_shrinkage_refit_other_than_the_registered_160_and_40(monkeypatch, tmp_path):
    class Reached(Exception):
        pass

    def reached(*a, **k):
        raise Reached
    (tmp_path / "nba_fetch_ledger.parquet").write_bytes(b"")
    monkeypatch.setenv("NBA_GAME2_GO", "1")
    monkeypatch.setenv("NBA_GAME2_RESULTS", str(tmp_path / "out"))
    monkeypatch.setenv("NBA_GAME2_BETS", str(tmp_path / "bets"))
    monkeypatch.setattr(G, "synthetic_checks", lambda *a, **k: None)
    monkeypatch.setattr(G, "load_real", lambda *a, **k: {"games_p": pd.DataFrame()})
    monkeypatch.setattr(G, "prepare", reached)
    assert G.REGISTERED_K == {"q1": 160.0, "h1": 40.0}
    for k in ({"q1": 160.0, "h1": 80.0}, {"q1": 320.0, "h1": 40.0}):
        monkeypatch.setattr(G, "fit_shrinkage", lambda gp, k=k: (k, pd.DataFrame()))
        with pytest.raises(SystemExit):
            G.full(tmp_path, out=tmp_path / "out")
    monkeypatch.setattr(G, "fit_shrinkage", lambda gp: ({"q1": 160.0, "h1": 40.0}, pd.DataFrame()))
    with pytest.raises(Reached):
        G.full(tmp_path, out=tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_f8_reads_its_market_side_and_cut_from_the_live_models(monkeypatch):
    import importlib
    from models import nba_team_total_luck as TT
    assert G.F8_SIGNALS == (("totals", "over", 3.0, "C"), ("team_totals_home", "under", 2.0, "D"))
    monkeypatch.setattr(tl, "GAP_CUT", 4.0)
    monkeypatch.setattr(TT, "GAP_CUT", 1.0)
    try:
        g2 = importlib.reload(G)
        assert g2.F8_SIGNALS == (("totals", "over", 4.0, "C"), ("team_totals_home", "under", 1.0, "D"))
    finally:
        monkeypatch.undo()
        importlib.reload(G)
    assert G.F8_SIGNALS == (("totals", "over", 3.0, "C"), ("team_totals_home", "under", 2.0, "D"))


def test_the_synthetic_checks_write_no_bets_into_the_graded_runs_folder(monkeypatch, tmp_path):
    seen = []

    def fake(world, n_placebo=2):
        seen.append(os.environ.get("NBA_GAME2_BETS"))
        return {"rows": {"F7": [{"pool_n": 1}] * 48, "control_F7_league": [{"pool_n": 1}] * 48,
                         "F8": [{"pool_n": 1}] * 6}}
    monkeypatch.setattr(G, "run_world", fake)
    monkeypatch.setattr(G, "synthetic_world", lambda *a, **k: None)
    monkeypatch.setenv("NBA_GAME2_BETS", str(tmp_path / "bets"))
    G.synthetic_checks()
    assert seen == [None]                                   # unset while the synthetic cells run
    assert os.environ["NBA_GAME2_BETS"] == str(tmp_path / "bets")    # and back for the graded run


def test_a_derivative_cache_other_than_2023_24_to_2025_26_is_refused(monkeypatch, tmp_path):
    games = pd.DataFrame({"game_id": ["G"], "season": [2025], "game_date": ["2024-12-01"],
                          "tip": [pd.Timestamp("2024-12-02T00:30:00Z")], "home_team": ["A"], "away_team": ["B"],
                          "home_score": [100.0], "away_score": [90.0]})
    monkeypatch.setattr(H, "load", lambda *a, **k: H.Data(games=games, quotes=pd.DataFrame(), fetches=pd.DataFrame()))
    monkeypatch.setattr(H, "load_games", lambda *a, **k: games)
    monkeypatch.setattr(H, "with_periods", lambda g, *a, **k: g)
    monkeypatch.setattr(P3, "load_derivatives", lambda *a, **k: (pd.DataFrame({"season": [2025]}), (2025, 2026)))
    with pytest.raises(RuntimeError, match="2024, 2025, 2026"):
        G.load_real(tmp_path, require=True)
