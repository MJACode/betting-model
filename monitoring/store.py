"""api_call_log — the durable record behind the live monitor, plus its reads.

WHY A TABLE AND NOT JUST AN IN-PROCESS STREAM
The scheduler SHELLS OUT (`python run_pipeline.py --step odds`, the live loops,
the NFL cards), so the process that makes the API calls is never the process
serving the dashboard. The database is the only place both can meet. It also
means a call made from Matt's laptop shows up on the worker's dashboard, and
that history survives a redeploy — Railway's disk does not.

The table is created HERE, like tracking/run_ledger.py, because the Supabase MCP
is read-only and setup_database() only runs at first-time setup. Same lockdown
too: RLS on with no policy, and REVOKE naming anon/authenticated by name —
Supabase's default privileges grant them by name and a PUBLIC-only revoke is a
no-op (the lesson from feedback_reply, session 126c).

Retention is deliberate: this table is append-only at roughly 25k rows/day, so
without pruning it is the fastest-growing table in the database. Rows older than
API_LOG_RETENTION_DAYS (7) are dropped by the writer, at most once an hour per
process.
"""

from __future__ import annotations

import os

RETENTION_DAYS = int(os.environ.get("API_LOG_RETENTION_DAYS", "7"))

DDL = """
CREATE TABLE IF NOT EXISTS api_call_log (
    call_id         BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL,
    api             TEXT NOT NULL,
    host            TEXT NOT NULL,
    category        TEXT NOT NULL,
    method          TEXT NOT NULL,
    path            TEXT NOT NULL,
    sport           TEXT,
    status          INTEGER,
    ok              BOOLEAN NOT NULL,
    duration_ms     INTEGER NOT NULL,
    resp_bytes      INTEGER,
    credits         NUMERIC,
    quota_remaining NUMERIC,
    error           TEXT,
    source          TEXT NOT NULL
)
"""

INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_api_call_ts ON api_call_log(ts)",
    "CREATE INDEX IF NOT EXISTS idx_api_call_api_ts ON api_call_log(api, ts)",
)

LOCKDOWN = (
    "ALTER TABLE api_call_log ENABLE ROW LEVEL SECURITY",
    "REVOKE ALL ON api_call_log FROM anon, authenticated",
)

