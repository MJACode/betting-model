"""NCAAB pre-tip injury feed. Tags only. Not a model feature.

Sources, in the order the task names them:
  * RotoWire's public injury-report JSON, primary:
    https://www.rotowire.com/cbasketball/tables/injury-report.php?team=ALL&pos=ALL
  * Covers' public injury HTML, fallback:
    https://www.covers.com/sport/basketball/ncaab/injuries

Neither page carries a status-change time. received_at is when this server
stored the poll. RotoWire is polled about every 10 minutes, and every 5
minutes while an NCAAB game tips within three hours. Covers is polled about
every 30 minutes. HTTP 403 and 429 back off (10 minutes, doubling, capped at
2 hours). A poll that errors exits non-zero. On a game day a zero-player
report exits non-zero only when that source is the one the tags are using:
RotoWire when it just listed players or is still healthy, otherwise Covers.
An empty Covers poll while RotoWire supplies the tags is a warning, not an
alert. A zero-player poll does not clear anyone.

Storage:
  * ncaab_injury_changes — one row per status change, including status
    'cleared' when a player leaves a non-empty report.
  * ncaab_injury_open — the report just stored, the state the next diff reads.
  * injury_status_current — sport NCAAB, absences only, replaced from the
    source we are willing to trust (RotoWire when it just returned players,
    otherwise Covers when RotoWire is not healthy). The Stats board already
    reads this table.

Names go through data.ingestors.ncaab_teams.resolve_team_name and
data.ingestors.ncaab_sdv_import.player_key, then the override maps in
config.NCAAB_INJURY_TEAM_MAP and config.NCAAB_INJURY_PLAYER_MAP. A team that
does not resolve, and a player key the roster does not hold, is logged in
ncaab_injury_misses. Nothing is assigned by shortening, fuzzy match, or
picking one of two teams.

injury_tags_before_tip reads the change log at or before tip for display
tags. models/ does not import this module, and this module does not write a
pick, a stake, or a feature.

    python -m scripts.ncaab_injury_feed
"""
from __future__ import annotations

import html
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import requests
from loguru import logger

import config
from data.anon_readable import API_ROLES, lock_down
from data.ingestors.ncaab_teams import (load_registry, ncaab_season_label,
                                        resolve_team_name)

ET_NAME = "America/New_York"
ROTOWIRE_URL = (
    "https://www.rotowire.com/cbasketball/tables/injury-report.php?team=ALL&pos=ALL"
)
COVERS_URL = "https://www.covers.com/sport/basketball/ncaab/injuries"
SOURCES = ("rotowire", "covers")
SPORT = "NCAAB"

ROTOWIRE_EVERY = timedelta(minutes=10)
ROTOWIRE_NEAR = timedelta(minutes=5)
COVERS_EVERY = timedelta(minutes=30)
NEAR_TIP = timedelta(hours=3)
ROTOWIRE_FRESH = timedelta(minutes=20)
BACKOFF_CAP = timedelta(hours=2)
BACKOFF_BASE = timedelta(minutes=10)
BACKOFF_STATUSES = frozenset({403, 429})

STATUS_CLEARED = "cleared"
ABSENCE_STATUSES = frozenset({"Out", "Doubtful", "Questionable", "Day-To-Day"})
_STATUS_RANK = {
    "Out": 0, "Doubtful": 1, "Questionable": 2, "Day-To-Day": 3, "Probable": 4,
}
_TAG = {"Out": "O", "Doubtful": "D", "Questionable": "Q", "Day-To-Day": "DTD"}

MIGRATION_NAME = "add_ncaab_injury_changes_2026_10_30.sql"
_TABLES = (
    "ncaab_injury_changes",
    "ncaab_injury_open",
    "ncaab_injury_polls",
    "ncaab_injury_misses",
)
_CHANGE_COLUMNS = (
    "change_id", "source", "received_at", "team_raw", "player_raw",
    "espn_team_id", "team", "player_key", "player_id", "status", "injury_type",
    "note", "return_date", "vendor_player_id", "match_status",
)
_OPEN_COLUMNS = (
    "source", "team_raw", "player_raw", "espn_team_id", "team", "player_key",
    "player_id", "status", "injury_type", "note", "return_date",
    "vendor_player_id", "match_status", "received_at",
)
_POLL_COLUMNS = (
    "source", "last_attempt_at", "last_success_at", "last_status_code",
    "last_row_count", "backoff_until", "consecutive_failures", "last_error",
)
_MISS_COLUMNS = (
    "source", "team_raw", "player_raw", "reason", "last_seen", "detail",
)
_CHANGE_INDEX = "idx_ncaab_injury_changes_player_ts"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
}

