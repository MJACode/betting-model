"""scripts/nba_game4_p1: P1 of the fourth NBA search, the market-anchored model
(docs/nba_models_2026.md sections 8 and 8.1). Every rule is pinned on small
hand-built or synthetic games by its outcome; each test was watched failing
once with the rule it guards broken. No real price is read."""
import numpy as np
import pandas as pd
import pytest

from scripts import nba_game4_p1 as M
from scripts import nba_game_harness as H

TIP = pd.Timestamp("2024-01-16T00:30:00Z")


# ── the cells ───────────────────────────────────────────────────────────────

def test_the_registered_cells_are_72_full_game_48_period_and_8_team_total():
    specs = M.cell_specs()
    assert len(specs) == 128
    full = [s for s in specs if s[1] in M.FULL_LABELS]
    assert len(full) == 72 and {s[0] for s in full} == {"A", "C", "D"}
    period = [s for s in specs if s[1] in M.PERIOD_LABELS]
    assert len(period) == 48 and {s[0] for s in period} == {"D"}
    tt = [s for s in specs if s[1] == M.TEAM_TOTALS]
    assert len(tt) == 8 and {s[2] for s in tt} == {"over", "under"}
    assert {s[4] for s in specs} == {0.02, 0.04, 0.06, 0.08}


# ── the centre's model ──────────────────────────────────────────────────────

def _signal_rows(n=600, seed=0, beta=2.0):
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 1, n)
    off = rng.normal(0, 5, n)
    y = off + beta * x + rng.normal(0, 3, n)
    return x[:, None], y, off


def test_the_offset_is_not_penalised_and_its_coefficient_stays_one():
    rng = np.random.default_rng(1)
    X = rng.normal(0, 1, (500, 3))
    off = rng.normal(0, 8, 500)
    y = off + 3.0                                  # the market off by a constant 3 points
    m = M.OffsetRidge(C=1e-6).fit(X, y, off)       # a penalty that kills every input
    assert np.allclose(m.predict(X, off), off + 3.0, atol=1e-6)


def test_a_real_input_is_recovered_and_a_harder_penalty_shrinks_it():
    X, y, off = _signal_rows()
    loose = M.OffsetRidge(C=1e6).fit(X, y, off)
    tight = M.OffsetRidge(C=1e-3).fit(X, y, off)
    slope = np.polyfit(X[:, 0], loose.move(X), 1)[0]
    assert slope == pytest.approx(2.0, abs=0.3)
    assert np.std(tight.move(X)) < 0.5 * np.std(loose.move(X))


def test_the_penalty_is_offset_logits_mean_loss_plus_w_squared_over_2Cn():
    from scipy.optimize import minimize
    X, y, off = _signal_rows(n=300, seed=4)
    X = np.c_[X, np.random.default_rng(5).normal(0, 1, (300, 2))]
    C = 0.01
    m = M.OffsetRidge(C).fit(X, y, off)
    Z = (X - X.mean(0)) / (X.std(0) + 1e-9)
    s = (y - off).std() + 1e-9
    u = (y - off) / s
    n = len(y)

    def f(w):
        e = u - w[0] - Z @ w[1:]
        return np.mean(e ** 2) / 2 + (w[1:] ** 2).sum() / (2 * C * n)
    w = minimize(f, np.zeros(Z.shape[1] + 1), method="BFGS").x
    assert np.allclose(m.w, w, atol=1e-5)


# ── the walk-forward ────────────────────────────────────────────────────────

def _rows(label="spreads", seasons=(2021, 2022, 2023, 2024), per=400, seed=0):
    rng = np.random.default_rng(seed)
    feats = list(M.features_of(label))
    out = []
    for s in seasons:
        X = rng.normal(0, 1, (per, len(feats)))
        off = rng.normal(0, 6, per)
        y = off + 1.5 * X[:, 0] + rng.normal(0, 10, per)
        d = pd.DataFrame(X, columns=feats)
        d["game_id"] = [f"G{s}_{i}" for i in range(per)]
        d["market"] = label
        d["season"] = s
        d["game_date"] = f"{s - 1}-12-01"
        d["offset"], d["y"] = off, y
        out.append(d)
    return pd.concat(out, ignore_index=True)


