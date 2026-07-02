/**
 * Per-day, per-model results aggregation for the "Yesterday's results" recap.
 *
 * Pure (no React / Supabase) so it's unit-testable. Grades a single day's
 * SETTLED BET picks at the CURRENT action thresholds — the same flat-ROI /
 * W-L-P logic the Models tab uses (computeBuiltInModelStats). For recent days
 * this matches the full-outcome view (yesterday's BET picks were generated under
 * today's server-driven thresholds), without needing a per-day DB view.
 */
import { passesActionFilter } from '@/lib/thresholds';
import type { Pick } from '@/types';
import type { CustomModelStats } from '@/hooks/useCustomModelStats';

export interface ModelDayStats extends CustomModelStats {
  modelId: string;
}

export interface SportDayBreakdown {
  sport: string;
  total: CustomModelStats;
  models: ModelDayStats[];
}

export interface DailyResults {
  date: string;
  overall: CustomModelStats;
  sports: SportDayBreakdown[];
  /** BET picks that cleared the current cut but have no W/L/P yet (result NULL —
   *  a prop whose player DNP, or a game not settled at fetch time). Surfaced so
   *  the recap reconciles with the number of picks the user actually placed. */
  pending: number;
  /** The individual graded (WIN/LOSS/PUSH) picks behind the record, sorted by
   *  sport order then profit desc, so the recap can list what was actually bet. */
  gradedPicks: Pick[];
}

/** Earliest day the recap can show — paper-trading evaluation start. */
export const RESULTS_MIN_DATE = '2026-04-14';

export function emptyDailyResults(date: string): DailyResults {
  return { date, overall: EMPTY_DAILY, sports: [], pending: 0, gradedPicks: [] };
}

// Preferred sport ordering — mirrors TrackRecordScreen's selector order.
const SPORT_ORDER: Record<string, number> = {
  MLB: 0,
  WNBA: 1,
  NBA: 2,
  UFC: 3,
  NHL: 4,
  GOLF: 5,
};

interface Acc {
  wins: number;
  losses: number;
  pushes: number;
  profitFlat: number;
  stakedFlat: number;
}

function emptyAcc(): Acc {
  return { wins: 0, losses: 0, pushes: 0, profitFlat: 0, stakedFlat: 0 };
}

/** Caller guarantees p.result is WIN / LOSS / PUSH. Each settled pick stakes
 *  $100 flat — pushes count toward staked (matches computeBuiltInModelStats). */
function tally(acc: Acc, p: Pick): void {
  if (p.result === 'WIN') acc.wins++;
  else if (p.result === 'LOSS') acc.losses++;
  else acc.pushes++; // PUSH
  acc.profitFlat += Number(p.profit_flat ?? 0);
  acc.stakedFlat += 100;
}

function finalize(acc: Acc): CustomModelStats {
  const decided = acc.wins + acc.losses;
  return {
    picks: acc.wins + acc.losses + acc.pushes,
    wins: acc.wins,
    losses: acc.losses,
    pushes: acc.pushes,
    winRate: decided > 0 ? acc.wins / decided : 0,
    profitFlat: acc.profitFlat,
    stakedFlat: acc.stakedFlat,
    roiFlat: acc.stakedFlat > 0 ? acc.profitFlat / acc.stakedFlat : 0,
  };
}

export const EMPTY_DAILY: CustomModelStats = {
  picks: 0,
  wins: 0,
  losses: 0,
  pushes: 0,
  winRate: 0,
  profitFlat: 0,
  stakedFlat: 0,
  roiFlat: 0,
};

/**
 * Group a day's picks into overall + per-sport + per-model records.
 * Only settled (WIN/LOSS/PUSH) BET picks that pass the current action filter
 * count toward the record; NO_ACTION rows, off-date rows, live picks, and
 * sub-threshold picks are excluded. BET picks awaiting a result (result NULL)
 * are tallied separately as `pending`. Models/sports with zero graded picks are
 * dropped. Accepts settled-only OR all-of-day picks (pending is 0 in the former).
 */
export function computeDailyResults(date: string, dayPicks: Pick[]): DailyResults {
  const overall = emptyAcc();
  const bySport = new Map<string, Acc>();
  const byModel = new Map<string, { sport: string; acc: Acc }>();
  const gradedPicks: Pick[] = [];
  let pending = 0;

  for (const p of dayPicks) {
    if (p.game_date !== date) continue;
    if (p.is_live) continue; // pre-game board only
    if (!passesActionFilter(p)) continue; // BET-only, meets current cut
    if (p.result !== 'WIN' && p.result !== 'LOSS' && p.result !== 'PUSH') {
      if (p.result == null) pending++; // placed, not yet graded
      continue;
    }

    gradedPicks.push(p);
    tally(overall, p);

    let sAcc = bySport.get(p.sport);
    if (!sAcc) {
      sAcc = emptyAcc();
      bySport.set(p.sport, sAcc);
    }
    tally(sAcc, p);

    let mEntry = byModel.get(p.model_id);
    if (!mEntry) {
      mEntry = { sport: p.sport, acc: emptyAcc() };
      byModel.set(p.model_id, mEntry);
    }
    tally(mEntry.acc, p);
  }

  // Per-model rows grouped under their sport.
  const modelsBySport = new Map<string, ModelDayStats[]>();
  for (const [modelId, { sport, acc }] of byModel) {
    const stats = finalize(acc);
    if (stats.picks === 0) continue;
    const arr = modelsBySport.get(sport) ?? [];
    arr.push({ modelId, ...stats });
    modelsBySport.set(sport, arr);
  }

  const sports: SportDayBreakdown[] = [];
  for (const [sport, acc] of bySport) {
    const total = finalize(acc);
    if (total.picks === 0) continue;
    const models = (modelsBySport.get(sport) ?? []).sort(
      (a, b) => b.profitFlat - a.profitFlat,
    );
    sports.push({ sport, total, models });
  }
  sports.sort(
    (a, b) =>
      (SPORT_ORDER[a.sport] ?? 99) - (SPORT_ORDER[b.sport] ?? 99) ||
      a.sport.localeCompare(b.sport),
  );

  gradedPicks.sort(
    (a, b) =>
      (SPORT_ORDER[a.sport] ?? 99) - (SPORT_ORDER[b.sport] ?? 99) ||
      a.sport.localeCompare(b.sport) ||
      Number(b.profit_flat ?? 0) - Number(a.profit_flat ?? 0),
  );

  return { date, overall: finalize(overall), sports, pending, gradedPicks };
}
