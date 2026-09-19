"""Shared slate-side concentration guard for game-market cards.

A slate where one pick_side is ≥70% of n_bet ≥ 4 is not a selective
card. First consumer is mlb_total_public_fade (always UNDER); the helper
is side-agnostic so other game-market cards can call it.
"""
from __future__ import annotations

from models.slate_concentration import (
    MAX_SHARE,
    MIN_BETS,
    POLICY_SUPPRESS_ALL,
    POLICY_TOP_K,
    apply_slate_concentration_guard,
    measure_side_concentration,
)


def _row(side, edge=0.20, signal="BET", gid=None):
    return {
        "game_id": gid or f"G-{side}-{edge}",
        "pick_side": side,
        "edge": edge,
        "signal_type": signal,
    }


def test_defaults_are_four_bets_and_seventy_percent():
    assert MIN_BETS == 4
    assert MAX_SHARE == 0.70


def test_ten_unders_are_concentrated_and_suppress_all_keeps_none():
    rows = [_row("under", 0.20 + i * 0.01, gid=f"G{i}") for i in range(10)]
    measured = measure_side_concentration(rows)
    assert measured.triggered is True
    assert measured.n_bet == 10
    assert measured.n_under == 10
    assert measured.n_over == 0
    assert measured.share == 1.0
    assert measured.concentrated_side == "under"
    kept, decision = apply_slate_concentration_guard(
        rows, policy=POLICY_SUPPRESS_ALL, log=False)
    assert kept == []
    assert decision.suppressed == 10
    assert decision.kept == 0
    msg = decision.warn_message("mlb_total_public_fade")
    assert "n_bet=10" in msg
    assert "n_under=10" in msg
    assert "n_over=0" in msg
    assert "threshold=70%" in msg


def test_three_unders_of_eight_is_not_concentrated():
    """3/8 = 37.5% < 70%. The unders that passed their own cut stay."""
    rows = (
        [_row("under", 0.25, gid=f"U{i}") for i in range(3)]
        + [_row("over", 0.22, gid=f"O{i}") for i in range(5)]
    )
    measured = measure_side_concentration(rows)
    assert measured.n_bet == 8
    assert measured.n_under == 3
    assert measured.n_over == 5
    assert measured.triggered is False
    kept, decision = apply_slate_concentration_guard(rows, log=False)
    assert kept == rows
    assert decision.triggered is False


def test_exactly_seventy_percent_of_ten_triggers():
    rows = (
        [_row("under", gid=f"U{i}") for i in range(7)]
        + [_row("over", gid=f"O{i}") for i in range(3)]
    )
    measured = measure_side_concentration(rows)
    assert measured.n_bet == 10
    assert measured.n_under == 7
    assert measured.share == 0.7
    assert measured.triggered is True


def test_four_all_one_side_triggers_three_does_not():
    four = [_row("under", gid=f"U{i}") for i in range(4)]
    three = [_row("under", gid=f"U{i}") for i in range(3)]
    assert measure_side_concentration(four).triggered is True
    assert measure_side_concentration(three).triggered is False
    kept, _ = apply_slate_concentration_guard(four, log=False)
    assert kept == []
    kept3, _ = apply_slate_concentration_guard(three, log=False)
    assert kept3 == three


def test_top_k_keeps_two_highest_edge_when_asked():
    rows = [_row("under", edge=0.10 + i * 0.01, gid=f"G{i}") for i in range(6)]
    kept, decision = apply_slate_concentration_guard(
        rows, policy=POLICY_TOP_K, top_k=2, log=False)
    assert decision.triggered is True
    assert decision.policy == POLICY_TOP_K
    assert decision.kept == 2
    assert decision.suppressed == 4
    assert {r["game_id"] for r in kept} == {"G4", "G5"}


def test_none_rows_do_not_count_toward_the_slate():
    rows = [_row("under", gid=f"U{i}") for i in range(3)] + [
        _row("under", signal="NONE", gid="N1"),
    ]
    measured = measure_side_concentration(rows)
    assert measured.n_bet == 3
    assert measured.triggered is False
