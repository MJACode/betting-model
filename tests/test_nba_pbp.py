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


def test_slim_plays_give_a_teamless_technical_free_throw_its_side_and_its_point():
    """ESPN 401469046: the made technical has no team; the running score says
    it was the away side's, and our running score now counts it."""
    recs = [_rec(1, 1, "6:58", "Running Layup Shot", 11, 1101, True, True, "A makes layup",
                 score_value=2, home_score=13, away_score=12),
            _rec(2, 1, "6:58", "Technical Foul", 1, 101, text="B technical foul",
                 home_score=13, away_score=12),
            _rec(3, 1, "6:58", "Free Throw - Technical", None, None, True, True,
                 "makes technical free throw", home_score=13, away_score=13)]
    rows = nb.slim_plays(recs, espn_game_id=401469046, game_id="x", season=2023, season_type=2)
    assert rows[2]["team_side"] == "A" and rows[2]["espn_team_id"] is None
    assert (rows[2]["home_score"], rows[2]["away_score"]) == (0, 3)
    assert nb.sides_inferred(rows) == 1


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


def test_a_player_logged_under_a_second_id_is_read_as_his_box_id():
    """Emanuel Terry's plays carry 4411934, his box row 4355392 (PHX_LAL
    2019-01-27); Jordan McLaughlin's plays carry both 4715220 and 3134916."""
    roster = {4355392: "A", 3134916: "H", 77: "A", 78: "A"}   # the blocker is the opponent
    names = {4355392: "Emanuel Terry", 3134916: "Jordan McLaughlin", 77: "Devin Booker",
             78: "Ivica Zubac Jr."}
    plays = [
        {"type_text": "Substitution", "team_side": "A", "athlete_id_1": 4411934,
         "athlete_id_2": 77, "text": "Emanuel Terry enters the game for Devin Booker"},
        {"type_text": "Cutting Layup Shot", "team_side": "A", "athlete_id_1": 4411934,
         "text": "Emanuel Terry makes 2-foot layup (Devin Booker assists)"},
        {"type_text": "Layup Shot", "team_side": "H", "athlete_id_1": 4715220,
         "text": "Jordan Mclaughlin misses layup"},
        {"type_text": "Driving Layup Shot", "team_side": "H", "athlete_id_1": 4715220,
         "text": "Ivica Zubac blocks Jordan Mclaughlin 's 3-foot driving layup"},
        {"type_text": "Jump Shot", "team_side": "H", "athlete_id_1": 3134916,
         "text": "Jordan McLaughlin makes jumper"},
        {"type_text": "Jump Shot", "team_side": "H", "athlete_id_1": 999,
         "text": "Someone Else makes jumper"},
    ]
    assert nb.alias_play_ids(plays, roster, names) == {4411934: 4355392, 4715220: 3134916}


def _game_recs():
    """A one-quarter game: the away side's sub comes on under an id the box
    does not list (900; the box says 4355392, same name)."""
    recs = []
    seq = iter(range(1, 100))
    for n, (home_id, away_id) in enumerate(zip((101, 102, 103, 104, 105),
                                               (1101, 1102, 1103, 1104, 1105))):
        clock = f"{11 - n}:00"
        recs.append(_rec(next(seq), 1, clock, "Jump Shot", 1, home_id, False, True,
                         f"H{home_id} misses 12-foot jumper"))
        recs.append(_rec(next(seq), 1, clock, "Jump Shot", 11, away_id, False, True,
                         f"A{away_id} misses 12-foot jumper"))
    recs.append(_rec(next(seq), 1, "5:00", "Substitution", 11, 900,
                     text="Emanuel Terry enters the game for A1105", athlete_id_2=1105))
    recs.append(_rec(next(seq), 1, "4:00", "Jump Shot", 11, 900, True, True,
                     "Emanuel Terry makes 12-foot jumper", score_value=2, away_score=2))
    recs.append(_rec(next(seq), 1, "0:00", "End Period", None, None, text="End of 1st",
                     away_score=2))
    box = []
    for aid in (101, 102, 103, 104, 105):
        box.append({"athlete_id": aid, "home_away": "home", "starter": True, "minutes": 12.0,
                    "athlete_display_name": f"H{aid}", "team_score": 0})
    for aid in (1101, 1102, 1103, 1104, 1105):
        box.append({"athlete_id": aid, "home_away": "away", "starter": True, "minutes": 12.0,
                    "athlete_display_name": f"A{aid}", "team_score": 2})
    box.append({"athlete_id": 4355392, "home_away": "away", "starter": False, "minutes": 4.0,
                "athlete_display_name": "Emanuel Terry", "team_score": 2})
    return recs, box


