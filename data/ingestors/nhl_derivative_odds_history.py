"""Historical NHL derivative totals: team totals, alternate totals, first-period totals.

WHY. The full-game total has nothing in it (docs/nhl_market_lab.md, round four:
every over −4.0%, every under −4.4% across six seasons). The markets where an
NHL book's margin can sit on one side are team totals, alternate totals and
the first-period total. Michael, 2026-10-02: buy them and build the models.

WHAT IS BOUGHT. Three markets only, from the ten books the game-line backfill
already uses (ten names is one billing region):

    team_totals   alternate_totals   totals_p1

Per game date, ONE pre-game snapshot an hour before that day's first puck
(the same timing as data/ingestors/nhl_prop_odds_history.py), then one
historical event-odds call per game. Newest season first. The feed bills
10 credits per market RETURNED on that call, plus one credit for the event
list. A dry run prints that upper bound and — when ODDS_API_KEY is set — a
measured probe of three games. Michael, 2026-10-03: there is no credit cap.
`--apply` buys every game in the window that is not already stored. It does
not stop for a ceiling, a reserve, or a quota plan.

WHERE IT LANDS. `odds`, source `odds_api_nhl_totals_history`, snapshot_type
`open` (relabelled `in_play` when the snapshot is after that game's start).
Team totals are two markets, `team_totals_home` and `team_totals_away`, one
row per line. Alternate totals and the period total are one row per line.
That is the shape the 2024-26 purchase already uses, so a re-run sees those
rows and buys nothing twice. A pull ledger (`nhl_derivative_odds_pulls`)
records the call itself, including a game the feed returned empty.

    python -m data.ingestors.nhl_derivative_odds_history
    python -m data.ingestors.nhl_derivative_odds_history --probe 2026-01-15
    python -m data.ingestors.nhl_derivative_odds_history --apply
"""
from __future__ import annotations

import argparse
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import requests
from loguru import logger

import config
from data.anon_readable import lock_down
from data.db import get_connection
from data.ingestors.odds_ingestor import NHL_ODDS_API_MAP, _insert_odds, _name_key
from data.ingestors.odds_quota import persist_quota, record_quota_headers

BASE = "https://api.the-odds-api.com/v4/historical/sports/icehockey_nhl"
# The same ten as scripts/nhl_odds_history_backfill.py. Fourteen names bill as
# two regions; ten bill as one. Tests pin the two lists together.
BOOKS = ["draftkings", "pinnacle", "fanduel", "betmgm", "williamhill_us",
         "espnbet", "fanatics", "bovada", "betrivers", "hardrockbet"]
