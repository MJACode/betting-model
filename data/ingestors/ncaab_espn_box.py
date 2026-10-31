"""ncaab_espn_box.py -- NCAAB team box scores and period scores from ESPN.

WHY THIS EXISTS. Every NCAAB rating model refits on ncaab_team_game_stats
(possessions, points, shooting, rebounds, turnovers per team per game). Its
only other writer is data/ingestors/ncaab_sdv_import.py, which loads whole
sportsdataverse season files, and that source has no 2026-27 file and no
in-season build. Without this module nothing fills the table this season.

THE SOURCES. ESPN's site API, free, no key:
  * summary?event=<ESPN event id> -- one game: both teams' box score and the
    period line scores. Measured 2026-10-30 on 25 games of 2025-26: HTTP 200
    every time, 1.00 s a call on average (max 1.12 s), 447-566 KB each. On
    49 team rows that also have an NCAA row, every one of points, FGA, FGM,
    3PA, 3PM, FTA, FTM, offensive and defensive rebounds and turnovers agreed
    with NCAA's number (0 differences in 490 values), and points = 2 x FGM +
    3PM + FTM held on all 50.
  * scoreboard?dates=YYYYMMDD&groups=50 -- every game of one ET date with each
    side's period line scores, overtimes included. The period backfill reads
    it: one call per date instead of one per game.

WHAT IT WRITES, one transaction per game, so a game is never half stored:
  * ncaab_team_game_stats  two rows per game, source 'espn_summary'.
      contest_id is 'espn:<ESPN event id>'. NCAA's contest ids are digits
      only (all 188,424 sportsdataverse rows, measured 2026-10-30), so the
      two sources can never share a key. team is the ESPN school name that
      games.home_team / away_team carry. Columns ESPN supplies are filled;
      rima, rimm (shots at the rim), e_poss, time_per_poss and team_ncaa_id
      are NCAA play-by-play fields with no ESPN equivalent and stay NULL.
      mins is the game's length, 40 + 5 per overtime.
  * ncaab_period_scores    one row per (game, period): period 1 and 2 are the
      halves, 3 and later the overtimes, in our stored home/away orientation
      (mapped by ESPN team id, not by ESPN's home flag). source says which
      ESPN endpoint it came from ('espn_summary' or 'espn_scoreboard').
  * ncaab_box_misses       one row per game ESPN could not answer usefully:
      attempts, the last reason, when. It stops a bad game being re-fetched
      on every pass (MAX_ATTEMPTS, COOL_MINUTES).

THE POSSESSION ESTIMATE. o_poss and d_poss are NOT NCAA's play-by-play count
(the sportsdataverse rows); ESPN's free summary has no possession number. Each
team's o_poss is the box-score estimate fga - orb + tov + 0.475 x fta, and its
d_poss is the opponent's, so one team's o_poss is the other's d_poss, as in
NCAA's rows. Against NCAA's count in 2020-21 to 2025-26 it runs 0.30 to 0.46
possessions a team-game BELOW it (mean by season); per team the mean absolute
gap is about 1.2 and the correlation about 0.967, and per game (the two teams
averaged) the correlation is 0.978 and the gap about 1.0. Fed to the frozen
rating model in place of NCAA's count it left totals MAE at 13.638 against
13.644 (2012-19). Evidence: the NCAAB research round's poss_agreement.csv
and poss_substitution.csv (2026-10-30).

TWO SOURCES, ONE GAME. If a game is ever held under both sources it has two
pairs of rows with different contest_ids and the same espn_game_id. A reader
keeps one SOURCE per game, both of its rows, preferring 'sportsdataverse_ncaa'
(NCAA's count) where it holds the game. The game is the espn_game_id where
the row has one and the contest_id where it does not: NCAA's rows carry no
espn_game_id before 2022-23 (138,338 of 188,424, read 2026-10-30), so a
reader that requires one keeps only the last four seasons. Do not key on
team_espn_id: NCAA's row for a non-Division I team has none (8,854 rows) and
this feed fills it, so the two sources' rows for that side never match by
team id; match a side across sources on the game and pts (no game ends
level), never on is_home, which the sources set differently at neutral
sites. The query
(docs/sports/ncaab.md prints the same one; a test runs that copy):
    SELECT * FROM (
      SELECT s.*, RANK() OVER (
               PARTITION BY COALESCE('espn:' || s.espn_game_id, s.contest_id)
               ORDER BY (s.source = 'sportsdataverse_ncaa') DESC) AS source_rank
        FROM ncaab_team_game_stats s) ranked
     WHERE source_rank = 1;
A reader keyed on date and team pair that drops duplicate keys would drop
such a game instead (the research prep does), so choose the source first.
team, is_home, game_date and mins follow games/ncaab_events in this feed's
rows and NCAA's own rules in NCAA's (docs/sports/ncaab.md lists the counts).
ast and blk are stored as ESPN reports them and were not checked against
NCAA beyond a 10-game sample (blocks differed on 1 of 20 team rows).

WHAT IT REFUSES, each counted, logged and recorded as a miss, never guessed:
  * a summary that is not final, names other teams than our event, or lacks
    any of FGA, FGM, 3PA, 3PM, FTA, FTM, OREB, DREB or turnovers;
  * a box whose points do not equal 2 x FGM + 3PM + FTM;
  * an ESPN final that differs from the one stored in games (the stored final
    settled the picks; CLAUDE.md section 1c);
  * period scores that do not sum to the stored final, differ in count
    between the teams, or disagree with games.went_to_ot.
  A refused game stores nothing at all, period scores included.

WHEN ESPN CHANGES THE SUMMARY FOR EVERY GAME (a renamed stat, a moved
endpoint), each game alone is only a refusal. So after every pass the step
counts the newest finals of the window that ESPN answered for and that were
refused, back to the newest one stored (refused_run). REFUSED_RUN_RED of them
in a row turns the step red ('espn-box-refused'), and it stays red, even on
passes with nothing due, until a game is stored again. It is counted from the
stored rows, so a break that arrives one game a pass is caught too, and a
refused game's retries behind a newer stored game are not. The refused games
use up their MAX_ATTEMPTS meanwhile; once the cause is fixed, the box backfill
(--box, job ncaab_box_backfill kind box) fetches them again, misses ignored.

COST. The refresh-pass step (run_recent) runs on the HOURLY passes only (7 am
to 5 pm and midnight to 5 am ET, scripts/refresh_pass.sh): an evening pass
already takes 455-526 s (median, 90th percentile, 7 days to 2026-10-30) of its
600 s tick. It reads the database first and calls ESPN only for finals of the
last RECENT_DAYS ET dates with no 'espn_summary' row, newest first, at most
MAX_GAMES_PER_PASS games and TIME_BUDGET_S seconds a pass (checked before each
call, so one call in flight can run past it), one request at a time with
REQUEST_SLEEP between them. An idle pass, and every pass out of season, makes
no ESPN call. A 403 or 429 from ESPN stops the run at once (ESPN has
IP-blocked the worker before). So does the first fetch that fails after the
helper's own retry: the next pass is the retry, and an ESPN outage costs one
fetch a pass (at most about 46 s: two 20 s timeouts and the helper's sleeps)
rather than three. The season backfills stop after STOP_AFTER_FAILURES.

Usage:
    python -m data.ingestors.ncaab_espn_box --recent [--date D] [--days 3]
    python -m data.ingestors.ncaab_espn_box --box --seasons 2027 2027
    python -m data.ingestors.ncaab_espn_box --periods --seasons 2021 2026
"""
from __future__ import annotations

