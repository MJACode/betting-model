"""
Tests for data/ingestors/odds_quota.py (Odds API credit telemetry) and the
odds_api_quota table shape.

Pure sqlite — no network, no Postgres. The production path goes through the
DBConnection wrapper, which translates '?' params; sqlite3 accepts them
natively, so the same SQL runs in both.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.ingestors import odds_quota


class FakeResp:
    def __init__(self, headers):
        self.headers = headers


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE odds_api_quota (
            quota_date         TEXT PRIMARY KEY,
            requests_used      NUMERIC,
            requests_remaining NUMERIC,
            observed_at        TEXT NOT NULL
        )
    """)
    return conn


def setup_function(_fn):
    odds_quota._LATEST = None


def test_record_and_persist_roundtrip():
    conn = _conn()
    odds_quota.record_quota_headers(
        FakeResp({"x-requests-used": "183211", "x-requests-remaining": "4816789"}))
    odds_quota.persist_quota(conn)
    row = conn.execute(
        "SELECT requests_used, requests_remaining FROM odds_api_quota").fetchone()
    assert row == (183211.0, 4816789.0)


def test_last_write_wins_same_day():
    # A mid-day credit top-up must be reflected immediately (no peak/floor
    # semantics that would keep warning off the pre-top-up number all day).
    conn = _conn()
    odds_quota.record_quota_headers(
        FakeResp({"x-requests-used": "100", "x-requests-remaining": "50"}))
    odds_quota.persist_quota(conn)
    odds_quota.record_quota_headers(
        FakeResp({"x-requests-used": "120", "x-requests-remaining": "999880"}))
    odds_quota.persist_quota(conn)
    rows = conn.execute(
        "SELECT requests_used, requests_remaining FROM odds_api_quota").fetchall()
    assert rows == [(120.0, 999880.0)]


def test_missing_headers_are_ignored():
    conn = _conn()
    odds_quota.record_quota_headers(FakeResp({}))
    odds_quota.persist_quota(conn)
    assert conn.execute("SELECT COUNT(*) FROM odds_api_quota").fetchone()[0] == 0


def test_persist_without_observation_is_noop():
    conn = _conn()
    odds_quota.persist_quota(conn)
    assert conn.execute("SELECT COUNT(*) FROM odds_api_quota").fetchone()[0] == 0


def test_persist_swallows_db_errors():
    # Telemetry must never break an ingest run.
    class BrokenConn:
        def execute(self, *a):
            raise RuntimeError("db down")

        def rollback(self):
            pass

    odds_quota.record_quota_headers(
        FakeResp({"x-requests-used": "1", "x-requests-remaining": "2"}))
    odds_quota.persist_quota(BrokenConn())  # must not raise


def test_record_survives_broken_headers():
    class WeirdResp:
        @property
        def headers(self):
            raise RuntimeError("no headers")

    odds_quota.record_quota_headers(WeirdResp())  # must not raise
    assert odds_quota._LATEST is None
