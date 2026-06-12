/**
 * Mirror of config.py — ACTION_THRESHOLDS, PROB_ONLY_MODELS, KELLY constants.
 *
 * UPDATE THIS FILE whenever the Python config.py thresholds change.
 * Last synced: 2026-06-11 (matches the 2026-06-03 settled-pick sweep in config.py
 * and the Section 16 SQL in CLAUDE.md).
 */

import type { Pick } from '@/types';

export interface ModelThreshold {
  min_prob: number;
  min_edge: number;
}

export const ACTION_THRESHOLDS: Record<string, ModelThreshold> = {
  // Game models — re-optimized 2026-06-03 from this season's settled BET picks
  mlb_moneyline: { min_prob: 0.72, min_edge: 0.12 },
  mlb_over_under: { min_prob: 0.72, min_edge: 0.15 },
  mlb_runline: { min_prob: 0.70, min_edge: 0.12 },
  mlb_f5_moneyline: { min_prob: 0.68, min_edge: 0.07 },

  // Pitcher props
  mlb_prop_pitcher_k: { min_prob: 0.62, min_edge: 0.08 },
  mlb_prop_pitcher_hits: { min_prob: 0.65, min_edge: 0.12 },
  mlb_prop_pitcher_er: { min_prob: 0.62, min_edge: 0.08 },
  mlb_prop_pitcher_outs: { min_prob: 0.60, min_edge: 0.12 },
  mlb_prop_pitcher_walks: { min_prob: 0.60, min_edge: 0.12 },

  // Batter props
  mlb_prop_batter_hits: { min_prob: 0.78, min_edge: 0.10 },
  mlb_prop_batter_tb: { min_prob: 0.85, min_edge: 0.12 },
  mlb_prop_batter_hr: { min_prob: 0.20, min_edge: 0.0 }, // prob-only
  mlb_prop_batter_rbi: { min_prob: 0.90, min_edge: 0.08 },
  mlb_prop_batter_runs: { min_prob: 0.65, min_edge: 0.15 },
  mlb_prop_batter_sb: { min_prob: 0.18, min_edge: 0.10 },
  mlb_prop_batter_walks: { min_prob: 0.95, min_edge: 0.10 },

  // WNBA — placeholder thresholds; retune after the 2025 holdout backtest sweep.
  wnba_moneyline: { min_prob: 0.66, min_edge: 0.12 },
  wnba_over_under: { min_prob: 0.66, min_edge: 0.12 },
  wnba_spread: { min_prob: 0.66, min_edge: 0.12 },
  wnba_prop_player_points: { min_prob: 0.60, min_edge: 0.08 },
  wnba_prop_player_rebounds: { min_prob: 0.60, min_edge: 0.08 },
  wnba_prop_player_assists: { min_prob: 0.60, min_edge: 0.08 },
  wnba_prop_player_threes: { min_prob: 0.60, min_edge: 0.08 },
  wnba_prop_player_pra: { min_prob: 0.60, min_edge: 0.08 },

  // UFC — placeholder thresholds; tune after 50+ settled picks.
  // ufc_method_of_victory is prob-only (no DK method odds via The Odds API).
  ufc_moneyline: { min_prob: 0.65, min_edge: 0.08 },
  ufc_total_rounds: { min_prob: 0.62, min_edge: 0.08 },
  ufc_method_of_victory: { min_prob: 0.65, min_edge: 0.0 }, // prob-only
};

export const PROB_ONLY_MODELS = new Set<string>([
  'mlb_prop_batter_hr',
  'ufc_method_of_victory',
]);

// Server-side Kelly fraction is computed as 0.10 × edge / (1 − implied), so
// pick.kelly_fraction reflects tenth-Kelly with the server's old 5% cap. The
// mobile client now lets the user scale this with a multiplier and apply an
// optional cap (see useKellySettings).
export const KELLY_MULTIPLIER = 0.10;

export interface KellySizingOpts {
  multiplier: number;     // 1.0 = tenth-Kelly (server default)
  cap: number | null;     // null = no cap; else max fraction of bankroll
}

export function passesActionFilter(p: Pick): boolean {
  if (p.signal_type !== 'BET') return false;
  const t = ACTION_THRESHOLDS[p.model_id];
  if (!t) return false;
  if (p.model_probability < t.min_prob) return false;
  if (PROB_ONLY_MODELS.has(p.model_id)) return true;
  return p.edge >= t.min_edge;
}

/** Effective fraction of bankroll after applying multiplier + user cap. */
export function effectiveKellyFraction(
  serverKellyFraction: number,
  opts: KellySizingOpts,
): number {
  const scaled = Math.max(0, serverKellyFraction * opts.multiplier);
  if (opts.cap != null) return Math.min(scaled, opts.cap);
  return scaled;
}

/** Bet size in dollars. */
export function recommendedBet(
  serverKellyFraction: number,
  bankroll: number,
  opts: KellySizingOpts,
): number {
  const f = effectiveKellyFraction(serverKellyFraction, opts);
  return Math.round(f * bankroll * 100) / 100;
}
