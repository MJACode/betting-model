"""Historical NHL player-prop prices (and the regulation 3-way line) from The Odds API.

WHY. scripts/nhl_prop_lab.py showed prop models built from the per-game logs
beat the season-average and last-ten projections on all 24 market / line /
season rows of two holdout seasons — and could not say a word about PROFIT,
because `player_prop_odds` has never held an NHL row. mike, 2026-09-20: "buy
the prop history now".

WHAT IS BOUGHT. The feed sells NHL props from 2023-05-03. Per game date, ONE
pre-game snapshot an hour before that day's first puck drop (props are posted
the morning of the game, so every game on the slate is priced by then), for:

    player_shots_on_goal  player_points  player_assists  player_goal_scorer_anytime
    player_total_saves    player_blocked_shots           h2h_3_way (regulation line)

from the ten fetched books (config.LINE_SHOP_BOOKMAKERS — DraftKings and
Pinnacle among them; ten names is one billing region). The feed bills
10 credits x markets RETURNED per game, and one credit per date for the event
list, so cost is MEASURED from `x-requests-last` on every response and the run
stops at the ceiling it was given. NEWEST SEASON FIRST: if the budget runs out,
what is stored is the most relevant data, not the oldest.

Props land in `player_prop_odds` exactly as every other sport's do; the 3-way
line lands in `odds` as market `h2h_3way` with `source = 'odds_api_nhl_prop_history'`.
A date that already holds NHL shots-on-goal rows is skipped, so a re-run buys
nothing twice.

    python -m data.ingestors.nhl_prop_odds_history --probe 2026-01-15      # 3 games, prints measured cost
    python -m data.ingestors.nhl_prop_odds_history --seasons 2026 2026 --max-credits 100000 --apply
"""
from __future__ import annotations

import argparse
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from loguru import logger

import config
from data.db import get_connection
from data.ingestors.odds_ingestor import _normalize_team, _parse_outcomes
from data.ingestors.odds_quota import persist_quota, record_quota_headers
from data.ingestors.prop_odds_ingestor import _insert_prop_odds, _parse_prop_markets

BASE = "https://api.the-odds-api.com/v4/historical/sports/icehockey_nhl"
PROP_MARKETS = ["player_shots_on_goal", "player_points", "player_assists",
                "player_goal_scorer_anytime", "player_total_saves", "player_blocked_shots"]
THREE_WAY = "h2h_3_way"
BOOKS = ",".join(config.LINE_SHOP_BOOKMAKERS[:10])
SOURCE_PREFIX = "odds_api_nhl_prop_history"   # the marker a re-run reads back
SOURCE = SOURCE_PREFIX
SNAPSHOT_TYPE = "open"          # the pre-game series, as every other sport's history is filed
ET = ZoneInfo("America/New_York")


class Meter:
    """Credits actually billed, read off every response."""

    def __init__(self, ceiling: int):
        self.ceiling, self.spent, self.remaining = ceiling, 0, None

    def get(self, url: str, params: dict):
        for attempt in range(4):
            try:
                r = requests.get(url, params={**params, "apiKey": config.ODDS_API_KEY}, timeout=60)
                break
            except requests.RequestException as exc:
                logger.warning(f"network: {exc}; retry {attempt + 1}")
                time.sleep(3 * (attempt + 1))
        else:
            return None
        record_quota_headers(r)
        self.spent += int(float(r.headers.get("x-requests-last") or 0))
        self.remaining = r.headers.get("x-requests-remaining")
        time.sleep(0.25)
        return r

    @property
    def room(self) -> int:
        return self.ceiling - self.spent


