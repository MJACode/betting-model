"""The local carbon copy of Supabase converges to the server, and reads politely.

scripts/local_mirror.py copies every table to mike's machine (mike,
2026-11-03: "everything should be a carbon copy on my local as a backup").
A backup that only ever appends is not a carbon copy: picks get graded, odds
rows get marked in_play, the odds prune deletes middles. These tests run the
real sync engine against an in-memory server they can change between runs,
and check the local Parquet rows equal the server's rows afterwards.

No database and no network: the fake implements the same five calls PgSource
does (fetch_page, range_summaries, tail_count, relpages/fetch_ctid_pages,
exact_count).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import os

import pytest

pa = pytest.importorskip("pyarrow")

from scripts import local_mirror as lm  # noqa: E402

UTC = dt.timezone.utc
T0 = dt.datetime(2026, 11, 3, 4, 0, tzinfo=UTC)


class Clock:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, **kw):
        self.t += dt.timedelta(**kw)


class FakeServer:
    """Rows keyed by a primary key, with the paging and range calls PgSource has."""

    def __init__(self, info: lm.TableInfo, rows: dict[tuple, tuple] | None = None,
                 page_rows: int = 7):
        self.info = info
        self.rows: dict[tuple, tuple] = dict(rows or {})
        self.heap: list[tuple] = list(self.rows.values())  # no-pk tables: insertion order
        self.page_rows = page_rows
        self.fetches = 0
        self.fail_after: int | None = None
        self.halve_once = False
        self.slow_his: set[tuple] = set()  # ranges whose check hits the statement timeout

    # helpers -------------------------------------------------------------------
    def _key(self, texts):
        if texts is None:
            return None
        return tuple(int(v) if t == "bigint" else v for v, t in zip(texts, self.info.pk_types))

    def _texts(self, key):
        return [str(v) for v in key]

    @staticmethod
    def _hash(row):
        h = int(hashlib.md5(repr(row).encode()).hexdigest()[:16], 16)
        return h - (1 << 64) if h >= (1 << 63) else h

    def _between(self, lo, hi):
        lo, hi = self._key(lo), self._key(hi)
        return [k for k in sorted(self.rows)
                if (lo is None or k > lo) and (hi is None or k <= hi)]

    def _page(self, rows, last_key, limit):
        cols = [list(c) for c in zip(*rows)] if rows else [[] for _ in self.info.columns]
        return lm.Page(cols, len(rows), last_key, lm.xor_all(self._hash(r) for r in rows), limit)

    # the PgSource surface -------------------------------------------------------
    def fetch_page(self, info, lo, hi, limit):
        self.fetches += 1
        if self.fail_after is not None and self.fetches > self.fail_after:
            raise RuntimeError("connection dropped (simulated)")
        if self.halve_once:
            self.halve_once = False
            limit = max(1, limit // 2)
        keys = self._between(lo, hi)[:limit]
        rows = [self.rows[k] for k in keys]
        return self._page(rows, self._texts(keys[-1]) if keys else None, limit)

    def range_summaries(self, info, lo, his, with_hash):
        out = []
        prev = lo
        for h in his:
            keys = self._between(prev, h)
            hsh = lm.xor_all(self._hash(self.rows[k]) for k in keys) if with_hash else None
            # PgSource returns None for a range whose check timed out on its own.
            out.append(None if tuple(h) in self.slow_his else (len(keys), hsh))
            prev = h
        return out

    def tail_count(self, info, lo):
        return len(self._between(lo, None))

    def exact_count(self, info):
        return len(self.heap) if not info.pk else len(self.rows)

    def relpages(self, info):
        return -(-len(self.heap) // self.page_rows)

    def fetch_ctid_pages(self, info, page_lo, page_hi):
        start = page_lo * self.page_rows
        end = None if page_hi is None else page_hi * self.page_rows
        rows = self.heap[start:end]
        return self._page(rows, None, 0)

    # mutations ----------------------------------------------------------------------
    def put(self, key, value):
        self.rows[key] = key + (value,)

    def delete(self, key):
        del self.rows[key]


def table(pk=("a", "b"), pk_types=("bigint", "text"), est_rows=10_000_000, extra=()):
    cols = [lm.Column("a", "bigint", "int64"), lm.Column("b", "text", "string"),
            lm.Column("v", "text", "string")] + list(extra)
    return lm.TableInfo("public", "t", cols, list(pk), list(pk_types), est_rows=est_rows)


def seeded(n=47, info=None):
    info = info or table()
    rows = {(i, f"k{i:03d}"): (i, f"k{i:03d}", f"v{i}") for i in range(1, n + 1)}
    return FakeServer(info, rows)


def mirror(src, root, clock=None, **kw):
    kw.setdefault("batch_rows", 10)
    kw.setdefault("hot_chunks", 0)
    kw.setdefault("rotate_days", 7)
    kw.setdefault("count_group", 3)
    return lm.Mirror(src, root, log=lambda m: None, batch_bytes=10 ** 12,
                     clock=clock or Clock(), **kw)


def local(root, info=None):
    info = info or table()
    store = lm.TableDir(root, info.fq)
    m = store.load()
    t = store.read_rows(m)
    if t is None:
        return []
    return sorted(tuple(r.values()) for r in t.to_pylist())


def server(src):
    return sorted(src.rows.values()) if src.info.pk else sorted(src.heap)


# ------------------------------------------------------------- keyset pagination

def test_keyset_pages_cover_every_row_exactly_once(tmp_path):
    src = seeded(47)
    mirror(src, tmp_path).sync_table(src.info)
    m = lm.TableDir(tmp_path, "public.t").load()
    assert [c["rows"] for c in m["chunks"]] == [10, 10, 10, 10, 7]
    assert [c["hi"] for c in m["chunks"]] == [["10", "k010"], ["20", "k020"], ["30", "k030"],
                                              ["40", "k040"], ["47", "k047"]]
    rows = local(tmp_path)
    assert rows == server(src)
    assert len(rows) == len(set(rows)) == 47


def test_keyset_sql_compares_the_whole_key_as_one_row():
    info = table()
    sql, params = lm.page_sql(info, ["10", "k010"], ["20", "k020"])
    assert '(__m."a", __m."b") > (%s::bigint, %s::text)' in sql
    assert '(__m."a", __m."b") <= (%s::bigint, %s::text)' in sql
    assert sql.rstrip().endswith('ORDER BY __m."a", __m."b" LIMIT %s')
    assert params == ["10", "k010", "20", "k020"]
    sql, params = lm.page_sql(info, None, None)
    assert "WHERE" not in sql and params == []


def test_a_halved_batch_does_not_end_the_range_early(tmp_path):
    """A statement timeout halves the batch. Fewer rows than asked for must then
    mean 'smaller page', not 'end of table'."""
    src = seeded(47)
    src.halve_once = True
    mirror(src, tmp_path).sync_table(src.info)
    assert local(tmp_path) == server(src)


def test_rows_added_after_the_copy_are_appended(tmp_path):
    src = seeded(47)
    mm = mirror(src, tmp_path)
    mm.sync_table(src.info)
    for i in range(48, 61):
        src.put((i, f"k{i:03d}"), f"v{i}")
    mm.sync_table(src.info)
    assert local(tmp_path) == server(src)
    m = lm.TableDir(tmp_path, "public.t").load()
    assert m["watermark"] == ["60", "k060"]


# ------------------------------------------------------------- update / delete convergence

def test_a_row_deleted_from_an_old_range_is_deleted_locally(tmp_path):
    """The odds prune removes unchanged middles. A count per range finds it."""
    src = seeded(47)
    mm = mirror(src, tmp_path)
    mm.sync_table(src.info)
    src.delete((15, "k015"))
    src.delete((33, "k033"))
    res = mm.sync_table(src.info)
    assert res.repulled == 2
    assert local(tmp_path) == server(src)


def test_a_row_inserted_into_the_middle_of_a_composite_key_is_copied(tmp_path):
    src = seeded(47)
    mm = mirror(src, tmp_path)
    mm.sync_table(src.info)
    src.put((15, "k015x"), "new")  # sorts between (15,'k015') and (16,'k016')
    mm.sync_table(src.info)
    assert local(tmp_path) == server(src)


def test_an_update_in_an_old_range_converges_when_its_range_is_hashed(tmp_path):
    """A graded pick keeps its key and its row count; only the hash sees it."""
    clock = Clock()
    src = seeded(47)
    mm = mirror(src, tmp_path, clock=clock, rotate_days=1)
    mm.sync_table(src.info)
    src.put((25, "k025"), "graded WIN")
    mm.sync_table(src.info)
    assert local(tmp_path) != server(src), "a count alone cannot see an update"
    clock.advance(days=2)  # every chunk's hash is now due
    mm.sync_table(src.info)
    assert local(tmp_path) == server(src)


def test_rolling_hash_reaches_every_chunk_within_the_rotation(tmp_path):
    clock = Clock()
    src = seeded(47)
    mm = mirror(src, tmp_path, clock=clock, rotate_days=5)
    mm.sync_table(src.info)
    for i in (5, 15, 25, 35, 45):
        src.put((i, f"k{i:03d}"), "changed")
    clock.advance(days=6)
    for _ in range(5):  # five runs of 1/5 of the chunks each
        mm.sync_table(src.info)
        clock.advance(days=1)
    assert local(tmp_path) == server(src)


def test_an_insert_and_a_delete_in_one_range_are_caught_by_the_hash(tmp_path):
    clock = Clock()
    src = seeded(47)
    mm = mirror(src, tmp_path, clock=clock, rotate_days=1)
    mm.sync_table(src.info)
    src.delete((12, "k012"))
    src.put((12, "k012b"), "moved")  # same range, same count
    clock.advance(days=2)
    mm.sync_table(src.info)
    assert local(tmp_path) == server(src)


def test_the_newest_chunks_are_hashed_every_run(tmp_path):
    """Recent odds get marked in_play and recent picks get graded: the newest
    chunks are hashed on every run, not once a rotation."""
    src = seeded(47)
    mm = mirror(src, tmp_path, hot_chunks=1)
    mm.sync_table(src.info)
    src.put((46, "k046"), "in_play")
    mm.sync_table(src.info)
    assert local(tmp_path) == server(src)


def test_small_tables_are_copied_whole_every_run(tmp_path):
    info = table(est_rows=100)
    src = seeded(47, info)
    mm = mirror(src, tmp_path, full_copy_below=2_000_000)
    mm.sync_table(info)
    before = set(os.listdir(lm.TableDir(tmp_path, info.fq).dir))
    src.put((3, "k003"), "updated")
    src.delete((40, "k040"))
    src.put((2, "k002a"), "inserted")
    res = mm.sync_table(info)
    assert res.mode == "full"
    assert local(tmp_path) == server(src)
    after = set(os.listdir(lm.TableDir(tmp_path, info.fq).dir))
    assert not (before - {"manifest.json"}) & after, "the old chunk files are removed"


# ------------------------------------------------------------- the copy never deletes
# CLAUDE.md §1b (mike, 2026-11-14): "the archive and the PC copy never delete".
# The chunks still converge to Supabase; rows that left it are kept beside them.

def vanished(root, info=None):
    import pyarrow.parquet as pq
    info = info or table()
    d = lm.TableDir(root, info.fq).dir / lm.VANISHED_DIR
    if not d.exists():
        return []
    rows = []
    for p in sorted(d.glob("*.parquet")):
        rows += [tuple(r.values()) for r in pq.read_table(p).to_pylist()]
    return sorted(rows)


def test_rows_deleted_upstream_are_kept_beside_the_copy(tmp_path):
    src = seeded(47)
    mm = mirror(src, tmp_path)
    mm.sync_table(src.info)
    src.delete((15, "k015"))
    src.delete((33, "k033"))
    res = mm.sync_table(src.info)
    assert local(tmp_path) == server(src), "the copy still matches Supabase"
    assert vanished(tmp_path) == [(15, "k015", "v15"), (33, "k033", "v33")]
    assert res.vanished == 2


def test_a_small_table_keeps_rows_deleted_upstream(tmp_path):
    info = table(est_rows=100)
    src = seeded(47, info)
    mm = mirror(src, tmp_path, full_copy_below=2_000_000)
    mm.sync_table(info)
    src.delete((40, "k040"))
    src.put((3, "k003"), "updated")
    res = mm.sync_table(info)
    assert res.mode == "full"
    assert local(tmp_path) == server(src)
    assert vanished(tmp_path) == [(40, "k040", "v40")], "an update is not a deletion"


def test_an_update_alone_keeps_nothing(tmp_path):
    clock = Clock()
    src = seeded(47)
    mm = mirror(src, tmp_path, clock=clock, rotate_days=1)
    mm.sync_table(src.info)
    src.put((25, "k025"), "graded WIN")
    clock.advance(days=2)
    mm.sync_table(src.info)
    assert local(tmp_path) == server(src)
    assert vanished(tmp_path) == []


def test_the_latest_line_caches_keep_no_vanished_rows(tmp_path):
    """latest_odds / latest_prop_odds are rebuilt from the odds tables: a cache,
    not a record, and their churn would fill the disk."""
    info = lm.TableInfo("public", "latest_odds", table().columns, ["a", "b"],
                        ["bigint", "text"], est_rows=10_000_000)
    src = seeded(47, info)
    mm = mirror(src, tmp_path, kind="full")  # the monthly full is what copies them
    mm.sync_table(info)
    src.delete((5, "k005"))
    mm.sync_table(info)
    assert local(tmp_path, info) == server(src)
    assert vanished(tmp_path, info) == []


def test_a_table_without_a_primary_key_is_copied_by_heap_pages(tmp_path):
    info = table(pk=(), pk_types=(), est_rows=47)
    src = seeded(47, info)
    mm = mirror(src, tmp_path)
    mm.sync_table(info)
    assert local(tmp_path, info) == server(src)
    src.heap = src.heap[5:] + [(99, "k099", "late")]
    mm.sync_table(info)
    assert local(tmp_path, info) == server(src)


def test_a_column_change_repulls_every_chunk(tmp_path):
    src = seeded(47)
    mm = mirror(src, tmp_path)
    mm.sync_table(src.info)
    info2 = table(extra=[lm.Column("w", "text", "string")])
    src.info = info2
    src.rows = {k: v + ("w",) for k, v in src.rows.items()}
    mm.sync_table(info2)
    assert local(tmp_path, info2) == server(src)
    m = lm.TableDir(tmp_path, "public.t").load()
    assert {c["sig"] for c in m["chunks"]} == {info2.signature()}


# ------------------------------------------------------------- manifest and resume

def test_the_manifest_records_rows_keys_watermark_bytes_and_reconcile(tmp_path):
    src = seeded(47)
    mirror(src, tmp_path).sync_table(src.info)
    m = lm.TableDir(tmp_path, "public.t").load()
    assert m["rows"] == 47
    assert m["key_columns"] == ["a", "b"]
    assert m["watermark"] == ["47", "k047"]
    assert m["bytes"] == sum(os.path.getsize(lm.TableDir(tmp_path, "public.t").dir / c["file"])
                             for c in m["chunks"])
    assert m["last_full_reconcile"]


def test_an_interrupted_copy_resumes_without_duplicates(tmp_path):
    src = seeded(47)
    src.fail_after = 2
    mm = mirror(src, tmp_path)
    with pytest.raises(RuntimeError):
        mm.sync_table(src.info)
    m = lm.TableDir(tmp_path, "public.t").load()
    assert m is not None and len(m["chunks"]) == 2, "progress was saved chunk by chunk"
    src.fail_after = None
    src.fetches = 0
    mm.sync_table(src.info)
    rows = local(tmp_path)
    assert rows == server(src) and len(rows) == len(set(rows))
    m = lm.TableDir(tmp_path, "public.t").load()
    files = {p for p in os.listdir(lm.TableDir(tmp_path, "public.t").dir) if p.endswith(".parquet")}
    assert files == {c["file"] for c in m["chunks"]}


def test_files_left_by_a_killed_run_are_removed(tmp_path):
    src = seeded(20)
    mm = mirror(src, tmp_path)
    mm.sync_table(src.info)
    d = lm.TableDir(tmp_path, "public.t").dir
    (d / "chunk_9999999.parquet").write_bytes(b"half written")
    (d / "chunk_0000003.parquet.tmp").write_bytes(b"x")
    mm.sync_table(src.info)
    assert not (d / "chunk_9999999.parquet").exists()
    assert not (d / "chunk_0000003.parquet.tmp").exists()
    assert local(tmp_path) == server(src)


def test_verify_counts_each_range_and_the_newer_keys(tmp_path):
    src = seeded(47)
    mm = mirror(src, tmp_path)
    mm.sync_table(src.info)
    src.delete((5, "k005"))
    src.put((50, "k050"), "late")
    v = mm.verify_table(src.info)
    assert (v.local_rows, v.server_rows, v.mismatched, v.tail_new) == (47, 46, 1, 1)


# ------------------------------------------------------------- read windows and load

def at(h, m, s=0):
    return dt.datetime(2026, 11, 3, h, m, s, tzinfo=UTC)


# 2026-11-03 is Eastern standard time (UTC-5): 06:00 ET is 11:00 UTC. The
# windows are Eastern: 05:40-07:15 ET (10:40-12:15 UTC here), and :15-:27 of
# every hour, overnight included.
@pytest.mark.parametrize("now,wait_until", [
    (at(10, 38), None),            # morning window opens in 120 s, more than the margin
    (at(10, 39), at(12, 28)),      # opens in 60 s; it ends 07:16 ET and 07:15-07:27 follows
    (at(11, 0), at(12, 28)),       # the 6am ET daily: closed (the old UTC window missed it)
    (at(12, 27, 59), at(12, 28)),
    (at(12, 28), None),
    (at(14, 15), at(14, 28)),      # 09:15 ET, a refresh pass
    (at(14, 13, 50), at(14, 28)),  # :15 opens in 70 s
    (at(8, 20), at(8, 28)),        # 03:20 ET: the overnight passes are covered now
    (at(4, 15), at(4, 28)),        # 23:15 ET
    (at(8, 30), None),
    (at(10, 0), None),             # 05:00 ET is open: the old summer window is gone
])
def test_reads_wait_for_the_pipeline_and_refresh_windows(now, wait_until):
    wait = lm.seconds_until_reads_allowed(now, margin_s=75)
    expected = 0 if wait_until is None else (wait_until - now).total_seconds()
    assert wait == expected


def test_the_windows_follow_eastern_time_through_the_clock_change():
    """In summer (EDT, UTC-4) the same Eastern windows sit an hour earlier in UTC."""
    summer = dt.datetime(2026, 7, 1, 9, 45, tzinfo=UTC)          # 05:45 EDT
    assert lm.seconds_until_reads_allowed(summer, margin_s=0) == (
        dt.datetime(2026, 7, 1, 11, 28, tzinfo=UTC) - summer).total_seconds()
    assert lm.seconds_until_reads_allowed(dt.datetime(2026, 7, 1, 9, 39, tzinfo=UTC), margin_s=0) == 0


def test_no_margin_means_the_last_second_before_a_window_is_open():
    assert lm.seconds_until_reads_allowed(at(10, 39, 59), margin_s=0) == 0
    assert lm.seconds_until_reads_allowed(at(10, 40, 0), margin_s=0) == 108 * 60


def _throttle(probe_values, start):
    clock = Clock(start)
    slept = []
    values = iter(probe_values)

    def sleeper(s):
        slept.append(s)
        clock.advance(seconds=s)
    th = lm.Throttle(lambda: next(values), log=lambda m: None, clock=clock, sleeper=sleeper)
    return th, slept, clock


def test_reads_pause_while_more_than_six_other_sessions_are_active():
    th, slept, _ = _throttle([7, 9, 6], at(4, 0))
    th.wait()
    assert slept == [20.0, 20.0]
    th, slept, _ = _throttle([6], at(4, 0))
    th.wait()
    assert slept == []


def test_reads_pause_through_the_6am_pipeline_window():
    # 05:50 ET in winter: closed until 07:28 ET (the morning window, then the
    # 07:15-07:27 refresh window), which is 12:28 UTC.
    th, slept, clock = _throttle([0], at(10, 50))
    th.wait()
    assert clock() == at(12, 28)
    assert th.paused_s == 98 * 60


# ------------------------------------------------------------- secrets

def test_database_urls_never_reach_a_log_line():
    msg = 'connection to "postgresql://postgres.ref:s3cret@aws-1.pooler.supabase.com:6543/postgres" failed'
    out = lm.scrub(msg)
    assert "s3cret" not in out and "<database-url>" in out


def test_the_env_file_is_read_at_run_time(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    env = tmp_path / ".env"
    env.write_bytes(b'ODDS_API_KEY=abc\r\nDATABASE_URL="postgresql://u:p@h:5432/d"\r\n')
    assert lm.read_env_value("DATABASE_URL", env) == "postgresql://u:p@h:5432/d"
    monkeypatch.setenv("DATABASE_URL", "postgresql://from-env")
    assert lm.read_env_value("DATABASE_URL", env) == "postgresql://from-env"
    assert lm.read_env_value("MISSING", env) is None


# ------------------------------------------------------------- restore

def test_export_csv_writes_what_postgres_copy_reads_back(tmp_path):
    """The restore path: one table to a CSV for `COPY ... CSV HEADER`.
    NULL is an unquoted empty field, an empty string is "", a timestamp keeps
    its microseconds and its UTC offset, and bytea is Postgres hex."""
    import csv
    cols = [lm.Column("a", "bigint", "int64"), lm.Column("b", "text", "string"),
            lm.Column("ts", "timestamp with time zone", "timestamp_us_utc"),
            lm.Column("blob", "bytea", "binary")]
    info = lm.TableInfo("public", "t", cols, ["a"], ["bigint"], est_rows=10)
    stamp = dt.datetime(2026, 11, 3, 18, 0, 48, 123456, tzinfo=UTC)
    rows = {(1,): (1, 'say "hi"', stamp, b"\x00\xff"), (2,): (2, "", None, None),
            (3,): (3, None, stamp, b"")}
    src = FakeServer(info, rows)
    mirror(src, tmp_path).sync_table(info)
    out = tmp_path / "t.csv"
    assert lm.main(["export-csv", "--dest", str(tmp_path), "--table", "public.t",
                    "--out", str(out)]) == 0
    raw = out.read_text(encoding="utf-8").splitlines()
    assert raw[0] == '"a","b","ts","blob"'
    assert raw[1] == r'"1","say ""hi""","2026-11-03 18:00:48.123456+00","\x00ff"'
    assert raw[2] == '"2","",,', "empty string quoted, NULLs bare"
    assert raw[3] == r'"3",,"2026-11-03 18:00:48.123456+00","\x"'
    assert len(list(csv.reader(out.open(encoding="utf-8", newline="")))) == 4


