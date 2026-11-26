"""Four free NHL sources. Not a pick input.

Parsers are checked against payloads read on 2026-11-26 (shift chart and
right rail for game 2026020386, EDGE detail for Matthews / Hellebuyck /
Toronto, and a Daily Faceoff line page archived 2026-03-03).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPE = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
SCHED = (ROOT / "scheduler.py").read_text(encoding="utf-8")
HEALTH = (ROOT / "tracking" / "system_health.py").read_text(encoding="utf-8")
MIGRATION = "nhl_free_feeds_2026_11_26.sql"

SHIFT_ROW = {
    "id": 16936892, "detailCode": 0, "duration": "00:57", "endTime": "05:19",
    "eventNumber": 110, "firstName": "Sean", "gameId": 2026020386,
    "lastName": "Kuraly", "period": 1, "playerId": 8476374, "shiftNumber": 1,
    "startTime": "04:22", "teamAbbrev": "BOS", "typeCode": 517,
}
META = {
    "nhl_game_id": 2026020386, "our_game_id": "NHL_2026-11-25_WPG_BOS",
    "season_end": 2027, "game_type": 2, "game_date": "2026-11-25",
    "home_abbr": "BOS", "away_abbr": "WPG",
}
RAIL = {
    "gameInfo": {
        "referees": [
            {"fullName": {"default": "Chris Rooney"}, "sweaterNumber": 5},
            {"fullName": {"default": "Stephen Hiff"}, "sweaterNumber": 33},
        ],
        "linesmen": [
            {"fullName": {"default": "Matt MacPherson"}, "sweaterNumber": 83},
        ],
        "awayTeam": {"scratches": [
            {"id": 8475799, "firstName": {"default": "Nino"},
             "lastName": {"default": "Niederreiter"}},
        ]},
        "homeTeam": {"scratches": []},
    }
}


def _page(players):
    payload = {"props": {"pageProps": {"slug": "boston-bruins", "combinations": {
        "teamAbbreviation": "BOS", "teamSlug": "boston-bruins",
        "sourceName": "Belle Fraser", "updatedAt": "2026-03-02T16:16:11.689Z",
        "players": players,
    }}}}
    return ('<html><script id="__NEXT_DATA__" type="application/json">'
            + json.dumps(payload) + "</script></html>")


def test_a_shift_uses_the_feed_id_and_our_team():
    from data.ingestors.nhl_shifts import clock_seconds, shift_record
    record = shift_record(SHIFT_ROW, META)
    assert record["shift_id"] == 16936892
    assert record["player_id"] == 8476374
    assert record["team_abbr"] == "BOS"
    assert record["start_seconds"] == 4 * 60 + 22
    assert record["end_seconds"] == 5 * 60 + 19
    assert record["duration_seconds"] == 57
    assert clock_seconds("1:02:03") == 3723
    assert clock_seconds("nope") is None


def test_pages_until_total_and_a_repeated_page_does_not_count_as_complete():
    from data.ingestors.nhl_polite_http import FetchFailed
    from data.ingestors.nhl_shifts import fetch_shift_rows
    calls = []

    def get(url):
        calls.append(url)
        if "start=0" in url:
            return {"total": 3, "data": [
                {"id": 1, "playerId": 10}, {"id": 2, "playerId": 11}]}
        return {"total": 3, "data": [{"id": 3, "playerId": 12}]}

    rows = fetch_shift_rows(2026020386, get=get, limit=2)
    assert {r["id"] for r in rows} == {1, 2, 3}
    assert len(calls) == 2

    def repeat(url):
        return {"total": 4, "data": [{"id": 1, "playerId": 10}]}

    try:
        fetch_shift_rows(1, get=repeat, limit=2)
    except FetchFailed as exc:
        assert "1 shifts of 4" in str(exc)
    else:
        raise AssertionError("a page that repeats before total is a failed game")


def test_linemates_are_shared_ice_and_a_short_overlap_is_dropped():
    from data.ingestors.nhl_shifts import linemate_pairs, shift_record
    def row(sid, pid, name, start, end):
        return shift_record({
            "id": sid, "playerId": pid, "firstName": name, "lastName": "X",
            "teamAbbrev": "BOS", "period": 1, "shiftNumber": 1,
            "startTime": start, "endTime": end, "duration": "01:00",
        }, META)
    long = linemate_pairs([row(1, 10, "A", "00:00", "02:00"),
                           row(2, 20, "B", "00:30", "02:30")])
    assert len(long) == 1
    assert long[0]["player_id_lo"] == 10
    assert long[0]["player_id_hi"] == 20
    assert long[0]["shared_seconds"] == 90
    short = linemate_pairs([row(3, 10, "A", "00:00", "00:20"),
                            row(4, 20, "B", "00:00", "00:20")])
    assert short == []


def test_right_rail_names_the_officials_and_the_log_names_the_team():
    from data.ingestors.nhl_right_rail import parse_right_rail
    officials, scratches = parse_right_rail(RAIL, META)
    assert [o["full_name"] for o in officials] == [
        "Chris Rooney", "Stephen Hiff", "Matt MacPherson"]
    assert officials[0]["role"] == "referee" and officials[0]["sweater_number"] == 5
    assert officials[2]["role"] == "linesman"
    assert scratches == [{
        "nhl_game_id": 2026020386, "player_id": 8475799, "team_abbr": "WPG",
        "side": "away", "player_name": "Nino Niederreiter", "season_end": 2027,
        "game_type": 2, "game_date": "2026-11-25",
        "our_game_id": "NHL_2026-11-25_WPG_BOS", "source": "nhl_api",
    }]
    assert parse_right_rail({"gameInfo": {}}, META)[0] == []


def test_a_line_page_keeps_the_forward_line_and_both_power_plays():
    from data.ingestors.dailyfaceoff_lines import line_rows, parse_line_page
    players = [
        {"playerId": 1, "name": "A", "groupIdentifier": "f1", "groupName": "Forwards 1",
         "categoryIdentifier": "ev", "positionIdentifier": "lw", "positionName": "Left Wing",
         "jerseyNumber": 11},
        {"playerId": 2, "name": "B", "groupIdentifier": "pp1", "groupName": "1st Powerplay Unit",
         "categoryIdentifier": "pp", "positionIdentifier": "sk1", "jerseyNumber": 22},
        {"playerId": 3, "name": "C", "groupIdentifier": "pp2", "groupName": "2nd Powerplay Unit",
         "categoryIdentifier": "pp", "positionIdentifier": "sk1", "jerseyNumber": 33},
        {"playerId": 2, "name": "B", "groupIdentifier": "pp1", "groupName": "1st Powerplay Unit",
         "categoryIdentifier": "pp", "positionIdentifier": "sk1", "jerseyNumber": 22},
    ]
    rows = line_rows(parse_line_page(_page(players)), "2026-11-26", "2026-11-26T16:10:00Z")
    groups = {(r["category"], r["group_id"], r["player_id"]) for r in rows}
    assert groups == {("ev", "f1", 1), ("pp", "pp1", 2), ("pp", "pp2", 3)}
    assert rows[0]["team_abbr"] == "BOS"
    assert rows[0]["snapshot_at"] == "2026-11-26T16:10:00Z"
    assert rows[0]["source"] == "dailyfaceoff"


def test_a_cloudflare_challenge_is_a_warning_not_an_exception():
    from data.ingestors.dailyfaceoff_lines import fetch_team
    assert fetch_team("boston-bruins", fetch_html=lambda url: "<html>Just a moment...</html>") is None


def test_line_inserts_do_not_update_and_the_slug_list_is_the_current_thirty_two():
    from data.ingestors.dailyfaceoff_lines import INSERT_SQL, TEAM_SLUGS
    assert "DO NOTHING" in INSERT_SQL
    assert "DO UPDATE" not in INSERT_SQL
    assert len(TEAM_SLUGS) == 32
    assert TEAM_SLUGS["BOS"] == "boston-bruins"
    assert TEAM_SLUGS["UTA"] == "utah-mammoth"
    assert TEAM_SLUGS["LAK"] == "los-angeles-kings"


def test_edge_records_use_the_measured_fields_and_utah_is_the_higher_id():
    from data.ingestors.nhl_edge import (
        current_team_ids, goalie_record, season_id_for, skater_record, team_record,
    )
    assert season_id_for("2026-11-26") == 20262027
    skater = skater_record({
        "player": {"id": 8479318, "firstName": {"default": "Auston"},
                   "lastName": {"default": "Matthews"}, "position": "C",
                   "gamesPlayed": 20, "team": {"abbrev": "TOR"}},
        "topShotSpeed": {"imperial": 90.48, "percentile": 0.9141},
        "skatingSpeed": {"speedMax": {"imperial": 21.46, "percentile": 0.26},
                         "burstsOver20": {"value": 35}},
        "totalDistanceSkated": {"imperial": 88.41},
        "zoneTimeDetails": {"offensiveZonePctg": 0.469, "neutralZonePctg": 0.173,
                            "defensiveZonePctg": 0.358},
        "sogSummary": [{"locationCode": "high", "shootingPctg": 0.25}],
    }, "2026-11-26", 20262027, 2)
    assert skater["top_shot_mph"] == 90.48
    assert skater["bursts_over_20"] == 35
    assert skater["high_danger_shooting_pct"] == 0.25
    assert skater["oz_pct"] == 0.469
    assert "8479318" in skater["payload"]
    goalie = goalie_record({
        "player": {"id": 8476945, "firstName": {"default": "Connor"},
                   "lastName": {"default": "Hellebuyck"}, "gamesPlayed": 18,
                   "team": {"abbrev": "WPG"}},
        "shotLocationSummary": [
            {"locationCode": "all", "savePctg": 0.899},
            {"locationCode": "high", "savePctg": 0.814, "saves": 57},
        ],
    }, "2026-11-26", 20262027, 2)
    assert goalie["save_pct"] == 0.899
    assert goalie["high_danger_save_pct"] == 0.814
    assert goalie["high_danger_saves"] == 57
    team = team_record({
        "team": {"id": 68, "abbrev": "UTA"},
        "shotSpeed": {"topShotSpeed": {"imperial": 97.46},
                      "shotAttemptsOver90": {"value": 12}},
        "skatingSpeed": {"speedMax": {"imperial": 23.1},
                         "burstsOver20": {"value": 400}, "burstsOver22": {"value": 40}},
        "distanceSkated": {"total": {"imperial": 1100.0}},
        "zoneTimeDetails": {"offensiveZonePctg": 0.40, "neutralZonePctg": 0.18,
                            "defensiveZonePctg": 0.42},
        "sogSummary": [{"locationCode": "high", "shootingPctg": 0.21}],
    }, "2026-11-26", 20262027, 2)
    assert team["team_id"] == 68
    assert team["shots_over_90"] == 12
    ids = current_team_ids(
        [{"triCode": "UTA", "id": 59}, {"triCode": "UTA", "id": 68},
         {"triCode": "BOS", "id": 6}, {"triCode": "ARI", "id": 53}],
        ["UTA", "BOS"])
    assert ids == [(68, "UTA"), (6, "BOS")]


def test_edge_pages_the_summary_the_server_caps_at_100():
    from data.ingestors.nhl_edge import rest_rows
    def get(url):
        if "start=0" in url:
            return {"total": 3, "data": [{"playerId": 1}, {"playerId": 2}]}
        return {"total": 3, "data": [{"playerId": 3}]}
    rows = rest_rows("skater/summary", "seasonId=20262027 and gameTypeId=2", get=get, limit=2)
    assert [r["playerId"] for r in rows] == [1, 2, 3]


def test_backfill_starts_at_2023_24_and_the_daily_is_this_season():
    from data.ingestors.nhl_completed_games import season_span
    assert season_span("2026-11-26", backfill=False) == (2027, 2027)
    assert season_span("2026-11-26", backfill=True) == (2024, 2027)


def test_migration_locks_the_tables_and_is_on_the_active_list():
    from data.view_migrations import ACTIVE_MIGRATIONS
    sql = (ROOT / "data" / "migrations" / MIGRATION).read_text(encoding="utf-8")
    assert MIGRATION in ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS[-1] == "published_record_units_2026_10_16.sql"
    for name in ("nhl_shifts", "nhl_shift_linemates", "nhl_game_officials",
                 "nhl_healthy_scratches", "dailyfaceoff_line_snapshots",
                 "nhl_edge_skater_snapshots", "nhl_edge_goalie_snapshots",
                 "nhl_edge_team_snapshots"):
        assert f"public.{name}" in sql
        assert f"REVOKE ALL ON public.{name} FROM anon, authenticated" in sql
    assert sql.count("ENABLE ROW LEVEL SECURITY") == 8
    assert "snapshot_date" in sql
    assert "PRIMARY KEY (snapshot_at, team_abbr, category, group_id, player_id)" in sql


def test_steps_crons_and_warn_checks_and_nothing_is_a_pick_input():
    choices = PIPE.split("choices=[", 1)[1].split("]", 1)[0]
    for step in ("nhl-shifts", "nhl-officials", "dailyfaceoff-lines", "nhl-edge"):
        assert f'"{step}"' in choices
    assert PIPE.index('results["nhl_shots"]') < PIPE.index('results["nhl_shifts"]')
    assert PIPE.index('results["nhl_shifts"]') < PIPE.index('results["nhl_officials"]')
    assert PIPE.index('results["nhl_officials"]') < PIPE.index('results["health_check"]')
    assert 'results["nhl_edge"]' not in PIPE
    assert 'results["dailyfaceoff_lines"]' not in PIPE
    ids = re.findall(r'^\s*id="([^"]+)"', SCHED, re.M)
    for job, snippet in (
        ("nhl_shifts", "hour=7, minute=35"),
        ("nhl_officials", "hour=7, minute=50"),
        ("dailyfaceoff_lines", 'hour="11,17", minute=10'),
        ("nhl_edge", "hour=2, minute=40"),
    ):
        assert job in ids
        block = SCHED.split(f'id="{job}"', 1)[0]
        assert snippet in block[-500:]
    import scheduler
    for job in ("nhl_shifts", "nhl_officials", "dailyfaceoff_lines", "nhl_edge"):
        assert job in scheduler._PIPELINE_JOBS
        assert job not in scheduler._POLLER_JOBS
    assert "byom_nfl_refresh" in scheduler._PIPELINE_JOBS
    for check in ("nhl_shift_freshness", "nhl_officials_freshness",
                  "dailyfaceoff_lines_freshness", "nhl_edge_freshness"):
        assert check in HEALTH
    needles = ("nhl_shifts", "nhl_shift_linemates", "nhl_game_officials",
               "nhl_healthy_scratches", "dailyfaceoff_line_snapshots",
               "nhl_edge_skater_snapshots", "nhl_edge_goalie_snapshots",
               "nhl_edge_team_snapshots")
    config = (ROOT / "config.py").read_text(encoding="utf-8").lower()
    for needle in needles:
        assert needle not in config
    for path in (ROOT / "models").rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for needle in needles:
            assert needle not in text, path
