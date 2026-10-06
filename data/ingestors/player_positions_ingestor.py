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
             and stats.nba.com blocks datacenter IPs.
  NCAAF      CFBD /roster. CFBD's athlete id is the id ncaaf_player_game_log
             already uses, so the join is exact. Needs CFBD_API_KEY, on the
             worker only.

ROSTER URL (measured worker_jobs 405765, 2026-10-06). The team list is
items[].$ref and returned 30 NBA / 17 WNBA teams. The constructed
`/teams/{id}/athletes` URL 404'd for every one of those teams, so that run
fetched no athlete docs. The roster is the team document's own `athletes`
$ref (season-scoped). Items there are $refs, or, when a payload already
carries id + name + position, the athlete doc is not fetched. A position
that is itself a $ref is fetched once per distinct URL and reused.

PLAYER IDS (load-bearing). The basketball logs key on the nba_api PLAYER_ID,
not ESPN's athlete id. Each ESPN athlete is mapped by normalised name
(norm_player_name), narrowed by team. The team rule compares log codes:
ESPN GS/NO/NY/SA/UTAH/WSH are GSW/NOP/NYK/SAS/UTA/WAS, and the WNBA map is
applied the same way. A unique name whose ESPN team is absent from that
player's log is `prior_season_team_change` when their latest game is older
than the current season start (NBA: October 1 of the ending-year season;
WNBA: January 1 of the calendar year). The NBA log ends 2026-04-12, so a
summer move would otherwise be stored unmatched for 7 days. The same
mismatch inside the current season is `team_conflict` and stays unmatched.
A name with no log row is `none` — a rookie does not inherit a veteran's
id. A name still shared after the team rule goes to the player with the
most recent game (Matt, 2026-10-06: "don't skip names"), counted as
tiebreak_recent. When the ESPN team matches nobody, that guess can be
another player's id. It is still returned, and the run will not let it
overwrite an id already claimed by a name, team, or prior-season match.
That collision, and any second claim of the same id, is duplicate_ids.

