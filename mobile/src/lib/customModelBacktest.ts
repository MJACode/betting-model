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

import { isOutcomeGraded, pickMatchesModel } from './customModelFilters';
import { flatPnl, isModelRetired, passesActionFilter } from './thresholds';
import type { CustomModel, CustomModelRule, SettledPick, SignalType } from '@/types';

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

/** Split a model's rules by whether the server grades that model's every pick.
 *
 * A rule on a RETIRED model goes to neither side. mv_scored_pick_outcomes keeps
 * a retired model's graded picks forever (it is the evaluation universe, not a
 * published total), so without this a saved custom model built on batter HR
 * or RBI would keep counting them through the backtest RPC. */
export function splitRulesByCoverage(rules: CustomModelRule[]): {
  covered: CustomModelRule[];
  uncovered: CustomModelRule[];
} {
  const covered: CustomModelRule[] = [];
  const uncovered: CustomModelRule[] = [];
  for (const r of rules) {
    if (isModelRetired(r.model_id)) continue;
    (isOutcomeGraded(r.model_id) ? covered : uncovered).push(r);
  }
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

// ---------------------------------------------------------------------------
// Settled-pick tallies (client side)
// ---------------------------------------------------------------------------
// Moved here from hooks/useCustomModelStats on 2026-09-03 so a tsx verify
// script can exercise them without dragging react-native in through the hook's
// imports (scripts/verify_unpriced_pnl.ts). The hook re-exports both.

export function computeCustomModelStats(model: CustomModel, settled: SettledPick[]): CustomModelStats {
  let picks = 0;
  let wins = 0;
  let losses = 0;
  let pushes = 0;
  let profitFlat = 0;
  let stakedFlat = 0;

  for (const p of settled) {
    if (!pickMatchesModel(p, model)) continue;
    // Only W/L/P count as picks — NO_ACTION rows (DNP, DQ, unsettleable)
    // would otherwise inflate the count vs the displayed record.
    if (p.result === 'WIN') wins++;
    else if (p.result === 'LOSS') losses++;
    else if (p.result === 'PUSH') pushes++;
    else continue;
    picks++;
    // Money only on a priced pick — see flatPnl. Matches the server half
    // (custom_model_backtest: profit_units NULL and priced=0 when dk_odds is
    // NULL), so the two halves mergeStats adds are priced on the same rule.
    const money = flatPnl(p);
    profitFlat += money.profit;
    stakedFlat += money.staked;
  }

  const decided = wins + losses;
  return {
    picks,
    wins,
    losses,
    pushes,
    winRate: decided > 0 ? wins / decided : 0,
    profitFlat,
    stakedFlat,
    roiFlat: stakedFlat > 0 ? profitFlat / stakedFlat : 0,
  };
}

// Built-in model records apply the CURRENT action thresholds retroactively, so
// the record answers "how has this model's current prob/edge combo performed?"
// rather than blending picks generated under older, looser thresholds.
export function computeBuiltInModelStats(modelId: string, settled: SettledPick[]): CustomModelStats {
  let picks = 0;
  let wins = 0;
  let losses = 0;
  let pushes = 0;
  let profitFlat = 0;
  let stakedFlat = 0;

  for (const p of settled) {
    if (p.model_id !== modelId) continue;
    if (!passesActionFilter(p)) continue;
    // Only W/L/P count as picks — NO_ACTION rows (DNP, DQ, unsettleable)
    // would otherwise inflate the count vs the displayed record.
    if (p.result === 'WIN') wins++;
    else if (p.result === 'LOSS') losses++;
    else if (p.result === 'PUSH') pushes++;
    else continue;
    picks++;
    // Money only on a priced pick — see flatPnl. This is the Models-tab row
    // for every sport the full-outcome view does not grade (UFC/NHL/NBA/golf/
    // NFL/NCAAF), so it has to price exactly what v_public_track_record's
    // `other` branch prices, or the two tabs disagree on the same 8-5.
    const money = flatPnl(p);
    profitFlat += money.profit;
    stakedFlat += money.staked;
  }

  const decided = wins + losses;
  return {
    picks,
    wins,
    losses,
    pushes,
    winRate: decided > 0 ? wins / decided : 0,
    profitFlat,
    stakedFlat,
    roiFlat: stakedFlat > 0 ? profitFlat / stakedFlat : 0,
  };
}