def test_a_seasons_model_is_fit_on_earlier_seasons_only():
    r = _rows()
    a, _ = M.walk_forward(r, "spreads", graded=(2023,))
    poisoned = r.copy()
    later = poisoned["season"] >= 2023
    poisoned.loc[later, "y"] = poisoned.loc[later, "y"] + 1000.0 * poisoned.loc[later, "proj"]
    b, _ = M.walk_forward(poisoned, "spreads", graded=(2023,))
    assert len(a) == 400
    assert np.allclose(a.sort_values("game_id")["move"], b.sort_values("game_id")["move"])


def test_the_penalty_is_chosen_on_the_training_seasons_only():
    r = _rows(seasons=(2021, 2022, 2023, 2024, 2025), per=900)
    _, fa = M.walk_forward(r, "spreads", graded=(2025,))
    poisoned = r.copy()
    s25 = poisoned["season"] == 2025
    poisoned.loc[s25, "y"] = -poisoned.loc[s25, "y"] * 50
    _, fb = M.walk_forward(poisoned, "spreads", graded=(2025,))
    assert fa[0]["C"] == fb[0]["C"] and fa[0]["n_train"] == 3600


def test_fewer_than_the_minimum_training_rows_gives_no_model_and_no_bet():
    r = _rows(seasons=(2021, 2022), per=200)
    mv, fits = M.walk_forward(r, "spreads", graded=(2022,))
    assert mv.empty and fits[0]["C"] is None and fits[0]["n_train"] == 200
    mv, fits = M.walk_forward(r, "spreads", graded=(2022,), min_train=150)
    assert len(mv) == 200


def test_the_moneyline_model_is_the_nhl_offset_logit_with_its_own_penalty_rule():
    rng = np.random.default_rng(2)
    r = _rows("h2h", per=500)
    r["offset"] = r["offset"] / 6.0                     # log-odds
    p = 1 / (1 + np.exp(-(r["offset"] + 0.8 * r["proj"])))
    r["y"] = (rng.random(len(r)) < p).astype(float)
    mv, fits = M.walk_forward(r, "h2h", graded=(2024,))
    assert fits[0]["C"] in M.C_GRID
    # the move is in log-odds and follows the input that drives the result
    t = r[r["season"] == 2024].set_index("game_id").loc[mv["game_id"]]
    assert np.corrcoef(t["proj"], mv["move"])[0, 1] > 0.5


def test_moneylines_fit_the_nhl_offset_logit_and_centres_fit_the_ridge():
    from models.nhl_moneyline_anchored import OffsetLogit
    rng = np.random.default_rng(3)
    r = _rows("h2h", per=300)
    r["offset"] = r["offset"] / 6.0
    r["y"] = (rng.random(len(r)) < 1 / (1 + np.exp(-r["offset"]))).astype(float)
    m, C, n = M.fit_one(r, M.features_of("h2h"), "ml")
    assert isinstance(m, OffsetLogit) and n == 1200
    x = r[list(M.features_of("h2h"))].to_numpy()
    p = m.predict_proba(x, r["offset"].to_numpy())[:, 1]
    assert np.allclose(np.log(p / (1 - p)) - r["offset"].to_numpy(), M.model_move(m, x, "ml"), atol=1e-8)
    m2, _, _ = M.fit_one(_rows("spreads"), M.features_of("spreads"), "spread")
    assert isinstance(m2, M.OffsetRidge)


# ── what the model is fit to ────────────────────────────────────────────────

def _period_games():
    return pd.DataFrame({"game_id": ["G", "L"], "season": 2024, "game_date": "2024-01-15",
                         "home_score": [110.0, 100.0], "away_score": [100.0, 104.0],
                         "home_q1": [30.0, 25.0], "away_q1": [20.0, 25.0],
                         "home_h1": [50.0, 55.0], "away_h1": [55.0, 55.0]})


