"""
The inning-gate replay's two load-bearing pure functions.

The replay itself is a measurement tool, not production code, but two things in
it decide every number it prints and both are easy to get silently wrong:

  * `_pair` — a state is only scoreable against a price that EXISTED at that
    moment. Pairing a state with a LATER price is lookahead, and the result
    would be an inning gate that looks profitable because it read the future.
  * `_grade` — an over/under settled against the final score, where the sign
    convention has cost this repo a wrong threshold twice (CLAUDE.md 4).
"""

from __future__ import annotations

from scripts.live_inning_gate_replay import _grade, _implied, _pair


def _state(ts, inning=1):
    return {"snapshot_at": ts, "inning": inning}


def _price(ts, line=8.5):
    return {"snapshot_at": ts, "total_line": line,
            "over_price": -110, "under_price": -110}


BASE = "2026-09-05T23:0"


def test_a_state_takes_the_newest_price_at_or_before_it():
    paired = _pair([_state(f"{BASE}5:00Z")],
                   [_price(f"{BASE}0:00Z", 8.5), _price(f"{BASE}4:00Z", 9.5)])
    assert [p["total_line"] for _, p in paired] == [9.5]


def test_a_price_from_the_future_is_never_used():
    """The lookahead that would make any gate look good."""
    assert _pair([_state(f"{BASE}0:00Z")], [_price(f"{BASE}5:00Z")]) == []


def test_a_price_older_than_the_age_bound_is_dropped():
    assert _pair([_state("2026-09-05T23:30:00Z")],
                 [_price("2026-09-05T23:00:00Z")]) == []


def test_the_walk_keeps_up_across_many_states():
    states = [_state(f"2026-09-05T23:{m:02d}:00Z") for m in range(0, 10)]
    prices = [_price(f"2026-09-05T23:{m:02d}:30Z", 8.0 + m) for m in range(0, 9)]
    paired = _pair(states, prices)
    # 23:00 has no price at or before it; every later state takes its own minute.
    assert [p["total_line"] for _, p in paired] == [8.0 + m for m in range(0, 9)]


def test_unparseable_timestamps_are_skipped_not_crashed():
    assert _pair([_state("not a time")], [_price(f"{BASE}0:00Z")]) == []


# ── grading ──────────────────────────────────────────────────────────────────

def _sig(side, line, odds=-110):
    return {"side": side, "line": line, "odds": odds}


def _game(home, away):
    return {"home_score": home, "away_score": away}


def test_an_over_wins_when_the_final_total_clears_the_line():
    assert _grade(_sig("over", 8.5), _game(5, 4))[0] == "WIN"


def test_an_over_loses_when_it_does_not():
    assert _grade(_sig("over", 8.5), _game(4, 4))[0] == "LOSS"


def test_an_under_is_the_mirror_of_the_over():
    for total, expected in ((_game(4, 4), "WIN"), (_game(5, 4), "LOSS")):
        assert _grade(_sig("under", 8.5), total)[0] == expected


def test_a_whole_number_line_can_push():
    assert _grade(_sig("over", 9.0), _game(5, 4)) == ("PUSH", 0.0)


def test_a_dog_returns_its_price_and_a_loss_returns_one_unit():
    assert _grade(_sig("over", 8.5, +130), _game(5, 4))[1] == 1.30
    assert _grade(_sig("over", 8.5, -110), _game(1, 1))[1] == -1.0


def test_implied_probability_handles_both_signs_and_refuses_nonsense():
    assert _implied(-110) == 110 / 210
    assert _implied(+100) == 0.5
    assert _implied(0) is None
    assert _implied(None) is None


# ── the control gates the tables ─────────────────────────────────────────────
#
# The 2026-09-07 run printed "13 the other way" immediately above two gate
# tables, and the tables were read and the verdict acted on. A check that is
# allowed to fail beside the number it guards is not a check.

from scripts.live_inning_gate_replay import _refuse_tables


def test_one_missed_game_is_enough_to_refuse():
    assert _refuse_tables({"MLB_2026-09-07_LAA_BOS"}, False) is True


def test_a_clean_control_prints_the_tables():
    assert _refuse_tables(set(), False) is False


def test_force_is_the_only_way_past_a_failing_control():
    assert _refuse_tables({"g1", "g2"}, True) is False


def test_force_does_not_invent_a_failure_when_the_control_passed():
    assert _refuse_tables(set(), True) is False
