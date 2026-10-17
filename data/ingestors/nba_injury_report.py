"""The official NBA injury report archive, every report, with the time it was published.

WHY. A model can only use a player's status if it knows what the status WAS
at the moment the bet was decided. The `injuries` table holds ESPN's current
view, overwritten in place, so for any past game it carries the answer from
after the fact. The league's own report is published as a series of PDFs
through the day, each one headed with the time it was issued, and every one of
them is still on the CDN. Stored here with that time, a model can ask "what
did the 5:30 PM report say" and see nothing later.

THE SOURCE (measured 2026-10-15).
  https://ak-static.cms.nba.com/referee/injury/Injury-Report_<YYYY-MM-DD>_<slot>.pdf
  * A missing file answers HTTP 403, not 404. There is no index; slots are probed.
  * Filename date is the ET date the report was issued. A report lists that
    date's games AND the next day's, so the evening report of the day before a
    game is the latest one a game-morning decision can have seen. The scope is
    therefore every game date plus the day before it.
  * Hourly names (_05PM) from 2018-12-17 through 2025-12-21. The header's
    time is stored as report_ts, never the filename's: of 13,070 hourly
    reports, 12,991 are headed hh:30, 41 hh:45, 36 hh:00 and two at :19 and
    :39 (backfill of 2026-10-15). 2018-19 to 2020-21 publish three a day
    (01PM, 05PM, 08PM; 04PM on 2018-12-17); from 2021-22 every hour, and all
    16 of 08AM..11PM answer on almost every date.
  * Quarter-hour names (_05_00PM) from 2025-12-22, every 15 minutes, headed
    with the slot's own time. Fetched at :00 and :30 from 08:00 to 23:30, plus
    the last quarter-hour before each tip-off that day.
  * Four page layouts in the files sampled, so columns are located from the
    header words of each page, never from fixed x positions: nine columns
    (Category and Reason separate, plus Previous Status) on 2018-12-26 ..
    2019-10-22; eight (no Category, Previous Status kept) on 2019-12-16; seven
    from 2020-01-15 to 2023-04-09; seven in a second renderer from 2024-01-15
    on, which prints the column header on page 1 only, so a page with no
    header reuses the previous page's columns. Category and Reason are joined
    as "Category - Reason", which is how the later layouts print them.
  * Rows are separated by ruled lines, and a two-line reason puts the player's
    name between its two lines, so words are grouped by the ruled lines, not by
    their height on the page. Date, time, matchup and team cells span several
    rows and carry forward, across page breaks too.

WHAT IT WRITES.
  * `nba_injury_report` -- one row per line of each report (PK source_url,
    row_no). A team the report lists as NOT YET SUBMITTED is a row with
    player_name NULL and status 'NOT YET SUBMITTED': it means "unknown", where
    a team with no rows at all means nobody is listed. December 2018 / January
    2019 reports also print ALL PLAYERS AVAILABLE for a team, stored the same
    way with that status. game_time_et is printed without AM/PM ("07:00"):
    join nba_schedule.commence_time on game_id for the tip time. A postponed
    game keeps the game_id it was reported under, which nba_schedule lacks.
    player_id is NBA.com's person id, matched to nba_player_game_log by name
    (team and season first); --remap-players re-matches after that table grows.
  * `nba_injury_report_pulls` -- one row per URL ever requested, 403s included,
    so a re-run requests nothing twice. Written in the same transaction as the
    report's rows. It also holds every report's time, so it is the list of
    reports that existed.
  * A report that repeats the one before it on the same date word for word
    (about half of them) gets its ledger row, with same_as_url naming the
    report whose rows it repeats, and no rows of its own. The latest stored
    report at or before any time T still says exactly what the latest issued
    one did, so the query below is unaffected. --no-dedupe stores them all.

AS OF A DECISION AT time T for game G (no look-ahead):
    SELECT * FROM nba_injury_report
     WHERE game_id = G AND report_ts = (
           SELECT max(report_ts) FROM nba_injury_report
            WHERE game_id = G AND report_ts <= T)

    python -m data.ingestors.nba_injury_report --dates 2019-01-15 2024-03-12
    python -m data.ingestors.nba_injury_report --backfill --seasons 2019 2026
    python -m data.ingestors.nba_injury_report --today
    python -m data.ingestors.nba_injury_report --remap-players
"""
from __future__ import annotations

import argparse
import hashlib
import io
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import psycopg2.errors
import requests
from loguru import logger

import config
from data.anon_readable import API_ROLES, lock_down
from data.db import ConnectionLost, get_connection

ET = ZoneInfo("America/New_York")
BASE_URL = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_{d}_{slot}.pdf"

# Measured 2026-10-15: 2025-12-21 answers only the hourly name, 2025-12-22 only
# the quarter-hour name. Dates inside BOTH_FORMATS are probed both ways so a
# day either side of the switch cannot be lost.
OLD_FORMAT_LAST = date(2025, 12, 21)
NEW_FORMAT_FIRST = date(2025, 12, 22)
BOTH_FORMATS = (date(2025, 12, 19), date(2025, 12, 24))

OLD_HOURS = range(8, 24)                    # 08AM .. 11PM
NEW_TIMES = [(h, m) for h in range(8, 24) for m in (0, 30)]   # 08:00 .. 23:30

# A 403 for a slot this recent may simply not be published yet. Only an older
# 403 is written to the ledger, so the today mode never blocks itself.
MISSING_IS_FINAL_AFTER = timedelta(hours=6)

