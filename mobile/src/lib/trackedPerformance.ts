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
 * P&L convention matches the rest of the app (Track Record / daily recap):
 * profit_flat is dollars at a $100 flat stake per bet. We surface it with an
 * explicit "$100 flat per bet" caption since we don't know the user's real
 * stake — the record and ROI are the honest signal.
 */
import type { Pick } from '@/types';

export type TrackedBetStatus = 'open' | 'won' | 'lost' | 'push' | 'no_action';

export interface TrackedBetRow {
  pick: Pick;
  status: TrackedBetStatus;
  /** Dollars at a $100 flat stake. 0 unless status is won/lost/push. */
  profit: number;
}

export interface TrackedBetSummary {
  /** Net dollars at $100 flat per settled bet. */
  net: number;
  wins: number;
  losses: number;
  pushes: number;
  /** Awaiting a result (result NULL). */
  open: number;
  /** wins + losses + pushes. */
  settled: number;
  /** Net / (settled × $100); null until something settles. */
  roi: number | null;
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
): { rows: TrackedBetRow[]; summary: TrackedBetSummary } {
  const tracked = new Set(trackedIds);
  const rows: TrackedBetRow[] = [];
  let net = 0;
  let wins = 0;
  let losses = 0;
  let pushes = 0;
  let open = 0;

  const seen = new Set<number>();
  for (const p of picks) {
    if (!tracked.has(p.pick_id) || seen.has(p.pick_id)) continue;
    seen.add(p.pick_id);
    const status = trackedBetStatus(p);
    const profit =
      status === 'won' || status === 'lost' || status === 'push'
        ? Number(p.profit_flat ?? 0)
        : 0;
    if (status === 'won') wins++;
    else if (status === 'lost') losses++;
    else if (status === 'push') pushes++;
    else if (status === 'open') open++;
    net += profit;
    rows.push({ pick: p, status, profit });
  }

  rows.sort((a, b) => {
    const aOpen = a.status === 'open' ? 0 : 1;
    const bOpen = b.status === 'open' ? 0 : 1;
    if (aOpen !== bOpen) return aOpen - bOpen;
    // Open: soonest game first. Settled/no-action: newest first.
    return aOpen === 0
      ? a.pick.game_date.localeCompare(b.pick.game_date)
      : b.pick.game_date.localeCompare(a.pick.game_date);
  });

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
      roi: settled > 0 ? net / (settled * 100) : null,
    },
  };
}
