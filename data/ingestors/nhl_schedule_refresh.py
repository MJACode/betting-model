"""nhl_schedule_refresh.py -- the NHL season stored ahead in `games`, from the NHL's own API.

WHY THIS EXISTS (mike, 2026-10-20: schedule look-ahead for every sport). Until
this module an NHL game reached `games` only from the odds feed
(data/ingestors/odds_ingestor._process_events), so a game existed once a book
listed it. Of the 167 2026-27 rows stored by 2026-10-22, 134 were created 24.7
to 34.7 hours before puck drop and 33 opening-week rows earlier (31 on
2026-07-19, one on 07-21, one on 09-14); none on game day (production,
created_at against commence_time). The table held 2 future rows on 10-20. The
NBA got the same fix in #1028 (nba_schedule_refresh).

THE SOURCE. https://api-web.nhle.com/v1/schedule/<date> is free and keyless.
Each answer is one week (`gameWeek`, seven dated days with their games) and
`nextStartDate`, the next week that holds a game, so the walk skips breaks on
its own; it also carries regularSeasonEndDate and playoffEndDate. From
2026-10-22 the walk took 25 calls to reach the last regular-season game
(2027-04-10, 1,191 games), every one gameType 2, gameState FUT and
gameScheduleState OK. Each run starts LOOKBACK_DAYS before its date: one more
call, so a game called off after the last run is read again on its date.

THE KEY IS THE ODDS FEED'S, MEASURED. The id is NHL_{ET date}_{away}_{home},
built by nhl_stats_ingestor.parse_nhl_game (the results step's parser) with the
date taken from the ET date of startTimeUTC, which is how the odds feed dates a
game. Checked against production on 2026-10-22, read-only:
  * every scored NHL game of 2024-25 (1,398 on 224 dates) and 2025-26 (1,394
    on 211 dates) is stored under exactly the id the API builds (per-date
    hashes of the id sets, no date differing), and every one of them carries
    odds rows under that id. That covers the ten neutral-site and international
    games of the two seasons (Prague, Tampere, Stockholm, the Winter Classics,
    the Stadium Series) and the ARI -> UTA fold.
  * 2026-27 to 10-23: 167 of 167 stored rows match the API's ids, none extra.
  * the gameWeek date equals the ET date of startTimeUTC for all 4,136 regular
    season and playoff games of the three seasons.
TWO IDS FOR ONE GAME. A book that keys a game with home and away the other way
round (the risk is a neutral site) gives it a second id. Both orders are
handled: a listed game that would sit beside a stored row of the same two teams
that day under another id is not inserted (`conflicts`), and a row this refresh
wrote first is removed once a row it did not write holds the same two teams
that day (`twins`): the book's row is the game.

WHAT IT WRITES. Only NHL rows, never a score, never a row the odds feed or the
results step wrote. "Its own" row below means data_source still DATA_SOURCE and
no score:
  * a regular-season or playoff game the API lists as scheduled (state OK, not
    an if-necessary playoff game, both teams known, not started) that `games`
    lacks is inserted with data_source 'nhl_schedule' (DATA_SOURCE).
  * its own unplayed row follows the API's start time when it moves, and has
    updated_at stamped when the API confirms it: that stamp is what the health
    check reads.
  * its own row is removed (only with no odds, no pick, and no other table
    referencing it: the delete runs in a savepoint and a foreign key keeps it)
    when it is a twin of a book's row; when the API lists the game that day as
    postponed or cancelled; when its start has passed and the API does not list
    it that day (the game did not happen; a game the league played is listed,
    and the results step, which runs first, scores it); or, still ahead, when
    the API no longer lists it that day with no reason given. A moved game is
    therefore re-keyed, which is how its date is "updated": the date is part of
    the id. Only the last kind is capped, at MAX_ORPHAN_DELETES a run: more
    is more likely a changed team code or a broken answer, and the step fails
    instead. Once such a row's start passes it is removed by the next run.
From the odds feed's first upsert the row is the feed's (data_source 'live',
odds_ingestor._upsert_games): its start time is the books' start, about ten
minutes after the league's, and moving it back would flip it every day.

WHO SEES THESE ROWS. A row no book has listed yet must not cause a bet, a
purchase or an alarm the old table could not. The readers that act on a game
skip it (`listed_by_a_book`): the scorer's game loop, the NHL slate the goalie
poll, the goalie window and the prop cards share (scripts/nhl_prop_card.slate),
the totals card's slate and the prop-odds purchase. No NHL model input
changes: the only NHL reader of the shared schedule (data/schedule_context) is
the last-night check (models/nhl_moneyline_anchored.stale_teams), which reads
the two days before a game. The rows do show in the app's seven-day forward
read (queries.fetchSlateGames), as the NBA's do.

FAIL-OPEN. The NHL API not answering leaves `games` exactly as it is; a week
that fails mid-walk limits the run to the weeks before it. The pipeline step
returns False either way (pipeline_runs names it), and the health check
nhl_schedule_refresh goes STALE after 36 hours with no confirmed row while
games this refresh wrote are still ahead.

    python -m data.ingestors.nhl_schedule_refresh              # fetch and write
    python -m data.ingestors.nhl_schedule_refresh --dry-run    # fetch, read, print the plan
"""
from __future__ import annotations