def test_a_level_period_is_left_out_of_the_moneyline_fit_and_a_full_game_never_is():
    g = _period_games()
    assert np.isnan(M.outcome("h2h_h1", g)[1]) and M.outcome("h2h_h1", g)[0] == 0.0
    assert np.isnan(M.outcome("h2h_q1", g)[1]) and M.outcome("h2h_q1", g)[0] == 1.0
    assert M.outcome("h2h", g).tolist() == [1.0, 0.0]


def test_every_market_is_fit_to_what_settles_it():
    g = _period_games()
    assert M.outcome("spreads_h1", g).tolist() == [-5.0, 0.0]
    assert M.outcome("totals_q1", g).tolist() == [50.0, 50.0]
    assert M.outcome("spreads", g).tolist() == [10.0, -4.0]
    assert M.outcome("team_totals_home", g).tolist() == [110.0, 100.0]
    assert M.outcome("team_totals_away", g).tolist() == [100.0, 104.0]


# ── inputs ──────────────────────────────────────────────────────────────────

def _base(game_ids=("G", "L")):
    n = len(game_ids)
    b = pd.DataFrame({"game_id": list(game_ids), "margin": [6.0, -2.0][:n], "total": [230.0, 220.0][:n],
                      "pace_h": [100.0, 98.0][:n], "pace_a": [97.0, 99.0][:n],
                      "gap_margin": [1.0, 0.0][:n], "gap_total": [3.0, -1.0][:n],
                      "altitude": [0.0, 1.0][:n], "h_game_no": [20.0, 5.0][:n],
                      "a_game_no": [21.0, 30.0][:n]})
    for i, f in enumerate(M.F5):
        b[f"{f}_h"], b[f"{f}_a"] = float(i + 1), float(10 * (i + 1))
    for s in ("h", "a"):
        for j, k in enumerate(M.SCHED):
            b[f"{s}_{k}"] = (1.0 if s == "h" else 2.0) + j
    return b


def test_a_team_total_reads_its_own_team_and_its_opponent():
    b = _base()
    h, a = M.oriented(b, "team_totals_home"), M.oriented(b, "team_totals_away")
    assert h["proj"].tolist() == [118.0, 109.0] and a["proj"].tolist() == [112.0, 111.0]
    assert h["luck"].tolist() == [2.0, -0.5] and a["luck"].tolist() == [1.0, -0.5]
    f = M.F5[0]
    assert h[f"own_{f}"].iloc[0] == 1.0 and h[f"opp_{f}"].iloc[0] == 10.0
    assert a[f"own_{f}"].iloc[0] == 10.0 and a[f"opp_{f}"].iloc[0] == 1.0
    assert h["pace_own"].iloc[0] == 100.0 and a["pace_own"].iloc[0] == 97.0
    assert h["own_rest"].iloc[0] == 1.0 and a["own_rest"].iloc[0] == 2.0
    assert h["is_home"].tolist() == [1.0, 1.0] and a["is_home"].tolist() == [0.0, 0.0]
    assert sorted(h.columns[1:]) == sorted(M.TEAM_FEATS)


def test_margin_models_take_home_minus_away_and_totals_take_the_sum():
    b = _base()
    m, t = M.oriented(b, "spreads_h1"), M.oriented(b, "totals")
    f = M.F5[1]
    assert m["proj"].iloc[0] == 6.0 and m["luck"].iloc[0] == 1.0 and m[f"d_{f}"].iloc[0] == 2.0 - 20.0
    assert t["proj"].iloc[0] == 230.0 and t["luck"].iloc[0] == 3.0 and t[f"s_{f}"].iloc[0] == 22.0
    assert sorted(m.columns[1:]) == sorted(M.MARGIN_FEATS) and sorted(t.columns[1:]) == sorted(M.TOTAL_FEATS)


def _fair():
    return pd.DataFrame({"game_id": ["G", "L", "G", "L"], "market": ["spreads", "spreads", "h2h", "h2h"],
                         "mu": [5.0, -1.0, np.nan, np.nan], "sigma": [12.0, 12.0, np.nan, np.nan],
                         "p_home": [np.nan, np.nan, 0.66, 0.45], "ref": "pinnacle"})


