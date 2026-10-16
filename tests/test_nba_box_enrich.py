"""NBA box-score enrichment: starters, exact minutes, DNP reasons, officials,
inactives, usage -- and the neutral-site game-log fill.

Each test pins one way the rows written to Supabase could be silently wrong:
a minutes string misread, a DNP counted as a 0-minute appearance, a bench
player marked as a starter, a row attached to the wrong game, a game-log fill
that writes rows for games that already had them.
"""
from __future__ import annotations

import pandas as pd
import pytest

from data.ingestors.nba_box_enrich import (
    box_rows, dnp_kind, inactive_rows, minutes_to_float, minutes_to_seconds,
    neutral_fill_rows, official_rows, starter_update_batches,
)

SCHED = {
    "0022500001": {"game_id": "NBA_2025-10-21_HOU_OKC", "season": 2026,
                   "game_type": "regular", "game_date": "2025-10-21",
                   "home_team": "OKC", "away_team": "HOU"},
}


def _box(**over):
    base = {
        "game_id": "0022500001", "team_id": 1610612760, "team_tricode": "OKC",
        "side": "home", "person_id": 1628983, "first_name": "Shai",
        "family_name": "Gilgeous-Alexander", "position": "G", "comment": "",
        "minutes": "47:13", "fouls_personal": 3, "plus_minus_points": 2.0,
        "season_type_id": "2",
    }
    base.update(over)
    return base


# ── minutes ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw, want", [
    ("45:15", 45.25), ("0:06", 0.1), ("12:00", 12.0), ("0:00", 0.0),
    ("48:53", 48 + 53 / 60),
])
def test_minutes_strings_are_read_to_the_second(raw, want):
    assert minutes_to_float(raw) == pytest.approx(want)


@pytest.mark.parametrize("raw", ["", None, "   ", float("nan")])
def test_a_blank_minutes_string_is_null_not_zero(raw):
    assert minutes_to_float(raw) is None
    assert minutes_to_seconds(raw) is None


def test_minutes_to_seconds():
    assert minutes_to_seconds("45:15") == 2715
    assert minutes_to_seconds("0:00") == 0


# ── DNP classification ────────────────────────────────────────────────────────

@pytest.mark.parametrize("comment, kind", [
    ("DNP - Coach's Decision", "DNP"),
    ("DND - Injury/Illness", "DND"),
    ("NWT - Not With Team", "NWT"),
    ("DND_LEAGUE_SUSPENSION", "DND"),
    ("NWT-Return to Competition Reconditioning", "NWT"),
    ("", None), (None, None),
])
def test_dnp_kind(comment, kind):
    assert dnp_kind(comment) == kind


# ── player rows ───────────────────────────────────────────────────────────────

def test_a_starter_is_a_row_with_a_starting_position():
    df = pd.DataFrame([_box(), _box(person_id=1, position="", minutes="12:53")])
    rows, unmapped = box_rows(df, SCHED)
    by = {r["player_id"]: r for r in rows}
    assert by["1628983"]["is_starter"] == 1
    assert by["1"]["is_starter"] == 0
    assert by["1"]["position"] is None
    assert unmapped == set()


def test_a_dnp_row_has_null_minutes_and_its_reason_and_is_not_a_starter():
    df = pd.DataFrame([_box(person_id=2, position="", minutes="",
                            comment="DNP - Coach's Decision",
                            plus_minus_points=0.0, fouls_personal=0)])
    (row,), _ = box_rows(df, SCHED)
    assert row["played"] is False
    assert row["minutes_exact"] is None
    assert row["seconds_played"] is None
    assert row["did_not_play_reason"] == "DNP - Coach's Decision"
    assert row["dnp_kind"] == "DNP"
    assert row["is_starter"] == 0
    # The feed writes 0 for a player who never checked in; 0 would read as
    # "played even minutes". NULL says he did not play.
    assert row["plus_minus"] is None
    assert row["fouls"] is None


def test_a_zero_minute_appearance_is_played_not_a_dnp():
    df = pd.DataFrame([_box(person_id=3, position="", minutes="0:00",
                            plus_minus_points=0.0, fouls_personal=1)])
    (row,), _ = box_rows(df, SCHED)
    assert row["played"] is True
    assert row["minutes_exact"] == 0.0
    assert row["did_not_play_reason"] is None
    assert row["fouls"] == 1


def test_a_played_row_carries_game_identity_from_the_schedule():
    df = pd.DataFrame([_box()])
    (row,), _ = box_rows(df, SCHED)
    assert row["game_id"] == "NBA_2025-10-21_HOU_OKC"
    assert row["nba_game_id"] == "0022500001"
    assert row["season"] == 2026
    assert row["game_type"] == "regular"
    assert row["game_date"] == "2025-10-21"
    assert row["team"] == "OKC"
    assert row["opponent"] == "HOU"
    assert row["is_home"] is True
    assert row["player_id"] == "1628983"          # TEXT, like nba_player_game_log
    assert row["minutes_exact"] == pytest.approx(47 + 13 / 60)
    assert row["plus_minus"] == 2
    assert row["fouls"] == 3


def test_a_game_the_schedule_does_not_know_is_dropped_and_reported():
    df = pd.DataFrame([_box(), _box(game_id="0022599999", person_id=9)])
    rows, unmapped = box_rows(df, SCHED)
    assert [r["player_id"] for r in rows] == ["1628983"]
    assert unmapped == {"0022599999"}


