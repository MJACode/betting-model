"""
NFL live game state from sports.core.api.espn.com.

WHY THIS FILE EXISTS AT ALL. site.api.espn.com has returned HTTP 403 to this
project's Railway worker every single day since early August; the platform's
own health probe records it. The live model runs on that worker, so a feed
built on site.api would not have worked in production even once. The platform
already hit this and solved it: session 115 ported the WNBA results ingestor to
sports.core, which is still serving the worker fine. This is the NFL analogue.

  events:  /v2/sports/football/leagues/nfl/events?dates=YYYYMMDD
  event:   the $ref each item carries

THE SHAPE IS DIFFERENT FROM site.api, NOT JUST THE HOST. The core API is a
linked-document API: almost every field arrives as {"$ref": url} and has to be
chased. So this is a genuine second parser rather than a base-URL swap, and
both parsers feed the SAME extract shape so state.from_espn does not care which
one produced it.

Every ref is chased defensively, every http ref is forced to https (core
returns mixed schemes), and athlete and team documents are cached per run
because the same team is referenced by every event it plays in.

NOT VERIFIED AGAINST A LIVE PAYLOAD. ESPN is blocked from the sandbox this was
written in, so the shapes below are written from the core v2 conventions the
WNBA ingestor already relies on in production. Assumptions are marked C1 to C4
and live_model/verify_espn.py checks every one. The worker also self-checks on
its first payload each gameday, so a shape change surfaces as an alert rather
than as silence.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from .espn import _dig, _int, _num

log = logging.getLogger(__name__)

CORE_ROOT = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
CORE_SLEEP = 0.1        # be polite: ref chasing makes many small calls

# C1 status.type.state is 'pre' | 'in' | 'post', as on site.api.
LIVE_STATES = ("in",)

# C2 a halftime game reports period 2 with the clock expired, or a type
#    description naming halftime.
HALFTIME_HINTS = ("halftime", "end of 2nd quarter")

SEASON_TYPES = {1: "preseason", 2: "regular", 3: "postseason", 4: "offseason"}
_TYPE_IN_REF = re.compile(r"/types/(\d+)")


def season_type(ev: dict) -> str | None:
    """
    preseason / regular / postseason, off the URLs already in the document.

    THIS EXISTS SO A PRESEASON REP CANNOT BE READ LATER AS A TRACK RECORD.
    The one deployed lane is a bias measured on regular season football; in
    preseason the starters play a quarter, so a decision taken then is
    evidence about the plumbing and about nothing else. An audit log that
    cannot tell the two apart is how contaminated evidence gets quoted as a
    result.

    Costs no request: ESPN core encodes the season type in the path,
    .../seasons/2026/types/1/events/..., and the event document carries those
    refs inline. Returns None rather than guessing when it is absent.
    """
    for ref in ((ev.get("season") or {}).get("$ref"),
                (ev.get("seasonType") or {}).get("$ref")
                if isinstance(ev.get("seasonType"), dict) else None,
                ev.get("$ref")):
        if not ref:
            continue
        m = _TYPE_IN_REF.search(str(ref))
        if m:
            return SEASON_TYPES.get(int(m.group(1)))
    raw = ev.get("seasonType")
    if isinstance(raw, int):
        return SEASON_TYPES.get(raw)
    return None



def _https(url: str) -> str:
    """Core returns some refs over http. Force https rather than following."""
    if isinstance(url, str) and url.startswith("http://"):
        return "https://" + url[len("http://"):]
    return url


def make_fetcher(session=None, timeout: int = 12):
    """A caching, defensive ref fetcher. Never raises: a miss returns {}."""
    import requests
    from ..feeds.espn import _dig as _  # noqa: F401  (keeps import surface stable)

    s = session or requests.Session()
    cache: dict[str, dict] = {}

    def fetch(url: str) -> dict:
        if not url:
            return {}
        url = _https(url)
        if url in cache:
            return cache[url]
        try:
            r = s.get(url, timeout=timeout)
            if r.status_code != 200:
                log.warning("core %s for %s", r.status_code, url[:120])
                cache[url] = {}
                return {}
            data = r.json()
        except Exception as e:                       # noqa: BLE001
            log.warning("core fetch failed %s: %s", url[:120], e)
            cache[url] = {}
            return {}
        cache[url] = data if isinstance(data, dict) else {}
        return cache[url]

    return fetch


def _deref(obj, fetch, need: str) -> dict:
    """
    Resolve a field that may be inline or a {'$ref': url} link.

    Fetches ONLY when the needed key is absent, which keeps a full state poll
    to a handful of calls rather than one per field.
    """
    if not isinstance(obj, dict):
        return {}
    if need in obj:
        return obj
    ref = obj.get("$ref")
    return fetch(_https(ref)) or {} if ref else obj


def fetch_live_events(fetch, now: datetime | None = None) -> list[dict]:
    """
    Games in progress right now.

    Queried as a TWO DAY range and filtered, because a Sunday night kickoff
    carries a next-day UTC date and a one-day query would silently drop every
    night game. Same correction the WNBA core port needed.
    """
    now = now or datetime.now(timezone.utc)
    days = [(now - timedelta(days=1)).strftime("%Y%m%d"), now.strftime("%Y%m%d")]
    listing = fetch(f"{CORE_ROOT}/events?dates={days[0]}-{days[1]}&limit=100")
    out = []
    for item in (listing or {}).get("items") or []:
        ev = _deref(item, fetch, need="competitions")
        parsed = parse_core_event(ev, fetch)
        if parsed and parsed["state"] in LIVE_STATES:
            out.append(parsed)
    return out


def parse_core_event(ev: dict, fetch) -> dict | None:
    """
    One core event document into the SAME shape espn.extract_summary_state
    emits, so state.from_espn is indifferent to which host produced it.

    Returns None when a REQUIRED field cannot be resolved. A half-built state
    that defaults to 0-0 in the first quarter is far worse than no state,
    because the engine would happily price it.
    """
    comps = (ev or {}).get("competitions") or []
    if not comps:
        return None
    comp = comps[0]

    status = _deref(comp.get("status") or ev.get("status") or {}, fetch,
                    need="type")
    stype = status.get("type") or {}
    state = stype.get("state")
    period = _int(status.get("period"))
    clock = _num(status.get("clock"))
    detail = str(stype.get("detail") or stype.get("description") or "").lower()

    home = away = None
    for c in comp.get("competitors") or []:
        side = c.get("homeAway")
        if side == "home":
            home = c
        elif side == "away":
            away = c
    if home is None or away is None or period is None:
        log.warning("core: event missing competitors or period")
        return None

    def _score(c):
        # C3 score arrives as {'$ref': ...} resolving to {'value': 21.0}.
        doc = _deref(c.get("score") or {}, fetch, need="value")
        v = _num(doc.get("value"))
        return None if v is None else int(v)

    def _team(c):
        doc = _deref(c.get("team") or {}, fetch, need="abbreviation")
        return doc.get("abbreviation"), str(doc.get("id") or "")

    home_score, away_score = _score(home), _score(away)
    if home_score is None or away_score is None:
        log.warning("core: unresolvable score refs")
        return None

    home_abbrev, home_id = _team(home)
    away_abbrev, away_id = _team(away)

    # C2 normalise halftime to the canonical period 2 / clock 0 the engine's
    # is_halftime looks for.
    if any(h in detail for h in HALFTIME_HINTS):
        period, clock = 2, 0.0
    if clock is None:
        log.warning("core: clock unreadable (detail=%r)", detail[:60])
        return None

    # C4 the drive-level situation lives on a separate ref and is OPTIONAL:
    # possession, down and field position are enrichment, not requirements.
    situation = _deref(comp.get("situation") or {}, fetch, need="down")
    poss_ref = _dig(situation, "possession", "$ref") or situation.get("possession")
    possession = None
    if isinstance(poss_ref, str):
        if home_id and home_id in poss_ref:
            possession = "home"
        elif away_id and away_id in poss_ref:
            possession = "away"

    return {
        "event_id": str(ev.get("id") or comp.get("id") or ""),
        "period": period,
        "clock_seconds": max(0, int(clock)),
        "home_score": home_score,
        "away_score": away_score,
        "possession": possession,
        "down": _int(situation.get("down")),
        "distance": _int(situation.get("distance")),
        "yardline_100": _yardline_from_core(situation, possession),
        "home_timeouts": _int(situation.get("homeTimeouts"), 3),
        "away_timeouts": _int(situation.get("awayTimeouts"), 3),
        # The core event doc carries no drive log, so pace and pass rate fall
        # back to the league prior via smooth_pass_rate. Those feed features,
        # not the bet decision, so degrading them is acceptable where
        # degrading the score is not.
        "plays_run": 0,
        "home_plays": 0, "away_plays": 0,
        "home_pass_plays": 0, "away_pass_plays": 0,
        "state": state,
        "state_name": detail,
        "home_abbrev": home_abbrev,
        "away_abbrev": away_abbrev,
        "home": home_abbrev, "away": away_abbrev,
        "season_type": season_type(ev),
    }


def _yardline_from_core(situation: dict, possession: str | None):
    """
    Yards to the opponent end zone for the team with the ball.

    Core exposes yardLine relative to the possessing team's own goal line.
    Anything out of range is dropped rather than clamped, because a wrong field
    position is worse for the model than a missing one.
    """
    v = _int(situation.get("yardLine"))
    if v is None or not (0 <= v <= 100):
        return None
    return 100 - v if possession else None
