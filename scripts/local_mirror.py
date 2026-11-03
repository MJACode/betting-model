#!/usr/bin/env python
"""A carbon copy of the whole Supabase project on mike's machine.

mike, 2026-11-03: *"supabase is the SOR, but everything should be a carbon copy
on my local as a backup - everything"*. Supabase stays the system of record
(CLAUDE.md section 1b). This is a backup, and every run makes it converge to
Supabase again: new rows, changed rows and deleted rows alike.

WHAT IS COPIED
  * Every base table in every non-system schema (public, auth, storage,
    realtime, vault, supabase_migrations), as Parquet chunk files with a
    manifest per table.
  * The schema, as .sql files per run: tables, constraints, indexes, views,
    functions, triggers, RLS policies, grants, sequences, types, extensions,
    publications.
  * Every object in every storage bucket.

WHERE IT GOES. Outside the repo:
C:\\Users\\micha\\Documents\\betting_local_copies\\supabase_mirror. Inside the repo it
would be committed (data/local is tracked) and tests/test_everything_in_supabase.py
would fail on it.

HOW A TABLE CONVERGES. A table is a list of chunks. A chunk is one Parquet file
holding every row whose primary key lies in (previous chunk's last key, this
chunk's last key]. Each chunk records its row count and an XOR of per-row
hashes (md5 of the row's text, computed by the server in the same SELECT that
returned the rows). On each run:

  * Tables under --full-copy-below rows (2M), tables with no primary key, and
    the two tables whose whole row set churns (latest_odds, latest_prop_odds:
    measured 2026-11-03 at 16.8M updates and 82M deletes against 2.8M and 8.8M
    live rows) are copied whole into a new set of chunks, then swapped in.
  * Bigger tables are incremental: new keys past the last chunk are appended;
    every chunk's row count is compared with the server's (an index range
    count, ten chunks per query), which catches deletes and inserts; and a
    rolling set of chunks also has its hash compared, which catches updates.
    The hashed set is the newest --hot-chunks chunks (where picks get graded
    and odds get marked in_play) plus the chunks whose hash is oldest, capped
    at 1/--rotate-days of the table per run, so every chunk is re-checked about
    every --rotate-days days. A chunk that differs is pulled again.
  * None of the tables above 2M rows has an updated_at-style column (measured
    2026-11-03), so the hash IS the update detector for them.

LOAD ON PRODUCTION. One database serves live scoring. This script reads through
one connection on the transaction pooler; every batch is its own
`BEGIN ... READ ONLY` transaction with `SET LOCAL statement_timeout = 60s` (a
SET SESSION on the transaction pooler would stay on a shared server connection
and could land on a live scorer's session). Batches are at most 50k rows and at
most ~32 MB, read by primary-key index, with a sleep between them. It pauses
while more than 6 other sessions are active, and does not read at 10:00-10:50
UTC (the 6am ET pipeline) or at minutes :15-:27 of hours 11-22 UTC (the hourly
refresh). It never writes to the database.

RESUMABLE. Each table's manifest is rewritten after every chunk; a killed run
picks up where it stopped. Files no manifest references are deleted on the
next run.

SECRETS. DATABASE_URL is read from the environment or, failing that, from the
main checkout's .env at run time. It is never printed, logged or written; every
logged error has database URLs scrubbed out.

Usage:
  python local_mirror.py run                 # one full pass (schema, storage, tables, verify)
  python local_mirror.py run --only public.picks --skip-storage --skip-schema
  python local_mirror.py verify              # counts only, local vs Supabase
  python local_mirror.py status              # local manifests only, no database
  python local_mirror.py export-csv --table public.picks --out picks.csv

See docs/local_ops.md, "Local carbon copy".
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fnmatch
import functools
import hashlib
import json
import math
import operator
import os
import re
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

UTC = dt.timezone.utc

DEFAULT_ROOT = Path(r"C:\Users\micha\Documents\betting_local_copies")
DEFAULT_DEST = DEFAULT_ROOT / "supabase_mirror"
DEFAULT_ENV_FILE = Path(r"C:\Users\micha\documents\betting-model\.env")

BATCH_ROWS = 50_000
BATCH_BYTES = 32 * 1024 * 1024
FULL_COPY_BELOW = 2_000_000
# Whole row set churns between runs, so range checks would re-pull nearly
# every chunk anyway. Measured 2026-11-03 (pg_stat_user_tables): latest_odds
# 16.8M updates + 6.1M deletes vs 2.8M live; latest_prop_odds 82M deletes vs
# 8.8M live.
ALWAYS_FULL = frozenset({"public.latest_odds", "public.latest_prop_odds"})
ROTATE_DAYS = 7
HOT_CHUNKS = 40
COUNT_GROUP = 10
MAX_ACTIVE_OTHERS = 6
SLEEP_S = 0.5
STATEMENT_TIMEOUT_S = 60
# A batch may not start this close to a closed window: a statement can run for
# up to STATEMENT_TIMEOUT_S, and it must not run into the window.
WINDOW_MARGIN_S = STATEMENT_TIMEOUT_S + 15
MIN_BATCH_ROWS = 500

SYSTEM_SCHEMAS = ("pg_catalog", "information_schema")


# --------------------------------------------------------------- secrets

_URL_RE = re.compile(r"postgres(?:ql)?://[^\s'\"]+", re.IGNORECASE)


def scrub(text: Any) -> str:
    """Remove anything shaped like a database URL from text that will be logged."""
    return _URL_RE.sub("<database-url>", str(text))


def read_env_value(name: str, env_file: Path | None) -> str | None:
    """The variable from the process environment, else from a .env file.

    Read at run time on purpose: a scheduled run must take the current value
    from the main checkout's .env, not a copy made when the task was set up.
    """
    val = os.environ.get(name, "").strip()
    if val:
        return val
    if env_file is None or not Path(env_file).exists():
        return None
    with open(env_file, encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip().rstrip("\r")
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key.startswith("export "):
                key = key[len("export "):].strip()
            if key != name:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            return value or None
    return None


# --------------------------------------------------------------- read windows

# (start minute of the UTC day, end minute, exclusive). The end minute named in
# the rule is included: "10:00-10:50" closes at 10:51, ":15-:27" at :28.
CLOSED_WINDOWS: tuple[tuple[int, int], ...] = (
    (10 * 60, 10 * 60 + 51),
) + tuple((h * 60 + 15, h * 60 + 28) for h in range(11, 23))


def _day_start(t: dt.datetime) -> dt.datetime:
    return t.replace(hour=0, minute=0, second=0, microsecond=0)


def closed_until(now: dt.datetime) -> dt.datetime | None:
    """End of the closed window containing `now`, or None when reads are open."""
    now = now.astimezone(UTC)
    day = _day_start(now)
    for start, end in CLOSED_WINDOWS:
        s = day + dt.timedelta(minutes=start)
        e = day + dt.timedelta(minutes=end)
        if s <= now < e:
            return e
    return None


def next_window(now: dt.datetime) -> tuple[dt.datetime, dt.datetime]:
    """(start, end) of the first closed window that starts after `now`."""
    now = now.astimezone(UTC)
    for day_offset in (0, 1):
        day = _day_start(now) + dt.timedelta(days=day_offset)
        for start, end in CLOSED_WINDOWS:
            s = day + dt.timedelta(minutes=start)
            if s > now:
                return s, day + dt.timedelta(minutes=end)
    raise AssertionError("unreachable: a window starts every day")


def seconds_until_reads_allowed(now: dt.datetime, margin_s: float = WINDOW_MARGIN_S) -> float:
    """0 when a read may start now; otherwise how long to wait.

    A read may start when `now` is outside every closed window AND no window
    opens within `margin_s` (so a batch cannot run into one).
    """
    now = now.astimezone(UTC)
    t = now
    for _ in range(64):
        end = closed_until(t)
        if end is not None:
            t = end
            continue
        start, end = next_window(t)
        if (start - t).total_seconds() < margin_s:
            t = end
            continue
        break
    return max(0.0, (t - now).total_seconds())


def _utcnow() -> dt.datetime:
    return dt.datetime.now(UTC)


def _iso(t: dt.datetime | None = None) -> str:
    return (t or _utcnow()).astimezone(UTC).isoformat(timespec="seconds")


def _parse_iso(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    return dt.datetime.fromisoformat(s)


class Throttle:
    """Waits for an open read window and a quiet database before each batch."""

    def __init__(self, active_probe: Callable[[], int], *, log: Callable[[str], None],
                 sleep_s: float = SLEEP_S, max_active: int = MAX_ACTIVE_OTHERS,
                 margin_s: float = WINDOW_MARGIN_S,
                 clock: Callable[[], dt.datetime] = _utcnow,
                 sleeper: Callable[[float], None] = time.sleep):
        self.active_probe = active_probe
        self.log = log
        self.sleep_s = sleep_s
        self.max_active = max_active
        self.margin_s = margin_s
        self.clock = clock
        self.sleeper = sleeper
        self.paused_s = 0.0
        self._announced: str | None = None
        self._probed_at: dt.datetime | None = None
        self._active = 0

    PROBE_EVERY_S = 15.0

    def _active_now(self) -> int:
        now = self.clock()
        if self._probed_at is None or (now - self._probed_at).total_seconds() >= self.PROBE_EVERY_S:
            self._active = self.active_probe()
            self._probed_at = now
        return self._active

    def wait(self) -> None:
        while True:
            wait = seconds_until_reads_allowed(self.clock(), self.margin_s)
            if wait > 0:
                key = "window"
                if self._announced != key:
                    resume = self.clock() + dt.timedelta(seconds=wait)
                    self.log(f"read window closed; pausing until {_iso(resume)}")
                    self._announced = key
                step = min(wait, 60.0)
                self.sleeper(step)
                self.paused_s += step
                continue
            active = self._active_now()
            if active > self.max_active:
                key = "busy"
                if self._announced != key:
                    self.log(f"{active} other active sessions (> {self.max_active}); pausing")
                    self._announced = key
                self.sleeper(20.0)
                self.paused_s += 20.0
                continue
            if self._announced:
                self.log("resuming reads")
            self._announced = None
            return

    def rest(self, elapsed_s: float, light: bool = False) -> None:
        # A slow batch means the database is working hard: back off by as long
        # as it took, so this reader never holds more than about half its time.
        # A count or catalog read rests less than a page of rows.
        base = min(self.sleep_s, 0.1) if light else self.sleep_s
        self.sleeper(base + (elapsed_s if elapsed_s > 10 else 0.0))


# --------------------------------------------------------------- table model

NATIVE_ARROW = {
    "bool": "bool", "int2": "int16", "int4": "int32", "int8": "int64",
    "oid": "int64", "float4": "float32", "float8": "float64",
    "date": "date32", "timestamp": "timestamp_us",
    "timestamptz": "timestamp_us_utc", "time": "time64_us", "bytea": "binary",
    "text": "string", "varchar": "string", "bpchar": "string",
    "name": "string", "numeric": "string",
}


def arrow_kind(typname: str, typcategory: str) -> tuple[str, bool]:
    """(arrow kind, fetch as text). Everything not mapped natively is fetched as
    its Postgres text form: exact, and restorable with a plain cast."""
    if typcategory != "A" and typname in NATIVE_ARROW:
        return NATIVE_ARROW[typname], False
    return "string", True


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


@dataclass
class Column:
    name: str
    pg_type: str
    arrow: str
    as_text: bool = False


@dataclass
class TableInfo:
    schema: str
    name: str
    columns: list[Column]
    pk: list[str]
    pk_types: list[str]
    est_rows: int = 0
    table_bytes: int = 0
    total_bytes: int = 0
    kind: str = "r"

    @property
    def fq(self) -> str:
        return f"{self.schema}.{self.name}"

    @property
    def qname(self) -> str:
        return f"{quote_ident(self.schema)}.{quote_ident(self.name)}"

    def signature(self) -> str:
        raw = json.dumps([[c.name, c.pg_type] for c in self.columns] + [self.pk])
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


ALIAS = "__m"
ROW_HASH = f"('x' || left(md5({ALIAS}::text), 16))::bit(64)::bigint"


def keyset_where(info: TableInfo, lo: Sequence[str] | None,
                 hi: Sequence[str] | None) -> tuple[str, list[Any]]:
    """WHERE clause for primary keys in (lo, hi]. Either bound may be open.

    The bound is a row comparison over the whole key, (a, b) > (x, y), which a
    btree on (a, b) answers as an index range. Keys travel as their Postgres
    text form and are cast back with the column's own type, so a timestamp or
    numeric key round-trips exactly.
    """
    cols = ", ".join(f"{ALIAS}.{quote_ident(c)}" for c in info.pk)
    parts: list[str] = []
    params: list[Any] = []
    for bound, op in ((lo, ">"), (hi, "<=")):
        if bound is None:
            continue
        ph = ", ".join(f"%s::{t}" for t in info.pk_types)
        parts.append(f"({cols}) {op} ({ph})")
        params.extend(bound)
    return (("WHERE " + " AND ".join(parts)) if parts else ""), params


def order_by(info: TableInfo) -> str:
    return ", ".join(f"{ALIAS}.{quote_ident(c)}" for c in info.pk)


def select_list(info: TableInfo) -> str:
    out = []
    for c in info.columns:
        ref = f"{ALIAS}.{quote_ident(c.name)}"
        out.append(f"{ref}::text" if c.as_text else ref)
    return ", ".join(out)


def page_sql(info: TableInfo, lo, hi) -> tuple[str, list[Any]]:
    where, params = keyset_where(info, lo, hi)
    keys = ", ".join(f"{ALIAS}.{quote_ident(c)}::text" for c in info.pk)
    sql = (f"SELECT {select_list(info)}, {keys}, {ROW_HASH} "
           f"FROM {info.qname} AS {ALIAS} {where} "
           f"ORDER BY {order_by(info)} LIMIT %s")
    return sql, params


def summaries_sql(info: TableInfo, lo, his: Sequence[Sequence[str]],
                  with_hash: bool) -> tuple[str, list[Any]]:
    """One statement: row count (and hash) for each consecutive sub-range
    (lo, his[0]], (his[0], his[1]], ... ."""
    cols = ", ".join(f"{ALIAS}.{quote_ident(c)}" for c in info.pk)
    ph = ", ".join(f"%s::{t}" for t in info.pk_types)
    exprs: list[str] = []
    params: list[Any] = []
    prev = lo
    for h in his:
        if prev is None:
            cond = f"({cols}) <= ({ph})"
            cparams = list(h)
        else:
            cond = f"({cols}) > ({ph}) AND ({cols}) <= ({ph})"
            cparams = list(prev) + list(h)
        exprs.append(f"count(*) FILTER (WHERE {cond})")
        params.extend(cparams)
        if with_hash:
            exprs.append(f"bit_xor({ROW_HASH}) FILTER (WHERE {cond})")
            params.extend(cparams)
        prev = h
    where, wparams = keyset_where(info, lo, his[-1])
    return f"SELECT {', '.join(exprs)} FROM {info.qname} AS {ALIAS} {where}", params + wparams


@dataclass
class Page:
    columns: list[Sequence[Any]]
    n: int
    last_key: list[str] | None
    xor: int
    limit: int = 0  # rows asked for; fewer back means the range is exhausted


def xor_all(values: Iterable[int]) -> int:
    return functools.reduce(operator.xor, (v for v in values if v is not None), 0)


# --------------------------------------------------------------- the server

class PgSource:
    """Read-only access to production. Every call is one READ ONLY transaction."""

    def __init__(self, url: str, *, log: Callable[[str], None], throttle_kw: dict | None = None):
        import psycopg2  # noqa: F401  (imported here so tests need no driver)
        self._url = self._transaction_endpoint(url)
        self.log = log
        self._conn_obj = None
        self.throttle = Throttle(self.active_others, log=log, **(throttle_kw or {}))
        self.db_seconds = 0.0

    @staticmethod
    def _transaction_endpoint(url: str) -> str:
        # Same rewrite as data/db.py: Supabase's session pooler (5432) hands
        # each client its own server connection; 6543 shares them.
        if "pooler.supabase.com" in url and ":5432" in url:
            return url.replace(":5432", ":6543", 1)
        return url

    def _conn(self):
        import psycopg2
        import psycopg2.extensions as ext
        if self._conn_obj is None or self._conn_obj.closed:
            conn = psycopg2.connect(self._url, connect_timeout=20,
                                    keepalives=1, keepalives_idle=30,
                                    keepalives_interval=10, keepalives_count=5)
            conn.autocommit = True  # we issue BEGIN ... READ ONLY ourselves
            numeric_text = ext.new_type((1700,), "MIRROR_NUMERIC_TEXT", lambda v, c: v)
            ext.register_type(numeric_text, conn)
            self._conn_obj = conn
        return self._conn_obj

    def _reset(self) -> None:
        with contextlib.suppress(Exception):
            if self._conn_obj is not None:
                self._conn_obj.close()
        self._conn_obj = None

    @contextlib.contextmanager
    def _txn(self):
        cur = self._conn().cursor()
        try:
            # One round trip: the transaction and its settings together.
            cur.execute(
                "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; "
                f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT_S}s'; "
                "SET LOCAL idle_in_transaction_session_timeout = '60s'; "
                "SET LOCAL TimeZone = 'UTC'; SET LOCAL DateStyle = 'ISO, MDY'; "
                "SET LOCAL IntervalStyle = 'postgres'; SET LOCAL extra_float_digits = 1; "
                "SET LOCAL bytea_output = 'hex'")
            yield cur
            cur.execute("COMMIT")
        except BaseException:
            with contextlib.suppress(Exception):
                cur.execute("ROLLBACK")
            raise
        finally:
            with contextlib.suppress(Exception):
                cur.close()

    def _run(self, fn: Callable[[Any], Any], *, throttled: bool = True, light: bool = False,
             txn: bool = True):
        import psycopg2
        import psycopg2.extensions as ext
        last: Exception | None = None
        for attempt in range(8):
            if throttled:
                self.throttle.wait()
            t0 = time.monotonic()
            try:
                if txn:
                    with self._txn() as cur:
                        out = fn(cur)
                else:
                    with contextlib.closing(self._conn().cursor()) as cur:
                        out = fn(cur)
                elapsed = time.monotonic() - t0
                self.db_seconds += elapsed
                if throttled:
                    self.throttle.rest(elapsed, light=light)
                return out
            except ext.QueryCanceledError:
                raise
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as exc:
                last = exc
                wait = min(300, 10 * 2 ** attempt)
                self.log(f"database connection problem ({scrub(exc).strip()[:200]}); "
                         f"reconnecting in {wait}s")
                self._reset()
                time.sleep(wait)
        raise RuntimeError(f"database unreachable after retries: {scrub(last)}")

    # -- probes and catalog ---------------------------------------------------

    def active_others(self) -> int:
        def q(cur):
            cur.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active' "
                        "AND backend_type = 'client backend' AND pid <> pg_backend_pid()")
            return int(cur.fetchone()[0])
        return self._run(q, throttled=False, txn=False)

    def query(self, sql: str, params: Sequence[Any] | None = None, *, light: bool = True) -> list[tuple]:
        """A read. With no params the SQL is sent as written (no % escaping)."""
        def q(cur):
            cur.execute(sql, list(params) if params else None)
            return cur.fetchall()
        return self._run(q, light=light)

    def list_tables(self) -> list[TableInfo]:
        rows = self.query("""
            SELECT c.oid, n.nspname, c.relname, c.relkind, c.reltuples::bigint,
                   pg_table_size(c.oid), pg_total_relation_size(c.oid),
                   has_table_privilege(c.oid, 'SELECT')
              FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE c.relkind IN ('r', 'p') AND NOT c.relispartition
               AND n.nspname NOT IN ('pg_catalog', 'information_schema')
               AND n.nspname NOT LIKE 'pg\\_toast%' AND n.nspname NOT LIKE 'pg\\_temp%'
             ORDER BY n.nspname, c.relname""")
        cols = self.query("""
            SELECT a.attrelid, a.attname, format_type(a.atttypid, a.atttypmod),
                   t.typname, t.typcategory, t.typtype
              FROM pg_attribute a
              JOIN pg_type t ON t.oid = a.atttypid
              JOIN pg_class c ON c.oid = a.attrelid
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE a.attnum > 0 AND NOT a.attisdropped AND c.relkind IN ('r', 'p')
               AND n.nspname NOT IN ('pg_catalog', 'information_schema')
             ORDER BY a.attrelid, a.attnum""")
        pks = self.query("""
            SELECT i.indrelid, a.attname, format_type(a.atttypid, a.atttypmod)
              FROM pg_index i
              JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS k(attnum, ord) ON true
              JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = k.attnum
             WHERE i.indisprimary
             ORDER BY i.indrelid, k.ord""")
        by_oid_cols: dict[int, list[Column]] = {}
        for oid, name, pg_type, typname, typcat, typtype in cols:
            # Domains, enums, arrays, json, uuid and the rest arrive as their
            # Postgres text: exact, and restorable with a plain cast.
            kind, as_text = arrow_kind(typname, typcat) if typtype == "b" else ("string", True)
            by_oid_cols.setdefault(oid, []).append(Column(name, pg_type, kind, as_text))
        by_oid_pk: dict[int, list[tuple[str, str]]] = {}
        for oid, name, pg_type in pks:
            by_oid_pk.setdefault(oid, []).append((name, pg_type))
        out = []
        for oid, schema, name, kind, reltuples, tbytes, total, can_read in rows:
            if not can_read:
                self.log(f"skipping {schema}.{name}: no SELECT privilege")
                continue
            pk = by_oid_pk.get(oid, [])
            out.append(TableInfo(schema, name, by_oid_cols.get(oid, []),
                                 [p[0] for p in pk], [p[1] for p in pk],
                                 int(reltuples), int(tbytes), int(total), kind))
        return out

    def exact_count(self, info: TableInfo) -> int:
        return int(self.query(f"SELECT count(*) FROM {info.qname}")[0][0])

    # -- data -------------------------------------------------------------------

    def fetch_page(self, info: TableInfo, lo, hi, limit: int) -> Page:
        import psycopg2.extensions as ext
        while True:
            sql, params = page_sql(info, lo, hi)

            def q(cur, sql=sql, params=params, limit=limit):
                cur.execute(sql, params + [limit])
                return cur.fetchall()
            try:
                rows = self._run(q, light=False)
                break
            except ext.QueryCanceledError:
                if limit <= MIN_BATCH_ROWS:
                    raise
                limit = max(MIN_BATCH_ROWS, limit // 2)
                self.log(f"{info.fq}: batch hit the statement timeout; retrying at {limit} rows")
                self._reset()
        page = _page_from_rows(info, rows, n_keys=len(info.pk))
        page.limit = limit
        return page

    def range_summaries(self, info: TableInfo, lo, his, with_hash: bool) -> list[tuple[int, int | None] | None]:
        """(count, hash) per sub-range; None for a range whose check hit the
        statement timeout on its own. The caller copies that range again,
        which always fits (fetch_page halves its batch until it does)."""
        import psycopg2.extensions as ext
        sql, params = summaries_sql(info, lo, his, with_hash)

        def q(cur):
            cur.execute(sql, params)
            return cur.fetchone()
        try:
            row = self._run(q, light=not with_hash)
        except ext.QueryCanceledError:
            self._reset()
            if len(his) == 1:
                self.log(f"{info.fq}: a range check hit the statement timeout; it will be copied again")
                return [None]
            # Split the group and try again.
            mid = len(his) // 2
            return (self.range_summaries(info, lo, his[:mid], with_hash)
                    + self.range_summaries(info, his[mid - 1], his[mid:], with_hash))
        out = []
        step = 2 if with_hash else 1
        for i in range(len(his)):
            cnt = int(row[i * step])
            hsh = (int(row[i * step + 1]) if row[i * step + 1] is not None else 0) if with_hash else None
            out.append((cnt, hsh))
        return out

    def tail_count(self, info: TableInfo, lo) -> int:
        where, params = keyset_where(info, lo, None)
        sql = f"SELECT count(*) FROM {info.qname} AS {ALIAS} {where}"
        return int(self.query(sql, params)[0][0])

    def relpages(self, info: TableInfo) -> int:
        return int(self.query(
            "SELECT pg_relation_size(%s::regclass) / current_setting('block_size')::int",
            (info.qname,))[0][0])

    def fetch_ctid_pages(self, info: TableInfo, page_lo: int, page_hi: int | None) -> Page:
        where = f"WHERE {ALIAS}.ctid >= '({int(page_lo)},0)'::tid"
        if page_hi is not None:
            where += f" AND {ALIAS}.ctid < '({int(page_hi)},0)'::tid"
        sql = f"SELECT {select_list(info)}, {ROW_HASH} FROM {info.qname} AS {ALIAS} {where}"
        rows = self.query(sql, light=False)
        return _page_from_rows(info, rows, n_keys=0)


def _page_from_rows(info: TableInfo, rows: list[tuple], n_keys: int) -> Page:
    ncol = len(info.columns)
    if not rows:
        return Page([[] for _ in range(ncol)], 0, None, 0)
    cols = list(zip(*rows))
    data = list(cols[:ncol])
    last_key = list(rows[-1][ncol:ncol + n_keys]) if n_keys else None
    return Page(data, len(rows), last_key, xor_all(cols[-1]))


# --------------------------------------------------------------- local store

def _arrow_type(kind: str):
    import pyarrow as pa
    return {
        "bool": pa.bool_(), "int16": pa.int16(), "int32": pa.int32(),
        "int64": pa.int64(), "float32": pa.float32(), "float64": pa.float64(),
        "string": pa.string(), "binary": pa.binary(), "date32": pa.date32(),
        "timestamp_us": pa.timestamp("us"),
        "timestamp_us_utc": pa.timestamp("us", tz="UTC"),
        "time64_us": pa.time64("us"),
    }[kind]


def arrow_schema(info: TableInfo):
    import pyarrow as pa
    return pa.schema([pa.field(c.name, _arrow_type(c.arrow)) for c in info.columns],
                     metadata={"mirror_table": info.fq,
                               "pg_types": json.dumps({c.name: c.pg_type for c in info.columns})})


def to_arrow(info: TableInfo, columns: list[Sequence[Any]]):
    import pyarrow as pa
    arrays = []
    for c, values in zip(info.columns, columns):
        if c.arrow == "binary":
            values = [bytes(v) if v is not None else None for v in values]
        arrays.append(pa.array(values, type=_arrow_type(c.arrow)))
    return pa.Table.from_arrays(arrays, schema=arrow_schema(info))


def _atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


class TableDir:
    def __init__(self, root: Path, fq: str):
        self.dir = Path(root) / "tables" / fq
        self.manifest_path = self.dir / "manifest.json"

    def load(self) -> dict | None:
        if not self.manifest_path.exists():
            return None
        with open(self.manifest_path, encoding="utf-8") as fh:
            return json.load(fh)

    def save(self, manifest: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        manifest["rows"] = sum(c["rows"] for c in manifest["chunks"])
        manifest["bytes"] = sum(c.get("bytes", 0) for c in manifest["chunks"])
        manifest["chunk_count"] = len(manifest["chunks"])
        manifest["watermark"] = manifest["chunks"][-1]["hi"] if manifest["chunks"] else None
        _atomic_write_text(self.manifest_path, json.dumps(manifest, indent=1, default=str))

    def write_chunk(self, chunk_id: int, table) -> tuple[str, int]:
        import pyarrow.parquet as pq
        self.dir.mkdir(parents=True, exist_ok=True)
        name = f"chunk_{chunk_id:07d}.parquet"
        path = self.dir / name
        tmp = path.with_name(name + ".tmp")
        pq.write_table(table, tmp, compression="zstd")
        os.replace(tmp, path)
        return name, path.stat().st_size

    def remove(self, name: str | None) -> None:
        if name:
            with contextlib.suppress(FileNotFoundError):
                (self.dir / name).unlink()

    def cleanup_orphans(self, manifest: dict | None) -> int:
        if not self.dir.exists():
            return 0
        keep = {c["file"] for c in (manifest or {}).get("chunks", []) if c.get("file")}
        removed = 0
        for p in self.dir.iterdir():
            if p.name == "manifest.json":
                continue
            if p.name.endswith(".tmp") or (p.suffix == ".parquet" and p.name not in keep):
                p.unlink()
                removed += 1
        return removed

    def read_rows(self, manifest: dict):
        """Every row, in key order, as one Arrow table (tests and export)."""
        import pyarrow as pa
        import pyarrow.parquet as pq
        tables = [pq.read_table(self.dir / c["file"]) for c in manifest["chunks"] if c.get("file")]
        if not tables:
            return None
        return pa.concat_tables(tables, promote_options="default")


# --------------------------------------------------------------- the engine

@dataclass
class TableResult:
    fq: str
    mode: str
    local_rows: int = 0
    server_rows: int | None = None
    tail_new: int = 0
    repulled: int = 0
    mismatched: int = 0
    unchecked: int = 0  # ranges whose count hit the statement timeout
    pulled_rows: int = 0
    error: str | None = None
    seconds: float = 0.0


class Mirror:
    def __init__(self, source, root: Path, *, log: Callable[[str], None] = print,
                 batch_rows: int = BATCH_ROWS, batch_bytes: int = BATCH_BYTES,
                 full_copy_below: int = FULL_COPY_BELOW, always_full=ALWAYS_FULL,
                 rotate_days: float = ROTATE_DAYS, hot_chunks: int = HOT_CHUNKS,
                 count_group: int = COUNT_GROUP,
                 clock: Callable[[], dt.datetime] = _utcnow,
                 progress: Callable[[str, int], None] | None = None):
        self.source = source
        self.root = Path(root)
        self.log = log
        self.batch_rows = batch_rows
        self.batch_bytes = batch_bytes
        self.full_copy_below = full_copy_below
        self.always_full = set(always_full)
        self.rotate_days = rotate_days
        self.hot_chunks = hot_chunks
        self.count_group = count_group
        self.clock = clock
        self.progress = progress or (lambda fq, n: None)

    # -- policy -----------------------------------------------------------------

    def mode_for(self, info: TableInfo) -> str:
        if not info.pk or info.fq in self.always_full or info.est_rows < self.full_copy_below:
            return "full"
        return "incremental"

    def rows_per_batch(self, info: TableInfo) -> int:
        if info.est_rows > 0 and info.table_bytes > 0:
            avg = info.table_bytes / info.est_rows
            return int(max(100, min(self.batch_rows, self.batch_bytes // max(avg, 1))))
        return self.batch_rows

    # -- manifest helpers ---------------------------------------------------------

    def _new_manifest(self, info: TableInfo, mode: str) -> dict:
        return {
            "table": info.fq, "mode": mode, "key_columns": info.pk,
            "key_types": info.pk_types,
            "columns": [{"name": c.name, "pg_type": c.pg_type, "arrow": c.arrow}
                        for c in info.columns],
            "schema_sig": info.signature(), "next_id": 1, "chunks": [],
            "created_at": _iso(self.clock()), "last_run": None,
            "last_full_reconcile": None, "last_verify": None,
        }

    def _write_page(self, store: TableDir, m: dict, info: TableInfo, page: Page,
                    hi: list[str] | None) -> dict:
        cid = m["next_id"]
        m["next_id"] = cid + 1
        name, size = store.write_chunk(cid, to_arrow(info, page.columns))
        now = _iso(self.clock())
        return {"id": cid, "file": name, "hi": hi, "rows": page.n, "bytes": size,
                "xor": str(page.xor), "sig": info.signature(),
                "pulled_at": now, "hash_checked_at": now}

    def _pull_range(self, store: TableDir, m: dict, info: TableInfo, lo, hi,
                    on_chunk: Callable[[dict], None]) -> int:
        """Keyset-page (lo, hi] (hi None = open tail) into new chunks.

        The last chunk of a bounded range takes `hi` as its bound, so the
        ranges stay contiguous whatever the server holds now.
        """
        limit = self.rows_per_batch(info)
        after = lo
        made: list[dict] = []
        pulled = 0
        while True:
            page = self.source.fetch_page(info, after, hi, limit)
            if page.n == 0:
                break
            chunk = self._write_page(store, m, info, page, page.last_key)
            made.append(chunk)
            pulled += page.n
            on_chunk(chunk)
            self.progress(info.fq, page.n)
            after = page.last_key
            if page.n < (page.limit or limit):
                break
        if hi is not None and made and made[-1]["hi"] != list(hi):
            made[-1]["hi"] = list(hi)
            on_chunk(made[-1])
        return pulled

    # -- full copy ------------------------------------------------------------------

    def _full_copy(self, store: TableDir, info: TableInfo, old: dict | None) -> TableResult:
        res = TableResult(info.fq, "full")
        m = self._new_manifest(info, "full")
        if old:
            m["next_id"] = old.get("next_id", 1)
            m["created_at"] = old.get("created_at", m["created_at"])
        new_chunks: list[dict] = []

        def keep(chunk):
            if not new_chunks or new_chunks[-1]["id"] != chunk["id"]:
                new_chunks.append(chunk)

        if info.pk:
            res.pulled_rows = self._pull_range(store, m, info, None, None, keep)
        else:
            res.pulled_rows = self._full_copy_ctid(store, m, info, keep)
        m["chunks"] = new_chunks
        now = _iso(self.clock())
        m["last_run"] = now
        m["last_full_reconcile"] = now
        m["run_no"] = (old or {}).get("run_no", 0) + 1
        for k in ("last_verify",):
            if old and old.get(k):
                m[k] = old[k]
        store.save(m)
        for c in (old or {}).get("chunks", []):
            store.remove(c.get("file"))
        res.local_rows = m["rows"]
        return res

    def _full_copy_ctid(self, store: TableDir, m: dict, info: TableInfo, keep) -> int:
        """No primary key: page through the heap by ctid block ranges."""
        pages = self.source.relpages(info)
        rows_per_page = max(1.0, info.est_rows / pages) if pages and info.est_rows > 0 else 50.0
        step = max(1, int(self.rows_per_batch(info) / rows_per_page))
        pulled = 0
        p = 0
        while True:
            last = p >= pages
            page = self.source.fetch_ctid_pages(info, p, None if last else p + step)
            if page.n:
                keep(self._write_page(store, m, info, page, None))
                pulled += page.n
                self.progress(info.fq, page.n)
            if last:
                break
            p += step
        return pulled

    # -- incremental ------------------------------------------------------------------

    def _bounds(self, chunks: list[dict], i: int):
        return (chunks[i - 1]["hi"] if i > 0 else None), chunks[i]["hi"]

    def _choose_hashed(self, m: dict) -> set[int]:
        chunks = m["chunks"]
        n = len(chunks)
        chosen = {c["id"] for c in chunks[-self.hot_chunks:]} if self.hot_chunks else set()
        now = self.clock()
        def age_s(c):
            t = _parse_iso(c.get("hash_checked_at"))
            return math.inf if t is None else (now - t).total_seconds()
        due = [c for c in chunks
               if c["id"] not in chosen and age_s(c) >= self.rotate_days * 86400]
        due.sort(key=lambda c: c.get("hash_checked_at") or "")
        cap = math.ceil(n / max(self.rotate_days, 1)) if n else 0
        chosen.update(c["id"] for c in due[:cap])
        return chosen

    def _compare(self, info: TableInfo, m: dict, hashed: set[int]) -> tuple[list[int], int]:
        """Ids of chunks whose server range differs from the local chunk."""
        chunks = m["chunks"]
        sig = info.signature()
        bad: list[int] = []
        i = 0
        n_checked_hash = 0
        now = _iso(self.clock())
        while i < len(chunks):
            c = chunks[i]
            if c.get("sig") != sig:
                bad.append(c["id"])
                i += 1
                continue
            if c["id"] in hashed:
                lo, hi = self._bounds(chunks, i)
                summary = self.source.range_summaries(info, lo, [hi], True)[0]
                n_checked_hash += 1
                if summary is None or summary[0] != c["rows"] or str(summary[1]) != c["xor"]:
                    bad.append(c["id"])
                else:
                    c["hash_checked_at"] = now
                i += 1
                continue
            group = [c]  # always at least this chunk, so the loop always advances
            j = i + 1
            while (j < len(chunks) and len(group) < self.count_group
                   and chunks[j]["id"] not in hashed and chunks[j].get("sig") == sig):
                group.append(chunks[j])
                j += 1
            lo = chunks[i - 1]["hi"] if i > 0 else None
            sums = self.source.range_summaries(info, lo, [g["hi"] for g in group], False)
            for g, s in zip(group, sums):
                if s is None or s[0] != g["rows"]:  # None: the check timed out
                    bad.append(g["id"])
            i = j
        return bad, n_checked_hash

    def _repull(self, store: TableDir, m: dict, info: TableInfo, chunk_id: int) -> int:
        chunks = m["chunks"]
        idx = next(k for k, c in enumerate(chunks) if c["id"] == chunk_id)
        lo, hi = self._bounds(chunks, idx)
        old = chunks[idx]
        fresh: list[dict] = []

        def keep(chunk):
            if not fresh or fresh[-1]["id"] != chunk["id"]:
                fresh.append(chunk)
        pulled = self._pull_range(store, m, info, lo, hi, keep)
        m["chunks"] = chunks[:idx] + fresh + chunks[idx + 1:]
        store.save(m)
        store.remove(old.get("file"))
        return pulled

    def _incremental(self, store: TableDir, info: TableInfo, m: dict | None) -> TableResult:
        res = TableResult(info.fq, "incremental")
        if m is None:
            m = self._new_manifest(info, "incremental")
            store.save(m)
        m["mode"] = "incremental"
        if m.get("schema_sig") != info.signature():
            self.log(f"{info.fq}: columns changed since the last run; every chunk will be re-pulled")
            m["schema_sig"] = info.signature()
            m["columns"] = [{"name": c.name, "pg_type": c.pg_type, "arrow": c.arrow}
                            for c in info.columns]
            m["key_columns"], m["key_types"] = info.pk, info.pk_types

        def append(chunk):
            if not m["chunks"] or m["chunks"][-1]["id"] != chunk["id"]:
                m["chunks"].append(chunk)
            store.save(m)

        last_hi = m["chunks"][-1]["hi"] if m["chunks"] else None
        res.pulled_rows += self._pull_range(store, m, info, last_hi, None, append)

        hashed = self._choose_hashed(m)
        bad, n_hashed = self._compare(info, m, hashed)
        for cid in bad:
            res.pulled_rows += self._repull(store, m, info, cid)
        res.repulled = len(bad)
        checked = [_parse_iso(c.get("hash_checked_at")) for c in m["chunks"]]
        if checked and all(checked):
            m["last_full_reconcile"] = _iso(min(checked))
        m["run_no"] = m.get("run_no", 0) + 1
        m["last_run"] = _iso(self.clock())
        m["last_reconcile"] = {"at": m["last_run"], "hashed_chunks": n_hashed,
                               "repulled_chunks": len(bad)}
        store.save(m)
        res.local_rows = m["rows"]
        return res

    # -- public -------------------------------------------------------------------------

    def sync_table(self, info: TableInfo) -> TableResult:
        t0 = time.monotonic()
        store = TableDir(self.root, info.fq)
        m = store.load()
        removed = store.cleanup_orphans(m)
        if removed:
            self.log(f"{info.fq}: removed {removed} file(s) left by an interrupted run")
        mode = self.mode_for(info)
        if mode == "full":
            res = self._full_copy(store, info, m)
        else:
            res = self._incremental(store, info, m)
        res.seconds = time.monotonic() - t0
        return res

    def verify_table(self, info: TableInfo) -> TableResult:
        """Exact counts, local vs server: per chunk range, plus rows past the last key."""
        store = TableDir(self.root, info.fq)
        m = store.load()
        res = TableResult(info.fq, (m or {}).get("mode", "?"))
        if m is None:
            res.error = "no local copy"
            return res
        res.local_rows = m["rows"]
        if not m.get("key_columns"):
            res.server_rows = self.source.exact_count(info)
            res.mismatched = int(res.server_rows != res.local_rows)
        else:
            chunks = m["chunks"]
            server = 0
            mism = 0
            i = 0
            while i < len(chunks):
                group = chunks[i:i + self.count_group]
                lo = chunks[i - 1]["hi"] if i > 0 else None
                sums = self.source.range_summaries(info, lo, [g["hi"] for g in group], False)
                for g, s in zip(group, sums):
                    if s is None:  # timed out: not counted, and taken as equal below
                        res.unchecked += 1
                        server += g["rows"]
                        continue
                    server += s[0]
                    mism += int(s[0] != g["rows"])
                i += len(group)
            res.server_rows = server
            res.mismatched = mism
            res.tail_new = self.source.tail_count(info, chunks[-1]["hi"] if chunks else None)
        m["last_verify"] = {"at": _iso(self.clock()), "local_rows": res.local_rows,
                            "server_rows_in_copied_ranges": res.server_rows,
                            "server_rows_past_last_key": res.tail_new,
                            "mismatched_chunks": res.mismatched,
                            "ranges_not_counted_timeout": res.unchecked}
        store.save(m)
        return res


# --------------------------------------------------------------- schema dump

_USER_NS = ("n.nspname NOT IN ('pg_catalog', 'information_schema') "
            "AND n.nspname NOT LIKE 'pg\\_toast%' AND n.nspname NOT LIKE 'pg\\_temp%'")
_NOT_EXT = "NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = {oid} AND d.deptype = 'e')"


def dump_schema(src: PgSource, out_dir: Path, log: Callable[[str], None]) -> dict:
    """The schema as .sql files, from the catalogs (there is no pg_dump here)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    q = src.query
    files: dict[str, list[str]] = {}

    def put(name: str, text: str) -> None:
        files.setdefault(name, []).append(text.rstrip() + "\n")

    for ext_name, ns, ver in q("SELECT e.extname, n.nspname, e.extversion FROM pg_extension e "
                               "JOIN pg_namespace n ON n.oid = e.extnamespace ORDER BY 1"):
        put("00_extensions.sql", f"CREATE EXTENSION IF NOT EXISTS {quote_ident(ext_name)} "
                                 f"WITH SCHEMA {quote_ident(ns)} VERSION '{ver}';")
    for ns, owner in q(f"SELECT n.nspname, pg_get_userbyid(n.nspowner) FROM pg_namespace n "
                       f"WHERE {_USER_NS} ORDER BY 1"):
        put("01_schemas.sql", f"CREATE SCHEMA IF NOT EXISTS {quote_ident(ns)} "
                              f"AUTHORIZATION {quote_ident(owner)};")

    for ns, typ, labels in q(f"""
            SELECT n.nspname, t.typname, array_agg(e.enumlabel ORDER BY e.enumsortorder)
              FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid
              JOIN pg_namespace n ON n.oid = t.typnamespace
             WHERE {_USER_NS} AND {_NOT_EXT.format(oid='t.oid')}
             GROUP BY 1, 2 ORDER BY 1, 2"""):
        vals = ", ".join("'" + v.replace("'", "''") + "'" for v in labels)
        put("02_types.sql", f"CREATE TYPE {quote_ident(ns)}.{quote_ident(typ)} AS ENUM ({vals});")
    for ns, typ, base, notnull, default, checks in q(f"""
            SELECT n.nspname, t.typname, format_type(t.typbasetype, t.typtypmod), t.typnotnull,
                   t.typdefault,
                   (SELECT string_agg(' CONSTRAINT ' || quote_ident(c.conname) || ' ' ||
                                      pg_get_constraintdef(c.oid), '')
                      FROM pg_constraint c WHERE c.contypid = t.oid)
              FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
             WHERE t.typtype = 'd' AND {_USER_NS} AND {_NOT_EXT.format(oid='t.oid')}
             ORDER BY 1, 2"""):
        put("02_types.sql", f"CREATE DOMAIN {quote_ident(ns)}.{quote_ident(typ)} AS {base}"
                            f"{' NOT NULL' if notnull else ''}"
                            f"{' DEFAULT ' + default if default else ''}{checks or ''};")
    for ns, typ, attrs in q(f"""
            SELECT n.nspname, t.typname,
                   string_agg(quote_ident(a.attname) || ' ' || format_type(a.atttypid, a.atttypmod),
                              ', ' ORDER BY a.attnum)
              FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
              JOIN pg_class c ON c.oid = t.typrelid AND c.relkind = 'c'
              JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
             WHERE t.typtype = 'c' AND {_USER_NS} AND {_NOT_EXT.format(oid='t.oid')}
             GROUP BY 1, 2 ORDER BY 1, 2"""):
        put("02_types.sql", f"CREATE TYPE {quote_ident(ns)}.{quote_ident(typ)} AS ({attrs});")

    for (ns, name, dtype, start, mn, mx, inc, cycle, cache, last) in q(f"""
            SELECT s.schemaname, s.sequencename, s.data_type::text, s.start_value, s.min_value,
                   s.max_value, s.increment_by, s.cycle, s.cache_size, s.last_value
              FROM pg_sequences s JOIN pg_namespace n ON n.nspname = s.schemaname
             WHERE {_USER_NS} ORDER BY 1, 2"""):
        fq = f"{quote_ident(ns)}.{quote_ident(name)}"
        put("03_sequences.sql",
            f"CREATE SEQUENCE IF NOT EXISTS {fq} AS {dtype} INCREMENT BY {inc} MINVALUE {mn} "
            f"MAXVALUE {mx} START WITH {start} CACHE {cache}{' CYCLE' if cycle else ''};")
        if last is not None:
            put("03_sequences.sql", f"SELECT setval('{fq}', {last}, true);")

    tables = q(f"""
        SELECT c.oid, n.nspname, c.relname, c.relkind, c.relpersistence, c.relispartition,
               CASE WHEN c.relkind = 'p' THEN pg_get_partkeydef(c.oid) END,
               CASE WHEN c.relispartition THEN pg_get_expr(c.relpartbound, c.oid) END,
               (SELECT quote_ident(pn.nspname) || '.' || quote_ident(pc.relname)
                  FROM pg_inherits i JOIN pg_class pc ON pc.oid = i.inhparent
                  JOIN pg_namespace pn ON pn.oid = pc.relnamespace WHERE i.inhrelid = c.oid LIMIT 1),
               c.relrowsecurity, c.relforcerowsecurity, obj_description(c.oid, 'pg_class')
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE c.relkind IN ('r', 'p') AND {_USER_NS} AND {_NOT_EXT.format(oid='c.oid')}
         ORDER BY c.relispartition, n.nspname, c.relname""")
    cols = q(f"""
        SELECT a.attrelid, quote_ident(a.attname), format_type(a.atttypid, a.atttypmod),
               a.attnotnull, pg_get_expr(ad.adbin, ad.adrelid), a.attidentity, a.attgenerated,
               CASE WHEN a.attcollation <> t.typcollation AND a.attcollation <> 0
                    THEN (SELECT quote_ident(cn.nspname) || '.' || quote_ident(co.collname)
                            FROM pg_collation co JOIN pg_namespace cn ON cn.oid = co.collnamespace
                           WHERE co.oid = a.attcollation) END
          FROM pg_attribute a
          JOIN pg_type t ON t.oid = a.atttypid
          JOIN pg_class c ON c.oid = a.attrelid JOIN pg_namespace n ON n.oid = c.relnamespace
          LEFT JOIN pg_attrdef ad ON ad.adrelid = a.attrelid AND ad.adnum = a.attnum
         WHERE a.attnum > 0 AND NOT a.attisdropped AND c.relkind IN ('r', 'p') AND {_USER_NS}
         ORDER BY a.attrelid, a.attnum""")
    by_rel: dict[int, list[tuple]] = {}
    for row in cols:
        by_rel.setdefault(row[0], []).append(row[1:])
    for (oid, ns, name, kind, persist, is_part, partkey, bound, parent, rls, force, comment) in tables:
        fq = f"{quote_ident(ns)}.{quote_ident(name)}"
        if is_part and parent:
            put("04_tables.sql", f"CREATE TABLE {fq} PARTITION OF {parent} {bound};")
        else:
            lines = []
            for cname, ctype, notnull, default, ident, gen, coll in by_rel.get(oid, []):
                s = f"    {cname} {ctype}"
                if coll:
                    s += f" COLLATE {coll}"
                if gen == "s":
                    s += f" GENERATED ALWAYS AS ({default}) STORED"
                elif ident in ("a", "d"):
                    s += f" GENERATED {'ALWAYS' if ident == 'a' else 'BY DEFAULT'} AS IDENTITY"
                elif default is not None:
                    s += f" DEFAULT {default}"
                if notnull:
                    s += " NOT NULL"
                lines.append(s)
            unlogged = "UNLOGGED " if persist == "u" else ""
            tail = f" PARTITION BY {partkey}" if partkey else ""
            put("04_tables.sql", f"CREATE {unlogged}TABLE {fq} (\n" + ",\n".join(lines) + f"\n){tail};")
        if comment:
            put("04_tables.sql", f"COMMENT ON TABLE {fq} IS '{comment.replace(chr(39), chr(39) * 2)}';")
        if rls:
            put("10_policies.sql", f"ALTER TABLE {fq} ENABLE ROW LEVEL SECURITY;")
        if force:
            put("10_policies.sql", f"ALTER TABLE {fq} FORCE ROW LEVEL SECURITY;")

    for rel, conname, condef, contype in q(f"""
            SELECT quote_ident(n.nspname) || '.' || quote_ident(c.relname), quote_ident(con.conname),
                   pg_get_constraintdef(con.oid), con.contype
              FROM pg_constraint con JOIN pg_class c ON c.oid = con.conrelid
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE {_USER_NS} AND con.conislocal AND {_NOT_EXT.format(oid='c.oid')}
             ORDER BY CASE con.contype WHEN 'p' THEN 0 WHEN 'u' THEN 1 WHEN 'c' THEN 2
                      WHEN 'x' THEN 3 ELSE 4 END, 1, 2"""):
        put("05_constraints.sql", f"ALTER TABLE ONLY {rel} ADD CONSTRAINT {conname} {condef};")

    for (indexdef,) in q(f"""
            SELECT pg_get_indexdef(i.indexrelid) || ';'
              FROM pg_index i JOIN pg_class ic ON ic.oid = i.indexrelid
              JOIN pg_class c ON c.oid = i.indrelid JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE {_USER_NS} AND {_NOT_EXT.format(oid='c.oid')}
               AND NOT EXISTS (SELECT 1 FROM pg_constraint con WHERE con.conindid = i.indexrelid
                                AND con.contype IN ('p', 'u', 'x'))
             ORDER BY n.nspname, c.relname, ic.relname"""):
        put("06_indexes.sql", indexdef)

    for ns, name, kind, viewdef, opts in q(f"""
            SELECT n.nspname, c.relname, c.relkind, pg_get_viewdef(c.oid, true), c.reloptions
              FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE c.relkind IN ('v', 'm') AND {_USER_NS} AND {_NOT_EXT.format(oid='c.oid')}
             ORDER BY n.nspname, c.relname"""):
        fq = f"{quote_ident(ns)}.{quote_ident(name)}"
        with_opts = f" WITH ({', '.join(opts)})" if opts else ""
        if kind == "m":
            put("07_views.sql", f"CREATE MATERIALIZED VIEW {fq}{with_opts} AS\n{viewdef.rstrip(';')}\nWITH NO DATA;")
        else:
            put("07_views.sql", f"CREATE OR REPLACE VIEW {fq}{with_opts} AS\n{viewdef.rstrip(';')};")

    for ns, name, kind, fdef in q(f"""
            SELECT n.nspname, p.proname, p.prokind,
                   CASE WHEN p.prokind IN ('f', 'p', 'w') THEN pg_get_functiondef(p.oid) END
              FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
             WHERE {_USER_NS} AND {_NOT_EXT.format(oid='p.oid')}
             ORDER BY n.nspname, p.proname, p.oid"""):
        if fdef:
            put("08_functions.sql", fdef.rstrip() + ";\n")
        else:
            put("08_functions.sql", f"-- aggregate {ns}.{name} not reconstructed (no pg_get_functiondef for aggregates)")

    for (tdef,) in q(f"""
            SELECT pg_get_triggerdef(t.oid, true) || ';'
              FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE NOT t.tgisinternal AND {_USER_NS} AND {_NOT_EXT.format(oid='c.oid')}
             ORDER BY n.nspname, c.relname, t.tgname"""):
        put("09_triggers.sql", tdef)
    for name, event, fn, tags, enabled in q("""
            SELECT e.evtname, e.evtevent, e.evtfoid::regprocedure::text, e.evttags, e.evtenabled
              FROM pg_event_trigger e ORDER BY 1"""):
        when = f" WHEN TAG IN ({', '.join(repr(t) for t in tags)})" if tags else ""
        fname = fn.split("(")[0]
        put("09_triggers.sql", f"CREATE EVENT TRIGGER {quote_ident(name)} ON {event}{when} "
                               f"EXECUTE FUNCTION {fname}();  -- enabled={enabled}")

    for rel, pol, permissive, cmd, roles, qual, check in q(f"""
            SELECT quote_ident(n.nspname) || '.' || quote_ident(c.relname), quote_ident(p.polname),
                   p.polpermissive, p.polcmd,
                   array(SELECT CASE WHEN r = 0 THEN 'PUBLIC' ELSE quote_ident(pg_get_userbyid(r)) END
                           FROM unnest(p.polroles) r),
                   pg_get_expr(p.polqual, p.polrelid), pg_get_expr(p.polwithcheck, p.polrelid)
              FROM pg_policy p JOIN pg_class c ON c.oid = p.polrelid
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE {_USER_NS} ORDER BY 1, 2"""):
        cmd_word = {"r": "SELECT", "a": "INSERT", "w": "UPDATE", "d": "DELETE", "*": "ALL"}[cmd]
        s = (f"CREATE POLICY {pol} ON {rel} AS {'PERMISSIVE' if permissive else 'RESTRICTIVE'} "
             f"FOR {cmd_word} TO {', '.join(roles)}")
        if qual:
            s += f" USING ({qual})"
        if check:
            s += f" WITH CHECK ({check})"
        put("10_policies.sql", s + ";")

    for ns, name, kind, grantee, priv, grantable in q(f"""
            SELECT n.nspname, c.relname, c.relkind,
                   CASE WHEN a.grantee = 0 THEN 'PUBLIC' ELSE quote_ident(pg_get_userbyid(a.grantee)) END,
                   a.privilege_type, a.is_grantable
              FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace,
                   aclexplode(c.relacl) a
             WHERE c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f') AND {_USER_NS}
             ORDER BY 1, 2, 4, 5"""):
        what = "SEQUENCE" if kind == "S" else "TABLE"
        put("11_grants.sql", f"GRANT {priv} ON {what} {quote_ident(ns)}.{quote_ident(name)} TO {grantee}"
                             f"{' WITH GRANT OPTION' if grantable else ''};")
    for ns, sig, grantee, priv in q(f"""
            SELECT n.nspname, quote_ident(p.proname) || '(' || pg_get_function_identity_arguments(p.oid) || ')',
                   CASE WHEN a.grantee = 0 THEN 'PUBLIC' ELSE quote_ident(pg_get_userbyid(a.grantee)) END,
                   a.privilege_type
              FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace,
                   aclexplode(p.proacl) a
             WHERE {_USER_NS} AND {_NOT_EXT.format(oid='p.oid')}
             ORDER BY 1, 2, 3"""):
        put("11_grants.sql", f"GRANT {priv} ON FUNCTION {quote_ident(ns)}.{sig} TO {grantee};")
    for ns, grantee, priv in q(f"""
            SELECT n.nspname,
                   CASE WHEN a.grantee = 0 THEN 'PUBLIC' ELSE quote_ident(pg_get_userbyid(a.grantee)) END,
                   a.privilege_type
              FROM pg_namespace n, aclexplode(n.nspacl) a WHERE {_USER_NS} ORDER BY 1, 2, 3"""):
        put("11_grants.sql", f"GRANT {priv} ON SCHEMA {quote_ident(ns)} TO {grantee};")

    for pub, alltables, ins, upd, dele, trunc in q(
            "SELECT pubname, puballtables, pubinsert, pubupdate, pubdelete, pubtruncate "
            "FROM pg_publication ORDER BY 1"):
        ops = ", ".join(o for o, on in (("insert", ins), ("update", upd), ("delete", dele),
                                        ("truncate", trunc)) if on)
        put("12_publications.sql", f"CREATE PUBLICATION {quote_ident(pub)}"
                                   f"{' FOR ALL TABLES' if alltables else ''} WITH (publish = '{ops}');")
    for pub, ns, name in q("SELECT pubname, schemaname, tablename FROM pg_publication_tables ORDER BY 1, 2, 3"):
        put("12_publications.sql", f"ALTER PUBLICATION {quote_ident(pub)} ADD TABLE "
                                   f"{quote_ident(ns)}.{quote_ident(name)};")

    counts = {}
    for name in sorted(files):
        text = "".join(files[name])
        _atomic_write_text(out_dir / name, text)
        counts[name] = len(files[name])
    with open(out_dir / "all.sql", "w", encoding="utf-8", newline="\n") as fh:
        for name in sorted(files):
            fh.write(f"-- ===== {name} =====\n")
            fh.write("".join(files[name]))
            fh.write("\n")
    log(f"schema: {', '.join(f'{k} {v}' for k, v in counts.items())}")
    return counts


