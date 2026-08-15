"""
Backfill closing lines at each kickoff cluster.

A snapshot at time T returns every game that has not yet kicked off, so each
game's true closing quote is taken from the latest cluster snapshot strictly
before that game's own kickoff.

Usage: backfill_closing.py <markets> [min_season] [max_season]
"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_ingest.odds_api import OddsAPIClient, ledger_status
from data_ingest.parse import snapshot_to_frame

API_KEY = os.environ["THE_ODDS_API_KEY"]
MARKETS = sys.argv[1] if len(sys.argv) > 1 else "spreads"
MIN_S = int(sys.argv[2]) if len(sys.argv) > 2 else 2020
MAX_S = int(sys.argv[3]) if len(sys.argv) > 3 else 2025
REGIONS = "eu"  # Pinnacle lives here; it is the CLV benchmark

client = OddsAPIClient(API_KEY, quota_guard=400)

snaps = pd.read_parquet("data/raw/snap_closing.parquet")
snaps = snaps[(snaps.season >= MIN_S) & (snaps.season <= MAX_S)].copy()
snaps["date_str"] = pd.to_datetime(snaps.snap_utc, utc=True).dt.strftime(
    "%Y-%m-%dT%H:%M:%SZ"
)

cost_each = client.cost_of(REGIONS, MARKETS)
print(f"closing snapshots: {len(snaps)} | markets={MARKETS} seasons={MIN_S}-{MAX_S}")
print(f"projected cost: {len(snaps) * cost_each} credits")
print(f"ledger before: {ledger_status()}")


def work(row):
    res = client.historical_odds(row.date_str, regions=REGIONS, markets=MARKETS)
    df = snapshot_to_frame(res.payload, row.date_str)
    df["snap_req_utc"] = row.snap_utc
    return df, res.from_cache, res.cost


frames, cached, spent = [], 0, 0
with ThreadPoolExecutor(max_workers=6) as ex:
    futs = [ex.submit(work, r) for r in snaps.itertuples()]
    for i, f in enumerate(as_completed(futs), 1):
        df, fc, cost = f.result()
        frames.append(df)
        cached += int(fc)
        spent += cost
        if i % 100 == 0:
            print(f"  {i}/{len(snaps)} done, spent {spent}")

out = pd.concat(frames, ignore_index=True)
tag = MARKETS.replace(",", "_")
out.to_parquet(f"data/raw/closing_raw_{tag}_{MIN_S}_{MAX_S}.parquet", index=False)

print(f"\nrows: {len(out):,} | cache hits: {cached} | spent: {spent}")
print(f"ledger after: {ledger_status()}")
