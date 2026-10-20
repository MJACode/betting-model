"""NBA box-score detail for a minutes/usage model: starters, exact minutes,
plus/minus, fouls, DNP reasons, usage, possessions, officials, inactives.

WHY. `nba_player_game_log` comes from LeagueGameLog, which carries whole-number
minutes, no starter flag (is_starter NULL on all 202,620 rows, measured
2026-10-15), no plus/minus, no fouls, and no row at all for a player who did not
play. There was no record of who refereed a game or who was inactive for it, and
the five neutral-site regular-season games a season that the schedule backfill
added to `games` had no player rows.

SOURCES (all free; nothing here touches a paid API).
  * sportsdataverse-data GitHub releases, one parquet per season:
      nba_stats_player_boxscores/player_boxscores_<season>.parquet
          -- boxscoretraditionalv3 for every game of the season: NBA.com
             person_id, starting `position` (blank for the bench), `minutes`
             as "MM:SS", `comment` (the DNP/DND/NWT reason), fouls_personal,
             plus_minus_points. Every DNP player is a row.
      nba_stats_officials/officials_<season>.parquet       -- the crew per game
      nba_stats_game_rosters/game_rosters_<season>.parquet -- the inactive list
    The files are keyed on the NBA.com game id and carry NO date, so a row
    reaches our game_id only through `nba_schedule` (nba_game_id -> game_id).
    A game the schedule does not know is dropped and counted, never guessed.
  * stats.nba.com PlayerGameLogs, MeasureType=Advanced, one call per season
    per season type: USG_PCT, POSS, PACE, ratings. Players who did not play
    are not in it, so their advanced columns stay NULL.

WHAT IT WRITES.
  * nba_player_game_adv  -- one row per (game_id, player_id), DNPs included.
  * nba_game_officials   -- one row per (game_id, official_id).
  * nba_game_inactives   -- one row per (game_id, player_id). The source has no
                            reason column, so `reason` is NULL.
  * nba_player_game_log  -- the regular-season games in `games` that have no
                            player rows get them (LeagueGameLog P, the layout of
                            nba_stats_ingestor), and is_starter is set from
                            nba_player_game_adv where it is NULL.

RESUMABLE. Every write is an idempotent upsert committed in chunks, and a
season whose row count for this source already equals what the file resolves
to is skipped, so a restart redoes only the season it died in.

The parquet files are a throwaway cache under %TEMP%/nba_rebuild/sdv; every
row is in Supabase.

    python -m data.ingestors.nba_box_enrich --seasons 2019 2026
    python -m data.ingestors.nba_box_enrich --seasons 2019 2026 --parts fill starters
    python -m data.ingestors.nba_box_enrich --seasons 2019 2026 --validate --sample 20
"""
from __future__ import annotations

import argparse
import math
import random
import re
import tempfile
import time
from pathlib import Path

import pandas as pd
from loguru import logger

from data.anon_readable import API_ROLES, lock_down
from data.db import get_connection
from data.ddl_guard import schema_is_current
from data.ingestors.nba_stats_ingestor import (
    _build_player_log_rows, _fetch_league_game_log, _norm_nba, _upsert_player_log,
)

SDV_BASE = ("https://github.com/sportsdataverse/sportsdataverse-data/"
            "releases/download")
SDV_FILES = {
    "box": ("nba_stats_player_boxscores", "player_boxscores_{season}.parquet"),
    "officials": ("nba_stats_officials", "officials_{season}.parquet"),
    "inactives": ("nba_stats_game_rosters", "game_rosters_{season}.parquet"),
}
CACHE_DIR = Path(tempfile.gettempdir()) / "nba_rebuild" / "sdv"

SOURCE_BOX = "sdv_nba_stats_player_boxscores"
SOURCE_ADV = "nba_api_playergamelogs_advanced"
SOURCE_OFFICIALS = "sdv_nba_stats_officials"
SOURCE_INACTIVES = "sdv_nba_stats_game_rosters"

# Game types the box files carry. Preseason and All-Star games are not in them
# and are not wanted.
GAME_TYPES = ("regular", "playin", "playoff", "cup_final")

# stats.nba.com season types for the Advanced log. IST is the NBA Cup; only its
# "006" final is taken from it -- its group and knockout games are regular
# season and already come back under "Regular Season".
ADV_SEASON_TYPES = ("Regular Season", "Playoffs", "PlayIn", "IST")
ADV_REQUIRED = ("Regular Season", "Playoffs")