# --------------------------------------------------------------- storage

_UNSAFE = re.compile(r'[<>:"|?*\x00-\x1f]')


def safe_object_path(base: Path, bucket: str, name: str) -> Path:
    parts = []
    for seg in name.split("/"):
        seg = {"": "%EMPTY%", ".": "%2E", "..": "%2E%2E"}.get(seg, seg)
        seg = _UNSAFE.sub(lambda m_: "%{:02X}".format(ord(m_.group(0))), seg)
        parts.append(seg)
    return base / _UNSAFE.sub("_", bucket) / Path(*parts)


def project_url(db_url: str, env_file: Path | None) -> str | None:
    explicit = read_env_value("SUPABASE_URL", env_file)
    if explicit:
        return explicit.rstrip("/")
    u = urllib.parse.urlparse(db_url)
    user = u.username or ""
    if "." in user:  # pooler: postgres.<project ref>
        return f"https://{user.split('.', 1)[1]}.supabase.co"
    m = re.match(r"db\.([a-z0-9]+)\.supabase\.co$", u.hostname or "")
    if m:
        return f"https://{m.group(1)}.supabase.co"
    return None


def mirror_storage(src: PgSource, dest: Path, base_url: str | None, service_key: str | None,
                   log: Callable[[str], None]) -> dict:
    root = dest / "storage"
    root.mkdir(parents=True, exist_ok=True)
    buckets = src.query("SELECT id, name, public FROM storage.buckets ORDER BY id")
    objects = src.query("""
        SELECT bucket_id, name, (metadata->>'size')::bigint, metadata->>'eTag',
               metadata->>'mimetype', updated_at::text
          FROM storage.objects ORDER BY bucket_id, name""")
    manifest_path = root / "objects_manifest.json"
    old = {}
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8") as fh:
            old = {(o["bucket"], o["name"]): o for o in json.load(fh).get("objects", [])}
    public = {b[0]: bool(b[2]) for b in buckets}
    report: dict[str, Any] = {"buckets": {}, "objects": [], "not_covered": []}
    keep_paths: set[Path] = set()
    for bucket, name, size, etag, mime, updated in objects:
        path = safe_object_path(root, bucket, name)
        keep_paths.add(path)
        entry = {"bucket": bucket, "name": name, "size": size, "etag": etag,
                 "mimetype": mime, "updated_at": updated, "local": str(path.relative_to(dest))}
        b = report["buckets"].setdefault(bucket, {"public": public.get(bucket), "objects": 0,
                                                  "bytes": 0, "downloaded": 0, "unchanged": 0,
                                                  "failed": 0})
        b["objects"] += 1
        prev = old.get((bucket, name))
        if (prev and path.exists() and path.stat().st_size == (size or 0)
                and prev.get("etag") == etag and prev.get("updated_at") == updated):
            b["unchanged"] += 1
            b["bytes"] += size or 0
            report["objects"].append(entry)
            continue
        quoted = urllib.parse.quote(name)
        headers = {"User-Agent": "betting-model-local-mirror"}
        if public.get(bucket):
            url = f"{base_url}/storage/v1/object/public/{urllib.parse.quote(bucket)}/{quoted}"
        elif service_key:
            url = f"{base_url}/storage/v1/object/authenticated/{urllib.parse.quote(bucket)}/{quoted}"
            headers["Authorization"] = f"Bearer {service_key}"
            headers["apikey"] = service_key
        else:
            b["failed"] += 1
            report["not_covered"].append({"bucket": bucket, "name": name,
                                          "reason": "private bucket and no SUPABASE_SERVICE_ROLE_KEY"})
            continue
        if not base_url:
            b["failed"] += 1
            report["not_covered"].append({"bucket": bucket, "name": name,
                                          "reason": "no project URL"})
            continue
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
                status = resp.status
        except urllib.error.HTTPError as exc:
            b["failed"] += 1
            report["not_covered"].append({"bucket": bucket, "name": name,
                                          "reason": f"HTTP {exc.code} from the storage API"})
            continue
        except Exception as exc:  # noqa: BLE001
            b["failed"] += 1
            report["not_covered"].append({"bucket": bucket, "name": name,
                                          "reason": f"download failed: {exc!r}"[:200]})
            continue
        md5 = hashlib.md5(data).hexdigest()
        etag_clean = (etag or "").strip('"')
        entry["md5"] = md5
        entry["verified"] = (len(data) == (size or 0)) and (
            etag_clean == md5 if re.fullmatch(r"[0-9a-f]{32}", etag_clean or "") else True)
        entry["http_status"] = status
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
        b["downloaded"] += 1
        b["bytes"] += len(data)
        report["objects"].append(entry)
    removed = 0
    for p in root.rglob("*"):
        if p.is_file() and p != manifest_path and p not in keep_paths:
            p.unlink()
            removed += 1
    report["removed_local_files"] = removed
    report["at"] = _iso()
    _atomic_write_text(manifest_path, json.dumps(report, indent=1, default=str))
    for bucket, b in report["buckets"].items():
        log(f"storage {bucket}: {b['objects']} objects, {b['bytes']:,} bytes, "
            f"{b['downloaded']} downloaded, {b['unchanged']} unchanged, {b['failed']} failed")
    for nc in report["not_covered"]:
        log(f"storage NOT COVERED {nc['bucket']}/{nc['name']}: {nc['reason']}")
    return report


