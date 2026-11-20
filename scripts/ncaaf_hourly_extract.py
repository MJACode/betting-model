"""Bring the NCAAF hourly price history bought on 2026-11-14 to mike's PC, as
light on production as the nightly copy, and join it to the research cache.

The three purchases (worker jobs 1316678-1316680, mike: "Buy all of it now")
stored about 2,500 hourly snapshots a season of moneyline and spread prices
under source `odds_api_historical`. The research cache
(scripts/ncaaf_search/audit_2026_11/extract_ncaaf.py) predates them. A
by-hand run of the nightly copy would re-count every chunk of the 50-million
row `odds` table against production, the load that held most of the
2026-11-12/13 timeouts (docs/sessions/2026-11.md, issue #1328). This reads
only the new rows: `odds_id` is the primary key and grows with time, so the
rows written since --since are one id range, read in --chunk-id slices, each
its own short read, waiting while more than --max-active other queries run
and never in minutes :15-:27 Eastern (the refresh pass), the copy's own
rules.

    python -m scripts.ncaaf_hourly_extract --old-cache DIR --out DIR
        [--since "2026-11-14 17:45"] [--chunk-ids 50000]

Writes OUT/ncaaf_odds.parquet (the old cache's rows, then the new ones in id
order) and OUT/ncaaf_games.parquet (every NCAAF row of `games`, re-read: the
purchase can add an odds-feed game the old cache lacks). Every row is in
Supabase; this is a cache of it, outside the repo. Read only.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.db import get_connection  # noqa: E402

SOURCE = "odds_api_historical"
ODDS_COLS = ["odds_id", "game_id", "sport", "market", "bookmaker", "snapshot_type", "snapshot_at",
             "home_price", "away_price", "draw_price", "spread_home", "total_line", "over_price",
             "under_price", "created_at", "home_link", "away_link", "draw_link", "over_link",
             "under_link", "home_sid", "away_sid", "draw_sid", "over_sid", "under_sid", "source"]
GAME_COLS = ["game_id", "sport", "season", "game_date", "home_team", "away_team", "home_score",
             "away_score", "commence_time"]
_ET = ZoneInfo("America/New_York")


def first_id_since(conn, since: str) -> int:
    """The smallest odds_id whose created_at is at or after `since`, by
    binary search on the primary key (each probe one index lookup)."""
    lo, hi = conn.execute("SELECT min(odds_id), max(odds_id) FROM odds").fetchone()
    lo, hi = int(lo), int(hi)
    while lo < hi:
        mid = (lo + hi) // 2
        row = conn.execute("SELECT created_at::timestamptz FROM odds WHERE odds_id >= %s "
                           "ORDER BY odds_id LIMIT 1", (mid,)).fetchone()
        if row is None or row[0] >= pd.Timestamp(since, tz="UTC").to_pydatetime():
            hi = mid
        else:
            lo = mid + 1
    return lo


def _polite(conn, max_active: int) -> None:
    while True:
        m = datetime.now(_ET).minute
        if 15 <= m <= 27:
            time.sleep(30)
            continue
        n, = conn.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active' "
                          "AND pid <> pg_backend_pid()").fetchone()
        if int(n) <= max_active:
            return
        time.sleep(10)


def read_new(conn, lo: int, hi: int, chunk: int, max_active: int, pause: float) -> pd.DataFrame:
    sel = ", ".join(f"{c}::text" if c not in ("odds_id",) else c for c in ODDS_COLS)
    parts, n, t0 = [], 0, time.time()
    for a in range(lo - 1, hi, chunk):
        _polite(conn, max_active)
        rows = conn.execute(f"SELECT {sel} FROM odds WHERE odds_id > %s AND odds_id <= %s "
                            f"AND source = %s AND game_id LIKE 'NCAAF\\_%%'",
                            (a, min(a + chunk, hi), SOURCE)).fetchall()
        conn.commit()
        if rows:
            parts.append(pd.DataFrame(rows, columns=ODDS_COLS))
            n += len(rows)
        print(f"  ids {a + 1}-{min(a + chunk, hi)}: {len(rows)} rows, {n} so far "
              f"({time.time() - t0:.0f}s)", flush=True)
        time.sleep(pause)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=ODDS_COLS)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--old-cache", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--since", default="2026-11-14 17:45")
    ap.add_argument("--chunk-ids", type=int, default=50_000)
    ap.add_argument("--max-active", type=int, default=6)
    ap.add_argument("--pause", type=float, default=1.0)
    ap.add_argument("--max-chunks", type=int, default=None,
                    help="stop after this many slices (a trial run)")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    old = pq.read_table(a.old_cache / "ncaaf_odds.parquet")
    old_max = int(pc.max(old["odds_id"]).as_py())
    conn = get_connection()
    try:
        lo = max(first_id_since(conn, a.since), old_max + 1)
        hi, = conn.execute("SELECT max(odds_id) FROM odds").fetchone()
        if a.max_chunks:
            hi = min(int(hi), lo - 1 + a.max_chunks * a.chunk_ids)
        print(f"old cache: {old.num_rows} rows to odds_id {old_max}; reading ids {lo}-{hi}", flush=True)
        new = read_new(conn, lo, int(hi), a.chunk_ids, a.max_active, a.pause)
        g = conn.execute("SELECT game_id, sport, season, game_date::text, home_team, away_team, "
                         "home_score::text, away_score::text, commence_time::text "
                         "FROM games WHERE sport = 'NCAAF'").fetchall()
    finally:
        conn.close()
    new = new.sort_values("odds_id", kind="mergesort")
    for c in ODDS_COLS:
        if c != "odds_id":
            new[c] = new[c].astype("string")
    new_t = pa.Table.from_pandas(new[ODDS_COLS], schema=old.schema.remove_metadata(),
                                 preserve_index=False)
    both = pa.concat_tables([old.replace_schema_metadata(None), new_t])
    pq.write_table(both, a.out / "ncaaf_odds.parquet", compression="zstd")
    games = pd.DataFrame(g, columns=GAME_COLS)
    games.to_parquet(a.out / "ncaaf_games.parquet", index=False)
    old_g = pd.read_parquet(a.old_cache / "ncaaf_games.parquet", columns=["game_id"])
    print(f"wrote {both.num_rows} odds rows ({len(new)} new, "
          f"{new['created_at'].nunique()} pulls, {new['game_id'].nunique()} games) and "
          f"{len(games)} games ({len(set(games.game_id) - set(old_g.game_id))} not in the old cache)",
          flush=True)


if __name__ == "__main__":
    main()
