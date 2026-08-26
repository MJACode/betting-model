"""
NCAAF search — opener/close pull from CFBD into a RESEARCH-LOCAL cache.

Why a local cache and not the `odds` table: the 2026 season is live and the
production odds table is being written by the worker every refresh pass. This
is a research program, so it reads production and writes only to
`data/raw/datawarehouse/ncaaf/lines_cache/`. Promoting openers into `odds` is
a separate, deliberate change if a model ever ships.

Availability (probed 2026-08-25 against the live API):

    season   provider     spreadOpen   overUnderOpen
    2016     ALL          0            0
    2021     Bovada       840 / 841    841 / 841
    2021     others       0            0
    2025     Bovada       887 / 887    887 / 887
    2025     DraftKings   676 / 759     72 / 759
    2025     ESPN Bet     878 / 1542   861 / 1542

Bovada is the ONLY provider with usable openers, and only from 2021 — which
is also the only provider with continuous closing coverage across 2021-2025.
That makes "Bovada, 2021-2025" the single choice that satisfies the spec's
no-provider-mixing rule AND unblocks Group D + CLV.

Run:
    python -m scripts.ncaaf_search.openers --seasons 2021 2022 2023 2024 2025
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

CACHE_DIR = (Path(__file__).parent.parent.parent
             / "data" / "raw" / "datawarehouse" / "ncaaf" / "lines_cache")
_API = "https://api.collegefootballdata.com/lines"
OPENER_PROVIDER = "Bovada"
OPENER_SEASONS = [2021, 2022, 2023, 2024, 2025]


def _headers() -> dict:
    from dotenv import load_dotenv
    load_dotenv()
    key = os.environ.get("CFBD_API_KEY")
    if not key:
        raise SystemExit("CFBD_API_KEY not set")
    return {"Authorization": f"Bearer {key}"}


def fetch_season(season: int, season_type: str = "both",
                 force: bool = False) -> list[dict]:
    """Raw /lines payload for a season, cached to disk (idempotent)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"lines_{season}_{season_type}.json"
    if path.exists() and not force:
        return json.loads(path.read_text(encoding="utf-8"))

    params = {"year": season}
    if season_type != "both":
        params["seasonType"] = season_type
    r = requests.get(_API, params=params, headers=_headers(), timeout=90)
    r.raise_for_status()
    data = r.json()
    path.write_text(json.dumps(data), encoding="utf-8")
    logger.info(f"CFBD lines {season}: {len(data)} games -> {path.name}")
    time.sleep(0.5)
    return data


def _norm(s: str | None) -> str:
    return (s or "").strip()


def to_frame(payload: list[dict], provider: str | None = None) -> pd.DataFrame:
    """
    Flatten /lines into one row per (game, provider) with open AND close.

    CFBD `spread`/`overUnder` are the CLOSE; `spreadOpen`/`overUnderOpen` the
    open. Spreads are HOME-relative, matching the §29 convention.
    """
    out = []
    for g in payload:
        for ln in (g.get("lines") or []):
            p = _norm(ln.get("provider"))
            if provider and p != provider:
                continue
            out.append({
                "cfbd_game_id": g.get("id"),
                "season": g.get("season"),
                "week": g.get("week"),
                "season_type": g.get("seasonType"),
                "start_date": g.get("startDate"),
                "home_team": _norm(g.get("homeTeam")),
                "away_team": _norm(g.get("awayTeam")),
                "home_score": g.get("homeScore"),
                "away_score": g.get("awayScore"),
                "provider": p,
                "spread_close": ln.get("spread"),
                "spread_open": ln.get("spreadOpen"),
                "total_close": ln.get("overUnder"),
                "total_open": ln.get("overUnderOpen"),
            })
    df = pd.DataFrame(out)
    for c in ("spread_close", "spread_open", "total_close", "total_open",
              "home_score", "away_score"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def build_opener_cache(seasons: list[int] | None = None,
                       provider: str = OPENER_PROVIDER,
                       force: bool = False) -> pd.DataFrame:
    """Fetch + flatten + persist a tidy opener/close frame for `provider`."""
    seasons = seasons or OPENER_SEASONS
    frames = [to_frame(fetch_season(s, force=force), provider) for s in seasons]
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if df.empty:
        logger.warning(f"No {provider} rows for {seasons}")
        return df

    df["game_key"] = (df["season"].astype(str) + "_"
                      + df["away_team"].str.replace(" ", "-", regex=False) + "_"
                      + df["home_team"].str.replace(" ", "-", regex=False))
    dup = int(df.duplicated(["season", "home_team", "away_team"]).sum())
    if dup:
        logger.warning(f"{dup} duplicate (season, home, away) rows — keeping first")
        df = df.drop_duplicates(["season", "home_team", "away_team"], keep="first")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out = CACHE_DIR / f"openers_{provider.lower().replace(' ', '')}.parquet"
    df.to_parquet(out, index=False)
    logger.success(f"{len(df)} {provider} rows -> {out}")
    return df


def coverage_report(df: pd.DataFrame) -> pd.DataFrame:
    """% non-null openers by season — the spec's item-3 deliverable."""
    if df.empty:
        return df
    g = df.groupby("season")
    return pd.DataFrame({
        "rows": g.size(),
        "spread_close": g["spread_close"].apply(lambda s: s.notna().mean()),
        "spread_open": g["spread_open"].apply(lambda s: s.notna().mean()),
        "total_close": g["total_close"].apply(lambda s: s.notna().mean()),
        "total_open": g["total_open"].apply(lambda s: s.notna().mean()),
    }).round(4)


def main() -> int:
    ap = argparse.ArgumentParser(description="CFBD opener/close cache")
    ap.add_argument("--seasons", nargs="+", type=int, default=OPENER_SEASONS)
    ap.add_argument("--provider", default=OPENER_PROVIDER)
    ap.add_argument("--force", action="store_true", help="re-fetch, ignore cache")
    a = ap.parse_args()

    df = build_opener_cache(a.seasons, a.provider, a.force)
    if df.empty:
        return 1
    print("\nOPENER COVERAGE (fraction non-null)")
    print(coverage_report(df).to_string())

    mv = df.dropna(subset=["spread_open", "spread_close"])
    if len(mv):
        moved = (mv["spread_close"] - mv["spread_open"]).abs()
        print(f"\nSpread open->close movement (n={len(mv)}):")
        print(f"  mean |move| {moved.mean():.2f} pts | median {moved.median():.2f} "
              f"| unmoved {(moved == 0).mean():.1%} | >=1pt {(moved >= 1).mean():.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
