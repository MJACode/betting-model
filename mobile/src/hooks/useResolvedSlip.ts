import { useEffect, useMemo, useRef, useState } from 'react';

import { useParlaySlip } from '@/hooks/useParlaySlip';
import { useTodayPicks } from '@/hooks/useTodayPicks';
import { canPruneSlip, resolveSlipLegs, type ParlayLeg } from '@/lib/parlay';
import type { EnrichedPick } from '@/types';

/**
 * The betslip, resolved against today's board — and self-cleaning.
 *
 * The slip persists STABLE keys (game|model|player) so a selection survives the
 * hourly delete+rescore. The cost of that durability is that a key outlives the
 * pick it points at: once the game ends (the board drops finished games), the
 * market de-lists, or the pick goes prob-only, the key resolves to nothing.
 * Before this hook those keys sat in storage forever — the badge counted them
 * while no card anywhere read as selected, and the only way to clear them was a
 * note buried on the betslip screen.
 *
 * So a key that cannot resolve is REMOVED, not just flagged. The guard is what
 * makes that safe: we only prune against a board we know is good — the slip has
 * been read, the fetch finished, it did not error, and it came back non-empty.
 * A failed or still-loading fetch looks exactly like "none of your picks exist
 * any more", and pruning on it would silently wipe a real slip. When the board
 * is not trustworthy the keys are left alone and reported as `stale` instead.
 *
 * `removed` counts what was pruned this session, so a screen can say the legs
 * went away rather than just showing a shorter slip — restoring a saved parlay
 * from an earlier day would otherwise quietly lose half its legs.
 */
export function useResolvedSlip() {
  const slip = useParlaySlip();
  const picks = useTodayPicks();
  const { data, loading, error } = picks;

  const { legs, missingKeys } = useMemo(
    () => resolveSlipLegs(data, slip.keys),
    [data, slip.keys],
  );

  // A board we can trust to say a key is genuinely gone.
  const boardKnown = canPruneSlip({
    slipReady: slip.ready,
    loading,
    error,
    boardSize: data.length,
  });

  const [removed, setRemoved] = useState(0);
  // Guard against double-counting: the effect can re-run before the store
  // update lands, and the same key must not be tallied twice.
  const countedRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!boardKnown || missingKeys.length === 0) return;
    const fresh = missingKeys.filter((k) => !countedRef.current.has(k));
    missingKeys.forEach((k) => {
      countedRef.current.add(k);
      slip.remove(k);
    });
    if (fresh.length > 0) setRemoved((n) => n + fresh.length);
  }, [boardKnown, missingKeys, slip]);

  return {
    slip,
    picks,
    legs,
    /** Keys we could not resolve but will not prune — the board is not trusted. */
    stale: boardKnown ? [] : missingKeys,
    /** How many selections were auto-removed this session. */
    removed,
    /** True while we genuinely cannot yet say what is in the slip. */
    resolving: !slip.ready || (loading && data.length === 0 && slip.count > 0),
  };
}

export type ResolvedSlip = {
  legs: ParlayLeg[];
  stale: string[];
  removed: number;
  resolving: boolean;
  picks: { data: EnrichedPick[]; loading: boolean; error: string | null; refresh: () => void };
};
