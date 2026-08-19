#!/usr/bin/env python3
"""
Daily opener-spread bet card — the live deployment of the sharp-vs-soft rule
validated in scripts/backtest_opener.py.

THE RULE (unchanged from the corrected backtest):
  In the T-7 to T-2 day window (Pinnacle posts ~T-6.5, soft books still carry
  stale early numbers), wherever a soft book's HOME spread deviates from
  Pinnacle's by >= 1.0 points, bet the side Pinnacle favours AT the soft
  book's stale number. One bet per game, taken at the FIRST qualifying moment
  — this card runs daily, so "first qualifying moment" is realized at daily
  resolution (the number corrects only ~4.8%/day, so daily granularity loses
  little). At the first qualifying run, the largest-deviation qualifying book
  is taken (the backtest's "first" variant: first snapshot, max |dev| within
  it). LATER RUNS NEVER REPRICE A TAKEN BET — the edge IS staleness; waiting
  destroys it. The platform publisher enforces the lock (insert-once).

Evidence (2023-2025, 29 clean books, priced at actually-quoted juice):
  |dev| >= 1.0 : n=593, ATS 58.18% vs 52.40% expected from the line advantage
  alone — +5.78pp excess [95% CI +1.8, +9.6]; ROI +6.98% [-0.6, +14.5].
  The ROI interval grazes zero: this model is live as a PAPER-FIRST track,
  same gate as every platform model.

    python scripts/daily_opener_card.py            # scan the T-2..T-7 window
    python scripts/daily_opener_card.py --threshold 1.5

Cost: 2 credits per run (regions=us,eu x markets=spreads — eu is required,
that's where Pinnacle lives). Zero cost when no games are in the window.
Output: printed card + data/cards/opener_card_YYYY-MM-DD.csv.
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


def american_to_prob(px: float) -> float:
    # Inlined from models.wind_totals so this module imports cleanly outside
    # the nfl/ package too (the platform repo has its own `models` package,
    # which would shadow ours when both roots are on sys.path — e.g. tests).
    return 100.0 / (px + 100.0) if px > 0 else -px / (-px + 100.0)

# Same screen as everywhere else in this package (scripts/screen_books.py).
DEFECTIVE_BOOKS = {"betanysports", "betsson", "nordicbet", "tipico_de"}
# Exchange prices are gross of ~2% commission — the platform's picks table has
# no way to express that, so the exchange is not bettable here (it was 1 of the
# 29 clean books in the backtest; excluding it is the conservative direction).
EXCHANGES = {"matchbook"}
REFERENCE = "pinnacle"

DEPLOY_THRESHOLD = 1.0   # |soft_home_line - pinnacle_home_line|, points
LEAD_LO_DAYS = 2.0       # the validated window: T-7 to T-2
LEAD_HI_DAYS = 7.0
# Pooled validated ATS at the deployment threshold (first-variant, one bet per
# game). Used as the flat per-bet win probability — there is no per-bet
# calibration curve (per-book thresholds are non-monotonic; see the doc).
MODEL_PROB = 0.5818


def load_window_schedule(lo_days: float = LEAD_LO_DAYS,
                         hi_days: float = LEAD_HI_DAYS) -> pd.DataFrame:
    g = pd.read_csv("data/games.csv")
    dt = pd.to_datetime(g.gameday + " " + g.gametime, errors="coerce")
    g["kick_utc"] = (dt.dt.tz_localize(ZoneInfo("America/New_York"), ambiguous=True,
                                       nonexistent="shift_forward").dt.tz_convert("UTC"))
    now = pd.Timestamp.now(tz="UTC")
    g = g[(g.kick_utc > now + pd.Timedelta(days=lo_days))
          & (g.kick_utc <= now + pd.Timedelta(days=hi_days))].copy()
    g["matchup"] = g.away_team + " @ " + g.home_team
    g["lead_days"] = (g.kick_utc - now).dt.total_seconds() / 86400
    return g


def select_opener_bets(frame: pd.DataFrame, sched: pd.DataFrame,
                       threshold: float = DEPLOY_THRESHOLD) -> pd.DataFrame:
    """
    Pure selection: long snapshot frame (snapshot_to_frame shape: one row per
    event x book x market x side with home/away sides, price, point) + the
    window schedule -> one bet row per qualifying game.

    Mirrors backtest_opener's "first" variant at this snapshot: qualifying
    books ranked by |dev| descending, top one taken per game.
    """
    sp = frame[(frame.market == "spreads")
               & (~frame.book.isin(DEFECTIVE_BOOKS | EXCHANGES))].copy()
    if sp.empty:
        return pd.DataFrame()

    home = sp[sp.side == "home"][["event_id", "home", "away", "book", "price", "point"]]
    away = sp[sp.side == "away"][["event_id", "book", "price"]].rename(
        columns={"price": "px_away"})
    piv = home.rename(columns={"price": "px_home"}).merge(
        away, on=["event_id", "book"], how="inner")

    pin = (piv[piv.book == REFERENCE]
           .groupby(["home", "away"], as_index=False)
           .point.median().rename(columns={"point": "pin_home_line"}))
    if pin.empty:
        return pd.DataFrame()  # Pinnacle not live yet — nothing is decidable

    soft = piv[piv.book != REFERENCE].merge(pin, on=["home", "away"], how="inner")
    soft["dev"] = soft.point - soft.pin_home_line
    soft = soft[soft.dev.abs() >= threshold]
    if soft.empty:
        return pd.DataFrame()

    rows = []
    for r in soft.sort_values("dev", key=lambda s: s.abs(), ascending=False).itertuples():
        game = sched[(sched.home_team == r.home) & (sched.away_team == r.away)]
        if game.empty:
            continue
        game = game.iloc[0]
        bet_home = r.dev > 0            # soft gives home more points than the sharp line
        price = r.px_home if bet_home else r.px_away
        if pd.isna(price):
            continue
        side_line = r.point if bet_home else -r.point
        market_prob = american_to_prob(float(price))
        rows.append({
            "game_id": game.game_id,
            "matchup": game.matchup,
            "kick_utc": str(game.kick_utc),
            "lead_days": round(float(game.lead_days), 2),
            "side": "home" if bet_home else "away",
            "bet_team": r.home if bet_home else r.away,
            "book": r.book,
            "price": int(price),
            "side_line": float(side_line),
            "soft_home_line": float(r.point),
            "pin_home_line": float(r.pin_home_line),
            "dev": round(float(r.dev), 2),
            "model_prob": MODEL_PROB,
            "market_prob": round(float(market_prob), 4),
            "edge": round(MODEL_PROB - float(market_prob), 4),
        })
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    # One bet per game, largest |dev| first (the "first" variant's tie-break).
    return (out.sort_values("dev", key=lambda s: s.abs(), ascending=False)
            .groupby("game_id", as_index=False).first())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=DEPLOY_THRESHOLD)
    ap.add_argument("--regions", default="us,eu",
                    help="must include eu — that's where Pinnacle lives")
    a = ap.parse_args()

    sched = load_window_schedule()
    if sched.empty:
        print("No games in the T-2..T-7 day window.")
        return 0

    key = os.environ.get("THE_ODDS_API_KEY")
    if not key:
        # Scheduled runs must not go red weekly on a missing key: the opener
        # has no weather-only dry-run side — without odds there is no card.
        print("THE_ODDS_API_KEY not set — opener card needs live odds; skipping.")
        return 0

    from data_ingest.odds_api import OddsAPIClient, ledger_status
    from data_ingest.parse import snapshot_to_frame

    client = OddsAPIClient(key, quota_guard=200)
    res = client.live_odds(regions=a.regions, markets="spreads")
    print(f"odds pulled, cost {res.cost} credit(s), ledger now {ledger_status()}",
          file=sys.stderr)
    frame = snapshot_to_frame(res.payload, "live")

    # Dump DraftKings' spreads for every upcoming game (wider than the card's
    # own T-2..T-7 window — this daily dump is what carries snapshot coverage
    # through game day for already-locked opener picks, so the app can show
    # how far the market has moved off the locked number). Enrichment only —
    # never sink the card. Runs BEFORE the no-qualifying-bets early exit.
    try:
        from data_ingest.line_snapshots import dump_dk_lines
        dump_dk_lines(frame, "spreads")
    except Exception as exc:
        print(f"WARNING: line snapshot dump failed: {exc}", file=sys.stderr)

    bets = select_opener_bets(frame, sched, threshold=a.threshold)
    if bets is None or len(bets) == 0:
        print(f"No qualifying opener bets at |dev| >= {a.threshold}.")
        return 0

    print(f"\n=== OPENER SPREAD CARD  {datetime.now(timezone.utc):%Y-%m-%d %H:%MZ} ===")
    cols = ["matchup", "kick_utc", "bet_team", "side_line", "book", "price",
            "dev", "pin_home_line", "model_prob", "edge"]
    print(bets[cols].to_string(index=False))
    print(f"\n{len(bets)} bet(s). NOTE: already-taken games are locked by the "
          "publisher — a game reappearing here does NOT re-price its bet.")

    out = Path("data/cards"); out.mkdir(parents=True, exist_ok=True)
    p = out / f"opener_card_{datetime.now(timezone.utc):%Y-%m-%d}.csv"
    bets.to_csv(p, index=False)
    print(f"\nwritten: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
