"""scripts/nba_game2_market: families F2, F6a and F6d of the second NBA game
search (docs/nba_models_2026.md §6.3). Every feature rule and every leak guard
is pinned on small games built by hand, by its outcome rather than its code."""
import os

import numpy as np
import pandas as pd
import pytest

from scripts import nba_game_harness as H
from scripts import nba_game2_market as M

TIP = pd.Timestamp("2024-01-16T00:30:00Z")          # 7:30 ET on 2024-01-15
SIG = {(s, m): v for s in (2024, 2025) for m, v in (("spreads", 12.0), ("totals", 18.0))}


def _game(gid, day, hs, aw, season=2024):
    tip = TIP + pd.Timedelta(days=day)
    return {"game_id": gid, "season": season,
            "game_date": (tip - pd.Timedelta(hours=5)).strftime("%Y-%m-%d"), "tip": tip,
            "home_team": f"H{gid}", "away_team": f"A{gid}", "home_score": hs, "away_score": aw}


def _q(g, book, market, lead, line, pa, pb, snap_lag=5):
    return {"game_id": g["game_id"], "season": g["season"], "game_date": g["game_date"],
            "tip": g["tip"], "market": market, "book": book,
            "fetch_at": g["tip"] - pd.Timedelta(minutes=lead),
            "snapshot_at": g["tip"] - pd.Timedelta(minutes=lead + snap_lag),
            "line": line, "price_a": float(pa), "price_b": float(pb), "coherent": True}


def _pe(g, book, market, lead, line, pa=-110, pb=-110):
    """A per-game purchase row: dated by its own snapshot (fetch_at = snapshot_at)."""
    t = g["tip"] - pd.Timedelta(minutes=lead)
    return {"game_id": g["game_id"], "season": g["season"], "game_date": g["game_date"],
            "tip": g["tip"], "market": market, "book": book, "fetch_at": t, "snapshot_at": t,
            "line": line, "price_a": float(pa), "price_b": float(pb), "coherent": True}


def _data(games, quotes):
    g = pd.DataFrame(games)
    q = pd.DataFrame(quotes)
    f = q[["game_id", "tip", "fetch_at"]].drop_duplicates(["game_id", "fetch_at"])
    f = f.assign(lead_min=(f["tip"] - f["fetch_at"]).dt.total_seconds() / 60.0)
    return H.Data(games=g, quotes=q, fetches=f.reset_index(drop=True))


# ── the spread -> win probability rule ───────────────────────────────────────

def test_the_win_probability_removes_the_tie_mass():
    p = M.p_home_from_margin([0.0, 4.0, -4.0], [12.0, 12.0, 12.0])
    assert p[0] == pytest.approx(0.5, abs=1e-12)
    assert p[1] > 0.5 and p[1] + p[2] == pytest.approx(1.0, abs=1e-12)
    raw, _ = H.side_probs(np.array(["spreads"]), np.array(["home"]), np.array([0.0]),
                          mu=[4.0], sigma=[12.0])
    assert p[1] > raw[0]                       # the level-margin mass is shared out


def test_each_reference_reads_only_its_own_books():
    g1, g2 = _game("G1", 0, 110, 100), _game("G2", 0, 110, 100)
    vis = pd.DataFrame([_q(g1, "pinnacle", "spreads", 60, -5.0, -105, -105),
                        _q(g1, "fanduel", "spreads", 60, -7.0, -110, -110),
                        _q(g1, "betmgm", "spreads", 60, -9.0, -110, -110),
                        _q(g2, "fanduel", "spreads", 60, -3.0, -110, -110)])
    pin = M.reference_fair(vis, SIG, "pinnacle").set_index("game_id")
    con = M.reference_fair(vis, SIG, "consensus").set_index("game_id")
    assert list(pin.index) == ["G1"]                       # G2 has no Pinnacle number
    assert pin.loc["G1", "mu"] == pytest.approx(5.0, abs=1e-6)
    assert con.loc["G1", "mu"] == pytest.approx(8.0, abs=1e-6)   # median of 7 and 9
    assert con.loc["G2", "mu"] == pytest.approx(3.0, abs=1e-6)


# ── F2: the favourite, read at T, graded as the favourite ────────────────────

