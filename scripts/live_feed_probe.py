"""
Is The Odds API's PER-EVENT endpoint fresher than its bulk one?

WHY THIS EXISTS. Measured on 2026-08-29 over 2.5 hours of in-play fetching, the
bulk /odds endpoint served ONE snapshot to ~7 consecutive requests: every event
in a response carries the same `last_update`, and that value only advanced every
~46 seconds (NCAAF looked closer to ~64s). So the bulk feed is a cache, our 5s
polling gets the identical payload seven times over, and a live pick can be a
full cache cycle behind the book's app before it is even written. That is the
whole of the "you posted 46.5 and DraftKings was on 51" complaint, and no amount
of polling the same endpoint fixes it.

The per-event endpoint (/events/{id}/odds) is billed separately and may well be
cached separately. This probe answers whether it is FRESHER, with data rather
than a guess, before anyone pays per event per market for it in the live loop.

WHAT IT MEASURES, per round, for the same live games at the same moment:
  * bulk       - one request, every live event, 1 credit per market per region
  * per-event  - one request per event, 1 credit per market per region EACH

and records both the API's `last_update` and our wall clock, so afterwards:
  * refresh interval  = how often each source's last_update actually advances
  * freshness delta   = per_event.last_update - bulk.last_update at one instant
                        (positive = the per-event endpoint is ahead)
  * line disagreement = whether the two sources ever show a different number

Read-only with respect to the platform: it writes to its own table and touches
nothing the loops read.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.db import get_connection                       # noqa: E402

API = "https://api.the-odds-api.com/v4"
SPORT_KEYS = {"MLB": "baseball_mlb", "NCAAF": "americanfootball_ncaaf",
              "NFL": "americanfootball_nfl"}

DDL = """
CREATE TABLE IF NOT EXISTS live_feed_probe (
    probe_id      BIGSERIAL PRIMARY KEY,
    run_id        TEXT NOT NULL,
    sport         TEXT NOT NULL,
    source        TEXT NOT NULL,          -- 'bulk' | 'event'
    event_id      TEXT NOT NULL,
    matchup       TEXT,
    last_update   TEXT,                   -- the API's own snapshot stamp
    fetched_at    TEXT NOT NULL,          -- our wall clock at response
    total_line    NUMERIC,
    over_price    NUMERIC,
    under_price   NUMERIC,
    credits_used  INTEGER,
    created_at    TEXT DEFAULT (NOW()::TEXT)
)
"""


def _key() -> str:
    k = os.environ.get("ODDS_API_KEY") or os.environ.get("THE_ODDS_API_KEY")
    if not k:
        raise SystemExit("no ODDS_API_KEY / THE_ODDS_API_KEY")
    return k


def _get(url: str, params: dict) -> tuple[object, int]:
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    used = r.headers.get("x-requests-last")
    return r.json(), int(float(used)) if used else 0


def _totals(ev: dict) -> tuple:
    """(last_update, line, over, under) for DraftKings' main total."""
    for bk in ev.get("bookmakers") or []:
        for m in bk.get("markets") or []:
            if m.get("key") != "totals":
                continue
            line = over = under = None
            for o in m.get("outcomes") or []:
                if o.get("name") == "Over":
                    line, over = o.get("point"), o.get("price")
                elif o.get("name") == "Under":
                    under = o.get("price")
            return (m.get("last_update") or bk.get("last_update"),
                    line, over, under)
    return (None, None, None, None)


def _is_live(ev: dict, now: datetime) -> bool:
    raw = ev.get("commence_time")
    if not raw:
        return False
    try:
        t = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return False
    return t <= now


def _row(run_id, sport, source, ev, lu, line, over, under, fetched, credits):
    return {"run_id": run_id, "sport": sport, "source": source,
            "event_id": str(ev.get("id") or ""),
            "matchup": f"{ev.get('away_team')} @ {ev.get('home_team')}",
            "last_update": lu, "fetched_at": fetched,
            "total_line": line, "over_price": over, "under_price": under,
            "credits_used": credits}


def run(sport: str, minutes: float, interval: float, max_events: int,
        book: str) -> None:
    key, sport_key = _key(), SPORT_KEYS[sport]
    run_id = f"{sport}-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}"
    conn = get_connection()
    conn.execute(DDL)
    conn.commit()

    deadline = time.time() + minutes * 60
    rounds = spent = 0
    print(f"probe {run_id}: every {interval}s for {minutes}m, "
          f"up to {max_events} live event(s), book={book}", flush=True)

    while time.time() < deadline:
        started = time.time()
        rows = []
        now = datetime.now(timezone.utc)
        try:
            events, c = _get(f"{API}/sports/{sport_key}/odds",
                             {"apiKey": key, "regions": "us",
                              "markets": "totals", "oddsFormat": "american",
                              "bookmakers": book})
        except Exception as exc:                          # noqa: BLE001
            print(f"bulk failed: {exc}", flush=True)
            time.sleep(max(0.0, interval - (time.time() - started)))
            continue
        spent += c
        fetched = datetime.now(timezone.utc).isoformat()
        live = [e for e in events if _is_live(e, now)][:max_events]
        for ev in live:
            lu, line, over, under = _totals(ev)
            if lu is None:
                continue
            rows.append(_row(run_id, sport, "bulk", ev, lu, line, over, under,
                             fetched, c))

        # Same games, same moment, the endpoint we are considering paying for.
        for ev in live:
            try:
                one, c1 = _get(f"{API}/sports/{sport_key}/events/"
                               f"{ev.get('id')}/odds",
                               {"apiKey": key, "regions": "us",
                                "markets": "totals", "oddsFormat": "american",
                                "bookmakers": book})
            except Exception as exc:                      # noqa: BLE001
                print(f"event {ev.get('id')} failed: {exc}", flush=True)
                continue
            spent += c1
            lu, line, over, under = _totals(one if isinstance(one, dict)
                                            else (one or [{}])[0])
            if lu is None:
                continue
            rows.append(_row(run_id, sport, "event", ev, lu, line, over, under,
                             datetime.now(timezone.utc).isoformat(), c1))

        if rows:
            conn.executemany(
                "INSERT INTO live_feed_probe (run_id, sport, source, event_id,"
                " matchup, last_update, fetched_at, total_line, over_price,"
                " under_price, credits_used) VALUES (%(run_id)s, %(sport)s,"
                " %(source)s, %(event_id)s, %(matchup)s, %(last_update)s,"
                " %(fetched_at)s, %(total_line)s, %(over_price)s,"
                " %(under_price)s, %(credits_used)s)", rows)
            conn.commit()
        rounds += 1
        if rounds % 10 == 0:
            print(f"round {rounds}: {len(live)} live, {spent} credits",
                  flush=True)
        # Deadline-based: a flat sleep would make the real cadence
        # interval + however long the fan-out took, which is the drift the
        # NCAAF loop had to be fixed for.
        time.sleep(max(0.0, interval - (time.time() - started)))

    print(f"probe {run_id} done: {rounds} rounds, {spent} credits", flush=True)
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sport", default="MLB", choices=sorted(SPORT_KEYS))
    ap.add_argument("--minutes", type=float, default=20.0)
    ap.add_argument("--interval", type=float, default=10.0)
    ap.add_argument("--max-events", type=int, default=3)
    ap.add_argument("--book", default="draftkings")
    a = ap.parse_args()
    run(a.sport, a.minutes, a.interval, a.max_events, a.book)
