"""
Women's college basketball history: per-game team box scores and season player
minutes, imported from sportsdataverse's public release files into Supabase.

A fork of the men's data/ingestors/ncaab_sdv_import.py (2026-11-09) on the
women's files (ncaa_wbb_*) and tables. What is quoted below was measured on
the men's files unless it says otherwise. The women's files have the same
shape (2026-11-09): the 2025-26 team box holds 12,038 rows on 6,019 contests;
ESPN's game id is on every 2025-26 row and on none of 2015-16's; and a 2026-27
file exists and held 479 contests through 2026-11-08, so the women's files are
being built in season (the men's had no 2026-27 file when theirs was written).
Imported 2026-11-09: 188,710 team rows, 2009-10 to 2026-27.

WHY THESE FILES
---------------
They are NCAA's official play-by-play (stats.ncaa.org), already turned into
possessions by sportsdataverse and keyed on ESPN's game and team ids, so they
join straight onto ncaabw_events. One parquet per season, about 1.4 MB for the
team box and 11 MB for the player box. stats.ncaa.org itself refuses requests
from this machine (HTTP 403, 2026-10-26), so these files are the route to the
official numbers.

WHAT LANDS WHERE (both worker-only, created on first write)
-----------------------------------------------------------
ncaabw_team_game_stats  one row per (NCAA contest, team): possessions, points,
                       shot mix (rim / three / free throws), rebounds,
                       turnovers. The rating model's input.
ncaabw_player_season    one row per (season, team, player name): games,
                       minutes, possessions, scoring. Returning-minutes and
                       transfer inputs for the preseason rating. NCAA's player
                       ids change every season (measured: 0 of 1,573 returning
                       players kept their id from 2024-25 to 2025-26), so the
                       key is the normalised name within a team.
ncaabw_player_game_log one row per player per game for the Stats tab. The
                       table is created by
                       add_ncaabw_player_game_log_2026_11_12.sql, which is not
                       on the worker's migration list. This module writes it
                       only when that table already exists, and never creates
                       it. ESPN's women's player box is not a source.

Everything in Supabase first (CLAUDE.md §1b): the parquet is read into memory
and written to the database; nothing is kept on disk. A re-run skips seasons
already stored under SOURCE unless --force.

    python -m data.ingestors.ncaabw_sdv_import --seasons 2011 2026
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import unicodedata

import pandas as pd
import requests
from loguru import logger

from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current

SOURCE = "sportsdataverse_ncaa"
RELEASE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download"
TEAM_BOX_URL = RELEASE + "/ncaa_wbb_team_box/ncaa_wbb_team_box_{season}.parquet"
SCHEDULE_URL = RELEASE + "/ncaa_wbb_schedule/ncaa_wbb_schedule_{season}.parquet"
PLAYER_BOX_URL = RELEASE + "/ncaa_wbb_player_box/ncaa_wbb_player_box_{season}.parquet"

TEAM_TABLE = "ncaabw_team_game_stats"
TEAM_COLS = ("contest_id", "team", "game_date", "espn_game_id", "team_espn_id",
             "opp_espn_id", "team_ncaa_id", "is_home", "season", "home_espn_id",
             "away_espn_id", "mins", "o_poss", "d_poss", "pts", "d_pts", "fga", "fgm",
             "tpa", "tpm", "fta", "ftm", "rima", "rimm", "orb", "drb", "tov", "ast",
             "blk", "e_poss", "time_per_poss", "source", "loaded_at")
TEAM_DDL = """
CREATE TABLE IF NOT EXISTS ncaabw_team_game_stats (
    contest_id     TEXT NOT NULL,
    team           TEXT NOT NULL,
    game_date      TEXT,
    espn_game_id   BIGINT,
    team_espn_id   INTEGER,
    opp_espn_id    INTEGER,
    team_ncaa_id   TEXT,
    is_home        BOOLEAN,
    season         INTEGER NOT NULL,
    home_espn_id   INTEGER,
    away_espn_id   INTEGER,
    mins           REAL,
    o_poss         REAL,
    d_poss         REAL,
    pts            REAL,
    d_pts          REAL,
    fga            REAL,
    fgm            REAL,
    tpa            REAL,
    tpm            REAL,
    fta            REAL,
    ftm            REAL,
    rima           REAL,
    rimm           REAL,
    orb            REAL,
    drb            REAL,
    tov            REAL,
    ast            REAL,
    blk            REAL,
    e_poss         REAL,
    time_per_poss  REAL,
    source         TEXT NOT NULL,
    loaded_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (contest_id, team)
)
"""
TEAM_INDEX = ("CREATE INDEX IF NOT EXISTS idx_ncaabw_tgs_season "
              "ON ncaabw_team_game_stats (season)")

PLAYER_TABLE = "ncaabw_player_season"
PLAYER_COLS = ("season", "team_espn_id", "player_key", "clean_name", "games", "mins",
               "o_poss", "pts", "fga", "fgm", "tpa", "tpm", "fta", "ftm", "orb", "drb",
               "ast", "stl", "blk", "tov", "pf", "source", "loaded_at")
PLAYER_DDL = """
CREATE TABLE IF NOT EXISTS ncaabw_player_season (
    season        INTEGER NOT NULL,
    team_espn_id  INTEGER NOT NULL,
    player_key    TEXT NOT NULL,
    clean_name    TEXT,
    games         INTEGER,
    mins          REAL,
    o_poss        REAL,
    pts           REAL,
    fga           REAL,
    fgm           REAL,
    tpa           REAL,
    tpm           REAL,
    fta           REAL,
    ftm           REAL,
    orb           REAL,
    drb           REAL,
    ast           REAL,
    stl           REAL,
    blk           REAL,
    tov           REAL,
    pf            REAL,
    source        TEXT NOT NULL,
    loaded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (season, team_espn_id, player_key)
)
"""

# team box column -> our column. "to" is a Python keyword in spirit and a SQL
# word in practice, so it lands as tov.
_TEAM_MAP = {"mins": "mins", "o_poss": "o_poss", "d_poss": "d_poss", "pts": "pts",
             "d_pts": "d_pts", "fga": "fga", "fgm": "fgm", "tpa": "tpa", "tpm": "tpm",
             "fta": "fta", "ftm": "ftm", "rima": "rima", "rimm": "rimm", "orb": "orb",
             "drb": "drb", "to": "tov", "ast": "ast", "blk": "blk", "e_poss": "e_poss",
             "time_per_poss": "time_per_poss"}
_PLAYER_SUMS = ("mins", "o_poss", "pts", "fga", "fgm", "tpa", "tpm", "fta", "ftm",
                "orb", "drb", "ast", "stl", "blk", "tov", "pf")


def ensure_tables(conn) -> None:
    """Create both tables once, locked down; a current schema costs one read."""
    changed = False
    if not schema_is_current(conn, TEAM_TABLE, columns=TEAM_COLS,
                             indexes=("idx_ncaabw_tgs_season",),
                             rls=True, revoked_from=API_ROLES):
        conn.execute(TEAM_DDL)
        conn.execute(TEAM_INDEX)
        lock_down(conn, TEAM_TABLE)
        changed = True
    if not schema_is_current(conn, PLAYER_TABLE, columns=PLAYER_COLS,
                             rls=True, revoked_from=API_ROLES):
        conn.execute(PLAYER_DDL)
        lock_down(conn, PLAYER_TABLE)
        changed = True
    if changed:
        conn.commit()


def player_key(name: str) -> str:
    """A player's name as a stable within-team key: accents, case and
    punctuation folded, suffixes kept ("C.J. Walker" -> "cj walker")."""
    v = unicodedata.normalize("NFKD", str(name or "").lower())
    v = "".join(c for c in v if not unicodedata.combining(c))
    v = re.sub(r"[.'’`]", "", v)
    v = re.sub(r"[^a-z0-9]+", " ", v)
    return " ".join(v.split())


def _int_or_none(v):
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == "":
            return None
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _s(v) -> str | None:
    """A text cell, or None for empty / NaN (pandas fills missing ids with NaN,
    and str(NaN) is "nan", which would match another missing id)."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    t = str(v).strip()
    return t if t and t.lower() != "nan" else None


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else f