import argparse
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from loguru import logger

from data.db import call_in_savepoint, get_connection
from data.ingestors.nhl_stats_ingestor import (
    ALL_NHL_TEAMS,
    NHL_API_BASE,
    NHL_HEADERS,
    parse_nhl_game,
)

_ET = ZoneInfo("America/New_York")

# The marker on a row only this refresh has written. The odds feed replaces it
# with 'live' the first time a book lists the game.
DATA_SOURCE = "nhl_schedule"

SCHEDULED = "OK"              # gameScheduleState of a game that is on
NOT_STARTED = ("FUT", "PRE")  # gameState before puck drop
MAX_CALLS = 45                # a season from opening night is ~27 weeks
REQUEST_SLEEP = 0.25          # backfill_nhl_games' pause between weeks
# Postponements are a handful a season. More than this many of this refresh's
# own rows for games still ahead vanishing from the API at once, with no
# postponement or cancellation listed, is more likely a changed team code or a
# broken answer, and deleting them would be the wrong fix: those are held and
# the step fails. The cap is for rows still ahead only. A held row whose start
# passes is removed by the next run (plan's gone_past), because a row left on
# a date that has passed is not harmless: the last-night check reads it as a
# missing game log and holds both teams' side models, the missing-finals check
# goes critical, and the results recaps wait for it.
MAX_ORPHAN_DELETES = 8
# Each run reads the week before its date again, so a row for a game called off
# after one run (its start has passed by the next) is still inside the dates
# read and is seen to be gone. One extra call: the API answers a week at a time.
# Seven days, not the results step's three, so a week of failed runs, and the
# weekly recap's window, are still covered when the API answers again.
LOOKBACK_DAYS = 7
# The odds feed has listed every 2026-27 game at least 24.7 hours before its
# start. A row still only this refresh's that close to puck drop means the feed
# is down or filed the game under another id.
FEED_LISTS_BY_HOURS = 24


def listed_by_a_book(alias: str = "") -> str:
    """SQL: the row is not one only this refresh wrote: a book has listed it
    (the odds feed sets 'live') or another writer created it. For the readers
    that act on a game that has not been played. (The results step's upsert
    keeps data_source, so a game no book ever listed is still marked after it
    is scored; none of those readers reads a scored row.)"""
    col = f"{alias}.data_source" if alias else "data_source"
    return f"COALESCE({col}, '') <> '{DATA_SOURCE}'"


def _ts(value) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).strip().replace(" ", "T").replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ── the walk ─────────────────────────────────────────────────────────────────

