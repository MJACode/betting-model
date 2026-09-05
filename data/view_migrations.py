"""
Apply idempotent view migrations from the running worker.

WHY THIS EXISTS. The Supabase MCP available to development sessions is
read-only, and setup_database() only runs at first-time setup — so a change to
a VIEW has no path into production without someone opening the SQL editor by
hand. The same gap is why tracking/run_ledger.py creates its own table with
CREATE TABLE IF NOT EXISTS on every start.

This closes it for views: the migrations listed below are written to be
idempotent (each checks whether it has already been applied and skips), so the
pipeline can run them on every pass and the change lands on the first run after
a merge.

Deliberate constraints:

  * ONLY files named here are executed, never a directory glob. A migrations
    directory is an archive of history — replaying all of it on every pass
    would be both slow and dangerous. Removing a file from this list once it is
    applied everywhere is the intended lifecycle.
  * Every migration must be safe to run repeatedly. A file that raises on a
    second run would red the pipeline forever.
  * Every migration must be a SINGLE statement -- in practice a DO $$...$$
    block. See the comment at the execute() call for why.
  * Failures are logged and swallowed. A view refinement must never take down
    settlement or scoring — the same rule run_ledger follows.
"""
from __future__ import annotations
from pathlib import Path

from loguru import logger

from data.db import get_connection

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

# Idempotent view migrations to keep applied. Order matters only if one
# depends on another.
ACTIVE_MIGRATIONS: list[str] = [
    "require_price_for_published_units.sql",
    "units_precision_for_public_record.sql",
    "add_message_id_to_push_sent.sql",
    "add_results_snapshots.sql",
    "add_player_news.sql",
    # 2026-09-02: the record views read the graded matview instead of
    # re-grading 126k picks per read (the Record tab was timing out at 8s).
    # Its daily-view branch was removed on 2026-09-04 -- see below.
    "track_record_reads_graded_matview.sql",
    # 2026-09-04: the published record starts at the official live date, in BOTH
    # views. This must run AFTER track_record_reads_graded_matview, which used to
    # own the daily view and reverted it to the 2026-04-14 window on every pass.
    "live_record_start_views_2026_09_01.sql",
    # 2026-09-05: one row per pick, enforced by a unique index. No-ops (with a
    # NOTICE) until scripts/dedupe_picks.py has cleared the 63 rows a released
    # lock wrote, then creates the index on the next pass.
    "picks_one_row_per_pick.sql",
]


def apply_view_migrations(conn=None) -> int:
    """Run each ACTIVE_MIGRATIONS file. Returns how many applied cleanly.
    Never raises — observability and schema polish must not break the pass."""
    owns = conn is None
    applied = 0
    try:
        conn = conn or get_connection()
    except Exception as exc:                      # no DB — nothing to do
        logger.warning(f"View migrations skipped (no connection): {exc}")
        return 0

    try:
        for name in ACTIVE_MIGRATIONS:
            path = MIGRATIONS_DIR / name
            if not path.exists():
                logger.warning(f"View migration missing on disk: {name}")
                continue
            try:
                # conn.execute, NOT conn.executescript: executescript splits on
                # ";" and would shred a dollar-quoted DO $$...$$ block into
                # fragments at every semicolon in its body. Each migration here
                # must therefore be a SINGLE statement (a DO block), which is
                # also what makes the idempotency check atomic.
                conn.execute(path.read_text(encoding="utf-8"))
                conn.commit()
                applied += 1
                logger.info(f"View migration OK: {name}")
            except Exception as exc:
                # Roll back so one bad migration cannot poison the next.
                try:
                    conn.rollback()
                except Exception:
                    pass
                logger.error(f"View migration FAILED ({name}): {exc}")
    finally:
        if owns:
            try:
                conn.close()
            except Exception:
                pass
    return applied


if __name__ == "__main__":
    n = apply_view_migrations()
    print(f"{n}/{len(ACTIVE_MIGRATIONS)} view migration(s) applied")
