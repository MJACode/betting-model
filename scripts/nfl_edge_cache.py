"""
Build the read-only local cache the NFL edge search (docs/nfl_edge_search.md)
runs on. Zero Odds API credits: everything here is already stored in Supabase
or is free public nflverse data.

    python -m scripts.nfl_edge_cache                 # everything
    python -m scripts.nfl_edge_cache --only odds_hist props_2026

Output goes to $NFL_EDGE_CACHE (default %TEMP%/nfl_edge), OUTSIDE the repo.
Every file is a cache of Supabase or of nflverse and is regenerable by
re-running this script, so nothing here is a store of record
(CLAUDE.md 1b, "everything goes in Supabase").

Production-safety: one database, shared with live scoring. Every read goes
through an index (season/week, game_id/market, game_id/... snapshot) in
chunks, one statement at a time, never a full-table scan of player_prop_odds
(24 GB) or nfl_odds_history (15.5M rows).
"""
from __future__ import annotations

import argparse
import io
import os
import shutil
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CACHE = Path(os.environ.get("NFL_EDGE_CACHE",
                            Path(os.environ.get("TEMP", "/tmp")) / "nfl_edge"))
MAIN_CHECKOUT_LOCAL = Path(os.environ.get(
    "BETTING_MAIN_LOCAL", Path.home() / "Documents" / "betting-model" / "data" / "local"))
MAIN_CHECKOUT_PBP = MAIN_CHECKOUT_LOCAL.parent.parent / "nfl" / "data" / "pbp"

NFLVERSE = "https://github.com/nflverse/nflverse-data/releases/download"
PBP_SEASONS = list(range(2016, 2027))

# Books pulled for the 2026 per-minute game-line archive. The sharp references,
# the books config.BETTABLE_BOOKS can bet, and the two offshore sharp-ish ones.
BOOKS_2026 = ["pinnacle", "draftkings", "fanduel", "betmgm", "williamhill_us",
              "fanatics", "betrivers", "espnbet", "bovada", "betonlineag",
              "lowvig", "betus", "mybookieag"]

# Leads (hours before kickoff) at which the 2026 prop board is snapshotted.
PROP_LEADS_H = [72, 48, 24, 12, 6, 3, 1.5, 0.75, 0.0]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _conn():
    """A raw psycopg2 connection, READ ONLY, with a statement timeout.
    The data.db wrapper rewrites ':name' as a bind parameter, which would
    mangle the '::timestamptz' casts below, so it is bypassed."""
    import psycopg2
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    # keepalives + a socket-level timeout: a pooler that silently drops the
    # connection must surface as an error, not hang the pull (it did, 2026-10-11).
    conn = psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=30,
                            keepalives=1, keepalives_idle=30,
                            keepalives_interval=10, keepalives_count=3,
                            options="-c statement_timeout=120000")
    conn.set_session(readonly=True, autocommit=True)
    with conn.cursor() as cur:
        cur.execute("SET statement_timeout = '120s'")
    return conn


_STATE: dict = {}


def _df(conn, sql: str, params=None) -> pd.DataFrame:
    conn = _STATE.get("conn", conn)
    for attempt in range(3):
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params or None)
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description] if cur.description else []
            return pd.DataFrame(rows, columns=cols)
        except Exception as exc:  # noqa: BLE001
            log(f"  query failed (attempt {attempt+1}): {str(exc)[:160]}")
            time.sleep(5 * (attempt + 1))
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
            conn = _conn()
            _STATE["conn"] = conn
    raise RuntimeError("query failed 3 times")


def _write(df: pd.DataFrame, name: str) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"{name}.parquet"
    df.to_parquet(p, index=False)
    log(f"  wrote {name}: {len(df):,} rows, {p.stat().st_size/1e6:.1f} MB")


# ─── free public data ───────────────────────────────────────────────────────

def nflverse_schedules() -> None:
    log("nflverse schedules")
    r = requests.get(f"{NFLVERSE}/schedules/games.csv", timeout=120)
    r.raise_for_status()
    _write(pd.read_csv(io.BytesIO(r.content), low_memory=False), "nflverse_games")


def nflverse_pbp() -> None:
    for s in PBP_SEASONS:
        out = CACHE / f"pbp_{s}.parquet"
        if out.exists() and s < 2026:
            log(f"pbp {s}: cached")
            continue
        local = MAIN_CHECKOUT_PBP / f"play_by_play_{s}.parquet"
        if local.exists() and s < 2026:
            shutil.copy(local, out)
            log(f"pbp {s}: copied from main checkout")
            continue
        log(f"pbp {s}: downloading")
        r = requests.get(f"{NFLVERSE}/pbp/play_by_play_{s}.parquet", timeout=600)
        r.raise_for_status()
        CACHE.mkdir(parents=True, exist_ok=True)
        out.write_bytes(r.content)
        log(f"  pbp {s}: {len(r.content)/1e6:.1f} MB")


