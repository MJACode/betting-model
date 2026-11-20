"""Put back the 2023-2025 NCAAF kickoff times the 2026-11-14 hourly purchase overwrote.

The hourly NCAAF history purchase (worker jobs 1316678-1316680 and fills
1317291-1317293, mike: "Buy all of it now") ran `_upsert_games` on every
snapshot, which sets `commence_time` and `data_source` from the snapshot. A
backfill's snapshots do not arrive in time order: the fills ran last with
early-week snapshots, and post-start snapshots list the actual start. Measured
against the local copy of `games` taken at 05:43 UTC that day, before the
purchase: 1,590 of 3,911 odds rows of 2023-2025 games changed kickoff, 84 by
more than an hour (Florida at Miami 2025-09-20: 23:30 to 16:00 UTC), and the
touched rows' `data_source` became 'live'. The ingestor no longer does this
(`data/ingestors/odds_ingestor._history_game_rows`).

This script:
  1. reads the pre-purchase values from that local copy (--before, the
     mirror's public.games parquet chunks, saved aside before the next copy);
  2. reads the current production rows the purchase touched (NCAAF, seasons
     2023-2025, updated_at from --since);
  3. stores every row whose kickoff or source differs, both values, in
     games_ncaaf_kickoff_restore_20261114 (row security on, no public read),
     so nothing written is lost and the restore can be undone;
  4. sets each such row's commence_time and data_source back, only where the
     row still holds the purchase's values, in the same transaction.

    python -m scripts.restore_ncaaf_kickoffs_20261114 --before DIR [--since "2026-11-14 17:45"] [--apply]

Without --apply it prints what it would do and writes nothing.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pyarrow.dataset as ds

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.anon_readable import lock_down  # noqa: E402
from data.db import get_connection  # noqa: E402

TABLE = "games_ncaaf_kickoff_restore_20261114"


def _v(x):
    """A stored text value, with every null spelled None."""
    return None if x is None or (isinstance(x, float) and x != x) else str(x)
SEASONS = (2023, 2024, 2025)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--before", required=True, type=Path)
    ap.add_argument("--since", default="2026-11-14 17:45")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)

    d = ds.dataset(str(a.before), format="parquet", exclude_invalid_files=True)
    pre = d.to_table(columns=["game_id", "season", "commence_time", "data_source"],
                     filter=ds.field("sport") == "NCAAF").to_pandas()
    pre = pre.set_index("game_id")

    conn = get_connection()
    try:
        cur = conn.execute("""
            SELECT game_id, season, commence_time, data_source, updated_at
            FROM games
            WHERE sport = 'NCAAF' AND season = ANY(%s) AND updated_at >= %s
        """, (list(SEASONS), a.since)).fetchall()
        rows = []
        for gid, season, ct, src, upd in cur:
            if gid not in pre.index:
                continue                       # a game the purchase added: no earlier value
            b = pre.loc[gid]
            before_ct, before_src = _v(b["commence_time"]), _v(b["data_source"])
            if before_ct != _v(ct) or before_src != _v(src):
                rows.append((gid, int(season), before_ct, _v(ct), before_src, _v(src), _v(upd)))
        moved = sum(1 for r in rows if r[2] != r[3])
        print(f"touched since {a.since}: {len(cur)}; with an earlier value that differs: {len(rows)} "
              f"({moved} kickoff, {len(rows) - moved} source only)", flush=True)
        if not a.apply:
            for r in rows[:10]:
                print("  ", r, flush=True)
            print("dry run: nothing written", flush=True)
            return
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                game_id TEXT PRIMARY KEY,
                season INTEGER,
                commence_time_before TEXT,
                commence_time_purchase TEXT,
                data_source_before TEXT,
                data_source_purchase TEXT,
                purchase_updated_at TEXT,
                restored_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )""")
        lock_down(conn, TABLE)
        conn.executemany(f"""
            INSERT INTO {TABLE} (game_id, season, commence_time_before, commence_time_purchase,
                                 data_source_before, data_source_purchase, purchase_updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (game_id) DO NOTHING
        """, rows)
        n = conn.execute(f"""
            UPDATE games g
               SET commence_time = b.commence_time_before,
                   data_source   = b.data_source_before,
                   updated_at    = NOW()::TEXT
              FROM {TABLE} b
             WHERE g.game_id = b.game_id
               AND g.commence_time IS NOT DISTINCT FROM b.commence_time_purchase
               AND g.data_source IS NOT DISTINCT FROM b.data_source_purchase
        """).rowcount
        conn.commit()
        print(f"stored {len(rows)} rows in {TABLE}; restored {n}", flush=True)
        left, = conn.execute(f"""
            SELECT count(*) FROM games g JOIN {TABLE} b ON b.game_id = g.game_id
             WHERE g.commence_time IS DISTINCT FROM b.commence_time_before
                OR g.data_source IS DISTINCT FROM b.data_source_before
        """).fetchone()
        print(f"rows still differing from their pre-purchase value: {left}", flush=True)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