import argparse
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from loguru import logger

from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current
from data.db import ConnectionLost, call_in_savepoint, get_connection

_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"
SUMMARY_URL = f"{_BASE}/summary"

BOX_SOURCE = "espn_summary"            # ncaab_team_game_stats.source
PERIODS_FROM_SUMMARY = "espn_summary"  # ncaab_period_scores.source
PERIODS_FROM_SCOREBOARD = "espn_scoreboard"
CONTEST_PREFIX = "espn:"

FTA_WEIGHT = 0.475        # the free-throw weight the research measured
RECENT_DAYS = 3           # the refresh pass looks back this many ET dates
MAX_GAMES_PER_PASS = 80
TIME_BUDGET_S = 150.0     # a pass stops fetching after this, the rest wait
REQUEST_SLEEP = 0.3       # between ESPN calls: one request in flight at a time
MAX_ATTEMPTS = 6          # a refused game is tried at most this often
COOL_MINUTES = 50         # and not again within this many minutes
STOP_AFTER_FAILURES = 3   # fetch failures in a row before a backfill stops
PASS_STOP_AFTER_FAILURES = 1  # a refresh pass stops at the first; the next pass retries
REFUSED_RUN_RED = 5       # newest answered finals refused in a row: the feed, not the games
EARLY_TIP_HOUR_ET = 6     # a tip before this hour ET is on the previous board

_ET = ZoneInfo("America/New_York")


# ── tables ───────────────────────────────────────────────────────────────────

PERIODS_TABLE = "ncaab_period_scores"
PERIODS_COLS = ("game_id", "period", "home_points", "away_points", "espn_event_id",
                "season", "game_date", "source", "loaded_at")
PERIODS_DDL = """
CREATE TABLE IF NOT EXISTS ncaab_period_scores (
    game_id        TEXT NOT NULL,
    period         INTEGER NOT NULL,
    home_points    INTEGER NOT NULL,
    away_points    INTEGER NOT NULL,
    espn_event_id  BIGINT NOT NULL,
    season         INTEGER NOT NULL,
    game_date      TEXT NOT NULL,
    source         TEXT NOT NULL,
    loaded_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (game_id, period)
)
"""
PERIODS_INDEX = ("CREATE INDEX IF NOT EXISTS idx_ncaab_period_scores_season "
                 "ON ncaab_period_scores (season)")

MISSES_TABLE = "ncaab_box_misses"
MISSES_COLS = ("espn_event_id", "game_id", "attempts", "first_at", "last_at", "reason")
MISSES_DDL = """
CREATE TABLE IF NOT EXISTS ncaab_box_misses (
    espn_event_id  BIGINT PRIMARY KEY,
    game_id        TEXT NOT NULL,
    attempts       INTEGER NOT NULL,
    first_at       TIMESTAMPTZ NOT NULL,
    last_at        TIMESTAMPTZ NOT NULL,
    reason         TEXT
)
"""


