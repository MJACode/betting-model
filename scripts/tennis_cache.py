"""A local cache of the tennis tables, for research: one read of production,
by indexed key, then every study reads parquet.

A cache of Supabase, never a store of its own (CLAUDE.md section 1b): every
row is already in the database and the files are rebuilt by this command.
tennis_odds_quotes is read one sport key at a time on its (sport_key,
commence_time) index; a single scan of its 3 million rows hit the statement
timeout on 2026-11-13.

    python -m scripts.tennis_cache --out C:/Users/micha/tennis_research/cache
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

SMALL = ("tennis_espn_matches", "tennis_pinnacle_matchups", "tennis_pinnacle_prices",
         "tennis_dk_selections")


def _frame(conn, sql: str, params=()) -> pd.DataFrame:
    cur = conn.execute(sql, params)
    rows = cur.fetchall()
    desc = cur._cur.description          # the wrapper's psycopg2 cursor (data/db._CursorResult)
    return pd.DataFrame(rows, columns=[d[0] for d in desc])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    from data.db import get_connection
    conn = get_connection()
    try:
        keys = [r[0] for r in conn.execute(
            "SELECT DISTINCT sport_key FROM tennis_odds_fetches WHERE endpoint IN ('odds', 'live')").fetchall()]
        parts = []
        for k in sorted(keys):
            t0 = time.time()
            f = _frame(conn, "SELECT * FROM tennis_odds_quotes WHERE sport_key = %s", (k,))
            parts.append(f)
            print(f"tennis_odds_quotes {k}: {len(f):,} rows in {time.time() - t0:.1f}s", flush=True)
        q = pd.concat(parts, ignore_index=True)
        q.to_parquet(a.out / "tennis_odds_quotes.parquet", index=False)
        print(f"tennis_odds_quotes: {len(q):,} rows", flush=True)
        for t in SMALL:
            f = _frame(conn, f"SELECT * FROM {t}")
            for c in f.columns:
                if f[c].dtype == object and f[c].map(lambda v: isinstance(v, list)).any():
                    f[c] = f[c].map(lambda v: list(v) if v is not None else None)
            f.to_parquet(a.out / f"{t}.parquet", index=False)
            print(f"{t}: {len(f):,} rows", flush=True)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
