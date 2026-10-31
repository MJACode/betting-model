"""Historical NBA game lines and player props from The Odds API.

WHY. Supabase held no NBA price before the 2026-27 season (measured
2026-10-15: `odds` empty for every past NBA game, `player_prop_odds` empty on
every sampled past date, `odds_history_pulls` MLB/NCAAF/NHL only). Without a
price no NBA model can be graded against a real line -- which is why
`nba_over_under` and `nba_spread` were never trained, and why every old NBA
"holdout" was an accuracy figure. mike, 2026-10-15: "pre-approve pull whatever
odds api data is needed".

WHAT IS BOUGHT (cost MEASURED on 2026-10-15 from x-requests-last):

  --lines  The bulk /historical/sports/basketball_nba/odds endpoint, h2h +
           spreads + totals, the ten fetched books (config.LINE_SHOP_BOOKMAKERS;
           ten names bill as one region): 30 credits a snapshot for the whole
           slate. For every ET game date D, snapshots at 22Z the evening before
           (the opener), 15Z, 19Z, 22Z, 23Z on D, and 00Z-03Z on D+1 -- so every
           game has a price within an hour of its own tip whatever time it
           starts. Featured markets exist from 2020-06-06. Rows land in `odds`
           with source 'odds_api_historical' (the pruner protects it), resumable
           through `odds_history_pulls` (sport, snapshot_date, hour_utc).

  --derivatives  The per-event endpoint, first-half and first-quarter
           moneyline / spread / total plus team totals (7 markets, ~70 credits
           a game), one snapshot at tip minus `--lead-min`. Rows land in `odds`
           with source 'odds_api_nba_derivative_history'; team totals split into
           `team_totals_home` / `team_totals_away` (the NHL shape).

  --props  The per-event endpoint, 14 player markets requested (13 returned
           on the probe: 130 credits a game), ONE snapshot per game at its own
           tip minus `--lead-min` (default 60). Props are sold from 2023-05-03.
           Rows land in `player_prop_odds`; a game already holding NBA
           player_points rows is skipped, so a re-run buys nothing twice.
           The event list (1 credit a date) also gives each game's start, which
           fills `games.commence_time` where it is NULL.

  --extra-hours / --fill-gaps  (2026-10-17, the second game-market search,
           docs/nba_models_2026.md §6.5.) More hours on every game date, and
           tip-relative fetches -- tip - 60 and tip - 240, the 5-minute snapshot
           at or before -- for every game whose decision windows no held fetch
           reaches. Same bulk endpoint and price as --lines. A fetch off the hour
           is ledgered in `odds_history_fetches` (sport, requested_at).

THE FLOOR. Last month the credit balance hit 0 on 09-26 and every live feed
stopped until the 10-01 reset. Every response carries x-requests-remaining, and
the run stops the moment it reads below `--floor` (default 2,200,000: October's
measured live burn of 63-85k a day, projected at 85k to 10-19 and 120k a day
once the NBA season adds its load, is ~1.78M to the 11-01 reset). NEWEST SEASON
FIRST, so a stop leaves the most relevant data stored.

Only games already in `games` are written: a preseason or playoff event the
feed lists is counted and skipped, never minted as a game row.

    python -m data.ingestors.nba_odds_history --lines --seasons 2021 2026 --max-credits 300000 --apply
    python -m data.ingestors.nba_odds_history --props --seasons 2024 2026 --max-credits 520000 --apply
    python -m data.ingestors.nba_odds_history --lines --extra-hours 16 17 18 20 21 28         --fill-gaps --season-order 2022 2023 2024 2025 2026 2021         --seasons 2021 2026 --max-credits 300000 --apply
"""
from __future__ import annotations

import argparse
import bisect
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from loguru import logger

import config
from data.anon_readable import lock_down
from data.db import get_connection
from data.ingestors.odds_ingestor import (HISTORICAL_ODDS_SOURCE, NBA_ODDS_API_MAP,
                                          PULL_LEDGER_DDL, _insert_odds, _mark_in_play,
                                          _name_key, _normalize_team, _parse_outcomes,
                                          _parse_spread_outcomes, _parse_total_outcomes,
                                          _process_events)
from data.ingestors.odds_quota import persist_quota, record_quota_headers
from data.ingestors.prop_odds_ingestor import _insert_prop_odds, _parse_prop_markets

BASE = "https://api.the-odds-api.com/v4/historical/sports/basketball_nba"
BOOKS = ",".join(config.LINE_SHOP_BOOKMAKERS[:10])
LINE_MARKETS = ["h2h", "spreads", "totals"]
PROP_MARKETS = ["player_points", "player_rebounds", "player_assists", "player_threes",
                "player_points_rebounds_assists", "player_points_rebounds",
                "player_points_assists", "player_rebounds_assists", "player_blocks",
                "player_steals", "player_blocks_steals", "player_turnovers",
                "player_double_double", "player_triple_double"]
YES_NO = {"player_double_double", "player_triple_double"}
# Half, quarter and team totals: 7 markets, ~70 credits a game. Settled on the
# period line scores, never on the full-game score.
DERIV_MARKETS = ["team_totals", "spreads_h1", "totals_h1", "h2h_h1",
                 "spreads_q1", "totals_q1", "h2h_q1"]
