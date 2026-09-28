"""NCAAF 2026 team-board refresh must not seq-scan odds.

Daily run 51e965f8023c4b0e86e03fe075af1f9c, 2026-09-28 10:15:00Z:

    team board NCAAF 2026 failed: canceling statement due to statement timeout
    CONTEXT: SQL function "team_stats_board_compute" statement 1

EXPLAIN of the live `picked` CTE was a parallel seq scan of `odds` (cost
1,122,366) because `bookmaker = 'draftkings' OR bookmaker LIKE 'cfbd\\_%'`
cannot use idx_odds_book_snap. The replacement probes that index per game,
LIMIT 1. Measured the same day: 25.7s for NCAAF 2026 versus the 120s cap.
A 25-game sample against the old DISTINCT ON was 50 lines, 0 mismatches.
"""

from __future__ import annotations

import io
from pathlib import Path

ROOT = Path(__file__).parent.parent
MIG = io.open(
    ROOT / "data" / "migrations" / "team_stats_board_line_probe_2026_09_28.sql",
    encoding="utf-8",
).read()
# The function body only. The header names the seq scan this file removes.
BODY = MIG[MIG.index("CREATE OR REPLACE FUNCTION"):]


def test_the_probe_is_on_the_worker_migration_list():
    from data.view_migrations import ACTIVE_MIGRATIONS

    name = "team_stats_board_line_probe_2026_09_28.sql"
    assert name in ACTIVE_MIGRATIONS


def test_the_closing_line_is_an_index_probe_not_a_season_sort():
    assert "team_board_line_probe" in BODY
    assert "LIMIT 1" in BODY
    assert "ORDER BY b.pri" in BODY
    assert "ORDER BY oo.snapshot_at DESC NULLS FIRST" in BODY
    assert "snapshot_at::timestamptz <= c.commence_time::timestamptz" in BODY
    assert "DISTINCT ON (o.game_id, o.market)" not in BODY
    assert "OR o.bookmaker LIKE" not in BODY
    assert "OR oo.bookmaker LIKE" not in BODY


def test_named_books_keep_the_old_priority_and_other_cfbd_books_still_qualify():
    for book in (
        "draftkings",
        "cfbd_draftkings",
        "cfbd_bovada",
        "cfbd_consensus",
        "cfbd_teamrankings",
    ):
        assert book in BODY
    assert "LIKE 'cfbd\\_%'" in BODY
    assert "named.ok IS NOT TRUE" in BODY


def test_the_migration_is_one_statement_and_revokes_the_compute_function():
    stripped = "\n".join(
        ln for ln in MIG.splitlines() if not ln.strip().startswith("--")
    ).strip()
    assert stripped.startswith("DO $mig$")
    assert stripped.endswith("$mig$;")
    assert "REVOKE ALL ON FUNCTION public.team_stats_board_compute(text, integer)" in BODY or \
        "REVOKE ALL ON FUNCTION public.team_stats_board_compute(text, integer)" in MIG
    assert "FROM PUBLIC, anon, authenticated" in MIG


def test_a_second_pass_is_a_no_op():
    assert "pg_get_functiondef(p.oid) LIKE '%team_board_line_probe%'" in MIG
    assert "RETURN;" in MIG
