"""
baseball_savant_ingestor.py — Season-level Statcast metrics from Baseball Savant.

Pulls the Statcast leaderboard CSV for pitchers and batters and stores
season aggregates in player_savant_stats. These are used as features in
all prop models (not per-game outcomes — those come from player_game_log).

Pitcher metrics: k%, bb%, whiff%, swstr%, csw%, xERA, pitch mix, velocity
Batter metrics:  k%, bb%, BA, SLG, OBP, wOBA, xwOBA, xBA, barrel%, hard_hit%,
                 launch angle, exit velocity

Data source:
    Baseball Savant leaderboard CSV — same source already used for pitcher
    SwStr%/CSW%/xERA in mlb_stats_ingestor. No auth required.
    URL: https://baseballsavant.mlb.com/leaderboard/custom?...&csv=true

Usage:
    python -m data.ingestors.baseball_savant_ingestor --season 2026
    python -m data.ingestors.baseball_savant_ingestor --backfill 2019 2025
    python -m data.ingestors.baseball_savant_ingestor --season 2026 --type pitcher
    python -m data.ingestors.baseball_savant_ingestor --season 2026 --type batter
"""

import argparse
import io
import time
from datetime import datetime
from pathlib import Path
import sys

import requests
import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import SAVANT_BASE_URL
from data.db import get_connection, DBConnection

# ── Savant Column Mappings ────────────────────────────────────────────────────
# Maps Baseball Savant CSV column names → our DB column names.
# Savant column names are stable but not guaranteed — we try each name and
# fall back to None if a column is absent. This avoids hard failures when
# Savant tweaks their export format.

PITCHER_COLUMN_MAP = {
    # Savant CSV col          DB column
    "player_id":              "player_id",
    "player_name":            "player_name",      # "Last, First" format
    "team_abbrev":            "team",
    "k_percent":              "k_pct",
    "bb_percent":             "bb_pct",
    "whiff_percent":          "whiff_pct",
    "swstr_percent":          "swstr_pct",
    "csw_percent":            "csw_pct",
    "xera":                   "xera",
    "ff_avg_speed":           "avg_velocity",      # 4-seam avg velo
    "groundball_percent":     "gb_pct",            # groundball rate — HR suppression signal
    # Pitch usage % — column names vary across seasons
    "n_fastball_formatted":   "ff_pct",
    "n_slider_formatted":     "sl_pct",
    "n_changeup_formatted":   "ch_pct",
    "n_curveball_formatted":  "cu_pct",
    "n_sinker_formatted":     "si_pct",
    "n_cutter_formatted":     "fc_pct",
}

BATTER_COLUMN_MAP = {
    "player_id":              "player_id",
    "player_name":            "player_name",
    "team_abbrev":            "team",
    "k_percent":              "batter_k_pct",
    "bb_percent":             "batter_bb_pct",
    "batting_avg":            "batting_avg",
    "slg_percent":            "slg_pct",
    "on_base_percent":        "obp",
    "woba":                   "woba",
    "xwoba":                  "xwoba",
    "xba":                    "xba",
    "xslg":                   "xslg",
    "barrel_batted_rate":     "barrel_pct",
    "hard_hit_percent":       "hard_hit_pct",
    "launch_angle_avg":       "launch_angle",
    "exit_velocity_avg":      "exit_velocity",
    "sprint_speed":           "sprint_speed",
}

# Columns selected from Savant for each player type
PITCHER_SELECTIONS = (
    "k_percent,bb_percent,whiff_percent,swstr_percent,csw_percent,xera,"
    "ff_avg_speed,groundball_percent,"
    "n_fastball_formatted,n_slider_formatted,n_changeup_formatted,"
    "n_curveball_formatted,n_sinker_formatted,n_cutter_formatted"
)

BATTER_SELECTIONS = (
    "k_percent,bb_percent,batting_avg,slg_percent,on_base_percent,"
    "woba,xwoba,xba,xslg,barrel_batted_rate,hard_hit_percent,"
    "launch_angle_avg,exit_velocity_avg,sprint_speed"
)

# Seconds to sleep between requests — Savant has no auth but rate-limits heavy use
REQUEST_SLEEP = 2.0


# ── Savant Fetcher ────────────────────────────────────────────────────────────

