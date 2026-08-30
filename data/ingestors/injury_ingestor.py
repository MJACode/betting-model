"""
injury_ingestor.py — Daily injury report fetcher.

Sources (in priority order):
  1. ESPN Hidden API  — near real-time, covers MLB, NHL, and WNBA
  2. MLB Stats API    — transactions endpoint (MLB only, backup)

Run daily at ~07:00 AM before odds/stats pulls.
Usage:
    python -m data.ingestors.injury_ingestor           # all sports
    python -m data.ingestors.injury_ingestor --sport MLB
    python -m data.ingestors.injury_ingestor --sport NHL
    python -m data.ingestors.injury_ingestor --sport WNBA
"""

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import sqlite3
import time
from datetime import date, datetime, timedelta
from pathlib import Path
import sys

import requests
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import (
    ESPN_INJURY_URLS,
    ESPN_MLB_TEAM_IDS,
    ESPN_NHL_TEAM_IDS,
    ESPN_WNBA_TEAM_IDS,
    ESPN_NBA_TEAM_IDS,
    RETURN_RAMP,
    SPORTS,
    WNBA_ODDS_API_MAP,
    NBA_ODDS_API_MAP,
)
from data.db import get_connection, DBConnection

# ── Constants ─────────────────────────────────────────────────────────────────

ESPN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

MLB_TRANSACTIONS_URL = (
    "https://statsapi.mlb.com/api/v1/transactions"
    "?sportId=1&limit=500&date={date}"
)

# ESPN injury status → our canonical status
# Keys cover both old title-case format and new lowercase/hyphenated format
ESPN_STATUS_MAP = {
    # Old format (title-case)
    "Out":           "Out",
    "Day-To-Day":    "Day-To-Day",
    "Questionable":  "Questionable",
    "Probable":      "Questionable",   # treat Probable as Questionable
    "Doubtful":      "Day-To-Day",
    "10-Day IL":     "IL10",
    "15-Day IL":     "IL15",
    "60-Day IL":     "IL60",
    "7-Day IL":      "IL10",           # MLB 7-day (minors) → treat as IL10
    # New format (lowercase / hyphenated, from type.description)
    "out":           "Out",
    "day-to-day":    "Day-To-Day",
    "questionable":  "Questionable",
    "probable":      "Questionable",
    "doubtful":      "Day-To-Day",
    "10-day IL":     "IL10",
    "15-day IL":     "IL15",
    "60-day IL":     "IL60",
    "7-day IL":      "IL10",
    "Paternity":     "Day-To-Day",     # paternity leave — short absence
    "paternity":     "Day-To-Day",
    # Basketball (WNBA) statuses
    "Game Time Decision": "Questionable",
    "game time decision": "Questionable",
    "Available":     "Questionable",   # listed but expected to play
    "available":     "Questionable",
    "Suspension":    "Out",
    "suspension":    "Out",
}

# Severity weights per status (used in feature engineering)
SEVERITY_WEIGHTS = {
    "IL60":       1.0,
    "IL15":       0.9,
    "IL10":       0.8,
    "Out":        0.7,
    "Day-To-Day": 0.7,
    "Questionable": 0.5,
}

# ── ESPN Helpers ──────────────────────────────────────────────────────────────

ESPN_WNBA_TEAMS_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/teams"
)
ESPN_NBA_TEAMS_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"
)
# sports.core.api.espn.com fallback for the WNBA teams list — the ESPN host
# that kept serving the worker through the 2026-08-05 site.api IP block
# (wnba_results_ingestor precedent). Core listings are $ref collections.
CORE_WNBA_TEAMS_URL = (
    "https://sports.core.api.espn.com/v2/sports/basketball/leagues/wnba/teams"
    "?limit=50"
)


def _normalize_team_name(name: str) -> str:
    """Lowercase, collapse whitespace — for matching ESPN names to our maps."""
    return " ".join((name or "").lower().split())


