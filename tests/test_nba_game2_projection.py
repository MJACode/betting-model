"""scripts/nba_game2_projection: F1, F1b and F5 of the second NBA game-market
search (docs/nba_models_2026.md section 6.3). Every feature rule and every
leak guard is pinned here on small games built by hand, never on real prices."""
import numpy as np
import pandas as pd
import pytest

from scripts import nba_game_harness as H
from scripts import nba_game2_projection as P

UTC = "UTC"


# ── a tiny world: two teams, two seasons ────────────────────────────────────

def _games(n_per_season=6, seasons=(2020, 2021)):
    rows = []
    for s in seasons:
        for i in range(n_per_season):
            day = pd.Timestamp(f"{s - 1}-12-01") + pd.Timedelta(days=2 * i)
            home, away = ("AAA", "BBB") if i % 2 == 0 else ("BBB", "AAA")
            rows.append({"game_id": f"G{s}_{i}", "season": s, "game_date": day.strftime("%Y-%m-%d"),
                         "tip": (day + pd.Timedelta(hours=24)).tz_localize(UTC),
                         "home_team": home, "away_team": away,
                         "home_score": 110 + i, "away_score": 100 + (i % 3)})
    return pd.DataFrame(rows)


def _box(games, extra=()):
    adv, log = [], []
    for _, g in games.iterrows():
        for team in (g.home_team, g.away_team):
            for j in range(6):
                pid = f"{team[0]}{j}"
                adv.append({"game_id": g.game_id, "player_id": pid, "team": team,
                            "is_starter": int(j < 5), "played": True, "minutes_exact": 40.0,
                            "possessions": 83.0, "fouls": 2.0})
                log.append({"game_id": g.game_id, "player_id": pid, "points": 18.0 + j,
                            "offensive_reb": 1.0, "defensive_reb": 4.0, "assists": 3.0,
                            "steals": 1.0, "blocks": 0.5, "turnovers": 2.0, "fg_att": 14.0,
                            "fg3_att": 5.0, "ft_att": 4.0})
    for r in extra:
        adv.append({**adv[0], **r})
    return pd.DataFrame(adv), pd.DataFrame(log)


def _inj(rows=()):
    cols = ["report_ts", "game_id", "team", "player_id", "player_name", "status", "season"]
    return pd.DataFrame(list(rows), columns=cols)


def _world(games=None, inj=None, extra=()):
    g = _games() if games is None else games
    adv, log = _box(g, extra)
    ina = pd.DataFrame(columns=["game_id", "team", "player_id"])
    return P.build_world(g, adv, log, ina, _inj() if inj is None else inj)


def _state(w, **kw):
    hp = {"hl": 90.0, "k": 300.0, "hl_lg": 30.0, "min_hl": 3.0, "hl_pace": 60.0, **kw}
    return P.build_state(w, hp)


# ── the cells section 6.3 lists ─────────────────────────────────────────────

def test_section_6_3_lists_exactly_228_cells():
    assert {f: len(P.cell_specs(f)) for f in P.FAMILIES} == {"F1": 144, "F1b": 48, "F5": 36}
    assert len(P.cell_specs()) == 228
    assert P.FAMILIES["F1"]["cuts"] == (0.0, 0.01, 0.02, 0.03, 0.05, 0.08)
    assert P.FAMILIES["F1b"]["points"] == ("A", "B", "C") and P.FAMILIES["F5"]["points"] == ("B", "C", "D")


def test_every_family_emits_exactly_its_cells_through_the_harness(monkeypatch):
    real = H.boot
    monkeypatch.setattr(H, "boot", lambda b, n=H.N_BOOT, seed=H.SEED: real(b, n=20, seed=seed))
    monkeypatch.setattr(H, "P_REFINE_BELOW", -1.0)
    got = P.synthetic_cells_check(n_placebo=1, seasons=(2021, 2022, 2026), per_season=4)
    assert got == {"F1": 144, "F1b": 48, "F5": 36}


# ── leak guards ─────────────────────────────────────────────────────────────

def test_a_report_counts_only_30_minutes_after_its_printed_time():
    T = pd.Timestamp("2024-01-15T23:00:00Z")
    inj = _inj([
        {"report_ts": T - pd.Timedelta(minutes=40), "game_id": "G", "team": "AAA", "player_id": "1",
         "player_name": "a", "status": "Questionable", "season": 2024},
        {"report_ts": T - pd.Timedelta(minutes=20), "game_id": "G", "team": "AAA", "player_id": "1",
         "player_name": "a", "status": "Out", "season": 2024},
    ])
    got = P.injury_at(inj, pd.DataFrame({"game_id": ["G"], "T": [T]}))
    assert got["status"].tolist() == ["Questionable"]
    assert bool(P.report_known(inj, pd.DataFrame({"game_id": ["G"], "T": [T - pd.Timedelta(minutes=65)]})).iloc[0]) is False


def test_the_latest_submitted_report_wins_and_not_yet_submitted_is_skipped():
    T = pd.Timestamp("2024-01-15T23:00:00Z")
    base = {"game_id": "G", "team": "AAA", "player_name": "a", "season": 2024}
    inj = _inj([
        {**base, "report_ts": T - pd.Timedelta(hours=5), "player_id": "1", "status": "Questionable"},
        {**base, "report_ts": T - pd.Timedelta(hours=2), "player_id": None, "status": "NOT YET SUBMITTED"},
    ])
    t = pd.DataFrame({"game_id": ["G"], "T": [T]})
    assert P.injury_at(inj, t)["status"].tolist() == ["Questionable"]
    inj2 = pd.concat([inj, _inj([{**base, "report_ts": T - pd.Timedelta(hours=1), "player_id": "1",
                                  "status": "Out"}])], ignore_index=True)
    assert P.injury_at(inj2, t)["status"].tolist() == ["Out"]


def test_box_inputs_come_only_from_games_on_earlier_dates():
    w = _world()
    st = _state(w)
    first = w.games.sort_values("day").iloc[0]
    q = pd.DataFrame({"player_id": ["A0", "A0"], "day": [first.day, first.day + 1], "season": 2020})
    r = st.rates.asof(q)
    # on the day of his first game nothing is known; the next day that game is
    assert r["poss"].iloc[0] == 0 and r["poss"].iloc[1] > 0
    x = P.player_x(st, q)
    assert x["prior_share"].iloc[0] == pytest.approx(1.0)
    assert np.isnan(x["last_played"].iloc[0]) and x["m"].iloc[0] == 0.0


def test_a_game_gets_no_projection_while_a_previous_date_game_could_still_be_running():
    w = _world()
    g = w.games.sort_values("day").iloc[[1]].copy()
    prev_tip = w.games.sort_values("day").iloc[0]["tip"]
    g["T"] = prev_tip + pd.Timedelta(hours=3)          # the earlier game is not final yet
    assert P.box_guard(w, g).tolist() == [False]
    g["T"] = prev_tip + pd.Timedelta(hours=5)
    assert P.box_guard(w, g).tolist() == [True]


def test_p_plays_is_fit_only_on_seasons_before_the_one_it_prices():
    obs = pd.DataFrame({"season": [2020] * 4 + [2021] * 4, "bucket": "near",
                        "status": "Questionable", "role": "core",
                        "played": [True, True, True, False, False, False, False, False]})
    play = P.fit_play(obs, 2021)
    assert play["seasons"] == [2020]
    assert play["listed"][("Questionable", "near")] == pytest.approx((3 + 1) / (4 + 2))