def nflverse_misc() -> None:
    """Injuries, officials, depth charts: free, small, used for situational tests."""
    for name, url in [
        ("nflverse_officials", f"{NFLVERSE}/officials/officials.parquet"),
        ("nflverse_injuries_2023", f"{NFLVERSE}/injuries/injuries_2023.parquet"),
        ("nflverse_injuries_2024", f"{NFLVERSE}/injuries/injuries_2024.parquet"),
        ("nflverse_injuries_2025", f"{NFLVERSE}/injuries/injuries_2025.parquet"),
    ]:
        try:
            r = requests.get(url, timeout=300)
            r.raise_for_status()
            (CACHE / f"{name}.parquet").write_bytes(r.content)
            log(f"  {name}: {len(r.content)/1e6:.1f} MB")
        except Exception as exc:  # noqa: BLE001
            log(f"  {name}: FAILED {exc}")


def copy_main_local() -> None:
    """The prop-odds parquet in the main checkout holds 2023-25 history the
    database has pruned (scripts/pull_local_cache._merge_with_cache)."""
    for f in ["nfl_player_game_log", "nfl_prop_odds", "nfl_snap_counts",
              "nfl_team_game_stats"]:
        src = MAIN_CHECKOUT_LOCAL / f"{f}.parquet"
        if src.exists():
            shutil.copy(src, CACHE / f"local_{f}.parquet")
            log(f"copied {f} ({src.stat().st_size/1e6:.1f} MB)")
        else:
            log(f"MISSING {src}")


# ─── Supabase reads ─────────────────────────────────────────────────────────

def odds_hist(conn) -> None:
    """nfl_odds_history 2020-2025, chunked on the (season, week) index."""
    frames = []
    for season in range(2020, 2026):
        for week in range(0, 23):
            df = _df(conn, """SELECT * FROM nfl_odds_history
                              WHERE season = %s AND week = %s""", (season, week))
            if len(df):
                frames.append(df)
        log(f"odds_hist {season}: {sum(len(f) for f in frames if f['season'].iat[0]==season):,}")
    _write(pd.concat(frames, ignore_index=True), "odds_hist_2020_2025")


def _games_2026() -> pd.DataFrame:
    g = pd.read_parquet(CACHE / "nflverse_games.parquet")
    g = g[g["season"] == 2026].copy()
    g["kick"] = pd.to_datetime(g["gameday"] + " " + g["gametime"]).dt.tz_localize(
        "America/New_York").dt.tz_convert("UTC")
    return g


def odds_2026(conn) -> None:
    """2026 game-line archive (per-minute, pre-game AND in-play) for BOOKS_2026,
    on the (game_id, market) index, games that have kicked off or kick within 8 days."""
    g = _games_2026()
    now = pd.Timestamp.now(tz="UTC")
    g = g[g["kick"] <= now + pd.Timedelta(days=8)]
    frames = []
    for i, gid in enumerate(g["game_id"]):
        # 2026 rows are keyed NFL_<nflverse id> (the card's ids); 2020-25 use the bare id.
        df = _df(conn, """SELECT snapshot_at, game_id, commence_time, bookmaker,
                                 market, point, price_home, price_away
                          FROM nfl_odds_history
                          WHERE game_id = %s AND bookmaker = ANY(%s)""",
                 (f"NFL_{gid}", BOOKS_2026))
        if len(df):
            frames.append(df)
        log(f"odds_2026 {i+1}/{len(g)} {gid}: {len(df):,}; total {sum(len(f) for f in frames):,}")
    _write(pd.concat(frames, ignore_index=True), "odds_2026")


