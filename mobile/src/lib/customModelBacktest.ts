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
import { flatPnl, isDuplicateCopy, isModelRetired, passesRecordFilter, postedPickUnits, publishedRecordKeeps } from './thresholds';
import type { CustomModel, CustomModelRule, SettledPick, SignalType } from '@/types';
import type { FullOutcomeRecord } from './queries';

/**
 * A model's (or a custom model's) graded set.
 *
 * `units` / `risked` / `roi` are what every screen shows, on ONE basis: the
 * published stake (CLAUDE.md §2; mike, 2026-11-03), 1u to win at
 * COALESCE(decision_odds, dk_odds), risk capped at 3u, a pick with no price at
 * the bare 1u. The same numbers the Record tab, Yesterday and Discord book
 * (postedPickUnits, published_pick_unit_profit / _risked).
 *
 * `profitFlat` / `stakedFlat` / `roiFlat` are the stored per-100, 1u-RISKED
 * figures. No screen prints them. They remain for the priced-pick count and
 * as the fallback a server answer without the posted columns falls back to.
 */
export interface CustomModelStats {
  picks: number;
  wins: number;
  losses: number;
  pushes: number;
  winRate: number; // wins / (wins + losses)
  profitFlat: number;
  stakedFlat: number;
  roiFlat: number;
  /** Units won or lost at the published stake. */
  units: number;
  /** Units laid at the published stake (graded wins and losses only). */
  risked: number;
  /** units / risked; 0 when nothing was risked. */
  roi: number;
  /**
   * False when a server half answered without the posted columns (the
   * custom_model_backtest_posted function not yet applied, or an older
   * v_public_track_record). units / risked then hold the 1u-risked figure.
   */
  postedKnown: boolean;
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
  units: 0,
  risked: 0,
  roi: 0,
  postedKnown: true,
};

/** Aggregate result of the custom_model_backtest RPC. units are 1u flat;
 *  roi_pct is over priced picks only (prob-only picks have no honest P&L).
 *  posted_units / posted_risked are custom_model_backtest_posted's answer
 *  over the same matched picks, on the published stake; absent until that
 *  function exists (data/migrations/custom_model_backtest_posted_2026_11_03.sql). */
export interface CustomBacktestSummary {
  bets: number;
  wins: number;
  losses: number;
  pushes: number;
  priced: number;
  units: number;
  roi_pct: number | null;
  posted_units?: number | null;
  posted_risked?: number | null;
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
  // The price the pick was DECIDED at (2026-09-09): the RPC cuts, filters
  // and grades at it (decide_on_best_price_2026_09_09.sql).
  decision_book: string | null;
  decision_odds: number | null;
  decision_edge: number | null;
}

/** One graded pick for display, whichever half it came from. `units` is the
 *  published stake's result (postedPickUnits): never profit_flat, which
 *  invents −110 on a pick with no price. */
export interface BacktestPickRow {
  pick_id: number;
  model_id: string;
  game_date: string;
  pick_label: string;
  signal_type: SignalType;
  result: string;
  units: number;
}

/**
 * The units and risk a set of graded picks books at the published stake.
 * `ownStake` reads each pick's stake_units (a built-in model, booked as
 * v_public_track_record books it). Without it every pick is the flat 1u to
 * win (a custom model is the member's own, and its server half, the
 * two-argument function, books it flat too).
 */
function postedTotals(picks: Iterable<{ kelly_fraction?: number | null; dk_odds?: number | null;
  decision_odds?: number | null; result?: string | null; stake_units?: number | null }>,
  ownStake: boolean): { units: number; risked: number } {
  let units = 0;
  let risked = 0;
  for (const p of picks) {
    const u = postedPickUnits(ownStake ? p : { ...p, stake_units: null });
    units += u.units;
    risked += u.risked;
  }
  return { units, risked };
}

/**
 * A published per-model record (v_public_track_record, shaped by
 * fetchPublishedModelRecord) as the stats the Models list and the model page
 * show. `units` / `risked` are the view's own posted-stake columns, the same
 * numbers the Record tab sums. Without them (an older view) `postedKnown` is
 * false and the caller recomputes from the settled picks.
 */
export function recordStatsFromPublished(rec: FullOutcomeRecord): CustomModelStats {
  const decided = rec.wins + rec.losses;
  const priced = rec.priced_bets ?? 0;
  const flatUnits = Number(rec.units ?? 0);
  const known = rec.posted_units != null && rec.posted_risked != null;
  const units = known ? Number(rec.posted_units) : flatUnits;
  const risked = known ? Number(rec.posted_risked) : priced;
  return {
    picks: rec.bets,
    wins: rec.wins,
    losses: rec.losses,
    pushes: rec.pushes,
    winRate: decided > 0 ? rec.wins / decided : 0,
    profitFlat: flatUnits * 100,
    stakedFlat: priced * 100,
    roiFlat: rec.roi_pct == null ? 0 : Number(rec.roi_pct) / 100,
    units,
    risked,
    roi: risked > 0 ? units / risked : 0,
    postedKnown: known,
  };
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
  // PostgREST can send NUMERIC as a string.
  const known = s.posted_units != null && s.posted_risked != null;
  const units = known ? Number(s.posted_units) : Number(s.units);
  const risked = known ? Number(s.posted_risked) : Number(s.priced);
  return {
    picks: s.bets,
    wins: s.wins,
    losses: s.losses,
    pushes: s.pushes,
    winRate: decided > 0 ? s.wins / decided : 0,
    profitFlat: s.units * 100,
    stakedFlat: s.priced * 100,
    roiFlat: s.priced > 0 ? s.units / s.priced : 0,
    units,
    risked,
    roi: risked > 0 ? units / risked : 0,
    postedKnown: known,
  };
}

