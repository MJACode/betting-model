"""Move the NFL stadium weather series off this laptop and into Supabase.

WHAT WAS WRONG. `nfl/data/weather_cache` held 44 JSON files -- the Open-Meteo
ISSUED-forecast series for 24 NFL stadium ids over the 2024 and 2025 seasons,
117,192 stadium-hours -- written by `nfl/data_ingest/weather.py` and read by
the wind replays and the lead calibration. That data existed on ONE laptop.
`tests/test_everything_in_supabase.py` had failed on it since the test was
written (noted, unfixed, on 2026-09-12): a local file is a cache of Supabase
or it is a bug (CLAUDE.md section 1b), and the fix the test names is an
importer, not an allowlist entry. The files are free to refetch, which is
not the point -- a refetch is ~30 minutes of one machine's time, and every
other machine, the worker included, had no copy at all.

WHAT THIS WRITES. One `nfl_stadium_weather_hourly` row per (stadium, UTC
hour):

    stadium_id          from the file name  (issued_<sid>_<start>_<end>.json)
    ts                  the hour, UTC (the module requests timezone=UTC)
    wind_analysis_mph   wind_speed_10m               -- near-analysis, LEAKS
    fc_d1..fc_d7_mph    wind_speed_10m_previous_dayN -- issued N days earlier
    temp_f, precip_mm   temperature_2m, precipitation
    source              'nfl_weather_cache|file=<file name>'

`source` is what resume keys on: the file names already stored are read
back before anything is written, so a re-run imports nothing already in
Supabase. The primary key is (stadium_id, ts) and the insert is ON CONFLICT
DO NOTHING -- measured 2026-09-20, the 44 files hold no overlapping hours,
so nothing is dropped; if a later fetch overlaps an earlier one, the earlier
row stands and the file still counts as imported.

WHAT IT SKIPS, AND COUNTS RATHER THAN INVENTS.
  * A file that is not an `issued_*` response (the ERA5 archive pulls have a
    different column set and are not in the cache today).
  * A file whose `hourly` block is missing or whose name does not parse.

    python -m data.ingestors.nfl_weather_cache_import --dry-run
    python -m data.ingestors.nfl_weather_cache_import --apply
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from data.db import DBConnection, get_connection

CACHE_DIR = Path(__file__).resolve().parents[2] / "nfl" / "data" / "weather_cache"
TABLE = "nfl_stadium_weather_hourly"
SOURCE_PREFIX = "nfl_weather_cache|"
LEADS = (1, 2, 3, 4, 5, 6, 7)
BATCH = 2000

# payload key -> column
COLUMNS = {
    "wind_speed_10m": "wind_analysis_mph",
    **{f"wind_speed_10m_previous_day{i}": f"fc_d{i}_mph" for i in LEADS},
    "temperature_2m": "temp_f",
    "precipitation": "precip_mm",
}

_INSERT = (
    f"INSERT INTO {TABLE} (stadium_id, ts, "
    + ", ".join(COLUMNS.values())
    + ", source) VALUES (%s, %s, "
    + ", ".join(["%s"] * len(COLUMNS))
    + ", %s) ON CONFLICT (stadium_id, ts) DO NOTHING"
)


def source_for(name: str) -> str:
    return f"{SOURCE_PREFIX}file={name}"


def stadium_from_name(name: str) -> str | None:
    """`issued_BAL00_2024-09-13_2025-01-14.json` -> `BAL00`; None otherwise."""
    parts = name.split("_")
    if len(parts) != 4 or parts[0] != "issued" or not name.endswith(".json"):
        return None
    return parts[1] or None


def rows_from_file(payload: dict, name: str) -> list[tuple]:
    """Every hour in the payload as an insert tuple. Empty when the file is
    not an issued-forecast response."""
    sid = stadium_from_name(name)
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    if sid is None or not times:
        return []
    src = source_for(name)
    series = [hourly.get(k) or [None] * len(times) for k in COLUMNS]
    out = []
    for i, t in enumerate(times):
        ts = datetime.fromisoformat(t).replace(tzinfo=timezone.utc)
        out.append((sid, ts, *(s[i] for s in series), src))
    return out


def stored_files(conn: DBConnection) -> set[str]:
    """File names already imported, read back from the source marker."""
    rows = conn.execute(
        f"SELECT DISTINCT source FROM {TABLE} WHERE source LIKE %s",
        (SOURCE_PREFIX + "%",),
    ).fetchall()
    prefix = SOURCE_PREFIX + "file="
    return {r[0][len(prefix):] for r in rows if r[0].startswith(prefix)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    if not (a.dry_run or a.apply):
        ap.error("choose --dry-run or --apply")

    files = sorted(CACHE_DIR.glob("*.json"))
    if a.limit:
        files = files[:a.limit]
    logger.info(f"{len(files):,} cached response(s) in {CACHE_DIR}")

    conn = get_connection()
    try:
        have = stored_files(conn)
        logger.info(f"{len(have):,} file(s) already in Supabase")

        rows_total = skipped = unreadable = wrote = 0
        batch: list[tuple] = []
        for f in files:
            if f.name in have:
                skipped += 1
                continue
            try:
                payload = json.loads(f.read_text(encoding="utf-8"))
            except Exception as exc:                 # noqa: BLE001
                logger.warning(f"{f.name}: unreadable ({exc})")
                unreadable += 1
                continue
            rows = rows_from_file(payload, f.name)
            if not rows:
                logger.warning(f"{f.name}: not an issued-forecast response, skipped")
                unreadable += 1
                continue
            rows_total += len(rows)
            logger.info(f"  {f.name}: {len(rows):,} hours")
            if a.apply:
                batch.extend(rows)
                while len(batch) >= BATCH:
                    conn.executemany(_INSERT, batch[:BATCH])
                    conn.commit()
                    wrote += BATCH
                    batch = batch[BATCH:]
        if a.apply and batch:
            conn.executemany(_INSERT, batch)
            conn.commit()
            wrote += len(batch)

        logger.success(
            f"{'APPLIED' if a.apply else 'DRY RUN'}: {len(files):,} files | "
            f"{rows_total:,} hours to import | written {wrote:,} | "
            f"already stored {skipped:,} | skipped {unreadable:,}"
        )
        if a.apply:
            n = conn.execute(
                f"SELECT COUNT(*) FROM {TABLE} WHERE source LIKE %s",
                (SOURCE_PREFIX + "%",),
            ).fetchone()[0]
            logger.info(f"{TABLE} now holds {n:,} rows from this cache")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