def test_the_offset_is_the_markets_own_fair_number_at_T():
    g = _period_games()
    r = M.model_rows("spreads", _fair(), _base(), g)
    assert r.set_index("game_id")["offset"].to_dict() == {"G": 5.0, "L": -1.0}
    r = M.model_rows("h2h", _fair(), _base(), g)
    assert np.allclose(r.set_index("game_id").loc[["G", "L"], "offset"],
                       np.log(np.array([0.66, 0.45]) / (1 - np.array([0.66, 0.45]))))


def test_a_games_inputs_do_not_move_when_its_result_does():
    g = _period_games()
    a = M.model_rows("spreads", _fair(), _base(), g)
    g2 = g.assign(home_score=[80.0, 140.0])
    b = M.model_rows("spreads", _fair(), _base(), g2)
    feats = list(M.MARGIN_FEATS) + ["offset"]
    pd.testing.assert_frame_equal(a[feats], b[feats])
    assert a["y"].tolist() != b["y"].tolist()


def test_a_game_the_luck_lab_leaves_out_reads_a_zero_gap(monkeypatch):
    games = pd.DataFrame({"game_id": ["E", "F"]})
    monkeypatch.setattr(M.L, "f4_projections",
                        lambda g, tb: pd.DataFrame({"game_id": ["F"], "gap_margin": [2.0], "gap_total": [-3.0]}))
    got = M.luck_inputs(games, None).set_index("game_id")
    assert got.loc["E"].tolist() == [0.0, 0.0] and got.loc["F"].tolist() == [2.0, -3.0]


def test_a_bet_counts_in_the_early_window_when_either_team_is_inside_its_first_10_games():
    b = _base()
    b["h_game_no"], b["a_game_no"] = [20.0, 5.0], [21.0, 30.0]
    assert M.early_games(b) == {"L"}
    b["h_game_no"], b["a_game_no"] = [11.0, 30.0], [10.0, 30.0]
    assert M.early_games(b) == {"G"}


def test_the_period_share_reads_only_earlier_seasons():
    g = pd.DataFrame({"season": [2023, 2024], "home_score": [100.0, 100.0], "away_score": [100.0, 100.0],
                      "home_q1": [25.0, 50.0], "away_q1": [25.0, 50.0],
                      "home_h1": [50.0, 90.0], "away_h1": [50.0, 90.0]})
    sh = M.period_shares(g, (2024, 2025))
    assert sh[(2024, "h1")] == pytest.approx(0.5) and sh[(2024, "q1")] == pytest.approx(0.25)
    assert sh[(2025, "h1")] == pytest.approx(0.7)
    with pytest.raises(ValueError):
        M.scaler("spreads_h1", sh)(2023)
    assert M.scaler(M.TEAM_TOTALS, sh)(2023) == 1.0


def test_the_period_scaling_is_one_constant_within_a_fit_and_moves_no_prediction():
    r = _rows("spreads_h1")
    a, fa = M.walk_forward(r, "spreads_h1", graded=(2024,), shares={(2024, "h1"): 0.5})
    b, fb = M.walk_forward(r, "spreads_h1", graded=(2024,), shares={(2024, "h1"): 1.0})
    assert fa[0]["share"] == 0.5 and fb[0]["share"] == 1.0
    assert np.allclose(a["move"], b["move"], atol=1e-8)


# ── the model's prices ──────────────────────────────────────────────────────

def _offers():
    rows = []
    for g in ("G", "L"):
        rows.append({"game_id": g, "market": "spreads", "book": "fanduel", "side": "home", "line": -4.5,
                     "price": -110.0})
        rows.append({"game_id": g, "market": "spreads", "book": "fanduel", "side": "away", "line": -4.5,
                     "price": -110.0})
        rows.append({"game_id": g, "market": "h2h", "book": "fanduel", "side": "home", "line": np.nan,
                     "price": -180.0})
        rows.append({"game_id": g, "market": "h2h", "book": "fanduel", "side": "away", "line": np.nan,
                     "price": 155.0})
    return pd.DataFrame(rows)


