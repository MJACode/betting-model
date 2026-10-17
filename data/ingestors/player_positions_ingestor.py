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

POLITENESS. ESPN has IP-blocked the worker twice. The roster LIST is ~45
requests a pass; athlete docs are fetched only for athletes not already stored
in the last REFRESH_DAYS, so a steady-state pass is the 45 list calls plus
whatever signed that week.

Everything lands in Supabase table `player_positions` (CLAUDE.md §1b).
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone

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

#: An athlete stored this recently is not re-fetched.
REFRESH_DAYS = 7
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


def _fresh_source_ids(conn, sport: str) -> set[str]:
    rows = conn.execute("""
        SELECT source_athlete_id FROM player_positions
        WHERE sport = %s AND updated_at > now() - make_interval(days => %s)
    """, (sport, REFRESH_DAYS)).fetchall()
    return {str(r[0]) for r in rows if r[0]}


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


def _basketball(conn, sport: str, dry_run: bool) -> dict:
    league = LEAGUE_OF[sport]
    teams = _refs(_get_json(f"{CORE}/{league}/teams?limit=50"))
    index = _name_index(conn, sport)
    fresh = set() if dry_run else _fresh_source_ids(conn, sport)
    stats = {"teams": len(teams), "athletes_listed": 0, "athletes_fetched": 0,
             "skipped_fresh": 0, "unparsed": 0, "matched": 0, "unmatched": 0,
             "match_method": {}, "tiebreak_sample": [], "roster_season_used": {},
             "no_group": 0, "positions": {}, "sample": [], "unmatched_sample": []}
    out: list[dict] = []
    for tref in teams:
        tdoc = _get_json(tref) or {}
        team_abbrev = tdoc.get("abbreviation")
        m = _TEAM_ID.search(tref)
        if not m:
            continue
        roster: list[str] = []
        for url in roster_candidates(league, m.group(1)):
            roster = _refs(_get_json(url))
            if roster:
                used = url.split("/seasons/")[1].split("/")[0]
                stats["roster_season_used"][used] = stats["roster_season_used"].get(used, 0) + 1
                break
        for aref in roster:
            stats["athletes_listed"] += 1
            am = _ATHLETE_ID.search(aref)
            if am and am.group(1) in fresh:
                stats["skipped_fresh"] += 1
                continue
            adoc = _get_json(aref)
            stats["athletes_fetched"] += 1
            pos_doc = None
            if isinstance(adoc, dict) and isinstance(adoc.get("position"), dict) \
                    and "$ref" in adoc["position"] and not adoc["position"].get("abbreviation"):
                pos_doc = _get_json(adoc["position"]["$ref"])
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
    stats["log_players_last_2_seasons"] = sum(len(v) for v in index.values())
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
                            dry_run: bool = False) -> dict:
    """Fetch and store positions. Returns a per-sport summary for the job card.

    `season` applies to NCAAF only (CFBD /roster is per year); basketball reads
    ESPN's current rosters.
    """
    from data.db import get_connection
    sports = [s.upper() for s in (sports or SPORTS)]
    season = season or datetime.now().year
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