# --------------------------------------------------------------- runner

class Logger:
    def __init__(self, path: Path | None):
        self.path = path
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)

    def __call__(self, msg: str) -> None:
        line = f"{_iso()} {scrub(msg)}"
        print(line, flush=True)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")


@contextlib.contextmanager
def single_run_lock(dest: Path):
    """One run at a time. The OS drops the lock if the process dies."""
    dest.mkdir(parents=True, exist_ok=True)
    fh = open(dest / ".lock", "a+")
    try:
        if os.name == "nt":
            import msvcrt
            try:
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise SystemExit("another local_mirror run holds the lock; exiting")
        else:
            import fcntl
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise SystemExit("another local_mirror run holds the lock; exiting")
        yield
    finally:
        fh.close()


def _select(tables: list[TableInfo], only: list[str], exclude: list[str]) -> list[TableInfo]:
    def hit(t, pats):
        return any(fnmatch.fnmatch(t.fq, p) or fnmatch.fnmatch(t.name, p) for p in pats)
    out = [t for t in tables if (not only or hit(t, only)) and not hit(t, exclude)]
    return sorted(out, key=lambda t: (t.total_bytes, t.fq))


def _fmt_table(results: list[TableResult]) -> str:
    head = (f"{'table':<52} {'mode':<11} {'local rows':>13} {'supabase rows':>14} "
            f"{'diff':>9} {'newer keys':>10}  status")
    lines = [head, "-" * len(head)]
    for r in results:
        if r.error:
            status = f"ERROR {r.error[:60]}"
        elif r.server_rows is None:
            status = "not verified"
        elif r.server_rows == r.local_rows and not r.unchecked:
            status = "OK"
        elif r.server_rows == r.local_rows:
            status = (f"{r.unchecked} range(s) not counted (60 s limit); the rest match; "
                      f"the next run copies them again")
        else:
            status = (f"MISMATCH in {r.mismatched} range(s): changed since it was copied; "
                      f"the next run re-pulls them")
        diff = "" if r.server_rows is None else f"{r.server_rows - r.local_rows:+,}"
        server = "" if r.server_rows is None else f"{r.server_rows:,}"
        lines.append(f"{r.fq:<52} {r.mode:<11} {r.local_rows:>13,} {server:>14} {diff:>9} "
                     f"{r.tail_new:>10,}  {status}")
    tot_l = sum(r.local_rows for r in results)
    tot_s = sum(r.server_rows or 0 for r in results)
    lines.append("-" * len(head))
    lines.append(f"{'TOTAL (' + str(len(results)) + ' tables)':<52} {'':<11} {tot_l:>13,} {tot_s:>14,} "
                 f"{tot_s - tot_l:>+9,} {sum(r.tail_new for r in results):>10,}")
    lines.append("'newer keys' = rows whose key is past the last copied key: written after "
                 "the copy, taken by the next run. Not counted in 'diff'.")
    return "\n".join(lines)