def test_with_nothing_to_say_the_model_prices_exactly_the_market():
    fair = _fair()
    zero = fair[["game_id", "market"]].assign(move=0.0)
    a = H.fair_offers(_offers(), fair).sort_values(["game_id", "market", "side"]).reset_index(drop=True)
    b = H.fair_offers(_offers(), M.model_fair(fair, zero)).sort_values(
        ["game_id", "market", "side"]).reset_index(drop=True)
    assert (a["ev"].to_numpy() == b["ev"].to_numpy()).all()


def test_a_move_toward_home_raises_home_and_lowers_away_at_the_home_number():
    fair = _fair()
    up = fair[["game_id", "market"]].assign(move=1.0)
    a = H.fair_offers(_offers(), fair).set_index(["game_id", "market", "side"])["ev"]
    b = H.fair_offers(_offers(), M.model_fair(fair, up)).set_index(["game_id", "market", "side"])["ev"]
    for mk in ("spreads", "h2h"):
        assert b[("G", mk, "home")] > a[("G", mk, "home")]
        assert b[("G", mk, "away")] < a[("G", mk, "away")]


def test_only_games_with_a_model_number_are_candidates():
    fair = _fair()
    mv = pd.DataFrame({"game_id": ["G"], "market": ["spreads"], "move": [0.5]})
    cand = H.fair_offers(_offers(), M.model_fair(fair, mv))
    assert set(zip(cand["game_id"], cand["market"])) == {("G", "spreads")}
    assert cand["ev"].notna().all()


def test_the_placebo_shuffles_the_move_and_keeps_each_games_own_market_number():
    ids = [f"G{i}" for i in range(6)]
    fair = pd.DataFrame({"game_id": ids, "market": "spreads", "mu": [float(i) for i in range(6)],
                         "sigma": 12.0, "p_home": np.nan})
    games = pd.DataFrame({"game_id": ids, "game_date": ["2024-01-01"] * 3 + ["2024-01-02"] * 3})
    mv = pd.DataFrame({"game_id": ids, "market": "spreads", "move": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]})
    seen_moved = False
    for f in M.placebo_fairs(fair, mv, games, 6):
        f = f.set_index("game_id")
        moved = f["mu"] - fair.set_index("game_id")["mu"]
        assert sorted(moved[ids[:3]]) == [10.0, 20.0, 30.0]          # day one's moves stay on day one
        assert sorted(moved[ids[3:]]) == [40.0, 50.0, 60.0]
        seen_moved |= not np.allclose(moved.loc[ids], mv["move"])
    assert seen_moved


# ── seasons the derivative cells grade ──────────────────────────────────────

def test_the_first_derivative_season_held_only_fits():
    assert M.derivative_plan((2025, 2026)) == ((2026,), ())
    assert M.derivative_plan((2024, 2025, 2026)) == ((2025, 2026), (2025,))


def test_the_held_derivative_seasons_are_read_from_counts_and_must_agree():
    rows = [{"market": m, "season": s} for m in H.DERIVATIVE_MARKETS for s in (2025, 2026)]
    assert M.derivative_seasons(pd.DataFrame(rows)) == (2025, 2026)
    rows.append({"market": "h2h_q1", "season": 2024})
    with pytest.raises(RuntimeError):
        M.derivative_seasons(pd.DataFrame(rows))


def test_the_derivative_markets_decide_at_the_per_game_purchase():
    tip = TIP
    q = pd.DataFrame({"game_id": ["G", "G"], "tip": [tip, tip],
                      "fetch_at": [tip - pd.Timedelta(minutes=200), tip - pd.Timedelta(minutes=61)]})
    dd = H.Data(games=pd.DataFrame(), quotes=q, fetches=pd.DataFrame())
    t = M.derivative_times(dd)
    assert t["T"].tolist() == [tip - pd.Timedelta(minutes=61)]