def http_get_json(url: str) -> dict:
    """GET with one retry on a timeout, a dropped connection or a 5xx."""
    import requests
    last: Exception | None = None
    for attempt in range(2):
        try:
            resp = requests.get(url, headers=NHL_HEADERS, timeout=20)
            if resp.status_code < 500:
                resp.raise_for_status()
                return resp.json()
            last = requests.HTTPError(f"{resp.status_code} from {url}")
        except requests.HTTPError:
            raise
        except requests.RequestException as exc:
            last = exc
        time.sleep(2.0 * (attempt + 1))
    raise last  # type: ignore[misc]


def walk(start: date, get_json=None, sleep: float = REQUEST_SLEEP) -> dict:
    """Every week the API lists from `start` to the end of its season.

    -> {games: [(game dict, gameWeek date)], covered_to: the last day of the
        last week read, or None, weeks, calls, failed: None or why the walk
        stopped early, meta: the first answer's season dates}
    """
    get_json = get_json or http_get_json
    out = {"games": [], "covered_to": None, "weeks": 0, "calls": 0, "failed": None, "meta": {}}
    cursor = start.isoformat()
    stop = None
    while cursor and out["calls"] < MAX_CALLS:
        try:
            out["calls"] += 1
            data = get_json(f"{NHL_API_BASE}/schedule/{cursor}") or {}
        except Exception as exc:                          # noqa: BLE001 -- fail-open
            out["failed"] = f"week of {cursor}: {type(exc).__name__}: {str(exc)[:160]}"
            break
        if not out["meta"]:
            out["meta"] = {k: data.get(k) for k in (
                "regularSeasonStartDate", "regularSeasonEndDate", "playoffEndDate")}
            stop = data.get("playoffEndDate") or data.get("regularSeasonEndDate")
        week = data.get("gameWeek") or []
        if not week:
            break
        out["weeks"] += 1
        for day in week:
            d = str(day.get("date") or "")[:10]
            if not d:
                continue
            if out["covered_to"] is None or d > out["covered_to"]:
                out["covered_to"] = d
            for g in day.get("games") or []:
                out["games"].append((g, d))
        nxt = data.get("nextStartDate")
        if not nxt or nxt <= cursor or (stop and nxt > stop):
            break
        cursor = nxt
        if sleep:
            time.sleep(sleep)
    else:
        if cursor and out["calls"] >= MAX_CALLS:
            out["failed"] = f"stopped at {MAX_CALLS} calls with weeks still to read (next {cursor})"
    return out


# ── parsing (pure) ───────────────────────────────────────────────────────────

def et_date(start_utc: str | None) -> str | None:
    dt = _ts(start_utc)
    return dt.astimezone(_ET).date().isoformat() if dt else None


def game_rows(listed: list[tuple[dict, str]], now: datetime,
              counts: dict | None = None,
              called_off: set | None = None) -> tuple[list[dict], set[str]]:
    """(rows to keep stored, every id the API lists as scheduled).

    A row is a regular-season or playoff game, scheduled (state OK), not an
    if-necessary playoff game, between two known teams, not started. The id
    set covers every scheduled game of those types, started, played or not,
    so a row is never called gone because its game has begun. `called_off`,
    when given, collects the ids the API lists with any other schedule state
    (postponed, cancelled, suspended): the API's own reason a game is off."""
    counts = counts if counts is not None else {}

    def tally(k):
        counts[k] = counts.get(k, 0) + 1

    rows, listed_ids = [], set()
    for g, week_day in listed:
        if g.get("gameType") not in (2, 3):
            tally("other_type")                                  # preseason, All-Star
            continue
        start = g.get("startTimeUTC")
        day = et_date(start)
        if day is None:
            tally("no_start")
            continue
        if day != week_day:
            # Never seen (0 of 4,136, three seasons); the odds feed dates by the
            # ET start, so that wins.
            tally("date_disagrees")
            logger.warning(f"NHL schedule refresh: game {g.get('id')} is listed on {week_day} "
                           f"but starts {start} ({day} ET); keyed on {day}")
        row = parse_nhl_game({**g, "gameDate": day})
        if row is None:
            tally("unparsed")
            continue
        if (g.get("gameScheduleState") or "").upper() != SCHEDULED:
            tally(f"state_{(g.get('gameScheduleState') or 'none').lower()}")   # PPD, CNCL, SUSP
            if called_off is not None:
                called_off.add(row["game_id"])
            continue
        listed_ids.add(row["game_id"])
        if g.get("ifNecessary"):
            tally("if_necessary")
            continue
        if row["home_team"] not in ALL_NHL_TEAMS or row["away_team"] not in ALL_NHL_TEAMS:
            tally("unknown_team")
            continue
        state = (g.get("gameState") or "").upper()
        if state not in NOT_STARTED or _ts(start) <= now:
            tally("started")
            continue
        rows.append({
            "game_id": row["game_id"], "season": row["season"], "game_date": day,
            "home_team": row["home_team"], "away_team": row["away_team"],
            "commence_time": start, "neutral_site": 1 if g.get("neutralSite") else 0,
            "nhl_id": g.get("id"),
        })
    return rows, listed_ids


