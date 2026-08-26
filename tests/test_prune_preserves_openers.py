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

The SQL is Postgres-specific (window functions, %(name)s params, NOT IN
%(tuple)s), so rather than stand up a database these tests assert on the
generated SQL and on the protection predicate, which is where the regression
would actually occur.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.prune_odds import (  # noqa: E402
    PROTECTED_BOOKMAKERS, PROTECTED_BOOKMAKER_PREFIXES, _unprotected,
)

_SOURCE = (Path(__file__).parent.parent / "data" / "prune_odds.py").read_text(
    encoding="utf-8")


# ── the opener guard itself ───────────────────────────────────────────────────

def test_openers_subquery_exists_and_orders_ascending():
    """
    The opener set must be built with ORDER BY snapshot_at ASC. Ordering DESC
    here would silently 'protect' the newest row instead of the oldest, which
    looks identical in row counts and destroys every opener.
    """
    assert "select_openers" in _SOURCE, "opener-protection subquery is gone"
    m = re.search(r"select_openers\s*=\s*f?\"\"\"(.*?)\"\"\"", _SOURCE, re.S)
    assert m, "could not locate the select_openers block"
    block = m.group(1)
    assert "ORDER BY snapshot_at ASC" in block, (
        "openers must be the EARLIEST snapshot per proposition")
    assert "rn_first = 1" in block


def test_both_delete_tiers_exclude_openers():
    """
    Tier 1 (old games) and tier 2 (superseded) must BOTH exempt openers.
    Exempting only one still loses them — tier 1 alone would delete the opener
    of every settled game.
    """
    tier1 = re.search(r"where_old\s*=\s*f\"\"\"(.*?)\"\"\"", _SOURCE, re.S)
    tier2 = re.search(r"select_superseded\s*=\s*f\"\"\"(.*?)\"\"\"", _SOURCE, re.S)
    assert tier1 and tier2
    assert "NOT IN ({select_openers})" in tier1.group(1), (
        "tier 1 deletes openers for settled games")
    assert "NOT IN ({select_openers})" in tier2.group(1), (
        "tier 2 deletes openers inside the retention window")


def test_tier2_still_prunes_intermediate_snapshots():
    """
    The storage win must survive. Tier 2 keeps newest + opener and drops the
    rest, so `rn > 1` must still be there — without it the pruner becomes a
    no-op and non-DK history grows unbounded again.
    """
    tier2 = re.search(r"select_superseded\s*=\s*f\"\"\"(.*?)\"\"\"", _SOURCE, re.S)
    assert "rn > 1" in tier2.group(1)
    assert "ORDER BY snapshot_at DESC" in tier2.group(1)


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
