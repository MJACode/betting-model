"""Re-ledger already-published picks under the richer publishing lock_key.

RUN THIS BEFORE the code that widens `tracking/publish_keys.KEY_PARTS` reaches
production, never after. The ordering is the whole safety argument:

  * Before the deploy, the producers still mint the OLD key, and every old key
    they look up is already ledgered — so adding rows under the NEW keys
    changes nothing about what posts. The window is inert.
  * After the deploy, the producers mint the NEW key. A pick already announced
    finds its ledger row and stays quiet; the pick that was SWALLOWED by the
    old key finds none and posts, which is the point.

Run it the other way round and every already-posted pick republishes, because
for a few minutes its new key is unledgered — one duplicate per pick, in a
channel members pay for.

WHICH PICK OWNS AN OLD LEDGER ROW. The one the old producer would have chosen:
`DISTINCT ON (old_key) ... ORDER BY created_at`, the first BET (§1c). That is
not an inference about what was posted — it is the same expression that did
the posting.

`opening_signals` is re-keyed rather than re-inserted: it is a UNIQUE-keyed
shadow row per proposition, so leaving the old key would let capture write a
SECOND row for the same pick under the new key and double-count it in the CLV
track. Checked before writing: no `parlay_track_record.leg_keys` references any
affected key.

Idempotent — `ON CONFLICT DO NOTHING` on the insert, and the update only
touches rows still carrying an old key. Dry-run by default.

    python -m scripts.backfill_publish_keys              # show what would change
    python -m scripts.backfill_publish_keys --apply      # write it
"""
from __future__ import annotations

import argparse

from loguru import logger

from data.db import get_connection
from tracking.publish_keys import live_lock_key_sql, lock_key_sql

# The key as it was minted before this change: game, model, player_id only.
_OLD_KEY = ("p.game_id || ':' || p.model_id "
            "|| COALESCE(':' || p.player_id, '')")

# One row per (old key, new key), for the pick that actually owned the old key.
_OWNERS = f"""
    WITH k AS (
        SELECT {_OLD_KEY} AS old_key,
               {lock_key_sql()} AS new_key,
               p.pick_label, p.pick_side, p.game_date, p.created_at
        FROM picks p
        WHERE p.signal_type = 'BET'
    )
    SELECT DISTINCT ON (old_key)
           old_key, new_key, pick_label, pick_side, game_date
    FROM k
    WHERE new_key <> old_key
    ORDER BY old_key, created_at
"""


# The LIVE key as it was minted before 2026-09-09: game, model, side, no
# player. Same shape of fix, same ordering argument, own ledger kinds
# (discord_live / live_signal). Applied to production by hand on 2026-09-09
# (one row: a settled 08-09 MLB walks prop) before the producers changed.
_OLD_LIVE_KEY = "'live:' || p.game_id || ':' || p.model_id || ':' || p.pick_side"

_LIVE_OWNERS = f"""
    WITH k AS (
        SELECT {_OLD_LIVE_KEY} AS old_key,
               {live_lock_key_sql()} AS new_key,
               p.pick_label, p.pick_side, p.game_date, p.created_at
        FROM picks p
        WHERE p.signal_type = 'BET' AND p.is_live = TRUE
    )
    SELECT DISTINCT ON (old_key)
           old_key, new_key, pick_label, pick_side, game_date
    FROM k
    WHERE new_key <> old_key
    ORDER BY old_key, created_at
"""


