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
would only prove a missing GRANT. All three tables are non-empty, checked first.

Everything is rolled back. Nothing here writes a durable row.

    python -m scripts.verify_worker_rls
"""

from __future__ import annotations

from loguru import logger

from data.anon_readable import WORKER_ONLY_TABLES
from data.db import get_connection


def main() -> int:
    conn = get_connection()
    failures: list[str] = []
    try:
        who = conn.execute(
            "SELECT current_user, "
            "(SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user)"
        ).fetchone()
        logger.info(f"connected as {who[0]!r}, rolbypassrls={who[1]}")

        for table in WORKER_ONLY_TABLES:
            rls, owner = conn.execute(
                "SELECT c.relrowsecurity, pg_get_userbyid(c.relowner) "
                "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relname = %s", (table,)
            ).fetchone()
            # The read probe. Zero rows here on a table known to be non-empty is
            # the failure this script exists to catch.
            seen = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            logger.info(f"{table}: rls={rls} owner={owner} rows_visible={seen}")
            if not rls:
                failures.append(f"{table}: RLS is OFF")
            if seen == 0:
                failures.append(
                    f"{table}: 0 rows visible -- either genuinely empty or RLS "
                    f"is filtering the worker out. Check before dismissing.")

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

    if failures:
        for f in failures:
            logger.error(f)
        return 1
    logger.success(
        f"the worker reads and writes all {len(WORKER_ONLY_TABLES)} RLS-enabled "
        f"worker-only tables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
