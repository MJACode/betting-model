"""Kalshi NFL player-prop ladders: fetch, parse, and start keeping them.

WHY. `docs/prop_market_research.md` records the finding this exists to act on:
Kalshi quotes a LADDER of strikes per player rather than a single over/under, and
a ladder is an implied distribution. That gives two things no book we currently
read can:

  * a fair value with no de-vig assumption -- the mid of a two-sided exchange
    order book, rather than a proportional split of somebody's margin;
  * a price at ANY line, which is the direct answer to the 63,676 NFL
    propositions `models/nfl_prop_market` discards because the sharp and soft
    books quote different numbers.

Measured 2026-09-08: 1,333 open NFL prop markets across a full 16-game slate,
149 player-games, median 9 strikes each, receiving-yards spreads of 1-2c against
a sportsbook's ~7% prop hold.

THIS DOES NOT SCORE ANYTHING, AND MUST NOT UNTIL IT IS GRADED. Kalshi's NFL prop
markets are new -- settled history reaches back only to 2026 preseason -- so
there is not yet a record to validate a reference against, and §5c's bar for
Pinnacle was a placebo test on three seasons. The purpose of this module today is
that history STARTS ACCUMULATING, so the grading is possible in weeks rather than
starting from zero whenever someone next asks.

KEYED ON (game_date, player, market), NOT ON A GAME ID. Kalshi's event code is
`26SEP13ATLPIT` and ours is `NFL_2026_02_ATL_PIT`; mapping between them needs a
team-abbreviation table and would fail quietly on the ones that disagree. A
player appears at most once per date, so (date, player, market) is already
unique, and it joins to our board without any team mapping at all.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime

import requests
from loguru import logger

import config
from models.prop_ladder import Ladder, from_kalshi

# Kalshi series -> the market name our board uses. Only per-GAME player series;
# season-long, head-to-head, "most yards" and team series are deliberately absent
# because they are different propositions that happen to share a stat name.
SERIES_MARKET = {
    "KXNFLPASSYDS": "player_pass_yds",
    "KXNFLRECYDS": "player_reception_yds",
    "KXNFLRSHYDS": "player_rush_yds",
    "KXNFLRRYDS": "player_rush_reception_yds",
    "KXNFLPASSTDS": "player_pass_tds",
    "KXNFLPASSINT": "player_pass_interceptions",
}

_BASE = config.KALSHI_API_BASE.rstrip("/")

# "KXNFLPASSYDS-26SEP13ATLPIT" -> 2026-09-13. The teams are deliberately not
# parsed; see the module docstring on why the join is (date, player, market).
#
# SEARCHED, NOT ANCHORED. The first version anchored this at the start of the
# string on the assumption that `event_ticker` was the bare event code. It is
# not -- it carries the series prefix -- so every one of 2,028 markets failed to
# parse and the probe reported "0 usable ladders", which looks exactly like a
# market that is not there.
_EVENT_DATE = re.compile(r"-(\d{2})([A-Z]{3})(\d{2})[A-Z]")
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
     "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}


def _event_date(event_ticker: str) -> str | None:
    m = _EVENT_DATE.search(event_ticker or "")
    if not m:
        return None
    yy, mon, dd = m.groups()
    month = _MONTHS.get(mon)
    if month is None:
        return None
    try:
        return datetime(2000 + int(yy), month, int(dd)).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _player(title: str) -> str | None:
    """"Tua Tagovailoa: 300+ passing yards" -> "Tua Tagovailoa".

    FROM THE TITLE, NOT THE TICKER. The ticker encodes the participant as
    `ATLTTAGOVAILOA1` -- team prefix, an initial, a surname and an index -- which
    is unparseable back into a name that will match nflverse. The title carries
    the book's own spelling, which is what the existing normaliser is built for.
    """
    if not title or ":" not in title:
        return None
    name = title.split(":", 1)[0].strip()
    return name or None


def fetch_series(series: str, status: str = "open",
                 limit: int = 1000, max_pages: int = 20) -> list[dict]:
    """Every market in one series, following the cursor."""
    out: list[dict] = []
    cursor = None
    for _ in range(max_pages):
        params = {"series_ticker": series, "status": status, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        r = requests.get(f"{_BASE}/markets", params=params, timeout=60)
        if r.status_code != 200:
            logger.warning(f"kalshi {series}: HTTP {r.status_code} {r.text[:160]}")
            return out
        body = r.json()
        out += body.get("markets", []) or []
        cursor = body.get("cursor")
        if not cursor:
            break
    return out


def ladders(status: str = "open",
            series_map: dict[str, str] | None = None) -> dict[tuple, Ladder]:
    """-> {(game_date, normalised_player, market): Ladder}.

    A market missing a date, a player or a strike is skipped rather than guessed
    at; the counts are logged so a silent collapse in coverage is visible as a
    number rather than as an empty result.
    """
    from data.ingestors.nfl_props_data_ingestor import norm_player_name

    series_map = series_map or SERIES_MARKET
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    skipped = defaultdict(int)

    for series, market in series_map.items():
        got = fetch_series(series, status=status)
        for m in got:
            date = _event_date(m.get("event_ticker", ""))
            name = _player(m.get("title", ""))
            if date is None:
                skipped["no_date"] += 1
                continue
            if name is None:
                skipped["no_player"] += 1
                continue
            if m.get("floor_strike") is None:
                skipped["no_strike"] += 1
                continue
            grouped[(date, norm_player_name(name), market)].append(m)
        logger.info(f"  kalshi {series}: {len(got)} markets -> {market}")

    out = {}
    for key, markets in grouped.items():
        lad = from_kalshi(markets)
        if lad.usable:
            out[key] = lad
        else:
            skipped["thin_ladder"] += 1
    logger.info(f"  kalshi: {len(out)} usable ladders "
                f"({dict(skipped)} skipped)")
    return out


def record_ladders(conn=None, status: str = "open",
                   series_map: dict[str, str] | None = None) -> dict:
    """Snapshot every open NFL prop rung into `kalshi_prop_ladders`.

    ONE `snapshot_at` FOR THE WHOLE RUN, taken before the first request rather
    than per row. A ladder is only meaningful as a set of prices that existed
    together: stamping each rung with its own arrival time would make the
    174.5 and 349.5 strikes of one player look like different observations, and
    any later reconstruction would have to guess which belonged together.

    RAW RUNGS, NOT LADDERS. The Ladder object is derived -- rebuild it with
    models.prop_ladder from the rungs at a snapshot. Storing interpolated output
    would freeze today's choices (logit space, PAVA, the spread gate) into the
    history, and those are exactly what a later analysis may want to vary. So no
    spread filtering happens here either: a one-sided rung is still a fact about
    the market at that instant, and the reader decides whether to use it.

    Idempotent within a snapshot via the (market_ticker, snapshot_at) unique
    index, so a retry costs nothing and cannot double a ladder.
    """
    from datetime import datetime, timezone

    from data.db import get_connection
    from data.ingestors.nfl_props_data_ingestor import norm_player_name

    series_map = series_map or SERIES_MARKET
    snapshot_at = datetime.now(timezone.utc)
    owns = conn is None
    conn = conn or get_connection()

    rows: list[tuple] = []
    skipped: dict[str, int] = defaultdict(int)
    try:
        for series, market in series_map.items():
            for m in fetch_series(series, status=status):
                date = _event_date(m.get("event_ticker", ""))
                name = _player(m.get("title", ""))
                strike = m.get("floor_strike")
                ticker = m.get("ticker")
                if date is None or name is None or strike is None or not ticker:
                    skipped["unparsed"] += 1
                    continue

                def _num(v):
                    if v in (None, ""):
                        return None
                    try:
                        return float(v)
                    except (TypeError, ValueError):
                        return None

                rows.append((
                    snapshot_at, date, norm_player_name(name), name, market,
                    float(strike),
                    _num(m.get("yes_bid_dollars")), _num(m.get("yes_ask_dollars")),
                    _num(m.get("volume_fp")), _num(m.get("open_interest_fp")),
                    m.get("event_ticker"), ticker,
                ))

        written = 0
        cols = ("snapshot_at, game_date, player_key, player_display, market, "
                "strike, yes_bid, yes_ask, volume, open_interest, "
                "event_ticker, market_ticker")
        ph = "(" + ", ".join(["%s"] * 12) + ")"
        for i in range(0, len(rows), 500):
            chunk = rows[i:i + 500]
            sql = (f"INSERT INTO kalshi_prop_ladders ({cols}) VALUES "
                   + ", ".join([ph] * len(chunk))
                   + " ON CONFLICT (market_ticker, snapshot_at) DO NOTHING")
            conn.execute(sql, tuple(v for r in chunk for v in r))
            written += len(chunk)
        conn.commit()

        props = len({(r[1], r[2], r[4]) for r in rows})
        out = {"rungs": written, "propositions": props,
               "snapshot_at": snapshot_at.isoformat(), "skipped": dict(skipped)}
        logger.info(f"kalshi ladders recorded: {out}")
        return out
    finally:
        if owns:
            conn.close()