STATUSES = ("Out", "Doubtful", "Questionable", "Probable", "Available")
NOT_SUBMITTED = "NOT YET SUBMITTED"
# December 2018 reports print this for a team with nobody listed (measured on
# 2018-12-17 .. 2018-12-19). Like NOT YET SUBMITTED it is a team row, not text.
ALL_AVAILABLE = "ALL PLAYERS AVAILABLE"
TEAM_LEVEL = (NOT_SUBMITTED, ALL_AVAILABLE)

REPORT_DDL = """
CREATE TABLE IF NOT EXISTS nba_injury_report (
    source_url      TEXT NOT NULL,
    row_no          INTEGER NOT NULL,
    report_ts       TIMESTAMPTZ NOT NULL,
    report_date     TEXT NOT NULL,
    game_date       TEXT,
    game_time_et    TEXT,
    matchup         TEXT,
    game_id         TEXT,
    season          INTEGER,
    team            TEXT,
    team_name       TEXT,
    player_name     TEXT,
    player_name_raw TEXT,
    player_id       TEXT,
    status          TEXT,
    reason          TEXT,
    PRIMARY KEY (source_url, row_no)
)
"""
REPORT_INDEXES = (
    "CREATE INDEX IF NOT EXISTS nba_injury_report_game_ts ON nba_injury_report (game_id, report_ts)",
    "CREATE INDEX IF NOT EXISTS nba_injury_report_player_ts ON nba_injury_report (player_id, report_ts)",
)
PULLS_DDL = """
CREATE TABLE IF NOT EXISTS nba_injury_report_pulls (
    url          TEXT PRIMARY KEY,
    report_date  TEXT NOT NULL,
    slot         TEXT NOT NULL,
    http_status  INTEGER NOT NULL,
    fetched_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    report_ts    TIMESTAMPTZ,
    rows         INTEGER,
    bytes        INTEGER,
    sha256       TEXT,
    parse_notes  TEXT,
    content_sha256 TEXT,
    same_as_url  TEXT
)
"""


# ── slots ─────────────────────────────────────────────────────────────────────

def _ampm(hour24: int) -> tuple[int, str]:
    return (hour24 % 12 or 12), ("AM" if hour24 < 12 else "PM")


def old_slot(hour24: int) -> str:
    """16 -> '04PM', 0 -> '12AM', 12 -> '12PM'."""
    h, ap = _ampm(hour24)
    return f"{h:02d}{ap}"


def new_slot(hour24: int, minute: int) -> str:
    """(17, 15) -> '05_15PM'."""
    h, ap = _ampm(hour24)
    return f"{h:02d}_{minute:02d}{ap}"


_OLD_SLOT = re.compile(r"^(\d{2})(AM|PM)$")
_NEW_SLOT = re.compile(r"^(\d{2})_(\d{2})(AM|PM)$")


def slot_time(d: date, slot: str) -> datetime:
    """The nominal ET time a slot names (the hourly report itself is issued at :30)."""
    m = _NEW_SLOT.match(slot)
    if m:
        h, mi, ap = int(m.group(1)), int(m.group(2)), m.group(3)
    else:
        m = _OLD_SLOT.match(slot)
        if not m:
            raise ValueError(f"not a report slot: {slot!r}")
        h, mi, ap = int(m.group(1)), 0, m.group(2)
    h24 = (h % 12) + (12 if ap == "PM" else 0)
    return datetime(d.year, d.month, d.day, h24, mi, tzinfo=ET)


def report_url(d: date, slot: str) -> str:
    return BASE_URL.format(d=d.isoformat(), slot=slot)


def pre_tip_slot(tip_et: datetime) -> tuple[int, int]:
    """The last quarter-hour strictly before a tip: 19:00 -> 18:45, 19:10 -> 19:00."""
    t = tip_et - timedelta(minutes=1)
    return t.hour, (t.minute // 15) * 15


def slots_for_date(d: date, tips_et: list[datetime] | tuple = ()) -> list[str]:
    """Every slot to request for one ET date, in time order."""
    out: list[str] = []
    old = d <= OLD_FORMAT_LAST or BOTH_FORMATS[0] <= d <= BOTH_FORMATS[1]
    new = d >= NEW_FORMAT_FIRST or BOTH_FORMATS[0] <= d <= BOTH_FORMATS[1]
    if old:
        out += [old_slot(h) for h in OLD_HOURS]
    if new:
        times = set(NEW_TIMES)
        for tip in tips_et:
            tip = tip.astimezone(ET)
            if tip.date() != d:
                continue
            h, m = pre_tip_slot(tip)
            if h >= 8:
                times.add((h, m))
        out += [new_slot(h, m) for h, m in sorted(times)]
    return out


# ── parsing ───────────────────────────────────────────────────────────────────

# Header labels, in the words the PDF prints them with.
_LABELS = (
    (("Game", "Date"), "date"),
    (("Game", "Time"), "time"),
    (("Matchup",), "matchup"),
    (("Team",), "team"),
    (("Player", "Name"), "player"),
    (("Category",), "category"),
    (("Reason",), "reason"),
    (("Current", "Status"), "status"),
    (("Previous", "Status"), "prev_status"),
)
_GROUP_COLS = ("date", "time", "matchup", "team")
_TITLE = re.compile(r"Report:\s*(\d{2}/\d{2}/\d{2,4})\s+(\d{1,2}:\d{2})\s*([AP]M)")
_FOOTER = re.compile(r"^Page\s*\d+\s*of\s*\d+$")
_MATCHUP = re.compile(r"^([A-Z]{2,3})@([A-Z]{2,3})$")
_GAME_DATE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_GAME_TIME = re.compile(r"(\d{1,2}:\d{2})")


@dataclass
class Report:
    report_ts: datetime | None
    rows: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _lines_of(words: list[dict], tol: float = 2.0) -> list[list[dict]]:
    """Words grouped into visual lines, top to bottom, each left to right."""
    lines: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and abs(lines[-1][0]["top"] - w["top"]) <= tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(ln, key=lambda w: w["x0"]) for ln in lines]


