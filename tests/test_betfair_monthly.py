"""The daily Betfair ANZ store: what it fetches, what it writes, and what it never does.

scripts/horse/betfair_monthly.py keeps the stored Betfair thoroughbred files
complete without a session (issue #1371). No network and no database: the
listing, the downloads and the table are faked here.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone

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
NOW = datetime(2026, 12, 1, 15, 43, 0, tzinfo=timezone.utc)
STAMP = "20261201T154300Z"
ZIP25 = "horse/betfair-ANZ_Thoroughbreds_2025.zip/ANZ_Thoroughbreds_2025_01.csv"
OCT = "horse/betfair-ANZ_Thoroughbreds_2026_10.csv/ANZ_Thoroughbreds_2026_10.csv"
NOV = "horse/betfair-ANZ_Thoroughbreds_2026_11.csv/ANZ_Thoroughbreds_2026_11.csv"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class FakeConn:
    """rel_path unique, insert-or-nothing, and a real transaction: writes are
    visible to this connection at once and to the table only on commit."""

    def __init__(self, rows: dict[str, bytes] | None = None):
        self.rows = {rel: (_sha(raw), len(raw), gzip.compress(raw)) for rel, raw in (rows or {}).items()}
        self.pending: dict = {}
        self.sql: list[str] = []
        self.fail_on_insert: int | None = None        # raise on the Nth INSERT
        self.inserts = 0

    def _view(self):
        return {**self.rows, **self.pending}

    def execute(self, sql, params=()):
        self.sql.append(sql)
        view = self._view()

        class Cur:
            def fetchall(self_inner):
                return [(r, s, n) for r, (s, n, _) in view.items()]

            def fetchone(self_inner):
                r = view.get(params[0])
                return None if r is None else (r[0], r[2])

        if sql.startswith("INSERT"):
            self.inserts += 1
            if self.fail_on_insert == self.inserts:
                raise ConnectionError("the pooler dropped")
            rel, source, sha, nraw, ngz, gz = params
            assert source == bm.SOURCE
            if rel not in view:                        # ON CONFLICT DO NOTHING
                self.pending[rel] = (sha, nraw, bytes(gz))
        return Cur()

    def commit(self):
        self.rows.update(self.pending)
        self.pending = {}

    def rollback(self):
        self.pending = {}


def _zip(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, raw in members.items():
            z.writestr(name, raw)
    return buf.getvalue()


def _run(conn, downloads: dict[str, bytes], sizes: dict[str, int | None] | None = None,
         dry_run: bool = False, html: str = LISTING_HTML):
    fetched = []

    def get_bytes(url):
        fetched.append(url.rsplit("/", 1)[-1])
        return downloads[url.rsplit("/", 1)[-1]]

    out = bm.run(conn, dry_run=dry_run, get_text=lambda url: html, get_bytes=get_bytes,
                 get_size=lambda url: (sizes or {}).get(url.rsplit("/", 1)[-1]),
                 say=lambda *_: None, now=NOW)
    return out, fetched


def test_the_listing_names_each_thoroughbred_file_once_with_its_full_address():
    got = bm.listed_files(LISTING_HTML)
    assert [f["name"] for f in got] == ["ANZ_Thoroughbreds_2025.zip", "ANZ_Thoroughbreds_2026_10.csv",
                                        "ANZ_Thoroughbreds_2026_11.csv"]
    assert got[2]["url"] == BASE + "ANZ_Thoroughbreds_2026_11.csv"
    assert [f["kind"] for f in got] == ["zip", "csv", "csv"]


def test_a_new_month_is_stored_and_a_quiet_day_writes_nothing():
    oct_raw, nov_raw = b"oct rows\n", b"nov rows\n"
    conn = FakeConn({ZIP25: b"jan", OCT: oct_raw})
    out, fetched = _run(conn, {"ANZ_Thoroughbreds_2026_10.csv": oct_raw,
                               "ANZ_Thoroughbreds_2026_11.csv": nov_raw},
                        sizes={"ANZ_Thoroughbreds_2026_10.csv": len(oct_raw)})
    assert "ANZ_Thoroughbreds_2026_11.csv" in fetched
    assert conn.rows[NOV][0] == _sha(nov_raw) and out["written"] == 1
    out2, _ = _run(conn, {"ANZ_Thoroughbreds_2026_10.csv": oct_raw,
                          "ANZ_Thoroughbreds_2026_11.csv": nov_raw},
                   sizes={"ANZ_Thoroughbreds_2026_10.csv": len(oct_raw),
                          "ANZ_Thoroughbreds_2026_11.csv": len(nov_raw)})
    assert out2["written"] == 0 and len(conn.rows) == 3


def test_a_republished_month_is_a_new_version_the_study_reads_and_the_old_row_stays():
    old, new = b"oct rows\n", b"oct rows, corrected\n"
    conn = FakeConn({OCT: old, ZIP25: b"jan", NOV: b"nov"})
    out, _ = _run(conn, {"ANZ_Thoroughbreds_2026_10.csv": new, "ANZ_Thoroughbreds_2026_11.csv": b"nov"},
                  sizes={"ANZ_Thoroughbreds_2026_10.csv": len(new), "ANZ_Thoroughbreds_2026_11.csv": 3})
    assert conn.rows[OCT][0] == _sha(old)                                 # the old row is untouched
    versioned = f"horse/betfair-ANZ_Thoroughbreds_2026_10.csv/ANZ_Thoroughbreds_2026_10.v{STAMP}-{_sha(new)[:8]}.csv"
    assert conn.rows[versioned][0] == _sha(new)
    assert not any("DO UPDATE" in s or s.startswith(("UPDATE", "DELETE")) for s in conn.sql)
    # the study's reader takes the new version, and only it, for that month
    from scripts.horse.anz_study import month_files
    picked = month_files(sorted(r[len("horse/"):] for r in conn.rows))
    assert [p for p in picked if "2026_10" in p] == [versioned[len("horse/"):]]
    # the next day: the new size is held and the new bytes are stored, so nothing is written
    out2, _ = _run(conn, {"ANZ_Thoroughbreds_2026_10.csv": new, "ANZ_Thoroughbreds_2026_11.csv": b"nov"},
                   sizes={"ANZ_Thoroughbreds_2026_10.csv": len(new), "ANZ_Thoroughbreds_2026_11.csv": 3})
    assert out2["written"] == 0


def test_a_same_size_correction_to_a_newest_month_is_caught_by_the_daily_hash():
    old, new = b"nov rows\n", b"nov ROWS\n"                               # same length
    conn = FakeConn({ZIP25: b"jan", OCT: b"oct", NOV: old})
    out, fetched = _run(conn, {"ANZ_Thoroughbreds_2026_10.csv": b"oct", "ANZ_Thoroughbreds_2026_11.csv": new},
                        sizes={"ANZ_Thoroughbreds_2026_10.csv": 3, "ANZ_Thoroughbreds_2026_11.csv": len(new)})
    assert "ANZ_Thoroughbreds_2026_11.csv" in fetched and out["written"] == 1
    assert conn.rows[NOV][0] == _sha(old)


def test_a_size_difference_with_the_same_bytes_writes_nothing():
    raw = b"oct rows\n"
    conn = FakeConn({OCT: raw, ZIP25: b"jan", NOV: b"nov"})
    out, fetched = _run(conn, {"ANZ_Thoroughbreds_2026_10.csv": raw, "ANZ_Thoroughbreds_2026_11.csv": b"nov"},
                        sizes={"ANZ_Thoroughbreds_2026_10.csv": len(raw) + 7,   # a misleading HEAD
                               "ANZ_Thoroughbreds_2026_11.csv": 3})
    assert "ANZ_Thoroughbreds_2026_10.csv" in fetched
    assert out["written"] == 0 and len(conn.rows) == 3


def test_no_size_from_the_server_for_any_stored_month_fails_the_run():
    conn = FakeConn({ZIP25: b"jan", OCT: b"oct", NOV: b"nov"})
    with pytest.raises(RuntimeError, match="no size for any"):
        _run(conn, {}, sizes={})


def test_a_new_zip_skips_months_already_stored_and_keeps_a_manifest():
    conn = FakeConn({OCT: b"oct", NOV: b"nov"})
    blob = _zip({"2025/ANZ_Thoroughbreds_2025_01.csv": b"jan", "ANZ_Thoroughbreds_2025_02.csv": b"feb",
                 "ANZ_Thoroughbreds_2026_10.csv": b"oct",          # identical to the stored monthly
                 "ANZ_Thoroughbreds_2026_11.csv": b"nov, final",   # differs from the stored monthly
                 "readme.txt": b"not a csv"})
    out, _ = _run(conn, {"ANZ_Thoroughbreds_2025.zip": blob, "ANZ_Thoroughbreds_2026_10.csv": b"oct",
                         "ANZ_Thoroughbreds_2026_11.csv": b"nov"},
                  sizes={"ANZ_Thoroughbreds_2026_10.csv": 3, "ANZ_Thoroughbreds_2026_11.csv": 3})
    z = "horse/betfair-ANZ_Thoroughbreds_2025.zip/"
    assert {z + "ANZ_Thoroughbreds_2025_01.csv", z + "ANZ_Thoroughbreds_2025_02.csv"} <= set(conn.rows)
    assert z + "ANZ_Thoroughbreds_2026_10.csv" not in conn.rows       # not stored twice
    nov_v = f"horse/betfair-ANZ_Thoroughbreds_2026_11.csv/ANZ_Thoroughbreds_2026_11.v{STAMP}-{_sha(b'nov, final')[:8]}.csv"
    assert nov_v in conn.rows                                          # a new version of November
    manifest = json.loads(gzip.decompress(conn.rows[z + bm.MANIFEST][2]))
    by = {m["member"]: m for m in manifest["members"]}
    assert by["ANZ_Thoroughbreds_2026_10.csv"]["identical_to"] == OCT
    assert by["ANZ_Thoroughbreds_2026_11.csv"]["stored_as"] == nov_v
    # the study reads each month once
    from scripts.horse.anz_study import month_files
    picked = month_files(sorted(r[len("horse/"):] for r in conn.rows if r.endswith(".csv")))
    assert len(picked) == 4 and len({p.rsplit("/", 1)[-1][:25] for p in picked}) == 4
    # a seen zip is not fetched again
    _, fetched2 = _run(conn, {"ANZ_Thoroughbreds_2026_10.csv": b"oct", "ANZ_Thoroughbreds_2026_11.csv": b"nov"},
                       sizes={"ANZ_Thoroughbreds_2026_10.csv": 3, "ANZ_Thoroughbreds_2026_11.csv": 3})
    assert "ANZ_Thoroughbreds_2025.zip" not in fetched2


def test_a_file_that_fails_part_way_leaves_nothing_and_the_next_run_stores_it_whole():
    conn = FakeConn({OCT: b"oct", NOV: b"nov"})
    blob = _zip({f"ANZ_Thoroughbreds_2025_{m:02d}.csv": f"m{m}".encode() for m in range(1, 13)})
    conn.fail_on_insert = 4
    with pytest.raises(ConnectionError):
        _run(conn, {"ANZ_Thoroughbreds_2025.zip": blob, "ANZ_Thoroughbreds_2026_10.csv": b"oct",
                    "ANZ_Thoroughbreds_2026_11.csv": b"nov"},
             sizes={"ANZ_Thoroughbreds_2026_10.csv": 3, "ANZ_Thoroughbreds_2026_11.csv": 3})
    assert not any("2025.zip" in r for r in conn.rows)                 # nothing half stored
    conn.fail_on_insert = None
    out, _ = _run(conn, {"ANZ_Thoroughbreds_2025.zip": blob, "ANZ_Thoroughbreds_2026_10.csv": b"oct",
                         "ANZ_Thoroughbreds_2026_11.csv": b"nov"},
                  sizes={"ANZ_Thoroughbreds_2026_10.csv": 3, "ANZ_Thoroughbreds_2026_11.csv": 3})
    assert sum("2025.zip/ANZ" in r for r in conn.rows) == 12 and out["written"] == 13


def test_a_row_that_does_not_read_back_is_rolled_back_and_retried_next_run():
    class Corrupting(FakeConn):
        corrupt = True

        def execute(self, sql, params=()):
            cur = super().execute(sql, params)
            if sql.startswith("INSERT") and self.corrupt and params[0] in self.pending:
                sha, n, _ = self.pending[params[0]]
                self.pending[params[0]] = (sha, n, gzip.compress(b"something else"))
            return cur

    conn = Corrupting({ZIP25: b"x", OCT: b"o"})
    with pytest.raises(RuntimeError, match="does not read back"):
        _run(conn, {"ANZ_Thoroughbreds_2026_10.csv": b"o", "ANZ_Thoroughbreds_2026_11.csv": b"nov"},
             sizes={"ANZ_Thoroughbreds_2026_10.csv": 1})
    assert NOV not in conn.rows
    conn.corrupt = False
    out, _ = _run(conn, {"ANZ_Thoroughbreds_2026_10.csv": b"o", "ANZ_Thoroughbreds_2026_11.csv": b"nov"},
                  sizes={"ANZ_Thoroughbreds_2026_10.csv": 1})
    assert conn.rows[NOV][0] == _sha(b"nov") and out["written"] == 1


def test_a_dry_run_downloads_nothing_and_writes_nothing():
    conn = FakeConn({ZIP25: b"jan", OCT: b"oct"})
    out, fetched = _run(conn, {}, sizes={"ANZ_Thoroughbreds_2026_10.csv": 3}, dry_run=True)
    assert fetched == [] and out["to_fetch"] >= 1 and out["written"] == 0
    assert not any(s.startswith("INSERT") for s in conn.sql)


def test_a_file_over_the_part_size_is_split_and_restores_byte_for_byte(monkeypatch, tmp_path):
    monkeypatch.setattr(bm, "PART_BYTES", 10)
    raw = bytes(range(32))
    conn = FakeConn({ZIP25: b"jan", OCT: b"oct"})
    _run(conn, {"ANZ_Thoroughbreds_2026_10.csv": b"oct", "ANZ_Thoroughbreds_2026_11.csv": raw},
         sizes={"ANZ_Thoroughbreds_2026_10.csv": 3})
    parts = sorted(r for r in conn.rows if r.startswith(NOV))
    assert parts == [f"{NOV}#part{i:04d}of0004" for i in range(1, 5)]
    from scripts.horse import store_files

    class Reader:
        def execute(self_inner, sql, params=()):
            rows = conn.rows

            class Cur:
                def fetchall(self_c):
                    return [(r, s) for r, (s, _, _) in sorted(rows.items())]

                def fetchone(self_c):                  # restore reads content_gz alone
                    return (rows[params[0]][2],)
            return Cur()

    store_files.restore(Reader(), tmp_path)
    assert (tmp_path / NOV[len("horse/"):]).read_bytes() == raw
    # The size check sees the whole file, not one part. Two newer months make November an
    # OLDER month, so only its size can bring it back: the whole size is held, it stays put.
    dec = "horse/betfair-ANZ_Thoroughbreds_2026_12.csv/ANZ_Thoroughbreds_2026_12.csv"
    jan = "horse/betfair-ANZ_Thoroughbreds_2027_01.csv/ANZ_Thoroughbreds_2027_01.csv"
    conn.rows.update(FakeConn({dec: b"dec", jan: b"jan27"}).rows)
    html = (LISTING_HTML + '<a href="../assets/ANZ_Thoroughbreds_2026_12.csv">Dec</a>'
            '<a href="../assets/ANZ_Thoroughbreds_2027_01.csv">Jan</a>')
    downloads = {"ANZ_Thoroughbreds_2026_10.csv": b"oct", "ANZ_Thoroughbreds_2026_11.csv": raw,
                 "ANZ_Thoroughbreds_2026_12.csv": b"dec", "ANZ_Thoroughbreds_2027_01.csv": b"jan27"}
    out, fetched = _run(conn, downloads, html=html,
                        sizes={"ANZ_Thoroughbreds_2026_10.csv": 3, "ANZ_Thoroughbreds_2026_11.csv": len(raw),
                               "ANZ_Thoroughbreds_2026_12.csv": 3, "ANZ_Thoroughbreds_2027_01.csv": 5})
    assert "ANZ_Thoroughbreds_2026_11.csv" not in fetched and out["written"] == 0


def test_a_listing_with_no_thoroughbred_file_fails_instead_of_reporting_nothing_new():
    with pytest.raises(RuntimeError, match="names no ANZ_Thoroughbreds file"):
        _run(FakeConn(), {}, html="<html>moved</html>")


def test_the_study_reader_refuses_two_unversioned_copies_of_one_month():
    from scripts.horse.anz_study import month_files
    with pytest.raises(SystemExit, match="two copies"):
        month_files(["betfair-ANZ_Thoroughbreds_2026.zip/ANZ_Thoroughbreds_2026_10.csv",
                     "betfair-ANZ_Thoroughbreds_2026_10.csv/ANZ_Thoroughbreds_2026_10.csv"])


def test_the_worker_runs_it_daily_on_the_pipeline_service_and_a_failure_is_an_alert(monkeypatch):
    import scheduler
    from tracking import job_heartbeat
    jobs = {j.id: j for j in scheduler.build_scheduler().get_jobs()}
    fields = {f.name: str(f) for f in jobs["betfair_monthly_store"].trigger.fields}
    assert fields["hour"] == "10" and fields["minute"] == "43" and fields["day"] == "*"
    assert "betfair_monthly_store" in scheduler._PIPELINE_JOBS
    assert "betfair_monthly_store" in job_heartbeat.MAX_SILENCE
    monkeypatch.setattr(scheduler, "_run", lambda *a, **k: "fail")
    with pytest.raises(RuntimeError, match="exited fail"):
        scheduler.run_betfair_monthly_store()
    monkeypatch.setattr(scheduler, "_run", lambda *a, **k: "ok")
    scheduler.run_betfair_monthly_store()


def test_the_store_can_be_queued_on_the_worker_with_only_a_dry_run_switch():
    from tracking import job_queue as jq
    assert jq.JOBS["betfair_monthly_store"][0] is jq._job_betfair_monthly_store
    assert jq._validate_betfair_monthly_store({}) == {"dry_run": False}
    assert jq._validate_betfair_monthly_store({"dry_run": True}) == {"dry_run": True}
    for bad in ({"url": "https://example.com"}, {"dry_run": "yes"}):
        with pytest.raises(ValueError):
            jq._validate_betfair_monthly_store(bad)


def test_the_web_calls_go_through_requests_so_the_traffic_probe_sees_them():
    import inspect
    src = inspect.getsource(bm)
    assert "urllib.request" not in src and "requests.Session()" in src


def test_a_size_check_that_disagrees_on_every_month_with_identical_bytes_fails_the_run():
    # The 2026-11-16 trap: a compressed Content-Length made every month look changed.
    sep = "horse/betfair-ANZ_Thoroughbreds_2026_09.csv/ANZ_Thoroughbreds_2026_09.csv"
    conn = FakeConn({ZIP25: b"jan", OCT: b"oct", NOV: b"nov", sep: b"sep"})
    html = LISTING_HTML + '<a href="../assets/ANZ_Thoroughbreds_2026_09.csv">Sep</a>'
    downloads = {"ANZ_Thoroughbreds_2026_09.csv": b"sep", "ANZ_Thoroughbreds_2026_10.csv": b"oct",
                 "ANZ_Thoroughbreds_2026_11.csv": b"nov"}
    with pytest.raises(RuntimeError, match="size check is not measuring"):
        _run(conn, downloads, sizes={k: 1 for k in downloads}, html=html)
    assert len(conn.rows) == 4                                         # and nothing was written
    out, _ = _run(conn, downloads, sizes={k: 3 for k in downloads}, html=html)
    assert out["written"] == 0


def test_an_older_month_that_changes_size_is_fetched_by_the_size_check_alone():
    # September is not one of the two newest stored months, so only its size can flag it.
    sep = "horse/betfair-ANZ_Thoroughbreds_2026_09.csv/ANZ_Thoroughbreds_2026_09.csv"
    conn = FakeConn({ZIP25: b"jan", OCT: b"oct", NOV: b"nov", sep: b"sep"})
    html = LISTING_HTML + '<a href="../assets/ANZ_Thoroughbreds_2026_09.csv">Sep</a>'
    new = b"sep, corrected"
    out, fetched = _run(conn, {"ANZ_Thoroughbreds_2026_09.csv": new, "ANZ_Thoroughbreds_2026_10.csv": b"oct",
                               "ANZ_Thoroughbreds_2026_11.csv": b"nov"},
                        sizes={"ANZ_Thoroughbreds_2026_09.csv": len(new), "ANZ_Thoroughbreds_2026_10.csv": 3,
                               "ANZ_Thoroughbreds_2026_11.csv": 3}, html=html)
    assert "ANZ_Thoroughbreds_2026_09.csv" in fetched and out["written"] == 1
    assert conn.rows[sep][0] == _sha(b"sep")


# ── a month is one month, wherever its copies sit (the second review's cases) ──

Z26 = "horse/betfair-ANZ_Thoroughbreds_2026.zip/"
DEC = "horse/betfair-ANZ_Thoroughbreds_2026_12.csv/ANZ_Thoroughbreds_2026_12.csv"
HTML_ZIP26 = (LISTING_HTML + '<a href="../assets/ANZ_Thoroughbreds_2026.zip">2026</a>'
              '<a href="../assets/ANZ_Thoroughbreds_2026_12.csv">Dec</a>')


def _study_months(conn):
    from scripts.horse.anz_study import month_files
    return month_files(sorted(r[len("horse/"):] for r in conn.rows
                              if r.endswith(".csv") and "/other/" not in r))


def test_a_month_arriving_with_its_years_zip_is_stored_once():
    conn = FakeConn({ZIP25: b"jan", OCT: b"oct", NOV: b"nov"})
    z = _zip({"ANZ_Thoroughbreds_2026_10.csv": b"oct", "ANZ_Thoroughbreds_2026_11.csv": b"nov",
              "ANZ_Thoroughbreds_2026_12.csv": b"dec"})
    downloads = {"ANZ_Thoroughbreds_2026.zip": z, "ANZ_Thoroughbreds_2026_10.csv": b"oct",
                 "ANZ_Thoroughbreds_2026_11.csv": b"nov", "ANZ_Thoroughbreds_2026_12.csv": b"dec"}
    sizes = {"ANZ_Thoroughbreds_2026_10.csv": 3, "ANZ_Thoroughbreds_2026_11.csv": 3}
    _run(conn, downloads, sizes=sizes, html=HTML_ZIP26)
    decs = [r for r in conn.rows if "2026_12" in r]
    assert decs == [Z26 + "ANZ_Thoroughbreds_2026_12.csv"]             # the zip's copy, and only it
    assert len(_study_months(conn)) == 4                               # Jan 2025, Oct, Nov, Dec 2026
    # the next day December's own link is now a held month: nothing is stored again
    out, _ = _run(conn, downloads, sizes={**sizes, "ANZ_Thoroughbreds_2026_12.csv": 3}, html=HTML_ZIP26)
    assert out["written"] == 0


def test_a_month_listed_after_its_years_zip_is_not_stored_twice():
    conn = FakeConn({ZIP25: b"jan", OCT: b"oct", NOV: b"nov"})
    z = _zip({"ANZ_Thoroughbreds_2026_12.csv": b"dec"})
    zip_only = LISTING_HTML + '<a href="../assets/ANZ_Thoroughbreds_2026.zip">2026</a>'
    _run(conn, {"ANZ_Thoroughbreds_2026.zip": z, "ANZ_Thoroughbreds_2026_10.csv": b"oct",
                "ANZ_Thoroughbreds_2026_11.csv": b"nov"},
         sizes={"ANZ_Thoroughbreds_2026_10.csv": 3, "ANZ_Thoroughbreds_2026_11.csv": 3}, html=zip_only)
    out, _ = _run(conn, {"ANZ_Thoroughbreds_2026_10.csv": b"oct", "ANZ_Thoroughbreds_2026_11.csv": b"nov",
                         "ANZ_Thoroughbreds_2026_12.csv": b"dec"},
                  sizes={"ANZ_Thoroughbreds_2026_10.csv": 3, "ANZ_Thoroughbreds_2026_11.csv": 3,
                         "ANZ_Thoroughbreds_2026_12.csv": 3}, html=HTML_ZIP26)
    assert out["written"] == 0 and [r for r in conn.rows if "2026_12" in r] == [Z26 + "ANZ_Thoroughbreds_2026_12.csv"]
    assert len(_study_months(conn)) == 4


def test_an_already_zipped_month_listed_again_with_the_same_bytes_stores_nothing():
    jun = "horse/betfair-ANZ_Thoroughbreds_2025.zip/ANZ_Thoroughbreds_2025_06.csv"
    conn = FakeConn({ZIP25: b"jan", jun: b"jun", OCT: b"oct", NOV: b"nov"})
    html = LISTING_HTML + '<a href="../assets/ANZ_Thoroughbreds_2025_06.csv">Jun</a>'
    out, _ = _run(conn, {"ANZ_Thoroughbreds_2025_06.csv": b"jun", "ANZ_Thoroughbreds_2026_10.csv": b"oct",
                         "ANZ_Thoroughbreds_2026_11.csv": b"nov"},
                  sizes={"ANZ_Thoroughbreds_2025_06.csv": 4, "ANZ_Thoroughbreds_2026_10.csv": 3,
                         "ANZ_Thoroughbreds_2026_11.csv": 3}, html=html)
    assert out["written"] == 0 and len(_study_months(conn)) == 4


def test_two_versions_of_one_month_in_one_run_get_different_stamps_and_the_later_is_read():
    conn = FakeConn({ZIP25: b"jan", OCT: b"oct", NOV: b"nov"})
    z = _zip({"ANZ_Thoroughbreds_2026_11.csv": b"nov from the zip"})
    zip_html = LISTING_HTML + '<a href="../assets/ANZ_Thoroughbreds_2026.zip">2026</a>'
    _run(conn, {"ANZ_Thoroughbreds_2026.zip": z, "ANZ_Thoroughbreds_2026_10.csv": b"oct",
                "ANZ_Thoroughbreds_2026_11.csv": b"nov from its own link"},
         sizes={"ANZ_Thoroughbreds_2026_10.csv": 3, "ANZ_Thoroughbreds_2026_11.csv": 21}, html=zip_html)
    versions = sorted(r for r in conn.rows if ".v" in r and "2026_11" in r)
    assert len(versions) == 2 and versions[0].split(".v")[1][:16] != versions[1].split(".v")[1][:16]
    nov = [p for p in _study_months(conn) if "2026_11" in p]
    assert nov == [max(versions)[len("horse/"):]]                      # the later stamp is read
    assert gzip.decompress(conn.rows[max(versions)][2]) == b"nov from its own link"


def test_a_return_to_an_earlier_version_is_stored_so_the_study_reads_what_is_published_now():
    conn = FakeConn({ZIP25: b"jan", OCT: b"oct", NOV: b"nov"})
    sizes = {"ANZ_Thoroughbreds_2026_10.csv": 3, "ANZ_Thoroughbreds_2026_11.csv": 3}
    _run(conn, {"ANZ_Thoroughbreds_2026_10.csv": b"oct", "ANZ_Thoroughbreds_2026_11.csv": b"NOV"}, sizes=sizes)
    out, _ = _run(conn, {"ANZ_Thoroughbreds_2026_10.csv": b"oct", "ANZ_Thoroughbreds_2026_11.csv": b"nov"},
                  sizes=sizes)
    assert out["written"] == 1
    nov = [p for p in _study_months(conn) if "2026_11" in p][0]
    assert gzip.decompress(conn.rows["horse/" + nov][2]) == b"nov"


def test_a_whole_year_re_exported_through_its_zip_is_not_a_false_size_alarm():
    sep = "horse/betfair-ANZ_Thoroughbreds_2026_09.csv/ANZ_Thoroughbreds_2026_09.csv"
    conn = FakeConn({ZIP25: b"jan", sep: b"sep", OCT: b"oct", NOV: b"nov"})
    new = {"ANZ_Thoroughbreds_2026_09.csv": b"sep v2", "ANZ_Thoroughbreds_2026_10.csv": b"oct v2",
           "ANZ_Thoroughbreds_2026_11.csv": b"nov v2"}
    html = (LISTING_HTML + '<a href="../assets/ANZ_Thoroughbreds_2026_09.csv">Sep</a>'
            '<a href="../assets/ANZ_Thoroughbreds_2026.zip">2026</a>')
    out, _ = _run(conn, {**new, "ANZ_Thoroughbreds_2026.zip": _zip(new)},
                  sizes={k: len(v) for k, v in new.items()}, html=html)      # no RuntimeError
    assert out["written"] == 4                                          # 3 versions + the manifest
    for m in ("2026_09", "2026_10", "2026_11"):
        p = [x for x in _study_months(conn) if m in x][0]
        assert gzip.decompress(conn.rows["horse/" + p][2]).endswith(b"v2")


def test_a_zip_member_that_is_not_a_month_file_is_kept_out_of_the_studys_way():
    conn = FakeConn({OCT: b"oct", NOV: b"nov"})
    z = _zip({"ANZ_Thoroughbreds_2025_01.csv": b"jan", "__MACOSX/notes.csv": b"x"})
    _run(conn, {"ANZ_Thoroughbreds_2025.zip": z, "ANZ_Thoroughbreds_2026_10.csv": b"oct",
                "ANZ_Thoroughbreds_2026_11.csv": b"nov"},
         sizes={"ANZ_Thoroughbreds_2026_10.csv": 3, "ANZ_Thoroughbreds_2026_11.csv": 3})
    assert "horse/betfair-ANZ_Thoroughbreds_2025.zip/other/notes.csv" in conn.rows
    assert len(_study_months(conn)) == 3


def test_a_new_version_sorts_after_every_stored_one_even_with_a_clock_behind():
    later = "horse/betfair-ANZ_Thoroughbreds_2026_11.csv/ANZ_Thoroughbreds_2026_11.v20991231T235959Z-00000000.csv"
    conn = FakeConn({ZIP25: b"jan", OCT: b"oct", NOV: b"nov", later: b"nov from the future"})
    _run(conn, {"ANZ_Thoroughbreds_2026_10.csv": b"oct", "ANZ_Thoroughbreds_2026_11.csv": b"nov now"},
         sizes={"ANZ_Thoroughbreds_2026_10.csv": 3, "ANZ_Thoroughbreds_2026_11.csv": 7})
    nov = [p for p in _study_months(conn) if "2026_11" in p][0]
    assert gzip.decompress(conn.rows["horse/" + nov][2]) == b"nov now"


def test_an_older_month_held_only_inside_a_zip_is_not_downloaded_again_by_its_own_link():
    # September sits only in the 2026 zip's folder, and is not one of the two newest
    # months, so neither the daily hash nor a size change brings it back.
    sep_in_zip = Z26 + "ANZ_Thoroughbreds_2026_09.csv"
    conn = FakeConn({ZIP25: b"jan", sep_in_zip: b"sep", Z26 + bm.MANIFEST: b"{}", OCT: b"oct", NOV: b"nov"})
    html = (LISTING_HTML + '<a href="../assets/ANZ_Thoroughbreds_2026.zip">2026</a>'
            '<a href="../assets/ANZ_Thoroughbreds_2026_09.csv">Sep</a>')
    out, fetched = _run(conn, {"ANZ_Thoroughbreds_2026_09.csv": b"sep", "ANZ_Thoroughbreds_2026_10.csv": b"oct",
                               "ANZ_Thoroughbreds_2026_11.csv": b"nov"},
                        sizes={"ANZ_Thoroughbreds_2026_09.csv": 3, "ANZ_Thoroughbreds_2026_10.csv": 3,
                               "ANZ_Thoroughbreds_2026_11.csv": 3}, html=html)
    assert "ANZ_Thoroughbreds_2026_09.csv" not in fetched and out["written"] == 0
