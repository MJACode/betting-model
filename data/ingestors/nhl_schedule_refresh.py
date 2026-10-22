"""nhl_schedule_refresh.py -- the NHL season stored ahead in `games`, from the NHL's own API.

WHY THIS EXISTS (mike, 2026-10-20: schedule look-ahead for every sport). Until
this module an NHL game reached `games` only from the odds feed
(data/ingestors/odds_ingestor._process_events), so a game existed once a book
listed it: every one of the 167 2026-27 rows stored by 2026-10-22 was created
24.7 to ~32 hours before puck drop (production, created_at against
commence_time), and the table held 2 future rows on 10-20. The shared schedule
reader (data/schedule_context) and anything that wants rest at kickoff or "the
team's next game" could see one day ahead at most. The NBA got the same fix in
#1028 (nba_schedule_refresh).

THE SOURCE. https://api-web.nhle.com/v1/schedule/<date> is free and keyless.
Each answer is one week (`gameWeek`, seven dated days with their games) and
`nextStartDate`, the next week that holds a game, so the walk skips breaks on
its own; it also carries regularSeasonEndDate and playoffEndDate. From
2026-10-22 the walk took 25 calls to reach the last regular-season game
(2027-04-10, 1,191 games), every one gameType 2, gameState FUT and
gameScheduleState OK.

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
A game the API lists that would sit on the same date as a stored row of the
same two teams under another id is NOT inserted (`conflicts`, a WARNING): the
stored row is the game, and a second id would split it.

WHAT IT WRITES. Only NHL rows, only games that have not started:
  * a regular-season or playoff game the API lists as scheduled (state OK, not
    an if-necessary playoff game, both teams known) that `games` lacks is
    inserted with data_source 'nhl_schedule' (DATA_SOURCE).
  * a row THIS refresh wrote (data_source still DATA_SOURCE, no score, its
    stored start not passed) follows the API's start time when it moves, and
    has updated_at stamped when the API confirms it: that stamp is what the
    health check reads.
  * a row this refresh wrote for a game the API no longer lists on that date
    (moved to another date, which is a new id, postponed or cancelled) is
    deleted, while it is still in the future, has no odds and no pick, and no
    other table references it (the delete runs in a savepoint and a foreign key
    keeps it). At most MAX_ORPHAN_DELETES a run: more than that is an API or
    team-code change, not a schedule change, and the step fails instead.
    A moved game is therefore re-keyed, which is how its date is "updated":
    the date is part of the id.
It NEVER touches a row the odds feed or the results step wrote: the odds
feed's upsert sets data_source = 'live' (odds_ingestor._upsert_games) and from
then the row is the feed's -- its start time is the books' start, about ten
minutes after the league's, and moving it back would flip it every day. Never a
score, never a started or past game.

WHO SEES THESE ROWS. A row no book has listed yet must not cause a bet, a
purchase or an alarm the old table could not. The readers that act on a game
skip it (`listed_by_a_book`): the scorer's game loop, the NHL slate the goalie
poll, the goalie window and the prop cards share (scripts/nhl_prop_card.slate),
the totals card's slate and the prop-odds purchase. The schedule readers see
it: data/schedule_context, rest at kickoff, the earlier-game rule.

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
# own rows vanishing from the API at once is a changed team code or a broken
# answer, and deleting them would be the wrong fix.
MAX_ORPHAN_DELETES = 8
# The odds feed has listed every 2026-27 game at least 24.7 hours before its
# start. A row still only this refresh's that close to puck drop means the feed
# is down or filed the game under another id.
FEED_LISTS_BY_HOURS = 24


def listed_by_a_book(alias: str = "") -> str:
    """SQL: the row is not one only this refresh wrote (a book has listed it,
    or the results step wrote it). For the readers that act on a game."""
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
              counts: dict | None = None) -> tuple[list[dict], set[str]]:
    """(rows to keep stored, every id the API lists as scheduled).

    A row is a regular-season or playoff game, scheduled (state OK), not an
    if-necessary playoff game, between two known teams, not started. The id
    set covers every scheduled game of those types, started or not, so a row
    is never called gone because its game has begun."""
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


def plan(api: list[dict], listed_ids: set[str], stored: list[dict],
         covered: tuple[str, str], now: datetime) -> dict:
    """What to write.

    `api`: game_rows' rows. `stored`: every NHL games row dated inside
    `covered` (lo, hi), with game_id, game_date, home_team, away_team,
    commence_time, data_source, home_score.

    -> {insert: rows `games` lacks, times: (game_id, new start, old start) for
        this refresh's own rows whose start moved, confirm: own rows the API
        lists unchanged, orphans: own future rows the API no longer lists,
        conflicts: (api id, stored id) of the same two teams on the same date
        under another id, unlisted_soon: own rows starting within
        FEED_LISTS_BY_HOURS that no book has listed}
    """
    lo, hi = covered
    by_id = {s["game_id"]: s for s in stored}
    by_day: dict[str, list[dict]] = {}
    for s in stored:
        by_day.setdefault(str(s["game_date"])[:10], []).append(s)
    out = {"insert": [], "times": [], "confirm": [], "orphans": [], "conflicts": [],
           "unlisted_soon": []}
    for r in api:
        s = by_id.get(r["game_id"])
        if s is None:
            pair = {r["home_team"], r["away_team"]}
            twin = next((x for x in by_day.get(r["game_date"], [])
                         if {x["home_team"], x["away_team"]} == pair), None)
            if twin is not None:
                out["conflicts"].append((r["game_id"], twin["game_id"]))
            else:
                out["insert"].append(r)
            continue
        if not _mine(s):
            continue                                  # the odds feed's or the results step's
        old = _ts(s.get("commence_time"))
        if old is not None and old <= now:
            continue                                  # started by our record: never touched
        if _ts(r["commence_time"]) != old:
            out["times"].append((r["game_id"], r["commence_time"], s.get("commence_time")))
        else:
            out["confirm"].append(r["game_id"])
    soon = now + timedelta(hours=FEED_LISTS_BY_HOURS)
    for s in stored:
        if not _mine(s):
            continue
        d = str(s["game_date"])[:10]
        start = _ts(s.get("commence_time"))
        if not (lo <= d <= hi) or (start is not None and start <= now):
            continue
        if s["game_id"] not in listed_ids:
            out["orphans"].append(s["game_id"])
        elif start is not None and start <= soon:
            out["unlisted_soon"].append(s["game_id"])
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
    for i, gid in enumerate(p["orphans"]):
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
    return {"from": today.isoformat(), "covered_to": None, "weeks": 0, "calls": 0,
            "listed": 0, "kept_rows": 0, "skipped": {}, "insert": 0, "times": 0, "confirm": 0,
            "orphans": 0, "orphans_deleted": 0, "orphans_kept": 0, "orphans_held": 0,
            "conflicts": 0, "unlisted_soon": 0, "failed": None, "error": None}


def refresh(run_date: str | None = None, *, get_json=None, connect=None, dry_run: bool = False,
            now: datetime | None = None, sleep: float = REQUEST_SLEEP) -> dict:
    """Walk the NHL API from `run_date` (ET; default today) and write the plan.
    Never raises: a failure is logged and returned in `failed` / `error`."""
    now = now or datetime.now(timezone.utc)
    today = date.fromisoformat(run_date) if run_date else now.astimezone(_ET).date()
    totals = _new_totals(today)
    w = walk(today, get_json, sleep=sleep)
    totals.update(weeks=w["weeks"], calls=w["calls"], covered_to=w["covered_to"], failed=w["failed"])
    if w["failed"]:
        logger.error(f"NHL schedule refresh: the NHL API stopped answering ({w['failed']}); "
                     + ("nothing written, `games` is left as it is" if not w["weeks"] else
                        f"only the weeks through {w['covered_to']} are written"))
    if not w["weeks"] or w["covered_to"] is None:
        if not w["failed"]:
            logger.warning(f"NHL schedule refresh: the NHL API lists no week from {today}; nothing written")
        return totals
    counts: dict = {}
    rows, listed_ids = game_rows(w["games"], now, counts)
    totals.update(listed=len(listed_ids), kept_rows=len(rows), skipped=counts)
    if counts.get("unknown_team"):
        logger.warning(f"NHL schedule refresh: {counts['unknown_team']} game(s) name a team code "
                       f"that is not ours (nhl_stats_ingestor.NHL_API_ABBREV_MAP); not stored")
    covered = (today.isoformat(), w["covered_to"])
    conn = None
    try:
        conn = (connect or get_connection)()
        stored = read_stored(conn, *covered)
        p = plan(rows, listed_ids, stored, covered, now)
        if not listed_ids and stored:
            # The API answered with weeks but no scheduled game where `games`
            # holds some: a broken answer, not an empty schedule.
            logger.error(f"NHL schedule refresh: the NHL API listed no scheduled game "
                         f"{covered[0]}..{covered[1]} while `games` holds {len(stored)}; "
                         f"nothing removed")
            totals["failed"] = totals["failed"] or "an empty answer over stored games"
            p["orphans"] = []
        if len(p["orphans"]) > MAX_ORPHAN_DELETES:
            logger.error(f"NHL schedule refresh: {len(p['orphans'])} of this refresh's own rows are "
                         f"no longer listed (more than {MAX_ORPHAN_DELETES}: a changed team code or "
                         f"a broken answer, not postponements); none deleted: "
                         f"{sorted(p['orphans'])[:20]}")
            totals["orphans_held"] = len(p["orphans"])
            p["orphans"] = []
        totals.update({k: len(p[k]) for k in ("insert", "times", "confirm", "orphans",
                                                "conflicts", "unlisted_soon")})
        for gid, new, old in p["times"]:
            logger.info(f"NHL schedule refresh: {gid} start moved {old} -> {new}")
        for api_id, stored_id in p["conflicts"]:
            logger.warning(f"NHL schedule refresh: the NHL API's {api_id} is stored as {stored_id} "
                           f"(the same two teams that day under another id); not inserted")
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
            totals.update(orphans_deleted=len(done["deleted"]), orphans_kept=len(done["kept"]))
            for gid in done["deleted"]:
                logger.info(f"NHL schedule refresh: {gid} removed (no longer listed on that date; "
                            f"a moved game is stored under its new date's id)")
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
