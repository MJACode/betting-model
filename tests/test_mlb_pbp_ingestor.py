"""
Tests for data/ingestors/mlb_pbp_ingestor.py — pure parser only.

Covers the play parser using a small synthetic feed payload that mirrors the
real MLB Stats API /api/v1.1/game/{gamePk}/feed/live shape.
"""

from data.ingestors.mlb_pbp_ingestor import (
    _bases_after_from_matchup,
    _split_event_type,
    parse_game_plays,
    parse_play,
)


# ── _bases_after_from_matchup ─────────────────────────────────────────────────

def test_bases_empty_matchup():
    assert _bases_after_from_matchup({}) == "000"
    assert _bases_after_from_matchup(None) == "000"


def test_bases_with_runners():
    assert _bases_after_from_matchup(
        {"postOnFirst": {"id": 1}}
    ) == "100"
    assert _bases_after_from_matchup(
        {"postOnFirst": {"id": 1}, "postOnThird": {"id": 3}}
    ) == "101"
    assert _bases_after_from_matchup(
        {"postOnFirst": {"id": 1}, "postOnSecond": {"id": 2}, "postOnThird": {"id": 3}}
    ) == "111"


# ── _split_event_type ─────────────────────────────────────────────────────────

def test_split_event_type():
    et, desc = _split_event_type({"eventType": "single", "description": "Singled to CF."})
    assert et == "single"
    assert desc == "Singled to CF."


def test_split_event_type_empty():
    assert _split_event_type({}) == (None, None)
    assert _split_event_type(None) == (None, None)


# ── parse_play (single-play) ──────────────────────────────────────────────────

_PLAY_SINGLE = {
    "result":  {"eventType": "single", "description": "Lindor singles to RF.",
                "homeScore": 0, "awayScore": 0},
    "about":   {"inning": 1, "isTopInning": True},
    "count":   {"outs": 0},
    "matchup": {
        "batter":   {"id": 596019, "fullName": "Francisco Lindor"},
        "pitcher":  {"id": 543037, "fullName": "Gerrit Cole"},
        "batSide":  {"code": "S"},
        "pitchHand":{"code": "R"},
        "postOnFirst": {"id": 596019},
    },
}


def test_parse_play_first_play_of_game():
    row = parse_play(
        _PLAY_SINGLE,
        state_before={
            "outs_after": 0, "score_home_after": 0, "score_away_after": 0,
            "bases_after": "000", "half_inning": None,
        },
        home_won=1,
        season=2024,
        game_id="MLB_2024-04-05_NYM_PHI",
        play_index=0,
    )
    assert row["play_index"] == 0
    assert row["inning"] == 1
    assert row["half_inning"] == "top"
    assert row["outs_before"] == 0
    assert row["bases_before"] == "000"
    assert row["bases_after"] == "100"
    assert row["batter_id"] == "596019"
    assert row["pitcher_id"] == "543037"
    assert row["bat_side"] == "S"
    assert row["pitch_hand"] == "R"
    assert row["event_type"] == "single"
    assert row["runs_on_play"] == 0
    assert row["outs_added"] == 0
    assert row["home_won"] == 1


def test_parse_play_carries_runners_forward():
    # Second play: runner on first, batter walks → runners on 1B and 2B.
    walk_play = {
        "result":  {"eventType": "walk", "description": "Alonso walks.",
                    "homeScore": 0, "awayScore": 0},
        "about":   {"inning": 1, "isTopInning": True},
        "count":   {"outs": 0},
        "matchup": {
            "batter":  {"id": 624413, "fullName": "Pete Alonso"},
            "pitcher": {"id": 543037, "fullName": "Gerrit Cole"},
            "batSide": {"code": "R"},
            "pitchHand":{"code": "R"},
            "postOnFirst":  {"id": 624413},
            "postOnSecond": {"id": 596019},
        },
    }
    row = parse_play(
        walk_play,
        state_before={
            "outs_after": 0, "score_home_after": 0, "score_away_after": 0,
            "bases_after": "100", "half_inning": "top",
        },
        home_won=0, season=2024, game_id="MLB_2024-04-05_NYM_PHI", play_index=1,
    )
    assert row["bases_before"] == "100"
    assert row["bases_after"]  == "110"
    assert row["outs_before"] == 0
    assert row["outs_added"] == 0


def test_parse_play_run_scored_increments_runs_on_play():
    home_run_play = {
        "result":  {"eventType": "home_run", "description": "Lindor HR.",
                    "homeScore": 0, "awayScore": 2},
        "about":   {"inning": 1, "isTopInning": True},
        "count":   {"outs": 0},
        "matchup": {
            "batter":  {"id": 596019}, "pitcher": {"id": 543037},
            "batSide": {"code": "S"}, "pitchHand": {"code": "R"},
        },
    }
    row = parse_play(
        home_run_play,
        state_before={
            "outs_after": 0, "score_home_after": 0, "score_away_after": 0,
            "bases_after": "100", "half_inning": "top",
        },
        home_won=0, season=2024, game_id="MLB_2024-04-05_NYM_PHI", play_index=2,
    )
    assert row["runs_on_play"] == 2
    assert row["score_away_after"] == 2
    assert row["bases_after"] == "000"


