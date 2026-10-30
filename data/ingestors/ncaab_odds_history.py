"""Historical NCAAB game lines, first-half lines and team totals from The Odds API.

WHY. Men's college basketball goes live for the 2026-27 season (first game
2026-11-01) with no stored price for any past game: no NCAAB row in `games`,
`odds` or `odds_history_pulls` (measured 2026-10-26). Without a price no NCAAB
model can be graded against a real line. mike, 2026-10-26: "3 approved" --
game lines 2020-21..2025-26 (~375,000 credits), first-half and team-total
lines 2023-24..2025-26 at the opener and the close (up to ~1,380,000), with a
reserve kept so the live feeds never stop.

WHAT IS BOUGHT

  --lines  The bulk /historical/sports/basketball_ncaab/odds endpoint, h2h +
           spreads + totals at the ten fetched books (config.LINE_SHOP_BOOKMAKERS;
           ten names bill as one region): 30 credits a snapshot for the whole
           slate, the cost the NBA purchase measured on the same endpoint and
           the same books (2026-10-15, x-requests-last). For every ET game date
           D: D-1 at 22Z (the evening-before opener), D at 15Z, and the UTC hour
           at or before tip minus 5 minutes for every tip that day, so every game
           has a price 5 to 65 minutes before its own tip whatever time it
           starts. NCAAB tips run from late morning to after 04Z, so the NBA's
           fixed hour list would miss the noon and late-West tips. Rows land in
           `odds` with source 'odds_api_historical' (the pruner protects it),
           resumable through `odds_history_pulls` (sport 'NCAAB', snapshot_date,
           hour_utc).

  --derivatives close|open  The per-event endpoint: first-half moneyline,
           spread and total plus team totals (4 markets; the feed bills 10 a
           market returned, so up to 40 a game, and an empty answer is free per
           the feed's docs). One snapshot a game: `close` at tip minus 10
           minutes, `open` at D-1 22Z or tip minus 20 hours, whichever is later.
           The event list (1 credit a date) names each game's event id. Period
           history starts 2023-05-03, so 2023-24 is the first season. Rows land
           in `odds` under NCAAB_DERIV_CLOSE_SOURCE / NCAAB_DERIV_OPEN_SOURCE;
           team totals split into `team_totals_home` / `team_totals_away` (the
           NBA shape). A game already holding rows under the source is skipped.

  --probe  One real paid call of each kind, writing nothing, printing the
           MEASURED x-requests-last of each, so the per-call cost is a
           measurement before the big run.

  --replay-unmatched  No paid call. Re-reads the raw events kept in
           `ncaab_odds_unmatched` and stores the ones that resolve now (after a
           fix to the team names), as the purchase would have stored them,
           with two differences: a listing whose start is 12 hours or more
           from the ESPN game it lands on is not stored, and an hour the feed
           answered with an earlier hour's snapshot is replayed only at the
           earlier hour (the raw table kept that snapshot once). A read-only
           dry run unless --apply; never writes the ledger, never deletes a raw
           row, and a second --apply stores nothing new.

WHO OWNS THE GAME. ESPN's schedule (data/ingestors/ncaab_teams.py). The feed
never mints an NCAAB game: every event resolves onto an ESPN game by its team
pair, and when the feed calls ESPN's away team home the names are swapped
before the outcomes are parsed, so the stored spread is ESPN's home number
(CLAUDE.md section 4).

UNMATCHED EVENTS ARE PAID DATA. A snapshot is bought once and ledgered, so an
event that resolves onto no game would be lost for good if it were dropped. Its
raw JSON goes to `ncaab_odds_unmatched` instead, and the run prints the names
that did not resolve, so a later fix to the name map can replay them.

THE PRECONDITION (raises). Every requested season must already hold its ESPN
schedule with scores -- `games` >= 4,000 scored NCAAB rows and `ncaab_events`
>= 4,000 rows -- because a snapshot bought before the schedule exists matches
nothing and is still ledgered. ESPN lists 4,285 completed D1 games for 2020-21,
the COVID season (scoreboard groups=50, 2020-11-25..2021-04-06, counted
2026-10-26), and 6,292 for 2024-25, so the bar clears every full season.

THE FLOOR. September 2026 ran the balance to 0 and every live feed stopped for
five days. Every response carries x-requests-remaining, and the run stops the
moment the next call would take it below `--floor` (300,000 at least: 3.5 of
October's worst organic days, measured 2026-10-28 from odds_api_quota; mike,
2026-10-28: "dont stop the spend" — the floor is the feeds' reserve, not a pause). NEWEST
DATE FIRST, so a stop leaves the most recent seasons stored.

    python -m data.ingestors.ncaab_odds_history --probe --seasons 2026 2026 --max-credits 200 --floor 300000 --apply
    python -m data.ingestors.ncaab_odds_history --lines --seasons 2021 2026 --max-credits 420000 --floor 300000 --apply
    python -m data.ingestors.ncaab_odds_history --derivatives close --seasons 2024 2026 --max-credits 800000 --floor 300000 --apply
    python -m data.ingestors.ncaab_odds_history --replay-unmatched --seasons 2026 2026 --dry-run
    python -m data.ingestors.ncaab_odds_history --replay-unmatched --seasons 2021 2026 --apply
"""
from __future__ import annotations

import argparse
import itertools
import json
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from loguru import logger

import config
from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current
from data.db import get_connection
from data.ingestors.nba_odds_history import _ODDS_KEYS, Meter, _write_with_retry
from data.ingestors.ncaab_teams import (eastern_game_date, load_games_window, ncaab_season_label,
                                        load_registry, match_event, reset_registry_cache,
                                        resolve_team_name)
from data.ingestors.odds_ingestor import (HISTORICAL_ODDS_SOURCE, PULL_LEDGER_DDL,
                                          _insert_odds, _mark_in_play, _parse_outcomes,
                                          _parse_spread_outcomes, _parse_total_outcomes,
                                          _process_events)
from data.ingestors.odds_quota import persist_quota

SPORT = "NCAAB"
BASE = "https://api.the-odds-api.com/v4/historical/sports/basketball_ncaab"
BOOKS = ",".join(config.LINE_SHOP_BOOKMAKERS[:10])
LINE_MARKETS = ["h2h", "spreads", "totals"]
DERIV_MARKETS = ["h2h_h1", "spreads_h1", "totals_h1", "team_totals"]
# The two derivative purchases are separate sources so the close and the open
# each resume on their own (a game can hold one and not the other). Named
# exactly as data/prune_odds.PROTECTED_SOURCES lists them.
NCAAB_DERIV_CLOSE_SOURCE = "odds_api_ncaab_derivative_close"
NCAAB_DERIV_OPEN_SOURCE = "odds_api_ncaab_derivative_open"
DERIV_SOURCES = {"close": NCAAB_DERIV_CLOSE_SOURCE, "open": NCAAB_DERIV_OPEN_SOURCE}
FIRST_DERIV_DATE = "2023-05-03"     # the feed's first period / prop snapshot
LINE_SNAPSHOT_COST = 30             # 10 x 3 markets x 1 region (measured on the NBA)
LIST_COST = 1                       # the historical event list, a date
DERIV_EVENT_COST = 10 * len(DERIV_MARKETS)   # the most one game can bill
MIN_FLOOR = 300_000     # 3.5 of October's worst organic days (84,534 on 10-04); refill lands ~00:00Z on the 1st
MIN_SCORED_GAMES = 4_000
ET = ZoneInfo("America/New_York")

UNMATCHED_TABLE = "ncaab_odds_unmatched"
UNMATCHED_COLS = ("snapshot_at", "event_id", "home_name", "away_name",
                  "commence_time", "payload", "source", "stored_at")
UNMATCHED_DDL = """
CREATE TABLE IF NOT EXISTS ncaab_odds_unmatched (
    snapshot_at    TEXT NOT NULL,
    event_id       TEXT NOT NULL,
    home_name      TEXT,
    away_name      TEXT,
    commence_time  TEXT,
    payload        JSONB NOT NULL,
    source         TEXT NOT NULL,
    stored_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (event_id, snapshot_at, source)
)
"""
PULL_LEDGER_COLS = ("sport", "snapshot_date", "hour_utc", "pulled_at", "rows")


