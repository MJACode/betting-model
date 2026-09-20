"""The NFL weather cache has a path INTO Supabase.

`nfl/data/weather_cache` is the directory `tests/test_everything_in_supabase.py`
failed on from the day it was written (2026-09-12) until 2026-09-20: 44
Open-Meteo issued-forecast files, 117,192 stadium-hours, on one laptop. The
rule's own instruction is an importer, not an allowlist entry; this pins the
importer, the same way the odds cache's is pinned.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.ingestors import nfl_weather_cache_import as imp   # noqa: E402

ROOT = Path(__file__).parent.parent


def test_the_importer_resumes_on_a_source_marker():
    src = (ROOT / "data" / "ingestors" / "nfl_weather_cache_import.py").read_text(
        encoding="utf-8")
    assert "SOURCE_PREFIX" in src
    assert "source LIKE" in src, "nothing reads the marker back, so a re-run re-imports"
    assert "already in Supabase" in src
    assert "ON CONFLICT (stadium_id, ts) DO NOTHING" in src


def test_the_table_has_a_migration_and_it_is_scheduled():
    sql = (ROOT / "data" / "migrations" / "add_nfl_stadium_weather_hourly.sql").read_text(
        encoding="utf-8")
    assert "to_regclass('public.nfl_stadium_weather_hourly') IS NULL" in sql, (
        "the migration re-runs daily; it must be a no-op once the table exists")
    assert "ENABLE ROW LEVEL SECURITY" in sql and "REVOKE ALL" in sql
    from data import view_migrations
    assert "add_nfl_stadium_weather_hourly.sql" in view_migrations.ACTIVE_MIGRATIONS


def test_the_file_name_names_the_stadium():
    assert imp.stadium_from_name("issued_BAL00_2024-09-13_2025-01-14.json") == "BAL00"
    assert imp.stadium_from_name("era5_BAL00_2024-09-13_2025-01-14.json") is None
    assert imp.stadium_from_name("issued_BAL00.json") is None


def test_every_hour_becomes_one_row_in_column_order():
    payload = {
        "hourly": {
            "time": ["2024-09-13T00:00", "2024-09-13T01:00"],
            "wind_speed_10m": [5.1, 6.2],
            **{f"wind_speed_10m_previous_day{i}": [float(i), float(i) + 0.5]
               for i in range(1, 8)},
            "temperature_2m": [70.0, 69.5],
            "precipitation": [0.0, 0.1],
        }
    }
    rows = imp.rows_from_file(payload, "issued_BUF00_2024-09-13_2024-09-13.json")
    assert len(rows) == 2
    sid, ts, analysis, *fc, temp, precip, source = rows[1]
    assert sid == "BUF00"
    assert ts == datetime(2024, 9, 13, 1, tzinfo=timezone.utc), "the hour is UTC"
    assert analysis == 6.2
    assert fc == [1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5], "fc_d1..fc_d7 in lead order"
    assert (temp, precip) == (69.5, 0.1)
    assert source == "nfl_weather_cache|file=issued_BUF00_2024-09-13_2024-09-13.json"
    assert len(rows[0]) == 2 + len(imp.COLUMNS) + 1 == _INSERT_PLACEHOLDERS()


def _INSERT_PLACEHOLDERS() -> int:
    return imp._INSERT.count("%s")


def test_a_non_issued_or_empty_payload_yields_nothing():
    assert imp.rows_from_file({}, "issued_BUF00_2024-09-13_2024-09-13.json") == []
    assert imp.rows_from_file({"hourly": {"time": ["2024-09-13T00:00"], "wind_speed_10m": [1.0]}},
                              "era5_BUF00_2024-09-13_2024-09-13.json") == []


def test_stored_files_reads_the_marker_back():
    class Conn:
        def execute(self, sql, params=None):
            assert "source LIKE" in sql and params == ("nfl_weather_cache|%",)
            class R:
                def fetchall(self_inner):
                    return [("nfl_weather_cache|file=issued_A_1_2.json",),
                            ("something_else|file=x.json",)]
            return R()
    assert imp.stored_files(Conn()) == {"issued_A_1_2.json"}