def _text(words: list[dict]) -> str:
    return " ".join(" ".join(w["text"] for w in ln) for ln in _lines_of(words)).strip()


def _columns(header: list[dict]) -> dict[str, float]:
    """Column name -> left edge, from the header line's words."""
    ws = sorted(header, key=lambda w: w["x0"])
    cols: dict[str, float] = {}
    i = 0
    while i < len(ws):
        for tokens, name in _LABELS:
            n = len(tokens)
            if tuple(w["text"] for w in ws[i:i + n]) == tokens and name not in cols:
                cols[name] = ws[i]["x0"] - 3.0
                i += n
                break
        else:
            i += 1
    return cols


def _column_of(x0: float, bounds: list[tuple[str, float]]) -> str | None:
    name = None
    for col, left in bounds:
        if x0 >= left:
            name = col
    return name


def _hrules(edges: list[dict], x: float, y_min: float, y_max: float) -> list[float]:
    """y of every horizontal rule crossing x, inside (y_min, y_max), deduplicated."""
    ys = sorted(e["top"] for e in edges
                if e["x0"] - 0.5 <= x <= e["x1"] + 0.5 and y_min < e["top"] < y_max)
    out: list[float] = []
    for y in ys:
        if not out or y - out[-1] > 1.0:
            out.append(y)
    return out


def _bands(rules: list[float], top: float, bottom: float) -> list[tuple[float, float]]:
    ys = [top] + rules + [bottom]
    return [(a, b) for a, b in zip(ys, ys[1:]) if b - a > 2.0]


def parse_page_layout(words: list[dict], hedges: list[dict], height: float,
                      prev_cols: dict[str, float] | None = None) -> dict:
    """One page's title, columns and rows of cell text. Pure; tests drive it directly.

    The 2023-24-on layout prints the column header on page 1 only, so a page
    with no header reuses the previous page's columns and its rows start under
    the title line.
    """
    out: dict = {"title": None, "cells": [], "cols": None}
    title_ln = next((ln for ln in _lines_of(words) if any(w["text"] == "Report:" for w in ln)), None)
    if title_ln:
        out["title"] = " ".join(w["text"] for w in title_ln)
    anchor = next((w for w in words if w["text"] == "Matchup"), None)
    cols = None
    if anchor is not None:
        header = [w for w in words if abs(w["top"] - anchor["top"]) <= 3.0]
        cols = _columns(header)
        head_bottom = max(w["bottom"] for w in header) + 0.5
    if not cols or "player" not in cols or "status" not in cols:
        if not prev_cols:
            return out
        cols = prev_cols
        head_bottom = (max(w["bottom"] for w in title_ln) + 0.5) if title_ln else 0.0
    out["cols"] = cols
    bounds = sorted(cols.items(), key=lambda kv: kv[1])
    rights = {c: (bounds[i + 1][1] if i + 1 < len(bounds) else 10_000.0)
              for i, (c, _) in enumerate(bounds)}
    centre = {c: (left + min(rights[c], left + 400.0)) / 2 for c, left in bounds}

    body = []
    for ln in _lines_of([w for w in words if w["top"] > head_bottom]):
        if _FOOTER.match("".join(w["text"] for w in ln)):
            continue
        body.extend(ln)
    by_col: dict[str, list[dict]] = {}
    for w in body:
        c = _column_of(w["x0"], bounds)
        if c:
            by_col.setdefault(c, []).append(w)

    def mid(w):
        return (w["top"] + w["bottom"]) / 2

    # A ruled line at or just under the header bottom is the header's own box.
    rule_top = head_bottom - 4.0
    row_bands = _bands(_hrules(hedges, centre["player"], rule_top, height), head_bottom, height)
    groups = {c: _bands(_hrules(hedges, centre[c], rule_top, height), head_bottom, height)
              for c in _GROUP_COLS if c in cols}

    for (y0, y1) in row_bands:
        cell = {}
        for c in cols:
            if c in _GROUP_COLS:
                continue
            cell[c] = _text([w for w in by_col.get(c, []) if y0 <= mid(w) < y1])
        ym = (y0 + y1) / 2
        for c, gb in groups.items():
            g = next(((a, b) for a, b in gb if a <= ym < b), None)
            if g is None:
                cell[c] = ""
                continue
            ga, gbot = g
            cell[c] = _text([w for w in by_col.get(c, []) if ga <= mid(w) < gbot])
        if any(cell.values()):
            cell["_first"] = not out["cells"]
            out["cells"].append(cell)
    return out


def name_first_last(raw: str | None) -> str | None:
    """'Pippen Jr., Scotty' -> 'Scotty Pippen Jr.'; a name with no comma is kept as printed."""
    if not raw:
        return None
    s = " ".join(raw.split())
    if "," not in s:
        return s
    last, first = s.split(",", 1)
    return f"{first.strip()} {last.strip()}".strip()


