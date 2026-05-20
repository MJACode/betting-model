/**
 * Mirror of config.py — ACTION_THRESHOLDS, PROB_ONLY_MODELS, KELLY constants.
 *
 * UPDATE THIS FILE whenever the Python config.py thresholds change.
 * Last synced: 2026-05-15 (matches Section 16 SQL in CLAUDE.md).
 */

import type { Pick } from '@/types';

export interface ModelThreshold {
  min_prob: number;
  min_edge: number;
}

export const ACTION_THRESHOLDS: Record<string, ModelThreshold> = {
  // Game models — raised 2026-05-15 from live data sweep
  mlb_moneyline: { min_prob: 0.72, min_edge: 0.12 },
  mlb_over_under: { min_prob: 0.67, min_edge: 0.15 },
  mlb_runline: { min_prob: 0.70, min_edge: 0.12 },
  mlb_f5_moneyline: { min_prob: 0.62, min_edge: 0.07 },

  // Pitcher props
  mlb_prop_pitcher_k: { min_prob: 0.62, min_edge: 0.08 },
  mlb_prop_pitcher_hits: { min_prob: 0.60, min_edge: 0.10 },
  mlb_prop_pitcher_er: { min_prob: 0.62, min_edge: 0.08 },
  mlb_prop_pitcher_outs: { min_prob: 0.60, min_edge: 0.12 },
  mlb_prop_pitcher_walks: { min_prob: 0.60, min_edge: 0.10 },

  // Batter props
  mlb_prop_batter_hits: { min_prob: 0.60, min_edge: 0.08 },
  mlb_prop_batter_tb: { min_prob: 0.60, min_edge: 0.08 },
  mlb_prop_batter_hr: { min_prob: 0.20, min_edge: 0.0 }, // prob-only
  mlb_prop_batter_rbi: { min_prob: 0.62, min_edge: 0.08 },
  mlb_prop_batter_runs: { min_prob: 0.62, min_edge: 0.08 },
  mlb_prop_batter_sb: { min_prob: 0.18, min_edge: 0.08 },
  mlb_prop_batter_walks: { min_prob: 0.62, min_edge: 0.08 },
};

export const PROB_ONLY_MODELS = new Set<string>(['mlb_prop_batter_hr']);

export const KELLY_MULTIPLIER = 0.10;
export const MAX_KELLY_FRACTION = 0.05;

export function passesActionFilter(p: Pick): boolean {
  if (p.signal_type !== 'BET') return false;
  const t = ACTION_THRESHOLDS[p.model_id];
  if (!t) return false;
  if (p.model_probability < t.min_prob) return false;
  if (PROB_ONLY_MODELS.has(p.model_id)) return true;
  return p.edge >= t.min_edge;
}

/** Bet size given user's bankroll and pick's kelly_fraction. Caps at 5%. */
export function recommendedBet(kellyFraction: number, bankroll: number): number {
  const capped = Math.max(0, Math.min(kellyFraction, MAX_KELLY_FRACTION));
  return Math.round(capped * bankroll * 100) / 100;
}