def _fetch_parquet(url: str) -> pd.DataFrame | None:
    r = requests.get(url, timeout=120)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return pd.read_parquet(io.BytesIO(r.content))


def team_rows(df: pd.DataFrame, season: int, dates: dict | None = None) -> list[dict]:
    """One dict per (NCAA contest, team).

    Keyed on NCAA's contest id and the team name, because ESPN's game id is
    filled in only from 2022-23 on (measured: NULL on every 2011-12, 2017-18
    and 2021-22 row) and about 5% of rows (non-D-I opponents) carry no team
    ids at all. The ESPN ids ride along where present; the rating model reads
    rows with both teams' ESPN ids. `dates` maps contest id -> ISO date (from
    the season's schedule file).
    """
    dates = dates or {}
    out, seen = [], set()
    for rec in df.to_dict("records"):
        contest = _s(rec.get("contest_id"))
        team_name = _s(rec.get("team"))
        if not contest or not team_name or (contest, team_name) in seen:
            continue
        seen.add((contest, team_name))
        team = _int_or_none(rec.get("team_espn_team_id"))
        home = _int_or_none(rec.get("home_espn_team_id"))
        away = _int_or_none(rec.get("away_espn_team_id"))
        ncaa = _s(rec.get("team_ncaa_team_id"))
        is_home = None
        if ncaa and _s(rec.get("home_ncaa_team_id")) == ncaa:
            is_home = True
        elif ncaa and _s(rec.get("away_ncaa_team_id")) == ncaa:
            is_home = False
        elif _s(rec.get("home")) == team_name:
            is_home = True
        elif _s(rec.get("away")) == team_name:
            is_home = False
        opp = None
        if team is not None and is_home is not None:
            opp = away if is_home else home
        row = {"contest_id": contest, "team": team_name, "game_date": dates.get(contest),
               "espn_game_id": _int_or_none(rec.get("espn_game_id")), "team_espn_id": team,
               "opp_espn_id": opp, "team_ncaa_id": ncaa, "is_home": is_home,
               "season": season, "home_espn_id": home, "away_espn_id": away,
               "source": SOURCE}
        for src, dst in _TEAM_MAP.items():
            row[dst] = _num(rec.get(src))
        out.append(row)
    return out


