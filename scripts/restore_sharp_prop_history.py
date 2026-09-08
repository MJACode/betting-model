"""Put the sharp-book prop history back into Supabase, where it belongs.

WHY IT EXISTS. On 2026-09-08 `player_prop_odds` held no NFL sharp prop snapshot
older than 2026-04-01. The pruner's prop-table carve-out was keyed on
config.SHARP_BOOKMAKERS ("pinnacle" alone), so betonlineag was never protected
and the older pinnacle rows had already gone before the carve-out existed.
117,048 sharp snapshots spanning 2023-2025 -- the entire history the
market-relative rule is validated on -- survived only in the tracked parquet at
data/local/nfl_prop_odds.parquet.

That is the arrangement CLAUDE.md rules out: a dataset that cost money and time
to acquire, living in exactly one place, where the next routine refresh
overwrites it. Being in git makes it recoverable, not queryable -- nothing can
join it against `picks`, and no backup story covers it but the repo's.

THIS DOES NOT MAKE THE ROWS SAFE ON ITS OWN. Restoring history into a table that
still prunes it just buys time. The durable half is
data/prune_odds._prop_reference_books, which derives the protected set from the
models so a new reference is protected the day it is added. Run that fix first;
this script assumes it is in place.

SAFE TO RE-RUN. `player_prop_odds` has no unique constraint on the natural key
(only a serial primary key), so ON CONFLICT cannot deduplicate and the anti-join
is done here: every row already present is skipped by (game_id, player_name,
market, line, bookmaker, snapshot_at, snapshot_type). Rows whose game_id is not
in `games` are skipped too -- there is a foreign key, and an orphan would abort
the batch it lands in.

    python -m scripts.restore_sharp_prop_history --dry-run
    python -m scripts.restore_sharp_prop_history
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from loguru import logger
from psycopg2.extras import execute_values

from data import local_store
from data.db import get_connection

KEY = ["game_id", "player_name", "market", "line", "over_price", "under_price",
       "bookmaker", "snapshot_at", "snapshot_type"]
INSERT_COLS = ["game_id", "game_date", "player_name", "market", "line",
               "over_price", "under_price", "bookmaker", "snapshot_at",
               "snapshot_type"]


def _norm_key(game_id, player_name, market, line, over_price, under_price,
              bookmaker, snapshot_at, snapshot_type) -> tuple:
    """The natural key, normalised so a parquet row and a database row compare.

    NAMED, NOT POSITIONAL. Both sides of the anti-join build this key, and the
    two sources hand their columns over in different orders; an off-by-one here
    does not raise, it just makes every row look new and re-inserts the whole
    history.

    Timestamps are PARSED, never string-compared: the feed renders
    '2024-09-21T16:55:38Z' and Postgres renders '2024-09-21 16:55:38+00:00',
    and at position 10 that is 'T' (84) against ' ' (32). Comparing those as
    text makes every row look new in exactly the same way.
    """
    def _num(v, cast):
        return None if v is None or pd.isna(v) else cast(v)

    ts = pd.to_datetime(snapshot_at, errors="coerce", utc=True)
    return (
        str(game_id), str(player_name), str(market),
        _num(line, lambda x: round(float(x), 2)),
        _num(over_price, int), _num(under_price, int),
        str(bookmaker),
        None if pd.isna(ts) else ts.isoformat(),
        str(snapshot_type),
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--batch", type=int, default=5000)
    a = ap.parse_args()

    local_store.activate()
    df = local_store.read_table("nfl_prop_odds")
    if df is None or df.empty:
        logger.error("no local cache to restore from")
        return

    import models.nfl_prop_market as mk
    df = df[df.bookmaker.isin(mk.SHARP_BOOKS)].copy()
    logger.info(f"cache holds {len(df):,} sharp-book rows")

    conn = get_connection()
    try:
        have = set()
        rows = conn.execute(
            "SELECT game_id, player_name, market, line, over_price, "
            "under_price, bookmaker, snapshot_at, snapshot_type "
            "FROM player_prop_odds WHERE bookmaker = ANY(%s)",
            (list(mk.SHARP_BOOKS),)).fetchall()
        for r in rows:
            have.add(_norm_key(*r))
        logger.info(f"database holds {len(rows):,} sharp-book rows "
                    f"({len(have):,} distinct)")

        known = {r[0] for r in conn.execute(
            "SELECT game_id FROM games WHERE game_id LIKE 'NFL%%'").fetchall()}

        missing, orphan = [], 0
        for t in df[INSERT_COLS].itertuples(index=False):
            k = _norm_key(t.game_id, t.player_name, t.market, t.line,
                          t.over_price, t.under_price, t.bookmaker,
                          t.snapshot_at, t.snapshot_type)
            if k in have:
                continue
            if t.game_id not in known:
                orphan += 1
                continue
            have.add(k)                       # de-dupe within the cache too
            missing.append(tuple(None if pd.isna(v) else v for v in t))

        logger.info(f"{len(missing):,} rows to restore "
                    f"({orphan:,} skipped: game_id not in `games`)")
        if a.dry_run or not missing:
            logger.info("dry run — nothing written" if a.dry_run else "nothing to do")
            return

        cur = conn.cursor()
        done = 0
        for i in range(0, len(missing), a.batch):
            chunk = missing[i:i + a.batch]
            execute_values(
                cur,
                f"INSERT INTO player_prop_odds ({', '.join(INSERT_COLS)}) VALUES %s",
                chunk)
            conn.commit()
            done += len(chunk)
            logger.info(f"  restored {done:,}/{len(missing):,}")
        logger.success(f"restored {done:,} sharp-book prop snapshots")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
