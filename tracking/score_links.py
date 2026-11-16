"""Score-page links for Discord pick posts.

The matchup in a pick embed is a masked link to that game's live score and
final result. Discord renders ``[text](url)`` in embed field values and
descriptions. It does not render it in embed titles or field names, so the
link lives in the field value, where the matchup line already is.

A link preview is a second embed Discord builds from a bare URL in message
content. These posts are one embeds payload and the URL appears only inside
the masked link, so Discord does not unfurl it.

Resolution never raises and never waits unbounded. A stored ESPN id (or a
EuroLeague game id we already mint) builds the page with no network. Anything
else is one scoreboard read per sport and date, cached, inside a one-second
budget for the whole batch. A miss, a timeout, or two games that both match
falls back to that sport's scoreboard for the date. A sport with no page
stays plain text.
"""
from __future__ import annotations

import re
import threading
import time
import unicodedata
import urllib.parse
from typing import Callable

from loguru import logger

# site.api scoreboard -> www gamecast. The page slug is what ESPN puts in the
# Gamecast href (…/mlb/game/_/gameId/<id>), measured off the scoreboard's own
# links. Tennis matches use /tennis/match/_/gameId/<competition id>.
_ESPN = {
    "NFL": {"api": "football/nfl", "page": "nfl", "params": {}},
    "NBA": {"api": "basketball/nba", "page": "nba", "params": {"limit": 100}},
    "WNBA": {"api": "basketball/wnba", "page": "wnba", "params": {}},
    "NHL": {"api": "hockey/nhl", "page": "nhl", "params": {}},
    "MLB": {"api": "baseball/mlb", "page": "mlb", "params": {}},
    "NCAAF": {
        "api": "football/college-football",
        "page": "college-football",
        "params": {"groups": 80, "limit": 400},
    },
    "NCAAB": {
        "api": "basketball/mens-college-basketball",
        "page": "mens-college-basketball",
        "params": {"groups": 50, "limit": 500},
    },
    "NCAABW": {
        "api": "basketball/womens-college-basketball",
        "page": "womens-college-basketball",
        "params": {"groups": 50, "limit": 500},
    },
    "ATP": {"api": "tennis/atp", "page": "tennis", "tennis": True, "params": {}},
    "WTA": {"api": "tennis/wta", "page": "tennis", "tennis": True, "params": {}},
}

# ESPN abbreviations that are not ours. Both directions, so a stored "CWS"
# matches a scoreboard "CHW" and the reverse.
_MLB_EQUIV = {
    "CWS": {"cws", "chw"},
    "CHW": {"cws", "chw"},
    "OAK": {"oak", "ath"},
    "ATH": {"oak", "ath"},
    "WSH": {"wsh", "was"},
    "WAS": {"wsh", "was"},
    "ARI": {"ari", "az"},
    "AZ": {"ari", "az"},
}

# game_id, event id. Table and column are fixed; nothing here is user input.
_STORED = (
    ("ncaab_events",
     "SELECT game_id, espn_event_id::text FROM ncaab_events "
     "WHERE game_id = ANY(%(ids)s)"),
    ("ncaabw_events",
     "SELECT game_id, espn_event_id::text FROM ncaabw_events "
     "WHERE game_id = ANY(%(ids)s)"),
    ("live_scoreboard",
     "SELECT game_id, event_id FROM live_scoreboard "
     "WHERE game_id = ANY(%(ids)s) AND event_id IS NOT NULL "
     "AND btrim(event_id) <> ''"),
    ("tennis_moneyline_decisions",
     "SELECT game_id, comp_id FROM tennis_moneyline_decisions "
     "WHERE game_id = ANY(%(ids)s) AND comp_id IS NOT NULL"),
)

_EVENT_ID = re.compile(r"^[0-9]{5,12}$")
_DAY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
_EUROLEAGUE = re.compile(r"^EUROLEAGUE_(E\d{4})_(\d{1,6})$")
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# One scoreboard answer is good for hours; an id does not move. A failure is
# remembered briefly so a dead host cannot add a wait to every later post.
_SUCCESS_TTL = 6 * 3600
_FAIL_TTL = 120
# The whole batch, not one request per sport. Past this, remaining games
# keep the scoreboard URL and the post goes out.
_BUDGET_S = 1.0

_cache: dict[tuple[str, str], tuple[float, list | None]] = {}
_cache_lock = threading.Lock()

Fetch = Callable[[str, str, float], dict | None]


def clear_cache() -> None:
    """Drop the scoreboard cache. Tests use it so one case cannot feed another."""
    with _cache_lock:
        _cache.clear()