def run(apply: bool = False) -> tuple[int, int]:
    """Returns (push_sent rows added, opening_signals rows re-keyed)."""
    with get_connection() as conn:
        owners = conn.execute(_OWNERS).fetchall()
        live_owners = conn.execute(_LIVE_OWNERS).fetchall()
        if not owners and not live_owners:
            logger.info("no keys change under the current KEY_PARTS — nothing "
                        "to do")
            return 0, 0

        ledger = conn.execute(f"""
            SELECT o.old_key, o.new_key, s.kind
            FROM ({_OWNERS}) o
            JOIN push_sent s ON s.lock_key = o.old_key
            WHERE NOT EXISTS (
                SELECT 1 FROM push_sent n
                WHERE n.lock_key = o.new_key AND n.kind = s.kind
            )
            UNION ALL
            SELECT o.old_key, o.new_key, s.kind
            FROM ({_LIVE_OWNERS}) o
            JOIN push_sent s ON s.lock_key = o.old_key
            WHERE s.kind IN ('discord_live', 'live_signal')
              AND NOT EXISTS (
                SELECT 1 FROM push_sent n
                WHERE n.lock_key = o.new_key AND n.kind = s.kind
            )
        """).fetchall()
        # Only rows whose NEW key is not already taken. Capture keeps writing
        # after the code ships, so a proposition can hold BOTH an old-key row
        # (captured before) and a new-key row (captured after). Re-keying the
        # old one then violates opening_signals' UNIQUE(lock_key) and rolls
        # the whole run back -- which is what failed job 47297 three times
        # on 2026-09-09. Those pairs are reported, not touched: which capture
        # is the opening line is a decision, not a migration.
        shadow = conn.execute(f"""
            SELECT o.old_key, o.new_key
            FROM ({_OWNERS}) o
            JOIN opening_signals os ON os.lock_key = o.old_key
            WHERE NOT EXISTS (
                SELECT 1 FROM opening_signals n WHERE n.lock_key = o.new_key
            )
        """).fetchall()
        duplicated = conn.execute(f"""
            SELECT o.old_key, o.new_key
            FROM ({_OWNERS}) o
            JOIN opening_signals os ON os.lock_key = o.old_key
            WHERE EXISTS (
                SELECT 1 FROM opening_signals n WHERE n.lock_key = o.new_key
            )
        """).fetchall()
        for old, new in duplicated:
            logger.warning(f"opening_signals holds BOTH {old} and {new}; "
                           f"left alone, needs a decision on which capture stands")

        for old, new, kind in ledger:
            logger.info(f"push_sent  {kind:<15} {old}  ->  {new}")
        for old, new in shadow:
            logger.info(f"opening_signals              {old}  ->  {new}")

        if not apply:
            logger.info(f"[dry-run] would add {len(ledger)} push_sent row(s) "
                        f"and re-key {len(shadow)} opening_signals row(s); "
                        f"re-run with --apply")
            return len(ledger), len(shadow)

        # Copy sent_at and message_id across so a restatement can still DELETE
        # the message this pick was actually posted in.
        conn.execute(f"""
            INSERT INTO push_sent (lock_key, kind, sent_at, message_id)
            SELECT o.new_key, s.kind, s.sent_at, s.message_id
            FROM ({_OWNERS}) o
            JOIN push_sent s ON s.lock_key = o.old_key
            ON CONFLICT (lock_key, kind) DO NOTHING
        """)
        conn.execute(f"""
            INSERT INTO push_sent (lock_key, kind, sent_at, message_id)
            SELECT o.new_key, s.kind, s.sent_at, s.message_id
            FROM ({_LIVE_OWNERS}) o
            JOIN push_sent s ON s.lock_key = o.old_key
            WHERE s.kind IN ('discord_live', 'live_signal')
            ON CONFLICT (lock_key, kind) DO NOTHING
        """)
        conn.execute(f"""
            UPDATE opening_signals os
               SET lock_key = o.new_key
              FROM ({_OWNERS}) o
             WHERE os.lock_key = o.old_key
               AND NOT EXISTS (
                   SELECT 1 FROM opening_signals n WHERE n.lock_key = o.new_key
               )
        """)
        conn.commit()
        logger.success(f"re-ledgered {len(ledger)} push_sent row(s), re-keyed "
                       f"{len(shadow)} opening_signals row(s)")
        return len(ledger), len(shadow)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="write the changes (default is a dry run)")
    args = ap.parse_args()
    run(apply=args.apply)
