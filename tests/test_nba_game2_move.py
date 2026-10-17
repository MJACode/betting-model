"""scripts/nba_game2_move: F3 (against part of each line move) and the controls.

Every feature rule and leak guard is pinned on small games built by hand, so
each is checked by its outcome. Each test was watched failing once with its
rule broken (see the commit message)."""
import numpy as np
import pandas as pd
import pytest

from scripts import nba_game2_move as M
from scripts import nba_game_harness as H

TIP = pd.Timestamp("2024-01-16T00:30:00Z")       # 7:30 pm ET on 2024-01-15


def _q(gid, book, market, lead, line, pa=-110.0, pb=-110.0, coherent=True, tip=TIP, snap_lag=10):
    return {"game_id": gid, "season": 2024, "game_date": "2024-01-15", "tip": tip,
            "market": market, "book": book,
            "fetch_at": tip - pd.Timedelta(minutes=lead),
            "snapshot_at": tip - pd.Timedelta(minutes=lead + snap_lag),
            "line": line, "price_a": pa, "price_b": pb, "coherent": coherent}


def _times(gid="G", lead=120, tip=TIP):
    return pd.DataFrame({"game_id": [gid], "T": [tip - pd.Timedelta(minutes=lead)]})


def _signal(rows, lead=120):
    s = M.move_signal(pd.DataFrame(rows), _times(lead=lead))
    return s.set_index("market")


# ── F3: the consensus and its move ───────────────────────────────────────────

def test_consensus_is_the_deciding_books_median_and_never_pinnacle():
    rows = [_q("G", "draftkings", "spreads", 120, -5.0), _q("G", "fanduel", "spreads", 120, -6.0),
            _q("G", "betmgm", "spreads", 120, -6.5), _q("G", "pinnacle", "spreads", 120, -20.0),
            _q("G", "bovada", "spreads", 120, -20.0)]
    c = M.consensus(pd.DataFrame(rows), _times().assign(market="spreads"))
    assert c["cons"].tolist() == [-6.0] and c["n_books"].tolist() == [3]


def test_the_first_quote_is_the_earliest_coherent_deciding_book_fetch():
    rows = [_q("G", "pinnacle", "spreads", 900, -1.0),                    # sharp only: not a deciding book
            _q("G", "fanduel", "spreads", 700, -2.0, pa=-300, pb=-300, coherent=False),
            _q("G", "draftkings", "spreads", 600, -3.0),                  # the first stored quote
            _q("G", "draftkings", "spreads", 120, -5.0)]
    s = _signal(rows)
    assert s.loc["spreads", "first_to_T_min"] == 600.0 - 120.0
    assert s.loc["spreads", "cons_first"] == -3.0 and s.loc["spreads", "move"] == -2.0


@pytest.mark.parametrize("market,first,now,side", [
    ("spreads", -3.0, -5.0, "away"),     # home number fell: the market moved TOWARD home -> fade to away
    ("spreads", -5.0, -3.0, "home"),
    ("totals", 220.0, 223.0, "under"),
    ("totals", 223.0, 220.0, "over"),
])
def test_the_fade_is_the_side_the_move_went_against(market, first, now, side):
    rows = [_q("G", "draftkings", market, 600, first), _q("G", "draftkings", market, 120, now)]
    s = _signal(rows)
    assert s.loc[market, "side_pick"] == side
    assert s.loc[market, "strength"] == abs(now - first)


def test_no_move_has_no_side():
    rows = [_q("G", "draftkings", "totals", 600, 221.0), _q("G", "draftkings", "totals", 120, 221.0)]
    s = _signal(rows)
    assert s.loc["totals", "side_pick"] is None and s.loc["totals", "strength"] == 0.0


def test_a_fetch_after_T_never_reaches_the_move():
    rows = [_q("G", "draftkings", "spreads", 600, -3.0), _q("G", "draftkings", "spreads", 120, -4.0)]
    before = _signal(rows)
    later = rows + [_q("G", "draftkings", "spreads", 60, -9.0), _q("G", "fanduel", "spreads", 30, -9.0)]
    after = _signal(later)
    assert after.loc["spreads", "cons_T"] == before.loc["spreads", "cons_T"] == -4.0
    assert after.loc["spreads", "move"] == -1.0


