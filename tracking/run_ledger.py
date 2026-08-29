"""
Pipeline run ledger — records that a pipeline invocation started and finished.

Why this exists: until 2026-08-27 nothing recorded that a refresh pass had run.
A NameError in the WNBA prop scorer aborted every hourly pass at step 9 of 24
for three days, and the only evidence was an ABSENCE — missing opening_signals,
missing Discord posts, missing settlements. The once-a-day health check stayed
green the whole time, because the daily 6am pipeline (which continues past step
failures) was unaffected.

A ledger turns that absence into a positive record. Two health checks read it:
  refresh_pass_completion — a finished pass within the expected cadence
  refresh_pass_steps      — which steps failed, and whether persistently

Design notes:
  * run_id is a client-generated uuid hex, not a serial, so the shell can
    round-trip it without depending on lastrowid semantics.
  * A pass that starts and never finishes leaves finished_at NULL — that is how
    a hang, an OOM or a killed worker becomes visible rather than silent.
  * EVERY function swallows its own exceptions and the CLI always exits 0.
    Observability must never be able to break the thing it observes.

CLI (used by scripts/refresh_pass.sh):
    RUN_ID="$(python -m tracking.run_ledger start --kind hourly)"
    python -m tracking.run_ledger finish --run-id "$RUN_ID" \
        --steps-total 24 --failed "wnba-prop-scoring golf-odds"
"""

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.db import get_connection


