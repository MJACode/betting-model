"""nba_schedule_refresh.py -- the NBA schedule, kept current on the worker from ESPN.

WHY THIS EXISTS. Until 2026-10-20 `nba_schedule` came from one load by hand
(data/ingestors/nba_schedule_ingestor.py, stats.nba.com, a residential
machine): every 2026-27 row carries updated_at 2026-10-15 22:17:47Z, and no
job ever reloaded it. That load was taken before the league set its NBA Cup
week, so 24 regular-season games (NBA.com ids 0022601205-0022601228) were not
in it at all and the six knockout games were placeholders with no teams. Play-in
and playoff games get their teams only in April, and a tip time moved after
the load never reached the table. Both NBA prop models price only a game the
schedule types as a regular-season game, and the projection model reads rest
and back-to-backs from the games the schedule lists, so a frozen schedule
quietly drops games and misreads rest (measured on 2023-24..2025-26 by removing
the same block: 30 team-games a season with the wrong rest).

THE SOURCE. ESPN's site scoreboard, one call per calendar month
(dates=YYYYMM&limit=1000; without `limit` ESPN returns the first 100 events,
and a date range answers HTTP 400). Free, no key. The worker reaches
site.api.espn.com (api_call_log, 2026-10-17..10-20: 774 calls from the
pipeline, every one HTTP 200, on the WNBA scoreboard); stats.nba.com blocks
datacenter addresses, and cdn.nba.com's static schedule answered 403 from the
build machine on 2026-10-20. Measured 2026-10-20 against production:
  * December 2026: ESPN lists 172 games with two teams; all 172 are in
    nba_schedule under the same game_id, at the same tip to the second. The
    other six are the Cup knockout slots (TBD, timeValid false). The week of
    Dec 5-11 holds 4 games: the league has not published it yet.
  * 2025-26: ESPN's types reproduce NBA.com's on every game compared -- the
    Cup final 1 of 1, play-in 6 of 6, playoffs 80 of 80, a regular-season
    sample 25 of 25 -- with the same tips.

THE FALLBACK HOST. site.api.espn.com has refused the worker before: its daily
probe read HTTP 403 on every day it ran from 2026-08-08 to 2026-09-30
(system_health_checks, espn_wnba_api), eight weeks, while
sports.core.api.espn.com served the WNBA results step's fallback the whole
time; site answered again from 2026-10-01. A month the scoreboard does not
answer is read from the core host (core_month), for this month and the next
only (CORE_MONTHS): one listing call a month, then one document per game and
one per team (cached for the run), since the core host lists events and teams
as links. A month further out that the scoreboard refuses stays failed. Measured 2026-10-21: its December
2025 and December 2026 listings hold the same event ids as the scoreboard's
(198 and 178), and its documents carry the date, timeValid, venue, neutral
site and notes inline, the season type and year in the link paths. Status and
broadcasts are one more link per game each and are not followed: a month read
this way records no postponement (the results step records those) and leaves
a stored status and national TV as they are. Read against the scoreboard on
2026-10-21, December 2026 came back the same: 172 games, the same game ids,
no field different but status and TV.

TYPES. season.type 2 is the regular season, the Cup quarterfinals and
semifinals included (they count in the standings, NBA.com types them 002);
a type-2 game whose note reads "NBA Cup Championship" is the Cup final
(cup_final, NBA.com's 006); 3 playoff; 5 play-in. Preseason (1) and anything
else is not stored. A slot whose teams are not set (TBD) is skipped: the
schedule keeps the league's own placeholder for it. The totals model reads
those placeholders' dates (models/nba_total_luck.regular_season), so this
never writes, removes or renames one.

WHAT IT WRITES, for the months it fetched (this ET month and the next
MONTHS_AHEAD):
  * nba_schedule, a game it already lists (matched on our game_id): the tip,
    when ESPN's differs AND the odds feed's own start for the game shows the
    new tip (a time change two sources show: the feed lists the books' start,
    at or up to 30 minutes after the league's tip, so it seconds ESPN when it
    sits that far after ESPN's tip and not the stored one, or nearer ESPN's
    when it fits both -- feed_shows), or the row has no tip; status_text,
    when ESPN marks the game postponed or cancelled (the results step's
    wording) and it has no score; and updated_at = NOW(), which is what the
    health check reads as "confirmed today". Never its type, arena, label or
    score: the NBA.com load and the results step own those. All four NBA
    models take the earlier of the schedule's tip and the feed's start (the
    totals card's slate, models.nba_prop_market.tip_of), so a tip moved LATER
    (a 7pm game flexed to 9:30) that the schedule still holds at 7pm has
    every one of them decide hours before the real tip, even once the feed
    shows 9:40.
    ESPN alone never moves the league's tip: on 2026-10-20 it disagreed on 1
    game of 1,200, CHI @ MIL on 2026-10-23 (ESPN 4:00pm ET; the league's
    load, the Bucks' own schedule release and ticket listings 7pm CT). Moved
    early on its word, the prop models would decide five hours before the
    real tip; moved late, they could decide after it. A disputed tip is left
    as stored, counted in `tip_disputed` and named in a WARNING.
  * nba_schedule, a game it does not list: inserted, keyed 'espn:<event id>'.
    An NBA.com id is all digits, so the prefix never collides with one (the
    convention nba_results_ingestor uses for players). The next NBA.com load,
    if anyone runs one, replaces it: nba_schedule_ingestor.write deletes the
    'espn:' row of every game it writes, and this module deletes any 'espn:'
    row whose game already has an NBA.com row.
  * games: a REGULAR-SEASON game `games` lacks is inserted (data_source
    'espn_schedule'), as the NBA.com load inserts one ('nba_api_schedule');
    the prop cards' slate reads `games`, so a game only the schedule lists is
    invisible to them. A row only this refresh wrote follows ESPN's tip; any
    other row keeps its own start (the odds feed rewrites its rows itself).
It NEVER deletes a game. A game the schedule lists, with two teams, in a
fetched month, that ESPN no longer lists under that game_id is counted in
`not_on_espn` and named in a WARNING: a moved game changes its game_id (the
date is in it), and a game removed on one day's read is safer named than
dropped.

FAIL-OPEN. A month that neither host answers whole, or that comes back with no
NBA game while the schedule lists games in it, is logged as an ERROR naming
the month and left exactly as stored; a month read from the core host is
named in `via_core` and a WARNING. Nothing else depends on this run: the models
keep reading the stored schedule. The pipeline step returns False when any
month failed (so pipeline_runs names it), and the health check
`nba_schedule_refresh` turns STALE when no schedule row has been confirmed for
36 hours while NBA games are scheduled (tracking/system_health.py); the
failure alerter posts a STALE check.

    python -m data.ingestors.nba_schedule_refresh              # fetch and write
    python -m data.ingestors.nba_schedule_refresh --dry-run    # fetch, read, print the plan
"""
from __future__ import annotations