# stats.nba.com column -> our column. Rank columns are derivable and skipped.
ADV_COLS = {
    "USG_PCT": "usage_pct", "E_USG_PCT": "e_usage_pct", "POSS": "possessions",
    "PACE": "pace", "E_PACE": "e_pace", "PACE_PER40": "pace_per40",
    "OFF_RATING": "off_rating", "DEF_RATING": "def_rating",
    "NET_RATING": "net_rating", "E_OFF_RATING": "e_off_rating",
    "E_DEF_RATING": "e_def_rating", "E_NET_RATING": "e_net_rating",
    "AST_PCT": "ast_pct", "AST_TO": "ast_to", "AST_RATIO": "ast_ratio",
    "OREB_PCT": "oreb_pct", "DREB_PCT": "dreb_pct", "REB_PCT": "reb_pct",
    "TM_TOV_PCT": "tm_tov_pct", "E_TOV_PCT": "e_tov_pct", "EFG_PCT": "efg_pct",
    "TS_PCT": "ts_pct", "PIE": "pie",
}

REQUEST_SLEEP = 0.6
CHUNK = 1000        # rows per multi-row INSERT; ~45 params a row stays < 65,535

ADV_DDL = """
CREATE TABLE IF NOT EXISTS nba_player_game_adv (
    game_id             TEXT NOT NULL,
    player_id           TEXT NOT NULL,
    nba_game_id         TEXT NOT NULL,
    season              INTEGER NOT NULL,
    game_type           TEXT NOT NULL,
    game_date           TEXT NOT NULL,
    team                TEXT NOT NULL,
    opponent            TEXT,
    is_home             BOOLEAN,
    player_name         TEXT,
    position            TEXT,
    is_starter          INTEGER NOT NULL,
    played              BOOLEAN NOT NULL,
    minutes_exact       DOUBLE PRECISION,
    seconds_played      INTEGER,
    plus_minus          INTEGER,
    fouls               INTEGER,
    did_not_play_reason TEXT,
    dnp_kind            TEXT,
    usage_pct           DOUBLE PRECISION,
    e_usage_pct         DOUBLE PRECISION,
    possessions         INTEGER,
    pace                DOUBLE PRECISION,
    e_pace              DOUBLE PRECISION,
    pace_per40          DOUBLE PRECISION,
    off_rating          DOUBLE PRECISION,
    def_rating          DOUBLE PRECISION,
    net_rating          DOUBLE PRECISION,
    e_off_rating        DOUBLE PRECISION,
    e_def_rating        DOUBLE PRECISION,
    e_net_rating        DOUBLE PRECISION,
    ast_pct             DOUBLE PRECISION,
    ast_to              DOUBLE PRECISION,
    ast_ratio           DOUBLE PRECISION,
    oreb_pct            DOUBLE PRECISION,
    dreb_pct            DOUBLE PRECISION,
    reb_pct             DOUBLE PRECISION,
    tm_tov_pct          DOUBLE PRECISION,
    e_tov_pct           DOUBLE PRECISION,
    efg_pct             DOUBLE PRECISION,
    ts_pct              DOUBLE PRECISION,
    pie                 DOUBLE PRECISION,
    source              TEXT NOT NULL,
    adv_source          TEXT,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (game_id, player_id)
)
"""
ADV_INDEXES = {
    "idx_nba_pga_player": "CREATE INDEX IF NOT EXISTS idx_nba_pga_player "
                          "ON nba_player_game_adv (player_id, game_date)",
    "idx_nba_pga_season": "CREATE INDEX IF NOT EXISTS idx_nba_pga_season "
                          "ON nba_player_game_adv (season, game_type)",
}

OFFICIALS_DDL = """
CREATE TABLE IF NOT EXISTS nba_game_officials (
    game_id         TEXT NOT NULL,
    official_id     TEXT NOT NULL,
    official_name   TEXT,
    jersey          TEXT,
    nba_game_id     TEXT NOT NULL,
    season          INTEGER NOT NULL,
    game_type       TEXT NOT NULL,
    game_date       TEXT NOT NULL,
    source          TEXT NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (game_id, official_id)
)
"""
OFFICIALS_INDEXES = {
    "idx_nba_go_official": "CREATE INDEX IF NOT EXISTS idx_nba_go_official "
                           "ON nba_game_officials (official_id, game_date)",
    "idx_nba_go_season": "CREATE INDEX IF NOT EXISTS idx_nba_go_season "
                         "ON nba_game_officials (season)",
}

INACTIVES_DDL = """
CREATE TABLE IF NOT EXISTS nba_game_inactives (
    game_id         TEXT NOT NULL,
    team            TEXT NOT NULL,
    player_id       TEXT NOT NULL,
    player_name     TEXT,
    reason          TEXT,
    jersey          TEXT,
    nba_game_id     TEXT NOT NULL,
    season          INTEGER NOT NULL,
    game_type       TEXT NOT NULL,
    game_date       TEXT NOT NULL,
    source          TEXT NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (game_id, player_id)
)
"""
INACTIVES_INDEXES = {
    "idx_nba_gi_player": "CREATE INDEX IF NOT EXISTS idx_nba_gi_player "
                         "ON nba_game_inactives (player_id, game_date)",
    "idx_nba_gi_season": "CREATE INDEX IF NOT EXISTS idx_nba_gi_season "
                         "ON nba_game_inactives (season)",
}