def test_a_game_first_quoted_after_T_has_no_model_number():
    rows = [_q("G", "pinnacle", "spreads", 300, -3.0), _q("G", "draftkings", "spreads", 60, -4.0)]
    assert _signal(rows).empty


def test_a_game_with_no_fresh_deciding_quote_at_T_has_no_model_number():
    # quoted 8 hours before T and never again before it: stale at T, so no consensus there
    rows = [_q("G", "draftkings", "spreads", 600, -3.0), _q("G", "draftkings", "spreads", 30, -6.0)]
    assert _signal(rows).empty


# ── F3: one whole cell through the harness ──────────────────────────────────

def _two_game_data():
    """G: market moved toward home (fade away); home wins by 10 -> away +4.5 loses.
    G2: market moved toward away (fade home); home wins by 2 -> home +1.5 covers."""
    tip2 = TIP + pd.Timedelta(days=1)
    games = pd.DataFrame([
        {"game_id": "G", "season": 2024, "game_date": "2024-01-15", "tip": TIP,
         "home_team": "BOS", "away_team": "NYK", "home_score": 110, "away_score": 100},
        {"game_id": "G2", "season": 2024, "game_date": "2024-01-16", "tip": tip2,
         "home_team": "LAL", "away_team": "DEN", "home_score": 102, "away_score": 100}])
    rows = []
    for b in ("draftkings", "fanduel"):
        rows += [_q("G", b, "spreads", 600, -2.5), _q("G", b, "spreads", 60, -4.5)]
        q2 = [_q("G2", b, "spreads", 600, -1.5, tip=tip2), _q("G2", b, "spreads", 60, 1.5, tip=tip2)]
        rows += [dict(r, game_date="2024-01-16") for r in q2]
    rows += [_q("G", "pinnacle", "spreads", 60, -4.5), _q("G2", "pinnacle", "spreads", 60, 1.5, tip=tip2)]
    quotes = pd.DataFrame(rows)
    f = quotes[["game_id", "tip", "fetch_at"]].drop_duplicates()
    f = f.assign(lead_min=(f["tip"] - f["fetch_at"]).dt.total_seconds() / 60)
    return H.Data(games=games, quotes=quotes, fetches=f.reset_index(drop=True))


def test_an_f3_cell_bets_the_fade_side_at_its_cut_and_grades_on_the_real_side():
    data = _two_game_data()
    sig = {(2024, "spreads"): 12.0}
    t, _, _, neutral = M.point_frames(data, "D", sig)
    signal = M.move_signal(data.quotes, t)
    assert dict(zip(signal["game_id"], signal["side_pick"])) == {"G": "away", "G2": "home"}
    assert dict(zip(signal["game_id"], signal["strength"])) == {"G": 2.0, "G2": 3.0}
    cand = M.attach(neutral, signal)
    rows = M.rule_cells(data, "F3", "D", cand, M.F3_CUTS, {"spreads": [M.F3_SIDE]})
    assert [r["side"] for r in rows] == ["fade"] * 4
    # cuts 0.5 / 1 / 1.5 / 2 take both games; nothing beyond is on the axis
    assert [r["n_choose"] for r in rows] == [2, 2, 2, 2]
    picks = H.grade(H.choose(cand, -np.inf, sides=["fade"]), data.games).set_index("game_id")
    assert picks["side"].to_dict() == {"G": "away", "G2": "home"}
    assert picks["result"].to_dict() == {"G": "L", "G2": "W"}
    # the fade side on every game that has one, no cut (reported beside bar 9)
    assert rows[0]["blind_roi_choose"] == pytest.approx(H.roi(picks))
    # Bar 9 reads the REAL side of every graded bet: G bets away, G2 home, so
    # home/away is split; both fades are underdogs by the market's fair line
    # (G: home -4.5 is the favourite; G2: home +1.5 is the underdog).
    r = rows[0]
    assert r["share_home"] == 0.5 and r["share_fav"] == 0.0 and np.isnan(r["share_over"])
    # blind home covers both (by 10 at -4.5, by 2 at +1.5); blind away loses both
    assert r["blind_home"] == pytest.approx(2.0 / 2.2) and r["blind_away"] == pytest.approx(-1.0)
    assert r["blind_dog"] == pytest.approx((1.0 - 1.1) / 2.2)          # G away loses, G2 home covers
    assert r["blind_fav"] == pytest.approx((1.0 - 1.1) / 2.2)
    assert r["population_games"] == 2


