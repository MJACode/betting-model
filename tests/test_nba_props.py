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
