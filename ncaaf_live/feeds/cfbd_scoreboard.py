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


def fetch_scoreboard_cfbd(timeout: int = 15) -> list | None:
    """CFBD gets slow under load (measured 30s+ on a Thursday). The old 60s
    timeout x 2 attempts was patience bought against a 45s re-poll; at a 10s
    cadence that same patience stalls the loop for up to two minutes, and a
    scoreboard that takes a minute to arrive describes a game state that has
    already moved on. So: fail fast and let the next pass - seconds away, not
    a minute - be the retry. The one immediate retry stays for a blip."""
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


_YARD_RE = re.compile(r"\bat\s+([A-Z][A-Z&.\-]*)\s+(\d{1,2})\s*$")


def _abbrev_fits(abbr: str, school: str) -> bool:
    """Does a scoreboard abbreviation ('CCU', 'BGSU', 'UNC', 'NCSU') name
    this school? The feed never supplies its abbreviations, so this is a
    shape rule measured on the first stored slate (2026-09-19, 13 distinct
    strings): strip a leading 'U' and a trailing 'U', then the core is either
    a prefix of the squashed name (ARK/Arkansas, NCS/NC State, ILL/Illinois)
    or the name's initials plus at most one letter (CC/Coastal Carolina,
    BGS/Bowling Green, NT/North Texas, AS/Arizona State)."""
    core = abbr.upper().replace(".", "").replace("&", "").replace("-", "")
    if len(core) > 2 and core.startswith("U"):
        core = core[1:]
    if len(core) > 2 and core.endswith("U"):
        core = core[:-1]
    if len(core) < 2:
        return False
    words = [w for w in re.split(r"[\s\-]+", school.upper()) if w]
    squashed = "".join(words)
    initials = "".join(w[0] for w in words)
    if squashed.startswith(core):
        return True
    if len(initials) >= 2 and core.startswith(initials) \
            and len(core) - len(initials) <= 1:
        return True
    # A two-letter code on a one-word school ('ME' for Maine): first letter
    # plus a later letter of the name. The both-sides refusal in the caller
    # is what keeps this from guessing.
    return (len(core) == 2 and len(words) == 1
            and squashed.startswith(core[0]) and core[1] in squashed[1:])


def _parse_yardline(text, home: str, away: str,
                    possession: str | None) -> int | None:
    """'2nd & 8 at EMU 27' -> yards to the opponent's end zone for the
    offense (the training column, CFBD's yardsToGoal), or None.

    The ball is on the named team's side of the field. If that team has the
    ball it is 100 minus the yard; if the other team does, the yard itself;
    the 50 is the 50. None when possession is unknown, when the abbreviation
    fits neither school or BOTH (Michigan / Michigan State), or when the
    string is any other shape -- a guess here is a feature value the model
    will trust."""
    if not isinstance(text, str) or possession not in ("home", "away"):
        return None
    m = _YARD_RE.search(text.strip())
    if not m:
        return None
    abbr, yard = m.group(1), int(m.group(2))
    if not 0 <= yard <= 50:
        return None
    if yard == 50:
        return 50
    fits_home, fits_away = _abbrev_fits(abbr, home), _abbrev_fits(abbr, away)
    if fits_home == fits_away:
        return None
    side = "home" if fits_home else "away"
    return 100 - yard if side == possession else yard


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
            # FIELD POSITION, from the situation string (2026-09-19). The
            # model was trained on yardsToGoal and served NaN here, which is
            # half of why it could only see an "edge" when the book moved:
            # a drive to the 5 changed the book's number and nothing in our
            # state. Parsed from the real live shape ("4th & 3 at UNC 5"),
            # stored on the first slate the string was kept; None on any
            # doubt (_parse_yardline).
            "yardline_100": _parse_yardline(g.get("situation"), home, away,
                                            possession),
            # The raw string rides along in `ncaaf_live_states.raw_state`.
            "situation": g.get("situation"),
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
