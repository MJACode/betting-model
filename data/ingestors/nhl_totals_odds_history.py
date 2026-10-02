"""Historical NHL team totals, alternate totals and first-period totals from The Odds API.

WHY. Four rounds found nothing in the full-game total (docs/nhl_market_lab.md,
"Total goals, round four"): the book's margin sits on BOTH sides of it. Every
NHL result that holds is in a market where the margin sits on one side -- the
player props, where every over loses 9-12% blind and every under 0-3.5%. The
total-goals markets shaped like that are the derivative ones, and no price for
any of them was stored. mike, 2026-10-01: "buy the totals data".

WHAT IS BOUGHT. Per game date, ONE pre-game snapshot an hour before that day's
first puck drop -- the same instant the prop history was bought at, so the two
series line up -- for three markets:

    team_totals        each team's own goals, over / under a number
    alternate_totals   the game total at every number the book hangs
    totals_p1          first-period goals

from the ten fetched books (config.LINE_SHOP_BOOKMAKERS; ten names is one
billing region). The feed bills 10 credits x markets RETURNED per game and one
credit per date for the event list, so cost is MEASURED from `x-requests-last`
on every response and the run stops at the ceiling it was given. NEWEST SEASON
FIRST: if the budget runs out, what is stored is the most relevant data.

WHERE IT LANDS. `odds`, one row per (game, book, market, number), written in
the same run that buys it, `source = 'odds_api_nhl_totals_history'`:

    market 'team_totals_home' / 'team_totals_away'   total_line, over_price, under_price
    market 'alternate_totals'                        one row per number
    market 'totals_p1'                               total_line, over_price, under_price

Every book in a snapshot is stamped with the SNAPSHOT's time, so rows of one
game share `snapshot_at` and are simultaneous by construction. No existing
reader names these markets, so nothing that scores reads them. A date that
already holds a row with this source is skipped: a re-run buys nothing twice.

    python -m data.ingestors.nhl_totals_odds_history --probe 2026-01-15      # 3 games, writes nothing, prints measured cost
    python -m data.ingestors.nhl_totals_odds_history --seasons 2024 2026 --max-credits 130000 --apply
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta

from loguru import logger

import config
from data.db import get_connection
from data.ingestors.nhl_prop_odds_history import BASE, ET, Meter, _games_by_date
from data.ingestors.odds_ingestor import _normalize_team
from data.ingestors.odds_quota import persist_quota

MARKETS = ["team_totals", "alternate_totals", "totals_p1"]
BOOKS = ",".join(config.LINE_SHOP_BOOKMAKERS[:10])
SOURCE = "odds_api_nhl_totals_history"
SNAPSHOT_TYPE = "open"          # the pre-game series, as every other sport's history is filed


def parse_market(market: dict, home: str, away: str) -> list[dict]:
    """One book's market -> rows of {market, total_line, over_price, under_price}.

    An over and an under belong together when they share a number (and, for
    team totals, a team). A number quoted on one side only is kept with the
    other side empty: it is what the book offered.

    `home` / `away` are the game's team abbreviations; a team-total outcome
    names its team in `description`, and one that names neither is dropped
    rather than guessed onto a side.
    """
    key = market.get("key")
    pairs: dict[tuple, dict] = {}
    for o in market.get("outcomes", []):
        side = str(o.get("name", "")).strip().lower()
        point, price = o.get("point"), o.get("price")
        if side not in ("over", "under") or point is None or price is None:
            continue
        if key == "team_totals":
            named = str(o.get("description") or "").strip()
            team = _normalize_team(named, "NHL") if named else None      # no team named: not a guess
            if team == home:
                stored = "team_totals_home"
            elif team == away:
                stored = "team_totals_away"
            else:
                continue
        else:
            stored = key
        row = pairs.setdefault((stored, float(point)), {"market": stored, "total_line": float(point),
                                                        "over_price": None, "under_price": None})
        row[f"{side}_price"] = price
    return list(pairs.values())


def _done_dates(conn, by_date: dict[str, list[dict]]) -> set[str]:
    """Dates already bought, read back from the source marker BY GAME ID (`odds` is 10 GB)."""
    ids = [g["game_id"] for games in by_date.values() for g in games]
    have: set[str] = set()
    for i in range(0, len(ids), 500):
        have |= {r[0] for r in conn.execute(
            "SELECT DISTINCT game_id FROM odds WHERE game_id = ANY(%s) AND source = %s",
            (ids[i:i + 500], SOURCE)).fetchall()}
    return {d for d, games in by_date.items() if any(g["game_id"] in have for g in games)}


def pull_date(conn, meter: Meter, game_date: str, games: list[dict],
              limit: int | None = None, apply: bool = True) -> dict:
    snap = (min(g["start"] for g in games) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = meter.get(f"{BASE}/events", {"date": snap})
    if r is None or r.status_code != 200:
        return {"date": game_date, "error": getattr(r, "status_code", "network")}
    by_teams = {(g["away"], g["home"]): g for g in games}
    stats = {"date": game_date, "snapshot": snap, "events": 0, "rows": 0,
             "by_market": defaultdict(int), "books": defaultdict(set)}
    for ev in (r.json().get("data") or []):
        g = by_teams.get((_normalize_team(ev.get("away_team", ""), "NHL"),
                          _normalize_team(ev.get("home_team", ""), "NHL")))
        if g is None:
            continue
        et_date = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00")).astimezone(ET).date()
        if et_date.isoformat() != game_date:
            continue                                   # tomorrow's rematch, listed early
        if limit is not None and stats["events"] >= limit:
            break
        if meter.room < 10 * len(MARKETS):
            stats["stopped"] = "ceiling"
            break
        resp = meter.get(f"{BASE}/events/{ev['id']}/odds", {
            "date": snap, "markets": ",".join(MARKETS), "bookmakers": BOOKS,
            "oddsFormat": "american", "dateFormat": "iso"})
        if resp is None or resp.status_code != 200:
            logger.warning(f"  {g['game_id']}: HTTP {getattr(resp, 'status_code', 'network')}")
            continue
        body = resp.json()
        stamp = body.get("timestamp") or snap
        stats["events"] += 1
        rows = []
        for book in (body.get("data") or {}).get("bookmakers", []):
            bk = book.get("key", "")
            for m in book.get("markets", []):
                if m.get("key") not in MARKETS:
                    continue
                for row in parse_market(m, g["home"], g["away"]):
                    rows.append((g["game_id"], row["market"], bk, stamp, row["total_line"],
                                 row["over_price"], row["under_price"]))
                    stats["by_market"][row["market"]] += 1
                    stats["books"][m["key"]].add(bk)
        if apply and rows:
            conn.executemany(
                "INSERT INTO odds (game_id, sport, market, bookmaker, snapshot_type, snapshot_at, "
                "total_line, over_price, under_price, source) "
                "VALUES (%s, 'NHL', %s, %s, '" + SNAPSHOT_TYPE + "', %s, %s, %s, %s, '" + SOURCE + "')", rows)
            conn.commit()
        stats["rows"] += len(rows)
    stats["by_market"] = dict(stats["by_market"])
    stats["books"] = {k: sorted(v) for k, v in stats["books"].items()}
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
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
            meter = Meter(ceiling=200)
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
        print(f"{len(todo):,} dates / {n_games:,} games to buy ({len(done):,} dates already stored); "
              f"at {10 * len(MARKETS)} credits a game + 1 a date that is about "
              f"{n_games * 10 * len(MARKETS) + len(todo):,} credits", flush=True)
        if not a.apply:
            print("dry run — nothing spent. Re-run with --apply --max-credits N.")
            return
        if not a.max_credits:
            ap.error("--apply needs --max-credits")
        meter = Meter(ceiling=a.max_credits)
        rows = games_done = 0
        for d in todo:
            if meter.room < 10 * len(MARKETS) + 1:
                print(f"ceiling reached before {d}", flush=True)
                break
            s = pull_date(conn, meter, d, by_date[d])
            rows += s.get("rows", 0)
            games_done += s.get("events", 0)
            logger.info(f"{d}: {s.get('events')} games, {s.get('rows')} rows {s.get('by_market')} "
                        f"| spent {meter.spent:,} of {meter.ceiling:,}")
        print(f"bought {games_done:,} games, {rows:,} rows, spent {meter.spent:,} credits; "
              f"feed says {meter.remaining} remain", flush=True)
    finally:
        try:
            persist_quota(conn)
        finally:
            conn.close()


if __name__ == "__main__":
    main()