# Full-name → our 3-letter abbrev, built from the odds-API map (covers all 15
# franchises incl. expansion teams). Used to join ESPN's team list to our abbrevs
# without hardcoding ESPN's numeric ids or its abbreviation scheme.
_WNBA_NAME_TO_ABBREV = {
    _normalize_team_name(full): abbrev for full, abbrev in WNBA_ODDS_API_MAP.items()
}
_NBA_NAME_TO_ABBREV = {
    _normalize_team_name(full): abbrev for full, abbrev in NBA_ODDS_API_MAP.items()
}


def _wnba_espn_team_to_abbrev(team: dict) -> str | None:
    """Resolve one ESPN WNBA team object to our 3-letter abbrev via its name."""
    candidates = [
        team.get("displayName"),
        f"{team.get('location', '')} {team.get('name', '')}".strip(),
        team.get("shortDisplayName"),
        team.get("name"),
    ]
    for cand in candidates:
        abbrev = _WNBA_NAME_TO_ABBREV.get(_normalize_team_name(cand))
        if abbrev:
            return abbrev
    return None


def _fetch_wnba_espn_team_ids() -> dict:
    """
    Resolve {our_abbrev: espn_numeric_id} live from ESPN's WNBA teams list.
    Joins on full team name (via WNBA_ODDS_API_MAP) so expansion teams resolve
    automatically with no hardcoded ids. Returns {} on any failure — the caller
    falls back to the static config map (ESPN_WNBA_TEAM_IDS).
    """
    try:
        resp = requests.get(ESPN_WNBA_TEAMS_URL, headers=ESPN_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, json.JSONDecodeError) as exc:
        logger.warning(f"ESPN WNBA teams list fetch failed ({exc}); "
                       f"using static ESPN_WNBA_TEAM_IDS")
        return {}

    try:
        teams = data["sports"][0]["leagues"][0]["teams"]
    except (KeyError, IndexError, TypeError):
        logger.warning("ESPN WNBA teams list had unexpected shape; "
                       "using static ESPN_WNBA_TEAM_IDS")
        return {}

    resolved: dict = {}
    for entry in teams:
        team = entry.get("team", {}) if isinstance(entry, dict) else {}
        espn_id = team.get("id")
        abbrev  = _wnba_espn_team_to_abbrev(team)
        if espn_id and abbrev:
            try:
                resolved[abbrev] = int(espn_id)
            except (TypeError, ValueError):
                continue

    if resolved:
        logger.info(f"ESPN WNBA: resolved {len(resolved)} team ids dynamically")
    return resolved


def _fetch_wnba_espn_team_ids_core(fetch=None) -> dict:
    """
    Resolve {our_abbrev: espn_numeric_id} from the sports.core.api.espn.com
    WNBA teams collection. Fallback for when site.api is blocked (as it has
    been for the worker since 2026-08-05): without it the 3 expansion teams
    (GSV/PDX/TOR) drop out of injury coverage, because the static
    ESPN_WNBA_TEAM_IDS map only carries the 12 legacy franchises.

    Core team docs carry the same name fields the site API does
    (displayName/location/name/shortDisplayName), so the name-join reuses
    _wnba_espn_team_to_abbrev. Returns {} on any failure.

    `fetch` is injectable for tests; the default GET forces https on http://
    $refs and paces calls (wnba_results_ingestor conventions).
    """
    def _get(url: str) -> dict:
        resp = requests.get(url, headers=ESPN_HEADERS, timeout=10)
        resp.raise_for_status()
        time.sleep(0.1)
        return resp.json()

    fetch = fetch or _get

    try:
        listing = fetch(CORE_WNBA_TEAMS_URL)
    except Exception as exc:
        logger.warning(f"ESPN core WNBA teams list fetch failed ({exc}); "
                       f"using static ESPN_WNBA_TEAM_IDS")
        return {}

    resolved: dict = {}
    for item in (listing or {}).get("items", []) or []:
        ref = item.get("$ref") if isinstance(item, dict) else (
            item if isinstance(item, str) else None)
        if not ref:
            continue
        # Core $refs are emitted as http:// — force https so the worker's
        # egress never downgrades (wnba_results_ingestor convention).
        if ref.startswith("http://"):
            ref = "https://" + ref[len("http://"):]
        try:
            team = fetch(ref) or {}
        except Exception:
            continue  # one bad team doc must not sink the rest
        espn_id = team.get("id")
        abbrev  = _wnba_espn_team_to_abbrev(team)
        if espn_id and abbrev:
            try:
                resolved[abbrev] = int(espn_id)
            except (TypeError, ValueError):
                continue

    if resolved:
        logger.info(f"ESPN core WNBA: resolved {len(resolved)} team ids "
                    f"(site.api fallback)")
    return resolved


