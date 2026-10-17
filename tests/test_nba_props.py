"""models/nba_props.py: the pure pieces the NBA prop backtest and card both rely on."""
import numpy as np
import pandas as pd

import models.nba_props as nb


def test_team_spread_is_the_home_number_from_each_side():
    # Milwaukee at home -8 (favoured): home reads -8, the visitor +8.
    assert list(nb.team_spread([-8.0, -8.0], [1.0, 0.0])) == [-8.0, 8.0]


def test_names_match_through_nickname_order_and_initial_and_refuse_a_shared_name():
    roster = pd.DataFrame({
        "game_id": ["G"] * 5,
        "player_id": ["1", "2", "3", "4", "5"],
        "player_name": ["Nic Claxton", "Dejounte Murray", "Jalen Green", "Jeff Green", "Jonathan Isaac"],
    })
    priced = pd.DataFrame({"game_id": ["G"] * 5,
                           "player_name": ["Nicolas Claxton", "Murray Dejounte", "J. Green", "J. Isaac", "Nobody"]})
    m = nb.match_names(priced, roster).set_index("player_name")
    assert m.loc["Nicolas Claxton", "player_id"] == "1"
    assert m.loc["Murray Dejounte", "player_id"] == "2"
    assert m.loc["J. Isaac", "player_id"] == "5"
    assert m.loc["J. Green", "how"] == "shared" and pd.isna(m.loc["J. Green", "player_id"])
    assert m.loc["Nobody", "how"] == "none"


def test_settlement_sums_parts_and_counts_double_and_triple_doubles():
    rows = pd.DataFrame({"points": [20, 10, 9], "rebounds": [10, 10, 9], "assists": [3, 10, 9],
                         "steals": [0, 0, 10], "blocks": [0, 0, 1], "fg3_made": [2, 0, 0], "turnovers": [1, 1, 1]})
    pra = nb.BY_MARKET["player_points_rebounds_assists"]
    assert list(nb.settle_value(pra, rows)) == [33, 30, 27]
    dd, td = nb.BY_MARKET["player_double_double"], nb.BY_MARKET["player_triple_double"]
    assert list(nb.settle_value(dd, rows)) == [1.0, 1.0, 0.0]
    assert list(nb.settle_value(td, rows)) == [0.0, 1.0, 0.0]


def test_one_unit_to_win_with_risk_capped_at_three():
    risk, win = nb.stake([-110, 150, -500])
    assert np.allclose(risk, [1.1, 1 / 1.5, 3.0])
    assert np.allclose(win, [1.0, 1.0, 3.0 * 0.2])


def test_half_point_lines_have_no_push_and_whole_lines_do():
    assert nb.p_push(5.0, 4.5, 0.1) == 0.0
    assert nb.p_push(5.0, 5.0, 0.0) > 0.0
    assert np.isclose(nb.p_over(5.0, 4.5, 0.0) + (1 - nb.p_over(5.0, 4.5, 0.0)), 1.0)


def test_injury_status_is_the_latest_submitted_report_before_the_decision():
    t = pd.Timestamp("2026-01-10 23:00", tz="UTC")
    inj = pd.DataFrame({
        "game_id": ["G"] * 5,
        "team": ["AAA", "AAA", "AAA", "BBB", "BBB"],
        "report_ts": [t - pd.Timedelta(hours=3), t - pd.Timedelta(hours=1), t + pd.Timedelta(minutes=30),
                      t - pd.Timedelta(hours=2), t - pd.Timedelta(hours=1)],
        "player_id": ["p1", "p2", "p3", "q1", None],
        "player_name": ["P One", "P Two", "P Three", "Q One", None],
        "status": ["Out", "Questionable", "Out", "Doubtful", "NOT YET SUBMITTED"],
    })
    dec = pd.DataFrame({"game_id": ["G"], "decision_ts": [t]})
    r = nb.injury_asof(inj, dec)
    # AAA: the 1-hour-old report lists only p2 (p1 dropped off it = available); the later report is unseen.
    assert set(r[r.team == "AAA"].player_id) == {"p2"}
    # BBB: its latest report says NOT YET SUBMITTED, so its last submitted one stands.
    assert set(r[r.team == "BBB"].player_id) == {"q1"}


def _synthetic_pairs(n, season, a, b, rng, market="player_points"):
    claimed = rng.uniform(0.05, 0.95, n)
    z = a + b * np.log(claimed / (1 - claimed))
    y = (rng.random(n) < 1 / (1 + np.exp(-z))).astype(float)
    return pd.DataFrame({"season": season, "market": market, "p": claimed, "y": y})


def test_calibration_for_a_season_is_fitted_only_on_the_seasons_before_it():
    rng = np.random.default_rng(3)
    before = _synthetic_pairs(40_000, 2024, -0.30, 0.60, rng)
    # the season being graded carries the opposite relationship: if it leaks in, the fit moves
    same = _synthetic_pairs(40_000, 2025, 0.50, -0.80, rng)
    maps = nb.fit_calibration(pd.concat([before, same]), season=2025)
    a, b = maps["player_points"]
    assert abs(a + 0.30) < 0.05 and abs(b - 0.60) < 0.05
    cal = nb.apply_calibration(np.array([0.2, 0.5, 0.8]), maps["player_points"])
    assert np.all(np.diff(cal) > 0)                       # monotone: the order of claims survives
    assert cal[2] < 0.8 and cal[0] > 0.2                  # an overclaiming model is pulled in


def test_calibration_refuses_a_season_with_nothing_before_it():
    rng = np.random.default_rng(4)
    only_same = _synthetic_pairs(1_000, 2024, 0.0, 1.0, rng)
    try:
        nb.fit_calibration(only_same, season=2024)
    except ValueError:
        return
    raise AssertionError("a calibration with no earlier season must refuse, not fit on the season it grades")


def test_a_proposition_another_model_bets_is_removed_on_every_line_and_side():
    C = pd.DataFrame({"game_id": ["G1", "G1", "G1", "G2"],
                      "player_id": ["7", "7", "7", "7"],
                      "market": ["player_points", "player_points", "player_rebounds", "player_points"],
                      "line": [20.5, 21.5, 8.5, 20.5],
                      "side": ["under", "over", "under", "under"]})
    taken = pd.DataFrame({"game_id": ["G1"], "player_id": [7], "market": ["player_points"]})   # int id on purpose
    out = nb.exclude_taken(C, taken)
    assert list(zip(out.game_id, out.market)) == [("G1", "player_rebounds"), ("G2", "player_points")]


def test_in_season_calibration_reads_only_games_before_the_cutoff_and_skips_thin_markets():
    rng = np.random.default_rng(5)
    cutoff = pd.Timestamp("2023-11-06")
    before = _synthetic_pairs(30_000, 2024, -0.30, 0.60, rng).assign(game_date=cutoff - pd.Timedelta(days=3))
    # games ON the cutoff day have not finished when that week's map is fitted
    on_day = _synthetic_pairs(30_000, 2024, 0.50, -0.80, rng).assign(game_date=cutoff)
    thin = _synthetic_pairs(100, 2024, 0.0, 1.0, rng, market="player_turnovers").assign(
        game_date=cutoff - pd.Timedelta(days=3))
    maps = nb.fit_calibration_before(pd.concat([before, on_day, thin]), cutoff=cutoff, min_pairs=300)
    assert set(maps) == {"player_points"}
    a, b = maps["player_points"]
    assert abs(a + 0.30) < 0.05 and abs(b - 0.60) < 0.05