def test_a_game_the_rule_gives_no_number_is_outside_the_cells_population():
    # §6.5 (second amendment): bar 9's population is the games the rule
    # produced a number for. G3 is priced at T but has no move number.
    data = _two_game_data()
    g3 = data.games.iloc[[1]].assign(game_id="G3", game_date="2024-01-17")
    data.games = pd.concat([data.games, g3], ignore_index=True)
    q3 = data.quotes[data.quotes["game_id"] == "G2"].assign(game_id="G3", game_date="2024-01-17")
    q3 = q3.assign(fetch_at=q3["fetch_at"] + pd.Timedelta(days=1),
                   snapshot_at=q3["snapshot_at"] + pd.Timedelta(days=1), tip=q3["tip"] + pd.Timedelta(days=1))
    data.quotes = pd.concat([data.quotes, q3], ignore_index=True)
    f = data.quotes[["game_id", "tip", "fetch_at"]].drop_duplicates()
    data.fetches = f.assign(lead_min=(f["tip"] - f["fetch_at"]).dt.total_seconds() / 60).reset_index(drop=True)
    sig = {(2024, "spreads"): 12.0}
    t, _, _, neutral = M.point_frames(data, "D", sig)
    signal = M.move_signal(data.quotes, t)
    signal = signal[signal["game_id"] != "G3"]
    cand = M.attach(neutral, signal)
    assert cand["game_id"].nunique() == 3                     # G3 is priced at T
    rows = M.rule_cells(data, "F3", "D", cand, M.F3_CUTS, {"spreads": [M.F3_SIDE]})
    assert rows[0]["population_games"] == 2


def test_a_rule_keyed_by_book_keeps_every_books_offer_in_its_population():
    # The soft-book outlier gives a number to one BOOK (betmgm, 1.5 off the
    # consensus); the game is in the population, so its blind bets are taken
    # at the best deciding offer on the game, not at the outlier book alone.
    games = pd.DataFrame([{"game_id": "G", "season": 2024, "game_date": "2024-01-15", "tip": TIP,
                           "home_team": "BOS", "away_team": "NYK", "home_score": 105, "away_score": 100}])
    quotes = pd.DataFrame([_q("G", "draftkings", "spreads", 60, -4.5), _q("G", "fanduel", "spreads", 60, -4.5),
                           _q("G", "betmgm", "spreads", 60, -6.0),
                           _q("G", "pinnacle", "spreads", 60, -4.5, pa=-105.0, pb=-105.0)])
    f = quotes[["game_id", "tip", "fetch_at"]].drop_duplicates()
    data = H.Data(games=games, quotes=quotes,
                  fetches=f.assign(lead_min=(f["tip"] - f["fetch_at"]).dt.total_seconds() / 60))
    t, vis, _, neutral = M.point_frames(data, "C", {(2024, "spreads"): 12.0})
    cand = M.attach(neutral, M.outlier_signal(vis), keys=("game_id", "market", "book"))
    rows = M.rule_cells(data, "control_soft_outlier", "C", cand, (1.0,), {"spreads": ["outlier_book"]})
    r = rows[0]
    # the bet: away +6 at betmgm, home won by 5 -> covers
    assert r["n_choose"] == 1 and r["share_home"] == 0.0 and r["units_choose"] == pytest.approx(1.0)
    # blind home is home -4.5 (draftkings or fanduel, both -110): covers by 5;
    # at betmgm's -6 alone it would lose
    assert r["blind_home"] == pytest.approx(1.0 / 1.1)


# ── market pricing, the graded load, the written cells ──────────────────────

def _priced_season(n=80):
    """n games in 2024 with Pinnacle's spread and total at 60 minutes out."""
    rng = np.random.default_rng(5)
    games, rows = [], []
    for i in range(n):
        tip = TIP + pd.Timedelta(days=i)
        day = (tip - pd.Timedelta(hours=5)).strftime("%Y-%m-%d")
        h, a = int(rng.integers(95, 125)), int(rng.integers(95, 125))
        games.append({"game_id": f"P{i}", "season": 2024, "game_date": day, "tip": tip,
                      "home_team": "BOS", "away_team": "NYK", "home_score": h, "away_score": a})
        for m, line in (("spreads", -3.5), ("totals", 220.5)):
            rows.append(dict(_q(f"P{i}", "pinnacle", m, 60, line, tip=tip), game_date=day))
    quotes = pd.DataFrame(rows)
    f = quotes[["game_id", "tip", "fetch_at"]].drop_duplicates()
    f = f.assign(lead_min=(f["tip"] - f["fetch_at"]).dt.total_seconds() / 60)
    return H.Data(games=pd.DataFrame(games), quotes=quotes, fetches=f.reset_index(drop=True))