ADV_ROW_COLS = (
    "game_id", "player_id", "nba_game_id", "season", "game_type", "game_date",
    "team", "opponent", "is_home", "player_name", "position", "is_starter",
    "played", "minutes_exact", "seconds_played", "plus_minus", "fouls",
    "did_not_play_reason", "dnp_kind", *ADV_COLS.values(), "source", "adv_source",
)
OFFICIAL_ROW_COLS = ("game_id", "official_id", "official_name", "jersey",
                     "nba_game_id", "season", "game_type", "game_date", "source")
INACTIVE_ROW_COLS = ("game_id", "team", "player_id", "player_name", "reason",
                     "jersey", "nba_game_id", "season", "game_type", "game_date",
                     "source")


# ── parsing ───────────────────────────────────────────────────────────────────

_MIN = re.compile(r"^\s*(\d+):(\d{1,2})\s*$")


def _blank(v) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    return isinstance(v, str) and not v.strip()


def minutes_to_seconds(raw) -> int | None:
    """'45:15' -> 2715. A blank string is NULL: the player did not play."""
    if _blank(raw):
        return None
    m = _MIN.match(str(raw))
    if not m:
        raise ValueError(f"unreadable minutes string {raw!r}")
    return int(m.group(1)) * 60 + int(m.group(2))


def minutes_to_float(raw) -> float | None:
    """'45:15' -> 45.25. '0:00' is a real 0 (checked in); '' is NULL (DNP)."""
    s = minutes_to_seconds(raw)
    return None if s is None else s / 60.0


def dnp_kind(comment) -> str | None:
    """DNP (coach's decision etc.), DND (did not dress), NWT (not with team)."""
    if _blank(comment):
        return None
    m = re.match(r"\s*([A-Za-z]{3})", str(comment))
    return m.group(1).upper() if m else None


def _txt(v) -> str | None:
    return None if _blank(v) else str(v).strip()


def _int(v) -> int | None:
    if _blank(v):
        return None
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def _flt(v) -> float | None:
    if _blank(v):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def _gid(v) -> str:
    """NBA.com game ids are 10-digit strings with leading zeros."""
    s = str(v).strip()
    return s.zfill(10) if s.isdigit() else s


def _game(sched: dict, nba_game_id: str, unmapped: set) -> dict | None:
    g = sched.get(nba_game_id)
    if g is None:
        unmapped.add(nba_game_id)
    return g


def box_rows(box: pd.DataFrame, sched: dict, adv: pd.DataFrame | None = None
             ) -> tuple[list[dict], set[str]]:
    """One row per player per game, DNPs included.

    `sched` maps NBA.com game id -> {game_id, season, game_type, game_date,
    home_team, away_team}. `adv` is the PlayerGameLogs Advanced frame (any
    season types concatenated); a player missing from it gets NULL advanced
    columns. Returns (rows, NBA.com game ids the schedule did not know).
    """
    adv_by: dict[tuple[str, str], dict] = {}
    if adv is not None and len(adv):
        for r in adv.to_dict("records"):
            adv_by[(_gid(r["GAME_ID"]), str(int(r["PLAYER_ID"])))] = r

    rows: list[dict] = []
    unmapped: set[str] = set()
    for r in box.to_dict("records"):
        ngid = _gid(r["game_id"])
        g = _game(sched, ngid, unmapped)
        if g is None:
            continue
        team = _norm_nba(str(r.get("team_tricode") or ""))
        if team not in (g["home_team"], g["away_team"]):
            raise ValueError(f"box row for {team} in {ngid}, which the schedule "
                             f"has as {g['away_team']} @ {g['home_team']}")
        is_home = team == g["home_team"]
        side = _txt(r.get("side"))
        if side is not None and (side == "home") != is_home:
            raise ValueError(f"{team} side={side} in {ngid} disagrees with the schedule")
        pid = str(int(r["person_id"]))
        secs = minutes_to_seconds(r.get("minutes"))
        played = secs is not None
        comment = _txt(r.get("comment"))
        position = _txt(r.get("position"))
        name = " ".join(x for x in (_txt(r.get("first_name")),
                                    _txt(r.get("family_name"))) if x)
        a = adv_by.get((ngid, pid)) if played else None
        row = {
            "game_id": g["game_id"], "player_id": pid, "nba_game_id": ngid,
            "season": g["season"], "game_type": g["game_type"],
            "game_date": g["game_date"], "team": team,
            "opponent": g["away_team"] if is_home else g["home_team"],
            "is_home": is_home, "player_name": name or None,
            "position": position, "is_starter": 1 if position else 0,
            "played": played,
            "minutes_exact": None if secs is None else secs / 60.0,
            "seconds_played": secs,
            "plus_minus": _int(r.get("plus_minus_points")) if played else None,
            "fouls": _int(r.get("fouls_personal")) if played else None,
            "did_not_play_reason": None if played else comment,
            "dnp_kind": None if played else dnp_kind(comment),
            "source": SOURCE_BOX,
            "adv_source": SOURCE_ADV if a is not None else None,
        }
        for src, dst in ADV_COLS.items():
            v = a.get(src) if a is not None else None
            row[dst] = _int(v) if dst == "possessions" else _flt(v)
        rows.append(row)
    return rows, unmapped