def _nba_espn_team_to_abbrev(team: dict) -> str | None:
    """Resolve one ESPN NBA team object to our 3-letter abbrev via its name."""
    candidates = [
        team.get("displayName"),
        f"{team.get('location', '')} {team.get('name', '')}".strip(),
        team.get("shortDisplayName"),
        team.get("name"),
    ]
    for cand in candidates:
        abbrev = _NBA_NAME_TO_ABBREV.get(_normalize_team_name(cand))
        if abbrev:
            return abbrev
    return None


def _fetch_nba_espn_team_ids() -> dict:
    """
    Resolve {our_abbrev: espn_numeric_id} live from ESPN's NBA teams list.
    The 30 NBA franchises are stable, so this is a self-heal overlay on the
    static ESPN_NBA_TEAM_IDS map (which is authoritative). Returns {} on failure.
    """
    try:
        resp = requests.get(ESPN_NBA_TEAMS_URL, headers=ESPN_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, json.JSONDecodeError) as exc:
        logger.warning(f"ESPN NBA teams list fetch failed ({exc}); "
                       f"using static ESPN_NBA_TEAM_IDS")
        return {}

    try:
        teams = data["sports"][0]["leagues"][0]["teams"]
    except (KeyError, IndexError, TypeError):
        logger.warning("ESPN NBA teams list had unexpected shape; "
                       "using static ESPN_NBA_TEAM_IDS")
        return {}

    resolved: dict = {}
    for entry in teams:
        team = entry.get("team", {}) if isinstance(entry, dict) else {}
        espn_id = team.get("id")
        abbrev  = _nba_espn_team_to_abbrev(team)
        if espn_id and abbrev:
            try:
                resolved[abbrev] = int(espn_id)
            except (TypeError, ValueError):
                continue

    if resolved:
        logger.info(f"ESPN NBA: resolved {len(resolved)} team ids dynamically")
    return resolved


def _espn_team_ids(sport: str) -> dict:
    if sport == "MLB":
        return ESPN_MLB_TEAM_IDS
    if sport == "NHL":
        return ESPN_NHL_TEAM_IDS
    if sport == "WNBA":
        # Static map is the offline fallback; live ESPN ids (incl. expansion
        # teams) override it when a teams endpoint is reachable. site.api is
        # tried first (cheapest, may recover); ANY site failure falls through
        # to the sports.core host, which survived the 2026-08-05 IP block.
        ids = dict(ESPN_WNBA_TEAM_IDS)
        ids.update(_fetch_wnba_espn_team_ids() or _fetch_wnba_espn_team_ids_core())
        return ids
    if sport == "NBA":
        # Static map is authoritative (NBA franchises are stable); live ids
        # overlay it as a self-heal when the teams endpoint is reachable.
        ids = dict(ESPN_NBA_TEAM_IDS)
        ids.update(_fetch_nba_espn_team_ids())
        return ids
    return {}


