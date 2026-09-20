"""The NFL weather cache is a CACHE of Supabase, in both directions.

2026-09-20 (michael: "yes fix the weather module"). #784 imported the 44
issued-forecast files into `nfl_stadium_weather_hourly` but the module kept
reading files and hitting Open-Meteo on a miss, so a second machine would
re-pull what the table already held, and a fresh pull landed on one disk.
Now: file -> table -> API, and an API response is written to the table in the
same call. Every test here fails against the pre-change module (no
_issued_from_supabase, no _store_issued, requests.get reached on a miss).
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).parent.parent
NFL_ROOT = ROOT / "nfl"


@pytest.fixture()
def wx(tmp_path, monkeypatch):
    monkeypatch.setenv("WX_CACHE", str(tmp_path / "cache"))
    sys.path.insert(0, str(NFL_ROOT))
    for m in list(sys.modules):
        if m == "data_ingest.weather" or m == "data_ingest":
            del sys.modules[m]
    try:
        from data_ingest import weather
    finally:
        sys.path.remove(str(NFL_ROOT))
    # never touch the network from a test
    monkeypatch.setattr(weather.requests, "get",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network hit")))
    return weather


SID, START, END = "BUF00", "2024-09-13", "2024-09-14"   # two days = 48 hours


def _rows(hours=48, leads=(1, 2, 3, 4, 5, 6, 7), null_lead=None):
    lo = datetime.fromisoformat(START).replace(tzinfo=timezone.utc)
    out = []
    for h in range(hours):
        ts = lo + timedelta(hours=h)
        fc = [None if i == null_lead else 10.0 + i for i in leads]
        out.append((ts, 9.5, 70.0, 0.0, *fc))
    return out


class FakeConn:
    def __init__(self, rows):
        self.rows, self.sql, self.params, self.closed = rows, None, None, False
        self.written = []

    def execute(self, sql, params=None):
        self.sql, self.params = sql, params
        rows = self.rows

        class R:
            def fetchall(self_inner):
                return rows
        return R()

    def executemany(self, sql, rows):
        self.written.extend(rows)

    def commit(self):
        pass

    def close(self):
        self.closed = True


def _patch_conn(monkeypatch, conn):
    import data.db
    monkeypatch.setattr(data.db, "get_connection", lambda *a, **k: conn)


def test_a_window_the_table_holds_is_read_from_the_table_and_never_fetched(wx, monkeypatch):
    conn = FakeConn(_rows())
    _patch_conn(monkeypatch, conn)
    df = wx.fetch_issued_forecasts(SID, START, END)
    assert len(df) == 48 and conn.closed
    assert list(df.columns) == ["stadium_id", "ts", "om_analysis", "om_temp", "om_precip",
                                "fc_d1", "fc_d2", "fc_d3", "fc_d4", "fc_d5", "fc_d6", "fc_d7"], (
        "the same column order _frame() builds from an API response")
    assert df.ts.dt.tz is not None and df.ts.iloc[0] == pd.Timestamp(START, tz="UTC")
    assert df.fc_d3.iloc[0] == 13.0 and df.om_analysis.iloc[0] == 9.5
    assert conn.params == (SID,
                           datetime(2024, 9, 13, tzinfo=timezone.utc),
                           datetime(2024, 9, 15, tzinfo=timezone.utc)), "end date inclusive"


def test_a_subset_of_leads_reads_only_those_columns(wx, monkeypatch):
    conn = FakeConn(_rows(leads=(3,)))
    _patch_conn(monkeypatch, conn)
    df = wx.fetch_issued_forecasts(SID, START, END, leads=(3,))
    assert list(df.columns) == ["stadium_id", "ts", "om_analysis", "om_temp", "om_precip", "fc_d3"]
    assert "fc_d3_mph" in conn.sql and "fc_d1_mph" not in conn.sql


def test_a_partial_window_is_not_returned(wx, monkeypatch):
    _patch_conn(monkeypatch, FakeConn(_rows(hours=47)))
    assert wx._issued_from_supabase(SID, START, END, wx.ALL_LEADS) is None


def test_a_null_requested_lead_is_not_returned(wx, monkeypatch):
    _patch_conn(monkeypatch, FakeConn(_rows(null_lead=3)))
    assert wx._issued_from_supabase(SID, START, END, wx.ALL_LEADS) is None


def test_no_database_falls_through_quietly(wx, monkeypatch):
    import data.db

    def boom(*a, **k):
        raise ValueError("DATABASE_URL is not set.")
    monkeypatch.setattr(data.db, "get_connection", boom)
    assert wx._issued_from_supabase(SID, START, END, wx.ALL_LEADS) is None


def test_the_file_on_disk_still_wins_over_the_table(wx, monkeypatch, tmp_path):
    import json
    payload = {"hourly": {"time": ["2024-09-13T00:00"], "wind_speed_10m": [1.0],
                          **{f"wind_speed_10m_previous_day{i}": [float(i)] for i in range(1, 8)},
                          "temperature_2m": [60.0], "precipitation": [0.0]}}
    wx.CACHE.mkdir(parents=True)
    (wx.CACHE / f"issued_{SID}_{START}_{END}.json").write_text(json.dumps(payload))
    calls = []
    monkeypatch.setattr(wx, "_issued_from_supabase", lambda *a: calls.append(a) or None)
    monkeypatch.setattr(wx, "_store_issued", lambda *a: calls.append(("store",) + a) or 0)
    df = wx.fetch_issued_forecasts(SID, START, END)
    assert len(df) == 1 and calls == [], "a cached file is neither re-read from the table nor re-stored"


def test_an_api_response_is_stored_in_the_same_call(wx, monkeypatch):
    payload = {"hourly": {"time": ["2024-09-13T00:00", "2024-09-13T01:00"], "wind_speed_10m": [1.0, 2.0],
                          **{f"wind_speed_10m_previous_day{i}": [float(i), float(i)] for i in range(1, 8)},
                          "temperature_2m": [60.0, 61.0], "precipitation": [0.0, 0.0]}}

    class Resp:
        status_code = 200

        def json(self):
            return payload
    monkeypatch.setattr(wx.requests, "get", lambda *a, **k: Resp())
    monkeypatch.setattr(wx, "_issued_from_supabase", lambda *a: None)   # table has nothing
    conn = FakeConn([])
    _patch_conn(monkeypatch, conn)
    df = wx.fetch_issued_forecasts(SID, START, END)
    assert len(df) == 2
    assert len(conn.written) == 2, "the fetched hours reach Supabase in the same call"
    assert conn.written[0][0] == SID and conn.written[0][-1] == f"nfl_weather_cache|file=issued_{SID}_{START}_{END}.json"
    assert (wx.CACHE / f"issued_{SID}_{START}_{END}.json").exists(), "and the file cache still fills"


def test_a_one_lead_response_is_not_stored(wx, monkeypatch):
    payload = {"hourly": {"time": ["2024-09-13T00:00"], "wind_speed_10m": [1.0],
                          "wind_speed_10m_previous_day3": [3.0],
                          "temperature_2m": [60.0], "precipitation": [0.0]}}
    conn = FakeConn([])
    _patch_conn(monkeypatch, conn)
    assert wx._store_issued(payload, "issued_BUF00_x_y.json") == 0
    assert conn.written == [], "a partial row would block the full row under ON CONFLICT DO NOTHING"


def test_a_store_failure_is_a_warning_not_an_error(wx, monkeypatch, caplog):
    import data.db

    def boom(*a, **k):
        raise ValueError("DATABASE_URL is not set.")
    monkeypatch.setattr(data.db, "get_connection", boom)
    payload = {"hourly": {"time": ["2024-09-13T00:00"], "wind_speed_10m": [1.0],
                          **{f"wind_speed_10m_previous_day{i}": [float(i)] for i in range(1, 8)},
                          "temperature_2m": [60.0], "precipitation": [0.0]}}
    with caplog.at_level("WARNING"):
        assert wx._store_issued(payload, "issued_BUF00_x_y.json") == 0
    assert "NOT stored" in caplog.text


def test_importing_the_module_creates_no_directory(wx):
    assert not wx.CACHE.exists(), "the cache directory is made on first write, not at import"
