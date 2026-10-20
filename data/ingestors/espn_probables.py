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
    out = {d["team"]: d for d in fetch_espn_nhl_designations(game_date, fetch=fetch)
           if d.get("player_name")}
    if out:
        logger.info(f"ESPN NHL probables: {len(out)} starting goalie(s) for {game_date}")
    return out


def _slot(probables) -> dict | None:
    for p in probables if isinstance(probables, list) else []:
        if str((p or {}).get("name") or "").lower() == PROBABLE_GOALIE:
            return p
    return None


def _short_name_teams(event: dict) -> dict[str, str]:
    """{'home': ours, 'away': ours} from the event's "AWAY @ HOME" short name,
    or {} when it does not read that way. Saves two team fetches a game; the
    caller falls back to the team docs when this cannot place a competitor."""
    parts = str(event.get("shortName") or "").split("@")
    if len(parts) != 2:
        return {}
    away, home = (p.strip().upper() for p in parts)
    if not away or not home:
        return {}
    return {"away": _ESPN_ABBREV_TO_OURS.get(away, away),
            "home": _ESPN_ABBREV_TO_OURS.get(home, home)}


def fetch_espn_nhl_designations(game_date: str, fetch=None, known: dict | None = None,
                                teams_ok=None, skip_game=None) -> list[dict]:
    """Every team ESPN lists on `game_date` (ET; `?dates=` is keyed on the ET
    date, measured 2026-10-20: the 01:00Z-02:30Z games came back under the
    previous day), with its probable starter and ESPN's status.

    One dict per team: {team, home_away, opponent, player_name, espn_athlete_id,
    designation}. A team whose competitor ESPN returned with no
    probableStartingGoalie comes back with player_name None and designation
    'none', so a withdrawn starter is recorded rather than left standing.

    `known`: {team: {"espn_athlete_id", "designation", "player_name"}} from the
    latest stored row. When ESPN still names the same athlete with the same
    status, his name is taken from there and his athlete doc is not fetched:
    a poll of an unchanged slate is the listing plus one call a game.

    `teams_ok(home, away)`: True when the pair read off the event's short name
    is a real game; otherwise the competitors' team docs are fetched (and so
    always when it is None). `skip_game(home, away)`: True for a game the
    caller does not want (one already started): nothing more is fetched for it.

    Inline data first: the event document already carries each competitor's
    homeAway and probables (measured 2026-10-20); the competitor document is
    fetched only when they are missing. Fail open: a listing failure returns
    [], a failed event or competitor is skipped.
    """
    fetch = fetch or _default_fetch
    known = known or {}
    yyyymmdd = str(game_date).replace("-", "")
    try:
        listing = fetch(CORE_NHL_EVENTS_URL.format(dates=yyyymmdd))
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"ESPN NHL events fetch failed ({exc}); no probable overlay")
        return []

    out: list[dict] = []
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
        by_side = _short_name_teams(event)
        if by_side and teams_ok is not None and not teams_ok(by_side["home"], by_side["away"]):
            by_side = {}
        if by_side and skip_game is not None and skip_game(by_side["home"], by_side["away"]):
            continue
        rows = []
        for cr in comps[0].get("competitors") or []:
            if not isinstance(cr, dict):
                continue
            competitor = cr
            if "probables" not in cr or "homeAway" not in cr:
                cref = cr.get("$ref")
                if not cref:
                    continue
                try:
                    competitor = {**cr, **(fetch(cref) or {})}
                except Exception:
                    continue
            side = str(competitor.get("homeAway") or "").lower()
            abbrev = by_side.get(side) if teams_ok is not None else None
            if not abbrev:
                team = {}
                team_ref = (competitor.get("team") or {}).get("$ref")
                if team_ref:
                    try:
                        team = fetch(team_ref) or {}
                    except Exception:
                        team = {}
                abbrev = _team_abbrev(team) if team else None
            if not abbrev:
                continue
            probables = competitor.get("probables")
            if isinstance(probables, dict) and probables.get("$ref"):
                # Some documents link the list instead of inlining it. A link
                # that cannot be read says nothing, so the team is skipped
                # rather than recorded as having no starter.
                try:
                    probables = (fetch(probables["$ref"]) or {}).get("items") or []
                except Exception:
                    continue
            slot = _slot(probables)
            if not slot:
                rows.append({"team": abbrev, "home_away": side, "player_name": None,
                             "espn_athlete_id": None, "designation": "none"})
                continue
            status = str(((slot.get("status") or {}).get("type") or "expected")).lower()
            ath_id = str(slot.get("playerId") or "")
            held = known.get(abbrev) or {}
            name = None
            if (ath_id and str(held.get("espn_athlete_id") or "") == ath_id
                    and held.get("designation") == status):
                name = held.get("player_name")
            if not name:
                ath_ref = (slot.get("athlete") or {}).get("$ref")
                athlete = {}
                if ath_ref:
                    try:
                        athlete = fetch(ath_ref) or {}
                    except Exception:
                        athlete = {}
                name = athlete.get("displayName") or athlete.get("fullName")
                ath_id = ath_id or str(athlete.get("id") or "")
            if not name:
                continue
            rows.append({"team": abbrev, "home_away": side, "player_name": name,
                         "espn_athlete_id": ath_id or None, "designation": status})
        if len(rows) == 2:
            rows[0]["opponent"], rows[1]["opponent"] = rows[1]["team"], rows[0]["team"]
        out += rows
    return out
