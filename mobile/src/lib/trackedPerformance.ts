/**
 * Tracked-bet scoring for the Performance tab.
 *
 * Pure (no React / Supabase) so it's unit-testable — see
 * scripts/verify_tracked_performance.ts.
 *
 * The user tracks a bet from a pick card (bell icon → useTrackedBets). The
 * tracked state is an on-device set of pick_ids; the picks themselves settle
 * server-side (paper_tracker writes result + profit_flat). Scoring a tracked
 * bet is therefore just grading its pick row: WIN/LOSS/PUSH → record + P&L,
 * result NULL → open, NO_ACTION → shown but excluded from the record.
 *
 * P&L convention: the server's profit_flat is dollars at a $100 flat stake,
 * so a bet at any stake S grades as profit_flat x S/100 (WIN scales the
 * payout, LOSS -100 becomes -S, PUSH stays 0). The caller chooses the stake
 * per bet via `stakeFor` — $100 flat (default), the pick's Kelly-sized bet,
 * or a user-entered custom amount (see useStakeSettings).
 */
import type { Pick } from '@/types';

export type TrackedBetStatus = 'open' | 'won' | 'lost' | 'push' | 'no_action';

export interface TrackedBetRow {
  pick: Pick;
  status: TrackedBetStatus;
  /** The stake this bet is scored at (dollars). */
  stake: number;
  /** Dollars at `stake`. 0 unless status is won/lost/push. */
  profit: number;
}

export interface TrackedBetSummary {
  /** Net dollars across settled bets at their stakes. */
  net: number;
  wins: number;
  losses: number;
  pushes: number;
  /** Awaiting a result (result NULL). */
  open: number;
  /** wins + losses + pushes. */
  settled: number;
  /** Total dollars staked on settled bets. */
  staked: number;
  /** Net / staked; null until something settles for a non-zero stake. */
  roi: number | null;
}

/** Row order: open first (soonest game first), then settled newest-first. */
export function sortTrackedRows(rows: TrackedBetRow[]): TrackedBetRow[] {
  return rows.sort((a, b) => {
    const aOpen = a.status === 'open' ? 0 : 1;
    const bOpen = b.status === 'open' ? 0 : 1;
    if (aOpen !== bOpen) return aOpen - bOpen;
    return aOpen === 0
      ? a.pick.game_date.localeCompare(b.pick.game_date)
      : b.pick.game_date.localeCompare(a.pick.game_date);
  });
}

/** Combine two tracked-bet summaries (e.g. non-live + live). */
export function mergeTrackedSummaries(
  a: TrackedBetSummary,
  b: TrackedBetSummary,
): TrackedBetSummary {
  const net = a.net + b.net;
  const staked = a.staked + b.staked;
  return {
    net,
    wins: a.wins + b.wins,
    losses: a.losses + b.losses,
    pushes: a.pushes + b.pushes,
    open: a.open + b.open,
    settled: a.settled + b.settled,
    staked,
    roi: staked > 0 ? net / staked : null,
  };
}

export function trackedBetStatus(p: Pick): TrackedBetStatus {
  switch (p.result) {
    case 'WIN':
      return 'won';
    case 'LOSS':
      return 'lost';
    case 'PUSH':
      return 'push';
    case 'NO_ACTION':
      return 'no_action';
    default:
      return 'open';
  }
}

/**
 * Grade the user's tracked bets. `trackedIds` is the on-device set of tracked
 * pick_ids; `picks` is whatever those ids resolved to in the picks table.
 * Ids with no matching pick (a pre-lock-era pick that was delete+rescored)
 * are dropped silently. Rows come back open-first (soonest game first), then
 * settled newest-first.
 */
export function computeTrackedResults(
  trackedIds: number[],
  picks: Pick[],
  stakeFor: (p: Pick) => number = () => 100,
): { rows: TrackedBetRow[]; summary: TrackedBetSummary } {
  const tracked = new Set(trackedIds);
  const rows: TrackedBetRow[] = [];
  let net = 0;
  let staked = 0;
  let wins = 0;
  let losses = 0;
  let pushes = 0;
  let open = 0;

  const seen = new Set<number>();
  for (const p of picks) {
    if (!tracked.has(p.pick_id) || seen.has(p.pick_id)) continue;
    seen.add(p.pick_id);
    const status = trackedBetStatus(p);
    const rawStake = stakeFor(p);
    const stake = Number.isFinite(rawStake) && rawStake >= 0 ? rawStake : 0;
    const isSettled = status === 'won' || status === 'lost' || status === 'push';
    const profit = isSettled
      ? Math.round(Number(p.profit_flat ?? 0) * stake) / 100
      : 0;
    if (status === 'won') wins++;
    else if (status === 'lost') losses++;
    else if (status === 'push') pushes++;
    else if (status === 'open') open++;
    if (isSettled) staked += stake;
    net += profit;
    rows.push({ pick: p, status, stake, profit });
  }

  sortTrackedRows(rows);

  const settled = wins + losses + pushes;
  return {
    rows,
    summary: {
      net,
      wins,
      losses,
      pushes,
      open,
      settled,
      staked,
      roi: staked > 0 ? net / staked : null,
    },
  };
}