def official_rows(df: pd.DataFrame, sched: dict) -> tuple[list[dict], set[str]]:
    rows, unmapped, seen = [], set(), set()
    for r in df.to_dict("records"):
        ngid = _gid(r["game_id"])
        g = _game(sched, ngid, unmapped)
        if g is None:
            continue
        oid = str(int(r["official_id"]))
        if (g["game_id"], oid) in seen:
            continue
        seen.add((g["game_id"], oid))
        name = " ".join(x for x in (_txt(r.get("first_name")),
                                    _txt(r.get("last_name"))) if x)
        rows.append({
            "game_id": g["game_id"], "official_id": oid,
            "official_name": name or None, "jersey": _txt(r.get("jersey_num")),
            "nba_game_id": ngid, "season": g["season"],
            "game_type": g["game_type"], "game_date": g["game_date"],
            "source": SOURCE_OFFICIALS,
        })
    return rows, unmapped


def inactive_rows(df: pd.DataFrame, sched: dict) -> tuple[list[dict], set[str]]:
    rows, unmapped, seen = [], set(), set()
    for r in df.to_dict("records"):
        ngid = _gid(r["game_id"])
        g = _game(sched, ngid, unmapped)
        if g is None:
            continue
        pid = str(int(r["player_id"]))
        if (g["game_id"], pid) in seen:
            continue
        seen.add((g["game_id"], pid))
        team = _norm_nba(str(r.get("team_abbreviation") or ""))
        if team not in (g["home_team"], g["away_team"]):
            raise ValueError(f"inactive {pid} for {team} in {ngid}, which the "
                             f"schedule has as {g['away_team']} @ {g['home_team']}")
        name = " ".join(x for x in (_txt(r.get("first_name")),
                                    _txt(r.get("last_name"))) if x)
        rows.append({
            "game_id": g["game_id"], "team": team, "player_id": pid,
            "player_name": name or None, "reason": None,
            "jersey": _txt(r.get("jersey_num")), "nba_game_id": ngid,
            "season": g["season"], "game_type": g["game_type"],
            "game_date": g["game_date"], "source": SOURCE_INACTIVES,
        })
    return rows, unmapped


def neutral_fill_rows(player_df: pd.DataFrame, id_map: dict[str, str],
                      season: int) -> list[dict]:
    """nba_player_game_log rows for the games in `id_map` only (NBA.com game id
    -> our game_id), in nba_stats_ingestor's layout."""
    if player_df is None or not len(player_df):
        return []
    df = player_df.copy()
    df["GAME_ID"] = df["GAME_ID"].map(_gid)
    df = df[df["GAME_ID"].isin(set(id_map))]
    return _build_player_log_rows(df, id_map, season)


def starter_update_batches(game_ids: list[str], size: int = 100):
    for i in range(0, len(game_ids), size):
        yield list(game_ids[i:i + size])


# ── fetch ─────────────────────────────────────────────────────────────────────

def sdv_file(kind: str, season: int, refresh: bool = False) -> pd.DataFrame:
    """The season's parquet from the sportsdataverse release, cached in %TEMP%."""
    import requests

    tag, pattern = SDV_FILES[kind]
    name = pattern.format(season=season)
    path = CACHE_DIR / name
    if refresh or not path.exists() or path.stat().st_size == 0:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        url = f"{SDV_BASE}/{tag}/{name}"
        for attempt in range(4):
            try:
                resp = requests.get(url, timeout=120)
                resp.raise_for_status()
                path.write_bytes(resp.content)
                break
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"{name}: {type(exc).__name__}; retry {attempt + 1}")
                time.sleep(5 * (attempt + 1))
        else:
            raise RuntimeError(f"could not download {url}")
    return pd.read_parquet(path)


