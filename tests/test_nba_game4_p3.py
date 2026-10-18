"""scripts/nba_game4_p3: the second search's shooting-luck gap and ratings
projection on first-half, first-quarter and team-total markets
(docs/nba_models_2026.md section 8 and 8.3). Every rule is pinned on small
hand-built or synthetic games by its outcome; each test was watched failing
once with the rule it guards broken. No real price is read here."""
import numpy as np
import pandas as pd
import pytest

from scripts import nba_game2_luck as L
from scripts import nba_game4_p3 as Q
from scripts import nba_game_harness as H
from scripts.nba_game2_verdict import house_verdict

SMALL = 60          # the floor the small worlds below use (the lab's is 300)


def _world(**kw):
    kw.setdefault("prior_games", 80)
    kw.setdefault("graded_games", 24)
    return Q.synthetic_world(**kw)


@pytest.fixture(scope="module")
def ran():
    w = _world()
    return w, Q.run_world(w, n_placebo=2, min_prior=SMALL)


# ── the registered cells ────────────────────────────────────────────────────

def test_section_8_registers_72_cells_24_shooting_luck_and_48_projection():
    specs = Q.cell_specs()
    assert len(specs) == 72
    f4 = {m for f, m, *_ in specs if f == Q.F4_FAMILY}
    f1 = {m for f, m, *_ in specs if f == Q.F1_FAMILY}
    assert f4 == {"totals_h1", "team_totals_home", "team_totals_away"}
    assert f1 == {"h2h_h1", "spreads_h1", "totals_h1", "h2h_q1", "spreads_q1", "totals_q1"}
    assert Q.F4_CUTS == (1.0, 2.0, 3.0, 4.0) and Q.F1_CUTS == (0.02, 0.04, 0.06, 0.08)


def test_every_cell_runs_through_the_harness_and_bets(ran):
    _, out = ran
    assert {f: len(r) for f, r in out["rows"].items()} == {"P3_F4": 24, "P3_F1": 48}
    for fam, rows in out["rows"].items():
        by_market = pd.DataFrame(rows).groupby("market")["pool_n"].sum()
        assert (by_market > 0).all(), (fam, by_market.to_dict())


def test_the_two_signals_carry_their_own_labels_so_a_gap_cut_is_never_an_ev_cuts_neighbour(ran):
    _, out = ran
    cells = pd.DataFrame(out["rows"]["P3_F4"] + out["rows"]["P3_F1"])
    both = cells[cells["market"] == "totals_h1"]
    assert set(both["family"]) == {"P3_F4", "P3_F1"}
    v = house_verdict(cells)                      # asserts no two cells share every axis
    assert len(v) == 72


# ── shooting luck: what the gap is ──────────────────────────────────────────

def _side(gid, date, team, opp, pts=105, fg3m=12, fg3a=34, ftm=17, fta=22,
          o_pts=105, o_fg3m=12, o_fg3a=34, o_ftm=17, o_fta=22, poss=100.0):
    return {"game_id": gid, "season": 2024, "game_date": date, "team": team, "opp": opp,
            "pts": pts, "fg3m": fg3m, "fg3a": fg3a, "ftm": ftm, "fta": fta,
            "opp_pts": o_pts, "opp_fg3m": o_fg3m, "opp_fg3a": o_fg3a, "opp_ftm": o_ftm,
            "opp_fta": o_fta, "poss": poss}


def _game(gid, date, home, away, h, a, hposs=100.0):
    """Both team rows; h / a are each team's own (pts, fg3m, fg3a, ftm, fta)."""
    k = ("pts", "fg3m", "fg3a", "ftm", "fta")
    hd, ad = dict(zip(k, h)), dict(zip(k, a))
    return [_side(gid, date, home, away, **hd, **{f"o_{x}": v for x, v in ad.items()}, poss=hposs),
            _side(gid, date, away, home, **ad, **{f"o_{x}": v for x, v in hd.items()}, poss=hposs)]


