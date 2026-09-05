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

import json
import os

from data.ddl_guard import schema_is_current

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


# Index names INDEXES creates, named separately so the guard below can ask the
# catalog for them without parsing SQL.
INDEX_NAMES = ("idx_api_call_ts", "idx_api_call_api_ts")


def ensure_table(conn) -> None:
    """Create the table, indexes and lockdown. Idempotent, best-effort.

    Returns without touching the database once the table already matches — see
    data/ddl_guard.py. That short-circuit is not an optimisation: this function
    runs on every writer reconnect from every process that makes an HTTP call,
    and re-running the block cost 11.6 HOURS of production database time and
    ~3,600 forced PostgREST schema-cache reloads, during which the API answered
    503 to the mobile app. Measured 2026-09-01.
    """
    if schema_is_current(
        conn, "api_call_log",
        indexes=INDEX_NAMES, rls=True, revoked_from=("anon", "authenticated"),
    ):
        return
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


# ── operational panels (models, performance, community) ──────────────────────
# These are the SLOW ones. Every query below is either index-served or read
# behind a TTL cache in server.py — see monitoring/cache.py for why that is not
# optional at a 10s poll rate.

def model_roster(conn) -> list[dict]:
    """Every registered model: its live/paused state, its cuts, and the trained
    artifact currently behind it.

    model_action_thresholds is the authority on whether a model FIRES (it is
    synced from config.py by the daily pipeline, and it is what the app's own
    action filter reads). model_registry is the authority on WHICH artifact is
    scoring. A model with thresholds but no active registry row is registered
    and untrained — which is a real state (NHL totals, the golf models) and one
    worth seeing on a dashboard rather than discovering at score time.
    """
    sql = """
        SELECT t.model_id, t.paused, t.prob_only, t.min_prob, t.min_edge, t.min_odds,
               r.version, r.trained_on, r.holdout_accuracy, r.calibration_score,
               r.holdout_picks
        FROM model_action_thresholds t
        LEFT JOIN LATERAL (
            SELECT version, trained_on, holdout_accuracy, calibration_score,
                   holdout_picks
            FROM model_registry mr
            WHERE mr.model_id = t.model_id AND mr.is_active = 1
            ORDER BY mr.created_at DESC LIMIT 1
        ) r ON TRUE
        ORDER BY t.model_id
    """
    cols = ("model_id", "paused", "prob_only", "min_prob", "min_edge", "min_odds",
            "version", "trained_on", "holdout_accuracy", "calibration_score",
            "holdout_picks")
    return [dict(zip(cols, r)) for r in _rows(conn, sql)]