def _f2_games():
    # G1: home is the favourite (home -5) and wins. G2: away is the favourite
    # (home +5) and wins. Fanduel prices the favourite at -180 in both.
    g1, g2 = _game("G1", 0, 110, 100), _game("G2", 1, 100, 110)
    q = [_q(g1, "pinnacle", "spreads", 120, -5.0, -105, -105),
         _q(g1, "fanduel", "h2h", 120, None, -180, 155),
         _q(g1, "pinnacle", "h2h", 120, None, -190, 165),
         _q(g2, "pinnacle", "spreads", 120, 5.0, -105, -105),
         _q(g2, "fanduel", "h2h", 120, None, 155, -180),
         _q(g2, "pinnacle", "h2h", 120, None, 165, -190),
         # Pinnacle's close (after T): both favourites shortened to -250
         _q(g1, "pinnacle", "h2h", 30, None, -250, 210),
         _q(g2, "pinnacle", "h2h", 30, None, 210, -250)]
    return _data([g1, g2], q)


def test_f2_grades_the_favourite_through_the_oriented_copy():
    rows, b = M.f2_cells(_f2_games(), "C", "pinnacle", SIG, runs=2)
    assert len(rows) == 12 and {r["side"] for r in rows} == {"fav", "dog"}
    assert {r["axis_ref"] for r in rows} == {"pinnacle"}
    fav0 = next(r for r in rows if r["side"] == "fav" and r["cut"] == 0.0)
    # both favourites bet at -180 (risk 1.8, win 1.0) and both win
    assert fav0["n_choose"] == 2 and fav0["units_choose"] == pytest.approx(2.0)
    # bar 9's blind bet is the favourite on every game, not the home team
    assert fav0["blind_roi_choose"] == pytest.approx(2.0 / 3.6)
    # closing-line value is read on the favourite's own close (-250 no-vig
    # 0.689 against a -180 bet: +0.072 per unit risked, both games)
    assert fav0["clv_n"] == 2 and fav0["clv_share_positive"] == 1.0
    assert fav0["clv_median"] == pytest.approx(0.0716, abs=5e-4)
    dog0 =next(r for r in rows if r["side"] == "dog" and r["cut"] == 0.0)
    assert dog0["n_choose"] == 0
    assert dog0["blind_roi_choose"] == pytest.approx(-1.0)
    # the oriented model probability is the favourite's
    assert (b["model"]["p_home"] > 0.5).all()


def test_the_favourite_is_read_at_T_not_from_a_later_fetch():
    g = _game("G", 0, 110, 100)
    q = [_q(g, "pinnacle", "spreads", 30, 5.0, -105, -105),     # later fetch: away favoured
         _q(g, "fanduel", "h2h", 30, None, 140, -160),
         _q(g, "pinnacle", "spreads", 120, -5.0, -105, -105),   # at T (C): home favoured
         _q(g, "fanduel", "h2h", 120, None, -180, 155)]
    b = M.f2_point(_data([g], q), "C", "pinnacle", SIG, runs=1)
    og = b["od"].games.set_index("game_id")
    assert og.loc["G", "home_team"] == "HG"                     # not swapped
    oq = b["cand"].set_index("side")
    assert oq.loc["home", "price"] == -180.0                     # the price at T


def test_orientation_swaps_teams_scores_and_prices_together():
    g = pd.DataFrame([_game("a", 0, 100, 90), _game("b", 0, 90, 100)])
    fav = pd.Series([True, False], index=["a", "b"])
    og = M.orient_games(g, fav).set_index("game_id")
    assert og.loc["b", ["home_team", "home_score", "away_score"]].tolist() == ["Ab", 100, 90]
    assert og.loc["a", ["home_team", "home_score"]].tolist() == ["Ha", 100]
    q = pd.DataFrame([_q(_game("a", 0, 0, 0), "fanduel", "h2h", 60, None, -150, 130),
                      _q(_game("b", 0, 0, 0), "fanduel", "h2h", 60, None, 130, -150),
                      _q(_game("b", 0, 0, 0), "fanduel", "spreads", 60, 3.0, -110, -110)])
    oq = M.orient_h2h(q, fav).set_index("game_id")
    assert len(oq) == 2                                          # moneyline only
    assert oq.loc["a", "price_a"] == -150.0 and oq.loc["b", "price_a"] == -150.0


