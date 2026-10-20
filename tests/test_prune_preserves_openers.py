"""
Regression tests for opening-line retention in data/prune_odds.py.

Why this exists: before 2026-08-25 the pruner destroyed opening lines. Tier 1
deleted every non-protected row for games older than PRUNE_NON_DK_KEEP_DAYS,
and tier 2 kept only the NEWEST snapshot per proposition — so a book's opener
survived at most two days.

That mattered the moment we found the NCAAF cross-book opener signal, which is
built entirely on comparing two books' OPENING numbers. It also silently
removed the ability to measure CLV from the open for every other sport.

The fix keeps ONE extra row per (proposition, book) — the earliest snapshot —
while still pruning the ~21 intraday snapshots in between. These tests pin
both halves of that: openers survive, redundant snapshots still go.

The keep rules run on SQLite here (tests/test_prune_bounded's stand-in), so
these check what survives, not only the SQL text.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.prune_odds import (  # noqa: E402
    PROTECTED_BOOKMAKERS, PROTECTED_BOOKMAKER_PREFIXES, _unprotected,
)
from tests.test_prune_bounded import StandIn  # noqa: E402
from tests.test_prune_keeps_the_close import DOOMED, _prune, _quotes  # noqa: E402


# ── the opener guard itself ───────────────────────────────────────────────────

def test_openers_subquery_exists_and_orders_ascending():
    """
    The opener must be ranked with ORDER BY snapshot_at ASC. Ordering DESC
    here would silently 'protect' the newest row instead of the oldest, which
    looks identical in row counts and destroys every opener.
    """
    assert "ORDER BY snapshot_at ASC" in DOOMED, (
        "openers must be the EARLIEST snapshot per proposition")
    assert "rn_first = 1" in DOOMED


def test_both_delete_tiers_exclude_openers():
    """
    Tier 1 (old games) and tier 2 (superseded) must BOTH exempt openers.
    Exempting only one still loses them — tier 1 alone would delete the opener
    of every settled game.
    """
    conn = StandIn()
    _quotes(conn, "OLD", "2026-10-10", [(1, "in_play", 1), (2, "in_play", 2)])
    _quotes(conn, "WIN", "2026-10-19", [(11, "in_play", 1), (12, "in_play", 2),
                                        (13, "in_play", 3)])
    _prune(conn)
    assert 1 in conn.ids("odds"), "tier 1 deletes openers for settled games"
    assert 11 in conn.ids("odds"), "tier 2 deletes openers inside the retention window"


def test_tier2_still_prunes_intermediate_snapshots():
    """
    The storage win must survive. Tier 2 keeps newest + opener and drops the
    rest — without that the pruner becomes a no-op and non-DK history grows
    unbounded again.
    """
    assert "rn_newest > 1" in DOOMED
    assert "ORDER BY snapshot_at DESC" in DOOMED
    conn = StandIn()
    _quotes(conn, "WIN", "2026-10-19", [(i, "open", i) for i in range(1, 7)])
    _prune(conn)
    assert conn.ids("odds") == {1, 6}


# ── protection predicate ──────────────────────────────────────────────────────

def test_scoring_book_and_synthetic_lines_are_protected():
    assert "draftkings" in PROTECTED_BOOKMAKERS
    assert "sbr_consensus" in PROTECTED_BOOKMAKERS


def test_cfbd_archive_prefix_is_protected():
    """
    The 2026-08-22 incident: the first NCAAF lines backfill (47,204 rows) was
    wiped by the next worker run because these labels were not protected. They
    are single-snapshot rows on finished games — exactly what tier 1 deletes.
    """
    assert "cfbd" in PROTECTED_BOOKMAKER_PREFIXES
    params: dict = {"protected": PROTECTED_BOOKMAKERS}
    sql = _unprotected(params)
    assert "NOT LIKE" in sql
    assert any(v == "cfbd%" for v in params.values()), (
        "cfbd prefix pattern was not added to the query params")


def test_unprotected_predicate_covers_every_prefix():
    """One NOT LIKE clause per protected prefix, params kept in sync."""
    params: dict = {"protected": PROTECTED_BOOKMAKERS}
    sql = _unprotected(params)
    assert sql.count("NOT LIKE") == len(PROTECTED_BOOKMAKER_PREFIXES)
    for i in range(len(PROTECTED_BOOKMAKER_PREFIXES)):
        assert f"protected_pfx_{i}" in params


def test_line_shop_books_are_not_protected_wholesale():
    """
    Bovada and Pinnacle were added for the opener work. They must NOT be
    blanket-protected — their openers are kept by the opener guard, and
    protecting them outright would retain every intraday snapshot and undo the
    retention policy.
    """
    for book in ("bovada", "pinnacle", "fanduel", "betmgm"):
        assert book not in PROTECTED_BOOKMAKERS
        assert not any(book.startswith(p) for p in PROTECTED_BOOKMAKER_PREFIXES)


# ── paid history must survive the pruner ─────────────────────────────────────

def test_historical_backfill_rows_are_protected_in_odds():
    """
    The MLB backfill of 2026-09-01 (three declared jobs, ~31k credits, two
    snapshots a day) was thinned to ONE row per proposition per non-DK book by
    the next morning's prune: measured 2026-09-07, pinnacle/bovada/fanduel at
    exactly 1.00 rows per (game, market) for May 2024 games. The pruner
    protects DK by name and the CFBD archive by prefix, and nothing else. Rows
    the historical endpoint wrote are stamped with a source, and that source
    is protected -- in `odds`, the table that has the column.
    """
    from data.ingestors.odds_ingestor import HISTORICAL_ODDS_SOURCE
    params = {}
    pred = _unprotected(params, table="odds")
    assert "source IS NULL" in pred, "live rows (NULL source) must stay prunable"
    assert "protected_sources" in pred
    assert HISTORICAL_ODDS_SOURCE in params["protected_sources"]


def test_prop_table_has_no_source_column_so_no_source_clause():
    """player_prop_odds carries no `source` column (checked against the live
    schema 2026-09-07); a clause referencing it would abort every prop prune."""
    params = {}
    pred = _unprotected(params, table="player_prop_odds")
    assert "source" not in pred
