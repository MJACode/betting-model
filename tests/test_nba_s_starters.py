"""scripts/nba_s_starters: the starters and the first quarter
(docs/nba_search_starters.md). Every rule is pinned on small hand-built or
synthetic games by its outcome; each was watched failing once with its rule
broken. No real price is read and no real bet is graded."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import models.nba_total_luck as tl
from models import nba_book_numbers as NB
from scripts import nba_game2_luck as L
from scripts import nba_game2_projection as P
from scripts import nba_game2_verdict as V
from scripts import nba_game5 as G5
from scripts import nba_game_harness as H
from scripts import nba_s_starters as S


@pytest.fixture(scope="module")
def ran():
    return S.synthetic_run(n_placebo=2)


# ── the registered cells ────────────────────────────────────────────────────

def test_the_search_registers_32_cells_and_no_moneyline():
    specs = S.cell_specs()
    assert len(specs) == S.EXPECTED_CELLS == 32
    assert {m for m, *_ in specs} == {"spreads_q1", "totals_q1", "spreads_h1", "totals_h1"}
    assert S.CUTS["spreads_q1"] == S.CUTS["totals_q1"] == (0.25, 0.5, 0.75, 1.0)
    assert S.CUTS["spreads_h1"] == S.CUTS["totals_h1"] == (0.5, 1.0, 1.5, 2.0)
    assert S.SIDES["totals_h1"] == ("over", "under") and S.SIDES["spreads_q1"] == ("home", "away")
    assert S.GRADED == (2024, 2025, 2026)


def test_every_cell_and_control_runs_through_the_harness_and_every_market_bets(ran):
    assert len(ran["rows"]) == len(ran["control"]) == 32
    for rows, fam in ((ran["rows"], "S1"), (ran["control"], "S1_league")):
        t = pd.DataFrame(rows)
        assert set(t["family"]) == {fam}
        got = t[t["cut_index"] == 0].groupby("market")["pool_n"].sum()
        assert set(got.index) == set(S.MARKETS) and (got > 0).all(), got.to_dict()
        assert {f"band{i}_n" for i in range(5)} <= set(t.columns)


def test_a_synthetic_world_without_a_market_this_search_bets_is_refused():
    w = G5.synthetic_world(days=30)
    w["pe"] = w["pe"][w["pe"]["market"] != "totals_h1"].reset_index(drop=True)
    with pytest.raises(AssertionError, match="lacks a market"):
        S.synthetic_run(w, n_placebo=0)


# ── impossible numbers ──────────────────────────────────────────────────────

@pytest.mark.parametrize("market,line,keep", [
    ("totals_q1", 57.5, True), ("totals_q1", 9.5, False), ("totals_q1", 113.5, False),
    ("totals_h1", 114.5, True), ("totals_h1", 57.5, False), ("totals_h1", 228.5, False),
    ("totals", 228.5, True), ("totals", 107.5, False), ("totals", 57.5, False),
    ("spreads_q1", -5.5, True), ("spreads_q1", -22.5, False),
    ("spreads_h1", 13.0, True), ("spreads_h1", 30.5, False),
    ("spreads", -24.5, True), ("spreads", 57.5, False)])
def test_a_number_no_board_could_hang_is_dropped_and_counted(market, line, keep):
    q = pd.DataFrame({"market": [market], "line": [line], "price_a": [-110.0], "price_b": [-110.0]})
    got, dropped = S.drop_impossible(q)
    assert (len(got) == 1) is keep
    assert dropped == ({} if keep else {market: 1})


def test_a_moneyline_has_no_number_to_drop():
    q = pd.DataFrame({"market": ["h2h"], "line": [np.nan], "price_a": [-110.0], "price_b": [-110.0]})
    assert len(S.drop_impossible(q)[0]) == 1


def test_a_main_number_priced_past_the_limit_is_not_a_main_number():
    v = pd.DataFrame({"price_a": [-110.0, -600.0, 145.0], "price_b": [-110.0, 400.0, -200.0]})
    got, n = S.drop_unpriceable(v)
    assert n == 1 and got["price_a"].tolist() == [-110.0, 145.0]


# ── minutes from the lineup segments ────────────────────────────────────────

def _seg(game, period, sec, home, away, n_home=5, n_away=5, season_type=2, hteam="HHH", ateam="AAA"):
    return {"game_id": game, "season_type": season_type, "period": period, "duration_s": sec,
            "home_team": hteam, "away_team": ateam, "home_player_ids": home, "away_player_ids": away,
            "n_home": n_home, "n_away": n_away}


H5, H5B = [f"{i}" for i in range(1, 6)], ["1", "2", "3", "4", "6"]
A5 = [f"{i}" for i in range(11, 16)]


def test_period_minutes_add_the_first_two_periods_five_a_side_regular_season_only():
    s = pd.DataFrame([
        _seg("g", 1, 420.0, H5, A5), _seg("g", 1, 300.0, H5B, A5), _seg("g", 2, 720.0, H5B, A5),
        _seg("g", 3, 720.0, H5, A5),                           # the third quarter counts nowhere
        _seg("g", 1, 60.0, H5, A5, n_home=4),                  # not five a side
        _seg("g", 1, 60.0, H5, A5, season_type=3)])            # a playoff segment
    m = S.period_minutes(s).set_index(["team", "player_id"])
    assert m.loc[("HHH", "1"), "q1"] == pytest.approx(12.0) and m.loc[("HHH", "1"), "h1"] == pytest.approx(24.0)
    assert m.loc[("HHH", "5"), "q1"] == pytest.approx(7.0) and m.loc[("HHH", "5"), "h1"] == pytest.approx(7.0)
    assert m.loc[("HHH", "6"), "q1"] == pytest.approx(5.0) and m.loc[("HHH", "6"), "h1"] == pytest.approx(17.0)
    assert m.loc[("AAA", "11"), "h1"] == pytest.approx(24.0)


def _panel(rows):
    return pd.DataFrame(rows, columns=["game_id", "team", "player_id", "day", "played"])


def _pm(rows):
    """Minutes per player; team-games are filled to 60 and 120 by a made-up teammate."""
    t = pd.DataFrame(rows, columns=["game_id", "team", "player_id", "q1", "h1"])
    fill = t.groupby(["game_id", "team"], as_index=False)[["q1", "h1"]].sum()
    fill = fill.assign(player_id="rest", q1=60.0 - fill["q1"], h1=120.0 - fill["h1"])
    return pd.concat([t, fill], ignore_index=True)


def test_a_game_never_counts_in_its_own_minutes():
    panel = _panel([("a", "T", "1", 10, True), ("b", "T", "1", 20, True), ("c", "T", "1", 30, True)])
    pm = _pm([("a", "T", "1", 10.0, 20.0), ("b", "T", "1", 10.0, 20.0), ("c", "T", "1", 1.0, 2.0)])
    last = P.Last(S.period_history(panel, pm, 3.0), "player_id", ["m_q1", "m_h1"])
    q = pd.DataFrame({"player_id": ["1"], "day": [30]})
    got = last.asof(q).iloc[0]
    # the third game (1 minute) is on the target date and not read
    assert got["m_q1"] == pytest.approx(10.0) and got["m_h1"] == pytest.approx(20.0)
    later = last.asof(pd.DataFrame({"player_id": ["1"], "day": [31]})).iloc[0]
    assert later["m_q1"] < 10.0


def test_only_games_he_played_count_and_sitting_out_the_period_counts_zero():
    panel = _panel([("a", "T", "1", 10, True), ("b", "T", "1", 20, False), ("c", "T", "1", 30, True)])
    pm = _pm([("a", "T", "1", 12.0, 24.0), ("b", "T", "2", 5.0, 5.0), ("c", "T", "2", 12.0, 24.0)])
    h = S.period_history(panel, pm, 3.0)
    # a game he missed is no reading; game c he played and is not in the segments' first half: zero
    assert len(h) == 2
    assert h["m_q1"].iloc[0] == pytest.approx(12.0) and 0.0 < h["m_q1"].iloc[1] < 12.0


def test_a_team_game_whose_segments_do_not_fill_the_period_gives_no_reading():
    panel = _panel([("a", "T", "1", 10, True), ("b", "T", "1", 20, True)])
    pm = pd.concat([_pm([("a", "T", "1", 12.0, 24.0)]),
                    pd.DataFrame({"game_id": ["b"], "team": ["T"], "player_id": ["1"], "q1": [1.0], "h1": [1.0]})],
                   ignore_index=True)
    h = S.period_history(panel, pm, 3.0)
    assert h["m_q1"].tolist() == pytest.approx([12.0, 12.0])     # not pulled toward 1 minute or 0


# ── the tiny world: the engine's own functions, two teams, two seasons ───────

def _games(n=8, seasons=(2020, 2021)):
    rows = []
    for s in seasons:
        for i in range(n):
            day = pd.Timestamp(f"{s - 1}-12-01") + pd.Timedelta(days=2 * i)
            home, away = ("AAA", "BBB") if i % 2 == 0 else ("BBB", "AAA")
            rows.append({"game_id": f"G{s}_{i}", "season": s, "game_date": day.strftime("%Y-%m-%d"),
                         "tip": (day + pd.Timedelta(hours=24)).tz_localize("UTC"),
                         "home_team": home, "away_team": away, "home_score": 110 + i, "away_score": 100 + (i % 3)})
    return pd.DataFrame(rows)


def _box(games):
    adv, log = [], []
    for _, g in games.iterrows():
        for team in (g.home_team, g.away_team):
            for j in range(8):
                pid = f"{team[0]}{j}"
                adv.append({"game_id": g.game_id, "player_id": pid, "team": team, "is_starter": int(j < 5),
                            "played": True, "minutes_exact": 40.0 if j < 5 else 40.0 / 3.0,
                            "possessions": 83.0 if j < 5 else 28.0, "fouls": 2.0})
                log.append({"game_id": g.game_id, "player_id": pid, "points": (30.0 if j < 5 else 3.0),
                            "offensive_reb": 1.0, "defensive_reb": 4.0, "assists": 3.0, "steals": 1.0,
                            "blocks": 0.5, "turnovers": 2.0, "fg_att": 14.0, "fg3_att": 5.0, "ft_att": 4.0})
    return pd.DataFrame(adv), pd.DataFrame(log)


def _inj(rows=()):
    return pd.DataFrame(list(rows), columns=["report_ts", "game_id", "team", "player_id", "player_name", "status", "season"])


def _tiny(inj=None, cap=44.0, rapm=None):
    """Five starters on for 11 of the first quarter's 12 minutes and 21 of the first half's 24, against 40 of
    the game's 48; a three-man bench the rest."""
    g = _games()
    adv, log = _box(g)
    ina = pd.DataFrame(columns=["game_id", "team", "player_id"])
    w = P.build_world(g, adv, log, ina, _inj() if inj is None else inj)
    rows = []
    for _, r in g.iterrows():
        for team in (r.home_team, r.away_team):
            for j in range(8):
                q = 11.0 if j < 5 else 5.0 / 3.0
                rows.append({"game_id": r.game_id, "team": team, "player_id": f"{team[0]}{j}",
                             "q1": q, "h1": 21.0 if j < 5 else 5.0})
    pm = pd.DataFrame(rows)
    st = P.build_state(w, {"hl": 90.0, "k": 300.0, "hl_lg": 30.0, "min_hl": 3.0, "hl_pace": 60.0})
    # made-up coefficients: 16 team-games cannot fit a box model, and a rating of NaN sums to a team of 0,
    # which would pass every comparison below without testing anything
    F = len(P.FEATURES)
    box = {"c": 0.5, "h": 2.5, "bo": np.arange(1, F + 1) * 0.01, "bd": np.arange(F, 0, -1) * 0.005}
    play = P.fit_play(pd.DataFrame(columns=["season", "bucket", "status", "role", "played"]), 2021)
    model = P.Model(season=2021, box=box, play=play, cap=cap, st=st, rapm=rapm)
    last = P.Last(S.period_history(w.panel, pm, 3.0), "player_id", ["m_q1", "m_h1"])
    gm = w.games[w.games["season"] == 2021].iloc[2:].assign(T=lambda d: d["tip"] - pd.Timedelta(hours=1))
    return w, st, model, gm, last


