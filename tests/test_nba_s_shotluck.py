"""The shot-location search's lab (docs/nba_search_shotluck.md): the zones, what each
gap reads and when, the bad-row rules, the placebo, the cell count. Each rule test here
was run once with the rule broken and watched failing."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from models import nba_team_total_luck as ttl
from models import nba_total_luck as tl
from scripts import nba_game2_verdict as V
from scripts import nba_game_harness as H
from scripts import nba_s_shotluck as S


# ── a small hand-built league ───────────────────────────────────────────────

def _games(rows):
    """rows: (game_id, season, date, home, away, home score, away score)."""
    g = pd.DataFrame(rows, columns=["game_id", "season", "game_date", "home_team", "away_team",
                                    "home_score", "away_score"])
    return g


def _tz_row(gid, season, date, team, opp, **zones):
    """One team-game of tz: `zones` as zone=(attempts, points) for its own shots and
    o_zone=(attempts, points) for its opponent's."""
    r = {"game_id": gid, "season": season, "game_date": date, "team": team, "opp": opp}
    for z in S.ZONES:
        a, p = zones.get(z, (0, 0))
        r[f"att_{z}"], r[f"pz_{z}"] = float(a), float(p)
        oa, op = zones.get(f"o_{z}", (0, 0))
        r[f"oatt_{z}"], r[f"_op_{z}"] = float(oa), float(op)
    r["pts_shots"] = sum(r[f"pz_{z}"] for z in S.ZONES)
    r["opts_shots"] = sum(r[f"_op_{z}"] for z in S.ZONES)
    return r


def _tz(rows):
    return pd.DataFrame(rows).drop(columns=[f"_op_{z}" for z in S.ZONES])


def _targets(rows):
    return pd.DataFrame(rows, columns=["season", "team", "game_date"])


def _rates(season, date, **rate):
    return pd.DataFrame([{"season": season, "game_date": date,
                          **{f"rate_{z}": float(rate.get(z, 0.0)) for z in S.ZONES}}])


# ── zones ───────────────────────────────────────────────────────────────────

ZONE_CASES = [
    # value, x, y, clock, text feet, zone
    (2, 25, 2, 500, 2, "ra"),                  # at the rim
    (2, 25, 4, 500, np.nan, "ra"),             # 4 feet is still the restricted area
    (2, 25, 5, 500, np.nan, "paint"),          # 5 feet straight out: in the key, past the arc
    (2, 33, 13, 500, np.nan, "paint"),         # the key's corner at the free-throw line
    (2, 34, 5, 500, np.nan, "mid"),            # a foot outside the key
    (2, 25, 14, 500, np.nan, "mid"),           # just past the free-throw line
    (3, 2, 5, 500, 24, "corner"),              # the left corner
    (3, 47, 9, 500, 24, "corner"),             # the top of the right corner
    (3, 47, 10, 500, 24, "above"),             # one foot higher: above the break
    (3, 25, 26, 500, 26, "above"),             # the top of the key
    (3, 25, 60, 1, np.nan, "heave"),           # the last second, 60 feet by coordinates
    (3, 25, 20, 2, 40, "heave"),               # the text's distance decides over the coordinates
    (3, 25, 60, 10, np.nan, "above"),          # 60 feet with time on the clock is a shot, not a heave
    (3, 25, 30, 1, np.nan, "above"),           # the buzzer from 30 feet is a shot, not a heave
    (1, 25, 13.75, 500, np.nan, "ft"),         # a free throw
    (1, np.nan, np.nan, 500, np.nan, "ft"),    # 2026-27: free throws carry no coordinates
    (2, np.nan, np.nan, 500, np.nan, "mid"),   # no location: a two is mid-range
    (3, np.nan, np.nan, 500, np.nan, "above"),  # no location: a three is above the break
    (2, 25, 30, 500, np.nan, "mid"),           # a stored two 30 feet out stays a two
    (3, 25, 10, 500, np.nan, "above"),         # a stored three in the key stays a three
    (3, 30, 5, 500, np.nan, "above"),          # a three logged at y <= 9 and dx < 20: a bad location
]


def test_every_zone_edge():
    a = np.array(ZONE_CASES, dtype=object)
    got = S.zone_of(a[:, 0].astype(float), a[:, 1].astype(float), a[:, 2].astype(float), a[:, 3].astype(float),
                    a[:, 4].astype(float))
    assert got.tolist() == a[:, 5].tolist()


def test_a_heave_is_the_same_zone_made_or_missed():
    # zone_of never reads the points, so the zone cannot depend on the outcome
    import inspect
    assert "points" not in inspect.signature(S.zone_of).parameters
    assert S.HEAVE_CLOCK_S == 3.0 and S.HEAVE_FEET == 36.0


# ── the team-game table ─────────────────────────────────────────────────────

def _shots(rows):
    return pd.DataFrame(rows, columns=["espn_game_id", "team_side", "shot_value", "points", "coord_x", "coord_y",
                                       "clock_s", "feet_text"])


def test_side_h_is_the_home_team_and_the_opponent_is_mirrored():
    g = _games([("G1", 2024, "2024-01-01", "HOM", "AWY", 5.0, 3.0)])
    s = _shots([(1, "H", 2, 2, 25, 1, 500, np.nan), (1, "H", 3, 3, 25, 26, 500, np.nan),
                (1, "A", 3, 3, 2, 5, 500, np.nan), (1, "A", 2, 0, 25, 1, 500, np.nan)])
    tz, bad = S.team_game_zones(s, pd.DataFrame({"espn_game_id": [1], "game_id": ["G1"]}), g)
    assert bad.empty
    h = tz[tz["team"] == "HOM"].iloc[0]
    assert h["opp"] == "AWY" and h["pts_shots"] == 5 and h["att_ra"] == 1 and h["att_above"] == 1
    assert h["opts_shots"] == 3 and h["oatt_corner"] == 1 and h["oatt_ra"] == 1
    a = tz[tz["team"] == "AWY"].iloc[0]
    assert a["pts_shots"] == 3 and a["opts_shots"] == 5 and a["oatt_above"] == 1


