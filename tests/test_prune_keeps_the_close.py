"""The pruner keeps the CLOSING non-DK snapshot, not just the opener.

mike, 2026-09-03: "keep one non-dk snapshot per day." Until then a settled
game's only surviving line-shop row was the OPENER, and an opener cannot answer
either question the retained history exists for — the best price available at
DECISION time (Stage 2's re-sweep, for propositions that never got a scored
row) or "did the best book beat DK at close?".

Pruned rows are gone permanently, so these assert the SQL keeps what it claims
before it is ever run against production. Source-level: prune_table builds one
statement per tier and the keep-set is the part that must not regress.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

SRC = (Path(__file__).parent.parent / "data" / "prune_odds.py").read_text(
    encoding="utf-8")


def _tier(name: str) -> str:
    """The SQL text of one delete tier or of the keep-set."""
    m = re.search(rf'{name} = f"""(.*?)"""', SRC, re.S)
    assert m, f"{name} not found — prune_odds.py was restructured"
    return m.group(1)


def test_the_close_is_selected_by_the_newest_snapshot():
    body = _tier("select_keepers")
    assert "ORDER BY snapshot_at DESC" in body
    assert "rn_last = 1" in body


def test_the_opener_is_still_selected_by_the_oldest():
    """The 2026-08-25 rule this is layered on top of, not a replacement for."""
    body = _tier("select_keepers")
    assert "ORDER BY snapshot_at ASC" in body
    assert "rn_first = 1" in body


def test_the_close_is_never_an_in_play_price():
    """An in-play row is a different proposition (CLAUDE.md §6). Keeping one as
    'the close' hands every later analysis a price from the third inning.

    The DESC ranking is partitioned BY the pre-game flag, so rn_last = 1 AND
    is_pre is the newest PRE-GAME row — not the newest row that happens to be
    pre-game, which is what an unpartitioned ranking would give.
    """
    body = _tier("select_keepers")
    assert "{is_pre}" in body, "the close can be an in-play price"
    assert "PARTITION BY {part_by}, {is_pre}" in body, (
        "the DESC ranking is not scoped to pre-game rows, so a proposition "
        "whose newest row is in-play keeps nothing pre-game at all")
    assert "is_pre AND rn_last = 1" in body
    assert "snapshot_type IS NULL" in SRC, (
        "NULL snapshot_type must count as pre-game — every reader treats it "
        "that way, and excluding it would keep nothing for older rows")


def test_both_delete_tiers_spare_the_keep_set():
    """Tier 1 (settled games past the window) and tier 2 (superseded rows
    inside it) both delete, so both must spare it. Sparing it in one tier only
    means the other deletes it a day later."""
    for tier in ("where_old", "select_superseded"):
        assert "select_keepers" in _tier(tier), (
            f"{tier} does not spare the opener and close")


def test_each_tier_uses_exactly_one_anti_join():
    """PERFORMANCE IS CORRECTNESS HERE. The first version of this change added
    a SECOND `NOT IN` beside the opener's, and the dry-run stopped completing:
    `canceling statement due to statement timeout` on a job that finishes in
    ~80s unchanged. A pruner that times out prunes nothing, and the growth it
    exists to bound is silent. Both keep-rules therefore ride on ONE scan.
    """
    for tier in ("where_old", "select_superseded"):
        assert _tier(tier).count("NOT IN") == 1, (
            f"{tier} does more than one anti-join — this timed out in "
            f"production against 2.2M and 2.5M rows")


def test_the_protected_books_are_untouched_by_this_change():
    """draftkings and sbr_consensus were never prunable and must stay that way;
    the close is an addition to what SURVIVES, never a widening of what is
    deleted."""
    assert 'PROTECTED_BOOKMAKERS = (ODDS_API_BOOKMAKER, "sbr_consensus")' in SRC
    for tier in ("where_old", "select_superseded", "select_keepers"):
        assert "{prunable}" in _tier(tier), (
            f"{tier} lost the protected-bookmaker predicate")


def test_the_cost_is_recorded_as_a_measurement_not_a_guess():
    """§1b: never estimate what you can measure. The retention decision was
    made on a real row count, and the next person changing it needs the same
    number rather than the old ~2.7 GB/month comment that counted one table."""
    assert "297,975" in SRC and "105,105" in SRC, (
        "the measured daily row counts behind this decision are gone")
    assert "+6 MB/day" in SRC