def ensure_tables(conn) -> None:
    """Create the period and miss tables once, locked down; the box table is
    ncaab_sdv_import's. A current schema costs catalog reads only, so no DDL
    (and no PostgREST schema reload) runs on a pass (data/ddl_guard.py)."""
    from data.ingestors.ncaab_sdv_import import ensure_tables as ensure_box_table

    ensure_box_table(conn)
    changed = False
    if not schema_is_current(conn, "ncaab_period_scores", columns=PERIODS_COLS,
                             indexes=("idx_ncaab_period_scores_season",),
                             rls=True, revoked_from=API_ROLES):
        conn.execute(PERIODS_DDL)
        conn.execute(PERIODS_INDEX)
        lock_down(conn, "ncaab_period_scores")
        changed = True
    if not schema_is_current(conn, "ncaab_box_misses", columns=MISSES_COLS,
                             rls=True, revoked_from=API_ROLES):
        conn.execute(MISSES_DDL)
        lock_down(conn, "ncaab_box_misses")
        changed = True
    if changed:
        conn.commit()


# ── ESPN ─────────────────────────────────────────────────────────────────────

def _default_get_json(url: str, params: dict) -> dict:
    """The schedule ingestor's GET: one retry on a timeout, a dropped
    connection or a 5xx; a 4xx raises at once."""
    from data.ingestors.ncaab_espn_ingestor import _http_get_json
    return _http_get_json(url, params)


def fetch_summary(event_id: int, get_json=None) -> dict:
    return (get_json or _default_get_json)(SUMMARY_URL, {"event": str(event_id)})


def fetch_scoreboard(day: str, get_json=None) -> dict:
    from data.ingestors.ncaab_espn_ingestor import fetch_scoreboard as _board
    return _board(day, get_json or _default_get_json)


class Refused(ValueError):
    """ESPN answered, but not with something this module will store."""


def _status_code(exc: Exception) -> int | None:
    resp = getattr(exc, "response", None)
    return getattr(resp, "status_code", None)


# ── parsing ──────────────────────────────────────────────────────────────────

# ESPN statistic name -> our columns. A "made-attempted" pair fills two.
_STATS = {
    "fieldGoalsMade-fieldGoalsAttempted": ("fgm", "fga"),
    "threePointFieldGoalsMade-threePointFieldGoalsAttempted": ("tpm", "tpa"),
    "freeThrowsMade-freeThrowsAttempted": ("ftm", "fta"),
    "offensiveRebounds": "orb",
    "defensiveRebounds": "drb",
    # `turnovers` is the field that matched NCAA's tov on 49 of 49 rows;
    # totalTurnovers equalled it on all 50 and is the fallback.
    "turnovers": "tov",
    "totalTurnovers": "_tov_total",
    "assists": "ast",
    "blocks": "blk",
}
REQUIRED = ("fga", "fgm", "tpa", "tpm", "fta", "ftm", "orb", "drb", "tov")


def _int(v) -> int | None:
    try:
        f = float(str(v).strip())
    except (TypeError, ValueError):
        return None
    return int(f) if f == int(f) else None


def team_box(statistics: list) -> dict:
    """One team's statistics list -> {fga: 66, fgm: 22, ...}. Refused when a
    required number is missing or not a whole number."""
    out: dict = {}
    for s in statistics or []:
        key = _STATS.get((s or {}).get("name"))
        if key is None:
            continue
        raw = str(s.get("displayValue") or "").strip()
        if isinstance(key, tuple):
            made, _, att = raw.partition("-")
            out[key[0]], out[key[1]] = _int(made), _int(att)
        else:
            out[key] = _int(raw)
    if out.get("tov") is None:
        out["tov"] = out.get("_tov_total")
    out.pop("_tov_total", None)
    missing = [k for k in REQUIRED if out.get(k) is None]
    if missing:
        raise Refused(f"box score lacks {', '.join(missing)}")
    if not (out["fgm"] <= out["fga"] and out["tpm"] <= out["tpa"]
            and out["tpa"] <= out["fga"] and out["ftm"] <= out["fta"]):
        raise Refused("box score makes exceed attempts")
    return out


def possessions(box: dict) -> float:
    """The box-score possession ESTIMATE, fga - orb + tov + 0.475 x fta. Not
    NCAA's play-by-play count: it runs 0.30-0.46 below it (module docstring)."""
    return round(box["fga"] - box["orb"] + box["tov"] + FTA_WEIGHT * box["fta"], 3)


def _periods(linescores) -> list[int]:
    """Line scores in period order. The scoreboard sends `value` and `period`,
    the summary only `displayValue`."""
    out = []
    for i, ls in enumerate(linescores or [], start=1):
        ls = ls or {}
        if ls.get("period") is not None and _int(ls.get("period")) != i:
            raise Refused(f"line scores out of order at period {i}")
        v = _int(ls.get("value")) if ls.get("value") is not None else _int(ls.get("displayValue"))
        if v is None or v < 0:
            raise Refused(f"period {i} score is not a count")
        out.append(v)
    return out


