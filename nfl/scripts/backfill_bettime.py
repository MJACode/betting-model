"""Backfill bet-time (Tuesday 18:00 UTC) lines for 2020-2025."""

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_ingest.odds_api import OddsAPIClient, ledger_status
from data_ingest.parse import snapshot_to_frame, unmapped_teams

API_KEY = os.environ["THE_ODDS_API_KEY"]
REGIONS = "us,eu"
MARKETS = "spreads,totals"

client = OddsAPIClient(API_KEY, quota_guard=400)

snaps = pd.read_parquet("data/raw/snap_bettime.parquet")
snaps["date_str"] = pd.to_datetime(snaps.snap_utc, utc=True).dt.strftime(
    "%Y-%m-%dT%H:%M:%SZ"
)

print(f"bet-time snapshots to fetch: {len(snaps)}")
print(f"projected cost: {len(snaps) * client.cost_of(REGIONS, MARKETS)} credits")
print(f"ledger before: {ledger_status()}")


def work(row):
    res = client.historical_odds(
        row.date_str, regions=REGIONS, markets=MARKETS
    )
    label = f"{int(row.season)}W{int(row.week)}"
    df = snapshot_to_frame(res.payload, label)
    df["season"] = int(row.season)
    df["week"] = int(row.week)
    return df, unmapped_teams(res.payload), res.from_cache, res.cost


frames, unmapped, cached, spent = [], set(), 0, 0
with ThreadPoolExecutor(max_workers=6) as ex:
    futs = {ex.submit(work, r): r for r in snaps.itertuples()}
    for i, f in enumerate(as_completed(futs), 1):
        df, um, fc, cost = f.result()
        frames.append(df)
        unmapped |= um
        cached += int(fc)
        spent += cost
        if i % 25 == 0:
            print(f"  {i}/{len(snaps)} done, spent so far {spent}")

out = pd.concat(frames, ignore_index=True)
out.to_parquet("data/raw/bettime_raw.parquet", index=False)

print(f"\nrows: {len(out):,}  cache hits: {cached}  credits spent: {spent}")
print(f"unmapped teams: {unmapped or 'none'}")
print(f"ledger after: {ledger_status()}")
print(f"\nbooks present: {sorted(out.book.unique())}")
print(f"\nrows per season:\n{out.groupby('season').size()}")