META = {"season": 2019, "season_type": 2, "home": "LAL", "away": "PHX", "game_date": "2019-01-27"}


def test_segments_carry_the_box_player_not_a_placeholder_for_a_second_id():
    recs, box = _game_recs()
    id_map = {4355392: "1629150", **{a: f"p{a}" for a in (101, 102, 103, 104, 105, 1101,
                                                             1102, 1103, 1104, 1105)}}
    g, plays, b_rows, s_rows = nb.build_game(7, recs, box, META, ("NBA_x", True, "exact", False),
                                             id_map)
    on = {pid for s in s_rows for pid in s["away_player_ids"]}
    assert "1629150" in on and not any(p.startswith("espn:") for p in on)
    assert g["diagnostics"]["play_id_aliases"] == {"900": 4355392}
    assert plays[-2]["athlete_id_1"] == 900                    # nba_pbp keeps ESPN's id
    assert g["_alias_map_rows"][0]["espn_id"] == 900
    assert g["_alias_map_rows"][0]["player_id"] == "1629150"


def test_the_ledger_flags_a_game_whose_segments_miss_the_final():
    recs, box = _game_recs()
    g, *_ = nb.build_game(7, recs, box, META, ("NBA_x", True, "exact", False), {})
    assert g["points_mismatch"] is False and g["points_source"] == "plays"
    short = [dict(b, team_score=5) if b["home_away"] == "away" else b for b in box]
    g, *_ = nb.build_game(7, recs, short, META, ("NBA_x", True, "exact", False), {})
    assert g["points_mismatch"] is True
    nobox_g, *_ = nb.build_game(7, recs, [], META, ("NBA_x", True, "exact", False), {},
                                games_final=(0, 2))
    assert nobox_g["points_mismatch"] is False


def test_a_rebuild_from_stored_rows_matches_the_load_and_rescores_a_teamless_free_throw():
    recs, box = _game_recs()
    recs.insert(-1, _rec(99, 1, "2:00", "Free Throw - Technical", None, None, True, True,
                         "makes technical free throw", home_score=1, away_score=2))
    for r in box:
        r["team_score"] = 1 if r["home_away"] == "home" else 2
    g, plays, b_rows, s_rows = nb.build_game(7, recs, box, META,
                                             ("NBA_2019-01-27_PHX_LAL", True, "exact", False), {})
    stored_game = {k: g[k] for k in nb.GAME_COLS[:-2]}
    stored_pbp = [{k: p[k] for k in nb.PBP_COLS} for p in plays]
    g2, plays2, s2, changed = nb.rebuild_stored(stored_game, stored_pbp, b_rows, {}, {})
    assert s2 == s_rows and changed is False
    assert sum(s["home_pts"] for s in s2) == 1
    # the same game as stored before sides were inferred: the rebuild rescores it
    for p in stored_pbp:
        if p["type_text"] == "Free Throw - Technical":
            p["team_side"] = None
    after = stored_pbp[[p["type_text"] for p in stored_pbp].index("Free Throw - Technical"):]
    for p in after:
        p["home_score"] = 0
    g3, plays3, s3, changed = nb.rebuild_stored(stored_game, stored_pbp, b_rows, {}, {})
    assert changed is True and s3 == s_rows
    assert g3["game_date"] == "2019-01-27" and g3["derivation"] == nb.DERIVATION