MARKETS = ["team_totals", "alternate_totals", "totals_p1"]
STORED_MARKETS = ("team_totals_home", "team_totals_away", "alternate_totals", "totals_p1")
SOURCE = "odds_api_nhl_totals_history"
# Ending years. 2024-2026 are the three seasons the feed had priced by
# 2026-10; 2027 is the season under way. Newest date first inside the window.
SEASONS = (2024, 2027)
LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS nhl_derivative_odds_pulls (
    game_id   TEXT PRIMARY KEY,
    game_date TEXT NOT NULL,
    pulled_at TIMESTAMPTZ NOT NULL,
    rows      INTEGER NOT NULL
)
"""


class Meter:
    """Credits actually billed, read off every response. It reports; it does not stop the pull."""

    def __init__(self):
        self.spent, self.remaining = 0, None

    def get(self, url: str, params: dict):
        if not config.ODDS_API_KEY:
            raise RuntimeError("ODDS_API_KEY is not set; refusing to call the Odds API")
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


def estimate_credits(n_games: int, n_dates: int) -> int:
    """Upper bound: every requested market is returned, plus the event list.

    The feed bills 10 credits per market RETURNED, not per market requested.
    A game that comes back with two of the three costs 20. This number is an
    upper bound, not a measurement and not a cap.
    """
    return n_games * 10 * len(MARKETS) + n_dates


def _team_abbrev(name: str) -> str | None:
    """Map a feed team name to the abbrev `games` uses. Unknown names are
    skipped — the fuzzy last-word fallback in `_normalize_team` invents one."""
    if not name:
        return None
    mapping = NHL_ODDS_API_MAP
    if name in mapping:
        return mapping[name]
    key = _name_key(name)
    return next((v for k, v in mapping.items() if _name_key(k) == key), None)


def _side_and_team(name: str, description: str) -> tuple[str | None, str]:
    """Over/Under and, for a team total, which team. The feed puts them in
    either field."""
    for side, team in ((name, description), (description, name)):
        if side.lower() in ("over", "under"):
            return side.capitalize(), team
    return None, ""


def parse_markets(book_markets: list[dict], home: str, away: str) -> list[dict]:
    """One odds-row dict per (market, line), home and away team totals split.

    A line the feed quotes on one side only is kept: the grader drops a side
    with no price, and discarding the row would hide that the other side was
    posted.
    """
    buckets: dict[tuple, dict] = {}
    for market in book_markets:
        key = market.get("key")
        if key not in MARKETS:
            continue
        for outcome in market.get("outcomes") or []:
            point, price = outcome.get("point"), outcome.get("price")
            if point is None or price is None:
                continue
            side, team = _side_and_team(outcome.get("name") or "", outcome.get("description") or "")
            if side is None:
                continue
            if key == "team_totals":
                abbrev = _team_abbrev(team)
                if abbrev == home:
                    stored = "team_totals_home"
                elif abbrev == away:
                    stored = "team_totals_away"
                else:
                    continue
            elif key == "totals_p1":
                stored = "totals_p1"
            else:
                stored = "alternate_totals"
            slot = buckets.setdefault((stored, float(point)), {})
            which = "over" if side == "Over" else "under"
            slot[which] = price
            slot[which + "_link"] = outcome.get("link")
            slot[which + "_sid"] = outcome.get("sid")
    rows = []
    for (stored, point), slot in buckets.items():
        rows.append({
            "market": stored, "total_line": point,
            "over_price": slot.get("over"), "under_price": slot.get("under"),
            "over_link": slot.get("over_link"), "under_link": slot.get("under_link"),
            "over_sid": slot.get("over_sid"), "under_sid": slot.get("under_sid"),
        })
    return rows


def _blank_row(game_id: str, book: str, snapshot_at: str, parsed: dict, commence) -> dict:
    snap_type = "open"
    try:
        snap_dt = datetime.fromisoformat(snapshot_at.replace("Z", "+00:00"))
        start = datetime.fromisoformat(str(commence).replace("Z", "+00:00"))
        if snap_dt > start:
            snap_type = "in_play"
    except (TypeError, ValueError):
        pass
    return {
        "game_id": game_id, "sport": "NHL", "market": parsed["market"], "bookmaker": book,
        "snapshot_type": snap_type, "snapshot_at": snapshot_at,
        "home_price": None, "away_price": None, "draw_price": None, "spread_home": None,
        "total_line": parsed["total_line"],
        "over_price": parsed["over_price"], "under_price": parsed["under_price"],
        "home_link": None, "away_link": None, "draw_link": None,
        "over_link": parsed["over_link"], "under_link": parsed["under_link"],
        "home_sid": None, "away_sid": None, "draw_sid": None,
        "over_sid": parsed["over_sid"], "under_sid": parsed["under_sid"],
        "source": SOURCE,
    }


def _games_by_date(conn, first_season: int, last_season: int) -> dict[str, list[dict]]:
    rows = conn.execute("""
        SELECT game_id, game_date, home_team, away_team, commence_time FROM games
        WHERE sport = 'NHL' AND season BETWEEN ? AND ? AND home_score IS NOT NULL
          AND commence_time IS NOT NULL
    """, (first_season, last_season)).fetchall()
    out: dict[str, list[dict]] = defaultdict(list)
    for gid, gd, home, away, ct in rows:
        t = datetime.fromisoformat(str(ct).replace("Z", "+00:00")).astimezone(timezone.utc)
        out[gd[:10]].append({"game_id": gid, "home": home, "away": away, "start": t})
    return out


def _done_ids(conn, game_ids: list[str]) -> set[str]:
    """Games already bought. Either the pull ledger has them, or `odds` already
    holds this source — the 2024-26 purchase wrote the rows before the ledger
    table existed, and a re-run must not buy them again."""
    if not game_ids:
        return set()
    have: set[str] = set()
    for i in range(0, len(game_ids), 500):
        chunk = game_ids[i:i + 500]
        have |= {r[0] for r in conn.execute(
            "SELECT DISTINCT game_id FROM odds WHERE game_id = ANY(%s) AND source = %s",
            (chunk, SOURCE)).fetchall()}
    try:
        have |= {r[0] for r in conn.execute(
            "SELECT game_id FROM nhl_derivative_odds_pulls WHERE game_id = ANY(%s)",
            (game_ids,)).fetchall()}
    except Exception:  # noqa: BLE001 — the ledger is created on --apply, not before
        conn.rollback()
    return have


def _ensure_ledger(conn) -> None:
    conn.execute(LEDGER_DDL)
    lock_down(conn, "nhl_derivative_odds_pulls")
    conn.commit()


def pull_date(conn, meter: Meter, game_date: str, games: list[dict],
              limit: int | None = None, apply: bool = True) -> dict:
    """One snapshot for the date, then one odds call per game.

    `limit` is only the dry-run probe (three games, so the measured cost is a
    sample). `--apply` passes None and buys every matched game on the date.
    """
    snap = (min(g["start"] for g in games) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = meter.get(f"{BASE}/events", {"date": snap})
    if r is None or r.status_code != 200:
        return {"date": game_date, "error": getattr(r, "status_code", "network"), "events": 0, "rows": 0}
    from data.ingestors.odds_ingestor import _normalize_team
    by_teams = {(g["away"], g["home"]): g for g in games}
    stats = {"date": game_date, "snapshot": snap, "events": 0, "rows": 0, "books": defaultdict(set)}
    for ev in (r.json().get("data") or []):
        # Match on the teams. The event list is UTC, so a late ET start is
        # already the next UTC date; the game row's own date is what we store.
        key = (_normalize_team(ev.get("away_team", ""), "NHL"),
               _normalize_team(ev.get("home_team", ""), "NHL"))
        g = by_teams.get(key)
        if g is None:
            continue
        if limit is not None and stats["events"] >= limit:
            break
        resp = meter.get(f"{BASE}/events/{ev['id']}/odds", {
            "date": snap, "markets": ",".join(MARKETS), "bookmakers": ",".join(BOOKS),
            "oddsFormat": "american", "dateFormat": "iso"})
        if resp is None or resp.status_code != 200:
            logger.warning(f"  {g['game_id']}: HTTP {getattr(resp, 'status_code', 'network')}")
            continue
        body = resp.json()
        stamp = body.get("timestamp") or snap
        rows = []
        for book in (body.get("data") or {}).get("bookmakers", []):
            parsed = parse_markets(book.get("markets") or [], g["home"], g["away"])
            for p in parsed:
                rows.append(_blank_row(g["game_id"], book.get("key", ""), stamp, p, g["start"]))
                stats["books"][p["market"]].add(book.get("key", ""))
        stats["events"] += 1
        if apply:
            if rows:
                _insert_odds(conn, rows)
            conn.execute("""
                INSERT INTO nhl_derivative_odds_pulls (game_id, game_date, pulled_at, rows)
                VALUES (%s, %s, NOW(), %s)
                ON CONFLICT (game_id) DO UPDATE SET pulled_at = NOW(), rows = EXCLUDED.rows
            """, (g["game_id"], game_date, len(rows)))
            conn.commit()
        stats["rows"] += len(rows)
    stats["books"] = {k: sorted(v) for k, v in stats["books"].items()}
    return stats


def format_plan(n_dates: int, n_games: int, n_done: int) -> str:
    est = estimate_credits(n_games, n_dates)
    return (f"{n_dates:,} dates / {n_games:,} games to buy "
            f"({n_done:,} games already stored, skipped)\n"
            f"ESTIMATE (not measured): {n_games:,} games x {10 * len(MARKETS)} credits "
            f"if all {len(MARKETS)} markets return, plus {n_dates:,} for the event lists "
            f"= {est:,}. The feed bills 10 per market returned, so a game missing one "
            f"market costs less.\n"
            f"no credit ceiling — --apply buys every game above")


def _print_measured(stats: dict, meter: Meter, day: str | None = None) -> None:
    """Print the credits the probe's responses actually billed."""
    events = stats.get("events") or 0
    per = (meter.spent - 1) / events if events else float("nan")
    label = f"MEASURED probe {day}" if day else "MEASURED"
    print(stats)
    print(f"{label}: {meter.spent} credits for {events} games + 1 event list "
          f"-> {per:.1f} per game; remaining {meter.remaining}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--probe", metavar="DATE", help="3 games on one date; writes nothing")
    ap.add_argument("--seasons", nargs=2, type=int, default=list(SEASONS))
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    if (a.apply or a.probe) and not config.ODDS_API_KEY:
        print("REFUSED: ODDS_API_KEY is not set. nothing spent.")
        return

    conn = get_connection()
    try:
        if a.probe:
            season = int(a.probe[:4]) + (1 if int(a.probe[5:7]) >= 9 else 0)
            games = _games_by_date(conn, season, season).get(a.probe, [])
            if not games:
                print(f"no scored NHL games on {a.probe}")
                return
            meter = Meter()
            _print_measured(pull_date(conn, meter, a.probe, games, limit=3, apply=False), meter)
            return

        by_date = _games_by_date(conn, *a.seasons)
        ids = [g["game_id"] for games in by_date.values() for g in games]
        done = _done_ids(conn, ids)
        todo = {}
        for d, games in by_date.items():
            left = [g for g in games if g["game_id"] not in done]
            if left:
                todo[d] = left
        dates = sorted(todo, reverse=True)
        n_games = sum(len(todo[d]) for d in dates)
        print(format_plan(len(dates), n_games, len(done)))
        if not a.apply:
            if config.ODDS_API_KEY and dates:
                day = dates[0]
                meter = Meter()
                _print_measured(
                    pull_date(conn, meter, day, todo[day], limit=3, apply=False), meter, day)
            elif not config.ODDS_API_KEY:
                print("probe not run: ODDS_API_KEY is not set. nothing spent.")
            print("nothing spent. Re-run with --apply.")
            return

        _ensure_ledger(conn)
        meter = Meter()
        rows = games_done = 0
        for d in dates:
            s = pull_date(conn, meter, d, todo[d])
            rows += s.get("rows", 0)
            games_done += s.get("events", 0)
            logger.info(f"{d}: {s.get('events')} games, {s.get('rows')} rows | spent {meter.spent:,}")
        print(f"bought {games_done:,} games, {rows:,} rows, spent {meter.spent:,} credits; "
              f"feed says {meter.remaining} remain")
    finally:
        try:
            persist_quota(conn)
        finally:
            conn.close()


if __name__ == "__main__":
    main()
