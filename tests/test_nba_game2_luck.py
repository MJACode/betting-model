"""scripts/nba_game2_luck: F4 (shooting-luck-adjusted ratings) and F6c
(late-season motivation), docs/nba_models_2026.md section 6.3. Every feature
rule and every leak guard is pinned on small hand-built games by its outcome;
each test was watched failing once with the rule it guards broken."""
import numpy as np
import pandas as pd
import pytest

from scripts import nba_game2_luck as L
from scripts import nba_game_harness as H


# ── hand-built box scores ────────────────────────────────────────────────────

def _tb_row(gid, date, team, opp, pts=100, fga=80, fg3m=10, fg3a=30, ftm=15, fta=20, oreb=10, tov=12,
            o_pts=100, o_fga=80, o_fg3m=10, o_fg3a=30, o_ftm=15, o_fta=20, o_oreb=10, o_tov=12,
            season=2024):
    r = {"game_id": gid, "season": season, "game_date": date, "team": team, "opp": opp,
         "pts": pts, "fga": fga, "fg3m": fg3m, "fg3a": fg3a, "ftm": ftm, "fta": fta, "oreb": oreb,
         "tov": tov, "opp_pts": o_pts, "opp_fga": o_fga, "opp_fg3m": o_fg3m, "opp_fg3a": o_fg3a,
         "opp_ftm": o_ftm, "opp_fta": o_fta, "opp_oreb": o_oreb, "opp_tov": o_tov}
    r["poss"] = 0.5 * ((fga - oreb + tov + 0.44 * fta) + (o_fga - o_oreb + o_tov + 0.44 * o_fta))
    return r


def _pair(gid, date, home, away, h=None, a=None, season=2024):
    """Both team rows of one game; h / a are the home / away team's own stats."""
    h, a = h or {}, a or {}
    keys = ("pts", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "tov")
    hs = {k: h.get(k, _tb_row.__defaults__[keys.index(k)]) for k in keys}
    as_ = {k: a.get(k, _tb_row.__defaults__[keys.index(k)]) for k in keys}
    return [_tb_row(gid, date, home, away, **hs, **{f"o_{k}": v for k, v in as_.items()}, season=season),
            _tb_row(gid, date, away, home, **as_, **{f"o_{k}": v for k, v in hs.items()}, season=season)]


def _target(team, date, season=2024):
    return pd.DataFrame([{"season": season, "team": team, "game_date": date}])


def test_possessions_are_olivers_estimate_averaged_over_both_teams():
    box = pd.DataFrame([
        {"game_id": "G", "team": "DET", "points": 100, "fg_att": 85, "fg3_made": 10, "fg3_att": 30,
         "ft_made": 15, "ft_att": 25, "offensive_reb": 10, "turnovers": 14},
        {"game_id": "G", "team": "BOS", "points": 110, "fg_att": 88, "fg3_made": 15, "fg3_att": 40,
         "ft_made": 12, "ft_att": 15, "offensive_reb": 12, "turnovers": 10}])
    games = pd.DataFrame([{"game_id": "G", "season": 2024, "game_date": "2024-01-02",
                           "home_team": "DET", "away_team": "BOS"}])
    tb = L.team_box(box, games).set_index("team")
    det = 85 - 10 + 14 + 0.44 * 25
    bos = 88 - 12 + 10 + 0.44 * 15
    assert tb.loc["DET", "poss"] == pytest.approx(0.5 * (det + bos))
    assert tb.loc["DET", "opp_fg3a"] == 40 and tb.loc["BOS", "opp_pts"] == 100


def test_ratings_use_only_games_before_the_date():
    # DET plays on the 1st, 2nd (the target date) and 3rd; only the 1st counts
    tb = pd.DataFrame(_pair("G1", "2024-01-01", "DET", "BOS", h={"pts": 90})
                      + _pair("G2", "2024-01-02", "DET", "NYK", h={"pts": 150})
                      + _pair("G3", "2024-01-03", "DET", "MIA", h={"pts": 150}))
    r = L.as_of_ratings(tb, _target("DET", "2024-01-02")).iloc[0]
    assert r["n"] == 1
    assert r["ortg_raw"] == pytest.approx(100 * 90 / tb.iloc[0]["poss"])


