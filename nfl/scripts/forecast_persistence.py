#!/usr/bin/env python3
"""
Does a wind flag raised a WEEK out survive to the day we would actually bet it?

    python scripts/forecast_persistence.py
    python scripts/forecast_persistence.py --threshold 12 --from-lead 7 --to-lead 3

THE QUESTION THIS ANSWERS

mike, 2026-09-06: "should we wait for closer to game so the weather can be more
dialed in but also don't want to lose edge." MAX_FIRE_LEAD was set to 4 that day
on the CALIBRATION argument -- past lead 7 the model's probability is a clip,
not a measurement. That argument is about the number attached to a bet. It says
nothing about how many bets there are, which is what mike actually asked, and
the two have different answers.

This measures the second one directly: of the games a long-lead card would have
FIRED ON, how many still clear the wind bar at the lead we now fire at, and --
the part that decides whether the gate is worth anything -- how the ones that
DROP OUT actually settled.

WHAT IT CANNOT DO, AND WHY THE HEADLINE IS A BOUND

Open-Meteo's wind_speed_10m_previous_dayN stops at N=7 (weather.py:176). The
five Week 1 picks locked at leads 7.2-8.7 days, so THE EXACT LEADS THAT
MOTIVATED THIS CANNOT BE MEASURED FROM ANY SOURCE WE HAVE. Lead 7 is the closest
available, and forecast skill only degrades further out, so every persistence
number here is an UPPER bound on what was happening at 8.7 days -- the real
behaviour is worse. Do not quote these as the lead-8 numbers.

Grading uses nflverse total_line and total off games.csv -- the same source as
the frozen rule's published 58.09% / n=408 -- so this is comparable to the
validation and needs neither the odds cache nor a credit. Pushes are excluded
from the rate and reported separately.

Free: Open-Meteo, zero Odds API credits. The first run fetches per
stadium-season and caches; later runs are local.
"""

from __future__ import annotations

import argparse
import os
import sys

import pandas as pd
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_ingest.weather import (INDOOR_ROOFS, DEPLOY_THRESHOLD, ISSUED_FORECAST_START,
                                 STADIUM_COORDS, fetch_issued_forecasts, wind_at_kickoff)

LEADS = (1, 2, 3, 4, 5, 6, 7)


def load_games(seasons: list[int]) -> pd.DataFrame:
    g = pd.read_csv("data/games.csv")
    g = g[g.season.isin(seasons)].copy()
    dt = pd.to_datetime(g.gameday + " " + g.gametime, errors="coerce")
    g["kick_utc"] = (dt.dt.tz_localize(ZoneInfo("America/New_York"), ambiguous=True,
                                       nonexistent="shift_forward").dt.tz_convert("UTC"))
    # Outdoor only, and only where the roof state is KNOWN. A blank roof is a
    # retractable venue whose state was never recorded; counting it as open-air
    # is the bug in docs/followups.md and it must not leak into a measurement of
    # the rule itself.
    g["roof"] = g.roof.fillna("").astype(str)
    g = g[~g.roof.isin(INDOOR_ROOFS) & (g.roof != "")]
    g = g[g.stadium_id.isin(STADIUM_COORDS)]
    g = g[g.kick_utc >= pd.Timestamp(ISSUED_FORECAST_START, tz="UTC")]
    return g.dropna(subset=["total", "total_line", "kick_utc"])


def attach_issued(g: pd.DataFrame) -> pd.DataFrame:
    """fc_d1..fc_d7 at kickoff hour for every game, fetched per stadium-season."""
    frames = []
    for (sid, season), part in g.groupby(["stadium_id", "season"]):
        start = (part.kick_utc.min() - pd.Timedelta(days=2)).strftime("%Y-%m-%d")
        end = (part.kick_utc.max() + pd.Timedelta(days=2)).strftime("%Y-%m-%d")
        print(f"  {sid} {season}: {start} -> {end} ({len(part)} games)", file=sys.stderr)
        frames.append(fetch_issued_forecasts(sid, start, end, leads=LEADS))
    hourly = pd.concat(frames, ignore_index=True)
    out = g.copy()
    for lead in LEADS:
        out[f"fc_d{lead}"] = wind_at_kickoff(hourly, out, f"fc_d{lead}").reindex(out.game_id).values
    return out