# ── Athlete-name cache ───────────────────────────────────────────────────────
# ESPN's core API is a graph of $ref links, so ONE team's injury list costs
# 1 + 2N requests: the list, then a detail fetch per injury, then an athlete
# fetch per injury just to turn an id into a display name. Measured on the
# 2026-08-30 16:17 pass that was 1,569 requests taking 98 of the step's 104
# seconds -- and injuries-refresh alone therefore set the floor for the entire
# parallel ingest group, which finished everything else in under 46s.
#
# Roughly two thirds of those calls asked the same question every hour: what is
# athlete 12345 called. A display name does not change. So the cheapest fix is
# not to make the calls faster but to stop making them, and the answers are
# already sitting in our own `injuries` table from previous runs.
#
# This matters more than raw speed: ESPN has IP-blocked this worker TWICE
# (CLAUDE.md §7), so removing requests is strictly safer than issuing the same
# number of them concurrently.
_ATHLETE_NAME_CACHE: dict[str, str] = {}


def _seed_athlete_cache(conn=None) -> int:
    """Warm the name cache from injuries we have already stored.

    Best-effort: a cold cache costs the old number of requests, never a wrong
    name. Returns how many names were loaded, for the log line."""
    global _ATHLETE_NAME_CACHE
    if _ATHLETE_NAME_CACHE:
        return len(_ATHLETE_NAME_CACHE)
    try:
        own = conn is None
        if own:
            from data.db import get_connection
            conn = get_connection()
        try:
            rows = conn.execute("""
                SELECT DISTINCT ON (player_id) player_id, player_name
                FROM injuries
                WHERE player_id IS NOT NULL AND player_id <> ''
                  AND player_name IS NOT NULL AND player_name <> 'Unknown'
                ORDER BY player_id, created_at DESC
            """).fetchall()
        finally:
            if own:
                conn.close()
        _ATHLETE_NAME_CACHE = {str(r[0]): r[1] for r in rows}
    except Exception as exc:                                  # noqa: BLE001
        logger.debug(f"athlete-name cache seed skipped ({exc})")
        _ATHLETE_NAME_CACHE = {}
    return len(_ATHLETE_NAME_CACHE)


def _athlete_name(athlete_id: str, ref_url: str) -> str:
    """Display name for an athlete, from cache when we have seen them before."""
    if athlete_id and athlete_id in _ATHLETE_NAME_CACHE:
        return _ATHLETE_NAME_CACHE[athlete_id]
    try:
        resp = requests.get(ref_url, headers=ESPN_HEADERS, timeout=10)
        if resp.status_code == 200:
            name = resp.json().get("displayName", "Unknown")
            if athlete_id and name != "Unknown":
                _ATHLETE_NAME_CACHE[athlete_id] = name
            return name
    except Exception:                                         # noqa: BLE001
        pass
    return "Unknown"