def norm_name(name: str | None) -> str:
    """Accents, punctuation and generational suffixes removed, lower case."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = re.sub(r"[^a-z ]+", " ", s.replace("'", "").replace(".", ""))
    toks = [t for t in s.split() if t not in {"jr", "sr", "ii", "iii", "iv", "v"}]
    return " ".join(toks)


_TEAM_BY_NAME = {norm_name(k): v for k, v in config.NBA_ODDS_API_MAP.items()}


def team_code(name: str | None) -> str | None:
    if not name:
        return None
    return _TEAM_BY_NAME.get(norm_name(name))


def parse_title(title: str | None) -> datetime | None:
    """'Injury Report: 03/12/24 05:30 PM' -> 2024-03-12 21:30 UTC."""
    if not title:
        return None
    m = _TITLE.search(title)
    if not m:
        return None
    d, hm, ap = m.groups()
    fmt = "%m/%d/%y" if len(d) == 8 else "%m/%d/%Y"
    day = datetime.strptime(d, fmt).date()
    h, mi = (int(x) for x in hm.split(":"))
    h24 = (h % 12) + (12 if ap == "PM" else 0)
    return datetime(day.year, day.month, day.day, h24, mi, tzinfo=ET).astimezone(timezone.utc)


def rows_from_pages(pages: list[dict]) -> Report:
    """Turn every page's cells into report rows, carrying group cells forward."""
    rep = Report(report_ts=parse_title(next((p["title"] for p in pages if p["title"]), None)))
    carry = {"date": "", "time": "", "matchup": "", "team": ""}
    for p in pages:
        for cell in p["cells"]:
            for c in _GROUP_COLS:
                if cell.get(c):
                    carry[c] = cell[c]
            player = cell.get("player", "")
            status = cell.get("status", "")
            cat = cell.get("category", "")
            reason = cell.get("reason", "")
            joined = " ".join(x for x in (cat, reason) if x and x != "-")
            said = " ".join((player, cat, reason, status)).upper()
            team_level = next((t for t in TEAM_LEVEL if t in said), None)
            if team_level and not status:
                rep.rows.append(_row(carry, None, team_level, None))
                continue
            if not player and not status:
                # A reason cut by a page break: the tail of the row above,
                # printed at the top of the next page.
                if joined and rep.rows and rep.rows[-1]["player_name_raw"]:
                    prev = rep.rows[-1]
                    prev["reason"] = " ".join(x for x in (prev["reason"], joined) if x)
                    if not cell.get("_first"):
                        rep.warnings.append(f"reason fragment not at a page top, after {prev['player_name_raw']!r}")
                elif joined:
                    rep.warnings.append(f"text with no player row to belong to: {joined[:60]!r}")
                continue
            if reason == "-":          # the nine-column layout's empty Reason
                reason = ""
            reason_txt = " - ".join(x for x in (cat, reason) if x) if cat else reason
            if status not in STATUSES:
                rep.warnings.append(f"unknown status {status!r} for {player!r}")
            rep.rows.append(_row(carry, player or None, status or None, reason_txt or None))
    return rep


def _row(carry: dict, player_raw: str | None, status: str | None, reason: str | None) -> dict:
    gd = None
    m = _GAME_DATE.match(carry["date"].strip())
    if m:
        gd = f"{m.group(3)}-{m.group(1)}-{m.group(2)}"
    gt = _GAME_TIME.search(carry["time"] or "")
    matchup = carry["matchup"].replace(" ", "") or None
    return {
        "game_date": gd,
        "game_time_et": gt.group(1) if gt else None,
        "matchup": matchup,
        "team_name": carry["team"] or None,
        "team": team_code(carry["team"]),
        "player_name_raw": player_raw,
        "player_name": name_first_last(player_raw),
        "status": status,
        "reason": reason,
    }


def parse_pdf(data: bytes) -> Report:
    import pdfplumber

    pages = []
    cols = None
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for pg in pdf.pages:
            words = pg.extract_words(x_tolerance=1.5, y_tolerance=2)
            hedges = [{"x0": e["x0"], "x1": e["x1"], "top": e["top"]}
                      for e in pg.horizontal_edges]
            page = parse_page_layout(words, hedges, float(pg.height), cols)
            cols = page["cols"] or cols
            pages.append(page)
    return rows_from_pages(pages)


def finish_rows(rep: Report, schedule: dict, players: dict) -> list[dict]:
    """Game id, season and player id beside each parsed row."""
    out = []
    for i, r in enumerate(rep.rows):
        r = dict(r)
        r["row_no"] = i
        gid = None
        m = _MATCHUP.match(r["matchup"] or "")
        if m and r["game_date"]:
            away, home = m.groups()
            gid = f"NBA_{r['game_date']}_{away}_{home}"
            if r["team"] and r["team"] not in (away, home):
                rep.warnings.append(f"team {r['team']} not in {r['matchup']}")
        r["game_id"] = gid
        sched = schedule.get(gid) if gid else None
        r["season"] = sched["season"] if sched else season_of(r["game_date"])
        r["player_id"] = match_player(players, r["season"], r["team"], r["player_name"])
        out.append(r)
    return out


def season_of(game_date: str | None) -> int | None:
    """Ending-year season label; the 2020 bubble ran to October 2020."""
    if not game_date:
        return None
    y, mo = int(game_date[:4]), int(game_date[5:7])
    if y == 2020 and mo <= 10:
        return 2020
    return y + 1 if mo >= 9 else y