def _fetch_savant_csv(player_type: str, season: int) -> pd.DataFrame:
    """
    Download the Statcast leaderboard CSV for a given player type and season.
    Returns a DataFrame. Empty DataFrame on error.

    player_type: 'pitcher' | 'batter'
    """
    selections = PITCHER_SELECTIONS if player_type == "pitcher" else BATTER_SELECTIONS
    params = {
        "year":       season,
        "type":       player_type,
        "filter":     "",
        "sort":       "4",
        "sortDir":    "desc",
        "min":        "0",        # include all players regardless of PA/BF
        "selections": selections,
        "csv":        "true",
    }

    try:
        resp = requests.get(SAVANT_BASE_URL, params=params, timeout=30,
                            headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            logger.warning(f"Savant {player_type} {season}: HTTP {resp.status_code}")
            return pd.DataFrame()

        content = resp.text
        if not content.strip() or content.startswith("<"):
            logger.warning(f"Savant {player_type} {season}: non-CSV response")
            return pd.DataFrame()

        df = pd.read_csv(io.StringIO(content))
        logger.info(f"Savant {player_type} {season}: {len(df)} rows, "
                    f"{len(df.columns)} columns")
        return df

    except Exception as exc:
        logger.warning(f"Savant fetch failed ({player_type} {season}): {exc}")
        return pd.DataFrame()


def _fetch_pitcher_gb_pct(season: int) -> dict[str, float]:
    """
    Fetch pitcher groundball % from the Savant statcast leaderboard.
    Returns {player_id: gb_pct_0_to_1}.  The custom leaderboard endpoint
    returns groundball_percent as all NaN; the statcast endpoint has it
    in the 'gb' column in 0-100 format (e.g. 48.3 = 48.3% GB rate).
    """
    url    = "https://baseballsavant.mlb.com/leaderboard/statcast"
    params = {"type": "pitcher", "year": season, "position": "",
              "team": "", "min": 0, "csv": "true"}
    try:
        time.sleep(REQUEST_SLEEP)
        resp = requests.get(url, params=params, timeout=30,
                            headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            logger.warning(f"Savant statcast pitcher {season}: HTTP {resp.status_code}")
            return {}
        df = pd.read_csv(io.StringIO(resp.text))
        if "gb" not in df.columns or "player_id" not in df.columns:
            logger.warning(f"Savant statcast pitcher {season}: expected columns not found")
            return {}
        out = {}
        for _, row in df.iterrows():
            raw_id = row.get("player_id")
            gb_val = row.get("gb")
            if pd.isna(raw_id) or pd.isna(gb_val):
                continue
            try:
                pid   = str(int(float(raw_id)))
                gb    = round(float(gb_val) / 100.0, 4)   # convert 48.3 → 0.483
                out[pid] = gb
            except (ValueError, TypeError):
                continue
        logger.debug(f"Savant statcast pitcher {season}: {len(out)} gb_pct values")
        return out
    except Exception as exc:
        logger.warning(f"Savant statcast pitcher gb_pct {season}: {exc}")
        return {}


# ── Parser ────────────────────────────────────────────────────────────────────

def _normalize_name(raw: str) -> str:
    """
    Savant returns "Last, First" format. Normalize to "First Last".
    Falls back to raw string if no comma found.
    """
    if not isinstance(raw, str):
        return str(raw)
    if "," in raw:
        parts = [p.strip() for p in raw.split(",", 1)]
        return f"{parts[1]} {parts[0]}"
    return raw.strip()


def _parse_pct(val) -> float | None:
    """Convert a percentage value (may be 0-100 or 0-1) to 0-1 scale."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        f = float(val)
        # Savant sometimes returns 0-100, sometimes 0-1
        return round(f / 100.0, 5) if f > 1.5 else round(f, 5)
    except (ValueError, TypeError):
        return None


def _get_col(df: pd.DataFrame, col: str):
    """Safely extract a column series, returning None series if absent."""
    if col in df.columns:
        return df[col]
    # Try case-insensitive match
    match = [c for c in df.columns if c.lower() == col.lower()]
    if match:
        return df[match[0]]
    return None


def _df_to_rows(df: pd.DataFrame, player_type: str, season: int) -> list[dict]:
    """
    Convert a Savant DataFrame to a list of player_savant_stats DB row dicts.
    """
    col_map = PITCHER_COLUMN_MAP if player_type == "pitcher" else BATTER_COLUMN_MAP
    rows = []

    for _, record in df.iterrows():
        # player_id — must have this
        raw_id = record.get("player_id") or record.get("xMLBAMID")
        if raw_id is None or (isinstance(raw_id, float) and pd.isna(raw_id)):
            continue
        player_id = str(int(float(raw_id)))

        # player_name
        raw_name = record.get("player_name") or record.get("last_name, first_name", "")
        player_name = _normalize_name(str(raw_name))

        # team
        team = str(record.get("team_abbrev") or record.get("team", "") or "").strip()
        if not team or team == "nan":
            team = None

        row: dict = {
            "player_id":   player_id,
            "player_name": player_name,
            "team":        team,
            "player_type": player_type,
            "season":      season,
            # All stat columns default to None
            "k_pct": None, "bb_pct": None, "whiff_pct": None,
            "swstr_pct": None, "csw_pct": None, "xera": None,
            "ff_pct": None, "sl_pct": None, "ch_pct": None,
            "cu_pct": None, "si_pct": None, "fc_pct": None,
            "avg_velocity": None, "gb_pct": None,
            "batter_k_pct": None, "batter_bb_pct": None,
            "batting_avg": None, "slg_pct": None, "obp": None,
            "woba": None, "xwoba": None, "xba": None, "xslg": None,
            "barrel_pct": None, "hard_hit_pct": None,
            "launch_angle": None, "exit_velocity": None, "sprint_speed": None,
        }

        # Populate stat columns from column map
        for csv_col, db_col in col_map.items():
            if csv_col in ("player_id", "player_name", "team_abbrev"):
                continue
            val = record.get(csv_col)
            if val is None or (isinstance(val, float) and pd.isna(val)):
                continue

            # Percentage columns — convert to 0-1
            pct_cols = {
                "k_pct", "bb_pct", "whiff_pct", "swstr_pct", "csw_pct",
                "batter_k_pct", "batter_bb_pct",
                "ff_pct", "sl_pct", "ch_pct", "cu_pct", "si_pct", "fc_pct",
                "barrel_pct", "hard_hit_pct", "gb_pct",
            }
            if db_col in pct_cols:
                row[db_col] = _parse_pct(val)
            else:
                try:
                    row[db_col] = round(float(val), 4)
                except (ValueError, TypeError):
                    row[db_col] = None

        rows.append(row)

    return rows


# ── DB Writer ─────────────────────────────────────────────────────────────────

def _upsert_savant_stats(conn: DBConnection, rows: list[dict]) -> int:
    """Upsert player Savant stats. UNIQUE(player_id, season, player_type)."""
    if not rows:
        return 0

    sql = """
        INSERT INTO player_savant_stats (
            player_id, player_name, team, player_type, season,
            k_pct, bb_pct, whiff_pct, swstr_pct, csw_pct, xera,
            ff_pct, sl_pct, ch_pct, cu_pct, si_pct, fc_pct, avg_velocity, gb_pct,
            batter_k_pct, batter_bb_pct, batting_avg, slg_pct, obp,
            woba, xwoba, xba, xslg,
            barrel_pct, hard_hit_pct, launch_angle, exit_velocity, sprint_speed
        ) VALUES (
            %(player_id)s, %(player_name)s, %(team)s, %(player_type)s, %(season)s,
            %(k_pct)s, %(bb_pct)s, %(whiff_pct)s, %(swstr_pct)s, %(csw_pct)s, %(xera)s,
            %(ff_pct)s, %(sl_pct)s, %(ch_pct)s, %(cu_pct)s, %(si_pct)s, %(fc_pct)s, %(avg_velocity)s, %(gb_pct)s,
            %(batter_k_pct)s, %(batter_bb_pct)s, %(batting_avg)s, %(slg_pct)s, %(obp)s,
            %(woba)s, %(xwoba)s, %(xba)s, %(xslg)s,
            %(barrel_pct)s, %(hard_hit_pct)s, %(launch_angle)s, %(exit_velocity)s, %(sprint_speed)s
        )
        ON CONFLICT (player_id, season, player_type) DO UPDATE SET
            player_name  = EXCLUDED.player_name,
            team         = EXCLUDED.team,
            k_pct        = COALESCE(EXCLUDED.k_pct,        player_savant_stats.k_pct),
            bb_pct       = COALESCE(EXCLUDED.bb_pct,       player_savant_stats.bb_pct),
            whiff_pct    = COALESCE(EXCLUDED.whiff_pct,    player_savant_stats.whiff_pct),
            swstr_pct    = COALESCE(EXCLUDED.swstr_pct,    player_savant_stats.swstr_pct),
            csw_pct      = COALESCE(EXCLUDED.csw_pct,      player_savant_stats.csw_pct),
            xera         = COALESCE(EXCLUDED.xera,         player_savant_stats.xera),
            ff_pct       = COALESCE(EXCLUDED.ff_pct,       player_savant_stats.ff_pct),
            sl_pct       = COALESCE(EXCLUDED.sl_pct,       player_savant_stats.sl_pct),
            ch_pct       = COALESCE(EXCLUDED.ch_pct,       player_savant_stats.ch_pct),
            cu_pct       = COALESCE(EXCLUDED.cu_pct,       player_savant_stats.cu_pct),
            si_pct       = COALESCE(EXCLUDED.si_pct,       player_savant_stats.si_pct),
            fc_pct       = COALESCE(EXCLUDED.fc_pct,       player_savant_stats.fc_pct),
            avg_velocity = COALESCE(EXCLUDED.avg_velocity, player_savant_stats.avg_velocity),
            gb_pct       = COALESCE(EXCLUDED.gb_pct,       player_savant_stats.gb_pct),
            batter_k_pct = COALESCE(EXCLUDED.batter_k_pct, player_savant_stats.batter_k_pct),
            batter_bb_pct= COALESCE(EXCLUDED.batter_bb_pct,player_savant_stats.batter_bb_pct),
            batting_avg  = COALESCE(EXCLUDED.batting_avg,  player_savant_stats.batting_avg),
            slg_pct      = COALESCE(EXCLUDED.slg_pct,      player_savant_stats.slg_pct),
            obp          = COALESCE(EXCLUDED.obp,          player_savant_stats.obp),
            woba         = COALESCE(EXCLUDED.woba,         player_savant_stats.woba),
            xwoba        = COALESCE(EXCLUDED.xwoba,        player_savant_stats.xwoba),
            xba          = COALESCE(EXCLUDED.xba,          player_savant_stats.xba),
            xslg         = COALESCE(EXCLUDED.xslg,         player_savant_stats.xslg),
            barrel_pct   = COALESCE(EXCLUDED.barrel_pct,   player_savant_stats.barrel_pct),
            hard_hit_pct = COALESCE(EXCLUDED.hard_hit_pct, player_savant_stats.hard_hit_pct),
            launch_angle = COALESCE(EXCLUDED.launch_angle, player_savant_stats.launch_angle),
            exit_velocity= COALESCE(EXCLUDED.exit_velocity,player_savant_stats.exit_velocity),
            sprint_speed = COALESCE(EXCLUDED.sprint_speed, player_savant_stats.sprint_speed)
    """
    conn.executemany(sql, rows)
    return len(rows)


# ── Main Entry Points ─────────────────────────────────────────────────────────

def run_savant_ingestor(season: int, player_type: str = "both") -> dict:
    """
    Fetch and store Baseball Savant Statcast stats for one season.

    Args:
        season:      MLB season year (e.g. 2025)
        player_type: 'pitcher' | 'batter' | 'both'

    Returns:
        Summary dict.
    """
    types = ["pitcher", "batter"] if player_type == "both" else [player_type]
    start = datetime.now()
    total = 0

    conn = get_connection()
    try:
        for pt in types:
            logger.info(f"Fetching Savant {pt} stats for {season}...")
            df = _fetch_savant_csv(pt, season)
            if df.empty:
                logger.warning(f"No data returned for {pt} {season}")
                continue

            rows = _df_to_rows(df, pt, season)
            if not rows:
                logger.warning(f"No parseable rows for {pt} {season}")
                continue

            # For pitchers: merge in gb_pct from the statcast leaderboard endpoint,
            # which carries groundball% in a column not available in the custom endpoint.
            if pt == "pitcher":
                gb_map = _fetch_pitcher_gb_pct(season)
                if gb_map:
                    for row in rows:
                        if row["player_id"] in gb_map:
                            row["gb_pct"] = gb_map[row["player_id"]]
                    covered = sum(1 for r in rows if r.get("gb_pct") is not None)
                    logger.info(f"  gb_pct coverage: {covered}/{len(rows)} pitchers")

            n = _upsert_savant_stats(conn, rows)
            total += n
            logger.success(f"  {pt} {season}: {n} rows upserted")
            time.sleep(REQUEST_SLEEP)

        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.error(f"Savant ingestor error: {exc}")
        raise
    finally:
        conn.close()

    return {
        "season":       season,
        "player_type":  player_type,
        "rows_upserted": total,
        "duration_s":   (datetime.now() - start).total_seconds(),
    }


def backfill_savant_stats(start_season: int, end_season: int,
                          player_type: str = "both") -> None:
    """
    Backfill Savant stats for a range of seasons. Idempotent.

    Usage:
        python -m data.ingestors.baseball_savant_ingestor --backfill 2019 2025
    """
    for season in range(start_season, end_season + 1):
        logger.info(f"── Backfill season {season} ──")
        try:
            result = run_savant_ingestor(season, player_type)
            logger.info(f"Season {season}: {result['rows_upserted']} rows")
        except Exception as exc:
            logger.error(f"Season {season} failed: {exc} — continuing")
        time.sleep(REQUEST_SLEEP)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fetch Baseball Savant Statcast leaderboard stats"
    )
    parser.add_argument("--season",   type=int, metavar="YYYY",
                        help="Single season to fetch")
    parser.add_argument("--backfill", nargs=2, type=int, metavar=("START", "END"),
                        help="Backfill season range (inclusive)")
    parser.add_argument("--type",     default="both",
                        choices=["pitcher", "batter", "both"],
                        help="Player type to fetch (default: both)")
    args = parser.parse_args()

    if args.backfill:
        backfill_savant_stats(args.backfill[0], args.backfill[1], args.type)
    elif args.season:
        result = run_savant_ingestor(args.season, args.type)
        logger.info(f"Done: {result}")
    else:
        parser.error("Provide --season YYYY or --backfill START END")