def test_ratings_ignore_the_previous_season():
    tb = pd.DataFrame(_pair("G0", "2023-04-01", "DET", "BOS", h={"pts": 150}, season=2023)
                      + _pair("G1", "2023-10-25", "DET", "NYK", h={"pts": 90}, season=2024))
    r = L.as_of_ratings(tb, _target("DET", "2023-10-27")).iloc[0]
    assert r["n"] == 1 and r["ortg_raw"] == pytest.approx(100 * 90 / tb.iloc[2]["poss"])


def test_league_averages_use_only_games_before_the_date():
    base = (_pair("G1", "2024-01-01", "DET", "BOS", h={"fg3m": 10, "fg3a": 30}, a={"fg3m": 8, "fg3a": 30})
            + _pair("G2", "2024-01-01", "NYK", "MIA"))
    hot_today = _pair("G3", "2024-01-02", "NYK", "MIA", h={"fg3m": 30, "fg3a": 31}, a={"fg3m": 30, "fg3a": 31})
    a = L.as_of_ratings(pd.DataFrame(base), _target("DET", "2024-01-02")).iloc[0]
    b = L.as_of_ratings(pd.DataFrame(base + hot_today), _target("DET", "2024-01-02")).iloc[0]
    assert a["ortg_adj"] == pytest.approx(b["ortg_adj"]) and a["drtg_adj"] == pytest.approx(b["drtg_adj"])


def _two_team_league(det_own=(12, 30), det_opp=(9, 30), det_opp_ft=(15, 20)):
    """DET v BOS once, NYK v MIA once, on 2024-01-01: league 3P% is the four
    teams' total. Returns (tb, DET's as-of row on the 2nd, league 3P%, FT%)."""
    rows = (_pair("G1", "2024-01-01", "DET", "BOS",
                  h={"fg3m": det_own[0], "fg3a": det_own[1]},
                  a={"fg3m": det_opp[0], "fg3a": det_opp[1], "ftm": det_opp_ft[0], "fta": det_opp_ft[1]})
            + _pair("G2", "2024-01-01", "NYK", "MIA"))
    tb = pd.DataFrame(rows)
    lg3 = tb["fg3m"].sum() / tb["fg3a"].sum()
    lgft = tb["ftm"].sum() / tb["fta"].sum()
    return tb, L.as_of_ratings(tb, _target("DET", "2024-01-02")).iloc[0], lg3, lgft


def test_own_three_point_pct_is_regressed_by_the_published_amount():
    tb, r, lg3, _ = _two_team_league(det_own=(14, 30))
    own3, poss = 14 / 30, tb.iloc[0]["poss"]
    want = 100 * 3 * 30 * (L.OWN3_KEEP - 1.0) * (own3 - lg3) / poss
    assert L.OWN3_KEEP == 0.42
    assert r["ortg_adj"] - r["ortg_raw"] == pytest.approx(want)


def test_opponent_three_and_free_throw_pct_are_replaced_by_the_league_average():
    tb, r, lg3, lgft = _two_team_league(det_opp=(15, 30), det_opp_ft=(20, 20))
    poss = tb.iloc[0]["poss"]
    want = 100 * (3 * (30 * lg3 - 15) + (20 * lgft - 20)) / poss
    assert r["drtg_adj"] - r["drtg_raw"] == pytest.approx(want)
    assert want < 0          # opponents shot hot: the adjusted defence is better