# ── player ids ────────────────────────────────────────────────────────────────

def _surname_key(k: str) -> tuple[str, str] | None:
    """('nicolas claxton') -> ('claxton', 'n'): the surname and the first initial."""
    toks = k.split()
    return (toks[-1], toks[0][0]) if len(toks) >= 2 else None


def load_players(conn) -> dict:
    """Lookups from nba_player_game_log, each kept only where it names one player."""
    rows = conn.execute("""
        SELECT DISTINCT season, team, player_id, player_name FROM nba_player_game_log
    """).fetchall()
    by_team: dict = {}
    by_season: dict = {}
    by_name: dict = {}
    by_surname: dict = {}
    for season, team, pid, name in rows:
        k = norm_name(name)
        by_team[(season, team, k)] = str(pid)
        by_season.setdefault((season, k), set()).add(str(pid))
        by_name.setdefault(k, {}).setdefault(str(pid), set()).add(season)
        sk = _surname_key(k)
        if sk:
            by_surname.setdefault((season, team) + sk, set()).add(str(pid))
    def unique(d):
        return {k: next(iter(v)) for k, v in d.items() if len(v) == 1}
    return {"team": by_team, "season": unique(by_season),
            "any": {k: next(iter(v.items())) for k, v in by_name.items() if len(v) == 1},
            "surname": unique(by_surname)}


def match_player(players: dict, season, team, name) -> str | None:
    """Same season and team first; then a name unique in that season; then a
    name unique across every season, for a player listed all year who never
    played in it (a season-long injury has no game log that season); last, the
    only player on that team that season with this surname and first initial,
    for a name the report prints differently ("Nicolas Claxton" for the game
    log's "Nic Claxton")."""
    if not name or not players:
        return None
    k = norm_name(name)
    sk = _surname_key(k)
    return (players["team"].get((season, team, k))
            or players["season"].get((season, k))
            or _near_season(players.get("any", {}).get(k), season)
            or (players.get("surname", {}).get((season, team) + sk) if sk else None))


ANY_SEASON_WINDOW = 2


def _near_season(hit, season) -> str | None:
    """A name unique across every season counts only if that player has a game
    log within two seasons of this one, so a namesake from another era never
    inherits an unrelated player's status."""
    if not hit or season is None:
        return None
    pid, seasons = hit
    return pid if any(abs(s - season) <= ANY_SEASON_WINDOW for s in seasons) else None


def load_schedule(conn) -> dict:
    out = {}
    for gid, season, ct in conn.execute(
            "SELECT game_id, season, commence_time FROM nba_schedule WHERE game_id IS NOT NULL").fetchall():
        out[gid] = {"season": season, "commence_time": ct}
    return out


def tips_by_date(schedule: dict) -> dict[date, list[datetime]]:
    out: dict[date, list[datetime]] = {}
    for g in schedule.values():
        ct = g["commence_time"]
        if not ct:
            continue
        t = datetime.fromisoformat(str(ct).replace("Z", "+00:00")).astimezone(ET)
        out.setdefault(t.date(), []).append(t)
    return out


# ── database ──────────────────────────────────────────────────────────────────

def ensure_tables(conn) -> None:
    """Create on first use only. `CREATE ... IF NOT EXISTS` is not free on this
    database: it locks, and fires PostgREST's schema reload (data/ddl_guard.py),
    so the catalog is asked first and a current schema runs no DDL at all."""
    from data.ddl_guard import schema_is_current

    if not schema_is_current(conn, "nba_injury_report",
                             columns=("player_id", "reason", "report_ts"),
                             indexes=("nba_injury_report_game_ts", "nba_injury_report_player_ts"),
                             rls=True, revoked_from=API_ROLES):
        conn.execute(REPORT_DDL)
        for stmt in REPORT_INDEXES:
            conn.execute(stmt)
    if not schema_is_current(conn, "nba_injury_report_pulls",
                             columns=("sha256", "parse_notes", "content_sha256", "same_as_url"),
                             indexes=("nba_injury_report_pulls_date_ts",),
                             rls=True, revoked_from=API_ROLES):
        conn.execute(PULLS_DDL)
        # previous_report() reads the date's reports newest first, once per pull.
        conn.execute("CREATE INDEX IF NOT EXISTS nba_injury_report_pulls_date_ts "
                     "ON nba_injury_report_pulls (report_date, report_ts)")
    lock_down(conn, "nba_injury_report")
    lock_down(conn, "nba_injury_report_pulls")
    conn.commit()


def pulled_urls(conn, urls: list[str]) -> set[str]:
    have: set[str] = set()
    for i in range(0, len(urls), 500):
        chunk = urls[i:i + 500]
        have |= {r[0] for r in conn.execute(
            "SELECT url FROM nba_injury_report_pulls WHERE url = ANY(%s)", (chunk,)).fetchall()}
    return have


_INSERT_ROW = """
    INSERT INTO nba_injury_report (source_url, row_no, report_ts, report_date, game_date,
        game_time_et, matchup, game_id, season, team, team_name, player_name,
        player_name_raw, player_id, status, reason)
    VALUES (%(source_url)s, %(row_no)s, %(report_ts)s, %(report_date)s, %(game_date)s,
        %(game_time_et)s, %(matchup)s, %(game_id)s, %(season)s, %(team)s, %(team_name)s,
        %(player_name)s, %(player_name_raw)s, %(player_id)s, %(status)s, %(reason)s)
    ON CONFLICT (source_url, row_no) DO NOTHING
"""
_INSERT_PULL = """
    INSERT INTO nba_injury_report_pulls (url, report_date, slot, http_status, fetched_at,
        report_ts, rows, bytes, sha256, parse_notes, content_sha256, same_as_url)
    VALUES (%s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (url) DO NOTHING
"""


