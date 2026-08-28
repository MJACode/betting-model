"""
Live NFL game state from ESPN's unofficial API.

  scoreboard  https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard
  summary     .../summary?event={id}

WHY THIS FILE IS WRITTEN SO DEFENSIVELY
This endpoint is undocumented and has changed shape without notice before (the
platform's own ESPN injury ingestor has been broken twice by it). So:

  * Every field is pulled through `_dig`, which walks a path and returns None
    rather than raising on a missing key.
  * A missing REQUIRED field returns None from the extractor. The caller alerts.
    A half-built state that silently defaults to 0-0 in the first quarter is
    far worse than no state at all, because the engine would happily price it.
  * Optional fields degrade to None and the engine treats them as unknown.
  * Nothing here has been validated against a live payload from this sandbox:
    ESPN is blocked by the egress proxy. `scripts/verify_espn.py` is the spike
    that prints the real keys and checks every assumption flagged below. Run it
    before trusting a single live price.

ASSUMPTIONS TO VERIFY (each one is checked by the spike):
  A1 status.clock is SECONDS remaining in the period (float).
  A2 status.period is 1-4, and 5+ for overtime.
  A3 a halftime state reports period == 2 with clock 0, or type.name
     STATUS_HALFTIME. Both are accepted.
  A4 situation.possession is a TEAM ID matching competitors[].team.id.
  A5 field position is recoverable from situation.possessionText ("KC 35").
     situation.yardLine is used only as a fallback because its reference point
     (own goal line vs opponent goal line) is not consistent across feeds.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

log = logging.getLogger(__name__)

SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
)
SUMMARY_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary"
)

# Statuses in which a game is live enough to price.
LIVE_STATES = ("in",)
HALFTIME_NAMES = ("STATUS_HALFTIME",)
FINAL_STATES = ("post",)


def _dig(obj: Any, *path, default=None):
    """Walk a dict/list path, returning `default` on any miss. Never raises."""
    cur = obj
    for key in path:
        if cur is None:
            return default
        try:
            if isinstance(key, int):
                cur = cur[key]
            else:
                cur = cur.get(key)
        except (KeyError, IndexError, TypeError, AttributeError):
            return default
    return cur if cur is not None else default


def _num(v, default=None):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _int(v, default=None):
    f = _num(v)
    return default if f is None else int(round(f))


def _parse_clock(status: dict) -> int | None:
    """
    Seconds remaining in the current period.

    A1: status.clock is normally a float of seconds. Some payloads only carry
    displayClock ("7:12"), so both are handled and neither is assumed.
    """
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
    """
    Yards to the OPPONENT end zone for the team with the ball.

    A5: `possessionText` reads "KC 35". If that team is the one with the ball,
    they are on their own 35 and have 65 to go. Otherwise they are in the
    opponent's half and have 35 to go. This is unambiguous, which is why it is
    preferred over `yardLine`, whose reference point is not.
    """
    text = _dig(situation, "possessionText")
    if isinstance(text, str) and text.strip():
        parts = text.strip().split()
        if len(parts) == 2:
            side, yard = parts[0].upper(), _int(parts[1])
            if yard is not None and 0 <= yard <= 50:
                if poss_abbrev and side == poss_abbrev.upper():
                    return 100 - yard
                return yard
        # Midfield can arrive as "50" with no team.
        lone = _int(text.strip())
        if lone is not None and 0 <= lone <= 100:
            return 50 if lone == 50 else None

    fallback = _int(_dig(situation, "yardLine"))
    if fallback is not None and 0 <= fallback <= 100:
        # Documented as distance from the possessing team's own goal line in
        # the feeds observed to date. Flagged for the spike to confirm.
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
    """
    Play counts and pass counts per side, from the drive log.

    Used only for pace and pass-rate features, so a partial drive log degrades
    the feature rather than the state: a missing drives block yields zeroes and
    `smooth_pass_rate` falls back to the league prior.
    """
    out = {"total": 0, "home_plays": 0, "away_plays": 0,
           "home_pass": 0, "away_pass": 0}
    if not drives:
        return out

    buckets: Iterable = []
    prev = _dig(drives, "previous", default=[]) or []
    cur = _dig(drives, "current")
    buckets = list(prev) + ([cur] if cur else [])

    for drive in buckets:
        # ESPN marks the offense on the drive, not on each play.
        side = _dig(drive, "team", "abbreviation")
        home_abbrev = drive.get("_home_abbrev") if isinstance(drive, dict) else None
        for play in _dig(drive, "plays", default=[]) or []:
            ptype = (_dig(play, "type", "text") or "").lower()
            # Kickoffs, extra points, penalties and timeouts are not scrimmage
            # plays and must not inflate the pace estimate.
            if any(k in ptype for k in ("kickoff", "extra point", "timeout",
                                        "end period", "end of", "two-minute",
                                        "official")):
                continue
            out["total"] += 1
            is_pass = "pass" in ptype or "sack" in ptype
            key_side = "home" if (home_abbrev and side == home_abbrev) else None
            if key_side is None:
                # Without a home abbreviation we can still count total plays,
                # which is what the pace model actually needs.
                continue
            out[f"{key_side}_plays"] += 1
            if is_pass:
                out[f"{key_side}_pass"] += 1
    return out


def extract_summary_state(summary: dict) -> dict | None:
    """
    Pull the raw state fields out of an ESPN summary payload.

    Returns None when a REQUIRED field is missing: period, clock, both scores.
    Everything else is optional and degrades to None.
    """
    if not isinstance(summary, dict):
        return None

    comp = _dig(summary, "header", "competitions", 0)
    if comp is None:
        comp = _dig(summary, "competitions", 0)
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
        log.warning(
            "espn: required field missing (period=%s home=%s away=%s)",
            period, home_score, away_score,
        )
        return None

    # A3: halftime can arrive as an explicit status name with a non-zero or
    # absent clock. Normalise it to the canonical period 2 / clock 0 form the
    # engine's `is_halftime` looks for.
    if state_name in HALFTIME_NAMES:
        period, clock = 2, 0
    if clock is None:
        log.warning("espn: clock unreadable (status=%s)", state_name)
        return None

    situation = _dig(comp, "situation") or _dig(summary, "situation") or {}
    poss_id = _dig(situation, "possession")
    home_id = str(_dig(home_c, "team", "id") or "")
    away_id = str(_dig(away_c, "team", "id") or "")
    home_abbrev = _dig(home_c, "team", "abbreviation")
    away_abbrev = _dig(away_c, "team", "abbreviation")

    possession = None
    poss_abbrev = None
    if poss_id is not None:
        pid = str(poss_id)
        if pid == home_id:
            possession, poss_abbrev = "home", home_abbrev
        elif pid == away_id:
            possession, poss_abbrev = "away", away_abbrev

    drives = _dig(summary, "drives")
    if isinstance(drives, dict) and home_abbrev:
        for bucket in ("previous",):
            for d in _dig(drives, bucket, default=[]) or []:
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
        "home_timeouts": _int(_dig(situation, "homeTimeouts"), 3),
        "away_timeouts": _int(_dig(situation, "awayTimeouts"), 3),
        "plays_run": counts["total"],
        "home_plays": counts["home_plays"],
        "away_plays": counts["away_plays"],
        "home_pass_plays": counts["home_pass"],
        "away_pass_plays": counts["away_pass"],
        "state": _dig(status, "type", "state"),
        "state_name": state_name,
        "home_abbrev": home_abbrev,
        "away_abbrev": away_abbrev,
    }


def extract_live_event_ids(scoreboard: dict) -> list[dict]:
    """
    Games currently in progress, from the scoreboard payload.

    Returns the minimum the worker needs to decide what to poll: the event id,
    both abbreviations, and whether the game is live or at half.
    """
    out = []
    for ev in _dig(scoreboard, "events", default=[]) or []:
        comp = _dig(ev, "competitions", 0)
        status = _dig(comp, "status") or _dig(ev, "status") or {}
        state = _dig(status, "type", "state")
        if state not in LIVE_STATES:
            continue
        home_c, away_c = _competitors(comp)
        out.append({
            "event_id": str(_dig(ev, "id") or ""),
            "home": _dig(home_c, "team", "abbreviation"),
            "away": _dig(away_c, "team", "abbreviation"),
            "state_name": _dig(status, "type", "name") or "",
            "period": _int(_dig(status, "period")),
        })
    return [e for e in out if e["event_id"] and e["home"] and e["away"]]


# ------------------------------------------------------------ host selection
# site.api.espn.com has returned HTTP 403 to this project's Railway worker
# every day since early August 2026; the platform health check records it
# daily. The live model runs on that worker, so sports.core is tried FIRST and
# site.api is the fallback, which is the reverse of the order the WNBA results
# ingestor uses. That ingestor was written while site.api still worked; this
# one was written after it stopped, and defaulting to a host we have measured
# as blocked would mean every live poll fails before it starts.
def live_events(prefer_core: bool = True, session=None) -> tuple[list[dict], str]:
    """
    Games in progress, from whichever ESPN host answers.

    Returns (events, host_used) so the worker can report which path is live and
    alert when it changes. Raises only when BOTH hosts fail, because that is a
    real outage rather than a host preference.
    """
    from . import espn_core

    errors = []
    order = ("core", "site") if prefer_core else ("site", "core")
    for host in order:
        try:
            if host == "core":
                fetch = espn_core.make_fetcher(session=session)
                events = espn_core.fetch_live_events(fetch)
                return events, "sports.core"
            board = fetch_scoreboard(session=session)
            return extract_live_event_ids(board), "site.api"
        except Exception as e:                      # noqa: BLE001
            errors.append(f"{host}:{type(e).__name__}")
    raise RuntimeError("both ESPN hosts failed: " + ", ".join(errors))


# --------------------------------------------------------------------- I/O
def fetch_scoreboard(session=None, timeout: int = 15) -> dict:
    import requests
    s = session or requests
    r = s.get(SCOREBOARD_URL, timeout=timeout)
    r.raise_for_status()
    return r.json()


def fetch_summary(event_id: str, session=None, timeout: int = 15) -> dict:
    import requests
    s = session or requests
    r = s.get(SUMMARY_URL, params={"event": event_id}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def extract_player_stats(summary: dict) -> list[dict]:
    """
    Per-player accrued stats from the summary boxscore.

    ESPN nests these as boxscore.players[].statistics[] with a `labels` array
    and per-athlete `stats` arrays of STRINGS, positionally aligned to labels.
    Reading them BY LABEL rather than by index is the whole point: the label
    order has changed before, and an index read would silently swap yards for
    attempts. Anything unreadable is skipped, not guessed.
    """
    out: list[dict] = []
    teams = _dig(summary, "boxscore", "players", default=[]) or []
    header_comp = _dig(summary, "header", "competitions", 0)
    home_c, _ = _competitors(header_comp or {})
    home_id = str(_dig(home_c, "team", "id") or "")

    for team_block in teams:
        team_id = str(_dig(team_block, "team", "id") or "")
        side = "home" if team_id and team_id == home_id else "away"
        for cat in _dig(team_block, "statistics", default=[]) or []:
            name = (_dig(cat, "name") or "").lower()
            labels = [str(x).upper() for x in (_dig(cat, "labels", default=[]) or [])]
            for ath in _dig(cat, "athletes", default=[]) or []:
                pid = str(_dig(ath, "athlete", "id") or "")
                if not pid:
                    continue
                stats = _dig(ath, "stats", default=[]) or []
                if len(stats) != len(labels):
                    continue
                row = dict(zip(labels, stats))
                out.append({
                    "player_id": pid,
                    "team_side": side,
                    "category": name,
                    "position": _dig(ath, "athlete", "position", "abbreviation") or "",
                    "name": _dig(ath, "athlete", "displayName") or "",
                    "raw": row,
                })
    return out
