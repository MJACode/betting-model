"""ESPN play-by-play ingestor (data/ingestors/nba_pbp.py): game matching,
the slim play rows, the box context and the ESPN -> NBA.com id map. Pure
functions only; nothing here touches a network or a database."""
from __future__ import annotations

from collections import Counter

import pytest

from data.ingestors import nba_pbp as nb


def _g(eid, d, away, home, stype=2):
    return {"espn_game_id": eid, "game_date": d, "away": away, "home": home,
            "season_type": stype}


# ── game matching ───────────────────────────────────────────────────────────

def test_an_exact_date_and_teams_match():
    out = nb.match_games([_g(1, "2024-01-15", "BOS", "NYK")], {"NBA_2024-01-15_BOS_NYK"})
    assert out[1] == ("NBA_2024-01-15_BOS_NYK", True, "exact", False)


def test_swapped_home_and_away_flips_the_sides():
    out = nb.match_games([_g(1, "2020-08-01", "LAL", "LAC")], {"NBA_2020-08-01_LAC_LAL"})
    assert out[1] == ("NBA_2020-08-01_LAC_LAL", True, "swapped", True)


def test_a_one_day_shift_matches_only_an_unclaimed_game():
    """2020-21 played the same two teams on consecutive days. The game that
    matches exactly keeps its id; the other may not take it by shifting."""
    ours = {"NBA_2021-01-10_BOS_MIA", "NBA_2021-01-12_BOS_MIA"}
    out = nb.match_games([_g(1, "2021-01-10", "BOS", "MIA"),
                          _g(2, "2021-01-11", "BOS", "MIA")], ours)
    assert out[1][2] == "exact"
    assert out[2] == ("NBA_2021-01-12_BOS_MIA", True, "date_shift", False)


def test_postseason_games_keep_the_id_format_but_are_not_in_games():
    out = nb.match_games([_g(1, "2024-05-01", "BOS", "MIA", stype=3)], set())
    assert out[1] == ("NBA_2024-05-01_BOS_MIA", False, "not_regular_season", False)


def test_an_unmatched_regular_season_game_is_named_as_such():
    out = nb.match_games([_g(1, "2024-01-15", "BOS", "NYK")], set())
    assert out[1][1:3] == (False, "unmatched")


# ── plays ───────────────────────────────────────────────────────────────────

def _rec(seq, period, clock, type_text, team_id=None, a1=None, scoring=False,
         shooting=False, text="", **extra):
    r = {"sequence_number": str(seq), "period_number": period, "clock_display_value": clock,
         "type_text": type_text, "team_id": team_id, "athlete_id_1": a1,
         "athlete_id_2": None, "athlete_id_3": None, "scoring_play": scoring,
         "shooting_play": shooting, "text": text, "home_team_id": 1, "away_team_id": 11,
         "home_score": 0, "away_score": 0, "score_value": 0,
         "coordinate_x_raw": -214748340.0, "coordinate_y_raw": -214748365.0,
         "wallclock": "2019-01-01T00:00:00Z", "type_id": 1}
    r.update(extra)
    return r


def test_slim_plays_order_score_and_drop_the_coordinate_sentinel():
    recs = [
        _rec(9, 1, "11:00", "Jump Shot", 11, 1101, True, True, "A makes 26-foot three point jumper",
             score_value=3, coordinate_x_raw=2.0, coordinate_y_raw=2.0),
        _rec(4, 1, "11:30", "Free Throw - 1 of 1", 1, 101, True, True,
             "B makes free throw 1 of 1", score_value=0),
        _rec(12, 1, "10:00", "Substitution", 1, 102, text="C enters the game for B"),
    ]
    rows = nb.slim_plays(recs, espn_game_id=7, game_id="NBA_x", season=2019, season_type=2)
    assert [r["sequence_number"] for r in rows] == [4, 9, 12]
    assert [r["play_no"] for r in rows] == [1, 2, 3]
    assert [(r["home_score"], r["away_score"]) for r in rows] == [(1, 0), (1, 3), (1, 3)]
    assert rows[0]["coord_x"] is None and rows[1]["coord_x"] == 2.0
    assert rows[1]["team_side"] == "A" and rows[1]["shot_value"] == 3
    assert rows[2]["game_s"] == 120.0 and rows[2]["clock_s"] == 600.0


def test_slim_plays_flip_sides_when_the_match_swapped_home_and_away():
    recs = [_rec(1, 1, "11:00", "Jump Shot", 1, 101, True, True, "B makes 10-foot jumper",
                 score_value=2, home_score=2, away_score=0)]
    rows = nb.slim_plays(recs, espn_game_id=7, game_id="x", season=2020, season_type=2,
                         swapped=True)
    assert rows[0]["team_side"] == "A"
    assert (rows[0]["home_score"], rows[0]["away_score"]) == (0, 2)
    assert (rows[0]["espn_home_score"], rows[0]["espn_away_score"]) == (0, 2)


def test_box_context_reads_sides_starters_and_minutes():
    box = [{"athlete_id": 101, "home_away": "home", "starter": True, "minutes": 30.0,
            "athlete_display_name": "B"},
           {"athlete_id": 1101, "home_away": "away", "starter": False, "minutes": None,
            "athlete_display_name": "A"}]
    roster, starters, secs, names = nb.box_context(box)
    assert roster == {101: "H", 1101: "A"}
    assert starters == {"H": {101}, "A": set()}
    assert secs == {101: 1800.0} and names[1101] == "A"