def _fetch_espn_team_injuries(sport: str, team_abbrev: str, team_id: int) -> list[dict]:
    """
    Hit the ESPN hidden API for one team. Returns a list of raw injury dicts.
    Each dict has: player_name, player_id, status, injury_type.
    """
    url = ESPN_INJURY_URLS[sport].format(team_id=team_id)
    try:
        resp = requests.get(url, headers=ESPN_HEADERS, timeout=10)
        if resp.status_code == 404:
            # Team has no injuries listed — perfectly normal
            return []
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.warning(f"ESPN {sport} {team_abbrev} request failed: {exc}")
        return []
    except json.JSONDecodeError:
        logger.warning(f"ESPN {sport} {team_abbrev} returned non-JSON response")
        return []

    items = data.get("items", [])
    injuries = []
    for item in items:
        # ESPN returns either {"$ref": "url"} objects or raw URL strings
        if isinstance(item, str):
            ref_url = item
        else:
            ref_url = item.get("$ref", "")
        if not ref_url:
            continue
        try:
            ref_resp = requests.get(ref_url, headers=ESPN_HEADERS, timeout=10)
            ref_resp.raise_for_status()
            injury_data = ref_resp.json()
        except requests.RequestException:
            continue
        except json.JSONDecodeError:
            continue

        # ── Player identification ─────────────────────────────────────────────
        # New format: athlete is {"$ref": "url"} — follow it for name/id.
        # Old format: athlete was {"displayName": "...", "id": 12345}.
        player_name = "Unknown"
        player_id   = ""
        athlete_field = injury_data.get("athlete", {})
        if isinstance(athlete_field, dict):
            if "displayName" in athlete_field:
                # Old format — direct fields present
                player_name = athlete_field.get("displayName", "Unknown")
                player_id   = str(athlete_field.get("id", ""))
            elif "$ref" in athlete_field:
                # New format — extract ID from URL, follow for display name
                m = re.search(r"/athletes/(\d+)", athlete_field["$ref"])
                if m:
                    player_id = m.group(1)
                # Cached where we have seen this athlete before -- a display
                # name does not change, and this was two thirds of the step's
                # 1,569 requests.
                player_name = _athlete_name(player_id, athlete_field["$ref"])

        # ── Status parsing ────────────────────────────────────────────────────
        # New format: status is a plain string ("15-Day-IL").
        # Old format: status was {"type": {"description": "15-Day IL"}}.
        # type.description (when present) gives the canonical label for mapping.
        type_obj     = injury_data.get("type", {})
        status_field = injury_data.get("status", {})
        if isinstance(type_obj, dict) and type_obj.get("description"):
            raw_status  = type_obj["description"]
            injury_type = type_obj["description"]
        elif isinstance(status_field, str):
            raw_status  = status_field
            injury_type = status_field
        else:
            raw_status  = status_field.get("type", {}).get("description", "Unknown") if isinstance(status_field, dict) else "Unknown"
            injury_type = raw_status

        comment = injury_data.get("longComment", "")

        injuries.append({
            "player_name": player_name,
            "player_id":   player_id,
            "raw_status":  raw_status,
            "injury_type": injury_type or comment or "Unknown",
        })

    return injuries


def fetch_espn_injuries(sport: str, report_date: str) -> list[dict]:
    """
    Pull all injuries for all teams in the given sport from ESPN.
    Returns a list of normalized injury dicts ready for DB insert.
    """
    team_ids = _espn_team_ids(sport)
    all_injuries = []

    seeded = _seed_athlete_cache()
    if seeded:
        logger.debug(f"injury cache: {seeded} athlete name(s) known")

    # One team's fetch is independent of every other team's, and all of it is
    # waiting on a socket. Serially this was ~30 teams x (1 + 2N) requests.
    #
    # SIX workers, not sixty. ESPN has IP-blocked this worker twice (CLAUDE.md
    # §7) and WNBA settlement was dead for two weeks as a result, so the goal
    # is to stop wasting wall clock -- not to hammer a host that has already
    # objected. Combined with the name cache the request COUNT falls by roughly
    # two thirds, so this issues far fewer requests than the old serial code
    # even while issuing them six at a time.
    results: dict = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_fetch_espn_team_injuries, sport, ab, tid): ab
                   for ab, tid in team_ids.items()}
        for fut in as_completed(futures):
            ab = futures[fut]
            try:
                results[ab] = fut.result()
            except Exception as exc:                          # noqa: BLE001
                # One team failing must never lose the other 29 -- the same
                # rule the refresh pass itself lives by.
                logger.warning(f"ESPN {sport} {ab} injuries failed: {exc}")
                results[ab] = []

    # Iterate the TEAM IDS, not the completion order, so the output row order
    # is identical to the serial version. A diff in row order is not a bug, but
    # it makes every future comparison against a stored run noisy for nothing.
    for abbrev in team_ids:
        raw_list = results.get(abbrev, [])
        for raw in raw_list:
            canonical_status = ESPN_STATUS_MAP.get(raw["raw_status"], "Out")
            severity         = SEVERITY_WEIGHTS.get(canonical_status, 0.7)

            all_injuries.append({
                "sport":            sport,
                "team":             abbrev,
                "player_name":      raw["player_name"],
                "player_id":        raw["player_id"],
                "status":           canonical_status,
                "injury_type":      raw["injury_type"],
                "scenario":         "A",        # active injury; B computed later
                "severity_weight":  severity,
                "return_ramp_factor": None,
                "games_since_return": None,
                "activation_date":  None,
                "report_date":      report_date,
            })

    logger.info(f"ESPN {sport}: fetched {len(all_injuries)} injuries "
                f"across {len(team_ids)} teams")
    return all_injuries