def test_each_game_is_projected_at_its_own_decision_time(monkeypatch):
    seen = []

    def fake_project(w, st, model, gm):
        seen.append(gm[["game_id", "T"]])
        return gm.assign(margin=1.0)
    monkeypatch.setattr(M.P, "project", fake_project)

    class W:
        games = pd.DataFrame({"game_id": ["G", "L"], "day": [1, 2]})
    games = pd.DataFrame({"game_id": ["G", "L"], "season": [2025, 2026]})
    times = pd.DataFrame({"game_id": ["G", "L"], "T": [TIP, TIP + pd.Timedelta(hours=5)]})
    M.project_at(W, None, {2025: None, 2026: None}, games, times)
    got = pd.concat(seen).set_index("game_id")["T"].to_dict()
    assert got == {"G": TIP, "L": TIP + pd.Timedelta(hours=5)}


# ── team totals pooled into one cell (the harness's market groups) ──────────

def _team_total_world():
    games = pd.DataFrame({"game_id": ["G", "K"], "season": 2025, "game_date": ["2025-01-15", "2025-01-16"],
                          "tip": [TIP, TIP + pd.Timedelta(days=1)], "home_team": "BOS", "away_team": "NYK",
                          "home_score": [120.0, 100.0], "away_score": [100.0, 115.0]})
    rows = []
    for g, tip in zip(games["game_id"], games["tip"]):
        at = tip - pd.Timedelta(minutes=60)
        base = {"game_id": g, "season": 2025, "game_date": "2025-01-15", "tip": tip, "book": "fanduel",
                "snapshot_at": at, "fetch_at": at, "coherent": True, "price_a": -110.0, "price_b": -110.0}
        rows.append({**base, "market": "team_totals_home", "line": 110.5})
        rows.append({**base, "market": "team_totals_away", "line": 107.5})
    pe = pd.DataFrame(rows)
    f = pe[["game_id", "tip", "fetch_at"]].drop_duplicates()
    f = f.assign(lead_min=(f["tip"] - f["fetch_at"]).dt.total_seconds() / 60)
    return H.Data(games=games, quotes=pe, fetches=f)


def test_both_teams_totals_grade_as_one_cell_per_side_and_cut():
    data = _team_total_world()
    t = H.per_event_times(data.quotes, "D")
    off = H.offers(H.visible(data.quotes, t))
    model = pd.DataFrame({"game_id": ["G", "K", "G", "K"],
                          "market": ["team_totals_home", "team_totals_home", "team_totals_away",
                                     "team_totals_away"],
                          "mu": [120.0, 120.0, 120.0, 120.0], "sigma": 10.0, "p_home": np.nan})
    cand = H.fair_offers(off, model)
    rows = H.run_cells(data, "T", "D", cand, cand, cuts=[0.0], sides_by_market={"team_totals": ["over"]},
                       choose_seasons=(2025,), times=t, market_groups=M.GROUPS)
    assert len(rows) == 1 and rows[0]["market"] == "team_totals"
    # four overs: home 120 > 110.5 W, home 100 < 110.5 L, away 100 < 107.5 L, away 115 > 107.5 W
    assert rows[0]["n_choose"] == 4
    assert rows[0]["units_choose"] == pytest.approx(2 * 1.0 - 2 * 1.1)
    alone = H.run_cells(data, "T", "D", cand, cand, cuts=[0.0], choose_seasons=(2025,), times=t,
                        sides_by_market={"team_totals_home": ["over"], "team_totals_away": ["over"]})
    assert [r["n_choose"] for r in alone] == [2, 2]


# ── the whole family on synthetic games ─────────────────────────────────────

def test_all_128_cells_run_end_to_end_on_synthetic_games():
    got = M.synthetic_cells_check(n_placebo=1, min_train=20, per_season=24)
    assert got["cells"] == 128 and got["full_bets"] > 0 and got["derivative_bets"] > 0
    assert got["derivative_graded"] == (2022, 2023, 2024, 2025, 2026)


def test_the_graded_run_refuses_without_the_go_flag(monkeypatch, tmp_path):
    monkeypatch.delenv(M.GO_ENV, raising=False)
    monkeypatch.setattr(M.H, "CACHE", tmp_path)
    with pytest.raises(SystemExit) as e:
        M.main(["--full"])
    assert e.value.code == 2