def model_performance(conn) -> list[dict]:
    """Settled BET record per model, from the graded matview.

    Deliberately mv_scored_pick_outcomes and not v_model_full_outcome_record:
    the view re-grades every pick against the CURRENT thresholds and costs
    1,596ms / 568k buffer hits, which cannot sit behind a dashboard at any poll
    rate. The matview is the same grading, materialised — 285ms — and filtering
    to signal_type='BET' gives the operationally honest question: what did the
    model actually tell us to bet, and how did that do?

    profit_units is NULL for prob-only picks with no real price (batter HR),
    so units and ROI are computed over the PRICED subset and the count is
    reported beside them. Fabricating a price for those is how a record-only
    model ends up with invented P&L.

    A MODEL THE MATVIEW DOES NOT GRADE TAKES ITS RECORD FROM `picks`.
    The matview grades what it can regrade from box scores, so it carries an
    explicit model allow-list and excludes in-play picks twice (`p.is_live IS
    NOT TRUE` plus no `*_live_*` model in the list). `profit_units` exists ONLY
    in the matview, so every model outside it joined to nothing and reported
    settled=0 — which this dashboard renders as "registered · awaiting first
    pick", the exact confusion tests/test_registered_not_firing.py exists to
    prevent. Measured 2026-09-04, eleven models with a real settled BET record
    read as never having fired, 182 bets in all:

        mlb_live_total_runs  94  58-36  +12.25u   <- best MLB model on the app
        mlb_live_win_prob    17   7-10   -5.44u      (retired)
        mlb_live_runline     16   6-10   -6.08u      (retired)
        ufc_total_rounds     13   8-5    -1.86u
        mlb_f5_over_under    11   8-1    unpriced
        ncaaf_live_total      8   3-5    -2.50u
        mlb_f5_runline        7   4-3    unpriced
        wnba_spread           6   2-4    -2.15u
        ufc_method_of_victory 5   3-2    unpriced (no method market exists)
        ufc_moneyline         3   2-1    +0.57u
        ncaaf_live_win_prob   2   1-1    -0.58u

    The second arm keys on "has no row in the matview at all" rather than on a
    model-id pattern, so the two arms are disjoint BY CONSTRUCTION — a model is
    graded by exactly one of them, never split across both — and the arm empties
    itself as the matview's allow-list grows, instead of going stale.
    `picks.profit_flat` is units x 100, so units divide back out.

    What this deliberately does NOT do: fold a pre-game model's IN-PLAY picks
    into its pre-game row. A model the matview already grades is untouched here,
    so its in-play picks stay out exactly as before — they are a different bet at
    a different price and CLAUDE.md section 6 keeps the two apart. (Today no
    model reaching the second arm has picks of both kinds; if one ever does, its
    row would blend them and this is where to split it.)
    """
    sql = """
        WITH agg AS (
            SELECT model_id, sport,
                   COUNT(*)                                   AS settled,
                   COUNT(*) FILTER (WHERE result = 'WIN')     AS wins,
                   COUNT(*) FILTER (WHERE result = 'LOSS')    AS losses,
                   COUNT(*) FILTER (WHERE result = 'PUSH')    AS pushes,
                   COUNT(profit_units)                        AS priced,
                   COALESCE(SUM(profit_units), 0)             AS units,
                   MAX(game_date)                             AS last_date
            FROM mv_scored_pick_outcomes
            WHERE signal_type = 'BET' AND result IN ('WIN', 'LOSS', 'PUSH')
            GROUP BY model_id, sport
            UNION ALL
            -- Models the matview does not grade at all (the live lanes, UFC,
            -- wnba_spread, the F5 secondary markets), from picks. The NOT
            -- EXISTS is what makes the two arms disjoint, so UNION ALL cannot
            -- double-count and a model is never split across both. Units and
            -- the ROI denominator gate on a real dk_odds, for the same reason
            -- the matview leaves profit_units NULL on an unpriced pick.
            SELECT p.model_id, p.sport,
                   COUNT(*)                                     AS settled,
                   COUNT(*) FILTER (WHERE p.result = 'WIN')     AS wins,
                   COUNT(*) FILTER (WHERE p.result = 'LOSS')    AS losses,
                   COUNT(*) FILTER (WHERE p.result = 'PUSH')    AS pushes,
                   COUNT(*) FILTER (WHERE p.dk_odds IS NOT NULL) AS priced,
                   COALESCE(SUM(p.profit_flat) FILTER (WHERE p.dk_odds IS NOT NULL), 0)
                       / 100.0                                  AS units,
                   MAX(p.game_date)                             AS last_date
            FROM picks p
            WHERE p.signal_type = 'BET' AND p.result IN ('WIN', 'LOSS', 'PUSH')
              AND NOT EXISTS (SELECT 1 FROM mv_scored_pick_outcomes m
                               WHERE m.model_id = p.model_id)
            GROUP BY p.model_id, p.sport
        )
        SELECT t.model_id,
               COALESCE(a.sport, upper(split_part(t.model_id, '_', 1))) AS sport,
               COALESCE(a.settled, 0), COALESCE(a.wins, 0),
               COALESCE(a.losses, 0), COALESCE(a.pushes, 0),
               COALESCE(a.priced, 0), COALESCE(a.units, 0), a.last_date,
               t.paused,
               EXISTS (SELECT 1 FROM model_registry mr
                        WHERE mr.model_id = t.model_id AND mr.is_active = 1)
          FROM model_action_thresholds t
          LEFT JOIN agg a ON a.model_id = t.model_id
        UNION ALL
        SELECT a.model_id, a.sport, a.settled, a.wins, a.losses, a.pushes,
               a.priced, a.units, a.last_date, FALSE, TRUE
          FROM agg a
         WHERE NOT EXISTS (SELECT 1 FROM model_action_thresholds t
                            WHERE t.model_id = a.model_id)
        ORDER BY 3 DESC, 1
    """
    cols = ("model_id", "sport", "settled", "wins", "losses", "pushes",
            "priced", "units", "last_date", "paused", "trained")
    out = [dict(zip(cols, r)) for r in _rows(conn, sql)]
    for m in out:
        # A push returns the stake, so it is not risked. ROI is over the priced
        # bets only — the denominator the units were actually won against.
        risked = (m["priced"] or 0) - (m["pushes"] or 0)
        m["roi_pct"] = (float(m["units"]) / risked * 100) if risked > 0 else None
    return out


