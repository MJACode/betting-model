"""How much does one day of stats drift move a live model's probability?

WHY THIS EXISTS
---------------
Diagnosing the inning-gate replay turned up a live decision that could not be
reproduced, and the reason was not the replay: holding the live state, the DK
line and the price FIXED and changing only which day's team-stats snapshot fed
the pre-game half of the feature row moved `p_over` from 0.5263 to 0.7199 on
`MLB_2026-09-07_LAA_BOS`, against a production record of 0.7268.

That was n=1. This measures it across every live BET, because "pathological"
needs a distribution rather than an anecdote.

WHAT IT DOES
    For each settled live BET, take the live state at the moment production
    picked, keep the pick's own line and price, and recompute the model's
    probability with the team-stats snapshot from the game date, one day
    earlier, and two days earlier. Report the spread.

Everything except the six season-to-date stats features is byte-identical
between the three runs -- state, weather, line, price -- so the spread is
attributable to stats drift alone.

    python -m scripts.live_feature_sensitivity
    python -m scripts.live_feature_sensitivity --since 2026-08-24 --limit 60
"""

from __future__ import annotations

import argparse
import datetime as dt
import statistics

import numpy as np
from loguru import logger

from data.db import get_connection
from features.feature_engine import build_mlb_game_features
from features.live_game_features import build_live_state_row
from models.live_scorer import _poisson_over_prob
from models.scorer import _get_dk_odds
from models.trainer import load_model

MODEL = "mlb_live_total_runs"
STATE = ["inning", "inning_half", "outs", "bases_state", "home_score",
         "away_score", "abstract_game_state", "snapshot_at"]


def measure(since: str, limit: int | None) -> list[tuple[str, float]]:
    conn = get_connection()
    artifact = load_model(MODEL)
    if artifact is None:
        raise SystemExit(f"no active artifact for {MODEL}")
    cols, clf = artifact["feature_cols"], artifact["model"]
    try:
        picks = conn.execute(f"""
            SELECT p.game_id, p.game_date, p.scored_line, p.created_at,
                   g.home_team, g.away_team, g.season
            FROM picks p JOIN games g ON g.game_id = p.game_id
            WHERE p.model_id = %s AND p.signal_type = 'BET' AND p.is_live
              AND p.game_date >= %s AND p.dk_odds IS NOT NULL
            ORDER BY p.game_date, p.game_id
            {f'LIMIT {int(limit)}' if limit else ''}
        """, (MODEL, since)).fetchall()

        out = []
        for gid, gd, line, created, home, away, season in picks:
            if line is None:
                continue
            st = conn.execute(f"""
                SELECT {', '.join(STATE)} FROM live_game_state
                WHERE game_id = %s AND snapshot_at::timestamptz <= %s::timestamptz
                ORDER BY snapshot_at::timestamptz DESC LIMIT 1
            """, (gid, created)).fetchone()
            if not st:
                continue
            state = dict(zip(STATE, st))
            base = dt.date.fromisoformat(str(gd)[:10])
            probs = []
            for back in (0, 1, 2):
                asof = (base - dt.timedelta(days=back)).isoformat()
                pre = build_mlb_game_features(
                    conn, gid, asof, home, away, season,
                    odds_row=_get_dk_odds(conn, gid, "h2h"))
                if not pre:
                    continue
                row = build_live_state_row(state, pre, MODEL)
                if row is None:
                    continue
                x = np.array([[np.nan if row.get(c) is None else float(row[c])
                               for c in cols]], dtype=float)
                lam = float(np.clip(clf.predict(x)[0], 1e-6, None))
                rest = float(line) - row["total_runs"]
                if rest < 0:
                    continue
                probs.append(_poisson_over_prob(lam, rest))
            if len(probs) >= 2:
                out.append((gid, max(probs) - min(probs)))
        return out
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--since", default="2026-08-24")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    rows = measure(args.since, args.limit)
    if not rows:
        logger.warning("no comparable games — nothing measured")
        return
    spreads = sorted(s for _, s in rows)
    print(f"\ngames measured: {len(spreads)}")
    print(f"median swing in p_over across 3 daily stats snapshots: "
          f"{statistics.median(spreads):.4f}")
    print(f"mean {statistics.mean(spreads):.4f}   "
          f"p90 {spreads[int(len(spreads) * 0.9) - 1]:.4f}   "
          f"max {spreads[-1]:.4f}")
    for t in (0.02, 0.05, 0.10, 0.20):
        n = sum(1 for s in spreads if s > t)
        print(f"   swing > {t:.0%}: {n:>4} / {len(spreads)}  ({n / len(spreads):.0%})")


if __name__ == "__main__":
    main()
