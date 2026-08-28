"""
NCAAF live game state from ESPN's site.api college-football endpoints.

Adapted from nfl/live_model/feeds/espn.py (same site.api football schema, and
that file's A1-A5 payload assumptions carry over). Two deliberate differences:

  * This loop runs on Matt's RESIDENTIAL machine for week 1, where site.api
    answers (verified live 2026-08-28: scoreboard HTTP 200, 99 events). The
    sports.core port matters only when this moves to the Railway worker.
  * Team identity is the `location` field ("Ohio State", "San José State"),
    which matches the platform's CFBD school-name convention accent for
    accent. Abbreviations are NOT identity in CFB - 136 FBS schools collide.

The one shape that could not be verified before Saturday is `situation` on a
LIVE college game (no game was in progress when this was written), so
`check_feed_assumptions` runs on the first live payload of the day and the
loop refuses to price on a failed check rather than pricing every game off
defaults.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

import requests

log = logging.getLogger(__name__)

SCOREBOARD_URL = ("https://site.api.espn.com/apis/site/v2/sports/football/"
                  "college-football/scoreboard")
SUMMARY_URL = ("https://site.api.espn.com/apis/site/v2/sports/football/"
               "college-football/summary")
# groups=80 is FBS; without it the scoreboard returns a curated subset.
SCOREBOARD_PARAMS = {"groups": 80, "limit": 400}

LIVE_STATES = ("in",)
HALFTIME_NAMES = ("STATUS_HALFTIME",)


def _dig(obj: Any, *path, default=None):
    cur = obj
    for key in path:
        if isinstance(cur, dict):
            cur = cur.get(key)
        elif isinstance(cur, list) and isinstance(key, int) and key < len(cur):
            cur = cur[key]
        else:
            return default
        if cur is None:
            return default
    return cur


def _num(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _int(v, default=None):
    n = _num(v)
    return default if n is None else int(n)


def fetch_scoreboard(timeout: int = 20) -> dict | None:
    try:
        r = requests.get(SCOREBOARD_URL, params=SCOREBOARD_PARAMS,
                         timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as exc:                        # noqa: BLE001
        log.warning("espn scoreboard fetch failed: %s", exc)
        return None


def fetch_summary(event_id: str, timeout: int = 20) -> dict | None:
    try:
        r = requests.get(SUMMARY_URL, params={"event": event_id},
                         timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as exc:                        # noqa: BLE001
        log.warning("espn summary fetch failed for %s: %s", event_id, exc)
        return None


def _parse_clock(status: dict) -> int | None:
    raw = _num(_dig(status, "clock"))
    if raw is not None and 0 <= raw <= 1200:
        return int(raw)
    disp = _dig(status, "displayClock")
    if isinstance(disp, str) and ":" in disp:
        try:
            mm, ss = disp.strip().split(":")[:2]
            return int(mm) * 60 + int(float(ss))
        except (ValueError, TypeError):
            return None
    return None


def _yardline_100(situation: dict, poss_abbrev: str | None) -> int | None:
    text = _dig(situation, "possessionText")
    if isinstance(text, str) and text.strip():
        parts = text.strip().split()
        if len(parts) == 2:
            side, yard = parts[0].upper(), _int(parts[1])
            if yard is not None and 0 <= yard <= 50:
                if poss_abbrev and side == poss_abbrev.upper():
                    return 100 - yard
                return yard
        lone = _int(text.strip())
        if lone is not None and 0 <= lone <= 100:
            return 50 if lone == 50 else None
    fallback = _int(_dig(situation, "yardLine"))
    if fallback is not None and 0 <= fallback <= 100:
        return 100 - fallback
    return None


def _competitors(comp: dict) -> tuple[dict | None, dict | None]:
    home = away = None
    for c in _dig(comp, "competitors", default=[]) or []:
        side = _dig(c, "homeAway")
        if side == "home":
            home = c
        elif side == "away":
            away = c
    return home, away


def _count_plays(drives: dict | None) -> dict:
    """Scrimmage-play and pass counts from the drive log; degrades to zero."""
    out = {"total": 0, "home_plays": 0, "away_plays": 0,
           "home_pass": 0, "away_pass": 0}
    if not drives:
        return out
    prev = _dig(drives, "previous", default=[]) or []
    cur = _dig(drives, "current")
    buckets: Iterable = list(prev) + ([cur] if cur else [])
    for drive in buckets:
        if not isinstance(drive, dict):
            continue
        side = _dig(drive, "team", "abbreviation")
        home_abbrev = drive.get("_home_abbrev")
        for play in _dig(drive, "plays", default=[]) or []:
            ptype = (_dig(play, "type", "text") or "").lower()
            if any(k in ptype for k in ("kickoff", "extra point", "timeout",
                                        "end period", "end of", "official",
                                        "coin toss")):
                continue
            out["total"] += 1
            if not (home_abbrev and side):
                continue
            key = "home" if side == home_abbrev else "away"
            out[f"{key}_plays"] += 1
            if "pass" in ptype or "sack" in ptype or "interception" in ptype:
                out[f"{key}_pass"] += 1
    return out


def extract_summary_state(summary: dict) -> dict | None:
    """
    Raw live state from a summary payload. None when a REQUIRED field is
    missing (period, clock, both scores); everything else degrades to None,
    which the feature layer turns into NaN for the trees.
    """
    if not isinstance(summary, dict):
        return None
    comp = _dig(summary, "header", "competitions", 0) or _dig(summary, "competitions", 0)
    if comp is None:
        log.warning("espn: no competition block in summary payload")
        return None

    status = _dig(comp, "status") or _dig(summary, "header", "status") or {}
    period = _int(_dig(status, "period"))
    clock = _parse_clock(status)
    state_name = _dig(status, "type", "name") or ""

    home_c, away_c = _competitors(comp)
    home_score = _int(_dig(home_c, "score"))
    away_score = _int(_dig(away_c, "score"))
    if period is None or home_score is None or away_score is None:
        log.warning("espn: required field missing (period=%s home=%s away=%s)",
                    period, home_score, away_score)
        return None

    if state_name in HALFTIME_NAMES:
        period, clock = 2, 0
    if clock is None:
        log.warning("espn: clock unreadable (status=%s)", state_name)
        return None

    situation = _dig(comp, "situation") or _dig(summary, "situation") or {}
    poss_id = _dig(situation, "possession")
    home_id = str(_dig(home_c, "team", "id") or "")
    home_abbrev = _dig(home_c, "team", "abbreviation")
    away_abbrev = _dig(away_c, "team", "abbreviation")
    possession = poss_abbrev = None
    if poss_id is not None:
        pid = str(poss_id)
        if pid == home_id:
            possession, poss_abbrev = "home", home_abbrev
        elif pid == str(_dig(away_c, "team", "id") or ""):
            possession, poss_abbrev = "away", away_abbrev

    drives = _dig(summary, "drives")
    if isinstance(drives, dict) and home_abbrev:
        for d in (_dig(drives, "previous", default=[]) or []):
            if isinstance(d, dict):
                d["_home_abbrev"] = home_abbrev
        cur = _dig(drives, "current")
        if isinstance(cur, dict):
            cur["_home_abbrev"] = home_abbrev
    counts = _count_plays(drives)

    return {
        "period": period,
        "clock_seconds": max(0, clock),
        "home_score": home_score,
        "away_score": away_score,
        "possession": possession,
        "down": _int(_dig(situation, "down")),
        "distance": _int(_dig(situation, "distance")),
        "yardline_100": _yardline_100(situation, poss_abbrev),
        # CFB teams get 3 timeouts per half, same default as the NFL parser.
        "home_timeouts": _int(_dig(situation, "homeTimeouts"), 3),
        "away_timeouts": _int(_dig(situation, "awayTimeouts"), 3),
        "plays_run": counts["total"],
        "home_plays": counts["home_plays"],
        "away_plays": counts["away_plays"],
        "home_pass_plays": counts["home_pass"],
        "away_pass_plays": counts["away_pass"],
        "state": _dig(status, "type", "state"),
        "state_name": state_name,
        "home_location": _dig(home_c, "team", "location"),
        "away_location": _dig(away_c, "team", "location"),
    }


def extract_live_events(scoreboard: dict) -> list[dict]:
    """Games in progress: event id + SCHOOL LOCATIONS (the identity key)."""
    out = []
    for ev in _dig(scoreboard, "events", default=[]) or []:
        comp = _dig(ev, "competitions", 0)
        status = _dig(comp, "status") or _dig(ev, "status") or {}
        if _dig(status, "type", "state") not in LIVE_STATES:
            continue
        home_c, away_c = _competitors(comp)
        out.append({
            "event_id": str(_dig(ev, "id") or ""),
            "home_location": _dig(home_c, "team", "location"),
            "away_location": _dig(away_c, "team", "location"),
            "state_name": _dig(status, "type", "name") or "",
            "period": _int(_dig(status, "period")),
        })
    return out


def check_feed_assumptions(state: dict) -> list[str]:
    """
    First-live-payload sanity check (the NFL worker's pattern). A payload
    that LOOKS plausible with one field renamed prices every game off a
    default - so the loop refuses to price until this passes once.
    """
    problems = []
    if not (1 <= (state.get("period") or 0) <= 5):
        problems.append(f"period out of range: {state.get('period')}")
    if not (0 <= (state.get("clock_seconds") or -1) <= 900):
        problems.append(f"clock out of range: {state.get('clock_seconds')}")
    for k in ("home_score", "away_score"):
        if state.get(k) is None or state[k] < 0 or state[k] > 120:
            problems.append(f"{k} implausible: {state.get(k)}")
    if not state.get("home_location"):
        problems.append("home_location missing - identity mapping will fail")
    if state.get("possession") is None and (state.get("state") == "in"
                                            and state.get("state_name") not in HALFTIME_NAMES):
        problems.append("possession unresolved on an in-progress game "
                        "(non-fatal, features degrade)")
    return problems