def norm(value) -> str:
    """Case- and accent-folded identity. '&' becomes 'and' so A&M matches."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("&", " and ")
    return " ".join(re.findall(r"[a-z0-9]+", text))


def game_id_of(signal: dict) -> str:
    """Our game id off the signal. Live lock keys are ``live:<game>:<model>:…``."""
    gid = signal.get("game_id")
    if gid:
        return str(gid)
    key = str(signal.get("lock_key") or "")
    if not key:
        return ""
    if key.startswith("live:"):
        parts = key.split(":")
        return parts[1] if len(parts) > 1 else ""
    return key.split(":", 1)[0]


def _yyyymmdd(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat") and not isinstance(value, str):
        value = value.isoformat()
    m = _DAY.match(str(value).strip())
    if not m:
        return None
    return f"{m.group(1)}{m.group(2)}{m.group(3)}"


def _event_id(value) -> str | None:
    text = str(value or "").strip()
    return text if _EVENT_ID.fullmatch(text) else None


def _allowed(url: str) -> bool:
    """Only hosts this module builds. A stored id never becomes the host."""
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if parsed.scheme == "https" and host in (
            "www.espn.com", "www.euroleaguebasketball.net"):
        return True
    if parsed.scheme in ("http", "https") and host in (
            "ufcstats.com", "www.ufcstats.com"):
        return True
    return False


def game_url(sport: str, event_id) -> str | None:
    """ESPN gamecast for one event, or None when the id is not an ESPN id."""
    eid = _event_id(event_id)
    spec = _ESPN.get((sport or "").upper())
    if not eid or not spec:
        return None
    if spec.get("tennis"):
        return f"https://www.espn.com/tennis/match/_/gameId/{eid}"
    return f"https://www.espn.com/{spec['page']}/game/_/gameId/{eid}"


def _ufc_scoreboard() -> str:
    base = "http://ufcstats.com"
    try:
        import config
        configured = getattr(config, "UFCSTATS_BASE_URL", "") or ""
        if configured:
            base = configured.rstrip("/")
    except Exception:                                          # noqa: BLE001
        pass
    url = f"{base}/statistics/events/upcoming"
    return url if _allowed(url) else "http://ufcstats.com/statistics/events/upcoming"


def euroleague_game_url(game_id: str | None) -> str | None:
    """The league game page from our own id, ``EUROLEAGUE_E2024_294``."""
    m = _EUROLEAGUE.match(str(game_id or ""))
    if not m:
        return None
    return ("https://www.euroleaguebasketball.net/euroleague/game-center/"
            f"?gamecode={m.group(2)}&seasoncode={m.group(1)}")


def scoreboard_url(sport: str, game_date) -> str | None:
    """A sport's scoreboard for that date, when we have no one game to open."""
    sport = (sport or "").upper()
    if sport == "GOLF":
        return "https://www.espn.com/golf/leaderboard"
    if sport == "UFC":
        return _ufc_scoreboard()
    if sport == "EUROLEAGUE":
        return "https://www.euroleaguebasketball.net/euroleague/games/"
    spec = _ESPN.get(sport)
    day = _yyyymmdd(game_date)
    if not spec or not day:
        return None
    if spec.get("tennis"):
        return f"https://www.espn.com/tennis/scoreboard/_/date/{day}"
    return f"https://www.espn.com/{spec['page']}/scoreboard/_/date/{day}"


def static_url(signal: dict, slate_date=None) -> str | None:
    """A page we can name with no network. None when the sport has no page."""
    sport = (signal.get("sport") or "")
    direct = game_url(sport, signal.get("espn_event_id"))
    if direct:
        return direct
    euro = euroleague_game_url(game_id_of(signal))
    if euro:
        return euro
    return scoreboard_url(sport, signal.get("game_date") or slate_date)


def mask(text: str, url: str | None) -> str:
    """``[text](url)`` when the URL is one we built. Otherwise the text as-is.

    Brackets or parentheses in the visible text would break the markdown, so
    those matchups stay plain rather than being rewritten.
    """
    if not text:
        return ""
    if not url or not _allowed(url) or any(ch in text for ch in "[]()"):
        return text
    return f"[{text}]({url})"


def _wnba_code(abbrev: str, display: str) -> str | None:
    try:
        from data.ingestors.wnba_stats_ingestor import (
            _WNBA_ABBREV_MAP, _WNBA_NAME_MAP)
    except Exception:                                          # noqa: BLE001
        return None
    return (_WNBA_ABBREV_MAP.get((abbrev or "").upper())
            or _WNBA_NAME_MAP.get(display or ""))


def _wnba_aliases(name: str) -> set[str]:
    code = (name or "").upper()
    try:
        from data.ingestors.wnba_stats_ingestor import _WNBA_ABBREV_MAP
    except Exception:                                          # noqa: BLE001
        return set()
    return {norm(abbr) for abbr, ours in _WNBA_ABBREV_MAP.items() if ours == code}


