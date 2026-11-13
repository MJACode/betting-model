"""The first-quarter player-prop search's lab (docs/nba_search_q1props.md): each rule the doc registers, on
hand-built rows and on the invented world. Each test here was run once with its rule broken and watched
failing (the mutation list is in the search's report)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts import nba_game_harness as H
from scripts import nba_s_q1props as Q


@pytest.fixture
def fast_boot(monkeypatch):
    """4,000 resamples per cell are most of a plumbing test's time; no test reads an interval's width."""
    monkeypatch.setattr(H.boot, "__defaults__", (200, H.SEED))


# ── registered shape ────────────────────────────────────────────────────────

def test_the_registered_cells_are_18_and_the_placebo_200_runs():
    groups = Q.world_groups(Q.synthetic_world(days=4))
    assert len(Q.registered(groups)) == 18
    assert Q.PLACEBO_SEEDS == tuple(range(1, 201))
    assert Q.EV_CUTS == (0.02, 0.04, 0.06) and Q.CHOOSE == (2025,)
    fams = {g.family for g in groups}
    assert fams == {Q.FAMILY, Q.CTL_HR, Q.CTL_FD, Q.CTL_BLIND, Q.CTL_ONE}
    assert all(len(g.cand) for g in groups), "the invented world must hold every group's offers"


# ── settlement ──────────────────────────────────────────────────────────────

def play(gid, period, typ, text, a1, a2=None, scoring=False, shooting=False, value=0, points=0):
    return {"espn_game_id": gid, "period": period, "type_id": typ, "type_text": text, "scoring_play": scoring,
            "shooting_play": shooting, "shot_value": value, "points": points, "athlete_id_1": a1, "athlete_id_2": a2,
            "text": text, "season_type": 2}


def plays_world():
    p = [play(1, 1, 92, "Jump Shot", 11, 12, True, True, 2, 2),           # 11 scores 2 in Q1, 12 assists
         play(1, 2, 92, "Jump Shot", 11, None, True, True, 3, 3),         # 11 scores 3 in Q2 (not Q1)
         play(1, 1, 156, "Offensive Rebound", 13),
         play(1, 3, 155, "Defensive Rebound", 13)]
    games = pd.DataFrame({"espn_game_id": [1], "game_id": ["G1"], "season_type": [2], "in_games": [True]})
    return pd.DataFrame(p), games


def test_first_quarter_lines_come_from_period_one_only():
    plays, games = plays_world()
    full, q1 = Q.derive_stats(plays, games, {11: "A", 12: "B", 13: "C"})
    f, q = full.set_index("player_id"), q1.set_index("player_id")
    assert f.at["A", "points"] == 5 and q.at["A", "points"] == 2
    assert q.at["B", "assists"] == 1
    assert f.at["C", "rebounds"] == 2 and q.at["C", "rebounds"] == 1


def test_an_unmapped_espn_id_never_matches_a_box_line():
    plays, games = plays_world()
    full, _ = Q.derive_stats(plays, games, {11: "A", 12: "B"})
    assert "espn:13" in set(full.player_id)
    log = pd.DataFrame({"game_id": "G1", "player_id": ["A", "B", "C"], "points": [5, 0, 0], "rebounds": [0, 0, 2],
                        "assists": [0, 1, 0]})
    bad, _ = Q.full_game_check(full, log, ["G1"])
    assert bad["rebounds"] == {"G1"}


def test_the_full_game_check_leaves_a_game_out_of_the_differing_stat_only():
    plays, games = plays_world()
    full, _ = Q.derive_stats(plays, games, {11: "A", 12: "B", 13: "C"})
    log = pd.DataFrame({"game_id": "G1", "player_id": ["A", "B", "C"], "points": [5, 0, 0], "rebounds": [0, 0, 3],
                        "assists": [0, 1, 0]})
    bad, rows = Q.full_game_check(full, log, ["G1"])
    assert bad == {"points": set(), "rebounds": {"G1"}, "assists": set()}
    assert rows["rebounds"] == 1


def test_first_quarter_points_must_equal_the_period_score():
    q1 = pd.DataFrame({"game_id": ["G1", "G1", "G2"], "player_id": ["A", "B", "C"], "points": [10.0, 7.0, 5.0]})
    team = pd.DataFrame({"game_id": ["G1", "G1", "G2"], "player_id": ["A", "B", "C"], "team": ["HOM", "AWY", "HOM"]})
    games = pd.DataFrame({"game_id": ["G1", "G2", "G3"], "home_team": "HOM", "away_team": "AWY"})
    per = pd.DataFrame({"game_id": ["G1", "G2"], "period": 1, "home_points": [10, 6], "away_points": [7, 0]})
    assert Q.period_points_check(q1, team, games, per, ["G1", "G2", "G3"]) == {"G2", "G3"}


def segment(gid, period, home, away, dur, team_h="HOM", team_a="AWY"):
    return {"game_id": gid, "season_type": 2, "period": period, "home_team": team_h, "away_team": team_a,
            "home_player_ids": np.array(home, dtype=object), "away_player_ids": np.array(away, dtype=object),
            "home_espn_ids": np.array([int(x[1:]) for x in home], dtype=object),
            "away_espn_ids": np.array([int(x[1:]) for x in away], dtype=object),
            "n_home": len(home), "n_away": len(away), "duration_s": float(dur)}


def test_court_time_sums_segments_and_a_short_quarter_fails():
    h1, h2 = ["h1", "h2", "h3", "h4", "h5"], ["h6", "h2", "h3", "h4", "h5"]
    a = ["a1", "a2", "a3", "a4", "a5"]
    st = pd.DataFrame([segment("G1", 1, h1, a, 400), segment("G1", 1, h2, a, 320), segment("G1", 2, h1, a, 720),
                       segment("G2", 1, h1, a, 700), segment("G2", 1, h1, a[:4], 20)])
    sec, tm, notes = Q.court_seconds(st)
    s = sec.set_index(["game_id", "player_id"]).q1_sec
    assert s[("G1", "h1")] == 400 and s[("G1", "h6")] == 320 and s[("G1", "h2")] == 720
    ok = tm.set_index(["game_id", "team"]).court_ok
    assert ok[("G1", "HOM")] and ok[("G1", "AWY")]
    assert not ok[("G2", "HOM")], "20 of 720 seconds are in a segment not five a side: 58.3 player-minutes"
    assert notes["q1_segments_not_five_a_side"] == 1


def settled_for(q1, valid):
    return Q.Settled(q1=q1, valid=valid, team_court=pd.DataFrame(), notes={})


def quote(gid="G1", pid="1", market="player_points_q1", book="hardrockbet", line=3.5, over=-110.0, under=-110.0,
          lead=54.4, season=2025, minutes=30.0):
    return {"game_id": gid, "player_id": pid, "namesake": False, "market": market, "bookmaker": book, "line": line,
            "over_price": over, "under_price": under, "lead_min": lead, "season": season, "minutes": minutes,
            "game_date": "2025-01-02", "player_name": f"N{pid}", "snapshot_at": "2025-01-02T23:05:00Z"}


def test_each_impossible_number_and_the_window_are_refused_and_counted():
    rows = pd.DataFrame([quote(), quote(pid="2", over=-12000.0), quote(pid="3", line=40.5),
                         quote(pid="4", over=-200.0, under=-200.0), quote(pid="5", lead=80.0),
                         quote(pid="6", under=np.nan), quote(pid="7", market="player_assists_q1", line=12.5)])
    q1 = pd.DataFrame({"game_id": "G1", "player_id": [str(i) for i in range(1, 8)], "q1_sec": 300.0,
                       "points": 1.0, "rebounds": 1.0, "assists": 1.0})
    valid = {m: {"G1"} for m in Q.Q1_MARKETS}
    co, one, n, _ = Q.refuse_rows(rows, settled_for(q1, valid))
    assert n["refused_price"] == 1 and n["refused_line"] == 1 and n["refused_incoherent"] == 1
    assert n["refused_window"] == 1 and n["one_sided"] == 1
    assert set(co.player_id) == {"1", "7"} and set(one.player_id) == {"6"}


def test_a_player_with_no_first_quarter_court_time_is_void_and_a_left_out_game_drops():
    rows = pd.DataFrame([quote(pid="1"), quote(pid="2"), quote(pid="3", market="player_rebounds_q1")])
    q1 = pd.DataFrame({"game_id": "G1", "player_id": ["1", "2", "3"], "q1_sec": [300.0, 0.0, 200.0],
                       "points": [2.0, 0.0, 0.0], "rebounds": 0.0, "assists": 0.0})
    valid = {"player_points_q1": {"G1"}, "player_rebounds_q1": set(), "player_assists_q1": {"G1"}}
    co, _, n, pre = Q.refuse_rows(rows, settled_for(q1, valid))
    assert list(co.player_id) == ["1"]
    assert n["void_no_first_quarter_court_time"] == 1 and n["left_out_by_settlement"] == 1
    played_not_q1 = pre[pre.kept & (pre.minutes > 0) & (pre.q1_sec <= 0)]
    assert list(played_not_q1.player_id) == ["2"]


# ── the projection ──────────────────────────────────────────────────────────

def test_minutes_history_reads_only_earlier_games():
    pg = pd.DataFrame({"player_id": "A", "date": pd.to_datetime(["2025-01-01", "2025-01-03", "2025-01-05"]),
                       "q1_sec": [360.0, 720.0, 0.0], "court_ok": True})
    h = Q.minutes_history(pg)
    t = pd.DataFrame({"player_id": ["A", "A"], "date": pd.to_datetime(["2025-01-03", "2025-01-04"])})
    a = Q._asof(t, h, ["m", "n_q1"], "player_id")
    assert a.m.iloc[0] == 6.0 and a.n_q1.iloc[0] == 1        # the game of the 3rd itself is not read
    w = 0.5 ** (1 / Q.HALF_LIFE)
    assert np.isclose(a.m.iloc[1], (12.0 + w * 6.0) / (1 + w)) and a.n_q1.iloc[1] == 2
    pg2 = pg.copy()
    pg2.loc[1, "q1_sec"] = 60.0                                  # change the target game's own minutes
    a2 = Q._asof(t.iloc[:1], Q.minutes_history(pg2), ["m"], "player_id")
    assert a2.m.iloc[0] == 6.0


def test_the_team_pool_counts_recent_games_with_court_time():
    rows = []
    for k in range(12):
        d = pd.Timestamp("2025-01-01") + pd.Timedelta(days=k)
        rows.append({"team": "HOM", "game_id": f"G{k}", "date": d, "court_ok": True, "player_id": "S", "q1_sec": 500.0})
        if k >= 7:
            rows.append({"team": "HOM", "game_id": f"G{k}", "date": d, "court_ok": True, "player_id": "B", "q1_sec": 100.0})
    pg = pd.DataFrame(rows)
    pool = Q.team_pools(pg, pd.DataFrame({"game_id": ["G11"], "team": ["HOM"]}))
    s = pool.set_index("player_id").s
    assert s["S"] == 1.0 and np.isclose(s["B"], 4 / 10)       # B played 4 of the 10 games before G11


def test_reallocation_moves_a_newly_out_starters_minutes_and_never_scales_a_players_own_minutes():
    tg = pd.DataFrame({"game_id": ["G", "G"], "team": "HOM", "player_id": ["X", "Y"], "m": [8.0, 6.0]})
    pool = pd.DataFrame({"game_id": "G", "team": "HOM", "season": 2025, "player_id": ["X", "Y", "S", "Z"],
                         "s": [1.0, 1.0, 1.0, 1.0], "m": [8.0, 6.0, 9.0, 37.0]})
    status = {2025: {"Out": 0.0, "Questionable": 0.5}}
    base = Q.reallocate(tg, pool, {}, status)
    assert np.isclose(base.r.iloc[0], 1.0)
    out = Q.reallocate(tg, pool, {("G", "S"): "Out"}, status)
    assert np.isclose(out.r.iloc[0], 60 / 51)
    q = Q.reallocate(tg, pool, {("G", "X"): "Questionable"}, status)
    assert np.isclose(q.mu_min.iloc[0], 8.0), "X's own Questionable leaves X's own minutes unchanged (section 16)"
    assert np.isclose(q.mu_min.iloc[1], 6.0 * 60 / 56), "his teammates read the plain team total, with him at 0.5"
    long_gone = Q.reallocate(tg, pool.assign(s=[1.0, 1.0, 0.0, 1.0]), {("G", "S"): "Out"}, status)
    assert np.isclose(long_gone.r.iloc[0], 60 / 51), "a teammate with no recent minutes changes nothing when Out"
    assert (Q.reallocate(tg.assign(m=[11.0, 6.0]), pool, {("G", "S"): "Out"}, status).mu_min <= 12.0).all()


def test_the_rate_shrinks_to_the_prior_and_the_prior_to_the_league():
    ri = pd.DataFrame({"cur_points": [0.0, 50.0], "cur_minutes": [0.0, 100.0], "prev_points": [0.0, 0.0],
                       "prev_minutes": [0.0, 0.0], "league_points": [0.45, 0.45]})
    r = Q.shrunk_rate(ri, "points", 100.0, 50.0)
    assert np.isclose(r[0], 0.45)                                # no minutes anywhere: the league
    assert np.isclose(r[1], (50 + 100 * 0.45) / 200)


def test_k_trusts_this_season_when_the_prior_is_wrong_and_the_prior_when_this_season_is_thin():
    rng = np.random.default_rng(3)
    n = 4000
    true = rng.gamma(4.0, 0.1, n)
    mins = np.full(n, 30.0)
    y = pd.DataFrame({s: rng.poisson(true * mins) for s in Q.STATS})

    def world(cur_min, prev_true):
        return pd.DataFrame({**{f"cur_{s}": rng.poisson(true * cur_min) for s in Q.STATS}, "cur_minutes": float(cur_min),
                             **{f"prev_{s}": rng.poisson(prev_true * 2000) for s in Q.STATS}, "prev_minutes": 2000.0,
                             **{f"league_{s}": 0.4 for s in Q.STATS}})
    wrong_prior = Q.fit_k(world(1500, rng.permutation(true)), y, mins)
    thin_season = Q.fit_k(world(20, true), y, mins)
    for s in Q.STATS:
        assert wrong_prior[s][0] < thin_season[s][0], (wrong_prior, thin_season)


def test_report_is_read_30_minutes_after_print():
    rep = pd.DataFrame({"game_id": ["G", "G"], "team": "HOM", "player_id": ["X", "Y"], "player_name": ["x", "y"],
                        "status": ["Out", "Out"],
                        "report_ts": pd.to_datetime(["2025-01-02 22:20", "2025-01-02 22:40"], utc=True)})
    dec = pd.DataFrame({"game_id": ["G"], "decision_ts": pd.to_datetime(["2025-01-02 23:00"], utc=True)})
    roster = pd.DataFrame({"team": "HOM", "season": 2025, "player_id": ["X", "Y"], "player_name": ["x", "y"]})
    got = Q.report_at(rep, dec, roster)
    assert list(got.player_id) == ["X"], "the 22:40 report is known at 23:10, after the decision"


# ── pricing, placebo, harness ───────────────────────────────────────────────

def test_ev_is_priced_at_each_books_own_line():
    props = pd.DataFrame({"prop_id": [0], "mu": [4.0], "alpha": [0.0], "main_line": [3.5]})
    rows = pd.DataFrame({"prop_id": [0, 0], "bookmaker": ["hardrockbet", "fanduel"], "line": [3.5, 4.5],
                         "over_price": [-110.0, 120.0], "under_price": [-110.0, -150.0], "season": 2025,
                         "game_date": "2025-01-02", "T": pd.Timestamp("2025-01-02 23:05", tz="UTC"),
                         "market": "player_points_q1"})
    c = Q.priced(Q.long_offers(rows, props))
    from scipy.stats import poisson
    quoted = {"hardrockbet": 3.5, "fanduel": 4.5}
    assert len(c) == 4
    for _, r in c.iterrows():
        assert r.line == quoted[r.book], "an offer keeps its own book's line"
        po = poisson.sf(np.floor(quoted[r.book]), 4.0)
        p = po if r.side == "over" else 1 - po
        assert np.isclose(r.p_win, p) and np.isclose(r.ev, p * H.dec(r.price) - 1)


def test_placebo_identity_returns_the_real_bets_and_shuffles_stay_in_their_group():
    w = Q.synthetic_world(days=6)
    for g in Q.world_groups(w):
        if g.placebo is None:
            continue
        Q.assert_identity(g)
        pr = g.placebo
        perm = pr.perm(7)
        assert (pr.groups[perm] == pr.groups).all()
        assert not (perm == np.arange(pr.n)).all()


def test_thin_dates_join_their_season_and_market():
    keys = pd.DataFrame({"game_date": ["d1"] * 6 + ["d2"] * 2 + ["d3"] * 2, "prop_market": "m",
                         "season": [2025] * 10})
    g = Q.placebo_groups(keys)
    assert len(set(g[:6])) == 1 and len(set(g[6:])) == 1 and g[0] != g[6]


def test_the_harness_settles_a_proposition_on_its_first_quarter_stat():
    props = pd.DataFrame({"prop_id": [0, 1], "season": 2025, "game_date": "2025-01-02",
                          "T": pd.Timestamp("2025-01-02 23:05", tz="UTC"), "lead_min": 54.4})
    games = Q.games_table(props, np.array([4.0, 3.0]))
    bets = pd.DataFrame({"game_id": [0, 1], "market": "totals", "side": ["over", "under"], "line": [3.5, 3.5],
                         "price": [-110.0, -110.0]})
    assert H.grade(bets, games).result.tolist() == ["W", "W"]
    assert (Q.games_table(props, None).home_score == 0).all()


def test_a_planted_edge_shows_and_bet_files_hold_no_unstorable_column(fast_boot, tmp_path, monkeypatch):
    monkeypatch.setenv(Q.BETS_ENV, str(tmp_path / "bets"))
    w = Q.synthetic_world(days=12)
    games, times = Q.games_table(w["props"], w["props"].stat.to_numpy()), Q.times_table(w["props"])
    g = [x for x in Q.world_groups(w) if x.family == Q.FAMILY and x.market == "player_points_q1" and x.side == "over"][0]
    rows = Q.emit(g, games, times, seeds=(1, 2))
    assert len(rows) == 3 and all(len(r["placebo_rois"]) == 2 for r in rows)
    assert rows[0]["pool_n"] > 0 and rows[0]["pool_roi"] > 0, "the invented edge must show in the lowest cut"
    files = list((tmp_path / "bets").glob("*.parquet"))
    assert files
    b = pd.read_parquet(files[0])
    assert {"game_id", "side", "book", "line", "price", "result", "units", "risk"} <= set(b.columns)


def test_full_refuses_without_its_switches(monkeypatch, tmp_path):
    for v in (Q.GO_ENV, Q.RESULTS_ENV, Q.BETS_ENV):
        monkeypatch.delenv(v, raising=False)
    why = Q.refuse_full(tmp_path, tmp_path)
    assert any(Q.GO_ENV in x for x in why) and any(Q.RESULTS_ENV in x for x in why) and any(Q.BETS_ENV in x for x in why)
    assert any("q1_props" in x for x in why)


def test_the_strict_season_bar_needs_both_seasons_positive(monkeypatch):
    base = {"family": Q.FAMILY, "point": "D", "market": "player_points_q1", "side": "over", "cut_index": 0,
            "cut": 0.02, "axis_book": "best", "axis_quotes": "two_sided", "house5_passes": True,
            "n_confirm": 300, "n_2025": 300}
    cells = pd.DataFrame([{**base, "roi_2025": 0.05, "roi_confirm": 0.04},
                          {**base, "cut_index": 1, "cut": 0.04, "roi_2025": -0.01, "roi_confirm": 0.10}])
    monkeypatch.setattr(Q.V, "house_verdict_bands", lambda c: c)
    v = Q.strict_verdict(cells)
    assert v.passes_strict.tolist() == [True, False]


# ── section 14: the points line map ─────────────────────────────────────────

def lumpy_points(rng, mu):
    """Points in twos and threes, few ones: the shape that broke the negative binomial on 2023-24."""
    twos, threes, ones = rng.poisson(mu * 0.30), rng.poisson(mu * 0.10), rng.poisson(mu * 0.03)
    return 2 * twos + 3 * threes + ones


def test_the_line_map_follows_a_lumpy_count_and_is_monotone_across_lines():
    rng = np.random.default_rng(5)
    mu = rng.gamma(3.0, 1.2, 40000)
    y = lumpy_points(rng, mu)
    m = Q.fit_line_map(y, mu)
    assert m["lines"][0] == 0.5 and len(m["lines"]) >= 10
    test_mu = np.full(5000, 3.5)
    yt = lumpy_points(rng, test_mu)
    for L in (1.5, 2.5, 3.5, 4.5):
        p = Q.map_p_over(m, test_mu, np.full(5000, L))
        assert abs(p.mean() - (yt > L).mean()) < 0.03, (L, p.mean(), (yt > L).mean())
    grid = np.array(m["lines"])
    pm = Q.map_p_over(m, np.full(len(grid), 2.0), grid)
    assert (np.diff(pm) <= 1e-12).all()
    crossing = {"lines": np.array([0.5, 1.5]), "a": np.array([0.0, 1.0]), "b": np.array([0.0, 0.0])}
    assert np.allclose(Q.map_p_over(crossing, np.array([2.0, 2.0]), np.array([0.5, 1.5])), [0.5, 0.5]), \
        "a fit whose higher line reads higher is carried down to the lower line's chance"
    assert np.isnan(Q.map_p_over(m, np.array([3.0]), np.array([40.5]))[0])


def test_points_price_through_the_map_and_a_line_outside_it_falls_back_and_is_counted():
    rng = np.random.default_rng(6)
    mu = rng.gamma(3.0, 1.2, 20000)
    m = Q.fit_line_map(lumpy_points(rng, mu), mu)
    maps = {("points", 2025): m}
    off = pd.DataFrame({"mu_prop": [3.0, 3.0, 3.0], "line": [2.5, 2.5, 30.5], "alpha": [0.6, 0.6, 0.6],
                        "map_key": ["points|2025", "", "points|2025"]})
    po = Q.model_p_over(off.mu_prop.to_numpy(), off.line.to_numpy(), off.alpha.to_numpy(), off.map_key.to_numpy(), maps)
    assert np.isclose(po[0], Q.map_p_over(m, np.array([3.0]), np.array([2.5]))[0])
    import models.nba_props as nbm
    assert np.isclose(po[1], nbm.p_over(np.array([3.0]), np.array([2.5]), 0.6)[0])
    assert np.isclose(po[2], nbm.p_over(np.array([3.0]), np.array([30.5]), 0.6)[0])
    assert Q.map_fallbacks(off, maps) == 1


def test_walk_forward_never_lets_a_season_reach_its_own_fits():
    rng = np.random.default_rng(8)
    season = np.repeat([2024, 2025, 2026], 6000)
    raw = rng.gamma(3.0, 1.2, len(season))
    y = lumpy_points(rng, raw * 0.9).astype(float)
    ok = np.ones(len(season), bool)
    f, a, m, mu = Q.walk_forward(y, raw, season, ok, "points")
    y2 = y.copy()
    y2[season == 2026] *= 3                                  # 2025-26's own results
    f2, a2, m2, _ = Q.walk_forward(y2, raw, season, ok, "points")
    assert f2[2026] == f[2026] and a2[2026] == a[2026] and np.allclose(m2[2026]["a"], m[2026]["a"])
    y3 = y.copy()
    y3[season == 2025] *= 3                                  # 2024-25's results reach 2025-26 only
    f3, a3, m3, _ = Q.walk_forward(y3, raw, season, ok, "points")
    assert f3[2025] == f[2025] and a3[2025] == a[2025] and f3[2026] != f[2026]
    assert f[2024] == f[2025], "2024-25 is priced with 2023-24's factor"
    assert np.allclose(mu[season == 2025], raw[season == 2025] * f[2025])


# ── section 16: the review's fixes ──────────────────────────────────────────

def test_the_pool_status_rates_read_only_earlier_seasons_and_out_is_zero():
    fit = pd.DataFrame({"season": [2022, 2022, 2023, 2023, 2024, 2024],
                        "status": ["Available", "Available", "Available", "Questionable", "Available", "Available"],
                        "played": [True, True, False, True, False, False]})
    r = Q.pool_status_rates(fit, [2024, 2025])
    assert np.isclose(r[2024]["Available"], 2 / 3) and np.isclose(r[2024]["Questionable"], 1.0)
    assert np.isclose(r[2025]["Available"], 2 / 5), "2025 reads 2021-22 through 2023-24, never 2024-25 itself"
    assert r[2024]["Out"] == 0.0


def test_the_team_as_of_reads_box_lines_inactive_lists_and_known_reports_only():
    box = pd.DataFrame({"player_id": ["P", "P"], "date": pd.to_datetime(["2025-02-01", "2025-02-04"]),
                        "team": ["AAA", "BBB"]})                  # played for AAA; then on BBB's inactive list
    rep = pd.DataFrame({"player_id": ["P", "P"], "team": ["CCC", "DDD"],
                        "known": pd.to_datetime(["2025-02-06 20:00", "2025-02-06 23:30"], utc=True),
                        "rep_date": pd.to_datetime(["2025-02-06", "2025-02-06"])})
    rows = pd.DataFrame({"player_id": ["P", "P", "P", "P"],
                         "date": pd.to_datetime(["2025-02-03", "2025-02-05", "2025-02-06", "2025-02-04"]),
                         "T": pd.to_datetime(["2025-02-03 23:00", "2025-02-05 23:00", "2025-02-06 23:00",
                                              "2025-02-04 23:00"], utc=True)})
    got = list(Q.team_as_of(rows, box, rep))
    assert got == ["AAA", "BBB", "CCC", "AAA"], got
    # the 23:30 report is known after the 23:00 decision; the inactive list of the 4th is not read on the 4th


def test_the_departed_player_leaves_the_pool_once_his_new_team_lists_him():
    rows = []
    for k in range(6):
        d = pd.Timestamp("2025-02-01") + pd.Timedelta(days=k)
        for pl, sec in (("S", 500.0), ("T", 400.0)):
            if pl == "T" and k >= 4:
                continue                                          # T traded away after game 3
            rows.append({"team": "HOM", "game_id": f"G{k}", "date": d, "court_ok": True, "player_id": pl,
                         "q1_sec": sec, "season": 2025})
    pg = pd.DataFrame(rows)
    hist = Q.minutes_history(pg)
    tt = pd.DataFrame({"game_id": ["G5"], "team": ["HOM"], "date": [pd.Timestamp("2025-02-06")],
                       "T": [pd.Timestamp("2025-02-06 23:00", tz="UTC")], "season": [2025]})
    box = pg[["player_id", "date", "team"]].drop_duplicates()
    rep = pd.DataFrame({"player_id": pd.Series(dtype=object), "known": pd.Series(dtype="datetime64[ns, UTC]"),
                        "rep_date": pd.Series(dtype="datetime64[ns]"), "team": pd.Series(dtype=object)})
    before = Q.pool_frame(pg, hist, tt, box, rep)
    assert set(before.player_id) == {"S", "T"}
    moved = pd.concat([box, pd.DataFrame({"player_id": ["T"], "date": [pd.Timestamp("2025-02-05")], "team": ["AWY"]})])
    after = Q.pool_frame(pg, hist, tt, moved, rep)
    assert set(after.player_id) == {"S"}, "on AWY's inactive list the day before: no longer in HOM's pool"


def test_full_refuses_a_checkout_whose_books_or_floor_are_not_the_registered_ones(monkeypatch, tmp_path):
    import config
    for v, val in ((Q.GO_ENV, "1"), (Q.RESULTS_ENV, str(tmp_path)), (Q.BETS_ENV, str(tmp_path))):
        monkeypatch.setenv(v, val)
    # The registered books are the research's (betparx included); the live
    # deciding list dropped betparx on 2026-11-06, so a full re-run is refused
    # today -- which is the guard working. Check the pass case on the registered set.
    monkeypatch.setattr(config, "BEST_LINE_BOOKMAKERS", list(Q.REGISTERED_BOOKS))
    monkeypatch.setattr(H, "BETTABLE", tuple(Q.REGISTERED_BOOKS))
    assert not any("deciding books" in x or "price floor" in x for x in Q.refuse_full(tmp_path, tmp_path))
    monkeypatch.setattr(config, "BEST_LINE_BOOKMAKERS", ["draftkings", "fanduel"])
    assert any("deciding books" in x for x in Q.refuse_full(tmp_path, tmp_path))
    monkeypatch.setattr(config, "BEST_LINE_BOOKMAKERS", list(Q.REGISTERED_BOOKS))
    monkeypatch.setattr(H, "PRICE_FLOOR", -250.0)
    assert any("price floor" in x for x in Q.refuse_full(tmp_path, tmp_path))


def test_the_map_check_fits_its_factor_on_the_first_half_only():
    rng = np.random.default_rng(9)
    n = 6000
    date = np.repeat(np.arange(60), n // 60).astype("datetime64[D]")
    raw = rng.gamma(3.0, 1.2, n)
    y = lumpy_points(rng, raw * 0.9).astype(float)
    hist = np.ones(n, bool)
    a = Q.map_check(y, raw, date, hist)
    y2 = y.copy()
    y2[date >= date[n // 2]] *= 2                             # the second half's own results
    b = Q.map_check(y2, raw, date, hist)
    assert a[0]["factor_first_half"] == b[0]["factor_first_half"]
    assert all(np.isclose(x["line_map"], z["line_map"]) and np.isclose(x["negative_binomial"], z["negative_binomial"])
               for x, z in zip(a, b))


def test_october_and_february_are_reported_beside_each_cell(fast_boot):
    w = Q.synthetic_world(days=4)
    w["props"]["game_date"] = np.where(np.arange(len(w["props"])) % 2 == 0, "2025-02-03", "2025-10-24")
    g = [x for x in Q.world_groups(w) if x.family == Q.FAMILY and x.market == "player_points_q1" and x.side == "over"][0]
    g.cand["game_date"] = g.cand.game_id.map(w["props"].set_index("prop_id").game_date)
    games = Q.games_table(w["props"], w["props"].stat.to_numpy())
    rows = Q.beside_rows(g, games, w["props"], {"any": set(), "stat": set(), "side": set()})
    what = {r["what"] for r in rows}
    assert {"month October", "month February", "other months"} <= what
    oct_n = sum(r["bets"] for r in rows if r["what"] == "month October" and r["cut"] == g.cuts[0])
    all_n = sum(r["bets"] for r in rows if r["what"] == "all" and r["cut"] == g.cuts[0])
    assert 0 < oct_n < all_n


def test_roster_events_hold_box_lines_inactive_lists_and_reports_read_30_minutes_late():
    log = pd.DataFrame({"game_id": ["G1"], "player_id": ["P"], "game_date": ["2025-02-01"], "team": ["AAA"]})
    ina = pd.DataFrame({"game_id": ["G2", "GX"], "player_id": ["P", "P"], "game_date": ["2025-02-03", "2025-02-03"],
                        "team": ["BBB", "ZZZ"]})
    rep = pd.DataFrame({"game_id": ["G3", "G3"], "team": "CCC", "player_id": ["P", None], "player_name": ["p", "q"],
                        "status": ["Out", "NOT YET SUBMITTED"], "game_date": "2025-02-05",
                        "report_ts": pd.to_datetime(["2025-02-05 17:30", "2025-02-05 17:30"], utc=True)})
    roster = pd.DataFrame({"team": "CCC", "season": 2025, "player_id": ["P"], "player_name": ["p"]})
    box, r = Q.roster_events(log, ina, rep, {"G1", "G2", "G3"}, roster)
    assert sorted(box.team) == ["AAA", "BBB"], "an inactive listing counts; a game outside the regular set does not"
    assert list(r.team) == ["CCC"] and r.known.iloc[0] == pd.Timestamp("2025-02-05 18:00", tz="UTC")