import argparse
import re
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from loguru import logger

from data.db import get_connection
from data.ingestors.nba_espn_box import ESPN_NBA_SCOREBOARD_URL, et_date, nba_team
from data.ingestors.nba_results_ingestor import FALLBACK_PREFIX, _http_get_json
from data.ingestors.nba_stats_ingestor import _build_game_id

_ET = ZoneInfo("America/New_York")

# This month and the next eight: from October that reaches the Finals in June,
# and in the summer it picks up the next season as soon as ESPN publishes it.
MONTHS_AHEAD = 8
EVENT_LIMIT = 1000            # a month holds at most ~250 NBA games
ESPN_KEY = FALLBACK_PREFIX    # 'espn:' -- nba_game_id of a game NBA.com has not given us
DATA_SOURCE = "espn_schedule"
# `games` rows a schedule load wrote. Their start is a schedule's, not the odds
# feed's, so it cannot second ESPN on a moved tip.
SCHEDULE_SOURCES = ("nba_api_schedule", DATA_SOURCE)

# How far after ESPN's new tip the odds feed's start may sit and still be the
# feed showing the move. The feed lists the books' start, not the league's tip:
# of the 46 2026-27 games whose games row it had written by 2026-10-20, 8 sat
# on the league's tip, 35 ten minutes after it and 3 (opening night, rewritten
# once the games began) 8, 18 and 22 minutes after; none before it (production).
# A minute's slack before covers a feed stamped to the second. A feed start
# that fits both the stored tip and ESPN's (a move of under half an hour)
# shows the one it sits nearer, so a feed that has not moved yet (still ten
# minutes after the stored tip) never seconds a small move.
FEED_LAG = (timedelta(minutes=-1), timedelta(minutes=30))

