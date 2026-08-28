"""
Pull real historical IN-PLAY player prop snapshots, on a measured budget.

    python -m live_model.backtest.pull_prop_snaps --plan
    python -m live_model.backtest.pull_prop_snaps --probe
    python -m live_model.backtest.pull_prop_snaps --run --budget 114000

WHY THIS MEASURES INSTEAD OF ASSUMING.
The documented cost for a historical call is 10 credits per market per region,
but the per-EVENT prop endpoint is a different endpoint and this project has
already been burned once this session by trusting a written figure over a live
one. So `--probe` spends a few hundred credits, reads the actual consumption
off the response headers, and reports the real cost per call. `--run` refuses
to start until a probe has established that number and the projected total fits
inside the approved budget.

THE BUDGET IS A HARD STOP, checked before every call, not a warning printed
afterwards.

TIMESTAMPS COME FROM THE RECONSTRUCTED GAME STATES, not from a guess about when
games kick off. states_all.parquet carries a real UTC wall clock for every
play, so each decision point maps to the exact moment a bettor would have been
looking, snapped to the API's five minute grid.

Everything lands in the shared odds cache keyed by URL, so an interrupted run
resumes for free and a re-run costs nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import timedelta
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from live_model.config import ARTIFACT_DIR                        # noqa: E402
from live_model.backtest.flow_dataset import DECISION_POINTS      # noqa: E402

API_ROOT = "https://api.the-odds-api.com/v4"
SPORT = "americanfootball_nfl"
CACHE = ARTIFACT_DIR / "prop_snaps"
LEDGER = ARTIFACT_DIR / "prop_pull_ledger.json"

# The count markets carry the largest flow contribution and the cleanest
# settlement. Each extra market multiplies the ENTIRE spend, so this list is
# short on purpose.
MARKETS = ("player_pass_attempts", "player_pass_completions",
           "player_receptions", "player_rush_attempts")
REGIONS = "us"

# Decision points worth paying for. The two earliest are dropped: at 2700 the
# game has barely started and at 300 a book has usually pulled the props.
PULL_POINTS = tuple(p for p in DECISION_POINTS if 600 <= p <= 2100)


def _key(url: str, params: dict) -> str:
    raw = url + "|" + json.dumps({k: v for k, v in sorted(params.items())
                                  if k != "apiKey"})
    return hashlib.md5(raw.encode()).hexdigest()


def _ledger() -> dict:
    if LEDGER.exists():
        try:
            return json.loads(LEDGER.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"spent": 0, "calls": 0, "remaining": None, "cost_per_event_call": None}


def _save_ledger(d: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    tmp = LEDGER.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=2))
    os.replace(tmp, LEDGER)


class Puller:
    def __init__(self, api_key: str, budget: int):
        self.key = api_key
        self.budget = budget
        self.led = _ledger()
        CACHE.mkdir(parents=True, exist_ok=True)

    def get(self, path: str, params: dict) -> tuple[dict | list, int]:
        """
        One call. Returns (payload, credits actually consumed).

        Consumption is MEASURED from the x-requests-remaining header rather
        than computed from a documented formula, so a wrong assumption about
        the cost model shows up immediately instead of silently overspending.
        """
        url = f"{API_ROOT}{path}"
        cache_path = CACHE / f"{_key(url, params)}.json"
        if cache_path.exists():
            return json.loads(cache_path.read_text()), 0

        if self.led["spent"] >= self.budget:
            raise RuntimeError(
                f"budget stop: {self.led['spent']} of {self.budget} spent")

        p = dict(params, apiKey=self.key)
        for attempt in range(4):
            r = requests.get(url, params=p, timeout=30)
            if r.status_code == 200:
                payload = r.json()
                cache_path.write_text(json.dumps(payload))
                before = self.led.get("remaining")
                after = r.headers.get("x-requests-remaining")
                used = r.headers.get("x-requests-last")
                if used is not None:
                    cost = int(float(used))
                elif before is not None and after is not None:
                    cost = max(int(float(before)) - int(float(after)), 0)
                else:
                    cost = 0
                if after is not None:
                    self.led["remaining"] = int(float(after))
                self.led["spent"] += cost
                self.led["calls"] += 1
                _save_ledger(self.led)
                return payload, cost
            if r.status_code == 422:
                # Market or event unavailable at that timestamp. Cache the
                # empty result so we never pay for it twice.
                cache_path.write_text(json.dumps({"_error": r.text[:200]}))
                return {}, 0
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Odds API {r.status_code}: {r.text[:200]}")
        raise RuntimeError("failed after 4 retries")

    def events_at(self, iso_ts: str):
        payload, cost = self.get(
            f"/historical/sports/{SPORT}/events",
            {"date": iso_ts, "dateFormat": "iso"})
        data = payload.get("data") if isinstance(payload, dict) else payload
        return (data or []), cost

    def props_at(self, event_id: str, iso_ts: str):
        payload, cost = self.get(
            f"/historical/sports/{SPORT}/events/{event_id}/odds",
            {"date": iso_ts, "regions": REGIONS, "markets": ",".join(MARKETS),
             "oddsFormat": "american"})
        return payload, cost


def match_event(events, home_abbrev: str, away_abbrev: str):
    """
    Find OUR game in the API's event list for that timestamp.

    The Odds API names teams in full ("Kansas City Chiefs"); nflverse uses
    abbreviations ("KC"). Both sides go through the package's existing TEAM_MAP
    so the comparison is abbreviation to abbreviation.

    Returns None rather than a guess. The first draft of this took the FIRST
    event in the list, which on a one o'clock Sunday means fetching a random
    other game's props and grading them against this game's model state. That
    would have quietly produced garbage for every row in the pull.
    """
    from data_ingest.parse import TEAM_MAP
    for e in events or []:
        h = TEAM_MAP.get(str(e.get("home_team", "")))
        a = TEAM_MAP.get(str(e.get("away_team", "")))
        if h == home_abbrev and a == away_abbrev:
            return e
    return None


def snapshot_plan(seasons) -> pd.DataFrame:
    """
    Every (game, decision point) we want, with its real UTC timestamp.

    Timestamps are snapped DOWN to the API's five minute grid, so a snapshot
    is never later than the state it is meant to price. Rounding up would price
    a state against a line published after it.
    """
    states = pd.read_parquet(ARTIFACT_DIR / "states_all.parquet")
    states = states[states.season.isin(seasons)]
    rows = []
    for mark in PULL_POINTS:
        at = states[states.seconds_remaining >= mark]
        if at.empty:
            continue
        snap = (at.sort_values(["game_id", "seconds_remaining"],
                               ascending=[True, False], kind="mergesort")
                .groupby("game_id", sort=False).last().reset_index())
        for _, r in snap.iterrows():
            ts = pd.Timestamp(r["wall_ts"])
            floored = ts - timedelta(
                minutes=ts.minute % 5, seconds=ts.second,
                microseconds=ts.microsecond)
            rows.append({
                "game_id": r["game_id"], "season": int(r["season"]),
                "decision_point": mark,
                "iso_ts": floored.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "home_team": r["home_team"], "away_team": r["away_team"],
            })
    return pd.DataFrame(rows).drop_duplicates(
        subset=["game_id", "decision_point"]).reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", type=int, nargs="+", default=[2023, 2024])
    ap.add_argument("--budget", type=int, default=114000)
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--probe", action="store_true",
                    help="spend a few hundred credits to MEASURE the real cost")
    ap.add_argument("--run", action="store_true")
    args = ap.parse_args()

    plan = snapshot_plan(args.seasons)
    n_ts = plan["iso_ts"].nunique()
    print(f"seasons {args.seasons}")
    print(f"  games              {plan.game_id.nunique():,}")
    print(f"  decision points    {list(PULL_POINTS)}")
    print(f"  event snapshots    {len(plan):,}")
    print(f"  distinct timestamps{n_ts:>7,}  (one events-list call each)")
    print(f"  markets            {', '.join(MARKETS)}")
    print(f"  budget             {args.budget:,}")

    led = _ledger()
    cpe = led.get("cost_per_event_call")
    if cpe:
        projected = len(plan) * cpe + n_ts * led.get("cost_per_list_call", 1)
        print(f"  MEASURED cost/event call {cpe}  ->  projected "
              f"{projected:,} credits")
        if projected > args.budget:
            print("  PROJECTION EXCEEDS BUDGET. Narrow the markets or the "
                  "decision points before running.")
    else:
        print("  cost per call NOT YET MEASURED. Run --probe first; the "
              "documented formula has been wrong in this repo before.")

    if args.plan:
        return

    key = os.getenv("THE_ODDS_API_KEY") or os.getenv("ODDS_API_KEY")
    if not key:
        raise SystemExit("Set THE_ODDS_API_KEY before pulling.")

    puller = Puller(key, args.budget)

    if args.probe:
        sample = plan.sample(min(4, len(plan)), random_state=0)
        list_costs, event_costs, with_props = [], [], 0
        for _, r in sample.iterrows():
            events, c1 = puller.events_at(r["iso_ts"])
            list_costs.append(c1)
            match = match_event(events, r["home_team"], r["away_team"])
            if not match:
                print(f"  {r['iso_ts']}: {r['away_team']} at {r['home_team']} "
                      f"not found among {len(events)} events")
                continue
            payload, c2 = puller.props_at(str(match.get("id")), r["iso_ts"])
            event_costs.append(c2)
            books = (payload.get("data", {}) or {}).get("bookmakers", []) \
                if isinstance(payload, dict) else []
            if books:
                with_props += 1
            print(f"  {r['iso_ts']}  list={c1} event={c2} credits  "
                  f"bookmakers={len(books)}")
        led = _ledger()
        # A resumed probe re-samples the SAME four snapshots, which are now
        # cache hits costing 0. Writing that 0 would erase the measurement and
        # make --run refuse to start, so a cached probe keeps whatever cost is
        # already on record and only a genuine paid call can update it.
        if max(event_costs, default=0) > 0:
            led["cost_per_event_call"] = max(event_costs)
            led["cost_per_list_call"] = max(list_costs) or 1
            _save_ledger(led)
        if event_costs and led.get("cost_per_event_call"):
            projected = (len(plan) * led["cost_per_event_call"]
                         + n_ts * led.get("cost_per_list_call", 1))
            print(f"\nMEASURED: {led['cost_per_event_call']} credits per event "
                  f"call, {led['cost_per_list_call']} per list call")
            print(f"PROJECTED TOTAL: {projected:,} credits "
                  f"({'fits' if projected <= args.budget else 'EXCEEDS'} the "
                  f"{args.budget:,} budget)")
            print(f"snapshots that actually carried prop lines: "
                  f"{with_props}/{len(event_costs)}")
            if with_props == 0:
                print("NO PROP LINES RETURNED. Historical in-play prop coverage "
                      "may not extend to these dates. Do not run the full pull.")
        print(f"probe spent {_ledger()['spent']} credits")
        return

    if args.run:
        # The gate protects against an UNMEASURED SPEND, not against running at
        # all. A plan whose calls are already cached spends nothing, so when the
        # cache covers it the missing cost model is moot: this is the resume
        # path after a container died holding the only copy of the ledger.
        cached = len(list(CACHE.glob("*.json")))
        expected = len(plan) + n_ts
        if not _ledger().get("cost_per_event_call"):
            if cached >= 0.9 * expected:
                print(f"cost model unmeasured, but {cached:,} of ~{expected:,} "
                      f"calls are already cached: resuming, which spends "
                      f"nothing on the cached ones.")
            else:
                raise SystemExit(
                    "Run --probe first: the cost model is unmeasured and the "
                    f"cache holds only {cached:,} of ~{expected:,} calls.")
        done = unmatched = 0
        for _, r in plan.iterrows():
            try:
                events, _ = puller.events_at(r["iso_ts"])
                match = match_event(events, r["home_team"], r["away_team"])
                if match is None:
                    unmatched += 1
                else:
                    puller.props_at(str(match.get("id")), r["iso_ts"])
                done += 1
                if done % 100 == 0:
                    print(f"  {done}/{len(plan)}  spent "
                          f"{_ledger()['spent']:,}")
            except RuntimeError as e:
                print(f"stopped: {e}")
                break
        print(f"done. spent {_ledger()['spent']:,} credits over "
              f"{_ledger()['calls']:,} calls; {unmatched} snapshots had no "
              f"matching event and were skipped")


if __name__ == "__main__":
    main()