def test_the_closing_line_move_is_fit_only_on_earlier_priced_seasons():
    data = P.synthetic_market(per_season=4)
    sig = {(s, m): 12.0 for s in data.games["season"].unique() for m in ("spreads", "totals")}
    inputs = {}
    for p in ("A", "B", "C"):
        t, off = H.point_offers(data, p)
        vis = H.visible(data.quotes, t)
        g = data.games
        proj = pd.DataFrame({"game_id": g["game_id"], "season": g["season"],
                             "margin": np.linspace(-8, 8, len(g)), "total": np.linspace(210, 230, len(g))})
        inputs[p] = P.PointInputs(p, t, off, vis, H.fair_offers(off, H.market_fair(vis, sig)), proj)
    old = P.MIN_FIT_ROWS
    P.MIN_FIT_ROWS = 2
    try:
        c1 = P.f1b_coefficients(data, inputs, [2022, 2023])
        later = inputs["A"].proj["season"] >= 2022
        inputs["A"].proj.loc[later, "margin"] += 50.0      # change 2021-22 onward only
        c2 = P.f1b_coefficients(data, inputs, [2022, 2023])
    finally:
        P.MIN_FIT_ROWS = old
    assert c1["A"][2022]["spreads"] == pytest.approx(c2["A"][2022]["spreads"])
    assert c1["A"][2023]["spreads"] != pytest.approx(c2["A"][2023]["spreads"])
    assert c1["A"].get(2021) is None


def test_a_seasons_hyperparameters_are_fit_and_scored_on_earlier_seasons():
    assert P.hyper_seasons(2026) == ([2019, 2020, 2021, 2022, 2023, 2024], 2025)
    assert P.hyper_seasons(2022) == ([2019, 2020], 2021)
    assert P.hyper_seasons(2021) == ([2019], 2020) == P.hyper_seasons(2020)
    for s in range(2021, 2027):
        fit, scored = P.hyper_seasons(s)
        assert scored < s and max(fit) < scored


def test_calibration_and_the_f5_model_see_only_earlier_seasons():
    refs = {2020: "r20", 2021: "r21", 2022: "r22"}
    assert P.prior_refs(refs, 2022) == ["r20", "r21"]
    assert P.prior_refs(refs, 2020) == []


def test_the_segment_ratings_use_only_games_before_the_refit_date():
    s = pd.DataFrame({"day": [10, 11, 12, 13]})
    assert P.segments_before(s, 12)["day"].tolist() == [10, 11]


def test_the_point_differential_baseline_reads_only_earlier_games():
    w = _world()
    base = P.pd_baseline(w, w.games[w.games["season"] == 2021])
    g = w.games[w.games["season"] == 2021].sort_values("day")
    first = base.set_index("game_id").loc[g.iloc[0].game_id]
    # the first game of 2021 knows only 2020: AAA's mean 2020 margin
    t = w.tg[(w.tg["season"] == 2020)]
    pd_prev = t.assign(mg=t["pts"] - t["opp_pts"]).groupby("team")["mg"].mean()
    home = g.iloc[0].home_team
    assert first["pd_h"] == pytest.approx(pd_prev[home])
    second = base.set_index("game_id").loc[g.iloc[1].game_id]
    m0 = g.iloc[0].home_score - g.iloc[0].away_score
    sign = 1 if g.iloc[1].home_team == home else -1
    assert second["pd_h"] == pytest.approx(sign * m0)


# ── feature rules ───────────────────────────────────────────────────────────

def test_time_decay_halves_a_game_one_half_life_old():
    hist = pd.DataFrame({"k": ["p", "p"], "day": [0, 10], "v": [1.0, 1.0]})
    e = P.EW(hist, "k", ["v"], hl=10.0)
    got = e.asof(pd.DataFrame({"k": ["p", "p", "q"], "day": [10, 20, 20]}))["v"].tolist()
    assert got == pytest.approx([0.5, 0.25 + 0.5, 0.0])


def test_rates_shrink_toward_the_league_by_k_pseudo_possessions():
    w = _world()
    st = _state(w, k=83.0)
    first = w.games.sort_values("day").iloc[0]
    q = pd.DataFrame({"player_id": ["A0"], "day": [first.day + 1], "season": [2020]})
    x = P.player_x(st, q)
    lg = st.lg_rates[2020]["pts"]
    f = 0.5 ** (1.0 / 90.0)                       # the game is one day old
    # one game of 83 possessions against 83 pseudo-possessions: about halfway
    assert x["pts"].iloc[0] == pytest.approx(100.0 * (18.0 * f + 83.0 * lg / 100.0) / (83.0 * f + 83.0))
    assert x["prior_share"].iloc[0] == pytest.approx(83.0 / (83.0 * f + 83.0))


def test_out_is_zero_minutes_and_listed_players_take_their_fitted_rate():
    play = {"listed": {("Questionable", "near"): 0.6}, "listed_status": {"Doubtful": 0.2},
            "unlisted": {("core", "far"): 0.97}, "unlisted_all": 0.9}
    got = P.play_prob(play, ["Out", "Questionable", "Doubtful", "unlisted", "unlisted"],
                      ["core", "core", "core", "core", "bench"], ["near", "near", "mid", "far", "far"])
    assert got.tolist() == pytest.approx([0.0, 0.6, 0.2, 0.97, 0.9])


def test_minutes_are_reallocated_to_240_with_a_cap():
    df = pd.DataFrame({"g": ["x"] * 6 + ["y"] * 2,
                       "e": [40.0, 30.0, 30.0, 20.0, 20.0, 20.0, 100.0, 20.0]})
    e = P.reallocate(df, "g", "e", cap=44.0)
    # x: scaled by 1.5, three players stop at the cap, the rest share what is left
    assert e[:6].tolist() == pytest.approx([44.0, 44.0, 44.0, 36.0, 36.0, 36.0])
    # y: two players cannot fill 240; each stops at the cap
    assert e[6:].tolist() == pytest.approx([44.0, 44.0])


def test_the_roster_is_the_last_ten_games_and_follows_a_trade():
    g = _games(n_per_season=14, seasons=(2020,))
    order = g.sort_values("game_date")
    # A9 played only in AAA's first game (14 games back), A8 only in its 6th (9 back)
    w = _world(games=g, extra=[{"game_id": order.iloc[0].game_id, "player_id": "A9", "team": "AAA"},
                               {"game_id": order.iloc[5].game_id, "player_id": "A8", "team": "AAA"}])
    last = order.iloc[-1]
    gm = pd.DataFrame([last]).assign(T=last.tip - pd.Timedelta(hours=1))
    gm["day"] = P.to_day(gm["game_date"])
    ros = P.roster(w, P.sides_of(gm))
    assert set(ros.loc[ros["team"] == "AAA", "player_id"]) == {f"A{j}" for j in range(6)} | {"A8"}
    # A5 last appears for BBB (a trade): he leaves AAA's roster and joins BBB's
    trade = g.sort_values("game_date").iloc[-2]
    w2 = _world(games=g, extra=[{"game_id": trade.game_id, "player_id": "A5", "team": "BBB"}])
    w2.panel = w2.panel[~((w2.panel["player_id"] == "A5") & (w2.panel["team"] == "AAA")
                          & (w2.panel["game_id"] == trade.game_id))]
    ros2 = P.roster(w2, P.sides_of(gm))
    assert "A5" not in set(ros2.loc[ros2["team"] == "AAA", "player_id"])
    assert "A5" in set(ros2.loc[ros2["team"] == "BBB", "player_id"])


def test_a_back_to_back_is_read_from_the_schedule():
    g = _games(n_per_season=3, seasons=(2020,))
    g.loc[1, "game_date"] = "2019-12-02"                  # the day after game 0
    g.loc[1, "tip"] = pd.Timestamp("2019-12-03T00:00:00Z")
    w = _world(games=g)
    b = w.tg.set_index(["game_id", "team"])["b2b"]
    assert b[("G2020_1", "AAA")] == 1.0 and b[("G2020_1", "BBB")] == 1.0
    assert b[("G2020_0", "AAA")] == 0.0 and b[("G2020_2", "AAA")] == 0.0


def test_lead_buckets_and_roles():
    assert P.lead_bucket([9.0, 6.0, 4.5, 3.0, 1.0]).tolist() == ["far", "mid", "mid", "near", "near"]
    assert P.role_of([30.0, 24.0, 20.0, 5.0]).tolist() == ["core", "core", "rotation", "bench"]


