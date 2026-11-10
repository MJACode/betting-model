"""College football first-half lines and team totals, 2023-2025, from The Odds API.

WHY. The 2026-11-10 market audit (docs/ncaaf_market_audit.md, section 7) found
that first-half and team-total prices have never been stored for NCAAF, so no
model on those markets can be graded. mike, 2026-11-10: "Buy all". On NCAAB the
two first-half models came out of exactly this purchase
(data/ingestors/ncaab_odds_history.py, --derivatives).

WHAT IS BOUGHT. For every NCAAF game of 2023, 2024 and 2025 that already holds
stored full-game historical prices: the first-half moneyline, spread and total
and the team totals (h2h_h1, spreads_h1, totals_h1, team_totals) at the ten
fetched books (config.LINE_SHOP_BOOKMAKERS; ten names bill as one region), at
the same two moments the full-game prices are stored at. So a first-half line
can be set beside the full-game line of the same moment.

THE TWO READS. The stored full-game history (`odds`, source
'odds_api_historical') was bought as two pulls a day, asked for at 14:00 and
23:00 UTC and served at about 13:55 and 22:55.

  am  14:00 UTC on the game's Eastern date (game-day morning)
  pm  23:00 UTC on the Eastern date before (the evening before)

A game is bought at a read only when BOTH hold:

  * it holds a stored full-game row from that pull: a row of that source
    stamped after one hour before the instant and no later than it (PULL_WINDOW);
  * it kicks off more than five minutes after the instant (KICKOFF_MARGIN), so
    no price bought here can be in play.

The feed is asked for its snapshot at the instant (the historical endpoints
take a `date` and answer with the snapshot at or before it), so the answer is
the same snapshot the full-game pull was served.

ONE REAL GAME, ONE PURCHASE, UNDER THE ID THAT HOLDS THE PRICES. A game can sit
in `games` twice. A night game has the odds feed's Eastern-dated row, which
carries the prices, beside CFBD's UTC-dated row, which carries the score
(docs/sports/ncaaf.md, "Data / conventions"). And the stored full-game history
was written on 2026-09-07, before the team registry held FCS schools, so some
of its rows carry the feed's own team name ("Furman Paladins") beside CFBD's
row under the school's ("Furman"). Rows whose two names resolve to the same
two schools, dated within a day of each other, are one game (real_games). It
is bought once and stored under the id that holds the stored pull at that
read; when two ids of one game both hold it, under the one with more stored
rows. `scored` in the plan means any row of the game has a final.

THE PLAN, MEASURED 2026-11-10 on the audit's extract of the local copy of the
database (not production): 2,510 games on 180 dates at `am`, at most 100,580
credits; 2,435 on 186 at `pm`, at most 97,586. At `am`, 2,467 have a final;
210 of those get it from a CFBD row under another spelling of the school.
The audit's "2,314 games on 205 dates" (92,765 credits a read) counted games
with any stored pull, not either read: its own extract holds 2,257 games with
a final on 180 dates at the morning read and 2,227 on 183 the evening before.

THE CALLS. One historical event list per date and read names each game's event
(1 credit). Then one historical event-odds call per game: the feed bills 10
credits per market it returns, so at most 40 a game; an empty answer and a
not-found are free. Calls run side by side through the NCAAB purchase's meter
(ncaab_odds_history.PoolMeter and _paid_calls): every call is cleared against
the ceiling and the floor with the calls in flight counted at their most.

MATCHING. A feed event is placed on one of our games by its two team names,
through the repo's NCAAF name resolution (odds_ingestor._normalize_team:
config.NCAAF_ODDS_API_MAP, then the ncaaf_teams registry), and its kickoff
time (within MATCH_WINDOW of the stored kickoff). Each name is tried as the
school it resolves to today and as the feed's own name, which is what a row
written before the name resolved still holds (EventMatcher). An event that
lands on no planned game, or on two, or whose home side cannot be told, is
counted, printed and skipped, never guessed. A row stored under a wrong
school by the old prefix rule (Florida A&M as Florida) matches nothing. When
the feed calls our away team home, the names are swapped before the outcomes
are read, so the stored spread is our home team's number (CLAUDE.md section 4).
The registry is read fresh before the first call, and a purchase refuses to
start when it is empty: without it no feed name lands on a stored school, and
every date's list would be paid for to match nothing (check_registry).

WHERE IT IS STORED. `odds`, exactly as the NCAAB purchase stores the same four
markets (parse_derivatives is imported from it): markets h2h_h1, spreads_h1,
totals_h1, team_totals_home and team_totals_away; snapshot_type 'open';
snapshot_at the snapshot time the feed served; created_at the table's own
default. Sources NCAAF_DERIV_AM_SOURCE and NCAAF_DERIV_PM_SOURCE, both named in
data/prune_odds.PROTECTED_SOURCES.

NOTHING IS BOUGHT TWICE. `ncaaf_derivative_fetches` (worker-only) holds one row
per game and read: when it was asked for, what the feed served, the credits
the call billed, the rows stored and a status. The odds rows and the ledger
row are written in one transaction. A rerun skips every game whose row says
'stored' or 'empty' (HELD_STATUSES). A game the feed did not list, a not-found
and a failed call are recorded too and asked for again on a rerun; listing a
date again costs 1 credit. The ledger is read again just before each date is
listed, so a second process started meanwhile buys nothing the first holds.

CREDITS. Without --apply it prints the plan and makes no call: no meter is
built and the connection is read only. --apply needs --max-credits and
--floor. Both limits are then tightened by what the system measures
(odds_quota.plan_credit_budget): the ceiling is the smaller of --max-credits
and the plan's own most, the floor the larger of --floor and --reserve-days of
the median daily burn in odds_api_quota. With no burn rate or no balance on
record it refuses to start. The balance is read off every response's
x-requests-remaining. NEWEST DATE FIRST, so a stop leaves the most recent
season stored.

A ceiling bounds one process and starts at zero: it does not know what an
earlier, interrupted run spent. What keeps a rerun from paying twice is the
ledger, not the ceiling.

    python -m data.ingestors.ncaaf_derivative_history --read both
    python -m data.ingestors.ncaaf_derivative_history --read am --sample 50
    python -m data.ingestors.ncaaf_derivative_history --read am --sample 50 --apply --max-credits 2050 --floor 300000
    python -m data.ingestors.ncaaf_derivative_history --read both --apply --max-credits 198166 --floor 300000
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from loguru import logger

import config
from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current
from data.db import get_connection
from data.ingestors.nba_odds_history import _ODDS_KEYS, _write_with_retry
from data.ingestors.ncaab_odds_history import (BOOKS, DEFAULT_CONCURRENCY, DERIV_EVENT_COST,
                                               DERIV_MARKETS, LIST_COST, MAX_CONCURRENCY,
                                               MIN_FLOOR, REPORT_MARKETS, PoolMeter, _billed,
                                               _end_read, _paid_calls, _rank,
                                               _read_only_connection, _stamp, _utc,
                                               parse_derivatives)
from data.ingestors.odds_ingestor import (HISTORICAL_ODDS_SOURCE, _insert_odds, _mark_in_play,
                                          _name_key, _normalize_team)
from data.ingestors.odds_quota import DEFAULT_RESERVE_DAYS, persist_quota, plan_credit_budget

SPORT = "NCAAF"
SPORT_KEY = "americanfootball_ncaaf"
BASE = f"{config.ODDS_API_BASE}/historical/sports/{SPORT_KEY}"
ET = ZoneInfo("America/New_York")

# The seasons the purchase was approved for (mike, 2026-11-10), which are the
# seasons that hold the two-a-day full-game pulls. NCAAF seasons are labelled
# by the year of the fall (CLAUDE.md section 4), so a January bowl is 2025's.
SEASONS = (2023, 2025)

READS = ("am", "pm")
NCAAF_DERIV_AM_SOURCE = "odds_api_ncaaf_derivative_am"
NCAAF_DERIV_PM_SOURCE = "odds_api_ncaaf_derivative_pm"
# One source a read, so a later reader can tell the two moments apart. Named
# exactly as data/prune_odds.PROTECTED_SOURCES lists them.
SOURCES = {"am": NCAAF_DERIV_AM_SOURCE, "pm": NCAAF_DERIV_PM_SOURCE}
READ_HOUR_UTC = {"am": 14, "pm": 23}        # the hour the full-game pull was asked for
READ_DAY = {"am": 0, "pm": -1}              # days from the game's Eastern date
READ_LABEL = {"am": "14:00 UTC on the game's Eastern date",
              "pm": "23:00 UTC on the Eastern date before"}
PULL_WINDOW = timedelta(hours=1)            # a stored row this close before the instant is that pull's
KICKOFF_MARGIN = timedelta(minutes=5)       # a game must kick off later than this after the instant
MATCH_WINDOW = timedelta(hours=24)          # a listing this far from the stored kickoff is another game
TWIN_DAYS = 1                               # the same two teams this close in date are one game

LEDGER = "ncaaf_derivative_fetches"
LEDGER_COLS = ("game_id", "read_slot", "requested_at", "served_at", "event_id", "credits",
               "rows_stored", "status", "fetched_at")
LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS ncaaf_derivative_fetches (
    game_id       TEXT NOT NULL,
    read_slot     TEXT NOT NULL,
    requested_at  TIMESTAMPTZ NOT NULL,
    served_at     TIMESTAMPTZ,
    event_id      TEXT,
    credits       INTEGER NOT NULL DEFAULT 0,
    rows_stored   INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL,
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (game_id, read_slot)
)
"""
# What a ledger row can say. Only the first two mean "bought": a rerun skips
# them. The others record a call that returned no answer to store, and are
# asked for again.
STORED, EMPTY, NOT_FOUND, UNLISTED, ERROR = "stored", "empty", "not_found", "unlisted", "error"
HELD_STATUSES = (STORED, EMPTY)
# A held row is never rewritten: not by a second process, not by a later error.
_LEDGER_UPSERT = """
    INSERT INTO ncaaf_derivative_fetches
           (game_id, read_slot, requested_at, served_at, event_id, credits, rows_stored,
            status, fetched_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
    ON CONFLICT (game_id, read_slot) DO UPDATE
       SET requested_at = EXCLUDED.requested_at, served_at = EXCLUDED.served_at,
           event_id = EXCLUDED.event_id, credits = EXCLUDED.credits,
           rows_stored = EXCLUDED.rows_stored, status = EXCLUDED.status, fetched_at = NOW()
     WHERE ncaaf_derivative_fetches.status NOT IN ('stored', 'empty')
"""
_LEDGER_HELD_SQL = ("SELECT game_id FROM ncaaf_derivative_fetches WHERE read_slot = %s "
                    "AND status = ANY(%s) AND game_id = ANY(%s)")