def _luck_games(bos_opp_threes=12, det_opp_threes=12, bos_own_threes=14):
    """DET and BOS each play ten games before 2024-01-20 against other teams,
    then meet there (DET at home). bos_opp_threes: threes BOS's opponents made
    in each earlier game -- BOS's defensive luck. bos_own_threes: BOS's own
    (F4 leaves a team's own shooting as played; it only moves the league rate)."""
    rows, games = [], []
    for i in range(10):
        d = f"2024-01-{i + 1:02d}"
        rows += _game(f"D{i}", d, "DET", f"X{i}", (104, 11, 33, 16, 21), (106, det_opp_threes, 34, 18, 22))
        rows += _game(f"B{i}", d, "BOS", f"Y{i}", (110, bos_own_threes, 38, 15, 19),
                      (101, bos_opp_threes, 34, 16, 21))
        games += [{"game_id": f"D{i}", "season": 2024, "game_date": d, "home_team": "DET", "away_team": f"X{i}"},
                  {"game_id": f"B{i}", "season": 2024, "game_date": d, "home_team": "BOS", "away_team": f"Y{i}"}]
    games.append({"game_id": "T", "season": 2024, "game_date": "2024-01-20",
                  "home_team": "DET", "away_team": "BOS"})
    proj = L.f4_projections(pd.DataFrame(games), pd.DataFrame(rows))
    return proj[proj["game_id"] == "T"].reset_index(drop=True)


def _gaps(proj):
    return Q.f4_signal(proj).set_index("market")["strength"]


def test_the_team_total_gaps_add_up_to_f4s_total_gap_and_differ_by_its_margin_gap():
    proj = _luck_games(bos_opp_threes=17, det_opp_threes=8)
    g = _gaps(proj)
    assert g["team_totals_home"] + g["team_totals_away"] == pytest.approx(proj.loc[0, "gap_total"])
    assert g["team_totals_home"] - g["team_totals_away"] == pytest.approx(proj.loc[0, "gap_margin"])
    assert abs(g["team_totals_home"]) > 0.5 and abs(g["team_totals_away"]) > 0.5


def test_a_teams_total_reads_only_the_luck_of_the_defence_it_scores_against():
    # six more threes by BOS's opponents, six fewer by BOS: the league's rate is unchanged
    calm = _luck_games(bos_opp_threes=12, bos_own_threes=14)
    hot = _luck_games(bos_opp_threes=18, bos_own_threes=8)
    gc, gh = _gaps(calm), _gaps(hot)
    # BOS's opponents shot hot from three: BOS's raw defence looks worse than
    # it is, so once the luck is removed DET (at home, scoring against BOS) is
    # projected to score LESS
    assert gh["team_totals_home"] < gc["team_totals_home"] - 0.5
    # how BOS's opponents shot says nothing about BOS's own scoring, which reads DET's defence
    assert gh["team_totals_away"] == pytest.approx(gc["team_totals_away"], abs=1e-9)


def test_the_first_half_total_reads_f4s_full_game_gap_unscaled():
    proj = _luck_games(bos_opp_threes=17, det_opp_threes=8)
    assert _gaps(proj)["totals_h1"] == pytest.approx(proj.loc[0, "gap_total"])
    assert abs(proj.loc[0, "gap_total"]) > 1.0


def test_each_side_carries_the_gap_in_its_own_favour(ran):
    w, out = ran
    cand = out["cand"]["P3_F4"]
    sig = w["signal"].set_index(["game_id", "market"])["strength"]
    x = cand.assign(gap=[sig[(g, m)] for g, m in zip(cand["game_id"], cand["market"])])
    over, under = x[x["side"] == "over"], x[x["side"] == "under"]
    assert np.allclose(over["strength"], over["gap"]) and np.allclose(under["strength"], -under["gap"])
    assert set(x["market"]) == set(Q.F4_SIDES)


# ── the projection scaled to the period ─────────────────────────────────────

def _maps(w, **kw):
    return Q.period_maps(w["refs"], w["games_p"], (2025, 2026), min_prior=SMALL, **kw)


def _with(games_p, seasons, col, add):
    g = games_p.copy()
    sel = g["season"].isin(seasons)
    g.loc[sel, col] = g.loc[sel, col] + add
    return g


def test_the_period_map_is_least_squares_on_that_periods_own_result():
    w = _world()
    maps, _ = _maps(w)
    x = w["refs"].merge(Q.period_results(w["games_p"]).drop(columns="season"), on="game_id")
    for p in Q.PERIODS:
        pr = x[(x["season"] >= 2021) & (x["season"] < 2025)]
        b, a = np.polyfit(pr["margin"], pr[f"margin_{p}"], 1)
        assert maps[(2025, p, "margin")] == pytest.approx((a, b), rel=1e-4, abs=1e-4)
        b, a = np.polyfit(pr["total"], pr[f"total_{p}"], 1)
        assert maps[(2025, p, "total")] == pytest.approx((a, b), rel=1e-4, abs=1e-4)