def _season_str(season: int) -> str:
    return f"{season - 1}-{str(season)[-2:]}"


def fetch_advanced(season: int) -> pd.DataFrame:
    """PlayerGameLogs Advanced for every season type, one frame."""
    from nba_api.stats.endpoints import playergamelogs

    frames = []
    for st in ADV_SEASON_TYPES:
        df = None
        for attempt in range(4):
            try:
                df = playergamelogs.PlayerGameLogs(
                    season_nullable=_season_str(season), season_type_nullable=st,
                    measure_type_player_game_logs_nullable="Advanced",
                    timeout=120).get_data_frames()[0]
                break
            except Exception as exc:  # noqa: BLE001 -- stats.nba.com times out at random
                logger.warning(f"advanced {season} {st}: {type(exc).__name__}; "
                               f"retry {attempt + 1}")
                time.sleep(5 * (attempt + 1))
        time.sleep(REQUEST_SLEEP)
        if df is None:
            if st in ADV_REQUIRED:
                raise RuntimeError(f"PlayerGameLogs Advanced {season} {st} failed 4x")
            logger.warning(f"advanced {season} {st}: unavailable, left NULL")
            continue
        if not len(df):
            continue
        df = df.copy()
        df["GAME_ID"] = df["GAME_ID"].map(_gid)
        if st == "IST":
            df = df[df["GAME_ID"].str.startswith("006")]
        frames.append(df)
        logger.info(f"advanced {season} {st}: {len(df)} rows")
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    return out.drop_duplicates(["GAME_ID", "PLAYER_ID"], keep="first")


# ── database ──────────────────────────────────────────────────────────────────

def _create(conn, ddl: str, indexes: dict[str, str]) -> None:
    conn.execute(ddl)
    for stmt in indexes.values():
        conn.execute(stmt)


def ensure_tables(conn) -> None:
    """DDL only when the catalog says it is needed (data/ddl_guard.py): a no-op
    CREATE still fires PostgREST's schema reload. Each table is named literally
    so tests/test_anon_readable.py can see the guard and the lock-down."""
    if not schema_is_current(conn, "nba_player_game_adv",
                             columns=ADV_ROW_COLS, indexes=tuple(ADV_INDEXES),
                             rls=True, revoked_from=API_ROLES):
        _create(conn, ADV_DDL, ADV_INDEXES)
        lock_down(conn, "nba_player_game_adv")
    if not schema_is_current(conn, "nba_game_officials",
                             columns=OFFICIAL_ROW_COLS,
                             indexes=tuple(OFFICIALS_INDEXES),
                             rls=True, revoked_from=API_ROLES):
        _create(conn, OFFICIALS_DDL, OFFICIALS_INDEXES)
        lock_down(conn, "nba_game_officials")
    if not schema_is_current(conn, "nba_game_inactives",
                             columns=INACTIVE_ROW_COLS,
                             indexes=tuple(INACTIVES_INDEXES),
                             rls=True, revoked_from=API_ROLES):
        _create(conn, INACTIVES_DDL, INACTIVES_INDEXES)
        lock_down(conn, "nba_game_inactives")
    conn.commit()


def load_schedule(conn, first: int, last: int) -> dict[str, dict]:
    rows = conn.execute("""
        SELECT nba_game_id, game_id, season, game_type, game_date,
               home_team, away_team
          FROM nba_schedule
         WHERE season BETWEEN %s AND %s AND game_type = ANY(%s)
    """, (first, last, list(GAME_TYPES))).fetchall()
    return {r[0]: {"game_id": r[1], "season": r[2], "game_type": r[3],
                   "game_date": r[4], "home_team": r[5], "away_team": r[6]}
            for r in rows}


def upsert(conn, table: str, cols: tuple[str, ...], key: tuple[str, ...],
           rows: list[dict], chunk: int = CHUNK) -> int:
    """Multi-row INSERT ... ON CONFLICT through conn.execute, one commit per
    chunk (the scripts/restore_sharp_prop_history.py shape: execute_batch would
    be one round trip per 100 rows at ~100 ms each)."""
    if not rows:
        return 0
    upd = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in key)
    ph = "(" + ", ".join(["%s"] * len(cols)) + ")"
    head = f"INSERT INTO {table} ({', '.join(cols)}) VALUES "
    tail = f" ON CONFLICT ({', '.join(key)}) DO UPDATE SET {upd}, updated_at = NOW()"
    done = 0
    for i in range(0, len(rows), chunk):
        part = rows[i:i + chunk]
        conn.execute(head + ", ".join([ph] * len(part)) + tail,
                     tuple(r[c] for r in part for c in cols))
        conn.commit()
        done += len(part)
    return done