def test_expected_minutes_fill_60_and_120_and_the_full_game_is_the_engines():
    w, st, model, gm, last = _tiny()
    pr = S.player_rows(w, st, model, gm, last)
    t = pr.groupby(["game_id", "team"])[["min_q1", "min_h1", "min_fg"]].sum()
    assert t["min_q1"].to_numpy() == pytest.approx(60.0) and t["min_h1"].to_numpy() == pytest.approx(120.0)
    assert t["min_fg"].to_numpy() == pytest.approx(240.0)
    assert pr["min_q1"].max() <= 12.0 + 1e-6 and pr["min_h1"].max() <= 24.0 + 1e-6


def test_the_lab_measures_the_tilt_against_the_engines_own_team_rating_and_pace():
    # the cap binds (a starter's 40 minutes against 36) and the segment ratings move every starter
    day0 = int(P.to_day(_games()["game_date"]).min())
    rapm = pd.DataFrame({"refit_day": day0, "player_id": ["A0", "A1", "B0", "B2"], "do": [2.0, -1.0, 1.5, 0.5],
                         "dd": [1.0, 0.5, -1.0, 2.0]})
    w, st, model, gm, last = _tiny(cap=36.0, rapm=rapm)

    class TwoPaces:                                         # both teams of a game share its possessions, so
        def asof(self, q):                                  # a real history cannot tell them apart
            return pd.DataFrame({"pw": np.where(q["team"] == "AAA", 110.0, 90.0), "one": 1.0}, index=q.index)
    st.team_pace = TwoPaces()
    pr = S.player_rows(w, st, model, gm, last)
    assert pr["min_fg"].max() == pytest.approx(36.0)        # the cap is reached: the check below reads it
    plain = P.project(w, st, P.Model(season=2021, box=model.box, play=model.play, cap=36.0, st=st), gm)
    fr = S.game_frame(w, st, model, gm, pr).set_index("game_id")
    pj = P.project(w, st, model, gm).set_index("game_id").loc[fr.index]
    assert np.abs(pj["O_h"]).min() > 0.1 and np.abs(pj["D_a"]).min() > 0.1          # real numbers, not a sum of NaN
    assert not np.allclose(pj["O_h"], plain.set_index("game_id").loc[fr.index, "O_h"])      # the segments reach it
    for a, b in (("O_fg_h", "O_h"), ("D_fg_h", "D_h"), ("O_fg_a", "O_a"), ("D_fg_a", "D_a")):
        assert fr[a].to_numpy(float) == pytest.approx(pj[b].to_numpy(float))
    assert fr["pace"].to_numpy(float) == pytest.approx(
        (pj["pace_t_h"] * pj["pace_t_a"] / pj["pace_lg"]).to_numpy(float))