# ------------------------------------------------------------- statement timeouts

def test_a_range_check_that_times_out_is_copied_again_not_failed(tmp_path):
    """A cold range can take longer than the 60 s limit to count or hash. That
    must mean 'copy it again' (the copy halves its batch until it fits), not
    'fail the table', or the same range would fail it on every run."""
    clock = Clock()
    src = seeded(47)
    mm = mirror(src, tmp_path, clock=clock, rotate_days=1)
    mm.sync_table(src.info)
    src.put((25, "k025"), "graded")       # an edit inside the slow range
    src.delete((14, "k014"))              # a delete inside another slow range
    src.slow_his = {("30", "k030"), ("20", "k020")}
    clock.advance(days=2)                 # (20,30] is hashed, (10,20] only counted
    res = mm.sync_table(src.info)
    assert res.repulled >= 2
    assert local(tmp_path) == server(src)
    v = mm.verify_table(src.info)
    assert v.unchecked == 2 and v.error is None


def test_a_page_of_huge_rows_halves_down_to_one_row_before_failing(monkeypatch):
    """2026-11-15: 34 rows of 33.6 MB each (the UK/Ireland racing zip, in
    parts) went into nfl_research_data_backup. Its average row size gave a
    100-row batch, the batch hit the statement timeout, and the retry floor
    (500 rows) sat above it, so the copy failed outright instead of halving.
    A page must keep halving until one row fits, and fail only on one row."""
    ext = pytest.importorskip("psycopg2.extensions")
    monkeypatch.setattr(lm, "page_sql", lambda info, lo, hi: ("SELECT", []))
    monkeypatch.setattr(lm, "_page_from_rows", lambda info, rows, n_keys: lm.Page([], len(rows), None, 0))
    src = lm.PgSource.__new__(lm.PgSource)
    src.log = lambda m: None
    src._conn_obj = None
    src._reset = lambda: None
    asked = []

    class Cur:
        def execute(self, sql, params):
            self.limit = params[-1]
            asked.append(self.limit)

        def fetchall(self):
            if self.limit > 1:
                raise ext.QueryCanceledError("canceling statement due to statement timeout")
            return [("row",)]

    src._run = lambda fn, **kw: fn(Cur())
    info = lm.TableInfo("public", "t", [], ["id"], ["bigint"])
    page = src.fetch_page(info, None, None, 100)
    assert page.limit == 1
    assert asked == [100, 50, 25, 12, 6, 3, 1]