def _stored(conn, table: str, season: int, source: str) -> int:
    return conn.execute(f"SELECT count(*) FROM {table} WHERE season = %s AND source = %s",
                        (season, source)).fetchone()[0]


def _check_unmapped(kind: str, season: int, unmapped: set[str]) -> None:
    if unmapped:
        logger.warning(f"{kind} {season}: {len(unmapped)} NBA.com games not in "
                       f"nba_schedule, dropped: {sorted(unmapped)[:10]}")


def write_box(conn, season: int, sched: dict, force: bool = False) -> dict:
    box = sdv_file("box", season)
    probe, unmapped = box_rows(box, sched)
    _check_unmapped("box", season, unmapped)
    have = _stored(conn, "nba_player_game_adv", season, SOURCE_BOX)
    if have == len(probe) and not force:
        logger.info(f"box {season}: {have} rows already stored, skipped")
        return {"season": season, "part": "box", "rows": have, "skipped": True,
                "unmapped_games": len(unmapped)}
    adv = fetch_advanced(season)
    rows, _ = box_rows(box, sched, adv)
    played = sum(1 for r in rows if r["played"])
    with_adv = sum(1 for r in rows if r["adv_source"])
    n = upsert(conn, "nba_player_game_adv", ADV_ROW_COLS, ("game_id", "player_id"), rows)
    logger.info(f"box {season}: wrote {n} rows ({played} played, {with_adv} with "
                f"advanced, {len(unmapped)} games unmapped)")
    return {"season": season, "part": "box", "rows": n, "played": played,
            "with_advanced": with_adv, "unmapped_games": len(unmapped)}


def write_officials(conn, season: int, sched: dict, force: bool = False) -> dict:
    rows, unmapped = official_rows(sdv_file("officials", season), sched)
    _check_unmapped("officials", season, unmapped)
    have = _stored(conn, "nba_game_officials", season, SOURCE_OFFICIALS)
    if have == len(rows) and not force:
        logger.info(f"officials {season}: {have} rows already stored, skipped")
        return {"season": season, "part": "officials", "rows": have, "skipped": True}
    n = upsert(conn, "nba_game_officials", OFFICIAL_ROW_COLS,
               ("game_id", "official_id"), rows)
    logger.info(f"officials {season}: wrote {n} rows")
    return {"season": season, "part": "officials", "rows": n,
            "unmapped_games": len(unmapped)}


def write_inactives(conn, season: int, sched: dict, force: bool = False) -> dict:
    rows, unmapped = inactive_rows(sdv_file("inactives", season), sched)
    _check_unmapped("inactives", season, unmapped)
    have = _stored(conn, "nba_game_inactives", season, SOURCE_INACTIVES)
    if have == len(rows) and not force:
        logger.info(f"inactives {season}: {have} rows already stored, skipped")
        return {"season": season, "part": "inactives", "rows": have, "skipped": True}
    n = upsert(conn, "nba_game_inactives", INACTIVE_ROW_COLS,
               ("game_id", "player_id"), rows)
    logger.info(f"inactives {season}: wrote {n} rows")
    return {"season": season, "part": "inactives", "rows": n,
            "unmapped_games": len(unmapped)}


def fill_missing_game_logs(conn, first: int, last: int) -> list[dict]:
    """Player rows for regular-season games in `games` that have none."""
    missing = conn.execute("""
        SELECT g.game_id, g.season, s.nba_game_id
          FROM games g
          LEFT JOIN nba_schedule s ON s.game_id = g.game_id AND s.game_type = 'regular'
         WHERE g.sport = 'NBA' AND g.season BETWEEN %s AND %s
           AND g.home_score IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM nba_player_game_log p WHERE p.game_id = g.game_id)
         ORDER BY g.season, g.game_id
    """, (first, last)).fetchall()
    out = []
    by_season: dict[int, dict[str, str]] = {}
    for game_id, season, ngid in missing:
        if not ngid:
            logger.warning(f"fill: {game_id} has no regular-season nba_schedule row")
            out.append({"season": season, "game_id": game_id, "rows": 0,
                        "error": "no nba_schedule row"})
            continue
        by_season.setdefault(season, {})[ngid] = game_id
    for season, id_map in sorted(by_season.items()):
        frame = None
        for attempt in range(4):
            try:
                frame = _fetch_league_game_log(season, "P")
                break
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"LeagueGameLog P {season}: {type(exc).__name__}; "
                               f"retry {attempt + 1}")
                time.sleep(5 * (attempt + 1))
        if frame is None:
            raise RuntimeError(f"LeagueGameLog P {season} failed four times")
        time.sleep(REQUEST_SLEEP)
        rows = neutral_fill_rows(frame, id_map, season)
        _upsert_player_log(conn, rows)
        conn.commit()
        per_game: dict[str, int] = {}
        for r in rows:
            per_game[r["game_id"]] = per_game.get(r["game_id"], 0) + 1
        for ngid, gid in id_map.items():
            out.append({"season": season, "game_id": gid, "nba_game_id": ngid,
                        "rows": per_game.get(gid, 0)})
        logger.info(f"fill {season}: {len(rows)} player rows for {len(id_map)} games")
    return out


