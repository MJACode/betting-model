import { useCallback, useEffect, useState } from 'react';

import type { ParlayLeg } from '@/lib/parlay';

/**
 * One-shot channel to seed the Parlay builder from another screen (Saved
 * Parlays → "Edit in builder"). The builder's custom legs live in ParlayScreen
 * session state, so they can't be passed as route params cleanly; this tiny
 * module store (same listener pattern as useParlaySlip) hands them over.
 *
 * `pickIds` are real DB pick_ids to push into the parlay slip (they re-resolve
 * against today's picks); `customLegs` are reconstructed custom/stale legs to
 * seed directly into the builder.
 */

export interface ParlayRestorePayload {
  pickIds: number[];
  customLegs: ParlayLeg[];
}

const listeners = new Set<(p: ParlayRestorePayload | null) => void>();
let cached: ParlayRestorePayload | null = null;

/** Stage a restore payload. ParlayScreen consumes it on its next render. */
export function setParlayRestore(payload: ParlayRestorePayload) {
  cached = payload;
  listeners.forEach((fn) => fn(payload));
}

export function useParlayRestore() {
  const [pending, setPending] = useState<ParlayRestorePayload | null>(cached);

  useEffect(() => {
    const listener = (p: ParlayRestorePayload | null) => setPending(p);
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, []);

  const consume = useCallback(() => {
    cached = null;
    listeners.forEach((fn) => fn(null));
  }, []);

  return { pending, consume };
}