# ── MLB Stats API Transactions (backup) ──────────────────────────────────────

# MLB transaction type codes that indicate IL placement
MLB_IL_TYPES = {
    "IL",         # generic
    "DL",         # old name for IL
    "RESTRICTED", # restricted list
}

# Reverse-map: full team name → our 3-letter abbrev
MLB_TEAM_NAME_TO_ABBREV = {
    "Arizona Diamondbacks": "ARI", "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL",    "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC",         "Chicago White Sox": "CWS",
    "Cincinnati Reds": "CIN",      "Cleveland Guardians": "CLE",
    "Cleveland Indians": "CLE",    "Colorado Rockies": "COL",
    "Detroit Tigers": "DET",       "Houston Astros": "HOU",
    "Kansas City Royals": "KC",    "Los Angeles Angels": "LAA",
    "Los Angeles Dodgers": "LAD",  "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL",    "Minnesota Twins": "MIN",
    "New York Mets": "NYM",        "New York Yankees": "NYY",
    "Oakland Athletics": "OAK",    "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT",   "San Diego Padres": "SD",
    "San Francisco Giants": "SF",  "Seattle Mariners": "SEA",
    "St. Louis Cardinals": "STL",  "Tampa Bay Rays": "TB",
    "Texas Rangers": "TEX",        "Toronto Blue Jays": "TOR",
    "Washington Nationals": "WSH",
}


def fetch_mlb_transactions(report_date: str) -> list[dict]:
    """
    Pull MLB transactions for the given date. Extracts IL placements.
    Returns normalized injury dicts (scenario='A' only).
    Used as a backup/supplement to ESPN.
    """
    url = MLB_TRANSACTIONS_URL.format(date=report_date)
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.warning(f"MLB Stats API transactions failed: {exc}")
        return []
    except json.JSONDecodeError:
        logger.warning("MLB Stats API transactions returned non-JSON")
        return []

    transactions = data.get("transactions", [])
    injuries = []

    for tx in transactions:
        type_code = tx.get("typeCode", "")
        if type_code not in MLB_IL_TYPES:
            continue

        player     = tx.get("person", {})
        player_name = player.get("fullName", "Unknown")
        player_id   = str(player.get("id", ""))

        team_data  = tx.get("toTeam", tx.get("fromTeam", {}))
        team_name  = team_data.get("name", "")
        team_abbrev = MLB_TEAM_NAME_TO_ABBREV.get(team_name, "")
        if not team_abbrev:
            continue  # skip minor league / unknown teams

        description = tx.get("description", "")

        # Infer IL duration from description string
        if "60-day" in description.lower():
            status = "IL60"
        elif "15-day" in description.lower():
            status = "IL15"
        elif "10-day" in description.lower():
            status = "IL10"
        else:
            status = "IL10"  # default

        severity = SEVERITY_WEIGHTS.get(status, 0.8)

        injuries.append({
            "sport":              "MLB",
            "team":               team_abbrev,
            "player_name":        player_name,
            "player_id":          player_id,
            "status":             status,
            "injury_type":        description[:200],
            "scenario":           "A",
            "severity_weight":    severity,
            "return_ramp_factor": None,
            "games_since_return": None,
            "activation_date":    None,
            "report_date":        report_date,
        })

    logger.info(f"MLB Stats API transactions: {len(injuries)} IL placements")
    return injuries


# ── Return-from-Injury Ramp (Scenario B) ──────────────────────────────────────

def _compute_return_ramp(games_since_return: int) -> float:
    """Quarter-ramp factor for players recently back from IL."""
    if games_since_return <= 2:
        return RETURN_RAMP["early"]   # 0.70
    elif games_since_return <= 5:
        return RETURN_RAMP["mid"]     # 0.85
    else:
        return RETURN_RAMP["full"]    # 1.00


