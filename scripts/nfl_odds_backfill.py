#!/usr/bin/env python3
"""
Publish the NFL odds snapshot cache into Supabase as `nfl_odds_history`.

    python -m scripts.nfl_odds_backfill --dry-run     # size it, write nothing
    python -m scripts.nfl_odds_backfill               # backfill everything
    python -m scripts.nfl_odds_backfill --season 2025 # one season
    python -m scripts.nfl_odds_backfill --since 2026-08-01

WHY
---
~100,000 Odds API credits of NFL book quotes existed only as JSON files under
`nfl/data/odds_cache/`, plus a derived parquet. Nothing else in the platform
could read them, and in production they live on the worker's EPHEMERAL disk —
a redeploy loses them. This makes them queryable and durable.

WHY NOT THE `odds` TABLE
------------------------
`odds` is the app's hot path and is capped by data/prune_odds.py, which DELETES
every non-DraftKings row once its game ages out. 47 books of NFL history would
be pruned away by design, and would add roughly 230MB to a ~2GB database that
is already managing growth. `nfl_odds_history` is append-only, never pruned,
and read by models and backtests rather than by the app.

IDEMPOTENT AND RESUMABLE
------------------------
The primary key is (snapshot_at, game_id, bookmaker, market) and every write is
ON CONFLICT DO NOTHING, so a re-run inserts only what is missing. That matters:
this is millions of rows over a network, and it WILL be interrupted.

SOURCE
------
`data/processed/dev_long.parquet`, which `screen_books.py --rebuild` already
produces from the cache. It is the same frame the backtests read, so what lands
in Supabase is exactly what the models were validated on — not a second
parse that could drift.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEV_LONG = ROOT / "nfl" / "data" / "processed" / "dev_long.parquet"
BATCH = 5000

COLUMNS = ("snapshot_at", "game_id", "season", "week", "commence_time",
           "bookmaker", "market", "point", "price_home", "price_away", "lead_hours")


def load_frame(season=None, since=None):
    import pandas as pd
    if not DEV_LONG.exists():
        raise SystemExit(
            f"{DEV_LONG} missing. Build it first (0 credits):\n"
            f"    cd nfl && python scripts/screen_books.py --rebuild")
    d = pd.read_parquet(DEV_LONG)
    keep = ["snap_ts", "game_id", "season", "week", "commence_time", "book",
            "market", "point", "px_home", "px_away", "lead_h"]
    missing = [c for c in keep if c not in d.columns]
    if missing:
        raise SystemExit(f"dev_long is missing {missing} — rebuild it")
    d = d[keep].rename(columns={
        "snap_ts": "snapshot_at", "book": "bookmaker",
        "px_home": "price_home", "px_away": "price_away", "lead_h": "lead_hours"})
    d = d.dropna(subset=["snapshot_at", "game_id", "bookmaker", "market"])
    if season:
        d = d[d.season == season]
    if since:
        d = d[d.snapshot_at >= since]
    # The PK is (snapshot_at, game_id, bookmaker, market). A book can quote the
    # same market twice in one snapshot (alternate lines); keep the row closest
    # to the main number rather than letting ON CONFLICT pick arbitrarily.
    d = d.sort_values("point", key=lambda s: s.abs())
    before = len(d)
    d = d.drop_duplicates(subset=["snapshot_at", "game_id", "bookmaker", "market"],
                          keep="first")
    if before != len(d):
        print(f"  collapsed {before - len(d):,} alternate-line rows to the main number",
              file=sys.stderr)
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=None)
    ap.add_argument("--since", default=None, help="ISO date lower bound")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None, help="cap rows, for a smoke test")
    a = ap.parse_args()

    d = load_frame(a.season, a.since)
    if a.limit:
        d = d.head(a.limit)

    # ~420 bytes/row measured against the live `odds` table (890,079 rows in
    # 373 MB, indexes included). An earlier 110-byte guess was 4x optimistic.
    est_mb = len(d) * 420 / 1_048_576
    print(f"rows to publish : {len(d):,}")
    print(f"markets         : {d.market.value_counts().to_dict()}")
    print(f"books           : {d.bookmaker.nunique()}")
    print(f"seasons         : {sorted(int(x) for x in d.season.dropna().unique())}")
    print(f"span            : {d.snapshot_at.min()} -> {d.snapshot_at.max()}")
    print(f"rough size      : ~{est_mb:.0f} MB")

    if a.dry_run:
        print("\nDRY RUN — nothing written.")
        return 0

    from data.db import get_connection
    conn = get_connection()
    written = 0
    try:
        cur = conn.execute("SELECT COUNT(*) FROM nfl_odds_history")
        before = cur.fetchone()[0]
        print(f"\ntable currently holds {before:,} rows; inserting in batches of {BATCH}")

        # executemany -> psycopg2.extras.execute_batch. Row-by-row over a
        # network would take hours for 2.3M rows; batched it is minutes.
        sql = """
            INSERT INTO nfl_odds_history
                (snapshot_at, game_id, season, week, commence_time,
                 bookmaker, market, point, price_home, price_away, lead_hours)
            VALUES (%(snapshot_at)s, %(game_id)s, %(season)s, %(week)s,
                    %(commence_time)s, %(bookmaker)s, %(market)s, %(point)s,
                    %(price_home)s, %(price_away)s, %(lead_hours)s)
            ON CONFLICT (snapshot_at, game_id, bookmaker, market) DO NOTHING
        """
        recs = [{k: (None if _isna(r.get(k)) else r.get(k)) for k in COLUMNS}
                for r in d.to_dict("records")]
        for i in range(0, len(recs), BATCH):
            conn.executemany(sql, recs[i:i + BATCH])
            conn.commit()
            written += len(recs[i:i + BATCH])
            if (i // BATCH) % 20 == 0:
                print(f"  {written:,}/{len(recs):,}", flush=True)

        after = conn.execute("SELECT COUNT(*) FROM nfl_odds_history").fetchone()[0]
        print(f"\ndone. table now holds {after:,} rows (+{after - before:,} new)")
    finally:
        conn.close()
    return 0


def _isna(v):
    try:
        import pandas as pd
        return v is None or pd.isna(v)
    except (TypeError, ValueError):
        return v is None


if __name__ == "__main__":
    raise SystemExit(main())