# The fallback host (THE FALLBACK HOST above). Its links say http://; they are
# followed as https://, as the WNBA results step's (wnba_results_ingestor).
CORE_NBA_EVENTS_URL = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events"
CORE_REQUEST_SLEEP = 0.1      # the WNBA results step's pause between core calls
# This month and next: far enough ahead for every game a model could price soon
# (a flex is announced days ahead, the Cup bracket the week before), and a
# month further out is read again by the time it is near. All nine would cost
# the 6am run about 18 minutes: December 2026 read this way took 209 calls
# and 170 seconds from the build machine on 2026-10-21.
CORE_MONTHS = 2
_REF_TYPE = re.compile(r"/seasons/(\d{4})/types/(\d+)")
_REF_SEASON = re.compile(r"/seasons/(\d{4})")
_REF_TEAM = re.compile(r"/seasons/\d{4}/teams/(-?\d+)")

ESPN_TYPES = {2: "regular", 3: "playoff", 5: "playin"}
CUP_FINAL_NOTE = "cup championship"
STORED_TYPES = ("regular", "cup_final", "playin", "playoff")
_POSTPONED = re.compile(r"(?i)(ppd|postpon|cancel)")
_NOT_A_TEAM = {"", "NAN", "NONE", "NULL", "TBD"}

SCHEDULE_COLS = ("nba_game_id", "game_id", "season", "game_type", "game_date", "commence_time",
                 "home_team", "away_team", "status_text", "arena_name", "arena_city",
                 "arena_state", "is_neutral", "game_label", "national_tv")


def _to_int(val):
    try:
        return int(str(val).strip()) if val is not None else None
    except (TypeError, ValueError):
        return None


