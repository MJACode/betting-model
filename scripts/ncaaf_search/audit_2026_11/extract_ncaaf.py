"""Pull every NCAAF row out of the local Supabase mirror into one parquet per table.

Reads the mirror on disk only (no database). Run once; later scripts read the
extracts in this scratchpad.
"""
import sys
import time
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from paths import CACHE as OUT, MIRROR  # noqa: E402


def schema(table):
    d = ds.dataset(str(MIRROR / table), format="parquet", exclude_invalid_files=True)
    return d


def main():
    t0 = time.time()
    odds = schema("public.odds")
    print("odds columns:", [(f.name, str(f.type)) for f in odds.schema])
    flt = pc.starts_with(ds.field("game_id"), "NCAAF_")
    tbl = odds.to_table(filter=flt)
    print("NCAAF odds rows:", tbl.num_rows, f"{time.time()-t0:.0f}s")
    pq.write_table(tbl, OUT / "ncaaf_odds.parquet", compression="zstd")

    games = schema("public.games")
    print("games columns:", [(f.name, str(f.type)) for f in games.schema])
    g = games.to_table(filter=ds.field("sport") == "NCAAF")
    print("NCAAF games rows:", g.num_rows)
    pq.write_table(g, OUT / "ncaaf_games.parquet", compression="zstd")

    picks = schema("public.picks")
    p = picks.to_table(filter=ds.field("sport") == "NCAAF")
    print("NCAAF picks rows:", p.num_rows)
    pq.write_table(p, OUT / "ncaaf_picks.parquet", compression="zstd")

    for t in ("public.ncaaf_team_game_log", "public.ncaaf_team_stats", "public.ncaaf_teams",
              "public.game_weather", "public.ncaaf_live_states", "public.ncaaf_plays",
              "public.kalshi_ncaaf_events"):
        try:
            x = schema(t).to_table()
            pq.write_table(x, OUT / (t.split(".")[1] + ".parquet"), compression="zstd")
            print(t, x.num_rows)
        except Exception as e:  # noqa: BLE001
            print(t, "FAILED", e)
    print(f"done {time.time()-t0:.0f}s")


if __name__ == "__main__":
    sys.exit(main())
