"""
The pre-registered forward test of the 2026-08-31 calibrated cuts.

WHY THIS EXISTS
---------------
mike, 2026-08-31: "are we projecting profitability?" The honest answer was no,
and the evidence was this system's own history. Every cut previously chosen by
sweeping live picks was shipped with a claimed ROI and then delivered something
far worse:

    wnba_moneyline   claimed +31.9%  ->  -16.1% over 28 forward bets
    wnba assists     claimed +19.3%  ->  -21.9% over 18
    pitcher_er       claimed +11.1%  ->  -21.0% over 35
    pitcher_k        claimed +17.1%  ->   -8.1% over 62
    f5_moneyline     claimed  +9.9%  ->   -3.2% over 92
    -------------------------------------------------------
    pooled across every shipped cut  ->   -4.7% over 258

A sweep picks the best of ~99 grid cells per model. The best of 99 noisy cells
is high because it is lucky as well as because it is good, and only the forward
sample can tell those apart. The plateau requirement and the time split reduce
that; they do not remove it.

So the cuts shipped on 2026-08-31 get a test that was agreed BEFORE the data
arrived, and that runs whether or not anyone remembers to look.

THE RULE, PRE-REGISTERED
------------------------
* Reviews fire at fixed slate-wide milestones: 250 settled bets since the
  epoch, then 500, 750, and so on. NOT continuously -- a rule re-evaluated
  every day is a rule that eventually fires on noise, which is the same
  multiple-comparison mistake as the sweep it is checking.
* At a review, a model is PAUSED if it has >= 50 settled bets of its own since
  the epoch AND its ROI over them is worse than -5%.
* No auto-unpause. Coming back is a decision with a person's name on it
  (CLAUDE.md 1b), and a rule that pauses and unpauses on the same noisy
  number just oscillates.
* No re-sweeping at the review. Finding a better cell in the data that just
  failed is fitting the noise twice.

WHY IT WRITES ITS OWN TABLE RATHER THAN config.py
-------------------------------------------------
config.py is canonical and version-controlled; a job cannot edit it. Writing
`paused` into model_action_thresholds would not work either -- the scorer reads
config.py directly, so a table pause hides picks in the app while the model
keeps betting, and the next threshold_sync overwrites it anyway (CLAUDE.md 6).
So the pause lives in `model_auto_pauses`, which models/scorer.py consults
alongside config.PAUSED_MODELS. That keeps config the record of DELIBERATE
pauses and this table the record of AUTOMATIC ones, without either silently
undoing the other.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from loguru import logger

import config
from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current

# The day the calibrated cuts shipped. Bets before this were made under
# different thresholds and belong to a different experiment.
EPOCH = "2026-08-31"

REVIEW_EVERY_N_BETS = 250     # slate-wide, since EPOCH
MIN_BETS_PER_MODEL  = 50      # below this a model's ROI is a number, not a result
PAUSE_ROI_PCT       = -5.0    # worse than this at a review = paused

DDL = """
CREATE TABLE IF NOT EXISTS model_auto_pauses (
    model_id    TEXT PRIMARY KEY,
    paused_at   TEXT NOT NULL,
    milestone   INTEGER NOT NULL,   -- slate-wide settled count at the review
    bets        INTEGER NOT NULL,   -- this model's own settled bets
    roi_pct     NUMERIC NOT NULL,
    reason      TEXT NOT NULL
)
"""

LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS threshold_reviews (
    milestone   INTEGER PRIMARY KEY, -- 250, 500, ... fires once each
    reviewed_at TEXT NOT NULL,
    slate_bets  INTEGER NOT NULL,
    slate_roi   NUMERIC,
    paused      TEXT                  -- comma-separated model_ids, '' if none
)
"""


def _enabled() -> bool:
    """Kill switch. An automatic pause path must be switchable off from the
    dashboard without a deploy, because the failure mode is a model going
    quiet and nobody knowing which of several mechanisms did it."""
    return os.environ.get("RUN_THRESHOLD_REVIEW", "1") not in ("0", "false", "False")