def test_page_size_follows_the_rows_just_read(tmp_path):
    """After a page of huge rows the next page is one row, not the table's
    batch size again (which would time out and halve once per huge row), and
    it returns to the batch size when the rows are small again."""
    src = seeded(30)
    for i in (11, 12, 13):
        src.rows[(i, f"k{i:03d}")] = (i, f"k{i:03d}", "x" * 5000)
    asked = []
    real = src.fetch_page

    def spy(info, lo, hi, limit):
        asked.append(limit)
        return real(info, lo, hi, limit)

    src.fetch_page = spy
    mi = mirror(src, tmp_path)
    mi.batch_bytes = 2000
    mi.sync_table(src.info)
    assert local(tmp_path) == server(src)
    assert asked[0] == 10
    assert 1 in asked, asked
    assert asked[asked.index(1):].count(10) >= 1, asked


def test_pg_source_narrows_a_timed_out_check_to_the_slow_range(monkeypatch):
    """PgSource splits a group whose check timed out, and reports only the
    range that times out on its own, as None."""
    ext = pytest.importorskip("psycopg2.extensions")
    monkeypatch.setattr(lm, "summaries_sql", lambda info, lo, his, wh: ((lo, [h[0] for h in his]), []))
    src = lm.PgSource.__new__(lm.PgSource)
    src.log = lambda m: None
    src._conn_obj = None

    class Cur:
        def execute(self, sql, params):
            self.sql = sql

        def fetchone(self):
            lo, his = self.sql
            if "30" in his:
                raise ext.QueryCanceledError("canceling statement due to statement timeout")
            return tuple(7 for _ in his)

    src._run = lambda fn, **kw: fn(Cur())
    info = lm.TableInfo("public", "t", [], ["a"], ["bigint"])
    out = src.range_summaries(info, None, [["10"], ["20"], ["30"], ["40"], ["50"]], False)
    assert out == [(7, None), (7, None), None, (7, None), (7, None)]