def test_nobody_is_rescaled_past_the_period_when_starters_are_out():
    g = _games()
    at = g[g["game_id"] == "G2021_2"].iloc[0]["tip"] - pd.Timedelta(hours=3)
    # three of AAA's five starters out: unchecked, the other two would scale to about 24 of 12 minutes
    inj = _inj([(at, "G2021_2", "AAA", f"A{j}", "x", "Out", 2021) for j in range(3)])
    w, st, model, gm, last = _tiny(inj)
    pr = S.player_rows(w, st, model, gm, last)
    x = pr[(pr["game_id"] == "G2021_2") & (pr["team"] == "AAA")]
    assert x["min_q1"].max() == pytest.approx(12.0) and x["min_q1"].sum() == pytest.approx(60.0)
    assert x["min_h1"].max() == pytest.approx(24.0) and x["min_h1"].sum() == pytest.approx(120.0)


def test_a_starters_first_quarter_weights_sum_to_five_players_so_the_tilt_is_a_reweighting():
    w, st, model, gm, last = _tiny()
    pr = S.player_rows(w, st, model, gm, last)
    a = pr.assign(o=1.0, d=1.0)
    t = S.team_ratings(a)
    for c in ("O_fg", "O_q1", "O_h1", "D_fg", "D_q1", "D_h1"):
        assert t[c].to_numpy() == pytest.approx(5.0)


def test_in_a_world_with_real_ratings_the_starters_heavy_first_quarter_shows_as_a_tilt():
    w, st, model, gm, last = _tiny()
    pr = S.player_rows(w, st, model, gm, last)
    assert pr["o"].notna().all() and pr["o"].nunique() > 1
    fr = S.game_frame(w, st, model, gm, pr)
    assert (fr["O_q1_h"] != fr["O_fg_h"]).all() and fr["ok"].all()
    x = S.tilt_points(fr)
    assert np.isfinite(x[["xm_q1", "xt_q1", "xm_h1", "xt_h1"]].to_numpy()).all()
    assert np.abs(x["xt_q1"]).min() > 0
    # starters take 55 of the quarter's 60 minutes and 105 of the half's 120 against 200 of the game's 240:
    # rate them above the bench and both periods lean their way
    good = pr.assign(o=np.where(pr["player_id"].str[1].astype(int) < 5, 3.0, -3.0))
    t = S.team_ratings(good)
    assert (t["O_q1"] > t["O_fg"]).all() and (t["O_h1"] > t["O_fg"]).all()


def test_the_better_starters_lift_the_first_quarter_rating_above_the_full_game():
    # two players: the good one plays more of the quarter than of the game
    pr = pd.DataFrame({"game_id": "g", "team": "T", "is_home": 1.0, "player_id": ["a", "b"], "o": [4.0, -4.0],
                       "d": [2.0, -2.0], "min_fg": [120.0, 120.0], "min_q1": [45.0, 15.0], "min_h1": [60.0, 60.0]})
    t = S.team_ratings(pr).iloc[0]
    assert t["O_fg"] == pytest.approx(0.0) and t["O_q1"] == pytest.approx((45.0 * 4.0 - 15.0 * 4.0) / 12.0)
    assert t["D_q1"] == pytest.approx((45.0 * 2.0 - 15.0 * 2.0) / 12.0) and t["O_h1"] == pytest.approx(0.0)


def test_out_is_zero_minutes_and_his_first_quarter_goes_to_the_others():
    g = _games()
    at = (g[g["game_id"] == "G2021_2"].iloc[0]["tip"] - pd.Timedelta(hours=3))
    inj = _inj([(at, "G2021_2", "AAA", "A0", "A Zero", "Out", 2021)])
    w, st, model, gm, last = _tiny(inj)
    pr = S.player_rows(w, st, model, gm, last)
    x = pr[(pr["game_id"] == "G2021_2") & (pr["team"] == "AAA")].set_index("player_id")
    assert x.loc["A0", "p_play"] == 0.0 and x.loc["A0", "min_q1"] == 0.0 and x.loc["A0", "min_fg"] == 0.0
    assert x["min_q1"].sum() == pytest.approx(60.0)
    assert x.loc["A1", "min_q1"] > pr[(pr["game_id"] == "G2021_3") & (pr["player_id"] == "A1")]["min_q1"].iloc[0]


def test_a_report_printed_after_t_changes_nothing():
    g = _games()
    tip = g[g["game_id"] == "G2021_2"].iloc[0]["tip"]
    # T is tip - 1h; a report counts 30 minutes after its printed time
    inj = _inj([(tip - pd.Timedelta(minutes=45), "G2021_2", "AAA", "A0", "A Zero", "Out", 2021)])
    w, st, model, gm, last = _tiny(inj)
    pr = S.player_rows(w, st, model, gm, last)
    assert pr[(pr["game_id"] == "G2021_2") & (pr["player_id"] == "A0")]["status"].iloc[0] == "unlisted"


def test_a_players_own_game_box_never_reaches_the_tilt():
    w, st, model, gm, last = _tiny()
    a = S.game_frame(w, st, model, gm, S.player_rows(w, st, model, gm, last))
    # rewrite the target games' own minutes and box: every number at T stays
    ids = set(gm["game_id"].iloc[3:])
    w2 = P.World(games=w.games, panel=w.panel.copy(), inj=w.inj, stints=w.stints, tg=w.tg, seq=w.seq)
    own = w2.panel["game_id"] == "G2021_6"
    w2.panel.loc[own, ["pts", "minutes"]] = [99.0, 1.0]
    st2 = P.build_state(w2, st.hp)
    m2 = P.Model(season=2021, box=model.box, play=model.play, cap=model.cap, st=st2)
    g6 = gm[gm["game_id"] == "G2021_6"]
    b = S.game_frame(w2, st2, m2, g6, S.player_rows(w2, st2, m2, g6, last)).iloc[0]
    x = a[a["game_id"] == "G2021_6"].iloc[0]
    assert ids and abs(x["O_q1_h"]) > 0.1
    assert b["O_q1_h"] == pytest.approx(x["O_q1_h"]) and b["O_fg_a"] == pytest.approx(x["O_fg_a"])
    # the same rewrite on an earlier date does move it: the check can see a change
    w3 = P.World(games=w.games, panel=w.panel.copy(), inj=w.inj, stints=w.stints, tg=w.tg, seq=w.seq)
    w3.panel.loc[w3.panel["game_id"] == "G2021_5", ["pts"]] = [99.0]
    st3 = P.build_state(w3, st.hp)
    m3 = P.Model(season=2021, box=model.box, play=model.play, cap=model.cap, st=st3)
    c = S.game_frame(w3, st3, m3, g6, S.player_rows(w3, st3, m3, g6, last)).iloc[0]
    assert c["O_q1_h"] != pytest.approx(x["O_q1_h"])


# ── the tilt, beta, the projection, the gap ─────────────────────────────────

def _frame(**over):
    row = {"game_id": "g", "season": 2024, "ok": True, "pace": 100.0}
    for s in ("h", "a"):
        for c in ("O", "D"):
            for p in ("fg", "q1", "h1"):
                row[f"{c}_{p}_{s}"] = 0.0
    row.update(over)
    return pd.DataFrame([row])


