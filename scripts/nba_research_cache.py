"""Cache the NBA research tables from Supabase to data/local/ (a cache, never a source).

Every NBA research script reads the same few million rows -- game lines,
player props, box scores, the injury report. Supabase is the one database the
live scorer also runs on, and repeated heavy reads have degraded it before
(docs/sessions/2026-10.md), so the rows are read ONCE, by indexed key, and the
grids run against the parquet copy. Re-run to refresh; nothing here is the
system of record (CLAUDE.md §1b: a local file is a cache of Supabase).

    python -m scripts.nba_research_cache            # everything
    python -m scripts.nba_research_cache --only props
"""
from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import pandas as pd
from loguru import logger

# Its own folder, ignored by git: the committed data/local cache is ~5 MB on
# purpose, and this one is millions of price rows.
os.environ.setdefault("BETTING_LOCAL_CACHE_DIR",
                      str(Path(__file__).resolve().parent.parent / "data" / "local" / "nba"))

from data import local_store  # noqa: E402  (reads the env var at import)
from data.db import get_connection

SEASONS = list(range(2019, 2028))


def _frame(conn, sql: str, params=()) -> pd.DataFrame:
    cur = conn.execute(sql, params)
    rows = cur.fetchall()
    raw = getattr(cur, "_cur", cur)          # data.db wraps the psycopg2 cursor
    cols = [d[0] for d in raw.description]
    return pd.DataFrame(rows, columns=cols)


def _table_exists(conn, name: str) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s",
        (name,)).fetchone())


def cache_games(conn) -> pd.DataFrame:
    g = _frame(conn, "SELECT * FROM games WHERE sport = 'NBA'")
    local_store.write_table("nba_games", g, SEASONS)
    if _table_exists(conn, "nba_schedule"):
        local_store.write_table("nba_schedule", _frame(conn, "SELECT * FROM nba_schedule"), SEASONS)
    logger.info(f"games {len(g):,}")
    return g


def _by_game_ids(conn, sql: str, ids: list[str], chunk: int = 150) -> pd.DataFrame:
    parts = []
    for i in range(0, len(ids), chunk):
        parts.append(_frame(conn, sql, (ids[i:i + chunk],)))
        if i and i % (chunk * 20) == 0:
            logger.info(f"  {i:,}/{len(ids):,} games")
        time.sleep(0.05)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def cache_lines(conn, games: pd.DataFrame) -> None:
    ids = games.loc[games["game_date"] >= "2020-12-01", "game_id"].tolist()
    df = _by_game_ids(conn, """
        SELECT game_id, market, bookmaker, snapshot_type, snapshot_at, source, created_at,
               home_price, away_price, spread_home, total_line, over_price, under_price
          FROM odds WHERE game_id = ANY(%s)
    """, ids)
    local_store.write_table("nba_odds", df, SEASONS)
    logger.info(f"odds {len(df):,}")
    # When each stored fetch was ASKED FOR. A quote's snapshot_at is the book's
    # last update, minutes before the fetch, so it cannot place a fetch in a
    # decision window; the ledgers can. Rows join their fetch on created_at =
    # pulled_at (one transaction writes both). docs/nba_models_2026.md §6.5.
    parts = [_frame(conn, """
        SELECT (snapshot_date || 'T' || lpad(hour_utc::text, 2, '0') || ':00:00+00')::timestamptz
                   AS requested_at, pulled_at, rows, 'hourly' AS why
          FROM odds_history_pulls WHERE sport = 'NBA'
    """)]
    if _table_exists(conn, "odds_history_fetches"):
        parts.append(_frame(conn, """
            SELECT requested_at, pulled_at, rows, why
              FROM odds_history_fetches WHERE sport = 'NBA'
        """))
    led = pd.concat(parts, ignore_index=True)
    local_store.write_table("nba_fetch_ledger", led, SEASONS)
    logger.info(f"fetch ledger {len(led):,}")


def cache_props(conn, games: pd.DataFrame) -> None:
    ids = games.loc[games["game_date"] >= "2023-05-01", "game_id"].tolist()
    df = _by_game_ids(conn, """
        SELECT game_id, game_date, player_name, market, bookmaker, snapshot_type,
               snapshot_at, created_at, line, over_price, under_price
          FROM player_prop_odds WHERE game_id = ANY(%s)
    """, ids, chunk=60)
    local_store.write_table("nba_props", df, SEASONS)
    logger.info(f"props {len(df):,}")


def cache_box(conn) -> None:
    for t in ("nba_player_game_log", "nba_player_game_adv", "nba_game_inactives",
              "nba_game_officials", "nba_injury_report", "nba_period_scores",
              "nba_player_dnp", "player_positions"):
        if not _table_exists(conn, t):
            logger.warning(f"{t}: not in the database yet")
            continue
        where = " WHERE sport = 'NBA'" if t == "player_positions" else ""
        df = _frame(conn, f"SELECT * FROM {t}{where}")
        local_store.write_table(t, df, SEASONS)
        logger.info(f"{t} {len(df):,}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", choices=["games", "lines", "props", "box"])
    a = ap.parse_args()
    conn = get_connection()
    try:
        games = cache_games(conn)
        if a.only in (None, "lines"):
            cache_lines(conn, games)
        if a.only in (None, "props"):
            cache_props(conn, games)
        if a.only in (None, "box"):
            cache_box(conn)
        print(local_store.status())
    finally:
        conn.close()


if __name__ == "__main__":
    main()
