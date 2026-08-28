"""
Fetch the nflverse play-by-play parquets. Free, no key, no credits.

    python -m live_model.backtest.pull_pbp
    python -m live_model.backtest.pull_pbp --seasons 2023 2024 2025 --force

~20MB per season, ~220MB for 2015-2025. Gitignored because it is free to
refetch and because a quarter of a gigabyte of derived data does not belong in
git history; this script is what rebuilds it.
"""

from __future__ import annotations

import argparse
import sys

import requests

from ..config import PBP_DIR

RELEASE = ("https://github.com/nflverse/nflverse-data/releases/download/pbp/"
           "play_by_play_{season}.parquet")
DEFAULT_SEASONS = tuple(range(2015, 2026))


def pull(seasons=DEFAULT_SEASONS, force: bool = False) -> dict:
    PBP_DIR.mkdir(parents=True, exist_ok=True)
    got, skipped, failed = [], [], []
    for season in seasons:
        path = PBP_DIR / f"play_by_play_{season}.parquet"
        if path.exists() and not force:
            skipped.append(season)
            continue
        url = RELEASE.format(season=season)
        try:
            r = requests.get(url, timeout=300)
            r.raise_for_status()
            # Write to a temp file first: a truncated parquet that looks like a
            # complete one is worse than a missing one, because pandas reports
            # it as a schema error somewhere unrelated.
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(r.content)
            tmp.replace(path)
            got.append(season)
        except requests.RequestException as e:
            print(f"  {season}: FAILED {e}", file=sys.stderr)
            failed.append(season)
    return {"fetched": got, "skipped": skipped, "failed": failed}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", type=int, nargs="+", default=list(DEFAULT_SEASONS))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    res = pull(args.seasons, args.force)
    print(f"fetched {res['fetched']}")
    print(f"already present {res['skipped']}")
    if res["failed"]:
        print(f"FAILED {res['failed']}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