def ensure_schema(conn) -> None:
    """Create both tables if absent, and COMMIT them.

    THE COMMIT IS THE WHOLE POINT, and its absence is why neither table existed
    in production for the first four days this module ran.

    `data.db.get_connection()` sets `autocommit = False`. `run_review` returns
    at `not_due` on every day the slate has not crossed a 250-bet milestone --
    which is every day so far: 80 settled bets since EPOCH on 2026-09-04 --
    and that early return reaches no `conn.commit()`. The caller then closes
    the connection, psycopg discards the open transaction, and the two CREATE
    TABLEs go with it. So the review created both tables every single morning
    and threw them away every single morning, silently, while
    `models/scorer.py` logged `relation "model_auto_pauses" does not exist`.

    A schema helper that does not persist its schema is broken regardless of
    what its caller does, so the commit belongs HERE and not in run_review --
    a fix in the caller would leave the next caller to rediscover this.

    Both probes must pass before the block is skipped. `CREATE TABLE IF NOT
    EXISTS` is the cheapest DDL here (single-digit ms, on a schedule rather
    than per write), but it still fires Supabase's pgrst_ddl_watch and so still
    costs a PostgREST schema-cache reload. See data/ddl_guard.py.
    """
    # rls= and revoked_from= are load-bearing: this returns EARLY, before the
    # lock_down() calls below, so without them it answers True on a database
    # where both tables exist but are still anon-granted and RLS-off, and the
    # lock-down never runs. A guard that dead code can satisfy.
    if (schema_is_current(conn, "model_auto_pauses", rls=True,
                          revoked_from=API_ROLES)
            and schema_is_current(conn, "threshold_reviews", rls=True,
                                  revoked_from=API_ROLES)):
        return
    conn.execute(DDL)
    conn.execute(LEDGER_DDL)
    # Worker-only, so they arrive closed rather than inheriting the default
    # anon grant (#464). lock_down carries its own ddl_guard gate internally.
    for table in ("model_auto_pauses", "threshold_reviews"):
        try:
            lock_down(conn, table)
        except Exception:  # noqa: BLE001 — a failed lock must not lose the table
            logger.exception(f"ensure_schema: could not lock down {table}")
    conn.commit()


def auto_paused(conn) -> set[str]:
    """Model ids currently paused by a review. Empty on any failure.

    FAILS OPEN deliberately: if this table cannot be read, models keep behaving
    exactly as config.py says. The alternative -- failing closed -- would turn a
    transient database error into every model on the platform going silent,
    which is a bigger outage than the one this guard prevents.
    """
    try:
        rows = conn.execute("SELECT model_id FROM model_auto_pauses").fetchall()
        return {r[0] for r in rows}
    except Exception as exc:  # noqa: BLE001 — see docstring
        logger.warning(f"auto_paused unavailable, treating as none: {exc}")
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        return set()


def _slate(conn) -> list[tuple[str, int, float]]:
    """(model_id, settled bets, ROI %) per model since EPOCH.

    Pre-game BETs only. Live lanes have their own cadence and their own
    calibration loop (tracking/live_calibration.py), so folding them in here
    would judge one mechanism by another's record.
    """
    rows = conn.execute("""
        SELECT model_id,
               COUNT(*)                              AS bets,
               SUM(profit_flat) / COUNT(*)           AS roi_pct
        FROM picks
        WHERE signal_type = 'BET'
          AND result IN ('WIN','LOSS','PUSH')
          AND is_live IS NOT TRUE
          AND game_date >= %s
        GROUP BY model_id
    """, (EPOCH,)).fetchall()
    # A retired model's picks stay in the table (§1c) but it is out of every
    # total, and it must never be judged, milestoned or auto-paused again.
    return [(r[0], int(r[1]), float(r[2])) for r in rows
            if r[0] not in config.RETIRED_MODELS]


