"""
Pure-function tests for the Phase 3/4 live decision logic:
trigger routing, fetch debounce, credit cap, and live signal classification.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.ingestors.live_trigger_orchestrator import (
    should_fetch,
    split_triggers,
    under_credit_cap,
)
from models.live_scorer import classify_live_signal


def _t(tid, game, ttype):
    return {"trigger_id": tid, "game_id": game, "trigger_type": ttype,
            "fired_at": "2026-06-13T00:00:00+00:00"}


# ── split_triggers ────────────────────────────────────────────────────────────

def test_split_triggers_routes_fg_tiers():
    pending = [
        _t(1, "MLB_2026-06-13_NYY_BOS", "inning_change"),
        _t(2, "MLB_2026-06-13_NYY_BOS", "score_change"),
        _t(3, "MLB_2026-06-13_LAD_SF",  "pitching_change"),
        _t(4, "MLB_2026-06-13_LAD_SF",  "due_up_change"),
    ]
    fg_games, ids = split_triggers(pending)
    assert fg_games == {"MLB_2026-06-13_NYY_BOS"}
    # ALL triggers are consumed, including the no-op tiers
    assert ids == [1, 2, 3, 4]


def test_split_triggers_unknown_type_is_noop():
    fg_games, ids = split_triggers([_t(9, "g1", "weather_delay")])
    assert fg_games == set()
    assert ids == [9]


def test_split_triggers_empty():
    assert split_triggers([]) == (set(), [])


# ── should_fetch (debounce) ───────────────────────────────────────────────────

def test_should_fetch_never_fetched():
    assert should_fetch(None, debounce_sec=60) is True


def test_should_fetch_inside_window():
    assert should_fetch(30, debounce_sec=60) is False


def test_should_fetch_window_elapsed():
    assert should_fetch(60, debounce_sec=60) is True
    assert should_fetch(300, debounce_sec=60) is True


# ── under_credit_cap ──────────────────────────────────────────────────────────

def test_credit_cap_uncapped():
    assert under_credit_cap(10_000, 3, cap=0) is True


def test_credit_cap_enforced():
    assert under_credit_cap(98, 3, cap=100) is False
    assert under_credit_cap(97, 3, cap=100) is True


# ── classify_live_signal ──────────────────────────────────────────────────────
# Live thresholds (config): prob ≥ 0.65 AND edge ≥ 0.10 → BET; edge ≤ −0.10 → AVOID.

def test_live_signal_bet():
    assert classify_live_signal("mlb_live_win_prob", 0.70, 0.12) == "BET"


def test_live_signal_requires_prob_floor():
    assert classify_live_signal("mlb_live_win_prob", 0.60, 0.12) is None


def test_live_signal_avoid():
    assert classify_live_signal("mlb_live_win_prob", 0.30, -0.12) == "AVOID"


def test_live_signal_dead_zone_not_written():
    assert classify_live_signal("mlb_live_win_prob", 0.70, 0.05) is None


def test_live_signal_noise_cap():
    # Edges beyond MAX_EDGE_CAP (0.20) are model noise — never written
    assert classify_live_signal("mlb_live_win_prob", 0.95, 0.45) is None