def test_f5_terms_tier_starters_questionable_and_first_game_back():
    seq = pd.DataFrame({"team": "AAA", "k": range(6), "game_id": [f"g{i}" for i in range(6)],
                        "day": range(100, 106)})
    w = P.World(games=pd.DataFrame(), panel=pd.DataFrame(), inj=pd.DataFrame(), seq=seq)
    av = pd.DataFrame({
        "game_id": "g5", "team": "AAA", "player_id": ["s1", "s2", "s3", "b1", "r1"],
        "m": [36.0, 34.0, 30.0, 8.0, 24.0], "o": [5.0, 3.0, 1.0, 9.0, 0.0], "d": [1.0, 1.0, 0.0, 0.0, 0.0],
        "p_play": [0.0, 0.5, 0.5, 1.0, 1.0], "starter": [1.0, 1.0, 1.0, 0.0, 0.2],
        "status": ["Out", "Questionable", "Questionable", "unlisted", "Probable"],
        "last_played": [104.0, 104.0, 104.0, 104.0, 101.0]})
    f = P.f5_player_terms(w, av).set_index("player_id")
    # tier 1 = the two best rotation players by rating (s1, s2); b1 plays 8 minutes: tier 3
    assert f.loc["s1", "miss_t1"] == pytest.approx(36.0 / 48.0)
    assert f.loc["s2", "miss_t1"] == pytest.approx(0.5 * 34.0 / 48.0) and f.loc["s2", "miss_t2"] == 0.0
    assert f.loc["s3", "miss_t2"] == pytest.approx(0.5 * 30.0 / 48.0)
    assert f.loc["b1", "miss_t1"] == 0.0 and f.loc["b1", "miss_t3"] == 0.0
    assert f["starters_out"].sum() == pytest.approx(1.0 + 0.5 + 0.5)
    assert f.loc["s3", "q_exposure"] == pytest.approx(30.0 / 48.0) and f.loc["s1", "q_exposure"] == 0.0
    # r1 last played at k = 1 and has missed k = 2, 3, 4: back tonight
    assert f.loc["r1", "first_back"] == pytest.approx(24.0 / 48.0)
    assert f.loc["s2", "first_back"] == 0.0


# ── adjusted plus-minus ─────────────────────────────────────────────────────