def test_a_game_whose_plays_do_not_add_up_is_left_out_of_every_sum():
    g = _games([("OK", 2024, "2024-01-01", "HOM", "AWY", 2.0, 3.0),
                ("OFF", 2024, "2024-01-02", "HOM", "AWY", 4.0, 3.0),     # plays say 2 for the home team
                ("GONE", 2024, "2024-01-03", "HOM", "AWY", 2.0, 3.0)])   # no plays at all
    s = _shots([(1, "H", 2, 2, 25, 1, 500, np.nan), (1, "A", 3, 3, 2, 5, 500, np.nan),
                (2, "H", 2, 2, 25, 1, 500, np.nan), (2, "A", 3, 3, 2, 5, 500, np.nan)])
    led = pd.DataFrame({"espn_game_id": [1, 2], "game_id": ["OK", "OFF"]})
    tz, bad = S.team_game_zones(s, led, g)
    assert set(tz["game_id"]) == {"OK"}
    assert dict(zip(bad["game_id"], bad["why"])) == {"OFF": "plays_do_not_add_up", "GONE": "no_plays"}


# ── the league's rate ───────────────────────────────────────────────────────

def _lg(rows):
    """(season, date, attempts, points) at the rim, one team-game each."""
    return _tz([_tz_row(f"g{i}", s, d, "AAA", "BBB", ra=(a, p)) for i, (s, d, a, p) in enumerate(rows)])


def test_the_league_rate_reads_only_games_before_the_date():
    tz = _lg([(2024, "2024-01-01", 300, 300), (2024, "2024-01-02", 300, 600), (2024, "2024-01-03", 300, 900)])
    t = pd.DataFrame({"season": [2024, 2024], "game_date": ["2024-01-02", "2024-01-03"]})
    r = S.league_rates(tz, t).sort_values("game_date")
    # on the 2nd only the 1st counts; on the 3rd the 1st and the 2nd; the 3rd never counts
    assert r["rate_ra"].round(6).tolist() == [1.0, 1.5]


def test_a_thin_zone_reads_last_season_and_a_full_one_never_does():
    tz = _lg([(2023, "2023-03-01", 1000, 1000), (2024, "2024-01-01", 199, 398), (2024, "2024-01-02", 1, 2),
              (2024, "2024-01-03", 300, 600)])
    t = pd.DataFrame({"season": [2024, 2024, 2024], "game_date": ["2024-01-02", "2024-01-03", "2024-01-04"]})
    r = S.league_rates(tz, t).sort_values("game_date")
    # 199 attempts: last season's 1.0. 200 and 500 attempts: this season's 2.0
    assert r["rate_ra"].round(6).tolist() == [1.0, 2.0, 2.0]


def test_the_leagues_drift_stays_out_of_the_gap():
    """A season where every shot beats last season's rate: this season's rate gives no
    league-wide luck. A last-season rate would book it to every team."""
    run = S.synthetic_run()
    z = run["prep"]["proj"]["zone"]
    assert z.groupby("season")["gap_total"].mean().abs().max() < 1.0
    # the same world, every zone reading last season's rate: the drift shows
    prep, world = run["prep"], run["world"]
    targets = tl.team_targets(world["all_games"])
    prior = S.league_rates(prep["tz"], targets, min_att=10 ** 12)
    tb = tl.team_box(world["box"], world["all_games"])
    moved = S.project(world["all_games"], S.rating_variants(tb, prep["tz"], targets, prior)["zone"])
    assert moved.groupby("season")["gap_total"].mean().abs().max() > 1.0


# ── luck ────────────────────────────────────────────────────────────────────

def test_a_team_shooting_the_league_rate_has_no_luck():
    tz = _tz([_tz_row("g1", 2024, "2024-01-01", "AAA", "BBB", ra=(10, 13), above=(10, 10), o_ra=(10, 13), o_above=(10, 10))])
    r = S.as_of_luck(tz, _targets([(2024, "AAA", "2024-01-05")]), _rates(2024, "2024-01-05", ra=1.3, above=1.0))
    assert np.isclose(r["luck_for"].iloc[0], 0.0) and np.isclose(r["luck_against"].iloc[0], 0.0)


def test_luck_is_points_minus_expected_for_each_side():
    tz = _tz([_tz_row("g1", 2024, "2024-01-01", "AAA", "BBB", ra=(10, 16), corner=(5, 3),
                      o_ra=(10, 10), o_above=(10, 15))])
    r = S.as_of_luck(tz, _targets([(2024, "AAA", "2024-01-05")]), _rates(2024, "2024-01-05", ra=1.3, corner=1.2, above=1.0))
    assert np.isclose(r["luck_for"].iloc[0], (16 + 3) - (10 * 1.3 + 5 * 1.2))
    assert np.isclose(r["luck_against"].iloc[0], (10 + 15) - (10 * 1.3 + 10 * 1.0))


def test_a_games_own_shots_never_count_toward_its_luck():
    rows = [_tz_row("g1", 2024, "2024-01-01", "AAA", "BBB", ra=(10, 10)),
            _tz_row("g2", 2024, "2024-01-02", "AAA", "CCC", ra=(10, 30))]       # the target's own date
    r = S.as_of_luck(_tz(rows), _targets([(2024, "AAA", "2024-01-02")]), _rates(2024, "2024-01-02", ra=1.0))
    assert np.isclose(r["luck_for"].iloc[0], 0.0)


def test_last_seasons_shots_never_count_toward_this_seasons_luck():
    rows = [_tz_row("g0", 2023, "2023-04-01", "AAA", "BBB", ra=(10, 30)),
            _tz_row("g1", 2024, "2024-01-01", "AAA", "BBB", ra=(10, 10))]
    r = S.as_of_luck(_tz(rows), _targets([(2024, "AAA", "2024-01-05")]), _rates(2024, "2024-01-05", ra=1.0))
    assert np.isclose(r["luck_for"].iloc[0], 0.0)