ESPN SEASON YEAR on the fallback roster path. NBA seasons are the ending
year (2026-10-06 is the 2026-27 season, ESPN 2027 — the same rule as
nba_stats_ingestor._nba_season_for_date). WNBA seasons are the calendar
year (wnba_stats_ingestor uses the date's year). The job's `season` argument
is the NCAAF roster year; it is not the basketball fallback year.

ONE SPORT PER JOB. A cold NBA pass is on the order of 1 team list + 30 team
docs + 30 roster lists + ~450 athlete docs + a handful of position docs
(about 520 HTTP calls). Both leagues in one invocation was the 1,000–2,000
call burst. The job rejects a list of sports; queue one job per sport.
`ingest_player_positions` still isolates a multi-sport call (its own cap,
its own rollback) so a direct caller cannot poison the next sport.

POLITENESS. ESPN has IP-blocked the worker twice; a third block also takes
out player news and WNBA results.
  * Cold pass (no athlete stored inside REFRESH_DAYS): pause 0.50s.
    A warm pass keeps 0.15s. Cache hits do not pause.
  * Hard cap REQUEST_CAP (750) HTTP calls per sport. The sport stops, logs
    a WARNING, and returns aborted_reason. It does not raise.
  * Three consecutive 403, 429, or 404 responses stop that sport the same
    way. 404 is in the streak because 405765 logged 47 of them and kept
    going. A 429 sleeps Retry-After (capped at 30s) and is tried once.
  * The dry run writes logs/player_positions_espn_cache.json (gitignored).
    The real run reads it and does not repeat those GETs. A new container
    has no file; the cap still bounds that pass. The file is a handoff, not
    the system of record — rows land in `player_positions`.

STEADY STATE, HONEST COUNT. Not "~45 calls".

  * Cold NBA, empty table, no cache file: about 520 HTTP calls (1 team
    list + 30 team docs + 30 roster lists + ~450 athlete docs + a handful
    of position docs). One sport, under the 750 cap. WNBA is the same
    shape with 17 teams.
  * Same worker, cache file still inside 7 days: team docs, roster lists,
    athlete docs and position docs are cache hits. Those URLs are not
    requested again. A new signing shows up when that roster entry expires.
  * New container (the file is gone) after a real run has stored rows:
    athletes whose source_athlete_id was written inside 7 days are not
    fetched. Matched players and unmatched athletes are both stored, so
    a miss is in that skip. The pass is still the team list + each team
    doc + each roster list — NBA about 61, WNBA about 35 — plus any
    athlete not stored. That is the steady state when the file does not
    survive a redeploy.

TEAM CODES. The NBA log spells GSW/NOP/NYK/SAS/UTA/WAS; ESPN spells
GS/NO/NY/SA/UTAH/WSH. The WNBA log spells CON/GSV/WAS (ESPN CONN/GS/WSH,
plus LVA/NYL/LAS/PHO) and, measured 2026-10-06, COOP and SPO: the
2026-07-25 all-star squads (game WNBA_2026-07-25_SPO_COOP, 11 players and
11 games each). Stored team is the log's code. A unique name whose history
does not contain that team is not a match — a rookie must not overwrite a
veteran who happens to be the only "John Smith" in the log.

COVERAGE. Current rosters miss waived, retired, and unsigned players. The
two-season log was 687 NBA players and 267 WNBA players on 2026-10-06.
The dry run reports player coverage and games-played coverage against that
log. NCAAF reads the requested season and the one before it (CFBD /roster
is per year); the default season is CFBD's fall-year rule, not
datetime.now().year, so a January run does not ask for next season.

Everything that is a row lands in Supabase `player_positions` (CLAUDE.md
§1b). An athlete we can read but cannot match is stored as
player_id `unmatched:{espn_id}`, source `espn_core_unmatched`, so the
7-day skip sees the source_athlete_id. A card must ignore that source.
The dry run writes none of those rows.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

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

#: An athlete stored this recently is not re-fetched. Same window as the
#: on-disk HTTP cache.
REFRESH_DAYS = 7
#: Pause between ESPN requests on a warm pass (seconds).
ESPN_PAUSE = 0.15
#: Pause on a cold pass — nothing in `player_positions` inside REFRESH_DAYS.
ESPN_PAUSE_COLD = 0.50
#: Hard HTTP cap per sport per run. A cold NBA pass is ~520; 750 finishes
#: one sport and stops a runaway before the second thousand calls.
REQUEST_CAP = 750
#: Consecutive 403 / 429 / 404 responses that stop the sport.
BLOCK_STREAK = 3
#: Retry-After is honoured up to this many seconds, then we give up the retry.
RETRY_AFTER_MAX = 30
#: How many sample rows a dry run reports.
SAMPLE = 8
#: player_id prefix for an athlete who parsed and did not match the log.
UNMATCHED_PREFIX = "unmatched:"

_ATHLETE_ID = re.compile(r"/athletes/(\d+)")
_TEAM_ID = re.compile(r"/teams/(\d+)")
_POS_TOKEN = re.compile(r"^[A-Z]{1,4}(-[A-Z]{1,4})?$")
_BLOCK_STATUSES = frozenset({403, 404, 429})

# ESPN abbreviation → the code the game log stores. NBA log measured
# 2026-10-06: GSW/NOP/NYK/SAS/UTA/WAS, never GS/NO/NY/SA/UTAH/WSH.
_NBA_TO_LOG = {
    "ATL": "ATL", "BOS": "BOS",
    "BKN": "BKN", "BRK": "BKN", "NJN": "BKN",
    "CHA": "CHA", "CHO": "CHA",
    "CHI": "CHI", "CLE": "CLE", "DAL": "DAL", "DEN": "DEN", "DET": "DET",
    "GSW": "GSW", "GS": "GSW",
    "HOU": "HOU", "IND": "IND", "LAC": "LAC", "LAL": "LAL", "MEM": "MEM",
    "MIA": "MIA", "MIL": "MIL", "MIN": "MIN",
    "NOP": "NOP", "NOH": "NOP", "NO": "NOP",
    "NYK": "NYK", "NY": "NYK",
    "OKC": "OKC", "ORL": "ORL", "PHI": "PHI",
    "PHX": "PHX", "PHO": "PHX",
    "POR": "POR", "SAC": "SAC",
    "SAS": "SAS", "SA": "SAS",
    "TOR": "TOR",
    "UTA": "UTA", "UTAH": "UTA",
    "WAS": "WAS", "WSH": "WAS",
}
# WNBA log codes include CON/GSV/WAS and the all-star squads COOP/SPO
# (WNBA_2026-07-25_SPO_COOP). ESPN's franchise spellings are on the left.
_WNBA_TO_LOG = {
    "ATL": "ATL", "CHI": "CHI",
    "CON": "CON", "CONN": "CON",
    "DAL": "DAL",
    "GSV": "GSV", "GS": "GSV",
    "IND": "IND",
    "LAS": "LA", "LA": "LA",
    "LVA": "LV", "LV": "LV", "VEG": "LV",
    "MIN": "MIN",
    "NYL": "NY", "NY": "NY",
    "PDX": "PDX",
    "PHO": "PHX", "PHX": "PHX",
    "SEA": "SEA", "TOR": "TOR",
    "WAS": "WAS", "WSH": "WAS",
    "COOP": "COOP", "SPO": "SPO",
}


def normalize_team(sport: str, abbrev: str | None) -> str | None:
    """Log team code for an ESPN (or log) abbreviation. None stays None."""
    if abbrev is None:
        return None
    raw = str(abbrev).strip().upper()
    if not raw:
        return None
    table = _WNBA_TO_LOG if str(sport).upper() == "WNBA" else _NBA_TO_LOG
    if str(sport).upper() == "NCAAF":
        return raw
    return table.get(raw, raw)


def default_cache_path() -> Path:
    env = os.environ.get("PLAYER_POSITIONS_CACHE")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "logs" / "player_positions_espn_cache.json"


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

def _https(url: str) -> str:
    if url.startswith("http://"):
        return "https://" + url[len("http://"):]
    return url


def _with_limit(url: str, limit: int = 200) -> str:
    """Force `limit`. A published $ref often carries limit=25, which would
    silently drop the back of a roster."""
    url = re.sub(r"([?&])limit=\d+", rf"\1limit={limit}", url)
    if "limit=" in url:
        return url
    joiner = "&" if "?" in url else "?"
    return f"{url}{joiner}limit={limit}"


def _link(doc: dict | None, key: str) -> str | None:
    if not isinstance(doc, dict):
        return None
    value = doc.get(key)
    if isinstance(value, str) and value:
        return value
    if isinstance(value, dict):
        ref = value.get("$ref")
        if ref:
            return str(ref)
    return None


def espn_basketball_season(sport: str, today: str) -> int:
    """ESPN core season year for `sport` on `today` (YYYY-MM-DD).

    NBA is the ending year: October–December belong to next year's season,
    so 2026-10-06 is 2027 (the 2026-27 season) and 2026-04-12 is 2026.
    WNBA is the calendar year of `today`.
    """
    year = int(today[:4])
    month = int(today[5:7])
    if str(sport).upper() == "WNBA":
        return year
    return year + 1 if month >= 10 else year


def basketball_season_start(sport: str, today: str) -> str:
    """First day of the season `today` falls in, YYYY-MM-DD.

    A unique-name team mismatch whose latest log game is strictly before
    this date is a prior-season move. NBA season start is October 1 before
    the ending year. WNBA season start is January 1 of the calendar year.
    """
    if str(sport).upper() == "WNBA":
        return f"{int(today[:4])}-01-01"
    return f"{espn_basketball_season('NBA', today) - 1}-10-01"


def roster_url(team_doc: dict | None, league: str, team_id: str,
               season: int) -> tuple[str, str]:
    """(url, via) for one team's roster.

    `via` is `team_ref` when the team document published an athletes or
    roster link, else `season_path`. Never `/teams/{id}/athletes` without
    a season: that path 404'd for every team in worker_jobs 405765.
    """
    ref = _link(team_doc, "athletes") or _link(team_doc, "roster")
    if ref:
        return _with_limit(_https(ref)), "team_ref"
    url = (f"{CORE}/{league}/seasons/{int(season)}/teams/{team_id}"
           f"/athletes?limit=200")
    return url, "season_path"


def _retry_after_seconds(headers) -> float:
    raw = None
    if headers:
        raw = headers.get("Retry-After") or headers.get("retry-after")
    try:
        seconds = float(raw)
    except (TypeError, ValueError):
        seconds = 2.0
    if seconds < 0:
        seconds = 0.0
    return min(seconds, RETRY_AFTER_MAX)


class EspnClient:
    """One sport's HTTP session: cap, block streak, and a URL cache.

    `docs` is url → body already in hand (the on-disk cache, or a test
    fixture). A hit is not a request and does not sleep.
    """

    def __init__(self, *, cold: bool = True, cap: int = REQUEST_CAP,
                 pause: float | None = None, get=None, sleep=None,
                 docs: dict | None = None):
        self.pause = ESPN_PAUSE_COLD if cold else ESPN_PAUSE
        if pause is not None:
            self.pause = pause
        self.cap = cap
        self.calls = 0
        self.cache_hits = 0
        self.consecutive_block = 0
        self.aborted_reason: str | None = None
        self.mem: dict[str, dict] = {}
        for url, body in (docs or {}).items():
            if isinstance(body, dict):
                self.mem[_https(url)] = body
        self.fetched: set[str] = set()
        self._get = get or requests.get
        self._sleep = sleep or time.sleep

    def _abort(self, reason: str) -> None:
        if self.aborted_reason:
            return
        self.aborted_reason = reason
        logger.warning(f"ESPN player positions: {reason}")

    def _attempt(self, url: str):
        """One HTTP GET, counted against the cap. None when the cap is spent
        or the socket fails. The politeness pause runs either way."""
        if self.aborted_reason:
            return None
        if self.calls >= self.cap:
            self._abort(f"request cap {self.cap} reached")
            return None
        self.calls += 1
        try:
            resp = self._get(url, headers=ESPN_HEADERS, timeout=15)
        except Exception as exc:                                  # noqa: BLE001
            logger.warning(f"ESPN fetch failed {url}: {exc}")
            self._sleep(self.pause)
            return None
        self._sleep(self.pause)
        return resp

    def _note_status(self, status: int, url: str) -> None:
        if status == 200:
            self.consecutive_block = 0
            return
        logger.warning(f"ESPN {status} for {url}")
        if status not in _BLOCK_STATUSES:
            return
        self.consecutive_block += 1
        if self.consecutive_block >= BLOCK_STREAK:
            self._abort(
                f"stopped after {self.consecutive_block} consecutive HTTP {status}"
            )

    def get_json(self, url: str) -> dict | None:
        """JSON object for `url`, or None. Stops the sport on cap or streak.

        A 429 sleeps Retry-After (max 30s) and is tried once more. The retry
        counts toward the cap. Position documents and team documents share
        this cache, so a repeated $ref is one call.
        """
        url = _https(url)
        if url in self.mem:
            self.cache_hits += 1
            return self.mem[url]
        if self.aborted_reason:
            return None
        resp = self._attempt(url)
        if resp is None:
            return None
        status = getattr(resp, "status_code", 0)
        if status == 429 and not self.aborted_reason:
            wait = _retry_after_seconds(getattr(resp, "headers", {}) or {})
            logger.warning(f"ESPN 429 for {url}; sleeping {wait}s (Retry-After)")
            self._sleep(wait)
            resp = self._attempt(url)
            if resp is None:
                self._note_status(429, url)
                return None
            status = getattr(resp, "status_code", 0)
        if status != 200:
            self._note_status(status, url)
            return None
        self.consecutive_block = 0
        try:
            body = resp.json()
        except Exception as exc:                                  # noqa: BLE001
            logger.warning(f"ESPN JSON failed {url}: {exc}")
            return None
        if not isinstance(body, dict):
            logger.warning(f"ESPN JSON for {url} was not an object")
            return None
        self.mem[url] = body
        self.fetched.add(url)
        return body


def _read_cache(path: Path | None) -> dict:
    """HTTP bodies only. An older file may still carry `unmatched`; it is
    not a skip list (the 7-day skip is the `player_positions` row)."""
    empty = {"docs": {}}
    if path is None or not path.exists():
        return empty
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning(f"player positions cache unreadable ({exc})")
        return empty
    if not isinstance(data, dict):
        return empty
    docs = data.get("docs") if isinstance(data.get("docs"), dict) else {}
    return {"docs": docs}


def _fresh_docs(path: Path | None, now: datetime | None = None) -> dict:
    """url → body for cache entries newer than REFRESH_DAYS."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=REFRESH_DAYS)
    out = {}
    for url, entry in _read_cache(path)["docs"].items():
        if not isinstance(entry, dict):
            continue
        body = entry.get("body")
        stamp = entry.get("at")
        if not isinstance(body, dict) or not stamp:
            continue
        try:
            at = datetime.fromisoformat(str(stamp))
        except ValueError:
            continue
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        if at >= cutoff:
            out[_https(str(url))] = body
    return out


def _write_cache(path: Path | None, client: EspnClient) -> None:
    """Persist bodies fetched this run. Hits keep the timestamp they had."""
    if path is None:
        return
    previous = _read_cache(path)
    now = datetime.now(timezone.utc).isoformat()
    docs = {}
    old = previous["docs"]
    for url, body in client.mem.items():
        if not isinstance(body, dict):
            continue
        if url in client.fetched or url not in old:
            docs[url] = {"at": now, "body": body}
        else:
            docs[url] = old[url]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps({"docs": docs}), encoding="utf-8")
    tmp.replace(path)


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


def _position_abbrev(pos, client: EspnClient | None) -> str | None:
    """Abbreviation from an inline position, a short string, or a cached $ref."""
    if isinstance(pos, str):
        token = pos.strip().upper()
        return token if _POS_TOKEN.match(token) else None
    if not isinstance(pos, dict):
        return None
    abbrev = pos.get("abbreviation") or pos.get("displayName") or pos.get("name")
    if abbrev and not (isinstance(abbrev, str) and abbrev.startswith("http")):
        # displayName "Point Guard" is not an abbreviation; prefer abbreviation
        # and only accept a name when it looks like a token (or abbreviation
        # was missing and the name is the short form).
        if pos.get("abbreviation"):
            return str(pos.get("abbreviation")).strip().upper()
        token = str(abbrev).strip().upper()
        if _POS_TOKEN.match(token):
            return token
    ref = pos.get("$ref")
    if not ref or client is None:
        return None
    doc = client.get_json(_https(str(ref)))
    if not isinstance(doc, dict):
        return None
    got = doc.get("abbreviation") or doc.get("displayName")
    if not got:
        return None
    token = str(got).strip().upper()
    return token if _POS_TOKEN.match(token) or doc.get("abbreviation") else None


def iter_roster_items(doc: dict | None):
    """Athlete-shaped dicts from a roster payload.

    Accepts the core collection (`items` of $refs or expanded athletes),
    the site roster (`athletes[].items[]`, position often on the group),
    and a game roster (`entries[].athlete`). An empty or unexpected
    document yields nothing.
    """
    if not isinstance(doc, dict):
        return
    items = doc.get("items")
    if isinstance(items, list):
        yield from items
        return
    athletes = doc.get("athletes")
    if isinstance(athletes, list):
        for group in athletes:
            if isinstance(group, dict) and isinstance(group.get("items"), list):
                for ath in group["items"]:
                    if (isinstance(ath, dict) and not ath.get("position")
                            and group.get("position")):
                        ath = {**ath, "position": group["position"]}
                    yield ath
            else:
                yield group
        return
    entries = doc.get("entries")
    if isinstance(entries, list):
        for entry in entries:
            if isinstance(entry, dict) and isinstance(entry.get("athlete"), dict):
                yield entry["athlete"]
            else:
                yield entry


def resolve_person(item, client: EspnClient) -> tuple[dict | None, bool]:
    """(parsed athlete, athlete_doc_was_requested).

    When the roster item already has an id, a name, and a position, the
    athlete document is not requested. A position $ref is still resolved,
    through the client's cache. The flag is True only when this call caused
    an HTTP attempt for the athlete document (a cache hit does not).
    """
    if isinstance(item, str):
        item = {"$ref": item}
    if not isinstance(item, dict):
        return None, False
    parsed = _person_from_doc(item, client)
    if parsed:
        return parsed, False
    ref = item.get("$ref")
    if not ref or client.aborted_reason:
        return None, False
    before = client.calls
    adoc = client.get_json(str(ref))
    did_http = client.calls > before
    if not isinstance(adoc, dict):
        return None, did_http
    return _person_from_doc(adoc, client), did_http


def _person_from_doc(doc: dict, client: EspnClient | None) -> dict | None:
    if not isinstance(doc, dict):
        return None
    espn_id = str(doc.get("id") or "").strip()
    name = doc.get("displayName") or doc.get("fullName")
    if not espn_id or not name:
        return None
    abbrev = _position_abbrev(doc.get("position"), client)
    if not abbrev:
        return None
    return {"espn_id": espn_id, "name": str(name), "position": abbrev}


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


def _candidate(cand, sport: str) -> tuple[str, set[str], str]:
    """(player_id, normalised team codes, latest game date) from an index entry.

    Shapes the callers build:
      (player_id, latest_team)
      (player_id, latest_team, all_teams)          all_teams is a list
      (player_id, latest_team, latest_game_date)   the date is a string
      (player_id, latest_team, all_teams, latest_game_date)
    A 2-tuple's latest team is the whole history, which is what the unit
    tests build. The date is "" when the entry has none, so it loses a
    most-recent tiebreak.
    """
    pid = str(cand[0])
    latest = cand[1] if len(cand) > 1 else None
    third = cand[2] if len(cand) > 2 else None
    fourth = cand[3] if len(cand) > 3 else None
    teams: set[str] = set()
    gdate = ""
    if isinstance(third, (list, tuple, set)):
        for team in third:
            code = normalize_team(sport, team)
            if code:
                teams.add(code)
        if fourth:
            gdate = str(fourth)
    elif third:
        gdate = str(third)
    code = normalize_team(sport, latest)
    if code:
        teams.add(code)
    return pid, teams, gdate


def _before_season(gdate: str, season_start: str) -> bool:
    """True when `gdate` is a real date strictly before `season_start`.

    Both are compared on their first 10 characters, so a timestamp and a
    date share the ISO day. An empty date is not a prior season.
    """
    day = str(gdate)[:10]
    start = str(season_start)[:10]
    if len(day) < 10 or len(start) < 10:
        return False
    return day < start


def match_to_log(name: str, team: str | None, index: dict,
                 how: dict | None = None, *, sport: str = "NBA",
                 as_of: str | None = None) -> str | None:
    """Our player_id for an ESPN athlete, by normalised name.

    `index` maps norm_name -> candidate tuples (see `_candidate`). A unique
    name matches when we have no ESPN team, the log has no team, or the
    ESPN team (after normalisation) appears in that player's history.
    A unique name on a different team is `prior_season_team_change` when
    `as_of` is set and their latest log game is older than this season's
    start, and `team_conflict` (no id) when the mismatch is inside the
    current season or the game date is missing. No log row at all is
    `none`: a rookie does not inherit a veteran's id.

    A shared name is settled by the team check. One still shared after
    that, or a team that matches nobody, goes to the candidate with the
    most recent game (Matt, 2026-10-06: "don't skip names").
    `how["method"]` records which rule decided.

    A tiebreak_recent result is a guess when the ESPN team matched nobody.
    The caller must not let that guess overwrite an id already claimed by
    a name, team, or prior-season match in the same run.
    """
    def _set(m: str) -> None:
        if isinstance(how, dict):
            how["method"] = m

    cands = index.get(norm_player_name(name)) or []
    by_id: dict[str, tuple[set[str], str]] = {}
    for pid, teams, gdate in (_candidate(c, sport) for c in cands):
        prev = by_id.get(pid)
        if prev is None:
            by_id[pid] = (set(teams), gdate)
            continue
        prev[0].update(teams)
        if gdate > prev[1]:
            by_id[pid] = (prev[0], gdate)
    if not by_id:
        _set("none")
        return None
    espn = normalize_team(sport, team)
    if len(by_id) == 1:
        pid, (teams, gdate) = next(iter(by_id.items()))
        if espn is None or not teams or espn in teams:
            _set("name")
            return pid
        if as_of and _before_season(gdate, basketball_season_start(sport, as_of)):
            _set("prior_season_team_change")
            return pid
        _set("team_conflict")
        return None
    if espn:
        on_team = {pid: info for pid, info in by_id.items() if espn in info[0]}
        if len(on_team) == 1:
            _set("team")
            return next(iter(on_team))
        if len(on_team) > 1:
            _set("tiebreak_recent")
            return max(on_team, key=lambda pid: on_team[pid][1])
    _set("tiebreak_recent")
    return max(by_id, key=lambda pid: by_id[pid][1])


def coverage_from_games(games_by_player: dict, matched_ids) -> dict:
    """Player-count coverage and games-played coverage.

    `games_by_player` is player_id → games in the log window. `matched_ids`
    is whoever we found a position for. Ratios are None when the log is empty.
    """
    players = len(games_by_player)
    games = int(sum(games_by_player.values()))
    have = {str(pid) for pid in matched_ids if str(pid) in games_by_player}
    games_have = int(sum(games_by_player[pid] for pid in have))
    return {
        "log_players": players,
        "log_games": games,
        "players_with_position": len(have),
        "games_with_position": games_have,
        "player_coverage": round(len(have) / players, 4) if players else None,
        "games_coverage": round(games_have / games, 4) if games else None,
    }


# ── DB ───────────────────────────────────────────────────────────────────────

def _rollback(conn) -> None:
    try:
        conn.rollback()
    except Exception as exc:                                      # noqa: BLE001
        logger.warning(f"player positions rollback failed: {exc}")


def _log_players(conn, sport: str) -> list:
    """One row per player over the last two seasons: id, name, latest team,
    games, every team, latest game date. The table name is the fixed
    LOG_TABLE value. The date is what the shared-name tiebreak sorts on."""
    table = LOG_TABLE[sport]
    return conn.execute(f"""
        SELECT player_id::text,
               (ARRAY_AGG(player_name ORDER BY game_date DESC))[1],
               (ARRAY_AGG(team ORDER BY game_date DESC))[1],
               COUNT(*)::int,
               ARRAY_AGG(DISTINCT team),
               MAX(game_date)
        FROM {table}
        WHERE season >= (SELECT max(season) - 1 FROM {table})
        GROUP BY player_id
    """).fetchall()


def _index_from_rows(rows, sport: str) -> tuple[dict, dict, dict]:
    """(name index, games by id, latest log team by id).

    A row is (id, name, team, games, teams, latest_date) from `_log_players`.
    A 5-tuple (no date) is the same row from a test fixture.
    """
    index: dict[str, list] = {}
    games: dict[str, int] = {}
    latest: dict[str, str | None] = {}
    for row in rows:
        if len(row) >= 6:
            pid, name, team, n_games, teams, gdate = row[:6]
        else:
            pid, name, team, n_games, teams = row[:5]
            gdate = None
        pid = str(pid)
        games[pid] = int(n_games or 0)
        latest[pid] = normalize_team(sport, team)
        hist = [t for t in (teams or []) if t]
        index.setdefault(norm_player_name(name), []).append(
            (pid, team, hist, str(gdate) if gdate else ""))
    return index, games, latest


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
    # A prior run may have stored this espn id as unmatched:{id}. Drop that
    # sentinel in the same transaction as the real row, or the 7-day skip
    # keeps hiding a player we can now match.
    seen: set[tuple[str, str]] = set()
    for r in rows:
        if r.get("source") == "espn_core_unmatched":
            continue
        espn_id = r.get("source_athlete_id")
        if not espn_id:
            continue
        key = (r["sport"], str(espn_id))
        if key in seen:
            continue
        seen.add(key)
        conn.execute("""
            DELETE FROM player_positions
            WHERE sport = %s
              AND player_id = %s
              AND source = 'espn_core_unmatched'
        """, (r["sport"], UNMATCHED_PREFIX + str(espn_id)))
    conn.commit()
    return len(rows)


# ── basketball ───────────────────────────────────────────────────────────────

def _empty_basketball_stats() -> dict:
    return {
        "teams": 0, "athletes_listed": 0, "athletes_fetched": 0,
        "athletes_inline": 0, "skipped_fresh": 0, "unparsed": 0,
        "matched": 0, "unmatched": 0, "duplicate_ids": 0, "no_group": 0,
        "match_method": {}, "tiebreak_sample": [],
        "positions": {}, "sample": [], "unmatched_sample": [],
        "teams_seen": [], "roster_via": {}, "requests": 0, "cache_hits": 0,
        "aborted_reason": None, "coverage": None, "written": 0,
        "prior_season_team_change": 0, "team_conflict": 0,
        "espn_season": None,
    }


def _basketball(conn, sport: str, dry_run: bool, *, season: int | None = None,
                as_of: str | None = None,
                client: EspnClient | None = None,
                cache_path: Path | None = None) -> dict:
    league = LEAGUE_OF[sport]
    as_of = as_of or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    espn_season = int(season) if season is not None else espn_basketball_season(sport, as_of)
    rows = _log_players(conn, sport)
    index, games, latest = _index_from_rows(rows, sport)
    fresh = set() if dry_run else _fresh_source_ids(conn, sport)
    if client is None:
        client = EspnClient(cold=not fresh, docs=_fresh_docs(cache_path))
    stats = _empty_basketball_stats()
    stats["log_players_last_2_seasons"] = len(games)
    stats["espn_season"] = espn_season
    out: list[dict] = []
    unmatched_rows: list[dict] = []
    seen: set[str] = set()
    # player_id -> the method that currently owns the row in `out`.
    # A tiebreak guess must not be the row that _upsert's ON CONFLICT keeps
    # when a name, team, or prior-season match for that id also happened.
    claimed: dict[str, str] = {}
    row_at: dict[str, int] = {}

    teams = []
    listing = client.get_json(f"{CORE}/{league}/teams?limit=50")
    if isinstance(listing, dict):
        for it in listing.get("items") or []:
            ref = it if isinstance(it, str) else (it or {}).get("$ref") if isinstance(it, dict) else None
            if ref:
                teams.append(str(ref))
    stats["teams"] = len(teams)

    for tref in teams:
        if client.aborted_reason:
            break
        tdoc = client.get_json(tref) or {}
        found = _TEAM_ID.search(_https(tref))
        if not found:
            continue
        team_id = found.group(1)
        raw_abbrev = tdoc.get("abbreviation")
        log_team = normalize_team(sport, raw_abbrev)
        if len(stats["teams_seen"]) < 40:
            stats["teams_seen"].append({
                "espn_id": team_id, "espn": raw_abbrev, "log": log_team,
            })
        url, via = roster_url(tdoc, league, team_id, espn_season)
        stats["roster_via"][via] = stats["roster_via"].get(via, 0) + 1
        if client.aborted_reason:
            break
        roster = client.get_json(url)
        if isinstance(roster, dict):
            listed = roster.get("items") if isinstance(roster.get("items"), list) else None
            count = roster.get("count")
            if isinstance(count, int) and listed is not None and count > len(listed):
                stats["roster_truncated"] = stats.get("roster_truncated", 0) + 1
        for item in iter_roster_items(roster):
            if client.aborted_reason:
                break
            stats["athletes_listed"] += 1
            ref = item.get("$ref") if isinstance(item, dict) else (
                item if isinstance(item, str) else None)
            am = _ATHLETE_ID.search(str(ref or ""))
            inline_id = ""
            if isinstance(item, dict) and item.get("id"):
                inline_id = str(item.get("id"))
            source_id = (am.group(1) if am else "") or inline_id
            if source_id and source_id in fresh:
                stats["skipped_fresh"] += 1
                continue
            person, fetched = resolve_person(item, client)
            if fetched:
                stats["athletes_fetched"] += 1
            elif person:
                stats["athletes_inline"] += 1
            if not person:
                stats["unparsed"] += 1
                if (len(stats["unmatched_sample"]) < SAMPLE
                        and isinstance(item, dict) and not item.get("$ref")):
                    stats["unmatched_sample"].append(
                        {"unparsed_keys": sorted(str(k) for k in item.keys())[:20],
                         "position": item.get("position")})
                continue
            stats["positions"][person["position"]] = (
                stats["positions"].get(person["position"], 0) + 1)
            how: dict = {}
            pid = match_to_log(person["name"], raw_abbrev, index, how,
                               sport=sport, as_of=as_of)
            method = how.get("method", "none")
            stats["match_method"][method] = stats["match_method"].get(method, 0) + 1
            if method == "tiebreak_recent" and len(stats["tiebreak_sample"]) < SAMPLE:
                stats["tiebreak_sample"].append({
                    "name": person["name"], "team": raw_abbrev, "player_id": pid,
                })
            grp = basketball_group(person["position"])
            if pid is None:
                stats["unmatched"] += 1
                if len(stats["unmatched_sample"]) < SAMPLE:
                    stats["unmatched_sample"].append(
                        {"name": person["name"], "team": log_team,
                         "espn_team": raw_abbrev})
                sentinel = UNMATCHED_PREFIX + person["espn_id"]
                unmatched_rows.append({
                    "sport": sport, "player_id": sentinel,
                    "player_name": person["name"], "team": log_team,
                    "position": person["position"], "pos_group": grp,
                    "source": "espn_core_unmatched",
                    "source_athlete_id": person["espn_id"],
                })
                continue
            if grp is None:
                stats["no_group"] += 1
            stored_team = latest.get(pid) or log_team
            row = {"sport": sport, "player_id": pid, "player_name": person["name"],
                   "team": stored_team, "position": person["position"],
                   "pos_group": grp, "source": "espn_core",
                   "source_athlete_id": person["espn_id"]}
            prior = claimed.get(pid)
            if prior is not None:
                # ON CONFLICT (sport, player_id) would let whichever row is
                # inserted last win. A tiebreak guess must not be that row
                # when a name, team, or prior-season match already owns the
                # id, and a later one of those replaces a guess so the guess
                # does not stick. Either way the collision is counted.
                stats["duplicate_ids"] += 1
                if method == "tiebreak_recent" or prior != "tiebreak_recent":
                    continue
                claimed[pid] = method
                out[row_at[pid]] = row
                for i, existing in enumerate(stats["sample"]):
                    if existing.get("player_id") == pid:
                        stats["sample"][i] = row
                        break
                continue
            claimed[pid] = method
            seen.add(pid)
            stats["matched"] += 1
            row_at[pid] = len(out)
            out.append(row)
            if len(stats["sample"]) < SAMPLE:
                stats["sample"].append(row)
    stats["coverage"] = coverage_from_games(games, seen)
    stats["requests"] = client.calls
    stats["cache_hits"] = client.cache_hits
    stats["aborted_reason"] = client.aborted_reason
    stats["prior_season_team_change"] = stats["match_method"].get(
        "prior_season_team_change", 0)
    stats["team_conflict"] = stats["match_method"].get("team_conflict", 0)
    if dry_run:
        stats["written"] = 0
    else:
        stats["written"] = _upsert(conn, out + unmatched_rows)
    _write_cache(cache_path, client)
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


def ncaaf_season_or_derived(season: int | None, today: str | None = None) -> int:
    """Explicit season, otherwise CFBD's fall-year label for `today`.

    January and February belong to the prior season. `datetime.now().year`
    in January would ask CFBD for a roster that does not exist yet.
    """
    if season:
        return int(season)
    from data.ingestors.cfbd_ingestor import ncaaf_season_for_date
    if today is None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return ncaaf_season_for_date(today)


def _ncaaf_log(conn, seasons: list[int]) -> dict[str, int]:
    rows = conn.execute("""
        SELECT player_id::text, COUNT(*)::int
        FROM ncaaf_player_game_log
        WHERE season = ANY(%s)
        GROUP BY player_id
    """, (list(seasons),)).fetchall()
    return {str(pid): int(n or 0) for pid, n in rows}


def _ncaaf(conn, season: int, dry_run: bool) -> dict:
    from data.ingestors.cfbd_ingestor import _get
    # Older roster first so the requested season's position wins.
    seasons = [int(season) - 1, int(season)]
    by_id: dict[str, dict] = {}
    for year in seasons:
        for row in parse_cfbd_roster(_get("/roster", year=year)):
            by_id[row["player_id"]] = row
    games = _ncaaf_log(conn, seasons)
    stats = {
        "season": int(season), "seasons": seasons,
        "roster_rows": len(by_id), "log_players": len(games),
        "matched": 0, "positions": {}, "sample": [],
        "aborted_reason": None,
    }
    out = []
    matched_ids = []
    for r in by_id.values():
        stats["positions"][r["position"]] = stats["positions"].get(r["position"], 0) + 1
        if r["player_id"] not in games:
            continue
        stats["matched"] += 1
        matched_ids.append(r["player_id"])
        row = {"sport": "NCAAF", "player_id": r["player_id"], "player_name": r["name"],
               "team": r["team"], "position": r["position"],
               "pos_group": FOOTBALL_GROUP.get(r["position"]),
               "source": "cfbd_roster", "source_athlete_id": r["player_id"]}
        out.append(row)
        if len(stats["sample"]) < SAMPLE:
            stats["sample"].append(row)
    stats["log_players_with_position"] = stats["matched"]
    stats["coverage"] = coverage_from_games(games, matched_ids)
    stats["written"] = 0 if dry_run else _upsert(conn, out)
    return stats


# ── entry point ──────────────────────────────────────────────────────────────

def ingest_player_positions(sports=None, season: int | None = None,
                            dry_run: bool = False, *, conn=None,
                            client_factory=None,
                            cache_path: Path | None = None) -> dict:
    """Fetch and store positions. Returns a per-sport summary for the job card.

    Default sport is NBA — one sport per call. Pass `sports` to run several;
    each sport has its own request cap and a failed sport rollbacks so the
    next one still runs. `season` is the NCAAF roster year. The basketball
    fallback roster path uses `espn_basketball_season`, not this year.
    The job passes one sport.
    """
    own_conn = conn is None
    if conn is None:
        from data.db import get_connection
        conn = get_connection()
    if cache_path is None and client_factory is None:
        cache_path = default_cache_path()
    sports = [s.upper() for s in (sports or ["NBA"])]
    ncaaf_season = ncaaf_season_or_derived(season)
    summary: dict = {"dry_run": dry_run, "ncaaf_season": ncaaf_season}
    try:
        for sport in sports:
            try:
                if sport in LEAGUE_OF:
                    client = None
                    if client_factory is not None:
                        client = client_factory(sport)
                    summary[sport] = _basketball(
                        conn, sport, dry_run, client=client,
                        cache_path=cache_path)
                elif sport == "NCAAF":
                    summary[sport] = _ncaaf(conn, ncaaf_season, dry_run)
                else:
                    summary[sport] = {"error": f"unknown sport {sport}"}
            except Exception as exc:                              # noqa: BLE001
                logger.exception(f"player positions {sport} failed")
                summary[sport] = {"error": str(exc)[:300]}
                _rollback(conn)
    finally:
        if own_conn:
            conn.close()
    logger.info(f"player positions: {summary}")
    return summary