def _season(n_dates, hot_vs_det=True, start="2024-01-01", season=2024):
    """Four teams, two games a date, every team every date; DET's opponents
    shoot 3s hot (20 of 30) when hot_vs_det, everyone else 10 of 30."""
    rows, games = [], []
    d0 = pd.Timestamp(start)
    for i in range(n_dates):
        d = (d0 + pd.Timedelta(days=i)).strftime("%Y-%m-%d")
        pairs = [("DET", "BOS"), ("NYK", "MIA")] if i % 2 == 0 else [("BOS", "NYK"), ("MIA", "DET")]
        for h, a in pairs:
            gid = f"NBA_{d}_{a}_{h}"
            hs, as_ = {}, {}
            if hot_vs_det and "DET" in (h, a):
                (as_ if h == "DET" else hs).update({"fg3m": 20, "fg3a": 30, "pts": 120})
            rows += _pair(gid, d, h, a, h=hs, a=as_, season=season)
            games.append({"game_id": gid, "season": season, "game_date": d, "home_team": h, "away_team": a,
                          "home_score": 100 + (5 if h == "DET" else 0), "away_score": 100})
    return pd.DataFrame(rows), pd.DataFrame(games)


def test_a_team_whose_opponents_shot_hot_is_favoured_by_the_adjustment():
    tb, games = _season(14)
    p = L.f4_projections(games, tb)
    det_home = p[p["home_team"] == "DET"]
    det_away = p[p["away_team"] == "DET"]
    assert len(det_home) and len(det_away)
    assert (det_home["gap_margin"] > 0).all() and (det_away["gap_margin"] < 0).all()
    assert (p.loc[p["home_team"].eq("DET") | p["away_team"].eq("DET"), "gap_total"] < 0).all()


def test_the_projection_is_the_net_rating_difference_times_pace():
    tb, games = _season(14)
    p = L.f4_projections(games, tb).iloc[0]
    pace = 0.5 * (p["h_pace"] + p["a_pace"]) / 100
    assert p["margin_raw"] == pytest.approx(
        pace * ((p["h_ortg_raw"] - p["h_drtg_raw"]) - (p["a_ortg_raw"] - p["a_drtg_raw"])))
    assert p["total_raw"] == pytest.approx(
        pace * (p["h_ortg_raw"] + p["a_drtg_raw"] + p["a_ortg_raw"] + p["h_drtg_raw"] - 2 * p["h_lg_rtg"]))


def test_a_team_needs_ten_games_before_the_date():
    tb, games = _season(14)
    p = L.f4_projections(games, tb)
    # every team plays every date: on date index 10 each has 10 earlier games
    first = pd.Timestamp("2024-01-01") + pd.Timedelta(days=10)
    assert p["game_date"].min() == first.strftime("%Y-%m-%d")
    assert (p["h_n"] >= 10).all() and (p["a_n"] >= 10).all()


def test_the_margin_gap_prices_spreads_and_the_total_gap_prices_totals():
    proj = pd.DataFrame({"game_id": ["G"], "gap_margin": [1.5], "gap_total": [-2.5]})
    s = L.f4_signal(proj).set_index("market")["strength"]
    assert s.to_dict() == {"spreads": 1.5, "totals": -2.5}


def test_each_side_carries_the_gap_in_its_own_favour():
    off = pd.DataFrame({"game_id": "G", "market": ["spreads", "spreads", "totals", "totals"],
                        "side": ["home", "away", "over", "under"], "book": "fanduel"})
    sig = pd.DataFrame({"game_id": "G", "market": ["spreads", "totals"], "strength": [2.5, -1.5]})
    s = L.side_strength(off, sig).set_index("side")["strength"]
    assert s.to_dict() == {"home": 2.5, "away": -2.5, "over": -1.5, "under": 1.5}


# ── F6c standings ───────────────────────────────────────────────────────────

def _standing(w, rem, games=80, conf="E", date="2024-04-01", season=2024, teams=None):
    teams = teams or [f"T{i:02d}" for i in range(len(w))]
    st = pd.DataFrame({"season": season, "game_date": date, "conf": conf, "team": teams,
                       "w": np.asarray(w, float), "remaining": float(rem)})
    st["l"] = games - st["remaining"] - st["w"]
    return st


