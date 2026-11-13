"""The popular-team search's lab (docs/nba_search_popular.md). Every rule here was
run once with the rule broken and watched failing. Synthetic games only: nothing
in this file reads a real result."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts import nba_game2_verdict as V
from scripts import nba_game_harness as H
from scripts import nba_s_popular as S

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def prep():
    return S.synthetic_prep()


@pytest.fixture(scope="module")
def groups(prep):
    """Each POP cell and its underdog control by market, built once."""
    cells = {g.market: g for g in S.cell_groups(prep)}
    dogs = {g.market: g for g in S.control_groups(prep) if g.family == S.CONTROL_DOG}
    return cells, dogs


@pytest.fixture(scope="module")
def ran(prep):
    with S.no_bet_files():
        return S.all_cells(prep, S.placebo_signals(prep["inp"], seeds=(1, 2, 3)))


def schedule(n, team="AAA", opp="BBB", season=2024, start="2023-11-01", first=0):
    d = pd.Timestamp(start) + pd.to_timedelta(np.arange(n), unit="D")
    return pd.DataFrame({"game_id": [f"g{season}_{first + i}" for i in range(n)], "season": season,
                         "game_date": d.strftime("%Y-%m-%d"), "home_team": team, "away_team": opp})


def closing_rows(games, home_share, over_share=None):
    rows = []
    over_share = home_share if over_share is None else over_share
    for gid, h, o in zip(games["game_id"], home_share, over_share):
        rows += [{"game_id": gid, "market": "spreads", "side": "home", "tickets_pct": float(h)},
                 {"game_id": gid, "market": "spreads", "side": "away", "tickets_pct": 100.0 - h},
                 {"game_id": gid, "market": S.TOTAL, "side": "over", "tickets_pct": float(o)},
                 {"game_id": gid, "market": S.TOTAL, "side": "under", "tickets_pct": 100.0 - o}]
    return pd.DataFrame(rows)


# ── the numbers each rule reads ─────────────────────────────────────────────

def test_a_game_never_counts_in_its_own_popularity():
    g = schedule(11)
    # the eleventh game's own share is 99: its popularity is the mean of the ten before it
    inp = S.game_inputs(g, closing_rows(g, [60 + i for i in range(10)] + [99]))
    assert inp.loc[10, "h_pop"] == pytest.approx(np.mean([60 + i for i in range(10)]))
    assert inp.loc[10, "a_pop"] == pytest.approx(100 - np.mean([60 + i for i in range(10)]))
    assert inp.loc[10, "h_over"] == pytest.approx(np.mean([60 + i for i in range(10)]))


def test_ten_earlier_games_are_needed_for_either_team():
    g = schedule(11)
    inp = S.game_inputs(g, closing_rows(g, [60.0] * 11))
    assert np.isnan(inp.loc[9, "h_pop"]) and inp.loc[9, "h_n"] == 9
    assert inp.loc[10, "h_pop"] == 60.0 and inp.loc[10, "h_n"] == 10
    # the other team is new: it has no ten games, so the gap has no number
    late = pd.concat([g, schedule(1, opp="CCC", start="2023-12-01", first=50)], ignore_index=True)
    inp2 = S.game_inputs(late, closing_rows(late, [60.0] * 12))
    assert not np.isnan(inp2.loc[11, "h_pop"]) and np.isnan(inp2.loc[11, "a_pop"])
    assert np.isnan(S.signals(inp2).loc[11, "gap_size"])


def test_numbers_start_again_each_season():
    a = schedule(12, season=2023, start="2022-11-01")
    b = schedule(5, season=2024, start="2023-11-01")
    g = pd.concat([a, b], ignore_index=True)
    inp = S.game_inputs(g, closing_rows(g, [60.0] * 17))
    assert inp["h_n"].tolist()[12:] == [0.0, 1.0, 2.0, 3.0, 4.0]
    assert inp.iloc[12:]["h_pop"].isna().all()


def test_the_leagues_mean_is_this_season_on_earlier_dates_each_game_once():
    by_game = pd.DataFrame({"season": [2024, 2024, 2024, 2023, 2024],
                            "game_date": ["2024-01-01", "2024-01-01", "2024-01-02", "2023-01-01", "2024-01-03"],
                            "over": [50.0, 70.0, 90.0, 1.0, 5.0]})
    tgt = pd.DataFrame({"season": [2024, 2024, 2024], "game_date": ["2024-01-01", "2024-01-02", "2024-01-03"]})
    got = S.league_to_date(by_game, tgt)
    assert np.isnan(got[0]) and got[1] == pytest.approx(60.0) and got[2] == pytest.approx(70.0)


@pytest.mark.parametrize("bad", [{"quality": "reversed_at_source"}, {"quality": "late_rewrite"},
                                 {"endpoint": "v2"}, {"capture_kind": "pregame_poll"},
                                 {"game_id": None}, {"tickets_pct": 0.0}, {"tickets_pct": 100.0}])
def test_only_clean_v1_closing_rows_are_read(bad):
    good = {"game_id": "g", "market": "spreads", "side": "home", "tickets_pct": 55.0, "endpoint": "v1",
            "capture_kind": "archive_undated", "quality": None}
    got = S.clean_splits(pd.DataFrame([good, {**good, **bad, "side": "away"}]))
    assert got["side"].tolist() == ["home"], bad


def test_a_filtered_games_frame_reads_each_games_own_numbers():
    # 30 rows, the games wanted are every third: nothing may line up by row label
    g = schedule(30)
    keep = g.iloc[::3].copy()
    assert list(keep.index[:2]) == [0, 3]
    inp = S.game_inputs(keep, closing_rows(keep, [60.0 + i for i in range(len(keep))]))
    assert inp["game_id"].tolist() == keep["game_id"].tolist()
    assert inp["h_n"].tolist() == [float(i) for i in range(10)]
    # read by position: a frame assigned by row label would hold these on other games
    more = schedule(30).iloc[1:].copy()
    inp2 = S.game_inputs(more, closing_rows(more, [50.0] * 10 + [90.0] * 19))
    assert inp2["h_pop"].iloc[10] == 50.0 and np.isnan(inp2["h_pop"].iloc[9])
    assert inp2["h_pop"].iloc[11] == pytest.approx((500.0 + 90.0) / 11)


# ── the rules ───────────────────────────────────────────────────────────────

def _inp(h, a, ho=70.0, ao=65.0, lg=60.0):
    return pd.DataFrame({"game_id": ["x"], "season": [2024], "game_date": ["2024-01-01"], "h_pop": [h],
                         "a_pop": [a], "h_over": [ho], "a_over": [ao], "lg_over": [lg]})


@pytest.mark.parametrize("h,a,against,with_,size", [(60.0, 45.0, "away", "home", 15.0),
                                                    (45.0, 60.0, "home", "away", 15.0),
                                                    (50.0, 50.0, None, None, 0.0)])
def test_the_bet_is_against_the_more_popular_team(h, a, against, with_, size):
    s = S.signals(_inp(h, a)).iloc[0]
    assert s["side_against"] == against and s["side_with"] == with_ and s["gap_size"] == size


def test_a_missing_popularity_gives_no_side():
    s = S.signals(_inp(np.nan, 50.0)).iloc[0]
    assert s["side_against"] is None and np.isnan(s["gap_size"])


def test_the_totals_strength_is_the_smaller_habit_above_the_league():
    assert S.signals(_inp(50.0, 50.0)).loc[0, "habit"] == pytest.approx(5.0)
    assert S.signals(_inp(50.0, 50.0, ho=62.0, ao=90.0)).loc[0, "habit"] == pytest.approx(2.0)
    assert np.isnan(S.signals(_inp(50.0, 50.0, ao=np.nan)).loc[0, "habit"])


def test_the_registered_cuts_and_cell_count(ran):
    rows, ctl, _ = ran
    assert S.GAP_CUTS == (5.0, 10.0, 15.0) and S.HABIT_CUTS == (1.0, 2.0, 3.0) and S.MIN_GAMES == 10
    assert S.EXPECTED_CELLS == len(rows) == 9
    got = {(r["family"], r["point"], r["market"], r["side"], r["cut"]) for r in rows}
    want = {("POP", "C", m, "against_popular", c) for m in ("spreads", "h2h") for c in (5.0, 10.0, 15.0)}
    want |= {("POPT", "C", "totals", "under", c) for c in (1.0, 2.0, 3.0)}
    assert got == want
    assert all(r["family"].startswith(V.CONTROL_PREFIX) for r in ctl)


def test_the_doc_registers_what_the_lab_runs():
    doc = (ROOT / "docs" / "nba_search_popular.md").read_text(encoding="utf-8")
    assert "## 3. The cells (9)" in doc
    assert "gap ≥ 5 / 10 / 15" in doc and "smaller over habit ≥ 1 / 2 / 3" in doc
    assert "strictly before today's date" in doc and "at least 10 such games" in doc
    assert "40 or more points from the median" in doc and "seeds 1-200" in doc
    assert "5 or more points from the median of the deciding books' spreads at the same fetch" in doc
    assert "The same games means the games the cell can bet" in doc


def test_each_pop_bet_is_on_the_side_against_the_popular_team_at_its_cut(prep):
    inp = prep["inp"].set_index("game_id")
    for g in S.cell_groups(prep)[:2]:
        for cut in g.cuts:
            b = S.pick(g.cand, cut, g.side)
            assert len(b), (g.market, cut)
            x = inp.reindex(b["game_id"])
            gap = x["h_pop"].to_numpy() - x["a_pop"].to_numpy()
            assert (np.abs(gap) >= cut).all()
            assert (b["side"].to_numpy() == np.where(gap > 0, "away", "home")).all()


def test_popt_bets_are_unders_at_the_smaller_habit(prep):
    g = S.cell_groups(prep)[2]
    sig = prep["signal"].set_index("game_id")
    assert g.side == "under"
    b = S.pick(g.cand, 1.0, g.side)
    assert len(b) and (b["side"] == "under").all()
    assert (sig.reindex(b["game_id"])["habit"].to_numpy() >= 1.0).all()


def test_the_with_control_bets_the_other_side_of_the_same_games(prep):
    groups = {(g.family, g.market): g for g in S.control_groups(prep)}
    real = S.cell_groups(prep)[0]
    ctl = groups[(S.CONTROL_WITH, "spreads")]
    a = S.pick(real.cand, 5.0, real.side).set_index("game_id")["side"]
    b = S.pick(ctl.cand, 5.0, ctl.side).set_index("game_id")["side"]
    common = a.index.intersection(b.index)
    assert len(common) > 20
    assert (a.reindex(common).to_numpy() != b.reindex(common).to_numpy()).all()


def test_the_dog_control_reads_the_home_number_the_right_way_round(groups):
    ctl = groups[1]["spreads"]
    b = S.pick(ctl.cand, 10.0, ctl.side)
    assert len(b) > 10
    # the home number is positive on a home underdog, negative on a home favourite
    assert (b.loc[b["side"] == "home", "line"] > -1.0).all()
    assert (b.loc[b["side"] == "away", "line"] < 1.0).all()


@pytest.mark.parametrize("market", ["spreads", "h2h"])
@pytest.mark.parametrize("cut", [0.0, 5.0, 10.0, 15.0])
def test_the_dog_control_bets_the_markets_underdog_in_the_same_games(groups, market, cut):
    real, ctl = groups[0][market], groups[1][market]
    a = set(S.pick(real.cand, cut, real.side)["game_id"])
    b = S.pick(ctl.cand, cut, ctl.side)
    assert len(b) > 10
    level = a - set(H.fav_sides(real.cand)["game_id"])
    assert set(b["game_id"]) == a - level
    x = b.merge(H.fav_sides(ctl.cand), on=["game_id", "market"])
    assert len(x) == len(b) and (x["side"] == x["dog"]).all() and (x["side"] != x["fav"]).all()


@pytest.mark.parametrize("cut", [0.0, 5.0, 10.0, 15.0])
def test_the_synthetic_moneyline_really_holds_favourites_the_cell_cannot_bet(groups, cut):
    # without these games the test above passes with the floor left off the control
    real = groups[0]["h2h"]
    c = real.cand[real.cand["book"].isin(H.BETTABLE) & (real.cand["side"] == real.cand["side_pick"])
                  & (real.cand["strength"] >= cut)]
    best = c.groupby("game_id")["price"].max()
    heavy = set(best[best < H.PRICE_FLOOR].index)
    assert heavy, cut
    assert heavy.isdisjoint(S.pick(real.cand, cut, real.side)["game_id"])
    # the underdog on each is the popular team, not the side the cell would bet
    dog = H.fav_sides(real.cand).set_index("game_id")["dog"]
    against = real.cand.drop_duplicates("game_id").set_index("game_id")["side_pick"]
    assert all(dog[g] != against[g] for g in heavy)
    assert heavy.isdisjoint(S.pick(groups[1]["h2h"].cand, cut, S.SIDE_DOG)["game_id"])


def _h2h_world():
    # game, home popularity, away popularity, home price, away price, the fair home chance
    games = [("beyond", 40.0, 60.0, -300.0, 250.0, 0.72),   # against home, past the floor: neither bets
             ("at_floor", 40.0, 60.0, -200.0, 170.0, 0.64),  # against home, on the floor: both bet
             ("underdog", 60.0, 40.0, -170.0, 150.0, 0.60),  # against away, the underdog: both bet it
             ("level", 40.0, 60.0, -105.0, -105.0, 0.50)]    # no underdog: the cell only
    rows = []
    for gid, _, _, hp, ap, ph in games:
        for side, price, pw in (("home", hp, ph), ("away", ap, 1.0 - ph)):
            rows.append({"game_id": gid, "season": 2024, "game_date": "2024-01-01", "market": "h2h", "side": side,
                         "book": "fanduel", "line": np.nan, "price": price, "mu": np.nan, "p_home": ph,
                         "p_win": pw, "p_push": 0.0, "ev": 0.01})
    sig = S.signals(pd.DataFrame({"game_id": [g[0] for g in games], "season": 2024, "game_date": "2024-01-01",
                                  "h_pop": [g[1] for g in games], "a_pop": [g[2] for g in games],
                                  "h_over": 60.0, "a_over": 60.0, "lg_over": 60.0}))
    return pd.DataFrame(rows), sig


def test_the_control_leaves_out_what_the_floor_keeps_from_the_cell_and_a_level_market_has_no_underdog():
    base, sig = _h2h_world()
    cell = S.pick(S.pop_cand(base, sig), 5.0, S.SIDE_AGAINST).set_index("game_id")["side"].to_dict()
    ctl = S.pick(S.dog_cand(base, sig), 5.0, S.SIDE_DOG).set_index("game_id")["side"].to_dict()
    assert cell == {"at_floor": "home", "underdog": "away", "level": "home"}
    assert ctl == {"at_floor": "away", "underdog": "away"}


def test_the_controls_games_do_not_depend_on_the_cut():
    base, sig = _h2h_world()
    # above every gap here, so the exclusion cannot have been read at a cut
    assert set(S.dog_cand(base, sig)["game_id"]) == {"at_floor", "underdog"}


def test_the_credit_line_stops_when_the_control_is_not_on_the_same_games(prep, monkeypatch):
    rows = S.credit_games(prep)
    assert {r["market"] for r in rows} == {"spreads", "h2h"} and len(rows) == 6
    for r in rows:
        assert r["control_only"] == 0 and r["cell_only"] == r["cell_only_level"] == 0
        assert r["cell_bets"] == r["control_bets"] > 0
    assert all(r["games_beyond_floor"] >= 3 for r in rows if r["market"] == "h2h")
    assert all(r["games_beyond_floor"] == 0 for r in rows if r["market"] == "spreads")

    def gap_filter_only(base, sig):
        fv = H.fav_sides(base)[["game_id", "dog"]]
        x = S._rule_frame(sig, "gap_size", sig["side_against"].to_numpy(object)).drop(columns="side_pick")
        return base.merge(x.merge(fv, on="game_id").rename(columns={"dog": "side_pick"}), on="game_id")
    monkeypatch.setattr(S, "dog_cand", gap_filter_only)
    with pytest.raises(RuntimeError, match="same games"):
        S.credit_games(prep)


def test_the_bands_are_the_one_below_the_cut_and_each_from_the_cut_up(ran):
    rows, _, _ = ran
    spread = {r["cut"]: r for r in rows if r["market"] == "spreads"}
    assert (spread[5.0]["band0_lo"], spread[5.0]["band0_hi"]) == (0.0, 5.0)
    assert (spread[5.0]["band3_lo"], spread[5.0]["band3_hi"]) == (15.0, np.inf)
    assert (spread[15.0]["band0_lo"], spread[15.0]["band0_hi"]) == (10.0, 15.0)
    assert spread[15.0]["band_slots"] == 2
    total = {r["cut"]: r for r in rows if r["market"] == "totals"}
    assert (total[1.0]["band0_lo"], total[1.0]["band0_hi"]) == (0.0, 1.0)
    assert (total[3.0]["band1_lo"], total[3.0]["band1_hi"]) == (3.0, np.inf)


# ── impossible numbers ──────────────────────────────────────────────────────

def test_an_impossible_total_is_not_a_total():
    # the median of the six totals is 219.5: 9.5 is far out, 259.0 and 180.0 are 39.5 away;
    # a spread at -50 is not read by this rule
    q = pd.DataFrame({"game_id": "g", "market": ["totals"] * 6 + ["spreads"],
                      "line": [220.0, 221.0, 219.0, 9.5, 259.0, 180.0, -50.0]})
    assert S.impossible_totals(q).tolist() == [False, False, False, True, False, False, False]
    kept, gone = S.drop_impossible(q)
    assert gone["line"].tolist() == [9.5] and len(kept) == 6
    # exactly 40 away is out
    assert S.impossible_totals(q.assign(line=[220.0, 221.0, 219.0, 9.5, 259.5, 180.0, -50.0]))[4]


def test_without_the_rule_the_over_control_really_takes_the_impossible_total(prep, monkeypatch):
    assert len(prep["removed"]) == 1 and prep["removed"].loc[0, "line"] == 9.5
    assert (prep["data"].quotes.loc[prep["data"].quotes["market"] == "totals", "line"] > 100).all()
    ctl = next(g for g in S.control_groups(prep) if g.family == S.CONTROL_OVER)
    assert not (S.pick(ctl.cand, -np.inf, "over")["line"] < 100).any()
    monkeypatch.setattr(S, "IMPOSSIBLE_GAP", 1e9)
    broken = S.synthetic_prep()
    ctl2 = next(g for g in S.control_groups(broken) if g.family == S.CONTROL_OVER)
    assert (S.pick(ctl2.cand, -np.inf, "over")["line"] < 100).sum() == 1


def _visible(game="g", books=None, **spreads):
    rows = []
    for book, line in spreads.items():
        for market, ln in (("spreads", line), ("h2h", np.nan), ("totals", 220.0)):
            rows.append({"game_id": game, "season": 2022, "market": market, "book": book, "line": ln,
                         "price_a": -110.0, "price_b": -110.0, "coherent": True})
    return pd.DataFrame(rows)


def test_a_spread_5_from_the_median_takes_the_books_spread_and_moneyline_and_leaves_its_total():
    vis = _visible(draftkings=-3.5, fanduel=3.5, betmgm=-3.5, williamhill_us=-4.0, betrivers=-3.5)
    kept, gone = S.drop_swapped(vis)
    assert sorted(zip(gone["book"], gone["market"])) == [("fanduel", "h2h"), ("fanduel", "spreads")]
    assert len(kept) == len(vis) - 2
    assert ("fanduel", "totals") in set(zip(kept["book"], kept["market"]))
    # the same book on another game stays
    other = _visible("h", draftkings=-3.5, fanduel=-3.5, betmgm=-3.5)
    _, gone2 = S.drop_swapped(pd.concat([vis, other], ignore_index=True))
    assert set(gone2["game_id"]) == {"g"} and len(gone2) == 2


@pytest.mark.parametrize("line,out", [(1.5, True), (1.0, False), (-8.5, True), (-8.0, False)])
def test_exactly_5_from_the_median_is_out_and_under_it_stays(line, out):
    # the median of the four is -3.5, whichever way the fourth lies
    vis = _visible(draftkings=-3.5, betmgm=-3.5, betrivers=-3.5, fanduel=line, williamhill_us=-3.5)
    assert len(S.drop_swapped(vis)[1]) == (2 if out else 0)


def test_only_deciding_books_set_the_median_and_only_they_are_removed():
    # Pinnacle and Bovada never decide. Read into the median, they would make it +3.5
    vis = _visible(draftkings=-3.5, betmgm=-3.5, fanduel=3.5, pinnacle=3.5, bovada=3.5)
    assert set(S.drop_swapped(vis)[1]["book"]) == {"fanduel"}
    # Pinnacle far from the deciding books is still Pinnacle
    vis2 = _visible(draftkings=-3.5, betmgm=-3.5, fanduel=-3.5, pinnacle=3.5)
    assert S.drop_swapped(vis2)[1].empty


def test_an_incoherent_row_does_not_move_the_median():
    vis = _visible(draftkings=-3.5, betmgm=-3.5, fanduel=-3.5, betrivers=3.5, williamhill_us=3.5, fanatics=3.5)
    vis.loc[vis["book"].isin(["williamhill_us", "fanatics"]), "coherent"] = False
    # read as coherent the six have a median of 0 and nothing is 5 away
    assert set(S.drop_swapped(vis)[1]["book"]) == {"betrivers"}


def test_two_books_cannot_say_which_is_wrong():
    assert S.SWAPPED_MIN_BOOKS == 3
    assert S.drop_swapped(_visible(draftkings=-6.0, fanduel=6.0))[1].empty
    assert set(S.drop_swapped(_visible(draftkings=-6.0, betmgm=-6.0, fanduel=6.0))[1]["book"]) == {"fanduel"}


def _swapped_game(prep):
    return prep["frames"]["C"]["swapped"]["game_id"].iloc[0]


@pytest.mark.parametrize("point", ["C", "D"])
def test_the_swapped_row_is_no_offer_at_either_point(prep, point):
    fr, gid = prep["frames"][point], _swapped_game(prep)
    assert set(fr["swapped"]["book"]) == {"fanduel"} and set(fr["swapped"]["game_id"]) == {gid}
    assert sorted(fr["swapped"]["market"]) == ["h2h", "spreads"]
    x = fr["neutral"][fr["neutral"]["game_id"] == gid]
    pairs = set(zip(x["book"], x["market"]))
    assert ("fanduel", "spreads") not in pairs and ("fanduel", "h2h") not in pairs
    assert ("fanduel", "totals") in pairs
    assert {("draftkings", "spreads"), ("betmgm", "spreads"), ("draftkings", "h2h"), ("betmgm", "h2h")} <= pairs


@pytest.mark.parametrize("market", ["spreads", "h2h"])
def test_without_the_swapped_rule_the_cell_really_bets_the_row(prep, groups, monkeypatch, market):
    gid = _swapped_game(prep)
    g = groups[0][market]

    def row(group):
        got = S.pick(group.cand, 0.0, group.side)     # its gap is under the first cut, like the real row's
        return got[got["game_id"] == gid].iloc[0]
    good = row(g)
    assert good["side"] == "home" and good["book"] != "fanduel"
    best = S.best_offers(prep["frames"]["C"]["neutral"].query("market == @market"))
    assert not ((best["game_id"] == gid) & (best["book"] == "fanduel")).any()   # the placebo's frame
    if market == "spreads":
        assert good["line"] <= -3.0
    monkeypatch.setattr(S, "SWAPPED_GAP", 1e9)
    bad = row(next(x for x in S.cell_groups(S.synthetic_prep()) if x.market == market))
    assert bad["side"] == "home" and bad["book"] == "fanduel" and bad["ev"] > good["ev"]
    if market == "spreads":
        assert bad["line"] >= 3.0


def test_the_swapped_row_is_out_before_the_fair_line_is_read(prep, monkeypatch):
    seen, fair = [], H.market_fair
    monkeypatch.setattr(H, "market_fair", lambda vis, sig: (seen.append(vis), fair(vis, sig))[1])
    fr = S.point_frames(prep["data"], "C", prep["pricing"])
    gid = _swapped_game(prep)
    v = seen[0]
    assert len(fr["swapped"]) == 2 and (v["game_id"] == gid).any()
    assert not ((v["game_id"] == gid) & (v["book"] == "fanduel") & v["market"].isin(S.POP_MARKETS)).any()


def test_the_synthetic_world_holds_what_the_checks_claim(prep, ran):
    q = prep["data"].quotes
    assert set(q["market"]) == {"h2h", "spreads", "totals"}
    sp = q[(q["game_id"] == _swapped_game(prep)) & (q["market"] == "spreads")].set_index("book")["line"]
    assert sp["fanduel"] >= 3.0 and sp["draftkings"] == -sp["fanduel"] and sp["betmgm"] == -sp["fanduel"]
    assert (q.loc[q["market"] == "h2h", ["price_a", "price_b"]].min(axis=1) == -300.0).any()
    rows, _, _ = ran
    for market in ("spreads", "h2h", "totals"):
        assert sum(r["pool_n"] for r in rows if r["market"] == market) > 0, market
    assert set(H.pinnacle_close(prep["data"])["market"]) >= {"h2h", "spreads", "totals"}
    raw = S.synthetic_splits(prep["data"].games)
    assert {"reversed_at_source", "late_rewrite"} <= set(raw["quality"].dropna())
    assert {"v1", "v2"} == set(raw["endpoint"]) and raw["game_id"].isna().any()
    assert "pregame_poll" in set(raw["capture_kind"])


# ── placebo ─────────────────────────────────────────────────────────────────

def _placebo_frame():
    rng = np.random.default_rng(3)
    n = 12
    out = pd.DataFrame({"game_id": [f"g{i}" for i in range(n)], "season": 2024,
                        "game_date": ["2024-01-01"] * 5 + ["2024-01-02"] * 6 + ["2024-01-03"],
                        "h_pop": rng.uniform(40, 60, n), "a_pop": rng.uniform(40, 60, n),
                        "h_over": rng.uniform(50, 70, n), "a_over": rng.uniform(50, 70, n), "lg_over": 60.0})
    out.loc[[0, 6], ["h_pop", "a_pop", "h_over", "a_over"]] = np.nan
    return out


def _tuples(f, idx):
    return sorted(map(tuple, f.loc[idx, list(S.INPUT_COLS)].round(6).fillna(-1.0).to_numpy()))


def test_the_placebo_moves_the_inputs_together_within_a_date():
    f = _placebo_frame()
    sh = S.shuffle_inputs(f, np.random.default_rng(1))
    assert (sh["game_id"] == f["game_id"]).all() and (sh["game_date"] == f["game_date"]).all()
    for _, idx in f.groupby("game_date").groups.items():
        assert _tuples(f, idx) == _tuples(sh, idx)            # whole rows, so they moved together
    assert not f[list(S.INPUT_COLS)].equals(sh[list(S.INPUT_COLS)])


def test_no_game_keeps_its_own_inputs_unless_it_is_alone_on_its_date():
    f = _placebo_frame()
    multi = [i for i in f.index if i not in (0, 6, 11)]     # 0 and 6 have no number; 11 is alone
    for seed in range(1, 21):
        sh = S.shuffle_inputs(f, np.random.default_rng(seed))
        assert (sh.loc[multi, "h_pop"].to_numpy() != f.loc[multi, "h_pop"].to_numpy()).all(), seed
        assert sh.loc[11, "h_pop"] == f.loc[11, "h_pop"]


def test_a_permutation_with_no_fixed_point_is_one_at_every_size():
    rng = np.random.default_rng(5)
    assert S.no_fixed_points(1, rng).tolist() == [0] and S.no_fixed_points(0, rng).tolist() == []
    for n in (2, 3, 4, 7, 15):
        p = S.no_fixed_points(n, rng)
        assert sorted(p.tolist()) == list(range(n)) and not (p == np.arange(n)).any()


def test_a_game_with_no_number_neither_gives_nor_takes():
    f = _placebo_frame()
    for seed in range(1, 6):
        sh = S.shuffle_inputs(f, np.random.default_rng(seed))
        assert sh.loc[[0, 6], list(S.INPUT_COLS)].isna().all().all()
        assert sh.drop([0, 6])[list(S.INPUT_COLS)].notna().all().all()


def test_a_seed_gives_one_shuffle_and_seeds_differ():
    f = _placebo_frame()
    a = S.placebo_signals(f, seeds=(1, 2))
    b = S.placebo_signals(f, seeds=(1, 2))
    assert a[0]["gap_size"].equals(b[0]["gap_size"]) and not a[0]["gap_size"].equals(a[1]["gap_size"])
    assert S.PLACEBO_SEEDS == tuple(range(1, 201))


def test_placebo_frames_give_the_bets_every_offer_gives(prep):
    keys = ["game_id", "market", "side", "book", "line", "price"]
    s = S.placebo_signals(prep["inp"], seeds=(1,))[0]
    for g in S.cell_groups(prep):
        full = S.pop_cand(prep["frames"]["C"]["neutral"].query("market == @g.market"), s) \
            if g.family == S.FAMILY_POP else S.total_cand(prep["frames"]["C"]["neutral"].query("market == @g.market"), s)
        for cut in g.cuts:
            a = S.pick(full, cut, g.side)[keys].sort_values(keys[:3]).reset_index(drop=True)
            b = S.pick(g.rebuild(s), cut, g.side)[keys].sort_values(keys[:3]).reset_index(drop=True)
            pd.testing.assert_frame_equal(a, b, check_dtype=False)
    assert len(a) or len(b)


def test_the_placebo_null_measure_reads_zero_when_the_shuffle_repeats_the_real_bets(prep, monkeypatch):
    shuffled = S.placebo_null(prep, seeds=(1, 2))
    assert max(r["placebo_bets_differing"] for r in shuffled) > 0.3
    assert all(r["real_bets_repeated"] < 1.0 for r in shuffled if r["real_bets"] > 5)
    monkeypatch.setattr(S, "placebo_signals", lambda inp, seeds: [S.signals(inp) for _ in seeds])
    same = S.placebo_null(prep, seeds=(1, 2))
    assert all(r["placebo_bets_differing"] == 0.0 for r in same)
    assert all(r["real_bets_repeated"] == 1.0 for r in same if r["real_bets"])


def test_every_registered_cell_carries_its_placebo_and_controls_none(ran):
    rows, ctl, _ = ran
    assert all(len(r["placebo_rois"]) == 3 for r in rows)
    assert all(len(r["placebo_rois"]) == 0 for r in ctl)


# ── through the verdict, and onto disk ──────────────────────────────────────

def test_the_cells_read_through_the_verdict_after_a_round_trip_to_disk(prep, ran, tmp_path):
    rows, ctl, cands = ran
    S.write_outputs(tmp_path, prep, rows, ctl, cands)
    cells = V.load_cells(tmp_path)
    assert len(cells) == len(rows) + len(ctl)
    v = V.house_verdict_bands(cells, n_placebo=3)
    assert len(v) == 9 and set(v["family"]) == {"POP", "POPT"} and v["key"].is_unique
    assert v[V.FIFTH_BARS].notna().all().all()
    # the keys name the market, the side and the cut
    assert "POP|C|h2h|against_popular|cut=10.0" in set(v["key"])
    assert (tmp_path / "population_POP.parquet").exists()
    assert pd.read_parquet(tmp_path / "signals_POP.parquet")["side_against"].notna().any()


def test_a_placebo_count_other_than_200_stops_the_real_verdict(ran):
    rows, _, _ = ran
    with pytest.raises(ValueError, match="placebo count"):
        V.house_verdict_bands(pd.DataFrame(rows))


def test_bets_are_written_without_pricing_objects(prep, tmp_path, monkeypatch):
    assert "sigma" not in prep["frames"]["C"]["neutral"]
    assert all(c not in S.cell_groups(prep)[0].cand for c in ("sigma", "sigma1"))
    monkeypatch.setenv(S.BETS_ENV, str(tmp_path))
    g = S.cell_groups(prep)[1]
    S.emit(prep, g)
    files = list(tmp_path.glob("bets_POP_C_h2h_*.parquet"))
    assert len(files) == 1
    b = pd.read_parquet(files[0])
    assert len(b) and "sigma" not in b and {"result", "units", "cut"} <= set(b)
    g.cand.head(50).to_parquet(tmp_path / "cand.parquet")     # a candidate frame stores whole


def test_synthetic_checks_write_no_bet_file(tmp_path, monkeypatch):
    monkeypatch.setenv(S.BETS_ENV, str(tmp_path))
    with S.no_bet_files():
        assert S.BETS_ENV not in os.environ
    assert os.environ[S.BETS_ENV] == str(tmp_path)


def test_smoke_never_grades_a_real_score(prep, monkeypatch):
    real = prep["data"].games
    seen, step1 = [], []
    grade, rows1 = H.grade, S.step1_rows

    def spy(bets, games):
        seen.append(games)
        return grade(bets, games)

    def spy1(signal, close, games):
        step1.append(games)
        return rows1(signal, close, games)
    monkeypatch.setattr(H, "grade", spy)
    monkeypatch.setattr(S, "step1_rows", spy1)
    printed = []
    rep = S.smoke_report(prep, 1.0, out=printed.append)
    assert seen and step1
    for g in [*seen, *step1]:
        assert g is not real
        m = g[["game_id", "home_score", "away_score"]].merge(
            real[["game_id", "home_score", "away_score"]], on="game_id", suffixes=("", "_real"))
        assert not ((m["home_score"] == m["home_score_real"]) & (m["away_score"] == m["away_score_real"])).all()
    assert rep["timing"]["projected_full_minutes"] > 0 and rep["read_gap"]["min_hours"] > 0
    text = "\n".join(printed)
    for needle in ("EXTREMES", "HIGHEST-EV OFFERS", "PLACEBO NULL", "TIMING", "same_fetch", "CREDIT LINE GAMES",
                   "swapped_rows_C", "swapped_rows_D", "farthest_spreads_C"):
        assert needle in text
    assert {r["book"] for r in rep["extremes"]["swapped_rows_D"]} == {"fanduel"}


def test_full_then_the_verdict_then_the_credit_line_run_end_to_end_on_synthetic_games(prep, monkeypatch, tmp_path, capsys):
    cache, out, bets = tmp_path / "cache", tmp_path / "out", tmp_path / "bets"
    cache.mkdir()
    for name in ("nba_fetch_ledger.parquet", "nba_public_splits.parquet", "nba_schedule.parquet"):
        (cache / name).write_bytes(b"")
    monkeypatch.setenv("NBA_GAME2_GO", "1")
    monkeypatch.setenv("NBA_GAME2_RESULTS", str(out))
    monkeypatch.setenv("NBA_GAME2_BETS", str(bets))
    signals = S.placebo_signals
    monkeypatch.setattr(S, "synthetic_checks", lambda: {})
    monkeypatch.setattr(S, "prepare", lambda c, require: prep)
    monkeypatch.setattr(S, "N_PLACEBO", 2)
    monkeypatch.setattr(S, "placebo_signals", lambda inp: signals(inp, seeds=(1, 2)))
    S.full(cache)
    text = capsys.readouterr().out
    assert "cells written" in text and "REPORT step1" in text and "min]" in text
    for name in ("POP", "POPT", S.CONTROL_WITH, S.CONTROL_DOG, S.CONTROL_OVER, S.CONTROL_POP_D, S.CONTROL_TOT_D):
        assert (out / f"cells_{name}.parquet").exists(), name
    for name in ("national_tv", "total_regimes", "step1"):
        assert len(pd.read_parquet(out / f"report_{name}.parquet")), name
    written = list(bets.glob("bets_*.parquet"))
    assert written and all("sigma" not in pd.read_parquet(p).columns for p in written)
    v = V.house_verdict_bands(V.load_cells(out), n_placebo=2)
    v.drop(columns=["placebo_rois"]).to_parquet(out / "verdict_house5.parquet")
    got = S.credit_table(out)
    assert len(got) == 9 and got["credited_popularity"].dtype == bool
    assert got.loc[got["family"] == "POP", "dog_pool_roi"].notna().all()


def test_full_stops_before_any_grade_when_the_credit_line_is_not_on_the_same_games(prep, monkeypatch, tmp_path):
    cache, out = tmp_path / "cache", tmp_path / "out"
    cache.mkdir()
    for name in ("nba_fetch_ledger.parquet", "nba_public_splits.parquet", "nba_schedule.parquet"):
        (cache / name).write_bytes(b"")
    monkeypatch.setenv("NBA_GAME2_GO", "1")
    monkeypatch.setenv("NBA_GAME2_RESULTS", str(out))
    monkeypatch.setenv("NBA_GAME2_BETS", str(tmp_path / "bets"))
    monkeypatch.setattr(S, "synthetic_checks", lambda: {})
    monkeypatch.setattr(S, "prepare", lambda c, require: prep)

    def boom(p):
        raise RuntimeError("the credit line does not compare the same games")

    def graded(*a, **k):
        raise AssertionError("graded before the credit line's games were checked")
    monkeypatch.setattr(S, "credit_games", boom)
    monkeypatch.setattr(S, "all_cells", graded)
    with pytest.raises(RuntimeError, match="same games"):
        S.full(cache)
    assert not out.exists()


def test_a_read_of_a_game_not_yet_started_stops_the_smoke(prep, monkeypatch):
    monkeypatch.setattr(S, "read_gap_hours", lambda p: {"min_hours": -1.0, "p01_hours": 0.0, "median_hours": 0.0})
    with pytest.raises(RuntimeError, match="not started"):
        S.smoke_report(prep, 1.0, out=lambda s: None)


def test_full_refuses_without_the_go_a_results_folder_or_a_bets_folder_before_reading(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise AssertionError("read data before refusing")
    monkeypatch.setattr(H, "load", boom)
    for name in ("nba_fetch_ledger.parquet", "nba_public_splits.parquet", "nba_schedule.parquet"):
        (tmp_path / name).write_bytes(b"")
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


# ── reports ─────────────────────────────────────────────────────────────────

def test_the_television_groups():
    sched = pd.DataFrame({"game_id": list("abcdefg"), "season": [2026, 2026, 2026, 2026, 2021, 2024, 2026],
                          "national_tv": ["ESPN", "NBA TV", None, "TNT,TNT OT", "NBA TV,ESPN", "ESPN", "NBC,Peacock"]})
    got = S.tv_groups(sched).set_index("game_id")["tv"].to_dict()
    assert got == {"a": S.TV_NATIONAL, "b": S.TV_NBA_TV, "c": S.TV_NONE, "d": S.TV_NATIONAL,
                   "e": S.TV_NATIONAL, "g": S.TV_NATIONAL}     # 2023-24 has no flag at all: left out


def test_the_reports_are_written_and_split_as_the_doc_says(prep, ran, tmp_path):
    _, _, cands = ran
    rep = S.write_reports(tmp_path, prep, cands)
    assert (tmp_path / "report_national_tv.parquet").exists()
    tv = rep["national_tv"]
    assert set(tv["season"]) <= set(S.TV_SEASONS) and set(tv["tv"]) == {S.TV_NATIONAL, S.TV_NBA_TV, S.TV_NONE}
    assert set(tv["family"]) == {"POP", "POPT"}
    reg = rep["total_regimes"]
    assert set(reg["seasons"]) == set(S.TOTAL_REGIMES) and set(reg["family"]) == {"POPT"} and len(reg) == 6
    assert set(rep["step1"]["market"]) == {"spreads", "h2h", "totals"}
    assert (reg.loc[reg["bets"] < 200, "note"] == "too few games to tell").all()


def _step1_world(popular_covers: bool):
    n = 40
    games = pd.DataFrame({"game_id": [f"g{i}" for i in range(n)], "season": 2024,
                          "game_date": [f"2024-01-{1 + i % 20:02d}" for i in range(n)],
                          "home_score": 110.0, "away_score": 100.0})
    # the home team is popular in the first half of the games, the away team in the rest
    home_popular = np.arange(n) < n / 2
    signal = pd.DataFrame({"game_id": games["game_id"], "gap_size": 10.0 + np.arange(n) % 7,
                           "side_against": np.where(home_popular, "away", "home"), "habit": 2.0})
    if not popular_covers:
        games = games.assign(home_score=np.where(home_popular, 100.0, 110.0), away_score=np.where(home_popular, 110.0, 100.0))
    else:
        games = games.assign(home_score=np.where(home_popular, 110.0, 100.0), away_score=np.where(home_popular, 100.0, 110.0))
    close = pd.DataFrame({"game_id": games["game_id"], "season": 2024, "market": "spreads",
                          "close_line": -3.0, "close_fa": 0.5, "close_at": pd.Timestamp("2024-01-01", tz="UTC")})
    close.loc[~home_popular, "close_line"] = 3.0
    return signal, close, games


@pytest.mark.parametrize("popular_covers,sign", [(True, 1.0), (False, -1.0)])
def test_step1_reads_the_popular_sides_result_against_the_no_vig_close(popular_covers, sign):
    r = S.step1_rows(*_step1_world(popular_covers))
    assert len(r) == 40 and set(r["market"]) == {"spreads"}
    assert (np.sign(r["resid"]) == sign).all() and r["resid"].abs().eq(0.5).all()


def test_step1_leaves_a_push_out_and_the_total_is_the_under():
    signal, close, games = _step1_world(True)
    games = games.assign(home_score=103.0, away_score=100.0)    # the home -3 lands on the number
    r = S.step1_rows(signal, close.iloc[:5], games)
    assert r.empty
    tot = close.iloc[:2].assign(market="totals", close_line=200.0, close_fa=0.4)
    r2 = S.step1_rows(signal, tot, games)                       # 203 is over 200: the under lost
    assert (r2["result"] == 0.0).all() and r2["close_p"].eq(0.6).all() and r2["strength"].eq(2.0).all()


def test_the_step1_report_has_each_band_and_a_slope():
    r = S.step1_report(S.step1_rows(*_step1_world(True)), seasons=(2024,))
    assert r[r["row"] == "band"]["n"].sum() == 40
    assert list(r[r["row"] == "band"]["lo"]) == [10.0, 15.0]
    assert r[r["row"] == "slope per point"]["value"].iloc[0] == pytest.approx(0.0, abs=1e-9)


def test_the_credit_line(tmp_path):
    v = pd.DataFrame({"family": ["POP", "POP", "POP", "POPT"], "market": ["spreads", "h2h", "spreads", "totals"],
                      "side": ["against_popular", "against_popular", "against_popular", "under"],
                      "cut": [5.0, 5.0, 10.0, 1.0], "pool_roi": [0.05, 0.05, 0.05, 0.05],
                      "house5_passes": [True, True, False, True], "pool_n": 300, "house5_failed": ""})
    v.to_parquet(tmp_path / "verdict_house5.parquet")
    d = pd.DataFrame({"market": ["spreads", "spreads"], "cut": [5.0, 10.0], "pool_roi": [0.01, 0.01]})
    d.to_parquet(tmp_path / f"cells_{S.CONTROL_DOG}.parquet")
    got = S.credit_table(tmp_path).set_index(["market", "cut"])["credited_popularity"]
    assert got[("spreads", 5.0)]                 # passes and beats the underdog in the same games
    assert got[("h2h", 5.0)]                     # no control bet counts as 0: +5% beats it
    assert not got[("spreads", 10.0)]            # beat it, failed the verdict
    assert got[("totals", 1.0)]                  # the total has no such control
    d2 = d.assign(pool_roi=[0.09, 0.09])
    d2.to_parquet(tmp_path / f"cells_{S.CONTROL_DOG}.parquet")
    got2 = S.credit_table(tmp_path).set_index(["market", "cut"])["credited_popularity"]
    assert not got2[("spreads", 5.0)]            # passes, but the underdog did better
