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
           over_price, under_price, bookmaker, snapshot_at, snapshot_type
    FROM player_prop_odds
    WHERE game_id LIKE 'NFL%%'
"""
_ODDS_COLS = ["game_id", "game_date", "player_name", "market", "line",
              "over_price", "under_price", "bookmaker", "snapshot_at",
              "snapshot_type"]


def _pull_seasoned(conn, table: str, seasons: list[int]) -> pd.DataFrame:
    sql, cols, _ = _TABLES[table]
    frames = []
    for s in seasons:
        rows = conn.execute(sql, ([s],)).fetchall()
        if rows:
            frames.append(pd.DataFrame(rows, columns=cols))
        logger.info(f"  {table} {s}: {len(rows):,} rows")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=cols)


# The natural key of a prop quote. Two rows agreeing on all of it are the same
# observation pulled twice.
_ODDS_KEY = ["game_id", "player_name", "market", "line", "over_price",
             "under_price", "bookmaker", "snapshot_at", "snapshot_type"]


def _merge_with_cache(df: pd.DataFrame) -> pd.DataFrame:
    """UNION with whatever the cache already holds. Never replace it.

    THE CACHE OUTLIVES THE DATABASE, which is the opposite of what a cache is
    supposed to do and is exactly why this function exists. `player_prop_odds`
    is pruned: on 2026-09-08 it held no NFL sharp prop snapshot older than
    2026-04-01, while the tracked parquet held 117,048 of them going back to
    2023 -- the entire history the market-relative rule is validated on.

    A plain refresh therefore DELETED the evidence. The rule re-graded at -2.81%
    on the replacement board and the drop was pure artefact: every 2025 sharp
    quote had gone. Nobody would have questioned a negative number, which is
    what makes this the expensive kind of wrong.

    So the pull is now additive. Rows the database has lost stay; rows it has
    gained arrive; a row present in both is kept once. The pruner-side fix is in
    data/prune_odds._prop_reference_books, and both are needed -- that one stops
    new history being deleted, this one stops old history being overwritten.
    """
    # READ THE FILE, not local_store.read_table. read_table returns None unless
    # the cache has been activate()d, and this entry point never activates it --
    # so routing the merge through it would have made this function a silent
    # no-op that still logged success. That is the same failure the rest of this
    # docstring is about, one layer down.
    path = local_store._path("nfl_prop_odds")
    if not path.exists():
        return df
    try:
        old = pd.read_parquet(path)
    except Exception as exc:                            # noqa: BLE001
        # Never let an unreadable cache silently discard history: stop instead.
        raise RuntimeError(
            f"cannot read the existing cache at {path} ({exc}). Refusing to "
            f"overwrite it -- it may hold rows the database no longer has."
        ) from exc
    if old.empty:
        return df
    before = len(old)
    merged = pd.concat([old.drop(columns=["season"], errors="ignore"),
                        df.drop(columns=["season"], errors="ignore")],
                       ignore_index=True)
    merged = merged.drop_duplicates(subset=_ODDS_KEY)
    kept = len(merged) - len(df.drop_duplicates(subset=_ODDS_KEY))
    logger.info(f"  merged with cache: {before:,} cached + {len(df):,} pulled "
                f"-> {len(merged):,} ({max(kept, 0):,} rows the DB no longer has)")
    return merged


def _pull_odds(conn) -> pd.DataFrame:
    rows = conn.execute(_ODDS_SQL).fetchall()
    df = pd.DataFrame(rows, columns=_ODDS_COLS)
    logger.info(f"  nfl_prop_odds: {len(df):,} rows")
    df = _merge_with_cache(df)
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