DERIV_SOURCE = "odds_api_nba_derivative_history"
# Every book's alternate ladder: each rung a row (2026-10-21, mike: "I want the game market
# models"; docs/nba_models_2026.md section 10). 30 credits a game at ten books, measured on
# one 2025-01-15 call (x-requests-last). The feed holds these from 2023-05-03, like props.
ALT_MARKETS = ["alternate_spreads", "alternate_totals", "alternate_team_totals"]
ALT_SOURCE = "odds_api_nba_alt_history"
# The marker a re-run reads back. Game lines resume on odds_history_pulls and
# props on the game's stored player_points rows (player_prop_odds has no source
# column); the derivative rows carry this.
SOURCE_PREFIX = DERIV_SOURCE
FIRST_LINES_DATE = "2020-06-06"     # the feed's first featured-market snapshot
FIRST_PROPS_DATE = "2023-05-03"     # the feed's first player-prop snapshot
DEFAULT_FLOOR = 2_200_000
# Fetches OFF the hour (a gap fill at 23:30Z). odds_history_pulls keys on an
# integer hour and cannot hold one; see _buy_snapshot for the routing rule.
# The NCAAB opener grid files its half hours here too (sport 'NCAAB', why
# 'opener_grid', data/ingestors/ncaab_odds_history.py); every NBA read of this
# table filters on sport = 'NBA'.
FETCH_LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS odds_history_fetches (
    sport        TEXT NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL,
    snapshot_ts  TIMESTAMPTZ,
    why          TEXT NOT NULL,
    pulled_at    TIMESTAMPTZ NOT NULL,
    rows         INTEGER NOT NULL,
    PRIMARY KEY (sport, requested_at)
)
"""
ET = ZoneInfo("America/New_York")


class Meter:
    """Credits actually billed, and the balance, read off every response."""

    def __init__(self, ceiling: int, floor: int):
        self.ceiling, self.floor = ceiling, floor
        self.spent, self.remaining = 0, None

    RETRY_STATUS = (429, 500, 502, 503, 504)

    def get(self, url: str, params: dict):
        """One call, retried on a network error and on a rate-limit or server answer
        (RETRY_STATUS), with a growing pause; every answer's billing headers are counted."""
        r = None
        for attempt in range(5):
            try:
                r = requests.get(url, params={**params, "apiKey": config.ODDS_API_KEY},
                                 timeout=90)
            except requests.RequestException as exc:
                logger.warning(f"network: {type(exc).__name__}; retry {attempt + 1}")
                time.sleep(3 * (attempt + 1))
                continue
            record_quota_headers(r)
            self.spent += int(float(r.headers.get("x-requests-last") or 0))
            rem = r.headers.get("x-requests-remaining")
            if rem is not None:
                self.remaining = int(float(rem))
            if r.status_code in self.RETRY_STATUS and attempt < 4:
                logger.warning(f"HTTP {r.status_code}; retry {attempt + 1}")
                time.sleep(5 * (attempt + 1))
                continue
            break
        time.sleep(0.2)
        return r

    def stop_reason(self, next_cost: int) -> str | None:
        if self.spent + next_cost > self.ceiling:
            return f"ceiling {self.ceiling:,} (spent {self.spent:,})"
        if self.remaining is not None and self.remaining - next_cost < self.floor:
            return f"floor {self.floor:,} (balance {self.remaining:,})"
        return None


def _known_games(conn, first_season: int, last_season: int) -> dict[str, dict]:
    rows = conn.execute("""
        SELECT game_id, game_date, home_team, away_team, commence_time
          FROM games WHERE sport = 'NBA' AND season BETWEEN %s AND %s
           AND home_score IS NOT NULL
    """, (first_season, last_season)).fetchall()
    return {r[0]: {"game_id": r[0], "game_date": str(r[1])[:10], "home": r[2],
                   "away": r[3], "commence_time": r[4]} for r in rows}


def _write_with_retry(conn, write, what: str, attempts: int = 4) -> bool:
    """Run one unit of writes; on a dropped connection, run the whole unit again.

    The rows were PAID for, so a lost commit must not lose them. data.db raises
    ConnectionLost when the server drops a transaction holding uncommitted writes
    (it has already reconnected), which is exactly the case to replay: the first
    attempt's rows never landed. A 2026-10-15 network blip killed a purchase
    process this way before this existed."""
    import psycopg2
    from data.db import ConnectionLost
    for i in range(attempts):
        try:
            write()
            return True
        except (ConnectionLost, psycopg2.errors.QueryCanceled) as exc:
            # A statement timeout means a lock was held -- on 2026-10-15 by this
            # job's own transaction orphaned by the same network blip. Roll back
            # and replay; the orphan is gone or the attempts run out.
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001
                pass
            logger.warning(f"{what}: {str(exc)[:80]}; replaying the write ({i + 1}/{attempts})")
            time.sleep(5 * (i + 1))
    logger.error(f"{what}: write failed {attempts} times; not marked stored, a re-run buys it")
    return False


# ── game lines ──────────────────────────────────────────────────────────────

def line_snapshots(game_dates: list[str],
                   extra_hours: tuple[int, ...] = ()) -> list[tuple[str, int]]:
    """(UTC date, hour) pairs covering every ET game date, newest first.

    NBA tips run 23:00Z to ~03:30Z, so a game dated D (Eastern) is priced near
    its own start by one of D 22Z/23Z or D+1 00Z-03Z; 15Z and 19Z give the
    day's path and D-1 22Z the overnight opener.

    `extra_hours` adds hours counted from midnight UTC on D: 16 is D 16Z, 28 is
    D+1 04Z, -2 is D-1 22Z. The second game-market search (docs/nba_models_2026.md
    §6.5) buys 16, 17, 18, 20, 21 and 28 so afternoon and late tips have a price
    in their own last hour."""
    pairs: set[tuple[str, int]] = set()
    for d in game_dates:
        day = date.fromisoformat(d)
        nxt, prv = (day + timedelta(days=1)).isoformat(), (day - timedelta(days=1)).isoformat()
        pairs |= {(d, 15), (d, 19), (d, 22), (d, 23), (prv, 22),
                  (nxt, 0), (nxt, 1), (nxt, 2), (nxt, 3)}
        for h in extra_hours:
            at = datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(hours=h)
            pairs.add((at.date().isoformat(), at.hour))
    return sorted(pairs, reverse=True)


