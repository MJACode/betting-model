"""ncaab_espn_ingestor.py -- the NCAAB schedule and finals, from ESPN.

WHY THIS EXISTS. ESPN's schedule owns every NCAAB games row
(data/ingestors/ncaab_teams.py says why: 360-odd Division I schools collide in
three letters, and on a neutral court the odds feed may call the other team
home). This module is the ONLY writer of those rows. The odds feed resolves
onto them through ncaab_teams.make_resolver, which reads ncaab_events, so the
games row and its ncaab_events row are written in the same transaction.

THE SOURCE. ESPN's site API, free, no key (verified 2026-10-26):
  * scoreboard?dates=YYYYMMDD&groups=50&limit=500 -- ONE ET date per call (a
    date range answers HTTP 400). groups=50 is Division I: every game with at
    least one D1 side, buy-game opponents included.
  * teams?groups=50&limit=500 -- 362 D1 teams WITH their `location` (the
    school name a games row carries).
  * groups -- conference names. Measured 2026-10-26 it is INCOMPLETE: 25 of
    the 31 conferences the standings list, 289 teams. The WCC, SoCon,
    Southland, SWAC, Summit, Sun Belt and UAC are missing, so Saint Mary's,
    Furman and Pacific are not in it, and three transitioning schools
    (Queens, Southern Indiana, Lindenwood) are in it and NOT in /teams. So
    is_d1 is the UNION of the two, and a D1 school the groups listing omits
    has a NULL conference (nothing reads it: conference_game comes from the
    event's own flag).

WHAT IT WRITES
  * ncaab_teams   every D1 team (refresh_teams), and every opponent a
                  scoreboard shows that the table lacks (is_d1 FALSE). is_d1 is
                  never downgraded. A slug is set once, on insert, and never
                  rewritten: game_ids carry it. Two ESPN ids whose schools
                  slug the same: the later one gets '-<espn_id>' appended.
  * ncaab_venues  id, name, city, state, indoor. Coordinates and elevation
                  are left to whatever fills them.
  * ncaab_events  ESPN event id -> our game_id, both teams' ESPN ids, ESPN's
                  status name (STATUS_SCHEDULED, STATUS_FINAL,
                  STATUS_POSTPONED, ...), season type and notes.
  * games         game_id NCAAB_<ET date>_<away slug>_<home slug> in ESPN's
                  orientation, built ONCE from the slugs stored in
                  ncaab_teams. An event already in ncaab_events keeps its
                  game_id: a postponed game moved to another date keeps its id
                  and its games row has game_date / commence_time / season
                  updated instead (picks and odds reference the id).
                  Scores only for a completed event, and only into a row whose
                  score is still NULL: home_score, away_score, home_win,
                  went_to_ot (ESPN's period > 2: two halves, then overtimes)
                  and regulation_tie (1 when it went to overtime). A different
                  ESPN score for a row already scored is logged as a WARNING
                  and counted (`score_conflicts`), never written: a final that
                  changes after its picks graded would break the settled record
                  (CLAUDE.md section 1c; the NBA results step does the same).

WHAT IT REFUSES, each counted and logged rather than guessed:
  * an event without two real teams (a bracket slot ESPN has not filled);
  * an event postponed or cancelled the first time it is seen (no games row
    for a game that will not be played on that date; if ESPN reschedules it
    under the same event id it is written then);
  * an event whose teams or orientation changed since it was stored: the
    stored spreads are in the old orientation, so its schedule is not
    rewritten and a human looks first. When ESPN only swapped home and away
    (the same two teams), its final is still written, mapped by team onto the
    stored orientation, so the game cannot sit unscored with its picks
    unsettled;
  * a new event whose game_id another ESPN event already owns (same date,
    same pair): one games row per game, never NCAAF's twins.

TIP TIMES. ESPN stamps a date with no tip yet (competitions[0].timeValid
false) at midnight ET; stored as is, a 7pm game would read as started at
midnight. Such a tip is stored as NULL commence_time, the rule
nba_schedule_refresh.py follows; a later TBD sighting on the same date keeps a
tip already stored. Times are written in the odds feed's shape
(YYYY-MM-DDTHH:MM:SSZ).

COST. run_results (every refresh pass) reads the database first and calls
ESPN only for the ET dates that hold a started NCAAB game with no score and
not postponed or cancelled, within the last HEAL_DAYS days. An idle pass, and
every pass out of season, makes no ESPN call. A game with no tip time counts as
started once its date is past or is one of config.live_slate_dates(), since
the only way to learn whether it has tipped is to look. A tip after midnight
ET also fetches the previous date, the board ESPN files it on
(EARLY_TIP_HOUR_ET). Repeat passes over the same date write nothing unless
ESPN changed something. The daily run_schedule_refresh makes 2 team calls and
one call per day for today and the next SCHEDULE_DAYS days.

Usage:
    python -m data.ingestors.ncaab_espn_ingestor --teams
    python -m data.ingestors.ncaab_espn_ingestor --schedule [--date D] [--days 14]
    python -m data.ingestors.ncaab_espn_ingestor --results [--date D]
    python -m data.ingestors.ncaab_espn_ingestor --backfill 2025-11-03 2026-04-06
"""
from __future__ import annotations

import argparse
import re
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from loguru import logger

