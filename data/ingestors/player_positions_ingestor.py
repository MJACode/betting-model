"""
player_positions_ingestor.py — a position for every NBA, WNBA and NCAAF player
we have a game log for, keyed on OUR player_id.

Why this exists (Matt, 2026-10-05): the player page's "same position vs the
next opponent" card needs a position for every player in the log, and only the
NFL log carries one. Measured 2026-10-03: nba_player_game_log and
wnba_player_game_log have no position column (only is_starter);
ncaaf_player_game_log has none either — CFBD's box score names participants,
not positions. Matt chose G / F / C for basketball (2026-10-05).

SOURCES — chosen for what the WORKER can reach:
  NBA, WNBA  ESPN core v2 (sports.core.api.espn.com). The worker reaches it;
             site.api.espn.com 403s the worker (wnba_results_ingestor, 2026-08-05)
             and stats.nba.com blocks datacenter IPs (run_pipeline.py's local
             Basketball Daily Ingest note). Team rosters list athlete $refs; the
             athlete doc carries the position.
  NCAAF      CFBD /roster, one call per season. CFBD's athlete id is the id
             ncaaf_player_game_log already uses (both come from CFBD), so the
             join is exact rather than by name. Needs CFBD_API_KEY, which is set
             on the worker only.

PLAYER IDS (load-bearing). The basketball logs key on the nba_api PLAYER_ID, not
ESPN's athlete id, so each ESPN athlete is mapped back by NORMALISED NAME
against the log — the same rule wnba_results_ingestor uses (norm_player_name),
narrowed by team when a name is shared, and — Matt, 2026-10-06: "don't skip
names" — a name still shared after that goes to the player with the most
recent game, counted as a tiebreak. An athlete with no log history is skipped
and counted: the card needs positions only for players with games.

UNVERIFIED SHAPES, ON PURPOSE MEASURED FIRST. The dev sandbox's egress proxy
403s ESPN and CFBD outright (requests and WebFetch, 2026-10-06), so the
response shapes below are read defensively and the first run is a DRY RUN on
the worker (`jobs/declared_jobs.json`, job type `player_positions`), which
writes nothing and reports counts, the match rate and a sample. Only after that
result is read does the real run write. Every unexpected shape skips the row;
nothing here raises on a single bad athlete.
  ESPN team list   /v2/sports/basketball/leagues/{league}/teams?limit=50
                   -> items[].$ref (.../teams/{id}?...)
  ESPN team doc    {id, abbreviation, displayName}
  ESPN roster      /v2/sports/basketball/leagues/{league}/seasons/{year}/teams/{id}/athletes?limit=200
                   -> items[].$ref (.../athletes/{id}?...)
                   MEASURED on the worker 2026-10-06 (dry run, job 405765): the
                   season-less /teams/{id}/athletes answers 404 for every NBA and
                   WNBA team, while /teams?limit=50 lists 30 and 17. Which season
                   LABEL ESPN files the current roster under is not measured yet
                   (the NBA season starting this month may be 2026 or 2027), so
                   roster_candidates() tries the likely years in order and the
                   run summary records the one that answered.
  ESPN athlete     {id, displayName, fullName, position{abbreviation | $ref}}
  CFBD /roster     [{id, firstName, lastName, team, position, year?}]

POLITENESS. ESPN has IP-blocked the worker twice. A pass always spends the
roster LIST (one teams call, one team doc and one roster call per club —
about 98 for NBA + WNBA once the first season year answers, which is what
dry run 2 measured). Athlete docs are the spike. Two things used to make
that spike daily or weekly:

  * A stored athlete skipped as fresh never had `updated_at` touched, so a
    cohort written on one morning all fell due REFRESH_DAYS later, on the
    same morning. Touching `updated_at` on the skip would stop that by
    never re-reading a position. The window is REFRESH_DAYS plus a
    deterministic 0–6 day jitter from the athlete id instead, so the same
    cohort falls due across the following week and a position change is
    still re-read.
  * An ESPN athlete with no game-log row was not stored, so the ~140
    unmatched (mostly rookies; dry run 2) were fetched again every morning.
    They are remembered in `player_position_unmatched` for the same window,
    then tried again so a rookie who starts playing does get a position.

MAX_ATHLETE_HTTP caps athlete docs and position $refs in one run, so a cold
or fully expired morning cannot walk the whole roster. List calls are not
capped: they are bounded by the number of clubs.

Everything lands in Supabase (CLAUDE.md §1b): `player_positions`, and the
unmatched ids in `player_position_unmatched`.
"""
from __future__ import annotations

