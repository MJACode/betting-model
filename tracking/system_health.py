"""
Daily system health check — verifies every API feed / data table is fresh.

Motivation: mlb_bullpen_stats silently froze at 2026-04-14 for ~80 days (no
daily ingest step existed) and fed wrong features to three models before it
was caught; the local WNBA/NBA "Basketball Daily Ingest" job also died
silently for ~5 days in June. This module makes any feed going stale visible
within one day.

Runs as the FINAL step of the daily pipeline (after all ingestion + scoring),
so expectations are "post-6am watermarks": team stats as-of today, yesterday's
game logs present, an odds snapshot in the last few hours, etc. Also runnable
any time via `python run_pipeline.py --step health-check` or
`python -m tracking.system_health` (note: running BEFORE the day's pipeline
may legitimately show a few pending feeds).

Checks are CADENCE-AWARE: each sport's checks only apply when that sport had
games in the relevant window (offseason/off-day → SKIPPED), so NBA in July or
UFC midweek never false-alarm.

Severity:
  CRIT — a load-bearing feed is stale → the step returns False → the daily
         GitHub Actions run shows RED (visible on GitHub mobile).
  WARN — degraded but not pick-blocking (best-effort feeds, settlement lag).

Every result row is upserted into `system_health_checks`
(UNIQUE(run_date, check_name) — re-runs overwrite), readable by Claude mobile:

    SELECT check_name, status, severity, detail, latest_seen
    FROM system_health_checks
    WHERE run_date = '{today}' AND status NOT IN ('OK', 'SKIPPED')
    ORDER BY CASE severity WHEN 'CRIT' THEN 0 ELSE 1 END, check_name;
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import MODELS, PROP_MODELS
from data.db import get_connection

# Models registered in config that intentionally have no trained artifact yet
# (blocked on historical odds for their target, or a pending data subscription).
# Update when one of these trains for real.
KNOWN_UNTRAINED = {
    "mlb_f5_over_under", "mlb_f5_runline",       # DK does not carry these markets
    "nhl_over_under", "nhl_puckline",            # need historical NHL lines
    "wnba_over_under", "wnba_spread",            # need historical DK WNBA lines
    "nba_over_under", "nba_spread",              # need historical DK NBA lines
    "golf_outright", "golf_top10", "golf_top20", # pending DataGolf backfill/training
    "golf_make_cut", "golf_matchup",
}

OK, STALE, EMPTY, SKIPPED, ERROR = "OK", "STALE", "EMPTY", "SKIPPED", "ERROR"


def _parse_ts(val):
    """Parse a stored timestamp (mixed formats: '...Z', '...-04:00', naive) to aware UTC."""
    if val is None:
        return None
    if isinstance(val, datetime):
        dt = val
    else:
        s = str(val).strip().replace(" ", "T", 1)
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _scalar(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def _games_count(conn, sport, start, end, finals_only=False):
    sql = """SELECT COUNT(*) FROM games
             WHERE sport = ? AND game_date >= ? AND game_date <= ?"""
    if finals_only:
        sql += " AND home_score IS NOT NULL"
    return _scalar(conn, sql, (sport, start, end)) or 0


class HealthReport:
    def __init__(self):
        self.results = []

    def add(self, check, status, severity, detail="", latest=None):
        self.results.append({
            "check_name": check, "status": status, "severity": severity,
            "detail": detail, "latest_seen": str(latest) if latest is not None else None,
        })

    def date_check(self, conn, check, severity, table, date_col, min_date,
                   gate_ok=True, gate_note="no games in window", where=""):
        """Generic 'MAX(date_col) >= min_date' freshness check."""
        if not gate_ok:
            self.add(check, SKIPPED, severity, gate_note)
            return
        try:
            latest = _scalar(conn, f"SELECT MAX({date_col}) FROM {table} {where}")
        except Exception as exc:
            self.add(check, ERROR, severity, f"query failed: {exc}")
            return
        if latest is None:
            self.add(check, EMPTY, severity, f"{table} has no rows")
        elif str(latest) >= min_date:
            self.add(check, OK, severity, f"latest {date_col} = {latest}", latest)
        else:
            self.add(check, STALE, severity,
                     f"latest {date_col} = {latest}, expected >= {min_date}", latest)

    def ts_check(self, conn, check, severity, table, ts_col, max_age_hours,
                 gate_ok=True, gate_note="no games in window"):
        """Generic 'MAX(ts_col) within max_age_hours of now' freshness check."""
        if not gate_ok:
            self.add(check, SKIPPED, severity, gate_note)
            return
        try:
            latest = _scalar(conn, f"SELECT MAX({ts_col}) FROM {table}")
        except Exception as exc:
            self.add(check, ERROR, severity, f"query failed: {exc}")
            return
        ts = _parse_ts(latest)
        if ts is None:
            self.add(check, EMPTY, severity, f"{table} has no parseable {ts_col}")
            return
        age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
        if age_h <= max_age_hours:
            self.add(check, OK, severity, f"last snapshot {age_h:.1f}h ago", latest)
        else:
            self.add(check, STALE, severity,
                     f"last snapshot {age_h:.1f}h ago (max {max_age_hours}h)", latest)


def run_system_health(run_date: str | None = None) -> dict:
    """Run all checks, upsert results into system_health_checks, log a summary.

    Returns {"ok": bool, "crit": int, "warn": int, "results": [...]}.
    ok=False (→ red Actions run) only when a CRIT check is STALE/EMPTY/ERROR.
    """
    if run_date is None:
        run_date = datetime.now().strftime("%Y-%m-%d")
    d = datetime.strptime(run_date, "%Y-%m-%d")
    yday = (d - timedelta(days=1)).strftime("%Y-%m-%d")
    d3 = (d - timedelta(days=3)).strftime("%Y-%m-%d")

    conn = get_connection()
    r = HealthReport()
    try:
        mlb_today = _games_count(conn, "MLB", run_date, run_date) > 0
        mlb_yday_finals = _games_count(conn, "MLB", yday, yday, finals_only=True) > 0
        any_today = _scalar(conn, "SELECT COUNT(*) FROM games WHERE game_date = ? AND sport <> 'GOLF'", (run_date,)) or 0

        # ── Odds feeds (The Odds API) ────────────────────────────────────────
        r.ts_check(conn, "odds_dk_lines", "CRIT", "odds", "snapshot_at", 12,
                   gate_ok=any_today > 0, gate_note="no games today")
        r.ts_check(conn, "player_prop_odds", "WARN", "player_prop_odds", "snapshot_at", 12,
                   gate_ok=mlb_today, gate_note="no MLB games today")

        # ── MLB stat feeds (MLB Stats API / Savant / Open-Meteo / ESPN) ─────
        r.date_check(conn, "mlb_team_stats", "CRIT", "mlb_team_stats", "as_of_date",
                     run_date, gate_ok=mlb_today, gate_note="no MLB games today")
        r.date_check(conn, "mlb_bullpen_workload", "CRIT", "mlb_bullpen_stats", "game_date",
                     yday, gate_ok=mlb_yday_finals, gate_note="no MLB finals yesterday")
        r.date_check(conn, "mlb_pitcher_stats", "WARN", "mlb_pitcher_stats", "game_date",
                     d3, gate_ok=_games_count(conn, "MLB", d3, yday, finals_only=True) > 0,
                     gate_note="no MLB finals in last 3 days")
        r.date_check(conn, "mlb_weather", "CRIT", "game_weather", "game_date",
                     run_date, gate_ok=mlb_today, gate_note="no MLB games today")
        r.date_check(conn, "mlb_player_game_log", "CRIT", "player_game_log", "game_date",
                     yday, gate_ok=mlb_yday_finals, gate_note="no MLB finals yesterday")
        r.date_check(conn, "injuries", "WARN", "injuries", "report_date",
                     yday, gate_ok=any_today > 0, gate_note="no games today")
        r.date_check(conn, "lineups", "WARN", "lineup_slots", "game_date",
                     yday, gate_ok=mlb_yday_finals, gate_note="no MLB finals yesterday")
        r.date_check(conn, "umpires", "WARN", "umpires", "game_date",
                     yday, gate_ok=mlb_yday_finals, gate_note="no MLB finals yesterday")
        r.date_check(conn, "public_betting", "WARN", "public_betting", "game_date",
                     run_date, gate_ok=mlb_today, gate_note="no MLB games today")

        # ── Final scores landing (all sports; catches dead local ingest jobs) ─
        # GOLF excluded: tournament rows keep NULL scores by design.
        rows = conn.execute("""
            SELECT sport, game_date, COUNT(*) FROM games
            WHERE game_date >= ? AND game_date <= ?
              AND sport <> 'GOLF' AND home_score IS NULL
            GROUP BY sport, game_date ORDER BY sport, game_date
        """, (d3, yday)).fetchall()
        missing_old = [(s, gd, n) for s, gd, n in rows if str(gd) < yday]
        if not rows:
            r.add("final_scores", OK, "CRIT", f"all finals present {d3}..{yday}")
        else:
            detail = "; ".join(f"{s} {gd}: {n} game(s) missing final score" for s, gd, n in rows)
            # ≥2 games older than yesterday = a dead ingest job, not a postponement
            if sum(n for _, _, n in missing_old) >= 2:
                r.add("final_scores", STALE, "CRIT", detail + " — ingest job likely dead (check local Basketball Daily Ingest / results steps)")
            else:
                r.add("final_scores", STALE, "WARN", detail + " — could be a postponement")

        # ── Basketball box-score logs (local Task Scheduler job) ────────────
        for sport, table, check in (("WNBA", "wnba_player_game_log", "wnba_game_log"),
                                    ("NBA", "nba_player_game_log", "nba_game_log")):
            last_final = _scalar(conn, """SELECT MAX(game_date) FROM games
                                          WHERE sport = ? AND game_date <= ? AND home_score IS NOT NULL""",
                                 (sport, yday))
            recent = last_final is not None and str(last_final) >= d3
            r.date_check(conn, check, "WARN", table, "game_date",
                         str(last_final) if recent else run_date,
                         gate_ok=recent, gate_note=f"no {sport} finals in last 3 days")

        # ── Golf odds (DataGolf) — only during an active/upcoming tournament ─
        golf_active = _scalar(conn, """SELECT COUNT(*) FROM games WHERE sport = 'GOLF'
                                       AND game_date >= ? AND game_date <= ?""",
                              (d3, (d + timedelta(days=7)).strftime("%Y-%m-%d"))) or 0
        r.ts_check(conn, "golf_odds", "WARN", "golf_odds", "snapshot_at", 24,
                   gate_ok=golf_active > 0, gate_note="no golf tournament in window")

        # ── Models + picks ───────────────────────────────────────────────────
        expected = (set(MODELS.keys()) | set(PROP_MODELS.keys())) - KNOWN_UNTRAINED
        active = {row[0] for row in conn.execute(
            "SELECT DISTINCT model_id FROM model_registry WHERE is_active = 1").fetchall()}
        missing = sorted(expected - active)
        if missing:
            r.add("model_registry", STALE, "WARN",
                  f"{len(missing)} config model(s) with no active artifact: {', '.join(missing)}")
        else:
            r.add("model_registry", OK, "WARN", f"{len(expected)} expected models all active")

        n_picks = _scalar(conn, "SELECT COUNT(*) FROM picks WHERE game_date = ?", (run_date,)) or 0
        if any_today == 0:
            r.add("picks_scored_today", SKIPPED, "CRIT", "no games today")
        elif n_picks > 0:
            r.add("picks_scored_today", OK, "CRIT", f"{n_picks} pick rows for {run_date}")
        else:
            r.add("picks_scored_today", EMPTY, "CRIT",
                  f"games exist for {run_date} but zero pick rows — scorer did not run/write")

        n_lag = _scalar(conn, """
            SELECT COUNT(*) FROM picks p JOIN games g ON g.game_id = p.game_id
            WHERE p.signal_type = 'BET' AND p.result IS NULL
              AND p.game_date >= ? AND p.game_date <= ?
              AND g.home_score IS NOT NULL AND p.is_live IS NOT TRUE
        """, ((d - timedelta(days=14)).strftime("%Y-%m-%d"),
              (d - timedelta(days=2)).strftime("%Y-%m-%d"))) or 0
        if n_lag > 0:
            r.add("settlement_lag", STALE, "WARN",
                  f"{n_lag} BET pick(s) >=2 days old with final scores but no result")
        else:
            r.add("settlement_lag", OK, "WARN", "no settled-score picks awaiting settlement")

        # ── Persist + summarize ──────────────────────────────────────────────
        checked_at = datetime.now(timezone.utc).isoformat()
        for res in r.results:
            conn.execute("""
                INSERT INTO system_health_checks
                    (run_date, check_name, status, severity, detail, latest_seen, checked_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (run_date, check_name) DO UPDATE SET
                    status = EXCLUDED.status, severity = EXCLUDED.severity,
                    detail = EXCLUDED.detail, latest_seen = EXCLUDED.latest_seen,
                    checked_at = EXCLUDED.checked_at
            """, (run_date, res["check_name"], res["status"], res["severity"],
                  res["detail"], res["latest_seen"], checked_at))
        conn.commit()
    finally:
        conn.close()

    bad = [x for x in r.results if x["status"] in (STALE, EMPTY, ERROR)]
    crit = [x for x in bad if x["severity"] == "CRIT"]
    warn = [x for x in bad if x["severity"] != "CRIT"]
    for res in r.results:
        line = f"[{res['severity']}] {res['check_name']}: {res['status']} — {res['detail']}"
        if res["status"] in (STALE, EMPTY, ERROR):
            (logger.error if res["severity"] == "CRIT" else logger.warning)(line)
        else:
            logger.info(line)
    if crit:
        logger.error(f"SYSTEM HEALTH: {len(crit)} CRITICAL failure(s), {len(warn)} warning(s)")
    elif warn:
        logger.warning(f"SYSTEM HEALTH: OK with {len(warn)} warning(s)")
    else:
        logger.success("SYSTEM HEALTH: all feeds fresh")

    return {"ok": not crit, "crit": len(crit), "warn": len(warn), "results": r.results}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run the daily system health check")
    parser.add_argument("--date", help="Run date YYYY-MM-DD (default: today)")
    args = parser.parse_args()
    out = run_system_health(args.date)
    sys.exit(0 if out["ok"] else 1)
