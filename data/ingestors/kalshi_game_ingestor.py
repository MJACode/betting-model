"""
Kalshi NCAAF GAME markets -- winner, total-points ladder, spread ladder --
recorded raw, one row per contract per snapshot. RECORDING ONLY: nothing
scores off this table, and nothing may until a settled record exists.

WHY (session 280, 2026-09-10). The NCAAF cross-book work found "one number
across thirteen books": DraftKings sits a mean 0.16 points from the 13-book
median total, Pinnacle and Bovada post ~5 days after DK, and no consensus,
dispersion or steam-lag construction cleared -110. Every one of those books is
a bookmaker. Kalshi is an exchange: no vig, resting orders, a timestamped
price on every rung of a total/spread ladder, and (probed 2026-09-10, no key)
it lists NCAAF winner markets on 118 events and total ladders on 68 for the
coming weekend. Whether that price knows anything the 13 books do not is
exactly the question a record answers and a guess does not -- the same
reason `kalshi_prop_ingestor` exists for NFL props.

SERIES (from /series?category=Sports, probed 2026-09-10):
  KXNCAAFGAME    "College Football Game"          two YES contracts per event, one per team
  KXNCAAFTOTAL   "College Football Total Points"  ladder: "Over 54.5 points scored", floor_strike 54.5
  KXNCAAFSPREAD  "College Football Spread"        ladder: "Miami (FL) wins by over 6.5", floor_strike 6.5
Half/quarter, team-total and season series are deliberately absent: different
propositions that happen to share a name.

KEYED ON THE EVENT TICKER, NOT OUR GAME ID. `KXNCAAFTOTAL-26SEP12ARKUTAH` names
the date and two Kalshi team codes; our id is `NCAAF_2026-09-12_arkansas_utah`.
Mapping codes to CFBD school names needs a table that would fail quietly on
the disagreements, so the row keeps Kalshi's event ticker, the parsed date and
the contract title verbatim, and the reader joins on (date, teams) with a map
it can inspect. `yes_sub_title` carries the team name for winner/spread rows.

ONE snapshot_at PER RUN, taken before the first request, so a ladder is a set
of prices that existed together. Raw prices, no spread gate, no interpolation.
Idempotent within a snapshot via (market_ticker, snapshot_at).

    python -m data.ingestors.kalshi_game_ingestor            # one snapshot
    python -m data.ingestors.kalshi_game_ingestor --probe    # counts only, no DB
"""
from __future__ import annotations

import argparse
import re
from collections import defaultdict
from datetime import datetime, timezone

from loguru import logger

import config
from data.ingestors.kalshi_prop_ingestor import fetch_series

# Kalshi series -> the proposition kind we store.
SERIES_KIND = {
    "KXNCAAFGAME":   "winner",
    "KXNCAAFTOTAL":  "total",
    "KXNCAAFSPREAD": "spread",
}

_EVENT_DATE = re.compile(r"-(\d{2})([A-Z]{3})(\d{2})[A-Z]")
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
     "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}


def event_date(event_ticker: str) -> str | None:
    """'KXNCAAFTOTAL-26SEP12ARKUTAH' -> '2026-09-12'. Searched, not anchored."""
    m = _EVENT_DATE.search(event_ticker or "")
    if not m:
        return None
    yy, mon, dd = m.groups()
    if mon not in _MONTHS:
        return None
    return f"20{yy}-{_MONTHS[mon]:02d}-{dd}"


def _num(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def rows_for(markets: list[dict], kind: str, snapshot_at: datetime,
             skipped: dict) -> list[tuple]:
    out = []
    for m in markets:
        date = event_date(m.get("event_ticker", ""))
        ticker = m.get("ticker")
        if date is None or not ticker:
            skipped["unparsed"] += 1
            continue
        strike = _num(m.get("floor_strike"))
        if kind != "winner" and strike is None:
            skipped["no_strike"] += 1
            continue
        out.append((
            snapshot_at, date, kind, m.get("event_ticker"), ticker,
            m.get("title"), m.get("yes_sub_title"), strike,
            _num(m.get("yes_bid_dollars")), _num(m.get("yes_ask_dollars")),
            _num(m.get("last_price_dollars")),
            _num(m.get("volume_fp")), _num(m.get("open_interest_fp")),
            m.get("status"), m.get("close_time"),
        ))
    return out


def record_game_markets(conn=None, status: str = "open",
                        series_kind: dict[str, str] | None = None) -> dict:
    """Snapshot every open NCAAF game contract into `kalshi_game_markets`."""
    from data.db import get_connection

    series_kind = series_kind or SERIES_KIND
    snapshot_at = datetime.now(timezone.utc)
    owns = conn is None
    conn = conn or get_connection()
    skipped: dict[str, int] = defaultdict(int)
    rows: list[tuple] = []
    try:
        for series, kind in series_kind.items():
            got = fetch_series(series, status=status)
            rows += rows_for(got, kind, snapshot_at, skipped)
            logger.info(f"  kalshi {series}: {len(got)} markets -> {kind}")

        cols = ("snapshot_at, game_date, kind, event_ticker, market_ticker, "
                "title, side_label, strike, yes_bid, yes_ask, last_price, "
                "volume, open_interest, status, close_time")
        ph = "(" + ", ".join(["%s"] * 15) + ")"
        written = 0
        for i in range(0, len(rows), 500):
            chunk = rows[i:i + 500]
            sql = (f"INSERT INTO kalshi_game_markets ({cols}) VALUES "
                   + ", ".join([ph] * len(chunk))
                   + " ON CONFLICT (market_ticker, snapshot_at) DO NOTHING")
            conn.execute(sql, tuple(v for r in chunk for v in r))
            written += len(chunk)
        conn.commit()
        events = len({r[3] for r in rows})
        out = {"contracts": written, "events": events,
               "snapshot_at": snapshot_at.isoformat(), "skipped": dict(skipped)}
        logger.info(f"kalshi game markets recorded: {out}")
        return out
    finally:
        if owns:
            conn.close()


def probe(status: str = "open") -> dict:
    """Counts per series, no database. What a snapshot would record."""
    out = {}
    for series, kind in SERIES_KIND.items():
        got = fetch_series(series, status=status)
        skipped: dict[str, int] = defaultdict(int)
        rows = rows_for(got, kind, datetime.now(timezone.utc), skipped)
        out[series] = {"markets": len(got), "rows": len(rows),
                       "events": len({r[3] for r in rows}), "skipped": dict(skipped)}
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--probe", action="store_true", help="counts only, write nothing")
    ap.add_argument("--status", default="open")
    args = ap.parse_args()
    if args.probe:
        for k, v in probe(args.status).items():
            print(k, v)
    else:
        print(record_game_markets(status=args.status))