# ------------------------------------------------------------- nightly diff, monthly full
# mike, 2026-11-19: "why is the nightly backup so big, we should just be running
# a diff and a full backup like once a month". The night of 11-19 pulled
# 35,347,926 rows: 29.8M of them were tables re-copied whole (every table under
# 2M rows, and the two latest-line caches), whether or not they had changed.

def small(name="t"):
    """A keyed table of the size that used to be re-copied whole every night."""
    return lm.TableInfo("public", name, table().columns, ["a", "b"], ["bigint", "text"], est_rows=100)


def nightly(src, root, clock=None, **kw):
    """The Mirror as the nightly run builds it: production defaults."""
    kw.setdefault("hot_chunks", lm.HOT_CHUNKS)
    kw.setdefault("full_copy_below", lm.FULL_COPY_BELOW)
    return mirror(src, root, clock=clock, kind="diff", **kw)


def test_a_nightly_diff_pulls_nothing_from_an_unchanged_small_table(tmp_path):
    src = seeded(47, small())
    mm = nightly(src, tmp_path)
    assert mm.sync_table(src.info).pulled_rows == 47
    res = mm.sync_table(src.info)
    assert res.mode == "incremental"
    assert res.pulled_rows == 0, "an unchanged table is not copied again"
    assert local(tmp_path, src.info) == server(src)


