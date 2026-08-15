"""
Scan the T-7 to T-2 day window at 6-hour resolution.

This is the window where Pinnacle is live (it posts around T-6.5) while soft
books still carry stale early numbers. Each snapshot is cached, so this is
resumable and reruns are free.
"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_ingest.odds_api import OddsAPIClient, ledger_status
from data_ingest.parse import snapshot_to_frame

API_KEY = os.environ["THE_ODDS_API_KEY"]
SEASONS = [int(s) for s in sys.argv[1:]] or [2023, 2024, 2025]

client = OddsAPIClient(API_KEY, quota_guard=2000)

g = pd.read_csv("data/raw/games.csv")
g = g[g.season.isin(SEASONS)].copy()
dt = pd.to_datetime(g.gameday + " " + g.gametime)
g["kick_utc"] = dt.dt.tz_localize(
    ZoneInfo("America/New_York"), ambiguous=True, nonexistent="shift_forward"
).dt.tz_convert("UTC")

jobs = []
for (season, week), grp in g.groupby(["season", "week"]):
    fk = grp.kick_utc.min()
    t = fk - pd.Timedelta(days=7)
    while t <= fk - pd.Timedelta(days=2):
        jobs.append((season, week, t.strftime("%Y-%m-%dT%H:%M:%SZ")))
        t += pd.Timedelta(hours=6)

print(f"seasons {SEASONS} | snapshots {len(jobs)} | max cost {len(jobs)*20}")
print(f"ledger before: {ledger_status()}", flush=True)


def work(j):
    season, week, ts = j
    r = client.historical_odds(ts, regions="us,eu", markets="spreads")
    d = snapshot_to_frame(r.payload, ts)
    d["season"] = season
    d["week"] = week
    d["snap"] = pd.Timestamp(ts)
    return d, r.cost


frames, spent, done = [], 0, 0
with ThreadPoolExecutor(max_workers=8) as ex:
    futs = [ex.submit(work, j) for j in jobs]
    for f in as_completed(futs):
        d, c = f.result()
        frames.append(d)
        spent += c
        done += 1
        if done % 150 == 0:
            print(f"  {done}/{len(jobs)} spent={spent}", flush=True)

out = pd.concat(frames, ignore_index=True)
tag = "_".join(str(s) for s in SEASONS)
out.to_parquet(f"data/raw/opener_window_{tag}.parquet", index=False)
print(f"rows {len(out):,} | spent {spent} | ledger {ledger_status()}")