# ── the plan (pure) ──────────────────────────────────────────────────────────

def _mine(s: dict) -> bool:
    return s.get("data_source") == DATA_SOURCE and s.get("home_score") is None


def _same_two_teams(day_rows: list[dict], game_id: str, pair: set) -> dict | None:
    return next((x for x in day_rows
                 if x["game_id"] != game_id and {x["home_team"], x["away_team"]} == pair), None)


def plan(api: list[dict], listed_ids: set[str], stored: list[dict],
         covered: tuple[str, str], now: datetime, called_off: set | frozenset = frozenset()) -> dict:
    """What to write.

    `api`: game_rows' rows. `stored`: every NHL games row dated inside
    `covered` (lo, hi), with game_id, game_date, home_team, away_team,
    commence_time, data_source, home_score. `called_off`: ids the API lists
    as postponed, cancelled or suspended.

    Removal candidates are only ever this refresh's own rows (unscored, still
    marked DATA_SOURCE) dated inside `covered`:
      twins:      (own id, the other id) where a row it did not write holds the
                  same two teams that day under another id. That row is the
                  game (a book keyed it the other way round); ours goes.
      called_off: own rows the API lists on their date as postponed or
                  cancelled.
      gone_past:  own rows whose start has passed that the API does not list
                  on their date: the game did not happen that day. A game the
                  league played is listed (state OFF) and is left for the
                  results step.
      orphans:    own rows still ahead that the API no longer lists, with no
                  reason given. Only these are capped (MAX_ORPHAN_DELETES).

    -> {insert: rows `games` lacks, times: (game_id, new start, old start) for
        this refresh's own unplayed rows whose start moved, confirm: own rows
        the API lists unchanged, twins, called_off, gone_past, orphans,
        conflicts: (api id, stored id) of the same two teams on the same date
        under another id (not inserted), unlisted_soon: own rows starting
        within FEED_LISTS_BY_HOURS that no book has listed}
    """
    lo, hi = covered
    by_id = {s["game_id"]: s for s in stored}
    by_day: dict[str, list[dict]] = {}
    for s in stored:
        by_day.setdefault(str(s["game_date"])[:10], []).append(s)
    out = {"insert": [], "times": [], "confirm": [], "twins": [], "called_off": [],
           "gone_past": [], "orphans": [], "conflicts": [], "unlisted_soon": []}

    # First: own rows whose game a book has since listed under another id.
    twinned: set[str] = set()
    for s in stored:
        d = str(s["game_date"])[:10]
        if not _mine(s) or not (lo <= d <= hi):
            continue
        other = _same_two_teams([x for x in by_day.get(d, []) if x.get("data_source") != DATA_SOURCE],
                                s["game_id"], {s["home_team"], s["away_team"]})
        if other is not None:
            out["twins"].append((s["game_id"], other["game_id"]))
            twinned.add(s["game_id"])

    for r in api:
        s = by_id.get(r["game_id"])
        if s is None:
            twin = _same_two_teams(by_day.get(r["game_date"], []), r["game_id"],
                                   {r["home_team"], r["away_team"]})
            if twin is not None:
                out["conflicts"].append((r["game_id"], twin["game_id"]))
            else:
                out["insert"].append(r)
            continue
        if not _mine(s) or s["game_id"] in twinned:
            continue                                  # the odds feed's or the results step's
        old = _ts(s.get("commence_time"))
        if old is not None and old <= now:
            continue                                  # started by our record: its start is never moved
        if _ts(r["commence_time"]) != old:
            out["times"].append((r["game_id"], r["commence_time"], s.get("commence_time")))
        else:
            out["confirm"].append(r["game_id"])

    soon = now + timedelta(hours=FEED_LISTS_BY_HOURS)
    for s in stored:
        gid, d = s["game_id"], str(s["game_date"])[:10]
        if not _mine(s) or gid in twinned or not (lo <= d <= hi):
            continue
        start = _ts(s.get("commence_time"))
        started = start is not None and start <= now
        if gid in listed_ids:
            if start is not None and now < start <= soon:
                out["unlisted_soon"].append(gid)
            continue                                  # listed: ahead, live or played
        if gid in called_off:
            out["called_off"].append(gid)
        elif started:
            out["gone_past"].append(gid)
        else:
            out["orphans"].append(gid)
    return out