class Progress:
    def __init__(self, dest: Path, total_est: int, log: Callable[[str], None], src: PgSource | None):
        self.dest = dest
        self.total_est = max(total_est, 1)
        self.log = log
        self.src = src
        self.started = time.monotonic()
        self.started_at = _iso()
        self.rows = 0
        self.table_rows: dict[str, int] = {}
        self._last_log = 0.0
        self._last_write = 0.0

    def __call__(self, fq: str, n: int) -> None:
        self.rows += n
        self.table_rows[fq] = self.table_rows.get(fq, 0) + n
        now = time.monotonic()
        if now - self._last_write > 10:
            self._last_write = now
            elapsed = now - self.started
            paused = self.src.throttle.paused_s if self.src else 0.0
            rate = self.rows / max(elapsed, 1e-6)
            _atomic_write_text(self.dest / "progress.json", json.dumps({
                "started_at": self.started_at, "now": _iso(), "table": fq,
                "table_rows": self.table_rows[fq], "rows_pulled": self.rows,
                "estimated_total_rows": self.total_est, "elapsed_s": round(elapsed),
                "paused_s": round(paused), "rows_per_s_wall": round(rate),
                "rows_per_s_reading": round(self.rows / max(elapsed - paused, 1e-6)),
            }, indent=1))
        if now - self._last_log > 60:
            self._last_log = now
            elapsed = now - self.started
            self.log(f"progress: {self.rows:,} rows pulled ({100 * self.rows / self.total_est:.1f}% "
                     f"of ~{self.total_est:,}), {self.rows / max(elapsed, 1e-6):,.0f} rows/s wall; "
                     f"now {fq} at {self.table_rows[fq]:,}")