def _sides(competitors) -> dict[int, dict]:
    """ESPN team id -> {score, periods} for a summary header or a scoreboard event."""
    out = {}
    for c in competitors or []:
        tid = _int((c or {}).get("id") or ((c or {}).get("team") or {}).get("id"))
        if tid is None:
            continue
        out[tid] = {"score": _int(c.get("score")), "periods": _periods(c.get("linescores"))}
    return out


def parse_summary(js: dict, event_id: int) -> dict:
    """A summary payload -> {team id: {score, periods, box}}. Refused (a
    ValueError) for anything that is not a complete final of `event_id`."""
    header = (js or {}).get("header") or {}
    if _int(header.get("id")) != int(event_id):
        raise Refused(f"summary is for event {header.get('id')}, not {event_id}")
    comp = (header.get("competitions") or [{}])[0] or {}
    st = ((comp.get("status") or {}).get("type")) or {}
    if not (st.get("completed") and st.get("state") == "post"):
        raise Refused(f"not final on ESPN ({st.get('name')})")
    sides = _sides(comp.get("competitors"))
    teams = ((js.get("boxscore") or {}).get("teams")) or []
    for t in teams:
        tid = _int(((t or {}).get("team") or {}).get("id"))
        if tid in sides:
            sides[tid]["box"] = team_box(t.get("statistics"))
    if len(sides) != 2 or any("box" not in s for s in sides.values()):
        raise Refused("summary does not carry two teams' box scores")
    return sides


def parse_scoreboard(board: dict) -> dict[int, dict]:
    """A scoreboard -> {event id: {team id: {score, periods}}} for its
    completed events. An event whose line scores cannot be read is left out
    (and stays due), not guessed."""
    out = {}
    for ev in (board or {}).get("events") or []:
        eid = _int((ev or {}).get("id"))
        comp = ((ev or {}).get("competitions") or [{}])[0] or {}
        st = ((comp.get("status") or {}).get("type")) or {}
        if eid is None or not (st.get("completed") and st.get("state") == "post"):
            continue
        try:
            out[eid] = _sides(comp.get("competitors"))
        except Refused as exc:
            logger.info(f"NCAAB periods: event {eid} skipped ({exc})")
    return out


# ── rows ─────────────────────────────────────────────────────────────────────

def _final(game: dict) -> tuple[int, int]:
    return int(float(game["home_score"])), int(float(game["away_score"]))


def period_rows(game: dict, sides: dict, source: str) -> list[tuple]:
    """Validated period rows for one stored game, home/away by ESPN team id."""
    home, away = game["home_espn_id"], game["away_espn_id"]
    if set(sides) != {home, away}:
        raise Refused(f"ESPN teams {sorted(sides)} are not the stored pair {sorted((home, away))}")
    hp, ap = sides[home]["periods"], sides[away]["periods"]
    if len(hp) < 2 or len(hp) != len(ap):
        raise Refused(f"period counts {len(hp)} and {len(ap)}")
    hs, as_ = _final(game)
    if (sum(hp), sum(ap)) != (hs, as_):
        raise Refused(f"periods sum to {sum(hp)}-{sum(ap)}, stored final {hs}-{as_}")
    ot = game.get("went_to_ot")
    if ot is not None and str(ot) != "" and bool(int(float(ot))) != (len(hp) > 2):
        raise Refused(f"{len(hp)} periods but went_to_ot={ot}")
    return [(game["game_id"], i, h, a, game["espn_event_id"], game["season"],
             game["game_date"], source) for i, (h, a) in enumerate(zip(hp, ap), start=1)]


BOX_COLS = ("contest_id", "team", "game_date", "espn_game_id", "team_espn_id", "opp_espn_id",
            "team_ncaa_id", "is_home", "season", "home_espn_id", "away_espn_id", "mins",
            "o_poss", "d_poss", "pts", "d_pts", "fga", "fgm", "tpa", "tpm", "fta", "ftm",
            "rima", "rimm", "orb", "drb", "tov", "ast", "blk", "e_poss", "time_per_poss",
            "source")


def contest_id(event_id: int) -> str:
    return f"{CONTEST_PREFIX}{int(event_id)}"