def test_luck_lands_on_the_right_row_with_a_filtered_index():
    """as_of_luck sorts by date and merges by key: each team gets its own number, whatever
    order and index the targets arrive with."""
    rows = [_tz_row("g1", 2024, "2024-01-01", "AAA", "BBB", ra=(10, 20)),
            _tz_row("g2", 2024, "2024-01-03", "BBB", "AAA", ra=(10, 5))]
    t = pd.DataFrame({"season": [2024, 2024], "team": ["BBB", "AAA"], "game_date": ["2024-01-05", "2024-01-02"]},
                     index=[40, 7])
    rates = pd.concat([_rates(2024, "2024-01-05", ra=1.0), _rates(2024, "2024-01-02", ra=1.0)], ignore_index=True)
    r = S.as_of_luck(_tz(rows), t, rates).set_index("team")
    assert np.isclose(r.at["AAA", "luck_for"], 10.0) and np.isclose(r.at["BBB", "luck_for"], -5.0)


# ── the gap ─────────────────────────────────────────────────────────────────

def _team_row(team, n, pace, ortg, drtg, ortg_adj, drtg_adj, date="2024-02-01"):
    return {"season": 2024, "team": team, "game_date": date, "n": float(n), "pace": pace, "lg_rtg": 112.0,
            "ortg_raw": ortg, "drtg_raw": drtg, "ortg_adj": ortg_adj, "drtg_adj": drtg_adj}


GAME = _games([("G", 2024, "2024-02-01", "HOM", "AWY", 110.0, 100.0)])


def _gap(home, away):
    return S.project(GAME, pd.DataFrame([home, away])).iloc[0]


def test_opponents_hot_against_a_defence_means_the_under_and_that_team_on_the_spread():
    # opponents made more than expected against HOM: its true defence is better than raw
    p = _gap(_team_row("HOM", 20, 100.0, 112, 112, 112, 110), _team_row("AWY", 20, 100.0, 112, 112, 112, 112))
    assert np.isclose(p["gap_total"], -2.0)     # the projected total falls: the under's side
    assert np.isclose(p["gap_margin"], 2.0)     # HOM is better than raw: the home side
    assert np.isclose(p["part_away"], -2.0)     # the away team scores against that defence
    assert np.isclose(p["part_home"], 0.0)


def test_own_hot_shooting_means_the_under_and_against_that_team_on_the_spread():
    # HOM's own shots dropped more than expected: its true offence is worse than raw
    p = _gap(_team_row("HOM", 20, 100.0, 112, 112, 110, 112), _team_row("AWY", 20, 100.0, 112, 112, 112, 112))
    assert np.isclose(p["gap_total"], -2.0)
    assert np.isclose(p["gap_margin"], -2.0)    # worse than raw: the away side
    assert np.isclose(p["part_home"], -2.0)
    assert np.isclose(p["part_away"], 0.0)


def test_the_parts_add_up_to_the_gaps():
    p = _gap(_team_row("HOM", 20, 98.0, 113, 111, 112, 110.5), _team_row("AWY", 20, 102.0, 110, 114, 111, 113))
    assert np.isclose(p["part_home"] + p["part_away"], p["gap_total"])
    assert np.isclose(p["part_home"] - p["part_away"], p["gap_margin"])
    assert np.isclose(p["part_home"], 1.0 * ((112 - 113) + (113 - 114)))       # pace 100: (98 + 102) / 2 / 100


def test_signal_gives_each_market_its_own_number_and_each_side_its_direction():
    p = pd.DataFrame({"game_id": ["G"], "season": [2024], "gap_total": [5.0], "gap_margin": [-3.0],
                      "part_home": [1.0], "part_away": [4.0]})
    s = S.signal_of(p).set_index("market")["strength"]
    assert s.to_dict() == {"totals": 5.0, "spreads": -3.0, "team_totals_home": 1.0, "team_totals_away": 4.0}
    off = pd.DataFrame({"game_id": "G", "market": ["spreads", "spreads", "totals", "totals", "team_totals_away"],
                        "side": ["home", "away", "over", "under", "under"]})
    got = tl.side_strength(off, S.signal_of(p).drop(columns="season")).set_index(["market", "side"])["strength"]
    assert got[("spreads", "away")] == 3.0 and got[("spreads", "home")] == -3.0
    assert got[("totals", "over")] == 5.0 and got[("totals", "under")] == -5.0
    assert got[("team_totals_away", "under")] == -4.0


def test_a_team_under_ten_games_has_no_gap():
    x = S.project(GAME, pd.DataFrame([_team_row("HOM", 9, 100.0, 112, 112, 112, 110),
                                      _team_row("AWY", 20, 100.0, 112, 112, 112, 112)]))
    assert x.empty
    y = S.project(GAME, pd.DataFrame([_team_row("HOM", 10, 100.0, 112, 112, 112, 110),
                                      _team_row("AWY", 10, 100.0, 112, 112, 112, 112)]))
    assert len(y) == 1


