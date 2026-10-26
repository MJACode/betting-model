"""
Men's college basketball history: per-game team box scores and season player
minutes, imported from sportsdataverse's public release files into Supabase.

WHY THESE FILES
---------------
They are NCAA's official play-by-play (stats.ncaa.org), already turned into
possessions by sportsdataverse and keyed on ESPN's game and team ids, so they
join straight onto ncaab_events. One parquet per season, about 1.4 MB for the
team box and 11 MB for the player box. stats.ncaa.org itself refuses requests
from this machine (HTTP 403, 2026-10-26), so these files are the route to the
official numbers.

WHAT LANDS WHERE (both worker-only, created on first write)
-----------------------------------------------------------
ncaab_team_game_stats  one row per (ESPN game, team): possessions, points,
                       shot mix (rim / three / free throws), rebounds,
                       turnovers. The rating model's input.
ncaab_player_season    one row per (season, team, player name): games,
                       minutes, possessions, scoring. Returning-minutes and
                       transfer inputs for the preseason rating. NCAA's player
                       ids change every season (measured: 0 of 1,573 returning
                       players kept their id from 2024-25 to 2025-26), so the
                       key is the normalised name within a team.

Everything in Supabase first (CLAUDE.md §1b): the parquet is read into memory
and written to the database; nothing is kept on disk. A re-run skips seasons
already stored under SOURCE unless --force.

    python -m data.ingestors.ncaab_sdv_import --seasons 2011 2026
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
TEAM_BOX_URL = RELEASE + "/ncaa_mbb_team_box/ncaa_mbb_team_box_{season}.parquet"
PLAYER_BOX_URL = RELEASE + "/ncaa_mbb_player_box/ncaa_mbb_player_box_{season}.parquet"

TEAM_TABLE = "ncaab_team_game_stats"
TEAM_COLS = ("espn_game_id", "team_espn_id", "opp_espn_id", "season", "home_espn_id",
             "away_espn_id", "mins", "o_poss", "d_poss", "pts", "d_pts", "fga", "fgm",
             "tpa", "tpm", "fta", "ftm", "rima", "rimm", "orb", "drb", "tov", "ast",
             "blk", "e_poss", "time_per_poss", "source", "loaded_at")
TEAM_DDL = """
CREATE TABLE IF NOT EXISTS ncaab_team_game_stats (
    espn_game_id   BIGINT NOT NULL,
    team_espn_id   INTEGER NOT NULL,
    opp_espn_id    INTEGER,
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
    PRIMARY KEY (espn_game_id, team_espn_id)
)
"""
TEAM_INDEX = ("CREATE INDEX IF NOT EXISTS idx_ncaab_tgs_season "
              "ON ncaab_team_game_stats (season)")

PLAYER_TABLE = "ncaab_player_season"
PLAYER_COLS = ("season", "team_espn_id", "player_key", "clean_name", "games", "mins",
               "o_poss", "pts", "fga", "fgm", "tpa", "tpm", "fta", "ftm", "orb", "drb",
               "ast", "stl", "blk", "tov", "pf", "source", "loaded_at")
PLAYER_DDL = """
CREATE TABLE IF NOT EXISTS ncaab_player_season (
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
                             indexes=("idx_ncaab_tgs_season",),
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


def team_rows(df: pd.DataFrame, season: int) -> list[dict]:
    """One dict per (game, team) with an ESPN game id and both ESPN team ids."""
    out = []
    for rec in df.to_dict("records"):
        gid = _int_or_none(rec.get("espn_game_id"))
        team = _int_or_none(rec.get("team_espn_team_id"))
        home = _int_or_none(rec.get("home_espn_team_id"))
        away = _int_or_none(rec.get("away_espn_team_id"))
        if gid is None or team is None:
            continue
        opp = away if team == home else (home if team == away else None)
        row = {"espn_game_id": gid, "team_espn_id": team, "opp_espn_id": opp,
               "season": season, "home_espn_id": home, "away_espn_id": away,
               "source": SOURCE}
        for src, dst in _TEAM_MAP.items():
            row[dst] = _num(rec.get(src))
        out.append(row)
    # A game listed twice for the same team keeps the first row (the PK).
    seen, uniq = set(), []
    for r in out:
        k = (r["espn_game_id"], r["team_espn_id"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    return uniq


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
    "INSERT INTO ncaab_team_game_stats (" + ", ".join(c for c in TEAM_COLS if c != "loaded_at")
    + ") VALUES (" + ", ".join(f"%({c})s" for c in TEAM_COLS if c != "loaded_at")
    + ") ON CONFLICT (espn_game_id, team_espn_id) DO UPDATE SET "
    + ", ".join(f"{c} = EXCLUDED.{c}" for c in TEAM_COLS
                if c not in ("espn_game_id", "team_espn_id", "loaded_at"))
    + ", loaded_at = NOW()")
_PLAYER_UPSERT = (
    "INSERT INTO ncaab_player_season (" + ", ".join(c for c in PLAYER_COLS if c != "loaded_at")
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
            rows = team_rows(df, season)
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
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seasons", nargs=2, type=int, metavar=("FIRST", "LAST"),
                    default=(2011, 2026), help="ending-year seasons (2026 = 2025-26)")
    ap.add_argument("--force", action="store_true", help="re-import stored seasons")
    args = ap.parse_args(argv)

    from data.db import get_connection
    conn = get_connection()
    try:
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
            logger.info(f"ncaab_sdv_import {res}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
