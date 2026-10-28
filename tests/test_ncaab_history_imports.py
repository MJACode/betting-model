"""The free NCAAB history importers: line archives (Prediction Tracker, SBRO)
in our sign convention and matched onto ESPN games by date and score, and the
sportsdataverse team/player box import (data/ingestors/ncaab_archive_import.py,
ncaab_sdv_import.py). No network, no database."""

import json

import pandas as pd

from data.ingestors import ncaab_archive_import as ai
from data.ingestors import ncaab_sdv_import as si


def test_prediction_tracker_lines_are_flipped_into_the_home_number():
    # PT: +3 means the HOME team is favoured by 3. Ours: home -3.
    df = pd.DataFrame([{"date": "11/03/2025", "home": "Alabama", "hscore": 91, "road": "North Dakota",
                        "rscore": 62, "line": 35.5, "lineopen": 29.5, "neutral": 0, "linemassey": 30.1}])
    r = ai.pt_rows(df, 2026)[0]
    assert r["game_date"] == "2025-11-03"
    assert r["close_spread_home"] == -35.5 and r["open_spread_home"] == -29.5
    assert json.loads(r["systems"]) == {"linemassey": 30.1}    # predicted HOME margin, as given
    assert r["season"] == 2026 and r["source"] == ai.PT_SOURCE


def test_a_corrupt_prediction_tracker_line_becomes_null():
    df = pd.DataFrame([{"date": "03/13/2022", "home": "Iowa", "hscore": 75, "road": "Purdue",
                        "rscore": 66, "line": -489, "lineopen": None, "neutral": 1}])
    r = ai.pt_rows(df, 2022)[0]
    assert r["close_spread_home"] is None and r["neutral"] is True


def _sbro(v_open, h_open, v_close, h_close, date=1106, vh=("V", "H")):
    return pd.DataFrame([
        {"Date": date, "Rot": 501, "VH": vh[0], "Team": "Towson", "1st": 20, "2nd": 22, "Final": 42,
         "Open": v_open, "Close": v_close, "ML": 6500, "2H": 60.5},
        {"Date": date, "Rot": 502, "VH": vh[1], "Team": "Virginia", "1st": 38, "2nd": 35, "Final": 73,
         "Open": h_open, "Close": h_close, "ML": -16500, "2H": 13},
    ])


def test_sbro_home_favourite_and_total_are_split_from_the_two_cells():
    r = ai.sbro_rows(_sbro(130, 25, 129, 26), 2019)[0]
    assert r["game_date"] == "2018-11-06"
    assert (r["open_spread_home"], r["open_total"]) == (-25, 130)
    assert (r["close_spread_home"], r["close_total"]) == (-26, 129)
    assert (r["home_ml"], r["away_ml"]) == (-16500, 6500)
    assert r["home_name"] == "Virginia" and r["away_name"] == "Towson"


def test_sbro_visitor_favourite_pickem_and_january_year():
    r = ai.sbro_rows(_sbro(4.5, 141, "pk", 140.5, date=115), 2019)[0]
    assert r["game_date"] == "2019-01-15"
    assert r["open_spread_home"] == 4.5 and r["open_total"] == 141
    assert r["close_spread_home"] == 0.0 and r["close_total"] == 140.5


def test_sbro_neutral_court_is_flagged():
    r = ai.sbro_rows(_sbro(130, 25, 129, 26, vh=("N", "N")), 2019)[0]
    assert r["neutral"] is True


GAMES = [
    {"game_id": "NCAAB_2018-11-06_towson_virginia", "game_date": "2018-11-06",
     "home_team": "Virginia", "away_team": "Towson", "home_score": 73, "away_score": 42},
    {"game_id": "NCAAB_2018-11-06_a_b", "game_date": "2018-11-06",
     "home_team": "B", "away_team": "A", "home_score": 70, "away_score": 60},
    {"game_id": "NCAAB_2018-11-06_c_d", "game_date": "2018-11-06",
     "home_team": "Dartmouth", "away_team": "Cornell", "home_score": 70, "away_score": 60},
]


def _arch(key, d, home, away, hs, as_):
    return {"row_key": key, "game_date": d, "home_name": home, "away_name": away,
            "home_score": hs, "away_score": as_}


def test_rows_match_on_date_and_scores_and_read_orientation_off_the_scores():
    hits = {k: (g, f, m) for k, g, f, m in ai.match_rows([
        _arch("same", "2018-11-06", "Virginia", "Towson", 73, 42),
        _arch("flip", "2018-11-06", "Towson", "Virginia", 42, 73),
        _arch("late", "2018-11-07", "Virginia", "Towson", 73, 42),
    ], GAMES)}
    assert hits["same"] == ("NCAAB_2018-11-06_towson_virginia", False, "scores")
    assert hits["flip"] == ("NCAAB_2018-11-06_towson_virginia", True, "scores")
    assert hits["late"][0] == "NCAAB_2018-11-06_towson_virginia" and hits["late"][2] == "scores_pm1"