import hashlib
import re
import time
from datetime import datetime, timedelta, timezone

import requests
from loguru import logger

from data.ingestors.wnba_results_ingestor import norm_player_name

ESPN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
CORE = "https://sports.core.api.espn.com/v2/sports/basketball/leagues"
LEAGUE_OF = {"NBA": "nba", "WNBA": "wnba"}
LOG_TABLE = {"NBA": "nba_player_game_log", "WNBA": "wnba_player_game_log"}
SPORTS = ("NBA", "WNBA", "NCAAF")

#: An athlete stored this recently is not re-fetched. The real window is
#: this plus a 0–6 day per-id jitter (`refresh_window_days`).
REFRESH_DAYS = 7
#: Extra days, hashed from the athlete id, so one ingest morning does not
#: become one refetch morning.
JITTER_DAYS = 7
#: Athlete documents and the position $ref each may follow, per run, both
#: leagues together. Above a steady week of the measured 852-athlete set
#: (about 90 docs/day at a 7–13 day window, or about 180 if every one of
#: those also follows a $ref) and below a cold read of all 852. List calls
#: are not counted here.
MAX_ATHLETE_HTTP = 320
#: Pause between ESPN requests (seconds).
ESPN_PAUSE = 0.15
#: How many sample rows a dry run reports.
SAMPLE = 8

_ATHLETE_ID = re.compile(r"/athletes/(\d+)")
_TEAM_ID = re.compile(r"/teams/(\d+)")


# ── basketball groups (Matt, 2026-10-05: G / F / C) ─────────────────────────
#: ESPN's basketball abbreviations. A combo listing groups by its FIRST
#: position ("G-F" is a guard), which is how ESPN orders a primary position.
BASKETBALL_GROUP = {
    "PG": "G", "SG": "G", "G": "G",
    "SF": "F", "PF": "F", "F": "F",
    "C": "C",
}


def basketball_group(position: str | None) -> str | None:
    if not position:
        return None
    first = re.split(r"[-/ ]", str(position).upper().strip())[0]
    return BASKETBALL_GROUP.get(first)


def refresh_window_days(source_athlete_id: str) -> int:
    """How long a stored id stays fresh: REFRESH_DAYS plus 0–6.

    `hash()` is salted per process, so two mornings would disagree about who
    is due. SHA-256 of the id does not.
    """
    digest = hashlib.sha256(str(source_athlete_id).encode("utf-8")).hexdigest()
    return REFRESH_DAYS + (int(digest[:8], 16) % JITTER_DAYS)


def is_within_window(seen_at: datetime, source_athlete_id: str, now: datetime) -> bool:
    """True while `seen_at` is still inside this id's refresh window."""
    if seen_at.tzinfo is None:
        seen_at = seen_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    age = now - seen_at
    return age < timedelta(days=refresh_window_days(source_athlete_id))


def ncaaf_roster_season(run_date: str) -> int:
    """Fall-year label for the CFBD roster pull.

    The 2025 season's games run 2025-08-23 → 2026-01-20. `ncaaf_season_for_date`
    (cfbd_ingestor) shifts only January and February, which is the right label
    for a game date and the wrong one for a roster pull in March–July: that
    calendar year has no season yet, so the daily step would read an empty
    log. Months January–July use year-1; August–December use the year itself.
    """
    year, month = int(run_date[:4]), int(run_date[5:7])
    return year - 1 if month <= 7 else year


# ── HTTP ─────────────────────────────────────────────────────────────────────

def _get_json(url: str) -> dict | None:
    try:
        r = requests.get(url, headers=ESPN_HEADERS, timeout=15)
        time.sleep(ESPN_PAUSE)
        if r.status_code != 200:
            logger.warning(f"ESPN {r.status_code} for {url}")
            return None
        return r.json()
    except Exception as exc:                                  # noqa: BLE001
        logger.warning(f"ESPN fetch failed {url}: {exc}")
        return None