def test_a_margin_of_luck_is_converted_per_possession():
    # 10 lucky points for and 5 lucky points against, on 50 possessions
    tz = _tz([_tz_row("g", 2024, "2024-01-01", "AAA", "BBB", ra=(50, 60), o_ra=(50, 55))])
    tb = pd.DataFrame([{"game_id": "g", "season": 2024, "game_date": "2024-01-01", "team": "AAA", "opp": "BBB",
                        "pts": 60.0, "fg3m": 0.0, "fg3a": 0.0, "ftm": 0.0, "fta": 0.0, "opp_pts": 55.0, "opp_fg3m": 0.0,
                        "opp_fg3a": 0.0, "opp_ftm": 0.0, "opp_fta": 0.0, "poss": 50.0}])
    t = _targets([(2024, "AAA", "2024-01-05")])
    r = S.rating_variants(tb, tz, t, _rates(2024, "2024-01-05", ra=1.0))
    z = r["zone"].iloc[0]
    assert np.isclose(z["ortg_raw"], 120.0) and np.isclose(z["ortg_adj"], 100.0)
    assert np.isclose(z["drtg_raw"], 110.0) and np.isclose(z["drtg_adj"], 100.0)
    f, a = r["for"].iloc[0], r["against"].iloc[0]
    assert np.isclose(f["ortg_adj"], 100.0) and np.isclose(f["drtg_adj"], 110.0)      # offence only
    assert np.isclose(a["ortg_adj"], 120.0) and np.isclose(a["drtg_adj"], 100.0)      # defence only


def test_the_shipped_variant_is_the_live_models_own_gap():
    run = S.synthetic_run()
    w = run["world"]
    tb = tl.team_box(w["box"], w["all_games"])
    live = tl.f4_projections(w["all_games"], tb).set_index("game_id").sort_index()
    mine = run["prep"]["proj"]["shipped"].set_index("game_id").reindex(live.index)
    assert np.allclose(mine["gap_total"], live["gap_total"])
    assert np.allclose(mine["gap_margin"], live["gap_margin"])
    assert np.allclose(mine["part_home"], ttl.home_part(live.reset_index()))


def test_what_the_new_gap_adds_removes_the_shipped_gap_from_earlier_seasons_only():
    z = pd.DataFrame({"game_id": ["a", "b", "c"], "season": [2023, 2023, 2024], "market": "totals",
                      "strength": [2.0, 4.0, 10.0]})
    sh = z.assign(strength=[1.0, 2.0, 3.0])
    out, betas = S.added_signal(z, sh, min_prior=2)
    assert betas["season"].tolist() == [2024] and np.isclose(betas["b"].iloc[0], 2.0)   # 2023 only
    assert out["game_id"].tolist() == ["c"] and np.isclose(out["strength"].iloc[0], 10.0 - 2.0 * 3.0)


# ── impossible numbers ──────────────────────────────────────────────────────

def _quotes(rows):
    return pd.DataFrame(rows, columns=["game_id", "market", "book", "line", "coherent"])


def test_a_number_40_away_from_the_games_median_is_not_that_market():
    q = _quotes([("g", "totals", "fanduel", 225.5, True), ("g", "totals", "betmgm", 226.5, True),
                 ("g", "totals", "draftkings", 226.0, True), ("g", "totals", "bovada", 1.0, True),
                 ("g", "totals", "williamhill_us", 136.5, True), ("g", "totals", "betparx", 200.0, True),
                 ("h", "spreads", "fanduel", -5.5, True), ("h", "spreads", "betmgm", 8.5, True)])
    # filtered, so the index is not 0..n: the rule must not read it
    q = q.iloc[::-1]
    q.index = range(100, 100 + len(q))
    kept, removed = S.drop_impossible(q)
    assert set(removed["line"]) == {1.0, 136.5}
    assert {200.0, 225.5, 226.5, 226.0, -5.5, 8.5} == set(kept["line"])


def test_a_moneyline_row_with_no_number_is_kept():
    q = _quotes([("g", "h2h", "fanduel", np.nan, True), ("g", "totals", "fanduel", 225.5, True)])
    kept, removed = S.drop_impossible(q)
    assert len(kept) == 2 and removed.empty


def test_a_deciding_books_flipped_spread_is_off_market_and_pinnacles_is_not():
    v = _quotes([("g", "spreads", "fanduel", 3.5, True), ("g", "spreads", "draftkings", -3.5, True),
                 ("g", "spreads", "betmgm", -3.5, True), ("g", "spreads", "pinnacle", 3.5, True)])
    v = v.iloc[::-1]
    v.index = range(100, 104)
    kept, removed = S.drop_off_market(v)
    assert removed[["book", "line"]].values.tolist() == [["fanduel", 3.5]]
    assert "pinnacle" in set(kept["book"])


def test_four_points_off_the_median_is_a_price_and_five_is_not():
    v = _quotes([("g", "totals", "fanduel", 230.0, True), ("g", "totals", "draftkings", 226.0, True),
                 ("g", "totals", "betmgm", 226.0, True), ("h", "totals", "fanduel", 231.0, True),
                 ("h", "totals", "draftkings", 226.0, True), ("h", "totals", "betmgm", 226.0, True)])
    _, removed = S.drop_off_market(v)
    assert removed[["game_id", "line"]].values.tolist() == [["h", 231.0]]


def test_the_bad_rows_in_the_world_reach_no_offer():
    run = S.synthetic_run()
    prep, bad = run["prep"], run["world"]["bad"]
    all_off = pd.concat([prep["at"]["A"]["neutral"], prep["at"]["C"]["neutral"]], ignore_index=True)
    # the world does hold them: they were in the stored frames before the rules
    for key, frame in (("total", prep["raw_q"]), ("spread", prep["raw_q"]), ("team_total", prep["raw_pe"])):
        gid, book, line = bad[key]
        assert ((frame["game_id"] == gid) & (frame["book"] == book) & (frame["line"] == line)).any(), key
    for key in ("total", "spread"):
        gid, book, line = bad[key]
        assert not ((all_off["game_id"] == gid) & (all_off["book"] == book) & (all_off["line"] == line)).any(), key
    gid, book, line = bad["team_total"]
    nd = prep["neutral_d"]
    assert not ((nd["game_id"] == gid) & (nd["book"] == book) & (nd["line"] == line)).any()
    assert ((prep["removed_tt"]["game_id"] == gid) & (prep["removed_tt"]["line"] == line)).any()