def content_hash(rows: list[dict]) -> str:
    """What a report SAYS, independent of when it said it."""
    keys = ("game_date", "game_time_et", "matchup", "team_name", "player_name_raw",
            "status", "reason")
    body = "\n".join("|".join(str(r.get(k) or "") for k in keys) for r in rows)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def write_report(conn, url: str, d: date, slot: str, status: int, rows: list[dict],
                 report_ts: datetime | None, data: bytes | None, notes: str | None,
                 content: str | None = None, same_as: str | None = None) -> None:
    """The rows and the ledger entry, one transaction, so a crash between them
    cannot leave rows the ledger does not know about, or the reverse. A report
    that repeats its predecessor word for word (`same_as`) writes the ledger
    entry only."""
    stored = [] if same_as else rows
    for r in stored:
        r["source_url"] = url
        r["report_ts"] = report_ts
        r["report_date"] = d.isoformat()
    if stored:
        conn.executemany(_INSERT_ROW, stored)
    conn.execute(_INSERT_PULL, (url, d.isoformat(), slot, status, report_ts,
                                len(rows) if status == 200 else None,
                                len(data) if data else None,
                                hashlib.sha256(data).hexdigest() if data else None,
                                notes, content, same_as))
    conn.commit()


def previous_report(conn, d: date, report_ts: datetime):
    """The ledger's last report of the same date issued before this one:
    (url, content_sha256, same_as_url), or None."""
    return conn.execute("""
        SELECT url, content_sha256, same_as_url FROM nba_injury_report_pulls
         WHERE report_date = %s AND http_status = 200 AND report_ts < %s
         ORDER BY report_ts DESC LIMIT 1
    """, (d.isoformat(), report_ts)).fetchone()


# ── fetching ──────────────────────────────────────────────────────────────────

class Fetcher:
    def __init__(self, pause: float = 0.15):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "Mozilla/5.0 (betting-model injury archive)"
        self.pause = pause
        self.requests = 0

    def get(self, url: str) -> tuple[int, bytes | None]:
        for attempt in range(5):
            try:
                r = self.s.get(url, timeout=45)
                self.requests += 1
                time.sleep(self.pause)
                if r.status_code == 200 and r.content[:4] == b"%PDF":
                    return 200, r.content
                if r.status_code in (403, 404):
                    return r.status_code, None
                logger.warning(f"{url}: HTTP {r.status_code}; retry {attempt + 1}")
            except requests.RequestException as exc:
                logger.warning(f"{url}: {type(exc).__name__}; retry {attempt + 1}")
            time.sleep(2 * (attempt + 1))
        return -1, None


def pull_one(conn, fetcher: Fetcher, d: date, slot: str, schedule: dict, players: dict,
             now: datetime | None = None, dedupe: bool = True) -> dict:
    """Fetch, parse and store one slot.

    DEDUPE. About half of all reports repeat the one before them word for word
    (25 of 51 in the 2026-10-15 pilot). Such a report is written to the ledger
    with same_as_url naming the report whose rows it repeats, and its rows are
    not stored again. The as-of query is unchanged by this: the latest stored
    report at or before T says exactly what the latest fetched one did. It is
    only safe when every earlier slot of the date has been attempted, which is
    why the caller turns it off for the rest of a date after a network failure.
    """
    url = report_url(d, slot)
    status, data = fetcher.get(url)
    now = now or datetime.now(timezone.utc)
    if status != 200:
        final = status in (403, 404) and now - slot_time(d, slot) > MISSING_IS_FINAL_AFTER
        if final:
            write_report(conn, url, d, slot, status, [], None, None, None)
        return {"url": url, "status": status, "rows": 0, "ledgered": final}
    notes: list[str] = []
    try:
        rep = parse_pdf(data)
        rows = finish_rows(rep, schedule, players)
        notes += sorted(set(rep.warnings))
    except Exception as exc:  # noqa: BLE001 -- one bad PDF must not stop the archive
        rep, rows = Report(None), []
        notes.append(f"parse failed: {type(exc).__name__}: {exc}")
    garbled = garbled_note(rows)
    if garbled:
        rows = []
        notes.insert(0, garbled)
    if rep.report_ts is None:
        rows = []          # a row with no publication time cannot be used as-of
        notes.append("no report time in header")
    elif rep.report_ts.astimezone(ET).date() != d:
        # Kept, and the header's time is what is stored; noted so it can be found.
        notes.append(f"header date {rep.report_ts.astimezone(ET).date()} != filename date {d}")
    note = "; ".join(notes)[:2000] or None
    content = same_as = None
    if rep.report_ts is not None and not garbled:
        content = content_hash(rows)
        prev = previous_report(conn, d, rep.report_ts) if dedupe else None
        if prev and prev[1] == content:
            same_as = prev[2] or prev[0]
    write_report(conn, url, d, slot, 200, rows, rep.report_ts, data, note, content, same_as)
    return {"url": url, "status": 200, "rows": 0 if same_as else len(rows),
            "report_ts": rep.report_ts, "notes": note, "same_as": same_as, "ledgered": True}