def _games_by_date(conn, first_season: int, last_season: int) -> dict[str, list[dict]]:
    rows = conn.execute("""
        SELECT game_id, game_date, home_team, away_team, commence_time FROM games
        WHERE sport = 'NHL' AND season BETWEEN ? AND ? AND home_score IS NOT NULL
          AND commence_time IS NOT NULL AND game_date >= '2023-05-03'
    """, (first_season, last_season)).fetchall()
    out: dict[str, list[dict]] = defaultdict(list)
    for gid, gd, home, away, ct in rows:
        t = datetime.fromisoformat(str(ct).replace("Z", "+00:00")).astimezone(timezone.utc)
        out[gd[:10]].append({"game_id": gid, "home": home, "away": away, "start": t})
    return out


def _done_dates(conn, by_date: dict[str, list[dict]]) -> set[str]:
    """Dates already bought. Asked BY GAME ID: `player_prop_odds` is hundreds of
    millions of rows indexed on (game_id, market, ...), and the first version's
    `game_id LIKE 'NHL%'` scanned all of it into the 2-minute statement timeout
    before a single credit was spent (2026-09-20)."""
    ids = [g["game_id"] for games in by_date.values() for g in games]
    have: set[str] = set()
    for i in range(0, len(ids), 500):
        have |= {r[0] for r in conn.execute(
            "SELECT DISTINCT game_id FROM player_prop_odds "
            "WHERE game_id = ANY(%s) AND market = 'player_shots_on_goal'",
            (ids[i:i + 500],)).fetchall()}
    # `player_prop_odds` carries no `source`; the 3-way rows this run writes to
    # `odds` do, so the marker is read back from there as the second key.
    have |= {r[0] for r in conn.execute(
        "SELECT DISTINCT game_id FROM odds WHERE sport = 'NHL' AND market = 'h2h_3way' "
        "AND source LIKE %s", (SOURCE_PREFIX + "%",)).fetchall()}
    return {d for d, games in by_date.items() if any(g["game_id"] in have for g in games)}