def test_a_player_listed_twice_in_the_box_keeps_the_id_the_plays_use():
    roster = {1: "H", 2: "H", 3: "H"}
    starters = {"H": {1, 2, 3}, "A": set()}
    secs = {1: 100, 2: 100, 3: 100}
    names = {1: "Isaiah Canaan", 2: "Isaiah Canaan", 3: "Someone Else"}
    dropped = nb.drop_duplicate_box_ids(roster, starters, secs, names, play_ids={2, 3})
    assert dropped == {1}
    assert roster == {2: "H", 3: "H"} and starters["H"] == {2, 3}


def test_players_missing_from_the_box_get_the_side_of_their_own_plays():
    plays = [{"type_text": "Jump Shot", "team_side": "H", "athlete_id_1": 5, "athlete_id_2": 50},
             {"type_text": "Substitution", "team_side": "A", "athlete_id_1": 6,
              "athlete_id_2": 7, "text": "x enters the game for y"},
             {"type_text": "Technical Foul", "team_side": "H", "athlete_id_1": 8}]
    roster = {}
    assert nb.roster_from_plays(plays, roster) == 3
    assert roster == {5: "H", 6: "A", 7: "A"}


# ── the id map ──────────────────────────────────────────────────────────────

def test_names_match_exactly_after_normalising():
    espn = {1: "Luka Dončić", 2: "Kelly Oubre Jr."}
    ours = {"p1": "Luka Doncic", "p2": "Kelly Oubre"}
    assert nb.match_names(espn, ours) == {1: ("p1", "name_in_game"), 2: ("p2", "name_in_game")}


def test_a_nickname_matches_on_initial_and_last_name_then_by_elimination():
    espn = {1: "Nic Claxton", 2: "Mo Bamba", 3: "Joe Smith"}
    ours = {"p1": "Nicolas Claxton", "p2": "Mohamed Bamba", "p3": "Joe Smith"}
    got = nb.match_names(espn, ours)
    assert got[3] == ("p3", "name_in_game")
    assert got[1] == ("p1", "initial_last_in_game")
    assert got[2] == ("p2", "initial_last_in_game")
    espn = {1: "Nene", 3: "Joe Smith"}
    ours = {"p9": "Maybyner Hilario", "p3": "Joe Smith"}
    assert nb.match_names(espn, ours)[1] == ("p9", "elimination_in_game")


def test_two_candidates_is_no_match():
    espn = {1: "M. Morris", 2: "Marcus Morris"}
    ours = {"pA": "Markieff Morris", "pB": "Marcus Morris Sr."}
    got = nb.match_names(espn, ours)
    assert got[2] == ("pB", "name_in_game")
    # once Marcus is taken, "M. Morris" has one initial-and-last candidate left
    assert got[1] == ("pA", "initial_last_in_game")
    espn = {1: "J. Holiday", 2: "J. Holiday"}
    ours = {"pA": "Jrue Holiday", "pB": "Justin Holiday"}
    assert nb.match_names(espn, ours, espn_played={1, 2}, ours_played={"pA", "pB"}) == {}


def test_an_id_no_game_matched_falls_back_to_its_team_season():
    """ESPN's second id for Isaiah Canaan never matches in a game (the box
    lists both ids, so two of him is ambiguous); his team-season has one."""
    from collections import defaultdict
    votes = defaultdict(lambda: defaultdict(list))
    votes[2490589]["203477"].append("name_in_game")
    names = {4412182: "Isaiah Canaan", 2490589: "Isaiah Canaan", 77: "Two Names"}
    ts = {4412182: {(2019, "PHX")}, 2490589: {(2019, "PHX")}, 77: {(2019, "PHX")}}
    by = {(2019, "PHX"): {"isaiah canaan": {"203477"}, "two names": {"a", "b"}}}
    assert nb.season_fallback(votes, names, ts, by) == 1
    assert dict(votes[4412182]) == {"203477": ["name_in_team_season"]}
    assert not votes.get(77)


def test_the_map_keeps_the_player_most_games_agree_on():
    votes = {1: {"p1": ["name_in_game"] * 9, "p2": ["elimination_in_game"]}, 2: {}}
    rows = nb.resolve_map(votes, {1: "A", 2: "B", 3: "C"}, {"p1": "A"},
                          Counter({1: 10, 3: 2}))
    by = {r["espn_id"]: r for r in rows}
    assert by[1]["player_id"] == "p1" and by[1]["games_conflict"] == 1
    assert by[1]["method"] == "name_in_game" and by[1]["games_matched"] == 9
    assert by[3]["player_id"] is None and by[3]["method"] == "unmatched"


def test_stint_player_ids_fall_back_to_the_espn_id_and_are_sorted():
    assert nb.our_ids([30, 10, 20], {10: "1629", 30: "201"}) == ["1629", "201", "espn:20"]


@pytest.mark.parametrize("spec, out", [("2019-2021", [2019, 2020, 2021]),
                                       ("2026,2019", [2019, 2026]), ("2024", [2024])])
def test_parse_seasons(spec, out):
    assert nb.parse_seasons(spec) == out
