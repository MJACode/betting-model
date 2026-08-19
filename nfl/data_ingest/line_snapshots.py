"""DraftKings line snapshots for the platform's movement tracking.

Both live card scripts (weekly_wind_card, daily_opener_card) already pay for a
full-sport odds pull on every scheduled run, then keep only the qualifying
bets. This module dumps DraftKings' line for EVERY scheduled game in that pull
to data/cards/line_snapshots_YYYY-MM-DD.csv, so the platform publisher
(scripts/nfl_wind_publisher.py) can mirror the rows into the odds table and
the app can show how a line has moved since a pick was locked — the day-of
user's "the opener locked Tuesday; where is the market now?" view.

Zero extra API credits: this only reuses the payload the card already fetched.
DraftKings is captured (not the pick's own best/soft book) because DK is the
platform's reference book everywhere the app reads line history.

The pure row builder (dk_line_rows) works on plain dict records so it is
testable without pandas; only the schedule/dump helpers touch pandas, and they
run inside the nfl/ package where pandas is always present.
"""

from __future__ import annotations

import csv
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

SNAPSHOT_CSV_FIELDS = [
    "game_id", "matchup", "kick_utc", "market",
    "spread_home", "total_line",
    "home_price", "away_price", "over_price", "under_price",
    "snapshot_at",
]

# How far ahead to snapshot. Wider than any single card's own window on
# purpose: the bulk odds pull returns every upcoming event anyway, and the
# daily opener run (whose card window stops at T-2) is what carries snapshot
# coverage through game day for already-locked opener picks.
SNAPSHOT_HI_DAYS = 8.0


def _num(v):
    """Coerce a frame value to float, treating None/NaN/'' as missing."""
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def dk_line_rows(records: list[dict], sched_records: list[dict],
                 market: str, snapshot_at: str) -> list[dict]:
    """
    Pure transform: long snapshot records (parse.snapshot_to_frame shape —
    one row per event x book x market x side) + a schedule (game_id,
    home_team, away_team, kick_utc as nflverse abbrevs) -> one DK snapshot
    row per scheduled game that DraftKings prices.

    market is 'totals' or 'spreads'. Rows without a usable line are dropped
    (a price with no number can't feed movement display).
    """
    sched_by_matchup = {
        (s["home_team"], s["away_team"]): s for s in sched_records
    }
    by_game: dict[tuple, dict] = {}
    for r in records:
        if r.get("book") != "draftkings" or r.get("market") != market:
            continue
        key = (r.get("home"), r.get("away"))
        if key not in sched_by_matchup:
            continue
        slot = by_game.setdefault(key, {})
        side = r.get("side")
        price = _num(r.get("price"))
        point = _num(r.get("point"))
        if market == "totals":
            if side == "Over":
                slot["total_line"] = point
                slot["over_price"] = price
            elif side == "Under":
                slot.setdefault("total_line", point)
                slot["under_price"] = price
        elif market == "spreads":
            if side == "home":
                slot["spread_home"] = point
                slot["home_price"] = price
            elif side == "away":
                slot["away_price"] = price

    rows = []
    for key, slot in by_game.items():
        line = slot.get("total_line") if market == "totals" else slot.get("spread_home")
        if line is None:
            continue
        sched = sched_by_matchup[key]
        rows.append({
            "game_id": sched["game_id"],
            "matchup": f'{sched["away_team"]} @ {sched["home_team"]}',
            "kick_utc": sched["kick_utc"],
            "market": market,
            "spread_home": slot.get("spread_home"),
            "total_line": slot.get("total_line"),
            "home_price": slot.get("home_price"),
            "away_price": slot.get("away_price"),
            "over_price": slot.get("over_price"),
            "under_price": slot.get("under_price"),
            "snapshot_at": snapshot_at,
        })
    return rows


def snapshot_schedule(hi_days: float = SNAPSHOT_HI_DAYS) -> list[dict]:
    """Every game kicking off within hi_days, as plain dicts (nflverse ids)."""
    import pandas as pd
    from zoneinfo import ZoneInfo

    g = pd.read_csv("data/games.csv")
    dt = pd.to_datetime(g.gameday + " " + g.gametime, errors="coerce")
    kick = (dt.dt.tz_localize(ZoneInfo("America/New_York"), ambiguous=True,
                              nonexistent="shift_forward").dt.tz_convert("UTC"))
    g = g.assign(kick_utc=kick)
    now = pd.Timestamp.now(tz="UTC")
    g = g[(g.kick_utc > now) & (g.kick_utc <= now + pd.Timedelta(days=hi_days))]
    return [
        {"game_id": r.game_id, "home_team": r.home_team,
         "away_team": r.away_team, "kick_utc": str(r.kick_utc)}
        for r in g.itertuples()
    ]


def append_snapshot_csv(rows: list[dict], cards_dir: Path) -> Path:
    """Append rows to the day's snapshot CSV (header written once)."""
    cards_dir.mkdir(parents=True, exist_ok=True)
    path = cards_dir / f"line_snapshots_{datetime.now(timezone.utc):%Y-%m-%d}.csv"
    new_file = not path.exists()
    with open(path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SNAPSHOT_CSV_FIELDS)
        if new_file:
            w.writeheader()
        for r in rows:
            w.writerow(r)
    return path


def dump_dk_lines(frame, market: str,
                  cards_dir: Path = Path("data/cards"),
                  hi_days: float = SNAPSHOT_HI_DAYS) -> int:
    """
    Called by the card scripts right after snapshot_to_frame. Returns the
    number of games snapshotted (0 when DK priced nothing in window).
    """
    sched = snapshot_schedule(hi_days)
    if not sched:
        return 0
    snapshot_at = datetime.now(timezone.utc).isoformat()
    rows = dk_line_rows(frame.to_dict("records"), sched, market, snapshot_at)
    if not rows:
        return 0
    path = append_snapshot_csv(rows, cards_dir)
    print(f"line snapshots: {len(rows)} DK {market} row(s) -> {path.name}",
          file=sys.stderr)
    return len(rows)