def test_a_seed_is_locked_only_when_no_team_can_reach_it_or_be_reached():
    # 15 teams, 2 games left: T00 is clear at the top; T01 and T02 can still meet
    w = [60, 45, 44, 40, 36, 33, 30, 27, 24, 21, 18, 15, 12, 9, 6]
    s = L.situations(_standing(w, 2)).set_index("team")
    assert bool(s.loc["T00", "seed_locked"]) and bool(s.loc["T03", "seed_locked"])
    assert not bool(s.loc["T01", "seed_locked"]) and not bool(s.loc["T02", "seed_locked"])
    # a possible tie is not a lock: T03 at 40 with 2 left can be met by a team at 38 with 2 left
    w2 = list(w)
    w2[4] = 38
    s2 = L.situations(_standing(w2, 2)).set_index("team")
    assert not bool(s2.loc["T03", "seed_locked"])


def test_a_locked_lottery_place_is_not_a_seed():
    w = [60, 55, 50, 46, 42, 38, 34, 30, 26, 22, 18, 14, 10, 6, 2]
    s = L.situations(_standing(w, 1)).set_index("team")
    assert bool(s.loc["T09", "seed_locked"])                 # 10th: a play-in seed
    assert not bool(s.loc["T10", "seed_locked"]) and not bool(s.loc["T14", "seed_locked"])


def test_eliminated_means_ten_teams_certainly_finish_above():
    w = [50, 49, 48, 47, 46, 45, 44, 43, 42, 41, 37, 36, 30, 20, 10]
    s = L.situations(_standing(w, 3)).set_index("team")
    # T10 at 37 can reach 40, below 10 teams' current wins (41+)
    assert bool(s.loc["T10", "eliminated"]) and bool(s.loc["T14", "eliminated"])
    # with 4 left T10 can reach 41 and tie the 10th team: not eliminated
    s4 = L.situations(_standing(w, 4)).set_index("team")
    assert not bool(s4.loc["T10", "eliminated"])


def _games_for_standings(results, season=2024):
    return pd.DataFrame([{"game_id": f"G{i}", "season": season, "game_date": d, "home_team": h,
                          "away_team": a, "home_score": hs, "away_score": as_}
                         for i, (d, h, a, hs, as_) in enumerate(results)])


def test_standings_count_only_results_before_the_date():
    g = _games_for_standings([("2024-03-01", "DET", "BOS", 100, 90),
                              ("2024-03-02", "DET", "BOS", 100, 90),
                              ("2024-03-03", "DET", "BOS", 100, 90)])
    lengths = pd.DataFrame({"season": 2024, "team": ["DET", "BOS"], "n_games": 82})
    st = L.standings(g, lengths).set_index(["game_date", "team"])
    assert st.loc[("2024-03-02", "DET"), "w"] == 1 and st.loc[("2024-03-02", "BOS"), "l"] == 1
    assert st.loc[("2024-03-01", "DET"), "w"] == 0
    # the date's own result cannot move its standing
    g2 = g.copy()
    g2.loc[1, ["home_score", "away_score"]] = [80, 120]
    st2 = L.standings(g2, lengths).set_index(["game_date", "team"])
    assert st2.loc[("2024-03-02", "DET"), "w"] == st.loc[("2024-03-02", "DET"), "w"]


def test_games_remaining_come_from_the_schedules_season_length():
    sched = pd.DataFrame([{"season": 2021, "game_type": "regular", "home_team": "DET", "away_team": "BOS"}] * 72
                         + [{"season": 2021, "game_type": "playoff", "home_team": "DET", "away_team": "BOS"}] * 3)
    lengths = L.season_lengths(sched).set_index("team")
    assert lengths.loc["DET", "n_games"] == 72
    g = _games_for_standings([("2021-05-01", "DET", "BOS", 100, 90),
                              ("2021-05-02", "DET", "BOS", 100, 90)], season=2021)
    st = L.standings(g, lengths.reset_index()).set_index(["game_date", "team"])
    assert st.loc[("2021-05-02", "DET"), "remaining"] == 71