def _refs(doc: dict | None) -> list[str]:
    """`items[].$ref` (or bare URL strings) out of a core collection doc."""
    out: list[str] = []
    for it in (doc or {}).get("items", []) or []:
        ref = it if isinstance(it, str) else (it or {}).get("$ref")
        if ref:
            out.append(str(ref))
    return out


# ── parsing (pure, unit-tested) ──────────────────────────────────────────────

def parse_athlete(doc: dict | None, position_doc: dict | None = None) -> dict | None:
    """{espn_id, name, position} from an ESPN core athlete doc, or None.

    `position` may be inline ({abbreviation}) or a $ref the caller followed and
    passed in as `position_doc`.
    """
    if not isinstance(doc, dict):
        return None
    espn_id = str(doc.get("id") or "").strip()
    name = doc.get("displayName") or doc.get("fullName")
    pos = doc.get("position")
    abbrev = None
    if isinstance(pos, dict):
        abbrev = pos.get("abbreviation") or pos.get("displayName") or pos.get("name")
        if not abbrev and position_doc:
            abbrev = position_doc.get("abbreviation") or position_doc.get("displayName")
    if not espn_id or not name or not abbrev:
        return None
    return {"espn_id": espn_id, "name": str(name), "position": str(abbrev).upper()}


def parse_cfbd_roster(rows) -> list[dict]:
    """[{player_id, name, team, position}] from CFBD /roster rows."""
    out = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        pid = r.get("id") or r.get("athleteId")
        pos = r.get("position")
        team = r.get("team")
        first = r.get("firstName") or r.get("first_name") or ""
        last = r.get("lastName") or r.get("last_name") or ""
        name = (f"{first} {last}").strip() or r.get("name")
        if pid is None or not pos or not team:
            continue
        out.append({"player_id": str(pid), "name": name, "team": str(team),
                    "position": str(pos).upper()})
    return out


def match_to_log(name: str, team: str | None, index: dict,
                 how: dict | None = None) -> str | None:
    """Our player_id for an ESPN athlete, by normalised name.

    `index` maps norm_name -> [(player_id, latest_team, latest_game_date)].
    A unique name wins outright; a shared name is settled by team; one still
    shared after that goes to the candidate with the most recent game (Matt,
    2026-10-06: "don't skip names") — among the same-team candidates when there
    are any, else among all of them. `how["method"]` records which rule
    decided, so a run can report how often the tiebreak was needed.
    """
    def _set(m: str) -> None:
        if how is not None:
            how["method"] = m

    cands = index.get(norm_player_name(name)) or []
    if not cands:
        _set("none")
        return None
    ids = {c[0] for c in cands}
    if len(ids) == 1:
        _set("name")
        return next(iter(ids))
    pool = cands
    if team:
        on_team = [c for c in cands if c[1] and str(c[1]).upper() == team.upper()]
        if len({c[0] for c in on_team}) == 1:
            _set("team")
            return on_team[0][0]
        if on_team:
            pool = on_team
    _set("tiebreak_recent")
    return max(pool, key=lambda c: str(c[2] if len(c) > 2 and c[2] else ""))[0]


# ── DB ───────────────────────────────────────────────────────────────────────

def _name_index(conn, sport: str) -> dict:
    """norm_name -> [(player_id, latest team, latest game date)] over the
    last two seasons' log."""
    table = LOG_TABLE[sport]
    rows = conn.execute(f"""
        SELECT DISTINCT ON (player_id) player_id, player_name, team, game_date
        FROM {table}
        WHERE season >= (SELECT max(season) - 1 FROM {table})
        ORDER BY player_id, game_date DESC
    """).fetchall()
    index: dict[str, list] = {}
    for pid, name, team, gdate in rows:
        index.setdefault(norm_player_name(name), []).append((str(pid), team, str(gdate)))
    return index


def _fresh_source_ids(conn, sport: str, now: datetime | None = None) -> set[str]:
    """Source ids whose stored row is still inside its own jittered window.

    The window is applied here, not by writing `updated_at` on the skip.
    A skip-time write would slide every row forward every morning and a
    position would never be re-read.
    """
    rows = conn.execute("""
        SELECT source_athlete_id, updated_at FROM player_positions
        WHERE sport = %s AND source_athlete_id IS NOT NULL
    """, (sport,)).fetchall()
    now = now or datetime.now(timezone.utc)
    fresh: set[str] = set()
    for sid, updated in rows:
        if sid and updated is not None and is_within_window(updated, str(sid), now):
            fresh.add(str(sid))
    return fresh