def _ts(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _known_team(x) -> bool:
    return isinstance(x, str) and x.strip().upper() not in _NOT_A_TEAM


def _fits(feed: datetime, tip: datetime) -> bool:
    return FEED_LAG[0] <= feed - tip <= FEED_LAG[1]


def feed_shows(feed: datetime | None, new: datetime, old: datetime) -> bool:
    """Does the odds feed's start for a game show ESPN's new tip, not the stored one?
    It fits the new tip (FEED_LAG), and either does not fit the old or sits nearer the new."""
    if feed is None or not _fits(feed, new):
        return False
    return not _fits(feed, old) or abs(feed - new) < abs(feed - old)


def months(today: date, ahead: int = MONTHS_AHEAD) -> list[str]:
    """['202610', '202611', ...]: this month and the `ahead` after it."""
    out, y, m = [], today.year, today.month
    for _ in range(ahead + 1):
        out.append(f"{y}{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


# ── parsing (pure) ───────────────────────────────────────────────────────────

def event_rows(data: dict, counts: dict | None = None) -> list[dict]:
    """One nba_schedule row per ESPN event between two NBA teams of a stored
    type. `counts`, when given, tallies what was left out and why."""
    counts = counts if counts is not None else {}
    out = []
    for ev in (data or {}).get("events") or []:
        kind = ESPN_TYPES.get(_to_int((ev.get("season") or {}).get("type")))
        if kind is None:
            counts["other_type"] = counts.get("other_type", 0) + 1       # preseason, All-Star
            continue
        comps = ev.get("competitions") or []
        comp = comps[0] if comps else {}
        home = away = None
        for c in comp.get("competitors") or []:
            team = c.get("team") or {}
            code = nba_team(team.get("abbreviation"), team.get("displayName"))
            if c.get("homeAway") == "home":
                home = code
            elif c.get("homeAway") == "away":
                away = code
        if not home or not away:
            counts["no_teams"] = counts.get("no_teams", 0) + 1           # a TBD slot, a non-NBA side
            continue
        notes = " / ".join(str(n.get("headline")) for n in comp.get("notes") or [] if n.get("headline"))
        if kind == "regular" and CUP_FINAL_NOTE in notes.lower():
            kind = "cup_final"
        game_date = et_date(ev.get("date") or comp.get("date"))
        season = _to_int((ev.get("season") or {}).get("year"))
        if game_date is None or season is None:
            counts["no_date"] = counts.get("no_date", 0) + 1
            continue
        # timeValid false is a date with no tip yet: ESPN stamps midnight ET on
        # it, which would read as a real start.
        tip = _ts(ev.get("date") or comp.get("date")) if comp.get("timeValid", True) is not False else None
        st = (ev.get("status") or {}).get("type") or {}
        venue = comp.get("venue") or {}
        addr = venue.get("address") or {}
        tv = [n for b in comp.get("broadcasts") or [] if b.get("market") == "national"
              for n in b.get("names") or []]
        out.append({
            "nba_game_id": f"{ESPN_KEY}{ev.get('id')}",
            "game_id": _build_game_id(game_date, away, home),
            "season": season,
            "game_type": kind,
            "game_date": game_date,
            "commence_time": tip.isoformat() if tip else None,
            "home_team": home,
            "away_team": away,
            "status_text": st.get("description") or None,
            "postponed": bool(_POSTPONED.search(str(st.get("name") or ""))),
            "arena_name": venue.get("fullName") or None,
            "arena_city": addr.get("city") or None,
            "arena_state": addr.get("state") or None,
            "is_neutral": bool(comp.get("neutralSite")),
            "game_label": notes or None,
            "national_tv": ",".join(tv) or None,
        })
    return out


# ── the fallback host (sports.core.api.espn.com) ─────────────────────────────

def _https(url: str) -> str:
    """The core host's links say http://; every one is followed over https."""
    return "https://" + url[len("http://"):] if url.startswith("http://") else url


def fetch_core(url: str) -> dict:
    """GET one core-API document, with nba_results_ingestor's one retry on a
    timeout or a 5xx."""
    out = _http_get_json(_https(url), {})
    time.sleep(CORE_REQUEST_SLEEP)
    return out


def _core_team(team: dict, fetch, teams: dict) -> dict:
    """A core competitor's team as the scoreboard carries it ({abbreviation,
    displayName}), fetched once a run per season and team. {} for a knockout
    slot with no teams yet: ESPN gives those team ids -1 and -2."""
    ref = str((team or {}).get("$ref") or "")
    m = _REF_TEAM.search(ref)
    if not m or int(m.group(1)) <= 0:
        return {}
    key = m.group(0)
    if key not in teams:
        doc = fetch(_https(ref)) or {}
        teams[key] = {"abbreviation": doc.get("abbreviation"), "displayName": doc.get("displayName")}
    return teams[key]


def core_event(ev: dict, fetch, teams: dict) -> dict:
    """One core-API event document in the scoreboard's event shape, for
    event_rows: the season type and year from the link paths, the teams
    followed, no status and no broadcasts (THE FALLBACK HOST)."""
    ev = ev or {}
    comp = (ev.get("competitions") or [{}])[0]
    kind = _REF_TYPE.search(str((ev.get("seasonType") or {}).get("$ref") or ""))
    year = _REF_SEASON.search(str((ev.get("season") or {}).get("$ref") or ""))
    return {
        "id": ev.get("id"),
        "date": ev.get("date") or comp.get("date"),
        "season": {"type": int(kind.group(2)) if kind else None,
                   "year": int(year.group(1)) if year else None},
        "competitions": [{
            "date": comp.get("date"),
            "timeValid": comp.get("timeValid", ev.get("timeValid")),
            "neutralSite": comp.get("neutralSite"),
            "notes": comp.get("notes") or [],
            "venue": comp.get("venue") or {},
            "competitors": [{"homeAway": c.get("homeAway"),
                             "team": _core_team(c.get("team"), fetch, teams)}
                            for c in comp.get("competitors") or []],
        }],
    }


def core_month(month: str, fetch=None, teams: dict | None = None) -> dict:
    """A month (YYYYMM) from the core host, as a scoreboard ({"events": [...]}).
    Raises on any document it cannot read, or a listing of more than one
    page: a month read in part would name every game it missed as no longer
    listed, so the caller fails the month whole."""
    fetch = fetch or fetch_core
    teams = {} if teams is None else teams
    listing = fetch(f"{CORE_NBA_EVENTS_URL}?dates={month}&limit={EVENT_LIMIT}") or {}
    if int(listing.get("pageCount") or 1) > 1:
        raise ValueError(f"core listing for {month} runs to {listing.get('pageCount')} pages")
    refs = [i.get("$ref") for i in listing.get("items") or [] if isinstance(i, dict)]
    if any(not r for r in refs):
        raise ValueError(f"core listing for {month} has an item with no link")
    return {"events": [core_event(fetch(_https(r)), fetch, teams) for r in refs]}


# ── the plan (pure) ──────────────────────────────────────────────────────────

def plan(espn: list[dict], stored: list[dict], games: dict[str, dict],
         fetched: list[str]) -> dict:
    """What to write, given ESPN's rows for the `fetched` months (YYYYMM), the
    nba_schedule rows stored for those months, and `games` (game_id ->
    {commence_time, data_source}) for every game ESPN listed.

    -> {upsert: ESPN rows to insert or update under their 'espn:' key,
        times: (nba_game_id, new tip, old tip) the odds feed agrees with,
        tip_disputed: (game_id, stored tip, ESPN's, the feed's) it does not,
        status: (nba_game_id, text), confirm: NBA.com-keyed rows ESPN listed,
        superseded: 'espn:' rows whose game has an NBA.com row, games_insert:
        regular-season rows `games` lacks, games_times: (game_id, new tip) for
        games rows only this refresh wrote, not_on_espn: stored games ESPN did
        not list}
    """
    by_gid: dict[str, list[dict]] = {}
    for r in stored:
        by_gid.setdefault(r["game_id"], []).append(r)
    out = {"upsert": [], "times": [], "tip_disputed": [], "status": [], "confirm": [],
           "superseded": [], "games_insert": [], "games_times": [], "not_on_espn": []}
    seen = set()
    for r in espn:
        if r["game_id"] in seen:
            continue
        seen.add(r["game_id"])
        rows = by_gid.get(r["game_id"], [])
        nba = [x for x in rows if not str(x["nba_game_id"]).startswith(ESPN_KEY)]
        g = games.get(r["game_id"])
        if nba:
            feed = _ts(g.get("commence_time")) if g and g.get("data_source") not in SCHEDULE_SOURCES else None
            for x in nba:
                new, old = _ts(r["commence_time"]), _ts(x.get("commence_time"))
                if new is None or new == old:
                    pass
                elif old is None or feed_shows(feed, new, old):
                    out["times"].append((x["nba_game_id"], r["commence_time"], x.get("commence_time")))
                else:
                    out["tip_disputed"].append((r["game_id"], x.get("commence_time"), r["commence_time"],
                                                g.get("commence_time") if feed else None))
                if r["postponed"] and not _POSTPONED.search(str(x.get("status_text") or "")):
                    out["status"].append((x["nba_game_id"], r["status_text"] or "Postponed"))
                out["confirm"].append(x["nba_game_id"])
        else:
            out["upsert"].append(r)
            # an 'espn:' row of this game under another event id: one row a game
            out["superseded"] += [x["nba_game_id"] for x in rows if x["nba_game_id"] != r["nba_game_id"]]
        if g is None:
            if r["game_type"] == "regular":
                out["games_insert"].append(r)
        elif g.get("data_source") == DATA_SOURCE and r["commence_time"] \
                and _ts(r["commence_time"]) != _ts(g.get("commence_time")):
            out["games_times"].append((r["game_id"], r["commence_time"]))
    moved = {r["nba_game_id"] for r in out["upsert"]}     # an 'espn:' row whose date ESPN moved
    for gid, rows in by_gid.items():
        espn_rows = [x for x in rows if str(x["nba_game_id"]).startswith(ESPN_KEY)]
        if espn_rows and len(espn_rows) < len(rows):
            out["superseded"] += [x["nba_game_id"] for x in espn_rows]
        if gid in seen:
            continue
        for x in rows:
            if x["nba_game_id"] in moved:
                continue
            if str(x.get("game_date"))[:7].replace("-", "") in fetched \
                    and x.get("game_type") in STORED_TYPES \
                    and _known_team(x.get("home_team")) and _known_team(x.get("away_team")):
                out["not_on_espn"].append(x["game_id"])
                break
    return out


# ── reads and writes ─────────────────────────────────────────────────────────

def _month_bounds(fetched: list[str]) -> tuple[str, str]:
    lo, hi = min(fetched), max(fetched)
    return f"{lo[:4]}-{lo[4:]}-01", f"{hi[:4]}-{hi[4:]}-31"


def read_stored(conn, fetched: list[str]) -> list[dict]:
    lo, hi = _month_bounds(fetched)
    cols = ("nba_game_id", "game_id", "season", "game_type", "game_date", "commence_time",
            "home_team", "away_team", "status_text")
    rows = conn.execute(f"""
        SELECT {', '.join(cols)} FROM nba_schedule
         WHERE game_date >= %s AND game_date <= %s
    """, (lo, hi)).fetchall()
    return [dict(zip(cols, r)) for r in rows]


def read_games(conn, game_ids: list[str]) -> dict[str, dict]:
    if not game_ids:
        return {}
    return {gid: {"commence_time": ct, "data_source": src} for gid, ct, src in conn.execute(
        "SELECT game_id, commence_time, data_source FROM games WHERE game_id = ANY(%s)",
        (list(game_ids),)).fetchall()}


_UPSERT = f"""
    INSERT INTO nba_schedule ({', '.join(SCHEDULE_COLS)}, updated_at)
    VALUES ({', '.join('%(' + c + ')s' for c in SCHEDULE_COLS)}, NOW())
    ON CONFLICT (nba_game_id) DO UPDATE SET
        game_id = EXCLUDED.game_id, season = EXCLUDED.season,
        game_type = EXCLUDED.game_type, game_date = EXCLUDED.game_date,
        commence_time = COALESCE(EXCLUDED.commence_time, nba_schedule.commence_time),
        home_team = EXCLUDED.home_team, away_team = EXCLUDED.away_team,
        status_text = COALESCE(EXCLUDED.status_text, nba_schedule.status_text),
        arena_name = EXCLUDED.arena_name,
        arena_city = EXCLUDED.arena_city, arena_state = EXCLUDED.arena_state,
        is_neutral = EXCLUDED.is_neutral, game_label = EXCLUDED.game_label,
        national_tv = COALESCE(EXCLUDED.national_tv, nba_schedule.national_tv), updated_at = NOW()
"""


def apply(conn, p: dict) -> None:
    """Write a plan in one transaction (the caller commits)."""
    if p["upsert"]:
        conn.executemany(_UPSERT, [{c: r[c] for c in SCHEDULE_COLS} for r in p["upsert"]])
    if p["times"]:
        conn.executemany(
            "UPDATE nba_schedule SET commence_time = %s, updated_at = NOW() WHERE nba_game_id = %s",
            [(new, nid) for nid, new, _ in p["times"]])
    if p["status"]:
        conn.executemany(
            "UPDATE nba_schedule SET status_text = %s, updated_at = NOW() "
            "WHERE nba_game_id = %s AND home_score IS NULL",
            [(text, nid) for nid, text in p["status"]])
    if p["confirm"]:
        conn.execute("UPDATE nba_schedule SET updated_at = NOW() WHERE nba_game_id = ANY(%s)",
                     (list(p["confirm"]),))
    if p["superseded"]:
        conn.execute("DELETE FROM nba_schedule WHERE nba_game_id = ANY(%s) AND nba_game_id LIKE %s",
                     (list(p["superseded"]), ESPN_KEY + "%"))
    if p["games_insert"]:
        conn.executemany("""
            INSERT INTO games (game_id, sport, season, game_date, home_team, away_team,
                neutral_site, commence_time, data_source, created_at, updated_at)
            VALUES (%s, 'NBA', %s, %s, %s, %s, %s, %s, %s, NOW()::TEXT, NOW()::TEXT)
            ON CONFLICT (game_id) DO NOTHING
        """, [(r["game_id"], r["season"], r["game_date"], r["home_team"], r["away_team"],
               1 if r["is_neutral"] else 0, r["commence_time"], DATA_SOURCE)
              for r in p["games_insert"]])
    if p["games_times"]:
        conn.executemany(
            "UPDATE games SET commence_time = %s, updated_at = NOW()::TEXT "
            "WHERE game_id = %s AND sport = 'NBA' AND data_source = %s",
            [(new, gid, DATA_SOURCE) for gid, new in p["games_times"]])


# ── the step ─────────────────────────────────────────────────────────────────

def _counts(p: dict) -> dict:
    return {k: len(v) for k, v in p.items()}


def refresh(run_date: str | None = None, *, get_json=None, core_json=None, connect=None,
            dry_run: bool = False, now: datetime | None = None) -> dict:
    """Fetch this month and the next MONTHS_AHEAD from ESPN and write the plan.
    A month the scoreboard does not answer is read from the core host
    (`core_json`, default fetch_core). Never raises: a failure is logged and
    returned in `failed` / `error`."""
    now = now or datetime.now(timezone.utc)
    today = date.fromisoformat(run_date) if run_date else now.astimezone(_ET).date()
    get_json = get_json or _http_get_json
    core_json = core_json or fetch_core
    totals: dict = {"months": months(today), "fetched": [], "failed": [], "via_core": [],
                    "events": 0, "skipped": {}, "error": None}
    espn: dict[str, list[dict]] = {}
    teams: dict = {}
    for i, m in enumerate(totals["months"]):
        try:
            board = get_json(ESPN_NBA_SCOREBOARD_URL, {"dates": m, "limit": EVENT_LIMIT})
        except Exception as exc:                      # noqa: BLE001 -- fail-open, by month
            site = f"{type(exc).__name__}: {str(exc)[:160]}"
            if i >= CORE_MONTHS:
                logger.error(f"NBA schedule refresh: ESPN month {m} failed ({site}), past the fallback "
                             f"host's {CORE_MONTHS} months; its stored schedule is left as it is")
                totals["failed"].append(m)
                continue
            try:
                board = core_month(m, core_json, teams)
            except Exception as core_exc:             # noqa: BLE001 -- fail-open, by month
                logger.error(f"NBA schedule refresh: ESPN month {m} failed on both hosts (site: {site}; "
                             f"core: {type(core_exc).__name__}: {str(core_exc)[:160]}); its stored "
                             f"schedule is left as it is")
                totals["failed"].append(m)
                continue
            logger.warning(f"NBA schedule refresh: ESPN's scoreboard refused month {m} ({site}); "
                           f"read from sports.core.api.espn.com instead (no status, no broadcasts)")
            totals["via_core"].append(m)
        espn[m] = event_rows(board, totals["skipped"])
        totals["events"] += len(espn[m])
    if not espn:
        logger.error("NBA schedule refresh: ESPN unreachable for every month; nothing written. "
                     "The NBA models keep the stored schedule.")
        return totals
    conn = None
    try:
        conn = (connect or get_connection)()
        stored = read_stored(conn, list(espn))
        # A month ESPN answered with no NBA game while the schedule lists games in
        # it is a broken answer, not an empty month: left as stored, and failed.
        listed = {str(r["game_date"])[:7].replace("-", "") for r in stored
                  if r.get("game_type") in STORED_TYPES
                  and _known_team(r.get("home_team")) and _known_team(r.get("away_team"))}
        for m in [m for m, rows in espn.items() if not rows and m in listed]:
            logger.error(f"NBA schedule refresh: ESPN month {m} came back with no NBA game, "
                         f"but the schedule lists games in it; left as stored")
            totals["failed"].append(m)
            del espn[m]
        totals["fetched"] = sorted(espn)
        rows = [r for m in totals["fetched"] for r in espn[m]]
        if not totals["fetched"]:
            conn.rollback()
            return totals
        stored = [r for r in stored if str(r["game_date"])[:7].replace("-", "") in totals["fetched"]]
        p = plan(rows, stored, read_games(conn, sorted({r["game_id"] for r in rows})),
                 totals["fetched"])
        totals.update(_counts(p))
        if p["not_on_espn"]:
            logger.warning(f"NBA schedule refresh: {len(p['not_on_espn'])} listed game(s) ESPN no "
                           f"longer shows on their date (moved or dropped? left as stored): "
                           f"{sorted(p['not_on_espn'])[:20]}")
        for nid, new, old in p["times"]:
            logger.info(f"NBA schedule refresh: {nid} tip moved {old} -> {new}")
        for gid, old, new, feed in p["tip_disputed"]:
            logger.warning(f"NBA schedule refresh: {gid} ESPN says {new}, the league's load {old}, "
                           f"the odds feed {feed or 'nothing yet'}; tip left as stored")
        if dry_run:
            conn.rollback()
            totals["plan"] = p
        else:
            apply(conn, p)
            conn.commit()
    except Exception as exc:                          # noqa: BLE001 -- fail-open
        logger.error(f"NBA schedule refresh: write failed ({type(exc).__name__}: {str(exc)[:200]}); "
                     f"rolled back, the stored schedule is unchanged")
        totals["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        if conn is not None:
            try:
                conn.rollback()
            except Exception:                         # noqa: BLE001
                pass
    finally:
        if conn is not None and connect is None:
            conn.close()
    summary = {k: v for k, v in totals.items() if k not in ("plan", "months")}
    logger.info(f"NBA schedule refresh{' (DRY RUN)' if dry_run else ''}: {summary}")
    return totals


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--date", help="ET run date (default today)")
    ap.add_argument("--dry-run", action="store_true", help="fetch and read; write nothing")
    a = ap.parse_args()
    t = refresh(a.date, dry_run=a.dry_run)
    print({k: v for k, v in t.items() if k != "plan"})


if __name__ == "__main__":
    main()