def test_the_impossible_total_is_removed_by_its_own_rule_before_any_decision():
    """The off-market rule at a decision would also catch this deciding book's 9.5, so an
    offer's absence cannot show the impossible-number rule ran. The rule's own output can,
    and it is what keeps such a number out of Pinnacle's close, which no decision rule reads."""
    prep, (gid, book, line) = (lambda r: (r["prep"], r["world"]["bad"]["total"]))(S.synthetic_run())
    gone = prep["removed_full"]
    assert ((gone["game_id"] == gid) & (gone["book"] == book) & (gone["line"] == line)).any()
    kept = prep["data"].quotes
    assert not ((kept["game_id"] == gid) & (kept["book"] == book) & (kept["line"] == line)).any()


def test_a_pinnacle_row_is_not_spared_by_the_impossible_number_rule():
    q = _quotes([("g", "totals", "pinnacle", 1.0, True), ("g", "totals", "fanduel", 225.5, True),
                 ("g", "totals", "betmgm", 226.5, True)])
    kept, removed = S.drop_impossible(q)
    assert removed["book"].tolist() == ["pinnacle"] and "pinnacle" not in set(kept["book"])


def test_the_synthetic_checks_pass_and_refuse_a_world_with_no_bad_row():
    assert S.synthetic_checks()["synthetic_checks"] == "pass"
    run = S.synthetic_run()
    saved = run["prep"]["removed_full"]
    run["prep"]["removed_full"] = saved.iloc[:0]
    try:
        with pytest.raises(AssertionError):
            S.synthetic_checks()
    finally:
        run["prep"]["removed_full"] = saved


def test_a_decision_without_the_rule_would_take_the_flipped_number():
    """The check above tests something: with the off-market rule off, the flipped spread
    is the home side's highest-EV offer on its game."""
    run = S.synthetic_run()
    prep, (gid, book, line) = run["prep"], run["world"]["bad"]["spread"]
    t = prep["at"]["C"]["times"]
    with S._CoarsePricing():
        vis = H.visible(prep["data"].quotes, t)
        n = H.fair_offers(H.offers(vis), H.market_fair(vis[~(vis["book"].eq(book) & vis["game_id"].eq(gid))], prep["sig"]))
    n = n[(n["game_id"] == gid) & (n["market"] == "spreads")]
    side = "home" if line > 0 else "away"       # a flipped number sits on the side it flatters
    best = H.choose(n, -np.inf, sides=[side]).iloc[0]
    assert best["book"] == book and best["line"] == line


# ── the placebo ─────────────────────────────────────────────────────────────

def test_the_best_offer_is_what_the_cell_takes_at_every_cut_and_under_a_shuffle():
    """The placebo runs and the bands read best_offers instead of every offer: the same
    bets, in every group, at every cut, real or shuffled."""
    run = S.synthetic_run()
    prep = run["prep"]
    key = ["game_id", "market", "side", "book", "line", "price"]
    for point, market, sides, neutral, dat, _ch, _t, _c, _s in S.groups(prep):
        nm, s, cand = S.group_frames(neutral, prep["signals"]["zone"], market)
        best = S.best_offers(nm, sides)
        assert len(best) < len(nm) and "sigma" not in best
        sh = S.G5.gap_shuffles(s, dat.games, (1,))[0]
        for label, signal in (("real", s), ("shuffled", sh)):
            full, slim = S.tl.side_strength(nm, signal), S.tl.side_strength(best, signal)
            for side in sides:
                for cut in S.CUTS:
                    a = S._pick(full, cut, side)[key].sort_values(key).reset_index(drop=True)
                    b = S._pick(slim, cut, side)[key].sort_values(key).reset_index(drop=True)
                    pd.testing.assert_frame_equal(a, b, check_dtype=False, obj=f"{point} {market} {side} {cut} {label}")
                    assert len(a) > 0


def test_one_markets_quotes_give_the_same_still_offered_answer():
    run = S.synthetic_run()
    prep = run["prep"]
    dat = prep["data"]
    nm, _, cand = S.group_frames(prep["at"]["A"]["neutral"], prep["signals"]["zone"], "totals")
    bets = S._pick(cand, 1.0, "over")
    one = H.Data(games=dat.games, quotes=dat.quotes[dat.quotes["market"] == "totals"], fetches=dat.fetches)
    a, b = H.next_fetch_check(bets, dat), H.next_fetch_check(bets, one)
    assert a.tolist() == b.tolist() and a.any()


def test_the_bands_read_the_same_bets_as_the_full_offers():
    run = S.synthetic_run()
    prep = run["prep"]
    r = pd.DataFrame(run["rows"])
    row = r[(r["point"] == "C") & (r["market"] == "totals") & (r["side"] == "under") & (r["cut"] == 2.0)].iloc[0]
    _, _, cand = S.group_frames(prep["at"]["C"]["neutral"], prep["signals"]["zone"], "totals")
    pool = tuple(int(x) for x in row["pool_seasons"].split(","))
    want = S.G5.band_columns(cand, "under", "strength", S.G5.band_bounds(S.CUTS, 1), prep["data"].games, pool)
    for k, v in want.items():
        assert (row[k] == v) or (np.isnan(row[k]) and np.isnan(v)) or (row[k] == pytest.approx(v)), k


def test_the_placebo_moves_a_gap_only_within_its_date_and_keeps_every_number():
    run = S.synthetic_run()
    prep = run["prep"]
    nm, s, _ = S.group_frames(prep["at"]["C"]["neutral"], prep["signals"]["zone"], "totals")
    dates = prep["data"].games.set_index("game_id")["game_date"]
    sh = S.G5.gap_shuffles(s, prep["data"].games, (1,))[0]
    a = s.assign(d=s["game_id"].map(dates)).sort_values(["d", "strength"]).groupby("d")["strength"].apply(list)
    b = sh.assign(d=sh["game_id"].map(dates)).sort_values(["d", "strength"]).groupby("d")["strength"].apply(list)
    assert a.to_dict() == b.to_dict()
    assert set(sh["game_id"]) == set(s["game_id"]) and sh["strength"].tolist() != s["strength"].tolist()