def test_a_nightly_diff_catches_an_edit_to_an_old_row_of_a_small_table(tmp_path):
    src = seeded(47, small())
    mm = nightly(src, tmp_path)
    mm.sync_table(src.info)
    src.put((3, "k003"), "graded WIN")
    res = mm.sync_table(src.info)
    assert local(tmp_path, src.info) == server(src)
    assert 0 < res.pulled_rows <= 10, "only the chunk holding the edit is copied again"


def test_a_nightly_diff_catches_a_row_inserted_mid_range_under_a_text_key(tmp_path):
    info = lm.TableInfo("public", "t", table().columns, ["b"], ["text"], est_rows=100)
    rows = {(f"k{i:03d}",): (i, f"k{i:03d}", f"v{i}") for i in range(1, 48)}
    src = FakeServer(info, rows)
    mm = nightly(src, tmp_path)
    mm.sync_table(info)
    src.rows[("k002a",)] = (99, "k002a", "inserted")
    mm.sync_table(info)
    assert local(tmp_path, info) == server(src)


def test_a_nightly_diff_keeps_a_row_deleted_from_a_small_table(tmp_path):
    src = seeded(47, small())
    mm = nightly(src, tmp_path)
    mm.sync_table(src.info)
    src.delete((40, "k040"))
    mm.sync_table(src.info)
    assert local(tmp_path, src.info) == server(src)
    assert vanished(tmp_path, src.info) == [(40, "k040", "v40")]


