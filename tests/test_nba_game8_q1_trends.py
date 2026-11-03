"""The eighth NBA search's lab (docs/nba_models_2026.md section 12): its
synthetic checks, the cell count, and that nothing in it reads a game's own
first quarter when building that game's record."""
from __future__ import annotations

import numpy as np
import pandas as pd

from scripts import nba_game8_q1_trends as Q


def test_synthetic_checks_pass():
    assert Q.synthetic_checks() == {"synthetic_checks": "pass"}


def test_registered_cell_count_is_64():
    spread = (len(Q.WINDOWS) * 3 + len(Q.STEP_CUTS)) * len(Q.SPREAD_CHECKS)
    total = len(Q.WINDOWS) * 3 * 2 * len(Q.TOTAL_CHECKS)
    assert spread + total == Q.EXPECTED_CELLS == 64


def test_a_game_never_counts_in_its_own_record():
    d = pd.to_datetime("2024-01-01") + pd.to_timedelta(np.arange(6), unit="D")
    tg = pd.DataFrame({"game_id": list("abcdef"), "season": 2024, "game_date": d.strftime("%Y-%m-%d"),
                       "tip": d, "team": "AAA", "venue": "home", "ats": [1, 1, 1, 1, 1, -1],
                       "ou": 1.0, "pf": 30.0, "pa": 25.0})
    # the sixth game (a fail) is on the target date: the record is the five before it
    tgt = pd.DataFrame({"season": [2024], "team": "AAA", "venue": "home", "game_date": ["2024-01-06"]})
    assert Q.last_n(tg, tgt, "ats", 5)[0] == 5.0


def test_records_cross_the_season_boundary():
    d = pd.to_datetime(["2024-04-01", "2024-04-03", "2024-04-05", "2024-10-25", "2024-10-27"])
    tg = pd.DataFrame({"game_id": list("abcde"), "season": [2024, 2024, 2024, 2025, 2025],
                       "game_date": d.strftime("%Y-%m-%d"), "tip": d, "team": "AAA", "venue": "away",
                       "ats": [-1, -1, 1, -1, -1], "ou": 1.0, "pf": 30.0, "pa": 25.0})
    tgt = pd.DataFrame({"season": [2025], "team": "AAA", "venue": "away", "game_date": ["2024-10-30"]})
    assert Q.last_n(tg, tgt, "ats", 5)[0] == -3.0


def test_the_spread_check_reads_the_home_number():
    inp = pd.DataFrame({"game_id": ["g"], "season": 2024, "game_date": "2024-02-01",
                        "h_ats5": [-3.0], "a_ats5": [3.0], "h_ats10": np.nan, "a_ats10": np.nan,
                        "h_ou5": 0.0, "a_ou5": 0.0, "h_ou10": np.nan, "a_ou10": np.nan,
                        "h_n": 10, "a_n": 10, "h_pf": 28.0, "h_pa": 28.0, "a_pf": 28.0, "a_pa": 28.0,
                        "h_pn": 10, "a_pn": 10, "h_pace": 99.0, "a_pace": 99.0, "lg_pace": 99.0})
    # level projection; the away team is hot. Home -0.5 means away +0.5: covers a level projection.
    # Home +0.5 means away -0.5: does not.
    for home_number, ok in ((-0.5, True), (0.5, False)):
        nums = pd.DataFrame({"game_id": ["g", "g"], "market": [Q.SPREAD, Q.TOTAL],
                             "number": [home_number, 55.5]})
        s = Q.signals(inp, nums)
        assert s.loc[0, "pick_L5"] == "away" and bool(s.loc[0, "chk_L5"]) is ok


def test_a_cover_is_read_off_the_home_number():
    games = pd.DataFrame({"game_id": ["g", "h"], "season": 2024, "game_date": "2024-02-01",
                          "tip": pd.to_datetime(["2024-02-01 00:00Z", "2024-02-01 01:00Z"]),
                          "home_team": ["HHH", "III"], "away_team": ["AAA", "BBB"],
                          "home_q1": [30.0, 25.0], "away_q1": [25.0, 27.0]})
    nums = pd.DataFrame({"game_id": ["g", "g", "h", "h"], "market": [Q.SPREAD, Q.TOTAL] * 2,
                         "number": [-4.5, 54.5, 2.0, 52.0]})
    tg = Q.team_games(games, nums).set_index(["game_id", "venue"])
    # g: home by 5 at -4.5 covers; 55 over 54.5. h: home loses by 2 at +2: a push; 52 on 52 a push.
    assert tg.loc[("g", "home"), "ats"] == 1 and tg.loc[("g", "away"), "ats"] == -1
    assert tg.loc[("g", "home"), "ou"] == 1 and tg.loc[("g", "away"), "ou"] == 1
    assert tg.loc[("h", "home"), "ats"] == 0 and tg.loc[("h", "away"), "ou"] == 0


def test_each_team_reads_its_record_at_todays_venue():
    # AAA: five home covers, five road fails. Today AAA is the away team, so its record is -5.
    d = pd.to_datetime("2024-01-01") + pd.to_timedelta(np.arange(10), unit="D")
    tg = pd.DataFrame({"game_id": [f"g{i}" for i in range(10)], "season": 2024,
                       "game_date": d.strftime("%Y-%m-%d"), "tip": d, "team": "AAA",
                       "venue": ["home", "away"] * 5, "ats": [1, -1] * 5, "ou": [1, -1] * 5,
                       "pf": 30.0, "pa": 25.0})
    tb = pd.DataFrame({"game_id": tg["game_id"], "team": "AAA", "season": 2024,
                       "game_date": tg["game_date"], "poss": 100.0})
    # the games frame keeps a filtered index, as prepare() passes it (row 7 only)
    games = pd.DataFrame({"game_id": ["t"], "season": 2024, "game_date": ["2024-01-20"],
                          "home_team": ["ZZZ"], "away_team": ["AAA"]}, index=[7])
    inp = Q.game_inputs(games, tg, tb)
    assert inp.loc[0, "a_ats5"] == -5.0 and inp.loc[0, "a_ou5"] == -5.0
    assert np.isnan(inp.loc[0, "h_ats5"])
    assert inp.loc[0, "a_n"] == 10 and inp.loc[0, "a_pf"] == 30.0 and inp.loc[0, "a_pace"] == 100.0