def _team_tokens(sport: str, team: dict) -> set[str]:
    abbr = str(team.get("abbreviation") or "").strip()
    display = str(team.get("displayName") or "").strip()
    out: set[str] = set()
    for raw in (abbr, display, team.get("shortDisplayName"),
                team.get("location"), team.get("name")):
        token = norm(raw)
        if token:
            out.add(token)
    if sport in ("NBA", "NFL", "NHL") and (abbr or display):
        try:
            from data.ingestors.live_scoreboard import team_code
            code = team_code(sport, abbr, display)
        except Exception:                                      # noqa: BLE001
            code = None
        if code:
            out.add(norm(code))
    if sport == "WNBA":
        code = _wnba_code(abbr, display)
        if code:
            out.add(norm(code))
    if sport == "MLB" and abbr:
        out |= _MLB_EQUIV.get(abbr.upper(), set())
    return out


def _our_tokens(sport: str, name) -> set[str]:
    raw = str(name or "").strip()
    token = norm(raw)
    if not token:
        return set()
    out = {token}
    if sport == "MLB":
        out |= _MLB_EQUIV.get(raw.upper(), set())
    if sport == "WNBA":
        out |= _wnba_aliases(raw)
    return out


def _side(comp: dict) -> dict:
    team = comp.get("team") or {}
    if team:
        return team
    athlete = comp.get("athlete") or {}
    name = athlete.get("displayName") or comp.get("displayName") or ""
    return {"displayName": name, "abbreviation": athlete.get("abbreviation") or ""}


def parse_events(sport: str, payload: dict | None) -> list[dict]:
    """Events on one scoreboard: id plus the two sides' name tokens.

    Tennis is unordered (ESPN does not mark home). A team event keeps
    home and away. An event with no id or no two sides is dropped.
    """
    sport = (sport or "").upper()
    if not payload:
        return []
    tennis = bool(_ESPN.get(sport, {}).get("tennis"))
    out: list[dict] = []

    def add(eid, comps, unordered: bool) -> None:
        eid = _event_id(eid)
        if not eid:
            return
        sides: dict[str, set[str]] = {}
        names: list[set[str]] = []
        for comp in comps or []:
            tokens = _team_tokens(sport, _side(comp))
            if not tokens:
                continue
            names.append(tokens)
            ha = comp.get("homeAway")
            if ha in ("home", "away"):
                sides[ha] = tokens
        if unordered:
            if len(names) < 2:
                return
            out.append({"id": eid, "unordered": True,
                        "sides": names[:2]})
            return
        if "home" not in sides or "away" not in sides:
            return
        out.append({"id": eid, "unordered": False,
                    "home": sides["home"], "away": sides["away"]})

    for ev in payload.get("events") or []:
        if tennis:
            for grouping in ev.get("groupings") or []:
                for comp in grouping.get("competitions") or []:
                    add(comp.get("id"), comp.get("competitors"), True)
            continue
        comps = ev.get("competitions") or []
        add(ev.get("id"), (comps[0].get("competitors") if comps else None), False)
    return out


def match_event(sport: str, home, away, events: list[dict]) -> str | None:
    """The one event both sides name. Two matches is no match: the scoreboard
    is then the honest link, not a guess at which game."""
    sport = (sport or "").upper()
    want_h = _our_tokens(sport, home)
    want_a = _our_tokens(sport, away)
    if not want_h or not want_a:
        return None
    hits: list[str] = []
    for ev in events:
        if ev.get("unordered"):
            sides = ev.get("sides") or []
            if len(sides) < 2 or (want_h & want_a):
                continue
            straight = (want_h & sides[0]) and (want_a & sides[1])
            swapped = (want_h & sides[1]) and (want_a & sides[0])
            if straight or swapped:
                hits.append(ev["id"])
            continue
        home_hit = bool(want_h & (ev.get("home") or set()))
        away_hit = bool(want_a & (ev.get("away") or set()))
        swapped = (bool(want_h & (ev.get("away") or set()))
                   and bool(want_a & (ev.get("home") or set())))
        if (home_hit and away_hit) or swapped:
            hits.append(ev["id"])
    unique = list(dict.fromkeys(hits))
    if len(unique) == 1:
        return unique[0]
    return None


def _offline(*_args, **_kwargs):
    """No scoreboard read. Stored ids and static pages still apply."""
    return None


def fetch_scoreboard(sport: str, day: str, timeout: float) -> dict | None:
    """One ESPN scoreboard. None on any failure. Does not raise."""
    spec = _ESPN.get(sport)
    if not spec or timeout <= 0:
        return None
    import requests
    url = ("https://site.api.espn.com/apis/site/v2/sports/"
           f"{spec['api']}/scoreboard")
    try:
        resp = requests.get(url, params={"dates": day, **spec["params"]},
                            headers=_HEADERS, timeout=timeout)
    except Exception as exc:                                   # noqa: BLE001
        logger.warning(f"score link {sport} {day}: {type(exc).__name__}")
        return None
    if resp.status_code != 200:
        logger.warning(f"score link {sport} {day}: HTTP {resp.status_code}")
        return None
    try:
        return resp.json()
    except ValueError:
        logger.warning(f"score link {sport} {day}: not JSON")
        return None


