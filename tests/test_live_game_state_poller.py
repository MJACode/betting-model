"""
Tests for data/ingestors/live_game_state_poller.py — pure functions only.

These tests cover trigger detection, base-state encoding, and game discovery
filtering. Network-touching paths (_fetch_live_feed, statsapi.schedule) are
not exercised here — they need a live API and belong in an integration suite.
"""

from datetime import datetime, timedelta, timezone

import pytest

from data.ingestors.live_game_state_poller import (
    _bases_state,
    _detect_triggers,
    _extract_state,
    _is_active_or_starting_soon,
)


# ── _bases_state ──────────────────────────────────────────────────────────────

def test_bases_state_empty():
    assert _bases_state({}) == "000"
    assert _bases_state({"offense": {}}) == "000"


def test_bases_state_single_runner():
    assert _bases_state({"offense": {"first":  {"id": 1}}}) == "100"
    assert _bases_state({"offense": {"second": {"id": 2}}}) == "010"
    assert _bases_state({"offense": {"third":  {"id": 3}}}) == "001"


def test_bases_state_loaded():
    assert _bases_state(
        {"offense": {"first": {"id": 1}, "second": {"id": 2}, "third": {"id": 3}}}
    ) == "111"


# ── _detect_triggers ──────────────────────────────────────────────────────────

_BASE_STATE = {
    "inning": 3, "inning_half": "top",
    "outs": 2, "bases_state": "100",
    "home_score": 2, "away_score": 1,
    "current_pitcher_id": "A", "current_batter_id": "X", "on_deck_batter_id": "Y",
    "abstract_game_state": "Live",
}


def test_no_prev_state_fires_no_triggers():
    # First snapshot — nothing to compare against.
    assert _detect_triggers(None, _BASE_STATE) == []


def test_identical_state_fires_no_triggers():
    assert _detect_triggers(_BASE_STATE, dict(_BASE_STATE)) == []


def test_outs_alone_fires_nothing():
    # Outs change without batter change is just a mid-PA event — we do not
    # treat it as a trigger (no line-move opportunity).
    curr = dict(_BASE_STATE, outs=3)
    assert _detect_triggers(_BASE_STATE, curr) == []


def test_inning_half_change_fires_inning_change():
    curr = dict(_BASE_STATE, inning_half="bottom", current_batter_id="Y")
    fired = {t for t, _ in _detect_triggers(_BASE_STATE, curr)}
    assert "inning_change" in fired
    assert "due_up_change" in fired


def test_score_change_fires_score_change():
    curr = dict(_BASE_STATE, home_score=3)
    fired = {t for t, _ in _detect_triggers(_BASE_STATE, curr)}
    assert fired == {"score_change"}


def test_pitching_change_fires_pitching_change():
    curr = dict(_BASE_STATE, current_pitcher_id="B")
    fired = {t for t, _ in _detect_triggers(_BASE_STATE, curr)}
    assert fired == {"pitching_change"}


def test_due_up_change_fires_due_up_change():
    curr = dict(_BASE_STATE, current_batter_id="Z")
    fired = {t for t, _ in _detect_triggers(_BASE_STATE, curr)}
    assert fired == {"due_up_change"}


def test_combined_changes_fire_all_relevant_triggers():
    curr = dict(
        _BASE_STATE,
        inning=4, inning_half="top",
        home_score=3,
        current_pitcher_id="B",
        current_batter_id="Z",
    )
    fired = {t for t, _ in _detect_triggers(_BASE_STATE, curr)}
    assert fired == {
        "inning_change", "score_change", "pitching_change", "due_up_change"
    }


def test_trigger_detail_contains_field_change():
    curr = dict(_BASE_STATE, home_score=3)
    triggers = _detect_triggers(_BASE_STATE, curr)
    assert len(triggers) == 1
    _, detail = triggers[0]
    assert "home_score" in detail
    assert "2" in detail and "3" in detail


# ── _extract_state ────────────────────────────────────────────────────────────

def test_extract_state_pulls_fields_from_live_feed():
    feed = {
        "gameData": {"status": {"abstractGameState": "Live"}},
        "liveData": {
            "linescore": {
                "currentInning": 4,
                "inningHalf":    "Top",
                "outs":          1,
                "offense":       {
                    "first":  {"id": 100},
                    "third":  {"id": 300},
                    "batter": {"id": 999},
                    "onDeck": {"id": 998},
                },
                "teams": {
                    "home": {"runs": 5},
                    "away": {"runs": 2},
                },
            },
            "plays": {
                "currentPlay": {
                    "matchup": {
                        "pitcher": {"id": 555},
                        "batter":  {"id": 999},
                    }
                }
            },
        },
    }
    state = _extract_state(feed)
    assert state["inning"] == 4
    assert state["inning_half"] == "top"          # lowercased
    assert state["outs"] == 1
    assert state["bases_state"] == "101"
    assert state["home_score"] == 5
    assert state["away_score"] == 2
    assert state["current_pitcher_id"] == "555"
    assert state["current_batter_id"] == "999"
    assert state["on_deck_batter_id"] == "998"
    assert state["abstract_game_state"] == "Live"


def test_extract_state_handles_empty_feed():
    state = _extract_state({})
    assert state["inning"] is None
    assert state["bases_state"] == "000"
    assert state["current_pitcher_id"] is None


# ── _is_active_or_starting_soon ───────────────────────────────────────────────

def test_active_in_progress_game_is_active():
    assert _is_active_or_starting_soon({
        "status": "In Progress",
        "abstract_game_state": "Live",
    })


def test_final_game_is_not_active():
    assert not _is_active_or_starting_soon({
        "status": "Final",
        "abstract_game_state": "Final",
    })


def test_pregame_far_in_future_is_not_active():
    future = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
    assert not _is_active_or_starting_soon({
        "status": "Scheduled",
        "abstract_game_state": "Preview",
        "game_datetime": future,
    })


def test_pregame_starting_soon_is_active():
    # 5 minutes from now — within the LIVE_PREGAME_BUFFER_MIN window.
    soon = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    assert _is_active_or_starting_soon({
        "status": "Scheduled",
        "abstract_game_state": "Preview",
        "game_datetime": soon,
    })


def test_pregame_missing_time_is_not_active():
    assert not _is_active_or_starting_soon({
        "status": "Scheduled",
        "abstract_game_state": "Preview",
    })