def fetch_return_ramp_players(conn: sqlite3.Connection, sport: str,
                               report_date: str) -> list[dict]:
    """
    Query the injuries table for players who were on IL and have since been
    activated (scenario='A', activation_date IS NOT NULL).
    Build scenario='B' rows with return_ramp_factor populated.

    We look back 30 days for activation dates, then count how many games
    each team has played since that date to get games_since_return.
    """
    cutoff = (datetime.strptime(report_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    rows = conn.execute("""
        SELECT DISTINCT player_name, player_id, team, activation_date
        FROM injuries
        WHERE sport = ?
          AND scenario = 'A'
          AND activation_date IS NOT NULL
          AND activation_date >= ?
          AND activation_date < ?
    """, (sport, cutoff, report_date)).fetchall()

    ramp_injuries = []
    for player_name, player_id, team, activation_date in rows:
        # Count team games since activation
        games_since = conn.execute("""
            SELECT COUNT(*)
            FROM games
            WHERE sport = ?
              AND (home_team = ? OR away_team = ?)
              AND game_date > ?
              AND game_date <= ?
              AND home_score IS NOT NULL
        """, (sport, team, team, activation_date, report_date)).fetchone()[0]

        if games_since > 6:
            # Fully integrated — no longer on ramp
            continue

        ramp_factor = _compute_return_ramp(games_since)

        ramp_injuries.append({
            "sport":               sport,
            "team":                team,
            "player_name":         player_name,
            "player_id":           player_id,
            "status":              "Returning",
            "injury_type":         "Return from IL",
            "scenario":            "B",
            "severity_weight":     1.0 - ramp_factor,  # 0.30 / 0.15 / 0.00
            "return_ramp_factor":  ramp_factor,
            "games_since_return":  games_since,
            "activation_date":     activation_date,
            "report_date":         report_date,
        })

    logger.info(f"{sport}: {len(ramp_injuries)} players on return ramp (scenario B)")
    return ramp_injuries


# ── Database Upsert ──────────────────────────────────────────────────────────

def _upsert_injuries(conn: DBConnection, injuries: list[dict]) -> int:
    """
    Insert injury rows. We insert fresh rows each day (append-only log).
    Deduplication done at query time by using the most recent report_date.
    Returns number of rows inserted.
    """
    if not injuries:
        return 0

    sql = """
        INSERT INTO injuries (
            sport, team, player_name, player_id, status, injury_type,
            scenario, severity_weight, return_ramp_factor,
            games_since_return, activation_date, report_date
        ) VALUES (
            %(sport)s, %(team)s, %(player_name)s, %(player_id)s, %(status)s, %(injury_type)s,
            %(scenario)s, %(severity_weight)s, %(return_ramp_factor)s,
            %(games_since_return)s, %(activation_date)s, %(report_date)s
        )
    """
    conn.executemany(sql, injuries)
    return len(injuries)


def _log_pipeline(conn: DBConnection, run_date: str,
                  status: str, records_in: int, records_out: int,
                  duration_s: float, error_msg: str = None):
    conn.execute("""
        INSERT INTO pipeline_log (run_date, step, status, records_in, records_out, duration_s, error_msg)
        VALUES (%s, 'injury', %s, %s, %s, %s, %s)
    """, (run_date, status, records_in, records_out, duration_s, error_msg))


# ── Main Entry Point ──────────────────────────────────────────────────────────

def run_injury_ingestor(sport: str = None, report_date: str = None) -> dict:
    """
    Full injury pull for a given date. Returns summary dict.

    Args:
        sport:       'MLB', 'NHL', or None (runs both)
        report_date: ISO date string; defaults to today
    """
    if report_date is None:
        report_date = date.today().isoformat()

    sports = [sport] if sport else ["MLB", "NHL", "WNBA", "NBA"]
    start  = datetime.now()
    total_inserted = 0

    conn = get_connection()

    try:
        for sp in sports:
            sp_start = datetime.now()
            all_injuries = []

            # ── Source 1: ESPN ────────────────────────────────────────────────
            try:
                espn_rows = fetch_espn_injuries(sp, report_date)
                all_injuries.extend(espn_rows)
            except Exception as exc:
                logger.error(f"ESPN {sp} ingestion error: {exc}")

            # ── Source 2: MLB Stats API transactions (MLB only) ───────────────
            if sp == "MLB":
                try:
                    tx_rows = fetch_mlb_transactions(report_date)
                    # Merge: add only players ESPN missed
                    espn_player_ids = {r["player_id"] for r in all_injuries if r.get("player_id")}
                    new_tx = [r for r in tx_rows if r.get("player_id") not in espn_player_ids]
                    all_injuries.extend(new_tx)
                    if new_tx:
                        logger.info(f"MLB: added {len(new_tx)} players from Stats API "
                                    f"not found in ESPN")
                except Exception as exc:
                    logger.error(f"MLB Stats API transactions error: {exc}")

            # ── Scenario B: return ramp ───────────────────────────────────────
            try:
                ramp_rows = fetch_return_ramp_players(conn, sp, report_date)
                all_injuries.extend(ramp_rows)
            except Exception as exc:
                logger.error(f"{sp} return ramp computation error: {exc}")

            # ── Insert ────────────────────────────────────────────────────────
            n = _upsert_injuries(conn, all_injuries)
            total_inserted += n

            duration = (datetime.now() - sp_start).total_seconds()
            _log_pipeline(conn, report_date, "success",
                          records_in=n, records_out=n, duration_s=duration)
            logger.success(f"{sp} injuries: {n} rows inserted ({duration:.1f}s)")

        conn.commit()

    except Exception as exc:
        conn.rollback()
        total_duration = (datetime.now() - start).total_seconds()
        _log_pipeline(conn, report_date, "error", 0, 0, total_duration, str(exc))
        conn.commit()
        logger.error(f"Injury ingestor failed: {exc}")
        raise
    finally:
        conn.close()

    return {
        "report_date":    report_date,
        "sports":         sports,
        "rows_inserted":  total_inserted,
        "duration_s":     (datetime.now() - start).total_seconds(),
    }


def query_injuries_for_game(conn: sqlite3.Connection,
                             sport: str,
                             home_team: str,
                             away_team: str,
                             game_date: str) -> dict:
    """
    Helper used by feature engine to pull injury context for a specific game.
    Returns dict with keys: home_injuries, away_injuries (list of injury rows).
    Pulls the most recent injury report on or before game_date.
    """
    latest_date = conn.execute("""
        SELECT MAX(report_date)
        FROM injuries
        WHERE sport = ?
          AND report_date <= ?
    """, (sport, game_date)).fetchone()[0]

    if not latest_date:
        return {"home_injuries": [], "away_injuries": []}

    def _get_team_injuries(team: str) -> list[dict]:
        rows = conn.execute("""
            SELECT player_name, player_id, status, injury_type,
                   scenario, severity_weight, return_ramp_factor,
                   games_since_return, activation_date
            FROM injuries
            WHERE sport = ?
              AND team = ?
              AND report_date = ?
            ORDER BY severity_weight DESC
        """, (sport, team, latest_date)).fetchall()

        cols = ["player_name", "player_id", "status", "injury_type",
                "scenario", "severity_weight", "return_ramp_factor",
                "games_since_return", "activation_date"]
        return [dict(zip(cols, r)) for r in rows]

    return {
        "home_injuries": _get_team_injuries(home_team),
        "away_injuries": _get_team_injuries(away_team),
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run injury ingestor")
    parser.add_argument("--sport", choices=["MLB", "NHL", "WNBA", "NBA"],
                        help="Sport to ingest (default: all)")
    parser.add_argument("--date", dest="report_date",
                        help="Report date YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    result = run_injury_ingestor(sport=args.sport, report_date=args.report_date)
    logger.info(f"Done: {result}")