def _buy_snapshot(conn, meter: Meter, games: dict, when: datetime, stats: dict,
                  why: str = "hourly") -> bool:
    """Buy the whole slate at `when`, write it and its ledger row. False = stop.

    On the hour it is ledgered in odds_history_pulls (sport, date, hour), the
    shape every earlier purchase used; off the hour in odds_history_fetches,
    keyed on the instant -- an integer hour cannot hold 23:30Z, and a :30 fetch
    filed as hour 23 would read as the :00 one and never be bought (or the
    reverse). One routing rule, so a gap fill landing on an hour the hourly
    plan also wants is bought once."""
    on_hour = when.minute == 0 and when.second == 0
    snap_date, hour = when.date().isoformat(), when.hour
    if on_hour:
        held = conn.execute("SELECT 1 FROM odds_history_pulls WHERE sport = 'NBA' "
                            "AND snapshot_date = %s AND hour_utc = %s",
                            (snap_date, hour)).fetchone()
    else:
        held = conn.execute("SELECT 1 FROM odds_history_fetches WHERE sport = 'NBA' "
                            "AND requested_at = %s", (when,)).fetchone()
    if held:
        conn.commit()
        stats["skipped_by_sibling"] += 1
        return True
    stop = meter.stop_reason(30)
    if stop:
        stats["stopped"] = stop
        logger.warning(f"lines stopping at {when:%Y-%m-%d %H:%M}Z: {stop}")
        return False
    snapshot_at = when.strftime("%Y-%m-%dT%H:%M:%SZ")
    r = meter.get(f"{BASE}/odds", {"date": snapshot_at, "markets": ",".join(LINE_MARKETS),
                                   "bookmakers": BOOKS, "oddsFormat": "american"})
    if r is None or r.status_code != 200:
        stats["errors"] += 1
        logger.warning(f"lines {snapshot_at}: HTTP {getattr(r, 'status_code', 'network')}")
        return True
    body = r.json()
    events = body.get("data") or []
    game_rows, odds_rows = _process_events(events, "NBA", "open", snapshot_at)
    for row in odds_rows:
        row["source"] = HISTORICAL_ODDS_SOURCE
    stats["marked_in_play"] += _mark_in_play(game_rows, odds_rows)
    keep = [o for o in odds_rows if o["game_id"] in games]
    stats["skipped_unknown_games"] += len({o["game_id"] for o in odds_rows
                                           if o["game_id"] not in games})
    starts = [(g["commence_time"], g["game_id"]) for g in game_rows
              if g["game_id"] in games and g.get("commence_time")]

    def _write():
        if keep:
            _insert_odds(conn, keep)
        # commence_time where it is missing, and nothing else
        if starts:
            conn.executemany("UPDATE games SET commence_time = %s WHERE game_id = %s "
                             "AND commence_time IS NULL", starts)
        if on_hour:
            conn.execute("""
                INSERT INTO odds_history_pulls (sport, snapshot_date, hour_utc, pulled_at, rows)
                VALUES ('NBA', %s, %s, NOW(), %s)
                ON CONFLICT (sport, snapshot_date, hour_utc) DO UPDATE
                   SET pulled_at = NOW(), rows = EXCLUDED.rows
            """, (snap_date, hour, len(keep)))
        else:
            conn.execute("""
                INSERT INTO odds_history_fetches
                       (sport, requested_at, snapshot_ts, why, pulled_at, rows)
                VALUES ('NBA', %s, %s, %s, NOW(), %s)
                ON CONFLICT (sport, requested_at) DO UPDATE
                   SET snapshot_ts = EXCLUDED.snapshot_ts, pulled_at = NOW(),
                       rows = EXCLUDED.rows
            """, (when, body.get("timestamp"), why, len(keep)))
        conn.commit()

    if not _write_with_retry(conn, _write, f"lines {snapshot_at}"):
        stats["errors"] += 1
        return True
    stats["odds_rows"] += len(keep)
    stats["calls"] += 1
    if stats["calls"] % 50 == 0:
        logger.info(f"lines {snapshot_at}: {stats['calls']} calls, {stats['odds_rows']:,} rows, "
                    f"spent {meter.spent:,}, balance {meter.remaining}")
    return True


def _ensure_ledgers(conn) -> None:
    conn.execute(PULL_LEDGER_DDL)
    lock_down(conn, "odds_history_pulls")
    conn.execute(FETCH_LEDGER_DDL)
    lock_down(conn, "odds_history_fetches")
    conn.commit()


