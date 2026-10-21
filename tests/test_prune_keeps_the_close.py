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

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data import prune_odds as po  # noqa: E402
from tests.test_prune_bounded import ODDS_COLS, StandIn  # noqa: E402

SRC = (Path(__file__).parent.parent / "data" / "prune_odds.py").read_text(
    encoding="utf-8")

# The statement prune_table sends, with the protected predicate left as a
# marker so the tests can see where it lands.
DOOMED = po.doomed_sql("odds", ("game_id", "market"), "%(game_day)s", "<<PRUNABLE>>")


def _quotes(conn: StandIn, game: str, day: str, rows) -> None:
    """rows: (odds_id, snapshot_type, hour)."""
    conn.db.execute("INSERT INTO games VALUES (?, 'MLB', ?)", (game, day))
    for oid, stype, hour in rows:
        conn.db.execute(
            f"INSERT INTO odds ({', '.join(ODDS_COLS)}) VALUES "
            f"(?, ?, 'MLB', 'h2h', 'fanduel', ?, ?, -110, 100, NULL, NULL, NULL, "
            f"NULL, NULL, NULL)", (oid, game, stype, f"{day}T{hour:02d}:00:00Z"))


def _prune(conn: StandIn, today: str = "2026-10-20") -> None:
    po.prune_table(conn, "odds", ("game_id", "market"), "%(game_day)s", 2, today,
                   budget=po.Budget(seconds=60, rows=10**9), floor="2026-10-01")


def test_the_close_is_selected_by_the_newest_snapshot():
    assert "ORDER BY snapshot_at DESC" in DOOMED
    assert "rn_last = 1" in DOOMED


def test_the_opener_is_still_selected_by_the_oldest():
    """The 2026-08-25 rule this is layered on top of, not a replacement for."""
    assert "ORDER BY snapshot_at ASC" in DOOMED
    assert "rn_first = 1" in DOOMED


def test_the_close_is_never_an_in_play_price():
    """An in-play row is a different proposition (CLAUDE.md §6). Keeping one as
    'the close' hands every later analysis a price from the third inning.

    The DESC ranking is partitioned BY the pre-game flag, so rn_last = 1 AND
    is_pre is the newest PRE-GAME row — not the newest row that happens to be
    pre-game, which is what an unpartitioned ranking would give.
    """
    assert f"PARTITION BY game_id, market, bookmaker, {po._IS_PRE}" in DOOMED, (
        "the DESC ranking is not scoped to pre-game rows, so a proposition "
        "whose newest row is in-play keeps nothing pre-game at all")
    assert "is_pre AND rn_last = 1" in DOOMED
    assert "snapshot_type IS NULL" in po._IS_PRE, (
        "NULL snapshot_type must count as pre-game — every reader treats it "
        "that way, and excluding it would keep nothing for older rows")
    conn = StandIn()
    _quotes(conn, "G", "2026-10-10", [(1, "open", 1), (2, "open", 2), (3, "open", 3),
                                      (4, "in_play", 4), (5, "in_play", 5)])
    _prune(conn)
    assert conn.ids("odds") == {1, 3}, "the close must be the newest PRE-GAME row"


def test_both_delete_tiers_spare_the_keep_set():
    """Tier 1 (settled games past the window) and tier 2 (superseded rows
    inside it) both delete, so both must spare the opener and the close.
    Sparing it in one tier only means the other deletes it a day later."""
    assert "WHERE NOT (rn_first = 1 OR (is_pre AND rn_last = 1))" in DOOMED
    conn = StandIn()
    _quotes(conn, "OLD", "2026-10-10", [(1, "open", 1), (2, "open", 2), (3, "open", 3),
                                        (4, "in_play", 4)])
    _quotes(conn, "WIN", "2026-10-19", [(11, "open", 1), (12, "open", 2), (13, "open", 3),
                                        (14, "in_play", 4)])
    _prune(conn)
    assert {1, 3} <= conn.ids("odds"), "tier 1 deleted the opener or the close"
    assert {11, 13} <= conn.ids("odds"), "tier 2 deleted the opener or the close"


def test_each_statement_reads_its_proposition_once_with_no_anti_join():
    """PERFORMANCE IS CORRECTNESS HERE. A version that added a SECOND `NOT IN`
    beside the opener's stopped completing (`canceling statement due to
    statement timeout`), and the whole-table version later timed out every
    day. A pruner that times out prunes nothing, and the growth it exists to
    bound is silent. Every keep rule rides on ONE read of one proposition.
    """
    assert DOOMED.count("FROM odds") == 1
    assert "NOT IN (" not in DOOMED
    delete = po.delete_sql("odds", ("game_id", "market"), "%(game_day)s", "<<PRUNABLE>>")
    assert delete.count("FROM odds") == 2          # the DELETE and its one read
    # The window is computed once and the DELETE looks those ids up by primary
    # key. A proposition predicate on the DELETE makes Postgres re-run the
    # scan once per doomed id (2026-10-21: 4,819 ids, 8.5 s, and the form
    # with the window inside that loop was cancelled at statement_timeout).
    assert "AS MATERIALIZED" in delete
    tail = delete.split("DELETE FROM", 1)[1]
    assert "game_id" not in tail
    assert tail.strip().startswith("odds WHERE odds_id IN (SELECT odds_id FROM doomed)")


def test_the_protected_books_are_untouched_by_this_change():
    """draftkings and sbr_consensus were never prunable and must stay that way;
    the close is an addition to what SURVIVES, never a widening of what is
    deleted."""
    assert 'PROTECTED_BOOKMAKERS = (ODDS_API_BOOKMAKER, "sbr_consensus")' in SRC
    assert "AND <<PRUNABLE>>" in DOOMED, (
        "the statement lost the protected-bookmaker predicate")


def test_the_cost_is_recorded_as_a_measurement_not_a_guess():
    """§1b: never estimate what you can measure. The retention decision was
    made on a real row count, and the next person changing it needs the same
    number rather than the old ~2.7 GB/month comment that counted one table."""
    assert "297,975" in SRC and "105,105" in SRC, (
        "the measured daily row counts behind this decision are gone")
    assert "+6 MB/day" in SRC