_STATUS_WORDS = {
    "out": "Out",
    "o": "Out",
    "out for season": "Out",
    "out for the season": "Out",
    "out indefinitely": "Out",
    "doubtful": "Doubtful",
    "d": "Doubtful",
    "questionable": "Questionable",
    "q": "Questionable",
    "game time decision": "Questionable",
    "gtd": "Questionable",
    "day to day": "Day-To-Day",
    "day-to-day": "Day-To-Day",
    "dtd": "Day-To-Day",
    "probable": "Probable",
    "p": "Probable",
    "suspension": "Out",
    "suspended": "Out",
    "susp": "Out",
    "ir": "Out",
    "injured reserve": "Out",
    "transfer portal": "Out",
}
_INJURY_FOR_WORD = {
    "suspension": "Suspension",
    "suspended": "Suspension",
    "susp": "Suspension",
    "ir": "Injured Reserve",
    "injured reserve": "Injured Reserve",
    "transfer portal": "Transfer Portal",
}


class ParseError(ValueError):
    """The page answered but is not the report shape. Not a zero-row report."""


@dataclass
class Listing:
    source: str
    team_raw: str
    team_query: str
    player_raw: str
    status: str
    injury_type: str | None
    note: str | None
    return_date: str | None
    vendor_player_id: str | None


@dataclass
class PollState:
    source: str
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    last_status_code: int | None = None
    last_row_count: int | None = None
    backoff_until: datetime | None = None
    consecutive_failures: int = 0
    last_error: str | None = None


@dataclass
class FetchResult:
    status: int | None
    body: str
    error: str | None


@dataclass
class TickResult:
    alerts: list[str] = field(default_factory=list)
    polled: list[str] = field(default_factory=list)
    changes: int = 0
    misses: int = 0

    @property
    def ok(self) -> bool:
        return not self.alerts


def enabled() -> bool:
    """RUN_NCAAB_INJURY=0 stops the tick. Default on. Not a model pause."""
    return os.environ.get("RUN_NCAAB_INJURY", "1").strip().lower() not in {
        "0", "false", "off", "no",
    }


def _aware(value) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _text(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment or "")).split())


def _status_phrase(phrase: str) -> tuple[str, str | None]:
    """(canonical or the printed phrase, injury label the phrase itself names).

    An unknown word is stored as printed. It is not mapped to Out.
    """
    raw = " ".join((phrase or "").split())
    key = raw.lower().replace("-", " ")
    key = " ".join(key.split())
    hyphen = raw.lower()
    canon = _STATUS_WORDS.get(key) or _STATUS_WORDS.get(hyphen)
    injury = _INJURY_FOR_WORD.get(key) or _INJURY_FOR_WORD.get(hyphen)
    if canon is None:
        return raw, injury
    return canon, injury


def classify_status(phrase: str, injury: str | None) -> tuple[str, str | None]:
    canon, implied = _status_phrase(phrase)
    body = (injury or "").strip() or None
    if body is None:
        body = implied
    return canon, body


def _return_text(value: str | None) -> str | None:
    text = _text(value or "")
    if not text:
        return None
    if "subscriber" in text.lower() or "<" in (value or ""):
        return None
    return text


def parse_rotowire(payload: str | list) -> list[Listing]:
    """The injury-report JSON array. A non-array is a parse error, not zero rows."""
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ParseError("rotowire body is not JSON") from exc
    else:
        data = payload
    if not isinstance(data, list):
        raise ParseError("rotowire JSON is not a list")
    out: list[Listing] = []
    for obj in data:
        if not isinstance(obj, dict):
            continue
        player = _text(str(obj.get("player") or ""))
        if not player:
            player = _text(f"{obj.get('firstname') or ''} {obj.get('lastname') or ''}")
        team = _text(str(obj.get("team") or ""))
        if not player or not team:
            continue
        status, injury = classify_status(str(obj.get("status") or ""), str(obj.get("injury") or ""))
        if not status:
            continue
        vid = obj.get("ID")
        out.append(Listing(
            source="rotowire",
            team_raw=team,
            team_query=team,
            player_raw=player,
            status=status,
            injury_type=injury,
            note=None,
            return_date=_return_text(None if obj.get("rDate") is None else str(obj.get("rDate"))),
            vendor_player_id=str(vid) if vid not in (None, "") else None,
        ))
    return out