# ── reads and writes ─────────────────────────────────────────────────────────

_STORED_COLS = ("game_id", "game_date", "home_team", "away_team", "commence_time",
                "data_source", "home_score")


def read_stored(conn, lo: str, hi: str) -> list[dict]:
    rows = conn.execute(f"""
        SELECT {', '.join(_STORED_COLS)} FROM games
         WHERE sport = 'NHL' AND game_date >= %s AND game_date <= %s
    """, (lo, hi)).fetchall()
    return [dict(zip(_STORED_COLS, r)) for r in rows]


_INSERT = """
    INSERT INTO games (game_id, sport, season, game_date, home_team, away_team,
        neutral_site, commence_time, data_source, created_at, updated_at)
    VALUES (%s, 'NHL', %s, %s, %s, %s, %s, %s, %s, NOW()::TEXT, NOW()::TEXT)
    ON CONFLICT (game_id) DO NOTHING
"""
# Every write below names the row as this refresh's own: unscored and still
# marked DATA_SOURCE. A row the odds feed reached between the read and the
# write is the feed's, and is left alone.
_MINE = "sport = 'NHL' AND data_source = %s AND home_score IS NULL"
_TIMES = f"UPDATE games SET commence_time = %s, updated_at = NOW()::TEXT WHERE game_id = %s AND {_MINE}"
_CONFIRM = f"UPDATE games SET updated_at = NOW()::TEXT WHERE game_id = ANY(%s) AND {_MINE}"
_DELETE = f"""
    DELETE FROM games g
     WHERE g.game_id = %s AND g.{_MINE.replace(' AND ', ' AND g.')}
       AND NOT EXISTS (SELECT 1 FROM odds o WHERE o.game_id = g.game_id)
       AND NOT EXISTS (SELECT 1 FROM picks p WHERE p.game_id = g.game_id)
    RETURNING g.game_id
"""


def removals(p: dict) -> list[str]:
    """Every own row a plan removes: the book's twins, then the games that are off."""
    return ([own for own, _ in p["twins"]] + list(p["called_off"]) + list(p["gone_past"])
            + list(p["orphans"]))


