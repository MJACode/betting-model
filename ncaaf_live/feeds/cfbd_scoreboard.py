"""
NCAAF live state from CFBD /scoreboard - the RAILWAY-SAFE source.

Why this exists: site.api.espn.com has answered the Railway worker with HTTP
403 every day since early August (the platform's own health probe records
it), so the ESPN feed works from Matt's machine but would return nothing in
production. CFBD is keyed, already reachable from the worker (the weekly
NCAAF step uses it), and its /scoreboard returns EVERY game's state in ONE
call - period, clock, scores, possession, situation - keyed by CFBD's own
numeric team ids, which map to school names (the platform's canonical
identity) via one /teams/fbs call at loop start. No name mapping, no
per-game summary fetches.

What it lacks vs the ESPN summary: structured down/distance/yardline
(situation is a display string, parsed defensively), timeouts, and the
drive log for pace/pass-rate. All of those degrade to NaN, which LightGBM
routes natively - the same degradation the serve tests already pin.

Live payload shapes (status strings, clock format, possession values) could
not be observed before a game was actually live, so every field is parsed
defensively and the same first-payload feed check gates pricing.
"""

from __future__ import annotations

import logging
import re

import requests

from ..config import CFBD_API_KEY, CFBD_BASE_URL

log = logging.getLogger(__name__)

SCOREBOARD_URL = f"{CFBD_BASE_URL}/scoreboard"
TEAMS_URL = f"{CFBD_BASE_URL}/teams/fbs"

LIVE_STATUSES = ("in_progress", "in progress", "live", "active")

# "3rd & 7 at TCU 25" and friends
_SITUATION_RE = re.compile(
    r"(\d)(?:st|nd|rd|th)\s*&\s*(\d+|goal)", re.IGNORECASE)


def _headers() -> dict:
    return {"Authorization": f"Bearer {CFBD_API_KEY}"}


def fetch_team_ids(season: int, timeout: int = 90) -> dict[int, str]:
    """
    {cfbd_team_id: school_name} - one call, cached by the caller. Retried,
    because a silently empty map plus an empty school vocabulary would skip
    every game on the worker; the caller ALSO supplies the platform's own
    ncaaf_teams schools as the mascot-strip fallback so identity survives
    this endpoint being down entirely.
    """
    import time as _time
    for attempt in range(3):
        try:
            r = requests.get(TEAMS_URL, params={"year": season},
                             headers=_headers(), timeout=timeout)
            r.raise_for_status()
            out = {}
            for t in r.json() or []:
                tid, school = t.get("id"), t.get("school")
                if tid is not None and school:
                    out[int(tid)] = school
            log.info("cfbd teams: %d id mappings", len(out))
            return out
        except Exception as exc:                    # noqa: BLE001
            log.warning("cfbd /teams/fbs attempt %d failed: %s",
                        attempt + 1, exc)
            _time.sleep(5 * (attempt + 1))
    return {}


def fetch_scoreboard_cfbd(timeout: int = 60) -> list | None:
    """One retry: CFBD gets slow under load (measured 30s+ on a Thursday),
    and the loop re-polls every 45s anyway, so patience beats hammering."""
    for attempt in range(2):
        try:
            r = requests.get(SCOREBOARD_URL, headers=_headers(),
                             timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as exc:                    # noqa: BLE001
            log.warning("cfbd scoreboard attempt %d failed: %s",
                        attempt + 1, exc)
    return None


def _clock_seconds(clock) -> int | None:
    """clock arrives as 'MM:SS', a bare number, or null."""
    if clock is None:
        return None
    if isinstance(clock, (int, float)) and 0 <= clock <= 1200:
        return int(clock)
    if isinstance(clock, str) and ":" in clock:
        try:
            mm, ss = clock.strip().split(":")[:2]
            return int(mm) * 60 + int(float(ss))
        except (ValueError, TypeError):
            return None
    return None


def _parse_situation(text) -> tuple[int | None, int | None]:
    """('3rd & 7 at ...') -> (down, distance); anything else -> (None, None)."""
    if not isinstance(text, str):
        return (None, None)
    m = _SITUATION_RE.search(text)
    if not m:
        return (None, None)
    down = int(m.group(1))
    dist_raw = m.group(2).lower()
    distance = 1 if dist_raw == "goal" else int(dist_raw)
    if 1 <= down <= 4:
        return (down, distance)
    return (None, None)


def _strip_mascot(name: str, known_schools: set[str]) -> str | None:
    """
    'TCU Horned Frogs' -> 'TCU' by longest-prefix match against the known
    school list. Fallback for when the id map failed to load - identity must
    never be guessed loosely, so no match means None (skip the game).
    """
    if not name:
        return None
    words = name.split()
    for cut in range(len(words), 0, -1):
        cand = " ".join(words[:cut])
        if cand in known_schools:
            return cand
    return None


def extract_live_states_cfbd(payload: list, id_to_school: dict[int, str],
                             known_schools: set[str] | None = None
                             ) -> list[dict]:
    """
    Every in-progress game as a state dict in the SAME shape the ESPN feed
    emits, so serve.LiveEngine cannot tell the sources apart.

    `known_schools` (the platform's ncaaf_teams) backs the mascot-strip
    fallback when the id map failed to load - identity survives either
    source being down, and only both failing skips a game.
    """
    known = set(id_to_school.values()) | (known_schools or set())
    out = []
    for g in payload or []:
        status = str(g.get("status") or "").lower()
        if status not in LIVE_STATUSES:
            continue
        home_t, away_t = g.get("homeTeam") or {}, g.get("awayTeam") or {}

        def school(t):
            tid = t.get("id")
            if tid is not None and int(tid) in id_to_school:
                return id_to_school[int(tid)]
            return _strip_mascot(t.get("name") or "", known)

        home, away = school(home_t), school(away_t)
        if not home or not away:
            log.warning("cfbd scoreboard: unresolved identity %s / %s - skip",
                        home_t.get("name"), away_t.get("name"))
            continue

        period = g.get("period")
        clock = _clock_seconds(g.get("clock"))
        hs, as_ = home_t.get("points"), away_t.get("points")
        if period is None or clock is None or hs is None or as_ is None:
            log.warning("cfbd scoreboard: required field missing for %s @ %s "
                        "(period=%s clock=%s)", away, home, period,
                        g.get("clock"))
            continue

        poss_raw = g.get("possession")
        possession = None
        if poss_raw is not None:
            p = str(poss_raw).lower()
            if p == "home":
                possession = "home"
            elif p == "away":
                possession = "away"
            else:
                # may be a team id
                try:
                    pid = int(poss_raw)
                    if pid == int(home_t.get("id") or -1):
                        possession = "home"
                    elif pid == int(away_t.get("id") or -1):
                        possession = "away"
                except (TypeError, ValueError):
                    pass

        down, distance = _parse_situation(g.get("situation"))
        out.append({
            "period": int(period),
            "clock_seconds": max(0, clock),
            "home_score": int(hs),
            "away_score": int(as_),
            "possession": possession,
            "down": down,
            "distance": distance,
            "yardline_100": None,          # not in the scoreboard - NaN degrade
            "home_timeouts": None,
            "away_timeouts": None,
            "plays_run": None,
            "home_plays": None, "away_plays": None,
            "home_pass_plays": None, "away_pass_plays": None,
            "state": "in",
            "state_name": status,
            "home_location": home,
            "away_location": away,
        })
    return out