def parse_covers(page: str) -> list[Listing]:
    """Covers team blocks. Zero player rows is a real empty report.

    A page with no team block is a parse error: the live page is one block
    per school, including schools with nobody listed.
    """
    if "covers-CoversSeasonInjuries-blockContainer" not in (page or ""):
        raise ParseError("covers page has no team blocks")
    blocks = page.split("covers-CoversSeasonInjuries-blockContainer")[1:]
    out: list[Listing] = []
    for block in blocks:
        team = _covers_team(block)
        if team is None:
            continue
        school, mascot = team
        query = f"{school} {mascot}".strip() if mascot else school
        tbody_m = re.search(r"<tbody>(.*?)</tbody>", block, re.S)
        if not tbody_m:
            continue
        tbody = tbody_m.group(1)
        if "No injuries to report" in tbody:
            continue
        pending: Listing | None = None
        for row in re.findall(r"<tr\b([^>]*)>(.*?)</tr>", tbody, re.S):
            attrs, inner = row
            if "collapse" in attrs or "injuryCopy" in inner or "colspan" in inner:
                note_m = re.search(r"injuryCopy\">(.*?)</div>", inner, re.S)
                if pending is not None and note_m:
                    note = _text(note_m.group(1)) or None
                    pending.note = note
                continue
            cells = re.findall(r"<td\b[^>]*>(.*?)</td>", inner, re.S)
            if len(cells) < 3:
                continue
            player = _text(cells[0])
            if not player or player.lower().startswith("no injuries"):
                continue
            bold = re.search(r"<b>(.*?)</b>", cells[2], re.S)
            phrase = _text(bold.group(1) if bold else cells[2])
            if " - " in phrase:
                left, right = phrase.split(" - ", 1)
            else:
                left, right = phrase, ""
            status, injury = classify_status(left, right)
            if not status:
                continue
            date_m = re.search(r"\(([^)]*)\)", _text(cells[2]))
            pending = Listing(
                source="covers",
                team_raw=query,
                team_query=query,
                player_raw=player,
                status=status,
                injury_type=injury,
                note=None,
                return_date=_return_text(date_m.group(1) if date_m else None),
                vendor_player_id=None,
            )
            out.append(pending)
    return out


def _covers_team(block: str) -> tuple[str, str] | None:
    m = re.search(r"covers-CoversMatchups-teamName.*?<a\b[^>]*>(.*?)</a>", block, re.S)
    if not m:
        return None
    inner = m.group(1)
    parts = re.split(r"<br\s*/?>", inner, maxsplit=1)
    school = _text(parts[0])
    mascot_m = re.search(r"<span>(.*?)</span>", inner, re.S)
    mascot = _text(mascot_m.group(1)) if mascot_m else ""
    if not school:
        return None
    return school, mascot


def backoff_after(failures: int) -> timedelta:
    """10 minutes, doubled each consecutive 403 or 429, capped at 2 hours."""
    steps = max(failures, 1)
    return min(BACKOFF_BASE * (2 ** (steps - 1)), BACKOFF_CAP)


def source_due(source: str, state: PollState, now: datetime, *, near_tip: bool) -> str:
    """'poll', 'backoff', or 'cadence'."""
    until = _aware(state.backoff_until)
    if until is not None and until > now:
        return "backoff"
    last = _aware(state.last_success_at)
    if source == "rotowire":
        gap = ROTOWIRE_NEAR if near_tip else ROTOWIRE_EVERY
    else:
        gap = COVERS_EVERY
    if last is None or now - last >= gap:
        return "poll"
    return "cadence"


def slate_flags(rows: list[tuple], now: datetime) -> tuple[bool, bool]:
    """(game_day, near_tip) from (game_date, commence_time) rows.

    A game day is an NCAAB game whose ET date is today, or a game that tips
    within three hours. Near tip is that three-hour window, still before the
    tip. A missing tip time is not near.
    """
    from zoneinfo import ZoneInfo
    today = now.astimezone(ZoneInfo(ET_NAME)).date().isoformat()
    game_day = False
    near = False
    for game_date, commence in rows:
        if str(game_date)[:10] == today:
            game_day = True
        tip = _aware(commence)
        if tip is None:
            continue
        delta = tip - now
        if timedelta(0) < delta <= NEAR_TIP:
            near = True
            game_day = True
    return game_day, near


def _rank(status: str) -> int:
    return _STATUS_RANK.get(status, 50)


def collapse(listings: list[Listing]) -> list[Listing]:
    """One row per (team, player). The more serious absence wins. No blend."""
    best: dict[tuple[str, str], Listing] = {}
    for row in listings:
        key = (row.team_raw, row.player_raw)
        prev = best.get(key)
        if prev is None or _rank(row.status) < _rank(prev.status):
            best[key] = row
    return list(best.values())


def fold_player(name: str) -> str:
    """The roster key. ncaab_sdv_import.player_key, not a second folding."""
    from data.ingestors.ncaab_sdv_import import player_key
    return player_key(name)


def resolve_team(team_query: str, registry: list[dict], team_map: dict) -> tuple[int | None, str]:
    """(espn id or None, 'matched' | 'team_miss').

    The override map is an exact feed string. Otherwise one call to
    resolve_team_name, which already returns None when two teams fit. A miss
    does not try a shorter piece of the name.
    """
    if team_query in team_map:
        try:
            return int(team_map[team_query]), "matched"
        except (TypeError, ValueError):
            return None, "team_miss"
    hit = resolve_team_name(team_query, registry)
    if hit is None:
        return None, "team_miss"
    return int(hit), "matched"


def school_name(espn_id: int | None, registry: list[dict]) -> str | None:
    if espn_id is None:
        return None
    names = {t.get("school") for t in registry if t.get("espn_id") == espn_id and t.get("school")}
    if len(names) == 1:
        return next(iter(names))
    return None