def test_the_placebo_is_a_null_on_the_world():
    run = S.synthetic_run()
    cells, dates = S.placebo_null(run["prep"], seeds=(1, 2, 3))
    by = cells.groupby("point")[["placebo_bets", "placebo_same"]].sum()
    share = 1.0 - by["placebo_same"] / by["placebo_bets"]
    assert set(by.index) == {"A", "C", "D"} and (share > 0.5).all(), share
    assert (dates["games_per_date"] > 1).all()


def test_the_share_at_random_is_worked_by_hand_and_reads_by_date_not_position():
    # date a: 2 of 4 games fire, date b: 1 of 1. Same-bet share (4/4 + 1/1) / 3 = 2/3.
    fired = pd.Series({"b": 1, "a": 2})
    games = pd.Series({"a": 4, "b": 1, "c": 9})
    assert S.share_different_at_random(fired, games) == pytest.approx(1.0 / 3.0)
    assert np.isnan(S.share_different_at_random(pd.Series({"a": 0}), games))


def test_the_measured_placebo_matches_a_perfect_shuffle_on_the_world():
    cells, _ = S.placebo_null(S.synthetic_run()["prep"], seeds=tuple(range(1, 21)))
    big = cells[cells["real_bets"] >= 100]
    assert len(big) >= 12
    assert (big["share_different"] - big["share_different_at_random"]).abs().max() < 0.03


def test_placebo_null_counts_a_repeat_as_the_same_bet():
    """The shuffle that repeats the real bets reads 0, not a share made up of something else."""
    run = S.synthetic_run()
    prep = run["prep"]
    alone = dict(prep)
    nm, s, cand = S.group_frames(prep["at"]["C"]["neutral"], prep["signals"]["zone"], "totals")
    # every game on its own date: nothing can move
    games = prep["data"].games.assign(game_date=lambda d: d["game_id"])
    alone["data"] = H.Data(games=games, quotes=prep["data"].quotes, fetches=prep["data"].fetches)
    alone_groups = [g for g in S.groups(alone) if g[0] == "C" and g[1] == "totals"]
    real_groups = S.groups
    try:
        S.groups = lambda _p: alone_groups
        cells, _ = S.placebo_null(alone, seeds=(1,))
    finally:
        S.groups = real_groups
    assert (cells["share_different"].dropna() == 0.0).all()


# ── the cells and the verdict ───────────────────────────────────────────────

def test_the_registered_cells_are_exactly_48():
    c = list(S.cell_list())
    assert len(c) == 48 == S.EXPECTED_CELLS and len(set(c)) == 48
    assert {x[3] for x in c} == {1.0, 2.0, 3.0, 4.0}
    assert sum(1 for x in c if x[0] == "A") == 16 and sum(1 for x in c if x[0] == "C") == 16
    assert sum(1 for x in c if x[0] == "D") == 16


def test_the_world_holds_every_market_with_bets_in_each():
    rows = pd.DataFrame(S.synthetic_run()["rows"])
    assert rows.groupby(["point", "market", "side"]).ngroups == 12
    assert (rows.groupby(["point", "market", "side"])["pool_n"].sum() > 0).all()


def test_the_verdict_reads_the_cells_and_refuses_the_wrong_placebo_count(tmp_path):
    run = S.synthetic_run()
    S.L.write_cells(run["rows"], tmp_path / "cells_SL.parquet")
    S.L.write_cells(run["ctl"], tmp_path / "cells_control_SL.parquet")
    cells = V.load_cells(tmp_path)
    v = V.house_verdict_bands(cells, n_placebo=2)
    assert len(v) == 48 and set(v["family"]) == {"SL"}       # controls are never judged
    assert (v["band_slots"] >= 2).all()
    with pytest.raises(ValueError, match="placebo count"):
        V.house_verdict_bands(cells)                          # 200 is the bar; 2 runs do not pass it


def test_the_report_reads_a_thin_cell_as_too_few_games(tmp_path, capsys):
    run = S.synthetic_run()
    S.L.write_cells(run["rows"], tmp_path / "cells_SL.parquet")
    S.L.write_cells(run["ctl"], tmp_path / "cells_control_SL.parquet")
    S.save_parquet(S.overlap(run["prep"]), tmp_path / "overlap_SL.parquet")
    out = S.report(tmp_path, n_placebo=2)
    assert len(out) == 48 and {"shipped_n", "added_roi", "against_roi", "for_roi", "share_same_bet"} <= set(out.columns)
    thin = out[out["pool_n"] < 200]
    assert len(thin) and (thin["reading"] == "too few games to tell").all()
    assert "of 48 pass" in capsys.readouterr().out


def test_controls_carry_no_placebo_and_every_family_ran():
    ctl = pd.DataFrame(S.synthetic_run()["ctl"])
    assert set(ctl["family"]) == set(S.CONTROLS.values())
    assert (ctl.groupby("family").size() == 16).all()
    assert ctl["placebo_rois"].map(len).eq(0).all()
    assert (ctl.groupby("family")["pool_n"].sum() > 0).all()


def test_the_pull_only_reads():
    for sql in (S.SHOT_SQL, S.LEDGER_SQL):
        assert sql.lstrip().upper().startswith("SELECT ")
        for word in ("INSERT", "UPDATE ", "DELETE", "DROP", "ALTER", "CREATE"):
            assert word not in sql.upper(), word


def test_bands_run_along_the_cut_axis():
    rows = pd.DataFrame(S.synthetic_run()["rows"])
    r = rows[(rows["point"] == "C") & (rows["market"] == "totals") & (rows["side"] == "over")].sort_values("cut")
    assert r.iloc[0][["band0_lo", "band0_hi", "band1_lo", "band1_hi"]].tolist() == [0.0, 1.0, 1.0, 2.0]
    top = r.iloc[-1]
    assert top["band0_lo"] == 3.0 and top["band0_hi"] == 4.0 and top["band1_lo"] == 4.0 and np.isinf(top["band1_hi"])