def _cached_events(sport: str, day: str, fetch: Fetch,
                   budget_end: float) -> list | None:
    key = (sport, day)
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[0] > now:
            return hit[1]
    left = budget_end - time.monotonic()
    if left < 0.15:
        return None
    timeout = min(0.8, left)
    try:
        payload = fetch(sport, day, timeout)
    except Exception as exc:                                   # noqa: BLE001
        logger.warning(f"score link {sport} {day}: {type(exc).__name__}")
        payload = None
    if payload is None:
        events = None
        ttl = _FAIL_TTL
    else:
        events = parse_events(sport, payload)
        ttl = _SUCCESS_TTL
    with _cache_lock:
        _cache[key] = (time.monotonic() + ttl, events)
    return events


def _stored_ids(conn, game_ids: list[str]) -> dict[str, str]:
    """game id -> ESPN event id, from tables we already write. Never raises
    and never leaves the caller's transaction aborted."""
    wanted = list(dict.fromkeys(g for g in game_ids if g))
    if not wanted or conn is None:
        return {}
    found: dict[str, str] = {}
    for table, sql in _STORED:
        rows = _read_table(conn, table, sql, wanted)
        for row in rows:
            if not isinstance(row, (tuple, list)) or len(row) < 2:
                continue
            gid, raw = row[0], row[1]
            eid = _event_id(raw)
            if gid in wanted and eid and gid not in found:
                found[str(gid)] = eid
    return found


def _read_table(conn, table: str, sql: str, ids: list[str]) -> list:
    try:
        conn.execute("SAVEPOINT discord_score_link")
    except Exception:                                          # noqa: BLE001
        return []
    try:
        exists = conn.execute(
            "SELECT to_regclass(%s)", (f"public.{table}",)).fetchone()
        if not exists or not exists[0]:
            conn.execute("RELEASE SAVEPOINT discord_score_link")
            return []
        rows = conn.execute(sql, {"ids": ids}).fetchall()
        conn.execute("RELEASE SAVEPOINT discord_score_link")
        return list(rows or [])
    except Exception as exc:                                   # noqa: BLE001
        logger.warning(f"score link {table}: {type(exc).__name__}")
        try:
            conn.execute("ROLLBACK TO SAVEPOINT discord_score_link")
        except Exception:                                      # noqa: BLE001
            pass
        return []


def _resolve(signal: dict, stored: dict[str, str], fetch: Fetch,
             budget_end: float) -> str | None:
    sport = signal.get("sport") or ""
    gid = game_id_of(signal)
    # An id already on the signal (or one we just read) is a game page.
    # Do not spend the budget looking the same game up again.
    eid = signal.get("espn_event_id") or (stored.get(gid) if gid else None)
    if eid:
        direct = game_url(sport, eid)
        if direct:
            return direct
    euro = euroleague_game_url(gid)
    if euro:
        return euro
    key = (sport or "").upper()
    day = _yyyymmdd(signal.get("game_date"))
    if (key in _ESPN and day and signal.get("home") and signal.get("away")
            and fetch is not _offline):
        events = _cached_events(key, day, fetch, budget_end)
        if events:
            matched = match_event(key, signal.get("home"), signal.get("away"),
                                  events)
            if matched:
                direct = game_url(sport, matched)
                if direct:
                    return direct
    return static_url(signal)


def attach(signals: list[dict], conn=None, *, fetch: Fetch | None = None,
           network: bool = True, slate_date=None) -> None:
    """Set ``score_url`` on each signal. Never raises. Does not drop signals."""
    if not signals:
        return
    if fetch is None:
        fetch = fetch_scoreboard if network else _offline
    for signal in signals:
        if slate_date and not signal.get("game_date"):
            signal["game_date"] = slate_date
        gid = game_id_of(signal)
        if gid and not signal.get("game_id"):
            signal["game_id"] = gid
    ids = [game_id_of(s) for s in signals]
    try:
        stored = _stored_ids(conn, ids) if conn is not None else {}
    except Exception as exc:                                   # noqa: BLE001
        logger.warning(f"score link lookup skipped ({type(exc).__name__})")
        stored = {}
    budget_end = time.monotonic() + _BUDGET_S
    for signal in signals:
        try:
            url = _resolve(signal, stored, fetch, budget_end)
        except Exception as exc:                               # noqa: BLE001
            logger.warning(f"score link skipped ({type(exc).__name__})")
            url = static_url(signal)
        if url and _allowed(url):
            signal["score_url"] = url