def test_the_tilt_in_points_is_the_engines_efficiency_read_over_the_period():
    # home's offence tilts up 2 and defence up 1; away's offence up 3 and defence up 0.5
    f = _frame(O_q1_h=2.0, D_q1_h=1.0, O_q1_a=3.0, D_q1_a=0.5, O_h1_h=4.0)
    x = S.tilt_points(f).iloc[0]
    poss = 25.0
    # eff_h moves by tO_h - tD_a = 1.5; eff_a by tO_a - tD_h = 2
    assert x["xm_q1"] == pytest.approx((1.5 - 2.0) * poss / 100.0)
    assert x["xt_q1"] == pytest.approx((1.5 + 2.0) * poss / 100.0)
    assert x["xm_h1"] == pytest.approx(4.0 * 50.0 / 100.0) and x["xt_h1"] == pytest.approx(4.0 * 50.0 / 100.0)


def test_the_tilt_is_measured_against_the_full_game_rating_not_from_zero():
    f = _frame(O_q1_h=3.0, O_fg_h=3.0, D_q1_a=-2.0, D_fg_a=-2.0)
    x = S.tilt_points(f).iloc[0]
    assert x["xm_q1"] == pytest.approx(0.0) and x["xt_q1"] == pytest.approx(0.0)


def test_a_game_with_an_unrated_player_has_no_tilt():
    w, st, model, gm, last = _tiny()
    pr = S.player_rows(w, st, model, gm, last)
    pr.loc[(pr["game_id"] == "G2021_3") & (pr["player_id"] == "A1"), "o"] = np.nan
    fr = S.game_frame(w, st, model, gm, pr)
    assert not bool(fr.loc[fr["game_id"] == "G2021_3", "ok"].iloc[0])
    assert bool(fr.loc[fr["game_id"] == "G2021_4", "ok"].iloc[0])


def test_a_game_failing_the_guard_has_no_tilt():
    f = pd.concat([_frame(O_q1_h=2.0), _frame(game_id="h", ok=False, O_q1_h=2.0)], ignore_index=True)
    assert S.tilt_points(f)["game_id"].tolist() == ["g"]


def _out_tonight(game, players=("A0", "A1", "A2"), cap=40.13):
    """AAA at `game` with the listed players Out, known well before T. AAA is home in G2021_2 and away in G2021_3."""
    at = _games().set_index("game_id").loc[game, "tip"] - pd.Timedelta(hours=3)
    w, st, model, gm, last = _tiny(_inj([(at, game, "AAA", p, "x", "Out", 2021) for p in players]), cap=cap)
    pr = S.player_rows(w, st, model, gm, last)
    return S.game_frame(w, st, model, gm, pr).set_index("game_id"), pr


@pytest.mark.parametrize("game,side,other", [("G2021_2", "h", "G2021_3"), ("G2021_3", "a", "G2021_2")])
def test_a_team_down_to_five_players_fills_the_periods_but_not_the_game_and_has_no_tilt(game, side, other):
    # NBA_2021-12-31_MIA_HOU: five available players, each capped at 40.13 over the game but playing all of
    # both periods. The period ratings carry five players and the full-game rating 4.18, so the tilt is a
    # level error and not a change of who plays.
    fr, _ = _out_tonight(game)
    assert fr.loc[game, f"min_q1_{side}"] == pytest.approx(60.0) and fr.loc[game, f"min_h1_{side}"] == pytest.approx(120.0)
    assert fr.loc[game, f"min_fg_{side}"] == pytest.approx(5 * 40.13)      # the fault is really in this world
    assert not bool(fr.loc[game, "ok"])
    assert bool(fr.loc[other, "ok"])
    x = S.tilt_points(fr.reset_index())
    assert game not in set(x["game_id"]) and other in set(x["game_id"])


def test_a_team_with_six_players_fills_the_game_and_keeps_its_tilt():
    # one more player than the fault needs: 6 x 40.13 reaches 240, so nothing here is thrown away
    fr, _ = _out_tonight("G2021_2", players=("A0", "A1"))
    assert fr.loc["G2021_2", "min_fg_h"] == pytest.approx(240.0) and bool(fr.loc["G2021_2", "ok"])


@pytest.mark.parametrize("player,moved,ok", [("A0", -1.5, False), ("A0", 1.5, False), ("A0", -0.5, True), ("A0", 0.5, True),
                                             ("B0", -1.5, False), ("B0", 1.5, False), ("B0", -0.5, True)])
def test_full_game_minutes_more_than_a_minute_from_240_stop_the_tilt_on_either_team(player, moved, ok):
    # G2021_4: AAA home, BBB away. Only the full-game column moves, so only the full-game check can see it.
    w, st, model, gm, last = _tiny()
    pr = S.player_rows(w, st, model, gm, last)
    pr.loc[(pr["game_id"] == "G2021_4") & (pr["player_id"] == player), "min_fg"] += moved
    fr = S.game_frame(w, st, model, gm, pr).set_index("game_id")
    assert bool(fr.loc["G2021_4", "ok"]) is ok
    assert bool(fr.loc["G2021_5", "ok"])


def _fit_rows(n_per=120, seasons=(2021, 2022, 2023, 2024, 2025), slope=0.6, seed=4):
    rng = np.random.default_rng(seed)
    ids = [f"G{s}_{i}" for s in seasons for i in range(n_per)]
    season = np.repeat(seasons, n_per)
    n = len(ids)
    base = pd.DataFrame({"game_id": ids, "season": season})
    x = pd.DataFrame({"game_id": ids, "season": season})
    res = pd.DataFrame({"game_id": ids, "season": season})
    for p in ("q1", "h1"):
        base[f"margin_{p}"], base[f"total_{p}"] = rng.normal(1, 2, n), rng.normal(57, 2, n)
        x[f"xm_{p}"], x[f"xt_{p}"] = rng.normal(0, 1, n), rng.normal(0, 1, n)
        res[f"margin_{p}_r"] = base[f"margin_{p}"] + 3.0 + slope * x[f"xm_{p}"] + rng.normal(0, 0.2, n)
        res[f"total_{p}_r"] = base[f"total_{p}"] - 1.0 - slope * x[f"xt_{p}"] + rng.normal(0, 0.2, n)
    return base, x, res


def test_beta_recovers_a_planted_slope_keeps_its_sign_and_ignores_a_level_bias():
    b, t = S.fit_betas(*_fit_rows(), seasons=(2024, 2025, 2026))
    assert b[(2026, "spreads_q1")] == pytest.approx(0.6, abs=0.03)
    assert b[(2026, "totals_h1")] == pytest.approx(-0.6, abs=0.03)     # no floor at zero
    assert set(t["fit_seasons"]) == {"2021-2023", "2021-2024", "2021-2025"}


def test_beta_reads_no_game_of_its_own_season_or_a_later_one():
    base, x, res = _fit_rows()
    before, _ = S.fit_betas(base, x, res, seasons=(2024,))
    r2 = res.copy()
    late = r2["season"] >= 2024
    for c in [c for c in r2 if c.endswith("_r")]:
        r2.loc[late, c] = r2.loc[late, c] + 50.0 * x.loc[late, "xm_q1"]
    after, _ = S.fit_betas(base, x, r2, seasons=(2024,))
    assert before == after
    moved, _ = S.fit_betas(base, x, r2, seasons=(2025,))
    assert moved[(2025, "spreads_q1")] != before[(2024, "spreads_q1")]


def test_too_few_earlier_games_stop_the_fit():
    base, x, res = _fit_rows(n_per=50)
    with pytest.raises(RuntimeError, match="earlier games"):
        S.fit_betas(base, x, res, seasons=(2024,))


