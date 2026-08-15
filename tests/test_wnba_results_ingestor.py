"""
Tests for the ESPN-based WNBA results ingestor — pure parsers only
(no network, no DB), same convention as test_ufc_csv_loader / test_datagolf.
Fixtures mirror ESPN's site.api.espn.com v2 scoreboard/summary shapes, plus
the sports.core.api.espn.com $ref-linked shapes for the 2026-08-11 fallback
(core fetches are injected as a dict-backed fake, so no network there either).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.ingestors.wnba_results_ingestor import (
    parse_scoreboard, parse_summary_boxscore, norm_player_name,
    _split_made_att, _min_to_float, build_log_row,
    parse_core_event, parse_core_stat_values, _fetch_core_games,
    _fetch_core_box_players, _et_date, CORE_WNBA_EVENTS_URL,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _scoreboard_fixture():
    def competitor(home_away, name, abbrev, score):
        return {"homeAway": home_away, "score": score,
                "team": {"displayName": name, "abbreviation": abbrev}}
    return {
        "events": [
            {   # completed game — LVA @ NYL (ESPN abbrevs differ from ours)
                "id": "401736123",
                "date": "2026-07-05T23:00Z",
                "status": {"type": {"completed": True, "name": "STATUS_FINAL"}},
                "competitions": [{
                    "competitors": [
                        competitor("home", "New York Liberty", "NYL", "88"),
                        competitor("away", "Las Vegas Aces", "LVA", "79"),
                    ],
                }],
            },
            {   # in-progress game — must not produce scores
                "id": "401736124",
                "date": "2026-07-06T01:00Z",
                "status": {"type": {"completed": False, "name": "STATUS_IN_PROGRESS"}},
                "competitions": [{
                    "competitors": [
                        competitor("home", "Phoenix Mercury", "PHX", "41"),
                        competitor("away", "Chicago Sky", "CHI", "39"),
                    ],
                }],
            },
        ],
    }


def _summary_fixture():
    labels = ["MIN", "FG", "3PT", "FT", "OREB", "DREB", "REB", "AST",
              "STL", "BLK", "TO", "PF", "+/-", "PTS"]

    def athlete(espn_id, name, starter, stats, dnp=False):
        return {"athlete": {"id": espn_id, "displayName": name},
                "starter": starter, "didNotPlay": dnp, "stats": stats}

    return {
        "boxscore": {
            "players": [
                {
                    "team": {"displayName": "New York Liberty", "abbreviation": "NYL"},
                    "statistics": [{
                        "labels": labels,
                        "athletes": [
                            athlete("3149391", "Breanna Stewart", True,
                                    ["34", "9-17", "2-5", "4-4", "1", "7", "8",
                                     "3", "1", "2", "2", "1", "+11", "24"]),
                            athlete("4398911", "Marine Johannès", False,
                                    ["18", "3-7", "2-4", "0-0", "0", "2", "2",
                                     "5", "0", "0", "1", "2", "-3", "8"]),
                            athlete("9999999", "Bench Player", False, [], dnp=False),
                            athlete("8888888", "Dnp Player", False,
                                    ["0", "0-0", "0-0", "0-0", "0", "0", "0",
                                     "0", "0", "0", "0", "0", "0", "0"], dnp=True),
                        ],
                    }],
                },
                {
                    "team": {"displayName": "Las Vegas Aces", "abbreviation": "LVA"},
                    "statistics": [{
                        "labels": labels,
                        "athletes": [
                            athlete("2998938", "A'ja Wilson", True,
                                    ["36", "11-20", "0-1", "6-7", "3", "8", "11",
                                     "2", "2", "3", "4", "3", "-9", "28"]),
                        ],
                    }],
                },
            ],
        },
    }


# ── Scoreboard parsing ────────────────────────────────────────────────────────

def test_scoreboard_completed_game():
    games = parse_scoreboard(_scoreboard_fixture(), "2026-07-05")
    final = next(g for g in games if g["completed"])
    assert final["game_id"] == "WNBA_2026-07-05_LV_NY"   # ESPN LVA/NYL → our LV/NY
    assert final["home"] == "NY" and final["away"] == "LV"
    assert final["home_score"] == 88 and final["away_score"] == 79
    assert final["home_win"] == 1
    assert final["season"] == 2026
    assert final["event_id"] == "401736123"
    assert final["commence_time"] == "2026-07-05T23:00Z"


def test_scoreboard_in_progress_game_has_no_scores():
    games = parse_scoreboard(_scoreboard_fixture(), "2026-07-05")
    live = next(g for g in games if not g["completed"])
    assert live["home_score"] is None and live["away_score"] is None
    assert live["home_win"] is None
    assert live["game_id"] == "WNBA_2026-07-05_CHI_PHX"


def test_scoreboard_empty_payload():
    assert parse_scoreboard({}, "2026-07-05") == []
    assert parse_scoreboard({"events": []}, "2026-07-05") == []


# ── Box-score parsing ─────────────────────────────────────────────────────────

def test_boxscore_stats_parsed_by_label():
    rows = parse_summary_boxscore(_summary_fixture())
    stew = next(r for r in rows if r["name"] == "Breanna Stewart")
    assert stew["team"] == "NY"
    assert stew["starter"] is True
    assert stew["minutes"] == 34.0
    assert stew["points"] == 24
    assert stew["rebounds"] == 8
    assert stew["offensive_reb"] == 1 and stew["defensive_reb"] == 7
    assert stew["assists"] == 3 and stew["steals"] == 1 and stew["blocks"] == 2
    assert stew["turnovers"] == 2
    assert (stew["fg_made"], stew["fg_att"]) == (9, 17)
    assert (stew["fg3_made"], stew["fg3_att"]) == (2, 5)
    assert (stew["ft_made"], stew["ft_att"]) == (4, 4)


def test_boxscore_skips_dnp_and_empty_stats():
    rows = parse_summary_boxscore(_summary_fixture())
    names = {r["name"] for r in rows}
    assert "Dnp Player" not in names      # didNotPlay
    assert "Bench Player" not in names    # empty stats row
    assert len(rows) == 3


def test_boxscore_both_teams_and_espn_abbrev_normalized():
    rows = parse_summary_boxscore(_summary_fixture())
    wilson = next(r for r in rows if "Wilson" in r["name"])
    assert wilson["team"] == "LV"          # ESPN LVA → our LV
    assert wilson["points"] == 28


def test_boxscore_empty_payload():
    assert parse_summary_boxscore({}) == []
    assert parse_summary_boxscore({"boxscore": {}}) == []


# ── Helpers ───────────────────────────────────────────────────────────────────

def test_split_made_att():
    assert _split_made_att("5-11") == (5, 11)
    assert _split_made_att(" 0-0 ") == (0, 0)
    assert _split_made_att("") == (None, None)
    assert _split_made_att(None) == (None, None)
    assert _split_made_att("abc") == (None, None)


def test_min_to_float():
    assert _min_to_float("32") == 32.0
    assert _min_to_float("32:30") == 32.5
    assert _min_to_float("--") is None
    assert _min_to_float("") is None
    assert _min_to_float(None) is None


def test_build_log_row_casts_is_starter_to_int():
    # Regression (2026-07-11 outage): the parser emits a Python bool for
    # starter, but wnba_player_game_log.is_starter is INTEGER in Postgres and
    # psycopg2 sends bools as boolean literals — the implicit cast is refused
    # and the whole ingest transaction aborts. The row builder must emit 1/0.
    game = {"game_id": "WNBA_2026-07-05_LV_NY", "season": 2026}
    base = {"name": "Breanna Stewart", "team": "NY", "minutes": 34.0,
            "points": 24, "rebounds": 8, "offensive_reb": 1, "defensive_reb": 7,
            "assists": 4, "steals": 1, "blocks": 2, "turnovers": 3,
            "fg_made": 9, "fg_att": 17, "fg3_made": 2, "fg3_att": 5,
            "ft_made": 4, "ft_att": 4}
    for starter, expected in ((True, 1), (False, 0)):
        row = build_log_row({**base, "starter": starter}, "203399", game, "2026-07-05")
        assert row["is_starter"] == expected
        assert type(row["is_starter"]) is int
    assert row["player_id"] == "203399"
    assert row["game_id"] == "WNBA_2026-07-05_LV_NY"
    assert row["season"] == 2026
    assert row["game_date"] == "2026-07-05"
    assert row["points"] == 24


def test_norm_player_name_matches_across_sources():
    # accents / punctuation / suffixes must not break the ESPN ↔ nba_api join
    assert norm_player_name("Marine Johannès") == norm_player_name("Marine Johannes")
    assert norm_player_name("A'ja Wilson") == norm_player_name("Aja Wilson")
    assert norm_player_name("Kelsey Plum Jr.") == norm_player_name("Kelsey Plum")
    assert norm_player_name("Skylar Diggins-Smith") == norm_player_name("Skylar Diggins Smith")
    assert norm_player_name("  Napheesa   Collier ") == "napheesa collier"


# ── sports.core.api.espn.com fallback ─────────────────────────────────────────

_B = CORE_WNBA_EVENTS_URL


def _core_web():
    """A tiny fake of the core API as {url: doc} — every $ref resolves here.
    ev1 = final LVA @ NYL tipping 8pm ET on 8/9 (UTC says 8/10 — the ET-date
    regression case); ev2 = a game on the NEXT ET day; ev3 = still scheduled."""
    stew_stats = {"splits": {"categories": [
        {"name": "defensive", "stats": [
            {"name": "defensiveRebounds", "abbreviation": "DR", "value": 7.0},
            {"name": "blocks", "abbreviation": "BLK", "value": 2.0},
            {"name": "steals", "abbreviation": "STL", "value": 1.0}]},
        {"name": "offensive", "stats": [
            {"name": "points", "abbreviation": "PTS", "value": 24.0},
            {"name": "offensiveRebounds", "abbreviation": "OR", "value": 1.0},
            {"name": "assists", "abbreviation": "AST", "value": 3.0},
            {"name": "turnovers", "abbreviation": "TO", "value": 2.0},
            {"name": "fieldGoalsMade", "abbreviation": "FGM", "value": 9.0},
            {"name": "fieldGoalsAttempted", "abbreviation": "FGA", "value": 17.0},
            {"name": "threePointFieldGoalsMade", "abbreviation": "3PM", "value": 2.0},
            {"name": "threePointFieldGoalsAttempted", "abbreviation": "3PA", "value": 5.0},
            {"name": "freeThrowsMade", "abbreviation": "FTM", "value": 4.0},
            {"name": "freeThrowsAttempted", "abbreviation": "FTA", "value": 4.0}]},
        {"name": "general", "stats": [
            {"name": "totalRebounds", "abbreviation": "REB", "value": 8.0},
            {"name": "minutes", "abbreviation": "MIN", "value": 34.0}]},
    ]}}
    # abbreviation-only doc — the by-NAME lookup must fall back to abbrevs
    wilson_stats = {"splits": {"categories": [
        {"name": "offensive", "stats": [
            {"abbreviation": "PTS", "value": 28.0},
            {"abbreviation": "REB", "value": 11.0},
            {"abbreviation": "AST", "value": 2.0},
            {"abbreviation": "MIN", "value": 36.0},
            {"abbreviation": "FGM", "value": 11.0},
            {"abbreviation": "FGA", "value": 20.0}]},
    ]}}
    away_roster_url = f"{_B}/401800001/competitions/401800001/competitors/17/roster"
    return {
        f"{_B}?dates=20260809-20260810&limit=100": {
            "count": 3,
            "items": [{"$ref": f"{_B}/401800001"},
                      {"$ref": f"{_B}/401800002"},
                      {"$ref": f"{_B}/401800003"}],
        },
        f"{_B}/401800001": {
            "id": "401800001",
            "date": "2026-08-10T00:00Z",     # 8pm EDT on 2026-08-09
            "competitions": [{
                "id": "401800001",
                "date": "2026-08-10T00:00Z",
                "status": {"$ref": f"{_B}/401800001/status"},
                "competitors": [
                    {"id": "9", "homeAway": "home",
                     "team": {"$ref": "http://core/teams/9"},   # http:// on purpose
                     "score": {"$ref": f"{_B}/401800001/score-home"},
                     "roster": {"$ref": f"{_B}/401800001/roster-home"}},
                    {"id": "17", "homeAway": "away",
                     "team": {"$ref": "http://core/teams/17"},
                     "score": {"$ref": f"{_B}/401800001/score-away"}},
                    # away has no roster ref → constructed-URL fallback
                ],
            }],
        },
        f"{_B}/401800001/status": {"type": {"name": "STATUS_FINAL",
                                            "state": "post", "completed": True}},
        "http://core/teams/9": {"id": "9", "abbreviation": "NYL",
                                "displayName": "New York Liberty"},
        "http://core/teams/17": {"id": "17", "abbreviation": "LVA",
                                 "displayName": "Las Vegas Aces"},
        f"{_B}/401800001/score-home": {"value": 88.0, "displayValue": "88"},
        f"{_B}/401800001/score-away": {"value": 79.0, "displayValue": "79"},
        f"{_B}/401800001/roster-home": {"entries": [
            {"playerId": 3149391, "starter": True, "didNotPlay": False,
             "athlete": {"$ref": "http://core/athletes/3149391"},
             "statistics": {"$ref": f"{_B}/401800001/stats-stewart"}},
            {"playerId": 111, "starter": False, "didNotPlay": True,
             "athlete": {"$ref": "http://core/athletes/111"},
             "statistics": {"$ref": f"{_B}/401800001/stats-dnp"}},
            {"playerId": 222, "starter": False, "didNotPlay": False,
             "athlete": {"$ref": "http://core/athletes/222"},
             "statistics": {"$ref": f"{_B}/401800001/stats-empty"}},
        ]},
        away_roster_url: {"entries": [
            {"playerId": 2998938, "starter": True, "didNotPlay": False,
             "athlete": {"$ref": "http://core/athletes/2998938"},
             "statistics": {"$ref": f"{_B}/401800001/stats-wilson"}},
        ]},
        f"{_B}/401800001/stats-stewart": stew_stats,
        f"{_B}/401800001/stats-wilson": wilson_stats,
        f"{_B}/401800001/stats-empty": {"splits": {"categories": []}},
        "http://core/athletes/3149391": {"id": 3149391,
                                         "displayName": "Breanna Stewart"},
        "http://core/athletes/2998938": {"id": 2998938,
                                         "displayName": "A'ja Wilson"},
        f"{_B}/401800002": {   # next ET day — must be filtered out for 8/9
            "id": "401800002",
            "date": "2026-08-10T23:00Z",
            "competitions": [{
                "id": "401800002", "date": "2026-08-10T23:00Z",
                "status": {"type": {"completed": True}},
                "competitors": [
                    {"id": "11", "homeAway": "home",
                     "team": {"abbreviation": "PHX", "displayName": "Phoenix Mercury"},
                     "score": {"value": 90.0}},
                    {"id": "19", "homeAway": "away",
                     "team": {"abbreviation": "CHI", "displayName": "Chicago Sky"},
                     "score": {"value": 80.0}},
                ],
            }],
        },
        f"{_B}/401800003": {   # 8/9 but still scheduled — no scores may land
            "id": "401800003",
            "date": "2026-08-09T23:00Z",
            "competitions": [{
                "id": "401800003", "date": "2026-08-09T23:00Z",
                "status": {"type": {"name": "STATUS_SCHEDULED", "completed": False}},
                "competitors": [
                    {"id": "8", "homeAway": "home",
                     "team": {"abbreviation": "MIN", "displayName": "Minnesota Lynx"},
                     "score": {"$ref": f"{_B}/401800003/score-home"}},
                    {"id": "14", "homeAway": "away",
                     "team": {"abbreviation": "SEA", "displayName": "Seattle Storm"},
                     "score": {"$ref": f"{_B}/401800003/score-away"}},
                ],
            }],
        },
    }


def _recording_fetch(web):
    calls = []

    def fetch(url):
        calls.append(url)
        return web[url]
    return fetch, calls


def test_core_events_completed_game():
    fetch, _ = _recording_fetch(_core_web())
    games = _fetch_core_games("2026-08-09", fetch=fetch)
    assert len(games) == 2                       # ev1 + ev3; ev2 is next ET day
    final = next(g for g in games if g["completed"])
    assert final["game_id"] == "WNBA_2026-08-09_LV_NY"   # ESPN LVA/NYL → LV/NY
    assert final["home"] == "NY" and final["away"] == "LV"
    assert final["home_score"] == 88 and final["away_score"] == 79
    assert final["home_win"] == 1
    assert final["season"] == 2026
    assert final["event_id"] == "401800001"
    # roster refs: inline for home, constructed-URL fallback for away
    assert final["core_rosters"]["NY"] == f"{_B}/401800001/roster-home"
    assert final["core_rosters"]["LV"] == (
        f"{_B}/401800001/competitions/401800001/competitors/17/roster")


def test_core_scheduled_game_has_no_scores_and_skips_score_refs():
    web = _core_web()
    fetch, calls = _recording_fetch(web)
    games = _fetch_core_games("2026-08-09", fetch=fetch)
    sched = next(g for g in games if not g["completed"])
    assert sched["home_score"] is None and sched["away_score"] is None
    assert sched["home_win"] is None
    assert sched["game_id"] == "WNBA_2026-08-09_SEA_MIN"
    # score refs of a non-final game must never be fetched
    assert f"{_B}/401800003/score-home" not in calls
    assert f"{_B}/401800003/score-away" not in calls


def test_core_et_date_filter():
    # the same 8pm-ET event carries a next-day UTC timestamp: it belongs to
    # 8/9 and must NOT be claimed by an 8/10 ingest (double-count guard)
    web = _core_web()
    fetch, _ = _recording_fetch(web)
    ev1 = web[f"{_B}/401800001"]
    assert parse_core_event(ev1, "2026-08-09", fetch) is not None
    assert parse_core_event(ev1, "2026-08-10", fetch) is None
    assert _et_date("2026-08-10T00:00Z") == "2026-08-09"
    assert _et_date("2026-08-09T23:00Z") == "2026-08-09"
    assert _et_date("") is None and _et_date("garbage") is None


def test_core_stat_values_by_name_and_abbreviation():
    web = _core_web()
    by_name = parse_core_stat_values(web[f"{_B}/401800001/stats-stewart"])
    assert by_name["points"] == 24 and by_name["rebounds"] == 8
    assert by_name["offensive_reb"] == 1 and by_name["defensive_reb"] == 7
    assert by_name["assists"] == 3 and by_name["steals"] == 1
    assert by_name["blocks"] == 2 and by_name["turnovers"] == 2
    assert (by_name["fg_made"], by_name["fg_att"]) == (9, 17)
    assert (by_name["fg3_made"], by_name["fg3_att"]) == (2, 5)
    assert (by_name["ft_made"], by_name["ft_att"]) == (4, 4)
    assert by_name["minutes"] == 34.0
    by_abbrev = parse_core_stat_values(web[f"{_B}/401800001/stats-wilson"])
    assert by_abbrev["points"] == 28 and by_abbrev["rebounds"] == 11
    assert by_abbrev["minutes"] == 36.0
    assert by_abbrev["fg3_made"] is None      # absent stat → None, not 0
    assert parse_core_stat_values({}) == {k: None for k in by_name}


def test_core_box_players_shape_and_skips():
    web = _core_web()
    fetch, calls = _recording_fetch(web)
    final = next(g for g in _fetch_core_games("2026-08-09", fetch=fetch)
                 if g["completed"])
    cache = {}
    rows = _fetch_core_box_players(final, fetch=fetch, athlete_cache=cache)
    names = {r["name"] for r in rows}
    assert names == {"Breanna Stewart", "A'ja Wilson"}   # DNP + empty skipped
    stew = next(r for r in rows if r["name"] == "Breanna Stewart")
    assert stew["team"] == "NY" and stew["starter"] is True
    assert stew["points"] == 24 and stew["espn_id"] == "3149391"
    wilson = next(r for r in rows if "Wilson" in r["name"])
    assert wilson["team"] == "LV" and wilson["points"] == 28
    # the parsed row must feed build_log_row unchanged (site-path parity)
    log = build_log_row(stew, "203399", final, "2026-08-09")
    assert log["is_starter"] == 1 and log["points"] == 24
    assert log["game_id"] == "WNBA_2026-08-09_LV_NY"
    # DNP player's stats and athlete docs were never fetched
    assert f"{_B}/401800001/stats-dnp" not in calls
    assert "http://core/athletes/111" not in calls
    # athlete docs cached: a second pass adds no new athlete fetches
    n_ath = sum(1 for c in calls if "athletes" in c)
    _fetch_core_box_players(final, fetch=fetch, athlete_cache=cache)
    assert sum(1 for c in calls if "athletes" in c) == n_ath


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  PASS {fn.__name__}")
    print(f"{len(fns)} tests passed")