def pull_date(conn, meter: Meter, game_date: str, games: list[dict],
              limit: int | None = None, apply: bool = True) -> dict:
    snap = (min(g["start"] for g in games) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = meter.get(f"{BASE}/events", {"date": snap})
    if r is None or r.status_code != 200:
        return {"date": game_date, "error": getattr(r, "status_code", "network")}
    by_teams = {(g["away"], g["home"]): g for g in games}
    stats = {"date": game_date, "snapshot": snap, "events": 0, "prop_rows": 0,
             "three_way": 0, "books": defaultdict(set)}
    for ev in (r.json().get("data") or []):
        key = (_normalize_team(ev.get("away_team", ""), "NHL"),
               _normalize_team(ev.get("home_team", ""), "NHL"))
        g = by_teams.get(key)
        if g is None:
            continue
        et_date = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00")).astimezone(ET).date()
        if et_date.isoformat() != game_date:
            continue                                   # tomorrow's rematch, listed early
        if limit is not None and stats["events"] >= limit:
            break
        if meter.room < 10 * (len(PROP_MARKETS) + 1):
            stats["stopped"] = "ceiling"
            break
        resp = meter.get(f"{BASE}/events/{ev['id']}/odds", {
            "date": snap, "markets": ",".join(PROP_MARKETS + [THREE_WAY]), "bookmakers": BOOKS,
            "oddsFormat": "american", "dateFormat": "iso"})
        if resp is None or resp.status_code != 200:
            logger.warning(f"  {g['game_id']}: HTTP {getattr(resp, 'status_code', 'network')}")
            continue
        body = resp.json()
        stamp = body.get("timestamp") or snap
        stats["events"] += 1
        prop_rows, odds_rows = [], []
        for book in (body.get("data") or {}).get("bookmakers", []):
            bk = book.get("key", "")
            props = [m for m in book.get("markets", []) if m.get("key") in PROP_MARKETS]
            # Anytime scorer is Yes/No with no number. The shared parser only
            # defaults a line for the markets it knows, and a row with no line
            # is dropped — the first probe was billed for this market and
            # stored none of it. "To score" IS over 0.5 goals.
            for m in props:
                if m.get("key") == "player_goal_scorer_anytime":
                    for o in m.get("outcomes", []):
                        o.setdefault("point", 0.5)
            got = _parse_prop_markets(props, game_id=g["game_id"], game_date=game_date,
                                      snapshot_type=SNAPSHOT_TYPE, snapshot_at=stamp,
                                      allowed_markets=PROP_MARKETS, bookmaker=bk)
            prop_rows += got
            for row in got:
                stats["books"][row["market"]].add(bk)
            for m in book.get("markets", []):
                if m.get("key") == THREE_WAY:
                    o = _parse_outcomes(m.get("outcomes", []), "NHL", ev.get("home_team", ""))
                    if o.get("home_price") is not None and o.get("draw_price") is not None:
                        odds_rows.append((g["game_id"], bk, m.get("last_update") or stamp,
                                          o.get("home_price"), o.get("away_price"), o.get("draw_price")))
                        stats["books"][THREE_WAY].add(bk)
        if apply:
            if prop_rows:
                stats["prop_rows"] += _insert_prop_odds(conn, prop_rows)
            if odds_rows:
                conn.executemany(
                    "INSERT INTO odds (game_id, sport, market, bookmaker, snapshot_type, snapshot_at, "
                    "home_price, away_price, draw_price, source) "
                    "VALUES (%s, 'NHL', 'h2h_3way', %s, 'open', %s, %s, %s, %s, '" + SOURCE + "')",
                    odds_rows)
                stats["three_way"] += len(odds_rows)
            conn.commit()
        else:
            stats["prop_rows"] += len(prop_rows)
            stats["three_way"] += len(odds_rows)
    stats["books"] = {k: sorted(v) for k, v in stats["books"].items()}
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--probe", metavar="DATE", help="3 games on one date; writes nothing")
    ap.add_argument("--seasons", nargs=2, type=int, metavar=("FIRST", "LAST"))
    ap.add_argument("--max-credits", type=int, help="REQUIRED with --apply: the ceiling for this run")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    conn = get_connection()
    try:
        if a.probe:
            season = int(a.probe[:4]) + (1 if int(a.probe[5:7]) >= 9 else 0)
            games = _games_by_date(conn, season, season).get(a.probe, [])
            meter = Meter(ceiling=400)
            s = pull_date(conn, meter, a.probe, games, limit=3, apply=False)
            print(s)
            print(f"MEASURED: {meter.spent} credits for {s.get('events')} games + 1 event list "
                  f"-> {(meter.spent - 1) / max(s.get('events') or 1, 1):.1f} per game; "
                  f"remaining {meter.remaining}")
            return
        if not a.seasons:
            ap.error("give --probe DATE or --seasons FIRST LAST")
        by_date = _games_by_date(conn, *a.seasons)
        done = _done_dates(conn, by_date)
        todo = sorted((d for d in by_date if d not in done), reverse=True)     # newest first
        n_games = sum(len(by_date[d]) for d in todo)
        print(f"{len(todo):,} dates / {n_games:,} games to buy ({len(done):,} dates already stored)")
        if not a.apply:
            print("dry run — nothing spent. Re-run with --apply --max-credits N.")
            return
        if not a.max_credits:
            ap.error("--apply needs --max-credits")
        meter = Meter(ceiling=a.max_credits)
        rows = games_done = 0
        for d in todo:
            if meter.room < 100:
                print(f"ceiling reached before {d}")
                break
            s = pull_date(conn, meter, d, by_date[d])
            rows += s.get("prop_rows", 0)
            games_done += s.get("events", 0)
            logger.info(f"{d}: {s.get('events')} games, {s.get('prop_rows')} prop rows, "
                        f"{s.get('three_way')} 3-way rows | spent {meter.spent:,} of {meter.ceiling:,}")
        print(f"bought {games_done:,} games, {rows:,} prop rows, spent {meter.spent:,} credits; "
              f"feed says {meter.remaining} remain")
    finally:
        try:
            persist_quota(conn)
        finally:
            conn.close()


if __name__ == "__main__":
    main()
