#!/usr/bin/env python3
"""
Weekly wind-totals bet card.

Run this any time from Thursday up to kickoff. Later is better: forecast skill
improves and the edge is against the closing number anyway.

    export THE_ODDS_API_KEY=...
    python scripts/weekly_wind_card.py                    # next 7 days
    python scripts/weekly_wind_card.py --days 3           # this weekend only
    python scripts/weekly_wind_card.py --threshold 12     # tighter
    python scripts/weekly_wind_card.py --dry-run          # no odds call, no credits

Cost: 1 credit per run at regions=us, markets=totals. Add regions to shop wider
at 1 credit each.

Output: data/cards/wind_card_YYYY-MM-DD.csv plus a printed card.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_ingest.weather import (STADIUM_COORDS, INDOOR_ROOFS, DEPLOY_THRESHOLD,
                                 fetch_live_forecast, expected_true_wind, wind_at_kickoff,
                                 coverage_check)
from models.wind_totals import select_bets, UNIT_PCT, MAX_CALIBRATED_LEAD

# Books carrying home/away sign flips in the Odds API feed. Screened across all
# 40 books on 1.4M quotes; see scripts/screen_books.py. Excluded everywhere.
DEFECTIVE_BOOKS = {"betanysports", "betsson", "nordicbet", "tipico_de"}

# Exchange: quoted price is gross of commission, so treat separately if used.
EXCHANGES = {"matchbook"}

TEAM_MAP_REV = None  # filled from parse.TEAM_MAP


def load_schedule(days: int) -> pd.DataFrame:
    g = pd.read_csv("data/games.csv")
    dt = pd.to_datetime(g.gameday + " " + g.gametime, errors="coerce")
    g["kick_utc"] = (dt.dt.tz_localize(ZoneInfo("America/New_York"), ambiguous=True,
                                       nonexistent="shift_forward").dt.tz_convert("UTC"))
    now = pd.Timestamp.now(tz="UTC")
    g = g[(g.kick_utc > now) & (g.kick_utc <= now + pd.Timedelta(days=days))].copy()
    g["matchup"] = g.away_team + " @ " + g.home_team
    g["lead_days"] = (g.kick_utc - now).dt.total_seconds() / 86400
    return g


def attach_forecast(g: pd.DataFrame, days: int = 9) -> pd.DataFrame:
    cov = coverage_check(g)
    if cov["missing_coords"]:
        raise SystemExit(f"FATAL: no coordinates for stadium(s) {cov['missing_coords']}. "
                         "Add them to STADIUM_COORDS before betting this slate.")
    outdoor = g[~g.roof.isin(INDOOR_ROOFS)].copy()
    if outdoor.empty:
        return outdoor
    frames = []
    for sid in sorted(outdoor.stadium_id.unique()):
        frames.append(fetch_live_forecast(sid, days=days))
    hourly = pd.concat(frames, ignore_index=True)
    outdoor["forecast_wind"] = wind_at_kickoff(hourly, outdoor, "wind").reindex(outdoor.game_id).values
    outdoor["gust"] = wind_at_kickoff(hourly, outdoor, "gust").reindex(outdoor.game_id).values
    outdoor["temp"] = wind_at_kickoff(hourly, outdoor, "temp").reindex(outdoor.game_id).values
    # E[true wind | forecast] depends on lead, and lead differs per game on a
    # slate that spans Thursday to Monday, so apply it per game.
    outdoor["exp_true_wind"] = [
        float(expected_true_wind([w], int(round(ld))).iloc[0])
        for w, ld in zip(outdoor.forecast_wind, outdoor.lead_days)
    ]
    return outdoor


def attach_odds(g: pd.DataFrame, regions: str, dry_run: bool) -> pd.DataFrame:
    """Best available UNDER price at the best (highest) total, defective books removed."""
    g = g.copy()
    for c in ("best_book", "best_total", "best_under_px", "best_over_px", "n_books"):
        g[c] = pd.NA
    if dry_run:
        return g

    from data_ingest.odds_api import OddsAPIClient, ledger_status
    from data_ingest.parse import snapshot_to_frame

    key = os.environ.get("THE_ODDS_API_KEY")
    if not key:
        raise SystemExit("THE_ODDS_API_KEY is not set. Use --dry-run to see the weather side only.")

    client = OddsAPIClient(key, quota_guard=200)
    res = client.live_odds(regions=regions, markets="totals")
    print(f"odds pulled, cost {res.cost} credit(s), ledger now {ledger_status()}", file=sys.stderr)

    d = snapshot_to_frame(res.payload, "live")
    d = d[(d.market == "totals") & (~d.book.isin(DEFECTIVE_BOOKS))]
    if d.empty:
        print("WARNING: no totals returned by the odds feed", file=sys.stderr)
        return g

    d["commence_time"] = pd.to_datetime(d.commence_time, format="ISO8601", utc=True)
    unders = d[d.side == "Under"].dropna(subset=["point", "price"])
    overs = d[d.side == "Over"].dropna(subset=["point", "price"])

    for i, row in g.iterrows():
        cand = unders[(unders.home == row.home_team) & (unders.away == row.away_team)]
        if cand.empty:
            continue
        # Best under = highest total first, then best price at that total.
        cand = cand.sort_values(["point", "price"], ascending=[False, False])
        top = cand.iloc[0]
        opp = overs[(overs.home == row.home_team) & (overs.away == row.away_team) &
                    (overs.book == top.book) & (overs.point == top.point)]
        g.at[i, "best_book"] = top.book
        g.at[i, "best_total"] = float(top.point)
        g.at[i, "best_under_px"] = int(top.price)
        g.at[i, "best_over_px"] = int(opp.iloc[0].price) if len(opp) else pd.NA
        g.at[i, "n_books"] = int(cand.book.nunique())
    return g


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7, help="look-ahead window")
    ap.add_argument("--threshold", type=float, default=DEPLOY_THRESHOLD)
    ap.add_argument("--regions", default="us")
    ap.add_argument("--bankroll", type=float, default=10000.0)
    ap.add_argument("--dry-run", action="store_true", help="skip the odds call, spend nothing")
    a = ap.parse_args()

    sched = load_schedule(a.days)
    if sched.empty:
        print("No games in window.")
        return 0
    print(f"{len(sched)} games in the next {a.days} days "
          f"({(~sched.roof.isin(INDOOR_ROOFS)).sum()} outdoor)", file=sys.stderr)

    g = attach_forecast(sched)
    if g.empty:
        print("No outdoor games in window.")
        return 0

    print("\n--- forecast wind at kickoff (all outdoor games) ---")
    show = g[["matchup", "stadium_id", "lead_days", "forecast_wind", "exp_true_wind", "gust", "temp"]]
    print(show.sort_values("forecast_wind", ascending=False).to_string(index=False,
          float_format=lambda x: f"{x:.1f}"))

    g = attach_odds(g, a.regions, a.dry_run)
    bets = select_bets(g, threshold=a.threshold, bankroll=a.bankroll)

    if bets.empty:
        print(f"\nNo qualifying bets at threshold {a.threshold} mph.")
        if a.dry_run:
            n = int((g.forecast_wind >= a.threshold).sum())
            print(f"(dry run: {n} game(s) clear the wind threshold; rerun without "
                  f"--dry-run to price them)")
        return 0

    print(f"\n=== WIND UNDER CARD  {datetime.now(timezone.utc):%Y-%m-%d %H:%MZ} ===")
    cols = ["matchup", "kick_utc", "exp_true_wind", "total_line", "book", "price",
            "model_prob", "market_prob", "edge", "ev_pct", "units", "stake_pct", "stake_amt"]
    print(bets[cols].to_string(index=False))
    print(f"\n{len(bets)} bet(s), {bets.units.sum():.2f} units total. "
          f"1 unit = {UNIT_PCT*100:.2f}% of bankroll = {UNIT_PCT*a.bankroll:,.0f}. "
          f"Sizing is derived in scripts/stake_sizing.py.")
    if (bets.units <= 0).any():
        print(f"{(bets.units <= 0).sum()} row(s) sized at ZERO: forecast lead beyond "
              f"{MAX_CALIBRATED_LEAD} days, which has no measured calibration. "
              f"Watch only, do not bet them.")
    print("Reminder: totals only. This rule does not apply to the spread.")
    if bets.book.isin(EXCHANGES).any():
        print("NOTE: an exchange is quoting best. Its price is gross of ~2% commission.")

    out = Path("data/cards"); out.mkdir(parents=True, exist_ok=True)
    p = out / f"wind_card_{datetime.now(timezone.utc):%Y-%m-%d}.csv"
    bets.to_csv(p, index=False)
    print(f"\nwritten: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