def schedule_dates(df: pd.DataFrame) -> dict:
    """contest id -> ISO date from a season's schedule file (MM/DD/YYYY)."""
    out = {}
    for rec in df.to_dict("records"):
        c = _s(rec.get("contest_id")) or ""
        try:
            m, d, y = str(rec.get("game_date") or "").split("/")
            out[c] = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
        except ValueError:
            continue
    return out


# Stats-tab log (add_ncaabw_player_game_log_2026_11_12.sql). Same columns as
# the men's ncaab_player_game_log, minus loaded_at. position and is_starter
# stay null: the player box file has neither.
LOG_TABLE = "ncaabw_player_game_log"
LOG_COLS = ("game_id", "player_id", "player_name", "team", "team_espn_id",
            "espn_event_id", "season", "game_date", "position", "is_starter",
            "minutes", "points", "rebounds", "offensive_reb", "defensive_reb",
            "assists", "steals", "blocks", "turnovers", "fouls", "fg_made",
            "fg_att", "fg3_made", "fg3_att", "ft_made", "ft_att", "source")
_LOG_INSERT = (
    "INSERT INTO ncaabw_player_game_log (" + ", ".join(LOG_COLS)
    + ") VALUES (" + ", ".join(f"%({c})s" for c in LOG_COLS)
    + ") ON CONFLICT (game_id, player_id) DO NOTHING")


def _count(v):
    n = _num(v)
    return None if n is None else int(round(n))


def _played(rec: dict) -> bool:
    """A box row that is a game, not an empty did-not-play line.

    The file has no didNotPlay flag. Minutes above zero is a game. A row with
    no minutes and every count zero is left out, the same cut the men's ESPN
    parser makes. A count with no minutes is kept: that is a missing number,
    not a player who did not play.
    """
    mins = _num(rec.get("mins"))
    if mins is not None and mins > 0:
        return True
    for col in ("pts", "orb", "drb", "ast", "stl", "blk", "tov", "fgm", "tpm", "ftm"):
        n = _count(rec.get(col))
        if n:
            return True
    return False


