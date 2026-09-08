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

Run standalone (`python -m data.threshold_sync`) or as the pipeline's
`sync-thresholds` step (auto-runs daily so the table never drifts from config).
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


def sync_action_thresholds(conn: DBConnection = None) -> int:
    """Upsert every config model into model_action_thresholds and prune stragglers.

    Returns the number of rows upserted. Idempotent.
    """
    own = conn is None
    if own:
        conn = get_connection()
    try:
        _ensure_scoring_method(conn)
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
                "paused":    mid in PAUSED_MODELS,
                # "artifact" | "rule" | "engine" — see config.SCORING_METHODS.
                # A reader that judges a model by its registry row alone calls
                # every rule-based model broken; this is how it knows better.
                "scoring_method": scoring_method(mid),
            }
            for mid, t in ACTION_THRESHOLDS.items()
        ]
        conn.executemany("""
            INSERT INTO model_action_thresholds
                (model_id, min_prob, min_edge, min_odds, prob_only, paused,
                 scoring_method, updated_at)
            VALUES (%(model_id)s, %(min_prob)s, %(min_edge)s, %(min_odds)s, %(prob_only)s, %(paused)s,
                    %(scoring_method)s, NOW())
            ON CONFLICT (model_id) DO UPDATE SET
                min_prob   = EXCLUDED.min_prob,
                min_edge   = EXCLUDED.min_edge,
                min_odds   = EXCLUDED.min_odds,
                prob_only  = EXCLUDED.prob_only,
                paused     = EXCLUDED.paused,
                scoring_method = EXCLUDED.scoring_method,
                updated_at = NOW()
        """, rows)

        # Prune any table rows that no longer exist in config (keep a true mirror).
        keep = tuple(ACTION_THRESHOLDS.keys())
        ph = ",".join(["%s"] * len(keep))
        deleted = conn.execute(
            f"DELETE FROM model_action_thresholds WHERE model_id NOT IN ({ph})", keep
        )

        conn.commit()
        logger.success(
            f"Synced {len(rows)} model thresholds → model_action_thresholds "
            f"({sum(r['paused'] for r in rows)} paused, "
            f"{sum(r['prob_only'] for r in rows)} prob-only, "
            f"{sum(r['scoring_method'] != 'artifact' for r in rows)} non-artifact)"
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