import config
from data.db import ConnectionLost, call_in_savepoint, get_connection, statement_timeout
from data.ingestors import ncaab_teams as nt

_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"
SCOREBOARD_URL = f"{_BASE}/scoreboard"
TEAMS_URL = f"{_BASE}/teams"
GROUPS_URL = f"{_BASE}/groups"
D1_GROUP = "50"
D1_GROUP_NAME = "ncaa division i"
SCOREBOARD_LIMIT = 500
REQUEST_SLEEP = 0.2          # between ESPN calls in a multi-day run
SCHEDULE_DAYS = 14           # the daily refresh: today and the next 14 days
HEAL_DAYS = 14               # run_results looks back this far for unscored games

# ESPN files a tip after midnight ET on the PREVIOUS date's scoreboard, and
# our game_date is the ET date, so the final is not on the board that date
# names. Measured 2026-10-26: East Texas A&M @ Hawai'i (event 401824896),
# tipped 2025-11-10T06:00Z = 01:00 ET on the 10th, is on the 20251109 board
# and not on 20251110's. Fetching only the 10th, run_results never found the
# final, and the daily schedule step never looks back, so the game would sit
# unscored with its picks unsettled. Hawai'i home games, Maui and late West
# Coast tips all land here. One data point cannot tell "the venue's local
# date" from "ESPN's day turns over in the early morning ET"; both put such a
# game on the previous board, so a stored tip before this hour (ET) makes
# due_dates fetch that board too. NOT covered: a game played east of ET (an
# Australia or Asia event) whose local date is ahead of its ET date.
EARLY_TIP_HOUR_ET = 6

_ET = ZoneInfo("America/New_York")
_OFF = re.compile(r"POSTPON|CANCEL", re.I)   # STATUS_POSTPONED, STATUS_CANCELED


# ── ESPN ─────────────────────────────────────────────────────────────────────

def _http_get_json(url: str, params: dict) -> dict:
    """GET with one retry on a timeout, a dropped connection or a 5xx. A 4xx
    (ESPN's 403 IP block, the 400 a date range draws) raises at once. The NBA
    results step's rule (nba_results_ingestor._http_get_json), copied rather
    than imported: that module's imports pull in nba_api."""
    import requests
    from data.ingestors.injury_ingestor import ESPN_HEADERS

    last: Exception | None = None
    for attempt in range(2):
        try:
            resp = requests.get(url, params=params, headers=ESPN_HEADERS, timeout=20)
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


def fetch_scoreboard(day: str, get_json=None) -> dict:
    get_json = get_json or _http_get_json
    return get_json(SCOREBOARD_URL, {"dates": day.replace("-", ""),
                                     "groups": D1_GROUP, "limit": SCOREBOARD_LIMIT})


# ── parsing ──────────────────────────────────────────────────────────────────