INSERT_SQL = """
INSERT INTO api_call_log
    (ts, api, host, category, method, path, sport, status, ok,
     duration_ms, resp_bytes, credits, quota_remaining, error, source)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""

# Column order the writer packs rows in. Named once so probe.py and the tests
# cannot drift from INSERT_SQL.
INSERT_COLUMNS = (
    "ts", "api", "host", "category", "method", "path", "sport", "status", "ok",
    "duration_ms", "resp_bytes", "credits", "quota_remaining", "error", "source",
)


def ensure_table(conn) -> None:
    """Create the table, indexes and lockdown. Idempotent, best-effort."""
    for stmt in (DDL, *INDEXES, *LOCKDOWN):
        try:
            conn.execute(stmt)
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass


def prune(conn, days: int = RETENTION_DAYS) -> int:
    """Drop rows older than `days`. Returns rows deleted (0 on any failure)."""
    try:
        row = conn.execute(
            "DELETE FROM api_call_log WHERE ts < NOW() - (? || ' days')::interval "
            "RETURNING 1",
            (str(days),),
        ).fetchall()
        conn.commit()
        return len(row or [])
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return 0


# ── reads (the dashboard's whole data layer) ─────────────────────────────────

def _rows(conn, sql, params=()):
    try:
        return conn.execute(sql, params).fetchall() or []
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return []


CALL_FIELDS = (
    "call_id", "ts", "api", "category", "method", "path", "sport",
    "status", "ok", "duration_ms", "credits", "error", "source",
)


def calls_since(conn, after_id: int, limit: int = 400) -> list[dict]:
    """New calls with call_id > after_id, oldest first (stream order)."""
    sql = f"""
        SELECT {', '.join(CALL_FIELDS)}
        FROM api_call_log WHERE call_id > ? ORDER BY call_id LIMIT {int(limit)}
    """
    return [dict(zip(CALL_FIELDS, r)) for r in _rows(conn, sql, (after_id,))]


def recent_calls(conn, limit: int = 120) -> list[dict]:
    """The most recent calls, oldest first so the UI can append in order."""
    sql = f"""
        SELECT {', '.join(CALL_FIELDS)} FROM (
            SELECT {', '.join(CALL_FIELDS)}
            FROM api_call_log ORDER BY call_id DESC LIMIT {int(limit)}
        ) t ORDER BY call_id
    """
    return [dict(zip(CALL_FIELDS, r)) for r in _rows(conn, sql)]


def api_rollup(conn, minutes: int = 60) -> list[dict]:
    """Per-API counts, error rate, p50/p95 latency and credits over a window."""
    sql = """
        SELECT api, category,
               COUNT(*)                                        AS calls,
               SUM(CASE WHEN ok THEN 0 ELSE 1 END)             AS errors,
               ROUND(AVG(duration_ms))                         AS avg_ms,
               PERCENTILE_DISC(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_ms,
               COALESCE(SUM(credits), 0)                       AS credits,
               MAX(ts)                                         AS last_ts
        FROM api_call_log
        WHERE ts > NOW() - (? || ' minutes')::interval
        GROUP BY api, category
        ORDER BY calls DESC
    """
    cols = ("api", "category", "calls", "errors", "avg_ms", "p95_ms", "credits", "last_ts")
    return [dict(zip(cols, r)) for r in _rows(conn, sql, (str(minutes),))]


def call_timeline(conn, minutes: int = 60, bucket_s: int = 60) -> list[dict]:
    """Calls and errors per time bucket — the sparkline behind the header."""
    sql = """
        SELECT to_timestamp(FLOOR(EXTRACT(EPOCH FROM ts) / ?) * ?) AS bucket,
               COUNT(*)                            AS calls,
               SUM(CASE WHEN ok THEN 0 ELSE 1 END) AS errors
        FROM api_call_log
        WHERE ts > NOW() - (? || ' minutes')::interval
        GROUP BY 1 ORDER BY 1
    """
    cols = ("bucket", "calls", "errors")
    return [dict(zip(cols, r))
            for r in _rows(conn, sql, (bucket_s, bucket_s, str(minutes)))]


PICK_FIELDS = (
    "pick_id", "created_at", "sport", "model_id", "pick_label", "signal_type",
    "model_probability", "edge", "dk_odds", "best_book", "best_odds",
    "game_date", "is_live",
)


def picks_since(conn, after_id: int, limit: int = 120) -> list[dict]:
    sql = f"""
        SELECT {', '.join(PICK_FIELDS)}
        FROM picks WHERE pick_id > ? ORDER BY pick_id LIMIT {int(limit)}
    """
    return [dict(zip(PICK_FIELDS, r)) for r in _rows(conn, sql, (after_id,))]


def recent_picks(conn, limit: int = 60) -> list[dict]:
    sql = f"""
        SELECT {', '.join(PICK_FIELDS)} FROM (
            SELECT {', '.join(PICK_FIELDS)}
            FROM picks ORDER BY pick_id DESC LIMIT {int(limit)}
        ) t ORDER BY pick_id
    """
    return [dict(zip(PICK_FIELDS, r)) for r in _rows(conn, sql)]


def pick_counts(conn, hours: int = 24) -> list[dict]:
    """Signals vs everything scored, per sport, over a window.

    The game_date bound is what makes this cheap. `created_at` is TEXT, so
    casting it to timestamptz is unindexable and the filter alone costs a
    parallel seq scan of picks — 679ms and ~3.5k disk reads, on a query the
    dashboard reruns every 10s per viewer. That is the exact pattern that
    depleted the Disk IO budget in #291. `game_date` has an index, and a pick
    written in the last 24h always belongs to a slate no older than yesterday
    (never newer-bounded: NFL and golf picks are written days ahead), so the
    prefilter prunes without changing the answer. Measured: 679ms -> 13ms,
    3,526 reads -> 0, identical rows.
    """
    sql = """
        SELECT sport,
               COUNT(*)                                                AS scored,
               SUM(CASE WHEN signal_type = 'BET' THEN 1 ELSE 0 END)    AS bets,
               SUM(CASE WHEN is_live THEN 1 ELSE 0 END)                AS live
        FROM picks
        WHERE game_date >= to_char(NOW() - (? || ' hours')::interval
                                   - interval '1 day', 'YYYY-MM-DD')
          AND created_at::timestamptz > NOW() - (? || ' hours')::interval
        GROUP BY sport ORDER BY scored DESC
    """
    cols = ("sport", "scored", "bets", "live")
    return [dict(zip(cols, r)) for r in _rows(conn, sql, (str(hours), str(hours)))]


def recent_runs(conn, limit: int = 12) -> list[dict]:
    sql = """
        SELECT run_id, run_kind, started_at, finished_at,
               steps_total, steps_failed, failed_steps, ok
        FROM pipeline_runs ORDER BY started_at DESC LIMIT %s
    """ % int(limit)
    cols = ("run_id", "run_kind", "started_at", "finished_at",
            "steps_total", "steps_failed", "failed_steps", "ok")
    return [dict(zip(cols, r)) for r in _rows(conn, sql)]


def health(conn) -> list[dict]:
    sql = """
        SELECT check_name, status, severity, detail, checked_at
        FROM system_health_checks
        WHERE run_date = (SELECT MAX(run_date) FROM system_health_checks)
        ORDER BY CASE severity WHEN 'CRIT' THEN 0 ELSE 1 END,
                 CASE WHEN status = 'OK' THEN 1 ELSE 0 END, check_name
    """
    cols = ("check_name", "status", "severity", "detail", "checked_at")
    return [dict(zip(cols, r)) for r in _rows(conn, sql)]


def quota(conn) -> dict | None:
    sql = """
        SELECT quota_date, requests_used, requests_remaining, observed_at
        FROM odds_api_quota ORDER BY quota_date DESC LIMIT 2
    """
    rows = _rows(conn, sql)
    if not rows:
        return None
    cols = ("quota_date", "requests_used", "requests_remaining", "observed_at")
    latest = dict(zip(cols, rows[0]))
    # Day-over-day burn — the only honest read of "how fast am I spending",
    # since requests_used resets each billing period.
    if len(rows) > 1 and latest["requests_used"] is not None:
        prev = dict(zip(cols, rows[1]))
        if prev["requests_used"] is not None:
            burn = latest["requests_used"] - prev["requests_used"]
            latest["burn_yesterday"] = burn if burn >= 0 else None
    return latest