_GAMES_SQL = ("SELECT game_id, season, game_date, home_team, away_team, commence_time, "
              "home_score, away_score FROM games WHERE sport = %s AND season BETWEEN %s AND %s")
# Which pulls each game holds: every stored full-game row's stamp, moved up to
# the end of its hour (13:55:38 and 14:00:00 both read 14:00, 13:00:00 reads
# 13:00), and counted. The stamp is TEXT in mixed shapes, so it is cast before
# it is compared (the cast odds_ingestor.relabel_in_play uses). Read by game
# id, the table's index, _PULL_CHUNK games a query: `odds` is the table the
# app and every scorer read, so no one query walks a whole season of it.
_PULL_CHUNK = 200
_PULLS_SQL = """
    SELECT game_id, pull_instant, COUNT(*) FROM (
        SELECT game_id,
               date_trunc('hour',
                          (CASE WHEN snapshot_at LIKE '%%Z'
                                  OR snapshot_at ~ '[+-][0-9]{2}:[0-9]{2}$'
                                THEN snapshot_at::timestamptz
                                ELSE (snapshot_at || 'Z')::timestamptz END)
                          + interval '1 hour' - interval '1 microsecond',
                          'UTC') AS pull_instant
          FROM odds
         WHERE game_id = ANY(%s) AND source = %s) stamped
     GROUP BY game_id, pull_instant
"""
_COVERAGE_SQL = ("SELECT DISTINCT bookmaker, market, game_id FROM odds "
                 "WHERE game_id = ANY(%s) AND source = %s "
                 "AND snapshot_type IS DISTINCT FROM 'in_play'")