/** Sum two backtest halves; ratios recomputed from the summed counters. */
export function mergeStats(a: CustomModelStats, b: CustomModelStats): CustomModelStats {
  const wins = a.wins + b.wins;
  const losses = a.losses + b.losses;
  const profitFlat = a.profitFlat + b.profitFlat;
  const stakedFlat = a.stakedFlat + b.stakedFlat;
  const units = a.units + b.units;
  const risked = a.risked + b.risked;
  return {
    picks: a.picks + b.picks,
    wins,
    losses,
    pushes: a.pushes + b.pushes,
    winRate: wins + losses > 0 ? wins / (wins + losses) : 0,
    profitFlat,
    stakedFlat,
    roiFlat: stakedFlat > 0 ? profitFlat / stakedFlat : 0,
    units,
    risked,
    roi: risked > 0 ? units / risked : 0,
    postedKnown: a.postedKnown && b.postedKnown,
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
  const counted: SettledPick[] = [];

  for (const p of settled) {
    if (!pickMatchesModel(p, model)) continue;
    // One bet stored under two game ids counts once (mike, 2026-10-09). The
    // labelled copy keeps its real result, so the W/L/P check below would
    // count it: skip it here, as passesRecordFilter does for built-in models.
    if (isDuplicateCopy(p)) continue;
    // Only W/L/P count as picks — NO_ACTION rows (DNP, DQ, unsettleable)
    // would otherwise inflate the count vs the displayed record.
    if (p.result === 'WIN') wins++;
    else if (p.result === 'LOSS') losses++;
    else if (p.result === 'PUSH') pushes++;
    else continue;
    picks++;
    counted.push(p);
    // Money only on a priced pick — see flatPnl. Matches the server half
    // (custom_model_backtest: profit_units NULL and priced=0 when dk_odds is
    // NULL), so the two halves mergeStats adds are priced on the same rule.
    const money = flatPnl(p);
    profitFlat += money.profit;
    stakedFlat += money.staked;
  }

  const decided = wins + losses;
  // The published stake's price math (an unpriced pick at 1u), at the flat
  // 1u to win: a custom model is the member's own, not the posted pick's
  // stake_units, and the server half books it the same way.
  const posted = postedTotals(counted, false);
  return {
    picks,
    wins,
    losses,
    pushes,
    winRate: decided > 0 ? wins / decided : 0,
    profitFlat,
    stakedFlat,
    roiFlat: stakedFlat > 0 ? profitFlat / stakedFlat : 0,
    units: posted.units,
    risked: posted.risked,
    roi: posted.risked > 0 ? posted.units / posted.risked : 0,
    postedKnown: true,
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
  const counted: SettledPick[] = [];

  for (const p of settled) {
    if (p.model_id !== modelId) continue;
    // AS POSTED, not re-cut (2026-09-12). This is the fallback behind the
    // detail screen's header tiles when the v_public_track_record fetch fails,
    // and that view no longer re-applies the cut. Re-cutting here made the
    // tiles read 0 picks for a paused model while the list directly below them
    // showed its settled bets. The custom-model callers keep passesActionFilter:
    // "what would this filter do" is a different question.
    if (!passesRecordFilter(p)) continue;
    // Discord still has the lock. An omitted or unknown stamp stays, so a
    // ledger outage does not zero the fallback behind the published view.
    if (!publishedRecordKeeps(p)) continue;
    // Only W/L/P count as picks — NO_ACTION rows (DNP, DQ, unsettleable)
    // would otherwise inflate the count vs the displayed record.
    if (p.result === 'WIN') wins++;
    else if (p.result === 'LOSS') losses++;
    else if (p.result === 'PUSH') pushes++;
    else continue;
    picks++;
    counted.push(p);
    // Money only on a priced pick — see flatPnl. This is the Models-tab row
    // for every sport the full-outcome view does not grade (UFC/NHL/NBA/golf/
    // NFL/NCAAF), so it has to price exactly what v_public_track_record's
    // `other` branch prices, or the two tabs disagree on the same 8-5.
    const money = flatPnl(p);
    profitFlat += money.profit;
    stakedFlat += money.staked;
  }

  const decided = wins + losses;
  // The published stake, as the Record tab books it (an unpriced pick at its
  // bare stake), each pick at its own stake_units when it carries one.
  const posted = postedTotals(counted, true);
  return {
    picks,
    wins,
    losses,
    pushes,
    winRate: decided > 0 ? wins / decided : 0,
    profitFlat,
    stakedFlat,
    roiFlat: stakedFlat > 0 ? profitFlat / stakedFlat : 0,
    units: posted.units,
    risked: posted.risked,
    roi: posted.risked > 0 ? posted.units / posted.risked : 0,
    postedKnown: true,
  };
}