def _int(v) -> int | None:
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _ts(v) -> datetime | None:
    s = str(v or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _utc_iso(v) -> str | None:
    """ESPN's '2025-11-28T01:00Z' as '2025-11-28T01:00:00Z', the odds feed's shape."""
    dt = _ts(v)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def parse_team(t: dict | None) -> dict | None:
    """A scoreboard or /teams team -> our team fields, or None for a slot with
    no real team (no positive id, no location, or 'TBD')."""
    t = t or {}
    espn_id = _int(t.get("id"))
    school = str(t.get("location") or "").strip()
    if espn_id is None or espn_id <= 0 or not school or school.upper() == "TBD":
        return None
    return {"espn_id": espn_id, "school": school,
            "mascot": t.get("name") or None,
            "display_name": t.get("displayName") or None,
            "short_name": t.get("shortDisplayName") or None,
            "abbreviation": t.get("abbreviation") or None}


def parse_event(ev: dict) -> dict | None:
    """One scoreboard event -> the fields we store, or None when it does not
    have two real teams or a usable date.

    `final` is True only for a completed event with both scores and no
    postponement; in-progress scores are never returned as final.
    """
    comp = (ev.get("competitions") or [{}])[0] or {}
    sides: dict[str, tuple] = {}
    for c in comp.get("competitors") or []:
        if c.get("homeAway") in ("home", "away"):
            sides[c["homeAway"]] = (parse_team(c.get("team")), c.get("score"))
    home, home_score = sides.get("home", (None, None))
    away, away_score = sides.get("away", (None, None))
    event_id = _int(ev.get("id"))
    raw = ev.get("date") or comp.get("date")
    if not home or not away or home["espn_id"] == away["espn_id"] \
            or event_id is None or not raw:
        return None
    game_date = nt.eastern_game_date(raw)
    try:
        date.fromisoformat(game_date)
    except ValueError:
        return None

    status = comp.get("status") or ev.get("status") or {}
    st = status.get("type") or {}
    status_name = str(st.get("name") or "") or None
    off = bool(_OFF.search(status_name or ""))
    period = _int(status.get("period")) or 0
    hs, as_ = _int(home_score), _int(away_score)
    final = (bool(st.get("completed")) and st.get("state") == "post" and not off
             and hs is not None and as_ is not None)
    if final and hs == as_:
        logger.warning(f"NCAAB ESPN: event {event_id} is final at {hs}-{as_}, a tie; "
                       f"no score taken")
        final = False

    season_info = ev.get("season") or {}
    venue = comp.get("venue") or {}
    addr = venue.get("address") or {}
    venue_id = _int(venue.get("id"))
    notes = " / ".join(str(n.get("headline")) for n in comp.get("notes") or []
                       if n.get("headline"))
    return {
        "espn_event_id": event_id,
        "game_date": game_date,
        # timeValid false = a date with no tip yet; ESPN's midnight-ET stamp is
        # not a start time (module docstring, TIP TIMES).
        "commence_time": _utc_iso(raw) if comp.get("timeValid", True) is not False else None,
        "season": _int(season_info.get("year")) or nt.ncaab_season_label(game_date),
        "season_type": _int(season_info.get("type")),
        "neutral_site": bool(comp.get("neutralSite")),
        "conference_game": bool(comp.get("conferenceCompetition")),
        "venue": ({"venue_id": venue_id, "name": venue.get("fullName") or None,
                   "city": addr.get("city") or None, "state": addr.get("state") or None,
                   "indoor": venue.get("indoor") if isinstance(venue.get("indoor"), bool)
                   else None} if venue_id is not None else None),
        "venue_id": venue_id,
        "home": home,
        "away": away,
        "status": status_name,
        "off": off,
        "period": period,
        "final": final,
        "home_score": hs if final else None,
        "away_score": as_ if final else None,
        "went_to_ot": 1 if period > 2 else 0,
        "notes": notes or None,
    }


def _school_from_display(t: dict) -> str | None:
    """A groups-only team has no `location`: its display name with the mascot
    taken off ("Queens University Royals" - "Royals"), else its short name."""
    display = str(t.get("displayName") or "").strip()
    mascot = str(t.get("name") or "").strip()
    if display and mascot and display.endswith(" " + mascot):
        return display[: -len(mascot) - 1].strip() or None
    return (t.get("shortDisplayName") or display or "").strip() or None


def merge_d1(teams_doc: dict, groups_doc: dict) -> list[dict]:
    """Every Division I team from /teams and the groups listing, merged.

    /teams supplies the school (`location`); groups supplies the conference.
    A team only the groups listing has gets a school derived from its display
    name, flagged keep_school so it never overwrites a location already stored.
    """
    out: dict[int, dict] = {}
    leagues = ((teams_doc.get("sports") or [{}])[0] or {}).get("leagues") or [{}]
    for item in (leagues[0] or {}).get("teams") or []:
        t = parse_team((item or {}).get("team") or item)
        if t:
            out[t["espn_id"]] = {**t, "conference": None, "conference_abbr": None,
                                 "is_d1": True, "keep_school": False}
    for grp in groups_doc.get("groups") or []:
        if str(grp.get("name") or "").strip().lower() != D1_GROUP_NAME:
            continue
        for conf in grp.get("children") or []:
            for t in conf.get("teams") or []:
                espn_id = _int(t.get("id"))
                if espn_id is None or espn_id <= 0:
                    continue
                row = out.get(espn_id)
                if row is None:
                    school = _school_from_display(t)
                    if not school:
                        continue
                    row = out[espn_id] = {
                        "espn_id": espn_id, "school": school,
                        "mascot": t.get("name") or None,
                        "display_name": t.get("displayName") or None,
                        "short_name": t.get("shortDisplayName") or None,
                        "abbreviation": t.get("abbreviation") or None,
                        "is_d1": True, "keep_school": True}
                row["conference"] = conf.get("name") or None
                row["conference_abbr"] = conf.get("abbreviation") or None
                row["abbreviation"] = row.get("abbreviation") or t.get("abbreviation") or None
    return list(out.values())


# ── teams ────────────────────────────────────────────────────────────────────

def assign_slug(school: str, espn_id: int, taken: dict[str, int]) -> str:
    """The slug a NEW team gets: its school's slug, or slug-<espn_id> when
    another ESPN id already holds that one. Records the result in `taken`
    (slug -> espn_id), so two new teams in one batch cannot collide either."""
    base = nt.ncaab_slug(school) or "team"
    slug = base if taken.get(base, espn_id) == espn_id else f"{base}-{espn_id}"
    taken[slug] = espn_id
    return slug


def _registry(conn) -> dict[int, dict]:
    rows = conn.execute("SELECT espn_id, school, slug, is_d1 FROM ncaab_teams").fetchall()
    return {int(r[0]): {"school": r[1], "slug": r[2], "is_d1": bool(r[3])} for r in rows}


_TEAM_UPSERT = """
INSERT INTO ncaab_teams (espn_id, school, slug, mascot, display_name, short_name,
                         abbreviation, conference, conference_abbr, is_d1, updated_at)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
ON CONFLICT (espn_id) DO UPDATE SET
    school          = CASE WHEN %s THEN ncaab_teams.school ELSE EXCLUDED.school END,
    mascot          = COALESCE(EXCLUDED.mascot, ncaab_teams.mascot),
    display_name    = COALESCE(EXCLUDED.display_name, ncaab_teams.display_name),
    short_name      = COALESCE(EXCLUDED.short_name, ncaab_teams.short_name),
    abbreviation    = COALESCE(EXCLUDED.abbreviation, ncaab_teams.abbreviation),
    conference      = COALESCE(EXCLUDED.conference, ncaab_teams.conference),
    conference_abbr = COALESCE(EXCLUDED.conference_abbr, ncaab_teams.conference_abbr),
    is_d1           = (ncaab_teams.is_d1 OR EXCLUDED.is_d1),
    updated_at      = NOW()
"""


def upsert_teams(conn, teams: list[dict], registry: dict[int, dict]) -> dict[int, dict]:
    """Write `teams`; returns the registry entries for the rows it INSERTED.

    The slug is chosen here for a new team and is never part of the update, so
    an existing team's slug (and every game_id built from it) cannot move.
    is_d1 is OR-ed: a scoreboard sighting can never downgrade a D1 school.
    """
    taken = {v["slug"]: k for k, v in registry.items()}
    rows, added = [], {}
    for t in {t["espn_id"]: t for t in teams}.values():
        prior = registry.get(t["espn_id"])
        if prior is not None:
            slug = prior["slug"]
        else:
            slug = assign_slug(t["school"], t["espn_id"], taken)
            added[t["espn_id"]] = {"school": t["school"], "slug": slug,
                                   "is_d1": bool(t.get("is_d1"))}
        rows.append((t["espn_id"], t["school"], slug, t.get("mascot"), t.get("display_name"),
                     t.get("short_name"), t.get("abbreviation"), t.get("conference"),
                     t.get("conference_abbr"), bool(t.get("is_d1")),
                     bool(t.get("keep_school"))))
    if rows:
        conn.executemany(_TEAM_UPSERT, rows)
    return added


def refresh_teams(conn, *, get_json=None) -> dict:
    """Every Division I team (/teams UNION the groups listing) into ncaab_teams.

    Two ESPN calls. Commits, and drops ncaab_teams' in-process registry cache
    so an odds step later in the same process resolves against the new rows.
    """
    get_json = get_json or _http_get_json
    teams_doc = get_json(TEAMS_URL, {"groups": D1_GROUP, "limit": SCOREBOARD_LIMIT})
    groups_doc = get_json(GROUPS_URL, {})
    d1 = merge_d1(teams_doc, groups_doc)
    registry = _registry(conn)
    added = upsert_teams(conn, d1, registry)
    conn.commit()
    nt.reset_registry_cache()
    out = {"d1_teams": len(d1), "added": len(added),
           "groups_only": sum(1 for t in d1 if t.get("keep_school")),
           "no_conference": sum(1 for t in d1 if not t.get("conference"))}
    logger.info(f"NCAAB teams (ESPN): {out}")
    return out


def _ensure_d1_registry(conn, get_json, totals: dict) -> None:
    """Run refresh_teams once if ncaab_teams holds no D1 school yet, so D1
    schools claim their slugs before any buy-game opponent seen on a
    scoreboard can (the later of two colliding ids is the one suffixed)."""
    row = conn.execute("SELECT 1 FROM ncaab_teams WHERE is_d1 LIMIT 1").fetchone()
    conn.rollback()
    if row is None:
        totals["teams"] = refresh_teams(conn, get_json=get_json)


# ── one ET date ──────────────────────────────────────────────────────────────

_VENUE_UPSERT = """
INSERT INTO ncaab_venues (venue_id, name, city, state, indoor, updated_at)
VALUES (%s, %s, %s, %s, %s, NOW())
ON CONFLICT (venue_id) DO UPDATE SET
    name = EXCLUDED.name, city = EXCLUDED.city, state = EXCLUDED.state,
    indoor = EXCLUDED.indoor, updated_at = NOW()
"""

_GAME_UPSERT = """
INSERT INTO games (game_id, sport, season, game_date, home_team, away_team,
                   commence_time, neutral_site, conference_game, venue_id,
                   data_source, created_at, updated_at)
VALUES (%s, 'NCAAB', %s, %s, %s, %s, %s, %s, %s, %s, 'espn', NOW()::TEXT, NOW()::TEXT)
ON CONFLICT (game_id) DO UPDATE SET
    season = EXCLUDED.season, game_date = EXCLUDED.game_date,
    commence_time = EXCLUDED.commence_time, neutral_site = EXCLUDED.neutral_site,
    conference_game = EXCLUDED.conference_game, venue_id = EXCLUDED.venue_id,
    updated_at = NOW()::TEXT
WHERE games.sport = 'NCAAB'
"""

# Belt and braces: the decision to fill is made in Python from the stored row,
# and this WHERE refuses to touch a row that has a score whatever Python decided.
_SCORE_FILL = """
UPDATE games SET home_score = %s, away_score = %s, home_win = %s, went_to_ot = %s,
                 regulation_tie = %s, updated_at = NOW()::TEXT
 WHERE game_id = %s AND sport = 'NCAAB'
   AND (home_score IS NULL OR away_score IS NULL)
"""

_EVENT_UPSERT = """
INSERT INTO ncaab_events (espn_event_id, game_id, season, game_date, commence_time,
                          home_espn_id, away_espn_id, neutral_site, conference_game,
                          venue_id, season_type, status, notes, updated_at)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
ON CONFLICT (espn_event_id) DO UPDATE SET
    season = EXCLUDED.season, game_date = EXCLUDED.game_date,
    commence_time = EXCLUDED.commence_time, neutral_site = EXCLUDED.neutral_site,
    conference_game = EXCLUDED.conference_game, venue_id = EXCLUDED.venue_id,
    season_type = EXCLUDED.season_type, status = EXCLUDED.status,
    notes = EXCLUDED.notes, updated_at = NOW()
"""


def new_totals() -> dict:
    return {"dates": 0, "dates_fetched": 0, "events": 0, "no_teams": 0,
            "games_inserted": 0, "games_updated": 0, "unchanged": 0, "moved": 0,
            "scores_filled": 0, "score_conflicts": 0, "postponed": 0,
            "postponed_unseen": 0, "teams_changed": 0, "id_collisions": 0,
            "teams_added": 0, "venues_written": 0, "errors": 0, "failed": []}


def _merge(into: dict, day: dict) -> None:
    for k, v in day.items():
        if k == "failed":
            into["failed"].extend(v)
        elif isinstance(v, int) and not isinstance(v, bool) and k in into:
            into[k] += v
        elif k not in into:
            into[k] = v


def _in(n: int) -> str:
    return ", ".join(["%s"] * n)


def _bool(v) -> bool | None:
    return None if v is None else bool(v)


def _stored_state(conn, parsed: list[dict]):
    """The rows this board's events already have: ncaab_events by event id,
    and the game_id each event id owns."""
    ids = [p["espn_event_id"] for p in parsed]
    known = {}
    for r in conn.execute(
            "SELECT espn_event_id, game_id, home_espn_id, away_espn_id, season, game_date, "
            "commence_time, neutral_site, conference_game, venue_id, season_type, status, "
            f"notes FROM ncaab_events WHERE espn_event_id IN ({_in(len(ids))})",
            tuple(ids)).fetchall():
        known[int(r[0])] = {
            "game_id": r[1], "home_espn_id": int(r[2]), "away_espn_id": int(r[3]),
            "row": (r[4], r[5], r[6], _bool(r[7]), _bool(r[8]), r[9], r[10], r[11], r[12])}
    return known


def _stored_games(conn, game_ids: list[str]) -> tuple[dict, dict]:
    """games rows by game_id, and which ESPN event owns each of those ids."""
    if not game_ids:
        return {}, {}
    games = {}
    for r in conn.execute(
            "SELECT game_id, season, game_date, commence_time, neutral_site, "
            "conference_game, venue_id, home_score, away_score FROM games "
            f"WHERE game_id IN ({_in(len(game_ids))})", tuple(game_ids)).fetchall():
        games[r[0]] = {"row": (r[1], r[2], r[3], r[4], r[5], r[6]),
                       "game_date": r[2], "commence_time": r[3],
                       "home_score": r[7], "away_score": r[8]}
    owners = {r[0]: int(r[1]) for r in conn.execute(
        f"SELECT game_id, espn_event_id FROM ncaab_events WHERE game_id IN ({_in(len(game_ids))})",
        tuple(game_ids)).fetchall()}
    return games, owners


def ingest_day(conn, day: str, *, get_json=None, ensure: bool = True,
               registry: dict | None = None) -> dict:
    """One ET date: one scoreboard call, then teams, venues, ncaab_events and
    games, committed together (one savepoint per event, so a bad event is
    counted and the rest still land). Returns that day's counts.

    ensure: create the tables and load the D1 registry first (a runner that
    has already done both for the run passes False). `registry`, when given,
    is the run's {espn_id: {school, slug, is_d1}}; teams this day inserts are
    added to it only after the commit.
    """
    get_json = get_json or _http_get_json
    totals = new_totals()
    totals["dates"] = 1
    if ensure:
        nt.ensure_tables(conn)
        _ensure_d1_registry(conn, get_json, totals)
    conn.rollback()                      # no read snapshot held while ESPN answers
    board = fetch_scoreboard(day, get_json)
    totals["dates_fetched"] = 1
    raw_events = board.get("events") or []
    if len(raw_events) >= SCOREBOARD_LIMIT:
        logger.warning(f"NCAAB ESPN: {day} returned {len(raw_events)} events, the limit; "
                       f"some may be missing")
    parsed = []
    for ev in raw_events:
        p = parse_event(ev)
        if p is None:
            totals["no_teams"] += 1
            continue
        parsed.append(p)
    totals["events"] = len(parsed)
    if not parsed:
        return totals

    reg = dict(registry) if registry is not None else _registry(conn)
    seen = [t for p in parsed for t in (p["home"], p["away"])]
    added = upsert_teams(conn, [t for t in seen if t["espn_id"] not in reg], reg)
    reg.update(added)
    totals["teams_added"] = len(added)

    known = _stored_state(conn, parsed)
    planned = {}
    for p in parsed:
        prior = known.get(p["espn_event_id"])
        if prior is not None:
            planned[p["espn_event_id"]] = prior["game_id"]
        else:
            planned[p["espn_event_id"]] = nt.build_ncaab_game_id(
                p["game_date"], reg[p["away"]["espn_id"]]["slug"],
                reg[p["home"]["espn_id"]]["slug"])
    stored, owners = _stored_games(conn, sorted(set(planned.values())))

    venues = {p["venue_id"]: p["venue"] for p in parsed if p["venue"]}
    venues_written = _write_venues(conn, venues)
    totals["venues_written"] = venues_written

    for p in parsed:
        try:
            _one_event(conn, p, reg, known, planned[p["espn_event_id"]], stored, owners, totals)
        except ConnectionLost:
            # The day's transaction is gone with the connection: fail the whole
            # date (the next pass redoes it) rather than commit the rest on a
            # fresh transaction and count writes that never landed.
            raise
        except Exception as exc:                          # noqa: BLE001
            why = "timed out" if statement_timeout(exc) else f"write failed: {exc}"
            logger.warning(f"NCAAB ESPN: event {p['espn_event_id']} ({day}) {why}")
            totals["errors"] += 1
            totals["failed"].append(f"{day}:{p['espn_event_id']}")
    conn.commit()
    if added:
        nt.reset_registry_cache()
        if registry is not None:
            registry.update(added)
    return totals


def _write_venues(conn, venues: dict[int, dict]) -> int:
    """Upsert the venues whose stored fields differ. Coordinates untouched."""
    if not venues:
        return 0
    ids = list(venues)
    have = {int(r[0]): (r[1], r[2], r[3], _bool(r[4])) for r in conn.execute(
        f"SELECT venue_id, name, city, state, indoor FROM ncaab_venues "
        f"WHERE venue_id IN ({_in(len(ids))})", tuple(ids)).fetchall()}
    rows = [(v["venue_id"], v["name"], v["city"], v["state"], v["indoor"])
            for v in venues.values()
            if have.get(v["venue_id"]) != (v["name"], v["city"], v["state"], v["indoor"])]
    if rows:
        conn.executemany(_VENUE_UPSERT, rows)
    return len(rows)


def _score_action(game_id: str, g: dict | None, hs: int, as_: int,
                  totals: dict) -> str | None:
    """'fill' when the stored row has no score yet; None when it already holds
    this one; a different stored score is a conflict, logged and counted and
    never written (CLAUDE.md section 1c)."""
    if g is None or g["home_score"] is None or g["away_score"] is None:
        return "fill"
    if (int(g["home_score"]), int(g["away_score"])) == (hs, as_):
        return None
    totals["score_conflicts"] += 1
    logger.warning(f"NCAAB ESPN: {game_id} stored {int(g['home_score'])}-"
                   f"{int(g['away_score'])} (home-away), ESPN says {hs}-{as_}; "
                   f"NOT overwritten")
    return None


def _fill_score(conn, game_id: str, g: dict | None, hs: int, as_: int, ot: int,
                totals: dict) -> None:
    """The final alone onto a stored games row (the flipped-orientation case):
    no schedule field and no ncaab_events field is touched."""
    if g is None or _score_action(game_id, g, hs, as_, totals) != "fill":
        return
    n = call_in_savepoint(conn, "ncaab_espn_score", lambda: conn.execute(
        _SCORE_FILL, (hs, as_, 1 if hs > as_ else 0, ot, ot, game_id)).rowcount or 0)
    if n:
        totals["scores_filled"] += 1
        g["home_score"], g["away_score"] = hs, as_


def _one_event(conn, p: dict, reg: dict, known: dict, game_id: str,
               stored: dict, owners: dict, totals: dict) -> None:
    eid = p["espn_event_id"]
    home, away = reg[p["home"]["espn_id"]], reg[p["away"]["espn_id"]]
    prior = known.get(eid)
    if prior is not None:
        was = (prior["home_espn_id"], prior["away_espn_id"])
        now = (p["home"]["espn_id"], p["away"]["espn_id"])
        if was != now:
            totals["teams_changed"] += 1
            flipped = was == now[::-1]
            logger.warning(f"NCAAB ESPN: event {eid} ({game_id}) was stored as "
                           f"{was[1]} @ {was[0]}, ESPN now says {now[1]} @ {now[0]}; "
                           f"schedule NOT rewritten (stored odds are in the old orientation)"
                           + ("; its final is taken in the stored orientation"
                              if flipped and p["final"] else ""))
            # Home and away swapped, same two teams: the final still belongs on
            # the stored row, mapped by team (stored home = ESPN's away now).
            # Skipping it too would leave the game unscored and its picks
            # unsettled for good. A different pair of teams is left to a human.
            if flipped and p["final"]:
                _fill_score(conn, game_id, stored.get(game_id), p["away_score"],
                            p["home_score"], p["went_to_ot"], totals)
            return
    else:
        if p["off"]:
            totals["postponed_unseen"] += 1
            logger.info(f"NCAAB ESPN: event {eid} {p['status']} on first sight; no games row")
            return
        owner = owners.get(game_id)
        if owner is not None and owner != eid:
            totals["id_collisions"] += 1
            logger.warning(f"NCAAB ESPN: event {eid} would be {game_id}, which event "
                           f"{owner} already owns; skipped (one games row per game)")
            return

    g = stored.get(game_id)
    # A TBD tip on the date already stored keeps the tip we have; on a new
    # date it is unknown again.
    commence = p["commence_time"]
    if commence is None and g is not None and g["game_date"] == p["game_date"]:
        commence = g["commence_time"]
    venue_id = p["venue_id"] if p["venue_id"] is not None else (g["row"][5] if g else None)
    game_row = (p["season"], p["game_date"], commence, 1 if p["neutral_site"] else 0,
                1 if p["conference_game"] else 0, venue_id)
    event_row = (p["season"], p["game_date"], commence, p["neutral_site"],
                 p["conference_game"], venue_id, p["season_type"], p["status"], p["notes"])

    fill = None
    if p["final"] and _score_action(game_id, g, p["home_score"], p["away_score"],
                                    totals) == "fill":
        fill = p

    game_same = g is not None and tuple(g["row"]) == game_row
    event_same = prior is not None and prior["row"] == event_row
    if game_same and event_same and fill is None:
        totals["unchanged"] += 1
        return

    def _write():
        if not game_same:
            conn.execute(_GAME_UPSERT, (game_id, p["season"], p["game_date"], home["school"],
                                        away["school"], commence, game_row[3], game_row[4],
                                        venue_id))
        if not event_same:
            conn.execute(_EVENT_UPSERT, (eid, game_id, p["season"], p["game_date"], commence,
                                         p["home"]["espn_id"], p["away"]["espn_id"],
                                         p["neutral_site"], p["conference_game"], venue_id,
                                         p["season_type"], p["status"], p["notes"]))
        if fill is not None:
            hs, as_ = fill["home_score"], fill["away_score"]
            return conn.execute(_SCORE_FILL, (hs, as_, 1 if hs > as_ else 0, fill["went_to_ot"],
                                              fill["went_to_ot"], game_id)).rowcount or 0
        return 0

    filled = call_in_savepoint(conn, "ncaab_espn_event", _write)
    owners[game_id] = eid
    if g is None:
        totals["games_inserted"] += 1
    else:
        totals["games_updated"] += 1
        if g["game_date"] != p["game_date"]:
            totals["moved"] += 1
            logger.info(f"NCAAB ESPN: {game_id} moved {g['game_date']} -> {p['game_date']} "
                        f"(event {eid}); game_id kept")
    if p["off"]:
        totals["postponed"] += 1
    if filled:
        totals["scores_filled"] += 1
    stored[game_id] = {"row": game_row, "game_date": p["game_date"],
                       "commence_time": commence,
                       "home_score": fill["home_score"] if filled else (g or {}).get("home_score"),
                       "away_score": fill["away_score"] if filled else (g or {}).get("away_score")}
    known[eid] = {"game_id": game_id, "home_espn_id": p["home"]["espn_id"],
                  "away_espn_id": p["away"]["espn_id"], "row": event_row}


# ── the runners ──────────────────────────────────────────────────────────────

def _today_et(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(_ET).strftime("%Y-%m-%d")


def _days(first: str, last: str) -> list[str]:
    d, end, out = date.fromisoformat(first), date.fromisoformat(last), []
    while d <= end:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _run_days(conn, days: list[str], totals: dict, *, get_json, sleep: float,
              registry: dict, label: str, echo: bool = False) -> None:
    for i, d in enumerate(days):
        if i and sleep:
            time.sleep(sleep)
        try:
            day = ingest_day(conn, d, get_json=get_json, ensure=False, registry=registry)
        except Exception as exc:                          # noqa: BLE001
            logger.warning(f"NCAAB {label}: {d} failed: {exc}")
            try:
                conn.rollback()
            except Exception:                             # noqa: BLE001
                pass
            totals["dates"] += 1
            totals["errors"] += 1
            totals["failed"].append(d)
            continue
        _merge(totals, day)
        if echo:
            print(f"{d}: " + ", ".join(f"{k}={v}" for k, v in day.items()
                                       if v and k not in ("dates", "dates_fetched", "failed")))


def _open(connect):
    return (connect or get_connection)(), connect is None


def due_dates(conn, run_date: str | None = None, now: datetime | None = None,
              heal_days: int = HEAL_DAYS) -> list[str]:
    """The scoreboard dates to fetch: the ET dates holding a started NCAAB
    game with no score, within heal_days.

    Pure database read; this is what lets an idle refresh pass make no ESPN
    call. A postponed or cancelled event is never due. A game with no tip time
    (ESPN's TBD) counts as started once its date is past or is one of
    config.live_slate_dates(). A tip before EARLY_TIP_HOUR_ET also names the
    previous ET date, the board ESPN files it on. Before the first NCAAB write
    the tables do not exist: that reads as nothing due.
    """
    now = now or datetime.now(timezone.utc)
    today = run_date or _today_et(now)
    first = (date.fromisoformat(today) - timedelta(days=heal_days)).isoformat()
    try:
        rows = conn.execute("""
            SELECT g.game_date, g.commence_time, e.status
              FROM games g LEFT JOIN ncaab_events e ON e.game_id = g.game_id
             WHERE g.sport = 'NCAAB'
               AND (g.home_score IS NULL OR g.away_score IS NULL)
               AND g.game_date >= %s AND g.game_date <= %s
        """, (first, today)).fetchall()
    except Exception as exc:                              # noqa: BLE001
        logger.info(f"NCAAB results: nothing to read yet ({str(exc)[:80]})")
        try:
            conn.rollback()
        except Exception:                                 # noqa: BLE001
            pass
        return []
    live = set(config.live_slate_dates(now.astimezone(_ET)))
    due = set()
    for game_date, commence, status in rows:
        if status and _OFF.search(str(status)):
            continue
        start = _ts(commence)
        if start is not None:
            if start <= now:
                due.add(str(game_date)[:10])
                et = start.astimezone(_ET)
                if et.hour < EARLY_TIP_HOUR_ET:
                    due.add((et.date() - timedelta(days=1)).isoformat())
        elif str(game_date) < today or str(game_date)[:10] in live:
            due.add(str(game_date)[:10])
    return sorted(due)


def run_results(run_date: str | None = None, *, now: datetime | None = None,
                get_json=None, connect=None, sleep: float = REQUEST_SLEEP) -> dict:
    """The refresh-pass step: finals for every due date (due_dates), nothing else.

    Costs no ESPN call when nothing is due -- the GROUP 3 contract in
    scripts/refresh_pass.sh. A due date also refreshes that day's schedule
    fields, since it is the same scoreboard.
    """
    now = now or datetime.now(timezone.utc)
    conn, own = _open(connect)
    totals = new_totals()
    try:
        dates = due_dates(conn, run_date, now)
        conn.rollback()
        if not dates:
            logger.info("NCAAB results: nothing pending (no ESPN call)")
            return totals
        get_json = get_json or _http_get_json
        nt.ensure_tables(conn)
        _ensure_d1_registry(conn, get_json, totals)
        registry = _registry(conn)
        conn.rollback()
        _run_days(conn, dates, totals, get_json=get_json, sleep=sleep,
                  registry=registry, label="results")
    finally:
        if own:
            conn.close()
    logger.info(f"NCAAB results (ESPN): {_summary(totals)}")
    return totals


def run_schedule_refresh(run_date: str | None = None, days: int = SCHEDULE_DAYS, *,
                         get_json=None, connect=None, sleep: float = REQUEST_SLEEP) -> dict:
    """The daily-pipeline step: the D1 team list, then today and the next
    `days` ET dates, so new games and moved tips appear."""
    get_json = get_json or _http_get_json
    run_date = run_date or _today_et()
    conn, own = _open(connect)
    totals = new_totals()
    try:
        nt.ensure_tables(conn)
        conn.rollback()
        try:
            totals["teams"] = refresh_teams(conn, get_json=get_json)
        except Exception as exc:                          # noqa: BLE001
            logger.warning(f"NCAAB schedule: team refresh failed: {exc}")
            try:
                conn.rollback()
            except Exception:                             # noqa: BLE001
                pass
            totals["errors"] += 1
            totals["failed"].append("teams")
        registry = _registry(conn)
        conn.rollback()
        anchor = date.fromisoformat(run_date)
        _run_days(conn, _days(run_date, (anchor + timedelta(days=days)).isoformat()), totals,
                  get_json=get_json, sleep=sleep, registry=registry, label="schedule")
    finally:
        if own:
            conn.close()
    logger.info(f"NCAAB schedule (ESPN): {_summary(totals)}")
    return totals


def run_backfill(first: str, last: str, *, get_json=None, connect=None,
                 sleep: float = REQUEST_SLEEP) -> dict:
    """Every ET date in [first, last]: the team list once, then one scoreboard
    per day, a pause between calls, counts printed per day. Re-running it is
    idempotent (event-id keyed upserts; a day already stored writes nothing),
    so an interrupted backfill resumes by running it again."""
    if date.fromisoformat(first) > date.fromisoformat(last):
        raise ValueError(f"backfill range is reversed: {first} > {last}")
    get_json = get_json or _http_get_json
    conn, own = _open(connect)
    totals = new_totals()
    try:
        nt.ensure_tables(conn)
        conn.rollback()
        totals["teams"] = refresh_teams(conn, get_json=get_json)
        registry = _registry(conn)
        conn.rollback()
        _run_days(conn, _days(first, last), totals, get_json=get_json, sleep=sleep,
                  registry=registry, label="backfill", echo=True)
    finally:
        if own:
            conn.close()
    logger.info(f"NCAAB backfill {first}..{last} (ESPN): {_summary(totals)}")
    return totals


def _summary(totals: dict) -> dict:
    return {k: (len(v) if isinstance(v, list) else v) for k, v in totals.items()}


# ── CLI ──────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="NCAAB schedule and finals from ESPN")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--backfill", nargs=2, metavar=("FIRST", "LAST"),
                      help="every ET date in FIRST..LAST (YYYY-MM-DD)")
    mode.add_argument("--results", action="store_true",
                      help="finals for the dates with a started, unscored game")
    mode.add_argument("--schedule", action="store_true",
                      help="the team list, then --date and the next --days dates")
    mode.add_argument("--teams", action="store_true", help="the Division I team list only")
    ap.add_argument("--date", help="ET anchor date (default: today ET)")
    ap.add_argument("--days", type=int, default=SCHEDULE_DAYS)
    a = ap.parse_args(argv)
    if a.backfill:
        t = run_backfill(*a.backfill)
    elif a.results:
        t = run_results(a.date)
    elif a.schedule:
        t = run_schedule_refresh(a.date, days=a.days)
    else:
        conn = get_connection()
        try:
            nt.ensure_tables(conn)
            conn.rollback()
            t = refresh_teams(conn)
        finally:
            conn.close()
    return 1 if t.get("failed") else 0


if __name__ == "__main__":
    # API telemetry for the live monitor (monitoring/). Best-effort and silent.
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("ncaab-espn")
    except Exception:  # noqa: BLE001
        pass

    raise SystemExit(main())