_CHUNK = 500


# ── the two reads ────────────────────────────────────────────────────────────

def read_instant(eastern_date: date, read: str) -> datetime:
    """The instant a read asks the feed for: am 14:00 UTC on the game's
    Eastern date, pm 23:00 UTC on the Eastern date before."""
    if read not in READS:
        raise ValueError(f"read must be one of {READS}, got {read!r}")
    d = eastern_date + timedelta(days=READ_DAY[read])
    return datetime(d.year, d.month, d.day, READ_HOUR_UTC[read], tzinfo=timezone.utc)


def _day(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _eastern_date(kick: datetime | None, game_date) -> date | None:
    """A game's Eastern date: its kickoff's, or its stored date when no
    kickoff is stored (the odds feed's row is dated by Eastern kickoff)."""
    return kick.astimezone(ET).date() if kick is not None else _day(game_date)


# ── what is stored ───────────────────────────────────────────────────────────

def load_games(conn, first: int, last: int) -> list[dict]:
    """Every NCAAF `games` row of seasons first..last."""
    rows = conn.execute(_GAMES_SQL, (SPORT, first, last)).fetchall()
    return [{"game_id": r[0], "season": int(r[1]), "game_date": str(r[2])[:10],
             "home_team": r[3], "away_team": r[4], "commence_time": r[5],
             "home_score": r[6], "away_score": r[7]} for r in rows]


def stored_pulls(conn, game_ids: list[str]) -> dict[str, dict[datetime, int]]:
    """{game_id: {pull instant: stored full-game rows}}. A row stamped after
    13:00 and no later than 14:00 UTC counts under 14:00."""
    out: dict[str, dict[datetime, int]] = defaultdict(dict)
    for i in range(0, len(game_ids), _PULL_CHUNK):
        for gid, at, n in conn.execute(
                _PULLS_SQL, (game_ids[i:i + _PULL_CHUNK], HISTORICAL_ODDS_SOURCE)).fetchall():
            when = _utc(at)
            if when is not None:
                out[gid][when] = out[gid].get(when, 0) + int(n)
    return dict(out)


def real_games(games: list[dict], school=None) -> list[list[dict]]:
    """`games` rows grouped into real games: rows with the same two schools
    dated within TWIN_DAYS of each other are one game (the odds feed's
    Eastern-dated row beside CFBD's UTC-dated one). A rematch weeks later is
    its own game; a row with no readable date stands alone.

    A STORED NAME IS RESOLVED BEFORE IT IS COMPARED. The stored full-game
    history was written on 2026-09-07, when the team registry held FBS
    schools only and Southern Miss had no map entry, so those rows carry the
    feed's own name ("Furman Paladins", "Southern Mississippi Golden Eagles")
    where CFBD's row for the same game, the one with the final, says "Furman"
    and "Southern Miss". Measured on the local copy of the database,
    2026-11-10: 245 of the 2,545 games with a game-day morning pull are
    stored that way. `school` is the name resolution (today's, by default);
    a name it cannot place stays as it is."""
    school = school or _school
    keys: dict[str, str] = {}

    def key(name: str) -> str:
        if name not in keys:
            keys[name] = _name_key(school(name or "")) or _name_key(name or "")
        return keys[name]

    by_pair: dict[frozenset, list[dict]] = defaultdict(list)
    for g in games:
        by_pair[frozenset((key(g["home_team"]), key(g["away_team"])))].append(g)
    out: list[list[dict]] = []
    for rows in by_pair.values():
        rows = sorted(rows, key=lambda g: (str(g["game_date"]), g["game_id"]))
        group = [rows[0]]
        for g in rows[1:]:
            a, b = _day(group[-1]["game_date"]), _day(g["game_date"])
            if a is not None and b is not None and (b - a).days <= TWIN_DAYS:
                group.append(g)
            else:
                out.append(group)
                group = [g]
        out.append(group)
    return sorted(out, key=lambda grp: (str(grp[0]["game_date"]), grp[0]["game_id"]))


@dataclass(frozen=True)
class Planned:
    """One real game at one read: what is asked for, and under which id."""
    game_id: str            # the `games` row that holds the stored full-game pull
    season: int
    eastern_date: str
    home: str               # our home team, as `games` stores it
    away: str
    kick: datetime | None
    read: str
    instant: datetime
    scored: bool            # any row of the real game has a final
    pull_rows: int          # stored full-game rows from this pull


def plan_read(games: list[dict], pulls: dict[str, dict[datetime, int]],
              read: str, school=None) -> tuple[list[Planned], Counter]:
    """The games one read buys, newest date first, and why the rest are not
    bought.

    Each real game is taken once. Each of its rows is asked whether it holds
    a stored full-game row from the read's pull; the row that holds the most
    is the id the purchase is stored under."""
    plan: list[Planned] = []
    why: Counter = Counter()
    for group in real_games(games, school):
        kicks = [k for k in (_utc(g.get("commence_time")) for g in group) if k is not None]
        holders = []
        for g in group:
            kick = _utc(g.get("commence_time")) or (min(kicks) if kicks else None)
            eastern = _eastern_date(kick, g["game_date"])
            if eastern is None:
                continue
            at = read_instant(eastern, read)
            held = pulls.get(g["game_id"], {})
            if held.get(at):
                holders.append((held[at], sum(held.values()), g, kick, eastern, at))
        if not holders:
            why["no_stored_pull"] += 1
            continue
        # the most rows from this pull, then the most stored at all, then the id
        holders.sort(key=lambda h: (-h[0], -h[1], h[2]["game_id"]))
        n, _, g, kick, eastern, at = holders[0]
        if kick is not None and kick - at <= KICKOFF_MARGIN:
            why["kicks_off_before_read"] += 1
            continue
        why["twin_ids_not_bought"] += len(holders) - 1
        plan.append(Planned(
            game_id=g["game_id"], season=int(g["season"]), eastern_date=eastern.isoformat(),
            home=g["home_team"], away=g["away_team"], kick=kick, read=read, instant=at,
            scored=any(r.get("home_score") is not None for r in group), pull_rows=int(n)))
    plan.sort(key=lambda p: p.game_id)
    plan.sort(key=lambda p: p.instant, reverse=True)
    return plan, why


# ── the test buy: a few games, spread over the seasons and the kickoff times ─
#
# Strata are season x the kickoff's Eastern hour. Within a stratum games are
# ranked by a hash of the seed and the game id (ncaab_odds_history._rank), and
# the strata are taken in turn. A hash, not a draw, means a game's place never
# moves, so a rerun picks the same games and the ledger skips them. Its rows
# are stored under the full purchase's own source and ledger, so the full run
# skips them too.

SAMPLE_SEED = "ncaaf-derivative-sample-2026-11-10"
# (the Eastern hour a stratum ends before, label); an hour after midnight is late
KICK_BUCKETS = ((15, "before 3pm ET"), (18, "3-6pm ET"), (21, "6-9pm ET"),
                (30, "9pm ET or later"))


def kick_bucket(kick: datetime) -> str:
    """The Eastern kickoff-time stratum of a kickoff (KICK_BUCKETS)."""
    local = kick.astimezone(ET)
    hour = local.hour + (24 if local.hour < 6 else 0)
    return next(label for end, label in KICK_BUCKETS if hour < end)


def sample_games(plan: list[Planned], n: int, seed: str = SAMPLE_SEED) -> list[Planned]:
    """Up to n of `plan`, spread over season x kickoff-time strata. Pure and
    deterministic. A game with no stored kickoff is not drawn."""
    strata: dict[tuple, list[Planned]] = defaultdict(list)
    order = {label: i for i, (_, label) in enumerate(KICK_BUCKETS)}
    for p in plan:
        if p.kick is not None:
            strata[(p.season, kick_bucket(p.kick))].append(p)
    keys = sorted(strata, key=lambda k: (order[k[1]], -k[0]))
    for k in keys:
        strata[k].sort(key=lambda p: _rank(p.game_id, seed))
    out: list[Planned] = []
    i = 0
    while len(out) < n:
        took = False
        for k in keys:
            if i < len(strata[k]):
                took = True
                out.append(strata[k][i])
                if len(out) >= n:
                    break
        if not took:
            break
        i += 1
    out.sort(key=lambda p: p.game_id)
    out.sort(key=lambda p: p.instant, reverse=True)
    return out


# ── the ledger ───────────────────────────────────────────────────────────────

def ensure_ledger(conn) -> None:
    """Create the ledger once, locked down (it is worker-only,
    data/anon_readable.WORKER_ONLY_TABLES), and fire no DDL after that
    (data/ddl_guard.py). Only a purchase calls it: the dry run never creates."""
    if schema_is_current(conn, "ncaaf_derivative_fetches", columns=LEDGER_COLS,
                         rls=True, revoked_from=API_ROLES):
        return
    conn.execute(LEDGER_DDL)
    lock_down(conn, "ncaaf_derivative_fetches")
    conn.commit()


def ledger_held(conn, game_ids: list[str], read: str) -> set[str]:
    """The games of `game_ids` already bought at `read` (HELD_STATUSES).

    A database the ledger has never reached holds none (the dry run before
    the first purchase). Any other failure of the read is raised: answering
    "nothing is held" on an error would buy everything again."""
    held: set[str] = set()
    try:
        for i in range(0, len(game_ids), _CHUNK):
            held |= {r[0] for r in conn.execute(
                _LEDGER_HELD_SQL, (read, list(HELD_STATUSES), game_ids[i:i + _CHUNK])).fetchall()}
    except Exception:                                           # noqa: BLE001
        conn.rollback()
        row = conn.execute("SELECT to_regclass('public.ncaaf_derivative_fetches')").fetchone()
        if row and row[0]:
            raise
        return set()
    return held


def _ledger_write(conn, g: Planned, *, served, event_id, credits: int, rows: int,
                  status: str) -> None:
    conn.execute(_LEDGER_UPSERT, (g.game_id, g.read, g.instant, served, event_id,
                                  int(credits), int(rows), status))


# ── placing the feed's events on our games ───────────────────────────────────

class PreconditionError(RuntimeError):
    """The purchase would pay for event lists nothing can be matched to."""


def check_registry(conn) -> int:
    """How many schools `ncaaf_teams` holds, read now. Raises when it holds
    none or cannot be read.

    WHY. The name resolution answers with the feed's own name when it cannot
    read the registry, and keeps that empty read for the life of the process
    (cfbd_ingestor._load_schools). The worker runs every job in one process.
    With no registry "Ohio State Buckeyes" lands on no stored school, so every
    planned game would be recorded as not listed, after its date's list had
    been paid for. So the registry is read fresh before the first call, and an
    empty read is not left behind for the next job."""
    from data.ingestors import cfbd_ingestor
    cfbd_ingestor.reset_school_cache()
    schools = cfbd_ingestor._load_schools(conn)
    if not schools:
        cfbd_ingestor.reset_school_cache()
        _end_read(conn)
        raise PreconditionError(
            "ncaaf_teams is empty or unreadable, so no feed team name can be placed on a "
            "stored school; refresh it first (the ncaaf_teams_refresh job)")
    return len(schools)


def _school(name: str) -> str:
    """A feed team name as the school `games` stores: the repo's NCAAF
    resolution (config.NCAAF_ODDS_API_MAP, then the ncaaf_teams registry)."""
    return _normalize_team(name or "", SPORT)


class EventMatcher:
    """Feed events onto one read instant's planned games, by the two team
    names and the kickoff. `(game, flipped)` or None; never a guess.

    A FEED NAME IS TRIED TWO WAYS: as the school it resolves to today, and as
    the feed's own name. The second is what a row written on 2026-09-07 holds
    for a school the registry could not place that day (real_games): the
    event that row was stored from carries that same name, so equal names and
    an equal kickoff are the same game, not a guess. A row stored under a
    WRONG school (the old prefix rule turned "Florida A&M Rattlers" into
    "Florida") matches neither way and is left alone.

    `schools` is the run's memory of resolved names, so a name is resolved
    (and an unresolved one warned about) once a run, not once a date."""

    def __init__(self, games: list[Planned], schools: dict | None = None):
        self.by_pair: dict[frozenset, list[Planned]] = defaultdict(list)
        for g in games:
            self.by_pair[frozenset((_name_key(g.home), _name_key(g.away)))].append(g)
        self._schools: dict[str, tuple] = {} if schools is None else schools

    def names(self, name: str) -> tuple[str, ...]:
        """The folded names a stored row could carry for this feed name."""
        if name not in self._schools:
            both = (_name_key(_school(name)), _name_key(name))
            self._schools[name] = tuple(dict.fromkeys(k for k in both if k))
        return self._schools[name]

    def __call__(self, ev: dict) -> tuple[Planned, bool] | None:
        homes = self.names(ev.get("home_team") or "")
        aways = self.names(ev.get("away_team") or "")
        start = _utc(ev.get("commence_time"))
        if not homes or not aways or start is None:
            return None
        near: dict[str, tuple] = {}
        for pair in {frozenset((h, a)) for h in homes for a in aways if h != a}:
            for g in self.by_pair.get(pair, ()):
                if g.kick is not None:
                    gap = abs(g.kick - start)
                    if gap <= MATCH_WINDOW:
                        near[g.game_id] = (gap, g)
                elif start.astimezone(ET).date().isoformat() == g.eastern_date:
                    near[g.game_id] = (timedelta(0), g)
        if not near:
            return None
        ranked = sorted(near.values(), key=lambda x: (x[0], x[1].game_id))
        if len(ranked) > 1 and ranked[0][0] == ranked[1][0]:
            return None                     # two games equally near: not guessed
        g = ranked[0][1]
        ours = _name_key(g.home)
        if (ours in homes) == (ours in aways):
            return None                     # which side is our home team cannot be told
        return g, ours not in homes


# ── buying ───────────────────────────────────────────────────────────────────

def _event_params(at: datetime) -> dict:
    return {"date": _stamp(at), "markets": ",".join(DERIV_MARKETS), "bookmakers": BOOKS,
            "oddsFormat": "american"}


def buy_read(conn, meter, plan: list[Planned], read: str) -> dict:
    """Buy one read's planned games, newest date first, and return the counts.

    For each date: the ledger is read again, the date's event list is bought
    (1 credit) and each listed game not yet held is bought through
    _paid_calls (each call cleared with the calls in flight counted at 40).
    Every answer is stored with its ledger row in one transaction. A date
    whose list got no answer, and a game whose call got none, are tried once
    more at the end under the same meter."""
    source = SOURCES[read]
    ids = [p.game_id for p in plan]
    held = ledger_held(conn, ids, read)
    by_instant: dict[datetime, list[Planned]] = defaultdict(list)
    for p in plan:
        by_instant[p.instant].append(p)
    pending = {p.game_id: p for p in plan if p.game_id not in held}
    totals: dict = defaultdict(int)
    totals["games_planned"], totals["held_at_start"] = len(plan), len(held)
    done: set[str] = set(held)             # held, or answered by this run
    failed: list[tuple] = []               # (event, game, flipped): the call got no answer
    unlisted_dates: list[datetime] = []    # the date's list got no answer
    not_listed: list[str] = []             # planned games no listed event matched
    strangers: Counter = Counter()         # that date's listed events on no planned game
    seen_strangers: set[str] = set()
    schools: dict[str, str] = {}           # feed name -> stored school, resolved once a run
    logger.info(f"NCAAF first half and team totals, {read}: {len(pending):,} games to buy on "
                f"{len({p.instant for p in pending.values()}):,} dates, {len(held):,} held")
    # End the planning reads' transaction before the first paid call, so no
    # read lock is held across the HTTP waits of a long run.
    conn.commit()

    def record(g: Planned, **kw) -> bool:
        def _write():
            _ledger_write(conn, g, **kw)
            conn.commit()
        return _write_with_retry(conn, _write, f"{g.game_id} {read} ledger")

    def listed(at: datetime):
        """[(event, game, flipped)] for the date's games still to buy, or None
        when the list got no answer."""
        r = meter.get(f"{BASE}/events", {"date": _stamp(at)})
        if r is None or r.status_code != 200:
            totals["errors"] += 1
            return None
        totals["lists"] += 1
        body = r.json()
        events = body.get("data") or []
        match = EventMatcher(by_instant[at], schools)
        day = by_instant[at][0].eastern_date
        out, matched = [], set()
        for ev in events:
            hit = match(ev)
            if hit is None:
                start = _utc(ev.get("commence_time"))
                eid = str(ev.get("id"))
                if (start is not None and start.astimezone(ET).date().isoformat() == day
                        and eid not in seen_strangers):
                    seen_strangers.add(eid)
                    strangers[f"{ev.get('away_team')} @ {ev.get('home_team')}"] += 1
                continue
            g, flipped = hit
            if g.game_id in matched:
                totals["second_listings_skipped"] += 1
                continue
            matched.add(g.game_id)
            if g.game_id in pending:
                out.append((ev, pending.pop(g.game_id), flipped))
        for g in by_instant[at]:
            if g.game_id in pending and g.game_id not in matched:
                pending.pop(g.game_id)
                not_listed.append(g.game_id)
                totals["games_not_listed"] += 1
                record(g, served=_utc(body.get("timestamp")), event_id=None, credits=0,
                       rows=0, status=UNLISTED)
        return out

    def finish(ev: dict, g: Planned, flipped: bool, kick, resp) -> bool:
        """Store one game's answer with its ledger row; False = no answer."""
        code = getattr(resp, "status_code", None)
        credits = _billed(resp) if resp is not None else 0
        if code != 200:
            status = NOT_FOUND if code == 404 else ERROR
            totals["not_found" if status == NOT_FOUND else "errors"] += 1
            record(g, served=None, event_id=str(ev.get("id")), credits=credits, rows=0,
                   status=status)
            return status == NOT_FOUND     # a not-found is an answer; an error is retried
        body = resp.json()
        stamp = body.get("timestamp") or _stamp(g.instant)
        home_name, away_name = ev.get("home_team") or "", ev.get("away_team") or ""
        if flipped:
            # the feed called our away team home: parse in our orientation
            home_name, away_name = away_name, home_name
        rows = []
        for book in (body.get("data") or {}).get("bookmakers", []):
            for p in parse_derivatives(book.get("markets", []), home_name, away_name):
                row = dict.fromkeys(_ODDS_KEYS)
                row.update({"game_id": g.game_id, "sport": SPORT, "bookmaker": book.get("key"),
                            "snapshot_type": "open", "snapshot_at": stamp, "source": source})
                row.update(p)
                rows.append(row)
        if kick is not None:
            totals["marked_in_play"] += _mark_in_play(
                [{"game_id": g.game_id, "commence_time": kick.isoformat()}], rows)
        stored = {"n": 0}

        def _write():
            # Read the ledger INSIDE the unit: data.db raises ConnectionLost at
            # a commit whose acknowledgement was lost although the server may
            # have committed, and _write_with_retry then runs this again. The
            # rows and the ledger row commit together, so a held row means the
            # rows are in, by that attempt or by another process.
            if ledger_held(conn, [g.game_id], read):
                conn.commit()
                return
            if rows:
                _insert_odds(conn, rows)
            _ledger_write(conn, g, served=_utc(body.get("timestamp")),
                          event_id=str(ev.get("id")), credits=credits, rows=len(rows),
                          status=STORED if rows else EMPTY)
            # counted before the commit: a commit the server made and did not
            # acknowledge still stored them, and the replay then finds them held
            stored["n"] = len(rows)
            conn.commit()

        if not _write_with_retry(conn, _write, f"{g.game_id} {read}"):
            totals["errors"] += 1
            return False
        totals["rows"] += stored["n"]
        totals["empty"] += int(not rows)
        totals["events"] += 1
        totals["flipped"] += int(flipped)
        done.add(g.game_id)
        return True

    def buy_many(items: list[tuple], on_fail) -> tuple[str | None, set[int]]:
        """Buy each (event, game, flipped), storing each answer in the order
        asked. Returns (the stop reason or None, the indexes handled)."""
        handled: set[int] = set()

        def jobs():
            for i, (ev, g, _) in enumerate(items):
                kick = g.kick or _utc(ev.get("commence_time"))
                if kick is None or kick - g.instant <= KICKOFF_MARGIN:
                    # only a game with no stored kickoff reaches here: the
                    # feed's own start decides it, before any call
                    handled.add(i)
                    totals["no_kickoff" if kick is None else "kicks_off_before_read"] += 1
                    continue
                yield (i, kick), f"{BASE}/events/{ev['id']}/odds", _event_params(g.instant)

        def consume(key, resp):
            i, kick = key
            handled.add(i)
            ev, g, flipped = items[i]
            if not finish(ev, g, flipped, kick, resp):
                on_fail(ev, g, flipped)

        return _paid_calls(meter, jobs(), DERIV_EVENT_COST, consume), handled

    def run_date(at: datetime) -> bool:
        waiting = [g.game_id for g in by_instant[at] if g.game_id in pending]
        if not waiting:
            return True
        # bought meanwhile by another process: not listed for, not bought
        for gid in ledger_held(conn, waiting, read):
            pending.pop(gid)
            done.add(gid)
            totals["held_meanwhile"] += 1
        _end_read(conn)
        if not any(g.game_id in pending for g in by_instant[at]):
            return True
        # The check sits HERE, so the second pass over unanswered dates cannot
        # list one (1 credit) under the floor either.
        why = meter.stop_reason(LIST_COST + DERIV_EVENT_COST)
        if why:
            totals["stopped"] = why
            logger.warning(f"{read} stopping before listing {at:%Y-%m-%d %H:%M}Z: {why}")
            return False
        evs = listed(at)
        if evs is None:
            unlisted_dates.append(at)
            return True
        why, handled = buy_many(evs, lambda ev, g, flipped: failed.append((ev, g, flipped)))
        if why:
            totals["stopped"] = why
            logger.warning(f"{read} stopping at {at:%Y-%m-%d %H:%M}Z: {why}")
            return False
        return True

    stopped = False
    logged = 0
    for at in sorted(by_instant, reverse=True):
        if not run_date(at):
            stopped = True
            break
        if totals["lists"] >= logged + 25:
            logged = totals["lists"]
            logger.info(f"{read} {at:%Y-%m-%d}: {totals['events']:,} games so far, "
                        f"{totals['rows']:,} rows | spent {meter.spent:,}, "
                        f"balance {meter.remaining}")
    if not stopped:
        totals["dates_unlisted"] = len(unlisted_dates)
        for at in list(unlisted_dates):
            if not run_date(at):
                stopped = True
                break
        if not stopped and failed:
            totals["retried"] = len(failed)

            def still_failed(*_):
                totals["still_failed"] += 1
            why, _ = buy_many(list(failed), still_failed)
            if why:
                totals["stopped"] = why
    totals["left_unbought"] = len(set(ids) - done)
    if isinstance(meter, PoolMeter):
        totals["concurrency"] = meter.workers
        totals["rate_limited_429"] = meter.rate_limited
    totals["events_on_no_planned_game"] = len(seen_strangers)
    print(f"{read}: planned games the feed's list did not name: {len(not_listed)} "
          f"[{', '.join(not_listed[:25]) or 'none'}]")
    print(f"{read}: listed events of those dates placed on no planned game: "
          f"{len(seen_strangers)} "
          f"[{', '.join(f'{n} ({c})' for n, c in strangers.most_common(25)) or 'none'}]")
    return dict(totals)


# ── what was bought, read back from `odds` ───────────────────────────────────

def coverage(conn, plan: list[Planned], read: str) -> str:
    """For each book and market, how many of the read's bought games hold a
    quote. Read back from `odds` and the ledger, not from the run's counters."""
    ids = [p.game_id for p in plan]
    bought = sorted(ledger_held(conn, ids, read))
    have: dict[tuple, set] = defaultdict(set)
    for i in range(0, len(bought), _CHUNK):
        for book, market, gid in conn.execute(
                _COVERAGE_SQL, (bought[i:i + _CHUNK], SOURCES[read])).fetchall():
            if market in REPORT_MARKETS:
                have[(book, market)].add(gid)
                have[("any book", market)].add(gid)
                have[("any book", "any")].add(gid)
    _end_read(conn)
    books = ["any book"] + sorted({b for b, _ in have} - {"any book"})
    lines = [f"coverage, {read} ({SOURCES[read]}): {len(bought):,} of {len(ids):,} planned games "
             f"bought; {len(have[('any book', 'any')]):,} hold a quote",
             f"  each cell: bought games with a quote, of {len(bought):,}",
             "  " + "book".ljust(16) + "".join(m.ljust(18) for m in REPORT_MARKETS)]
    for b in books:
        lines.append("  " + b[:15].ljust(16)
                     + "".join(str(len(have[(b, m)])).ljust(18) for m in REPORT_MARKETS))
    return "\n".join(lines)


# ── the plan, printed ────────────────────────────────────────────────────────

@dataclass
class ReadPlan:
    read: str
    games: list            # the Planned games this run is for (the sample, with --sample)
    why: Counter           # why the other real games are not bought
    held: set              # ids of `games` the ledger already holds
    full: int              # planned games before any sample

    @property
    def todo(self) -> list:
        return [p for p in self.games if p.game_id not in self.held]

    @property
    def most(self) -> int:
        """The most this read can still bill: 40 a game, 1 a date's list."""
        todo = self.todo
        return DERIV_EVENT_COST * len(todo) + LIST_COST * len({p.instant for p in todo})


def build_plans(conn, first: int, last: int, reads, sample: int | None = None,
                school=None) -> dict:
    """{read: ReadPlan}. Reads `games`, the stored pulls and the ledger.
    `school` is the name resolution real_games groups by (today's, by
    default; the dry run passes the names as stored when the registry cannot
    be read)."""
    games = load_games(conn, first, last)
    pulls = stored_pulls(conn, [g["game_id"] for g in games])
    out = {}
    for read in reads:
        plan, why = plan_read(games, pulls, read, school)
        chosen = sample_games(plan, sample) if sample is not None else plan
        out[read] = ReadPlan(read, chosen, why, ledger_held(conn, [p.game_id for p in chosen], read),
                             len(plan))
    _end_read(conn)
    return out


def describe_plan(rp: ReadPlan, sample: int | None = None) -> str:
    """One read's plan: games and Eastern dates by season, how many have a
    final, what the ledger holds, and the most it can spend."""
    lines = [f"read {rp.read} ({READ_LABEL[rp.read]}), source {SOURCES[rp.read]}"
             + (f": test buy of {sample}, {len(rp.games)} sampled of {rp.full:,} planned"
                if sample is not None else "")]
    lines.append("  " + "".join(h.ljust(w) for h, w in (
        ("season", 8), ("games", 8), ("dates", 8), ("with a final", 14),
        ("their dates", 13), ("already bought", 14))))

    def row(label, games):
        scored = [p for p in games if p.scored]
        return "  " + "".join(str(v).ljust(w) for v, w in (
            (label, 8), (f"{len(games):,}", 8), (len({p.eastern_date for p in games}), 8),
            (f"{len(scored):,}", 14), (len({p.eastern_date for p in scored}), 13),
            (f"{sum(1 for p in games if p.game_id in rp.held):,}", 14)))

    for season in sorted({p.season for p in rp.games}, reverse=True):
        lines.append(row(season, [p for p in rp.games if p.season == season]))
    lines.append(row("all", rp.games))
    lines.append(f"  not planned: {rp.why['no_stored_pull']:,} real games hold no stored "
                 f"full-game pull at this read; {rp.why['kicks_off_before_read']:,} kick off "
                 f"within 5 minutes of it or before it; {rp.why['twin_ids_not_bought']:,} second "
                 f"ids of a game already counted")
    todo = rp.todo
    lines.append(f"  to buy: {len(todo):,} games on {len({p.instant for p in todo}):,} dates, at "
                 f"most {rp.most:,} credits ({DERIV_EVENT_COST} a game, {LIST_COST} a date's "
                 f"event list; an empty answer and a not-found are free)")
    return "\n".join(lines)


def _budget(conn, plans: dict, a):
    """(budget, problems) for the whole run: the ceiling the smaller of
    --max-credits and the plan's own most, the reserve measured."""
    most = sum(rp.most for rp in plans.values())
    cap = most if a.max_credits is None else min(a.max_credits, most)
    return most, plan_credit_budget(
        conn, shard_calls=most, total_calls=most, credits_per_call=1, max_credits=cap,
        reserve_days=a.reserve_days, burn_per_day=a.burn_per_day, remaining=a.remaining)


def _dry_run(conn, a, reads, first: int, last: int) -> None:
    """The plan and the most it can cost, printed. Reads only: no meter is
    built, so no call can be made."""
    problems: list[str] = []
    school = None
    try:
        registry = f"team registry: {check_registry(conn):,} schools in ncaaf_teams"
    except PreconditionError as exc:
        # still print a plan, with the names as they are stored, and say why
        # a purchase would not start
        registry, school, problems = None, (lambda name: name), [str(exc)]
    plans = build_plans(conn, first, last, reads, a.sample, school=school)
    print(f"dry run: NCAAF first-half lines and team totals, seasons {first}-{last}. "
          f"No call is made and nothing is written.")
    for read in reads:
        rp = plans[read]
        print(describe_plan(rp, a.sample))
        if a.sample is not None:
            for p in rp.games:
                when = f"{p.kick.astimezone(ET):%H:%M} ET ({kick_bucket(p.kick)})"
                print(f"  {p.eastern_date} kickoff {when}, would buy at "
                      f"{p.instant:%Y-%m-%d %H:%M}Z  {p.game_id}"
                      + ("  [bought]" if p.game_id in rp.held else ""))
            print(coverage(conn, rp.games, read))
    most, (budget, unmeasured) = _budget(conn, plans, a)
    _end_read(conn)
    print(f"all reads asked for: at most {most:,} credits")
    if registry:
        print(registry)
    if most:
        print("credit guards, measured (data/ingestors/odds_quota.py):\n" + budget.describe())
    for p in problems + (list(unmeasured) if most else []):
        print("WOULD REFUSE:", p)
    floor = max(MIN_FLOOR, budget.floor or 0)
    print(f"re-run with --apply --max-credits {most} --floor {floor}")


# ── command line ─────────────────────────────────────────────────────────────

def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--read", choices=READS + ("both",), required=True,
                    help="am: 14:00 UTC on the game's Eastern date; pm: 23:00 UTC the "
                         "Eastern date before; both: am then pm")
    ap.add_argument("--seasons", nargs=2, type=int, metavar=("FIRST", "LAST"),
                    default=list(SEASONS),
                    help=f"fall years, within {SEASONS[0]}..{SEASONS[1]} (the default)")
    ap.add_argument("--sample", type=int, metavar="N",
                    help="the test buy: N games a read, spread over the seasons and the "
                         "kickoff times, stored under the same sources and ledger")
    ap.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY, metavar="N",
                    help=f"paid calls in flight at once, 1..{MAX_CONCURRENCY} "
                         f"(default {DEFAULT_CONCURRENCY})")
    ap.add_argument("--apply", action="store_true", help="spend; without it, a dry run")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the plan and call nothing: the default without --apply")
    ap.add_argument("--max-credits", type=int,
                    help="the most the run may spend; required with --apply. The plan's own "
                         "most is the limit when it is smaller")
    ap.add_argument("--floor", type=int,
                    help=f"the balance the run will not go under; required with --apply, "
                         f">= {MIN_FLOOR:,}. The measured reserve is the limit when it is higher")
    ap.add_argument("--reserve-days", type=int, default=DEFAULT_RESERVE_DAYS,
                    help=f"days of the measured daily burn the balance must keep "
                         f"(default {DEFAULT_RESERVE_DAYS})")
    ap.add_argument("--burn-per-day", type=int,
                    help="state the daily burn when odds_api_quota cannot measure one")
    ap.add_argument("--remaining", type=int,
                    help="state the balance when odds_api_quota holds no reading")
    return ap


