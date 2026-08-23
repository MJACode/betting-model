#!/usr/bin/env python3
"""
Replay the weekly card against a completed week, using ONLY information that
existed at the chosen lead. This is the regression test for the live pipeline
and the honest way to see what a real week looks like.

    python scripts/replay_wind_card.py --season 2024 --week 12 --lead 3
    python scripts/replay_wind_card.py --season 2025 --week 15 --lead 1 --settle

Weather comes from historical-forecast-api `previous_dayN`, which is the
forecast as actually issued N days before kickoff. Totals come from the odds
snapshot cache, so this costs zero credits.

Requires issued-forecast coverage, i.e. kickoff on or after 2024-01-18.
"""

from __future__ import annotations

import argparse
import json
import glob
import os
import sys

import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_ingest.weather import (INDOOR_ROOFS, DEPLOY_THRESHOLD, ISSUED_FORECAST_START,
                                 fetch_issued_forecasts, expected_true_wind, wind_at_kickoff,
                                 coverage_check)
from data_ingest.parse import snapshot_to_frame
from models.wind_totals import select_bets

DEFECTIVE_BOOKS = {"betanysports", "betsson", "nordicbet", "tipico_de"}


def load_week(season: int, week: int) -> pd.DataFrame:
    g = pd.read_csv("data/games.csv")
    g = g[(g.season == season) & (g.week == week)].copy()
    dt = pd.to_datetime(g.gameday + " " + g.gametime, errors="coerce")
    g["kick_utc"] = (dt.dt.tz_localize(ZoneInfo("America/New_York"), ambiguous=True,
                                       nonexistent="shift_forward").dt.tz_convert("UTC"))
    g["matchup"] = g.away_team + " @ " + g.home_team
    return g