def game_log_rows(df: pd.DataFrame, games: dict) -> list[dict]:
    """One dict per player per stored game, in LOG_COLS order's keys.

    `games` maps an ESPN event id to the stored game: game_id, game_date,
    season, home_espn_id, away_espn_id, home_team, away_team. `team` on the
    row is that stored school, never the file's own team string (the file
    says "Colorado St."; games says "Colorado State"). A row with no ESPN
    game id, or whose id is not one of ours, is left out: the board joins on
    our game_id.

    player_id is "{team espn id}:{folded name}". The file's player_id is
    NCAA's, and that id changes every season (see the module docstring), so
    using it would split one player into a new board row each year.
    """
    best: dict[tuple, dict] = {}
    for rec in df.to_dict("records"):
        if not _played(rec):
            continue
        espn = _int_or_none(rec.get("espn_game_id"))
        team_id = _int_or_none(rec.get("team_espn_team_id"))
        game = games.get(espn) if espn is not None else None
        name = _s(rec.get("clean_name"))
        key_name = player_key(name or "")
        if game is None or team_id is None or not key_name:
            continue
        if team_id == game["home_espn_id"]:
            school = game["home_team"]
        elif team_id == game["away_espn_id"]:
            school = game["away_team"]
        else:
            continue
        orb, drb = _count(rec.get("orb")), _count(rec.get("drb"))
        rebounds = None if orb is None and drb is None else (orb or 0) + (drb or 0)
        row = {
            "game_id": game["game_id"],
            "player_id": f"{team_id}:{key_name}",
            "player_name": name,
            "team": school,
            "team_espn_id": team_id,
            "espn_event_id": espn,
            "season": int(game["season"]),
            "game_date": game["game_date"],
            "position": None,
            "is_starter": None,
            "minutes": _num(rec.get("mins")),
            "points": _count(rec.get("pts")),
            "rebounds": rebounds,
            "offensive_reb": orb,
            "defensive_reb": drb,
            "assists": _count(rec.get("ast")),
            "steals": _count(rec.get("stl")),
            "blocks": _count(rec.get("blk")),
            "turnovers": _count(rec.get("tov")),
            "fouls": _count(rec.get("pf")),
            "fg_made": _count(rec.get("fgm")),
            "fg_att": _count(rec.get("fga")),
            "fg3_made": _count(rec.get("tpm")),
            "fg3_att": _count(rec.get("tpa")),
            "ft_made": _count(rec.get("ftm")),
            "ft_att": _count(rec.get("fta")),
            "source": SOURCE,
        }
        slot = (row["game_id"], row["player_id"])
        prev = best.get(slot)
        if prev is not None:
            logger.info("ncaabw player log: {} {} is in the file twice; "
                        "keeping the longer minutes", row["game_id"], row["player_id"])
        if prev is None or (row["minutes"] or 0) > (prev["minutes"] or 0):
            best[slot] = row
    return list(best.values())


def _log_table_ready(conn) -> bool:
    """True only when the hand-applied migration has created the log.

    A missing table is not an error and is not created here. The daily box
    step keeps running on a database that has not had the migration yet.
    """
    row = conn.execute(
        "SELECT to_regclass(%s)", ("public.ncaabw_player_game_log",)).fetchone()
    return bool(row and row[0])


def _stored_games(conn, season: int) -> dict:
    rows = conn.execute(
        "SELECT e.espn_event_id, e.game_id, e.game_date, e.season, "
        "e.home_espn_id, e.away_espn_id, g.home_team, g.away_team "
        "FROM ncaabw_events e "
        "JOIN games g ON g.game_id = e.game_id AND g.sport = 'NCAABW' "
        "WHERE e.season = %s",
        (int(season),)).fetchall()
    return {int(r[0]): {"game_id": r[1], "game_date": r[2], "season": int(r[3]),
                        "home_espn_id": int(r[4]), "away_espn_id": int(r[5]),
                        "home_team": r[6], "away_team": r[7]}
            for r in rows}


def _write_game_log(conn, season: int, df: pd.DataFrame) -> int | None:
    """Insert log rows for sides not stored yet. None when the table is absent.

    A stored (game, team) is left alone: a corrected box is a --force concern.
    The skip is the side, not the whole game, so a day when only one school's
    ESPN id matched still picks up the other school on the next read.
    """
    if not _log_table_ready(conn):
        return None
    rows = game_log_rows(df, _stored_games(conn, season))
    have = {(r[0], int(r[1])) for r in conn.execute(
        "SELECT game_id, team_espn_id FROM ncaabw_player_game_log "
        "WHERE season = %s AND source = %s",
        (int(season), SOURCE)).fetchall()}
    new = [r for r in rows if (r["game_id"], int(r["team_espn_id"])) not in have]
    for i in range(0, len(new), 2000):
        conn.executemany(_LOG_INSERT, new[i:i + 2000])
    if new:
        conn.commit()
    return len(new)


