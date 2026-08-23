#!/usr/bin/env python3
"""
Per-book integrity screen. Run this BEFORE any analysis that selects on extreme
values, and re-run it whenever new books appear in the feed.

    python scripts/screen_books.py                 # T-7 to T-2, 2023-2025
    python scripts/screen_books.py --min-season 2020 --write

Why this exists: three separate findings in this project were reversed by data
quality rather than by modelling. Selection procedures preferentially sample
corrupted records, so a defect present in 0.4% of rows can supply 15% of
selected bets. Screen first, always.

Detection
  flip     |book_line + pinnacle_line| <= 1 while |pinnacle_line| >= 3.
           Equal magnitude, opposite sign, i.e. home and away transposed.
  dev sd   dispersion of (book_line - pinnacle_line). Clean books sit at
           0.34-0.68. Anything above ~0.9 is carrying junk.

Reads data/processed/dev_long.parquet if present, else rebuilds it from the
odds snapshot cache at zero credits.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_ingest.parse import snapshot_to_frame

CLEAN_SD_CEILING = 0.90
FLIP_RATE_CEILING = 0.001          # 0.1%
DEV_LONG = "data/processed/dev_long.parquet"


def _prob(px):
    px = np.asarray(px, dtype=float)
    return np.where(px > 0, 100.0 / (px + 100.0), -px / (-px + 100.0))


def devig_series(px_a, px_b, method: str = "power") -> np.ndarray:
    """
    De-vig a two-way market, vectorised.

    `power` solves for k with p_a^k + p_b^k = 1. Multiplicative de-vig assumes
    the hold is spread proportionally, which is wrong wherever the
    favourite-longshot bias bites - and on a moneyline it bites hard, which is
    the whole reason h2h needs its own treatment rather than reusing the totals
    code. Power de-vig is the standard fix and is what the moneyline arm uses.
    """
    a, b = _prob(px_a), _prob(px_b)
    ok = np.isfinite(a) & np.isfinite(b) & (a > 0) & (b > 0)
    out = np.full(a.shape, np.nan)
    if method == "mult":
        s = a + b
        np.divide(a, s, out=out, where=ok & (s > 0))
        return out
    # a**k + b**k is DECREASING in k for a, b < 1, so s > 1 means k is too small.
    lo = np.full(a.shape, 0.2)
    hi = np.full(a.shape, 5.0)
    for _ in range(60):                      # bisection on k, plenty of precision
        k = (lo + hi) / 2
        s = np.where(ok, a ** k + b ** k, 1.0)
        lo = np.where(s > 1, k, lo)
        hi = np.where(s > 1, hi, k)
    k = (lo + hi) / 2
    np.divide(a ** k, a ** k + b ** k, out=out, where=ok)
    return out


def _two_sided(fr, market, side_a, side_b, needs_point):
    """
    Collapse a market to one row per (snap, event, book) carrying BOTH prices,
    so downstream analysis can price either side of the bet.

    `side_a` is the side whose handicap is stored in `point` and whose price is
    `px_home`: the home spread, the Over, or the home moneyline. Everything
    downstream reads the pair the same way regardless of market.
    """
    f = fr[fr.market == market]
    if needs_point:
        f = f.dropna(subset=["point"])
    if f.empty:
        return None
    a = f[f.side == side_a].drop(columns=["side"])
    b = (f[f.side == side_b][["snap_ts", "event_id", "book", "price"]]
         .rename(columns={"price": "px_away"}))
    out = a.rename(columns={"price": "px_home"}).merge(
        b.drop_duplicates(["snap_ts", "event_id", "book"]),
        on=["snap_ts", "event_id", "book"], how="left")
    return out if len(out) else None


def _one(f):
    try:
        d = json.load(open(f))
    except (json.JSONDecodeError, OSError):
        return None
    fr = snapshot_to_frame(d, os.path.basename(f)[:-5])
    if fr.empty:
        return None
    parts = [
        _two_sided(fr, "spreads", "home", "away", True),
        _two_sided(fr, "totals", "Over", "Under", True),
        # h2h has no handicap. `point` stays null and the deviation is defined
        # in probability space instead; see backtest_opener.
        _two_sided(fr, "h2h", "home", "away", False),
    ]
    parts = [p for p in parts if p is not None]
    if not parts:
        return None
    return pd.concat(parts, ignore_index=True)


def rebuild() -> pd.DataFrame:
    files = sorted(glob.glob("data/odds_cache/*.json"))
    print(f"rebuilding from {len(files)} cached snapshots (0 credits) ...", file=sys.stderr)
    frames = []
    with ProcessPoolExecutor(max_workers=8) as ex:
        for r in ex.map(_one, files, chunksize=8):
            if r is not None:
                frames.append(r)
    d = pd.concat(frames, ignore_index=True)
    for c in ("snap_ts", "commence_time"):
        d[c] = pd.to_datetime(d[c], format="ISO8601", utc=True)

    g = pd.read_csv("data/games.csv")
    dt = pd.to_datetime(g.gameday + " " + g.gametime, errors="coerce")
    g["kick_utc"] = (dt.dt.tz_localize(ZoneInfo("America/New_York"), ambiguous=True,
                                       nonexistent="shift_forward").dt.tz_convert("UTC"))
    g["matchup"] = g.home_team + "_" + g.away_team
    d["matchup"] = d.home + "_" + d.away
    key = (g[["game_id", "season", "week", "matchup", "kick_utc", "spread_line",
              "total_line", "result", "total"]]
           .dropna(subset=["kick_utc"]).sort_values("kick_utc"))
    d = pd.merge_asof(d.dropna(subset=["commence_time"]).sort_values("commence_time"),
                      key, left_on="commence_time", right_on="kick_utc", by="matchup",
                      tolerance=pd.Timedelta(days=5), direction="nearest")
    d = d.dropna(subset=["game_id"])
    d["lead_h"] = (d.kick_utc - d.snap_ts).dt.total_seconds() / 3600

    # De-vigged probability of the `point` side (home spread / Over / home ML).
    # For spreads and totals this is a diagnostic. For h2h it IS the signal,
    # because a moneyline has no handicap to difference.
    d["p_home"] = devig_series(d.px_home.values, d.px_away.values)

    # Reference is Pinnacle, per market. Grouping without `market` would have
    # silently differenced a total against a spread once totals landed in here.
    keys = ["snap_ts", "game_id", "market"]
    pin = (d[d.book == "pinnacle"].groupby(keys, as_index=False)
           .agg(pin=("point", "median"), pin_p=("p_home", "median")))
    d = d.merge(pin, on=keys, how="left")
    d["dev"] = d.point - d.pin
    d["dev_p"] = d.p_home - d.pin_p
    os.makedirs("data/processed", exist_ok=True)
    d.to_parquet(DEV_LONG, index=False)
    for m, n in d.market.value_counts().items():
        print(f"  {m}: {n:,} rows, {d[d.market == m].game_id.nunique():,} games",
              file=sys.stderr)
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-season", type=int, default=2023)
    ap.add_argument("--lead-lo", type=float, default=48.0)
    ap.add_argument("--lead-hi", type=float, default=168.0)
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--write", action="store_true", help="write data/processed/book_screen.csv")
    a = ap.parse_args()

    d = rebuild() if (a.rebuild or not os.path.exists(DEV_LONG)) else pd.read_parquet(DEV_LONG)
    if "market" not in d.columns:
        raise SystemExit("dev_long.parquet predates the multi-market rebuild. "
                         "Rerun: python scripts/screen_books.py --rebuild")

    # The flip test is spread-specific: it detects home and away transposed,
    # which has no meaning for a total. Screen on spreads, as always.
    d = d[d.market == "spreads"]
    w = d[(d.lead_h.between(a.lead_lo, a.lead_hi)) & d.pin.notna()
          & (d.book != "pinnacle") & (d.season >= a.min_season)].copy()
    w["flip"] = ((w.point + w.pin).abs() <= 1) & (w.pin.abs() >= 3)
    w["big"] = w.dev.abs() >= 3

    r = (w.groupby("book").agg(n=("dev", "size"), games=("game_id", "nunique"),
                               flip_rate=("flip", "mean"), dev_sd=("dev", "std"),
                               big_rate=("big", "mean"))
         .sort_values("flip_rate", ascending=False))
    r["defective"] = (r.flip_rate > FLIP_RATE_CEILING) | (r.dev_sd > CLEAN_SD_CEILING)
    out = r.assign(flip_rate=(r.flip_rate * 100).round(2), dev_sd=r.dev_sd.round(3),
                   big_rate=(r.big_rate * 100).round(2))

    print(f"\n=== BOOK INTEGRITY SCREEN, seasons {a.min_season}+, "
          f"lead {a.lead_lo:.0f}-{a.lead_hi:.0f}h ===")
    print(out.to_string())
    bad = sorted(r.index[r.defective])
    print(f"\nDEFECTIVE ({len(bad)}): {bad}")
    print(f"CLEAN ({int((~r.defective).sum())} books)")
    print("\nExclude the defective set from every analysis that selects on cross-book "
          "deviation, line shopping, or best price.")
    if a.write:
        os.makedirs("data/processed", exist_ok=True)
        out.to_csv("data/processed/book_screen.csv")
        print("written: data/processed/book_screen.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
