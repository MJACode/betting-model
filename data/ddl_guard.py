"""data/ddl_guard.py — run schema DDL only when the catalog says it is needed.

WHY THIS EXISTS
Several modules create their own table at write time rather than in a migration
(monitoring/store.py, tracking/run_ledger.py, tracking/live_calibration.py,
models/probability_calibration.py, tracking/job_queue.py,
data/ingestors/dk_direct_feed.py). Each of them re-runs the same block on every
call, on the reasoning that `CREATE TABLE IF NOT EXISTS` and friends are cheap
no-ops. **They are not.** Postgres treats them as real DDL:

  - `CREATE INDEX IF NOT EXISTS` takes a SHARE lock on the table before it
    discovers the index already exists, so it queues behind every writer.
  - `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` takes ACCESS EXCLUSIVE whether
    or not RLS is already on, so it queues behind every reader AND writer.
  - **Every one of them fires Supabase's `pgrst_ddl_watch` event trigger**, and
    PostgREST answers **503 to every request** while it rebuilds its schema
    cache. The rebuild is one very large catalog query; under load it hits the
    8s `authenticator` statement timeout and the cache never lands.

MEASURED ON PRODUCTION, 2026-09-01 (pg_stat_statements, not an estimate):

    CREATE INDEX IF NOT EXISTS idx_api_call_ts ON api_call_log(ts)
        1,925 calls   mean 15,082 ms   29,032 s total
    ALTER TABLE api_call_log ENABLE ROW LEVEL SECURITY
        1,676 calls   mean  7,797 ms   13,067 s total

11.6 hours of database time spent re-creating a table that already existed, and
~3,600 forced PostgREST schema-cache reloads — 232 of which timed out. That is
why the Stats tab showed "Connection error": every leaderboard RPC came back
503/500 while the cache was down.

The loop is self-reinforcing. monitoring/probe.py's writer drops its connection
on ANY failure and re-runs the ensure block on reconnect, so the busier the
database gets, the more DDL it fires at it.

THE GUARD
`schema_is_current()` is one indexed catalog SELECT (sub-millisecond) that
answers "would every statement in this block be a no-op?". It **fails closed
towards the old behaviour**: any doubt — SQLite, a shim connection in the
tests, a role that cannot read the catalog, a missing index — returns False and
the caller runs its DDL exactly as it did before. It can therefore only ever
remove redundant work, never skip work that is genuinely needed.
"""

from __future__ import annotations

# Privileges a default-privileges grant hands anon/authenticated, i.e. what a
# `REVOKE ALL` is there to take away. has_table_privilege accepts a comma list
# and returns true if ANY of them is held.
_PRIVS_PG17 = "SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN"
_PRIVS_LEGACY = "SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER"

_SQL = """
SELECT
    c.relrowsecurity,
    (SELECT coalesce(array_agg(a.attname::text), '{}')
       FROM pg_attribute a
      WHERE a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped),
    (SELECT coalesce(array_agg(ci.relname::text), '{}')
       FROM pg_index i JOIN pg_class ci ON ci.oid = i.indexrelid
      WHERE i.indrelid = c.oid),
    (SELECT count(*) FROM pg_roles r
      WHERE r.rolname = ANY(%s)
        AND has_table_privilege(r.oid, c.oid, %s))
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relname = %s AND c.relkind IN ('r', 'p')
"""



def _fetchone(conn, sql: str, params):
    """One row, from either connection shape this repo uses.

    data/db.py's DBConnection exposes sqlite-style `conn.execute(...)`, but the
    standalone scripts hold a raw psycopg2 connection, which does not. The
    query uses %s placeholders precisely so it is valid for both -- db.py's
    adapter only rewrites `?` and `:name` and passes %s straight through.
    """
    try:
        return conn.execute(sql, params).fetchone()
    except AttributeError:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()


def schema_is_current(
    conn,
    table: str,
    *,
    columns: tuple[str, ...] = (),
    indexes: tuple[str, ...] = (),
    rls: bool = False,
    revoked_from: tuple[str, ...] = (),
) -> bool:
    """True when `table` already matches everything the caller would create.

    Checks, in one catalog query: the table exists; it has every name in
    `columns`; it has every index in `indexes`; RLS is on if `rls`; and none of
    `revoked_from` holds any privilege on it.

    Returns False on ANY doubt — a missing piece, a non-Postgres connection, or
    a catalog read that raises — so the caller falls back to running its DDL.
    """
    for privs in (_PRIVS_PG17, _PRIVS_LEGACY):
        try:
            row = _fetchone(conn, _SQL, (list(revoked_from), privs, table))
            break
        except Exception:                                   # noqa: BLE001
            # A failed statement poisons the Postgres transaction, so the
            # rollback is what keeps the caller's next statement usable. Retry
            # once without MAINTAIN, which only exists from Postgres 17.
            try:
                conn.rollback()
            except Exception:                               # noqa: BLE001
                pass
    else:
        return False

    if not row:
        return False                                        # table not there yet

    try:
        rls_on, have_cols, have_idx, granted = row[0], row[1], row[2], row[3]
        if rls and not rls_on:
            return False
        if revoked_from and int(granted) > 0:
            return False
        have_cols = set(have_cols or ())
        have_idx = set(have_idx or ())
        return (set(columns) <= have_cols) and (set(indexes) <= have_idx)
    except Exception:                                       # noqa: BLE001
        return False