def buy_lines(conn, meter: Meter, first_season: int, last_season: int,
              oldest_first: bool = False, extra_hours: tuple[int, ...] = ()) -> dict:
    _ensure_ledgers(conn)
    games = _known_games(conn, first_season, last_season)
    dates = sorted({g["game_date"] for g in games.values()
                    if g["game_date"] >= FIRST_LINES_DATE})
    pairs = line_snapshots(dates, extra_hours)
    if oldest_first:
        # A second process over the same season walks the other way; the
        # per-snapshot ledger check below is what stops them double-buying
        # where they meet.
        pairs = pairs[::-1]
    done = {(r[0], int(r[1])) for r in conn.execute(
        "SELECT snapshot_date, hour_utc FROM odds_history_pulls WHERE sport = 'NBA'").fetchall()}
    todo = [p for p in pairs if p not in done]
    logger.info(f"lines: {len(dates)} game dates -> {len(pairs)} snapshots, "
                f"{len(pairs) - len(todo)} already stored, {len(todo)} to buy "
                f"(~{30 * len(todo):,} credits)")
    stats = defaultdict(int)
    for snap_date, hour in todo:
        when = datetime.fromisoformat(f"{snap_date}T{hour:02d}:00:00+00:00")
        if not _buy_snapshot(conn, meter, games, when, stats):
            break
    return dict(stats)


# ── tip-relative gap fill ───────────────────────────────────────────────────
#
# The second game-market search grades four decision points per game, each the
# NEWEST fetch inside a window before tip (docs/nba_models_2026.md §6.2). The
# hourly plan reaches every window for a tip on the hour; for a 7:30 ET tip
# (00:30Z) the fetches sit at lead 30 and 90 and NONE lands in 45-75. Measured
# 2026-10-17 on the cached archive, full-game markets only: the 45-75 window is
# reached on 93% of :00 tips and 3% of the 2,195 :30 tips, every season. One
# fetch at tip - 60 closes both the 45-75 and the 60-180 windows; tip - 240
# closes 3-6 h.
GAP_WINDOWS = {"B": (180, 360, 240), "C": (60, 180, 60), "D": (45, 75, 60)}


def _held_fetches(conn) -> list[datetime]:
    """Every NBA fetch instant already bought, from both ledgers."""
    out = [datetime.fromisoformat(f"{d}T{int(h):02d}:00:00+00:00") for d, h in conn.execute(
        "SELECT snapshot_date, hour_utc FROM odds_history_pulls WHERE sport = 'NBA'").fetchall()]
    out += [t if t.tzinfo else t.replace(tzinfo=timezone.utc) for (t,) in conn.execute(
        "SELECT requested_at FROM odds_history_fetches WHERE sport = 'NBA'").fetchall()]
    return out


def gap_instants(tips: list[datetime], held: list[datetime],
                 windows: dict = GAP_WINDOWS) -> list[datetime]:
    """The fetch instants that put every tip in every window, none already held.

    A window (lo, hi, aim) is reached when a held fetch sits lo..hi minutes
    before tip; a tip that misses it asks for tip - aim, rounded down to five
    minutes (the feed's snapshot spacing). Pure, so the plan is testable."""
    have = sorted(set(held))
    want: set[datetime] = set()
    for tip in sorted(tips):
        for lo, hi, aim in windows.values():
            i = bisect.bisect_left(have, tip - timedelta(minutes=hi))
            j = bisect.bisect_right(have, tip - timedelta(minutes=lo))
            if j > i:
                continue
            at = tip - timedelta(minutes=aim)
            at = at.replace(minute=at.minute - at.minute % 5, second=0, microsecond=0)
            want.add(at)
            # a fetch planned for one game serves every other game it reaches
            bisect.insort(have, at)
    return sorted(want)


def buy_gaps(conn, meter: Meter, first_season: int, last_season: int,
             season_order: list[int] | None = None) -> dict:
    """Fill every decision window for every game, choosing seasons first.

    `season_order` decides what a floor stop leaves unbought: the seasons cuts
    are chosen on come first, the confirmation season next, 2020-21 last."""
    _ensure_ledgers(conn)
    games = _known_games(conn, first_season, last_season)
    season_of = {r[0]: int(r[1]) for r in conn.execute(
        "SELECT game_id, season FROM games WHERE sport = 'NBA' AND season BETWEEN %s AND %s",
        (first_season, last_season)).fetchall()}
    tips_by_season: dict[int, list[datetime]] = defaultdict(list)
    for g in games.values():
        ct = g.get("commence_time")
        if not ct or g["game_date"] < FIRST_LINES_DATE:
            continue
        t = ct if isinstance(ct, datetime) else datetime.fromisoformat(str(ct).replace("Z", "+00:00"))
        tips_by_season[season_of[g["game_id"]]].append(t.astimezone(timezone.utc))
    held = _held_fetches(conn)
    order = season_order or sorted(tips_by_season, reverse=True)
    plan = [(s, at) for s in order for at in gap_instants(tips_by_season.get(s, []), held)]
    seen: set[datetime] = set()
    plan = [(s, at) for s, at in plan if not (at in seen or seen.add(at))]
    per = {s: sum(1 for x, _ in plan if x == s) for s in order}
    logger.info(f"gaps: {len(plan)} fetches to buy (~{30 * len(plan):,} credits), by season {per}")
    stats = defaultdict(int)
    for s, at in plan:
        if not _buy_snapshot(conn, meter, games, at, stats, why=f"gap_fill_{s}"):
            break
    return dict(stats)


def read_instants(path) -> list[datetime]:
    """The request times a plan file names (scripts/nba_news_window_plan.py), newest
    first, each on a whole minute (a plan asks one minute past each 5-minute mark, because
    the feed returns the latest snapshot at or before the request). A malformed instant
    stops the read."""
    import json
    from pathlib import Path
    body = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for raw in body["instants"]:
        t = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if t.tzinfo is None or t.second or t.microsecond:
            raise ValueError(f"plan instant {raw!r} is not a UTC time on a whole minute")
        out.append(t.astimezone(timezone.utc))
    return sorted(set(out), reverse=True)


