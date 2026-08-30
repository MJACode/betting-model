"""
One command that answers "is the pipeline healthy, and where does the time go".

WHY THIS EXISTS AS A SCRIPT AND NOT AS AN AGENT PROMPT
The pipeline-watch agent (docs/agents.md) runs on a schedule with no memory of
yesterday. If it had to discover the schema, guess which tables matter and
write its own SQL every morning, it would produce a different analysis each
day and its findings would not be comparable -- which is the one thing a watch
needs. So the DATA is deterministic and lives here; the agent's job is
judgement about what the numbers mean.

That division also makes the watch testable. A human can run this and see
exactly what the agent saw.

Usage:
    python -m scripts.pipeline_report              # last 24h
    python -m scripts.pipeline_report --hours 6
    python -m scripts.pipeline_report --json       # machine-readable
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.db import get_connection  # noqa: E402


def _rows(conn, sql, params=()):
    try:
        return conn.execute(sql, params).fetchall()
    except Exception as exc:                                  # noqa: BLE001
        return [("QUERY FAILED", str(exc)[:200])]


def collect(conn, hours: int = 24) -> dict:
    """Everything the watch needs, in one round trip per question."""
    out: dict = {}

    # ── Where the time goes. This is the whole point: until 2026-08-30 only 8
    # of 28 steps were timed, so 9 of a 12-minute pass was invisible.
    out["slowest_steps"] = _rows(conn, """
        SELECT replace(step, 'dispatch:', '') AS step,
               count(*) AS runs,
               round(avg(duration_s::numeric), 1) AS avg_s,
               round(max(duration_s::numeric), 1) AS max_s,
               round(sum(duration_s::numeric), 1) AS total_s
        FROM pipeline_log
        WHERE step LIKE 'dispatch:%%'
          AND created_at::timestamptz >= now() - (%s || ' hours')::interval
        GROUP BY 1
        ORDER BY avg_s DESC NULLS LAST
        LIMIT 15
    """, (hours,))

    # ── Is a pass finishing, and how fast. A pass that never finishes looks
    # exactly like a quiet market, which is why the ledger exists at all.
    out["recent_passes"] = _rows(conn, """
        SELECT started_at::timestamptz AS started,
               round((EXTRACT(epoch FROM (finished_at::timestamptz
                     - started_at::timestamptz))/60.0)::numeric, 1) AS minutes,
               steps_total, failed_steps
        FROM pipeline_runs
        WHERE started_at::timestamptz >= now() - (%s || ' hours')::interval
        ORDER BY started_at DESC LIMIT 12
    """, (hours,))

    # ── Anything a health check is actively complaining about.
    out["failing_checks"] = _rows(conn, """
        SELECT check_name, severity, status, left(detail, 180)
        FROM system_health_checks
        WHERE run_date >= (now() AT TIME ZONE 'America/New_York')::date - 1
          AND status <> 'OK'
        ORDER BY CASE severity WHEN 'CRIT' THEN 0 ELSE 1 END, check_name
    """)

    # ── Metered spend. A runaway loop is cheap to catch here and expensive not
    # to: the account is on a monthly reset, not an unlimited plan.
    out["api_burn_by_source"] = _rows(conn, """
        SELECT COALESCE(source, 'unknown') AS source,
               count(*) AS calls,
               round(COALESCE(SUM(credits), 0)::numeric, 0) AS credits,
               count(*) FILTER (WHERE NOT ok) AS errors
        FROM api_call_log
        WHERE host = 'api.the-odds-api.com'
          AND ts >= now() - (%s || ' hours')::interval
        GROUP BY 1 ORDER BY credits DESC NULLS LAST
    """, (hours,))

    # ── Did the board actually produce anything. An empty board and a broken
    # pipeline look identical (§7), so this is stated positively.
    out["picks_written"] = _rows(conn, """
        SELECT game_date, signal_type, count(*)
        FROM picks
        WHERE created_at::timestamptz >= now() - (%s || ' hours')::interval
        GROUP BY 1, 2 ORDER BY 1 DESC, 2
    """, (hours,))

    # ── Did anything reach a human. Nothing is ledgered unless a POST
    # confirmed, so a kind with zero rows has never once succeeded.
    out["delivery"] = _rows(conn, """
        SELECT kind, count(*), max(sent_at) AS latest
        FROM push_sent
        WHERE sent_at::timestamptz >= now() - (%s || ' hours')::interval
        GROUP BY 1 ORDER BY 1
    """, (hours,))

    return out


def render(data: dict, hours: int) -> str:
    lines = [f"PIPELINE REPORT — last {hours}h", "=" * 60, ""]
    titles = {
        "slowest_steps":     "SLOWEST STEPS (step, runs, avg_s, max_s, total_s)",
        "recent_passes":     "RECENT PASSES (started, minutes, steps, failed)",
        "failing_checks":    "HEALTH CHECKS NOT OK (name, severity, status, detail)",
        "api_burn_by_source": "ODDS API BURN (source, calls, credits, errors)",
        "picks_written":     "PICKS WRITTEN (date, signal, n)",
        "delivery":          "DELIVERED (kind, n, latest)",
    }
    for key, title in titles.items():
        lines.append(title)
        rows = data.get(key) or []
        if not rows:
            lines.append("  (none)")
        for r in rows:
            lines.append("  " + " | ".join("" if v is None else str(v) for v in r))
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    conn = get_connection()
    try:
        data = collect(conn, args.hours)
    finally:
        conn.close()

    if args.json:
        print(json.dumps({k: [list(map(str, r)) for r in v]
                          for k, v in data.items()}, indent=2))
    else:
        print(render(data, args.hours))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