def test_a_level_reference_has_no_favourite():
    ref = pd.DataFrame({"game_id": ["a", "b", "c"], "p_home": [0.6, 0.5, 0.4]})
    fav = M.favourite_home(ref)
    assert fav.to_dict() == {"a": True, "c": False}


# ── F6a: the overtime tail ───────────────────────────────────────────────────

def test_strength_is_minus_the_absolute_margin_so_the_cut_is_within_k():
    fair = pd.DataFrame({"game_id": ["a", "b", "c", "d"], "market": "spreads",
                         "mu": [-1.5, 3.0, 0.5, np.nan]})
    st = M.f6a_strength(fair).set_index("game_id")["strength"]
    assert st.to_dict() == {"a": -1.5, "b": -3.0, "c": -0.5}
    assert M.F6A_CUTS == (-1.0, -2.0, -3.0, -4.0)
    within_2 = set(st[st >= M.F6A_CUTS[1]].index)
    assert within_2 == {"a", "c"}


def test_the_f6a_placebo_shuffles_strength_and_keeps_the_price():
    games = pd.DataFrame({"game_id": list("abcd"),
                          "game_date": ["2024-01-15"] * 3 + ["2024-01-16"]})
    neutral = pd.DataFrame({"game_id": list("abcd"), "market": "totals", "side": "over",
                            "price": [-110.0, -105.0, -115.0, -110.0], "ev": [-.05, -.03, -.06, -.05]})
    st = pd.DataFrame({"game_id": list("abcd"), "strength": [-1.0, -2.0, -3.0, -4.0]})
    moved = 0
    for r in range(20):
        p = M.f6a_placebo(neutral, st, games, r).set_index("game_id")
        assert p["price"].tolist() == neutral["price"].tolist()
        assert p["ev"].tolist() == neutral["ev"].tolist()
        assert p.loc["d", "strength"] == -4.0                    # alone on its date
        assert sorted(p.loc[list("abc"), "strength"]) == [-3.0, -2.0, -1.0]
        moved += p.loc["a", "strength"] != -1.0
    assert moved > 0


# ── F6d: one book against itself ─────────────────────────────────────────────

def test_each_book_moneyline_is_priced_on_its_own_spread():
    g = _game("G", 0, 110, 100)
    q = [_q(g, "fanduel", "spreads", 120, -3.0, -110, -110),
         _q(g, "fanduel", "h2h", 120, None, -150, 130),
         _q(g, "betmgm", "spreads", 120, -8.0, -110, -110),
         _q(g, "betmgm", "h2h", 120, None, -150, 130)]
    b = M.f6d_ml_point(_data([g], q), "C", SIG, runs=1)
    c = b["cand"]
    assert len(c) == 4                                           # 2 books x 2 sides, once each
    home = c[c["side"] == "home"].set_index("book")["p_win"]
    assert home["fanduel"] == pytest.approx(M.p_home_from_margin([3.0], [12.0])[0], abs=1e-6)
    assert home["betmgm"] == pytest.approx(M.p_home_from_margin([8.0], [12.0])[0], abs=1e-6)


def _f6d_total_data(slate_leads=(70,)):
    g = _game("G", 0, 115, 110, season=2025)
    q = [_q(g, "fanduel", "totals", lead, 220.5, -110, -110) for lead in slate_leads]
    pe = pd.DataFrame([_pe(g, "fanduel", "team_totals_home", 62, 112.5),
                       _pe(g, "fanduel", "team_totals_away", 62, 107.5),
                       # bought 20 minutes out: outside D, and after T
                       _pe(g, "fanduel", "team_totals_home", 20, 120.5),
                       _pe(g, "fanduel", "team_totals_away", 20, 115.5)])
    return _data([g], q), pe


SIG_TT = {(2025, m): 11.0 for m in M.TT_MARKETS}