def cmd_run(args) -> int:
    dest = Path(args.dest)
    log = Logger(Path(args.log_file) if args.log_file else None)
    url = read_env_value("DATABASE_URL", Path(args.env_file) if args.env_file else None)
    if not url:
        log("DATABASE_URL is not set and is not in the env file; nothing to do")
        return 2
    with single_run_lock(dest):
        log(f"local mirror run starting; destination {dest}")
        src = PgSource(url, log=log, throttle_kw={"sleep_s": args.sleep, "max_active": args.max_active})
        run_ts = _utcnow().strftime("%Y%m%dT%H%M%SZ")
        state: dict[str, Any] = {"run_started_at": _iso(), "run_id": run_ts}
        if not args.skip_schema:
            try:
                state["schema"] = dump_schema(src, dest / "schema" / run_ts, log)
                _atomic_write_text(dest / "schema" / "LATEST.txt", run_ts + "\n")
            except Exception as exc:  # noqa: BLE001
                log(f"schema dump FAILED: {scrub(exc)}")
                state["schema_error"] = scrub(exc)
        if not args.skip_storage:
            try:
                env_file = Path(args.env_file) if args.env_file else None
                key = read_env_value("SUPABASE_SERVICE_ROLE_KEY", env_file)
                rep = mirror_storage(src, dest, project_url(url, env_file), key, log)
                state["storage"] = {k: v for k, v in rep.items() if k != "objects"}
            except Exception as exc:  # noqa: BLE001
                log(f"storage mirror FAILED: {scrub(exc)}")
                state["storage_error"] = scrub(exc)

        tables = _select(src.list_tables(), args.only or [], args.exclude or [])
        for t in tables:
            if t.est_rows < 0:  # never analysed: small, so count it exactly
                t.est_rows = src.exact_count(t)
        total_est = sum(max(t.est_rows, 0) for t in tables)
        log(f"{len(tables)} tables, ~{total_est:,} rows by the planner's estimate")
        progress = Progress(dest, total_est, log, src)
        mirror = Mirror(src, dest, log=log, batch_rows=args.batch_rows,
                        full_copy_below=args.full_copy_below, rotate_days=args.rotate_days,
                        hot_chunks=args.hot_chunks, progress=progress)
        _atomic_write_text(dest / "tables_inventory.json", json.dumps(
            [{"table": t.fq, "est_rows": t.est_rows, "table_bytes": t.table_bytes,
              "total_bytes": t.total_bytes, "key_columns": t.pk, "mode": mirror.mode_for(t)}
             for t in tables], indent=1))
        results: list[TableResult] = []
        for t in tables:
            try:
                r = mirror.sync_table(t)
                log(f"{t.fq}: {r.mode} pass done: {r.local_rows:,} rows local, "
                    f"{r.pulled_rows:,} pulled, {r.repulled} range(s) re-pulled, {r.seconds:,.0f}s")
                if not args.no_verify:
                    v = mirror.verify_table(t)
                    v.pulled_rows, v.repulled, v.seconds = r.pulled_rows, r.repulled, r.seconds
                    r = v
                    log(f"{t.fq}: verify local {v.local_rows:,} vs supabase {v.server_rows:,} "
                        f"in copied ranges, {v.tail_new:,} newer keys, {v.mismatched} range(s) differ")
            except Exception as exc:  # noqa: BLE001
                log(f"{t.fq}: FAILED {scrub(exc)}\n{scrub(traceback.format_exc())}")
                r = TableResult(t.fq, mirror.mode_for(t), error=scrub(exc)[:300])
            results.append(r)
        report = _fmt_table(results)
        (dest / "verify").mkdir(parents=True, exist_ok=True)
        with open(dest / "verify" / f"{run_ts}.txt", "w", encoding="utf-8") as fh:
            fh.write(report + "\n")
        log("verification, local vs Supabase:\n" + report)
        state.update({"run_finished_at": _iso(), "tables": len(results),
                      "failed_tables": [r.fq for r in results if r.error],
                      "mismatched_tables": [r.fq for r in results
                                            if r.server_rows is not None and r.server_rows != r.local_rows],
                      "rows_pulled": progress.rows, "db_seconds": round(src.db_seconds),
                      "paused_seconds": round(src.throttle.paused_s)})
        _atomic_write_text(dest / "STATE.json", json.dumps(state, indent=1, default=str))
        log(f"run finished: {progress.rows:,} rows pulled; "
            f"{len(state['failed_tables'])} failed, {len(state['mismatched_tables'])} with differences")
        return 1 if state["failed_tables"] else 0


