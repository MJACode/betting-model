"""Watch an online table rewrite (pg_repack) and cancel it from SQL if disk crosses a line.

Used for the props table on 2026-11-18 (docs/data_archive.md, "Getting the space back").
Every 30 s it logs: database + write-ahead log size, the table's storage file, heap and
index size, pg_repack's copy and log tables, app errors and failed app reads in the last
5 minutes, and the rewrite's own connections.

Abort rule: database + WAL above --abort-gib while the rewrite is connected -> cancel its
running statement (or end its working connection if it is between statements). pg_repack
then drops its trigger and copy tables itself; that was rehearsed twice on a test table.
Never abort by redeploying or deleting the helper service: that kills the client before it
can clean up.

Supavisor (the 5432 pooler) rewrites application_name, so the rewrite's connections are
found by what they run. A query that mentions pg_stat_activity is skipped, or this
watcher would find itself.

Never writes a row. Usage:
    python -m scripts.pg_repack_guard --table player_prop_odds
"""
from __future__ import annotations

import argparse
import time

import psycopg2

from scripts._envfile import database_url

GIB = 1024 ** 3

REPACK = r"""SELECT pid, state, coalesce(wait_event_type||':'||wait_event,''),
       extract(epoch from now()-coalesce(query_start, backend_start))::int,
       left(regexp_replace(query, '\s+', ' ', 'g'), 100)
FROM pg_stat_activity
WHERE pid <> pg_backend_pid() AND query NOT ILIKE '%%pg_stat_activity%%'
  AND (query ILIKE '%%repack%%' OR query ILIKE '%%virtualxid%%'
       OR query ILIKE 'LOCK TABLE%%' || %(t)s || '%%ACCESS SHARE%%')
ORDER BY backend_start"""

SIZES = """SELECT pg_database_size(current_database()),
  (SELECT sum(size) FROM pg_ls_waldir()),
  (SELECT relfilenode FROM pg_class WHERE oid=('public.'||%(t)s)::regclass),
  pg_relation_size(('public.'||%(t)s)::regclass),
  pg_indexes_size(('public.'||%(t)s)::regclass),
  (SELECT coalesce(string_agg(c.relname||'='||round(pg_total_relation_size(c.oid)/1073741824.0,2)::text||'G', ' '), '-')
     FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
     WHERE n.nspname='repack' AND c.relkind='r'),
  (SELECT count(*) FROM app_errors WHERE received_at > now() - interval '5 minutes'),
  (SELECT count(*) FROM app_timings WHERE received_at > now() - interval '5 minutes'
       AND (status >= 400 OR status = 0))"""


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def connect():
    conn = psycopg2.connect(database_url(), keepalives=1, keepalives_idle=30,
                            keepalives_interval=10, keepalives_count=6)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SET statement_timeout = '20s'")
    return conn, cur


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", required=True, help="table name in schema public")
    ap.add_argument("--abort-gib", type=float, required=True,
                    help="cancel above this database + WAL size (GiB); set it under the disk's auto-grow line")
    ap.add_argument("--polls", type=int, default=0, help="stop after N polls (0 = until done)")
    ap.add_argument("--interval", type=int, default=30)
    ap.add_argument("--max-hours", type=float, default=4.0)
    args = ap.parse_args()

    conn, cur = connect()
    seen, gone_polls, aborted, polls, start_node = False, 0, 0, 0, None
    end = time.time() + args.max_hours * 3600
    while time.time() < end:
        try:
            cur.execute(SIZES, {"t": args.table})
            db, wal, node, heap, idx, rp, errs, bad = cur.fetchone()
            used = (db + (wal or 0)) / GIB
            if start_node is None:
                start_node = node
            cur.execute(REPACK, {"t": args.table})
            rows = cur.fetchall()
            log(f"db+wal={used:.2f}GiB heap={heap / GIB:.2f}G idx={idx / GIB:.2f}G file={node}"
                f"{' (SWAPPED)' if node != start_node else ''} repack_tables[{rp}] app_err5m={errs}"
                f" bad_reads5m={bad} backends={len(rows)}")
            for r in rows:
                log(f"   pid={r[0]} {r[1]} {r[2]} {r[3]}s {r[4]}")
            if rows:
                seen, gone_polls = True, 0
            elif seen:
                gone_polls += 1
                if gone_polls >= 3:
                    log("rewrite connections gone for 3 polls; stopping")
                    break
            if used > args.abort_gib and rows:
                work = [r for r in rows if r[1] != "idle in transaction"]
                if work:
                    pid, state = work[0][0], work[0][1]
                    fn = "pg_cancel_backend" if state == "active" else "pg_terminate_backend"
                    cur.execute(f"SELECT {fn}(%s)", (pid,))
                    log(f"ABORT: db+wal {used:.2f} GiB > {args.abort_gib}; {fn}({pid}) -> {cur.fetchone()[0]}")
                    aborted += 1
        except Exception as e:  # keep watching through a dropped connection
            log(f"watch error: {e!r}")
            try:
                conn, cur = connect()
            except Exception as e2:
                log(f"reconnect failed: {e2!r}")
        polls += 1
        if args.polls and polls >= args.polls:
            log(f"stopping after {polls} polls; aborts sent={aborted}")
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
