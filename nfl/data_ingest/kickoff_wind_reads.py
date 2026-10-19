"""
Live kickoff-hour wind readings for `nfl_wind_totals`.

The live card polls Open-Meteo every hour (every 10 minutes inside a day of
kickoff). The threshold check needs the recent readings, not only the one it
just fetched, or the first poll at 11 mph locks the under. This table is those
readings: one row per game per poll, the kickoff-hour wind in mph. It is not a
pick, and a game that never covers the window never gets a row in `picks`.

The card fails closed. If the table cannot be read or written, the only
reading the check sees is the one just fetched, and one reading does not cover
the window, so nothing locks.
"""

from __future__ import annotations

import sys
from datetime import timedelta

import pandas as pd

from data.ddl_guard import schema_is_current

TABLE = "nfl_kickoff_wind_reads"
# An hour past the lookback the rule uses, so a clock skew between the insert
# and the read cannot drop the oldest reading the window needs.
_LOAD_HOURS = 14

_DDL = (
    f"""
    CREATE TABLE IF NOT EXISTS {TABLE} (
        game_id     TEXT        NOT NULL,
        observed_at TIMESTAMPTZ NOT NULL,
        wind_mph    NUMERIC     NOT NULL,
        PRIMARY KEY (game_id, observed_at)
    )
    """,
    f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY",
    f"REVOKE ALL ON {TABLE} FROM anon, authenticated",
)

_INSERT = f"""
    INSERT INTO {TABLE} (game_id, observed_at, wind_mph)
    VALUES (%s, %s, %s)
    ON CONFLICT (game_id, observed_at) DO NOTHING
"""

_SELECT = f"""
    SELECT game_id, observed_at, wind_mph
    FROM {TABLE}
    WHERE game_id = ANY(%s)
      AND observed_at >= %s
      AND observed_at <= %s
"""


def _utc(now) -> pd.Timestamp:
    t = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    if t.tzinfo is None:
        return t.tz_localize("UTC")
    return t.tz_convert("UTC")


def _current(games: pd.DataFrame, now: pd.Timestamp) -> dict[str, list[tuple]]:
    """The reading this poll just fetched, keyed by nflverse game_id."""
    out: dict[str, list[tuple]] = {}
    for row in games.itertuples():
        wind = getattr(row, "forecast_wind", None)
        if wind is None or pd.isna(wind):
            continue
        out[str(row.game_id)] = [(now.to_pydatetime(), float(wind))]
    return out


def _connect():
    from data.db import get_connection
    return get_connection()


def attach_live_wind_reads(games: pd.DataFrame, *, now=None) -> dict[str, list[tuple]]:
    """
    Record this poll's kickoff-hour wind and return every reading in the
    recent window, including this one.

    Always returns a dict. A database failure returns only this poll's
    reading, which `ruling_wind` rejects until a later poll covers the window.
    """
    now = _utc(now)
    current = _current(games, now)
    if not current:
        return {}
    try:
        conn = _connect()
    except Exception as exc:                                   # noqa: BLE001
        print(f"WARNING: kickoff wind reads not stored ({exc}); "
              "this poll cannot lock a wind bet", file=sys.stderr)
        return current
    try:
        # Hourly, and every 10 minutes inside a day of kickoff. CREATE,
        # ENABLE ROW LEVEL SECURITY and REVOKE are not free on a table that
        # already exists: each takes a lock and fires pgrst_ddl_watch, and
        # PostgREST answers 503 while it reloads (2026-09-01). The catalog
        # check is one SELECT. It returns False when the table is missing or
        # the probe cannot be read, so this poll still creates the table and
        # the insert and select below still run.
        if not schema_is_current(
            conn, TABLE,
            columns=("game_id", "observed_at", "wind_mph"),
            rls=True,
            revoked_from=("anon", "authenticated"),
        ):
            for stmt in _DDL:
                conn.execute(stmt)
        conn.executemany(
            _INSERT,
            [(gid, ts, mph) for gid, series in current.items() for ts, mph in series],
        )
        rows = conn.execute(
            _SELECT,
            (list(current), now.to_pydatetime() - timedelta(hours=_LOAD_HOURS),
             now.to_pydatetime()),
        ).fetchall()
        conn.commit()
    except Exception as exc:                                   # noqa: BLE001
        try:
            conn.rollback()
        except Exception:                                      # noqa: BLE001
            pass
        print(f"WARNING: kickoff wind reads failed ({exc}); "
              "this poll cannot lock a wind bet", file=sys.stderr)
        return current
    finally:
        try:
            conn.close()
        except Exception:                                      # noqa: BLE001
            pass

    series: dict[str, list[tuple]] = {gid: [] for gid in current}
    for gid, observed_at, mph in rows:
        series.setdefault(str(gid), []).append((observed_at, float(mph)))
    return _with_current(series, current)


def _with_current(series: dict[str, list[tuple]],
                  current: dict[str, list[tuple]]) -> dict[str, list[tuple]]:
    """Make sure this poll's reading is in the series the check sees."""
    out: dict[str, list[tuple]] = {gid: list(points) for gid, points in series.items()}
    for gid, points in current.items():
        got = out.setdefault(gid, [])
        for ts, mph in points:
            stamp = pd.Timestamp(ts)
            if stamp.tzinfo is None:
                stamp = stamp.tz_localize("UTC")
            else:
                stamp = stamp.tz_convert("UTC")
            already = False
            for prev_ts, prev_mph in got:
                prev = pd.Timestamp(prev_ts)
                if prev.tzinfo is None:
                    prev = prev.tz_localize("UTC")
                else:
                    prev = prev.tz_convert("UTC")
                if prev == stamp and float(prev_mph) == float(mph):
                    already = True
                    break
            if not already:
                got.append((ts, mph))
    return out
