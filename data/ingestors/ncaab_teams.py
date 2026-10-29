"""
Men's college basketball (NCAAB) identity: teams, games, and the odds join.

WHO OWNS THE GAMES ROW
----------------------
ESPN's schedule does. Every NCAAB games row is written by the ESPN
schedule/results ingestor (data/ingestors/ncaab_espn_ingestor.py) in ESPN's
home/away orientation, and nothing else may mint one. The odds feed RESOLVES
onto those rows (the NFL shape, odds_ingestor.NFL_GAMES_ARE_NOT_OURS), for two
reasons that each cost NCAAF real bets:

* 360-odd Division I schools collide in three letters. The odds ingestor's
  fallback turns "Kentucky Wildcats" and "Kansas State Wildcats" into the
  same id (measured 2026-10-26: NCAAB_2026-11-03_WIL_WIL).
* On a neutral court the feed may call the other team home. NCAAF minted a
  second games row for those (twins: odds on one, the final on the other).
  Here the feed's event is matched on the UNORDERED pair and, when its home is
  ESPN's away, the caller swaps the names before the outcomes are parsed, so
  the stored spread is ESPN's home number (CLAUDE.md §4: scored_line is the
  HOME number). About half of Thanksgiving-week games are neutral (ESPN,
  2026-11-25: 30 of 69).

THE THREE TABLES (worker-only, created on first write, never read by the app)
-----------------------------------------------------------------------------
ncaab_teams   one row per ESPN team id: every Division I school AND every
              non-D1 opponent ESPN lists, so a buy-game opponent resolves
              instead of being guessed (NCAAF's fix was loading every
              classification).
ncaab_events  ESPN event id <-> our game_id, with both teams' ESPN ids. The
              odds join reads THIS, not team names.
ncaab_venues  ESPN venue id, name, city/state, coordinates and elevation once
              they are filled in.

Season label: the ENDING year, as ESPN labels it (2026-27 is 2027, ESPN's own
season.year), the same rule as the NBA and NHL. Dates: the America/New_York
calendar date of the tip, the rule every games row in this repo follows.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

from loguru import logger

import config
from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current

SPORT = "NCAAB"
ODDS_API_SPORT_KEY = "basketball_ncaab"
_ET = ZoneInfo("America/New_York")


# ── tables ───────────────────────────────────────────────────────────────────

TEAMS_TABLE = "ncaab_teams"
TEAMS_COLS = ("espn_id", "school", "slug", "mascot", "display_name", "short_name",
              "abbreviation", "conference", "conference_abbr", "is_d1",
              "alt_names", "updated_at")
TEAMS_DDL = """
CREATE TABLE IF NOT EXISTS ncaab_teams (
    espn_id          INTEGER PRIMARY KEY,
    school           TEXT NOT NULL,
    slug             TEXT NOT NULL UNIQUE,
    mascot           TEXT,
    display_name     TEXT,
    short_name       TEXT,
    abbreviation     TEXT,
    conference       TEXT,
    conference_abbr  TEXT,
    is_d1            BOOLEAN NOT NULL DEFAULT FALSE,
    alt_names        TEXT,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

EVENTS_TABLE = "ncaab_events"
EVENTS_COLS = ("espn_event_id", "game_id", "season", "game_date", "commence_time",
               "home_espn_id", "away_espn_id", "neutral_site", "conference_game",
               "venue_id", "season_type", "status", "notes", "updated_at")
EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS ncaab_events (
    espn_event_id    BIGINT PRIMARY KEY,
    game_id          TEXT NOT NULL UNIQUE,
    season           INTEGER NOT NULL,
    game_date        TEXT NOT NULL,
    commence_time    TEXT,
    home_espn_id     INTEGER NOT NULL,
    away_espn_id     INTEGER NOT NULL,
    neutral_site     BOOLEAN,
    conference_game  BOOLEAN,
    venue_id         INTEGER,
    season_type      INTEGER,
    status           TEXT,
    notes            TEXT,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""
EVENTS_INDEX_DDL = ("CREATE INDEX IF NOT EXISTS idx_ncaab_events_date "
                    "ON ncaab_events (game_date)")

VENUES_TABLE = "ncaab_venues"
VENUES_COLS = ("venue_id", "name", "city", "state", "indoor", "latitude",
               "longitude", "elevation_ft", "updated_at")
VENUES_DDL = """
CREATE TABLE IF NOT EXISTS ncaab_venues (
    venue_id      INTEGER PRIMARY KEY,
    name          TEXT,
    city          TEXT,
    state         TEXT,
    indoor        BOOLEAN,
    latitude      DOUBLE PRECISION,
    longitude     DOUBLE PRECISION,
    elevation_ft  DOUBLE PRECISION,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""


def ensure_tables(conn) -> None:
    """Create the three tables once, locked down, and cost nothing after that.

    data/ddl_guard.schema_is_current answers from one catalog read, so a pass
    that finds the tables current fires no DDL (a CREATE ... IF NOT EXISTS
    still trips Supabase's pgrst_ddl_watch). Committed on its own.
    """
    changed = False
    if not schema_is_current(conn, TEAMS_TABLE, columns=TEAMS_COLS,
                             rls=True, revoked_from=API_ROLES):
        conn.execute(TEAMS_DDL)
        lock_down(conn, TEAMS_TABLE)
        changed = True
    if not schema_is_current(conn, EVENTS_TABLE, columns=EVENTS_COLS,
                             indexes=("idx_ncaab_events_date",),
                             rls=True, revoked_from=API_ROLES):
        conn.execute(EVENTS_DDL)
        conn.execute(EVENTS_INDEX_DDL)
        lock_down(conn, EVENTS_TABLE)
        changed = True
    if not schema_is_current(conn, VENUES_TABLE, columns=VENUES_COLS,
                             rls=True, revoked_from=API_ROLES):
        conn.execute(VENUES_DDL)
        lock_down(conn, VENUES_TABLE)
        changed = True
    if changed:
        conn.commit()


# ── names, slugs, ids, seasons, dates ────────────────────────────────────────

def ncaab_slug(school: str) -> str:
    """A school name as it appears inside a game_id.

    Same rule as NCAAF (cfbd_ingestor.ncaaf_slug): accents stripped, every
    non-alphanumeric run collapsed to one hyphen. "Miami (OH)" -> "miami-oh",
    "Texas A&M" -> "texas-a-m", "Saint Mary's" -> "saint-mary-s".
    """
    if not school:
        return ""
    s = unicodedata.normalize("NFKD", str(school))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "-", s.lower())
    return s.strip("-")


def build_ncaab_game_id(game_date: str, away_slug: str, home_slug: str) -> str:
    """NCAAB_<ET date>_<away slug>_<home slug>, in ESPN's orientation."""
    return f"NCAAB_{game_date}_{away_slug}_{home_slug}"


def ncaab_season_label(game_date: str) -> int:
    """The ENDING year: Nov 2026 -> 2027, Mar 2027 -> 2027 (ESPN's season.year).

    The season opens in early November and the title game is in April, so a
    month of October or later belongs to the next calendar year's label.
    """
    y, m = int(game_date[:4]), int(game_date[5:7])
    return y + 1 if m >= 10 else y


def eastern_game_date(start) -> str:
    """The America/New_York calendar date of an ISO timestamp.

    A bare YYYY-MM-DD is already a calendar date. A naive timestamp is read as
    UTC (ESPN and the odds feed both send UTC). Unparseable input falls back to
    its first ten characters rather than inventing a date.
    """
    raw = str(start or "").strip()
    if len(raw) == 10 and raw[4:5] == "-" and raw[7:8] == "-":
        return raw
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return raw[:10]
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_ET).strftime("%Y-%m-%d")


@lru_cache(maxsize=16384)
def _fold(v: str) -> str:
    """Case-, accent- and punctuation-insensitive comparison key.

    Apostrophes vanish ("Saint Mary's" = "Saint Marys", "Hawai'i" =
    "Hawaii"); every other punctuation run becomes a space, so "A&M" folds
    the same as "A M" and "Miami (OH)" the same as "Miami OH".

    Cached: every resolve_team_name call folds the registry's 1,348 rows
    several times over, and the 5-minute capture resolves each event's two
    names twice (measured 2026-10-29: 14-127 ms a call uncached, 1-9 ms
    cached).
    """
    v = unicodedata.normalize("NFKD", (v or "").strip().lower())
    v = "".join(c for c in v if not unicodedata.combining(c))
    v = re.sub(r"['‘’`]", "", v)
    v = re.sub(r"[^a-z0-9]+", " ", v)
    return " ".join(v.split())


# ── the registry and the name resolver ───────────────────────────────────────

_TEAM_CACHE: list[dict] | None = None


def load_registry(conn) -> list[dict]:
    """Every ncaab_teams row, cached for the process.

    Each dict: espn_id, school, slug, mascot, display_name, short_name,
    abbreviation, is_d1, alt (list of alternate names). An unreadable or empty
    table yields an empty list (logged, never cached): the resolver then
    resolves nothing, and the caller drops the event rather than guessing.
    """
    global _TEAM_CACHE
    if _TEAM_CACHE is not None:
        return _TEAM_CACHE
    try:
        rows = conn.execute(
            "SELECT espn_id, school, slug, mascot, display_name, short_name, "
            "abbreviation, is_d1, alt_names FROM ncaab_teams").fetchall()
    except Exception as exc:                                    # noqa: BLE001
        logger.warning(f"ncaab_teams unavailable ({exc}); NCAAB names will not resolve")
        try:
            conn.rollback()
        except Exception:                                       # noqa: BLE001
            pass
        rows = []
    teams = [
        {"espn_id": int(r[0]), "school": r[1], "slug": r[2], "mascot": r[3],
         "display_name": r[4], "short_name": r[5], "abbreviation": r[6],
         "is_d1": bool(r[7]),
         "alt": [a for a in (r[8] or "").split("|") if a]}
        for r in rows
    ]
    # An EMPTY read is never cached. The worker runs every job in one process,
    # and a job that looked before the ESPN backfill created the table (the
    # declared feed probe does) would otherwise leave every later NCAAB job,
    # the live odds pass included, resolving nothing until a restart
    # (2026-10-26 review).
    if teams:
        _TEAM_CACHE = teams
    return teams


def reset_registry_cache() -> None:
    """Drop the cached registry (call after the teams table is re-ingested)."""
    global _TEAM_CACHE
    _TEAM_CACHE = None


def _rest_is_mascot(rest: str, mascot: str | None) -> bool:
    """Is the folded text left after a school's name that school's mascot?

    Exact, or the same final word (a book that shortens a two-word mascot).
    Anything else ("state bulldogs", "christian wildcats") is a DIFFERENT
    school that happens to start with this one's name, the exact trap that
    filed "Indiana State Sycamores" under Indiana in NCAAF.
    """
    m = _fold(mascot or "")
    if not m or not rest:
        return False
    if rest == m:
        return True
    return rest.split()[-1] == m.split()[-1]


# ── the last step: the feed's shortened school names ────────────────────────
#
# The odds feed shortens school names that ESPN spells out. "Michigan St
# Spartans" is ESPN's Michigan State, "CSU Fullerton Titans" is Cal State
# Fullerton, "Loyola (Chi) Ramblers" is Loyola Chicago. No earlier step places
# them: the 2026-10-29 history purchase (worker job 805227) stored 137,007
# event snapshots raw in ncaab_odds_unmatched because 82 feed names resolved
# to no team. This step runs only after every earlier step has returned None,
# so a name that resolved before it existed resolves to the same team now.

# A feed abbreviation (folded) -> what it may stand for. Each token is also
# tried as written, so the "St" of "Mt. St. Mary's" can stay "St". Every entry
# is here because a feed name stored on 2026-10-29 needs it.
SCHOOL_ABBREVIATIONS: dict[str, tuple[str, ...]] = {
    "st": ("state",),            # "East Tennessee St Buccaneers" -> East Tennessee State
    "se": ("southeast",),        # "SE Missouri St Redhawks" -> Southeast Missouri State
    "univ": ("university",),     # "Boston Univ. Terriers" -> Boston University
    "csu": ("cal state",),       # "CSU Fullerton Titans" -> Cal State Fullerton
    "cal": ("california",),      # "Cal Baptist Lancers" -> California Baptist
    "chi": ("chicago",),         # "Loyola (Chi) Ramblers" -> Loyola Chicago
    "mt": ("mount",),            # "Mt. St. Mary's Mountaineers" -> Mount St. Mary's
    "bkn": ("brooklyn",),        # "St. Francis BKN Terriers" -> St. Francis Brooklyn
    "intl": ("international",),  # "Florida Int'l Golden Panthers" -> Florida International
}

# ESPN team id -> the other names the feed gives that team's mascot (folded).
# Keyed by team, not by word: another school can carry the same word.
MASCOT_ALIASES: dict[int, tuple[str, ...]] = {
    2253: ("antelopes",),        # Grand Canyon: ESPN "Lopes", the feed "Antelopes"
    2229: ("golden panthers",),  # Florida International: ESPN "Panthers", the feed "Golden Panthers"
}

# A school part with more abbreviations than this is not tried (each one
# doubles the spellings). The longest measured feed name has two.
_MAX_ABBREVIATIONS = 4


def _school_spellings(tokens: list[str]) -> set[str]:
    """Every spelling of a feed school part: each token as written or expanded."""
    forms = [""]
    for tok in tokens:
        options = (tok,) + SCHOOL_ABBREVIATIONS.get(tok, ())
        forms = [f"{f} {o}".strip() for f in forms for o in options]
    return set(forms)


def _resolve_shortened_school(key: str, registry: list[dict]) -> int | None:
    """The last step of resolve_team_name, on the folded name `key`.

    Splits the name into a school part and the rest at every word. The school
    part, with its abbreviations expanded, must equal the school, short name
    or an alternate name of exactly ONE registry team, and the rest must be
    that team's mascot (exactly) or one of its MASCOT_ALIASES. Exactly one
    team across every split and spelling resolves; anything else is None, and
    so is a name where one spelling belongs to two teams that both carry the
    rest as their mascot. A spelling two teams share is otherwise skipped:
    "Wright State" is both ESPN 2750's school and 134850's short name, so
    "Wright St Raiders" places 2750 through its short name "Wright St".
    """
    by_name: dict[str, set[int]] = {}
    mascots: dict[int, set[str]] = {}
    for t in registry:
        tid = t["espn_id"]
        for n in (t.get("school"), t.get("short_name"), *(t.get("alt") or ())):
            folded = _fold(n or "")
            if folded:
                by_name.setdefault(folded, set()).add(tid)
        own = mascots.setdefault(tid, set())
        if _fold(t.get("mascot") or ""):
            own.add(_fold(t["mascot"]))
        own.update(MASCOT_ALIASES.get(tid, ()))

    tokens = key.split()
    hits: set[int] = set()
    shared = False
    for i in range(1, len(tokens)):
        school, rest = tokens[:i], " ".join(tokens[i:])
        if sum(1 for tok in school if tok in SCHOOL_ABBREVIATIONS) > _MAX_ABBREVIATIONS:
            continue
        for spelling in _school_spellings(school):
            ids = by_name.get(spelling, set())
            fits = {tid for tid in ids if rest in mascots.get(tid, ())}
            if len(fits) > 1:
                shared = True          # two teams answer to this school AND mascot
            elif len(ids) == 1:
                hits |= fits
    if shared or len(hits) != 1:
        return None
    return next(iter(hits))


def resolve_team_name(name: str, registry: list[dict]) -> int | None:
    """An odds-feed team name -> ESPN team id, or None when it does not resolve.

    Order: config.NCAAB_ODDS_API_MAP override (name -> ESPN id) -> exact ESPN
    display name -> "school mascot" -> exact school -> short name -> alternate
    name -> the longest school that prefixes the name, only when the rest is
    that school's mascot -> LAST, the feed's shortened school names
    (_resolve_shortened_school: "Michigan St Spartans", "CSU Fullerton
    Titans"), tried only when every step before it found nothing. Ambiguity at
    any step (two teams claim the same folded name) resolves to None, never to
    a guess: an unresolved event is dropped and counted, a mis-resolved one
    settles on the wrong game.
    """
    if not name:
        return None
    override = (getattr(config, "NCAAB_ODDS_API_MAP", None) or {}).get(name)
    if override:
        return int(override)
    if not registry:
        return None
    key = _fold(name)

    def unique(hits):
        ids = {t["espn_id"] for t in hits}
        return next(iter(ids)) if len(ids) == 1 else None

    for field in ("display_name",):
        hit = unique([t for t in registry if _fold(t.get(field) or "") == key])
        if hit is not None:
            return hit
    hit = unique([t for t in registry if t.get("mascot")
                  and _fold(f"{t['school']} {t['mascot']}") == key])
    if hit is not None:
        return hit
    for field in ("school", "short_name"):
        hit = unique([t for t in registry if _fold(t.get(field) or "") == key])
        if hit is not None:
            return hit
    hit = unique([t for t in registry if any(_fold(a) == key for a in t["alt"])])
    if hit is not None:
        return hit

    best, best_len, tie = None, -1, False
    for t in registry:
        sl = _fold(t["school"])
        if not sl or not key.startswith(sl):
            continue
        rest = key[len(sl):]
        if rest and not rest.startswith(" "):
            continue
        rest = rest.strip()
        if rest and not _rest_is_mascot(rest, t.get("mascot")):
            continue
        if len(sl) > best_len:
            best, best_len, tie = t["espn_id"], len(sl), False
        elif len(sl) == best_len and t["espn_id"] != best:
            tie = True
    if best is not None and not tie:
        return best
    return _resolve_shortened_school(key, registry)


# ── matching an odds event onto ESPN's schedule ──────────────────────────────

def load_games_window(conn, first: str, last: str) -> list[dict]:
    """NCAAB games with game_date in [first, last], with both ESPN team ids.

    Each dict: game_id, game_date, commence_time, home_espn_id, away_espn_id.
    Read from ncaab_events, which the ESPN ingestor writes in the same
    transaction as the games row.
    """
    try:
        rows = conn.execute(
            "SELECT game_id, game_date, commence_time, home_espn_id, away_espn_id "
            "FROM ncaab_events WHERE game_date BETWEEN %s AND %s",
            (first, last)).fetchall()
    except Exception as exc:                                    # noqa: BLE001
        logger.warning(f"ncaab_events unavailable ({exc}); NCAAB odds cannot resolve")
        try:
            conn.rollback()
        except Exception:                                       # noqa: BLE001
            pass
        return []
    return [{"game_id": r[0], "game_date": r[1], "commence_time": r[2],
             "home_espn_id": int(r[3]), "away_espn_id": int(r[4])} for r in rows]


def _ts(v) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def match_event(games: list[dict], home_id: int | None, away_id: int | None,
                commence_time: str, max_day_skew: int = 1) -> tuple[str, bool] | None:
    """(game_id, flipped) for the scheduled game this odds event is, or None.

    Matches the UNORDERED team pair within `max_day_skew` ET days of the
    event's tip. `flipped` is True when the feed's home team is ESPN's away
    team: the caller must then swap home and away before parsing outcomes.
    Two candidates (a team pair meeting twice inside the window, which a
    conference tournament can produce) go to the one whose tip is nearest the
    event's; an exact tie resolves to None.
    """
    if home_id is None or away_id is None or home_id == away_id:
        return None
    d = eastern_game_date(commence_time)
    try:
        day = date.fromisoformat(d)
    except ValueError:
        return None
    lo = (day - timedelta(days=max_day_skew)).isoformat()
    hi = (day + timedelta(days=max_day_skew)).isoformat()
    pair = {home_id, away_id}
    cands = [g for g in games if lo <= g["game_date"] <= hi
             and {g["home_espn_id"], g["away_espn_id"]} == pair]
    if not cands:
        return None
    if len(cands) > 1:
        t0 = _ts(commence_time)

        def gap(g):
            t = _ts(g.get("commence_time"))
            return abs((t - t0).total_seconds()) if (t and t0) else float("inf")
        cands.sort(key=gap)
        if gap(cands[0]) == gap(cands[1]):
            return None
    g = cands[0]
    return g["game_id"], (g["home_espn_id"] != home_id)


def make_resolver(conn, around_date: str, days_back: int = 2, days_fwd: int = 10):
    """A `resolve_game_id` callable for odds_ingestor._process_events, or None.

    Returns resolve(home_name, away_name, commence_time) -> (game_id, flipped)
    or None. FAILS OPEN TO None when the registry or the schedule window is
    empty, and the caller must then SKIP NCAAB rather than mint ids.
    """
    registry = load_registry(conn)
    if not registry:
        logger.warning("NCAAB: team registry is empty; odds skipped")
        return None
    anchor = date.fromisoformat(str(around_date)[:10])
    games = load_games_window(conn, (anchor - timedelta(days=days_back)).isoformat(),
                              (anchor + timedelta(days=days_fwd)).isoformat())
    if not games:
        logger.warning(f"NCAAB: no scheduled games near {around_date}; odds skipped")
        return None

    def resolve(home_name: str, away_name: str, commence_time: str):
        return match_event(games, resolve_team_name(home_name, registry),
                           resolve_team_name(away_name, registry), commence_time)

    return resolve
