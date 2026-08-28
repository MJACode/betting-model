"""
Build the state parquet from pulled PBP + the platform tables.

    python -m ncaaf_live.backtest.build_states

Separate from train_engine so the (slow) platform join runs once and the
diagnostics print where a human sees them: the score-convention verdict, the
playType routing table, the pace check, and how many games each filter cost.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ncaaf_live.backtest.states import (  # noqa: E402
    build_states, classify_report, load_pbp, load_platform_games, pace_report)
from ncaaf_live.backtest.train_engine import STATES_PATH  # noqa: E402


def main() -> int:
    pbp = load_pbp()
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

    STATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    states.to_parquet(STATES_PATH)
    print(f"\nwrote {STATES_PATH} "
          f"({STATES_PATH.stat().st_size // (1 << 20)} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