# CREATE TABLE IF NOT EXISTS, run once per pass. The Supabase MCP is read-only
# and setup_database() only runs during first-time setup, so without this the
# table would need a manual migration before any of this works. Idempotent and
# cheap; swallowed like every other ledger failure.
_DDL = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id       TEXT PRIMARY KEY,
    run_kind     TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    steps_total  INTEGER,
    steps_failed INTEGER,
    failed_steps TEXT,
    ok           BOOLEAN
)
"""


# Postgres-only, and the reason this exists: because the table is created HERE
# rather than by a migration, it was born without the RLS that
# data/supabase_schema.sql has always specified for it -- so in production anon
# held SELECT + INSERT + UPDATE + DELETE on the ledger that records whether the
# pipeline ran at all (found 2026-08-29; ERROR-level rls_disabled_in_public).
# Deleting a row here would blind refresh_pass_completion / refresh_pass_steps,
# the only checks that can see a silent outage.
#
# RLS ON with NO policy is the intended state (pipeline_log and ~25 other
# pipeline-internal tables are the same): the pipeline writes as the table owner
# via DATABASE_URL and bypasses RLS, and nothing in the app reads this table.
# REVOKE names the roles, not PUBLIC -- Supabase's default privileges grant
# anon/authenticated by name and a PUBLIC-only revoke does not touch them.
_LOCKDOWN = (
    "ALTER TABLE pipeline_runs ENABLE ROW LEVEL SECURITY",
    "REVOKE ALL ON pipeline_runs FROM anon, authenticated",
)


def _ensure_table(conn) -> None:
    try:
        conn.execute(_DDL)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started "
                     "ON pipeline_runs(started_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_kind "
                     "ON pipeline_runs(run_kind, started_at)")
        conn.commit()
    except Exception as exc:
        logger.debug(f"run_ledger: ensure table skipped ({exc})")

    # Separate transaction per statement: these are no-ops on SQLite (no RLS,
    # no anon role) and on a already-locked-down table, and a failure must not
    # roll back the CREATE above or leave the connection in an aborted state.
    for stmt in _LOCKDOWN:
        try:
            conn.execute(stmt)
            conn.commit()
        except Exception as exc:
            # Postgres aborts the transaction on a failed statement, so the
            # rollback is what keeps the NEXT ledger write usable. It is itself
            # best-effort: a connection shim without rollback (the tests use
            # one) must not turn observability into an outage.
            try:
                conn.rollback()
            except Exception:                        # noqa: BLE001
                pass
            logger.debug(f"run_ledger: lockdown skipped ({exc})")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _abort_orphans(conn) -> int:
    """Close out runs that started but never finished, before recording a new one.

    A row with finished_at NULL means the process that owned it never called
    finish_run. Until now that row stayed open forever, and every deploy creates
    one: Railway replaces the container mid-pass, the worker dies between the
    INSERT and the UPDATE, and the row is orphaned. refresh_pass_completion
    counts unfinished runs older than 2h as "stuck", so each deploy permanently
    added a false hang to a CRIT check -- observed live after two deploys on
    2026-08-27.

    Closing them HERE is safe and precise, because a new pass starting proves
    the previous one's process is gone: the scheduler runs refresh passes with
    max_instances=1, so it never launches an overlapping pass. Anything still
    open at this moment is dead, not running.

    Hang detection is preserved rather than masked. These are recorded as
    ok = FALSE with failed_steps = 'aborted', so a worker dying mid-pass stays
    visible and countable -- it is simply no longer indistinguishable from a
    pass that is hanging right now. The stuck check keeps its meaning too: after
    this, an unfinished row older than 2h can only be the CURRENTLY running
    pass, which is exactly the case that check exists to catch.
    """
    try:
        cur = conn.execute(
            """
            UPDATE pipeline_runs
               SET finished_at  = ?,
                   ok           = FALSE,
                   failed_steps = 'aborted'
             WHERE finished_at IS NULL
            """,
            (_now(),),
        )
        n = getattr(cur, "rowcount", 0) or 0
        if n:
            logger.warning(
                f"run_ledger: closed {n} orphaned run(s) as aborted — the worker "
                f"was replaced or killed mid-pass (usually a deploy)"
            )
        return n
    except Exception as exc:
        # Never block the pass that is starting.
        logger.warning(f"run_ledger: could not close orphaned runs ({exc})")
        return 0


def start_run(run_kind: str) -> str:
    """Record the start of a pipeline run. Returns the run_id (always a string).

    On any DB failure this still returns a usable id so the caller's `finish`
    call is well-formed; the finish simply won't match a row, which the health
    checks treat the same as a missing run.
    """
    run_id = uuid.uuid4().hex
    try:
        conn = get_connection()
        try:
            _ensure_table(conn)
            _abort_orphans(conn)
            conn.execute(
                """
                INSERT INTO pipeline_runs (run_id, run_kind, started_at)
                VALUES (?, ?, ?)
                """,
                (run_id, run_kind, _now()),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:                                  # never break a pass
        logger.warning(f"run_ledger: could not record start ({exc})")
    return run_id


def finish_run(run_id: str, steps_total: int, failed_steps: list[str]) -> None:
    """Record completion. `failed_steps` empty => ok."""
    if not run_id:
        return
    failed = [s for s in failed_steps if s]
    try:
        conn = get_connection()
        try:
            conn.execute(
                """
                UPDATE pipeline_runs
                   SET finished_at = ?, steps_total = ?, steps_failed = ?,
                       failed_steps = ?, ok = ?
                 WHERE run_id = ?
                """,
                (_now(), steps_total, len(failed),
                 ",".join(failed) if failed else None,
                 len(failed) == 0, run_id),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.warning(f"run_ledger: could not record finish ({exc})")


def main() -> int:
    ap = argparse.ArgumentParser(description="Pipeline run ledger")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start")
    s.add_argument("--kind", required=True,
                   choices=["daily", "hourly", "evening", "manual"])

    f = sub.add_parser("finish")
    f.add_argument("--run-id", required=True)
    f.add_argument("--steps-total", type=int, default=0)
    f.add_argument("--failed", default="",
                   help="whitespace- or comma-separated failed step names")

    args = ap.parse_args()
    if args.cmd == "start":
        print(start_run(args.kind))
    else:
        raw = args.failed.replace(",", " ").split()
        finish_run(args.run_id, args.steps_total, raw)
    return 0


if __name__ == "__main__":
    # Always exit 0: the ledger is observability, never a gate.
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:
        logger.warning(f"run_ledger failed: {exc}")
        sys.exit(0)
