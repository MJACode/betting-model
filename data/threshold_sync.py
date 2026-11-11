"""
threshold_sync.py — Push config.py thresholds → the model_action_thresholds table.

config.py is the single CANONICAL, version-controlled source for every model's
prob/edge cut, PAUSED_MODELS, and PROB_ONLY_MODELS. This script mirrors that into
the `model_action_thresholds` Supabase table, which is read by:
  • the public track-record views (v_public_track_record*), and
  • the mobile app's action filter (live, via fetchActionThresholds + a server
    store with the bundled thresholds.ts as offline fallback).

So the workflow becomes: edit config.py → run this sync → the table updates →
the Track Record screen AND every installed app reflect the new cuts on next
refresh, with NO mobile rebuild. (The scorer reads config.py directly, so the
server-side BET decision is always config-canonical.)

VOLUME SETTINGS (mike, 2026-11-11). A pre-game model can carry a setting that
posts fewer, stronger bets (`model_volume_settings`, set from the dashboard
through `set_model_volume`). The table then holds TWO cuts per model:
`base_min_prob` / `base_min_edge` are config.py's, written here on every pass,
and `min_prob` / `min_edge`, the columns every surface reads, are the cut in
force: the tighter of config's and the setting's. This sync writes config's
cut into both and, in the same transaction, calls
`apply_model_volume_settings()` to put the settings back over it, so no reader
sees the table without them. A setting never loosens a cut, and it changes
what is posted, not what the scorer writes (docs/thresholds.md).

Run standalone (`python -m data.threshold_sync`) or as the pipeline's
`sync-thresholds` step (daily after view migrations, every refresh pass,
and immediately before a Discord post, so the table the publishers join
cannot lag `config.py` overnight).
"""

import sys
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (ACTION_THRESHOLDS, PAUSED_MODELS, PROB_ONLY_MODELS,
                    min_odds_for, scoring_method)
from data.db import get_connection, DBConnection
from data.ddl_guard import schema_is_current


def _ensure_scoring_method(conn: DBConnection) -> None:
    """Add the scoring_method column the first time this runs, and never again.

    `scoring_method` tells a reader whether a missing model_registry row is a
    FAULT or the design (config.SCORING_METHODS). The ops roster consumes it;
    without it every rule-based model reads as broken.

    The guard is not decoration: `ALTER TABLE` fires Supabase's pgrst_ddl_watch
    and 503s the whole app while PostgREST rebuilds its schema cache, and this
    runs on every daily pipeline pass (.claude/rules/operations.md). One indexed
    catalog SELECT, then nothing.
    """
    if schema_is_current(conn, "model_action_thresholds",
                         columns=("scoring_method",)):
        return
    conn.execute(
        "ALTER TABLE model_action_thresholds "
        "ADD COLUMN IF NOT EXISTS scoring_method TEXT NOT NULL DEFAULT 'artifact'"
    )


def _volume_settings_ready(conn: DBConnection) -> bool:
    """True once the volume-setting migration has added config's-own-cut columns.

    data/migrations/model_volume_settings_2026_11_11.sql adds base_min_prob /
    base_min_edge and apply_model_volume_settings() in one block, so the
    columns being there means the function is too. Until then this sync writes
    the table as it always did. It never runs that DDL itself: one catalog
    SELECT on every pass, nothing else (.claude/rules/operations.md).
    """
    return schema_is_current(conn, "model_action_thresholds",
                             columns=("base_min_prob", "base_min_edge"))


def _apply_volume_settings(conn: DBConnection) -> int | None:
    """Put every volume setting back in force over the cuts just written.

    Returns how many settings are in force, or None if they could not be
    applied. FAILS OPEN, and says so: a failure here leaves config.py's cuts
    committed as written (the cuts each model's evidence was measured at) and
    the settings out of force until the next pass. Failing the whole sync
    instead would also hold back a pause, which is the worse miss.
    """
    try:
        conn.execute("SAVEPOINT volume_settings")
        row = conn.execute("SELECT apply_model_volume_settings()").fetchone()
        conn.execute("RELEASE SAVEPOINT volume_settings")
        return int(row[0])
    except Exception as exc:                           # noqa: BLE001
        logger.error(
            f"Volume settings NOT applied, config.py's cuts are in force "
            f"until the next sync: {exc}")
        # If the savepoint itself is gone this raises, and the caller's
        # handler rolls the whole sync back: the table keeps its last state.
        conn.execute("ROLLBACK TO SAVEPOINT volume_settings")
        return None