def test_the_period_map_and_its_error_read_only_seasons_before_the_one_they_price():
    w = _world()
    maps, dists = _maps(w)
    later = _with(w["games_p"], (2025, 2026), "home_h1", 9.0)
    m2, d2 = Q.period_maps(w["refs"], later, (2025, 2026), min_prior=SMALL)
    assert m2[(2025, "h1", "margin")] == maps[(2025, "h1", "margin")]
    assert np.array_equal(d2[(2025, "spreads_h1")].win_whole, dists[(2025, "spreads_h1")].win_whole)
    # the season before does move it
    earlier = _with(w["games_p"], (2024,), "home_h1", 9.0)
    m3, _ = Q.period_maps(w["refs"], earlier, (2025, 2026), min_prior=SMALL)
    assert m3[(2025, "h1", "margin")] != maps[(2025, "h1", "margin")]
    assert dists[(2025, "spreads_h1")].n == int(((w["refs"]["season"] >= 2021)
                                                  & (w["refs"]["season"] < 2025)).sum())


def test_the_period_map_starts_at_2020_21_the_first_calibrated_season():
    w = _world()
    maps, _ = _maps(w)
    g20 = w["games_p"][w["games_p"]["season"] == 2021].assign(
        game_id=lambda d: "Z" + d["game_id"], season=2020)
    r20 = w["refs"][w["refs"]["season"] == 2021].assign(
        game_id=lambda d: "Z" + d["game_id"], season=2020, margin=lambda d: -5 * d["margin"])
    m2, _ = Q.period_maps(pd.concat([w["refs"], r20]), pd.concat([w["games_p"], g20]),
                          (2025, 2026), min_prior=SMALL)
    assert m2[(2025, "h1", "margin")] == maps[(2025, "h1", "margin")]


def test_too_few_earlier_games_refuses_rather_than_reading_the_season_itself():
    w = _world()
    with pytest.raises(RuntimeError, match="no fallback"):
        Q.period_maps(w["refs"], w["games_p"], (2025, 2026), min_prior=10_000)


def test_each_season_is_calibrated_by_its_own_model_and_2019_20_is_left_out():
    class M:
        def __init__(self, add):
            self.calib = None if add is None else {"margin": np.array([add, 1.0, 0.0, 0.0]),
                                                   "total": np.array([0.0, 1.0, 0.0, 0.0])}
            self.f5 = None

    def ref(s):
        return pd.DataFrame({"game_id": [f"G{s}"], "season": [s], "raw_margin": [3.0], "raw_total": [220.0],
                             "b2b_h": [0.0], "b2b_a": [0.0], "pace_lg": [100.0], "L": [110.0]})
    refs = {s: ref(s) for s in (2020, 2021, 2022)}
    models = {2020: M(None), 2021: M(1.0), 2022: M(2.0)}
    r = Q.calibrated_refs(refs, models).set_index("season")["margin"]
    assert r.to_dict() == {2021: pytest.approx(4.0), 2022: pytest.approx(5.0)}


def test_a_period_moneyline_removes_the_tie_mass():
    # residuals on whole numbers: a level half carries real mass at a centre of 0
    rng = np.random.default_rng(3)
    dist = H.ResidDist(rng.integers(-12, 13, 4000).astype(float), "test")
    proj = pd.DataFrame({"game_id": ["G"], "season": [2025], "margin": [0.0], "total": [220.0]})
    maps = {(2025, p, k): (0.0, 1.0 if k == "margin" else 0.5) for p in Q.PERIODS for k in ("margin", "total")}
    dists = {(2025, f"{k}_{p}"): dist for p in Q.PERIODS for k in ("spreads", "totals")}
    f = Q.f1_fair(proj, maps, dists).set_index("market")
    w, push, lose = dist.probs(np.array([0.0]), np.array([0.0]))
    assert push[0] > 0.02
    assert f.loc["h2h_h1", "p_home"] == pytest.approx(w[0] / (w[0] + lose[0]))
    assert f.loc["h2h_h1", "p_home"] != pytest.approx(w[0])


def test_the_projection_is_priced_with_its_own_period_error_never_the_markets(ran):
    _, out = ran
    key = ["game_id", "market", "book", "side", "line", "price"]
    c = out["cand"]["P3_F1"]
    x = c[key + ["p_win"]].merge(out["neutral"][key + ["p_win"]], on=key, suffixes=("", "_mkt"))
    sp = x[x["market"] == "spreads_h1"]
    assert len(sp) and not np.allclose(sp["p_win"], sp["p_win_mkt"])
    # and it is exactly the projection's own distribution at its own centre
    f = out["fair"].set_index(["game_id", "market"])
    r = sp.iloc[0]
    mu = f.loc[(r["game_id"], "spreads_h1"), "mu"]
    s = int(out["dd"].games.set_index("game_id").loc[r["game_id"], "season"])
    pw, _ = H.side_probs(np.array(["spreads_h1"]), np.array([r["side"]]), np.array([r["line"]]),
                         mu=[mu], sigma=np.array([out["dists"][(s, "spreads_h1")]], dtype=object))
    assert r["p_win"] == pytest.approx(pw[0])