def buy_instants(conn, meter: Meter, first_season: int, last_season: int,
                 path, why: str) -> dict:
    """Buy the whole slate at every instant the plan file names (docs/nba_models_2026.md
    section 11), newest first. _buy_snapshot ledgers each one (odds_history_fetches off the
    hour, odds_history_pulls on it) and skips an instant either ledger already holds, so a
    re-run after an interruption buys only what is missing."""
    _ensure_ledgers(conn)
    games = _known_games(conn, first_season, last_season)
    plan = read_instants(path)
    held = set(_held_fetches(conn))
    todo = [t for t in plan if t not in held]
    logger.info(f"instants ({why}): {len(plan)} in the plan, {len(plan) - len(todo)} held, "
                f"{len(todo)} to buy (~{30 * len(todo):,} credits)")
    stats = defaultdict(int)
    failed = []
    for at in todo:
        before = stats["errors"]
        if not _buy_snapshot(conn, meter, games, at, stats, why=why):
            return dict(stats)
        if stats["errors"] > before:
            failed.append(at)
    # one more pass over every instant that got no usable answer, under the same meter
    stats["retried"] = len(failed)
    for at in failed:
        before = stats["errors"]
        if not _buy_snapshot(conn, meter, games, at, stats, why=why):
            break
        if stats["errors"] > before:
            stats["still_failed"] += 1
    return dict(stats)


# ── player props ────────────────────────────────────────────────────────────

def _props_done(conn, game_ids: list[str]) -> set[str]:
    """Asked BY GAME ID: player_prop_odds is ~60M rows indexed on game_id first."""
    have: set[str] = set()
    for i in range(0, len(game_ids), 500):
        have |= {r[0] for r in conn.execute(
            "SELECT DISTINCT game_id FROM player_prop_odds "
            "WHERE game_id = ANY(%s) AND market = 'player_points'",
            (game_ids[i:i + 500],)).fetchall()}
    return have


def buy_props_date(conn, meter: Meter, game_date: str, games: list[dict],
                   lead_min: int, apply: bool = True, limit: int | None = None) -> dict:
    stats = {"date": game_date, "events": 0, "prop_rows": 0, "markets": defaultdict(set)}
    # The event list at noon Eastern lists the whole slate with its starts.
    noon = datetime.fromisoformat(f"{game_date}T12:00:00").replace(tzinfo=ET)
    r = meter.get(f"{BASE}/events", {"date": noon.astimezone(timezone.utc)
                                     .strftime("%Y-%m-%dT%H:%M:%SZ")})
    if r is None or r.status_code != 200:
        stats["error"] = getattr(r, "status_code", "network")
        return stats
    by_teams = {(g["away"], g["home"]): g for g in games}
    for ev in (r.json().get("data") or []):
        start = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
        if start.astimezone(ET).date().isoformat() != game_date:
            continue
        g = by_teams.get((_normalize_team(ev.get("away_team", ""), "NBA"),
                          _normalize_team(ev.get("home_team", ""), "NBA")))
        if g is None:
            stats.setdefault("unmatched", []).append(f"{ev.get('away_team')} @ {ev.get('home_team')}")
            continue
        if g.get("done"):
            continue
        if limit is not None and stats["events"] >= limit:
            break
        why = meter.stop_reason(10 * len(PROP_MARKETS))
        if why:
            stats["stopped"] = why
            break
        if apply and not g.get("commence_time"):
            conn.execute("UPDATE games SET commence_time = %s WHERE game_id = %s "
                         "AND commence_time IS NULL",
                         (start.astimezone(timezone.utc).isoformat(), g["game_id"]))
        snap = (start - timedelta(minutes=lead_min)).strftime("%Y-%m-%dT%H:%M:%SZ")
        resp = meter.get(f"{BASE}/events/{ev['id']}/odds", {
            "date": snap, "markets": ",".join(PROP_MARKETS), "bookmakers": BOOKS,
            "oddsFormat": "american"})
        if resp is None or resp.status_code != 200:
            logger.warning(f"  {g['game_id']}: HTTP {getattr(resp, 'status_code', 'network')}")
            continue
        body = resp.json()
        stamp = body.get("timestamp") or snap
        stats["events"] += 1
        rows = []
        for book in (body.get("data") or {}).get("bookmakers", []):
            bk = book.get("key", "")
            mkts = [m for m in book.get("markets", []) if m.get("key") in PROP_MARKETS]
            # A triple-double is Yes/No with no number, like the double-double
            # the shared parser already defaults; without a line it is dropped.
            for m in mkts:
                if m.get("key") in YES_NO:
                    for o in m.get("outcomes", []):
                        o.setdefault("point", 0.5)
            got = _parse_prop_markets(mkts, game_id=g["game_id"], game_date=game_date,
                                      snapshot_type="open", snapshot_at=stamp,
                                      allowed_markets=PROP_MARKETS, bookmaker=bk)
            rows += got
            for row in got:
                stats["markets"][row["market"]].add(bk)
        if apply and rows:
            def _write(rows=rows):
                _insert_prop_odds(conn, rows)
                conn.commit()
            if _write_with_retry(conn, _write, g["game_id"]):
                stats["prop_rows"] += len(rows)
        else:
            stats["prop_rows"] += len(rows)
    if apply:
        conn.commit()
    stats["markets"] = {k: sorted(v) for k, v in stats["markets"].items()}
    return stats


