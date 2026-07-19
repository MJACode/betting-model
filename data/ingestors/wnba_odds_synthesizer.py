"""
wnba_odds_synthesizer.py — Generate synthetic WNBA totals + spread lines for training.

WHY
---
`wnba_over_under` and `wnba_spread` were blocked since launch: their targets need
`total_line` / `spread_home`, and no historical WNBA odds exist (real DK WNBA lines
only started accumulating 2026-05-31 — ~115 completed games, far too thin to train
on). This is the F5 precedent (f5_odds_synthesizer.py) applied to WNBA: fabricate
a reasonable line for every completed 2019-2025 WNBA game, insert it as
bookmaker='sbr_consensus' (the bulk feature loader already treats that as the
DK fallback), train against the synthetic lines, and score live against REAL DK
lines. Backtest/holdout numbers vs synthetic lines are DIRECTIONAL ONLY.

LINE FORMULAS (calibrated 2026-07-19 against the 118 real DK 2026 lines)
------------------------------------------------------------------------
Per team, ASOF each game: the average game total and average signed margin over
that team's PRIOR games in the same season (leak-free; min 3 prior games per side
— the early-season analog, mirrors the 10-game rule).

  pred_total  = (home_avg_total + away_avg_total) / 2
  total_line  = floor(pred_total) + 0.5                      # forced .5 → no pushes

  pred_margin = (home_avg_margin - away_avg_margin) / 2      # ~0-centered, misses HCA
  spread_home = -(HCA + SLOPE * pred_margin), rounded to 0.5, nudged off integers

Calibration findings: the naive predictor is season-self-anchoring (per-season
mean within ~1-3 pts of actual scoring in every season 2019-2026 — no era bias),
so totals use slope 1.0. Real DK spreads regress on -pred_margin with slope 1.46
and intercept -2.16 (r=0.57, n=118) — the intercept IS home-court advantage, which
the raw margin diff misses entirely, so spreads use the fitted form. Totals r vs
real lines = 0.50: synthetic lines are noisy — another reason holdout metrics vs
them are directional until real-line live picks accumulate.

Rows are only inserted for games with no existing totals/spreads odds row —
re-running is safe, and 2026 (real DK lines) is excluded entirely.

Usage:
    python -m data.ingestors.wnba_odds_synthesizer            # insert
    python -m data.ingestors.wnba_odds_synthesizer --dry-run  # count only
"""

import argparse
from pathlib import Path
import sys

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from data.db import get_connection

# Spread calibration vs real 2026 DK lines (see module docstring).
WNBA_SPREAD_HCA = 2.16      # home-court baseline (points)
WNBA_SPREAD_SLOPE = 1.46    # dispersion: books spread wider than naive margin diff
MIN_PRIOR_GAMES = 3         # per side, same season — else no synthetic line
LAST_SYNTH_SEASON = 2025    # 2026+ has real DK lines; never synthesize over them

_SYNTH_SQL = f"""
WITH g AS (
    SELECT game_id, season, game_date, home_team, away_team,
           home_score::float AS hs, away_score::float AS aw
    FROM games
    WHERE sport = 'WNBA'
      AND home_score IS NOT NULL AND away_score IS NOT NULL
      AND season <= {LAST_SYNTH_SEASON}
),
team_games AS (
    SELECT game_id, season, game_date, home_team AS team,
           hs + aw AS total, hs - aw AS margin FROM g
    UNION ALL
    SELECT game_id, season, game_date, away_team,
           hs + aw, aw - hs FROM g
),
asof AS (
    SELECT tg.game_id, tg.team,
           AVG(p.total)  AS avg_total,
           AVG(p.margin) AS avg_margin,
           COUNT(*)      AS n_prior
    FROM team_games tg
    JOIN team_games p
      ON p.team = tg.team AND p.season = tg.season AND p.game_date < tg.game_date
    GROUP BY tg.game_id, tg.team
),
pred AS (
    SELECT g.game_id, g.game_date,
           (h.avg_total + a.avg_total) / 2.0 AS pred_total,
           -({WNBA_SPREAD_HCA} + {WNBA_SPREAD_SLOPE}
             * (h.avg_margin - a.avg_margin) / 2.0) AS raw_spread
    FROM g
    JOIN asof h ON h.game_id = g.game_id AND h.team = g.home_team
               AND h.n_prior >= {MIN_PRIOR_GAMES}
    JOIN asof a ON a.game_id = g.game_id AND a.team = g.away_team
               AND a.n_prior >= {MIN_PRIOR_GAMES}
),
lines AS (
    SELECT game_id, game_date,
           floor(pred_total) + 0.5 AS total_line,
           -- round to nearest 0.5; nudge integers off by 0.5 away from zero so
           -- spread targets can never push
           CASE WHEN mod(round(raw_spread * 2)::int, 2) = 0
                THEN round(raw_spread * 2) / 2.0
                     + CASE WHEN raw_spread > 0 THEN 0.5 ELSE -0.5 END
                ELSE round(raw_spread * 2) / 2.0 END AS spread_home
    FROM pred
)
INSERT INTO odds (game_id, sport, market, bookmaker, snapshot_type, snapshot_at,
                  home_price, away_price, draw_price,
                  spread_home, total_line, over_price, under_price)
SELECT l.game_id, 'WNBA', m.market, 'sbr_consensus', 'open',
       l.game_date || 'T00:00:00Z',
       NULL, NULL, NULL,
       CASE WHEN m.market = 'spreads' THEN l.spread_home END,
       CASE WHEN m.market = 'totals'  THEN l.total_line  END,
       NULL, NULL
FROM lines l
CROSS JOIN (VALUES ('totals'), ('spreads')) AS m(market)
WHERE NOT EXISTS (
    SELECT 1 FROM odds o2
    WHERE o2.game_id = l.game_id AND o2.market = m.market
)
"""


def run_synthesizer(dry_run: bool = False) -> int:
    conn = get_connection()
    try:
        if dry_run:
            n = conn.execute(
                "SELECT COUNT(*) FROM games WHERE sport='WNBA' "
                "AND home_score IS NOT NULL AND season <= %s",
                (LAST_SYNTH_SEASON,),
            ).fetchone()[0]
            logger.info(f"Dry run: {n} completed WNBA games <= {LAST_SYNTH_SEASON} "
                        f"are candidates (min-prior + existing-row filters apply at insert)")
            return 0
        conn.execute(_SYNTH_SQL)
        conn.commit()
        n = conn.execute(
            "SELECT COUNT(*) FROM odds o JOIN games g ON g.game_id = o.game_id "
            "WHERE g.sport='WNBA' AND o.bookmaker='sbr_consensus' "
            "AND o.market IN ('totals','spreads')"
        ).fetchone()[0]
        logger.success(f"WNBA synthetic odds rows present: {n}")
        return n
    finally:
        conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    run_synthesizer(dry_run=args.dry_run)
