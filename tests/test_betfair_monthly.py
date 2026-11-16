"""The daily Betfair ANZ store: what it fetches, what it writes, and what it never does.

scripts/horse/betfair_monthly.py keeps the stored Betfair thoroughbred files
complete without a session (issue #1371). No network and no database: the
listing, the downloads and the table are faked here.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import zipfile

import pytest

from scripts.horse import betfair_monthly as bm

LISTING_HTML = """
<a href="../assets/ANZ_Thoroughbreds_2025.zip">2025</a>
<a href="../assets/ANZ_Thoroughbreds_2026_10.csv">Oct</a>
<a href='../assets/ANZ_Thoroughbreds_2026_11.csv'>Nov</a>
<a href="../assets/ANZ_Greyhounds_2026_11.csv">dogs</a>
<a href="../assets/ANZ_Harness_2026_11.csv">harness</a>
<a href="../assets/ANZ_Thoroughbreds_2026_11.csv">Nov again</a>
"""
BASE = "https://betfair-datascientists.github.io/data/assets/"


class FakeConn:
    """Enough of the table for the job: rel_path unique, insert-or-nothing."""

    def __init__(self, rows: dict[str, bytes] | None = None):
        self.rows = {}
        for rel, raw in (rows or {}).items():
            self.rows[rel] = (hashlib.sha256(raw).hexdigest(), len(raw), gzip.compress(raw))
        self.sql: list[str] = []

    def execute(self, sql, params=()):
        self.sql.append(sql)
        conn = self

        class Cur:
            def fetchall(self_inner):
                return [(r, s, n) for r, (s, n, _) in conn.rows.items()]

            def fetchone(self_inner):
                r = conn.rows.get(params[0])
                return None if r is None else (r[0], r[2])

        if sql.startswith("INSERT"):
            rel, source, sha, nraw, ngz, gz = params
            assert source == bm.SOURCE
            if rel not in self.rows:                   # ON CONFLICT DO NOTHING
                self.rows[rel] = (sha, nraw, bytes(gz))
        return Cur()

    def commit(self):
        pass


def _zip(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, raw in members.items():
            z.writestr(name, raw)
    return buf.getvalue()


def _run(conn, downloads: dict[str, bytes], sizes: dict[str, int | None] | None = None):
    fetched = []

    def get_bytes(url):
        fetched.append(url.rsplit("/", 1)[-1])
        return downloads[url.rsplit("/", 1)[-1]]

    out = bm.run(conn, get_text=lambda url: LISTING_HTML, get_bytes=get_bytes,
                 get_size=lambda url: (sizes or {}).get(url.rsplit("/", 1)[-1]),
                 say=lambda *_: None)
    return out, fetched


def test_the_listing_names_each_thoroughbred_file_once_with_its_full_address():
    got = bm.listed_files(LISTING_HTML)
    assert [f["name"] for f in got] == ["ANZ_Thoroughbreds_2025.zip", "ANZ_Thoroughbreds_2026_10.csv",
                                        "ANZ_Thoroughbreds_2026_11.csv"]
    assert got[2]["url"] == BASE + "ANZ_Thoroughbreds_2026_11.csv"
    assert [f["kind"] for f in got] == ["zip", "csv", "csv"]


def test_a_new_month_is_stored_and_a_stored_month_is_not_fetched():
    oct_raw, nov_raw = b"oct rows\n", b"nov rows\n"
    conn = FakeConn({
        "horse/betfair-ANZ_Thoroughbreds_2025.zip/ANZ_Thoroughbreds_2025_01.csv": b"jan",
        "horse/betfair-ANZ_Thoroughbreds_2026_10.csv/ANZ_Thoroughbreds_2026_10.csv": oct_raw,
    })
    out, fetched = _run(conn, {"ANZ_Thoroughbreds_2026_11.csv": nov_raw},
                        sizes={"ANZ_Thoroughbreds_2026_10.csv": len(oct_raw)})
    assert fetched == ["ANZ_Thoroughbreds_2026_11.csv"]
    rel = "horse/betfair-ANZ_Thoroughbreds_2026_11.csv/ANZ_Thoroughbreds_2026_11.csv"
    assert conn.rows[rel][0] == hashlib.sha256(nov_raw).hexdigest()
    assert out["written"] == 1
    # a second run finds nothing to do
    out2, fetched2 = _run(conn, {}, sizes={"ANZ_Thoroughbreds_2026_10.csv": len(oct_raw),
                                           "ANZ_Thoroughbreds_2026_11.csv": len(nov_raw)})
    assert fetched2 == [] and out2["written"] == 0


def test_a_republished_month_is_stored_beside_the_old_one_and_never_overwrites_it():
    old, new = b"oct rows\n", b"oct rows, corrected\n"
    rel = "horse/betfair-ANZ_Thoroughbreds_2026_10.csv/ANZ_Thoroughbreds_2026_10.csv"
    conn = FakeConn({rel: old,
                     "horse/betfair-ANZ_Thoroughbreds_2025.zip/ANZ_Thoroughbreds_2025_01.csv": b"jan",
                     "horse/betfair-ANZ_Thoroughbreds_2026_11.csv/ANZ_Thoroughbreds_2026_11.csv": b"nov"})
    out, fetched = _run(conn, {"ANZ_Thoroughbreds_2026_10.csv": new},
                        sizes={"ANZ_Thoroughbreds_2026_10.csv": len(new),
                               "ANZ_Thoroughbreds_2026_11.csv": 3})
    assert fetched == ["ANZ_Thoroughbreds_2026_10.csv"]
    assert conn.rows[rel][0] == hashlib.sha256(old).hexdigest()          # the old row is untouched
    versioned = f"{rel}#v{hashlib.sha256(new).hexdigest()[:12]}"
    assert conn.rows[versioned][0] == hashlib.sha256(new).hexdigest()
    assert not any("DO UPDATE" in s or s.startswith(("UPDATE", "DELETE")) for s in conn.sql)
    # the next day the new size is already held, so nothing is fetched again
    _, fetched2 = _run(conn, {}, sizes={"ANZ_Thoroughbreds_2026_10.csv": len(new),
                                        "ANZ_Thoroughbreds_2026_11.csv": 3})
    assert fetched2 == []


def test_a_size_difference_with_the_same_bytes_writes_nothing():
    raw = b"oct rows\n"
    rel = "horse/betfair-ANZ_Thoroughbreds_2026_10.csv/ANZ_Thoroughbreds_2026_10.csv"
    conn = FakeConn({rel: raw,
                     "horse/betfair-ANZ_Thoroughbreds_2025.zip/ANZ_Thoroughbreds_2025_01.csv": b"jan",
                     "horse/betfair-ANZ_Thoroughbreds_2026_11.csv/ANZ_Thoroughbreds_2026_11.csv": b"nov"})
    out, fetched = _run(conn, {"ANZ_Thoroughbreds_2026_10.csv": raw},
                        sizes={"ANZ_Thoroughbreds_2026_10.csv": len(raw) + 7,   # a misleading HEAD
                               "ANZ_Thoroughbreds_2026_11.csv": 3})
    assert fetched == ["ANZ_Thoroughbreds_2026_10.csv"]
    assert out["written"] == 0 and len(conn.rows) == 3


def test_a_new_annual_zip_is_stored_as_its_monthly_members_and_a_seen_zip_is_not_fetched():
    conn = FakeConn({
        "horse/betfair-ANZ_Thoroughbreds_2026_10.csv/ANZ_Thoroughbreds_2026_10.csv": b"oct",
        "horse/betfair-ANZ_Thoroughbreds_2026_11.csv/ANZ_Thoroughbreds_2026_11.csv": b"nov",
    })
    blob = _zip({"2025/ANZ_Thoroughbreds_2025_01.csv": b"jan", "ANZ_Thoroughbreds_2025_02.csv": b"feb",
                 "readme.txt": b"not a csv"})
    out, fetched = _run(conn, {"ANZ_Thoroughbreds_2025.zip": blob},
                        sizes={"ANZ_Thoroughbreds_2026_10.csv": 3, "ANZ_Thoroughbreds_2026_11.csv": 3})
    assert fetched == ["ANZ_Thoroughbreds_2025.zip"]
    assert set(conn.rows) >= {"horse/betfair-ANZ_Thoroughbreds_2025.zip/ANZ_Thoroughbreds_2025_01.csv",
                              "horse/betfair-ANZ_Thoroughbreds_2025.zip/ANZ_Thoroughbreds_2025_02.csv"}
    assert out["written"] == 2
    _, fetched2 = _run(conn, {}, sizes={"ANZ_Thoroughbreds_2026_10.csv": 3,
                                        "ANZ_Thoroughbreds_2026_11.csv": 3})
    assert fetched2 == []


def test_a_listing_with_no_thoroughbred_file_fails_instead_of_reporting_nothing_new():
    with pytest.raises(RuntimeError, match="names no ANZ_Thoroughbreds file"):
        bm.run(FakeConn(), get_text=lambda url: "<html>moved</html>",
               get_bytes=lambda url: b"", get_size=lambda url: None, say=lambda *_: None)


def test_a_row_that_does_not_read_back_fails_the_run():
    class Corrupting(FakeConn):
        def execute(self, sql, params=()):
            cur = super().execute(sql, params)
            if sql.startswith("INSERT"):
                sha, n, _ = self.rows[params[0]]
                self.rows[params[0]] = (sha, n, gzip.compress(b"something else"))
            return cur

    conn = Corrupting({"horse/betfair-ANZ_Thoroughbreds_2025.zip/x.csv": b"x",
                       "horse/betfair-ANZ_Thoroughbreds_2026_10.csv/ANZ_Thoroughbreds_2026_10.csv": b"o"})
    with pytest.raises(RuntimeError, match="does not read back"):
        _run(conn, {"ANZ_Thoroughbreds_2026_11.csv": b"nov"},
             sizes={"ANZ_Thoroughbreds_2026_10.csv": 1})


def test_the_worker_runs_it_daily_on_the_pipeline_service():
    import scheduler
    jobs = {j.id: j for j in scheduler.build_scheduler().get_jobs()}
    job = jobs["betfair_monthly_store"]
    fields = {f.name: str(f) for f in job.trigger.fields}
    assert fields["hour"] == "10" and fields["minute"] == "43"
    assert fields["day"] == "*"
    assert "betfair_monthly_store" in scheduler._PIPELINE_JOBS


def test_the_store_can_be_queued_on_the_worker_with_only_a_dry_run_switch():
    from tracking import job_queue as jq
    assert jq.JOBS["betfair_monthly_store"][0] is jq._job_betfair_monthly_store
    assert jq._validate_betfair_monthly_store({}) == {"dry_run": False}
    assert jq._validate_betfair_monthly_store({"dry_run": True}) == {"dry_run": True}
    for bad in ({"url": "https://example.com"}, {"dry_run": "yes"}):
        with pytest.raises(ValueError):
            jq._validate_betfair_monthly_store(bad)