def apply(conn, p: dict) -> dict:
    """Write a plan in one transaction (the caller commits). -> {deleted, kept}."""
    if p["insert"]:
        conn.executemany(_INSERT, [
            (r["game_id"], r["season"], r["game_date"], r["home_team"], r["away_team"],
             r["neutral_site"], r["commence_time"], DATA_SOURCE) for r in p["insert"]])
    if p["times"]:
        conn.executemany(_TIMES, [(new, gid, DATA_SOURCE) for gid, new, _ in p["times"]])
    if p["confirm"]:
        conn.execute(_CONFIRM, (list(p["confirm"]), DATA_SOURCE))
    deleted, kept = [], []
    for i, gid in enumerate(removals(p)):
        try:
            got = call_in_savepoint(conn, f"nhl_sched_orphan_{i}",
                                    lambda g=gid: conn.execute(_DELETE, (g, DATA_SOURCE)).fetchall())
        except Exception as exc:                          # noqa: BLE001 -- a row something references
            logger.warning(f"NHL schedule refresh: {gid} is no longer listed, but another table "
                           f"references it ({type(exc).__name__}); left in place")
            kept.append(gid)
            continue
        (deleted if got else kept).append(gid)
    return {"deleted": deleted, "kept": kept}


# ── the step ─────────────────────────────────────────────────────────────────

def _new_totals(today: date) -> dict:
    return {"from": today.isoformat(), "read_from": None, "covered_to": None, "weeks": 0,
            "calls": 0, "listed": 0, "kept_rows": 0, "skipped": {}, "insert": 0, "times": 0,
            "confirm": 0, "twins": 0, "called_off": 0, "gone_past": 0, "orphans": 0,
            "orphans_deleted": 0, "orphans_kept": 0, "twins_deleted": 0, "twins_kept": 0,
            "orphans_held": 0, "conflicts": 0, "unlisted_soon": 0, "failed": None, "error": None}


_WHY_REMOVED = {
    "called_off": "the NHL API lists it as postponed or cancelled that day",
    "gone_past": "its start has passed and the NHL API does not list it that day",
    "orphans": "the NHL API no longer lists it that day; a moved game is stored under "
               "its new date's id",
}