def props_2026(conn) -> None:
    """2026 prop board since the local parquet's 2026-09-09 pull.

    For every (market, player, book, line) and every lead L in PROP_LEADS_H,
    the latest PRE-GAME quote at or before kickoff - L hours. One sort per game
    (through idx_prop_odds_line_snap): each row is labelled with the largest
    cutoff <= its lead, and the latest row per label is kept. The latest quote
    at or before cutoff L is then the row of the smallest label >= L, which the
    reader forward-fills (`lead_label`). Exact, not an approximation.
    A second statement keeps the first quote ever seen (lead_label = -1)."""
    g = _games_2026()
    now = pd.Timestamp.now(tz="UTC")
    g = g[g["kick"] <= now]
    cuts = sorted(PROP_LEADS_H, reverse=True)
    case = " ".join(f"WHEN lead_h >= {c} THEN {c}" for c in cuts)
    parts = CACHE / "props_2026_parts"
    parts.mkdir(parents=True, exist_ok=True)
    frames = []
    for i, row in enumerate(g.itertuples()):
        pid = f"NFL_{row.game_id}"
        part = parts / f"{pid}.parquet"
        if part.exists():
            frames.append(pd.read_parquet(part))
            continue
        kick = row.kick.isoformat()
        df = _df(conn, f"""
            SELECT DISTINCT ON (market, player_name, bookmaker, line, lead_label)
                   game_id, game_date, player_name, team, market, bookmaker, line,
                   over_price, under_price, snapshot_at, lead_h, lead_label
            FROM (SELECT *, CASE {case} END AS lead_label FROM (
                    SELECT game_id, game_date, player_name, team, market, bookmaker,
                           line, over_price, under_price, snapshot_at,
                           EXTRACT(EPOCH FROM (%s::timestamptz - snapshot_at::timestamptz))/3600.0 AS lead_h
                    FROM player_prop_odds WHERE game_id = %s) a
                  WHERE lead_h >= 0) b
            ORDER BY market, player_name, bookmaker, line, lead_label, snapshot_at DESC
        """, (kick, pid))
        df2 = _df(conn, """
            SELECT DISTINCT ON (market, player_name, bookmaker, line)
                   game_id, game_date, player_name, team, market, bookmaker, line,
                   over_price, under_price, snapshot_at
            FROM player_prop_odds WHERE game_id = %s
            ORDER BY market, player_name, bookmaker, line, snapshot_at ASC
        """, (pid,))
        if len(df2):
            df2["lead_label"] = -1.0
        game_frames = []
        for d in (df, df2):
            if len(d):
                d["kick"] = row.kick
                game_frames.append(d)
        if game_frames:
            gf = pd.concat(game_frames, ignore_index=True)
            # Postgres numerics arrive as Decimal; parquet needs one type per column.
            for c in ("line", "over_price", "under_price", "lead_h", "lead_label"):
                if c in gf:
                    gf[c] = pd.to_numeric(gf[c], errors="coerce").astype(float)
            gf.to_parquet(part, index=False)
            frames.append(gf)
        log(f"props_2026 {i+1}/{len(g)} {pid}: {len(df):,}+{len(df2):,}; total {sum(len(f) for f in frames):,}")
    _write(pd.concat(frames, ignore_index=True), "props_2026")


def small_tables(conn) -> None:
    jobs = {
        "player_game_log_2025_2026": ("SELECT * FROM nfl_player_game_log WHERE season >= %s", (2025,)),
        "team_game_stats": ("SELECT * FROM nfl_team_game_stats", ()),
        "stadium_weather_hourly": ("SELECT * FROM nfl_stadium_weather_hourly", ()),
        "game_weather_issued_nfl": ("SELECT * FROM game_weather_issued WHERE game_id LIKE %s", ("NFL%",)),
        "game_weather_nfl": ("SELECT * FROM game_weather WHERE game_id LIKE %s", ("NFL%",)),
        "injuries_nfl": ("SELECT * FROM injuries WHERE sport = %s", ("NFL",)),
        "player_news_nfl": ("SELECT * FROM player_news WHERE sport = %s", ("NFL",)),
        "picks_nfl": ("SELECT * FROM picks WHERE model_id LIKE %s", ("nfl%",)),
        "opening_signals_nfl": ("SELECT * FROM opening_signals WHERE model_id LIKE %s", ("nfl%",)),
        "nfl_live_prop_snapshots": ("SELECT * FROM nfl_live_prop_snapshots", ()),
        "nfl_pick_status_history": ("SELECT * FROM nfl_pick_status_history", ()),
    }
    for name, (sql, params) in jobs.items():
        try:
            _write(_df(conn, sql, params), name)
        except Exception as exc:  # noqa: BLE001
            log(f"  {name}: FAILED {exc}")


STEPS = ["schedules", "pbp", "misc", "copy", "small", "odds_hist", "odds_2026", "props_2026"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="+", choices=STEPS)
    args = ap.parse_args()
    steps = args.only or STEPS
    CACHE.mkdir(parents=True, exist_ok=True)
    log(f"cache -> {CACHE}")
    if "schedules" in steps:
        nflverse_schedules()
    if "pbp" in steps:
        nflverse_pbp()
    if "misc" in steps:
        nflverse_misc()
    if "copy" in steps:
        copy_main_local()
    db_steps = [s for s in steps if s in ("small", "odds_hist", "odds_2026", "props_2026")]
    if db_steps:
        conn = _conn()
        try:
            if "small" in db_steps:
                small_tables(conn)
            if "odds_hist" in db_steps:
                odds_hist(conn)
            if "odds_2026" in db_steps:
                odds_2026(conn)
            if "props_2026" in db_steps:
                props_2026(conn)
        finally:
            conn.close()
    log("done")


if __name__ == "__main__":
    main()