def buy_props(conn, meter: Meter, first_season: int, last_season: int, lead_min: int) -> dict:
    games = _known_games(conn, first_season, last_season)
    games = {k: v for k, v in games.items() if v["game_date"] >= FIRST_PROPS_DATE}
    done = _props_done(conn, list(games))
    for gid in done:
        games[gid]["done"] = True
    by_date: dict[str, list[dict]] = defaultdict(list)
    for g in games.values():
        by_date[g["game_date"]].append(g)
    todo = sorted((d for d, gs in by_date.items() if not all(g.get("done") for g in gs)),
                  reverse=True)
    n = sum(1 for d in todo for g in by_date[d] if not g.get("done"))
    logger.info(f"props: {len(games)} games since {FIRST_PROPS_DATE}, {len(done)} stored, "
                f"{n} to buy on {len(todo)} dates (~{130 * n:,} credits)")
    totals = defaultdict(int)
    for d in todo:
        s = buy_props_date(conn, meter, d, by_date[d], lead_min)
        totals["events"] += s["events"]
        totals["prop_rows"] += s["prop_rows"]
        if s.get("unmatched"):
            totals["unmatched"] += len(s["unmatched"])
            logger.warning(f"{d}: unmatched events {s['unmatched']}")
        logger.info(f"props {d}: {s['events']} games, {s['prop_rows']} rows | "
                    f"spent {meter.spent:,}, balance {meter.remaining}")
        if s.get("stopped"):
            totals["stopped"] = s["stopped"]
            logger.warning(f"props stopping at {d}: {s['stopped']}")
            break
    return dict(totals)


# -- first half / first quarter / team totals ---------------------------------

def _nba_abbrev(name: str) -> str | None:
    if not name:
        return None
    if name in NBA_ODDS_API_MAP:
        return NBA_ODDS_API_MAP[name]
    key = _name_key(name)
    return next((v for k, v in NBA_ODDS_API_MAP.items() if _name_key(k) == key), None)


def parse_derivatives(book_markets: list[dict], home_name: str, home: str, away: str) -> list[dict]:
    """One `odds`-shaped dict per (market, line) for one book."""
    rows = []
    for m in book_markets:
        key, outs = m.get("key"), m.get("outcomes") or []
        if key in ("h2h_h1", "h2h_q1"):
            p = _parse_outcomes(outs, "NBA", home_name)
            if p.get("home_price") is not None and p.get("away_price") is not None:
                rows.append({"market": key, **p})
        elif key in ("spreads_h1", "spreads_q1"):
            p = _parse_spread_outcomes(outs, home_name)
            if p.get("spread_home") is not None:
                rows.append({"market": key, **p})
        elif key in ("totals_h1", "totals_q1"):
            p = _parse_total_outcomes(outs)
            if p.get("total_line") is not None:
                rows.append({"market": key, **p})
        elif key == "team_totals":
            slots: dict[tuple, dict] = {}
            for o in outs:
                name, desc = (o.get("name") or ""), (o.get("description") or "")
                side, team = (name, desc) if name.lower() in ("over", "under") else (desc, name)
                if side.lower() not in ("over", "under") or o.get("point") is None:
                    continue
                ab = _nba_abbrev(team)
                stored = ("team_totals_home" if ab == home else
                          "team_totals_away" if ab == away else None)
                if stored is None:
                    continue
                slot = slots.setdefault((stored, float(o["point"])), {})
                slot[side.lower() + "_price"] = o.get("price")
            for (stored, pt), slot in slots.items():
                rows.append({"market": stored, "total_line": pt,
                             "over_price": slot.get("over_price"),
                             "under_price": slot.get("under_price")})
    return rows


def parse_alternates(book_markets: list[dict], home_name: str, home: str, away: str) -> list[dict]:
    """One `odds`-shaped dict per rung for one book's alternate ladders.

    alternate_spreads: the home outcome at point p pairs with the away outcome at -p, stored
    as spread_home = p (the HOME number, CLAUDE.md section 4) with both prices.
    alternate_totals: over and under at the same point. alternate_team_totals: over and under
    at the same point for one team, stored as alternate_team_totals_home / _away.
    A rung missing either side is not stored."""
    rows = []
    hkey = _name_key(home_name)
    for m in book_markets:
        key, outs = m.get("key"), m.get("outcomes") or []
        n0 = len(rows)
        if key == "alternate_spreads":
            home_at, away_at = {}, {}
            for o in outs:
                if o.get("point") is None or o.get("price") is None:
                    continue
                is_home = _name_key(o.get("name") or "") == hkey
                (home_at if is_home else away_at)[float(o["point"])] = o["price"]
            for p, hp in home_at.items():
                ap = away_at.get(-p)
                if ap is not None:
                    rows.append({"market": key, "spread_home": p, "home_price": hp, "away_price": ap})
        elif key == "alternate_totals":
            slots: dict[float, dict] = {}
            for o in outs:
                side = (o.get("name") or "").lower()
                if side in ("over", "under") and o.get("point") is not None:
                    slots.setdefault(float(o["point"]), {})[side + "_price"] = o.get("price")
            for pt, s in slots.items():
                if s.get("over_price") is not None and s.get("under_price") is not None:
                    rows.append({"market": key, "total_line": pt, **s})
        elif key == "alternate_team_totals":
            slots = {}
            for o in outs:
                name, desc = (o.get("name") or ""), (o.get("description") or "")
                side, team = (name, desc) if name.lower() in ("over", "under") else (desc, name)
                if side.lower() not in ("over", "under") or o.get("point") is None:
                    continue
                ab = _nba_abbrev(team)
                stored = ("alternate_team_totals_home" if ab == home else
                          "alternate_team_totals_away" if ab == away else None)
                if stored is None:
                    continue
                slots.setdefault((stored, float(o["point"])), {})[side.lower() + "_price"] = o.get("price")
            for (stored, pt), s in slots.items():
                if s.get("over_price") is not None and s.get("under_price") is not None:
                    rows.append({"market": stored, "total_line": pt, **s})
        if m.get("last_update"):
            # the market's own update stamp, as the main-line archive keeps the book's
            # (docs/nba_models_2026.md 10.3): a ladder older than the purchase is visible
            for r in rows[n0:]:
                r["snapshot_at"] = m["last_update"]
    return rows


