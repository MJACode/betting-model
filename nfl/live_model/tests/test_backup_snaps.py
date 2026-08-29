"""
Guards on the backup of 100,116 credits of irreplaceable data.

A backup nobody has read back is a belief rather than a backup, so the
properties pinned here are the ones that make it real: bytes survive the
round trip exactly, corruption is detected rather than restored, and a
partial upload reports itself as partial instead of as success.
"""
from __future__ import annotations

import gzip
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from live_model.backtest import backup_snaps as bs  # noqa: E402


class _FakeCur:
    """Enough of a cursor to exercise the module against an in-memory store."""

    def __init__(self, store):
        self.store = store
        self._rows = []

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if s.startswith("CREATE TABLE") or "ALTER TABLE" in s:
            self._rows = []
        elif "SELECT rel_path, sha256, content_gz" in s:
            self._rows = [(k, v[0], v[1]) for k, v in self.store.items()]
        elif "SELECT rel_path, sha256" in s:
            self._rows = [(k, v[0]) for k, v in self.store.items()]

    def fetchall(self):
        return list(self._rows)


class _FakeConn:
    def __init__(self):
        self.store = {}
        self._cur = _FakeCur(self.store)

    def cursor(self):
        return self._cur

    def commit(self):
        pass

    def close(self):
        pass


@pytest.fixture(autouse=True)
def _no_psycopg(monkeypatch):
    monkeypatch.setattr(bs, "psycopg2_bytes", lambda b: b)

    def fake_flush(conn, cur, batch):
        for rel, sha, _rb, _gb, blob in batch:
            conn.store[rel] = (sha, blob)
    monkeypatch.setattr(bs, "_flush", fake_flush)


def _cache(tmp_path, files):
    for name, body in files.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)
    return tmp_path


def test_bytes_survive_the_round_trip_exactly(tmp_path):
    root = _cache(tmp_path, {"a/b.json": b'{"line": 32.5}', "c.json": b"\x00\xff"})
    conn = _FakeConn()
    bs.back_up(conn, root)
    for rel, (sha, blob) in conn.store.items():
        assert gzip.decompress(blob) == (root / rel).read_bytes()


def test_a_rerun_uploads_nothing_new(tmp_path):
    root = _cache(tmp_path, {"a.json": b"x" * 500})
    conn = _FakeConn()
    assert bs.back_up(conn, root)["uploaded"] == 1
    r = bs.back_up(conn, root)
    assert r["uploaded"] == 0 and r["unchanged"] == 1


def test_a_changed_file_is_reuploaded(tmp_path):
    root = _cache(tmp_path, {"a.json": b"old"})
    conn = _FakeConn()
    bs.back_up(conn, root)
    (root / "a.json").write_bytes(b"new")
    assert bs.back_up(conn, root)["uploaded"] == 1
    assert gzip.decompress(conn.store["a.json"][1]) == b"new"


def test_verify_decompresses_rather_than_trusting_the_stored_digest(tmp_path):
    """The stored checksum agreeing with itself proves nothing."""
    root = _cache(tmp_path, {"a.json": b"payload"})
    conn = _FakeConn()
    bs.back_up(conn, root)
    sha, _ = conn.store["a.json"]
    conn.store["a.json"] = (sha, gzip.compress(b"something else"))
    assert bs.verify(conn, root)["corrupt"] == 1


def test_a_missing_file_reports_the_backup_as_incomplete(tmp_path):
    root = _cache(tmp_path, {"a.json": b"1", "b.json": b"2"})
    conn = _FakeConn()
    bs.back_up(conn, root)
    del conn.store["b.json"]
    v = bs.verify(conn, root)
    assert v["stored"] == 1 and v["on_disk"] == 2


def test_restore_refuses_to_write_a_corrupt_row(tmp_path):
    root = _cache(tmp_path, {"a.json": b"good"})
    conn = _FakeConn()
    bs.back_up(conn, root)
    sha, _ = conn.store["a.json"]
    conn.store["a.json"] = (sha, gzip.compress(b"tampered"))
    (root / "a.json").unlink()
    with pytest.raises(SystemExit):
        bs.restore(conn, root)
    assert not (root / "a.json").exists(), "wrote a file it could not verify"


def test_restore_rebuilds_the_tree_from_the_backup_alone(tmp_path):
    root = _cache(tmp_path, {"x/y/a.json": b"deep", "b.json": b"flat"})
    conn = _FakeConn()
    bs.back_up(conn, root)
    for p in list(bs.iter_files(root)):
        p.unlink()
    assert bs.restore(conn, root)["restored"] == 2
    assert (root / "x/y/a.json").read_bytes() == b"deep"
    assert (root / "b.json").read_bytes() == b"flat"


def test_an_absent_cache_is_an_error_not_an_empty_success(tmp_path):
    with pytest.raises(SystemExit):
        list(bs.iter_files(tmp_path / "nope"))
