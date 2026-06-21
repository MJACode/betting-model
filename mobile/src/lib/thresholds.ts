/**
 * Mirror of config.py — ACTION_THRESHOLDS, PROB_ONLY_MODELS, KELLY constants.
 *
 * UPDATE THIS FILE whenever the Python config.py thresholds change.
 * Last synced: 2026-06-13 (matches the 2026-06-06 settled-pick sweep in config.py
 * and the Section 16 SQL in CLAUDE.md, plus the live in-play models).
 */

import type { Pick } from '@/types';

export interface ModelThreshold {
  min_prob: number;
  min_edge: number;
}

export const ACTION_THRESHOLDS: Record<string, ModelThreshold> = {
  // Game models — re-optimized 2026-06-20 from settled BET picks since 2026-04-14 (in-sample; will regress)
  mlb_moneyline: { min_prob: 0.70, min_edge: 0.10 },
  mlb_over_under: { min_prob: 0.50, min_edge: 0.12 },
  mlb_runline: { min_prob: 0.68, min_edge: 0.08 },
  mlb_f5_moneyline: { min_prob: 0.71, min_edge: 0.08 },

  // Live (in-play) models — conservative placeholders; tune after 50+ settled live picks.
  mlb_live_win_prob: { min_prob: 0.65, min_edge: 0.10 },
  mlb_live_total_runs: { min_prob: 0.65, min_edge: 0.10 },
  mlb_live_runline: { min_prob: 0.65, min_edge: 0.10 },

  // Pitcher props (2026-06-20 sweep; hits/walks have no winning cut → retraining)
  mlb_prop_pitcher_k: { min_prob: 0.71, min_edge: 0.06 },
  mlb_prop_pitcher_hits: { min_prob: 0.65, min_edge: 0.12 },
  mlb_prop_pitcher_er: { min_prob: 0.60, min_edge: 0.08 },
  mlb_prop_pitcher_outs: { min_prob: 0.50, min_edge: 0.12 },
  mlb_prop_pitcher_walks: { min_prob: 0.60, min_edge: 0.08 },

  // Batter props (2026-06-20 sweep; hr/sb have no winning cut)
  mlb_prop_batter_hits: { min_prob: 0.64, min_edge: 0.16 },
  mlb_prop_batter_tb: { min_prob: 0.83, min_edge: 0.17 },
  mlb_prop_batter_hr: { min_prob: 0.20, min_edge: 0.0 }, // prob-only
  mlb_prop_batter_rbi: { min_prob: 0.89, min_edge: 0.15 },
  mlb_prop_batter_runs: { min_prob: 0.60, min_edge: 0.15 },
  mlb_prop_batter_sb: { min_prob: 0.18, min_edge: 0.10 },
  mlb_prop_batter_walks: { min_prob: 0.95, min_edge: 0.10 },

  // WNBA — placeholder thresholds; retune after the 2025 holdout backtest sweep.
  wnba_moneyline: { min_prob: 0.66, min_edge: 0.12 },
  wnba_over_under: { min_prob: 0.66, min_edge: 0.12 },
  wnba_spread: { min_prob: 0.66, min_edge: 0.12 },
  // WNBA props — re-optimized 2026-06-20 (thin 15-40 bet samples since June 1; will regress)
  wnba_prop_player_points: { min_prob: 0.60, min_edge: 0.15 },
  wnba_prop_player_rebounds: { min_prob: 0.73, min_edge: 0.11 },
  wnba_prop_player_assists: { min_prob: 0.69, min_edge: 0.11 },
  wnba_prop_player_threes: { min_prob: 0.66, min_edge: 0.14 },
  wnba_prop_player_pra: { min_prob: 0.67, min_edge: 0.16 },

  // NBA — placeholder thresholds; tune after live odds accumulate.
  // nba_prop_player_dd is prob-only (DK juices double-double Yes/No).
  nba_moneyline: { min_prob: 0.66, min_edge: 0.12 },
  nba_over_under: { min_prob: 0.66, min_edge: 0.12 },
  nba_spread: { min_prob: 0.66, min_edge: 0.12 },
  nba_prop_player_points: { min_prob: 0.60, min_edge: 0.08 },
  nba_prop_player_rebounds: { min_prob: 0.60, min_edge: 0.08 },
  nba_prop_player_assists: { min_prob: 0.60, min_edge: 0.08 },
  nba_prop_player_threes: { min_prob: 0.60, min_edge: 0.08 },
  nba_prop_player_pra: { min_prob: 0.60, min_edge: 0.08 },
  nba_prop_player_blocks: { min_prob: 0.60, min_edge: 0.08 },
  nba_prop_player_steals: { min_prob: 0.60, min_edge: 0.08 },
  nba_prop_player_turnovers: { min_prob: 0.60, min_edge: 0.08 },
  nba_prop_player_dd: { min_prob: 0.55, min_edge: 0.0 }, // prob-only

  // UFC — placeholder thresholds; tune after 50+ settled picks.
  // ufc_method_of_victory is prob-only (no DK method odds via The Odds API).
  ufc_moneyline: { min_prob: 0.65, min_edge: 0.08 },
  ufc_total_rounds: { min_prob: 0.62, min_edge: 0.08 },
  ufc_method_of_victory: { min_prob: 0.65, min_edge: 0.0 }, // prob-only

  // NHL — placeholder thresholds; tune after 50+ settled picks.
  // moneyline_regulation is a 3-way market (lower per-side prob).
  nhl_moneyline: { min_prob: 0.55, min_edge: 0.05 },
  nhl_moneyline_regulation: { min_prob: 0.40, min_edge: 0.05 },
  nhl_over_under: { min_prob: 0.55, min_edge: 0.05 },
  nhl_puckline: { min_prob: 0.55, min_edge: 0.05 },

  // GOLF — placeholder thresholds on a market-relative prob scale (win ~3%,
  // top-N ~15-25%, make-cut ~65%). Tune after 50+ settled picks per model.
  golf_outright: { min_prob: 0.03, min_edge: 0.015 },
  golf_top10: { min_prob: 0.15, min_edge: 0.05 },
  golf_top20: { min_prob: 0.25, min_edge: 0.05 },
  golf_make_cut: { min_prob: 0.65, min_edge: 0.05 },
  golf_matchup: { min_prob: 0.55, min_edge: 0.05 },
};

export const PROB_ONLY_MODELS = new Set<string>([
  'mlb_prop_batter_hr',
  'ufc_method_of_victory',
  'nba_prop_player_dd',
]);

// Mirror of config.py PAUSED_MODELS — models that never fire a BET (paused for
// poor performance). Excluded from the action filter so they don't appear as
// actionable picks anywhere in the app.
export const PAUSED_MODELS = new Set<string>([
  // mlb_prop_batter_hr UNPAUSED 2026-06-20 — the -66.6% was a -110-settlement
  // artifact (DK HR odds weren't ingested; now sourced from batter_home_runs_alternate).
  // Kept live + +EV-filtered when priced.
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
  if (PAUSED_MODELS.has(p.model_id)) return false;
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