# ── the market's own pricing ────────────────────────────────────────────────

def test_the_market_pricing_reads_only_earlier_seasons():
    w = _world()
    d = Q.period_market_pricing(w["close"], w["games_p"], (2025, 2026), min_prior=SMALL)
    later = _with(w["games_p"], (2025, 2026), "home_q1", 7.0)
    d2 = Q.period_market_pricing(w["close"], later, (2025, 2026), min_prior=SMALL)
    assert np.array_equal(d[(2025, "spreads_q1")].win_whole, d2[(2025, "spreads_q1")].win_whole)
    earlier = _with(w["games_p"], (2024,), "home_q1", 7.0)
    d3 = Q.period_market_pricing(w["close"], earlier, (2025, 2026), min_prior=SMALL)
    assert not np.array_equal(d[(2025, "spreads_q1")].win_whole, d3[(2025, "spreads_q1")].win_whole)


def test_a_season_with_too_few_earlier_games_gets_no_pricing_and_the_run_stops():
    w = _world()
    n_before_2025 = int((w["close"]["season"] < 2025).sum() / 2)
    d = Q.period_market_pricing(w["close"], w["games_p"], (2025, 2026), min_prior=n_before_2025 + 1)
    assert (2025, "totals_h1") not in d and (2026, "totals_h1") in d
    with pytest.raises(RuntimeError, match="no distribution"):
        Q.require_pricing(d, (2025, 2026), Q.PRICED_MARKETS, "test")


def test_team_totals_take_f6ds_distribution():
    from scripts.nba_game2_market import team_total_dist
    w = _world()
    d = Q.market_pricing(w["close"], w["games_p"], (2025, 2026), min_prior=SMALL)
    tt = team_total_dist(w["close"], w["games_p"], min_games=SMALL)
    for s in (2025, 2026):
        for m in ("team_totals_home", "team_totals_away"):
            assert np.array_equal(d[(s, m)].win_whole, tt[(s, m)].win_whole)
    Q.require_pricing(d, (2025, 2026), Q.PRICED_MARKETS, "test")


# ── the decision, settlement and the placebo ────────────────────────────────

def test_a_purchase_outside_45_to_75_minutes_is_never_a_decision():
    w = _world()
    gid = w["pe"]["game_id"].iloc[0]
    late = w["pe"]["game_id"] == gid
    for c in ("snapshot_at", "fetch_at"):
        w["pe"].loc[late, c] = w["pe"].loc[late, "tip"] - pd.Timedelta(minutes=120)
    out = Q.run_world(w, n_placebo=1, min_prior=SMALL)
    assert gid not in set(out["times"]["game_id"])
    for c in out["cand"].values():
        assert gid not in set(c["game_id"])
    assert len(out["times"]) == w["pe"]["game_id"].nunique() - 1


def test_a_first_half_total_bet_settles_on_the_first_two_quarters():
    tip = pd.Timestamp("2025-01-16T00:30:00Z")
    games = pd.DataFrame([{"game_id": "G", "season": 2025, "game_date": "2025-01-15", "tip": tip,
                           "home_team": "DET", "away_team": "BOS", "home_score": 110.0, "away_score": 100.0}])
    per = pd.DataFrame([{"game_id": "G", "period": i + 1, "home_points": h, "away_points": a}
                        for i, (h, a) in enumerate(zip((25, 25, 30, 30), (30, 25, 20, 25)))])
    games_p = H.with_periods(games, periods=per)            # first half 50-55: 105 points
    at = tip - pd.Timedelta(minutes=55)
    pe = pd.DataFrame([{"game_id": "G", "season": 2025, "game_date": "2025-01-15", "tip": tip,
                        "market": "totals_h1", "book": "fanduel", "snapshot_at": at, "fetch_at": at,
                        "line": 107.5, "price_a": -110.0, "price_b": -110.0, "coherent": True}])
    times = H.per_event_times(pe, "D")
    off = H.offers(H.visible(pe, times))
    neutral = H.fair_offers(off, pd.DataFrame({"game_id": ["G"], "market": ["totals_h1"], "mu": [108.0],
                                               "sigma": [10.0], "p_home": [np.nan]}))
    signal = pd.DataFrame({"game_id": ["G"], "market": ["totals_h1"], "strength": [3.5]})
    rows, _ = Q.emit_f4(Q.derivative_data(games_p, pe), times, neutral, signal, (2025,), n_placebo=1)
    r = {(x["market"], x["side"], x["cut"]): x for x in rows}[("totals_h1", "over", 1.0)]
    # the game went 210, well over 107.5; the half went 105, under it: a loss
    assert r["n_choose"] == 1 and r["units_choose"] == pytest.approx(-1.1)