def test_a_team_that_is_not_in_the_scheduled_game_is_refused():
    # A box row attached to the wrong game must not be written under it.
    df = pd.DataFrame([_box(team_tricode="BOS", side="away")])
    with pytest.raises(ValueError):
        box_rows(df, SCHED)


def test_advanced_stats_merge_on_game_and_player():
    df = pd.DataFrame([_box(), _box(person_id=2, position="", minutes="",
                                    comment="DNP - Coach's Decision")])
    adv = pd.DataFrame([{
        "GAME_ID": "0022500001", "PLAYER_ID": 1628983, "USG_PCT": 0.33,
        "E_USG_PCT": 0.34, "POSS": 101, "PACE": 99.5, "E_PACE": 100.1,
        "PACE_PER40": 82.9, "OFF_RATING": 120.0, "DEF_RATING": 110.0,
        "NET_RATING": 10.0, "E_OFF_RATING": 119.0, "E_DEF_RATING": 111.0,
        "E_NET_RATING": 8.0, "AST_PCT": 0.3, "AST_TO": 2.0, "AST_RATIO": 20.0,
        "OREB_PCT": 0.02, "DREB_PCT": 0.1, "REB_PCT": 0.06, "TM_TOV_PCT": 9.0,
        "E_TOV_PCT": 9.1, "EFG_PCT": 0.55, "TS_PCT": 0.61, "PIE": 0.2,
    }])
    rows, _ = box_rows(df, SCHED, adv)
    by = {r["player_id"]: r for r in rows}
    assert by["1628983"]["usage_pct"] == pytest.approx(0.33)
    assert by["1628983"]["possessions"] == 101
    assert by["1628983"]["pace"] == pytest.approx(99.5)
    assert by["2"]["usage_pct"] is None
    assert by["2"]["possessions"] is None


# ── officials and inactives ───────────────────────────────────────────────────

def test_officials_rows_strip_the_jersey_and_join_the_name():
    df = pd.DataFrame([{"official_id": 2534, "first_name": "Zach",
                        "last_name": "Zarba", "jersey_num": "15 ",
                        "game_id": "0022500001", "season_type_id": "2"},
                       {"official_id": 7, "first_name": "X", "last_name": "Y",
                        "jersey_num": "", "game_id": "0022599999",
                        "season_type_id": "2"}])
    rows, unmapped = official_rows(df, SCHED)
    assert rows == [{
        "game_id": "NBA_2025-10-21_HOU_OKC", "official_id": "2534",
        "official_name": "Zach Zarba", "jersey": "15",
        "nba_game_id": "0022500001", "season": 2026, "game_type": "regular",
        "game_date": "2025-10-21", "source": "sdv_nba_stats_officials",
    }]
    assert unmapped == {"0022599999"}


def test_inactive_rows_carry_team_and_leave_reason_null():
    df = pd.DataFrame([{"player_id": 1627832, "first_name": "Fred",
                        "last_name": "VanVleet", "jersey_num": "5 ",
                        "team_abbreviation": "HOU", "game_id": "0022500001",
                        "season_type_id": "2"}])
    rows, _ = inactive_rows(df, SCHED)
    assert rows == [{
        "game_id": "NBA_2025-10-21_HOU_OKC", "team": "HOU",
        "player_id": "1627832", "player_name": "Fred VanVleet",
        "reason": None, "jersey": "5", "nba_game_id": "0022500001",
        "season": 2026, "game_type": "regular", "game_date": "2025-10-21",
        "source": "sdv_nba_stats_game_rosters",
    }]


# ── neutral-site game-log fill ────────────────────────────────────────────────

def test_the_neutral_fill_writes_only_the_missing_games():
    frame = pd.DataFrame([
        {"GAME_ID": "0022500101", "GAME_DATE": "2025-11-15", "PLAYER_ID": 1,
         "PLAYER_NAME": "A", "TEAM_ABBREVIATION": "DET", "TEAM_NAME": "",
         "MIN": 30, "PTS": 10},
        {"GAME_ID": "0022500102", "GAME_DATE": "2025-11-15", "PLAYER_ID": 2,
         "PLAYER_NAME": "B", "TEAM_ABBREVIATION": "BOS", "TEAM_NAME": "",
         "MIN": 20, "PTS": 4},
    ])
    rows = neutral_fill_rows(frame, {"0022500101": "NBA_2025-11-15_DAL_DET"}, 2026)
    assert [(r["game_id"], r["player_id"]) for r in rows] == [
        ("NBA_2025-11-15_DAL_DET", "1")]
    assert rows[0]["season"] == 2026
    assert rows[0]["minutes"] == 30


def test_the_neutral_fill_matches_a_game_id_that_lost_its_leading_zeros():
    # A frame read back with GAME_ID as a number has 22500101, not 0022500101;
    # matching on the raw value would write nothing and report success.
    frame = pd.DataFrame([
        {"GAME_ID": 22500101, "GAME_DATE": "2025-11-15", "PLAYER_ID": 1,
         "PLAYER_NAME": "A", "TEAM_ABBREVIATION": "DET", "TEAM_NAME": "",
         "MIN": 30, "PTS": 10},
    ])
    rows = neutral_fill_rows(frame, {"0022500101": "NBA_2025-11-15_DAL_DET"}, 2026)
    assert [r["game_id"] for r in rows] == ["NBA_2025-11-15_DAL_DET"]


def test_starter_updates_are_batched_by_game():
    ids = [f"g{i}" for i in range(250)]
    batches = list(starter_update_batches(ids, 100))
    assert [len(b) for b in batches] == [100, 100, 50]
    assert sum(batches, []) == ids