def _relation_exists(conn, name: str) -> bool:
    row = conn.execute("SELECT to_regclass(%s)", (f"public.{name}",)).fetchone()
    return bool(row and row[0])


def _cached_unmatched_ids(conn, sport: str, now: datetime | None = None) -> set[str]:
    """Unmatched ESPN ids still inside their window. Empty if Matt has not
    applied add_player_position_unmatched.sql yet — the pass still runs, and
    those athletes are fetched again until the table exists."""
    if not _relation_exists(conn, "player_position_unmatched"):
        logger.warning(
            "player_position_unmatched does not exist yet — unmatched athletes "
            "will be re-fetched (migration not applied)")
        return set()
    rows = conn.execute("""
        SELECT source_athlete_id, seen_at FROM player_position_unmatched
        WHERE sport = %s
    """, (sport,)).fetchall()
    now = now or datetime.now(timezone.utc)
    return {
        str(sid) for sid, seen in rows
        if sid and seen is not None and is_within_window(seen, str(sid), now)
    }


def _remember_unmatched(conn, sport: str, ids: list[str]) -> int:
    """Remember ESPN ids that had no log row, so tomorrow's pass skips them
    until the window lapses and a new rookie can match."""
    ids = list(dict.fromkeys(str(i) for i in ids if i))
    if not ids:
        return 0
    if not _relation_exists(conn, "player_position_unmatched"):
        logger.warning(
            "player_position_unmatched does not exist yet — not caching "
            f"{len(ids)} unmatched {sport} athletes")
        return 0
    now = datetime.now(timezone.utc).isoformat()
    for aid in ids:
        conn.execute("""
            INSERT INTO player_position_unmatched
                (sport, source_athlete_id, seen_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (sport, source_athlete_id) DO UPDATE SET
                seen_at = EXCLUDED.seen_at
        """, (sport, aid, now))
    conn.commit()
    return len(ids)


def _upsert(conn, rows: list[dict]) -> int:
    if not rows:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    for r in rows:
        conn.execute("""
            INSERT INTO player_positions
                (sport, player_id, player_name, team, position, pos_group,
                 source, source_athlete_id, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (sport, player_id) DO UPDATE SET
                player_name = EXCLUDED.player_name,
                team = EXCLUDED.team,
                position = EXCLUDED.position,
                pos_group = EXCLUDED.pos_group,
                source = EXCLUDED.source,
                source_athlete_id = EXCLUDED.source_athlete_id,
                updated_at = EXCLUDED.updated_at
        """, (r["sport"], r["player_id"], r["player_name"], r.get("team"),
              r["position"], r.get("pos_group"), r["source"],
              r.get("source_athlete_id"), now))
    conn.commit()
    return len(rows)


# ── basketball ───────────────────────────────────────────────────────────────

def roster_candidates(league: str, team_id: str, today: datetime | None = None) -> list[str]:
    """Season-scoped roster URLs to try, most likely first.

    NBA seasons straddle two years (ending-year label in this repo, CLAUDE.md
    §4); WNBA is the year of play. Both orders end with the neighbouring years
    so a label convention we have not measured still finds the roster.
    """
    year = (today or datetime.now(timezone.utc)).year
    years = [year + 1, year, year - 1] if league == "nba" else [year, year + 1, year - 1]
    return [f"{CORE}/{league}/seasons/{y}/teams/{team_id}/athletes?limit=200" for y in years]


def _espn(url: str, budget: dict, *, athlete: bool = False) -> dict | None:
    """One ESPN GET, counted. Athlete docs and position $refs share the cap;
    a call past it is not made."""
    if athlete and budget["athlete_http"] >= MAX_ATHLETE_HTTP:
        budget["cap_hit"] = True
        return None
    if athlete:
        budget["athlete_http"] += 1
    budget["espn_calls"] += 1
    return _get_json(url)


def _athlete_room(budget: dict) -> bool:
    if budget["athlete_http"] >= MAX_ATHLETE_HTTP:
        budget["cap_hit"] = True
        return False
    return True