def picks_over_time(conn, days: int = 14) -> list[dict]:
    """Picks scored and signals fired, per model per day.

    Bounded on game_date, which is indexed — the same lesson as pick_counts.
    Live picks are excluded: they churn per pass and would swamp the pre-game
    board they would be charted beside.
    """
    sql = """
        SELECT game_date, model_id,
               COUNT(*)                                           AS scored,
               COUNT(*) FILTER (WHERE signal_type = 'BET')        AS bets
        FROM picks
        WHERE game_date >= to_char(NOW() - (? || ' days')::interval, 'YYYY-MM-DD')
          AND game_date <= to_char(NOW() + interval '1 day', 'YYYY-MM-DD')
          AND is_live IS NOT TRUE
        GROUP BY game_date, model_id
        ORDER BY game_date, model_id
    """
    cols = ("game_date", "model_id", "scored", "bets")
    return [dict(zip(cols, r)) for r in _rows(conn, sql, (str(days),))]


def community(conn) -> dict:
    """Audience size: paying subscribers, app devices, Discord reach.

    Every counter here is honest about being zero for a reason rather than
    absent: subscriptions is empty because billing ships dark (BILLING_ENABLED
    defaults false) and device_push_tokens is empty because the native push
    build was never made. Both light up on their own when those turn on.
    """
    def scalar(sql, params=()):
        rows = _rows(conn, sql, params)
        return (rows[0][0] if rows and rows[0] else 0) or 0

    return {
        "subscribers_active": scalar(
            "SELECT COUNT(*) FROM subscriptions WHERE status IN ('active','trialing')"),
        "subscribers_total": scalar("SELECT COUNT(*) FROM subscriptions"),
        "push_devices": scalar(
            "SELECT COUNT(*) FROM device_push_tokens WHERE enabled"),
        "linked_books": scalar("SELECT COUNT(*) FROM linked_sportsbook_accounts"),
        "feedback_open": scalar(
            "SELECT COUNT(*) FROM feedback_threads WHERE status <> 'closed'"),
        # Discord REACH, not membership — the number of posts we have actually
        # delivered. Membership needs a bot token (see discord_stats.py).
        "discord_posts_7d": scalar(
            "SELECT COUNT(*) FROM push_sent WHERE kind LIKE 'discord%%' "
            "AND sent_at::timestamptz > NOW() - interval '7 days'"),
        "discord_posts_total": scalar(
            "SELECT COUNT(*) FROM push_sent WHERE kind LIKE 'discord%%'"),
    }


