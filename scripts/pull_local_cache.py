"""
Pull the NFL-prop modelling tables from Supabase to a local cache, once.

    python -m scripts.pull_local_cache                  # all tables, 2015-2026
    python -m scripts.pull_local_cache --seasons 2015 2026
    python -m scripts.pull_local_cache --tables nfl_prop_odds
    python -m scripts.pull_local_cache --status

Needs DATABASE_URL (your .env already has it). After this, the backtest and the
trainer read from disk and never touch the network, so a threshold sweep or a
feature experiment runs in seconds instead of minutes.

Reads are chunked by season. A season of player rows is ~17k and comfortably
inside Supabase's statement timeout; the whole table in one SELECT is not
guaranteed to be (the same limit that forced chunked writes in the ingestor).
"""
from __future__ import annotations

import argparse

import pandas as pd

try:
    from loguru import logger
except ImportError:                                        # pragma: no cover
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

from data import local_store
from data.db import get_connection

# table -> (SQL with a %s season filter, column names, needs season chunking)
_TABLES: dict[str, tuple[str, list[str], bool]] = {}


def _register_from_feature_engine() -> None:
    """Source the SQL from the feature engine so the two can never diverge."""
    from features import nfl_prop_feature_engine as fe
    _TABLES["nfl_player_game_log"] = (fe._PLAYER_SQL, fe._PLAYER_COLS, True)
    _TABLES["nfl_team_game_stats"] = (fe._TEAM_SQL, fe._TEAM_COLS, True)
    _TABLES["nfl_snap_counts"] = (fe._SNAP_SQL, fe._SNAP_COLS, True)


_ODDS_SQL = """
    SELECT game_id, game_date, player_name, market, line,
           over_price, under_price, bookmaker, snapshot_at
    FROM player_prop_odds
    WHERE game_id LIKE 'NFL%%'
"""
_ODDS_COLS = ["game_id", "game_date", "player_name", "market", "line",
              "over_price", "under_price", "bookmaker", "snapshot_at"]


def _pull_seasoned(conn, table: str, seasons: list[int]) -> pd.DataFrame:
    sql, cols, _ = _TABLES[table]
    frames = []
    for s in seasons:
        rows = conn.execute(sql, ([s],)).fetchall()
        if rows:
            frames.append(pd.DataFrame(rows, columns=cols))
        logger.info(f"  {table} {s}: {len(rows):,} rows")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=cols)


def _pull_odds(conn) -> pd.DataFrame:
    rows = conn.execute(_ODDS_SQL).fetchall()
    df = pd.DataFrame(rows, columns=_ODDS_COLS)
    logger.info(f"  nfl_prop_odds: {len(df):,} rows")
    # `season` lets read_table honour a season filter like the other tables.
    if not df.empty:
        gd = pd.to_datetime(df["game_date"], errors="coerce")
        # NFL season label is the year the season STARTS: Jan/Feb belong to the
        # prior label. Same rule as the ingestor — never derive it from the raw year.
        df["season"] = (gd.dt.year - (gd.dt.month <= 2).astype(int)).astype("Int64")
    return df


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seasons", nargs=2, type=int, metavar=("START", "END"),
                    default=[2015, 2026])
    ap.add_argument("--tables", nargs="+",
                    help="subset to refresh (default: all)")
    ap.add_argument("--status", action="store_true", help="show the cache and exit")
    args = ap.parse_args()

    if args.status:
        print(local_store.status())
        return

    _register_from_feature_engine()
    seasons = list(range(args.seasons[0], args.seasons[1] + 1))
    wanted = args.tables or [*_TABLES, "nfl_prop_odds"]

    conn = get_connection()
    try:
        for table in wanted:
            logger.info(f"pulling {table} ...")
            if table == "nfl_prop_odds":
                df = _pull_odds(conn)
                sea = sorted(int(s) for s in df["season"].dropna().unique()) if not df.empty else []
            elif table in _TABLES:
                df = _pull_seasoned(conn, table, seasons)
                sea = seasons
            else:
                logger.warning(f"unknown table '{table}' — skipping")
                continue
            path = local_store.write_table(table, df, sea)
            logger.success(f"{table}: {len(df):,} rows -> {path} "
                           f"({path.stat().st_size/1e6:.1f} MB)")
    finally:
        conn.close()

    print()
    print(local_store.status())
    print("\nThe backtest now runs offline:")
    print("  python -m models.nfl_prop_backtest --all --seasons 2024 2025")


if __name__ == "__main__":
    main()