def test_tanking_is_the_bottom_three_after_the_deadline_ties_included():
    w = [30, 25, 20, 20, 20, 50]
    before = L.situations(_standing(w, 10, games=70, date="2024-02-08", teams=list("ABCDEF")))
    after = L.situations(_standing(w, 10, games=70, date="2024-02-09", teams=list("ABCDEF")))
    assert not before["tanking"].any()                       # the deadline day itself is not after it
    assert set(after.loc[after["tanking"], "team"]) == {"C", "D", "E"}
    w2 = [30, 25, 20, 19, 18, 50]
    a2 = L.situations(_standing(w2, 10, games=70, date="2024-02-09", teams=list("ABCDEF")))
    assert set(a2.loc[a2["tanking"], "team"]) == {"C", "D", "E"}
    w3 = [30, 20, 20, 19, 18, 50]                            # B ties C at third-lowest
    a3 = L.situations(_standing(w3, 10, games=70, date="2024-02-09", teams=list("ABCDEF")))
    assert set(a3.loc[a3["tanking"], "team"]) == {"B", "C", "D", "E"}


def test_a_game_with_both_teams_in_the_situation_has_no_side():
    games = pd.DataFrame([{"game_id": "G1", "season": 2024, "game_date": "2024-04-01",
                           "home_team": "DET", "away_team": "WAS"},
                          {"game_id": "G2", "season": 2024, "game_date": "2024-04-01",
                           "home_team": "BOS", "away_team": "CHA"}])
    sit = pd.DataFrame({"season": 2024, "game_date": "2024-04-01", "team": ["DET", "WAS", "BOS", "CHA"],
                        "seed_locked": False, "eliminated": [True, True, False, True], "tanking": False})
    gs = L.game_situations(games, sit)
    e = gs[gs["situation"] == "eliminated"].set_index("game_id")
    assert not bool(e.loc["G1", "single"]) and bool(e.loc["G1", "both"])
    assert bool(e.loc["G2", "single"]) and bool(e.loc["G2", "away_in"]) and not bool(e.loc["G2", "home_in"])


def test_only_games_with_the_situation_team_at_home_are_flipped_and_flagged_once():
    gs = pd.DataFrame({"game_id": ["G1", "G2", "G3", "G4"],
                       "home_in": [True, False, True, False], "away_in": [False, True, True, False]})
    gs["single"], gs["both"] = gs["home_in"] ^ gs["away_in"], gs["home_in"] & gs["away_in"]
    assert L.f6c_flip(gs) == {"G1"}
    neutral = pd.DataFrame({"game_id": ["G1", "G1", "G2", "G3", "G4"], "market": "spreads",
                            "side": ["home", "away", "home", "home", "home"]})
    sig = L.f6c_signal(neutral, gs).set_index("game_id")["strength"]
    assert sig.to_dict() == {"G1": 1.0, "G2": 1.0, "G3": 0.0, "G4": 0.0}


# ── F6c orientation ─────────────────────────────────────────────────────────

TIP = pd.Timestamp("2024-03-20T23:30:00Z")


def _one_game_data(home_score, away_score, line, pa, pb):
    games = pd.DataFrame([{"game_id": "G", "season": 2024, "game_date": "2024-03-20", "tip": TIP,
                           "home_team": "DET", "away_team": "BOS",
                           "home_score": home_score, "away_score": away_score}])
    q = pd.DataFrame([{"game_id": "G", "season": 2024, "game_date": "2024-03-20", "tip": TIP,
                       "market": "spreads", "book": "fanduel", "snapshot_at": TIP - pd.Timedelta(minutes=70),
                       "fetch_at": TIP - pd.Timedelta(minutes=60), "line": line, "price_a": pa,
                       "price_b": pb, "coherent": True},
                      {"game_id": "G", "season": 2024, "game_date": "2024-03-20", "tip": TIP,
                       "market": "totals", "book": "fanduel", "snapshot_at": TIP - pd.Timedelta(minutes=70),
                       "fetch_at": TIP - pd.Timedelta(minutes=60), "line": 220.5, "price_a": -108.0,
                       "price_b": -112.0, "coherent": True}])
    f = pd.DataFrame({"game_id": ["G"], "tip": [TIP], "fetch_at": [TIP - pd.Timedelta(minutes=60)],
                      "lead_min": [60.0]})
    return H.Data(games=games, quotes=q, fetches=f)