def test_the_projection_is_base_plus_each_seasons_own_beta_times_the_tilt_by_game_not_by_row():
    base = pd.DataFrame({"game_id": ["a", "b"], "season": [2024, 2025], "margin_q1": [1.0, 2.0], "total_q1": [57.0, 58.0],
                         "margin_h1": [2.0, 4.0], "total_h1": [114.0, 116.0]}, index=[7, 9])
    # the tilt frame comes in another order and with its own index
    x = pd.DataFrame({"game_id": ["b", "a"], "season": [2025, 2024], "xm_q1": [10.0, 1.0], "xt_q1": [20.0, 2.0],
                      "xm_h1": [30.0, 3.0], "xt_h1": [40.0, 4.0]}, index=[3, 4])
    betas = {(s, m): (0.5 if s == 2024 else 0.1) for s in (2024, 2025) for m in S.MARKETS}
    p = S.project_with_tilt(base, x, betas).set_index("game_id")
    assert p.loc["a", "margin_q1"] == pytest.approx(1.0 + 0.5 * 1.0)
    assert p.loc["b", "margin_q1"] == pytest.approx(2.0 + 0.1 * 10.0)
    assert p.loc["a", "total_h1"] == pytest.approx(114.0 + 0.5 * 4.0)
    assert p.loc["b", "tilt_totals_q1"] == pytest.approx(0.1 * 20.0)


def _dist():
    return H.ResidDist(np.random.default_rng(3).normal(0.0, 5.0, 2000), "test")


def test_the_gap_is_projected_minus_the_markets_fair_centre_on_the_home_number():
    # the book hangs home -2.5 at even money: the market's home margin centre is +2.5
    vis = pd.DataFrame({"game_id": ["g"], "season": [2024], "market": ["spreads_q1"], "book": ["pinnacle"],
                        "line": [-2.5], "price_a": [-110.0], "price_b": [-110.0], "coherent": [True]})
    fair = H.market_fair(vis, {(2024, "spreads_q1"): _dist()})
    assert fair["mu"].iloc[0] == pytest.approx(2.5, abs=0.05)
    proj = pd.DataFrame({"game_id": ["g"], "season": [2024], "margin_q1": [3.5]})
    s = pd.DataFrame({"game_id": ["g"], "market": ["spreads_q1"], "strength": [3.5 - fair["mu"].iloc[0]]})
    got = _gap_one(proj, fair)
    assert got == pytest.approx(s["strength"].iloc[0]) and got > 0
    off = pd.DataFrame({"game_id": ["g", "g"], "market": ["spreads_q1"] * 2, "side": ["home", "away"]})
    c = tl.side_strength(off, pd.DataFrame({"game_id": ["g"], "market": ["spreads_q1"], "strength": [got]}))
    assert c.set_index("side")["strength"].to_dict() == pytest.approx({"home": got, "away": -got})


def _gap_one(proj, fair):
    full = proj.assign(total_q1=np.nan, margin_h1=np.nan, total_h1=np.nan)
    return S.gap_frame(full, fair)["strength"].iloc[0]


def test_every_book_on_a_side_carries_the_same_gap_and_a_game_off_the_list_has_none(ran):
    c = ran["cands"]["totals_q1"]
    assert c.groupby(["game_id", "side"])["strength"].nunique().max() == 1
    assert set(c["game_id"]) <= set(ran["gap"]["game_id"])


def test_the_control_is_the_league_share_alone_and_the_cell_adds_the_tilt(ran):
    g = ran["gap"].set_index(["game_id", "market"])["strength"]
    c = ran["gap_control"].set_index(["game_id", "market"])["strength"]
    both = g.index.intersection(c.index)
    t = ran["proj"].melt(id_vars="game_id", value_vars=[f"tilt_{m}" for m in S.MARKETS])
    t = t.assign(market=t["variable"].str.replace("tilt_", "")).set_index(["game_id", "market"])["value"]
    assert (g[both] - c[both]).to_numpy() == pytest.approx(t.reindex(both).to_numpy())
    assert np.abs(t.reindex(both).to_numpy()).max() > 0


def test_near_t_changes_nothing_the_full_game_numbers_read(ran):
    data, times = ran["world"]["data"], ran["times"]
    a = G5.full_game_visible(data.quotes, times).sort_values(["game_id", "market", "book"]).reset_index(drop=True)
    b = G5.full_game_visible(S.near_t(data.quotes, times), times).sort_values(["game_id", "market", "book"]).reset_index(drop=True)
    assert len(a) and a[["game_id", "market", "book", "line"]].equals(b[["game_id", "market", "book", "line"]])


def test_near_t_keeps_every_fetch_of_the_last_hour_up_to_t_and_nothing_else():
    T = pd.Timestamp("2024-01-02 00:00", tz="UTC")
    ago = [-1, 0, 1, 5, 60, 61]                             # minutes before T; -1 is a minute after it
    q = pd.DataFrame({"game_id": "g", "market": "totals", "book": "fanduel", "line": 230.5, "price_a": -110.0,
                      "price_b": -110.0, "fetch_at": [T - pd.Timedelta(minutes=m) for m in ago]})
    got = S.near_t(q, pd.DataFrame({"game_id": ["g"], "T": [T]}))
    assert sorted(((T - got["fetch_at"]).dt.total_seconds() / 60.0).tolist()) == [0.0, 1.0, 5.0, 60.0]


# ── the placebo ─────────────────────────────────────────────────────────────

def _runs(n_games_per_date=4, dates=("2024-01-01", "2024-01-02"), seeds=(1, 2, 3)):
    ids = [f"{d}_{i}" for d in dates for i in range(n_games_per_date)]
    dd = pd.Series({g: g[:10] for g in ids})
    off = pd.DataFrame({"game_id": np.repeat(ids, 2), "market": "spreads_q1", "side": ["home", "away"] * len(ids),
                        "book": "fanduel", "line": -1.5, "price": -110.0, "p_win": 0.5, "p_push": 0.0})
    g = pd.DataFrame({"game_id": ids, "market": "spreads_q1", "strength": np.arange(len(ids), dtype=float)})
    return off, g, dd, seeds


def test_a_placebo_gap_stays_on_its_date_and_never_touches_an_offer():
    off, g, dates, seeds = _runs()
    runs = S.whole_gap_runs(off, g, dates, seeds)
    for s in seeds:
        c = runs.frame(s)
        home = c[c["side"] == "home"].set_index("game_id")["strength"]
        for d, ids in g.groupby(g["game_id"].str[:10])["game_id"]:
            assert sorted(home[list(ids)]) == sorted(g.set_index("game_id").loc[list(ids), "strength"])
        assert (c[c["side"] == "away"]["strength"].to_numpy() == -home.reindex(c[c["side"] == "away"]["game_id"]).to_numpy()).all()
        assert c[["line", "price", "book"]].equals(off[["line", "price", "book"]])
    assert not runs.frame(1)["strength"].equals(runs.frame(2)["strength"])


def test_the_same_seed_is_the_same_run_and_the_registered_seeds_are_1_to_200():
    off, g, dates, seeds = _runs()
    runs = S.whole_gap_runs(off, g, dates, seeds)
    assert runs.frame(2)["strength"].equals(runs.frame(2)["strength"])
    assert S.PLACEBO_SEEDS == tuple(range(1, 201)) and len(runs) == 3 and len(list(runs)) == 3


def test_a_game_alone_on_its_date_keeps_its_number_and_share_differs_says_so():
    off, g, dates, seeds = _runs(n_games_per_date=1, dates=("2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"))
    runs = S.whole_gap_runs(off, g, dates, seeds)
    assert runs.frame(1)[lambda c: c["side"] == "home"]["strength"].tolist() == [0.0, 1.0, 2.0, 3.0]
    cand = tl.side_strength(off, g)
    assert S.share_differs(cand, runs, "home", 1.0, 3)["share_differs"] == 0.0