def _basketball(conn, sport: str, dry_run: bool) -> dict:
    league = LEAGUE_OF[sport]
    budget = {"espn_calls": 0, "athlete_http": 0, "cap_hit": False}
    teams = _refs(_espn(f"{CORE}/{league}/teams?limit=50", budget))
    index = _name_index(conn, sport)
    fresh = set() if dry_run else _fresh_source_ids(conn, sport)
    cached = set() if dry_run else _cached_unmatched_ids(conn, sport)
    stats = {"teams": len(teams), "athletes_listed": 0, "athletes_fetched": 0,
             "skipped_fresh": 0, "cached_unmatched": 0, "deferred_cap": 0,
             "unparsed": 0, "matched": 0, "unmatched": 0,
             "match_method": {}, "tiebreak_sample": [], "roster_season_used": {},
             "no_group": 0, "positions": {}, "sample": [], "unmatched_sample": []}
    out: list[dict] = []
    unmatched_ids: list[str] = []
    for tref in teams:
        tdoc = _espn(tref, budget) or {}
        team_abbrev = tdoc.get("abbreviation")
        m = _TEAM_ID.search(tref)
        if not m:
            continue
        roster: list[str] = []
        for url in roster_candidates(league, m.group(1)):
            roster = _refs(_espn(url, budget))
            if roster:
                used = url.split("/seasons/")[1].split("/")[0]
                stats["roster_season_used"][used] = stats["roster_season_used"].get(used, 0) + 1
                break
        for aref in roster:
            stats["athletes_listed"] += 1
            am = _ATHLETE_ID.search(aref)
            aid = am.group(1) if am else None
            # Skipped rows are not rewritten. The jittered window is what
            # keeps this cohort from expiring together; a touch of updated_at
            # would keep them fresh forever.
            if aid and aid in fresh:
                stats["skipped_fresh"] += 1
                continue
            if aid and aid in cached:
                stats["cached_unmatched"] += 1
                continue
            if not _athlete_room(budget):
                stats["deferred_cap"] += 1
                continue
            adoc = _espn(aref, budget, athlete=True)
            stats["athletes_fetched"] += 1
            pos_doc = None
            needs_ref = isinstance(adoc, dict) and isinstance(adoc.get("position"), dict) \
                and "$ref" in adoc["position"] and not adoc["position"].get("abbreviation")
            if needs_ref:
                # Leave the athlete unread rather than cache a guess. The
                # doc call is already spent; the next morning finishes it.
                if not _athlete_room(budget):
                    stats["deferred_cap"] += 1
                    continue
                pos_doc = _espn(adoc["position"]["$ref"], budget, athlete=True)
            a = parse_athlete(adoc, pos_doc)
            if not a:
                stats["unparsed"] += 1
                if len(stats["unmatched_sample"]) < SAMPLE and isinstance(adoc, dict):
                    stats["unmatched_sample"].append(
                        {"unparsed_keys": sorted(adoc.keys())[:20],
                         "position": adoc.get("position")})
                continue
            stats["positions"][a["position"]] = stats["positions"].get(a["position"], 0) + 1
            how: dict = {}
            pid = match_to_log(a["name"], team_abbrev, index, how)
            m_ = how.get("method", "none")
            stats["match_method"][m_] = stats["match_method"].get(m_, 0) + 1
            if m_ == "tiebreak_recent" and len(stats["tiebreak_sample"]) < SAMPLE:
                stats["tiebreak_sample"].append({"name": a["name"], "team": team_abbrev, "player_id": pid})
            if not pid:
                stats["unmatched"] += 1
                unmatched_ids.append(a["espn_id"])
                if len(stats["unmatched_sample"]) < SAMPLE:
                    stats["unmatched_sample"].append({"name": a["name"], "team": team_abbrev})
                continue
            grp = basketball_group(a["position"])
            if grp is None:
                stats["no_group"] += 1
            stats["matched"] += 1
            row = {"sport": sport, "player_id": pid, "player_name": a["name"],
                   "team": team_abbrev, "position": a["position"], "pos_group": grp,
                   "source": "espn_core", "source_athlete_id": a["espn_id"]}
            out.append(row)
            if len(stats["sample"]) < SAMPLE:
                stats["sample"].append(row)
    stats["written"] = 0 if dry_run else _upsert(conn, out)
    stats["unmatched_cached"] = 0 if dry_run else _remember_unmatched(conn, sport, unmatched_ids)
    stats["espn_calls"] = budget["espn_calls"]
    stats["athlete_http"] = budget["athlete_http"]
    stats["cap_hit"] = budget["cap_hit"]
    stats["log_players_last_2_seasons"] = sum(len(v) for v in index.values())
    logger.info(
        f"player positions {sport}: espn_calls={stats['espn_calls']} "
        f"athletes_fetched={stats['athletes_fetched']} "
        f"skipped_fresh={stats['skipped_fresh']} "
        f"cached_unmatched={stats['cached_unmatched']} "
        f"deferred_cap={stats['deferred_cap']} cap_hit={stats['cap_hit']}"
    )
    return stats


