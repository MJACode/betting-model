"""scripts/nba_game2_props (family F6b): every feature rule and every leak guard,
each pinned by an outcome on small games built by hand. No real season is read."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts import nba_game_harness as H
from scripts import nba_game2_props as L

TIP = pd.Timestamp("2024-01-16T00:30:00Z")      # 7:30 ET on 2024-01-15
T = TIP - pd.Timedelta(minutes=60)
DAY = pd.Timedelta(days=1)


# ── builders ────────────────────────────────────────────────────────────────

def _g(gid, season, tip, home, away, hs=110, as_=100):
    return {"game_id": gid, "season": season, "game_date": str((tip - pd.Timedelta(hours=5)).date()),
            "tip": tip, "home_team": home, "away_team": away, "home_score": hs, "away_score": as_}


def _games(*extra):
    """G (the decided game, BOS v NYK) and P0 (both teams' previous game, final two days before)."""
    rows = [_g("G", 2024, TIP, "BOS", "NYK"), _g("P0", 2024, TIP - 2 * DAY, "BOS", "NYK")]
    return pd.DataFrame(rows + list(extra))


_REASON = {"coach": "DNP - Coach's Decision", "injury": "DND - Injury/Illness", "played": None}


def _box(rows, games):
    """rows: (game_id, player_id, name, team, kind, points); kind played / coach / injury / inactive."""
    adv, log, ina = [], [], []
    season = games.set_index("game_id")["season"]
    for gid, pid, name, team, kind, pts in rows:
        base = {"game_id": gid, "player_id": pid, "player_name": name, "team": team,
                "season": int(season[gid]), "game_type": "regular"}
        if kind == "inactive":
            ina.append(base)
            continue
        adv.append({**base, "played": kind == "played", "did_not_play_reason": _REASON[kind]})
        if kind == "played":
            log.append({"game_id": gid, "player_id": pid, "points": float(pts)})
    adv = pd.DataFrame(adv, columns=["game_id", "player_id", "player_name", "team", "season", "game_type",
                                     "played", "did_not_play_reason"])
    log = pd.DataFrame(log, columns=["game_id", "player_id", "points"])
    ina = pd.DataFrame(ina, columns=["game_id", "player_id", "player_name", "team", "season", "game_type"])
    return L.appearances(adv, log, ina, games)


def _props(rows, games, snap=T):
    """rows: (player_name, book, line, over, under)."""
    raw = pd.DataFrame([{"game_id": "G", "player_name": n, "market": L.PROP_MARKET, "bookmaker": b,
                         "snapshot_type": "open", "snapshot_at": snap.isoformat(), "line": ln,
                         "over_price": o, "under_price": u} for n, b, ln, o, u in rows])
    return L.props_frame(raw, games)


def _inj(rows):
    """rows: (team, player_id, name, status, minutes_before_T)."""
    return pd.DataFrame([{"game_id": "G", "team": t, "player_id": pid, "player_name": n, "status": s,
                          "report_ts": T - pd.Timedelta(minutes=m)} for t, pid, n, s, m in rows],
                        columns=["game_id", "team", "player_id", "player_name", "status", "report_ts"])


SHAPES = {2024: L.symmetric_shape()}
BASE_BOX = [("P0", "b1", "Ann Bee", "BOS", "played", 30), ("P0", "b2", "Cal Dee", "BOS", "played", 12),
            ("P0", "n1", "Gus Hay", "NYK", "played", 25), ("P0", "n2", "Ivy Jay", "NYK", "played", 8)]
BASE_PROPS = [("Ann Bee", "fanduel", 27.5, -110, -110), ("Gus Hay", "fanduel", 22.5, -110, -110)]


def _model(games, box_rows=BASE_BOX, prop_rows=BASE_PROPS, inj=None, snap=T):
    app = _box(box_rows, games)
    props = _props(prop_rows, games, snap)
    times = H.per_event_times(props, "D")
    model, pg, names = L.model_numbers(times, props, games, app, inj, SHAPES)
    return model.set_index("market")["mu"] if len(model) else pd.Series(dtype=float), \
        pg.set_index("game_id"), names


# ── props: dated by their own stamp, one quote per player and book ──────────

def test_props_are_dated_by_their_own_stamp_and_nothing_after_tip_survives():
    games = _games()
    raw = pd.DataFrame([
        {"game_id": "G", "player_name": "Ann Bee", "market": L.PROP_MARKET, "bookmaker": "fanduel",
         "snapshot_type": "open", "snapshot_at": s.isoformat(), "line": 27.5, "over_price": -110.0,
         "under_price": u}
        for s, u in ((T, -110.0), (TIP + pd.Timedelta(minutes=5), -110.0), (T, 300.0))])
    p = L.props_frame(raw, games)
    assert len(p) == 2                                    # the in-play row is gone
    assert (p["fetch_at"] == p["snapshot_at"]).all()
    assert p["market"].unique().tolist() == ["pp|Ann Bee"]
    assert p["coherent"].tolist() == [True, False]        # -110 / +300 sums under 1.00


def test_t_is_the_purchase_in_the_45_75_window_and_each_player_keeps_his_own_quote():
    games = _games()
    early = _props([("Ann Bee", "fanduel", 27.5, -110, -110), ("Gus Hay", "fanduel", 22.5, -110, -110)],
                   games, snap=T)
    late = _props([("Ann Bee", "fanduel", 29.5, -110, -110)], games, snap=TIP - pd.Timedelta(minutes=30))
    stale = _props([("Gus Hay", "draftkings", 20.5, -110, -110)], games, snap=T - pd.Timedelta(minutes=70))
    props = pd.concat([early, late, stale], ignore_index=True)
    times = H.per_event_times(props, "D")
    assert times["T"].tolist() == [T]
    vis = H.visible(props, times).set_index(["market", "book"])
    # 30 minutes out is not D; 70 minutes before T is stale; both players kept
    assert sorted(vis.index.tolist()) == [("pp|Ann Bee", "fanduel"), ("pp|Gus Hay", "fanduel")]
    assert vis.loc[("pp|Ann Bee", "fanduel"), "line"] == 27.5


# ── the shape ───────────────────────────────────────────────────────────────

def _season_rows(season, pts, pid="p", team="BOS"):
    games = pd.DataFrame([_g(f"{season}-{i}", season, pd.Timestamp(f"{season - 1}-11-01T00:00Z") + i * DAY,
                             team, "NYK") for i in range(len(pts))])
    return games, [(f"{season}-{i}", pid, "P", team, "played", x) for i, x in enumerate(pts)]


def test_the_shape_is_fit_only_on_seasons_before_the_graded_one():
    g1, r1 = _season_rows(2023, [10] * 25)
    g2, r2 = _season_rows(2024, [10] * 24 + [90])
    games = pd.concat([g1, g2], ignore_index=True)
    sh = L.fit_shape(_box(r1 + r2, games), 2024)
    assert sh.seasons == (2023,)
    assert np.abs(sh.e).max() == 0.0                       # the 2024 outlier is not in it


def test_the_shape_reads_residuals_around_the_whole_season_average():
    g, r = _season_rows(2023, [10] * 19 + [30])
    sh = L.fit_shape(_box(r, g), 2024)
    assert np.allclose(sh.m, 11.0)                         # one average for the player-season
    assert sorted(sh.e.tolist()) == [-1.0] * 19 + [19.0]


def test_the_mean_reads_the_skew_at_even_money_and_rises_with_the_over_price():
    sym = L.symmetric_shape()
    assert L.mean_from_over([20.5], [0.5], sym)[0] == pytest.approx(20.5, abs=1e-6)
    assert L.mean_from_over([20.5], [0.6], sym)[0] > 20.5
    # every residual -1 (a player who scores one under his average): X = mu - 1 + U
    point = L.Shape(m=np.full(10, 20.0), e=np.full(10, -1.0))
    assert L.mean_from_over([20.5, 20.5], [0.5, 0.8], point) == pytest.approx([21.5, 21.8], abs=1e-3)


def test_the_continuity_correction_keeps_each_over_probability_exact():
    y = np.array([18, 19, 19, 20, 21, 21, 21, 24], float)      # whole points, average 0 removed
    F = L.smooth_cdf(y, x=np.array([18.5, 19.5, 20.5, 23.5]))
    assert F == pytest.approx([1 / 8, 3 / 8, 4 / 8, 7 / 8])      # P(points <= k) at k + 0.5
    # between half-points the mass is spread: at 19.0, half of the two 19s
    assert L.smooth_cdf(y, x=np.array([19.0]))[0] == pytest.approx(2 / 8)


def test_the_nearest_residuals_are_the_k_closest_averages():
    sh = L.Shape(m=np.arange(10.0), e=np.arange(10.0) * 100)
    got = sorted(L.nearest_residuals(sh, 4.1, k=3).tolist())
    assert got == [300.0, 400.0, 500.0]


# ── one mean per player ─────────────────────────────────────────────────────

def test_pinnacle_sets_the_mean_else_the_deciding_books_median_and_bovada_alone_prices_nobody():
    games = _games()
    props = _props([("Ann Bee", "pinnacle", 20.5, -110, -110), ("Ann Bee", "fanduel", 24.5, -110, -110),
                    ("Gus Hay", "fanduel", 10.5, -110, -110), ("Gus Hay", "draftkings", 14.5, -110, -110),
                    ("Gus Hay", "bovada", 30.5, -110, -110), ("Ivy Jay", "bovada", 8.5, -110, -110)], games)
    times = H.per_event_times(props, "D")
    qm = L.quote_means(H.visible(props, times), SHAPES)
    assert "Ivy Jay" not in set(qm["player_name"])
    pm = L.player_mean(qm.assign(player_id=qm["player_name"])).set_index("player_id")
    assert pm.loc["Ann Bee", "mu"] == pytest.approx(20.5) and pm.loc["Ann Bee", "ref"] == "pinnacle"
    assert pm.loc["Gus Hay", "mu"] == pytest.approx(12.5) and pm.loc["Gus Hay", "ref"] == "consensus"


def test_two_spellings_of_one_player_count_once():
    games = _games()
    box = BASE_BOX + [("P0", "b9", "Nic Claxton", "BOS", "played", 9)]
    props = BASE_PROPS + [("Nic Claxton", "fanduel", 9.5, -110, -110),
                          ("Nicolas Claxton", "draftkings", 11.5, -110, -110)]
    m, pg, _ = _model(games, box, props)
    assert pg.loc["G", "h_n_priced"] == 2                     # Ann Bee and Claxton, once
    assert m["totals"] == pytest.approx(27.5 + 12 + 10.5 + 22.5 + 8)


# ── the roster and the bench, as of T ───────────────────────────────────────

def test_the_bench_rule_is_points_per_available_team_game():
    games = _games(_g("P1", 2024, TIP - 4 * DAY, "BOS", "NYK"), _g("P2", 2024, TIP - 6 * DAY, "BOS", "NYK"))
    box = BASE_BOX + [("P0", "b3", "Eve Eff", "BOS", "played", 10), ("P1", "b3", "Eve Eff", "BOS", "coach", 0),
                      ("P2", "b3", "Eve Eff", "BOS", "inactive", 0)]
    m, pg, _ = _model(games, box)
    # played 10, coach's decision 0, inactive skipped -> 5 a game; Cal Dee 12
    assert pg.loc["G", "h_bench_pts"] == pytest.approx(12 + 5)


def test_a_box_game_counts_only_once_final_four_hours_before_t():
    # BOS played P9 two hours before T (not final): its box must not be read
    games = _games(_g("P9", 2024, T - pd.Timedelta(hours=2), "BOS", "MIA"))
    box = BASE_BOX + [("P9", "b1", "Ann Bee", "BOS", "played", 30), ("P9", "b7", "New Guy", "BOS", "played", 40)]
    m, pg, _ = _model(games, box)
    assert pg.loc["G", "h_bench_pts"] == pytest.approx(12.0)  # Cal Dee from P0 only; New Guy unseen


def test_the_roster_is_this_season_only_and_a_player_who_left_is_not_on_it():
    games = _games(_g("L0", 2023, TIP - 200 * DAY, "BOS", "NYK"),
                   _g("X1", 2024, TIP - 1 * DAY, "MIA", "CHI"))
    box = BASE_BOX + [("L0", "b8", "Old Hand", "BOS", "played", 20),       # last season only
                      ("L0", "b2", "Cal Dee", "BOS", "played", 50),        # not in this season's rate
                      ("P0", "b6", "Gone Soon", "BOS", "played", 15),      # then played for MIA
                      ("X1", "b6", "Gone Soon", "MIA", "played", 15)]
    m, pg, _ = _model(games, box)
    assert pg.loc["G", "h_bench_pts"] == pytest.approx(12.0)


def test_the_injury_report_counts_thirty_minutes_after_its_stamp():
    games = _games()
    early = _inj([("BOS", "b2", "Cal Dee", "Out", 45)])
    late = _inj([("BOS", "b2", "Cal Dee", "Out", 20)])
    _, pg_early, _ = _model(games, inj=early)
    _, pg_late, _ = _model(games, inj=late)
    assert pg_early.loc["G", "h_bench_pts"] == 0.0            # known: Out
    assert pg_late.loc["G", "h_bench_pts"] == 12.0            # printed 20 minutes before T: not yet known


def test_a_report_row_with_no_nba_id_is_matched_by_name_within_the_team():
    _, pg, _ = _model(_games(), inj=_inj([("BOS", None, "Cal Dee", "Out", 45)]))
    assert pg.loc["G", "h_bench_pts"] == 0.0


def test_the_report_wins_a_player_it_lists_for_one_team_is_not_on_the_other():
    # Ivy Jay played for BOS in P0, then was traded: NYK's report lists him Out
    box = [r for r in BASE_BOX if r[1] != "n2"] + [("P0", "n2", "Ivy Jay", "BOS", "played", 8)]
    _, pg, _ = _model(_games(), box, inj=_inj([("NYK", "n2", "Ivy Jay", "Out", 45)]))
    assert pg.loc["G", "h_bench_pts"] == 12.0 and pg.loc["G", "a_bench_pts"] == 0.0


def test_doubtful_and_questionable_bench_players_still_count():
    _, pg, _ = _model(_games(), inj=_inj([("BOS", "b2", "Cal Dee", "Doubtful", 45)]))
    assert pg.loc["G", "h_bench_pts"] == 12.0


def test_a_priced_player_out_at_t_contributes_nothing_and_is_counted():
    m, pg, _ = _model(_games(), inj=_inj([("BOS", "b1", "Ann Bee", "Out", 45)]),
                      prop_rows=BASE_PROPS + [("Cal Dee", "fanduel", 11.5, -110, -110)])
    assert pg.loc["G", "h_n_priced_out"] == 1
    assert pg.loc["G", "h_team_pts"] == pytest.approx(11.5)


def test_the_report_places_a_player_the_box_has_not_seen_on_his_team():
    # a new signing, Probable for BOS, priced: the report puts him on the roster
    m, pg, names = _model(_games(), inj=_inj([("BOS", "b5", "Neo Signing", "Probable", 45)]),
                          prop_rows=BASE_PROPS + [("Neo Signing", "fanduel", 6.5, -110, -110)])
    assert pg.loc["G", "refused"] == ""
    assert pg.loc["G", "h_n_priced"] == 2


# ── names ───────────────────────────────────────────────────────────────────

def test_a_name_two_roster_players_share_refuses_the_game():
    box = BASE_BOX + [("P0", "b4", "Jalen Green", "BOS", "played", 20), ("P0", "b5", "Jeff Green", "BOS", "played", 8)]
    m, pg, names = _model(_games(), box, BASE_PROPS + [("J. Green", "fanduel", 19.5, -110, -110)])
    assert pg.loc["G", "refused"] == "name_collision"
    assert m.empty
    assert names.set_index("player_name").loc["J. Green", "how"] == "shared"


def test_a_name_nobody_on_either_roster_has_refuses_the_game():
    m, pg, _ = _model(_games(), prop_rows=BASE_PROPS + [("Traded Today", "fanduel", 14.5, -110, -110)])
    assert pg.loc["G", "refused"] == "unresolved_name" and m.empty


def test_a_book_spelling_in_the_alias_table_finds_its_player():
    box = BASE_BOX + [("P0", "b4", "Brandon Boston", "BOS", "played", 10)]
    m, pg, _ = _model(_games(), box, BASE_PROPS + [("B.J. Boston Jr", "fanduel", 9.5, -110, -110)])
    assert pg.loc["G", "refused"] == "" and pg.loc["G", "h_n_priced"] == 2


def test_a_team_with_no_final_game_this_season_has_no_model_number():
    games = pd.DataFrame([_g("G", 2024, TIP, "BOS", "NYK"), _g("L0", 2023, TIP - 200 * DAY, "BOS", "NYK")])
    box = [("L0", "b1", "Ann Bee", "BOS", "played", 30), ("L0", "n1", "Gus Hay", "NYK", "played", 25)]
    m, pg, _ = _model(games, box)
    assert pg.loc["G", "refused"] == "no_final_game_this_season" and m.empty


# ── the gap ─────────────────────────────────────────────────────────────────

def _vis(rows):
    """rows: (game_id, market, book, line, coherent): full-game quotes visible at T."""
    return pd.DataFrame([{"game_id": g, "market": m, "book": b, "line": ln, "coherent": c}
                         for g, m, b, ln, c in rows])


def test_the_gap_is_in_the_side_s_favour_and_agrees_with_settlement():
    model = pd.DataFrame({"game_id": ["G", "G"], "market": ["spreads", "totals"], "mu": [8.0, 230.0]})
    off = pd.DataFrame({"game_id": "G", "market": ["spreads", "spreads", "totals", "totals"],
                        "side": ["home", "away", "over", "under"], "line": [-5.5, -5.5, 225.5, 225.5]})
    cons = pd.DataFrame({"game_id": "G", "market": ["spreads", "totals"], "cons": [-5.5, 225.5]})
    gap = L.with_gap(off, model, cons).set_index("side")["gap"]
    assert gap.to_dict() == {"home": 2.5, "away": -2.5, "over": 4.5, "under": -4.5}
    # a game that lands exactly on the model's numbers (119-111) pays the positive-gap sides
    res = H.settle(np.array(["spreads", "spreads", "totals", "totals"]),
                   np.array(["home", "away", "over", "under"]), np.array([-5.5, -5.5, 225.5, 225.5]),
                   np.array([119] * 4), np.array([111] * 4))
    assert res.tolist() == ["W", "L", "W", "L"]


def test_the_consensus_number_is_pinnacle_s_else_the_deciding_books_median():
    vis = _vis([
        # G: Pinnacle quotes both markets coherently; a soft book is off it
        ("G", "spreads", "pinnacle", -5.5, True), ("G", "spreads", "draftkings", -5.5, True),
        ("G", "spreads", "fanduel", -3.5, True),
        ("G", "totals", "pinnacle", 225.5, True), ("G", "totals", "fanduel", 228.5, True),
        # H2: Pinnacle's spread is incoherent and it has no total: the deciding books' median,
        # Bovada (never a deciding book) and an incoherent deciding quote setting nothing
        ("H2", "spreads", "pinnacle", -1.0, False), ("H2", "spreads", "fanduel", -3.5, True),
        ("H2", "spreads", "draftkings", -5.5, True), ("H2", "spreads", "betmgm", -6.5, True),
        ("H2", "spreads", "bovada", 9.5, True), ("H2", "spreads", "caesars", 30.0, False),
        ("H2", "totals", "fanduel", 210.5, True), ("H2", "totals", "draftkings", 212.5, True),
        ("H2", "totals", "bovada", 250.5, True),
    ])
    c = L.consensus_number(vis).set_index(["game_id", "market"])["cons"]
    assert c.to_dict() == {("G", "spreads"): -5.5, ("G", "totals"): 225.5,
                           ("H2", "spreads"): -5.5, ("H2", "totals"): 211.5}


def test_the_gap_is_measured_against_the_consensus_number_not_each_book_s_own():
    """Third amendment: a soft book's off-consensus number must not raise the gap
    (the refuted outlier mechanism). Every book's offer on a side carries ONE gap."""
    vis = _vis([("G", "spreads", "pinnacle", -5.5, True), ("G", "spreads", "draftkings", -5.5, True),
                ("G", "spreads", "fanduel", -3.5, True),
                ("G", "totals", "pinnacle", 225.5, True), ("G", "totals", "draftkings", 225.5, True),
                ("G", "totals", "fanduel", 221.5, True)])
    off = pd.DataFrame([{"game_id": "G", "market": m, "book": b, "side": s, "line": ln}
                        for m, b, ln in zip(vis["market"], vis["book"], vis["line"])
                        for s in (("home", "away") if m == "spreads" else ("over", "under"))])
    model = pd.DataFrame({"game_id": ["G", "G"], "market": ["spreads", "totals"], "mu": [8.0, 230.0]})
    g = L.with_gap(off, model, L.consensus_number(vis)).set_index(["book", "side"])["gap"]
    for b in ("pinnacle", "draftkings", "fanduel"):
        assert g[(b, "home")] == 2.5 and g[(b, "away")] == -2.5, b       # FanDuel's -3.5 is not a 4.5 gap
        assert g[(b, "over")] == 4.5 and g[(b, "under")] == -4.5, b      # nor its 221.5 an 8.5 one


def test_an_off_consensus_soft_number_does_not_clear_a_cut_but_is_still_the_best_offer():
    """End to end: FanDuel hangs home -1.5 against Pinnacle's -3.5. The model has
    home by 6, so the gap is 2.5 at every book: it clears 2 and not 4. At 2 the
    bet is the best offer under the market's fair line -- FanDuel's -1.5."""
    s = L.synthetic_case()
    q = s["data"].quotes
    soft = (q["game_id"] == "G1") & (q["market"] == "spreads") & (q["book"] == "fanduel")
    data = H.Data(games=s["data"].games, quotes=q.assign(line=np.where(soft, -1.5, q["line"])),
                  fetches=s["data"].fetches)
    props = s["props"].assign(line=np.where(s["props"]["player_name"] == "Gus Hay", 33.5, s["props"]["line"]))
    out = _run(s, props=props, data=data)
    assert out["model"].set_index("market").loc["spreads", "mu"] == 6.0      # 39.5 - 33.5
    assert out["cons"].set_index(["game_id", "market"]).loc[("G1", "spreads"), "cons"] == -3.5
    home = out["cand"][(out["cand"]["market"] == "spreads") & (out["cand"]["side"] == "home")]
    assert set(home["gap"]) == {2.5}
    cells = out["cells"].set_index(["market", "side", "cut"])
    assert cells.loc[("spreads", "home", 2.0), "n_choose"] == 1
    assert cells.loc[("spreads", "home", 4.0), "n_choose"] == 0     # FanDuel's own number would say 4.5
    bet = L.pick(out["cand"], 2.0, "home", "spreads")
    assert bet["book"].tolist() == ["fanduel"] and bet["line"].tolist() == [-1.5]


def test_the_placebo_moves_model_numbers_only_between_games_on_one_date_and_regaps():
    games = pd.DataFrame({"game_id": ["a", "b", "c"], "game_date": ["2024-01-15", "2024-01-15", "2024-01-16"]})
    model = pd.DataFrame({"game_id": ["a", "b", "c"], "market": "totals", "mu": [200.0, 240.0, 220.0]})
    # the offers hang 215; the market's number is 220: the placebo regaps against 220
    off = pd.DataFrame({"game_id": ["a", "b", "c"], "market": "totals", "side": "over", "line": 215.0})
    cons = pd.DataFrame({"game_id": ["a", "b", "c"], "market": "totals", "cons": 220.0})
    seen = set()
    for c in L.placebo_frames(off, model, cons, games):
        g = c.set_index("game_id")["gap"]
        assert g["c"] == 0.0
        assert {g["a"], g["b"]} == {-20.0, 20.0}
        seen.add(g["a"])
    assert seen == {-20.0, 20.0}                               # the shuffle moved it


# ── the whole run ───────────────────────────────────────────────────────────

def test_the_run_emits_exactly_the_twelve_cells_and_the_coverage_files(tmp_path):
    s = L.synthetic_case()
    out = L.run(s["data"], s["games"], s["props"], s["app"], s["inj"], s["shape"], tmp_path)
    cells = pd.read_parquet(tmp_path / "cells_F6b.parquet")
    assert len(cells) == L.EXPECTED_CELLS == 12
    assert set(cells["family"]) == {"F6b"} and set(cells["point"]) == {"D"}
    assert set(zip(cells["market"], cells["side"])) == {("spreads", "home"), ("spreads", "away"),
                                                       ("totals", "over"), ("totals", "under")}
    assert sorted(cells["cut"].unique()) == [2.0, 4.0, 6.0]
    # asked for 2024 and 2025; the synthetic case has no 2025 game, so the D gate drops it
    assert set(cells["choose_seasons_asked"]) == {"2024,2025"}
    assert set(cells["choose_seasons"]) == {"2024"} and set(cells["gate_dropped"]) == {"2025"}
    assert cells["placebo_rois"].map(len).eq(L.N_PLACEBO).all()
    pop = pd.read_parquet(tmp_path / "population_F6b.parquet").set_index("season")
    assert pop.loc[2024, "games_props_at_T"] == 2 and pop.loc[2024, "games_model"] == 1
    assert pop.loc[2024, "bets_spreads_home_g2"] == 1 and pop.loc[2024, "bets_totals_over_g2"] == 0
    assert (tmp_path / "names_F6b.parquet").exists()
    # the cells and the population count the same bets
    n = cells.set_index(["market", "side", "cut"])["n_choose"]
    assert n[("spreads", "home", 2.0)] == pop.loc[2024, "bets_spreads_home_g2"]


def test_the_synthetic_check_passes():
    r = L.synthetic_check()
    assert r["home"] == 39.5 and r["away"] == 22.5


def _run(s, props=None, data=None):
    return L.run(s["data"] if data is None else data, s["games"], s["props"] if props is None else props,
                 s["app"], s["inj"], s["shape"], None)


def test_the_market_is_priced_through_the_empirical_close_of_earlier_seasons():
    s = L.synthetic_case()
    out = _run(s)
    nm = out["neutral"]
    assert set(nm["game_id"]) == {"P0", "G1"}
    for m in ("spreads", "totals"):
        d = nm.loc[nm["market"] == m, "sigma"]
        # an empirical distribution, not a bell curve's float sd
        assert all(isinstance(x, H.ResidDist) for x in d)
        # fit on the 2023 closes alone: none of 2024's own results is in it
        assert {x.label for x in d} == {f"2024 {m} (prior)"}
        assert {x.n for x in d} == {L.PRIOR_GAMES}


def test_a_prop_season_priced_from_its_own_results_is_refused():
    s = L.synthetic_case()
    d = s["data"]
    # the earlier closes relabelled 2024: no earlier season is left, so the
    # harness would fit 2024's pricing on 2024's own results
    own = H.Data(games=d.games.assign(season=2024), quotes=d.quotes.assign(season=2024),
                 fetches=d.fetches)
    with pytest.raises(RuntimeError, match="earlier seasons"):
        _run(s, data=own)
    with pytest.raises(RuntimeError, match="earlier seasons"):      # a missing entry prices nothing
        L.check_close_prior({}, [2024])


def test_the_d_gate_reads_the_prop_purchases_not_the_slate_fetches():
    s = L.synthetic_case()
    full = _run(s)["cells"]
    assert (full["gate_cov_2024"] == 1.0).all()
    # P0's props not bought: the slate still reaches P0 at D (70 minutes out),
    # but this rule decides at its prop purchase, so D reaches half of 2024
    cells = _run(s, props=s["props"][s["props"]["game_id"] != "P0"])["cells"]
    assert (cells["gate_cov_2024"] == 0.5).all()
    assert set(cells["gate_dropped"]) == {"2024,2025"} and set(cells["choose_seasons"]) == {""}
    assert (cells["n_choose"] == 0).all()


def test_the_population_is_the_games_with_a_model_number():
    s = L.synthetic_case()
    out = _run(s)
    # P0 is reached and priced at D but has no final game before it: no model number
    assert out["per_game"].set_index("game_id").loc["P0", "refused"] == "no_final_game_this_season"
    assert set(out["neutral"]["game_id"]) == {"P0", "G1"}
    # the consensus number exists wherever the market's fair line does (same books),
    # so measuring the gap against it drops no game from the population
    assert set(zip(out["cons"]["game_id"], out["cons"]["market"])) == \
        set(zip(out["neutral"]["game_id"], out["neutral"]["market"]))
    # the harness's bar-9 population (the games in the cells' offers) is G1 alone
    assert (out["cells"]["population_games"] == 1).all()
    assert set(out["cand"]["game_id"]) == {"G1"}


def test_bets_carry_the_real_side_and_the_cells_report_real_side_shares_and_blinds():
    s = L.synthetic_case()
    # Gus Hay (NYK) at 60.5: the model has the AWAY team by 21 against home -3.5
    props = s["props"].assign(line=np.where(s["props"]["player_name"] == "Gus Hay", 60.5, s["props"]["line"]))
    out = _run(s, props=props)
    cells = out["cells"].set_index(["market", "side", "cut"])
    away, under = cells.loc[("spreads", "away", 2.0)], cells.loc[("totals", "under", 2.0)]
    assert away["n_choose"] == 1 and cells.loc[("spreads", "home", 2.0), "n_choose"] == 0
    # every bet on the real away side; the market has home as favourite, so it is the underdog
    assert away["share_home"] == 0.0 and away["share_fav"] == 0.0
    assert under["n_choose"] == 1 and under["share_over"] == 0.0
    for col in ("blind_home", "blind_away", "blind_fav", "blind_dog"):
        assert np.isfinite(away[col]), col
    for col in ("blind_over", "blind_under"):
        assert np.isfinite(under[col]), col
    # the graded bets are the real sides, settled on the real score (BOS won 120-100)
    bets = pd.concat([H.grade(L.pick(out["cand"], 2.0, "away", "spreads"), s["games"]),
                      H.grade(L.pick(out["cand"], 2.0, "under", "totals"), s["games"])])
    assert bets["side"].tolist() == ["away", "under"] and set(bets["side"]) <= set(H.REAL_SIDES)
    assert bets["line"].tolist() == [-3.5, 220.5] and bets["result"].tolist() == ["L", "W"]


class _Stop(Exception):
    pass


def test_full_loads_and_requires_every_season_the_market_pricing_is_fit_on(monkeypatch):
    monkeypatch.setenv("NBA_GAME2_GO", "1")
    monkeypatch.setattr("sys.argv", ["nba_game2_props", "--full"])
    seen = {}

    def fake_load(cache=H.CACHE, seasons=None, require_seasons=None):   # nothing real is read
        seen.update(seasons=seasons, require_seasons=require_seasons)
        raise _Stop
    monkeypatch.setattr(H, "load", fake_load)
    with pytest.raises(_Stop):
        L.main()
    # the seasons before 2024 are loaded for the market's pricing; 2026-27 never is
    assert seen["seasons"] == (2021, 2022, 2023, 2024, 2025, 2026)
    # and each is REQUIRED priced: a cache that lost most of 2022's quotes would
    # otherwise price 2024 from 2021 and 2023 and nothing would refuse it
    assert seen["require_seasons"] == (2021, 2022, 2023, 2024, 2025, 2026)


def test_full_fits_a_shape_only_for_the_seasons_with_props(monkeypatch):
    monkeypatch.setenv("NBA_GAME2_GO", "1")
    monkeypatch.setattr("sys.argv", ["nba_game2_props", "--full"])
    s = L.synthetic_case()
    d = s["data"]
    g19 = d.games.iloc[[0]].assign(game_id="S19", season=2019)      # a season with no box season before it
    data = H.Data(games=pd.concat([d.games, g19], ignore_index=True), quotes=d.quotes, fetches=d.fetches)
    monkeypatch.setattr(L, "load_all", lambda *a, **k: (data, s["games"], s["app"], s["inj"], s["props"]))
    asked = []

    def fake_shapes(app, seasons):
        asked.extend(int(x) for x in seasons)
        raise _Stop
    monkeypatch.setattr(L, "shapes", fake_shapes)
    with pytest.raises(_Stop):
        L.main()
    assert asked == [2024, 2025, 2026]


def test_full_refuses_to_run_without_the_owner_s_go(monkeypatch):
    monkeypatch.delenv("NBA_GAME2_GO", raising=False)
    monkeypatch.setattr("sys.argv", ["nba_game2_props", "--full"])

    def no_load(*a, **k):                                 # nothing real is ever read here
        raise RuntimeError("--full went past the gate")
    monkeypatch.setattr(L, "load_all", no_load)
    with pytest.raises(SystemExit) as e:
        L.main()
    assert "NBA_GAME2_GO" in str(e.value)


def test_the_price_free_checks_refuse_2026():
    with pytest.raises(AssertionError):
        L.quality(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), seasons=(2026,))
    with pytest.raises(AssertionError):
        L.names_check(cache=Path("does-not-exist"), seasons=(2025, 2026))