def test_share_differs_is_high_when_a_game_has_partners_and_reads_the_ceiling():
    off, g, dates, seeds = _runs(n_games_per_date=10, dates=[f"2024-01-{d:02d}" for d in range(1, 11)],
                                 seeds=tuple(range(1, 11)))
    g = g.assign(strength=(g["game_id"].str[-1] == "0").astype(float))     # one game a night has a gap
    runs = S.whole_gap_runs(off, g, dates, seeds)
    d = S.share_differs(tl.side_strength(off, g), runs, "home", 1.0, 10)
    assert d["real_bets"] == 10 and d["share_differs"] > 0.7 and d["ceiling"] == pytest.approx(0.9)


def test_the_tilt_only_runs_keep_each_games_own_base_and_move_only_the_tilt():
    off, g, dates, seeds = _runs()
    part = pd.Series(np.linspace(-1.0, 1.0, len(g)), index=g["game_id"].to_numpy())
    runs = S.tilt_only_runs(off, g, part, dates, seeds)
    c = runs.frame(1)
    home = c[c["side"] == "home"].set_index("game_id")["strength"]
    base = g.set_index("game_id")["strength"] - part
    moved = (home - base).reindex(g["game_id"])
    for d, ids in g.groupby(g["game_id"].str[:10])["game_id"]:
        assert sorted(moved[list(ids)].round(9)) == sorted(part[list(ids)].round(9))
    assert np.abs(moved - part.reindex(moved.index)).max() > 0


def test_the_placebo_reaches_the_cells_as_exactly_the_runs_asked_for(ran):
    assert all(len(r["placebo_rois"]) == 2 for r in ran["rows"] + ran["control"])
    assert all(r["tilt_placebo_runs"] == 2 for r in ran["rows"])
    assert all("tilt_placebo_runs" not in r for r in ran["control"])


@pytest.mark.parametrize("market", ["spreads_q1", "totals_h1"])
def test_the_array_placebo_returns_what_run_cells_own_path_returns(ran, market):
    nm = ran["neutral"][ran["neutral"]["market"] == market]
    g = ran["gap"][ran["gap"]["market"] == market].reset_index(drop=True)
    seeds = (1, 2, 3)
    dates = S._dates(ran["dd"].games)
    slow = G5.run_market(ran["dd"], S.FAMILY, S.POINT, market, S.SIDES[market], S.CUTS[market], ran["cands"][market],
                         nm, S.whole_gap_runs(nm, g, dates, seeds), "strength", ran["choose"], ran["times"])
    numbered = nm[nm["game_id"].isin(set(g["game_id"]))]
    runs = S.whole_gap_runs(nm, g, dates, seeds)
    seen = 0
    for r in slow:
        fast = S.placebo_rois(runs, S.side_table(numbered, r["side"], ran["dd"].games), r["side"], r["cut"], S._row_seasons(r))
        assert len(fast) == 3 and np.allclose(fast, r["placebo_rois"], equal_nan=True)
        seen += int(np.isfinite(fast).any())
    assert seen >= 4                                        # not a comparison of empty runs


def test_a_run_with_no_bet_is_not_a_return_of_anything():
    runs = S.ShuffledGaps(pd.DataFrame({"game_id": ["a"], "side": ["home"]}), ["a"], [0.0], [0.0],
                          pd.Series({"a": "2024-01-01"}), (1,))
    table = pd.DataFrame({"game_id": ["a"], "season": [2024], "units": [1.0], "risk": [1.0]})
    assert np.isnan(S.placebo_rois(runs, table, "home", 1.0, (2024,))[0])
    assert S.placebo_rois(runs, table, "home", 0.0, (2024,)) == [1.0]
    assert np.isnan(S.placebo_rois(runs, table, "home", 0.0, (2025,))[0])     # outside the choosing seasons


def test_the_array_placebo_reads_the_cut_toward_the_cells_own_side():
    runs = S.ShuffledGaps(pd.DataFrame({"game_id": ["a"], "side": ["home"]}), ["a"], [0.0], [2.0],
                          pd.Series({"a": "2024-01-01"}), (1,))
    table = pd.DataFrame({"game_id": ["a"], "season": [2024], "units": [1.0], "risk": [1.0]})
    assert S.placebo_rois(runs, table, "home", 1.0, (2024,)) == [1.0]
    assert np.isnan(S.placebo_rois(runs, table, "away", 1.0, (2024,))[0])
    assert np.isnan(S.placebo_rois(runs, table, "under", 1.0, (2024,))[0])


# ── the verdict and the credit ──────────────────────────────────────────────

def _cell(k, fam="S1", **over):
    row = {"family": fam, "point": "D", "market": "totals_q1", "side": "over", "cut_index": k,
           "cut": (0.25, 0.5, 0.75, 1.0)[k], "pool_n": 600, "pool_units": 40.0, "pool_roi": 0.06,
           "pool_ci95_lo": 0.01, "pool_ci95_hi": 0.11, "pool_seasons_counted": 3, "pool_seasons_positive": 3,
           "pool_share_home": np.nan, "pool_share_fav": np.nan, "pool_share_over": 1.0, "blind_pool_over": -0.04,
           "blind_pool_under": -0.03, "roi_choose": 0.06, "placebo_rois": [0.0] * 200, "band_slots": 5}
    for i in range(5):
        row.update({f"band{i}_n": 100, f"band{i}_roi": 0.05, f"band{i}_units": 5.0, f"band{i}_lo": 0.0, f"band{i}_hi": 1.0})
    row.update(over)
    return row


def _spread_cell(k, fam="S1", **over):
    """A cell on a market where credit is possible, with the blind bets a spread row carries."""
    row = {"market": "spreads_q1", "side": "home", "pool_share_over": np.nan, "pool_share_home": 1.0,
           "blind_pool_home": -0.04, "blind_pool_away": -0.03, **over}
    return _cell(k, fam=fam, **row)


def test_the_verdicts_own_call_judges_the_control_like_a_cell():
    cells = pd.DataFrame([_cell(k) for k in range(3)] + [_cell(k, fam=S.CONTROL) for k in range(3)])
    v = V.house_verdict_bands(cells)
    assert set(v["family"]) == {"S1", "S1_league"} and bool(v["house5_passes"].all())
    # and a control with the wrong placebo count stops it, as a cell's would
    bad = cells.copy()
    bad.loc[bad["family"] == S.CONTROL, "placebo_rois"] = pd.Series([[0.0] * 20] * 3, index=bad.index[3:])
    with pytest.raises(ValueError, match="200"):
        V.house_verdict_bands(bad)


@pytest.mark.parametrize("control_roi,credited", [(0.08, False), (0.06, False), (0.04, True), (np.nan, True)])
def test_a_cell_counts_for_the_starters_only_when_it_passes_and_beats_its_control(control_roi, credited):
    cells = pd.DataFrame([_spread_cell(k) for k in range(3)]
                         + [_spread_cell(k, fam=S.CONTROL, pool_roi=control_roi) for k in range(3)])
    c = S.credit_table(cells)
    m = c[(c["family"] == "S1") & (c["cut_index"] == 1)].iloc[0]
    assert bool(m["house5_passes"]) is True and bool(m["credited"]) is credited


def test_a_cell_that_fails_a_bar_is_never_credited():
    cells = pd.DataFrame([_spread_cell(k, pool_ci95_lo=-0.01) for k in range(3)]
                         + [_spread_cell(k, fam=S.CONTROL, pool_roi=-0.5) for k in range(3)])
    c = S.credit_table(cells)
    assert not c.loc[c["family"] == "S1", "credited"].any()
    assert bool(c.loc[c["family"] == "S1", "beats_control"].all())          # it fails on the bar, not on the control