# ── NCAAF ────────────────────────────────────────────────────────────────────

#: Same buckets as the NFL card (add_position_vs_opponent_nfl.sql), so the two
#: football cards group alike. CFBD positions outside these get no group.
FOOTBALL_GROUP = {
    "QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE",
    "DE": "DL", "DT": "DL", "NT": "DL", "DL": "DL", "EDGE": "DL",
    "LB": "LB", "ILB": "LB", "OLB": "LB", "MLB": "LB",
    "CB": "DB", "S": "DB", "FS": "DB", "SS": "DB", "SAF": "DB", "DB": "DB",
}


def _ncaaf(conn, season: int, dry_run: bool) -> dict:
    from data.ingestors.cfbd_ingestor import _get
    rows = parse_cfbd_roster(_get("/roster", year=season))
    log_ids = {str(r[0]) for r in conn.execute(
        "SELECT DISTINCT player_id FROM ncaaf_player_game_log WHERE season = %s", (season,)
    ).fetchall()}
    stats = {"season": season, "roster_rows": len(rows), "log_players": len(log_ids),
             "matched": 0, "positions": {}, "sample": []}
    out = []
    for r in rows:
        stats["positions"][r["position"]] = stats["positions"].get(r["position"], 0) + 1
        if r["player_id"] not in log_ids:
            continue
        stats["matched"] += 1
        row = {"sport": "NCAAF", "player_id": r["player_id"], "player_name": r["name"],
               "team": r["team"], "position": r["position"],
               "pos_group": FOOTBALL_GROUP.get(r["position"]),
               "source": "cfbd_roster", "source_athlete_id": r["player_id"]}
        out.append(row)
        if len(stats["sample"]) < SAMPLE:
            stats["sample"].append(row)
    stats["log_players_with_position"] = stats["matched"]
    stats["written"] = 0 if dry_run else _upsert(conn, out)
    return stats


# ── entry point ──────────────────────────────────────────────────────────────

def ingest_player_positions(sports=None, season: int | None = None,
                            dry_run: bool = False,
                            run_date: str | None = None) -> dict:
    """Fetch and store positions. Returns a per-sport summary for the job card.

    `season` applies to NCAAF only (CFBD /roster is per year). When it is
    omitted, the season is the fall year of `run_date` (January–July → the
    previous year), not the calendar year. Basketball reads ESPN's current
    rosters.
    """
    from data.db import get_connection
    sports = [s.upper() for s in (sports or SPORTS)]
    run_date = run_date or datetime.now(timezone.utc).date().isoformat()
    if season is None:
        season = ncaaf_roster_season(run_date)
    conn = get_connection()
    summary: dict = {"dry_run": dry_run}
    if not dry_run and conn.execute(
            "SELECT to_regclass('public.player_positions')").fetchone()[0] is None:
        conn.close()
        # Raised, not reported: a job that "succeeds" with a per-sport error
        # inside is never retried, and the table lands on the next refresh
        # pass (add_player_positions.sql), so a retry is what fixes it.
        raise RuntimeError("player_positions does not exist yet (migration pending)")
    try:
        for sport in sports:
            try:
                if sport in LEAGUE_OF:
                    summary[sport] = _basketball(conn, sport, dry_run)
                elif sport == "NCAAF":
                    summary[sport] = _ncaaf(conn, season, dry_run)
            except Exception as exc:                          # noqa: BLE001
                logger.exception(f"player positions {sport} failed")
                summary[sport] = {"error": str(exc)[:300]}
    finally:
        conn.close()
    logger.info(f"player positions: {summary}")
    return summary