def test_the_placebo_moves_the_number_between_games_on_a_date_and_never_the_price():
    w = _world()
    sig = w["signal"]
    runs = Q.shuffled(sig, w["games_p"], 3)
    dates = w["games_p"].set_index("game_id")["game_date"]
    for sh in runs:
        a = sig.assign(d=sig["game_id"].map(dates)).groupby(["d", "market"])["strength"].apply(sorted)
        b = sh.assign(d=sh["game_id"].map(dates)).groupby(["d", "market"])["strength"].apply(sorted)
        assert a.to_dict() == b.to_dict()
    moved = sig.merge(runs[0], on=["game_id", "market"], suffixes=("", "_sh"))
    assert (moved["strength"] != moved["strength_sh"]).any()
    out = Q.run_world(w, n_placebo=1, min_prior=SMALL)
    key = ["game_id", "market", "book", "side", "line"]
    nm = out["neutral"][out["neutral"]["market"].isin(list(Q.F4_SIDES))]
    pl = L.side_strength(nm, runs[0].merge(nm[["game_id", "market"]].drop_duplicates()))
    x = out["cand"]["P3_F4"][key + ["price"]].merge(pl[key + ["price"]], on=key, suffixes=("", "_pl"))
    assert len(x) and (x["price"] == x["price_pl"]).all()


# ── seasons and the refusals ────────────────────────────────────────────────

def test_choosing_seasons_are_every_graded_season_but_2025_26_and_the_pool_is_all(ran):
    assert Q.choosing((2024, 2025, 2026)) == (2024, 2025)
    assert Q.graded_seasons([2024]) == (2024, 2025, 2026)
    _, out = ran
    for rows in out["rows"].values():
        assert {r["pool_seasons"] for r in rows} == {"2025,2026"}
        assert {r["choose_seasons"] for r in rows} == {"2025"}


def _odds_row(gid, season, market="totals_h1"):
    return {"game_id": gid, "market": market, "bookmaker": "fanduel", "snapshot_type": "open",
            "snapshot_at": f"{season - 1}-12-01T23:35:00Z", "source": H.PER_EVENT_SOURCE,
            "created_at": "2026-10-16 00:00:00+00", "home_price": None, "away_price": None,
            "spread_home": None, "total_line": 110.5, "over_price": -110.0, "under_price": -110.0}


def _games3(seasons):
    return pd.DataFrame([{"game_id": f"G{s}_{i}", "season": s, "game_date": f"{s - 1}-12-01",
                          "tip": pd.Timestamp(f"{s - 1}-12-02T00:30:00Z")} for s in seasons for i in range(3)])


def test_a_partly_bought_season_makes_the_graded_load_refuse(tmp_path):
    games = _games3((2024, 2025, 2026))
    rows = [_odds_row(f"G{s}_{i}", s) for s in (2025, 2026) for i in range(3)] + [_odds_row("G2024_0", 2024)]
    pd.DataFrame(rows).to_parquet(tmp_path / "nba_odds.parquet")
    with pytest.raises(RuntimeError, match="too few games"):
        Q.load_derivatives(games, tmp_path)
    full = rows + [_odds_row(f"G2024_{i}", 2024) for i in (1, 2)]
    pd.DataFrame(full).to_parquet(tmp_path / "nba_odds.parquet")
    pe, graded = Q.load_derivatives(games, tmp_path)
    assert graded == (2024, 2025, 2026) and pe["game_id"].nunique() == 9


def test_2024_25_and_2025_26_are_required_even_when_the_cache_lacks_one(tmp_path):
    games = _games3((2025, 2026))
    pd.DataFrame([_odds_row(f"G2026_{i}", 2026) for i in range(3)]).to_parquet(tmp_path / "nba_odds.parquet")
    with pytest.raises(RuntimeError, match="too few games"):
        Q.load_derivatives(games, tmp_path)


def test_full_refuses_without_the_owners_go_before_reading_anything(monkeypatch, tmp_path):
    monkeypatch.delenv("NBA_GAME2_GO", raising=False)

    def boom(*a, **k):
        raise AssertionError("read data before refusing")
    monkeypatch.setattr(H, "load", boom)
    monkeypatch.setattr(H, "load_per_event", boom)
    with pytest.raises(SystemExit):
        Q.full(tmp_path, out=tmp_path / "out")
    assert not (tmp_path / "out").exists()