def _under_rate(df: pd.DataFrame):
    """(under rate excluding pushes, n graded, n pushes)."""
    d = df.dropna(subset=["total", "total_line"])
    push = int((d.total == d.total_line).sum())
    d = d[d.total != d.total_line]
    if d.empty:
        return None, 0, push
    return float((d.total < d.total_line).mean()), len(d), push


def _fmt(label: str, df: pd.DataFrame) -> str:
    rate, n, push = _under_rate(df)
    if rate is None:
        return f"  {label:<46} n=0"
    # Wald interval. Crude at these counts and stated as such -- it is here to
    # stop a 3-game cell being read as a result, not to be quoted.
    se = (rate * (1 - rate) / n) ** 0.5
    tail = f"  (+{push} push)" if push else ""
    return (f"  {label:<46} {rate*100:5.1f}% under  n={n:<4} "
            f"[{max(0.0, rate - 1.96 * se) * 100:4.1f}, "
            f"{min(1.0, rate + 1.96 * se) * 100:5.1f}]{tail}")


def report(g: pd.DataFrame, thr: float, hi: int, lo: int) -> None:
    both = g[g[f"fc_d{hi}"].notna() & g[f"fc_d{lo}"].notna()]
    fh = both[f"fc_d{hi}"] >= thr
    fl = both[f"fc_d{lo}"] >= thr
    survivors, dropped, added = both[fh & fl], both[fh & ~fl], both[~fh & fl]

    print(f"\n{'=' * 78}")
    print(f"WIND FLAG PERSISTENCE  lead {hi}d -> lead {lo}d, threshold {thr} mph")
    print("=" * 78)
    print(f"outdoor games with a known roof state and both forecasts: {len(both)}")
    print(f"\nflagged at lead {hi}: {int(fh.sum())}     flagged at lead {lo}: {int(fl.sum())}")
    if int(fh.sum()):
        print(f"P(still flagged at lead {lo} | flagged at lead {hi}) = "
              f"{len(survivors) / int(fh.sum()) * 100:.1f}%  "
              f"({len(survivors)}/{int(fh.sum())})")

    print("\nHOW EACH GROUP ACTUALLY SETTLED (nflverse closing total):")
    print(_fmt(f"flagged at {hi}d - what a long-lead card bets", both[fh]))
    print(_fmt(f"flagged at {lo}d - what the {lo}-day gate bets", both[fl]))
    print(_fmt(f"  survived {hi}d -> {lo}d", survivors))
    print(_fmt(f"  DROPPED {hi}d -> {lo}d (the gate skips these)", dropped))
    print(_fmt(f"  ADDED at {lo}d (the gate gains these)", added))
    print(_fmt("every outdoor game (base rate)", both))

    print("\nPER SEASON - a pooled edge that vanishes on a time split is noise:")
    for season, part in both.groupby("season"):
        ph = part[f"fc_d{hi}"] >= thr
        pl = part[f"fc_d{lo}"] >= thr
        print(f"  {season}:")
        print(_fmt(f"    flagged at {hi}d", part[ph]))
        print(_fmt(f"    flagged at {lo}d", part[pl]))
        print(_fmt(f"    DROPPED {hi}d -> {lo}d", part[ph & ~pl]))

    print(f"\nNOTE: lead {hi} is the LONGEST Open-Meteo archives (previous_dayN "
          "stops at 7). The picks that prompted this locked at 7.2-8.7 days, "
          "which no source can measure. Skill only degrades with lead, so "
          "persistence at 8.7d is WORSE than the number above.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", type=int, nargs="+", default=[2024, 2025])
    ap.add_argument("--threshold", type=float, default=DEPLOY_THRESHOLD)
    ap.add_argument("--from-lead", type=int, default=7, choices=LEADS)
    ap.add_argument("--to-lead", type=int, default=3, choices=LEADS)
    a = ap.parse_args()

    g = load_games(a.seasons)
    if g.empty:
        raise SystemExit("no gradeable outdoor games in those seasons")
    print(f"{len(g)} outdoor games, seasons {a.seasons}", file=sys.stderr)
    report(attach_issued(g), a.threshold, a.from_lead, a.to_lead)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