def test_the_oriented_home_bet_is_the_bet_against_the_situation_team():
    # DET (home, the situation team) +6.5 at -105 lost by 10: the bet against it
    # is BOS -6.5 at -115, and it wins
    d = L.orient(_one_game_data(100, 110, 6.5, -105.0, -115.0), ["G"])
    _, off = H.point_offers(d, "C")
    home = off[(off["side"] == "home") & (off["market"] == "spreads")]
    b = H.grade(home, d.games)
    assert b["result"].tolist() == ["W"] and b.iloc[0]["price"] == -115.0 and b.iloc[0]["line"] == -6.5
    # BOS winning by 6 does not cover -6.5
    d2 = L.orient(_one_game_data(100, 106, 6.5, -105.0, -115.0), ["G"])
    _, off2 = H.point_offers(d2, "C")
    assert H.grade(off2[(off2["side"] == "home") & (off2["market"] == "spreads")], d2.games)["result"].tolist() == ["L"]
    # totals are not touched
    tot = d.quotes[d.quotes["market"] == "totals"].iloc[0]
    assert tot["price_a"] == -108.0 and tot["line"] == 220.5


def test_an_unflipped_game_is_left_as_it_was():
    raw = _one_game_data(100, 110, 6.5, -105.0, -115.0)
    d = L.orient(raw, [])
    pd.testing.assert_frame_equal(d.games, raw.games)
    pd.testing.assert_frame_equal(d.quotes, raw.quotes)


# ── placebo ─────────────────────────────────────────────────────────────────

def test_the_placebo_moves_the_number_between_games_and_never_the_price():
    games = pd.DataFrame({"game_id": ["a", "b", "c", "d"],
                          "game_date": ["2024-01-15", "2024-01-15", "2024-01-15", "2024-01-16"]})
    neutral = pd.DataFrame([{"game_id": g, "market": "spreads", "side": s, "book": "fanduel",
                             "price": -110.0, "ev": ev}
                            for g, ev in zip("abcd", (0.01, -0.02, 0.03, 0.0)) for s in ("home", "away")])
    signal = pd.DataFrame({"game_id": list("abcd"), "market": "spreads", "strength": [3.0, 0.0, -1.0, 5.0]})
    frames = L.placebo_frames(neutral, signal, games)
    assert len(frames) == L.N_PLACEBO == 20
    moved = False
    for f in frames:
        h = f[f["side"] == "home"].set_index("game_id")
        assert h.loc["d", "strength"] == 5.0                    # alone on its date
        assert sorted(h.loc[list("abc"), "strength"]) == [-1.0, 0.0, 3.0]
        assert h["ev"].to_dict() == {"a": 0.01, "b": -0.02, "c": 0.03, "d": 0.0}
        moved |= h.loc["a", "strength"] != 3.0
    assert moved


# ── whole families on a synthetic season ────────────────────────────────────

def _synthetic_data(n_dates=13, start="2024-03-01"):
    tb, games = _season(n_dates, start=start)
    games["tip"] = pd.to_datetime(games["game_date"]) .dt.tz_localize("UTC") + pd.Timedelta(days=1)
    rows = []
    for _, g in games.iterrows():
        for fetch in (g["tip"] - pd.Timedelta(minutes=540), g["tip"] - pd.Timedelta(minutes=60)):
            for book, pa in (("fanduel", -110.0), ("pinnacle", -105.0), ("draftkings", -112.0)):
                for m, line in (("spreads", -2.5), ("totals", 200.5)):
                    rows.append({"game_id": g["game_id"], "season": g["season"], "game_date": g["game_date"],
                                 "tip": g["tip"], "market": m, "book": book,
                                 "snapshot_at": fetch - pd.Timedelta(minutes=5), "fetch_at": fetch,
                                 "line": line, "price_a": pa, "price_b": -110.0, "coherent": True})
    q = pd.DataFrame(rows)
    f = q[["game_id", "tip", "fetch_at"]].drop_duplicates()
    f = f.assign(lead_min=(f["tip"] - f["fetch_at"]).dt.total_seconds() / 60)
    return H.Data(games=games, quotes=q, fetches=f.reset_index(drop=True)), tb