def _credit_cells(total_market, control_roi=0.04):
    """A total cell and a spread cell, each passing every bar and beating its control."""
    tot = dict(market=total_market, cut=None)
    rows = []
    for k in range(3):
        rows += [_cell(k, **_cuts(tot, k)), _cell(k, fam=S.CONTROL, pool_roi=control_roi, **_cuts(tot, k)),
                 _spread_cell(k), _spread_cell(k, fam=S.CONTROL, pool_roi=control_roi)]
    return pd.DataFrame(rows)


def _cuts(tot, k):
    return {**tot, "cut": S.CUTS[tot["market"]][k]}


@pytest.mark.parametrize("market", ["totals_q1", "totals_h1"])
@pytest.mark.parametrize("control_roi", [0.04, np.nan])
def test_a_total_cell_earns_no_credit_for_the_starters_even_when_it_beats_its_control(market, control_roi):
    # section 8: a total cell's bets are nearly all its control's, so beating the control there says nothing
    # about the starters. The spread cell beside it, with the same numbers, is the proof the rule is what stops it.
    c = S.credit_table(_credit_cells(market, control_roi))
    s1 = c[c["family"] == "S1"]
    tot, spr = s1[s1["market"] == market], s1[s1["market"] == "spreads_q1"]
    assert len(tot) == 3 and bool(tot["house5_passes"].all()) and bool(tot["beats_control"].all())
    assert not tot["credited"].any()
    assert bool(spr["credited"].all())
    assert not tot["creditable"].any() and bool(spr["creditable"].all())
    assert set(tot["counts_for"]) == {S.LEAGUE_IDEA} and set(spr["counts_for"]) == {S.STARTERS_IDEA}


def test_the_control_is_read_as_the_league_share_idea_and_a_failing_cell_as_no_one():
    cells = _credit_cells("totals_q1")
    c = S.credit_table(cells)
    k = c[c["family"] == S.CONTROL]
    assert set(k["counts_for"]) == {S.LEAGUE_IDEA}
    assert bool(k["creditable"].all()) and bool(k["credited"].all())        # the rule reaches the S1 cells only
    failing = S.credit_table(cells.assign(pool_ci95_lo=-0.01))
    assert set(failing["counts_for"]) == {""} and not failing["credited"].any()


def test_a_spread_cell_that_passes_and_loses_to_its_control_is_not_the_starters():
    cells = pd.DataFrame([_spread_cell(k) for k in range(3)] + [_spread_cell(k, fam=S.CONTROL, pool_roi=0.08) for k in range(3)])
    s1 = S.credit_table(cells).query("family == 'S1'")
    assert bool(s1["house5_passes"].all()) and not s1["credited"].any()
    assert S.STARTERS_IDEA not in set(s1["counts_for"]) and S.LEAGUE_IDEA not in set(s1["counts_for"])


def test_the_credit_report_gives_a_total_pass_to_the_league_share_idea(monkeypatch, capsys):
    cells = _credit_cells("totals_h1")
    # one spread cell fails a bar, so the three counts below are three different numbers
    one = (cells["family"] == "S1") & (cells["market"] == "spreads_q1") & (cells["cut_index"] == 0)
    cells.loc[one, "pool_ci95_lo"] = -0.01
    monkeypatch.setattr(V, "load_cells", lambda results: cells)
    S.credit(Path("unused"))
    out = capsys.readouterr().out
    assert "S1: 6 cells, 5 pass, 2 credited" in out
    assert "3 total cells pass and read as the league-share idea's" in out
    assert S.LEAGUE_IDEA in out and S.STARTERS_IDEA in out


# ── nothing here grades a real bet before --full ────────────────────────────

def test_the_counts_the_placebo_share_and_the_extremes_never_call_the_grader(ran, monkeypatch, capsys):
    prep = _prep(ran)

    def boom(*a, **k):
        raise AssertionError("a count graded a bet")
    monkeypatch.setattr(H, "grade", boom)
    S.counts(prep)
    S.placebo_null(prep, n_runs=2)
    S.extremes(prep)
    assert "EXTREMES" in capsys.readouterr().out


def test_the_counts_say_how_many_bets_are_only_the_cells_and_only_the_controls(ran):
    t = S.counts(_prep(ran))["cells"]
    assert (t["bets_pooled"] - t["only_cell"] == t["control_bets"] - t["only_control"]).all()      # both are the bets in both
    has = t["bets_pooled"] > 0
    both = t.loc[has, "bets_pooled"] - t.loc[has, "only_cell"]
    assert (t.loc[has, "share_also_control"] * t.loc[has, "bets_pooled"]).to_numpy() == pytest.approx(both.to_numpy())
    assert (t["only_cell"] > 0).any() and (t["only_control"] > 0).any()      # the synthetic tilt really moves bets


def _prep(ran):
    frames = {"games_T": ran["gap"][["game_id"]].drop_duplicates().assign(ok=True),
              "players_T": ran["gap"][["game_id"]].drop_duplicates().assign(covered=True)}
    vis = ran["dd"].quotes
    return {"dd": ran["dd"], "gap": ran["gap"], "gap_control": ran["gap_control"], "neutral": ran["neutral"],
            "times": ran["times"], "full": ran["base"], "frames": frames, "proj": ran["proj"], "fair": ran["fair"],
            "x": ran["x"],
            "vis": vis, "vis_f": vis, "vis_r": vis, "pe_raw": vis, "q_raw": vis, "dropped": {},
            "graded": (2024, 2025, 2026), "seconds": 1.0}


def test_the_clock_grades_only_made_up_results(ran, monkeypatch):
    prep = _prep(ran)
    prep["graded"] = tuple(sorted({int(s) for s in ran["dd"].games["season"]}))
    real = ran["dd"].games.set_index("game_id")["home_q1"]
    grade = H.grade
    seen = []

    def spy(b, games):
        seen.append(1)
        same = (games.set_index("game_id")["home_q1"].reindex(real.index).to_numpy() == real.to_numpy()).mean()
        assert same < 0.2, "the clock read real scores"
        return grade(b, games)
    monkeypatch.setattr(H, "grade", spy)
    monkeypatch.setenv("NBA_GAME2_BETS", "should-not-be-written")
    got = S.time_cells(prep)
    assert seen and got["projected_full_minutes"] > 0
    assert not __import__("pathlib").Path("should-not-be-written").exists()


# ── what the run writes ─────────────────────────────────────────────────────

def test_the_bets_file_holds_no_column_parquet_cannot_store(ran, monkeypatch, tmp_path):
    bets = tmp_path / "bets"
    monkeypatch.setenv("NBA_GAME2_BETS", str(bets))
    m = "spreads_q1"
    nm = ran["neutral"][ran["neutral"]["market"] == m]
    assert nm["sigma"].map(lambda v: isinstance(v, H.ResidDist)).any()      # the frame holds the shape parquet refuses
    G5.run_market(ran["dd"], S.FAMILY, S.POINT, m, ("home",), S.CUTS[m], ran["cands"][m], nm, None, "strength",
                  ran["choose"], ran["times"])
    files = list(bets.glob("*.parquet"))
    assert files
    back = pd.read_parquet(files[0])
    assert len(back) and "sigma" not in back and "units" in back
    for c in back.select_dtypes(include="object"):
        assert back[c].map(lambda v: isinstance(v, str)).all(), c