def cache_table():
    return lm.TableInfo("public", "latest_odds", table().columns, ["a", "b"],
                        ["bigint", "text"], est_rows=10_000_000)


def test_the_latest_line_caches_are_left_alone_by_the_nightly_diff(tmp_path):
    """They are rebuilt from the odds tables and change almost whole between
    nights (12.99M of the 34.39M rows pulled on 11-19), so a diff saves nothing
    on them. The monthly full copies them."""
    info = cache_table()
    src = seeded(47, info)
    nightly(src, tmp_path).sync_table(info)  # no copy yet: the first run makes one
    kept = local(tmp_path, info)
    src.put((5, "k005"), "moved")
    res = nightly(src, tmp_path).sync_table(info)
    assert res.mode == "skipped" and res.pulled_rows == 0
    assert local(tmp_path, info) == kept
    res = mirror(src, tmp_path, kind="full").sync_table(info)
    assert res.mode == "full"
    assert local(tmp_path, info) == server(src)


def test_the_monthly_full_checks_every_chunk_of_a_big_table(tmp_path):
    clock = Clock()
    src = seeded(47)
    mirror(src, tmp_path, clock=clock, kind="diff").sync_table(src.info)
    src.put((3, "k003"), "edited")
    mirror(src, tmp_path, clock=clock, kind="diff").sync_table(src.info)
    assert local(tmp_path) != server(src), "a diff hashes only the rotating share"
    mirror(src, tmp_path, clock=clock, kind="full").sync_table(src.info)
    assert local(tmp_path) == server(src)


