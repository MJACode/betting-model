/**
 * Grading for tracked LIVE (in-play) bets on the Performance tab.
 *
 * Pure (no React / Supabase) so it's unit-testable — see
 * scripts/verify_live_tracked.ts.
 *
 * A live bet is tracked by its stable proposition key (game|model|side), not
 * pick_id, because live picks are delete+rescored every pass. To grade one we
 * look at the live picks that currently exist for its game and resolve the row
 * for that exact (game, model, side):
 *
 *   - a SETTLED live pick exists for the side  → grade it (the model's final
 *     pick on that side, at the price it settled). WIN/LOSS/PUSH count.
 *   - only an unsettled live pick exists       → open (game in progress).
 *   - no live pick for the side AND game final → the model moved off this side
 *     before the close, so there is no model-final result → shown as no_action
 *     (excluded from the record). Rendered from the tracked snapshot.
 *   - no live pick and game not final          → open (rendered from snapshot).
 *
 * P&L convention matches trackedPerformance: profit_flat is dollars at a $100
 * flat stake, so a bet at stake S grades as profit_flat x S/100.
 */
import type { Pick } from '@/types';
import type { LiveTrackSnapshot } from '@/hooks/useTrackedBets';
import {
  trackedBetStatus,
  type TrackedBetRow,
  type TrackedBetSummary,
} from './trackedPerformance';

function keyOf(p: Pick): string {
  return `${p.game_id}|${p.model_id}|${p.pick_side}`;
}

/** Deterministic negative pick_id for a snapshot-only row (no live pick row). */
function synthPickId(key: string): number {
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) | 0;
  return -(Math.abs(h) + 1);
}

/** Minimal Pick built from a snapshot so a row renders without a live pick row. */
function synthPick(s: LiveTrackSnapshot): Pick {
  return {
    pick_id: synthPickId(s.key),
    game_id: s.game_id,
    model_id: s.model_id,
    sport: s.sport,
    game_date: s.game_date,
    pick_side: s.pick_side,
    pick_label: s.pick_label,
    dk_odds: s.dk_odds,
    scored_line: s.scored_line,
    kelly_fraction: 0,
    result: null,
    profit_flat: null,
    is_live: true,
  } as unknown as Pick;
}

/**
 * Grade tracked live bets. `livePicks` is every is_live pick row for the
 * tracked games (settled + unsettled). `isGameFinal(gameId)` distinguishes an
 * in-progress game from one that has ended (final score in).
 */
export function computeLiveTrackedResults(
  snapshots: LiveTrackSnapshot[],
  livePicks: Pick[],
  isGameFinal: (gameId: string) => boolean,
  stakeFor: (p: Pick) => number = () => 100,
): { rows: TrackedBetRow[]; summary: TrackedBetSummary } {
  const byKey = new Map<string, Pick[]>();
  for (const p of livePicks) {
    const k = keyOf(p);
    const arr = byKey.get(k);
    if (arr) arr.push(p);
    else byKey.set(k, [p]);
  }

  const rows: TrackedBetRow[] = [];
  let net = 0;
  let staked = 0;
  let wins = 0;
  let losses = 0;
  let pushes = 0;
  let open = 0;

  const seen = new Set<string>();
  for (const s of snapshots) {
    if (seen.has(s.key)) continue;
    seen.add(s.key);

    const matching = byKey.get(s.key) ?? [];
    // Prefer a graded row (WIN/LOSS/PUSH), then any settled (NO_ACTION), then
    // the latest unsettled one for display.
    const graded = matching.find(
      (p) => p.result === 'WIN' || p.result === 'LOSS' || p.result === 'PUSH',
    );
    const settled = graded ?? matching.find((p) => p.result != null);
    const openPick = matching
      .filter((p) => p.result == null)
      .sort((a, b) => b.pick_id - a.pick_id)[0];

    let pick: Pick;
    let status: TrackedBetRow['status'];
    if (settled) {
      pick = settled;
      status = trackedBetStatus(settled);
    } else if (openPick) {
      pick = openPick;
      status = 'open';
    } else {
      // No live pick row for this side. If the game is over, the model moved
      // off this side before the close — no model-final result.
      pick = synthPick(s);
      status = isGameFinal(s.game_id) ? 'no_action' : 'open';
    }

    const rawStake = stakeFor(pick);
    const stake = Number.isFinite(rawStake) && rawStake >= 0 ? rawStake : 0;
    const isCounted = status === 'won' || status === 'lost' || status === 'push';
    const profit = isCounted ? Math.round(Number(pick.profit_flat ?? 0) * stake) / 100 : 0;

    if (status === 'won') wins++;
    else if (status === 'lost') losses++;
    else if (status === 'push') pushes++;
    else if (status === 'open') open++;
    if (isCounted) staked += stake;
    net += profit;

    rows.push({ pick, status, stake, profit });
  }

  const settled = wins + losses + pushes;
  return {
    rows,
    summary: { net, wins, losses, pushes, open, settled, staked, roi: staked > 0 ? net / staked : null },
  };
}