def test_the_cell_tables_round_trip_with_the_placebo_lists_and_the_tilt_columns(ran, tmp_path):
    L.write_cells(ran["rows"], tmp_path / "cells_S1.parquet")
    L.write_cells(ran["control"], tmp_path / "cells_S1_league.parquet")
    back = V.load_cells(tmp_path)
    assert len(back) == 64 and len(back["placebo_rois"].iloc[0]) == 2
    assert back.loc[back["family"] == "S1", "tilt_placebo_runs"].notna().all()


def test_the_synthetic_checks_write_no_bets_into_a_graded_runs_folder(ran, monkeypatch, tmp_path):
    bets = tmp_path / "bets"
    monkeypatch.setenv("NBA_GAME2_BETS", str(bets))
    env = {}

    def stub(*a, **k):
        env["during"] = __import__("os").environ.get("NBA_GAME2_BETS")
        return ran
    monkeypatch.setattr(S, "synthetic_run", stub)
    S.synthetic_checks(n_placebo=2)
    assert env["during"] is None and __import__("os").environ["NBA_GAME2_BETS"] == str(bets)


def test_full_refuses_without_the_go_a_results_folder_or_a_bets_folder_before_reading(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise AssertionError("read data before refusing")
    monkeypatch.setattr(H, "load", boom)
    monkeypatch.setattr(H, "load_per_event", boom)
    monkeypatch.setattr(S, "synthetic_run", boom)
    for f in (P.LEDGER_FILE, P.STINTS_FILE):
        (tmp_path / f).write_bytes(b"")
    monkeypatch.delenv("NBA_GAME2_GO", raising=False)
    monkeypatch.setenv("NBA_GAME2_RESULTS", str(tmp_path / "out"))
    monkeypatch.setenv("NBA_GAME2_BETS", str(tmp_path / "bets"))
    with pytest.raises(SystemExit):
        S.full(tmp_path, out=tmp_path / "out")
    assert not (tmp_path / "out").exists()
    monkeypatch.setenv("NBA_GAME2_GO", "1")
    assert S.refuse_full(tmp_path) == []
    for env in ("NBA_GAME2_RESULTS", "NBA_GAME2_BETS"):
        monkeypatch.delenv(env)
        assert any(env in w for w in S.refuse_full(tmp_path))
        monkeypatch.setenv(env, str(tmp_path / env))
    (tmp_path / P.STINTS_FILE).unlink()
    assert any("nba_stints" in w for w in S.refuse_full(tmp_path))


def test_full_end_to_end_on_made_up_games_writes_what_the_verdict_and_the_credit_read(ran, monkeypatch, tmp_path, capsys):
    prep = {**_prep(ran), "fit": ran["fit"], "betas": ran["betas"], "seconds": 1.0}
    prep["vis"] = ran["dd"].quotes
    out, bets = tmp_path / "out", tmp_path / "bets"
    monkeypatch.setenv("NBA_GAME2_GO", "1")
    monkeypatch.setenv("NBA_GAME2_RESULTS", str(out))
    monkeypatch.setenv("NBA_GAME2_BETS", str(bets))
    cache = tmp_path / "cache"
    cache.mkdir()
    for f in (P.LEDGER_FILE, P.STINTS_FILE):
        (cache / f).write_bytes(b"")
    monkeypatch.setattr(S, "synthetic_checks", lambda *a, **k: None)
    monkeypatch.setattr(S, "prepare", lambda *a, **k: prep)
    monkeypatch.setattr(S, "beta_mismatch", lambda *a, **k: [])
    S.full(cache)
    cells = V.load_cells(out)
    assert sorted(cells["family"].value_counts().to_dict().items()) == [("S1", 32), ("S1_league", 32)]
    assert all(len(v) == 200 for v in cells["placebo_rois"])
    v = V.house_verdict_bands(cells)                        # the script's own default call
    assert len(v) == 64
    S.credit(out)
    assert "credited" in capsys.readouterr().out
    written = list(bets.glob("*.parquet"))
    assert written and all("sigma" not in pd.read_parquet(f).columns for f in written[:3])
    assert (out / "gaps_S1.parquet").exists() and (out / "betas_S1.parquet").exists()


def test_a_refit_other_than_the_registered_betas_stops_the_run():
    reg = {(2024, "spreads_q1"): 0.5}
    assert S.beta_mismatch({(2024, "spreads_q1"): 0.5}, reg) == []
    assert S.beta_mismatch({(2024, "spreads_q1"): 0.5 + 1e-3}, reg)
    assert S.beta_mismatch({(2025, "spreads_q1"): 0.5}, reg)
    assert S.beta_mismatch({(2024, "spreads_q1"): 0.5}, {})


def test_a_saved_engine_is_read_when_its_fingerprint_matches_and_rebuilt_when_not(monkeypatch, tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    for f in ("nba_games.parquet", "nba_player_game_adv.parquet", "nba_player_game_log.parquet",
              "nba_game_inactives.parquet", "nba_injury_report.parquet", "nba_stints.parquet"):
        (cache / f).write_bytes(b"x")
    built = []
    monkeypatch.setattr(S, "build_engine", lambda w, say=None: built.append(1) or {"models": {}, "first_hp": {"min_hl": 3.0}})
    scratch = tmp_path / "scratch"
    S.engine(cache, None, scratch, lambda *_: None)
    S.engine(cache, None, scratch, lambda *_: None)
    assert len(built) == 1
    (cache / "nba_stints.parquet").write_bytes(b"xx")
    S.engine(cache, None, scratch, lambda *_: None)
    assert len(built) == 2


def test_neutral_prices_every_side_and_no_visible_rung_is_an_alternate(ran):
    # the offers read one number per book per game: the main rung the harness keeps
    v = NB.visible_numbers(ran["world"]["pe"][ran["world"]["pe"]["market"].isin(S.MARKETS)], ran["times"])
    assert v.groupby(["game_id", "market", "book"]).size().max() == 1
    assert set(ran["neutral"]["market"]) == set(S.MARKETS)


def test_saved_frames_built_by_other_code_do_not_pass_for_this_codes(monkeypatch, tmp_path):
    for f in S.ENGINE_FILES:
        (tmp_path / f).write_bytes(b"x")
    times = pd.DataFrame({"game_id": ["g"], "T": [pd.Timestamp("2024-01-02", tz="UTC")]})
    a = S.frames_fingerprint(tmp_path, times)
    assert a == S.frames_fingerprint(tmp_path, times)
    assert a != S.frames_fingerprint(tmp_path, times.assign(T=times["T"] + pd.Timedelta(minutes=1)))

    def player_rows(*_):                                    # a different way to build the same frame
        return None
    monkeypatch.setattr(S, "player_rows", player_rows)
    assert a != S.frames_fingerprint(tmp_path, times)


def test_the_betas_the_lab_requires_are_the_ones_the_rules_document_registers():
    doc = (Path(S.ROOT) / "docs" / "nba_search_starters.md").read_text(encoding="utf-8")
    section = doc[doc.index("### 11.2"):doc.index("### 11.3")]
    names = {"First-quarter spread": "spreads_q1", "First-quarter total": "totals_q1",
             "First-half spread": "spreads_h1", "First-half total": "totals_h1"}
    got, season = {}, None
    for row in section.splitlines():
        c = [x.strip() for x in row.strip().strip("|").split("|")]
        if len(c) == 8 and c[3] in names:
            season = int(c[0][:4]) + 1 if c[0] else season
            got[(season, names[c[3]])] = float(c[4])
    assert len(got) == 12 and got == S.REGISTERED_BETA