def _alt_done(conn, game_ids: list[str]) -> set[str]:
    have: set[str] = set()
    for i in range(0, len(game_ids), 500):
        have |= {r[0] for r in conn.execute(
            "SELECT DISTINCT game_id FROM odds WHERE game_id = ANY(%s) AND source = %s",
            (game_ids[i:i + 500], ALT_SOURCE)).fetchall()}
    return have


def _deriv_done(conn, game_ids: list[str]) -> set[str]:
    have: set[str] = set()
    for i in range(0, len(game_ids), 500):
        have |= {r[0] for r in conn.execute(
            "SELECT DISTINCT game_id FROM odds WHERE game_id = ANY(%s) AND source LIKE %s",
            (game_ids[i:i + 500], SOURCE_PREFIX + "%")).fetchall()}
    return have


_ODDS_KEYS = ("game_id", "sport", "market", "bookmaker", "snapshot_type", "snapshot_at",
              "home_price", "away_price", "draw_price", "spread_home", "total_line",
              "over_price", "under_price", "home_link", "away_link", "draw_link",
              "over_link", "under_link", "home_sid", "away_sid", "draw_sid",
              "over_sid", "under_sid", "source")


def buy_derivatives(conn, meter: Meter, first_season: int, last_season: int,
                    lead_min: int) -> dict:
    return _buy_per_event(conn, meter, first_season, last_season, lead_min,
                          DERIV_MARKETS, DERIV_SOURCE, parse_derivatives, _deriv_done, "derivatives")


def buy_alternates(conn, meter: Meter, first_season: int, last_season: int,
                   lead_min: int, dates: tuple[str, str] | None = None) -> dict:
    """Every book's alternate spread, total and team-total ladders, one purchase per game
    `lead_min` before tip (ALT_MARKETS, ALT_SOURCE). `dates` (first, last) bounds a pilot."""
    return _buy_per_event(conn, meter, first_season, last_season, lead_min,
                          ALT_MARKETS, ALT_SOURCE, parse_alternates, _alt_done, "alternates",
                          dates=dates)