def test_full_game_cells_pool_five_seasons_and_team_totals_three():
    rows = pd.DataFrame(S.synthetic_run()["rows"])
    assert set(rows.loc[rows["point"] != "D", "pool_seasons"]) == {"2022,2023,2024,2025,2026"}
    assert set(rows.loc[rows["point"] == "D", "pool_seasons"]) == {"2024,2025,2026"}


def test_each_family_asks_for_its_own_choosing_seasons():
    """The harness drops a season with no quotes, which hides a wrong ask in pool_seasons:
    the ask itself is the only place a team total reading the full game's seasons shows."""
    rows = pd.DataFrame(S.synthetic_run()["rows"])
    assert set(rows.loc[rows["point"] != "D", "choose_seasons_asked"]) == {"2022,2023,2024,2025"}
    assert set(rows.loc[rows["point"] == "D", "choose_seasons_asked"]) == {"2024,2025"}
    assert set(rows.loc[rows["point"] == "D", "choose_seasons"]) == {"2024,2025"}
    for point, _m, _s, _n, _d, choose, *_rest in S.groups(S.synthetic_run()["prep"]):
        assert tuple(choose) == ((2024, 2025) if point == "D" else (2022, 2023, 2024, 2025)), point


def _only_team_total_purchases(prep):
    """The lab's first version: decision times counted only from purchases holding team totals."""
    return {**prep, "times_d": H.per_event_times(prep["raw_pe"], "D")}


def test_a_season_missing_team_totals_on_some_games_stays_in_the_pool():
    """2023-24 has a per-game purchase on every game and team totals on 1,138 of 1,230. The
    95% check counts purchases, so all three registered seasons stay in every team-total cell."""
    run = S.synthetic_run()
    world, prep = run["world"], run["prep"]
    games = world["games_p"][world["games_p"]["season"] == 2024]
    pe = world["pe"][world["pe"]["season"] == 2024]
    tt = set(pe.loc[pe["market"].isin(list(S.TT_SIDES)), "game_id"])
    # the world really holds the case: a purchase on every game, with team totals missing on about 8%
    assert set(pe["game_id"]) == set(games["game_id"])
    assert world["no_team_totals"] == set(games["game_id"]) - tt
    assert 0.90 <= len(tt) / len(games) <= 0.93
    assert set(pe.loc[pe["game_id"].isin(world["no_team_totals"]), "market"]) == {"totals_h1"}
    rows = pd.DataFrame(run["rows"])
    d = rows[rows["point"] == "D"]
    assert len(d) == 16
    assert set(d["gate_dropped"]) == {""}
    assert set(d["choose_seasons"]) == {"2024,2025"}
    assert set(d["pool_seasons"]) == {"2024,2025,2026"}
    assert (d["gate_cov_2024"] == 1.0).all()


def test_a_game_with_a_purchase_and_no_team_total_has_a_time_and_no_offer():
    run = S.synthetic_run()
    prep, gone = run["prep"], run["world"]["no_team_totals"]
    assert gone <= set(prep["times_d"]["game_id"])
    assert not gone & set(prep["neutral_d"]["game_id"])
    # no team-total game's decision time moves
    both = prep["times_d"].merge(H.per_event_times(prep["raw_pe"], "D"), on="game_id", suffixes=("", "_rows"))
    assert len(both) and (both["T"] == both["T_rows"]).all()
    reach = S.team_total_reach(prep).set_index("season")
    assert reach.loc[2024, "games"] - reach.loc[2024, "team_total_games"] == len(gone)
    assert reach.loc[2024, "decision_games"] == reach.loc[2024, "games"]
    assert reach.loc[2024, "decision_games_counting_team_total_purchases_only"] == reach.loc[2024, "team_total_games"]
    assert (reach["decision_times_that_differ"] == 0).all()
    # that last column can read other than 0: one game's time moved by a minute shows as one
    moved = prep["times_d"].copy()
    moved.loc[moved["game_id"] == both["game_id"].iloc[0], "T"] -= pd.Timedelta(minutes=1)
    assert S.team_total_reach({**prep, "times_d": moved})["decision_times_that_differ"].sum() == 1


def test_the_gate_table_reads_what_the_cells_read():
    """With only team-total purchases counted the harness really drops 2023-24, and the table
    says so; on the times the lab builds it drops nothing."""
    prep = S.synthetic_run()["prep"]
    good = S.season_gate(prep)
    assert len(good) == 6 and set(good["dropped"]) == {""} and S.gate_refusals(good) == []
    assert set(good.loc[good["point"] == "D", "kept"]) == {"2024,2025"}
    assert set(good.loc[good["point"] != "D", "kept"]) == {"2022,2023,2024,2025"}
    broken = _only_team_total_purchases(prep)
    gate = S.season_gate(broken)
    assert set(gate.loc[gate["point"] == "D", "dropped"]) == {"2024"}
    assert set(gate.loc[gate["point"] == "D", "kept"]) == {"2025"}
    assert (gate.loc[gate["point"] == "D", "cov_2024"] < H.GATE_MIN).all()
    assert set(gate.loc[gate["point"] != "D", "dropped"]) == {""}
    why = S.gate_refusals(gate)
    assert len(why) == 2 and all("drops 2024" in w for w in why)
    rows = pd.DataFrame(S.emit(broken, "zone", S.FAMILY, only={("D", "team_totals_home")})[0])
    assert set(rows["gate_dropped"]) == {"2024"} and set(rows["pool_seasons"]) == {"2025,2026"}