def pull_with_retry(conn, fetcher, d: date, slot: str, schedule: dict, players: dict,
                    dedupe: bool = True, attempts: int = 4, pause: float = 5.0) -> dict:
    """pull_one, re-run whole when the database drops the connection mid-write.

    Measured 2026-10-15 19:19 ET: one drop closed every backfill connection at
    once and killed the four processes caught mid-write. The wrapper has
    already reconnected when it raises ConnectionLost and the report's
    transaction is gone, so re-running the slot from the fetch is the whole
    recovery: nothing of it was stored, and its place in the date's order is
    unchanged."""
    for attempt in range(1, attempts + 1):
        try:
            return pull_one(conn, fetcher, d, slot, schedule, players, dedupe=dedupe)
        except (ConnectionLost, psycopg2.errors.QueryCanceled) as exc:
            # QueryCanceled: the statement timeout, measured once at 19:28 when
            # an insert waited on a row lock held by a connection the network
            # drop had orphaned on the server. The transaction is aborted;
            # roll it back and re-run the slot.
            if attempt == attempts:
                raise
            if not isinstance(exc, ConnectionLost):
                conn.rollback()
            logger.warning(f"{d} {slot}: {str(exc)[:120]}; re-running the slot ({attempt})")
            time.sleep(pause * attempt)
    raise AssertionError("unreachable")


# Above this share of player rows with no recognised status, a report is not
# stored. Measured: Injury-Report_2019-11-13_03PM ("03:39 PM") prints every
# data cell one column left of its header, so names land under Team and
# statuses under Reason; 42 rows came out, none with a real status. Every other
# report checked so far is at 0.
GARBLED_SHARE = 0.2


def garbled_note(rows: list[dict]) -> str | None:
    """Why a parsed report should not be stored, or None if it is fine."""
    players = [r for r in rows if r.get("status") not in TEAM_LEVEL]
    bad = sum(1 for r in players if r.get("status") not in STATUSES)
    if players and bad / len(players) > GARBLED_SHARE:
        return (f"layout not understood: {bad} of {len(players)} rows have no known "
                f"status; rows not stored")
    return None


def retry_failed() -> dict:
    """Pull again every report that answered 200 but gave no usable rows."""
    conn = get_connection()
    try:
        ensure_tables(conn)
        bad = conn.execute("""
            SELECT url, report_date, slot FROM nba_injury_report_pulls
             WHERE http_status = 200 AND report_ts IS NULL
        """).fetchall()
        schedule, players = load_schedule(conn), load_players(conn)
        conn.commit()
        fetcher = Fetcher()
        out = []
        for url, rd, slot in bad:
            conn.execute("DELETE FROM nba_injury_report WHERE source_url = %s", (url,))
            conn.execute("DELETE FROM nba_injury_report_pulls WHERE url = %s", (url,))
            conn.commit()
            out.append(pull_one(conn, fetcher, date.fromisoformat(rd), slot, schedule, players,
                                dedupe=False))
        return {"retried": len(out), "now_with_rows": sum(1 for r in out if r["rows"])}
    finally:
        conn.close()


def scope_dates(conn, first: int, last: int) -> list[date]:
    """Every regular-season game date in `games`, and the day before each, newest first."""
    rows = conn.execute("""
        SELECT DISTINCT game_date FROM games
         WHERE sport = 'NBA' AND season BETWEEN %s AND %s
    """, (first, last)).fetchall()
    days: set[date] = set()
    for (gd,) in rows:
        d = date.fromisoformat(str(gd)[:10])
        days.add(d)
        days.add(d - timedelta(days=1))
    today = datetime.now(ET).date()
    return sorted((d for d in days if d < today), reverse=True)


def run_dates(dates: list[date], label: str = "run", dedupe: bool = True) -> dict:
    conn = get_connection()
    try:
        ensure_tables(conn)
        schedule = load_schedule(conn)
        tips = tips_by_date(schedule)
        players = load_players(conn)
        conn.commit()
        fetcher = Fetcher()
        totals = {"dates": 0, "requested": 0, "pdfs": 0, "repeats": 0, "rows": 0,
                  "skipped": 0, "noted": 0}
        for d in dates:
            slots = slots_for_date(d, tips.get(d, []))
            urls = [report_url(d, s) for s in slots]
            done = pulled_urls(conn, urls)
            todo = [s for s, u in zip(slots, urls) if u not in done]
            totals["skipped"] += len(slots) - len(todo)
            pdfs = rows = repeats = 0
            chain = dedupe
            for s in todo:
                res = pull_with_retry(conn, fetcher, d, s, schedule, players, dedupe=chain)
                totals["requested"] += 1
                if res["status"] == -1 or (res["status"] == 200 and res.get("report_ts") is None):
                    # A report that is missing from the chain (network failure)
                    # or has no known time (unparsed) may later land between
                    # two reports already compared: store the rest in full.
                    chain = False
                if res["status"] == 200:
                    pdfs += 1
                    rows += res["rows"]
                    repeats += 1 if res.get("same_as") else 0
                    if res.get("notes"):
                        totals["noted"] += 1
                        logger.warning(f"{res['url']}: {res['notes'][:300]}")
            totals["dates"] += 1
            totals["pdfs"] += pdfs
            totals["repeats"] += repeats
            totals["rows"] += rows
            logger.info(f"[{label}] {d} slots={len(slots)} new={len(todo)} pdfs={pdfs} "
                        f"repeats={repeats} rows={rows} | total {totals}")
        return totals
    finally:
        conn.close()


