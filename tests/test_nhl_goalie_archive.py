"""data/ingestors/nhl_goalie_archive: DailyFaceoff's archived goalie cards.

The page shape is the live page's (data/ingestors/nhl_goalie_designations reads
the same __NEXT_DATA__ for today). The X example is a real card: DailyFaceoff's
2025-01-15 page, BUF vs CAR, Luukkonen confirmed, news written
2025-01-15T22:29:59.766Z from the post linked below.
"""
import json
from datetime import datetime, timezone

import pytest

from data.ingestors import nhl_goalie_archive as ga
from tracking import job_queue as jq

REAL_URL = "https://x.com/engelheather/status/1879656923274121354"
REAL_NEWS_AT = datetime(2025, 1, 15, 22, 29, 59, 766000, tzinfo=timezone.utc)


def _game(home="Buffalo Sabres", away="Carolina Hurricanes", **kw):
    g = {"homeTeamName": home, "awayTeamName": away,
         "homeGoalieName": "Ukko-Pekka Luukkonen", "homeGoalieId": 4783,
         "homeNewsStrengthName": "Confirmed", "homeNewsSourceName": "Heather Engel",
         "homeNewsSourceUrl": REAL_URL, "homeNewsCreatedAt": "2025-01-15T22:29:59.766Z",
         "awayGoalieName": "Pyotr Kochetkov", "awayGoalieId": 30486,
         "awayNewsStrengthName": None, "awayNewsStrengthId": 3,
         "awayNewsSourceUrl": "https://www.nhl.com/news/x", "awayNewsCreatedAt": None}
    g.update(kw)
    return g


def test_an_x_link_gives_the_post_time_just_before_the_write_up():
    t = ga.x_post_time(REAL_URL)
    assert t is not None and t.tzinfo is not None
    # The post comes first, and DailyFaceoff wrote it up within the hour.
    assert t < REAL_NEWS_AT
    assert (REAL_NEWS_AT - t).total_seconds() < 3600
    assert ga.x_post_time("https://twitter.com/someone/status/1879656923274121354") == t
    assert ga.x_post_time("https://www.nhl.com/news/x") is None
    assert ga.x_post_time(None) is None


def test_a_card_becomes_one_row_per_team_on_our_schedule_and_others_are_skipped():
    sched = {("BUF", "CAR"): "NHL_2025-01-15_CAR_BUF"}
    page = {"data": [_game(), _game(home="Boston Bruins", away="Toronto Maple Leafs")]}
    rows, skipped = ga.parse_archive(page, "2025-01-15", sched)
    assert skipped == 1
    assert [(r["team"], r["side"]) for r in rows] == [("BUF", "home"), ("CAR", "away")]
    home, away = rows
    assert home["game_id"] == away["game_id"] == "NHL_2025-01-15_CAR_BUF"
    assert home["status"] == "confirmed" and home["source_player_id"] == "4783"
    assert home["news_created_at"] == REAL_NEWS_AT and home["post_at"] == ga.x_post_time(REAL_URL)
    # A missing strength name falls back to DailyFaceoff's id (3 = Likely).
    assert away["status"] == "likely" and away["news_created_at"] is None and away["post_at"] is None
    assert {r["source"] for r in rows} == {"dailyfaceoff_archive"}


def test_a_team_with_no_goalie_named_is_no_starter():
    sched = {("BUF", "CAR"): "G"}
    rows, _ = ga.parse_archive({"data": [_game(awayGoalieName=None)]}, "2025-01-15", sched)
    assert rows[1]["player_name"] is None and rows[1]["status"] == ga.NO_STARTER


def test_the_insert_never_rewrites_a_stored_row():
    assert "ON CONFLICT (game_id, team) DO NOTHING" in ga._INSERT
    assert "PRIMARY KEY (game_id, team)" in ga.DDL


def test_the_job_is_registered_and_its_declared_run_validates():
    fn, validate = jq.JOBS["nhl_goalie_archive"]
    assert fn is jq._job_nhl_goalie_archive
    with open("jobs/declared_jobs.json", encoding="utf-8") as fh:
        declared = [j for j in json.load(fh) if j["job_type"] == "nhl_goalie_archive"]
    assert declared and declared[0]["requested_by"] == "mike"
    assert validate(declared[0]["args"]) == {"apply": True, "start": None, "end": None}
    assert validate({"start": "2025-10-01", "end": "2026-04-20"})["start"] == "2025-10-01"
    with pytest.raises(ValueError):
        validate({"apply": True, "credit_cap": 5})
    with pytest.raises(ValueError):
        validate({"start": "2026-04-20", "end": "2025-10-01"})


def test_the_table_is_locked_from_the_app():
    from data import anon_readable
    assert "nhl_goalie_archive" in anon_readable.WORKER_ONLY_TABLES
