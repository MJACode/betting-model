#!/usr/bin/env python3
"""
Scan the T-7 to T-2 day window at 6-hour resolution, for any market.

This is the window where Pinnacle is live (it posts around T-6.5) while soft
books still carry stale early numbers. Each snapshot is cached, so this is
resumable and reruns are free.

    python scripts/scan_opener_window.py --markets h2h 2024 2025
    python scripts/scan_opener_window.py --markets totals,h2h --dry-run 2023 2024 2025
    python scripts/scan_opener_window.py --markets spreads 2025      # already cached, free

COST
----
Historical snapshots cost `10 x n_markets x n_regions`. The cache key includes
the markets string, so asking for "spreads,totals" in one call is a DIFFERENT
key from "spreads" and re-pays for the spreads data already on disk. This
script therefore issues one call per market and never bundles them: at
regions=us,eu that is 20 credits per market per snapshot, and any market
already scanned costs nothing on a rerun.

Always run --dry-run first. It prices the job exactly and spends nothing.
"""

from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_ingest.odds_api import CACHE_DIR, OddsAPIClient, _key, ledger_status
from data_ingest.parse import snapshot_to_frame

VALID_MARKETS = ("spreads", "totals", "h2h")


def schedule(seasons) -> pd.DataFrame:
    path = "data/raw/games.csv" if os.path.exists("data/raw/games.csv") else "data/games.csv"
    g = pd.read_csv(path)
    g = g[g.season.isin(seasons)].copy()
    if g.empty:
        raise SystemExit(f"no games for seasons {seasons} in {path}")
    dt = pd.to_datetime(g.gameday + " " + g.gametime, errors="coerce")
    g["kick_utc"] = dt.dt.tz_localize(
        ZoneInfo("America/New_York"), ambiguous=True, nonexistent="shift_forward"
    ).dt.tz_convert("UTC")
    return g.dropna(subset=["kick_utc"])


def build_jobs(g: pd.DataFrame, markets, regions, lo_days, hi_days, step_h):
    jobs = []
    for (season, week), grp in g.groupby(["season", "week"]):
        fk = grp.kick_utc.min()
        t = fk - pd.Timedelta(days=lo_days)
        while t <= fk - pd.Timedelta(days=hi_days):
            ts = t.strftime("%Y-%m-%dT%H:%M:%SZ")
            for mk in markets:
                jobs.append((season, week, ts, mk))
            t += pd.Timedelta(hours=step_h)
    return jobs


def cached(ts: str, regions: str, market: str) -> bool:
    return (CACHE_DIR / f"{_key(ts, regions, market)}.json").exists()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("seasons", nargs="*", type=int, default=[2023, 2024, 2025])
    ap.add_argument("--markets", default="spreads",
                    help="comma separated: spreads, totals, h2h. Fetched as separate "
                         "calls so anything already cached stays free")
    ap.add_argument("--regions", default="us,eu")
    ap.add_argument("--lead-lo-days", type=float, default=7.0)
    ap.add_argument("--lead-hi-days", type=float, default=2.0)
    ap.add_argument("--step-hours", type=float, default=6.0)
    ap.add_argument("--quota-guard", type=int, default=2000)
    ap.add_argument("--max-credits", type=int, default=None,
                    help="refuse to start if the job would cost more than this")
    ap.add_argument("--dry-run", action="store_true", help="price the job, spend nothing")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()

    markets = [m.strip() for m in a.markets.split(",") if m.strip()]
    bad = [m for m in markets if m not in VALID_MARKETS]
    if bad:
        raise SystemExit(f"unknown market(s) {bad}. Valid: {list(VALID_MARKETS)}")

    seasons = a.seasons or [2023, 2024, 2025]
    jobs = build_jobs(schedule(seasons), markets, a.regions,
                      a.lead_lo_days, a.lead_hi_days, a.step_hours)
    per_call = 10 * len(a.regions.split(","))
    todo = [j for j in jobs if not cached(j[2], a.regions, j[3])]
    cost = len(todo) * per_call

    print(f"seasons {seasons} | markets {markets} | regions {a.regions}")
    print(f"snapshots {len(jobs)}  cached {len(jobs)-len(todo)}  to fetch {len(todo)}")
    print(f"cost {per_call} credits per call -> {cost:,} credits for this job")
    for mk in markets:
        m = [j for j in todo if j[3] == mk]
        print(f"  {mk:8s} {len(m):5d} to fetch = {len(m)*per_call:,} credits")
    print(f"ledger before: {ledger_status()}", flush=True)

    if a.dry_run:
        print("\nDRY RUN, nothing fetched.")
        return 0
    if a.max_credits is not None and cost > a.max_credits:
        raise SystemExit(f"job costs {cost:,}, above --max-credits {a.max_credits:,}. Aborting.")
    if not todo:
        print("\nEverything already cached. Nothing to spend.")
        return 0

    key = os.environ.get("THE_ODDS_API_KEY")
    if not key:
        raise SystemExit("THE_ODDS_API_KEY is not set. Use --dry-run to price the job.")
    client = OddsAPIClient(key, quota_guard=a.quota_guard)

    def work(j):
        season, week, ts, mk = j
        r = client.historical_odds(ts, regions=a.regions, markets=mk)
        d = snapshot_to_frame(r.payload, ts)
        d["season"], d["week"], d["snap"] = season, week, pd.Timestamp(ts)
        return d, r.cost

    frames, spent, done = [], 0, 0
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(work, j) for j in jobs]
        for f in as_completed(futs):
            d, c = f.result()
            frames.append(d)
            spent += c
            done += 1
            if done % 150 == 0:
                print(f"  {done}/{len(jobs)} spent={spent}", flush=True)

    out = pd.concat(frames, ignore_index=True)
    os.makedirs("data/raw", exist_ok=True)
    tag = "_".join(str(s) for s in seasons) + "__" + "-".join(markets)
    out.to_parquet(f"data/raw/opener_window_{tag}.parquet", index=False)
    print(f"rows {len(out):,} | spent {spent} | ledger {ledger_status()}")
    print("\nNow rebuild the analysis frame (0 credits):")
    print("    python scripts/screen_books.py --rebuild --write")
    print("    python scripts/backtest_opener.py --market all --placebo draftkings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