def update_starters(conn, first: int, last: int, batch: int = 100) -> dict:
    """nba_player_game_log.is_starter from nba_player_game_adv, NULLs only,
    ~100 games per statement, one commit each."""
    games = [r[0] for r in conn.execute("""
        SELECT DISTINCT game_id FROM nba_player_game_adv
         WHERE season BETWEEN %s AND %s AND game_type = 'regular'
         ORDER BY game_id
    """, (first, last)).fetchall()]
    updated = 0
    for ids in starter_update_batches(games, batch):
        cur = conn.execute("""
            UPDATE nba_player_game_log p
               SET is_starter = a.is_starter
              FROM nba_player_game_adv a
             WHERE a.game_id = p.game_id AND a.player_id = p.player_id
               AND p.game_id = ANY(%s) AND p.is_starter IS NULL
        """, (ids,))
        updated += cur.rowcount or 0
        conn.commit()
    logger.info(f"starters: set is_starter on {updated} nba_player_game_log rows "
                f"across {len(games)} games")
    return {"part": "starters", "games": len(games), "rows_updated": updated}


# ── validation ────────────────────────────────────────────────────────────────

def validate(conn, first: int, last: int, sample: int = 20, seed: int = 7) -> dict:
    out: dict = {}
    out["counts"] = conn.execute("""
        SELECT season, game_type, count(*), count(DISTINCT game_id),
               sum(CASE WHEN played THEN 1 ELSE 0 END),
               sum(is_starter), count(usage_pct)
          FROM nba_player_game_adv WHERE season BETWEEN %s AND %s
         GROUP BY 1, 2 ORDER BY 1, 2
    """, (first, last)).fetchall()
    out["starters_per_team_game"] = conn.execute("""
        SELECT s, count(*) FROM (
            SELECT game_id, team, sum(is_starter) s FROM nba_player_game_adv
             WHERE season BETWEEN %s AND %s GROUP BY 1, 2) t
         GROUP BY 1 ORDER BY 1
    """, (first, last)).fetchall()
    # Team minutes against 240 + 25 per overtime period (nba_schedule.ot_periods).
    out["minutes_vs_regulation"] = conn.execute("""
        WITH t AS (
            SELECT a.season, a.game_id, a.team, sum(a.seconds_played) secs,
                   max(s.ot_periods) ot
              FROM nba_player_game_adv a
              JOIN nba_schedule s ON s.nba_game_id = a.nba_game_id
             WHERE a.season BETWEEN %s AND %s
             GROUP BY 1, 2, 3)
        SELECT season, count(*),
               sum(CASE WHEN secs = (240 + 25 * ot) * 60 THEN 1 ELSE 0 END),
               sum(CASE WHEN abs(secs - (240 + 25 * ot) * 60) <= 60 THEN 1 ELSE 0 END),
               sum(CASE WHEN ot IS NULL THEN 1 ELSE 0 END),
               min(secs - (240 + 25 * ot) * 60), max(secs - (240 + 25 * ot) * 60)
          FROM t GROUP BY 1 ORDER BY 1
    """, (first, last)).fetchall()
    out["log_match"] = conn.execute("""
        SELECT p.season, count(*), count(a.player_id),
               sum(CASE WHEN p.is_starter IS NOT NULL THEN 1 ELSE 0 END),
               sum(CASE WHEN a.player_id IS NOT NULL
                         AND abs(a.minutes_exact - p.minutes) > 1 THEN 1 ELSE 0 END)
          FROM nba_player_game_log p
          LEFT JOIN nba_player_game_adv a
            ON a.game_id = p.game_id AND a.player_id = p.player_id
         WHERE p.season BETWEEN %s AND %s
         GROUP BY 1 ORDER BY 1
    """, (first, last)).fetchall()
    out["adv_played_not_in_log"] = conn.execute("""
        SELECT a.season, count(*) FROM nba_player_game_adv a
         WHERE a.season BETWEEN %s AND %s AND a.game_type = 'regular' AND a.played
           AND NOT EXISTS (SELECT 1 FROM nba_player_game_log p
                            WHERE p.game_id = a.game_id AND p.player_id = a.player_id)
         GROUP BY 1 ORDER BY 1
    """, (first, last)).fetchall()
    out["officials"] = conn.execute("""
        SELECT season, count(*), count(DISTINCT game_id) FROM nba_game_officials
         WHERE season BETWEEN %s AND %s GROUP BY 1 ORDER BY 1
    """, (first, last)).fetchall()
    out["inactives"] = conn.execute("""
        SELECT season, count(*), count(DISTINCT game_id) FROM nba_game_inactives
         WHERE season BETWEEN %s AND %s GROUP BY 1 ORDER BY 1
    """, (first, last)).fetchall()
    if sample:
        out["sample_compare"] = sample_compare(conn, first, last, sample, seed)
    return out


