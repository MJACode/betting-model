"""ESPN core probable starters — NHL starting goalie (and the same shape for MLB).

Measured 2026-09-14 against sports.core.api.espn.com (site.api 403s from this
sandbox, same host the worker lost on 2026-08-05):

* `/v2/sports/hockey/leagues/nhl/events?dates=20260919` → 200, 7 events.
* Each competitor carries `probables` with `name=probableStartingGoalie`,
  an athlete `$ref`, and `status.type` (`expected` on the sample).
* NHL's own `/v1/schedule/now` homeTeam/awayTeam has **no** `probableGoalie`
  (43 games, 0 populated). `nhl_stats_ingestor._build_goalie_rows` already
  looked for that field and always fell through to the season leader.

This module is the overlay: resolve tonight's named goalie from ESPN core
and hand it to the daily NHL stats write so `nhl_goalie_stats` is the
confirmed (or expected) starter, not last year's #1. The game-model gate
then matches that name against `injuries` with the same clock as the NFL
prop veto.

Fail open: any network/shape error returns {}. The caller keeps the NHL-API
season-leader fallback.
"""
from __future__ import annotations

import time

import requests
from loguru import logger

from data.ingestors.injury_ingestor import ESPN_HEADERS
from data.ingestors.odds_ingestor import NHL_ODDS_API_MAP

CORE_NHL_EVENTS_URL = (
    "https://sports.core.api.espn.com/v2/sports/hockey/leagues/nhl/events"
    "?dates={dates}&limit=50"
)

# ESPN hockey abbreviations that are not our ids (NHL_API_ABBREV_MAP twins).
_ESPN_ABBREV_TO_OURS = {
    "LA": "LAK", "TB": "TBL", "SJ": "SJS", "NJ": "NJD",
}

_NHL_NAME_TO_ABBREV = {
    " ".join((name or "").lower().split()): abbrev
    for name, abbrev in NHL_ODDS_API_MAP.items()
}

PROBABLE_GOALIE = "probablestartinggoalie"


def _https(url: str) -> str:
    if url.startswith("http://"):
        return "https://" + url[len("http://"):]
    return url


def _default_fetch(url: str) -> dict:
    resp = requests.get(_https(url), headers=ESPN_HEADERS, timeout=10)
    resp.raise_for_status()
    time.sleep(0.1)
    return resp.json()


def _team_abbrev(team: dict) -> str | None:
    """Join ESPN's team doc to our abbrev. displayName first (Utah Mammoth /
    LA Kings); abbreviation is a fallback after the LA→LAK remap.

    Do NOT use config.ESPN_NHL_TEAM_IDS: that map collides (ANA and DAL
    both 25; BOS and NJD both 1) and would attach the wrong franchise.
    """
    candidates = [
        team.get("displayName"),
        f"{team.get('location', '')} {team.get('name', '')}".strip(),
        team.get("shortDisplayName"),
        team.get("name"),
    ]
    for cand in candidates:
        abbrev = _NHL_NAME_TO_ABBREV.get(" ".join((cand or "").lower().split()))
        if abbrev:
            return abbrev
    raw = (team.get("abbreviation") or "").upper()
    if not raw:
        return None
    return _ESPN_ABBREV_TO_OURS.get(raw, raw)


def parse_probable(probables: list | None, athlete: dict | None,
                   team: dict | None) -> dict | None:
    """Pure: one competitor's probableStartingGoalie → a designation dict.

    `status.type` is ESPN's confirm/scratch flag (`expected` / `confirmed` /
    `scratched`). There is no date on the probable object itself (measured
    2026-09-14); the clock for a scratch is `injuries.status_ts`.
    """
    if not probables:
        return None
    slot = None
    for p in probables:
        if str((p or {}).get("name") or "").lower() == PROBABLE_GOALIE:
            slot = p
            break
    if not slot:
        return None
    name = None
    if athlete:
        name = athlete.get("displayName") or athlete.get("fullName")
    abbrev = _team_abbrev(team or {})
    if not name or not abbrev:
        return None
    status = ((slot.get("status") or {}).get("type") or "expected")
    return {
        "team": abbrev,
        "player_name": name,
        "espn_athlete_id": str(slot.get("playerId") or athlete.get("id") or ""),
        "designation": str(status).lower(),
    }


def fetch_espn_nhl_probables(game_date: str, fetch=None) -> dict[str, dict]:
    """Tonight's ESPN probable starting goalie per our team abbrev.

    `game_date` is ISO `YYYY-MM-DD`. Returns {} on any failure.
    """
    fetch = fetch or _default_fetch
    yyyymmdd = str(game_date).replace("-", "")
    try:
        listing = fetch(CORE_NHL_EVENTS_URL.format(dates=yyyymmdd))
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"ESPN NHL events fetch failed ({exc}); no probable overlay")
        return {}

    out: dict[str, dict] = {}
    for item in (listing or {}).get("items", []) or []:
        ref = item.get("$ref") if isinstance(item, dict) else item
        if not ref:
            continue
        try:
            event = fetch(ref) or {}
        except Exception:
            continue
        comps = event.get("competitions") or []
        if not comps:
            continue
        for cr in comps[0].get("competitors") or []:
            cref = cr.get("$ref") if isinstance(cr, dict) else None
            if not cref:
                continue
            try:
                competitor = fetch(cref) or {}
            except Exception:
                continue
            team_ref = (competitor.get("team") or {}).get("$ref")
            team = {}
            if team_ref:
                try:
                    team = fetch(team_ref) or {}
                except Exception:
                    team = {}
            athlete = {}
            slot = None
            for p in competitor.get("probables") or []:
                if str((p or {}).get("name") or "").lower() == PROBABLE_GOALIE:
                    slot = p
                    break
            ath_ref = ((slot or {}).get("athlete") or {}).get("$ref")
            if ath_ref:
                try:
                    athlete = fetch(ath_ref) or {}
                except Exception:
                    athlete = {}
            parsed = parse_probable(competitor.get("probables"), athlete, team)
            if parsed:
                out[parsed["team"]] = parsed
    if out:
        logger.info(f"ESPN NHL probables: {len(out)} starting goalie(s) for {game_date}")
    return out
