/**
 * Pure pieces of the custom-model backtest — the stats shape, the server/local
 * coverage split, and the merge of the two halves. Kept free of React and
 * react-native imports so the verify script can exercise them under tsx.
 *
 * The full picture: rules on server-graded models (see isOutcomeGraded) run
 * through the custom_model_backtest RPC against mv_scored_pick_outcomes —
 * every scored pick since paper start (BET + AVOID + dead-zone NONE), graded
 * from final scores and refreshed daily after settle. Rules on anything else
 * (UFC/NHL/golf) fall back to the settled BET/AVOID rows, which is all that
 * exists for those sports. A pick only matches rules for its own model_id, so
 * summing the halves is exact — no double counting.
 */

import { isOutcomeGraded } from './customModelFilters';
import type { CustomModelRule, SignalType } from '@/types';

export interface CustomModelStats {
  picks: number;
  wins: number;
  losses: number;
  pushes: number;
  winRate: number; // wins / (wins + losses)
  profitFlat: number;
  stakedFlat: number;
  roiFlat: number;
}

export const EMPTY_STATS: CustomModelStats = {
  picks: 0,
  wins: 0,
  losses: 0,
  pushes: 0,
  winRate: 0,
  profitFlat: 0,
  stakedFlat: 0,
  roiFlat: 0,
};

/** Aggregate result of the custom_model_backtest RPC. units are 1u flat;
 *  roi_pct is over priced picks only (prob-only picks have no honest P&L). */
export interface CustomBacktestSummary {
  bets: number;
  wins: number;
  losses: number;
  pushes: number;
  priced: number;
  units: number;
  roi_pct: number | null;
}

/** One graded pick from the custom_model_picks RPC. */
export interface CustomBacktestPickRow {
  pick_id: number;
  model_id: string;
  game_date: string;
  game_id: string;
  pick_label: string;
  pick_side: string;
  signal_type: string;
  model_probability: number;
  edge: number;
  dk_odds: number | null;
  result: 'WIN' | 'LOSS' | 'PUSH';
  profit_units: number | null;
}

/** One graded pick for display, whichever half it came from. profit_flat is at
 *  the app's $100-notional convention; null = unpriced. */
export interface BacktestPickRow {
  pick_id: number;
  model_id: string;
  game_date: string;
  pick_label: string;
  signal_type: SignalType;
  result: string;
  profit_flat: number | null;
}

/** Split a model's rules by whether the server grades that model's every pick. */
export function splitRulesByCoverage(rules: CustomModelRule[]): {
  covered: CustomModelRule[];
  uncovered: CustomModelRule[];
} {
  const covered: CustomModelRule[] = [];
  const uncovered: CustomModelRule[] = [];
  for (const r of rules) (isOutcomeGraded(r.model_id) ? covered : uncovered).push(r);
  return { covered, uncovered };
}

export function summaryToStats(s: CustomBacktestSummary): CustomModelStats {
  const decided = s.wins + s.losses;
  return {
    picks: s.bets,
    wins: s.wins,
    losses: s.losses,
    pushes: s.pushes,
    winRate: decided > 0 ? s.wins / decided : 0,
    profitFlat: s.units * 100,
    stakedFlat: s.priced * 100,
    roiFlat: s.priced > 0 ? s.units / s.priced : 0,
  };
}

/** Sum two backtest halves; ratios recomputed from the summed counters. */
export function mergeStats(a: CustomModelStats, b: CustomModelStats): CustomModelStats {
  const wins = a.wins + b.wins;
  const losses = a.losses + b.losses;
  const profitFlat = a.profitFlat + b.profitFlat;
  const stakedFlat = a.stakedFlat + b.stakedFlat;
  return {
    picks: a.picks + b.picks,
    wins,
    losses,
    pushes: a.pushes + b.pushes,
    winRate: wins + losses > 0 ? wins / (wins + losses) : 0,
    profitFlat,
    stakedFlat,
    roiFlat: stakedFlat > 0 ? profitFlat / stakedFlat : 0,
  };
}
