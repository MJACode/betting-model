"""
Pull CFBD play-by-play into per-season parquet files AND/OR Supabase.

    python -m ncaaf_live.backtest.pull_pbp                # all seasons -> parquet
    python -m ncaaf_live.backtest.pull_pbp --seasons 2025
    python -m ncaaf_live.backtest.pull_pbp --seasons 2025 --to-db   # + Supabase

THE PARQUET IS A CACHE; SUPABASE IS THE COPY THAT SURVIVES A MACHINE. PBP_DIR
is gitignored, so a season pulled here exists on exactly one laptop -- and the
laptop that needs it for the 2025 in-play replay does not hold CFBD_API_KEY
(it is a Railway variable; the connector redacts values and there is no CLI
here). `--to-db` is what lets the WORKER fetch, with the key it already has,
and any machine build states from the result. CLAUDE.md section 1b.

/plays is week-scoped, so a season is ~15 regular weeks + postseason weeks.
Free (CFBD key), idempotent per season file, ~165 calls for the full history.

The columns are kept RAW here - offense/defense relative, clock as a dict -
and every transformation into home/away state lives in states.py, so there is
exactly one place the tricky relabelling can be wrong.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ncaaf_live.config import (  # noqa: E402
    ALL_SEASONS, CFBD_API_KEY, CFBD_BASE_URL, CFBD_REQUEST_PAUSE, PBP_DIR)

KEEP = [
    "id", "gameId", "driveId", "playNumber", "period", "clock",
    "offense", "defense", "home", "away",
    "offenseScore", "defenseScore", "offenseTimeouts", "defenseTimeouts",
    "down", "distance", "yardsToGoal", "yardsGained",
    "playType", "scoring", "wallclock",
]


def _get(path: str, **params) -> list | None:
    if not CFBD_API_KEY:
        raise RuntimeError("CFBD_API_KEY is not set")
    for attempt in range(3):
        try:
            r = requests.get(
                f"{CFBD_BASE_URL}{path}", params=params,
                headers={"Authorization": f"Bearer {CFBD_API_KEY}"}, timeout=120)
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            time.sleep(CFBD_REQUEST_PAUSE)
            return r.json()
        except Exception as exc:                       # noqa: BLE001
            if attempt == 2:
                print(f"  WARN {path} {params}: {exc}")
                return None
            time.sleep(3 * (attempt + 1))
    return None


# `states.py` consumes the CFBD spelling; the table stores snake_case. One
# map, both directions, so the rename cannot drift into two spellings.
DB_COLUMNS = {
    "id": "play_id", "gameId": "game_id_cfbd", "driveId": "drive_id",
    "playNumber": "play_number", "period": "period",
    "clock_minutes": "clock_minutes", "clock_seconds": "clock_seconds",
    "offense": "offense", "defense": "defense", "home": "home", "away": "away",
    "offenseScore": "offense_score", "defenseScore": "defense_score",
    "offenseTimeouts": "offense_timeouts", "defenseTimeouts": "defense_timeouts",
    "down": "down", "distance": "distance", "yardsToGoal": "yards_to_goal",
    "yardsGained": "yards_gained", "playType": "play_type",
    "scoring": "scoring", "wallclock": "wallclock", "season": "season",
    "week": "week", "season_type": "season_type",
}
DB_TO_CFBD = {v: k for k, v in DB_COLUMNS.items()}


def fetch_season(season: int):
    """Every play of a season from CFBD, RAW, as a DataFrame. No file IO."""
    frames = []
    for stype, weeks in (("regular", range(1, 17)), ("postseason", range(1, 3))):
        for wk in weeks:
            payload = _get("/plays", year=season, week=wk, seasonType=stype)
            if not payload:
                continue
            df = pd.DataFrame(payload)
            cols = [c for c in KEEP if c in df.columns]
            df = df[cols].copy()
            # flatten the {minutes, seconds} clock at pull time - it is the
            # one nested field, and parquet stores it poorly as a dict
            if "clock" in df.columns:
                cl = df["clock"].apply(
                    lambda c: (c or {}).get("minutes"), )
                cs = df["clock"].apply(
                    lambda c: (c or {}).get("seconds"), )
                df["clock_minutes"] = pd.to_numeric(cl, errors="coerce")
                df["clock_seconds"] = pd.to_numeric(cs, errors="coerce")
                df = df.drop(columns=["clock"])
            df["season"] = season
            df["week"] = wk
            df["season_type"] = stype
            frames.append(df)

    if not frames:
        print(f"{season}: NO plays returned")
        return None
    return pd.concat(frames, ignore_index=True)


def pull_season(season: int, force: bool = False) -> Path | None:
    out = PBP_DIR / f"plays_{season}.parquet"
    if out.exists() and not force:
        print(f"{season}: exists ({out.stat().st_size // 1024} KB), skipping")
        return out
    full = fetch_season(season)
    if full is None:
        return None
    full.to_parquet(out)
    print(f"{season}: {len(full):,} plays, "
          f"{full['gameId'].nunique():,} games -> {out.name}")
    return out


# Postgres does not name the column in `integer out of range` / `bigint out of
# range`. Attempt 1 of the ncaaf_pbp_pull job (2026-09-12) failed the first way,
# the columns were widened to BIGINT, and attempt 2 failed the second way — so
# some value CFBD serves genuinely exceeds 2^63, and neither traceback said
# which.
#
# WHAT IS NOT KNOWN YET, STATED PLAINLY: attempt 2 ran WITH a pre-insert range
# check and that check PASSED, then Postgres refused the row anyway. The
# obvious explanation — that `pd.to_numeric(..., errors="coerce")` NaN-drops a
# value too large to represent, so the check skipped it — was tested against a
# 2**70 object column and is FALSE: to_numeric returns 1.18e21 there and the
# check would have caught it. So the reason the check passed is still open, and
# no comment here should pretend otherwise.
#
# What changed on the evidence actually in hand:
#   * the columns are NUMERIC (data/migrations/ncaaf_plays_numeric_not_bigint),
#     which has no ceiling. That ends a sequence of guesses at the right width
#     rather than adding a third.
#   * the scan below walks the RAW objects with Python's int(), which has no
#     ceiling and no coercion step, instead of routing through to_numeric. Not
#     because to_numeric was proven wrong, but because the raw walk has strictly
#     fewer ways to be wrong on the exact question being asked.
#   * it REPORTS instead of raising, and store_season returns the observed
#     min/max per column in the job result — which is how the actual value gets
#     identified, since guessing at it has now cost two deploy cycles.
NUMERIC_COLUMNS = (
    "play_number", "period", "clock_minutes", "clock_seconds",
    "offense_score", "defense_score", "offense_timeouts", "defense_timeouts",
    "down", "distance", "yards_to_goal", "yards_gained", "season", "week",
)
BIGINT_MAX = 2 ** 63 - 1


def _extremes(series):
    """(min, max) as PYTHON ints over the raw objects.

    Deliberately not `pd.to_numeric`: its `errors="coerce"` maps an
    unrepresentable integer to NaN, and `errors="raise"` would abort the scan on
    the first non-numeric cell. int() on each object has neither problem and no
    ceiling.
    """
    lo = hi = None
    for v in series:
        if v is None:
            continue
        try:
            if v != v:                                   # NaN, without numpy
                continue
        except (TypeError, ValueError):
            pass
        try:
            i = int(v)
        except (TypeError, ValueError, OverflowError):
            continue
        lo = i if lo is None else min(lo, i)
        hi = i if hi is None else max(hi, i)
    return lo, hi


def observed_ranges(out) -> dict:
    """min/max per numeric column, for the job result."""
    got = {}
    for col in NUMERIC_COLUMNS:
        if col in out.columns:
            lo, hi = _extremes(out[col])
            if lo is not None:
                got[col] = [lo, hi]
    return got


def _report_ranges(out, season: int) -> dict:
    """Log any column carrying a value past BIGINT, naming it and a play."""
    ranges = observed_ranges(out)
    for col, (lo, hi) in ranges.items():
        if hi > BIGINT_MAX or lo < -BIGINT_MAX:
            worst = max(out[col], key=lambda v: abs(int(v))
                        if isinstance(v, (int, float)) and v == v else -1)
            print(f"  WARN {season}: {col} carries {worst!r} "
                  f"(min {lo}, max {hi}) — past bigint; stored as NUMERIC")
    return ranges


def store_season(conn, season: int, df=None) -> dict:
    """Upsert a season's plays into `ncaaf_plays`.

    Idempotent on CFBD's own play id, so a re-run after a partial write costs
    CFBD calls but never duplicates a play -- which matters because the dedupe
    key downstream IS that id (states.py drops duplicates on (gameId, id)).
    """
    if df is None:
        df = fetch_season(season)
    if df is None or df.empty:
        return {"season": season, "plays": 0, "games": 0}

    cols = [c for c in DB_COLUMNS if c in df.columns]
    out = df[cols].rename(columns=DB_COLUMNS)
    out = out[out["play_id"].notna()]
    # One row per play id. CFBD has served the same play twice across a week
    # boundary before; executemany would raise on the second.
    out = out.drop_duplicates(subset=["play_id"], keep="first")
    for c in ("play_id", "game_id_cfbd", "drive_id"):
        if c in out.columns:
            out[c] = out[c].astype(str)
    ranges = _report_ranges(out, season)
    names = list(out.columns)
    placeholders = ", ".join(f"%({c})s" for c in names)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in names if c != "play_id")
    sql = (f"INSERT INTO ncaaf_plays ({', '.join(names)}) "
           f"VALUES ({placeholders}) "
           f"ON CONFLICT (play_id) DO UPDATE SET {updates}")
    rows = out.where(pd.notna(out), None).to_dict("records")
    conn.executemany(sql, rows)
    conn.commit()
    return {"season": season, "plays": len(rows),
            "games": int(out["game_id_cfbd"].nunique()),
            "ranges": ranges}


def load_season_from_db(conn, season: int):
    """A season's plays back out of Supabase, in the CFBD spelling states.py
    expects. The inverse of store_season, and the reason a machine with no
    CFBD key can still build the states corpus."""
    names = list(DB_COLUMNS.values())
    rows = conn.execute(
        f"SELECT {', '.join(names)} FROM ncaaf_plays WHERE season = %s",
        (season,)).fetchall()
    df = pd.DataFrame(rows, columns=names)
    if df.empty:
        return df
    df = df.rename(columns=DB_TO_CFBD)
    for c in ("playNumber", "period", "clock_minutes", "clock_seconds",
              "offenseScore", "defenseScore", "offenseTimeouts",
              "defenseTimeouts", "down", "distance", "yardsToGoal",
              "yardsGained", "season", "week"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="+", type=int, default=list(ALL_SEASONS))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--to-db", action="store_true",
                    help="also upsert each season into Supabase (ncaaf_plays)")
    a = ap.parse_args()
    conn = None
    try:
        for s in a.seasons:
            if a.to_db:
                from data.db import get_connection
                conn = conn or get_connection()
                got = store_season(conn, s)
                print(f"{s}: {got['plays']:,} plays, {got['games']:,} games -> ncaaf_plays")
            else:
                pull_season(s, force=a.force)
    finally:
        if conn is not None:
            conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
