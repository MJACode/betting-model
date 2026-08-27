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
from zoneinfo import ZoneInfo
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
        # NOT gated on games existing: MLB/WNBA games rows are CREATED by this
        # feed, so "no games today" is exactly what a dead odds feed looks like.
        # During the 2026-08-14 quota outage the old gate reported SKIPPED on
        # day 2+ — quieter than day 1 — while zero picks were being written.
        # (A check must never be gated on the thing it detects — the
        # wnba_game_log lesson.) Two tiers keep genuine off-days quiet:
        #   games rows exist today  → normal 12h freshness check
        #   no games rows today     → SKIPPED only while the newest snapshot is
        #                             under 48h old; beyond that, games-missing
        #                             + odds-missing together mean the feed
        #                             itself is down (quota/key) → CRIT.
        if any_today > 0:
            r.ts_check(conn, "odds_dk_lines", "CRIT", "odds", "snapshot_at", 12)
        else:
            _odds_ts = _parse_ts(_scalar(conn, "SELECT MAX(snapshot_at) FROM odds"))
            _odds_age_h = (None if _odds_ts is None else
                           (datetime.now(timezone.utc) - _odds_ts).total_seconds() / 3600)
            if _odds_age_h is not None and _odds_age_h <= 48:
                r.add("odds_dk_lines", SKIPPED, "CRIT",
                      f"no games today (last snapshot {_odds_age_h:.1f}h ago — plausible off-day)")
            else:
                age_note = "no parseable snapshot" if _odds_age_h is None else f"{_odds_age_h:.1f}h ago"
                r.add("odds_dk_lines", STALE, "CRIT",
                      f"no games rows for {run_date} AND last odds snapshot {age_note} "
                      f"(max 48h) — the odds feed itself is likely down (quota/key/API); "
                      f"games rows come from this feed, so 'no games today' cannot be trusted")
        r.ts_check(conn, "player_prop_odds", "WARN", "player_prop_odds", "snapshot_at", 12,
                   gate_ok=mlb_today, gate_note="no MLB games today")

        # ── Odds API credit quota (odds_api_quota, written by odds_quota.py) ─
        # Early warning BEFORE credits run out — on 2026-08-14 the quota hit
        # zero with no notice and the odds feed (and with it all MLB/WNBA games
        # + picks) was dead for 2.5 days. WARN, never CRIT: when credits
        # actually hit zero, odds_dk_lines CRITs on the real impact.
        try:
            qrow = conn.execute("""
                SELECT quota_date, requests_used, requests_remaining, observed_at
                FROM odds_api_quota ORDER BY quota_date DESC LIMIT 1
            """).fetchone()
            if qrow is None:
                r.add("odds_api_credits", SKIPPED, "WARN",
                      "no quota telemetry yet (populates on the next odds fetch)")
            else:
                q_date, q_used, q_rem, q_obs = qrow
                q_obs_ts = _parse_ts(q_obs)
                obs_age_h = (None if q_obs_ts is None else
                             (datetime.now(timezone.utc) - q_obs_ts).total_seconds() / 3600)
                if obs_age_h is not None and obs_age_h > 72:
                    r.add("odds_api_credits", SKIPPED, "WARN",
                          f"quota telemetry stale ({obs_age_h:.0f}h old) — "
                          f"odds_dk_lines covers a dead feed", q_obs)
                elif q_rem is None:
                    r.add("odds_api_credits", SKIPPED, "WARN",
                          "API did not report x-requests-remaining", q_obs)
                else:
                    q_rem, q_used = float(q_rem), float(q_used or 0)
                    total = q_used + q_rem
                    pct = (q_rem / total * 100) if total > 0 else 0.0
                    # Yesterday's burn, when comparable (same billing period)
                    prev = conn.execute("""
                        SELECT requests_used FROM odds_api_quota
                        WHERE quota_date < ? ORDER BY quota_date DESC LIMIT 1
                    """, (q_date,)).fetchone()
                    burn = ""
                    if prev and prev[0] is not None and float(prev[0]) <= q_used:
                        daily = q_used - float(prev[0])
                        burn = f"; burning ~{daily:,.0f}/day"
                        if daily > 0:
                            burn += f" (~{q_rem / daily:.1f} days left at this rate)"
                    detail = (f"{q_rem:,.0f} of {total:,.0f} credits remaining "
                              f"({pct:.1f}%){burn}")
                    if q_rem < 1000 or pct < 15:
                        r.add("odds_api_credits", STALE, "WARN",
                              detail + " — top up / raise the plan or cut refresh "
                              "cadence before the feed dies (2026-08-14 incident)", q_obs)
                    else:
                        r.add("odds_api_credits", OK, "WARN", detail, q_obs)
        except Exception as exc:
            r.add("odds_api_credits", ERROR, "WARN", f"query failed: {exc}")

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
        # Only MLB/NHL missing-finals are CRIT — those are the sports GitHub Actions
        # itself controls (statsapi / NHL API both reachable from the runner), so a
        # gap there is a genuine Actions/pipeline failure worth reddening the run.
        #
        # UFC and NBA are excluded from the CRIT tally (WARN only):
        #   • UFC — The Odds API's mma_mixed_martial_arts feed also lists non-UFC
        #     promotions (Cage Warriors / PFL / regional cards); those games rows keep
        #     NULL scores forever (the ufcstats mirror only covers UFC) — a structural
        #     false positive, and the scorer's min-history gate keeps them pick-less.
        #   • NBA — final scores + box scores still come only from nba_api
        #     (stats.nba.com), which blocks datacenter IPs, so they land via the LOCAL
        #     residential-IP "Basketball Daily Ingest" job. When that job falls behind,
        #     the worker cannot fix it — reddening the run would wrongly imply the
        #     pipeline broke. The nba_game_log WARN check surfaces that lag.
        #
        # WNBA *is* CRIT (2026-08-07): since session 97 its finals come from the
        # worker-controlled ESPN step (step_wnba_results), so a WNBA gap IS a
        # pipeline failure — this is the follow-up the box-score block below asked
        # for. It was promoted after site.api.espn.com started refusing the worker
        # on 2026-08-05 and three days of WNBA finals silently went missing behind a
        # green run (the step logs "✗ WNBA results failed" but returns False, and a
        # WARN never reddens anything). The local nba_api job remains a redundant
        # writer, so a CRIT here means BOTH paths are down — which is exactly when
        # someone needs to know.
        CRIT_FINALS_SPORTS = {"MLB", "NHL", "WNBA"}
        missing_old_crit = [(s, gd, n) for s, gd, n in missing_old if s in CRIT_FINALS_SPORTS]
        if not rows:
            r.add("final_scores", OK, "CRIT", f"all finals present {d3}..{yday}")
        else:
            detail = "; ".join(f"{s} {gd}: {n} game(s) missing final score" for s, gd, n in rows)
            # ≥2 MLB/NHL games older than yesterday = a dead ingest job, not a postponement
            if sum(n for _, _, n in missing_old_crit) >= 2:
                r.add("final_scores", STALE, "CRIT", detail + " — MLB/NHL/WNBA ingest job likely dead (check results steps)")
            else:
                r.add("final_scores", STALE, "WARN", detail + " — UFC/NBA local ingest or postponement (non-CRIT)")

        # ── Basketball box-score logs ────────────────────────────────────────
        # WNBA: fed by BOTH the worker's ESPN results step (step_wnba_results,
        # pre-settle) and the local Basketball Daily Ingest job (nba_api).
        # NBA: local job only (ESPN NBA results step is a follow-up for Oct).
        #
        # The gate is "were games PLAYED in the window", NOT "did finals land".
        # Gating on finals was circular: when the results ingest died on
        # 2026-08-05, no finals landed, so this check reported SKIPPED ("no WNBA
        # finals in last 3 days") on the very days it should have been screaming.
        # A check must never be gated on the thing it is meant to detect. Gating
        # on the schedule keeps the cadence-awareness that matters (NBA in July,
        # WNBA off-days correctly SKIP) without the blind spot.
        for sport, table, check in (("WNBA", "wnba_player_game_log", "wnba_game_log"),
                                    ("NBA", "nba_player_game_log", "nba_game_log")):
            played = _scalar(conn, """SELECT COUNT(*) FROM games
                                      WHERE sport = ? AND game_date >= ? AND game_date <= ?""",
                             (sport, d3, yday)) or 0
            last_final = _scalar(conn, """SELECT MAX(game_date) FROM games
                                          WHERE sport = ? AND game_date <= ? AND home_score IS NOT NULL""",
                                 (sport, yday))
            # Expect box scores as fresh as the newest final we hold, but never
            # older than the window — so a stalled finals feed still trips this.
            expect = max(str(last_final), d3) if last_final is not None else d3
            r.date_check(conn, check, "WARN", table, "game_date", expect,
                         gate_ok=played > 0,
                         gate_note=f"no {sport} games scheduled in last 3 days")

        # ── ESPN reachability probe (diagnostic, not an impact check) ────────
        # WNBA finals come from site.api.espn.com, which stopped serving the
        # Railway worker on 2026-08-05. The exception was only ever visible in
        # the worker's stdout, so diagnosing it meant reading Railway logs by
        # hand — and Railway is not reachable from the dev sandbox. This records
        # the actual failure reason into system_health_checks (anon-readable),
        # so "why did WNBA results fail" is answerable from Supabase alone.
        #
        # Since 2026-08-11 the results ingestor falls back to
        # sports.core.api.espn.com when site.api fails, so a site block alone
        # no longer stops finals — when site fails, the core host is probed
        # too, and only "BOTH hosts down" is reported as finals-blocking.
        #
        # Deliberately WARN: final_scores already CRITs on the real impact, and
        # a transient ESPN blip should not redden a run on its own. Never
        # raises, short timeout — a health probe must not hang the pipeline.
        wnba_recent = _scalar(conn, """SELECT COUNT(*) FROM games
                                       WHERE sport = 'WNBA' AND game_date >= ? AND game_date <= ?""",
                              (d3, yday)) or 0
        if wnba_recent == 0:
            r.add("espn_wnba_api", SKIPPED, "WARN", "no WNBA games scheduled in last 3 days")
        else:
            probe_date = yday.replace("-", "")
            try:
                import requests
                from data.ingestors.injury_ingestor import ESPN_HEADERS
                site_fail = None
                try:
                    resp = requests.get(
                        "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard",
                        params={"dates": probe_date}, headers=ESPN_HEADERS, timeout=8)
                    if resp.status_code == 200:
                        n_events = len((resp.json() or {}).get("events", []) or [])
                        r.add("espn_wnba_api", OK, "WARN",
                              f"site.api.espn.com OK, {n_events} event(s) for {yday}")
                    else:
                        site_fail = f"HTTP {resp.status_code}"
                except Exception as exc:
                    site_fail = f"{type(exc).__name__}: {str(exc)[:120]}"
                if site_fail:
                    # site.api down → is the sports.core fallback path alive?
                    try:
                        core = requests.get(
                            "https://sports.core.api.espn.com/v2/sports/basketball/"
                            "leagues/wnba/events",
                            params={"dates": probe_date, "limit": 1},
                            headers=ESPN_HEADERS, timeout=8)
                        core_ok = core.status_code == 200
                        core_note = f"HTTP {core.status_code}"
                    except Exception as exc:
                        core_ok = False
                        core_note = f"{type(exc).__name__}: {str(exc)[:120]}"
                    if core_ok:
                        r.add("espn_wnba_api", OK, "WARN",
                              f"site.api.espn.com {site_fail} for {yday}; "
                              f"sports.core fallback OK — finals land via core")
                    else:
                        r.add("espn_wnba_api", ERROR, "WARN",
                              f"site.api.espn.com {site_fail} AND sports.core "
                              f"{core_note} for {yday} — BOTH ESPN hosts down, "
                              f"WNBA finals cannot land")
            except Exception as exc:
                r.add("espn_wnba_api", ERROR, "WARN",
                      f"probe failed: {type(exc).__name__}: {str(exc)[:200]}")

        # ── Golf odds (DataGolf) — only during an active/upcoming tournament ─
        golf_active = _scalar(conn, """SELECT COUNT(*) FROM games WHERE sport = 'GOLF'
                                       AND game_date >= ? AND game_date <= ?""",
                              (d3, (d + timedelta(days=7)).strftime("%Y-%m-%d"))) or 0
        r.ts_check(conn, "golf_odds", "WARN", "golf_odds", "snapshot_at", 24,
                   gate_ok=golf_active > 0, gate_note="no golf tournament in window")

        # ── Schema drift ─────────────────────────────────────────────────────
        # Merging a migration does NOT apply it: setup_database() is only
        # reachable from first_time_setup() and the DB Migrate workflow, so a
        # column added in a PR reaches master without reaching Postgres. When
        # that happens the code that selects it fails at runtime — 2026-08-23
        # picks.prop_market/player_key shipped this way and would have broken
        # prop settlement for EVERY sport on the next morning's settle, not
        # just the model that introduced them. CRIT so the run goes red the
        # same day instead of at the first query that needs the column.
        try:
            from data.db_setup import _MIGRATIONS
            want: dict[str, set[str]] = {}
            for tbl, col, _type in _MIGRATIONS:
                want.setdefault(tbl, set()).add(col)
            gone = []
            for tbl, cols in sorted(want.items()):
                have = {row[0] for row in conn.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = ?",
                    (tbl,)).fetchall()}
                if not have:
                    continue          # table itself absent — its own check covers that
                gone += [f"{tbl}.{c}" for c in sorted(cols - have)]
            if gone:
                r.add("schema_drift", STALE, "CRIT",
                      f"{len(gone)} merged column(s) missing from the database — "
                      f"run the DB Migrate workflow: {', '.join(gone)}")
            else:
                r.add("schema_drift", OK, "CRIT",
                      f"all {sum(len(c) for c in want.values())} migrated columns present")
        except Exception as exc:
            r.add("schema_drift", SKIPPED, "CRIT",
                  f"could not read information_schema: {type(exc).__name__}")

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

        # Opening-signal capture. This is the step that feeds Discord posts, the
        # mobile signal push AND the shadow track — and when it dies it dies
        # SILENTLY as far as the data is concerned: picks keep scoring, so every
        # other check stays green while no signal reaches anyone. That is exactly
        # what happened 2026-08-24..27, when a corrupted SQL literal made capture
        # throw on every pass for three days before anyone noticed.
        #
        # A BET pick whose game_date has no opening_signals row at all means
        # capture did not run or raised. CRIT: silent non-delivery of signals is
        # as bad as not generating them.
        n_uncaptured = _scalar(conn, """
            SELECT COUNT(DISTINCT p.game_date)
            FROM picks p
            WHERE p.signal_type = 'BET' AND p.is_live IS NOT TRUE
              AND p.game_date >= ? AND p.game_date <= ?
              AND NOT EXISTS (
                  SELECT 1 FROM opening_signals os WHERE os.game_date = p.game_date
              )
        """, ((d - timedelta(days=3)).strftime("%Y-%m-%d"),
              d.strftime("%Y-%m-%d"))) or 0
        n_recent_bets = _scalar(conn, """
            SELECT COUNT(*) FROM picks
            WHERE signal_type = 'BET' AND is_live IS NOT TRUE
              AND game_date >= ? AND game_date <= ?
        """, ((d - timedelta(days=3)).strftime("%Y-%m-%d"),
              d.strftime("%Y-%m-%d"))) or 0
        if n_recent_bets == 0:
            # No BET picks in the window is a thin board, not a broken capture.
            r.add("opening_signal_capture", SKIPPED, "CRIT",
                  "no BET picks in the last 3 days to capture")
        elif n_uncaptured > 0:
            r.add("opening_signal_capture", STALE, "CRIT",
                  f"{n_uncaptured} recent date(s) have BET picks but ZERO opening_signals "
                  f"rows — capture is failing, so no signal is reaching Discord or push")
        else:
            r.add("opening_signal_capture", OK, "CRIT",
                  f"every date with BET picks in the last 3 days has captured signals")

        # ── Refresh-pass completion (pipeline_runs) ─────────────────────────
        # THE 2026-08-27 LESSON. A NameError killed every hourly pass at step 9
        # of 24 for three days. Every check above stayed green, because they all
        # measure DATA freshness and the daily 6am pipeline — which continues
        # past step failures — kept the data fresh. Nothing measured whether the
        # PASSES themselves were completing. These two checks do.
        #
        # Cadence: hourly :17 (7am-5pm ET) + every 10 min (6pm-11:50pm ET). So
        # inside 7am-midnight ET a finished pass should never be >90 min old.
        # Outside that window no pass is due, so the check SKIPS rather than
        # crying wolf overnight.
        et_now = datetime.now(ZoneInfo("America/New_York"))
        in_pass_window = 7 <= et_now.hour <= 23
        try:
            last_finish = _parse_ts(_scalar(
                conn,
                "SELECT MAX(finished_at) FROM pipeline_runs WHERE finished_at IS NOT NULL"))
            ledger_readable = True
        except Exception as exc:
            # The ledger creates its own table on the first pass, so this means
            # the ledger itself never ran -- i.e. the observability is the thing
            # that is broken. Surface it rather than skipping quietly.
            r.add("refresh_pass_completion", ERROR, "CRIT",
                  f"cannot read pipeline_runs: {exc}")
            r.add("refresh_pass_steps", ERROR, "CRIT",
                  f"cannot read pipeline_runs: {exc}")
            ledger_readable = False
            last_finish = None

        # A run that started long ago and never finished = hang / OOM / killed
        # worker. Absence of finished_at is the only way that becomes visible.
        stuck = 0
        if ledger_readable:
            stuck = _scalar(conn, """
                SELECT COUNT(*) FROM pipeline_runs
                WHERE finished_at IS NULL AND started_at < ?
            """, ((datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),)) or 0

        if not ledger_readable:
            pass                     # already reported above
        elif last_finish is None:
            # The health check runs as a STEP, i.e. before this pass calls
            # finish_run - so on the first pass after this ships there is a
            # started row but no finished one yet. That is startup, not a fault.
            started_recently = _scalar(conn, """
                SELECT COUNT(*) FROM pipeline_runs WHERE started_at > ?
            """, ((datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),)) or 0
            if started_recently:
                r.add("refresh_pass_completion", SKIPPED, "CRIT",
                      "run ledger just started recording - no completed pass yet")
            else:
                r.add("refresh_pass_completion", EMPTY, "CRIT",
                      "pipeline_runs has no completed run - the run ledger is "
                      "not being written")
        else:
            age_m = (datetime.now(timezone.utc) - last_finish).total_seconds() / 60
            if not in_pass_window:
                r.add("refresh_pass_completion", SKIPPED, "CRIT",
                      f"outside the 7am-midnight ET pass window "
                      f"(last completed pass {age_m:.0f} min ago)", last_finish)
            elif age_m > 90:
                r.add("refresh_pass_completion", STALE, "CRIT",
                      f"last completed pass {age_m:.0f} min ago (max 90) - passes "
                      f"are not finishing; picks are not being scored or pushed",
                      last_finish)
            elif stuck > 0:
                r.add("refresh_pass_completion", STALE, "CRIT",
                      f"{stuck} run(s) started >2h ago and never finished - a pass "
                      f"is hanging or the worker was killed mid-pass", last_finish)
            else:
                r.add("refresh_pass_completion", OK, "CRIT",
                      f"last completed pass {age_m:.0f} min ago", last_finish)

        # ── Which steps are failing, and persistently? ───────────────────────
        # A step failing in EVERY one of the last 3 passes is a real break, not
        # a blip - that is the exact shape of the WNBA NameError. A step failing
        # in some but not all is usually a flaky upstream API and stays WARN.
        recent = [] if not ledger_readable else conn.execute("""
            SELECT failed_steps FROM pipeline_runs
            WHERE finished_at IS NOT NULL AND run_kind <> 'daily'
            ORDER BY finished_at DESC LIMIT 3
        """).fetchall()
        if not ledger_readable:
            pass                     # already reported above
        elif len(recent) < 3:
            r.add("refresh_pass_steps", SKIPPED, "CRIT",
                  f"only {len(recent)} completed refresh pass(es) on record - "
                  f"need 3 to judge whether a failure is persistent")
        else:
            per_pass = [set((row[0] or "").split(",")) - {""} for row in recent]
            persistent = sorted(set.intersection(*per_pass))
            intermittent = sorted(set.union(*per_pass) - set(persistent))
            if persistent:
                r.add("refresh_pass_steps", STALE, "CRIT",
                      f"step(s) failing in ALL of the last 3 passes: "
                      f"{', '.join(persistent)} - everything after them in the "
                      f"chain is degraded")
            elif intermittent:
                r.add("refresh_pass_steps", STALE, "WARN",
                      f"intermittent failures (not in every pass): "
                      f"{', '.join(intermittent)}")
            else:
                r.add("refresh_pass_steps", OK, "CRIT",
                      "no step failures in the last 3 refresh passes")

        # ── Signal delivery (captured -> actually pushed) ────────────────────
        # opening_signal_capture proves a signal was LOCKED. This proves it was
        # DELIVERED. Uses the notifier's own predicate (same thresholds join,
        # same ':early' shadow-row exclusion) so the two cannot disagree about
        # what counts as postable.
        try:
            from config import DISCORD_WEBHOOKS, DISCORD_WEBHOOK_DEFAULT
        except Exception:
            DISCORD_WEBHOOKS, DISCORD_WEBHOOK_DEFAULT = {}, ""
        wired = set(DISCORD_WEBHOOKS)
        if not wired and not DISCORD_WEBHOOK_DEFAULT:
            r.add("signal_delivery", SKIPPED, "CRIT",
                  "no DISCORD_WEBHOOK_* configured - nothing to deliver to")
        else:
            # A sport only counts if its channel (or the catch-all) exists.
            sport_pred = ("" if DISCORD_WEBHOOK_DEFAULT
                          else " AND os.sport IN (" +
                               ",".join("?" for _ in wired) + ")")
            grace = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
            params = ([d3, run_date]
                      + ([] if DISCORD_WEBHOOK_DEFAULT else sorted(wired))
                      + [grace])
            undelivered = _scalar(conn, f"""
                SELECT COUNT(*)
                FROM opening_signals os
                JOIN model_action_thresholds t ON t.model_id = os.model_id
                WHERE os.game_date >= ? AND os.game_date <= ?
                  AND os.lock_key NOT LIKE '%:early'
                  AND t.paused = FALSE
                  AND os.model_probability >= t.min_prob
                  AND (t.prob_only = TRUE OR os.edge >= COALESCE(t.min_edge, 0))
                  AND (t.min_odds IS NULL OR os.dk_odds IS NULL
                       OR os.dk_odds >= t.min_odds)
                  {sport_pred}
                  AND os.locked_at < ?          -- grace: a signal locked minutes
                                                -- ago has not had a pass yet
                  AND NOT EXISTS (
                      SELECT 1 FROM push_sent s
                      WHERE s.lock_key = os.lock_key AND s.kind = 'discord_signal'
                  )
            """, tuple(params)) or 0
            pending = undelivered
            if pending > 0:
                r.add("signal_delivery", STALE, "CRIT",
                      f"{pending} postable signal(s) in the last 3 days have no "
                      f"discord_signal ledger row - signals are being generated "
                      f"but not delivered")
            else:
                r.add("signal_delivery", OK, "CRIT",
                      f"every postable signal in the last 3 days was delivered "
                      f"({wired and ', '.join(sorted(wired)) or 'default channel'})")

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