def box_rows(game: dict, sides: dict) -> list[tuple]:
    """The two ncaab_team_game_stats rows for one stored game (BOX_COLS order)."""
    home, away = game["home_espn_id"], game["away_espn_id"]
    if set(sides) != {home, away}:
        raise Refused(f"ESPN teams {sorted(sides)} are not the stored pair {sorted((home, away))}")
    hs, as_ = _final(game)
    for tid, stored in ((home, hs), (away, as_)):
        s = sides[tid]
        if s["score"] != stored:
            raise Refused(f"ESPN final {s['score']} for team {tid}, stored {stored}")
        b = s["box"]
        if 2 * b["fgm"] + b["tpm"] + b["ftm"] != stored:
            raise Refused(f"team {tid} box makes {2 * b['fgm'] + b['tpm'] + b['ftm']} "
                          f"points, final {stored}")
    n_periods = len(sides[home]["periods"])
    mins = 40.0 + 5.0 * max(n_periods - 2, 0)
    est = {tid: possessions(sides[tid]["box"]) for tid in (home, away)}
    rows = []
    for tid, opp, name, is_home in ((home, away, game["home_team"], True),
                                    (away, home, game["away_team"], False)):
        b = sides[tid]["box"]
        row = {"contest_id": contest_id(game["espn_event_id"]), "team": name,
               "game_date": game["game_date"], "espn_game_id": int(game["espn_event_id"]),
               "team_espn_id": tid, "opp_espn_id": opp, "team_ncaa_id": None,
               "is_home": is_home, "season": int(game["season"]),
               "home_espn_id": home, "away_espn_id": away, "mins": mins,
               "o_poss": est[tid], "d_poss": est[opp],
               "pts": float(sides[tid]["score"]), "d_pts": float(sides[opp]["score"]),
               "rima": None, "rimm": None, "e_poss": None, "time_per_poss": None,
               "source": BOX_SOURCE}
        for k in ("fga", "fgm", "tpa", "tpm", "fta", "ftm", "orb", "drb", "tov", "ast", "blk"):
            row[k] = None if b.get(k) is None else float(b[k])
        rows.append(tuple(row[c] for c in BOX_COLS))
    return rows


# ── the database ─────────────────────────────────────────────────────────────

_BOX_INSERT = (
    "INSERT INTO ncaab_team_game_stats (" + ", ".join(BOX_COLS) + ") VALUES ("
    + ", ".join(["%s"] * len(BOX_COLS)) + ") ON CONFLICT (contest_id, team) DO NOTHING")
_PERIOD_INSERT = (
    "INSERT INTO ncaab_period_scores (game_id, period, home_points, away_points, "
    "espn_event_id, season, game_date, source) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
    "ON CONFLICT (game_id, period) DO NOTHING")
_MISS_UPSERT = """
INSERT INTO ncaab_box_misses (espn_event_id, game_id, attempts, first_at, last_at, reason)
VALUES (%s, %s, 1, %s, %s, %s)
ON CONFLICT (espn_event_id) DO UPDATE SET
    attempts = ncaab_box_misses.attempts + 1,
    last_at  = EXCLUDED.last_at,
    reason   = EXCLUDED.reason
"""

_GAME_COLS = ("espn_event_id", "game_id", "season", "game_date", "commence_time",
              "home_espn_id", "away_espn_id", "home_team", "away_team", "home_score",
              "away_score", "went_to_ot")
_GAMES_SQL = """
SELECT e.espn_event_id, e.game_id, e.season, g.game_date, g.commence_time,
       e.home_espn_id, e.away_espn_id, g.home_team, g.away_team, g.home_score,
       g.away_score, g.went_to_ot
  FROM games g
  JOIN ncaab_events e ON e.game_id = g.game_id
 WHERE g.sport = 'NCAAB'
   AND g.home_score IS NOT NULL AND g.away_score IS NOT NULL
"""
# A game is done for the box when its 'espn_summary' rows exist. The key is
# built the way box_rows builds it, so the primary-key index answers.
_NO_BOX = (" AND NOT EXISTS (SELECT 1 FROM ncaab_team_game_stats s "
           "WHERE s.contest_id = 'espn:' || e.espn_event_id)")
_NOT_COOLING = (" AND NOT EXISTS (SELECT 1 FROM ncaab_box_misses m "
                "WHERE m.espn_event_id = e.espn_event_id "
                "AND (m.attempts >= %s OR m.last_at > %s))")
_NO_PERIODS = (" AND NOT EXISTS (SELECT 1 FROM ncaab_period_scores p "
               "WHERE p.game_id = g.game_id)")
_NEWEST_FIRST = " ORDER BY g.game_date DESC, g.commence_time DESC, e.espn_event_id"


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _rows_to_games(rows) -> list[dict]:
    out = []
    for r in rows:
        g = dict(zip(_GAME_COLS, r))
        g["espn_event_id"] = int(g["espn_event_id"])
        g["home_espn_id"], g["away_espn_id"] = int(g["home_espn_id"]), int(g["away_espn_id"])
        g["season"] = int(g["season"])
        g["game_date"] = str(g["game_date"])[:10]
        out.append(g)
    return out


def due_box_games(conn, *, first: str | None = None, last: str | None = None,
                  seasons: tuple[int, int] | None = None, now: datetime,
                  respect_misses: bool = True, limit: int | None = None) -> list[dict]:
    """Final games with an ESPN event and no 'espn_summary' box rows, newest
    first. A game refused MAX_ATTEMPTS times, or within COOL_MINUTES of its
    last refusal, is left out unless respect_misses is False."""
    sql, params = _GAMES_SQL, []
    if first is not None:
        sql += " AND g.game_date >= %s AND g.game_date <= %s"
        params += [first, last]
    if seasons is not None:
        sql += " AND e.season >= %s AND e.season <= %s"
        params += list(seasons)
    sql += _NO_BOX
    if respect_misses:
        sql += _NOT_COOLING
        params += [MAX_ATTEMPTS, _iso(now - timedelta(minutes=COOL_MINUTES))]
    sql += _NEWEST_FIRST
    if limit is not None:
        sql += " LIMIT %s"
        params.append(int(limit))
    return _rows_to_games(conn.execute(sql, tuple(params)).fetchall())