def test_the_graded_run_refuses_without_a_named_results_folder(monkeypatch, tmp_path):
    monkeypatch.setenv(M.GO_ENV, "1")
    monkeypatch.setenv("NBA_GAME2_BETS", str(tmp_path / "bets"))
    monkeypatch.delenv(M.RESULTS_ENV, raising=False)
    assert any(M.RESULTS_ENV in x for x in M.full_refusals(tmp_path))
    monkeypatch.setenv(M.RESULTS_ENV, str(tmp_path))
    assert not any(M.RESULTS_ENV in x for x in M.full_refusals(tmp_path))


def _rung(book, market, line, pa, pb, tip, gid="G", lead=60):
    return {"game_id": gid, "season": 2026, "game_date": "2024-01-15", "tip": tip,
            "market": market, "book": book, "fetch_at": tip - pd.Timedelta(minutes=lead),
            "snapshot_at": tip - pd.Timedelta(minutes=lead + 5), "line": float(line),
            "price_a": float(pa), "price_b": float(pb), "coherent": True}


def _ladder_quotes(tip):
    """BetRivers hangs three team-total numbers in one purchase, its main one
    (prices closest to even) first in the file; Hard Rock hangs a first-half
    total 3 points from the deciding books' median."""
    return pd.DataFrame([
        _rung("betrivers", "team_totals_home", 111.5, -112, -108, tip),
        _rung("betrivers", "team_totals_home", 109.5, -190, 150, tip),
        _rung("betrivers", "team_totals_home", 114.5, 150, -190, tip),
        _rung("pinnacle", "team_totals_home", 111.5, -110, -110, tip),
        _rung("fanduel", "team_totals_home", 111.5, -110, -110, tip),
        _rung("hardrockbet", "totals_h1", 117.5, 135, -165, tip),
        _rung("fanduel", "totals_h1", 114.5, -110, -110, tip),
        _rung("draftkings", "totals_h1", 114.5, -110, -110, tip),
        _rung("pinnacle", "totals_h1", 114.5, -110, -110, tip)])


def _offered(off):
    return {k: sorted(set(v)) for k, v in off.groupby(["market", "book"])["line"]}


def test_a_book_listing_several_numbers_is_offered_at_its_main_number_only(monkeypatch):
    """Section 8.1, 2026-10-18 (the review): the harness alone keeps whichever
    rung of a ladder is last in the file. P1 reads P2's rule: each book's main
    number, and no deciding book's derivative alternate."""
    times = pd.DataFrame({"game_id": ["G"], "T": [TIP - pd.Timedelta(minutes=60)]})
    monkeypatch.setattr(H, "market_fair", lambda vis, sig: pd.DataFrame())
    monkeypatch.setattr(H, "fair_offers", lambda off, fair: off)
    data = H.Data(games=pd.DataFrame(), quotes=_ladder_quotes(TIP), fetches=pd.DataFrame())
    got = _offered(M.make_point(data, "D", times, {}, pd.DataFrame()).off)
    assert got[("team_totals_home", "betrivers")] == [111.5]
    assert ("totals_h1", "hardrockbet") not in got
    assert got[("totals_h1", "fanduel")] == [114.5] and got[("totals_h1", "pinnacle")] == [114.5]


def test_the_graded_run_refuses_without_a_bets_folder(monkeypatch, tmp_path):
    """A passing cell's figures and its first-10-games split read its bets."""
    monkeypatch.setenv(M.GO_ENV, "1")
    monkeypatch.setenv(M.RESULTS_ENV, str(tmp_path))
    monkeypatch.delenv("NBA_GAME2_BETS", raising=False)
    assert any("NBA_GAME2_BETS" in x for x in M.full_refusals(tmp_path))
    monkeypatch.setenv("NBA_GAME2_BETS", str(tmp_path / "bets"))
    assert not any("NBA_GAME2_BETS" in x for x in M.full_refusals(tmp_path))
