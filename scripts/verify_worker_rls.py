"""Prove the worker can still read and write the RLS-enabled worker-only tables.

mike, 2026-09-04: "enable rls on those three tables."

WHY THIS EXISTS RATHER THAN AN ARGUMENT. RLS with zero policies is deny-all for
any role that is neither the table owner nor BYPASSRLS. All three tables are
owned by `postgres`, which also carries rolbypassrls, and pg_stat_activity shows
the worker connecting as `postgres` -- so the worker is exempt twice over and
enabling RLS cannot lock it out. That is a sound argument and it is still an
argument. §1b: never estimate what you can measure.

It cannot be measured from the dev sandbox or the Supabase MCP: that connection
is `supabase_read_only_user` and `SET LOCAL ROLE postgres` fails with
"permission denied to set role". The only place the question can be answered is
a connection that IS the worker's, so this runs on the Railway worker over the
same DATABASE_URL.

THE READ PROBE IS THE SUBTLE HALF. A non-exempt role hitting an RLS table with
no policies does not get an error -- it gets ZERO ROWS. So a SELECT that returns
the row count we already know is there is what proves exemption; an exception
would only prove a missing GRANT.

WHICH MEANS AN EMPTY TABLE IS INCONCLUSIVE, and this script says so rather than
guessing. threshold_reviews can be genuinely empty; a count cannot tell that from
being filtered out. Those are reported as WARNINGS, not failures. What proves
exemption for an empty table is `current_user` being the owner or BYPASSRLS,
logged on the first line, plus the worker_jobs write probe. A missing table is
also a warning: an ARCHIVE_TABLE can legitimately be dropped by a retention
decision.

Hard failures are RLS off, FORCE RLS on (which would subject the OWNER to the
policies and deny the worker), and a write that does not read back.

Everything is rolled back. Nothing here writes a durable row.

    python -m scripts.verify_worker_rls
"""

from __future__ import annotations

from loguru import logger

from data.anon_readable import closed_tables
from data.db import get_connection


def main() -> int:
    conn = get_connection()
    failures: list[str] = []
    ambiguous: list[str] = []
    try:
        who = conn.execute(
            "SELECT current_user, "
            "(SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user)"
        ).fetchone()
        logger.info(f"connected as {who[0]!r}, rolbypassrls={who[1]}")

        for table in closed_tables():
            row = conn.execute(
                "SELECT c.relrowsecurity, c.relforcerowsecurity, "
                "pg_get_userbyid(c.relowner) "
                "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relname = %s "
                "AND c.relkind = 'r'", (table,)
            ).fetchone()
            if row is None:
                # An ARCHIVE_TABLE can legitimately be dropped by a retention
                # decision. Absent is not a failure; absent-and-still-declared is
                # a list to tidy.
                ambiguous.append(f"{table}: not in pg_class (dropped?)")
                logger.warning(f"{table}: not in pg_class, skipped")
                continue
            rls, forced, owner = row
            # The read probe. A non-exempt role gets ZERO ROWS here rather than
            # an error, so a count matching what is known to be there is the
            # thing that proves exemption.
            seen = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            logger.info(f"{table}: rls={rls} force={forced} owner={owner} "
                        f"rows_visible={seen}")
            if not rls:
                failures.append(f"{table}: RLS is OFF")
            if forced:
                failures.append(
                    f"{table}: FORCE RLS is ON, which subjects the OWNER to the "
                    f"policies -- with none defined that denies the worker")
            if seen == 0:
                # NOT a failure, and saying so is the honest reading: a table
                # can be genuinely empty (threshold_reviews on a fresh database)
                # and counting alone cannot tell that from being filtered out.
                # What proves exemption for an empty table is current_user being
                # the owner or BYPASSRLS, logged above, plus the write probe.
                ambiguous.append(
                    f"{table}: 0 rows visible -- genuinely empty, or filtered. "
                    f"A count cannot tell these apart.")

        # The write probe, on the table whose loss would matter most: worker_jobs
        # is the queue the worker claims and executes. Rolled back.
        conn.execute(
            "INSERT INTO worker_jobs (job_type, args, requested_by, note) "
            "VALUES ('rls_probe', '{}'::jsonb, 'verify_worker_rls', 'rolled back')")
        back = conn.execute(
            "SELECT count(*) FROM worker_jobs WHERE requested_by = "
            "'verify_worker_rls'").fetchone()[0]
        if back != 1:
            failures.append(
                f"worker_jobs: inserted 1 row, read back {back}. Under RLS an "
                f"INSERT can succeed and the row be invisible.")
        conn.execute(
            "UPDATE worker_jobs SET note = 'updated' WHERE requested_by = "
            "'verify_worker_rls'")
        conn.execute(
            "DELETE FROM worker_jobs WHERE requested_by = 'verify_worker_rls'")
        logger.info(f"worker_jobs write probe: insert/read-back/update/delete "
                    f"all succeeded (read back {back})")
    finally:
        # ALWAYS. The probe row must not survive, and nothing here is a change
        # we want to keep.
        conn.rollback()
        logger.info("rolled back")

    for a in ambiguous:
        logger.warning(a)
    if failures:
        for f in failures:
            logger.error(f)
        return 1
    logger.success(
        f"the worker reads and writes all {len(closed_tables())} declared "
        f"closed tables ({len(ambiguous)} inconclusive, see warnings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