def due_period_games(conn, seasons: tuple[int, int]) -> list[dict]:
    """Final games in `seasons` with an ESPN event and no period rows."""
    sql = (_GAMES_SQL + " AND e.season >= %s AND e.season <= %s" + _NO_PERIODS
           + _NEWEST_FIRST)
    return _rows_to_games(conn.execute(sql, tuple(seasons)).fetchall())


# The window's finals, newest first: stored or not, and the miss on record.
# Both lookups are by primary key, as in the due query.
_ANSWERED_SQL = (
    "SELECT e.espn_event_id, "
    "EXISTS (SELECT 1 FROM ncaab_team_game_stats s "
    "WHERE s.contest_id = 'espn:' || e.espn_event_id) AS stored, m.reason "
    "FROM games g JOIN ncaab_events e ON e.game_id = g.game_id "
    "LEFT JOIN ncaab_box_misses m ON m.espn_event_id = e.espn_event_id "
    "WHERE g.sport = 'NCAAB' AND g.home_score IS NOT NULL AND g.away_score IS NOT NULL "
    "AND g.game_date >= %s AND g.game_date <= %s" + _NEWEST_FIRST)


def refused_run(conn, first: str, last: str) -> tuple[int, str | None]:
    """How many of the newest finals of the window ESPN answered for were
    refused, counted back to the newest one stored, and the newest refusal's
    reason. A final not tried yet (left for a later pass) is skipped. A game
    ESPN cannot answer for now and then sits among stored ones and counts 0
    or 1; a summary changed for every game counts every final since."""
    n, reason = 0, None
    for _eid, stored, miss in conn.execute(_ANSWERED_SQL, (first, last)).fetchall():
        if stored:
            break
        if miss is None:
            continue
        n += 1
        reason = reason or miss
    return n, reason


def write_game(conn, box: list[tuple], periods: list[tuple]) -> tuple[int, int]:
    """Box rows and period rows in one savepoint; ON CONFLICT DO NOTHING, so a
    row already stored is never rewritten. Returns the row counts sent."""
    def _write():
        if box:
            conn.executemany(_BOX_INSERT, box)
        if periods:
            conn.executemany(_PERIOD_INSERT, periods)
        return len(box), len(periods)
    return call_in_savepoint(conn, "ncaab_espn_box", _write)


def record_miss(conn, game: dict, reason: str, now: datetime) -> None:
    stamp = _iso(now)
    call_in_savepoint(conn, "ncaab_box_miss", lambda: conn.execute(
        _MISS_UPSERT, (game["espn_event_id"], game["game_id"], stamp, stamp, reason[:300])))


# ── the runners ──────────────────────────────────────────────────────────────

def new_totals() -> dict:
    return {"due": 0, "fetched": 0, "games_stored": 0, "box_rows": 0, "period_rows": 0,
            "refused": 0, "left": 0, "fetch_errors": 0, "stopped": None,
            "refused_run": 0, "reasons": {}, "failed": []}


def _open(connect):
    return (connect or get_connection)(), connect is None


def _today_et(now: datetime) -> str:
    return now.astimezone(_ET).strftime("%Y-%m-%d")


def _one_game(conn, game: dict, js: dict, totals: dict, now: datetime) -> None:
    """Parse, validate and store one game's summary, or record why not."""
    try:
        sides = parse_summary(js, game["espn_event_id"])
        periods = period_rows(game, sides, PERIODS_FROM_SUMMARY)
        box = box_rows(game, sides)
    except (Refused, KeyError, TypeError, AttributeError, ValueError) as exc:
        reason = str(exc) if isinstance(exc, Refused) else f"malformed summary: {exc!r}"
        _refuse(conn, game, reason, totals, now)
        return
    nb, np_ = write_game(conn, box, periods)
    conn.commit()
    totals["games_stored"] += 1
    totals["box_rows"] += nb
    totals["period_rows"] += np_


def _refuse(conn, game: dict, reason: str, totals: dict, now: datetime) -> None:
    logger.warning(f"NCAAB box: {game['game_id']} (event {game['espn_event_id']}) "
                   f"not stored: {reason}")
    totals["refused"] += 1
    key = reason.split(":")[0][:60]
    totals["reasons"][key] = totals["reasons"].get(key, 0) + 1
    record_miss(conn, game, reason, now)
    conn.commit()