def test_the_own_total_is_the_two_team_totals_bought_in_D_and_in_hand_at_T():
    data, pe = _f6d_total_data()
    b = M.f6d_total_point(data, "D", SIG, SIG_TT, pe, runs=1)
    c = b["cand"]
    assert len(c) == 2 and set(c["side"]) == {"over", "under"}
    assert c["mu"].iloc[0] == pytest.approx(220.0, abs=1e-6)      # 112.5 + 107.5
    assert c["sigma"].iloc[0] == 18.0                             # the full-game totals sigma
    # T is the team-total purchase (62 min out), later than the slate fetch (70)
    assert (b["times"]["T"] == data.games["tip"].iloc[0] - pd.Timedelta(minutes=62)).all()


def test_team_totals_never_reach_the_c_cells_and_the_empty_cell_still_grades():
    data, pe = _f6d_total_data(slate_leads=(90, 60))
    b = M.f6d_total_point(data, "C", SIG, SIG_TT, pe, runs=2)
    assert len(b["cand"]) == 0 and len(b["neutral"]) == 2
    rows = H.run_cells(data, "F6d", "C", b["cand"], b["neutral"], M.F6D_CUTS,
                       {"totals": ["over", "under"]}, placebo=b["placebo"],
                       choose_seasons=M.F6D_TT_CHOOSE)
    assert len(rows) == 4 and all(r["n_choose"] == 0 for r in rows)
    assert all(len(r["placebo_rois"]) == 2 for r in rows)


def test_the_team_total_cells_decide_when_both_quotes_are_in_hand():
    tip = TIP
    sl = pd.DataFrame({"game_id": ["a", "b"], "T": [tip - pd.Timedelta(minutes=70),
                                                   tip - pd.Timedelta(minutes=50)]})
    pe = pd.DataFrame({"game_id": ["a", "c"], "T": [tip - pd.Timedelta(minutes=62),
                                                   tip - pd.Timedelta(minutes=63)]})
    t = M.combine_times(sl, pe).set_index("game_id")["T"]
    assert t["a"] == tip - pd.Timedelta(minutes=62)              # the later of 70 and 62
    assert t["b"] == tip - pd.Timedelta(minutes=50)
    assert t["c"] == tip - pd.Timedelta(minutes=63)


def _sigma_frames():
    rng = np.random.default_rng(3)
    close, games = [], []
    for s, sd in ((2023, 10.0), (2024, 10.0), (2025, 30.0)):
        for i in range(300):
            gid = f"{s}-{i}"
            close += [{"game_id": gid, "season": s, "market": "spreads", "close_line": -5.0},
                      {"game_id": gid, "season": s, "market": "totals", "close_line": 220.0}]
            eh, ea = rng.normal(0, sd, 2)
            games.append({"game_id": gid, "season": s, "home_score": 112.5 + eh,
                          "away_score": 107.5 + ea})
    games.append({"game_id": "2026-0", "season": 2026, "home_score": 100, "away_score": 100})
    return pd.DataFrame(close), pd.DataFrame(games)


def test_team_sigma_is_the_spread_around_the_close_implied_team_total():
    close, games = _sigma_frames()
    sig = M.team_sigma(close, games)
    g23 = games[games["season"] == 2023]
    want = np.concatenate([g23["home_score"] - 112.5, g23["away_score"] - 107.5]).std(ddof=1)
    assert sig[(2024, "team_totals_home")] == pytest.approx(want, rel=1e-9)
    assert sig[(2024, "team_totals_away")] == sig[(2024, "team_totals_home")]


def test_team_sigma_uses_only_earlier_seasons():
    close, games = _sigma_frames()
    sig = M.team_sigma(close, games)
    assert np.isnan(sig[(2023, "team_totals_home")])              # nothing earlier
    assert sig[(2025, "team_totals_home")] < 12.0                 # 2025's own SD is 30
    g2 = games.copy()
    g2.loc[g2["season"] == 2025, "home_score"] += 50.0            # change 2025's results
    assert M.team_sigma(close, g2)[(2025, "team_totals_home")] == sig[(2025, "team_totals_home")]
    assert M.team_sigma(close, g2)[(2026, "team_totals_home")] != sig[(2026, "team_totals_home")]


# ── run guards, the cell list, population ────────────────────────────────────