def test_market_pricing_is_the_empirical_distribution_around_pinnacles_close():
    data = _priced_season()
    close, sig = M.market_pricing(data)
    assert set(sig) == {(2024, "spreads"), (2024, "totals")}
    assert all(isinstance(v, H.ResidDist) for v in sig.values())
    # and that is what the market's fair line at a decision point carries
    _, _, fair, _ = M.point_frames(data, "C", sig)
    assert all(isinstance(v, H.ResidDist) for v in fair["sigma"])


def test_full_names_every_season_it_grades_so_a_stale_cache_is_refused(monkeypatch, tmp_path):
    seen = {}

    def fake_load(cache, seasons=None, require_seasons=None):
        seen.update(seasons=seasons, require=require_seasons)
        return "data"

    monkeypatch.setattr(H, "load", fake_load)
    assert M.load_data(tmp_path, full=True) == "data"
    assert list(seen["seasons"]) == list(seen["require"]) == [2021, 2022, 2023, 2024, 2025, 2026]
    M.load_data(tmp_path, full=False)
    assert list(seen["seasons"]) == list(seen["require"]) == [2021]


def test_placebo_returns_are_written_as_floats_even_when_every_one_is_empty(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq
    from scripts import nba_game2_verdict as V
    rows = [{"family": "F3", "cut": 0.5, "placebo_rois": [np.nan] * 20},
            {"family": "control_blind", "cut": 0.0, "placebo_rois": []},
            {"family": "F3", "cut": 1.0, "placebo_rois": [np.nan, np.nan]}]
    M.write_cells(rows, tmp_path / "cells_F3.parquet")
    assert pq.read_schema(tmp_path / "cells_F3.parquet").field("placebo_rois").type == pa.list_(pa.float64())
    back = V.load_cells(tmp_path)
    assert [len(v) for v in back["placebo_rois"]] == [20, 0, 2]
    assert all(np.isnan(x) for x in back["placebo_rois"].iloc[0])


# ── the controls: every cell through the harness, every one a control ───────

def _three_market_data():
    """G and G2 (as _two_game_data) quoted on spreads, totals and moneyline by
    three deciding books and Pinnacle, at 600 and 120 minutes before tip."""
    tip2 = TIP + pd.Timedelta(days=1)
    games = pd.DataFrame([
        {"game_id": "G", "season": 2024, "game_date": "2024-01-15", "tip": TIP,
         "home_team": "BOS", "away_team": "NYK", "home_score": 110, "away_score": 100},
        {"game_id": "G2", "season": 2024, "game_date": "2024-01-16", "tip": tip2,
         "home_team": "LAL", "away_team": "DEN", "home_score": 102, "away_score": 100}])
    rows = []
    for gid, tip, day, sp in (("G", TIP, "2024-01-15", (-2.5, -4.5)), ("G2", tip2, "2024-01-16", (-1.5, 1.5))):
        for b in ("draftkings", "fanduel", "betmgm", "pinnacle"):
            for lead, s in zip((600, 120), sp):
                rows.append(dict(_q(gid, b, "spreads", lead, s, tip=tip), game_date=day))
                rows.append(dict(_q(gid, b, "totals", lead, 220.5 if lead == 600 else 222.5, tip=tip),
                                 game_date=day))
                rows.append(dict(_q(gid, b, "h2h", lead, np.nan, pa=-150.0, pb=130.0, tip=tip), game_date=day))
    quotes = pd.DataFrame(rows)
    f = quotes[["game_id", "tip", "fetch_at"]].drop_duplicates()
    f = f.assign(lead_min=(f["tip"] - f["fetch_at"]).dt.total_seconds() / 60)
    sched = pd.concat([_sched(game_id="G", home_b2b=1, away_rest_days=1.0),
                       _sched(game_id="G2", venue="Denver", away_b2b=1, days_since_open=5)],
                      ignore_index=True)
    return H.Data(games=games, quotes=quotes, fetches=f.reset_index(drop=True)), sched


def test_every_control_runs_through_the_harness_as_a_control_on_real_sides():
    data, sched = _three_market_data()
    sig = {(2024, "spreads"): 12.0, (2024, "totals"): 18.0}
    cells, _ = M.run_controls(data, H.pinnacle_close(data), sig, sched, None, n_placebo=2)
    assert len(cells) == M.CONTROL_CELLS
    assert cells["family"].str.startswith("control_").all()       # so the verdict never judges them
    # a per-game side (the favourite) is graded on the real side it names:
    # both games' home team is -150 everywhere, so both bets are home favourites
    fav = cells[(cells["side"] == "favourite") & (cells["market"] == "h2h")].iloc[0]
    assert fav["n_choose"] == 2 and fav["share_home"] == 1.0 and fav["share_fav"] == 1.0
    assert np.isfinite(fav["blind_fav"]) and fav["blind_fav"] == pytest.approx(fav["blind_home"])
    # the back-to-back spot bets the rested visitor in G only
    r1 = cells[(cells["family"] == "control_spot_b2b_vs_rested") & (cells["market"] == "spreads")].iloc[0]
    assert r1["n_choose"] == 1 and r1["share_home"] == 0.0


def test_the_placebo_moves_the_signal_and_leaves_every_price_alone():
    data = _two_game_data()
    data.games["game_date"] = "2024-01-15"                         # one date: the two games swap
    sig = {(2024, "spreads"): 12.0}
    t, _, _, neutral = M.point_frames(data, "D", sig)
    signal = M.move_signal(data.quotes, t)
    real = M.attach(neutral, signal).sort_values(["game_id", "book", "side"]).reset_index(drop=True)
    seen = set()
    for pc in M.placebo_cands(neutral, signal, data.games, n=20):
        pc = pc.sort_values(["game_id", "book", "side"]).reset_index(drop=True)
        for col in ("mu", "sigma", "price", "line", "ev", "p_win"):
            assert np.allclose(pc[col].astype(float), real[col].astype(float), equal_nan=True), col
        seen.add(tuple(pc.drop_duplicates("game_id")["side_pick"]))
    assert seen == {("away", "home"), ("home", "away")}


# ── controls ────────────────────────────────────────────────────────────────

def _season_games(results, season=2024, start="2023-11-01"):
    """results: list of (home, away, home_wins) one game per day."""
    rows = []
    for i, (h, a, hw) in enumerate(results):
        d = pd.Timestamp(start) + pd.Timedelta(days=i)
        rows.append({"game_id": f"g{season}_{i}", "season": season, "game_date": d.strftime("%Y-%m-%d"),
                     "tip": pd.Timestamp(d.strftime("%Y-%m-%d") + "T23:30:00Z"),
                     "home_team": h, "away_team": a,
                     "home_score": 110 if hw else 100, "away_score": 100 if hw else 110})
    return pd.DataFrame(rows)


def test_streaks_count_runs_and_reset():
    g = _season_games([("BOS", "NYK", True), ("BOS", "MIA", True), ("CHI", "BOS", False),
                       ("BOS", "LAL", False), ("BOS", "PHX", True)])
    st = M.team_streaks(g)
    b = st[st["team"] == "BOS"].sort_values("tip")
    # BOS: W W W (won at CHI) L W
    assert b["win_streak"].tolist() == [1, 2, 3, 0, 1]
    assert b["loss_streak"].tolist() == [0, 0, 0, 1, 0]


def test_a_streak_counts_only_games_final_before_T():
    g = _season_games([("BOS", "NYK", True), ("BOS", "MIA", True), ("BOS", "CHI", True)])
    last = g.iloc[-1]
    on_time = pd.DataFrame({"game_id": [last["game_id"]], "T": [last["tip"] - pd.Timedelta(hours=2)]})
    s = M.streaks_at(g, on_time).set_index("game_id")
    assert s.loc[last["game_id"], "home_win"] == 2
    # a decision only 2 hours after the previous tip cannot know that game yet
    early = pd.DataFrame({"game_id": [last["game_id"]],
                          "T": [g.iloc[1]["tip"] + pd.Timedelta(hours=2)]})
    assert M.streaks_at(g, early).set_index("game_id").loc[last["game_id"], "home_win"] == 1


def test_a_streak_does_not_cross_seasons():
    old = _season_games([("BOS", "NYK", True)] * 4, season=2023, start="2023-04-01")
    new = _season_games([("BOS", "NYK", True)], season=2024, start="2023-10-25")
    g = pd.concat([old, new], ignore_index=True)
    t = pd.DataFrame({"game_id": [new.iloc[0]["game_id"]], "T": [new.iloc[0]["tip"] - pd.Timedelta(hours=2)]})
    assert M.streaks_at(g, t).iloc[0]["home_win"] == 0


def test_the_streak_rule_fades_the_longer_streak_and_a_tie_bets_nothing():
    st = pd.DataFrame({"game_id": ["a", "b", "c"], "home_win": [4, 1, 3], "away_win": [2, 5, 3],
                       "home_loss": [0, 0, 0], "away_loss": [0, 0, 0]})
    s = M.streak_signal(st, "win", markets=("spreads",)).set_index("game_id")
    assert s.loc["a", "side_pick"] == "away" and s.loc["a", "strength"] == 4
    assert s.loc["b", "side_pick"] == "home" and s.loc["b", "strength"] == 5
    assert pd.isna(s.loc["c", "side_pick"]) and np.isnan(s.loc["c", "strength"])


def test_a_big_home_dog_is_home_plus_7_or_more():
    cs = pd.DataFrame({"game_id": ["a", "b", "c"], "cons": [7.0, 6.5, -8.0]})
    s = M.big_home_dog_signal(cs, markets=("spreads",))
    assert s.loc[s["strength"] >= M.BIG_DOG_CUTS[0], "game_id"].tolist() == ["a"]


def _sched(**over):
    base = {"game_id": "a", "venue": "Boston", "neutral": 0, "home_b2b": 0, "away_b2b": 0,
            "away_rest_days": 0.0, "away_is_3in4": 0, "home_travel_mi": 0.0, "away_travel_mi": 0.0,
            "days_since_open": 40}
    return pd.DataFrame([{**base, **over}])


def test_the_schedule_spots_are_the_first_searchs_rules():
    r1 = M.schedule_spots(_sched(home_b2b=1, away_rest_days=1.0)).iloc[0]
    assert r1["b2b_vs_rested"] and not r1["altitude"] and not r1["long_travel_b2b"]
    assert not M.schedule_spots(_sched(home_b2b=1, away_rest_days=0.0)).iloc[0]["b2b_vs_rested"]
    assert M.schedule_spots(_sched(venue="Denver", away_is_3in4=1)).iloc[0]["altitude"]
    assert M.schedule_spots(_sched(venue="Salt Lake City", away_b2b=1)).iloc[0]["altitude"]
    assert not M.schedule_spots(_sched(venue="Denver", away_b2b=1, neutral=1)).iloc[0]["altitude"]
    assert not M.schedule_spots(_sched(venue="Phoenix", away_b2b=1)).iloc[0]["altitude"]
    tired_away = M.schedule_spots(_sched(away_b2b=1, away_travel_mi=900.0)).iloc[0]
    assert tired_away["long_travel_b2b"] and tired_away["long_travel_bet"] == "home"
    tired_home = M.schedule_spots(_sched(home_b2b=1, home_travel_mi=750.0)).iloc[0]
    assert tired_home["long_travel_b2b"] and tired_home["long_travel_bet"] == "away"
    both = M.schedule_spots(_sched(home_b2b=1, home_travel_mi=800.0, away_b2b=1, away_travel_mi=800.0))
    assert not both.iloc[0]["long_travel_b2b"] and both.iloc[0]["long_travel_bet"] is None


def test_early_season_is_the_first_three_weeks():
    sp = M.schedule_spots(pd.concat([_sched(game_id=f"d{d}", days_since_open=d) for d in (0, 20, 21)],
                                    ignore_index=True))
    assert sp.loc[sp["early_season"], "game_id"].tolist() == ["d0", "d20"]
    s = M.flag_signal(sp["game_id"], sp["early_season"], ["totals"])
    assert s.loc[s["strength"] >= M.SPOT_CUTS[0], "game_id"].tolist() == ["d0", "d20"]


def test_the_favourite_follows_the_markets_own_fair_line():
    fair = pd.DataFrame({"game_id": ["a", "a", "b", "b"], "market": ["spreads", "h2h"] * 2,
                         "mu": [4.0, np.nan, -2.0, np.nan], "p_home": [np.nan, 0.6, np.nan, 0.45]})
    f = M.favourite_sides(fair).set_index(["game_id", "market"])
    assert f.loc[("a", "spreads"), "fav"] == "home" and f.loc[("a", "h2h"), "dog"] == "away"
    assert f.loc[("b", "spreads"), "fav"] == "away" and f.loc[("b", "h2h"), "fav"] == "away"


def test_the_soft_outlier_bets_the_deviating_books_number_on_the_side_it_favours():
    vis = pd.DataFrame([
        _q("G", "draftkings", "spreads", 120, -5.0), _q("G", "fanduel", "spreads", 120, -5.0),
        _q("G", "betmgm", "spreads", 120, -3.5),                   # home gets 1.5 more points here
        _q("G", "pinnacle", "spreads", 120, 0.0),                  # never in the consensus or the bet
        _q("G", "draftkings", "totals", 120, 220.0), _q("G", "fanduel", "totals", 120, 220.0),
        _q("G", "betrivers", "totals", 120, 219.0),                # the over is a point cheaper here
    ])
    s = M.outlier_signal(vis).set_index(["market", "book"])
    assert s.loc[("spreads", "betmgm"), "side_pick"] == "home"
    assert s.loc[("spreads", "betmgm"), "strength"] == 1.5
    assert s.loc[("totals", "betrivers"), "side_pick"] == "over"
    assert ("spreads", "pinnacle") not in s.index
    assert s.loc[s["strength"] >= 1.0].index.tolist() == [("spreads", "betmgm"), ("totals", "betrivers")]


def _split(side, pct, observed, kind="pregame_poll", endpoint="v2", market="spreads"):
    return {"game_id": "G", "market": market, "side": side, "tickets_pct": pct,
            "capture_kind": kind, "endpoint": endpoint, "observed_at": observed}


def test_public_fade_reads_only_polls_observed_before_T():
    T = TIP - pd.Timedelta(minutes=120)
    splits = pd.DataFrame([
        _split("home", 72.0, T - pd.Timedelta(minutes=30)), _split("away", 28.0, T - pd.Timedelta(minutes=30)),
        _split("home", 20.0, T + pd.Timedelta(minutes=10)), _split("away", 80.0, T + pd.Timedelta(minutes=10)),
        _split("home", 10.0, None, kind="archive_undated"), _split("away", 90.0, None, kind="archive_undated"),
        # an archive row is refused by its kind even if something stamped it
        _split("home", 5.0, T - pd.Timedelta(minutes=5), kind="archive_undated"),
        _split("away", 95.0, T - pd.Timedelta(minutes=5), kind="archive_undated"),
    ])
    s = M.public_signal(splits, _times(lead=120))
    assert s["side_pick"].tolist() == ["away"] and s["strength"].tolist() == [72.0]


def test_public_fade_without_a_pre_T_poll_or_with_an_even_split_bets_nothing():
    T = TIP - pd.Timedelta(minutes=120)
    archive_only = pd.DataFrame([_split("home", 85.0, T - pd.Timedelta(minutes=1), kind="archive_undated"),
                                 _split("away", 15.0, T - pd.Timedelta(minutes=1), kind="archive_undated")])
    assert M.public_signal(archive_only, _times(lead=120)).empty
    even = pd.DataFrame([_split("over", 50.0, T, market="totals"), _split("under", 50.0, T, market="totals")])
    assert M.public_signal(even, _times(lead=120)).empty
    assert M.public_signal(None, _times(lead=120)).empty


def test_full_refuses_without_the_owners_go(monkeypatch):
    monkeypatch.delenv("NBA_GAME2_GO", raising=False)
    with pytest.raises(SystemExit):
        M.refuse_full_without_go()
    monkeypatch.setenv("NBA_GAME2_GO", "1")
    M.refuse_full_without_go()


def test_the_cell_counts_are_the_registered_ones():
    assert M.F3_CELLS == 24 and len(M.F3_MARKETS) * len(M.F3_POINTS) * len(M.F3_CUTS) == 24
    assert M.SMOKE_SEASONS == [2021] and M.FULL_SEASONS == [2021, 2022, 2023, 2024, 2025, 2026]
    M.synthetic_checks()
