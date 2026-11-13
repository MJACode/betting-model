"""EuroLeague identity: the clubs, the season label, the game id, and the
resolver that places the odds feed's events on EuroLeague's own games.

WHO OWNS THE GAMES ROW. EuroLeague's own API (api-live.euroleague.net, written
by data/ingestors/euroleague_api.py). The odds feed never mints a EuroLeague
game: its events are resolved onto the stored schedule by the unordered club
pair nearest the listed start, and when the feed calls EuroLeague's away club
home the names are swapped before any outcome is read, so a stored spread is
the home club's number (CLAUDE.md section 4).

THE ID. `EUROLEAGUE_<season code>_<game code>`, e.g. EUROLEAGUE_E2024_294: the
league's own identifier, which does not change when a game is moved to another
date (the 2020-21 season moved several). A date-built id would mint a twin.

THE SEASON. EuroLeague codes a season by the year it STARTS (E2024 is
2024-25). This repo labels basketball by the year it ENDS (CLAUDE.md section
4), so E2024 is season 2025. The label is threaded from the season code,
never derived from a game's date.

THE CLUBS. EuroLeague's three-letter club codes (MAD, PAN, ULK ...), which
hold across seasons while sponsors rename the clubs ("Cazoo Baskonia", "Kosner
Baskonia" are both BAS). The feed's names map onto them through
config.EUROLEAGUE_ODDS_API_MAP, built from the census of every name on the
feed's 2,164 events of 2020-10 to 2026-11 (27 names, 26 clubs: Fenerbahce
appears twice). A name the map lacks is matched on its accent-folded letters
against the clubs' stored names; one that still fails resolves to None, and
the event is dropped with a warning rather than filed under an invented id.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone

from loguru import logger

import config
from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current

SPORT = "EUROLEAGUE"
ODDS_API_SPORT_KEY = "basketball_euroleague"
COMPETITION = "E"
# A feed event is placed on a stored game whose start is within this of the
# feed's listed start. EuroLeague and the feed agreed to the minute on the
# games checked (2026-11-12); a rescheduled game moves by days, and its id is
# stable, so a wide window only has to tell apart two meetings of one pair,
# which are weeks apart (a playoff series is the closest: two or three days).
MATCH_WINDOW = timedelta(hours=30)

TEAMS = "euroleague_teams"
TEAM_COLS = ("code", "name", "names", "first_season", "last_season", "updated_at")
TEAMS_DDL = """
CREATE TABLE IF NOT EXISTS euroleague_teams (
    code          TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    names         TEXT[] NOT NULL DEFAULT '{}',
    first_season  INTEGER,
    last_season   INTEGER,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""
EVENTS = "euroleague_events"
EVENT_COLS = ("game_id", "identifier", "season", "season_code", "game_code", "phase",
              "round", "game_date", "commence_time", "home_code", "away_code",
              "neutral_site", "status", "played", "venue_code", "venue_name",
              "referees", "audience", "updated_at")
EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS euroleague_events (
    game_id        TEXT PRIMARY KEY,
    identifier     TEXT NOT NULL UNIQUE,
    season         INTEGER NOT NULL,
    season_code    TEXT NOT NULL,
    game_code      INTEGER NOT NULL,
    phase          TEXT,
    round          INTEGER,
    game_date      TEXT NOT NULL,
    commence_time  TEXT,
    home_code      TEXT NOT NULL,
    away_code      TEXT NOT NULL,
    neutral_site   BOOLEAN NOT NULL DEFAULT FALSE,
    status         TEXT,
    played         BOOLEAN NOT NULL DEFAULT FALSE,
    venue_code     TEXT,
    venue_name     TEXT,
    referees       TEXT[],
    audience       INTEGER,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""
EVENTS_INDEX = "idx_euroleague_events_commence"
EVENTS_INDEX_DDL = ("CREATE INDEX IF NOT EXISTS idx_euroleague_events_commence "
                    "ON euroleague_events (commence_time)")


def ensure_tables(conn) -> None:
    """The club and event tables, once, locked down (worker-only,
    data/anon_readable.WORKER_ONLY_TABLES)."""
    changed = False
    if not schema_is_current(conn, TEAMS, columns=TEAM_COLS, rls=True, revoked_from=API_ROLES):
        conn.execute(TEAMS_DDL)
        lock_down(conn, TEAMS)
        changed = True
    if not schema_is_current(conn, EVENTS, columns=EVENT_COLS, indexes=(EVENTS_INDEX,),
                             rls=True, revoked_from=API_ROLES):
        conn.execute(EVENTS_DDL)
        conn.execute(EVENTS_INDEX_DDL)
        lock_down(conn, EVENTS)
        changed = True
    if changed:
        conn.commit()


# ── season and id ────────────────────────────────────────────────────────────

def season_label(season_code: str) -> int:
    """E2024 -> 2025: the ENDING year of the season EuroLeague codes by its start."""
    m = re.fullmatch(r"[A-Z](\d{4})", str(season_code).strip())
    if not m:
        raise ValueError(f"not a EuroLeague season code: {season_code!r}")
    return int(m.group(1)) + 1


def season_code(label: int) -> str:
    """2025 -> E2024."""
    return f"{COMPETITION}{int(label) - 1}"


def build_game_id(identifier: str) -> str:
    """E2024_294 -> EUROLEAGUE_E2024_294."""
    ident = str(identifier).strip()
    if not re.fullmatch(r"[A-Z]\d{4}_\d+", ident):
        raise ValueError(f"not a EuroLeague game identifier: {identifier!r}")
    return f"{SPORT}_{ident}"


# ── club names ───────────────────────────────────────────────────────────────

def fold(name: str) -> str:
    """Lower-case letters and digits only, accents removed: 'Žalgiris' and
    'Zalgiris' both fold to 'zalgiris', 'Beşiktaş J.K.' to 'besiktasjk'."""
    s = unicodedata.normalize("NFKD", str(name or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("ı", "i").replace("ø", "o").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]", "", s.lower())


_MAP_FOLDED: dict[str, str] | None = None
_REGISTRY: list[dict] | None = None


def reset_registry_cache() -> None:
    global _MAP_FOLDED, _REGISTRY
    _MAP_FOLDED = None
    _REGISTRY = None


def _folded_map() -> dict[str, str]:
    global _MAP_FOLDED
    if _MAP_FOLDED is None:
        _MAP_FOLDED = {fold(k): v for k, v in config.EUROLEAGUE_ODDS_API_MAP.items()}
    return _MAP_FOLDED


def load_registry(conn) -> list[dict]:
    """[{code, name, names}] from euroleague_teams; [] when it cannot be read."""
    global _REGISTRY
    if _REGISTRY is not None:
        return _REGISTRY
    try:
        rows = conn.execute(f"SELECT code, name, names FROM {TEAMS}").fetchall()
    except Exception as exc:                                    # noqa: BLE001
        logger.warning(f"{TEAMS} unavailable ({exc}); EuroLeague names resolve from config only")
        try:
            conn.rollback()
        except Exception:                                       # noqa: BLE001
            pass
        rows = []
    _REGISTRY = [{"code": r[0], "name": r[1], "names": list(r[2] or [])} for r in rows]
    return _REGISTRY


def resolve_team_name(name: str, registry: list[dict] | None = None) -> str | None:
    """The club code for a feed name, or None.

    1. config.EUROLEAGUE_ODDS_API_MAP, compared accent-folded.
    2. A stored club name (any season's sponsor name) that folds to the same
       letters, or that contains the folded feed name / is contained in it, when
       exactly one club does. Two or more clubs is None: Tel Aviv has two clubs
       ('Maccabi Tel Aviv', 'Hapoel Tel Aviv'), Istanbul three."""
    key = fold(name)
    if not key:
        return None
    hit = _folded_map().get(key)
    if hit:
        return hit
    if not registry:
        return None
    exact = {t["code"] for t in registry
             if any(fold(n) == key for n in [t["name"], *t["names"]])}
    if len(exact) == 1:
        return exact.pop()
    if exact:
        return None
    if len(key) < 6:
        return None
    partial = {t["code"] for t in registry
               if any((key in fold(n) or fold(n) in key) and len(fold(n)) >= 6
                      for n in [t["name"], *t["names"]])}
    return partial.pop() if len(partial) == 1 else None


# ── matching events to games ─────────────────────────────────────────────────

def _ts(v) -> datetime | None:
    if v is None:
        return None
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def load_games_window(conn, first: str, last: str) -> list[dict]:
    """Stored, not-cancelled EuroLeague games with game_date in [first, last]:
    game_id, game_date, commence_time, home_code, away_code."""
    try:
        rows = conn.execute(
            f"SELECT game_id, game_date, commence_time, home_code, away_code FROM {EVENTS} "
            "WHERE game_date BETWEEN %s AND %s AND COALESCE(status, '') <> 'Cancelled'",
            (first, last)).fetchall()
    except Exception as exc:                                    # noqa: BLE001
        logger.warning(f"{EVENTS} unavailable ({exc}); EuroLeague odds cannot resolve")
        try:
            conn.rollback()
        except Exception:                                       # noqa: BLE001
            pass
        return []
    return [{"game_id": r[0], "game_date": r[1], "commence_time": r[2],
             "home_code": r[3], "away_code": r[4]} for r in rows]


def match_event(games: list[dict], home_code: str | None, away_code: str | None,
                commence_time: str) -> tuple[str, bool] | None:
    """(game_id, flipped) for the stored game this feed event is, or None.

    The unordered club pair, with a start within MATCH_WINDOW of the feed's;
    the nearest start wins, and an exact tie is None. `flipped` is True when
    the feed's home club is EuroLeague's away club (a Final Four game, or the
    feed's error): the caller swaps the names before reading any outcome."""
    if not home_code or not away_code or home_code == away_code:
        return None
    t0 = _ts(commence_time)
    if t0 is None:
        return None
    pair = {home_code, away_code}
    cands = []
    for g in games:
        if {g["home_code"], g["away_code"]} != pair:
            continue
        t = _ts(g.get("commence_time"))
        if t is None:
            continue
        gap = abs((t - t0).total_seconds())
        if gap <= MATCH_WINDOW.total_seconds():
            cands.append((gap, g))
    if not cands:
        return None
    cands.sort(key=lambda c: c[0])
    if len(cands) > 1 and cands[0][0] == cands[1][0]:
        return None
    g = cands[0][1]
    return g["game_id"], g["home_code"] != home_code


class Resolver:
    """The `resolve_game_id` contract of odds_ingestor._process_events over a
    fixed list of games: __call__(home_name, away_name, commence_time) ->
    (game_id, flipped) or None. Misses are counted for the report."""

    def __init__(self, registry: list[dict], games: list[dict]):
        self.registry = registry
        self.games = games
        self._codes: dict[str, str | None] = {}
        self.unresolved_names: dict[str, int] = {}
        self.no_game: dict[str, int] = {}

    def code(self, name: str) -> str | None:
        if name not in self._codes:
            self._codes[name] = resolve_team_name(name, self.registry)
        return self._codes[name]

    def __call__(self, home_name: str, away_name: str, commence_time: str):
        home, away = self.code(home_name), self.code(away_name)
        hit = match_event(self.games, home, away, commence_time)
        if hit is None:
            for n, c in ((home_name, home), (away_name, away)):
                if c is None:
                    self.unresolved_names[n] = self.unresolved_names.get(n, 0) + 1
            if home and away:
                k = f"{away_name} @ {home_name}"
                self.no_game[k] = self.no_game.get(k, 0) + 1
        return hit

    def report(self) -> str:
        names = ", ".join(f"{n} ({c})" for n, c in sorted(self.unresolved_names.items()))
        pairs = ", ".join(f"{n} ({c})" for n, c in sorted(self.no_game.items())[:25])
        return (f"unresolved names: {len(self.unresolved_names)} [{names or 'none'}]; "
                f"resolved pairs with no stored game: {len(self.no_game)} [{pairs or 'none'}]")


def make_resolver(conn, around_date: str, days_back: int = 2, days_fwd: int = 30):
    """A Resolver over the stored games near `around_date`, or None when the
    schedule window is empty (the caller then skips EuroLeague for the pass
    and never mints an id)."""
    day = datetime.fromisoformat(str(around_date)[:10])
    games = load_games_window(conn, (day - timedelta(days=days_back)).date().isoformat(),
                              (day + timedelta(days=days_fwd)).date().isoformat())
    if not games:
        logger.warning(f"EuroLeague: no stored games near {around_date}; odds skipped")
        return None
    return Resolver(load_registry(conn), games)