def test_ensure_tables_adds_the_new_ledger_columns_to_an_existing_table():
    ran = []

    class Fake:
        def execute(self, sql, params=None):
            ran.append(" ".join(str(sql).split()))
            raise_ = "pg_class" in sql or "information_schema" in sql
            if raise_:
                raise RuntimeError("not postgres")
            return self

        def fetchone(self):
            return None

        def commit(self):
            pass

        def rollback(self):
            pass

    nb.ensure_tables(Fake())
    assert any(s.startswith("ALTER TABLE nba_pbp_games ADD COLUMN IF NOT EXISTS points_mismatch")
               for s in ran)
    assert any(s.startswith("ALTER TABLE nba_pbp_games ADD COLUMN IF NOT EXISTS points_source")
               for s in ran)


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


# ── gaps from ESPN's summary endpoint ───────────────────────────────────────

def _summary():
    return {
        "header": {"competitions": [{"competitors": [
            {"homeAway": "home", "score": "107", "team": {"id": "22", "abbreviation": "POR",
                                                          "displayName": "Portland Trail Blazers"}},
            {"homeAway": "away", "score": "104", "team": {"id": "8", "abbreviation": "DET",
                                                          "displayName": "Detroit Pistons"}}]}]},
        "plays": [{"sequenceNumber": "7", "type": {"id": "95", "text": "Layup Shot"},
                   "text": "A makes layup (B assists)", "awayScore": 0, "homeScore": 2,
                   "period": {"number": 1}, "clock": {"displayValue": "11:45"},
                   "scoringPlay": True, "scoreValue": 2, "team": {"id": "22"},
                   "participants": [{"athlete": {"id": "11"}}, {"athlete": {"id": "12"}}],
                   "wallclock": "2020-02-24T03:11:09Z", "shootingPlay": True,
                   "coordinate": {"x": 23, "y": 1}, "pointsAttempted": 2}],
        "boxscore": {"players": []},
    }


def test_a_summary_reads_into_the_release_columns():
    plays, box = nb.summary_records(_summary(), 401161490, 2020, 2, "2020-02-24")
    p = plays[0]
    assert (p["athlete_id_1"], p["athlete_id_2"], p["athlete_id_3"]) == ("11", "12", None)
    assert (p["coordinate_x_raw"], p["coordinate_y_raw"]) == (23, 1)
    assert (p["home_team_id"], p["away_team_id"]) == (22, 8)
    rows = nb.slim_plays(plays, espn_game_id=401161490, game_id="NBA_2020-02-23_DET_POR",
                         season=2020, season_type=2)
    assert rows[0]["team_side"] == "H" and rows[0]["points"] == 2 and rows[0]["clock_s"] == 705.0
    meta = nb.espn_game_meta(401161490, plays)
    assert (meta["home"], meta["away"]) == ("POR", "DET")


def test_a_gap_game_is_found_by_its_teams_a_day_off_and_never_twice():
    """ESPN dates DET at POR 2020-02-24T12:00Z; ours says 2020-02-23."""
    boards = {}
    board_days = {"2020-02-24": [{"event_id": "401161490", "away": "DET", "home": "POR",
                                  "game_date": "2020-02-24"}]}
    found = nb.find_event("NBA_2020-02-23_DET_POR", "2020-02-23", boards,
                          lambda d: board_days.get(d, []))
    assert found[0]["event_id"] == "401161490" and found[1] is False
    swapped = nb.find_event("NBA_2020-02-23_POR_DET", "2020-02-23", boards,
                            lambda d: board_days.get(d, []))
    assert swapped[1] is True
    assert nb.find_event("NBA_2020-02-23_DET_POR", "2020-02-23", boards,
                         lambda d: board_days.get(d, []), taken={401161490}) is None


def test_a_gap_game_found_a_day_off_is_dated_by_our_games_row():
    """ESPN's placeholder 2020-02-24T12:00Z for DET at POR; ours is 2020-02-23."""
    ev = {"event_id": "401161490", "away": "DET", "home": "POR", "game_date": "2020-02-24",
          "season_type": 2}
    g = nb.build_gap_game("NBA_2020-02-23_DET_POR", "2020-02-23", ev, False, _summary(),
                          2020, {}, {})
    assert g[0]["game_date"] == "2020-02-23"
    assert g[0]["source"] == nb.GAP_SOURCE and g[0]["match_method"] == "gap_exact"