def cmd_verify(args) -> int:
    dest = Path(args.dest)
    log = Logger(Path(args.log_file) if args.log_file else None)
    url = read_env_value("DATABASE_URL", Path(args.env_file) if args.env_file else None)
    if not url:
        log("DATABASE_URL is not set")
        return 2
    src = PgSource(url, log=log, throttle_kw={"sleep_s": args.sleep, "max_active": args.max_active})
    mirror = Mirror(src, dest, log=log)
    results = []
    for t in _select(src.list_tables(), args.only or [], args.exclude or []):
        try:
            results.append(mirror.verify_table(t))
        except Exception as exc:  # noqa: BLE001
            results.append(TableResult(t.fq, "?", error=scrub(exc)[:300]))
    print(_fmt_table(results))
    return 0


def cmd_status(args) -> int:
    dest = Path(args.dest)
    rows = []
    for p in sorted((dest / "tables").glob("*/manifest.json")):
        with open(p, encoding="utf-8") as fh:
            m = json.load(fh)
        lv = m.get("last_verify") or {}
        rows.append((m["table"], m["mode"], m.get("rows", 0), m.get("bytes", 0),
                     m.get("chunk_count", 0), m.get("last_run"), m.get("last_full_reconcile"),
                     lv.get("mismatched_chunks")))
    print(f"{'table':<52} {'mode':<11} {'rows':>13} {'MB':>9} {'chunks':>7}  last run              "
          f"  last full reconcile   differing")
    for r in rows:
        print(f"{r[0]:<52} {r[1]:<11} {r[2]:>13,} {r[3] / 1e6:>9.1f} {r[4]:>7}  {str(r[5]):<22}  "
              f"{str(r[6]):<22} {'' if r[7] is None else r[7]}")
    print(f"{len(rows)} tables, {sum(r[2] for r in rows):,} rows, {sum(r[3] for r in rows) / 1e9:.2f} GB")
    return 0