class PreconditionError(RuntimeError):
    """The purchase would pay for snapshots nothing can be matched to."""


class ContractError(RuntimeError):
    """odds_ingestor._process_events does not yet honour the NCAAB resolver contract."""


def _utc(v) -> datetime | None:
    """A stored or fed timestamp as an aware UTC datetime, or None."""
    if not v:
        return None
    if isinstance(v, datetime):
        dt = v
    else:
        try:
            dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _stamp(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _season_window(first: int, last: int) -> tuple[str, str]:
    """The game dates seasons first..last cover under the ending-year label
    (ncaab_teams.ncaab_season_label: October onwards is the next year's)."""
    return f"{first - 1}-10-01", f"{last}-09-30"


# ── the two checks that run before any credit is spent ──────────────────────

def check_precondition(conn, seasons: list[int]) -> dict[int, tuple[int, int]]:
    """Raise unless every season holds its ESPN schedule. Returns {season: (games, events)}."""
    try:
        scored = dict(conn.execute(
            "SELECT season, COUNT(*) FROM games WHERE sport = 'NCAAB' "
            "AND season = ANY(%s) AND home_score IS NOT NULL GROUP BY season",
            (list(seasons),)).fetchall())
        events = dict(conn.execute(
            "SELECT season, COUNT(*) FROM ncaab_events WHERE season = ANY(%s) "
            "GROUP BY season", (list(seasons),)).fetchall())
    except Exception as exc:                                    # noqa: BLE001
        try:
            conn.rollback()
        except Exception:                                       # noqa: BLE001
            pass
        raise PreconditionError(
            f"the NCAAB schedule is unreadable ({type(exc).__name__}: {exc}); run the "
            "ESPN backfill (data.ingestors.ncaab_espn_ingestor --backfill) first") from exc
    got = {s: (int(scored.get(s, 0)), int(events.get(s, 0))) for s in seasons}
    short = {s: v for s, v in got.items()
             if v[0] < MIN_SCORED_GAMES or v[1] < MIN_SCORED_GAMES}
    if short:
        raise PreconditionError(
            "the ESPN schedule is not stored for every season, so these snapshots "
            "would match nothing and still be ledgered as bought: "
            + ", ".join(f"{s}: {g:,} scored games, {e:,} ncaab_events rows"
                        for s, (g, e) in sorted(short.items()))
            + f" (each needs {MIN_SCORED_GAMES:,}). Run the ESPN backfill first.")
    return got


def check_process_events_contract() -> None:
    """Prove, for free, that odds_ingestor._process_events honours the NCAAB contract.

    The contract (data/ingestors/ncaab_teams.make_resolver): the resolver returns
    (game_id, flipped); the id is used as given, a flipped event has its names
    swapped BEFORE the outcomes are parsed, and NCAAB is not held to the
    DraftKings gate. A synthetic event at one non-DraftKings book goes through
    the real function; a wrong answer raises here, before the first paid call,
    rather than storing a season of tuple ids or away-team spreads.
    """
    book = next(b for b in config.LINE_SHOP_BOOKMAKERS if b != config.ODDS_API_BOOKMAKER)
    event = {"id": "selftest", "commence_time": "2026-01-10T00:00:00Z",
             "home_team": "Feed Home", "away_team": "Feed Away",
             "bookmakers": [{"key": book, "markets": [
                 {"key": "h2h", "outcomes": [{"name": "Feed Home", "price": -150},
                                             {"name": "Feed Away", "price": 130}]},
                 {"key": "spreads", "outcomes": [
                     {"name": "Feed Home", "price": -105, "point": -3.5},
                     {"name": "Feed Away", "price": -115, "point": 3.5}]}]}]}
    try:
        _, rows = _process_events([event], SPORT, "open", "2026-01-09T22:00:00Z",
                                  resolve_game_id=lambda h, a, c: ("NCAAB_selftest", True))
    except Exception as exc:                                    # noqa: BLE001
        raise ContractError(f"_process_events raised on a (game_id, flipped) resolver: "
                            f"{type(exc).__name__}: {exc}") from exc
    by_market = {r.get("market"): r for r in rows}
    problems = []
    if not rows:
        problems.append("no rows from a non-DraftKings book (NCAAB still held to the DK gate)")
    if any(r.get("game_id") != "NCAAB_selftest" for r in rows):
        problems.append(f"game_id taken as {rows[0].get('game_id')!r}, not the resolved id")
    h2h, spread = by_market.get("h2h"), by_market.get("spreads")
    if rows and (h2h is None or h2h.get("home_price") != 130 or h2h.get("away_price") != -150):
        problems.append(f"flipped h2h not swapped (home_price {h2h and h2h.get('home_price')})")
    if rows and (spread is None or spread.get("spread_home") != 3.5
                 or spread.get("home_price") != -115):
        problems.append(f"flipped spread not ESPN's home number "
                        f"(spread_home {spread and spread.get('spread_home')})")
    if problems:
        raise ContractError("odds_ingestor._process_events does not honour the NCAAB "
                            "resolver contract: " + "; ".join(problems))


# ── tables ───────────────────────────────────────────────────────────────────

def _ensure_tables(conn) -> None:
    """The pull ledger and the unmatched store, created once and locked down.

    Both are worker-only (data/anon_readable.WORKER_ONLY_TABLES). The catalog
    gate means a run that finds them current fires no DDL (data/ddl_guard.py).
    """
    changed = False
    if not schema_is_current(conn, "odds_history_pulls", columns=PULL_LEDGER_COLS,
                             rls=True, revoked_from=API_ROLES):
        conn.execute(PULL_LEDGER_DDL)
        lock_down(conn, "odds_history_pulls")
        changed = True
    if not schema_is_current(conn, "ncaab_odds_unmatched", columns=UNMATCHED_COLS,
                             rls=True, revoked_from=API_ROLES):
        conn.execute(UNMATCHED_DDL)
        lock_down(conn, "ncaab_odds_unmatched")
        changed = True
    if changed:
        conn.commit()


_UNMATCHED_INSERT = """
    INSERT INTO ncaab_odds_unmatched
           (snapshot_at, event_id, home_name, away_name, commence_time, payload, source)
    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
    ON CONFLICT (event_id, snapshot_at, source) DO NOTHING
"""


# ── resolving the feed's events onto ESPN's games ────────────────────────────

def _event_key(ev: dict) -> tuple[str, str, str]:
    """(home, away, commence) as the feed sent them: the resolver's arguments."""
    return (ev.get("home_team") or "", ev.get("away_team") or "",
            ev.get("commence_time") or "")


class EventResolver:
    """ncaab_teams.match_event over a whole season, fast, and counting what misses.

    A season is ~6,000 games and a lines purchase resolves ~150 events a
    snapshot over ~2,000 snapshots, so the games are bucketed by ET date and
    each name is resolved against the registry once.
    """

    def __init__(self, registry: list[dict], games: list[dict]):
        self.registry = registry
        self.by_date: dict[str, list[dict]] = defaultdict(list)
        for g in games:
            self.by_date[g["game_date"]].append(g)
        self._ids: dict[str, int | None] = {}
        self._seen: set[str] = set()
        self.unresolved_names: Counter = Counter()   # distinct events per unresolved name
        self.no_game: Counter = Counter()            # both names resolved, no scheduled game

    def team(self, name: str) -> int | None:
        if name not in self._ids:
            self._ids[name] = resolve_team_name(name, self.registry)
        return self._ids[name]

    def __call__(self, home_name: str, away_name: str, commence_time: str):
        """(game_id, flipped) or None -- the make_resolver contract."""
        try:
            day = date.fromisoformat(eastern_game_date(commence_time))
        except ValueError:
            return None
        near = [g for k in (-1, 0, 1)
                for g in self.by_date.get((day + timedelta(days=k)).isoformat(), ())]
        return match_event(near, self.team(home_name), self.team(away_name), commence_time)

    def split(self, events: list[dict]) -> tuple[dict, list[dict]]:
        """Resolve every event once: ({(home, away, commence): hit}, unmatched events)."""
        hits, unmatched = {}, []
        for ev in events:
            key = _event_key(ev)
            hit = self(*key)
            hits[key] = hit
            if hit is not None:
                continue
            unmatched.append(ev)
            eid = str(ev.get("id"))
            if eid in self._seen:
                continue
            self._seen.add(eid)
            ids = [self.team(key[0]), self.team(key[1])]
            for name, tid in zip(key[:2], ids):
                if tid is None:
                    self.unresolved_names[name] += 1
            if None not in ids:
                self.no_game[f"{key[1]} @ {key[0]}"] += 1
        return hits, unmatched

    def report(self, top: int = 25) -> str:
        names = ", ".join(f"{n} ({c})" for n, c in self.unresolved_names.most_common(top))
        pairs = ", ".join(f"{n} ({c})" for n, c in self.no_game.most_common(top))
        return (f"unresolved team names: {len(self.unresolved_names)} "
                f"[{names or 'none'}]; resolved pairs with no ESPN game: "
                f"{len(self.no_game)} [{pairs or 'none'}]")


def _season_games(conn, first: int, last: int) -> list[dict]:
    lo, hi = _season_window(first, last)
    return load_games_window(conn, lo, hi)


def _fresh_registry(conn) -> list[dict]:
    """ncaab_teams read now, not the process's cached copy.

    The worker runs every job in ONE process, and ncaab_teams.load_registry
    caches whatever it read first, an empty list included. The declared feed
    probe runs before the ESPN backfill creates the table, so without this the
    purchases queued behind the backfill would read that empty cache and
    refuse to start (2026-10-26 review)."""
    reset_registry_cache()
    return load_registry(conn)


def _resolver(conn, games: list[dict]) -> EventResolver:
    registry = _fresh_registry(conn)
    if not registry:
        raise PreconditionError("ncaab_teams is empty, so no feed name can resolve; "
                                "run the ESPN backfill first")
    return EventResolver(registry, games)


# ── game lines ───────────────────────────────────────────────────────────────

def line_snapshots(games: list[dict]) -> list[datetime]:
    """The on-the-hour UTC instants to buy, newest first, each once.

    For every ET game date D: D-1 22Z (the overnight opener), D 15Z (the
    morning), and for every tip the hour at or before tip minus 5 minutes --
    a 19:00Z tip is priced at 18Z (60 minutes out), a 19:05Z tip at 19Z (5
    minutes out). A game with no stored tip gets the first two only. Dates and
    tips that share an hour share the snapshot. Pure, so the plan is testable.
    """
    want: set[datetime] = set()
    for g in games:
        d = date.fromisoformat(str(g["game_date"])[:10])
        midnight = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        want.add(midnight + timedelta(hours=15))
        want.add(midnight - timedelta(hours=2))
        tip = _utc(g.get("commence_time"))
        if tip is not None:
            want.add((tip - timedelta(minutes=5)).replace(minute=0, second=0, microsecond=0))
    return sorted(want, reverse=True)


class QuoteKeeper:
    """Which bought rows are stored: the board's opener, its two anchors, and
    the hours before tip. Everything else in a snapshot is a repeat.

    WHY. A bulk snapshot returns every game the books list, days ahead, and
    the plan buys ~13 snapshots a game day. Storing every row of every
    snapshot would repeat the same far-off quote a dozen times a day: NCAAF's
    historical snapshots average 1,348 rows (odds_history_pulls, 2026-10-26)
    and NCAAB lists more games, so the approved ~12,500 snapshots would store
    tens of millions of rows into an odds table that holds 18.5M (13 GB) on a
    68 GB database (2026-10-26 review). The purchase still BUYS every snapshot
    (that is what the ledger and the credits record); it stores, per
    (game, market, book):

      * the first quote this run sees (the opener as far as the plan reaches),
      * the game date's two anchors, D-1 22Z and D 15Z (every book at the same
        instant, which the Pinnacle-versus-soft-book sweep pairs on),
      * every snapshot from three hours before ESPN's tip to the tip (the
        close and the decision window).

    In-play prices are not stored at all: the approved purchase is for
    pre-game models, and _mark_in_play has already labelled them.
    """

    PRE_TIP = timedelta(hours=3)

    def __init__(self, games: list[dict]):
        self.dates: dict[str, date] = {}
        self.tips: dict[str, datetime | None] = {}
        for g in games:
            self.dates[g["game_id"]] = date.fromisoformat(str(g["game_date"])[:10])
            self.tips[g["game_id"]] = _utc(g.get("commence_time"))
        self.seen: set[tuple[str, str, str]] = set()

    def anchors(self, game_id: str) -> tuple[datetime, ...]:
        d = self.dates.get(game_id)
        if d is None:
            return ()
        midnight = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        return (midnight - timedelta(hours=2), midnight + timedelta(hours=15))

    def wanted(self, row: dict, when: datetime) -> bool:
        if row.get("snapshot_type") == "in_play":
            return False
        gid = row["game_id"]
        key = (gid, row.get("market") or "", row.get("bookmaker") or "")
        tip = self.tips.get(gid)
        keep = (key not in self.seen
                or when in self.anchors(gid)
                or (tip is not None and timedelta(0) <= tip - when <= self.PRE_TIP))
        if keep:
            self.seen.add(key)
        return keep


def season_order(todo: list[datetime]) -> list[datetime]:
    """Seasons newest first (the recent seasons land first), each season
    oldest first, so a quote's first appearance is its earliest snapshot."""
    def season(w: datetime) -> int:
        return ncaab_season_label(w.date().isoformat())
    return sorted(todo, key=lambda w: (-season(w), w))


def _held_hours(conn) -> set[tuple[str, int]]:
    return {(str(r[0]), int(r[1])) for r in conn.execute(
        "SELECT snapshot_date, hour_utc FROM odds_history_pulls WHERE sport = %s",
        (SPORT,)).fetchall()}


def _parse_snapshot(events: list[dict], when: datetime, resolver: EventResolver,
                    tips: dict[str, str]) -> tuple[dict, list[dict], list[dict], list[dict], int]:
    """One snapshot's events resolved, parsed and labelled: the single path the
    purchase (_buy_snapshot) and the replay (replay_unmatched) both take.

    Returns (hits, unmatched, odds_rows, dropped, marked_in_play). `when` is the
    planned on-the-hour instant, handed to the parser as the snapshot time; a
    market's own `last_update`, which the feed sends, wins over it in the rows.
    """
    snapshot_at = _stamp(when)
    hits, unmatched = resolver.split(events)
    # The contract: _process_events takes (game_id, flipped) and swaps the
    # names itself before parsing (proved by check_process_events_contract).
    # It gets the resolver ITSELF, not a lookup of split()'s answers keyed on
    # the exact strings: a lookup misses if the parser passes the start in any
    # other form, and that event would then be neither stored nor kept raw.
    _, odds_rows = _process_events(events, SPORT, "open", snapshot_at,
                                   resolve_game_id=resolver)
    for row in odds_rows:
        row["source"] = HISTORICAL_ODDS_SOURCE
    # The backstop for the same loss: an event that DID resolve and carried
    # prices but produced no row (a filter inside the parser, which this
    # module does not own) is kept raw beside the unmatched ones, because the
    # ledger row means this snapshot is never bought again.
    kept = {o["game_id"] for o in odds_rows}
    dropped = [ev for ev in events
               if (hit := hits.get(_event_key(ev))) and hit[0] not in kept
               and any(b.get("markets") for b in ev.get("bookmakers") or [])]
    # With a resolver _process_events emits no game rows, so the in-play
    # relabel takes each game's tip from ESPN's schedule (the feed's own start
    # where ESPN has none). Without this a 22Z price on a 19Z tip is stored
    # as pre-game: the section 7 leak. Both are read as aware UTC first, so a
    # stored tip without an offset cannot raise mid-purchase in the compare.
    fed = {hit[0]: c for (h, a, c), hit in hits.items() if hit}
    starts = []
    for gid in kept:
        tip = _utc(tips.get(gid)) or _utc(fed.get(gid))
        starts.append({"game_id": gid, "commence_time": tip.isoformat() if tip else None})
    marked = _mark_in_play(starts, odds_rows)
    return hits, unmatched, odds_rows, dropped, marked


def _buy_snapshot(conn, meter: Meter, tips: dict[str, str], resolver: EventResolver,
                  when: datetime, stats: dict, keeper: "QuoteKeeper | None" = None) -> bool:
    """Buy the whole slate at `when`, write it, its unmatched events and its
    ledger row in one transaction. False = stop (ceiling or floor)."""
    snap_date, hour = when.date().isoformat(), when.hour
    held = conn.execute("SELECT 1 FROM odds_history_pulls WHERE sport = %s "
                        "AND snapshot_date = %s AND hour_utc = %s",
                        (SPORT, snap_date, hour)).fetchone()
    if held:
        conn.commit()
        stats["skipped_held"] += 1
        return True
    stop = meter.stop_reason(LINE_SNAPSHOT_COST)
    if stop:
        stats["stopped"] = stop
        logger.warning(f"lines stopping at {when:%Y-%m-%d %H}Z: {stop}")
        return False
    snapshot_at = _stamp(when)
    r = meter.get(f"{BASE}/odds", {"date": snapshot_at, "markets": ",".join(LINE_MARKETS),
                                   "bookmakers": BOOKS, "oddsFormat": "american"})
    if r is None or r.status_code != 200:
        stats["errors"] += 1
        logger.warning(f"lines {snapshot_at}: HTTP {getattr(r, 'status_code', 'network')}")
        return True
    body = r.json()
    events = body.get("data") or []
    stamp = body.get("timestamp") or snapshot_at
    _, unmatched, odds_rows, dropped, marked = _parse_snapshot(events, when, resolver, tips)
    if dropped:
        logger.warning(f"lines {snapshot_at}: {len(dropped)} resolved event(s) produced no "
                       f"odds row; kept raw in {UNMATCHED_TABLE}")
    stats["marked_in_play"] += marked
    bought = len(odds_rows)
    if keeper is not None:
        odds_rows = [r for r in odds_rows if keeper.wanted(r, when)]
    stats["rows_not_stored"] += bought - len(odds_rows)
    lost = [(stamp, str(ev.get("id")), ev.get("home_team"), ev.get("away_team"),
             ev.get("commence_time"), json.dumps(ev), HISTORICAL_ODDS_SOURCE)
            for ev in unmatched + dropped]

    def _write():
        if odds_rows:
            _insert_odds(conn, odds_rows)
        if lost:
            conn.executemany(_UNMATCHED_INSERT, lost)
        conn.execute("""
            INSERT INTO odds_history_pulls (sport, snapshot_date, hour_utc, pulled_at, rows)
            VALUES (%s, %s, %s, NOW(), %s)
            ON CONFLICT (sport, snapshot_date, hour_utc) DO UPDATE
               SET pulled_at = NOW(), rows = EXCLUDED.rows
        """, (SPORT, snap_date, hour, len(odds_rows)))
        conn.commit()

    if not _write_with_retry(conn, _write, f"lines {snapshot_at}"):
        stats["errors"] += 1
        return True
    stats["calls"] += 1
    stats["odds_rows"] += len(odds_rows)
    stats["unmatched_events"] += len(unmatched)
    stats["dropped_by_parser"] += len(dropped)
    if stats["calls"] % 50 == 0:
        logger.info(f"lines {snapshot_at}: {stats['calls']} calls, {stats['odds_rows']:,} rows, "
                    f"spent {meter.spent:,}, balance {meter.remaining}")
    return True


def plan_lines(conn, first: int, last: int) -> tuple[list[dict], list[datetime], list[datetime]]:
    """(games, every snapshot, the snapshots not yet ledgered), newest first."""
    games = _season_games(conn, first, last)
    pairs = line_snapshots(games)
    try:
        done = _held_hours(conn)
    except Exception:                                           # noqa: BLE001
        conn.rollback()                    # a database the ledger has never reached
        done = set()
    todo = [w for w in pairs if (w.date().isoformat(), w.hour) not in done]
    return games, pairs, todo


def buy_lines(conn, meter: Meter, first: int, last: int) -> dict:
    check_precondition(conn, list(range(first, last + 1)))
    check_process_events_contract()
    _ensure_tables(conn)
    games, pairs, todo = plan_lines(conn, first, last)
    resolver = _resolver(conn, games)
    tips = {g["game_id"]: g.get("commence_time") for g in games}
    logger.info(f"lines: {len(games):,} games -> {len(pairs):,} snapshots, "
                f"{len(pairs) - len(todo):,} already stored, {len(todo):,} to buy "
                f"(~{LINE_SNAPSHOT_COST * len(todo):,} credits)")
    stats: dict = defaultdict(int)
    keeper = QuoteKeeper(games)
    for when in season_order(todo):
        if not _buy_snapshot(conn, meter, tips, resolver, when, stats, keeper):
            break
    print("lines", resolver.report())
    return dict(stats)


# ── first half and team totals ───────────────────────────────────────────────

def deriv_instant(tip: datetime | None, game_date: str, mode: str) -> datetime | None:
    """The snapshot one game's derivatives are bought at, on the 5-minute grid.

    close: tip minus 10 minutes. open: D-1 22Z or tip minus 20 hours, whichever
    is LATER (a 7pm ET tip opens at 04Z the same night, a noon tip at D-1 22Z).
    Rounded down to five minutes, the feed's snapshot spacing.
    """
    d = date.fromisoformat(str(game_date)[:10]) - timedelta(days=1)
    evening_before = datetime(d.year, d.month, d.day, 22, tzinfo=timezone.utc)
    if mode == "close":
        if tip is None:
            return None
        at = tip - timedelta(minutes=10)
    elif mode == "open":
        at = evening_before if tip is None else max(evening_before, tip - timedelta(hours=20))
    else:
        raise ValueError(f"mode must be close or open, got {mode!r}")
    return at.replace(minute=at.minute - at.minute % 5, second=0, microsecond=0)


def _side_team(o: dict) -> tuple[str, str]:
    """(over/under, team) of a team-total outcome, whichever field carries which."""
    name, desc = (o.get("name") or ""), (o.get("description") or "")
    return (name, desc) if name.lower() in ("over", "under") else (desc, name)


def parse_derivatives(book_markets: list[dict], home_name: str, away_name: str) -> list[dict]:
    """One `odds`-shaped dict per (market, line) for one book.

    `home_name` / `away_name` are the feed's names in ESPN's orientation (the
    caller swaps them for a flipped event), so spreads_h1 stores ESPN's home
    number and team totals land under ESPN's home and away. A team total whose
    description names neither team is never filed under either side.
    """
    rows = []
    for m in book_markets:
        key, outs = m.get("key"), m.get("outcomes") or []
        if key == "h2h_h1":
            p = _parse_outcomes(outs, SPORT, home_name)
            if p.get("home_price") is not None and p.get("away_price") is not None:
                rows.append({"market": key, **p})
        elif key == "spreads_h1":
            p = _parse_spread_outcomes(outs, home_name)
            if p.get("spread_home") is not None:
                rows.append({"market": key, **p})
        elif key == "totals_h1":
            p = _parse_total_outcomes(outs)
            if p.get("total_line") is not None:
                rows.append({"market": key, **p})
        elif key == "team_totals":
            slots: dict[tuple, dict] = {}
            for o in outs:
                side, team = _side_team(o)
                if side.lower() not in ("over", "under") or o.get("point") is None:
                    continue
                stored = ("team_totals_home" if team == home_name else
                          "team_totals_away" if team == away_name else None)
                if stored is None:
                    continue
                slots.setdefault((stored, float(o["point"])), {})[side.lower() + "_price"] = o.get("price")
            for (stored, pt), slot in slots.items():
                rows.append({"market": stored, "total_line": pt,
                             "over_price": slot.get("over_price"),
                             "under_price": slot.get("under_price")})
    return rows


def _deriv_done(conn, game_ids: list[str], source: str) -> set[str]:
    have: set[str] = set()
    for i in range(0, len(game_ids), 500):
        have |= {r[0] for r in conn.execute(
            "SELECT DISTINCT game_id FROM odds WHERE game_id = ANY(%s) AND source = %s",
            (game_ids[i:i + 500], source)).fetchall()}
    return have


def _list_instant(game_date: str, tips: list[datetime]) -> datetime:
    """When to ask for date D's event list: noon ET, or an hour before D's
    first tip when that is earlier (a Thanksgiving-tournament 11am tip is
    already under way at noon and may no longer be listed)."""
    noon = datetime.fromisoformat(f"{game_date}T12:00:00").replace(tzinfo=ET).astimezone(timezone.utc)
    early = [t - timedelta(hours=1) for t in tips if t is not None]
    return min([noon] + early)


def plan_derivatives(conn, first: int, last: int, mode: str):
    """(every season game, those since FIRST_DERIV_DATE, the ids already stored
    under the mode's source)."""
    every = _season_games(conn, first, last)
    games = [g for g in every if g["game_date"] >= FIRST_DERIV_DATE]
    return every, games, _deriv_done(conn, [g["game_id"] for g in games], DERIV_SOURCES[mode])


def buy_derivatives(conn, meter: Meter, first: int, last: int, mode: str) -> dict:
    """One purchase per game at its mode's instant, newest date first; a game
    already holding rows under the source is skipped, so a re-run (the r2 job
    after the monthly refill) buys only what is missing. An answer with no
    markets writes nothing and is asked again on a re-run; the feed documents
    an empty answer as free."""
    source = DERIV_SOURCES[mode]
    check_precondition(conn, list(range(first, last + 1)))
    every, games, done = plan_derivatives(conn, first, last, mode)
    resolver = _resolver(conn, every)
    pending = {g["game_id"]: g for g in games if g["game_id"] not in done}
    by_date: dict[str, list[dict]] = defaultdict(list)
    for g in pending.values():
        by_date[g["game_date"]].append(g)
    logger.info(f"derivatives {mode}: {len(pending):,} games to buy on {len(by_date):,} dates "
                f"(<= ~{DERIV_EVENT_COST * len(pending) + len(by_date):,} credits), "
                f"{len(done):,} stored")
    totals: dict = defaultdict(int)
    failed: list[tuple] = []
    unlisted: list[str] = []
    answered: set[str] = set()             # games whose purchase got an answer
    # End the planning reads' transaction before the first paid call, so no
    # read lock is held across the HTTP waits of a long run.
    conn.commit()

    def listed(d: str):
        """[(event, game, flipped)] for D's pending games, or None on no answer."""
        when = _list_instant(d, [_utc(g.get("commence_time")) for g in by_date[d]])
        r = meter.get(f"{BASE}/events", {"date": _stamp(when)})
        if r is None or r.status_code != 200:
            totals["errors"] += 1
            return None
        events = r.json().get("data") or []
        hits, _ = resolver.split(events)
        out = []
        for ev in events:
            hit = hits.get(_event_key(ev))
            if hit and hit[0] in pending:
                out.append((ev, pending.pop(hit[0]), hit[1]))
        return out

    def buy_one(ev: dict, g: dict, flipped: bool) -> bool:
        """Buy and store one game; False = no usable answer (kept for the second pass)."""
        tip = _utc(g.get("commence_time")) or _utc(ev.get("commence_time"))
        at = deriv_instant(tip, g["game_date"], mode)
        if at is None:
            totals["no_tip"] += 1
            return True
        resp = meter.get(f"{BASE}/events/{ev['id']}/odds", {
            "date": _stamp(at), "markets": ",".join(DERIV_MARKETS), "bookmakers": BOOKS,
            "oddsFormat": "american"})
        if resp is None or resp.status_code != 200:
            totals["errors"] += 1
            return False
        body = resp.json()
        stamp = body.get("timestamp") or _stamp(at)
        home_name, away_name = ev.get("home_team") or "", ev.get("away_team") or ""
        if flipped:
            # the feed called ESPN's away team home: parse in ESPN's orientation
            home_name, away_name = away_name, home_name
        rows = []
        for book in (body.get("data") or {}).get("bookmakers", []):
            for p in parse_derivatives(book.get("markets", []), home_name, away_name):
                row = dict.fromkeys(_ODDS_KEYS)
                row.update({"game_id": g["game_id"], "sport": SPORT,
                            "bookmaker": book.get("key"), "snapshot_type": "open",
                            "snapshot_at": stamp, "source": source})
                row.update(p)
                rows.append(row)
        if tip is not None:
            totals["marked_in_play"] += _mark_in_play(
                [{"game_id": g["game_id"], "commence_time": tip.isoformat()}], rows)
        if rows:
            def _write(rows=rows):
                _insert_odds(conn, rows)
                conn.commit()
            if not _write_with_retry(conn, _write, g["game_id"]):
                totals["errors"] += 1
                return False
            totals["rows"] += len(rows)
        else:
            totals["empty"] += 1
        totals["events"] += 1
        totals["flipped"] += int(flipped)
        answered.add(g["game_id"])
        return True

    def run_date(d: str) -> bool:
        # The check sits HERE, not only in the first loop, so the second pass
        # over unanswered dates cannot list one (1 credit) under the floor.
        why = meter.stop_reason(LIST_COST + DERIV_EVENT_COST)
        if why:
            totals["stopped"] = why
            logger.warning(f"derivatives {mode} stopping before listing {d}: {why}")
            return False
        evs = listed(d)
        if evs is None:
            unlisted.append(d)
            return True
        for i, (ev, g, flipped) in enumerate(evs):
            why = meter.stop_reason(DERIV_EVENT_COST)
            if why:
                totals["stopped"] = why
                logger.warning(f"derivatives {mode} stopping at {d}: {why}")
                for _, left, _ in evs[i:]:      # listed but not bought: still owed
                    pending[left["game_id"]] = left
                return False
            if not buy_one(ev, g, flipped):
                failed.append((ev, g, flipped))
        return True

    stopped = False
    for d in sorted(by_date, reverse=True):
        if not any(g["game_id"] in pending for g in by_date[d]):
            continue                         # every game already bought off another date's list
        if not run_date(d):
            stopped = True
            break
        logger.info(f"derivatives {mode} {d}: {totals['events']} games so far, "
                    f"{totals['rows']:,} rows | spent {meter.spent:,}, balance {meter.remaining}")
    if not stopped:
        # one more pass: re-list every date whose list got no answer, and buy
        # every game that got none, under the same meter and floor
        totals["dates_unlisted"] = len(unlisted)
        for d in list(unlisted):
            if not any(g["game_id"] in pending for g in by_date[d]):
                continue                     # bought off another date's list meanwhile
            if not run_date(d):
                stopped = True
                break
        if not stopped:
            totals["retried"] = len(failed)
            for ev, g, flipped in list(failed):
                why = meter.stop_reason(DERIV_EVENT_COST)
                if why:
                    totals["stopped"] = why
                    break
                if not buy_one(ev, g, flipped):
                    totals["still_failed"] += 1
    # Still owed, for the report: never listed or past a stop, plus listed games
    # whose purchase never got an answer (a stop skips the retry pass).
    totals["left_unbought"] = len(pending) + len(
        {g["game_id"] for _, g, _ in failed} - answered)
    print(f"derivatives {mode}", resolver.report())
    return dict(totals)


# ── the probe: one measured call of each kind ────────────────────────────────

PROBE_FALLBACK_DATE = "2026-01-17"   # a full Saturday slate in 2025-26


def _busiest_date(conn, season: int) -> str:
    try:
        row = conn.execute("SELECT game_date FROM ncaab_events WHERE season = %s "
                           "GROUP BY game_date ORDER BY COUNT(*) DESC, game_date DESC LIMIT 1",
                           (season,)).fetchone()
    except Exception:                                           # noqa: BLE001
        conn.rollback()
        row = None
    return str(row[0]) if row else PROBE_FALLBACK_DATE


def probe(conn, meter: Meter, season: int) -> dict:
    """One bulk snapshot, one event list, one event's derivatives. Writes nothing.

    Prints what each call was MEASURED to bill (x-requests-last), so the
    purchase's per-call cost is a reading, not the NBA's figure carried over.
    """
    out: dict = {}
    try:
        check_process_events_contract()
        out["contract"] = "ok"
    except ContractError as exc:
        out["contract"] = f"NOT MET: {exc}"
    print(f"probe: _process_events contract {out['contract']}")
    d = _busiest_date(conn, season)
    try:
        resolver = EventResolver(_fresh_registry(conn), _season_games(conn, season, season))
    except Exception:                                           # noqa: BLE001
        resolver = EventResolver([], [])

    def billed(r) -> str:
        return (r.headers.get("x-requests-last") if r is not None else None) or "?"

    day = date.fromisoformat(d)
    when = datetime(day.year, day.month, day.day, 23, tzinfo=timezone.utc)
    if not meter.stop_reason(LINE_SNAPSHOT_COST):
        r = meter.get(f"{BASE}/odds", {"date": _stamp(when), "markets": ",".join(LINE_MARKETS),
                                       "bookmakers": BOOKS, "oddsFormat": "american"})
        events = (r.json().get("data") or []) if r is not None and r.status_code == 200 else []
        hits, unmatched = resolver.split(events)
        out["bulk"] = {"status": getattr(r, "status_code", None), "billed": billed(r),
                       "events": len(events), "resolved": len(events) - len(unmatched)}
        print(f"probe bulk {_stamp(when)}: HTTP {out['bulk']['status']}, MEASURED "
              f"x-requests-last {out['bulk']['billed']}, {len(events)} events, "
              f"{out['bulk']['resolved']} resolve onto ESPN games")
    noon = _list_instant(d, [])
    listing = []
    if not meter.stop_reason(LIST_COST):
        r = meter.get(f"{BASE}/events", {"date": _stamp(noon)})
        listing = (r.json().get("data") or []) if r is not None and r.status_code == 200 else []
        out["list"] = {"status": getattr(r, "status_code", None), "billed": billed(r),
                       "events": len(listing)}
        print(f"probe list {_stamp(noon)}: HTTP {out['list']['status']}, MEASURED "
              f"x-requests-last {out['list']['billed']}, {len(listing)} events")
    ev = next((e for e in listing if (_utc(e.get("commence_time")) or noon) > noon), None)
    if ev is not None and not meter.stop_reason(DERIV_EVENT_COST):
        at = deriv_instant(_utc(ev["commence_time"]), d, "close")
        r = meter.get(f"{BASE}/events/{ev['id']}/odds", {
            "date": _stamp(at), "markets": ",".join(DERIV_MARKETS), "bookmakers": BOOKS,
            "oddsFormat": "american"})
        body = r.json() if r is not None and r.status_code == 200 else {}
        books = {b.get("key"): sorted(m.get("key") for m in b.get("markets", []))
                 for b in (body.get("data") or {}).get("bookmakers", [])}
        out["derivatives"] = {"status": getattr(r, "status_code", None), "billed": billed(r),
                              "event": f"{ev.get('away_team')} @ {ev.get('home_team')}",
                              "books": books}
        print(f"probe derivatives {ev.get('away_team')} @ {ev.get('home_team')} at {_stamp(at)}: "
              f"HTTP {out['derivatives']['status']}, MEASURED x-requests-last "
              f"{out['derivatives']['billed']}, markets by book {books}")
    print(f"probe: MEASURED {meter.spent} credits in total; balance {meter.remaining}")
    return out


# ── the replay: kept raw events that resolve now ─────────────────────────────
#
# WHY. ncaab_odds_unmatched holds every event the purchase bought and could
# not place on an ESPN game: 137,007 rows after the lines job (worker job
# 805227, 2026-10-29; the job counted 137,083, and the table keeps one row per
# event and feed time), nearly all because the feed's shortened school names
# ("Michigan St Spartans") placed no team. Those snapshots are ledgered as
# bought, so the purchase never asks for them again. Once the names resolve,
# this stores them from the raw JSON on the purchase's own path
# (_parse_snapshot, one QuoteKeeper, seasons in season_order). It makes no
# paid call, never writes odds_history_pulls, never deletes a raw row, and a
# quote already in `odds` is never stored twice, so a second --apply stores
# nothing new.
#
# TWO DIFFERENCES FROM THE PURCHASE. (1) A listing placed on an ESPN game
# whose tip is REPLAY_MAX_TIP_GAP or more from the listing's own start is not
# stored (_far_from_tip). (2) When the feed answered several bought hours
# with the same stale snapshot, the raw table kept it once, under the first
# of them, so it is replayed at that hour only: a later hour's pre-tip copy of
# the same quote is not stored again (2020-11-27 18Z-20Z, measured by the
# 2026-10-29 review).
#
# THE STAMP. _buy_snapshot keyed each raw row on the feed's own timestamp
# (21:55:38Z for the 22Z snapshot), not on the instant it asked for. The
# keeper's anchors (D-1 22Z, D 15Z) and its pre-tip window are measured from
# the asked-for instant, so each stamp maps back to it: the smallest
# odds_history_pulls instant at or after the stamp, within an hour. A stamp
# with none is counted and skipped, never guessed.

REPLAY_BATCH_ROWS = 500                     # rows per fetch, never more
REPLAY_MAX_STAMP_GAP = timedelta(minutes=60)
REPLAY_MAX_TIP_GAP = timedelta(hours=12)
_CURSOR_IDS = itertools.count(1)

_UNMATCHED_KEYS_SQL = ("SELECT event_id, snapshot_at FROM ncaab_odds_unmatched "
                       "WHERE source = %s AND snapshot_at >= %s AND snapshot_at < %s")
_UNMATCHED_PAYLOADS_SQL = ("SELECT event_id, snapshot_at, payload FROM ncaab_odds_unmatched "
                           "WHERE source = %s AND snapshot_at = ANY(%s) AND event_id = ANY(%s)")
_ROW_VALUES = ("home_price", "away_price", "draw_price", "spread_home", "total_line",
               "over_price", "under_price")
_STORED_ROWS_SQL = ("SELECT game_id, market, bookmaker, snapshot_at, " + ", ".join(_ROW_VALUES)
                    + " FROM odds WHERE source = %s AND game_id = ANY(%s) AND snapshot_at = ANY(%s)")


def planned_instant(stamp: datetime, instants: list[datetime]) -> datetime | None:
    """The instant a raw row was bought at: the smallest of `instants` (sorted
    ascending, the pull ledger's) at or after the feed's `stamp`, within an
    hour. None when there is none: the caller counts it and skips it."""
    i = bisect_left(instants, stamp)
    if i < len(instants) and instants[i] - stamp <= REPLAY_MAX_STAMP_GAP:
        return instants[i]
    return None


def _far_from_tip(ev: dict, hit, tips: dict[str, str]) -> bool:
    """Is this feed listing placed on an ESPN game whose tip is
    REPLAY_MAX_TIP_GAP or more from the listing's own start?

    match_event takes the nearest game within a day either side of the
    listing's date, so a second listing of the same pair a day later lands on
    the same game, and at that game's anchors the keeper would store its
    quotes beside the real listing's. Among the kept raw events, 24 feed
    events (144 event snapshots) landed 12 to 29 hours from their game's tip,
    and every one of those games also has a listing within the hour; below
    12 hours the widest was 9.0 (SQL on the Supabase connector, 2026-10-29).
    False when the game, its tip or the listing's start is unknown: nothing
    to compare, so the purchase's answer stands."""
    if not hit:
        return False
    espn, feed = _utc(tips.get(hit[0])), _utc(ev.get("commence_time"))
    return bool(espn and feed and abs(espn - feed) >= REPLAY_MAX_TIP_GAP)


def _ledger_instants(conn) -> list[datetime]:
    """Every NCAAB instant odds_history_pulls records as bought, ascending."""
    out = set()
    for d, hour in conn.execute("SELECT snapshot_date, hour_utc FROM odds_history_pulls "
                                "WHERE sport = %s", (SPORT,)).fetchall():
        try:
            day = date.fromisoformat(str(d)[:10])
        except ValueError:
            continue
        out.add(datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
                + timedelta(hours=int(hour)))
    return sorted(out)


def _stream(conn, sql: str, params: tuple):
    """Yield the answer to `sql` in lists of at most REPLAY_BATCH_ROWS rows.

    A real connection reads through a server-side (named) cursor, so no
    query's whole answer is held at once. It lives inside the caller's
    transaction (a commit closes it), so read it to the end first. A test
    double with no raw psycopg2 connection is read with execute().fetchall()
    in the same batches."""
    raw = getattr(conn, "_conn", None)
    if raw is None:
        rows = conn.execute(sql, params).fetchall()
        for i in range(0, len(rows), REPLAY_BATCH_ROWS):
            yield rows[i:i + REPLAY_BATCH_ROWS]
        return
    cur = raw.cursor(name=f"ncaab_replay_{next(_CURSOR_IDS)}")
    try:
        cur.itersize = REPLAY_BATCH_ROWS
        cur.execute(sql, params)
        while True:
            rows = cur.fetchmany(REPLAY_BATCH_ROWS)
            if not rows:
                break
            yield rows
    finally:
        cur.close()


def _end_read(conn) -> None:
    """End a transaction that only read, so its locks go with it."""
    try:
        conn.rollback()
    except Exception:                                           # noqa: BLE001
        pass


def _payloads(conn, wanted: dict[str, str]) -> list[dict]:
    """The raw events of one planned instant ({event_id: stamp}), by primary
    key, at most REPLAY_BATCH_ROWS ids a query, ordered by event id."""
    ids, stamps = sorted(wanted), sorted(set(wanted.values()))
    found: dict[str, dict] = {}
    for i in range(0, len(ids), REPLAY_BATCH_ROWS):
        chunk = ids[i:i + REPLAY_BATCH_ROWS]
        for batch in _stream(conn, _UNMATCHED_PAYLOADS_SQL,
                             (HISTORICAL_ODDS_SOURCE, stamps, chunk)):
            for event_id, stamp, payload in batch:
                if wanted.get(event_id) != stamp:
                    continue
                found[event_id] = payload if isinstance(payload, dict) else json.loads(payload)
    return [found[k] for k in sorted(found)]


def _row_key(game_id, market, bookmaker, snapshot_at, *values) -> tuple:
    """What makes two odds rows the same stored quote: game, market, book, the
    quote's own time, and its prices and line (as numbers: the table's NUMERIC
    reads back as float, the feed's prices arrive as int)."""
    at = _utc(snapshot_at)
    return (game_id, market or "", bookmaker or "", _stamp(at) if at else str(snapshot_at),
            *(None if v is None else round(float(v), 4) for v in values))


def _not_yet_stored(conn, rows: list[dict], taken: set) -> list[tuple[tuple, dict]]:
    """(key, row) for each row whose identical quote is neither in `odds` under
    the historical source nor already taken by this run (`taken`)."""
    if not rows:
        return []
    game_ids = sorted({r["game_id"] for r in rows})
    stamps = sorted({str(r["snapshot_at"]) for r in rows})
    stored = {_row_key(*rec) for rec in conn.execute(
        _STORED_ROWS_SQL, (HISTORICAL_ODDS_SOURCE, game_ids, stamps)).fetchall()}
    out, here = [], set()
    for r in rows:
        key = _row_key(r["game_id"], r.get("market"), r.get("bookmaker"), r.get("snapshot_at"),
                       *(r.get(c) for c in _ROW_VALUES))
        if key in stored or key in taken or key in here:
            continue
        here.add(key)
        out.append((key, r))
    return out


def replay_unmatched(conn, first: int, last: int, apply: bool) -> dict:
    """Store the kept raw events of seasons first..last that resolve now.

    Pass 1 reads only the raw rows' keys (event id, stamp) through one
    server-side cursor and maps each stamp to its planned instant. Pass 2 walks
    the instants in season_order; for each it reads that instant's payloads
    by primary key, sets aside any listing _far_from_tip refuses, resolves
    the rest over ESPN's stored games, parses and labels them through
    _parse_snapshot exactly as _buy_snapshot does, filters them through ONE
    QuoteKeeper for the run, drops any quote already stored, and with `apply`
    inserts the rest with _insert_odds (source odds_api_historical),
    committing per instant. The read-back of `odds` is repeated inside each
    write, so a retry after a commit whose acknowledgement was lost stores
    nothing twice. Without `apply` it writes nothing; main() also hands it a
    read-only connection. Returns the counts.
    """
    st: Counter = Counter()
    instants = _ledger_instants(conn)
    games = _season_games(conn, first, last)
    resolver = _resolver(conn, games)
    tips = {g["game_id"]: g.get("commence_time") for g in games}
    keeper = QuoteKeeper(games)
    _end_read(conn)

    lo = _stamp(datetime(first - 1, 10, 1, tzinfo=timezone.utc) - REPLAY_MAX_STAMP_GAP)
    hi = _stamp(datetime(last, 10, 1, tzinfo=timezone.utc))
    mapped: dict[str, datetime | None] = {}
    by_instant: dict[datetime, dict[str, str]] = defaultdict(dict)
    for batch in _stream(conn, _UNMATCHED_KEYS_SQL, (HISTORICAL_ODDS_SOURCE, lo, hi)):
        for event_id, stamp in batch:
            if stamp not in mapped:
                at = _utc(stamp)
                mapped[stamp] = planned_instant(at, instants) if at else None
            when = mapped[stamp]
            if when is None:
                st["event_snapshots_unmapped"] += 1
                continue
            if not first <= ncaab_season_label(when.date().isoformat()) <= last:
                st["event_snapshots_outside_seasons"] += 1
                continue
            have = by_instant[when].get(event_id)
            if have is None or stamp > have:        # one raw row per event per instant
                by_instant[when][event_id] = stamp
    _end_read(conn)
    st["stamps_mapped"] = sum(1 for w in mapped.values() if w is not None)
    st["stamps_unmapped"] = sum(1 for w in mapped.values() if w is None)
    st["instants"] = len(by_instant)

    seen, placed, far_events = set(), set(), set()
    taken: set = set()
    season = None
    for when in season_order(list(by_instant)):
        label = ncaab_season_label(when.date().isoformat())
        if label != season:            # no game spans two seasons: bound the memory
            season, taken = label, set()
        wanted = by_instant.pop(when)
        events = _payloads(conn, wanted)
        st["event_snapshots"] += len(events)
        st["payloads_missing"] += len(wanted) - len(events)
        far = {id(ev) for ev in events if _far_from_tip(ev, resolver(*_event_key(ev)), tips)}
        if far:
            st["event_snapshots_far_from_tip"] += len(far)
            far_events.update(str(ev.get("id")) for ev in events if id(ev) in far)
            events = [ev for ev in events if id(ev) not in far]
        _, unmatched, odds_rows, dropped, marked = _parse_snapshot(events, when, resolver, tips)
        missed = {str(ev.get("id")) for ev in unmatched}
        for ev in events:
            seen.add(str(ev.get("id")))
            if str(ev.get("id")) not in missed:
                placed.add(str(ev.get("id")))
        st["event_snapshots_resolved"] += len(events) - len(unmatched)
        st["event_snapshots_unresolved"] += len(unmatched)
        st["dropped_by_parser"] += len(dropped)
        st["rows_parsed"] += len(odds_rows)
        st["rows_marked_in_play"] += marked
        kept = [r for r in odds_rows if keeper.wanted(r, when)]
        st["rows_kept"] += len(kept)
        fresh = _not_yet_stored(conn, kept, taken)
        st["rows_already_stored"] += len(kept) - len(fresh)
        if not apply or not fresh:
            if not apply:
                taken.update(k for k, _ in fresh)
                st["rows_to_insert"] += len(fresh)
            _end_read(conn)
            continue

        def _write(kept=kept):
            # Read `odds` back INSIDE the unit: data.db raises ConnectionLost
            # at a commit whose acknowledgement was lost, although the server
            # may have committed, and _write_with_retry then runs this again.
            now = _not_yet_stored(conn, kept, taken)
            if now:
                _insert_odds(conn, [r for _, r in now])
            conn.commit()
        if _write_with_retry(conn, _write, f"replay {_stamp(when)}"):
            taken.update(k for k, _ in fresh)       # stored now, by one attempt or another
            st["rows_inserted"] += len(fresh)
        else:
            st["write_errors"] += 1
    st["events_resolved"] = len(placed)
    st["events_unresolved"] = len(seen - placed)
    st["events_far_from_tip"] = len(far_events)

    mode = "applied" if apply else "dry run, read only, nothing written"
    print(f"replay seasons {first}-{last} ({mode})")
    print(f"  stamps: {st['stamps_mapped']:,} mapped to a planned instant, "
          f"{st['stamps_unmapped']:,} unmapped ({st['event_snapshots_unmapped']:,} event "
          f"snapshots skipped); {st['instants']:,} instants; "
          f"{st['event_snapshots_outside_seasons']:,} event snapshots outside the seasons")
    print(f"  events: {st['events_resolved']:,} resolved, {st['events_unresolved']:,} unresolved "
          f"(event snapshots: {st['event_snapshots_resolved']:,} resolved, "
          f"{st['event_snapshots_unresolved']:,} unresolved, {st['payloads_missing']:,} "
          f"payloads missing)")
    print(f"  far: {st['events_far_from_tip']:,} events ({st['event_snapshots_far_from_tip']:,} "
          f"event snapshots) placed on an ESPN game whose tip is "
          f"{REPLAY_MAX_TIP_GAP.total_seconds() / 3600:g} hours or more from their own start, "
          f"not stored")
    print(f"  rows: {st['rows_parsed']:,} parsed, {st['rows_marked_in_play']:,} marked in-play, "
          f"{st['rows_kept']:,} kept by the keeper, {st['rows_already_stored']:,} already stored, "
          + (f"{st['rows_inserted']:,} inserted, {st['write_errors']:,} instants failed to write"
             if apply else f"{st['rows_to_insert']:,} would be inserted"))
    print("  replay", resolver.report())
    return dict(st)


def _read_only_connection():
    """get_connection(), unable to write: the dry run's connection.

    psycopg2's set_session(readonly=True) opens EVERY transaction as BEGIN
    READ ONLY, which holds through Supabase's transaction pooler, the port
    get_connection() dials. A SET SESSION CHARACTERISTICS AS TRANSACTION READ
    ONLY is not used: on that port a session setting stays on whichever server
    connection ran it, where another client's next transaction would inherit
    it (data/db.py: no session settings on the transaction port). Reconnecting
    is switched off, because a fresh connection would not be read only.
    Raises unless the server reports transaction_read_only = on."""
    conn = get_connection()
    conn._url = None
    conn._conn.set_session(readonly=True)
    state = conn.execute("SHOW transaction_read_only").fetchone()[0]
    conn.rollback()
    if state != "on":
        conn.close()
        raise RuntimeError(f"the dry run's connection is not read only "
                           f"(transaction_read_only = {state!r})")
    return conn


def _run_replay(first: int, last: int, apply: bool) -> dict:
    conn = get_connection() if apply else _read_only_connection()
    try:
        out = replay_unmatched(conn, first, last, apply=apply)
    finally:
        conn.close()
    print("replay:", out)
    return out


# ── command line ─────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    what = ap.add_mutually_exclusive_group(required=True)
    what.add_argument("--lines", action="store_true", help="bulk game lines, every planned snapshot")
    what.add_argument("--derivatives", choices=("close", "open"),
                      help="first-half lines and team totals, one snapshot a game")
    what.add_argument("--probe", action="store_true",
                      help="one measured paid call of each kind, writes nothing")
    what.add_argument("--replay-unmatched", action="store_true",
                      help="store the kept raw events that resolve now; no paid call; "
                           "a read-only dry run unless --apply")
    ap.add_argument("--seasons", nargs=2, type=int, metavar=("FIRST", "LAST"), required=True,
                    help="ending years (2026 = the 2025-26 season)")
    ap.add_argument("--max-credits", type=int, help="the ceiling; required with --apply")
    ap.add_argument("--floor", type=int,
                    help=f"stop before the balance falls below this; required with --apply, "
                         f">= {MIN_FLOOR:,}")
    ap.add_argument("--apply", action="store_true",
                    help="spend (the purchases) or write (the replay); without it, a dry run")
    ap.add_argument("--dry-run", action="store_true",
                    help="write nothing: the default without --apply")
    a = ap.parse_args()
    first, last = a.seasons
    if first > last:
        ap.error("--seasons FIRST must not be after LAST")
    if a.apply and a.dry_run:
        ap.error("--apply and --dry-run contradict each other")
    if a.replay_unmatched:
        if a.max_credits is not None or a.floor is not None:
            ap.error("--replay-unmatched buys nothing; it takes no --max-credits or --floor")
        _run_replay(first, last, apply=a.apply)
        return
    if a.floor is not None and a.floor < MIN_FLOOR:
        ap.error(f"--floor must be at least {MIN_FLOOR:,} (the live feeds' reserve)")
    if a.apply and (not a.max_credits or a.max_credits <= 0):
        ap.error("--apply needs --max-credits")
    if a.apply and a.floor is None:
        ap.error("--apply needs --floor")
    conn = get_connection()
    try:
        if not a.apply:
            _dry_run(conn, a, first, last)
            return
        meter = Meter(ceiling=a.max_credits, floor=a.floor)
        if a.probe:
            print("probe:", probe(conn, meter, last))
        elif a.lines:
            print("lines:", buy_lines(conn, meter, first, last))
        else:
            print(f"derivatives {a.derivatives}:",
                  buy_derivatives(conn, meter, first, last, a.derivatives))
        print(f"spent {meter.spent:,} credits; balance {meter.remaining}")
    finally:
        try:
            persist_quota(conn)
        finally:
            conn.close()


def _dry_run(conn, a, first: int, last: int) -> None:
    """The plan and its credit estimate. Spends nothing; raises on the precondition."""
    if a.probe:
        print(f"dry run: --probe would buy 1 bulk snapshot (~{LINE_SNAPSHOT_COST}), 1 event "
              f"list ({LIST_COST}) and 1 game's derivatives (<= {DERIV_EVENT_COST}) on "
              f"{_busiest_date(conn, last)}; re-run with --apply --max-credits N --floor N")
        return
    print("precondition:", check_precondition(conn, list(range(first, last + 1))))
    if a.lines:
        games, pairs, todo = plan_lines(conn, first, last)
        by_season = Counter((w.year + 1 if w.month >= 10 else w.year) for w in todo)
        print(f"dry run: lines {len(games):,} games -> {len(pairs):,} snapshots, "
              f"{len(todo):,} to buy (~{LINE_SNAPSHOT_COST * len(todo):,} credits); "
              f"by season {dict(sorted(by_season.items()))}")
    else:
        _, games, done = plan_derivatives(conn, first, last, a.derivatives)
        n = len(games) - len(done)
        dates = len({g["game_date"] for g in games if g["game_id"] not in done})
        print(f"dry run: derivatives {a.derivatives} {n:,} games on {dates:,} dates to buy "
              f"(<= ~{DERIV_EVENT_COST * n + LIST_COST * dates:,} credits), {len(done):,} stored")
    print("re-run with --apply --max-credits N --floor N")


if __name__ == "__main__":
    main()