def main() -> None:
    ap = _parser()
    a = ap.parse_args()
    first, last = a.seasons
    if not SEASONS[0] <= first <= last <= SEASONS[1]:
        ap.error(f"--seasons must be FIRST <= LAST within {SEASONS[0]}..{SEASONS[1]}")
    if a.apply and a.dry_run:
        ap.error("--apply and --dry-run contradict each other")
    if a.sample is not None and a.sample < 1:
        ap.error("--sample N needs N >= 1")
    if not 1 <= a.concurrency <= MAX_CONCURRENCY:
        ap.error(f"--concurrency must be 1..{MAX_CONCURRENCY}")
    if a.floor is not None and a.floor < MIN_FLOOR:
        ap.error(f"--floor must be at least {MIN_FLOOR:,} (the live feeds' reserve)")
    if a.apply and (not a.max_credits or a.max_credits <= 0):
        ap.error("--apply needs --max-credits")
    if a.apply and a.floor is None:
        ap.error("--apply needs --floor")
    reads = READS if a.read == "both" else (a.read,)
    if not a.apply:
        conn = _read_only_connection()     # the dry run cannot write, by the server's word
        try:
            _dry_run(conn, a, reads, first, last)
        finally:
            conn.close()
        return
    if not config.ODDS_API_KEY:
        raise SystemExit("ODDS_API_KEY is not set")
    conn = get_connection()
    try:
        # first: the plan groups a game's rows by resolved names, and every
        # event is placed by them
        try:
            print(f"team registry: {check_registry(conn):,} schools in ncaaf_teams")
        except PreconditionError as exc:
            raise SystemExit(f"refusing to start: {exc}") from exc
        ensure_ledger(conn)
        plans = build_plans(conn, first, last, reads, a.sample)
        for read in reads:
            print(describe_plan(plans[read], a.sample))
        most, (budget, problems) = _budget(conn, plans, a)
        _end_read(conn)
        outs: dict = {}
        meter = None
        if most:
            print("credit guards, measured (data/ingestors/odds_quota.py):\n" + budget.describe())
            if problems:
                raise SystemExit("refusing to start: " + "; ".join(problems))
            floor = max(a.floor, budget.floor or 0)
            meter = PoolMeter(ceiling=budget.ceiling, floor=floor, workers=a.concurrency)
            # the balance on record, so the first call is checked against the floor too
            meter.remaining = budget.remaining_at_start
            print(f"ceiling {meter.ceiling:,} (the smaller of --max-credits {a.max_credits:,} "
                  f"and the plan's most {most:,}); floor {floor:,} (the larger of --floor "
                  f"{a.floor:,} and the measured reserve {budget.floor:,}); balance on record "
                  f"{meter.remaining:,}")
            for read in reads:
                outs[read] = buy_read(conn, meter, plans[read].games, read)
                if outs[read].get("stopped"):
                    break
        for read in reads:
            print(coverage(conn, plans[read].games, read))
        # the counts last, so the worker's tail of the printout keeps them
        for read, out in outs.items():
            print(f"{read}:", out)
        if meter is None:
            print("nothing to buy: every planned game is in the ledger")
        else:
            print(f"spent {meter.spent:,} credits; balance {meter.remaining}; "
                  f"{meter.workers} in flight at most; HTTP 429 answers {meter.rate_limited}")
    finally:
        try:
            persist_quota(conn)
        finally:
            conn.close()


if __name__ == "__main__":
    main()
