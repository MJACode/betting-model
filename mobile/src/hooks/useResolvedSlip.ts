import { useEffect, useMemo, useRef, useState } from 'react';

import { useLineLegs } from '@/hooks/useLineLegs';
import { useParlaySlip } from '@/hooks/useParlaySlip';
import { useTodayPicks } from '@/hooks/useTodayPicks';
import { lineLegFromRows, lineLegKey, type LineLegSpec } from '@/lib/lineLegs';
import { canPruneSlip, resolveSlipLegs, type ParlayLeg } from '@/lib/parlay';
import { fetchGameById, fetchPropLineRows } from '@/lib/queries';
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
 *
 * LINE LEGS (2026-09-04, lib/lineLegs.ts) resolve the same way from their own
 * store: each spec re-reads that player's latest lines and re-prices; a spec
 * whose read SUCCEEDED and priced nothing (game started, line pulled) is
 * pruned, a spec whose read failed is held — same rule as pick keys. They
 * follow the pick legs in slip order.
 */
export function useResolvedSlip() {
  const slip = useParlaySlip();
  const lineLegs = useLineLegs();
  const picks = useTodayPicks();
  const { data, loading, error } = picks;

  const { legs: pickLegs, missingKeys } = useMemo(
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

  // ── line legs: re-price each spec from the latest lines ────────────────────
  const [priced, setPriced] = useState<Map<string, ParlayLeg | null>>(new Map());
  const [failedLineKeys, setFailedLineKeys] = useState<string[]>([]);
  const [lineLoading, setLineLoading] = useState(false);
  const specsKey = lineLegs.specs.map(lineLegKey).join('\n');

  useEffect(() => {
    if (!lineLegs.ready) return;
    const specs = lineLegs.specs;
    if (specs.length === 0) {
      setPriced(new Map());
      setFailedLineKeys([]);
      setLineLoading(false);
      return;
    }
    let alive = true;
    setLineLoading(true);
    Promise.all(
      specs.map(async (spec): Promise<[string, ParlayLeg | null | undefined]> => {
        const key = lineLegKey(spec);
        try {
          const [rows, game] = await Promise.all([
            fetchPropLineRows(spec.game_id, spec.market, spec.player_name),
            fetchGameById(spec.game_id).catch(() => null),
          ]);
          return [key, lineLegFromRows(spec, rows, game)];
        } catch {
          return [key, undefined]; // read failed: hold, never prune
        }
      }),
    ).then((entries) => {
      if (!alive) return;
      const next = new Map<string, ParlayLeg | null>();
      const failed: string[] = [];
      for (const [key, leg] of entries) {
        if (leg === undefined) failed.push(key);
        else next.set(key, leg);
      }
      setPriced(next);
      // A read that failed is HELD (never pruned) but must not be invisible:
      // the bar and the header count it, so the screen's stale note has to
      // name it and offer the remove (UX review).
      setFailedLineKeys(failed);
      setLineLoading(false);
    });
    return () => {
      alive = false;
    };
    // specsKey stands in for the specs array identity: same keys, same work.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lineLegs.ready, specsKey]);

  // Prune specs the latest lines could not price (read succeeded, no row).
  useEffect(() => {
    if (lineLoading) return;
    const dead = lineLegs.specs.filter((s) => priced.get(lineLegKey(s)) === null);
    if (dead.length === 0) return;
    const fresh = dead.map(lineLegKey).filter((k) => !countedRef.current.has(k));
    dead.forEach((s) => {
      countedRef.current.add(lineLegKey(s));
      lineLegs.remove(lineLegKey(s));
    });
    if (fresh.length > 0) setRemoved((n) => n + fresh.length);
  }, [lineLoading, priced, lineLegs]);

  const legs = useMemo(() => {
    const out = [...pickLegs];
    for (const spec of lineLegs.specs) {
      const leg = priced.get(lineLegKey(spec));
      if (leg) out.push(leg);
    }
    return out;
  }, [pickLegs, lineLegs.specs, priced]);

  const count = slip.count + lineLegs.count;
  const ready = slip.ready && lineLegs.ready;

  return {
    slip,
    lineLegs,
    picks,
    legs,
    /** Every selection, pick keys and line legs alike. */
    count,
    /** Both stores read from storage. */
    ready,
    /** Keys we could not resolve but will not prune — the board is not
     *  trusted, or a line leg's read failed. `line:`-prefixed keys belong to
     *  the line-leg store. */
    stale: [...(boardKnown ? [] : missingKeys), ...failedLineKeys],
    /** How many selections were auto-removed this session. */
    removed,
    /** True while we genuinely cannot yet say what is in the slip. */
    resolving:
      !ready ||
      (loading && data.length === 0 && slip.count > 0) ||
      (lineLoading && lineLegs.count > 0 && priced.size === 0),
  };
}

export type ResolvedSlip = {
  legs: ParlayLeg[];
  stale: string[];
  removed: number;
  resolving: boolean;
};

export type { LineLegSpec };