def sample_compare(conn, first: int, last: int, n: int, seed: int = 7) -> dict:
    """Live boxscoretraditionalv3 against what is stored, `n` games spread
    across the seasons. Every player row: starter, seconds, +/-, fouls, comment."""
    from nba_api.stats.endpoints import boxscoretraditionalv3

    games = conn.execute("""
        SELECT DISTINCT nba_game_id, season FROM nba_player_game_adv
         WHERE season BETWEEN %s AND %s
    """, (first, last)).fetchall()
    rng = random.Random(seed)
    by_season: dict[int, list[str]] = {}
    for g, s in games:
        by_season.setdefault(s, []).append(g)
    picks: list[str] = []
    seasons = sorted(by_season)
    while len(picks) < n and any(by_season.values()):
        for s in seasons:
            pool = sorted(set(by_season[s]) - set(picks))
            if pool and len(picks) < n:
                picks.append(rng.choice(pool))
    result = {"games": len(picks), "players": 0, "mismatches": []}
    for ngid in picks:
        live = None
        for attempt in range(4):
            try:
                live = boxscoretraditionalv3.BoxScoreTraditionalV3(
                    game_id=ngid, timeout=60).get_data_frames()[0]
                break
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"v3 {ngid}: {type(exc).__name__}; retry {attempt + 1}")
                time.sleep(3 * (attempt + 1))
        time.sleep(REQUEST_SLEEP)
        if live is None:
            result["mismatches"].append((ngid, "fetch failed"))
            continue
        stored = {r[0]: r for r in conn.execute("""
            SELECT player_id, is_starter, seconds_played, plus_minus, fouls,
                   did_not_play_reason
              FROM nba_player_game_adv WHERE nba_game_id = %s
        """, (ngid,)).fetchall()}
        live_ids = set()
        for r in live.to_dict("records"):
            pid = str(int(r["personId"]))
            live_ids.add(pid)
            result["players"] += 1
            s = stored.get(pid)
            if s is None:
                result["mismatches"].append((ngid, pid, "not stored"))
                continue
            secs = minutes_to_seconds(r.get("minutes"))
            played = secs is not None
            want = (1 if _txt(r.get("position")) else 0, secs,
                    _int(r.get("plusMinusPoints")) if played else None,
                    _int(r.get("foulsPersonal")) if played else None,
                    None if played else _txt(r.get("comment")))
            got = tuple(s[1:])
            if want != got:
                result["mismatches"].append((ngid, pid, want, got))
        for pid in set(stored) - live_ids:
            result["mismatches"].append((ngid, pid, "stored, not in live box"))
    return result


# ── entry point ───────────────────────────────────────────────────────────────

PARTS = ("box", "officials", "inactives", "fill", "starters")


def run(first: int, last: int, parts=PARTS, force: bool = False) -> list[dict]:
    conn = get_connection()
    try:
        ensure_tables(conn)
        sched = load_schedule(conn, first, last)
        logger.info(f"nba_schedule: {len(sched)} games for {first}-{last}")
        out = []
        for season in range(first, last + 1):
            if "box" in parts:
                out.append(write_box(conn, season, sched, force))
            if "officials" in parts:
                out.append(write_officials(conn, season, sched, force))
            if "inactives" in parts:
                out.append(write_inactives(conn, season, sched, force))
        if "fill" in parts:
            out.extend(fill_missing_game_logs(conn, first, last))
        if "starters" in parts:
            out.append(update_starters(conn, first, last))
        return out
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seasons", nargs=2, type=int, metavar=("FIRST", "LAST"),
                    required=True)
    ap.add_argument("--parts", nargs="+", choices=PARTS, default=list(PARTS))
    ap.add_argument("--force", action="store_true",
                    help="rewrite a season even when its row count already matches")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--sample", type=int, default=20)
    a = ap.parse_args()
    if a.validate:
        conn = get_connection()
        try:
            res = validate(conn, *a.seasons, sample=a.sample)
        finally:
            conn.close()
        for k, v in res.items():
            print(k, v)
        return
    for s in run(*a.seasons, parts=a.parts, force=a.force):
        print(s)


if __name__ == "__main__":
    main()