def test_f4_emits_its_32_cells_with_twenty_placebos_each():
    data, tb = _synthetic_data()
    assert H.decision_times(data.fetches, data.games, "A")["T"].dt.hour.eq(15).all()
    close = H.pinnacle_close(data)
    sig = H.close_sigma(close, data.games)
    rows, pop = L.run_f4(data, tb, close, sig)
    assert len(rows) == L.EXPECTED_CELLS["F4"] == 32
    keys = {(r["point"], r["market"], r["side"], r["cut"]) for r in rows}
    assert len(keys) == 32 and {r["family"] for r in rows} == {"F4"}
    assert all(len(r["placebo_rois"]) == 20 for r in rows)
    assert set(pop["point"]) == {"A", "C"} and (pop["games_with_number"] > 0).all()


def test_f6c_emits_its_6_cells_one_per_situation_and_point():
    data, _ = _synthetic_data()
    lengths = pd.DataFrame({"season": 2024, "team": ["DET", "BOS", "NYK", "MIA"], "n_games": 20})
    sit = L.situations(L.standings(data.games, lengths))
    rows, pop = L.run_f6c(data, L.game_situations(data.games, sit))
    assert len(rows) == L.EXPECTED_CELLS["F6c"] == 6
    assert {(r["axis_situation"], r["point"]) for r in rows} == {
        (k, p) for k in L.SITUATIONS for p in L.F6C_POINTS}
    assert {r["side"] for r in rows} == {"home"} and all(len(r["placebo_rois"]) == 20 for r in rows)


def test_the_registered_count_is_38():
    assert L.EXPECTED_CELLS == {"F4": 32, "F6c": 6}
    assert len(L.F4_CUTS) == 4 and L.F4_POINTS == ("A", "C") and L.F6C_POINTS == ("A", "C")


def test_full_refuses_without_the_owners_go(monkeypatch, tmp_path):
    # an empty cache and results folder: a broken gate fails here, it never grades
    monkeypatch.setattr(H, "CACHE", tmp_path)
    monkeypatch.setattr(L, "RESULTS", tmp_path)
    monkeypatch.delenv("NBA_GAME2_GO", raising=False)
    with pytest.raises(SystemExit, match="NBA_GAME2_GO"):
        L.main(["--full"])


def test_the_price_free_check_refuses_2026():
    with pytest.raises(AssertionError, match="2026"):
        L.quality(pd.DataFrame(), pd.DataFrame(), seasons=(2025, 2026))


def test_a_cell_table_with_only_nan_placebos_reads_back_as_numbers(tmp_path):
    from scripts import nba_game2_verdict as V
    rows = [{"family": "F6c", "point": "A", "market": "spreads", "side": "home", "cut_index": 0,
             "cut": 1.0, "axis_situation": "eliminated", "placebo_rois": [np.nan] * 20}]
    L.write_cells(rows, tmp_path / "cells_X.parquet")
    back = V.load_cells(tmp_path)
    v = back["placebo_rois"].iloc[0]
    assert len(v) == 20 and all(np.isnan(x) for x in v)
    # the verdict's own placebo line runs on it
    p95 = back["placebo_rois"].apply(lambda v: np.percentile([x for x in v if np.isfinite(x)], 95)
                                     if len([x for x in v if np.isfinite(x)]) else np.nan)
    assert np.isnan(p95.iloc[0])