def player_rows(df: pd.DataFrame, season: int) -> list[dict]:
    """Season totals per (team, player name)."""
    df = df.copy()
    df["team_espn_id"] = df["team_espn_team_id"].map(_int_or_none)
    df = df[df["team_espn_id"].notna()]
    df["player_key"] = df["clean_name"].map(player_key)
    df = df[df["player_key"] != ""]
    for c in _PLAYER_SUMS:
        df[c] = pd.to_numeric(df.get(c), errors="coerce")
    g = df.groupby(["team_espn_id", "player_key"])
    agg = g[list(_PLAYER_SUMS)].sum(min_count=1)
    agg["games"] = g["espn_game_id"].nunique()
    agg["clean_name"] = g["clean_name"].first()
    out = []
    for (team, key), rec in agg.iterrows():
        row = {"season": season, "team_espn_id": int(team), "player_key": key,
               "clean_name": rec["clean_name"], "games": int(rec["games"]),
               "source": SOURCE}
        for c in _PLAYER_SUMS:
            row[c] = _num(rec[c])
        out.append(row)
    return out


_TEAM_UPSERT = (
    "INSERT INTO ncaabw_team_game_stats (" + ", ".join(c for c in TEAM_COLS if c != "loaded_at")
    + ") VALUES (" + ", ".join(f"%({c})s" for c in TEAM_COLS if c != "loaded_at")
    + ") ON CONFLICT (contest_id, team) DO UPDATE SET "
    + ", ".join(f"{c} = EXCLUDED.{c}" for c in TEAM_COLS
                if c not in ("contest_id", "team", "loaded_at"))
    + ", loaded_at = NOW()")
_PLAYER_UPSERT = (
    "INSERT INTO ncaabw_player_season (" + ", ".join(c for c in PLAYER_COLS if c != "loaded_at")
    + ") VALUES (" + ", ".join(f"%({c})s" for c in PLAYER_COLS if c != "loaded_at")
    + ") ON CONFLICT (season, team_espn_id, player_key) DO UPDATE SET "
    + ", ".join(f"{c} = EXCLUDED.{c}" for c in PLAYER_COLS
                if c not in ("season", "team_espn_id", "player_key", "loaded_at"))
    + ", loaded_at = NOW()")


def stored_seasons(conn, table: str) -> set[int]:
    """Seasons already imported under this module's SOURCE (the resume key)."""
    return {int(r[0]) for r in conn.execute(
        f"SELECT DISTINCT season FROM {table} WHERE source = %s", (SOURCE,)).fetchall()}


def import_season(conn, season: int, *, team: bool = True, players: bool = True) -> dict:
    out = {"season": season, "team_rows": 0, "player_rows": 0}
    if team:
        df = _fetch_parquet(TEAM_BOX_URL.format(season=season))
        if df is None:
            out["team_missing"] = True
        else:
            sched = _fetch_parquet(SCHEDULE_URL.format(season=season))
            dates = schedule_dates(sched) if sched is not None else {}
            rows = team_rows(df, season, dates)
            for i in range(0, len(rows), 2000):
                conn.executemany(_TEAM_UPSERT, rows[i:i + 2000])
            conn.commit()
            out["team_rows"] = len(rows)
    if players:
        df = _fetch_parquet(PLAYER_BOX_URL.format(season=season))
        if df is None:
            out["player_missing"] = True
        else:
            rows = player_rows(df, season)
            for i in range(0, len(rows), 2000):
                conn.executemany(_PLAYER_UPSERT, rows[i:i + 2000])
            conn.commit()
            out["player_rows"] = len(rows)
            logged = _write_game_log(conn, season, df)
            if logged is not None:
                out["log_rows"] = logged
    return out


_TEAM_INSERT_NEW = (
    "INSERT INTO ncaabw_team_game_stats (" + ", ".join(c for c in TEAM_COLS if c != "loaded_at")
    + ") VALUES (" + ", ".join(f"%({c})s" for c in TEAM_COLS if c != "loaded_at")
    + ") ON CONFLICT (contest_id, team) DO NOTHING")