def test_parse_play_out_increments_outs_added():
    strikeout = {
        "result":  {"eventType": "strikeout", "description": "Soto K-ing.",
                    "homeScore": 0, "awayScore": 2},
        "about":   {"inning": 1, "isTopInning": True},
        "count":   {"outs": 1},
        "matchup": {
            "batter":  {"id": 665742}, "pitcher": {"id": 543037},
            "batSide": {"code": "L"}, "pitchHand": {"code": "R"},
        },
    }
    row = parse_play(
        strikeout,
        state_before={
            "outs_after": 0, "score_home_after": 0, "score_away_after": 2,
            "bases_after": "000", "half_inning": "top",
        },
        home_won=0, season=2024, game_id="MLB_2024-04-05_NYM_PHI", play_index=3,
    )
    assert row["outs_added"] == 1
    assert row["outs_after"] == 1


def test_parse_play_half_inning_change_resets_outs_and_bases():
    # The bottom of the inning starts; previous state had 3 outs / runners on
    # base (which would carry over wrongly without the half-inning reset).
    bottom_first = {
        "result":  {"eventType": "field_out", "description": "Schwarber grounds out.",
                    "homeScore": 0, "awayScore": 2},
        "about":   {"inning": 1, "isTopInning": False},
        "count":   {"outs": 1},
        "matchup": {
            "batter":  {"id": 656941}, "pitcher": {"id": 605400},
            "batSide": {"code": "L"}, "pitchHand": {"code": "R"},
        },
    }
    row = parse_play(
        bottom_first,
        state_before={
            "outs_after": 3, "score_home_after": 0, "score_away_after": 2,
            "bases_after": "110", "half_inning": "top",
        },
        home_won=0, season=2024, game_id="MLB_2024-04-05_NYM_PHI", play_index=4,
    )
    assert row["half_inning"] == "bottom"
    assert row["outs_before"] == 0          # reset across half-inning
    assert row["bases_before"] == "000"     # reset across half-inning


# ── parse_game_plays (end-to-end) ─────────────────────────────────────────────

def test_parse_game_plays_walks_full_inning():
    feed = {
        "liveData": {
            "plays": {
                "allPlays": [
                    {
                        "result":  {"eventType": "single", "description": "Lindor 1B.",
                                    "homeScore": 0, "awayScore": 0},
                        "about":   {"inning": 1, "isTopInning": True},
                        "count":   {"outs": 0},
                        "matchup": {
                            "batter": {"id": 1}, "pitcher": {"id": 99},
                            "batSide": {"code": "S"}, "pitchHand": {"code": "R"},
                            "postOnFirst": {"id": 1},
                        },
                    },
                    {
                        "result":  {"eventType": "home_run", "description": "Alonso HR.",
                                    "homeScore": 0, "awayScore": 2},
                        "about":   {"inning": 1, "isTopInning": True},
                        "count":   {"outs": 0},
                        "matchup": {
                            "batter": {"id": 2}, "pitcher": {"id": 99},
                            "batSide": {"code": "R"}, "pitchHand": {"code": "R"},
                        },
                    },
                    {
                        "result":  {"eventType": "strikeout", "description": "Soto K.",
                                    "homeScore": 0, "awayScore": 2},
                        "about":   {"inning": 1, "isTopInning": True},
                        "count":   {"outs": 1},
                        "matchup": {
                            "batter": {"id": 3}, "pitcher": {"id": 99},
                            "batSide": {"code": "L"}, "pitchHand": {"code": "R"},
                        },
                    },
                ]
            }
        }
    }

    rows = parse_game_plays(feed, game_id="MLB_2024-04-05_NYM_PHI", season=2024, home_won=0)
    assert len(rows) == 3
    assert [r["play_index"] for r in rows] == [0, 1, 2]
    # Carry-forward of bases between plays
    assert rows[0]["bases_after"] == "100"
    assert rows[1]["bases_before"] == "100"
    # Score increment carries forward
    assert rows[1]["runs_on_play"] == 2
    assert rows[2]["score_away_before"] == 2
    # Outs accumulate
    assert rows[2]["outs_before"] == 0
    assert rows[2]["outs_after"]  == 1
    # Label stamped on every row
    assert all(r["home_won"] == 0 for r in rows)


def test_parse_game_plays_empty_feed():
    assert parse_game_plays({}, game_id="X", season=2024, home_won=1) == []
    assert parse_game_plays(
        {"liveData": {"plays": {"allPlays": []}}},
        game_id="X", season=2024, home_won=1,
    ) == []
