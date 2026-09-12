"""
Build the state parquet from pulled PBP + the platform tables.

    python -m ncaaf_live.backtest.build_states

Separate from train_engine so the (slow) platform join runs once and the
diagnostics print where a human sees them: the score-convention verdict, the
playType routing table, the pace check, and how many games each filter cost.

    python -m ncaaf_live.backtest.build_states                  # the full corpus
    python -m ncaaf_live.backtest.build_states --seasons 2025   # one season

A PARTIAL BUILD NEVER TAKES THE FULL CORPUS'S FILENAME. `states_all.parquet`
is what train_engine fits on, and a one-season file sitting at that path would
train the engine on a corpus nobody chose while every diagnostic still read
fine. `--seasons` therefore writes `states_<seasons>.parquet` unless `--out`
says otherwise, and prints the path it used. This is the same rule `load_pbp`
enforces on the way in: a short corpus is an error, not a convenience.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ncaaf_live.backtest.states import (  # noqa: E402
    build_states, classify_report, load_pbp, load_platform_games, pace_report)
from ncaaf_live.backtest.train_engine import STATES_PATH  # noqa: E402
from ncaaf_live.config import ALL_SEASONS  # noqa: E402


def out_path(seasons, explicit=None) -> Path:
    """Where a build of `seasons` belongs. The full corpus keeps its name; a
    subset gets its own, so the two can never be confused for each other."""
    if explicit:
        return Path(explicit)
    if seasons is None or set(seasons) == set(ALL_SEASONS):
        return STATES_PATH
    tag = "-".join(str(s) for s in sorted(seasons))
    return STATES_PATH.parent / f"states_{tag}.parquet"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seasons", nargs="+", type=int, default=None,
                    help="default: the full configured corpus")
    ap.add_argument("--out", default=None,
                    help="explicit output parquet (overrides the naming rule)")
    a = ap.parse_args()
    dest = out_path(a.seasons, a.out)

    pbp = load_pbp(a.seasons) if a.seasons else load_pbp()
    print(f"pbp: {len(pbp):,} plays, {pbp['gameId'].nunique():,} games, "
          f"seasons {sorted(pbp['season'].unique().tolist())}")

    rep = classify_report(pbp)
    unroutable = rep[(rep["is_scrim"] == 0) & (rep["n"] > 500)]
    print("\nplayType routing (top 20 by volume):")
    print(rep.head(20).to_string())
    print(f"\nnon-scrimmage types with >500 plays "
          f"(verify none is a real snap): {len(unroutable)}")

    platform = load_platform_games()
    print(f"\nplatform games with finals: {len(platform):,}  "
          f"with a pregame total: {platform['pregame_total'].notna().sum():,}")

    states = build_states(pbp, platform)
    print(f"\nstates: {len(states):,} rows, "
          f"{states['gameId'].nunique():,} games")
    print(f"score convention detected: {states.attrs['score_convention']}")
    print(f"games dropped for negative remaining targets: "
          f"{states.attrs['dropped_games_negative_target']}")
    print(f"pace check: {pace_report(states)}")

    per = states.groupby("season")["gameId"].nunique()
    print("\ngames with states per season:")
    print(per.to_string())

    dest.parent.mkdir(parents=True, exist_ok=True)
    states.to_parquet(dest)
    print(f"\nwrote {dest} ({dest.stat().st_size // (1 << 20)} MB)")
    if dest != STATES_PATH:
        print(f"NOTE: partial corpus. train_engine reads {STATES_PATH.name}; "
              f"this file is for a replay or a scoped analysis.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