def _buy_per_event(conn, meter: Meter, first_season: int, last_season: int, lead_min: int,
                   markets: list[str], source: str, parse, done_fn, what: str,
                   dates: tuple[str, str] | None = None) -> dict:
    """One purchase per game `lead_min` before tip, newest date first; a game already holding
    `source` rows is skipped, so a re-run buys only what is missing."""
    games = {k: v for k, v in _known_games(conn, first_season, last_season).items()
             if v["game_date"] >= FIRST_PROPS_DATE
             and (dates is None or dates[0] <= v["game_date"] <= dates[1])}
    done = done_fn(conn, list(games))
    by_date: dict[str, list[dict]] = defaultdict(list)
    for g in games.values():
        if g["game_id"] not in done:
            by_date[g["game_date"]].append(g)
    todo = sorted(by_date, reverse=True)
    n = sum(len(v) for v in by_date.values())
    logger.info(f"{what}: {n} games to buy on {len(todo)} dates "
                f"(~{10 * len(markets) * n:,} credits), {len(done)} stored")
    totals = defaultdict(int)
    failed: list[tuple] = []           # (event, game, date) whose purchase got no answer
    unlisted: list[str] = []           # dates whose game list got no answer

    def buy_one(ev, g, start) -> bool:
        """Buy and store one game; False = no usable answer (kept for the second pass)."""
        snap = (start - timedelta(minutes=lead_min)).strftime("%Y-%m-%dT%H:%M:%SZ")
        resp = meter.get(f"{BASE}/events/{ev['id']}/odds", {
            "date": snap, "markets": ",".join(markets), "bookmakers": BOOKS,
            "oddsFormat": "american"})
        if resp is None or resp.status_code != 200:
            totals["errors"] += 1
            return False
        body = resp.json()
        stamp = body.get("timestamp") or snap
        rows = []
        for book in (body.get("data") or {}).get("bookmakers", []):
            for p in parse(book.get("markets", []), ev.get("home_team", ""),
                           g["home"], g["away"]):
                row = dict.fromkeys(_ODDS_KEYS)
                row.update({"game_id": g["game_id"], "sport": "NBA",
                            "bookmaker": book.get("key"), "snapshot_type": "open",
                            "snapshot_at": stamp, "source": source})
                row.update(p)                     # a parser's own snapshot_at wins
                rows.append(row)
        if rows:
            def _write(rows=rows):
                _insert_odds(conn, rows)
                conn.commit()
            if not _write_with_retry(conn, _write, g["game_id"]):
                totals["errors"] += 1
                return False
            totals["rows"] += len(rows)
        totals["events"] += 1
        return True

    def listed(d):
        noon = datetime.fromisoformat(f"{d}T12:00:00").replace(tzinfo=ET)
        r = meter.get(f"{BASE}/events", {"date": noon.astimezone(timezone.utc)
                                         .strftime("%Y-%m-%dT%H:%M:%SZ")})
        if r is None or r.status_code != 200:
            totals["errors"] += 1
            return None
        by_teams = {(g["away"], g["home"]): g for g in by_date[d]}
        out = []
        for ev in (r.json().get("data") or []):
            start = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
            if start.astimezone(ET).date().isoformat() != d:
                continue
            g = by_teams.get((_normalize_team(ev.get("away_team", ""), "NBA"),
                              _normalize_team(ev.get("home_team", ""), "NBA")))
            if g is not None:
                out.append((ev, g, start))
        return out

    for d in todo:
        evs = listed(d)
        if evs is None:
            unlisted.append(d)
            continue
        for ev, g, start in evs:
            why = meter.stop_reason(10 * len(markets))
            if why:
                totals["stopped"] = why
                logger.warning(f"{what} stopping at {d}: {why}")
                return dict(totals)
            if not buy_one(ev, g, start):
                failed.append((ev, g, start))
        logger.info(f"{what} {d}: {totals['events']} games so far, {totals['rows']:,} rows | "
                    f"spent {meter.spent:,}, balance {meter.remaining}")
    # one more pass: list every date whose list got no answer, and buy every game that got
    # none, under the same meter and floor
    totals["dates_unlisted"] = len(unlisted)
    for d in unlisted:
        evs = listed(d)
        if evs is None:
            totals["dates_still_unlisted"] += 1
            continue
        failed.extend(evs)
    totals["retried"] = len(failed)
    for ev, g, start in failed:
        why = meter.stop_reason(10 * len(markets))
        if why:
            totals["stopped"] = why
            break
        if not buy_one(ev, g, start):
            totals["still_failed"] += 1
    return dict(totals)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lines", action="store_true")
    ap.add_argument("--props", action="store_true")
    ap.add_argument("--derivatives", action="store_true")
    ap.add_argument("--alternates", action="store_true",
                    help="every book's alternate spread / total / team-total ladder, one purchase a game")
    ap.add_argument("--dates", nargs=2, metavar=("FIRST", "LAST"),
                    help="alternates: only game dates in this range (a pilot)")
    ap.add_argument("--instants", metavar="PLAN",
                    help="buy the whole slate at every instant the plan file names "
                         "(scripts/nba_news_window_plan.py)")
    ap.add_argument("--why", default="news_window", help="instants: the ledger's why")
    ap.add_argument("--probe-props", metavar="DATE", help="2 games on DATE, writes nothing")
    ap.add_argument("--seasons", nargs=2, type=int, metavar=("FIRST", "LAST"))
    ap.add_argument("--lead-min", type=int, default=60)
    ap.add_argument("--oldest-first", action="store_true",
                    help="lines: walk the dates oldest first (run beside a newest-first sibling)")
    ap.add_argument("--extra-hours", nargs="+", type=int, default=[],
                    help="lines: more hours, counted from midnight UTC on the game date "
                         "(28 = next day 04Z)")
    ap.add_argument("--fill-gaps", action="store_true",
                    help="buy tip-relative fetches so every game reaches every decision window")
    ap.add_argument("--season-order", nargs="+", type=int,
                    help="fill-gaps: the order seasons are bought in")
    ap.add_argument("--max-credits", type=int)
    ap.add_argument("--floor", type=int, default=DEFAULT_FLOOR)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    conn = get_connection()
    try:
        if a.probe_props:
            season = int(a.probe_props[:4]) + (1 if int(a.probe_props[5:7]) >= 9 else 0)
            gs = [g for g in _known_games(conn, season, season).values()
                  if g["game_date"] == a.probe_props]
            meter = Meter(ceiling=400, floor=a.floor)
            s = buy_props_date(conn, meter, a.probe_props, gs, a.lead_min, apply=False, limit=2)
            print(s)
            print(f"MEASURED {meter.spent} credits for {s['events']} games; balance {meter.remaining}")
            return
        if not a.seasons or not (a.lines or a.props or a.derivatives or a.alternates or a.fill_gaps
                                 or a.instants):
            ap.error("give --lines, --fill-gaps, --props, --derivatives or --alternates "
                     "with --seasons FIRST LAST")
        if not a.apply:
            print("dry run: re-run with --apply --max-credits N")
            return
        if not a.max_credits:
            ap.error("--apply needs --max-credits")
        meter = Meter(ceiling=a.max_credits, floor=a.floor)
        # Hours before gaps, so the gap plan is drawn against every hour held.
        if a.lines:
            print("lines:", buy_lines(conn, meter, *a.seasons, oldest_first=a.oldest_first,
                                      extra_hours=tuple(a.extra_hours)))
        if a.fill_gaps and not meter.stop_reason(30):
            print("gaps:", buy_gaps(conn, meter, *a.seasons, season_order=a.season_order))
        if a.props:
            print("props:", buy_props(conn, meter, *a.seasons, a.lead_min))
        if a.derivatives:
            print("derivatives:", buy_derivatives(conn, meter, *a.seasons, a.lead_min))
        if a.alternates:
            print("alternates:", buy_alternates(conn, meter, *a.seasons, a.lead_min,
                                                dates=tuple(a.dates) if a.dates else None))
        if a.instants:
            print("instants:", buy_instants(conn, meter, *a.seasons, a.instants, a.why))
        print(f"spent {meter.spent:,} credits; balance {meter.remaining}")
    finally:
        try:
            persist_quota(conn)
        finally:
            conn.close()


if __name__ == "__main__":
    main()
