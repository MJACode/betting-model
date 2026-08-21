#!/usr/bin/env python3
"""
Wind-under poller: watch the board, wait for Pinnacle, fire once per game.

WHAT IT DOES
------------
Polls the odds feed on a two-speed cadence, holds fire on a game until Pinnacle
is actually quoting a total on it, and the first time a game clears the frozen
rule with Pinnacle up, prints an alert and writes the bet to
`data/cards/fired_bets.csv`. Each game fires at most once, ever, across restarts.

    export THE_ODDS_API_KEY=...
    python scripts/wind_poller.py                    # run the loop
    python scripts/wind_poller.py --once             # one tick, for Task Scheduler
    python scripts/wind_poller.py --dry-run          # weather + cadence, 0 credits

IT DOES NOT PLACE BETS. It alerts; a human places. There is no path in this
repo to a sportsbook account and there should not be one.

CADENCE
-------
  * every 60 min while every watched game is more than 3 hours from kickoff
  * every 10 min once any watched game is inside 3 hours
  * horizon 10 days
A tick returns the whole board in one call, so cadence is global rather than
per game; the loop shortens its sleep so it never oversleeps the moment the
next game crosses into the fast window.

THE PINNACLE GATE
-----------------
Pinnacle sits in the Odds API `eu` region, so the default is `--regions us,eu`
at 2 credits a tick. Before Pinnacle is up, the "best" total on the board is
whichever soft book posted first, and this project has already been burned once
by selecting on extreme quotes: four books transpose home and away, and a defect
in 0.4% of rows supplied 15% of selected bets. A live Pinnacle total is the
cheapest available check that a number is a real number.

Pinnacle gates. It does not price. Selection and the de-vig still run off the
book actually being bet, exactly as validated. The Pinnacle de-vig is carried on
the card as a diagnostic, and `--min-edge-vs-pinnacle` can require it as well,
which is a stricter rule than the one that was backtested. Off by default.

COST
----
2 credits a tick at us,eu. A full week of hourly polling plus fast windows on
five kickoff clusters is roughly 500-700 credits. `--max-credits` stops the run
before it can eat the quota, and the ledger guard in OddsAPIClient still applies.

WHAT FIRING EARLY COSTS
-----------------------
The edge decays with forecast lead. Measured under rate at threshold 11:
57.41% at lead 1, 56.70% at lead 3, 55.82% at lead 5, 55.51% at 6, 54.89% at 7.
Firing on the FIRST qualifying quote therefore trades win rate for the number,
which is the opposite of the runbook's advice to bet late. That is a choice
about which risk you would rather carry, line risk or forecast risk, and it is
a defensible one - but it is not free, and the stake has to reflect it. It does:
sizing is Kelly-proportional off the lead-specific probability, so a lead-7 fire
is 0.58 units where a lead-3 fire is 1.00. Past lead 7 there is no measured
forecast error at all, `stake_units` returns zero, and the poller reports the
game as watch-only instead of betting it.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_ingest.weather import DEPLOY_THRESHOLD
from models.wind_totals import (MAX_CALIBRATED_LEAD, UNIT_PCT, devig_two_way,
                                select_bets)
from weekly_wind_card import (DEFECTIVE_BOOKS, EXCHANGES, attach_forecast,
                              load_schedule)

PINNACLE = "pinnacle"
HORIZON_DAYS = 10
SLOW_SECONDS = 3600
FAST_SECONDS = 600
FAST_WINDOW_HOURS = 3

CARDS = Path("data/cards")
STATE_PATH = CARDS / "poll_state.json"
FIRED_PATH = CARDS / "fired_bets.csv"
LOG_PATH = CARDS / "poll_log.csv"


# --------------------------------------------------------------------------- #
# state

def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            print("WARNING: unreadable poll state, starting fresh", file=sys.stderr)
    return {"fired": {}, "first_pinnacle": {}, "ticks": 0, "credits": 0}


def save_state(state: dict) -> None:
    CARDS.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, default=str))
    os.replace(tmp, STATE_PATH)


def append_csv(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([row])
    df.to_csv(path, mode="a", header=not path.exists(), index=False)


# --------------------------------------------------------------------------- #
# odds

def attach_odds(g: pd.DataFrame, regions: str, quota_guard: int) -> tuple[pd.DataFrame, int]:
    """
    Best available UNDER quote across the clean books, plus Pinnacle's own quote.

    Same selection as the weekly card - highest total first, then best price at
    that total, defective books removed - with the Pinnacle columns added so the
    gate has something to test.
    """
    from data_ingest.odds_api import OddsAPIClient
    from data_ingest.parse import snapshot_to_frame

    g = g.copy()
    for c in ("best_book", "best_total", "best_under_px", "best_over_px", "n_books",
              "pin_total", "pin_under_px", "pin_over_px", "pin_prob"):
        g[c] = pd.NA

    key = os.environ.get("THE_ODDS_API_KEY")
    if not key:
        raise SystemExit("THE_ODDS_API_KEY is not set. Use --dry-run for the weather side only.")

    client = OddsAPIClient(key, quota_guard=quota_guard)
    res = client.live_odds(regions=regions, markets="totals")

    d = snapshot_to_frame(res.payload, "live")
    d = d[(d.market == "totals")  (~d.book.isin(DEFECTIVE_BOOKS))]
    if d.empty:
        print("WARNING: no totals returned by the odds feed", file=sys.stderr)
        return g, res.cost

    unders = d[d.side == "Under"].dropna(subset=["point", "price"])
    overs = d[d.side == "Over"].dropna(subset=["point", "price"])

    for i, row in g.iterrows():
        cand = unders[(unders.home == row.home_team)  (unders.away == row.away_team)]
        if cand.empty:
            continue
        top = cand.sort_values(["point", "price"], ascending=[False, False]).iloc[0]
        opp = overs[(overs.home == row.home_team)  (overs.away == row.away_team) 
                    (overs.book == top.book)  (overs.point == top.point)]
        g.at[i, "best_book"] = top.book
        g.at[i, "best_total"] = float(top.point)
        g.at[i, "best_under_px"] = int(top.price)
        g.at[i, "best_over_px"] = int(opp.iloc[0].price) if len(opp) else pd.NA
        g.at[i, "n_books"] = int(cand.book.nunique())

    return g, res.cost


# --------------------------------------------------------------------------- #
# cadence

def next_wait(watched: pd.DataFrame, now: pd.Timestamp) -> tuple[int, str]:
    """Seconds until the next tick, and why."""
    if watched.empty:
        return SLOW_SECONDS, "nothing on the watchlist"
    hrs = (watched.kick_utc - now).dt.total_seconds() / 3600
    hrs = hrs[hrs > 0]
    if hrs.empty:
        return SLOW_SECONDS, "no future kickoffs on the watchlist"
    if hrs.min() <= FAST_WINDOW_HOURS:
        return FAST_SECONDS, f"{(hrs <= FAST_WINDOW_HOURS).sum()} game(s) inside 3h"
    until_fast = int((hrs.min() - FAST_WINDOW_HOURS) * 3600)
    if until_fast < SLOW_SECONDS:
        return max(60, until_fast), f"next game crosses 3h in {until_fast/60:.0f} min"
    return SLOW_SECONDS, f"nearest kickoff in {hrs.min():.1f}h"


# --------------------------------------------------------------------------- #
# firing

def alert_text(bet: dict, row: pd.Series, bankroll: float) -> str:
    stake = bet["stake_pct"] / 100 * bankroll
    lines = [
        "=" * 68,
        f"FIRE  {bet['matchup']}   UNDER {bet['total_line']}  {bet['price']:+d}  @ {bet['book']}",
        "=" * 68,
        f"  kickoff        {bet['kick_utc']}  (lead {bet['lead_days']:.2f} days)",
        f"  forecast wind  {bet['forecast_wind']:.1f} mph   E[true] {bet['exp_true_wind']:.1f} mph",
        f"  model P(under) {bet['model_prob']:.4f}   market {bet['market_prob']:.4f}   "
        f"edge {bet['edge']*100:+.2f} pp",
        f"  stake          {bet['units']:.2f} units = {bet['stake_pct']:.3f}% "
        f"= {stake:,.2f} at a {bankroll:,.0f} bankroll",
        f"  EV             {bet['ev_pct']:+.2f}% of stake",
    ]
    if pd.notna(row.get("pin_total")):
        lines.append(f"  pinnacle       total {row.pin_total} under {int(row.pin_under_px):+d}"
                     + (f"  de-vig {row.pin_prob:.4f}  edge vs pin "
                        f"{(bet['model_prob'] - row.pin_prob)*100:+.2f} pp"
                        if pd.notna(row.get("pin_prob")) else ""))
    if bet["book"] in EXCHANGES:
        lines.append("  NOTE: exchange price, gross of ~2% commission")
    if not bet["calibrated_lead"]:
        lines.append("  WARNING: lead beyond the calibrated range")
    lines.append("  This is an alert. Place it yourself, or do not.")
    lines.append("=" * 68)
    return "\n".join(lines)


def notify(cmd: str | None, text: str) -> None:
    if not cmd:
        return
    try:
        subprocess.run(cmd, shell=True, input=text.encode(), timeout=30, check=False)
    except Exception as exc:                                   # noqa: BLE001
        print(f"WARNING: notify command failed: {exc}", file=sys.stderr)


# --------------------------------------------------------------------------- #

def tick(a, state: dict) -> tuple[int, str]:
    now = pd.Timestamp.now(tz="UTC")
    stamp = f"{now:%Y-%m-%d %H:%MZ}"

    sched = load_schedule(a.days)
    if sched.empty:
        print(f"[{stamp}] no games in the next {a.days} days")
        return SLOW_SECONDS, "empty schedule"

    sched = sched[~sched.game_id.isin(state["fired"])]
    g = attach_forecast(sched, days=a.days + 1) if len(sched) else sched
    if g.empty:
        print(f"[{stamp}] no unfired outdoor games in window")
        return next_wait(sched, now)

    watch = g[g.forecast_wind >= a.threshold - a.buffer].copy()
    wait, why = next_wait(watch, now)

    if watch.empty:
        top = g.forecast_wind.max()
        print(f"[{stamp}] {len(g)} outdoor game(s), none within {a.buffer} mph of the "
              f"threshold (max forecast {top:.1f}). No odds call. Next in {wait//60} min.")
        append_csv(LOG_PATH, dict(ts=stamp, watched=0, pinnacle=0, qualifying=0,
                                  fired=0, credits=0, wait_s=wait, reason=why))
        return wait, why

    if a.dry_run:
        print(f"[{stamp}] DRY RUN. {len(watch)} watched game(s):")
        print(watch[["matchup", "lead_days", "forecast_wind", "exp_true_wind"]]
              .sort_values("forecast_wind", ascending=False)
              .to_string(index=False, float_format=lambda x: f"{x:.1f}"))
        print(f"  next tick in {wait//60} min ({why})")
        return wait, why

    tick_cost = len(a.regions.split(","))          # 1 credit per region, totals only
    if state["credits"] + tick_cost > a.max_credits:
        raise SystemExit(f"credit budget exhausted: {state['credits']} spent of "
                         f"{a.max_credits} allowed for this run")

    priced, cost = attach_odds(watch, a.regions, a.quota_guard)
    state["credits"] += cost
    state["ticks"] += 1

    has_pin = priced.pin_total.notna()
    for _, r in priced[has_pin].iterrows():
        state["first_pinnacle"].setdefault(r.game_id, stamp)

    gated = priced[has_pin] if a.require_pinnacle else priced
    bets = select_bets(gated, threshold=a.threshold, min_edge=a.min_edge,
                       bankroll=a.bankroll) if len(gated) else pd.DataFrame()

    n_fired = 0
    for _, b in bets.iterrows():
        bet = b.to_dict()
        if bet["game_id"] in state["fired"]:
            continue
        row = priced[priced.game_id == bet["game_id"]].iloc[0]
        if bet["units"] <= 0:
            continue                       # lead beyond calibration, watch only
        if a.min_edge_vs_pinnacle is not None:
            if pd.isna(row.get("pin_prob")) or \
                bet["model_prob"] - row.pin_prob < a.min_edge_vs_pinnacle:
                continue
        text = alert_text(bet, row, a.bankroll)
        print("\n" + text + "\n")
        notify(a.notify_cmd, text)
        rec = dict(bet)
        rec.update(fired_at=stamp, pin_total=row.get("pin_total"),
                   pin_under_px=row.get("pin_under_px"), pin_prob=row.get("pin_prob"),
                   first_pinnacle=state["first_pinnacle"].get(bet["game_id"]),
                   n_books=row.get("n_books"))
        append_csv(FIRED_PATH, rec)
        state["fired"][bet["game_id"]] = rec
        n_fired += 1

    n_pin = int(has_pin.sum())
    waiting = priced[~has_pin]
    print(f"[{stamp}] watched {len(priced)}, pinnacle up on {n_pin}, "
          f"qualifying {len(bets)}, fired {n_fired}, cost {cost} "
          f"(run total {state['credits']}). Next in {wait//60} min ({why}).")
    if len(waiting):
        print("  waiting on pinnacle: " + ", ".join(
            f"{r.matchup} ({r.forecast_wind:.0f} mph, {r.lead_days:.1f}d)"
            for _, r in waiting.iterrows()))
    if len(bets) and not n_fired:
        print("  qualifying but not fired: already fired, uncalibrated lead, "
              "or blocked by --min-edge-vs-pinnacle")

    append_csv(LOG_PATH, dict(ts=stamp, watched=len(priced), pinnacle=n_pin,
                              qualifying=len(bets), fired=n_fired, credits=cost,
                              wait_s=wait, reason=why))
    save_state(state)
    return wait, why


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=HORIZON_DAYS, help="look-ahead horizon")
    ap.add_argument("--threshold", type=float, default=DEPLOY_THRESHOLD)
    ap.add_argument("--buffer", type=float, default=3.0,
                    help="mph below the threshold still worth pricing; a forecast "
                         "this far out moves, and an odds call covers the whole board")
    ap.add_argument("--regions", default="us,eu",
                    help="eu is where pinnacle lives; dropping it disables the gate")
    ap.add_argument("--min-edge", type=float, default=0.03)
    ap.add_argument("--min-edge-vs-pinnacle", type=float, default=None,
                    help="also require this edge against pinnacle's de-vig. STRICTER "
                         "than the backtested rule; leave unset to reproduce it")
    ap.add_argument("--bankroll", type=float, default=10000.0)
    ap.add_argument("--no-require-pinnacle", dest="require_pinnacle",
                    action="store_false", help="fire without waiting for pinnacle")
    ap.add_argument("--once", action="store_true", help="one tick and exit")
    ap.add_argument("--dry-run", action="store_true", help="no odds call, no credits")
    ap.add_argument("--max-credits", type=int, default=1500, help="budget for this run")
    ap.add_argument("--quota-guard", type=int, default=200)
    ap.add_argument("--notify-cmd", default=os.environ.get("WIND_NOTIFY_CMD"),
                    help="shell command receiving the alert on stdin")
    ap.add_argument("--reset", action="store_true",
                    help="clear the fired-once state before starting")
    a = ap.parse_args()

    if a.require_pinnacle and "eu" not in a.regions.split(","):
        raise SystemExit("pinnacle is in the eu region. Add it to --regions or pass "
                         "--no-require-pinnacle.")

    state = {"fired": {}, "first_pinnacle": {}, "ticks": 0, "credits": 0} if a.reset \
        else load_state()
    if a.reset:
        save_state(state)

    print(f"wind poller up. horizon {a.days}d, threshold {a.threshold} mph, "
          f"regions {a.regions}, pinnacle gate "
          f"{'ON' if a.require_pinnacle else 'OFF'}, "
          f"1 unit = {UNIT_PCT*100:.2f}% = {UNIT_PCT*a.bankroll:,.0f}")
    print(f"already fired: {len(state['fired'])} game(s). "
          f"Leads beyond {MAX_CALIBRATED_LEAD} days are watch-only.")

    while True:
        try:
            wait, _ = tick(a, state)
        except SystemExit:
            raise
        except Exception as exc:                               # noqa: BLE001
            # A poller that dies on one bad tick is worse than useless: it is
            # silently useless. Log, back off, keep going.
            print(f"ERROR on tick: {exc}", file=sys.stderr)
            save_state(state)
            wait = FAST_SECONDS
        if a.once:
            return 0
        time.sleep(wait)


if __name__ == "__main__":
    raise SystemExit(main())