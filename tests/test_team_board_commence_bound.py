"""MLB 2026 team-board refresh must not walk the in-play tail.

Daily runs 873cb1fe2e1e487d975ae3367f219a3f (2026-09-29) and
fd57b13575f04d63b219134d62f434dc (2026-09-30):

    failed_steps = refresh_team_board,health_check

team_stats_board_cache MLB 2026 stayed at 2026-09-28 10:04:47+00. The
2026-09-28 index probe still filters
`snapshot_at::timestamptz <= commence_time::timestamptz`. Both columns are
text, so that cast is not an index condition: the backward scan of
idx_odds_book_snap starts at the newest in-play row. DraftKings MLB 2026
spreads are 406,606 in_play rows. Putting the cutoff on the text column
(`snapshot_at <` the next UTC second, Z-formatted) made the same scan an
index condition. EXPLAIN ANALYZE of every finished MLB 2026 game, both
markets, five named books: 11,626.902 ms, against a 2min statement_timeout.
"""

from __future__ import annotations

import io
from pathlib import Path

ROOT = Path(__file__).parent.parent
MIG = io.open(
    ROOT / "data" / "migrations" / "team_stats_board_commence_bound_2026_09_30.sql",
    encoding="utf-8",
).read()
BODY = MIG[MIG.index("CREATE OR REPLACE FUNCTION"):]


def test_the_bound_is_on_the_worker_migration_list_after_the_line_probe():
    from data.view_migrations import ACTIVE_MIGRATIONS

    name = "team_stats_board_commence_bound_2026_09_30.sql"
    earlier = "team_stats_board_line_probe_2026_09_28.sql"
    assert name in ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS.index(earlier) < ACTIVE_MIGRATIONS.index(name)


def test_the_commence_cutoff_is_an_index_bound_not_a_timestamptz_or():
    """The three-way OR (commence IS NULL OR snapshot_at IS NULL OR cast)
    was planned as a Filter, so the scan read the in-play tail. The bounded
    arm is a plain `snapshot_at <` comparison, which idx_odds_book_snap can
    apply. The cast remains only as a residual."""
    assert "team_board_commence_bound" in BODY
    assert "team_board_line_probe" in BODY
    assert BODY.count("oo.snapshot_at < to_char(") == 2
    assert "interval '1 second'" in BODY
    assert "AT TIME ZONE 'UTC'" in BODY
    assert 'YYYY-MM-DD"T"HH24:MI:SS"Z"' in BODY
    assert "oo.snapshot_at::timestamptz <= c.commence_time::timestamptz" in BODY
    assert "OR oo.snapshot_at IS NULL" not in BODY
    assert "OR oo.snapshot_at::timestamptz" not in BODY
    assert "c.commence_time IS NOT NULL" in BODY
    assert "c.commence_time IS NULL" in BODY
    assert "ORDER BY oo.snapshot_at DESC NULLS FIRST" in BODY
    assert "LIMIT 1" in BODY


def test_named_books_and_the_cfbd_fallback_are_unchanged():
    for book in (
        "draftkings",
        "cfbd_draftkings",
        "cfbd_bovada",
        "cfbd_consensus",
        "cfbd_teamrankings",
    ):
        assert book in BODY
    assert "ORDER BY b.pri" in BODY
    assert "LIKE 'cfbd\\_%'" in BODY
    assert "named.ok IS NOT TRUE" in BODY
    assert "snapshot_type IS DISTINCT FROM 'in_play'" in BODY


def test_the_migration_is_one_statement_and_revokes_the_compute_function():
    stripped = "\n".join(
        ln for ln in MIG.splitlines() if not ln.strip().startswith("--")
    ).strip()
    assert stripped.startswith("DO $mig$")
    assert stripped.endswith("$mig$;")
    assert "REVOKE ALL ON FUNCTION public.team_stats_board_compute(text, integer)" in MIG
    assert "FROM PUBLIC, anon, authenticated" in MIG


def test_a_second_pass_is_a_no_op_and_the_line_probe_migration_stays_one():
    assert "pg_get_functiondef(p.oid) LIKE '%team_board_commence_bound%'" in MIG
    assert "RETURN;" in MIG
    # The 09-28 file no-ops when the live body still names its marker.
    assert "team_board_line_probe" in BODY