def _due_milestone(conn, slate_bets: int) -> int | None:
    """The highest un-reviewed milestone this slate count has reached.

    Returns None until the next multiple of REVIEW_EVERY_N_BETS is crossed, so
    the rule looks at the data on a fixed schedule rather than every day.
    """
    if slate_bets < REVIEW_EVERY_N_BETS:
        return None
    milestone = (slate_bets // REVIEW_EVERY_N_BETS) * REVIEW_EVERY_N_BETS
    row = conn.execute(
        "SELECT 1 FROM threshold_reviews WHERE milestone = %s", (milestone,)
    ).fetchone()
    return None if row else milestone


def run_review(conn, now: datetime | None = None, dry_run: bool = False) -> dict:
    """Evaluate the rule. Returns what it found, whether or not it acted."""
    now = now or datetime.now(timezone.utc)
    if not _enabled():
        logger.info("Threshold review: disabled by RUN_THRESHOLD_REVIEW")
        return {"status": "disabled"}

    ensure_schema(conn)
    slate = _slate(conn)
    slate_bets = sum(n for _, n, _ in slate)
    milestone = _due_milestone(conn, slate_bets)
    if milestone is None:
        logger.info(f"Threshold review: {slate_bets}/{REVIEW_EVERY_N_BETS} "
                    f"settled since {EPOCH} — next review not due")
        return {"status": "not_due", "slate_bets": slate_bets}

    already = auto_paused(conn)
    to_pause = [
        (mid, n, roi) for mid, n, roi in slate
        if n >= MIN_BETS_PER_MODEL and roi < PAUSE_ROI_PCT
        and mid not in already and mid not in config.PAUSED_MODELS
    ]
    slate_roi = (sum(n * roi for _, n, roi in slate) / slate_bets) if slate_bets else None

    if not dry_run:
        for mid, n, roi in to_pause:
            conn.execute("""
                INSERT INTO model_auto_pauses
                    (model_id, paused_at, milestone, bets, roi_pct, reason)
                VALUES (%(m)s, %(at)s, %(k)s, %(n)s, %(roi)s, %(why)s)
                ON CONFLICT (model_id) DO NOTHING
            """, {"m": mid, "at": now.isoformat(), "k": milestone, "n": n,
                  "roi": round(roi, 2),
                  "why": (f"{REVIEW_EVERY_N_BETS}-bet review at milestone {milestone}: "
                          f"{roi:.1f}% over {n} settled bets since {EPOCH}, "
                          f"worse than the pre-registered {PAUSE_ROI_PCT}% floor")})
        conn.execute("""
            INSERT INTO threshold_reviews (milestone, reviewed_at, slate_bets, slate_roi, paused)
            VALUES (%(k)s, %(at)s, %(n)s, %(roi)s, %(p)s)
            ON CONFLICT (milestone) DO NOTHING
        """, {"k": milestone, "at": now.isoformat(), "n": slate_bets,
              "roi": round(slate_roi, 2) if slate_roi is not None else None,
              "p": ",".join(m for m, _, _ in to_pause)})
        conn.commit()

    result = {
        "status": "reviewed", "milestone": milestone, "slate_bets": slate_bets,
        "slate_roi": slate_roi,
        "paused": [{"model_id": m, "bets": n, "roi": roi} for m, n, roi in to_pause],
        "kept": sorted(m for m, n, _ in slate if n >= MIN_BETS_PER_MODEL
                       and not any(m == p for p, _, _ in to_pause)),
    }
    _announce(result)
    return result


def _announce(result: dict) -> None:
    """Post the verdict. A pause nobody hears about is the outage it prevents.

    Logged at CRITICAL when the webhook is unset, because "paused three models
    and told no one" must not look the same in the logs as a quiet review.
    """
    from tracking.discord_notifier import _post

    paused = result["paused"]
    lines = [
        f"Milestone **{result['milestone']}** settled bets since {EPOCH}.",
        f"Slate: {result['slate_bets']} bets, "
        + (f"{result['slate_roi']:+.1f}%" if result["slate_roi"] is not None else "n/a"),
        "",
    ]
    if paused:
        lines.append("**PAUSED** (>= "
                     f"{MIN_BETS_PER_MODEL} bets and worse than {PAUSE_ROI_PCT}%):")
        lines += [f"• `{p['model_id']}` — {p['roi']:+.1f}% over {p['bets']} bets"
                  for p in paused]
        lines.append("")
        lines.append("Unpausing is a person's call — this rule never does it.")
    else:
        lines.append("No model met the pause rule.")

    url = config.DISCORD_WEBHOOK_OPS
    body = "\n".join(lines)
    if not url:
        logger.critical(f"THRESHOLD REVIEW (no DISCORD_WEBHOOK_OPS set)\n{body}")
        return
    _post(url, {"embeds": [{
        "title": ("⏸️ Threshold review — models paused" if paused
                  else "✅ Threshold review — no action"),
        "description": body,
        "color": 0xE67E22 if paused else 0x2ECC71,
    }]})


if __name__ == "__main__":  # pragma: no cover — manual invocation
    import json
    from data.db import get_connection

    _conn = get_connection()
    try:
        print(json.dumps(run_review(_conn), indent=2, default=str))
    finally:
        _conn.close()