def refresh(run_date: str | None = None, *, get_json=None, connect=None, dry_run: bool = False,
            now: datetime | None = None, sleep: float = REQUEST_SLEEP) -> dict:
    """Walk the NHL API from LOOKBACK_DAYS before `run_date` (ET; default
    today) and write the plan. Never raises: a failure is logged and returned
    in `failed` / `error`."""
    now = now or datetime.now(timezone.utc)
    today = date.fromisoformat(run_date) if run_date else now.astimezone(_ET).date()
    read_from = today - timedelta(days=LOOKBACK_DAYS)
    totals = _new_totals(today)
    totals["read_from"] = read_from.isoformat()
    w = walk(read_from, get_json, sleep=sleep)
    totals.update(weeks=w["weeks"], calls=w["calls"], covered_to=w["covered_to"], failed=w["failed"])
    if w["failed"]:
        logger.error(f"NHL schedule refresh: the NHL API stopped answering ({w['failed']}); "
                     + ("nothing written, `games` is left as it is" if not w["weeks"] else
                        f"only the weeks through {w['covered_to']} are written"))
    if not w["weeks"] or w["covered_to"] is None:
        if not w["failed"]:
            logger.warning(f"NHL schedule refresh: the NHL API lists no week from {read_from}; "
                           f"nothing written")
        return totals
    counts: dict = {}
    called_off: set[str] = set()
    rows, listed_ids = game_rows(w["games"], now, counts, called_off)
    totals.update(listed=len(listed_ids), kept_rows=len(rows), skipped=counts)
    if counts.get("unknown_team"):
        logger.warning(f"NHL schedule refresh: {counts['unknown_team']} game(s) name a team code "
                       f"that is not ours (nhl_stats_ingestor.NHL_API_ABBREV_MAP); not stored")
    covered = (read_from.isoformat(), w["covered_to"])
    conn = None
    try:
        conn = (connect or get_connection)()
        stored = read_stored(conn, *covered)
        p = plan(rows, listed_ids, stored, covered, now, called_off)
        if not listed_ids and not called_off and stored:
            # The API answered with weeks but no game at all where `games`
            # holds some: a broken answer, not an empty schedule. Rows still
            # ahead stay. A row whose start has passed unlisted, or a twin of
            # a book's row, is removed as on any run: neither can be wrong
            # for long (a game the league played is scored by the results
            # step, which runs first, and is then never a candidate).
            logger.error(f"NHL schedule refresh: the NHL API listed no game "
                         f"{covered[0]}..{covered[1]} while `games` holds {len(stored)}; "
                         f"no row for a game still ahead removed")
            totals["failed"] = totals["failed"] or "an empty answer over stored games"
            p["orphans"] = []
        if len(p["orphans"]) > MAX_ORPHAN_DELETES:
            logger.error(f"NHL schedule refresh: {len(p['orphans'])} of this refresh's own rows for "
                         f"games still ahead are no longer listed, and the NHL API does not say they "
                         f"were postponed or cancelled (more than {MAX_ORPHAN_DELETES}: more likely a "
                         f"changed team code or a broken answer); none of those deleted. A row whose "
                         f"start passes unlisted is removed by the next run: "
                         f"{sorted(p['orphans'])[:20]}")
            totals["orphans_held"] = len(p["orphans"])
            p["orphans"] = []
        totals.update({k: len(p[k]) for k in ("insert", "times", "confirm", "twins", "called_off",
                                                "gone_past", "orphans", "conflicts",
                                                "unlisted_soon")})
        for gid, new, old in p["times"]:
            logger.info(f"NHL schedule refresh: {gid} start moved {old} -> {new}")
        for api_id, stored_id in p["conflicts"]:
            logger.warning(f"NHL schedule refresh: the NHL API's {api_id} is stored as {stored_id} "
                           f"(the same two teams that day under another id); not inserted")
        for own, other in p["twins"]:
            logger.warning(f"NHL schedule refresh: a book lists the same two teams that day as "
                           f"{other}; this refresh's {own} is removed (the book's row is the game)")
        if p["unlisted_soon"]:
            logger.warning(f"NHL schedule refresh: no book lists {sorted(p['unlisted_soon'])} yet, "
                           f"within {FEED_LISTS_BY_HOURS}h of the start: the odds feed is behind or "
                           f"filed the game under another id")
        if dry_run:
            conn.rollback()
            totals["plan"] = p
        else:
            done = apply(conn, p)
            conn.commit()
            twin_ids = {own for own, _ in p["twins"]}
            totals.update(
                orphans_deleted=sum(1 for g in done["deleted"] if g not in twin_ids),
                orphans_kept=sum(1 for g in done["kept"] if g not in twin_ids),
                twins_deleted=sum(1 for g in done["deleted"] if g in twin_ids),
                twins_kept=sum(1 for g in done["kept"] if g in twin_ids))
            gone = set(done["deleted"])
            for kind, why in _WHY_REMOVED.items():
                for gid in p[kind]:
                    if gid in gone:
                        logger.info(f"NHL schedule refresh: {gid} removed ({why})")
    except Exception as exc:                              # noqa: BLE001 -- fail-open
        logger.error(f"NHL schedule refresh: write failed ({type(exc).__name__}: {str(exc)[:200]}); "
                     f"rolled back, `games` is unchanged")
        totals["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        if conn is not None:
            try:
                conn.rollback()
            except Exception:                             # noqa: BLE001
                pass
    finally:
        if conn is not None and connect is None:
            conn.close()
    summary = {k: v for k, v in totals.items() if k != "plan"}
    logger.info(f"NHL schedule refresh{' (DRY RUN)' if dry_run else ''}: {summary}")
    return totals


def step_ok(t: dict) -> bool:
    """The daily step's verdict on a refresh: False names it in pipeline_runs."""
    return not (t["failed"] or t["error"] or not t["weeks"] or t["orphans_held"])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--date", help="ET run date (default today)")
    ap.add_argument("--dry-run", action="store_true", help="fetch and read; write nothing")
    a = ap.parse_args()
    t = refresh(a.date, dry_run=a.dry_run)
    print({k: v for k, v in t.items() if k != "plan"})


if __name__ == "__main__":
    main()