def test_the_monthly_full_copies_again_a_chunk_whose_file_is_damaged(tmp_path):
    src = seeded(47)
    mirror(src, tmp_path, kind="diff").sync_table(src.info)
    store = lm.TableDir(tmp_path, src.info.fq)
    victim = store.dir / store.load()["chunks"][1]["file"]
    victim.write_bytes(b"not a parquet file")
    res = mirror(src, tmp_path, kind="full").sync_table(src.info)
    assert res.repulled == 1
    assert local(tmp_path) == server(src)


def test_auto_runs_the_full_once_a_month_and_a_diff_otherwise(tmp_path):
    et = lm.ET
    nov19 = dt.datetime(2026, 11, 19, 0, 30, tzinfo=et)
    assert lm.choose_kind("auto", tmp_path, nov19, partial=False)[0] == "full", "no full yet"
    lm.record_full(tmp_path, {"run_id": "x", "run_started_at": lm._iso(nov19)})
    assert lm.choose_kind("auto", tmp_path, nov19 + dt.timedelta(days=1), partial=False)[0] == "diff"
    nov30 = dt.datetime(2026, 11, 30, 23, 59, tzinfo=et)
    assert lm.choose_kind("auto", tmp_path, nov30, partial=False)[0] == "diff"
    dec3 = dt.datetime(2026, 12, 3, 0, 30, tzinfo=et)
    assert lm.choose_kind("auto", tmp_path, dec3, partial=False)[0] == "full", \
        "a PC that was off on the 1st runs it at its next pass"
    assert lm.choose_kind("auto", tmp_path, dec3, partial=True)[0] == "diff", \
        "a run by hand on a few tables is never the month's full"
    assert lm.choose_kind("full", tmp_path, nov19, partial=False)[0] == "full"
    assert lm.choose_kind("diff", tmp_path, dec3, partial=False)[0] == "diff"