def _run_games(conn, games: list[dict], totals: dict, *, get_json, sleep: float,
               budget_s: float | None, now: datetime, clock=time.monotonic,
               stop_after: int = STOP_AFTER_FAILURES) -> None:
    """Fetch and store each game in turn, one request at a time.

    What makes the run red (totals["failed"]): ESPN refusing the worker (403
    or 429), `stop_after` fetch failures in a row, or a database write that
    failed. A game ESPN answered for but that is refused on its content is
    logged, counted and recorded as a miss, and does not make it red by
    itself (run_recent's refused_run check is what catches every game being
    refused).
    """
    start = clock()
    in_a_row = 0
    for i, game in enumerate(games):
        if budget_s is not None and clock() - start > budget_s:
            totals["left"] += len(games) - i
            logger.info(f"NCAAB box: time budget spent, {len(games) - i} game(s) left "
                        f"for the next pass")
            return
        if i and sleep:
            time.sleep(sleep)
        js, refusal = None, None
        try:
            js = fetch_summary(game["espn_event_id"], get_json)
        except Exception as exc:                          # noqa: BLE001
            code = _status_code(exc)
            if code in (403, 429):
                totals["stopped"] = f"ESPN answered {code}"
                totals["failed"].append(f"espn-{code}")
                totals["left"] += len(games) - i
                logger.error(f"NCAAB box: ESPN answered {code}; stopping the run")
                return
            if code is not None and 400 <= code < 500:
                # This game's summary does not exist (404) or is refused:
                # a fact about the game, not about ESPN.
                refusal = f"ESPN answered {code}"
            else:
                totals["fetch_errors"] += 1
                in_a_row += 1
                logger.warning(f"NCAAB box: event {game['espn_event_id']} fetch failed: {exc}")
                if in_a_row >= stop_after:
                    totals["stopped"] = f"{in_a_row} fetch failures in a row"
                    totals["failed"].append("espn-unreachable")
                    totals["left"] += len(games) - i - 1
                    logger.error(f"NCAAB box: {in_a_row} fetch failures in a row; stopping")
                    return
                continue
        in_a_row = 0
        try:
            if refusal is not None:
                _refuse(conn, game, refusal, totals, now)
            else:
                totals["fetched"] += 1
                _one_game(conn, game, js, totals, now)
        except ConnectionLost:
            raise
        except Exception as exc:                          # noqa: BLE001
            # A write failure: logged, the transaction restored, the step red.
            logger.warning(f"NCAAB box: {game['game_id']} write failed: {exc}")
            try:
                conn.rollback()
            except Exception:                             # noqa: BLE001
                pass
            totals["failed"].append(game["game_id"])


def run_recent(run_date: str | None = None, days: int = RECENT_DAYS, *, now: datetime | None = None,
               get_json=None, connect=None, sleep: float = REQUEST_SLEEP,
               max_games: int = MAX_GAMES_PER_PASS, budget_s: float | None = TIME_BUDGET_S,
               clock=time.monotonic) -> dict:
    """The refresh-pass step: box and period scores for the finals of the last
    `days` ET dates that have none yet. No ESPN call when nothing is due.
    Red, besides _run_games' reasons, while the newest REFUSED_RUN_RED finals
    ESPN answered for were all refused (refused_run)."""
    now = now or datetime.now(timezone.utc)
    today = run_date or _today_et(now)
    first = (date.fromisoformat(today) - timedelta(days=days)).isoformat()
    conn, own = _open(connect)
    totals = new_totals()
    try:
        ensure_tables(conn)
        games = due_box_games(conn, first=first, last=today, now=now, limit=max_games + 1)
        conn.rollback()                  # no read snapshot held while ESPN answers
        if len(games) > max_games:
            totals["left"] += 1          # at least one more waits for the next pass
            games = games[:max_games]
        totals["due"] = len(games)
        if games:
            _run_games(conn, games, totals, get_json=get_json, sleep=sleep,
                       budget_s=budget_s, now=now, clock=clock,
                       stop_after=PASS_STOP_AFTER_FAILURES)
        else:
            logger.info("NCAAB box: nothing due (no ESPN call)")
        run, reason = refused_run(conn, first, today)
        conn.rollback()
        totals["refused_run"] = run
        if run >= REFUSED_RUN_RED:
            totals["failed"].append("espn-box-refused")
            logger.error(
                f"NCAAB box: the newest {run} finals ESPN answered for were all refused "
                f"and none stored since (newest reason: {reason}). ESPN's game summary "
                f"has likely changed for every game. Once fixed, the box backfill "
                f"(job ncaab_box_backfill, kind box) fetches the refused games again.")
    finally:
        if own:
            conn.close()
    if games:
        logger.info(f"NCAAB box (ESPN): {_summary(totals)}")
    return totals


def run_box_backfill(first_season: int, last_season: int, *, now: datetime | None = None,
                     get_json=None, connect=None, sleep: float = REQUEST_SLEEP,
                     echo: bool = False) -> dict:
    """Every final of the seasons with no 'espn_summary' box yet, one summary
    call each. A game refused before is tried once more (respect_misses off),
    and refused again it is recorded again. Re-running stores nothing twice."""
    now = now or datetime.now(timezone.utc)
    conn, own = _open(connect)
    totals = new_totals()
    try:
        ensure_tables(conn)
        games = due_box_games(conn, seasons=(first_season, last_season), now=now,
                              respect_misses=False)
        conn.rollback()
        totals["due"] = len(games)
        if echo:
            print(f"box backfill {first_season}-{last_season}: {len(games)} game(s) due")
        _run_games(conn, games, totals, get_json=get_json, sleep=sleep, budget_s=None, now=now)
    finally:
        if own:
            conn.close()
    logger.info(f"NCAAB box backfill {first_season}-{last_season}: {_summary(totals)}")
    return totals