def resolve_player(player_raw: str, espn_id: int | None, roster: set[str],
                   player_map: dict) -> tuple[str | None, str]:
    """(player_key or None, 'matched' | 'player_unconfirmed').

    The override is used only when its value is on this team's roster. A key
    the roster does not hold is not written as that other person. The printed
    name's own fold is what an unconfirmed row keeps, and the miss is logged.
    """
    folded = fold_player(player_raw)
    if not folded or espn_id is None:
        return None, "player_unconfirmed"
    forced = player_map.get(f"{espn_id}|{folded}")
    if forced is not None:
        if forced in roster:
            return forced, "matched"
        return folded, "player_unconfirmed"
    if folded in roster:
        return folded, "matched"
    return folded, "player_unconfirmed"


def resolve_listing(row: Listing, registry: list[dict], roster: set[str],
                    team_map: dict, player_map: dict) -> dict:
    espn_id, team_state = resolve_team(row.team_query, registry, team_map)
    school = school_name(espn_id, registry) if team_state == "matched" else None
    if team_state != "matched" or school is None:
        return _resolved(row, None, None, None, None, "team_miss")
    player_key, player_state = resolve_player(row.player_raw, espn_id, roster, player_map)
    return _resolved(row, espn_id, school, player_key, None, player_state)


def _resolved(row: Listing, espn_id, school, player_key, player_id, match_status) -> dict:
    return {
        "source": row.source,
        "team_raw": row.team_raw,
        "player_raw": row.player_raw,
        "espn_team_id": espn_id,
        "team": school,
        "player_key": player_key,
        "player_id": player_id,
        "status": row.status,
        "injury_type": row.injury_type,
        "note": row.note,
        "return_date": row.return_date,
        "vendor_player_id": row.vendor_player_id,
        "match_status": match_status,
    }


def _sig(row: dict) -> tuple:
    return (row.get("status"), row.get("injury_type") or "", row.get("note") or "",
            row.get("return_date") or "")


def diff_report(previous: list[dict], resolved: list[dict], received_at: datetime) -> tuple[list[dict], list[dict]]:
    """(change rows, new open rows).

    An empty resolved list writes nothing and leaves the open report as it
    was: a zero-player poll is not a list of clearances.
    """
    if not resolved:
        return [], list(previous)
    prev = {(r["team_raw"], r["player_raw"]): r for r in previous}
    changes: list[dict] = []
    opened: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for row in resolved:
        key = (row["team_raw"], row["player_raw"])
        seen.add(key)
        current = dict(row)
        current["received_at"] = received_at
        old = prev.get(key)
        if old is None or _sig(old) != _sig(current):
            changes.append(dict(current))
        opened.append(current)
    for key, old in prev.items():
        if key in seen:
            continue
        cleared = dict(old)
        cleared["status"] = STATUS_CLEARED
        cleared["injury_type"] = None
        cleared["note"] = None
        cleared["return_date"] = None
        cleared["received_at"] = received_at
        changes.append(cleared)
    return changes, opened


def misses_for(resolved: list[dict], received_at: datetime) -> list[dict]:
    out = []
    for row in resolved:
        if row["match_status"] == "matched":
            continue
        out.append({
            "source": row["source"],
            "team_raw": row["team_raw"],
            "player_raw": row["player_raw"],
            "reason": row["match_status"],
            "last_seen": received_at,
            "detail": None if row["match_status"] != "team_miss" else row["team_raw"],
        })
    return out


def absence_rows(open_rows: list[dict]) -> list[dict]:
    """Rows for injury_status_current. Two printed names on one key: neither.

    That collision is a miss, not a pick of which player the injury belongs to.
    """
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in open_rows:
        if row.get("match_status") == "team_miss":
            continue
        if row.get("status") not in ABSENCE_STATUSES:
            continue
        if not row.get("team") or not row.get("player_key"):
            continue
        grouped.setdefault((row["team"], row["player_key"]), []).append(row)
    out = []
    for group in grouped.values():
        if len({g["player_raw"] for g in group}) > 1:
            continue
        best = min(group, key=lambda g: _rank(g["status"]))
        out.append(best)
    return out


def tag_label(status: str, injury_type: str | None) -> str | None:
    """The same chip letters as mobile/src/lib/injuryStatus.ts injuryTag."""
    if status not in ABSENCE_STATUSES:
        return None
    kind = (injury_type or "").strip().lower()
    if status == "Out" and kind == "injured reserve":
        return "IR"
    if status == "Out" and kind == "suspension":
        return "SUSP"
    return _TAG[status]


def tags_from_rows(rows: list[dict]) -> list[dict]:
    """Display tags. 'cleared', Probable and an unknown word are not tags."""
    out = []
    for row in rows:
        label = tag_label(row.get("status") or "", row.get("injury_type"))
        if label is None or not row.get("team") or not row.get("player_key"):
            continue
        out.append({
            "team": row["team"],
            "player_key": row["player_key"],
            "player_name": row.get("player_raw"),
            "status": row["status"],
            "injury_type": row.get("injury_type"),
            "as_of": row.get("received_at"),
            "tag": label,
        })
    return out


