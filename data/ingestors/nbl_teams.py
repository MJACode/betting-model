"""NBL identity: the clubs, the season label, the game id, and the resolver
that places the odds feed's events on ESPN's NBL schedule.

THE LEAGUE. Australia's National Basketball League: ten clubs, FIBA rules
(four 10-minute quarters, 5-minute overtimes), September to March.

WHO OWNS THE GAMES ROW. ESPN's site API (league 55, `basketball/nbl`, written by
data/ingestors/nbl_espn.py). The odds feed never mints an NBL game: its events
are resolved onto the stored schedule by the unordered club pair nearest the
listed start, and when the feed calls ESPN's away club home the names are
swapped before any outcome is read, so a stored spread is the home club's
number (CLAUDE.md section 4). The matching itself is EuroLeague's
(data/ingestors/euroleague_teams.match_event), which is sport-blind.

THE ID. `NBL_<ESPN event id>`, e.g. NBL_401875310. The league's own match ids
(Genius Sports) were not read: the league's site API was refused to a request
carrying the site's own headers (2026-11-14), and ESPN answers plainly.

THE SEASON. Labelled by the year it ENDS (CLAUDE.md section 4): 2026-27 is
2027, which is also ESPN's own `season.year`. The label is ESPN's, threaded
from each event, never derived from a game's date (nbl_espn checks the two
agree).

THE CLUBS. ESPN's abbreviations (ADL, BRI, CNS, HWK, MEL, NZL, PER, PNX, SYD,
TAS; ESPN team ids 1 to 10), which held across every season ESPN serves
(2022-23 to 2026-27, read 2026-11-14). A preseason opponent from outside the
league (Shanghai Sharks, ESPN id 110305, no abbreviation) has no code, and its
games never reach `games`. The feed's names map onto the codes through
config.NBL_ODDS_API_MAP; a name the map lacks is matched on its folded letters
against the clubs' stored names, and one that still fails resolves to None, so
the event is dropped with a warning rather than filed under an invented id.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from loguru import logger

import config
from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current
from data.ingestors import euroleague_teams as _el

SPORT = "NBL"
ODDS_API_SPORT_KEY = "basketball_nbl"
ESPN_LEAGUE = "nbl"
REGULATION_PERIODS = 4
# A feed event is placed on a stored game whose start is within this of the
# feed's listed start; the nearest wins. Two meetings of one pair are days
# apart (a finals series is the closest: two or three days).
MATCH_WINDOW = timedelta(hours=30)

TEAMS = "nbl_teams"
TEAM_COLS = ("code", "espn_id", "name", "names", "first_season", "last_season", "updated_at")
TEAMS_DDL = """
CREATE TABLE IF NOT EXISTS nbl_teams (
    code          TEXT PRIMARY KEY,
    espn_id       INTEGER NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    names         TEXT[] NOT NULL DEFAULT '{}',
    first_season  INTEGER,
    last_season   INTEGER,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""
EVENTS = "nbl_events"
EVENT_COLS = ("game_id", "espn_id", "season", "season_type", "game_date", "commence_time",
              "home_code", "away_code", "home_espn_id", "away_espn_id", "neutral_site",
              "status", "played", "venue_name", "venue_city", "updated_at")
EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS nbl_events (
    game_id        TEXT PRIMARY KEY,
    espn_id        BIGINT NOT NULL UNIQUE,
    season         INTEGER NOT NULL,
    season_type    TEXT NOT NULL,
    game_date      TEXT NOT NULL,
    commence_time  TEXT,
    home_code      TEXT,
    away_code      TEXT,
    home_espn_id   INTEGER NOT NULL,
    away_espn_id   INTEGER NOT NULL,
    neutral_site   BOOLEAN NOT NULL DEFAULT FALSE,
    status         TEXT,
    played         BOOLEAN NOT NULL DEFAULT FALSE,
    venue_name     TEXT,
    venue_city     TEXT,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""
EVENTS_INDEX = "idx_nbl_events_commence"
EVENTS_INDEX_DDL = ("CREATE INDEX IF NOT EXISTS idx_nbl_events_commence "
                    "ON nbl_events (commence_time)")

# Season types that are real league games. Preseason games (the Blitz, and
# exhibitions against clubs from outside the league) stay in nbl_events only.
LEAGUE_SEASON_TYPES = frozenset({"regular-season", "post-season"})


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

def season_label_for_date(game_date: str) -> int:
    """The ending-year label a game on this date belongs to: from July, the
    season that ends next year. Only a CHECK on ESPN's own label
    (nbl_espn.parse_event); never the stored value."""
    d = datetime.fromisoformat(str(game_date)[:10])
    return d.year + 1 if d.month >= 7 else d.year


def build_game_id(espn_id) -> str:
    """401875310 -> NBL_401875310."""
    s = str(espn_id).strip()
    if not s.isdigit():
        raise ValueError(f"not an ESPN event id: {espn_id!r}")
    return f"{SPORT}_{s}"


# ── club names ───────────────────────────────────────────────────────────────

fold = _el.fold

_MAP_FOLDED: dict[str, str] | None = None
_REGISTRY: list[dict] | None = None


def reset_registry_cache() -> None:
    global _MAP_FOLDED, _REGISTRY
    _MAP_FOLDED = None
    _REGISTRY = None


def _folded_map() -> dict[str, str]:
    global _MAP_FOLDED
    if _MAP_FOLDED is None:
        _MAP_FOLDED = {fold(k): v for k, v in config.NBL_ODDS_API_MAP.items()}
    return _MAP_FOLDED


def load_registry(conn) -> list[dict]:
    """[{code, name, names}] from nbl_teams; [] when it cannot be read."""
    global _REGISTRY
    if _REGISTRY is not None:
        return _REGISTRY
    try:
        rows = conn.execute(f"SELECT code, name, names FROM {TEAMS}").fetchall()
    except Exception as exc:                                    # noqa: BLE001
        logger.warning(f"{TEAMS} unavailable ({exc}); NBL names resolve from config only")
        try:
            conn.rollback()
        except Exception:                                       # noqa: BLE001
            pass
        rows = []
    _REGISTRY = [{"code": r[0], "name": r[1], "names": list(r[2] or [])} for r in rows]
    return _REGISTRY


def resolve_team_name(name: str, registry: list[dict] | None = None) -> str | None:
    """The club code for a feed name, or None.

    1. config.NBL_ODDS_API_MAP, compared folded.
    2. A stored club name that folds to the same letters, when exactly one
       club does. Melbourne has two clubs ('Melbourne United', 'South East
       Melbourne Phoenix'), so no partial match is tried: a contained name
       would be ambiguous exactly where it matters."""
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
    return exact.pop() if len(exact) == 1 else None


# ── matching events to games ─────────────────────────────────────────────────

def load_games_window(conn, first: str, last: str) -> list[dict]:
    """Stored NBL league games (regular season and finals, not cancelled) with
    game_date in [first, last]: game_id, game_date, commence_time, home_code,
    away_code."""
    try:
        rows = conn.execute(
            f"SELECT game_id, game_date, commence_time, home_code, away_code FROM {EVENTS} "
            "WHERE game_date BETWEEN %s AND %s AND season_type = ANY(%s) "
            "AND home_code IS NOT NULL AND away_code IS NOT NULL "
            "AND COALESCE(status, '') NOT IN ('STATUS_CANCELED', 'STATUS_POSTPONED')",
            (first, last, sorted(LEAGUE_SEASON_TYPES))).fetchall()
    except Exception as exc:                                    # noqa: BLE001
        logger.warning(f"{EVENTS} unavailable ({exc}); NBL odds cannot resolve")
        try:
            conn.rollback()
        except Exception:                                       # noqa: BLE001
            pass
        return []
    return [{"game_id": r[0], "game_date": r[1], "commence_time": r[2],
             "home_code": r[3], "away_code": r[4]} for r in rows]


def match_event(games: list[dict], home_code: str | None, away_code: str | None,
                commence_time: str) -> tuple[str, bool] | None:
    """(game_id, flipped) for the stored game this feed event is, or None:
    the unordered club pair, a start within MATCH_WINDOW, the nearest start,
    an exact tie None (euroleague_teams.match_event, with this window)."""
    if not home_code or not away_code or home_code == away_code:
        return None
    t0 = _el._ts(commence_time)
    if t0 is None:
        return None
    pair = {home_code, away_code}
    cands = []
    for g in games:
        if {g["home_code"], g["away_code"]} != pair:
            continue
        t = _el._ts(g.get("commence_time"))
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


class Resolver(_el.Resolver):
    """The `resolve_game_id` contract of odds_ingestor._process_events over a
    fixed list of NBL games: __call__(home_name, away_name, commence_time) ->
    (game_id, flipped) or None. EuroLeague's class, with NBL's names and
    window; misses are counted for the report."""

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


def make_resolver(conn, around_date: str, days_back: int = 2, days_fwd: int = 30):
    """A Resolver over the stored games near `around_date`, or None when the
    schedule window is empty (the caller then skips the NBL for the pass and
    never mints an id)."""
    day = datetime.fromisoformat(str(around_date)[:10])
    games = load_games_window(conn, (day - timedelta(days=days_back)).date().isoformat(),
                              (day + timedelta(days=days_fwd)).date().isoformat())
    if not games:
        logger.warning(f"NBL: no stored games near {around_date}; odds skipped")
        return None
    return Resolver(load_registry(conn), games)
