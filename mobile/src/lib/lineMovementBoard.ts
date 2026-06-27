/**
 * Line Movement board — annotates today's live (locked) signals with how the DK
 * line has moved since we locked them.
 *
 * Now that picks lock (game markets at 7am, props at their first signal) they no
 * longer drop or churn, so the old "Dropped" view goes quiet. The useful question
 * becomes: *after we locked our number, which way did the line move?* — i.e. did
 * the market come to our side (we beat the close) or move against us. That's
 * exactly what the hourly line refresh feeds, and it's what this board surfaces.
 */
import { gameStatus } from './format';
import { movementFromLatest, type Movement } from './markets';
import type { EnrichedPick } from '@/types';

export type MovedSignal = EnrichedPick & { movement: Movement };

/**
 * Live signals whose DK line has moved meaningfully since we locked, biggest
 * move first. Movement is only meaningful pre-game (once the game starts the
 * closing line / CLV takes over), mirroring PickCard.
 */
export function movedSignals(live: EnrichedPick[]): MovedSignal[] {
  const out: MovedSignal[] = [];
  for (const p of live) {
    if (gameStatus(p.game).kind !== 'pre') continue;
    const m = movementFromLatest(p.pick, p.latestOdds);
    if (m) out.push({ ...p, movement: m });
  }
  // Rank by price-shift magnitude; line-only moves (no priced shift) sort below.
  const mag = (m: Movement) => (m.priceShiftPp != null ? Math.abs(m.priceShiftPp) : 0.5);
  return out.sort((a, b) => mag(b.movement) - mag(a.movement));
}

/** Toward/against tally for the tab subtitle. `good` = market moved to our side. */
export function movementTally(moved: MovedSignal[]): { toward: number; against: number } {
  let toward = 0;
  let against = 0;
  for (const s of moved) {
    if (s.movement.severity === 'good') toward += 1;
    else against += 1; // caution (price against) or skip (line against)
  }
  return { toward, against };
}