def zero_row_alert(game_day: bool, empty: set[str], refreshed: set[str],
                   rotowire: PollState, now: datetime) -> str | None:
    """The game-day zero-row alert, or None.

    The tags use RotoWire when this tick stored its players, or when RotoWire
    is still healthy and this tick did not find it empty. An empty Covers
    report is not an alert in that case. Otherwise the tags use Covers, and
    an empty Covers report is an alert. If Covers was not polled and did not
    supply players, an empty RotoWire report is the alert: it is the source
    the tags are left with.
    """
    if not game_day or not empty:
        return None
    rotowire_tags = ("rotowire" in refreshed) or (
        rotowire_healthy(rotowire, now) and "rotowire" not in empty
    )
    if rotowire_tags:
        return None
    if "covers" in empty:
        return "covers returned 0 rows on a game day"
    if "rotowire" in empty and "covers" not in refreshed:
        return "rotowire returned 0 rows on a game day"
    return None


def rotowire_healthy(state: PollState, now: datetime) -> bool:
    until = _aware(state.backoff_until)
    if until is not None and until > now:
        return False
    last = _aware(state.last_success_at)
    if last is None or not state.last_row_count:
        return False
    return now - last <= ROTOWIRE_FRESH


def fetch_url(url: str, timeout: float = 30) -> FetchResult:
    try:
        response = requests.get(url, headers=_HEADERS, timeout=timeout)
    except requests.RequestException as exc:
        return FetchResult(None, "", type(exc).__name__)
    return FetchResult(response.status_code, response.text or "", None)


