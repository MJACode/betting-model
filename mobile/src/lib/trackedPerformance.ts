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
 * result NULL → open, NO_ACTION → shown but excluded from the record. A VOID
 * (condition_status 'VOID', result NO_ACTION as its marker) is 'not_graded':
 * a Discord-published VOID stays trackable (openForAction) but never grades.
 *
 * Units: the caller supplies each bet's stake (`stakeFor`, built by
 * lib/trackedStake). By default that is the POSTED stake, the one the Record
 * tab books (postedPickUnits): 1u to win at the price the pick was decided
 * at, risk capped at 3u, a pick with no price at 1u. A member can set their
 * own stake per bet instead. This file only applies the result: a win pays
 * `win`, a loss costs `risk`, and a push, a void or an ungraded pick risks
 * nothing. It never reads profit_flat, which is 1u risked and invents −110
 * for a pick with no price.
 *
 * Every figure stays at the 100-is-1u scale (lib/format FLAT_UNIT); screens
 * print it as units with `formatFlatUnits`, never as dollars. No value
 * imports on purpose: a node test loads this file with type stripping.
 */
import type { Pick } from '@/types';

/** What one tracked bet risks and what a win pays, at the 100-is-1u scale. */
export interface TrackedStake {
  risk: number;
  win: number;
  /** True when the member set this stake, false when it is the posted one. */
  custom: boolean;
}

export type TrackedStakeFor = (p: Pick) => TrackedStake;

export type TrackedBetStatus = 'open' | 'won' | 'lost' | 'push' | 'no_action' | 'not_graded';

export interface TrackedBetRow {
  pick: Pick;
  status: TrackedBetStatus;
  /** What this bet risks, at the 100-is-1u scale. */
  stake: number;
  /** True when the member set the stake; false when it is the posted stake. */
  customStake: boolean;
  /** Won or lost at `stake`, same scale. 0 unless status is won/lost. */
  profit: number;
}

export interface TrackedBetSummary {
  /** Net across settled bets at their stakes (100-is-1u scale). */
  net: number;
  wins: number;
  losses: number;
  pushes: number;
  /** Awaiting a result (result NULL). */
  open: number;
  /** wins + losses + pushes. */
  settled: number;
  /** Risked on won and lost bets (a push risks nothing), same scale. */
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

function finite(n: number): number {
  return Number.isFinite(n) && n >= 0 ? n : 0;
}

/**
 * One bet's result at its stake. A win pays `win`, a loss costs `risk`; a
 * push, a void and an open bet risk nothing, as postedPickUnits counts them.
 */
export function gradeTrackedBet(
  status: TrackedBetStatus,
  stake: TrackedStake,
): { profit: number; risked: number } {
  const risk = finite(stake.risk);
  const win = finite(stake.win);
  const cents = (n: number) => Math.round(n * 100) / 100;
  if (status === 'won') return { profit: cents(win), risked: risk };
  if (status === 'lost') return { profit: -cents(risk), risked: risk };
  return { profit: 0, risked: 0 };
}

export function trackedBetStatus(p: Pick): TrackedBetStatus {
  // Before the result switch: a VOID's NO_ACTION is its marker, not a
  // settlement, so "No action" on a fight hours away read as scratched.
  if (p.condition_status === 'VOID') return 'not_graded';
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
 * settled newest-first. `stakeFor` has no default on purpose: a hidden
 * default is how a second unit basis survived here.
 */
export function computeTrackedResults(
  trackedIds: number[],
  picks: Pick[],
  stakeFor: TrackedStakeFor,
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
    const stake = stakeFor(p);
    const { profit, risked } = gradeTrackedBet(status, stake);
    if (status === 'won') wins++;
    else if (status === 'lost') losses++;
    else if (status === 'push') pushes++;
    else if (status === 'open') open++;
    staked += risked;
    net += profit;
    rows.push({ pick: p, status, stake: finite(stake.risk), customStake: stake.custom, profit });
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