def test_smoke_and_full_refuse_a_season_that_would_drop(tmp_path, monkeypatch, capsys):
    broken = _only_team_total_purchases(S.synthetic_run()["prep"])

    def not_reached(*a, **k):
        raise AssertionError("the run went past the seasons check")
    monkeypatch.setattr(S, "synthetic_checks", lambda: {"synthetic_checks": "pass"})
    monkeypatch.setattr(S, "load_shots", lambda folder: (None, None))
    monkeypatch.setattr(S.G5, "load_real", lambda cache, require: {
        "data": None, "all_games": None, "games_p": None, "pe": None, "graded": S.TT_GRADED, "tb": None})
    monkeypatch.setattr(S, "assemble", lambda *a, **k: broken)
    monkeypatch.setattr(S, "coverage", not_reached)
    monkeypatch.setattr(S, "emit", not_reached)
    monkeypatch.setenv(S.SHOTS_ENV, str(tmp_path))
    with pytest.raises(SystemExit):
        S.smoke(tmp_path)
    out = capsys.readouterr().out
    assert "THE SEASONS EACH GROUP CHOOSES ON" in out and "REFUSED: D team_totals_home" in out and "drops 2024" in out
    monkeypatch.setenv(S.GO_ENV, "1")
    monkeypatch.setenv(S.RESULTS_ENV, str(tmp_path / "results"))
    monkeypatch.setenv(S.BETS_ENV, str(tmp_path / "bets"))
    for f in (S.P.LEDGER_FILE, S.SHOTS_FILE, S.SHOT_GAMES_FILE):
        (tmp_path / f).write_bytes(b"x")
    with pytest.raises(SystemExit):
        S.full(tmp_path)
    assert "REFUSED: D team_totals_away" in capsys.readouterr().out
    assert not (tmp_path / "results").exists()


def test_the_counts_never_grade():
    run = S.synthetic_run()
    real_grade = H.grade

    def refuse(*a, **k):
        raise AssertionError("counts graded a bet")
    H.grade = refuse
    try:
        c = S.counts(run["prep"])
        o = S.overlap(run["prep"])
        S.placebo_null(run["prep"], seeds=(1,))
    finally:
        H.grade = real_grade
    assert len(c) == 48 and len(o) == 48 and (c["bets_pooled"] > 0).any()


def test_the_timing_grades_on_invented_scores_only():
    g = pd.DataFrame({"game_id": ["a", "b"], "season": 2024, "game_date": "2024-01-01", "home_score": [100.0, 120.0],
                      "away_score": [90.0, 95.0], "home_q1": [30.0, 31.0], "away_q1": [25.0, 26.0],
                      "home_h1": [55.0, 60.0], "away_h1": [50.0, 45.0]})
    f = S.scrambled_games(g)
    assert not any(c in f for c in H.PERIOD_COLS)
    assert f["game_id"].tolist() == ["a", "b"] and len(f) == 2
    many = pd.DataFrame({"game_id": [str(i) for i in range(400)], "home_score": 110.0, "away_score": 100.0})
    sc = S.scrambled_games(many)
    assert sc["home_score"].nunique() > 5 and (sc["home_score"] == 110.0).mean() < 0.2
    assert (S.scrambled_games(many)["home_score"] == sc["home_score"]).all()     # the same invention each run


def test_the_live_overlap_uses_each_live_models_own_cut_and_side():
    run = S.synthetic_run()
    prep = run["prep"]
    same_bet, same_game = S.live_bets(prep)
    assert S.LIVE_OVER_CUT == tl.GAP_CUT == 3.0 and S.LIVE_TT_CUT == ttl.GAP_CUT == 2.0
    assert {(k[1], k[2]) for k in same_bet} <= {("totals", "over"), ("team_totals_home", "under")}
    o = S.overlap(prep)
    others = o[~(((o["market"] == "totals") & (o["side"] == "over"))
                 | ((o["market"] == "team_totals_home") & (o["side"] == "under")))]
    assert (others["same_bet"] == 0).all()
    assert len(same_game) >= len({k[0] for k in same_bet})


def test_bets_write_with_no_pricing_object(tmp_path, monkeypatch):
    """run_cells' bet files hold numbers and strings; an offers frame saved through
    save_parquet drops the ResidDist it carries."""
    run = S.synthetic_run()
    prep = run["prep"]
    monkeypatch.setenv(S.BETS_ENV, str(tmp_path / "bets"))
    rows, _ = S.emit(prep, "zone", S.FAMILY, only={("C", "totals")})
    files = list((tmp_path / "bets").glob("bets_*.parquet"))
    assert files and len(rows) == 8
    back = pd.read_parquet(files[0])
    assert {"game_id", "market", "side", "line", "price", "units"} <= set(back.columns)
    assert not ({"sigma", "sigma1"} & set(back.columns))
    n = prep["at"]["C"]["neutral"].head(50)
    assert "sigma" in n.columns and isinstance(n["sigma"].iloc[0], H.ResidDist)
    S.save_parquet(n, tmp_path / "offers.parquet")
    assert "sigma" not in pd.read_parquet(tmp_path / "offers.parquet").columns


def test_full_refuses_without_the_owners_go(tmp_path, monkeypatch):
    for k in (S.GO_ENV, S.RESULTS_ENV, S.BETS_ENV):
        monkeypatch.delenv(k, raising=False)
    why = S.refuse_full(tmp_path, tmp_path)
    text = " ".join(why)
    assert S.GO_ENV in text and S.RESULTS_ENV in text and S.BETS_ENV in text
    assert S.SHOTS_FILE in text and S.SHOT_GAMES_FILE in text
    monkeypatch.setenv(S.GO_ENV, "1")
    monkeypatch.setenv(S.RESULTS_ENV, str(tmp_path))
    monkeypatch.setenv(S.BETS_ENV, str(tmp_path))
    for f in (S.P.LEDGER_FILE,):
        (tmp_path / f).write_bytes(b"x")
    for f in (S.SHOTS_FILE, S.SHOT_GAMES_FILE):
        (tmp_path / f).write_bytes(b"x")
    assert S.refuse_full(tmp_path, tmp_path) == []