def issued_wind(g: pd.DataFrame, lead: int) -> pd.DataFrame:
    outdoor = g[~g.roof.isin(INDOOR_ROOFS)].copy()
    if outdoor.empty:
        return outdoor
    cov = coverage_check(g)
    if cov["missing_coords"]:
        raise SystemExit(f"FATAL: missing coordinates for {cov['missing_coords']}")
    lo = outdoor.kick_utc.min().strftime("%Y-%m-%d")
    hi = (outdoor.kick_utc.max() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    if hi < ISSUED_FORECAST_START:
        raise SystemExit(f"issued forecasts begin {ISSUED_FORECAST_START}; this week ends {hi}")
    frames = [fetch_issued_forecasts(sid, lo, hi, leads=(lead,))
              for sid in sorted(outdoor.stadium_id.unique())]
    hourly = pd.concat(frames, ignore_index=True)
    col = f"fc_d{lead}"
    outdoor["forecast_wind"] = wind_at_kickoff(hourly, outdoor, col).reindex(outdoor.game_id).values
    outdoor["truth_wind"] = wind_at_kickoff(hourly, outdoor, "om_analysis").reindex(outdoor.game_id).values
    outdoor["exp_true_wind"] = expected_true_wind(outdoor.forecast_wind, lead).values
    outdoor["lead_days"] = float(lead)
    return outdoor


def cached_totals(g: pd.DataFrame, lead: int) -> pd.DataFrame:
    """Best under quote from the snapshot closest to `lead` days before kickoff."""
    target = g.kick_utc.min() - pd.Timedelta(days=lead)
    # Rank candidates by timestamp FIRST and only parse the ones we might use.
    # Parsing all ~2,600 snapshots to find one takes minutes; this takes seconds.
    cands = []
    for f in glob.glob("data/odds_cache/*.json"):
        try:
            payload = json.load(open(f))
        except (json.JSONDecodeError, OSError):
            continue
        ts = payload.get("timestamp")
        if not ts:
            continue
        cands.append((abs((pd.Timestamp(ts) - target).total_seconds()), f, payload))
    cands.sort(key=lambda x: x[0])

    best, best_gap = None, None
    for gap, f, payload in cands[:40]:
        d = snapshot_to_frame(payload, os.path.basename(f))
        if d.empty or not (d.market == "totals").any():
            continue
        best, best_gap = d, gap
        break
    g = g.copy()
    for c in ("best_book", "best_total", "best_under_px", "best_over_px", "n_books"):
        g[c] = pd.NA
    if best is None:
        print("WARNING: no cached totals snapshot found for this week", file=sys.stderr)
        return g
    print(f"using cached totals snapshot {best_gap/3600:.1f}h from the {lead}-day mark",
          file=sys.stderr)
    d = best[(best.market == "totals") & (~best.book.isin(DEFECTIVE_BOOKS))]
    un = d[d.side == "Under"].dropna(subset=["point", "price"])
    ov = d[d.side == "Over"].dropna(subset=["point", "price"])
    for i, row in g.iterrows():
        c = un[(un.home == row.home_team) & (un.away == row.away_team)]
        if c.empty:
            continue
        c = c.sort_values(["point", "price"], ascending=[False, False])
        top = c.iloc[0]
        opp = ov[(ov.home == row.home_team) & (ov.away == row.away_team) &
                 (ov.book == top.book) & (ov.point == top.point)]
        g.at[i, "best_book"] = top.book
        g.at[i, "best_total"] = float(top.point)
        g.at[i, "best_under_px"] = int(top.price)
        g.at[i, "best_over_px"] = int(opp.iloc[0].price) if len(opp) else pd.NA
        g.at[i, "n_books"] = int(c.book.nunique())
    return g


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--lead", type=int, default=3, choices=[1, 2, 3, 4, 5, 6, 7])
    ap.add_argument("--threshold", type=float, default=DEPLOY_THRESHOLD)
    ap.add_argument("--settle", action="store_true", help="show realised results")
    a = ap.parse_args()

    g = load_week(a.season, a.week)
    if g.empty:
        raise SystemExit("no such week in data/games.csv")
    w = issued_wind(g, a.lead)
    if w.empty:
        print("no outdoor games this week")
        return 0

    print(f"\n--- {a.season} week {a.week}, forecast as issued {a.lead} day(s) out ---")
    cols = ["matchup", "stadium_id", "forecast_wind", "exp_true_wind", "truth_wind"]
    if "wind" in w:
        cols.append("wind")
    print(w[cols].sort_values("forecast_wind", ascending=False)
          .to_string(index=False, float_format=lambda x: f"{x:.1f}"))

    w = cached_totals(w, a.lead)
    bets = select_bets(w, threshold=a.threshold)
    if bets.empty:
        n = int((w.forecast_wind >= a.threshold).sum())
        print(f"\nno qualifying bets ({n} game(s) cleared the wind threshold but "
              f"failed the edge or pricing filter)")
        return 0

    print("\n=== card ===")
    print(bets[["matchup", "exp_true_wind", "total_line", "book", "price",
                "model_prob", "market_prob", "edge", "ev_pct", "stake_pct"]]
          .to_string(index=False))

    if a.settle:
        res = g.set_index("game_id")[["total"]].rename(columns={"total": "final_total"})
        b = bets.join(res, on="game_id")
        # settle against the line we actually took, not the consensus close
        b["result"] = np.select([b.final_total < b.total_line, b.final_total == b.total_line],
                                ["UNDER", "PUSH"], "OVER")
        # Return per unit STAKED. `units` is the stake size from select_bets, so
        # do not overwrite it here: flat P&L and staked P&L are different numbers
        # and the older weeks in this document are quoted flat.
        b["flat_pnl"] = np.select(
            [b.result == "UNDER", b.result == "PUSH"],
            [np.where(b.price > 0, b.price / 100, 100 / -b.price), 0.0], -1.0)
        b["staked_pnl"] = (b.flat_pnl * b.units).round(3)
        print("\n=== settled ===")
        print(b[["matchup", "total_line", "final_total", "result", "units",
                 "flat_pnl", "staked_pnl"]].to_string(index=False))
        print(f"\nweek total: {b.flat_pnl.sum():+.2f} units flat, "
              f"{b.staked_pnl.sum():+.2f} units as staked, on {len(b)} bet(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