def refresh_season(conn, season: int) -> dict:
    """The daily read of one season's team box file: store the contests that
    are not stored yet, and leave every stored row alone.

    The women's 2026-27 file is built in season (it held games through
    2026-11-08 on 2026-11-09), and it is the second box source of the totals
    model: on 2026-11-10 it held 5 of the 6 finals whose ESPN box the ESPN
    feed refused. A stored row is never rewritten here (import_season with
    --force does that), so a day with nothing new writes nothing.
    -> {season, file_rows, new_rows, team_missing?}."""
    out = {"season": int(season), "file_rows": 0, "new_rows": 0}
    df = _fetch_parquet(TEAM_BOX_URL.format(season=season))
    if df is None:
        out["team_missing"] = True
        return out
    sched = _fetch_parquet(SCHEDULE_URL.format(season=season))
    dates = schedule_dates(sched) if sched is not None else {}
    rows = team_rows(df, int(season), dates)
    out["file_rows"] = len(rows)
    ensure_tables(conn)
    have = {(r[0], r[1]) for r in conn.execute(
        "SELECT contest_id, team FROM ncaabw_team_game_stats WHERE season = %s AND source = %s",
        (int(season), SOURCE)).fetchall()}
    new = [r for r in rows if (r["contest_id"], r["team"]) not in have]
    for i in range(0, len(new), 2000):
        conn.executemany(_TEAM_INSERT_NEW, new[i:i + 2000])
    conn.commit()
    out["new_rows"] = len(new)
    # The Stats log, only after the migration has created the table. A missing
    # table adds nothing to the result, so a database that has not been
    # migrated keeps this step's old shape.
    if _log_table_ready(conn):
        df = _fetch_parquet(PLAYER_BOX_URL.format(season=int(season)))
        out["log_rows"] = 0 if df is None else (_write_game_log(conn, int(season), df) or 0)
    return out


def run_refresh(run_date: str | None = None, *, connect=None) -> dict:
    """refresh_season for the season `run_date` (ET, default today) falls in."""
    from datetime import date as _date

    from data.ingestors import ncaabw_teams as nt
    day = run_date or _date.today().isoformat()
    season = nt.ncaabw_season_label(day)
    if connect is None:
        from data.db import get_connection as connect
    conn = connect()
    try:
        return refresh_season(conn, season)
    finally:
        conn.close()


def import_game_logs(conn, first: int, last: int) -> list[dict]:
    """Fill the player log for a season range. Empty when the table is absent.

    Does not rewrite team boxes or season totals. A season whose totals are
    already stored is still read: `main` skips those seasons, and head-to-head
    looks at this season and the one before it.
    """
    if not _log_table_ready(conn):
        return []
    out = []
    for season in range(int(first), int(last) + 1):
        df = _fetch_parquet(PLAYER_BOX_URL.format(season=season))
        if df is None:
            out.append({"season": season, "log_rows": 0, "player_missing": True})
            continue
        out.append({"season": season, "log_rows": _write_game_log(conn, season, df) or 0})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seasons", nargs=2, type=int, metavar=("FIRST", "LAST"),
                    default=(2011, 2026), help="ending-year seasons (2026 = 2025-26)")
    ap.add_argument("--force", action="store_true", help="re-import stored seasons")
    ap.add_argument("--log", action="store_true",
                    help="fill ncaabw_player_game_log only; do not rewrite stored rows")
    args = ap.parse_args(argv)

    from data.db import get_connection
    conn = get_connection()
    try:
        if args.log:
            res = import_game_logs(conn, args.seasons[0], args.seasons[1])
            if not res and not _log_table_ready(conn):
                print("ncaabw_player_game_log is not created yet")
                return 1
            for row in res:
                print(row)
            return 0
        ensure_tables(conn)
        have_t = stored_seasons(conn, TEAM_TABLE)
        have_p = stored_seasons(conn, PLAYER_TABLE)
        for s in range(args.seasons[0], args.seasons[1] + 1):
            t = args.force or s not in have_t
            p = args.force or s not in have_p
            if not (t or p):
                print(f"{s}: already stored")
                continue
            res = import_season(conn, s, team=t, players=p)
            print(f"{s}: {res}")
            logger.info(f"ncaabw_sdv_import {res}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