def sync_action_thresholds(conn: DBConnection = None) -> int:
    """Upsert every config model into model_action_thresholds and prune stragglers.

    Returns the number of rows upserted. Idempotent.
    """
    own = conn is None
    if own:
        conn = get_connection()
    try:
        _ensure_scoring_method(conn)
        volume = _volume_settings_ready(conn)
        # Fails OPEN (an unreadable table pauses nothing), same contract as
        # models.scorer._auto_paused_models, which is the reader that stops a
        # paused model writing a pick at all.
        try:
            from tracking.threshold_review import auto_paused
            auto_paused_set = auto_paused(conn)
        except Exception as exc:                       # noqa: BLE001
            logger.warning(f"auto-pause lookup failed, syncing config only: {exc}")
            auto_paused_set = set()
        rows = [
            {
                "model_id":  mid,
                "min_prob":  t["min_prob"],
                "min_edge":  t["min_edge"],
                # Never NULL now: config.min_odds_for falls back to the
                # house floor, so the app action filter, the Discord
                # card's "good to" bound and the track-record views all
                # apply the same juice rule the scorer applied.
                "min_odds":  min_odds_for(mid),
                "prob_only": mid in PROB_ONLY_MODELS,
                # BOTH registers, empty-map identity after 2026-09-14.
                # config.PAUSED_MODELS is what a person chose. model_auto_pauses
                # is leftover rows the review no longer writes (mike:
                # nothing autopauses). Until 2026-09-12 this wrote only the
                # first, so an auto-paused model read `paused = false` to every
                # reader of this table -- the app's action filter, Discord,
                # push and the Claude-mobile prompt -- and a hand UPDATE to
                # correct it was erased by the next 6am sync. Measured that
                # day: mlb_prop_pitcher_k and mlb_prop_batter_runs were
                # auto-paused and the table said false for both. After the
                # 2026-09-14 migration the auto-pause set is empty.
                "paused":    mid in PAUSED_MODELS or mid in auto_paused_set,
                # "artifact" | "rule" | "engine" — see config.SCORING_METHODS.
                # A reader that judges a model by its registry row alone calls
                # every rule-based model broken; this is how it knows better.
                "scoring_method": scoring_method(mid),
            }
            for mid, t in ACTION_THRESHOLDS.items()
        ]
        # config's own cut goes into base_min_* as well as min_*, once the
        # volume-setting migration has added those columns. min_* is then
        # raised to the cut in force below, before the commit.
        base_cols = ", base_min_prob, base_min_edge" if volume else ""
        base_vals = ", %(min_prob)s, %(min_edge)s" if volume else ""
        base_sets = (""",
                base_min_prob = EXCLUDED.base_min_prob,
                base_min_edge = EXCLUDED.base_min_edge""" if volume else "")
        conn.executemany(f"""
            INSERT INTO model_action_thresholds
                (model_id, min_prob, min_edge, min_odds, prob_only, paused,
                 scoring_method, updated_at{base_cols})
            VALUES (%(model_id)s, %(min_prob)s, %(min_edge)s, %(min_odds)s, %(prob_only)s, %(paused)s,
                    %(scoring_method)s, NOW(){base_vals})
            ON CONFLICT (model_id) DO UPDATE SET
                min_prob   = EXCLUDED.min_prob,
                min_edge   = EXCLUDED.min_edge,
                min_odds   = EXCLUDED.min_odds,
                prob_only  = EXCLUDED.prob_only,
                paused     = EXCLUDED.paused,
                scoring_method = EXCLUDED.scoring_method,
                updated_at = NOW(){base_sets}
        """, rows)

        # Prune any table rows that no longer exist in config (keep a true mirror).
        keep = tuple(ACTION_THRESHOLDS.keys())
        ph = ",".join(["%s"] * len(keep))
        deleted = conn.execute(
            f"DELETE FROM model_action_thresholds WHERE model_id NOT IN ({ph})", keep
        )

        # LAST before the commit: the upsert above has just written config's
        # cut over every row, settings included.
        in_force = _apply_volume_settings(conn) if volume else None

        conn.commit()
        logger.success(
            f"Synced {len(rows)} model thresholds → model_action_thresholds "
            f"({sum(r['paused'] for r in rows)} paused, "
            f"{sum(r['prob_only'] for r in rows)} prob-only, "
            f"{sum(r['scoring_method'] != 'artifact' for r in rows)} non-artifact, "
            + ("volume settings not installed" if not volume
               else "volume settings NOT APPLIED" if in_force is None
               else f"{in_force} volume setting(s) in force") + ")"
        )
        return len(rows)
    except Exception as exc:
        conn.rollback()
        logger.error(f"Threshold sync failed: {exc}")
        raise
    finally:
        if own:
            conn.close()


if __name__ == "__main__":
    sync_action_thresholds()