def test_full_refuses_without_the_owners_go_flag():
    with pytest.raises(SystemExit):
        M.go_guard(True, {})
    with pytest.raises(SystemExit):
        M.go_guard(True, {"NBA_GAME2_GO": "yes"})
    M.go_guard(True, {"NBA_GAME2_GO": "1"})
    M.go_guard(False, {})


def test_smoke_reads_2020_21_only():
    assert M.seasons_for("smoke") == [2021]
    assert M.seasons_for("full") is None


def test_the_shared_cache_is_never_written_or_linked(tmp_path, monkeypatch):
    shared = tmp_path / "shared"
    shared.mkdir()
    for f in ("nba_games.parquet", "nba_odds.parquet"):
        (shared / f).write_bytes(b"x" * 10)
    ledger = tmp_path / "ledger.parquet"
    ledger.write_bytes(b"L")
    before = {p.name: p.stat().st_mtime_ns for p in shared.iterdir()}
    monkeypatch.setattr(H, "CACHE", shared)
    with pytest.raises(SystemExit):                               # --full needs the real ledger
        M.cache_for("full", ledger, tmp_path / "res")
    ov = M.cache_for("smoke", ledger, tmp_path / "res")
    assert ov != shared and (ov / "nba_fetch_ledger.parquet").exists()
    assert not os.path.samefile(ov / "nba_odds.parquet", shared / "nba_odds.parquet")
    assert {p.name: p.stat().st_mtime_ns for p in shared.iterdir()} == before
    (shared / "nba_fetch_ledger.parquet").write_bytes(b"L")
    assert M.cache_for("full", None, tmp_path / "res") == shared


def test_the_cells_are_exactly_section_6_3s():
    assert M.F2_POINTS == ("A", "B", "C", "D")
    assert M.F2_CUTS == (0.0, 0.01, 0.02, 0.03, 0.05, 0.08)
    assert M.F2_REFS == ("pinnacle", "consensus")
    assert M.F6A_POINTS == ("B", "C") and M.F6A_K == (1, 2, 3, 4)
    assert M.F6D_POINTS == ("C", "D") and M.F6D_CUTS == (0.01, 0.03)
    assert M.F6D_TT_CHOOSE == (2025,)
    assert M.EXPECTED_CELLS == {"F2": 96, "F6a": 8, "F6d": 16}
    assert M.PLACEBO_RUNS == 20
    row = {"point": "A", "market": "h2h", "side": "fav", "cut": 0.0, "axis_ref": "pinnacle"}
    with pytest.raises(AssertionError):
        M.check_cells("F2", [row] * 96)                           # duplicates
    with pytest.raises(AssertionError):
        M.check_cells("F6a", [dict(row, cut=float(i)) for i in range(7)])


def test_an_all_nan_placebo_column_survives_the_parquet_round_trip(tmp_path):
    rows = [{"point": "B", "market": "totals", "side": "over", "cut": -float(k), "cut_index": k - 1,
             "placebo_rois": [np.nan] * 20} for k in M.F6A_K]
    rows += [dict(r, point="C") for r in rows]
    M.check_cells("F6a", rows).to_parquet(tmp_path / "c.parquet")
    back = pd.read_parquet(tmp_path / "c.parquet")["placebo_rois"]
    assert all(len(v) == 20 and not np.isfinite(v).any() for v in back)


def test_population_reads_each_seasons_bets_from_its_own_count():
    row = {"side": "over", "cut_index": 0, "cut": 0.01, "n_2021": 3, "n_2022": 4,
           "n_2023": 5, "n_2024": 6, "n_2025": 7, "n_confirm": 8}
    assert [M._season_bets(row, s) for s in range(2021, 2027)] == [3, 4, 5, 6, 7, 8]
    games = pd.DataFrame({"game_id": ["a", "b", "c"], "season": [2021, 2026, 2026]})
    built = {"times": pd.DataFrame({"game_id": ["a", "b"]}), "priced": {"a", "b"},
             "modelled": {"b"}}
    pop = pd.DataFrame(M.population_rows("F6d", "D", "totals", games, built, [row]))
    p26 = pop[pop["season"] == 2026].iloc[0]
    assert (p26["games"], p26["games_at_point"], p26["games_priced"], p26["games_model"],
            p26["bets"]) == (2, 1, 1, 1, 8)