def cmd_export_csv(args) -> int:
    """One table as a CSV that Postgres' COPY ... CSV HEADER reads back exactly."""
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.csv as pacsv
    store = TableDir(Path(args.dest), args.table)
    m = store.load()
    if not m:
        print(f"no local copy of {args.table}")
        return 2
    out = Path(args.out)
    writer = None
    try:
        for c in m["chunks"]:
            if not c.get("file"):
                continue
            import pyarrow.parquet as pq
            t = pq.read_table(store.dir / c["file"])
            cols = []
            for f, col in zip(t.schema, t.columns):
                if pa.types.is_binary(f.type):
                    col = pa.array([("\\x" + v.hex()) if v is not None else None
                                    for v in col.to_pylist()], type=pa.string())
                elif pa.types.is_timestamp(f.type) and f.type.tz:
                    # Arrow's %S already carries the microseconds.
                    col = pc.strftime(col, format="%Y-%m-%d %H:%M:%S+00")
                cols.append(col)
            t = pa.Table.from_arrays(cols, names=t.schema.names)
            if writer is None:
                writer = pacsv.CSVWriter(out, t.schema, write_options=pacsv.WriteOptions(
                    include_header=True, quoting_style="all_valid"))
            writer.write_table(t)
    finally:
        if writer is not None:
            writer.close()
    print(f"wrote {m['rows']:,} rows of {args.table} to {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--dest", default=str(DEFAULT_DEST))
        p.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
        p.add_argument("--log-file", default=None)
        p.add_argument("--only", action="append", help="table glob (schema.table or table); repeatable")
        p.add_argument("--exclude", action="append")
        p.add_argument("--sleep", type=float, default=SLEEP_S)
        p.add_argument("--max-active", type=int, default=MAX_ACTIVE_OTHERS)

    p = sub.add_parser("run")
    common(p)
    p.add_argument("--skip-schema", action="store_true")
    p.add_argument("--skip-storage", action="store_true")
    p.add_argument("--no-verify", action="store_true")
    p.add_argument("--batch-rows", type=int, default=BATCH_ROWS)
    p.add_argument("--full-copy-below", type=int, default=FULL_COPY_BELOW)
    p.add_argument("--rotate-days", type=float, default=ROTATE_DAYS)
    p.add_argument("--hot-chunks", type=int, default=HOT_CHUNKS)
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("verify")
    common(p)
    p.set_defaults(fn=cmd_verify)
    p = sub.add_parser("status")
    p.add_argument("--dest", default=str(DEFAULT_DEST))
    p.set_defaults(fn=cmd_status)
    p = sub.add_parser("export-csv")
    p.add_argument("--dest", default=str(DEFAULT_DEST))
    p.add_argument("--table", required=True, help="schema.table")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_export_csv)
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001
        print(f"{_iso()} FATAL {scrub(exc)}\n{scrub(traceback.format_exc())}", flush=True)
        return 3


if __name__ == "__main__":
    sys.exit(main())
