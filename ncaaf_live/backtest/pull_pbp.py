"""
Pull CFBD play-by-play into per-season parquet files.

    python -m ncaaf_live.backtest.pull_pbp                # all configured seasons
    python -m ncaaf_live.backtest.pull_pbp --seasons 2024 2025

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


def pull_season(season: int, force: bool = False) -> Path | None:
    out = PBP_DIR / f"plays_{season}.parquet"
    if out.exists() and not force:
        print(f"{season}: exists ({out.stat().st_size // 1024} KB), skipping")
        return out

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
    full = pd.concat(frames, ignore_index=True)
    full.to_parquet(out)
    print(f"{season}: {len(full):,} plays, "
          f"{full['gameId'].nunique():,} games -> {out.name}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="+", type=int, default=list(ALL_SEASONS))
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    for s in a.seasons:
        pull_season(s, force=a.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