def run_today(now: datetime | None = None) -> dict:
    """The newest report already published for today's ET date, stored if new.

    Walks back from the current quarter-hour (or hour, for an hourly date) to
    the first slot that answers. A 403 here is not written to the ledger
    unless the slot is MISSING_IS_FINAL_AFTER old, so a later run can still
    pick the report up.
    """
    now = now or datetime.now(timezone.utc)
    d = now.astimezone(ET).date()
    conn = get_connection()
    try:
        ensure_tables(conn)
        schedule = load_schedule(conn)
        players = load_players(conn)
        conn.commit()
        fetcher = Fetcher(pause=0.05)
        cands = [s for s in _all_slots(d) if slot_time(d, s) <= now.astimezone(ET)]
        for s in reversed(cands):
            url = report_url(d, s)
            seen = conn.execute("SELECT http_status FROM nba_injury_report_pulls WHERE url = %s",
                                (url,)).fetchone()
            if seen and seen[0] == 200:
                return {"url": url, "status": "already stored"}
            if seen:
                continue                     # a final 403: keep walking back
            # Stored in full, never as a repeat: a later backfill of this date
            # fetches slots this run skipped, and would land between the two.
            res = pull_one(conn, fetcher, d, s, schedule, players, now=now, dedupe=False)
            if res["status"] == 200:
                return res
        return {"date": d.isoformat(), "status": "no report published yet"}
    finally:
        conn.close()


def _all_slots(d: date) -> list[str]:
    out = []
    if d <= OLD_FORMAT_LAST:
        out += [old_slot(h) for h in range(24)]
    if d >= NEW_FORMAT_FIRST:
        out += [new_slot(h, m) for h in range(24) for m in (0, 15, 30, 45)]
    return out


def remap_changes(players: dict, current: list[tuple]) -> list[tuple]:
    """(pid, season, team, name) for every name whose stored ids differ from
    what match_player now says. `current` rows: (season, team, name, ids),
    ids being the distinct player_id values stored for that name (None included)."""
    out = []
    for season, team, name, ids in current:
        pid = match_player(players, season, team, name)
        if set(ids) != {pid}:
            out.append((pid, season, team, name))
    return out


def remap_players() -> dict:
    """Re-match every stored name against nba_player_game_log as it is now,
    and rewrite only the names whose id changed: a NULL that now matches (the
    player has since played), or an id the matching rules no longer support.
    One read of the table, then one UPDATE per 500 changed names."""
    conn = get_connection()
    try:
        players = load_players(conn)
        current = conn.execute("""
            SELECT season, team, player_name, array_agg(DISTINCT player_id)
              FROM nba_injury_report WHERE player_name IS NOT NULL
             GROUP BY 1, 2, 3
        """).fetchall()
        changes = remap_changes(players, [(a, b, c, list(d)) for a, b, c, d in current])
        for i in range(0, len(changes), 500):
            chunk = changes[i:i + 500]
            values = ",".join(["(%s::text, %s::int, %s::text, %s::text)"] * len(chunk))
            conn.execute(f"""
                UPDATE nba_injury_report r SET player_id = v.pid
                  FROM (VALUES {values}) AS v(pid, season, team, name)
                 WHERE r.season = v.season AND r.team IS NOT DISTINCT FROM v.team
                   AND r.player_name = v.name AND r.player_id IS DISTINCT FROM v.pid
            """, [x for h in chunk for x in h])
            conn.commit()
        return {"names": len(current), "changed": len(changes),
                "now_matched": sum(1 for c in changes if c[0]),
                "now_unmatched": sum(1 for c in changes if not c[0])}
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dates", nargs="+", help="ET report dates, YYYY-MM-DD")
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--seasons", nargs=2, type=int, metavar=("FIRST", "LAST"), default=(2019, 2026))
    ap.add_argument("--before", help="backfill only dates before this one (split a run)")
    ap.add_argument("--on-or-after", help="backfill only dates on or after this one")
    ap.add_argument("--oldest-first", action="store_true",
                    help="walk the range from its oldest date: a second process on the same "
                         "range meets the first in the middle, and the ledger skips what is done")
    ap.add_argument("--today", action="store_true")
    ap.add_argument("--remap-players", action="store_true")
    ap.add_argument("--retry-failed", action="store_true")
    ap.add_argument("--no-dedupe", action="store_true",
                    help="store every report's rows, even one that repeats its predecessor")
    a = ap.parse_args()
    if a.today:
        print(run_today())
    elif a.retry_failed:
        print(retry_failed())
    elif a.remap_players:
        print(remap_players())
    elif a.dates:
        print(run_dates([date.fromisoformat(x) for x in a.dates], label="dates",
                        dedupe=not a.no_dedupe))
    elif a.backfill:
        conn = get_connection()
        try:
            dates = scope_dates(conn, *a.seasons)
        finally:
            conn.close()
        if a.before:
            dates = [d for d in dates if d < date.fromisoformat(a.before)]
        if a.on_or_after:
            dates = [d for d in dates if d >= date.fromisoformat(a.on_or_after)]
        if a.oldest_first:
            dates = dates[::-1]
        logger.info(f"backfill: {len(dates)} dates, {dates[0] if dates else None} back to "
                    f"{dates[-1] if dates else None}")
        print(run_dates(dates, label="backfill", dedupe=not a.no_dedupe))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