def test_same_scores_on_one_day_fall_back_to_names_and_ambiguity_stays_unmatched():
    hits = {k: g for k, g, _, _ in ai.match_rows([
        _arch("named", "2018-11-06", "Dartmouth", "Cornell", 70, 60),
        _arch("nameless", "2018-11-06", "Zzz", "Yyy", 70, 60),
    ], GAMES)}
    assert hits.get("named") == "NCAAB_2018-11-06_c_d"
    assert "nameless" not in hits


def test_oriented_turns_a_flipped_row_round():
    row = {"flipped": True, "open_spread_home": 4.5, "close_spread_home": 3.0, "h2_spread_home": None,
           "home_ml": 150, "away_ml": -170, "home_score": 60, "away_score": 70,
           "home_h1": 30, "away_h1": 31, "home_h2": 30, "away_h2": 39,
           "home_name": "A", "away_name": "B"}
    o = ai.oriented(row)
    assert o["close_spread_home"] == -3.0 and o["open_spread_home"] == -4.5
    assert (o["home_ml"], o["away_ml"]) == (-170, 150)
    assert (o["home_score"], o["away_score"]) == (70, 60) and o["home_name"] == "B"
    assert ai.oriented({"flipped": False, "close_spread_home": 3.0})["close_spread_home"] == 3.0


def test_team_box_rows_key_on_the_ncaa_contest_and_carry_the_opponent():
    # ESPN's game id is NULL before 2022-23, so the key is (contest, team name).
    df = pd.DataFrame([
        {"contest_id": "10039", "team": "Vanderbilt", "home": "Vanderbilt", "away": "Austin Peay",
         "espn_game_id": None, "team_espn_team_id": "238", "home_espn_team_id": "238",
         "away_espn_team_id": "2046", "team_ncaa_team_id": "111240",
         "home_ncaa_team_id": "111240", "away_ncaa_team_id": "110954",
         "o_poss": 66, "pts": 85, "to": 8},
        {"contest_id": "10039", "team": "Austin Peay", "home": "Vanderbilt", "away": "Austin Peay",
         "espn_game_id": None, "team_espn_team_id": "2046", "home_espn_team_id": "238",
         "away_espn_team_id": "2046", "team_ncaa_team_id": "110954",
         "home_ncaa_team_id": "111240", "away_ncaa_team_id": "110954",
         "o_poss": 67, "pts": 79, "to": 14},
        {"contest_id": "10039", "team": "Austin Peay", "o_poss": 99, "pts": 0, "to": 0},
        {"contest_id": "10040", "team": "Some D-II School", "home": "Oakland",
         "away": "Some D-II School", "team_espn_team_id": None, "o_poss": 60, "pts": 50, "to": 5},
    ])
    rows = si.team_rows(df, 2018, {"10039": "2017-11-10"})
    got = [(r["contest_id"], r["team"], r["team_espn_id"], r["opp_espn_id"], r["is_home"], r["tov"])
           for r in rows]
    assert got == [("10039", "Vanderbilt", 238, 2046, True, 8.0),
                   ("10039", "Austin Peay", 2046, 238, False, 14.0),
                   ("10040", "Some D-II School", None, None, False, 5.0)]
    assert rows[0]["game_date"] == "2017-11-10" and rows[0]["espn_game_id"] is None
    assert all(r["source"] == si.SOURCE for r in rows)


def test_schedule_dates_are_iso():
    df = pd.DataFrame([{"contest_id": "10039", "game_date": "11/10/2017"},
                       {"contest_id": "x", "game_date": ""}])
    assert si.schedule_dates(df) == {"10039": "2017-11-10"}


def test_player_seasons_sum_by_team_and_folded_name():
    df = pd.DataFrame([
        {"espn_game_id": "1", "team_espn_team_id": "150", "clean_name": "C.J. Walker", "mins": 20, "pts": 10},
        {"espn_game_id": "2", "team_espn_team_id": "150", "clean_name": "CJ Walker", "mins": 25, "pts": 12},
        {"espn_game_id": "2", "team_espn_team_id": "151", "clean_name": "CJ Walker", "mins": 5, "pts": 0},
    ])
    rows = {(r["team_espn_id"], r["player_key"]): r for r in si.player_rows(df, 2026)}
    duke = rows[(150, "cj walker")]
    assert duke["games"] == 2 and duke["mins"] == 45 and duke["pts"] == 22
    assert rows[(151, "cj walker")]["mins"] == 5


def test_player_key_folds_accents_case_and_punctuation():
    assert si.player_key("José O'Neal Jr.") == "jose oneal jr"