def _segments(n=4000, P_=12, seed=3):
    rng = np.random.default_rng(seed)
    o_true = rng.normal(0, 3, P_)
    d_true = rng.normal(0, 2, P_)
    home = np.array([rng.choice(P_ // 2, 5, replace=False) for _ in range(n)])
    away = np.array([P_ // 2 + rng.choice(P_ // 2, 5, replace=False) for _ in range(n)])
    yh = o_true[home].sum(1) - d_true[away].sum(1) + rng.normal(0, 1, n)
    ya = o_true[away].sum(1) - d_true[home].sum(1) + rng.normal(0, 1, n)
    return home, away, yh, ya, np.full(n, 10.0), o_true, d_true


def test_the_segment_ridge_returns_its_prior_under_a_huge_penalty_and_the_truth_under_a_small_one():
    home, away, yh, ya, wt, o_true, d_true = _segments()
    prior_o, prior_d = np.full(len(o_true), 1.5), np.full(len(d_true), -0.5)
    o, d = P.ridge_with_prior(home, away, yh, ya, wt, wt, prior_o, prior_d, lam=1e12)
    assert o == pytest.approx(prior_o, abs=1e-6) and d == pytest.approx(prior_d, abs=1e-6)
    o, d = P.ridge_with_prior(home, away, yh, ya, wt, wt, o_true + 0.0, d_true + 0.0, lam=1e-3)
    assert np.corrcoef(o, o_true)[0, 1] > 0.99 and np.corrcoef(d, d_true)[0, 1] > 0.99


def test_the_segment_loader_reads_the_ingestor_schema_and_names_what_is_missing():
    games = pd.DataFrame({"game_id": ["G1"], "season": [2024], "day": [19000]})
    s = pd.DataFrame({"game_id": ["G1", "G1", "G1", "X"],
                      "home_player_ids": [["1", "2", "3", "4", "5"]] * 3 + [["1", "2", "3", "4", "5"]],
                      "away_player_ids": [["6", "7", "8", "9", "10"], ["6", "7", "8", "9", "10"],
                                          ["6", "7", "8", "9"], ["6", "7", "8", "9", "10"]],
                      "home_pts": [5, 2, 1, 3], "away_pts": [3, 2, 0, 1], "home_poss": [4, 2, 1, 2],
                      "away_poss": [4, 3, 1, 2], "garbage_time": [False, True, False, False]})
    out = P.normalize_stints(s, games)
    # garbage time dropped, a four-man side dropped, a game outside the table dropped
    assert len(out) == 1 and out.loc[0, "h0"] == "1" and out.loc[0, "a4"] == "10"
    assert out.loc[0, "season"] == 2024 and out.loc[0, "day"] == 19000
    with pytest.raises(ValueError, match="home_poss"):
        P.normalize_stints(s.drop(columns=["home_poss", "away_poss"]), games)


# Supabase `nba_stints`, every column in table order (information_schema,
# 2026-10-17; the writer is data/ingestors/nba_pbp.py on branch nba-pbp-stints)
REAL_STINT_COLS = (
    "espn_game_id", "stint_no", "game_id", "season", "season_type", "period", "start_s", "end_s",
    "duration_s", "home_team", "away_team", "home_espn_ids", "away_espn_ids", "home_player_ids",
    "away_player_ids", "n_home", "n_away", "home_pts", "away_pts", "home_poss", "away_poss",
    "home_fga", "home_fg3a", "home_fg3m", "home_fta", "home_ftm", "home_oreb", "home_tov",
    "away_fga", "away_fg3a", "away_fg3m", "away_fta", "away_ftm", "away_oreb", "away_tov",
    "home_score_start", "away_score_start", "garbage_time", "derivation")


def test_the_segment_loader_reads_the_real_table_after_a_parquet_round_trip(tmp_path):
    games = pd.DataFrame({"game_id": ["G1"], "season": [2022], "day": [18950]})
    five_h = ["201939", "203110", "1626172", "1628398", "espn:4432158"]   # one unmapped player
    five_a = ["2544", "203076", "1629060", "1630559", "1627936"]
    base = {c: 0 for c in REAL_STINT_COLS}
    base.update({"espn_game_id": 401360000, "game_id": "G1", "season": 2022, "home_team": "GSW",
                 "away_team": "LAL", "home_espn_ids": [1, 2, 3, 4, 5], "away_espn_ids": [6, 7, 8, 9, 10],
                 "home_player_ids": five_h, "away_player_ids": five_a, "n_home": 5, "n_away": 5,
                 "home_pts": 7, "away_pts": 4, "home_poss": 4, "away_poss": 4,
                 "garbage_time": False, "derivation": "stints-v1", "season_type": 2})
    rows = [dict(base, stint_no=1),
            dict(base, stint_no=2, season_type=3),                                  # postseason
            dict(base, stint_no=3, n_away=4, away_player_ids=five_a[:4]),           # four on the floor
            dict(base, stint_no=4, garbage_time=True)]
    pd.DataFrame(rows, columns=list(REAL_STINT_COLS)).to_parquet(tmp_path / "s.parquet")
    s = pd.read_parquet(tmp_path / "s.parquet")
    assert isinstance(s.loc[0, "home_player_ids"], np.ndarray)      # lists come back as arrays
    out = P.normalize_stints(s, games)
    assert out["home_pts"].tolist() == [7.0] and out["home_poss"].tolist() == [4.0]
    assert [out.loc[0, f"h{j}"] for j in range(5)] == five_h
    assert [out.loc[0, f"a{j}"] for j in range(5)] == five_a
    # a postseason row is dropped by its season_type even when its game id is a games row
    assert len(P.normalize_stints(s[s["stint_no"] == 2], games)) == 0


def _segment_rows(games, per_game=8, seed=5):
    rng = np.random.default_rng(seed)
    rows = []
    for _, g in games.iterrows():
        for k in range(per_game):
            hs = [f"{g.home_team[0]}{j}" for j in range(6) if j != k % 6]
            as_ = [f"{g.away_team[0]}{j}" for j in range(6) if j != (k + 3) % 6]
            hp = int(rng.integers(8, 14))
            rows.append({"game_id": g.game_id, "home_player_ids": hs, "away_player_ids": as_,
                         "home_pts": int(rng.integers(5, 20)), "away_pts": int(rng.integers(5, 20)),
                         "home_poss": hp, "away_poss": hp, "garbage_time": False})
    return pd.DataFrame(rows)


def _rapm_inputs(hl):
    """Real segments through the real loader, targets and box prior: one season."""
    g = _games(n_per_season=30)
    adv, log = _box(g)
    ina = pd.DataFrame(columns=["game_id", "team", "player_id"])
    w = P.build_world(g, adv, log, ina, _inj(), stints=_segment_rows(g))
    st = _state(w, hl=hl)
    box = P.fit_box(w, st, [2020])
    s = P.stint_targets(st, box, w.stints[w.stints["season"] == 2021])
    day = int(w.games.loc[w.games["season"] == 2021, "day"].max()) + 1
    return st, box, s, day


def test_the_chosen_penalty_reaches_the_segment_ridge():
    # review fix 1: the cross-validated penalty was overwritten by the decay
    # rate, so any two penalties gave the same deviations
    st, box, s, day = _rapm_inputs(365.0)
    lo = P.rapm_solve(st, box, s, day, 2021, 250.0)
    hi = P.rapm_solve(st, box, s, day, 2021, 8000.0)
    assert not np.allclose(lo["do"], hi["do"])
    # the larger penalty holds every player closer to his box rating
    assert np.abs(hi[["do", "dd"]].to_numpy()).max() < np.abs(lo[["do", "dd"]].to_numpy()).max()


def test_no_time_decay_is_not_a_singular_solve():
    # with no decay the overwritten penalty was 0: LinAlgError, Singular matrix
    st, box, s, day = _rapm_inputs(np.inf)
    dev = P.rapm_solve(st, box, s, day, 2021, 2000.0)
    v = dev[["do", "dd"]].to_numpy()
    assert np.isfinite(v).all() and np.abs(v).max() < 50.0


def test_segment_ratings_flow_into_the_projection_and_move_it():
    g = _games(n_per_season=30)
    adv, log = _box(g)
    ina = pd.DataFrame(columns=["game_id", "team", "player_id"])
    w = P.build_world(g, adv, log, ina, _inj(), stints=_segment_rows(g))
    st = _state(w)
    box = P.fit_box(w, st, [2020])
    table, info = P.rapm_table(w, st, box, 2021)
    assert table is not None and len(table) and info["refits"] > 0
    first_2021 = int(w.games.loc[w.games["season"] == 2021, "day"].min())
    assert table["refit_day"].min() >= first_2021
    play = P.fit_play(pd.DataFrame(columns=["season", "bucket", "status", "role", "played"]), 2021)
    gm = w.games[w.games["season"] == 2021].assign(T=lambda d: d["tip"] - pd.Timedelta(hours=1))
    plain = P.project(w, st, P.Model(season=2021, box=box, play=play, cap=40.0), gm)
    seg = P.project(w, st, P.Model(season=2021, box=box, play=play, cap=40.0, rapm=table), gm)
    assert np.isfinite(seg["raw_margin"]).all() and np.isfinite(plain["raw_margin"]).all()
    assert not np.allclose(seg["raw_margin"], plain["raw_margin"])


def test_the_segment_file_is_read_from_the_cache_when_present(tmp_path):
    g = _games(n_per_season=2, seasons=(2025,))
    g["commence_time"] = g["tip"].astype(str)
    adv, log = _box(g)
    g.to_parquet(tmp_path / "nba_games.parquet")
    adv.assign(game_type="regular", season=2025).to_parquet(tmp_path / "nba_player_game_adv.parquet")
    log.assign(season=2025).to_parquet(tmp_path / "nba_player_game_log.parquet")
    pd.DataFrame({"game_id": ["G2025_0"], "team": ["AAA"], "player_id": ["A0"], "game_type": ["regular"],
                  "season": [2025]}).to_parquet(tmp_path / "nba_game_inactives.parquet")
    _inj().astype({"season": "int64"}).to_parquet(tmp_path / "nba_injury_report.parquet")
    assert P.load_world(tmp_path, 2025).stints is None
    _segment_rows(g).assign(season=2025).to_parquet(tmp_path / P.STINTS_FILE)
    w = P.load_world(tmp_path, 2025)
    assert w.stints is not None and len(w.stints) == 16 and set(w.stints["season"]) == {2025}


# ── pricing and the rule families ───────────────────────────────────────────

def _dist(sd, n=1000, seed=11, label=""):
    return H.ResidDist(np.random.default_rng(seed).normal(0.0, sd, n), label)


def test_the_moneyline_comes_from_the_margin_distribution_with_ties_removed():
    proj = pd.DataFrame({"game_id": ["a", "b"], "season": 2024, "margin": [0.0, 4.0], "total": 220.0})
    dsp, dto = _dist(12.0), _dist(18.0, seed=12)
    f = P.fair_frame(proj, {(2024, "spreads"): dsp, (2024, "totals"): dto})
    ph = f[f["market"] == "h2h"].set_index("game_id")["p_home"]
    w0, _, l0 = dsp.probs(0.0, 0.0)
    assert ph["a"] == pytest.approx(float(w0 / (w0 + l0)))
    w, _, l = dsp.probs(4.0, 0.0)
    assert ph["b"] == pytest.approx(float(w / (w + l))) and ph["b"] > 0.6
    sp = f[f["market"] == "spreads"].set_index("game_id")
    assert sp.loc["b", "mu"] == 4.0 and sp.loc["b", "sigma"] is dsp


def test_f1_is_priced_through_the_projections_own_error_not_the_markets():
    # review fix 2: the first build priced F1 with the spread of results around
    # Pinnacle's close; the projection's own error is wider
    data = P.synthetic_market(per_season=4, seasons=(2022,))
    market = {(2022, m): 6.0 for m in ("spreads", "totals")}
    t, off = H.point_offers(data, "C")
    vis = H.visible(data.quotes, t)
    neutral = H.fair_offers(off, H.market_fair(vis, market))
    g = data.games
    proj = pd.DataFrame({"game_id": g["game_id"], "season": g["season"], "margin": 9.0, "total": 230.0})
    own = {(2022, "spreads"): _dist(14.0), (2022, "totals"): _dist(19.0, seed=12)}
    pi = P.PointInputs("C", t, off, vis, neutral, proj, own)
    cand, _ = P.family_frames("F1", pi, g, None, n_placebo=0)
    sp = cand[(cand["market"] == "spreads") & (cand["side"] == "home")]
    w, push, _ = own[(2022, "spreads")].probs(np.full(len(sp), 9.0), -sp["line"].to_numpy())
    assert np.allclose(sp["p_win"], w) and np.allclose(sp["p_push"], push)
    # the market's narrower spread would price the same home number higher
    w_mkt, _, _ = H.probs_at(np.full(len(sp), 9.0), np.full(len(sp), 6.0), -sp["line"].to_numpy())
    assert (w_mkt > sp["p_win"].to_numpy() + 0.05).all()
    with pytest.raises(ValueError, match="own error distribution"):
        P.family_frames("F1", P.PointInputs("C", t, off, vis, neutral, proj), g, None, n_placebo=0)


def test_the_projections_error_distribution_is_read_from_earlier_seasons_only():
    rng = np.random.default_rng(4)
    games, proj = [], []
    for s, sd in ((2021, 10.0), (2022, 30.0)):
        for i in range(400):
            hs, as_ = int(rng.integers(90, 130)), int(rng.integers(90, 130))
            games.append({"game_id": f"{s}_{i}", "home_score": hs, "away_score": as_})
            proj.append({"game_id": f"{s}_{i}", "season": s, "margin": hs - as_ - rng.normal(0, sd),
                         "total": hs + as_ - rng.normal(0, sd)})
    games, proj = pd.DataFrame(games), pd.DataFrame(proj)
    d = P.projection_dist(games, proj)
    # 2022 is priced on 2021's residuals (result minus projection), never its own
    assert d[(2022, "spreads")].n == 400 and d[(2022, "spreads")].sd == pytest.approx(10.0, rel=0.1)
    assert "prior" in d[(2022, "totals")].label
    r = P.projection_resid(games, proj)
    x = proj.iloc[0]
    g0 = games.iloc[0]
    assert r.loc[0, "resid"] == pytest.approx(g0.home_score - g0.away_score - x.margin)
    # 2021 has no earlier season: its own rows, which the label says
    assert "own season" in d[(2021, "spreads")].label


def test_a_biased_earlier_season_still_prices_around_the_projection():
    # re-review, third amendment: 2021-22's F1 price is built from 2020-21's
    # misses alone, which averaged about -1 (margin) and -2 (total). Uncentred,
    # that average moved every price a second time. Here the earlier season's
    # results sit 5 points above the projection on average: the next season's
    # price must keep the spread of those misses and drop their average.
    rng = np.random.default_rng(8)
    games, proj = [], []
    for s in (2021, 2022):
        for i in range(600):
            hs, as_ = int(rng.integers(95, 126)), int(rng.integers(95, 126))
            games.append({"game_id": f"{s}_{i}", "home_score": hs, "away_score": as_})
            proj.append({"game_id": f"{s}_{i}", "season": s,
                         "margin": hs - as_ - 5.0 - rng.normal(0, 13), "total": hs + as_ - 5.0 - rng.normal(0, 18)})
    games, proj = pd.DataFrame(games), pd.DataFrame(proj)
    r = P.projection_resid(games, proj)
    prior = r[r["season"] == 2021]
    bias = prior.groupby("market")["resid"].mean()
    assert bias["spreads"] == pytest.approx(5.0, abs=1.5) and bias["totals"] == pytest.approx(5.0, abs=1.5)
    d = P.projection_dist(games, proj)
    for m, mu in (("spreads", 3.0), ("totals", 220.0)):
        dist = d[(2022, m)]
        assert "prior" in dist.label
        w, push, _ = dist.probs(mu, mu + 0.5)
        res = prior.loc[prior["market"] == m, "resid"].to_numpy()
        w0, _, _ = H.ResidDist(res - res.mean()).probs(mu, mu + 0.5)
        # half a point above the centre: a little under one half, no push
        assert float(w) == pytest.approx(float(w0), abs=1e-9) and abs(float(w) - 0.5) < 0.03
        assert float(push) == 0.0
    # and through the moneyline: a level projection is close to a coin flip
    f = P.fair_frame(pd.DataFrame({"game_id": ["x"], "season": [2022], "margin": [0.0], "total": [220.0]}), d)
    assert abs(float(f.loc[f["market"] == "h2h", "p_home"].iloc[0]) - 0.5) < 0.03


def _neutral(rows):
    return pd.DataFrame([{"game_id": "G", "market": m, "side": s, "line": l, "book": "fanduel",
                          "price": -110.0, "p_win": 0.5, "p_push": 0.0, "ev": -0.05}
                         for m, s, l in rows])


def _cons(spread, total, game="G"):
    return pd.DataFrame({"game_id": game, "market": ["spreads", "totals"], "cons": [spread, total]})


def test_the_f5_gap_reads_the_home_number():
    n = _neutral([("spreads", "home", -6.5), ("spreads", "away", -6.5),
                  ("totals", "over", 220.5), ("totals", "under", 220.5)])
    mu = pd.DataFrame({"game_id": "G", "market": ["spreads", "totals"], "mu": [9.0, 225.0]})
    g = P.gap_strength(n, mu, _cons(-6.5, 220.5))["strength"].tolist()
    assert g == pytest.approx([2.5, -2.5, 4.5, -4.5])


def test_the_f5_gap_is_measured_against_the_consensus_not_each_books_number():
    # third amendment: against each book's own number, a soft book hanging
    # home -5.5 against a -6.5 consensus scored a point more for home with the
    # projection unchanged (the refuted outlier mechanism)
    n = _neutral([("spreads", "home", -6.5), ("spreads", "home", -5.5), ("spreads", "away", -7.5),
                  ("totals", "over", 218.5), ("totals", "under", 222.5)])
    mu = pd.DataFrame({"game_id": "G", "market": ["spreads", "totals"], "mu": [9.0, 225.0]})
    s = P.gap_strength(n, mu, _cons(-6.5, 220.5))["strength"].tolist()
    assert s == pytest.approx([2.5, 2.5, -2.5, 4.5, -4.5])
    # a game with no consensus number has no gap, so it is outside the population
    assert P.gap_strength(n, mu, _cons(-6.5, 220.5).iloc[0:0])["strength"].isna().all()


def _vis_rows(rows):
    return pd.DataFrame([{"game_id": g, "market": m, "book": b, "line": l, "coherent": c}
                         for g, m, b, l, c in rows])


def test_the_consensus_number_is_pinnacles_else_the_deciding_books_median():
    v = _vis_rows([
        ("G1", "spreads", "pinnacle", -4.0, True), ("G1", "spreads", "fanduel", -5.0, True),
        ("G1", "spreads", "draftkings", -5.0, True), ("G1", "spreads", "betmgm", -6.0, True),
        ("G1", "totals", "pinnacle", 221.0, False),              # incoherent: not a number to read
        ("G1", "totals", "fanduel", 219.0, True), ("G1", "totals", "betmgm", 220.0, True),
        ("G1", "totals", "bovada", 230.0, True),                 # never a deciding book
        ("G2", "spreads", "fanduel", 3.0, True), ("G2", "spreads", "draftkings", 2.0, True),
        ("G2", "h2h", "pinnacle", np.nan, True)])
    c = P.consensus(v).set_index(["game_id", "market"])["cons"]
    assert c.to_dict() == {("G1", "spreads"): -4.0, ("G1", "totals"): 219.5, ("G2", "spreads"): 2.5}
    ref = P.consensus(v).set_index(["game_id", "market"])["ref"]
    assert ref.to_dict() == {("G1", "spreads"): "pinnacle", ("G1", "totals"): "median",
                             ("G2", "spreads"): "median"}


def test_f5_and_f1b_read_the_consensus_number_at_t_through_the_lab():
    data = P.synthetic_market(per_season=4, seasons=(2022,))
    sig = {(2022, m): 12.0 for m in ("spreads", "totals")}
    t, off = H.point_offers(data, "C")
    vis = H.visible(data.quotes, t)
    neutral = H.fair_offers(off, H.market_fair(vis, sig))
    g = data.games
    proj = pd.DataFrame({"game_id": g["game_id"], "season": g["season"], "margin": 7.0, "total": 225.0,
                         "margin5": 7.0, "total5": 225.0})
    pi = P.PointInputs("C", t, off, vis, neutral, proj)
    pin = vis[vis["book"] == "pinnacle"].set_index(["game_id", "market"])["line"]
    med = vis[vis["book"].isin(H.BETTABLE)].groupby(["game_id", "market"])["line"].median()
    assert (pin.reindex(med.index) != med).any()          # the fixture tells Pinnacle from the median
    cand, _ = P.family_frames("F5", pi, g, None, n_placebo=0)
    p_line = pin.reindex(pd.MultiIndex.from_frame(cand[["game_id", "market"]])).to_numpy()
    a_gap = np.where(cand["market"] == "spreads", 7.0 + p_line, 225.0 - p_line)
    assert np.allclose(cand["strength"], np.where(cand["side"].isin(["home", "over"]), a_gap, -a_gap))
    # every book's offer on a side carries the same gap
    assert (cand.groupby(["game_id", "market", "side"])["strength"].nunique() == 1).all()
    # F1b: the predicted move a + b (projection's number - Pinnacle's number at T)
    coef = {2022: {"spreads": (0.0, 0.5), "totals": (0.0, 0.5)}}
    c1, _ = P.family_frames("F1b", pi, g, coef, n_placebo=0)
    p1 = pin.reindex(pd.MultiIndex.from_frame(c1[["game_id", "market"]])).to_numpy()
    move = 0.5 * (np.where(c1["market"] == "spreads", -7.0, 225.0) - p1)
    fav_a = np.where(c1["market"] == "spreads", -move, move)
    assert np.allclose(c1["strength"], np.where(c1["side"].isin(["home", "over"]), fav_a, -fav_a))


def test_f1b_strength_is_the_predicted_move_in_the_sides_favour():
    n = _neutral([("spreads", "home", -3.0), ("spreads", "away", -3.0),
                  ("totals", "over", 220.0), ("totals", "under", 220.0)])
    mu = pd.DataFrame({"game_id": "G", "market": ["spreads", "totals"], "mu": [5.0, 224.0]})
    dec = pd.DataFrame({"game_id": "G", "market": ["spreads", "totals"], "cons": [-3.0, 220.0]})
    # the projection says home by 5 (home number -5): half the gap closes, so
    # the home number is predicted to fall 1 (home +1); the total 224: half
    # closes, a rise of 2 (over +2)
    s = P.move_strength(n, mu, dec, {"spreads": (0.0, 0.5), "totals": (0.0, 0.5)})["strength"].tolist()
    assert s == pytest.approx([1.0, -1.0, 2.0, -2.0])
    none = P.move_strength(n, mu, dec, {"spreads": None})["strength"]
    assert none.isna().all()


def test_f1b_does_not_score_a_books_number_off_the_consensus():
    # review fix 3: the first build scored (offered number - predicted close),
    # so a soft book hanging home -2 against a -3 consensus scored +1 for home
    # with no move predicted at all (the refuted outlier mechanism)
    n = _neutral([("spreads", "home", -3.0), ("spreads", "home", -2.0), ("spreads", "away", -2.0),
                  ("totals", "over", 218.0), ("totals", "under", 222.0)])
    mu = pd.DataFrame({"game_id": "G", "market": ["spreads", "totals"], "mu": [3.0, 220.0]})
    dec = pd.DataFrame({"game_id": "G", "market": ["spreads", "totals"], "cons": [-3.0, 220.0]})
    half = {"spreads": (0.0, 0.5), "totals": (0.0, 0.5)}
    # the projection equals the consensus (home by 3, total 220): no move predicted
    s = P.move_strength(n, mu, dec, half)["strength"].tolist()
    assert s == pytest.approx([0.0, 0.0, 0.0, 0.0, 0.0])
    # a predicted move gives every book's offer on a side the same strength
    s2 = P.move_strength(n, mu.assign(mu=[7.0, 226.0]), dec, half)["strength"].tolist()
    assert s2 == pytest.approx([2.0, 2.0, -2.0, 3.0, -3.0])


def test_the_placebo_moves_the_projection_and_never_the_price():
    data = P.synthetic_market(per_season=4)
    sig = {(s, m): 12.0 for s in data.games["season"].unique() for m in ("spreads", "totals")}
    t, off = H.point_offers(data, "C")
    vis = H.visible(data.quotes, t)
    neutral = H.fair_offers(off, H.market_fair(vis, sig))
    g = data.games
    proj = pd.DataFrame({"game_id": g["game_id"], "season": g["season"],
                         "margin": np.arange(len(g), dtype=float), "total": 220.0,
                         "margin5": np.arange(len(g), dtype=float), "total5": 220.0})
    pi = P.PointInputs("C", t, off, vis, neutral, proj)
    cand, pl = P.family_frames("F5", pi, g, None, n_placebo=3)
    key = ["game_id", "market", "side", "book", "line"]
    a = cand.sort_values(key).reset_index(drop=True)
    for p in pl:
        b = p.sort_values(key).reset_index(drop=True)
        assert np.allclose(a["ev"], b["ev"]) and np.allclose(a["price"], b["price"])
    # only the markets the projection numbers (no moneyline gap), every row scored
    assert set(a["market"]) == {"spreads", "totals"} and a["strength"].notna().all()
    assert any(not np.allclose(a["strength"], p.sort_values(key)["strength"].to_numpy()) for p in pl)


def test_a_game_the_projection_did_not_number_is_outside_the_population():
    # review follow-up (bar 9): the harness reads a cell's priced population
    # from the games in `cand`; F5 and F1b carried every priced game, with an
    # empty strength where the projection gave no number
    data = P.synthetic_market(per_season=4, seasons=(2022,))
    sig = {(2022, m): 12.0 for m in ("spreads", "totals")}
    t, off = H.point_offers(data, "C")
    vis = H.visible(data.quotes, t)
    neutral = H.fair_offers(off, H.market_fair(vis, sig))
    g = data.games
    proj = pd.DataFrame({"game_id": g["game_id"], "season": g["season"],
                         "margin": [5.0, np.nan, 5.0, 5.0], "total": [220.0, np.nan, 220.0, 220.0],
                         "margin5": [5.0, np.nan, 5.0, 5.0], "total5": [220.0, np.nan, 220.0, 220.0]})
    pi = P.PointInputs("C", t, off, vis, neutral, proj)
    coef = {2022: {"spreads": (0.0, 0.5), "totals": (0.0, 0.5)}}
    unpriced = g["game_id"].iloc[1]
    for fam, c in (("F5", None), ("F1b", coef)):
        cand, pl = P.family_frames(fam, pi, g, c, n_placebo=2)
        assert unpriced not in set(cand["game_id"]) and len(cand), fam
        assert all(unpriced not in set(p["game_id"]) for p in pl), fam
        rows = H.run_cells(data, fam, "C", cand, neutral, [0.0], {"spreads": ["home"]},
                           strength="strength", times=t)
        assert rows[0]["population_games"] == 3, fam


def test_population_counts_games_prices_model_numbers_and_bets():
    data = P.synthetic_market(per_season=4, seasons=(2022, 2023))
    sig = {(s, m): 12.0 for s in (2022, 2023) for m in ("spreads", "totals")}
    t, off = H.point_offers(data, "D")
    t = t[t["game_id"] != "S2023_3"]                      # one game never reaches D
    off = off[off["game_id"].isin(t["game_id"])]
    vis = H.visible(data.quotes, t)
    neutral = H.fair_offers(off, H.market_fair(vis, sig))
    g = data.games
    proj = pd.DataFrame({"game_id": g["game_id"], "season": g["season"], "margin": 30.0, "total": 220.0,
                         "margin5": [30.0, np.nan, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0], "total5": 220.0})
    pi = P.PointInputs("D", t, off, vis, neutral, proj)
    cand, _ = P.family_frames("F5", pi, g, None, n_placebo=0)
    pop = P.population("F5", "D", data, pi, cand).set_index(["season", "market", "side", "cut"])
    r = pop.loc[(2023, "spreads", "home", 1.0)]
    assert (r["games"], r["games_with_time"], r["games_priced"], r["games_with_model"]) == (4, 3, 3, 3)
    assert r["bets"] == 3                                  # home by 30 clears every spread
    assert pop.loc[(2022, "spreads", "home", 1.0), "games_with_model"] == 3   # one game had no number
    assert pop.loc[(2022, "spreads", "away", 1.0), "bets"] == 0


def test_the_f1_placebo_shuffles_the_projection_between_games_on_a_date():
    # re-review: an F1 placebo left unshuffled passed every test
    data = P.synthetic_market(per_season=4, seasons=(2022,))
    sig = {(2022, m): 12.0 for m in ("spreads", "totals")}
    t, off = H.point_offers(data, "C")
    vis = H.visible(data.quotes, t)
    neutral = H.fair_offers(off, H.market_fair(vis, sig))
    g = data.games
    proj = pd.DataFrame({"game_id": g["game_id"], "season": g["season"],
                         "margin": [-8.0, 9.0, -2.0, 6.0], "total": [205.0, 232.0, 214.0, 228.0]})
    own = {(2022, "spreads"): _dist(14.0), (2022, "totals"): _dist(19.0, seed=12)}
    pi = P.PointInputs("C", t, off, vis, neutral, proj, own)
    cand, pl = P.family_frames("F1", pi, g, None, n_placebo=4)
    key = ["game_id", "market", "side", "book", "line"]
    a = cand.sort_values(key).reset_index(drop=True)
    date = g.set_index("game_id")["game_date"]
    moved = 0
    for p in pl:
        b = p.sort_values(key).reset_index(drop=True)
        assert (a[key].fillna(0) == b[key].fillna(0)).all().all() and np.allclose(a["price"], b["price"])
        moved += int(not np.allclose(a["p_win"], b["p_win"]))
        # a game only ever takes the number of a game on its own date
        for (d_, m), x in a.assign(d=a["game_id"].map(date)).groupby(["d", "market"]):
            y = b.loc[x.index]
            col = "p_home" if m == "h2h" else "mu"
            assert sorted(x[col].unique()) == pytest.approx(sorted(y[col].unique()))
    assert moved >= 1


def _emit_world(drop_at_d=None):
    """A synthetic priced world for emit_family: every choosing season and the
    confirmation season, the market priced through an EMPIRICAL distribution,
    and the projection far from every line so each home cell bets."""
    seasons = (2022, 2023, 2024, 2025, 2026)
    data = P.synthetic_market(per_season=4, seasons=seasons)
    rng = np.random.default_rng(2)
    emp = {m: H.ResidDist(rng.normal(0.0, 12.0 if m == "spreads" else 18.0, 2000), f"market {m}")
           for m in ("spreads", "totals")}
    market_sig = {(s, m): emp[m] for s in seasons for m in emp}
    g = data.games
    proj = pd.DataFrame({"game_id": g["game_id"], "season": g["season"], "margin": 30.0, "total": 260.0,
                         "margin5": 30.0, "total5": 260.0})
    inputs = {}
    for p in H.POINTS:
        times, off = H.point_offers(data, p)
        if p == "D" and drop_at_d is not None:
            times = times[times["game_id"] != drop_at_d].reset_index(drop=True)
            off = off[off["game_id"] != drop_at_d]
        vis = H.visible(data.quotes, times)
        neutral = H.fair_offers(off, H.market_fair(vis, market_sig))
        inputs[p] = P.PointInputs(p, times, off, vis, neutral, proj)
    return data, inputs, market_sig


def _spy_run_cells(monkeypatch):
    real_boot = H.boot
    monkeypatch.setattr(H, "boot", lambda b, n=H.N_BOOT, seed=H.SEED: real_boot(b, n=20, seed=seed))
    monkeypatch.setattr(H, "P_REFINE_BELOW", -1.0)
    seen, real = [], H.run_cells

    def spy(*a, **k):
        seen.append({"point": a[2], **k})
        return real(*a, **k)

    monkeypatch.setattr(H, "run_cells", spy)
    return seen


def test_closing_value_is_priced_with_the_markets_empirical_distribution(monkeypatch):
    # re-review: passing no pricing (sig=None) to run_cells silently drops
    # closing-line value from every cell, and no test noticed
    seen = _spy_run_cells(monkeypatch)
    data, inputs, market_sig = _emit_world()
    rows, _ = P.emit_family("F5", data, inputs, market_sig, H.pinnacle_close(data), None, n_placebo=1)
    # every home and over cell bets (3 points x 3 cuts each), and every one of
    # them carries a closing value
    bet = [r for r in rows if r["side"] in ("home", "over") and r["n_choose"] > 0]
    assert len(bet) == 18 and all(r["clv_n"] > 0 and np.isfinite(r["clv_median"]) for r in bet)
    # priced with the market's own empirical distribution, the one the lab was given
    assert len(seen) == 3 and all(k["sig"] is market_sig for k in seen)
    assert all(isinstance(v, H.ResidDist) for v in market_sig.values())


def test_the_d_cells_are_gated_on_the_points_own_decision_times(monkeypatch):
    # re-review: the 95% gate at D reads the decision times the lab passes;
    # passed empty, every choosing season is dropped, and passed none, the
    # harness falls back to the slate fetches. One 2023 game never reaches D
    # here, so 2023's coverage at D is 3 of 4 games and 2023 is not chosen on.
    seen = _spy_run_cells(monkeypatch)
    data, inputs, market_sig = _emit_world(drop_at_d="S2023_3")
    rows, _ = P.emit_family("F5", data, inputs, market_sig, H.pinnacle_close(data), None, n_placebo=1)
    d_rows = [r for r in rows if r["point"] == "D"]
    assert len(d_rows) == 12
    assert [(r["gate_cov_2022"], r["gate_cov_2023"]) for r in d_rows] == [(1.0, 0.75)] * 12
    assert {(r["gate_dropped"], r["choose_seasons"]) for r in d_rows} == {("2023", "2022,2024,2025")}
    assert all(r["gate_dropped"] == "" for r in rows if r["point"] != "D")
    at_d = [k for k in seen if k["point"] == "D"]
    assert len(at_d) == 1 and at_d[0]["times"] is inputs["D"].times and len(at_d[0]["times"]) == 19


def test_the_ratings_label_says_which_ratings_were_used():
    # re-review: quality() printed "box-score only" whatever the cache held
    g = _games(n_per_season=30)
    adv, log = _box(g)
    ina = pd.DataFrame(columns=["game_id", "team", "player_id"])
    w = P.build_world(g, adv, log, ina, _inj(), stints=_segment_rows(g))
    st = _state(w)
    box = P.fit_box(w, st, [2020])
    table, info = P.rapm_table(w, st, box, 2021)
    play = P.fit_play(pd.DataFrame(columns=["season", "bucket", "status", "role", "played"]), 2021)
    seg = P.Model(season=2021, box=box, play=play, cap=40.0, rapm=table, info={"rapm": info})
    u = P.ratings_used(w, {2021: seg}, [2021])
    assert u["label"] == f"{P.SEGMENTS_USED}, every season"
    assert u["by_season"][2021].startswith(P.SEGMENTS_USED) and f"{info['refits']} refits" in u["by_season"][2021]
    # a season whose model has no refit is named as box-score only
    bare = P.Model(season=2020, box=box, play=play, cap=40.0, info={"rapm": {"lambda": 2000.0, "refits": 0}})
    mixed = P.ratings_used(w, {2020: bare, 2021: seg}, [2020, 2021])
    assert mixed["label"] == f"{P.SEGMENTS_USED} in 2021; {P.BOX_ONLY} in 2020"
    assert mixed["by_season"][2020].startswith(P.BOX_ONLY)
    # no segment file at all
    plain = P.ratings_used(_world(), {2021: P.Model(season=2021, box=box, play=play, cap=40.0)}, [2021])
    assert plain["label"] == f"{P.BOX_ONLY} (no lineup segment file in the cache)"


def test_the_quality_run_reports_the_ratings_it_used(tmp_path, monkeypatch):
    # re-review: the label was a hard-coded string in quality() itself
    g = _games(n_per_season=30)
    adv, log = _box(g)
    ina = pd.DataFrame(columns=["game_id", "team", "player_id"])
    w = P.build_world(g, adv, log, ina, _inj(), stints=_segment_rows(g))
    st = _state(w, fit=[2019], scored=2020, mse={})
    box = P.fit_box(w, st, [2020])
    table, info = P.rapm_table(w, st, box, 2021)
    play = P.fit_play(pd.DataFrame(columns=["season", "bucket", "status", "role", "played"]), 2021)
    models = {2021: P.Model(season=2021, box=box, play=play, cap=40.0, rapm=table, info={"rapm": info}, st=st)}
    refs = {2020: P.project(w, st, P.Model(season=2020, box=box, play=play, cap=40.0, st=st), P.ref_games(w, 2020))}
    obs = pd.DataFrame(columns=["season", "status", "role", "bucket", "played"])
    monkeypatch.setattr(P, "QUALITY_SEASONS", (2021,))
    monkeypatch.setattr(P, "RESULTS", tmp_path)
    monkeypatch.setattr(P, "load_world", lambda cache, max_season: w)
    monkeypatch.setattr(P, "run_projection_setup",
                        lambda w_, last, log=print, obs_seasons=(): (st.hp, st, models, refs, obs))
    res = P.quality(tmp_path)
    assert res["ratings"] == f"{P.SEGMENTS_USED}, every season"
    assert res["seasons"][2021]["fit"]["ratings"].startswith(P.SEGMENTS_USED)


# ── run modes ───────────────────────────────────────────────────────────────

def test_full_refuses_without_go_segments_or_ledger(tmp_path, monkeypatch):
    monkeypatch.delenv(P.GO_ENV, raising=False)
    why = P.refuse_full(tmp_path)
    assert len(why) == 3
    monkeypatch.setenv(P.GO_ENV, "1")
    (tmp_path / P.STINTS_FILE).write_bytes(b"x")
    assert len(P.refuse_full(tmp_path)) == 1 and "ledger" in P.refuse_full(tmp_path)[0]
    (tmp_path / P.LEDGER_FILE).write_bytes(b"x")
    assert P.refuse_full(tmp_path) == []
    (tmp_path / P.STINTS_FILE).unlink()
    assert len(P.refuse_full(tmp_path)) == 1 and "segments" in P.refuse_full(tmp_path)[0]


def _games_file(tmp_path, seasons=(2019, 2020), n=10):
    g = _games(n_per_season=n, seasons=seasons)
    g["commence_time"] = g["tip"].astype(str)
    g.to_parquet(tmp_path / "nba_games.parquet")
    return g


def test_a_segment_file_missing_part_of_a_season_is_refused(tmp_path):
    # review fix 6: Supabase holds 2022-23 only to 2022-12-23 today; a file
    # exported mid-load would grade later seasons on box ratings alone
    g = _games_file(tmp_path)
    covered = list(g.loc[g["season"] == 2019, "game_id"]) + list(g.loc[g["season"] == 2020, "game_id"][:6])
    pd.DataFrame({"game_id": covered, "season_type": 2}).to_parquet(tmp_path / P.STINTS_FILE)
    assert P.stints_short(tmp_path, seasons=(2019, 2020)) == {2020: 0.6}
    # postseason segments do not count toward a regular-season game
    pd.DataFrame({"game_id": list(g["game_id"]), "season_type": [2] * 10 + [3] * 10}).to_parquet(
        tmp_path / P.STINTS_FILE)
    assert P.stints_short(tmp_path, seasons=(2019, 2020)) == {2020: 0.0}
    pd.DataFrame({"game_id": list(g["game_id"]), "season_type": 2}).to_parquet(tmp_path / P.STINTS_FILE)
    assert P.stints_short(tmp_path, seasons=(2019, 2020)) == {}
    assert P.stints_short(tmp_path, seasons=(2019, 2020, 2021)) == {2021: 0.0}
    assert P.STINT_SEASONS == (2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026)


def test_full_checks_the_price_cache_for_every_graded_season_before_building_anything(tmp_path, monkeypatch):
    # review fix 6: --full calls H.load(require_seasons=...) with every season
    # it grades, and does so before the hour-long projection build
    monkeypatch.setenv(P.GO_ENV, "1")
    (tmp_path / P.STINTS_FILE).write_bytes(b"x")
    (tmp_path / P.LEDGER_FILE).write_bytes(b"x")
    seen = {}

    class Stop(Exception):
        pass

    def fake_load(cache, seasons=None, require_seasons=None):
        seen.update(seasons=seasons, require_seasons=require_seasons)
        raise Stop

    def built_too_early(*a, **k):
        raise AssertionError("the projection was built before the cheap refusals ran")

    monkeypatch.setattr(H, "load", fake_load)
    monkeypatch.setattr(P, "load_world", built_too_early)
    monkeypatch.setattr(P, "run_projection_setup", built_too_early)
    with pytest.raises(Stop):
        P.full(tmp_path)
    assert tuple(seen["require_seasons"]) == P.GRADED == (2021, 2022, 2023, 2024, 2025, 2026)
    assert tuple(seen["seasons"]) == P.GRADED

    # a stale cache (the harness refuses) is a REFUSED exit, not a traceback
    def stale(cache, seasons=None, require_seasons=None):
        raise RuntimeError("cache prices too few games in {2024: 0.3}")

    monkeypatch.setattr(H, "load", stale)
    with pytest.raises(SystemExit) as e:
        P.full(tmp_path)
    assert e.value.code == 2

    # prices fine, segments for only part of the seasons the ratings read: refused
    g = _games_file(tmp_path, seasons=P.STINT_SEASONS, n=2)
    pd.DataFrame({"game_id": g.loc[g["season"] <= 2022, "game_id"], "season_type": 2}).to_parquet(
        tmp_path / P.STINTS_FILE)
    monkeypatch.setattr(H, "load", lambda cache, seasons=None, require_seasons=None: H.Data(
        games=g, quotes=pd.DataFrame(), fetches=pd.DataFrame(), notes={}))
    with pytest.raises(SystemExit) as e:
        P.full(tmp_path)
    assert e.value.code == 2


def test_the_smoke_ledger_has_every_2020_21_pull_and_never_writes_into_the_cache(tmp_path, monkeypatch):
    led = P.ledger_2021()
    assert len(led) == 1963 and led["requested_at"].dt.tz is not None
    assert (led["requested_at"] == pd.Timestamp("2021-01-05T15:00:00Z")).any()
    assert not (led["requested_at"].dt.strftime("%Y-%m-%d") == "2021-03-07").any()
    monkeypatch.setattr(P, "SMOKE_CACHE", tmp_path / "cache" / "inside")
    with pytest.raises(AssertionError):
        P.smoke_price_cache(tmp_path / "cache")


def test_the_quality_run_never_reads_the_confirmation_season(tmp_path):
    g = _games(n_per_season=2, seasons=(2025, 2026))
    g["commence_time"] = g["tip"].astype(str)
    adv, log = _box(g)
    adv = adv.assign(game_type="regular", season=adv["game_id"].str[1:5].astype(int))
    log = log.assign(season=log["game_id"].str[1:5].astype(int))
    g.to_parquet(tmp_path / "nba_games.parquet")
    adv.to_parquet(tmp_path / "nba_player_game_adv.parquet")
    log.to_parquet(tmp_path / "nba_player_game_log.parquet")
    pd.DataFrame({"game_id": ["G2026_0"], "team": ["AAA"], "player_id": ["A0"], "game_type": ["regular"],
                  "season": [2026]}).to_parquet(tmp_path / "nba_game_inactives.parquet")
    _inj([{"report_ts": pd.Timestamp("2025-12-01T20:00:00Z"), "game_id": "G2026_0", "team": "AAA",
           "player_id": "A0", "player_name": "a", "status": "Out", "season": 2026}]).to_parquet(
        tmp_path / "nba_injury_report.parquet")
    w = P.load_world(tmp_path, max_season=2025)
    assert set(w.games["season"]) == {2025} and set(w.panel["season"]) == {2025} and w.inj.empty