def live_calibration(conn) -> list[dict]:
    """Latest recalibration report per live model (tracking/live_calibration.py).

    The dashboard shows the cutoff, what it is projected to cost per week, what
    it has actually returned, and whether the sweep still endorses it — because
    a live cutoff is a claim that decays. Returns [] when the table does not
    exist yet (it is created on the first calibration run), which the panel
    renders as an honest empty state rather than an error.
    """
    rows = _rows(conn, """
        SELECT model_id, sport, computed_at, verdict, payload
        FROM live_calibration ORDER BY sport, model_id
    """)
    out = []
    for model_id, sport, computed_at, verdict, payload in rows:
        try:
            report = json.loads(payload)
        except (TypeError, ValueError):
            continue
        cur = report.get("current") or {}
        rec = report.get("recommended") or None
        cal = report.get("calibration") or {}
        out.append({
            "model_id": model_id, "sport": sport, "computed_at": computed_at,
            "verdict": verdict,
            "max_bets_per_week": report.get("max_bets_per_week"),
            # the cutoff in force
            "min_prob": cur.get("min_prob"), "min_ev": cur.get("min_ev"),
            # what it is projected to cost, and what it has returned
            "bets_per_week": cur.get("bets_per_week"),
            "units_per_week": cur.get("units_per_week"),
            "settled": cur.get("settled"), "w": cur.get("w"), "l": cur.get("l"),
            "roi_pct": cur.get("roi_pct"), "units_flat": cur.get("units_flat"),
            "ci_low_pct": cur.get("ci_low_pct"), "ci_high_pct": cur.get("ci_high_pct"),
            # is the model honest about itself
            "pred_prob": cal.get("mean_pred_prob"),
            "real_win_pct": cal.get("realised_win_pct"),
            "cal_gap_pp": cal.get("calibration_gap_pp"),
            "pred_ev_pct": cal.get("mean_pred_ev_pct"),
            "real_roi_pct": cal.get("realised_roi_pct"),
            "ev_gap_pp": cal.get("ev_gap_pp"),
            # what the sweep would do instead
            "rec_min_prob": (rec or {}).get("min_prob"),
            "rec_min_ev": (rec or {}).get("min_ev"),
            "rec_roi_pct": (rec or {}).get("roi_pct"),
            "rec_settled": (rec or {}).get("settled"),
            "rec_bets_per_week": (rec or {}).get("bets_per_week"),
            "rec_units_per_week": (rec or {}).get("units_per_week"),
            "rec_plateau": (rec or {}).get("plateau"),
        })
    return out


def model_calibration(conn) -> dict[str, dict]:
    """Per-model claimed-vs-realised gap on the LIVE graded record.

    Sits beside the performance rows because ROI and honesty are different
    questions and a model can be profitable while lying: `mlb_moneyline` is
    +23.8% ROI and was 10pp overconfident, its threshold doing the work. Scoped
    to each model's ACTIVE version, since a gap measured across a version swap
    describes a blend of the live model and its dead predecessor.
    """
    rows = _rows(conn, """
        SELECT o.model_id, COUNT(*) AS n,
               AVG(o.model_probability) * 100 AS claimed,
               100.0 * COUNT(*) FILTER (WHERE o.result = 'WIN') / COUNT(*) AS realised
        FROM mv_scored_pick_outcomes o
        JOIN model_registry r ON r.model_id = o.model_id AND r.is_active = 1
        WHERE o.result IN ('WIN','LOSS') AND o.model_probability >= 0.60
          AND o.game_date >= SUBSTRING(r.created_at, 1, 10)
        GROUP BY o.model_id HAVING COUNT(*) >= 100
    """)
    out = {}
    for model_id, n, claimed, realised in rows:
        out[model_id] = {"n": int(n), "claimed": float(claimed),
                         "realised": float(realised),
                         "gap_pp": float(claimed) - float(realised)}
    # Which models publish a corrected number, so the panel can say so.
    for model_id, in _rows(conn,
            "SELECT model_id FROM model_calibration WHERE applied"):
        out.setdefault(model_id, {}).update(mapped=True)
    return out