def _board_dates(games: list[dict]) -> list[str]:
    """The scoreboard dates that hold these games: each game's ET date, plus
    the previous date for a tip before EARLY_TIP_HOUR_ET (ESPN files those on
    the previous board; data/ingestors/ncaab_espn_ingestor.py)."""
    dates = set()
    for g in games:
        dates.add(g["game_date"])
        raw = str(g.get("commence_time") or "")
        try:
            tip = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if tip.tzinfo is None:
            tip = tip.replace(tzinfo=timezone.utc)
        et = tip.astimezone(_ET)
        if et.hour < EARLY_TIP_HOUR_ET:
            dates.add((et.date() - timedelta(days=1)).isoformat())
    return sorted(dates)


def run_period_backfill(first_season: int, last_season: int, *, get_json=None, connect=None,
                        sleep: float = REQUEST_SLEEP, echo: bool = False) -> dict:
    """Period scores for every final of the seasons that has none, from ESPN's
    scoreboard: one call per date, every game on it. A game is stored when its
    event is on any board read in this run, and refused (counted, not
    recorded) when its line scores do not match the stored final."""
    conn, own = _open(connect)
    totals = {**new_totals(), "dates": 0, "dates_failed": 0, "not_on_board": 0}
    try:
        ensure_tables(conn)
        games = due_period_games(conn, (first_season, last_season))
        conn.rollback()
        totals["due"] = len(games)
        pending = {g["espn_event_id"]: g for g in games}
        dates = _board_dates(games)
        if echo:
            print(f"period backfill {first_season}-{last_season}: {len(games)} game(s) "
                  f"due on {len(dates)} date(s)")
        seen: dict[int, dict] = {}
        in_a_row = 0
        for i, day in enumerate(dates):
            if i and sleep:
                time.sleep(sleep)
            try:
                board = fetch_scoreboard(day, get_json)
            except Exception as exc:                      # noqa: BLE001
                code = _status_code(exc)
                totals["dates_failed"] += 1
                in_a_row += 1
                logger.warning(f"NCAAB periods: {day} fetch failed: {exc}")
                if code in (403, 429) or in_a_row >= STOP_AFTER_FAILURES:
                    totals["stopped"] = (f"ESPN answered {code}" if code in (403, 429)
                                         else f"{in_a_row} fetch failures in a row")
                    totals["failed"].append(totals["stopped"])
                    break
                continue
            in_a_row = 0
            totals["dates"] += 1
            seen.update(parse_scoreboard(board))
            ready = [g for eid, g in pending.items() if eid in seen]
            stored = 0
            for g in ready:
                del pending[g["espn_event_id"]]
                try:
                    rows = period_rows(g, seen[g["espn_event_id"]], PERIODS_FROM_SCOREBOARD)
                except Refused as exc:
                    totals["refused"] += 1
                    logger.warning(f"NCAAB periods: {g['game_id']} not stored: {exc}")
                    continue
                try:
                    _, n = write_game(conn, [], rows)
                except ConnectionLost:
                    raise
                except Exception as exc:                  # noqa: BLE001
                    logger.warning(f"NCAAB periods: {g['game_id']} write failed: {exc}")
                    totals["failed"].append(g["game_id"])
                    continue
                totals["games_stored"] += 1
                totals["period_rows"] += n
                stored += 1
            conn.commit()
            if echo:
                print(f"{day}: {len(board.get('events') or [])} event(s), "
                      f"{stored} game(s) stored")
        totals["not_on_board"] = len(pending)
        if pending and echo:
            sample = sorted(g["game_id"] for g in pending.values())[:10]
            print(f"not on any board read: {len(pending)} (first: {sample})")
    finally:
        if own:
            conn.close()
    logger.info(f"NCAAB period backfill {first_season}-{last_season}: {_summary(totals)}")
    return totals


def _summary(totals: dict) -> dict:
    return {k: (len(v) if isinstance(v, list) else v) for k, v in totals.items()}


# ── CLI ──────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="NCAAB box and period scores from ESPN")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--recent", action="store_true",
                      help="the refresh-pass step: finals of the last --days ET dates")
    mode.add_argument("--box", action="store_true",
                      help="box and period scores for every final of --seasons (summary per game)")
    mode.add_argument("--periods", action="store_true",
                      help="period scores for every final of --seasons (scoreboard per date)")
    ap.add_argument("--seasons", nargs=2, type=int, metavar=("FIRST", "LAST"),
                    help="ending-year seasons (2027 = 2026-27)")
    ap.add_argument("--date", help="ET anchor date for --recent (default: today ET)")
    ap.add_argument("--days", type=int, default=RECENT_DAYS)
    a = ap.parse_args(argv)
    if (a.box or a.periods) and not a.seasons:
        ap.error("--box and --periods need --seasons FIRST LAST")
    if a.recent:
        t = run_recent(a.date, days=a.days)
    elif a.box:
        t = run_box_backfill(*a.seasons, echo=True)
    else:
        t = run_period_backfill(*a.seasons, echo=True)
    print(_summary(t))
    return 1 if t.get("failed") else 0


if __name__ == "__main__":
    # API telemetry for the live monitor (monitoring/). Best-effort and silent.
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("ncaab-espn")
    except Exception:  # noqa: BLE001
        pass

    raise SystemExit(main())