# The migration file is the pipeline's copy of this DDL. ensure_tables is the
# writer’s copy, so a tick before that pass still locks the tables down.
# tests/test_ncaab_injury_feed.py checks the two copies name the same columns.
_DDL = (
    """
    CREATE TABLE IF NOT EXISTS ncaab_injury_changes (
        change_id        BIGSERIAL PRIMARY KEY,
        source           TEXT NOT NULL,
        received_at      TIMESTAMPTZ NOT NULL,
        team_raw         TEXT NOT NULL,
        player_raw       TEXT NOT NULL,
        espn_team_id     INTEGER,
        team             TEXT,
        player_key       TEXT,
        player_id        TEXT,
        status           TEXT NOT NULL,
        injury_type      TEXT,
        note             TEXT,
        return_date      TEXT,
        vendor_player_id TEXT,
        match_status     TEXT NOT NULL
    )
    """,
    f"CREATE INDEX IF NOT EXISTS {_CHANGE_INDEX} "
    "ON ncaab_injury_changes (espn_team_id, player_key, received_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS ncaab_injury_open (
        source           TEXT NOT NULL,
        team_raw         TEXT NOT NULL,
        player_raw       TEXT NOT NULL,
        espn_team_id     INTEGER,
        team             TEXT,
        player_key       TEXT,
        player_id        TEXT,
        status           TEXT NOT NULL,
        injury_type      TEXT,
        note             TEXT,
        return_date      TEXT,
        vendor_player_id TEXT,
        match_status     TEXT NOT NULL,
        received_at      TIMESTAMPTZ NOT NULL,
        PRIMARY KEY (source, team_raw, player_raw)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ncaab_injury_polls (
        source                TEXT PRIMARY KEY,
        last_attempt_at       TIMESTAMPTZ,
        last_success_at       TIMESTAMPTZ,
        last_status_code      INTEGER,
        last_row_count        INTEGER,
        backoff_until         TIMESTAMPTZ,
        consecutive_failures  INTEGER NOT NULL DEFAULT 0,
        last_error            TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ncaab_injury_misses (
        source      TEXT NOT NULL,
        team_raw    TEXT NOT NULL,
        player_raw  TEXT NOT NULL,
        reason      TEXT NOT NULL,
        last_seen   TIMESTAMPTZ NOT NULL,
        detail      TEXT,
        PRIMARY KEY (source, team_raw, player_raw, reason)
    )
    """,
)


def ensure_tables(conn) -> None:
    """Create the four tables once. A current schema runs no DDL."""
    from data.ddl_guard import schema_is_current

    specs = {
        "ncaab_injury_changes": dict(
            columns=_CHANGE_COLUMNS, indexes=(_CHANGE_INDEX,),
            rls=True, revoked_from=API_ROLES),
        "ncaab_injury_open": dict(
            columns=_OPEN_COLUMNS, rls=True, revoked_from=API_ROLES),
        "ncaab_injury_polls": dict(
            columns=_POLL_COLUMNS, rls=True, revoked_from=API_ROLES),
        "ncaab_injury_misses": dict(
            columns=_MISS_COLUMNS, rls=True, revoked_from=API_ROLES),
    }
    if all(schema_is_current(conn, name, **kw) for name, kw in specs.items()):
        return
    for stmt in _DDL:
        conn.execute(stmt)
    for name in _TABLES:
        lock_down(conn, name)
    conn.commit()


def _rows(conn, sql: str, params=None) -> list:
    cur = conn.execute(sql, params)
    return cur.fetchall()


def load_polls(conn) -> dict[str, PollState]:
    found = {s: PollState(s) for s in SOURCES}
    try:
        rows = _rows(conn, """
            SELECT source, last_attempt_at, last_success_at, last_status_code,
                   last_row_count, backoff_until, consecutive_failures, last_error
            FROM ncaab_injury_polls
        """)
    except Exception as exc:                                    # noqa: BLE001
        logger.warning(f"NCAAB injury polls unreadable ({type(exc).__name__})")
        try:
            conn.rollback()
        except Exception:                                       # noqa: BLE001
            pass
        return found
    for row in rows:
        found[row[0]] = PollState(
            source=row[0],
            last_attempt_at=_aware(row[1]),
            last_success_at=_aware(row[2]),
            last_status_code=row[3],
            last_row_count=row[4],
            backoff_until=_aware(row[5]),
            consecutive_failures=int(row[6] or 0),
            last_error=row[7],
        )
    return found


def load_slate(conn, now: datetime) -> list[tuple]:
    from zoneinfo import ZoneInfo
    today = now.astimezone(ZoneInfo(ET_NAME)).date()
    try:
        return _rows(conn, """
            SELECT game_date, commence_time FROM games
            WHERE sport = %s AND game_date BETWEEN %s AND %s
        """, (SPORT, today.isoformat(), (today + timedelta(days=1)).isoformat()))
    except Exception as exc:                                    # noqa: BLE001
        logger.warning(f"NCAAB injury slate unreadable ({type(exc).__name__})")
        try:
            conn.rollback()
        except Exception:                                       # noqa: BLE001
            pass
        return []


def load_open(conn, source: str) -> list[dict] | None:
    """The stored report, [] when nobody is listed, None when the read failed.

    None is not an empty report: diffing against [] would store every player
    again and clear nobody.
    """
    try:
        rows = _rows(conn, """
            SELECT source, team_raw, player_raw, espn_team_id, team, player_key,
                   player_id, status, injury_type, note, return_date,
                   vendor_player_id, match_status, received_at
            FROM ncaab_injury_open WHERE source = %s
        """, (source,))
    except Exception as exc:                                    # noqa: BLE001
        logger.warning(f"NCAAB injury open report unreadable ({type(exc).__name__})")
        try:
            conn.rollback()
        except Exception:                                       # noqa: BLE001
            pass
        return None
    keys = ("source", "team_raw", "player_raw", "espn_team_id", "team", "player_key",
            "player_id", "status", "injury_type", "note", "return_date",
            "vendor_player_id", "match_status", "received_at")
    return [dict(zip(keys, row)) for row in rows]


def load_roster(conn, espn_id: int, seasons: tuple[int, ...]) -> set[str]:
    try:
        rows = _rows(conn, """
            SELECT player_key FROM ncaab_player_season
            WHERE team_espn_id = %s AND season = ANY(%s)
        """, (espn_id, list(seasons)))
    except Exception as exc:                                    # noqa: BLE001
        logger.warning(f"NCAAB injury roster unreadable ({type(exc).__name__})")
        try:
            conn.rollback()
        except Exception:                                       # noqa: BLE001
            pass
        return set()
    return {row[0] for row in rows if row[0]}


def save_poll(conn, state: PollState) -> None:
    conn.execute("""
        INSERT INTO ncaab_injury_polls (
            source, last_attempt_at, last_success_at, last_status_code,
            last_row_count, backoff_until, consecutive_failures, last_error
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source) DO UPDATE SET
            last_attempt_at = EXCLUDED.last_attempt_at,
            last_success_at = EXCLUDED.last_success_at,
            last_status_code = EXCLUDED.last_status_code,
            last_row_count = EXCLUDED.last_row_count,
            backoff_until = EXCLUDED.backoff_until,
            consecutive_failures = EXCLUDED.consecutive_failures,
            last_error = EXCLUDED.last_error
    """, (state.source, state.last_attempt_at, state.last_success_at,
          state.last_status_code, state.last_row_count, state.backoff_until,
          state.consecutive_failures, state.last_error))


def insert_changes(conn, rows: list[dict]) -> None:
    if not rows:
        return
    conn.executemany("""
        INSERT INTO ncaab_injury_changes (
            source, received_at, team_raw, player_raw, espn_team_id, team,
            player_key, player_id, status, injury_type, note, return_date,
            vendor_player_id, match_status
        ) VALUES (
            %(source)s, %(received_at)s, %(team_raw)s, %(player_raw)s,
            %(espn_team_id)s, %(team)s, %(player_key)s, %(player_id)s,
            %(status)s, %(injury_type)s, %(note)s, %(return_date)s,
            %(vendor_player_id)s, %(match_status)s
        )
    """, rows)


def replace_open(conn, source: str, rows: list[dict]) -> None:
    conn.execute("DELETE FROM ncaab_injury_open WHERE source = %s", (source,))
    if not rows:
        return
    conn.executemany("""
        INSERT INTO ncaab_injury_open (
            source, team_raw, player_raw, espn_team_id, team, player_key,
            player_id, status, injury_type, note, return_date,
            vendor_player_id, match_status, received_at
        ) VALUES (
            %(source)s, %(team_raw)s, %(player_raw)s, %(espn_team_id)s, %(team)s,
            %(player_key)s, %(player_id)s, %(status)s, %(injury_type)s, %(note)s,
            %(return_date)s, %(vendor_player_id)s, %(match_status)s, %(received_at)s
        )
    """, rows)


def replace_current(conn, open_rows: list[dict]) -> int:
    """Replace injury_status_current for NCAAB from this non-empty report.

    Absences only. A player who cleared is absent here, so the DELETE drops
    the chip. The caller does not call this for a zero-player poll.
    """
    rows = absence_rows(open_rows)
    conn.execute("DELETE FROM injury_status_current WHERE sport = %s", (SPORT,))
    if rows:
        conn.executemany("""
            INSERT INTO injury_status_current (
                sport, team, player_key, player_name, player_id,
                status, injury_type, status_ts, as_of
            ) VALUES (
                'NCAAB', %(team)s, %(player_key)s, %(player_raw)s, %(player_id)s,
                %(status)s, %(injury_type)s, %(status_ts)s, NOW()
            )
        """, [{**r, "status_ts": _aware(r.get("received_at")).isoformat()
               if _aware(r.get("received_at")) else None} for r in rows])
    return len(rows)


def save_misses(conn, rows: list[dict]) -> None:
    if not rows:
        return
    conn.executemany("""
        INSERT INTO ncaab_injury_misses (
            source, team_raw, player_raw, reason, last_seen, detail
        ) VALUES (
            %(source)s, %(team_raw)s, %(player_raw)s, %(reason)s, %(last_seen)s, %(detail)s
        )
        ON CONFLICT (source, team_raw, player_raw, reason) DO UPDATE SET
            last_seen = EXCLUDED.last_seen,
            detail = EXCLUDED.detail
    """, rows)


def _log_misses(rows: list[dict]) -> None:
    for row in rows:
        logger.warning(
            f"NCAAB injury miss: {row['source']} team={row['team_raw']!r} "
            f"player={row['player_raw']!r} {row['reason']}"
        )


def _parse_source(source: str, body: str) -> list[Listing]:
    if source == "rotowire":
        return parse_rotowire(body)
    return parse_covers(body)


def _url(source: str) -> str:
    return ROTOWIRE_URL if source == "rotowire" else COVERS_URL


def run(conn, *, now: datetime | None = None, fetch=None,
        registry: list[dict] | None = None,
        roster_for=None) -> TickResult:
    """One tick. Commits the poll, the diff and the current-status replace."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    fetch = fetch or fetch_url
    ensure_tables(conn)
    if registry is None:
        registry = load_registry(conn)
    team_map = getattr(config, "NCAAB_INJURY_TEAM_MAP", None) or {}
    player_map = getattr(config, "NCAAB_INJURY_PLAYER_MAP", None) or {}
    from zoneinfo import ZoneInfo
    today = now.astimezone(ZoneInfo(ET_NAME)).date().isoformat()
    season = ncaab_season_label(today)
    seasons = (season, season - 1)
    polls = load_polls(conn)
    game_day, near = slate_flags(load_slate(conn, now), now)
    # Open reports are read before any write. A failure here rolls back an
    # empty transaction; doing it after save_poll would drop the poll row.
    previous_open: dict[str, list[dict]] = {}
    result = TickResult()
    for source in SOURCES:
        opened = load_open(conn, source)
        if opened is None:
            result.alerts.append(f"{source} open report unreadable")
            return result
        previous_open[source] = opened
    refreshed: dict[str, list[dict]] = {}
    if roster_for is None:
        cache: dict[int, set[str]] = {}

        def roster_for(espn_id: int) -> set[str]:
            if espn_id not in cache:
                cache[espn_id] = load_roster(conn, espn_id, seasons)
            return cache[espn_id]

    # Resolve before writing. A roster read that rolls back then discards
    # selects only: no change row is inserted until every source is resolved.
    planned: list[tuple] = []
    empty: set[str] = set()
    for source in SOURCES:
        state = polls.get(source) or PollState(source)
        action = source_due(source, state, now, near_tip=near)
        if action == "cadence":
            continue
        if action == "backoff":
            until = _aware(state.backoff_until)
            result.alerts.append(
                f"{source} backing off until {until.isoformat()} after {state.last_error}"
            )
            continue
        fetched = fetch(_url(source))
        state.last_attempt_at = now
        state.last_status_code = fetched.status
        if fetched.error or fetched.status != 200:
            code = fetched.error or f"HTTP {fetched.status}"
            state.last_error = code
            if fetched.status in BACKOFF_STATUSES:
                state.consecutive_failures += 1
                state.backoff_until = now + backoff_after(state.consecutive_failures)
            result.alerts.append(f"{source} poll error {code}")
            result.polled.append(source)
            planned.append((state, None))
            continue
        try:
            listings = collapse(_parse_source(source, fetched.body))
        except ParseError as exc:
            state.last_error = type(exc).__name__
            result.alerts.append(f"{source} poll error {exc}")
            result.polled.append(source)
            planned.append((state, None))
            continue
        state.last_success_at = now
        state.last_row_count = len(listings)
        state.last_error = None
        state.consecutive_failures = 0
        state.backoff_until = None
        result.polled.append(source)
        if not listings:
            # A zero-player poll is not a list of clearances. Whether it
            # alerts depends on which source the tags are using, decided
            # after both polls (zero_row_alert).
            if game_day:
                empty.add(source)
            planned.append((state, None))
            continue
        resolved = []
        for listing in listings:
            espn_id, _team_state = resolve_team(listing.team_query, registry, team_map)
            roster = roster_for(espn_id) if espn_id is not None else set()
            resolved.append(resolve_listing(listing, registry, roster, team_map, player_map))
        planned.append((state, resolved))

    for state, resolved in planned:
        save_poll(conn, state)
        polls[state.source] = state
        if resolved is None:
            continue
        changes, opened = diff_report(previous_open.get(state.source) or [], resolved, now)
        misses = misses_for(resolved, now)
        _log_misses(misses)
        insert_changes(conn, changes)
        replace_open(conn, state.source, opened)
        save_misses(conn, misses)
        result.changes += len(changes)
        result.misses += len(misses)
        refreshed[state.source] = opened

    rw = polls.get("rotowire") or PollState("rotowire")
    if "rotowire" in refreshed:
        replace_current(conn, refreshed["rotowire"])
    elif "covers" in refreshed and not rotowire_healthy(rw, now):
        replace_current(conn, refreshed["covers"])
    alert = zero_row_alert(game_day, empty, set(refreshed), rw, now)
    if alert:
        result.alerts.append(alert)
    if game_day and "covers" in empty and alert is None and (
            "rotowire" in refreshed or rotowire_healthy(rw, now)):
        logger.warning(
            "NCAAB injury: covers returned 0 rows on a game day; tags stay on rotowire"
        )
    if game_day and "rotowire" in empty and "covers" in refreshed:
        logger.warning(
            "NCAAB injury: rotowire returned 0 rows on a game day; tags use covers"
        )
    conn.commit()
    return result


def injury_tags_before_tip(conn, game_id: str) -> list[dict]:
    """Latest status of each matched player on this game, at or before tip.

    Display tags only. A row after tip is not visible here. 'cleared' is not
    a tag. This is not a model feature and is not read by the scorers.
    """
    try:
        game = _rows(conn, """
            SELECT g.commence_time, e.home_espn_id, e.away_espn_id
            FROM games g
            LEFT JOIN ncaab_events e ON e.game_id = g.game_id
            WHERE g.game_id = %s AND g.sport = %s
        """, (game_id, SPORT))
    except Exception as exc:                                    # noqa: BLE001
        logger.warning(f"NCAAB injury tag read failed ({type(exc).__name__})")
        try:
            conn.rollback()
        except Exception:                                       # noqa: BLE001
            pass
        return []
    if not game:
        return []
    tip = _aware(game[0][0])
    if tip is None:
        return []
    ids = [int(i) for i in (game[0][1], game[0][2]) if i is not None]
    if not ids:
        return []
    try:
        rows = _rows(conn, """
            SELECT DISTINCT ON (team, player_key)
                   player_raw, team, player_key, status, injury_type, received_at
            FROM ncaab_injury_changes
            WHERE received_at <= %s
              AND espn_team_id = ANY(%s)
              AND player_key IS NOT NULL
              AND team IS NOT NULL
            ORDER BY team, player_key, received_at DESC
        """, (tip, ids))
    except Exception as exc:                                    # noqa: BLE001
        logger.warning(f"NCAAB injury tag read failed ({type(exc).__name__})")
        try:
            conn.rollback()
        except Exception:                                       # noqa: BLE001
            pass
        return []
    keys = ("player_raw", "team", "player_key", "status", "injury_type", "received_at")
    return tags_from_rows([dict(zip(keys, row)) for row in rows])


def main() -> int:
    """Exit 1 when a due poll errors or returns 0 players on a game day."""
    if not enabled():
        logger.info("NCAAB injury feed: RUN_NCAAB_INJURY is off")
        return 0
    from data.db import get_connection
    conn = get_connection()
    try:
        result = run(conn)
    finally:
        conn.close()
    logger.info(
        f"NCAAB injury feed: polled={result.polled or 'none'} "
        f"changes={result.changes} misses={result.misses}"
    )
    if result.alerts:
        logger.error("NCAAB_INJURY_ALERT " + "; ".join(result.alerts))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
