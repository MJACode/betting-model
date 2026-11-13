"""The in-play search on 2026-27's live prices (scripts/nba_s_ingame27.py,
docs/nba_search_ingame27.md), on synthetic frames.

What each test pins:
  - impossible numbers: a price strictly between -100 and +100 is dropped, -100 and +100 are not;
    a deciding spread more than 6 points, or a moneyline more than 0.25 of no-vig chance, from its
    paired Pinnacle quote is dropped, and nothing else is;
  - a game whose first ESPN play is more than 15 minutes before its listed tip is left out whole;
  - served = created_at, never before the newest stamp in that fetch;
  - the live rows: only the worker's rows (source empty); the same stamp in a later fetch is
    dropped for the decision but kept for "still offered";
  - still offered: a re-served unchanged quote counts; a moved number or a worse price does not;
    reading de-duplicated rows would miss the repeat;
  - step 2's window: period 4, live, 0 < clock <= 6:00 (6:00 in, 6:01 out, 0:00 out), lead 4-16
    (3 and 17 out), the leader as the side, the first eligible fetch in the population;
  - step 1's frames are IG-2's own (cand, neutral and each placebo seed);
  - choose_seasons=(2027,) puts the live season in the pooled columns; the default leaves them empty;
  - the 200-bet projection date from a measured rate and the schedule;
  - --full refuses without its three settings; a no-result run refuses real scores;
  - the cells emitted are the 24 registered.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts import nba_game_harness as H
from scripts import nba_ingame_ig2 as G
from scripts import nba_s_ingame27 as S

T0 = pd.Timestamp("2026-11-01T01:00:00Z")


# ── impossible numbers ───────────────────────────────────────────────────────

def test_a_price_between_minus_100_and_plus_100_is_impossible():
    assert S.impossible_price([-99, 99, -100, 100, np.nan, -50000, 3500]).tolist() == \
        [True, True, False, False, True, False, False]


def _paired(book, market, line, pin_line, fa, pin_fa):
    return {"book": book, "market": market, "line": line, "pin_line": pin_line, "fa": fa, "pin_fa": pin_fa}


def test_a_deciding_quote_far_from_its_pinnacle_pair_is_dropped_and_nothing_else():
    q = pd.DataFrame([
        _paired("fanduel", "spreads", -6.0, 0.0, .5, .5),        # 6 points: kept
        _paired("fanduel", "spreads", -6.5, 0.0, .5, .5),        # 6.5 points: dropped
        _paired("betmgm", "h2h", np.nan, np.nan, .75, .5),       # 0.25: kept
        _paired("betmgm", "h2h", np.nan, np.nan, .76, .5),       # 0.26: dropped
        _paired("pinnacle", "spreads", 9.0, 0.0, .5, .5),        # Pinnacle never dropped here
        _paired("bovada", "spreads", 9.0, 0.0, .5, .5),          # not a deciding book
        _paired("draftkings", "spreads", 9.0, 0.0, .5, np.nan),  # no coherent pair: not judged
    ])
    assert S.pin_gap_bad(q).tolist() == [False, True, False, True, False, False, False]


def test_a_game_whose_espn_clock_starts_before_its_listed_tip_is_left_out():
    tip = T0
    q = pd.DataFrame({"game_id": ["A", "A", "B", "C"], "tip": tip,
                      "first_play_at": [tip - pd.Timedelta(minutes=16)] * 2
                      + [tip - pd.Timedelta(minutes=14), tip + pd.Timedelta(minutes=60)]})
    kept, dropped = S.drop_early_clocks(q)
    assert sorted(kept["game_id"].unique()) == ["B", "C"]
    assert list(dropped) == ["A"]


# ── the live rows ────────────────────────────────────────────────────────────

def test_served_is_created_at_never_before_the_fetchs_newest_stamp():
    f1, f2 = T0, T0 + pd.Timedelta(minutes=10)
    o = pd.DataFrame({"created_at": [f1, f1, f2],
                      "snapshot_at": [f1 - pd.Timedelta(seconds=30), f1 + pd.Timedelta(seconds=4),
                                      f2 - pd.Timedelta(seconds=40)]})
    s = S.served_times(o)
    assert s["fetch_at"].tolist() == [f1, f1, f2]
    assert s["served_at"].tolist() == [f1 + pd.Timedelta(seconds=4)] * 2 + [f2]


def _odds_row(created, stamp, book="fanduel", market="spreads", line=-3.5, pa=-110, pb=-110, source=None,
              game="G1"):
    return {"game_id": game, "market": market, "bookmaker": book, "snapshot_type": "open",
            "snapshot_at": stamp.isoformat(), "source": source, "created_at": created.isoformat(),
            "home_price": pa, "away_price": pb, "spread_home": line if market == "spreads" else None,
            "total_line": None, "over_price": None, "under_price": None}


def _games(tip=T0):
    return pd.DataFrame({"game_id": ["G1"], "season": [2027], "game_date": ["2026-10-31"], "tip": [tip],
                         "home_team": ["HOM"], "away_team": ["AWY"], "home_score": [100.0], "away_score": [90.0]})


def test_live_rows_keep_the_worker_rows_and_drop_repeats_only_for_the_decision():
    f1, f2 = T0 + pd.Timedelta(minutes=20), T0 + pd.Timedelta(minutes=30)
    s1 = f1 - pd.Timedelta(seconds=20)
    odds = pd.DataFrame([
        _odds_row(f1, s1),                                         # first sight of the quote
        _odds_row(f2, s1),                                         # re-served unchanged next fetch
        _odds_row(f2, f2 - pd.Timedelta(seconds=5), book="betmgm"),
        _odds_row(f2, f2 - pd.Timedelta(seconds=5), book="draftkings", source="odds_api_historical"),
        _odds_row(f1, T0 - pd.Timedelta(minutes=120), book="betrivers"),   # before tip - 90 min
        _odds_row(f2, f2, book="fanatics", pa=-50),                # impossible price
    ])
    q, raw, dropped, notes = S.live_quotes(odds, _games())
    assert len(raw) == 3 and len(q) == 2
    assert sorted(q["book"]) == ["betmgm", "fanduel"]
    assert q.loc[q["book"] == "fanduel", "fetch_at"].iloc[0] == f1
    assert notes["rows_same_stamp_later_fetch"] == 1
    assert list(dropped["book"]) == ["fanatics"]


# ── still offered at the next fetch ──────────────────────────────────────────

def _raw(rows):
    return pd.DataFrame(rows, columns=["game_id", "market", "book", "fetch_at", "line", "price_a", "price_b"])


def test_still_offered_counts_an_unchanged_requote_and_rejects_a_move():
    f1, f2 = T0, T0 + pd.Timedelta(minutes=10)
    raw = _raw([("G1", "spreads", "fanduel", f1, -3.5, -110, -110),
                ("G1", "spreads", "fanduel", f2, -3.5, -110, -110),       # unchanged re-quote
                ("G1", "spreads", "betmgm", f1, -3.5, -105, -115),
                ("G1", "spreads", "betmgm", f2, -4.5, -105, -115),        # number moved
                ("G1", "h2h", "draftkings", f1, np.nan, 150, -180),
                ("G1", "h2h", "draftkings", f2, np.nan, 140, -170),       # home price worse
                ("G1", "h2h", "fanatics", f1, np.nan, 150, -180),
                ("G1", "h2h", "fanatics", f2, np.nan, 160, -190)])        # home price better
    bets = pd.DataFrame({"game_id": "G1", "market": ["spreads", "spreads", "h2h", "h2h"],
                         "book": ["fanduel", "betmgm", "draftkings", "fanatics"], "side": "home",
                         "line": [-3.5, -3.5, np.nan, np.nan], "price": [-110.0, -105.0, 150.0, 150.0],
                         "fetch_at": f1})
    s = S.still_offered(bets, raw)
    assert s["still"].tolist() == [True, False, False, True]
    assert s["identical"].tolist() == [True, False, False, False]
    # the same check on rows with the repeat dropped reads the unchanged quote as gone
    dedup = raw.drop_duplicates(["game_id", "market", "book", "line", "price_a", "price_b"], keep="first")
    assert S.still_offered(bets, dedup)["still"].tolist()[0] is False or \
        not bool(S.still_offered(bets, dedup)["still"].iloc[0])


# ── step 2's window, lead and side ───────────────────────────────────────────

def test_the_window_is_period_4_live_with_six_minutes_or_less():
    st = pd.DataFrame({"period": [4, 4, 4, 4, 3, 4, 5], "phase": ["live"] * 5 + ["break", "live"],
                       "clock_s": [360.0, 361.0, 0.0, 1.0, 100.0, 100.0, 100.0],
                       "h_pts": 90, "a_pts": 80})
    assert S.late_label(st).tolist() == [S.PT_LATE, "", "", S.PT_LATE, "", "", ""]


def test_the_lead_is_4_to_16_and_the_leader_is_the_side():
    st = pd.DataFrame({"period": 4, "phase": "live", "clock_s": 100.0,
                       "h_pts": [93, 94, 106, 107, 80, 79], "a_pts": [90, 90, 90, 90, 96, 96]})
    assert S.late_label(st).tolist() == ["", S.PT_LATE, S.PT_LATE, "", S.PT_LATE, ""]
    assert S.leader_side(st).tolist() == ["home", "home", "home", "home", "away", "away"]


def _late_quote(fetch, book="draftkings", clock=300.0, h=95, a=88, game="G1", pts_since=0, pin_since=0):
    f = T0 + pd.Timedelta(minutes=10 * fetch)
    s = f - pd.Timedelta(seconds=20)
    return {"game_id": game, "market": "h2h", "book": book, "coherent": True, "pin_fa": 0.8,
            "pts_since_stamp": pts_since, "pin_pts_since": pin_since, "period": 4, "phase": "live",
            "clock_s": clock, "h_pts": h, "a_pts": a, "fetch_at": f, "stamp": s, "pin_stamp": s}


def test_step_2_decides_at_the_first_eligible_fetch_inside_the_population():
    q = pd.DataFrame([
        _late_quote(0, clock=420.0),                  # before the window
        _late_quote(1, h=92),                         # lead 4: inside
        _late_quote(1, book="fanduel", h=92),
        _late_quote(2, h=99),                         # later fetch, never used
        _late_quote(1, book="betmgm", h=92, pts_since=2),   # not fresh
    ])
    q = q.assign(phase_ig2=S.late_label(q))
    dec = S.late_decisions(q)
    assert sorted(dec["book"]) == ["draftkings", "fanduel"]
    assert dec["fetch_at"].nunique() == 1 and dec["fetch_at"].iloc[0] == T0 + pd.Timedelta(minutes=10)


# ── step 1 is IG-2's frames ──────────────────────────────────────────────────

def _model(season):
    m = G.StateModel(G.FEATURES)
    m.beta = np.array([1.0, 0.5, 0.0, 0.1, 0.2, 0.1, 0.3, 0.2, 0.05])
    m.s1, m.s0, m.S = 150.0, 2.0, season
    return m


def _dec(n_games=6, dates=2, seed=3):
    rng = np.random.default_rng(seed)
    rows = []
    for g in range(n_games):
        gid = f"G{g}"
        date = f"2026-10-{20 + g % dates}"
        for mk in ("h2h", "spreads"):
            for book in ("draftkings", "fanduel"):
                line = -3.5 + (g % 3) if mk == "spreads" else np.nan
                rows.append({
                    "game_id": gid, "season": 2027, "game_date": date, "market": mk, "book": book,
                    "line": line, "price_a": -110.0 + 10 * rng.integers(-3, 4), "price_b": -110.0,
                    "fetch_at": T0, "served_at": T0, "h_pts": 50 + g, "a_pts": 48, "h_pts_m120": 48 + g,
                    "a_pts_m120": 46, "secs_left": 1500.0, "clock_s": 300.0, "period": 3.0,
                    "mu_pre": 2.0 - g, "h_tf_period": 2, "a_tf_period": 3, "h_top1_pf": 1, "h_top2_pf": 2,
                    "h_top3_pf": 0, "a_top1_pf": 3, "a_top2_pf": 1, "a_top3_pf": 0,
                    "pin_line": line, "pin_fa": 0.45 + 0.02 * g, "phase_ig2": "Q3"})
    d = pd.DataFrame(rows)
    models = {2027: _model(2027)}
    pin = G.apply_model(G.features(d.drop_duplicates(["game_id", "market"])), models)
    d = d.merge(pin[["game_id", "market", "mean", "sd", "p_home"]].rename(
        columns={"mean": "pin_mean", "sd": "pin_sd", "p_home": "pin_p_home"}), on=["game_id", "market"])
    games = d.drop_duplicates("game_id")[["game_id", "game_date"]]
    return d, models, games


def test_step_1_frames_are_ig2s_own_cand_neutral_and_placebo():
    d, models, games = _dec()
    cand0, neutral0, placebo0 = G.grid_frames(d, models, games, n_placebo=3)
    fr = S.step1_frames(d, models, games)
    pd.testing.assert_frame_equal(fr.cand.reset_index(drop=True), cand0.reset_index(drop=True))
    pd.testing.assert_frame_equal(fr.neutral.reset_index(drop=True), neutral0.reset_index(drop=True))
    for seed in (0, 1, 2):
        pd.testing.assert_frame_equal(fr.build(seed).reset_index(drop=True), placebo0[seed].reset_index(drop=True))
    assert len(fr.placebo(S.PLACEBO_SEEDS)) == 200


def test_step_2_bets_only_the_leader_and_the_placebo_keeps_the_leader():
    d, models, games = _dec()
    d = d[d["market"] == "h2h"].assign(h_pts=lambda x: np.where(x["game_id"].isin(["G0", "G1"]), 40, 60))
    fr = S.step2_frames(d, models, games)
    lead = np.where(fr.cand["h_pts"] > fr.cand["a_pts"], "home", "away")
    assert (fr.cand["side_pick"].to_numpy() == lead).all()
    assert (fr.build(1)["side_pick"].to_numpy() == lead).all()
    bets = H.choose(fr.cand, -np.inf, sides=[S.LEADER])
    assert (bets["side"].to_numpy() == np.where(bets["h_pts"] > bets["a_pts"], "home", "away")).all()


# ── the live season in the harness's pooled columns ──────────────────────────

def test_choose_seasons_2027_puts_the_live_season_in_the_pooled_columns():
    rows = []
    for g in range(40):
        for side, pa in (("home", 120.0), ("away", -140.0)):
            rows.append({"game_id": f"G{g}", "season": 2027, "game_date": f"2026-10-{20 + g % 10}",
                         "market": "h2h", "book": "draftkings", "side": side, "line": np.nan, "price": pa,
                         "p_win": 0.5, "p_push": 0.0, "side_pick": "home", "T": T0,
                         "mu": np.nan, "p_home": 0.45})
    cand = H.with_ev(pd.DataFrame(rows))
    games = pd.DataFrame({"game_id": [f"G{g}" for g in range(40)], "season": 2027,
                          "game_date": [f"2026-10-{20 + g % 10}" for g in range(40)],
                          "home_score": [100.0 + (g % 2) * 10 for g in range(40)], "away_score": 105.0})
    data = S.empty_data(games)
    times = cand.drop_duplicates("game_id")[["game_id", "T"]]
    live = H.run_cells(data, "X", "Q3", cand, cand, [0.02], {"h2h": ["model"]}, times=times,
                       choose_seasons=(2027,))
    dflt = H.run_cells(data, "X", "Q3", cand, cand, [0.02], {"h2h": ["model"]}, times=times)
    assert live[0]["pool_n"] == 40 and live[0]["n_choose"] == 40
    assert dflt[0]["pool_n"] == 0


# ── projection, refusals, guards, the registered cells ───────────────────────

def test_the_200_bet_date_counts_scheduled_games_at_the_measured_rate():
    sched = pd.DataFrame({"game_date": ["2026-11-02"] * 30 + ["2026-11-03"] * 30 + ["2026-11-04"] * 30})
    # 1.5 bets a game, 30 games a day: 195 after 11-03, 240 after 11-04; 11-02 is already played
    assert S.projection_date(150, 100, sched, "2026-11-02") == "2026-11-04"
    assert S.projection_date(150, 1000, sched, "2026-11-02") == "not this season"
    assert S.projection_date(0, 100, sched, "2026-11-02").startswith("no bets yet")
    assert S.projection_date(250, 100, sched, "2026-11-02") == "reached"


def test_full_refuses_without_its_three_settings(monkeypatch):
    for k in (S.GO_ENV, S.RESULTS_ENV, S.BETS_ENV):
        monkeypatch.delenv(k, raising=False)
    why = S.refuse_full()
    assert any(S.GO_ENV in w for w in why) and any(S.RESULTS_ENV in w for w in why) \
        and any(S.BETS_ENV in w for w in why)
    with pytest.raises(SystemExit):
        S.full()


def test_a_no_result_run_refuses_real_scores():
    games = pd.DataFrame({"game_id": ["G1"], "home_score": [100.0], "away_score": [90.0]})
    bets = pd.DataFrame({"game_id": ["G1"], "market": ["h2h"], "side": ["home"], "line": [np.nan],
                         "price": [-110.0]})
    with S.only_random_scores():
        with pytest.raises(RuntimeError):
            H.grade(bets, games)
        assert len(H.grade(bets, S.blind_scores(games))) == 1


def test_the_cells_are_the_24_registered():
    specs = S.cell_specs()
    assert len(specs) == 24
    assert sum(1 for s in specs if s[0] == S.FAM_S1) == 18
    assert sum(1 for s in specs if s[0] in (S.FAM_S2H, S.FAM_S2L)) == 6
    rows = [{"family": f, "point": p, "market": m, "side": s, "cut_index": k, "cut": c}
            for f, p, m, s, k, c in specs]
    S.check_rows(rows)
    with pytest.raises(AssertionError):
        S.check_rows(rows[:-1])


def test_top_player_minutes_are_earlier_games_this_season_else_last_seasons_average():
    box = pd.DataFrame({
        "espn_game_id": [1, 2, 3, 4, 5, 5],
        "espn_id": [7, 7, 7, 7, 7, 8],
        "game_id": ["a", "b", "c", "d", "e", "e"],
        "season": [2026, 2026, 2027, 2027, 2027, 2027],
        "game_date": ["2026-01-01", "2026-01-03", "2026-10-21", "2026-10-23", "2026-10-25", "2026-10-25"],
        "minutes": [30.0, 20.0, 40.0, 0.0, 35.0, 10.0]})
    p = S.box_prior_minutes(box).set_index(["espn_game_id", "athlete_id"])["prior_min"]
    assert p[(3, 7)] == 25.0          # first game of 2026-27: 2025-26's average
    assert p[(4, 7)] == 40.0          # earlier 2026-27 games only
    assert p[(5, 7)] == 40.0          # a game he did not play does not count
    assert p[(5, 8)] == 0.0           # nothing known
    assert p[(1, 7)] == 0.0


# ── the fixes after the independent review (doc 3.2) ─────────────────────────

def _tl_tied():
    """Four plays, three logged in the same second; rows given in REVERSE play order, as an
    unstable or wallclock-only sort may leave them."""
    w0, w1 = T0, T0 + pd.Timedelta(seconds=40)
    rows = [("G1", w1, 432, 104, 99), ("G1", w1, 431, 103, 99), ("G1", w1, 430, 102, 99),
            ("G1", w0, 429, 100, 99)]
    return pd.DataFrame(rows, columns=["game_id", "wc", "play_no", "h_pts", "a_pts"])


def test_the_state_at_a_stamp_is_the_last_play_in_play_order_among_plays_in_one_second():
    tl = _tl_tied()
    q = pd.DataFrame({"game_id": ["G1", "G1"], "stamp": [T0 + pd.Timedelta(seconds=49), T0 + pd.Timedelta(seconds=10)]})
    st = S.state_at_stable(q, tl, "stamp", ["h_pts", "a_pts"])
    assert st["h_pts"].tolist() == [104, 100]


def test_restate_reads_the_score_and_the_points_since_the_stamp_from_the_last_play():
    tl = _tl_tied().assign(period=4, clock_s=300.0, game_s=2580.0, h_tf_period=0, a_tf_period=0)
    q = pd.DataFrame({"game_id": ["G1"], "stamp": [T0 + pd.Timedelta(seconds=20)],
                      "served_at": [T0 + pd.Timedelta(seconds=60)], "served_newest": [T0 + pd.Timedelta(seconds=60)],
                      "h_pts": [0], "pts_since_stamp": [-9]})          # stored values are replaced
    r = S.restate(q, tl)
    assert r["h_pts"].iloc[0] == 100 and r["h_pts_served"].iloc[0] == 104
    assert r["pts_since_stamp"].iloc[0] == 4


def test_rules_3_and_4_are_counted_in_decisions_not_rows():
    f0, f1 = T0, T0 + pd.Timedelta(minutes=10)
    q_all = pd.DataFrame({"game_id": ["A", "A", "A", "B", "B"], "market": "h2h", "phase_ig2": "Q3",
                          "fetch_at": [f0, f0, f1, f0, f0], "book": ["dk", "fd", "dk", "dk", "fd"]})
    q_kept = q_all.drop(index=[0, 1, 3])     # A's first fetch loses both quotes; B keeps one
    decide = lambda q: q.sort_values("fetch_at").assign(  # noqa: E731
        first=lambda d: d.groupby(["game_id", "market", "phase_ig2"])["fetch_at"].transform("min")).query(
        "fetch_at == first")
    r = S.decisions_changed(q_kept, q_all, decide)
    assert r == {"decisions_with_rules": 2, "decisions_without_rules": 2, "only_without": 0, "only_with": 0,
                 "different_fetch": 1}


def test_a_clock_jump_of_45_minutes_between_consecutive_plays_drops_the_game():
    def game(gid, gaps_min):
        t = [T0]
        for g in gaps_min:
            t.append(t[-1] + pd.Timedelta(minutes=g))
        return pd.DataFrame({"game_id": gid, "play_no": range(1, len(t) + 1), "wallclock": [x.isoformat() for x in t]})
    pbp = pd.concat([game("ok", [1, 20, 44.9, 1]), game("fwd", [1, 45.0, 1]), game("back", [1, -60, 1]),
                     game("stall", [1, 138.3, -134.4])], ignore_index=True)
    # rows shuffled out of play order: the rule reads play order, not file order or wallclock
    j = S.jump_games(pbp.sample(frac=1.0, random_state=3))
    assert set(j) == {"fwd", "back", "stall"}
    assert j["back"] == -60.0 and j["stall"] == 138.3


def test_time_since_the_last_logged_play_is_reported_as_median_p90_and_count_over_180():
    picks = pd.DataFrame({"stamp": [T0 + pd.Timedelta(seconds=s) for s in (10, 20, 30, 181, 600)],
                          "last_play_at": T0})
    st = S.stall_stats(picks)
    assert st["since_last_play_median_s"] == 30.0
    assert st["since_last_play_over_180"] == 2
    assert np.isclose(st["since_last_play_p90_s"], 432.4)


def test_units_without_outliers_count_only_the_pooled_seasons():
    cand = pd.DataFrame({"game_id": ["A", "A", "B", "B"], "season": [2021, 2021, 2022, 2022],
                         "game_date": ["2021-01-01", "2021-01-01", "2022-01-01", "2022-01-01"],
                         "market": "h2h", "side": "home", "line": np.nan,
                         "book": ["draftkings", "fanduel", "draftkings", "fanduel"],
                         "price": [300.0, 100.0, 105.0, 100.0], "p_win": 0.6, "p_push": 0.0,
                         "side_pick": "home"})
    cand = H.with_ev(cand)
    games = pd.DataFrame({"game_id": ["A", "B"], "home_score": [100.0, 90.0], "away_score": [90.0, 100.0]})
    fr = S.Frames(cand, cand, None, None, cand)
    r = S.pooled_outliers(fr, {"market": "h2h", "side": "home", "cut": 0.0}, games, (2022,))
    assert r["share_outlier"] == 0.0 and np.isclose(r["units_without_outliers"], -1 / 1.05)
