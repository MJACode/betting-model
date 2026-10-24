import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

import { lineLegsAfterAdd } from '@/lib/betslipGuard';
import { EMPTY_INJURY_INDEX } from '@/lib/injuryStatus';
import { injuryIndexForSport } from '@/lib/injuryLookup';
import { isGameSpec, lineLegKey, type LineLegSpec } from '@/lib/lineLegs';

/**
 * The betslip's LINE legs — Stats-board lines the user asked to add (Matt,
 * 2026-09-04: "it should ask you if you want to add to bet slip"). Sibling of
 * useParlaySlip, same module-store + listeners pattern, separate storage:
 * a pick leg is a stable KEY resolved against today's picks, a line leg has
 * no pick to resolve against, so the whole SPEC is stored and re-priced from
 * the latest lines on read (lib/lineLegs.ts). Ordered by insertion.
 *
 * A sidelined player is not inserted (Matt, 2026-10-24). The add reads the
 * same injury index the Stats board does and admits the spec through
 * lineLegsAfterAdd. A rejection is a no-op: the caller toasts only when this
 * returns true. A game line has no player and is not looked up.
 */

const STORAGE_KEY = 'betslip.lineLegs.v1';

const listeners = new Set<(specs: LineLegSpec[]) => void>();
let cached: LineLegSpec[] | null = null;

function isSpec(v: unknown): v is LineLegSpec {
  if (!v || typeof v !== 'object') return false;
  const s = v as Record<string, unknown>;
  if (typeof s.game_id !== 'string' || typeof s.sport !== 'string') return false;
  if (s.kind === 'game') {
    // A Teams-board line (2026-09-05): a team's moneyline, spread or the total.
    return (
      (s.market === 'h2h' || s.market === 'spreads' || s.market === 'totals') &&
      typeof s.team === 'string' &&
      typeof s.opponent === 'string' &&
      typeof s.isHome === 'boolean' &&
      (s.line === null || typeof s.line === 'number') &&
      (s.side === null || s.side === 'over' || s.side === 'under')
    );
  }
  return (
    typeof s.market === 'string' &&
    typeof s.player_name === 'string' &&
    typeof s.line === 'number' &&
    (s.side === 'over' || s.side === 'under') &&
    typeof s.statLabel === 'string'
  );
}

function sanitize(raw: unknown): LineLegSpec[] {
  if (!Array.isArray(raw)) return [];
  const seen = new Set<string>();
  const out: LineLegSpec[] = [];
  for (const v of raw) {
    if (!isSpec(v)) continue;
    const k = lineLegKey(v);
    if (seen.has(k)) continue;
    seen.add(k);
    out.push(isGameSpec(v) ? v : { ...v, team: typeof v.team === 'string' ? v.team : null });
  }
  return out;
}

async function load(): Promise<LineLegSpec[]> {
  if (cached) return cached;
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    cached = raw ? sanitize(JSON.parse(raw)) : [];
  } catch {
    cached = [];
  }
  return cached;
}

async function save(specs: LineLegSpec[]) {
  cached = specs;
  listeners.forEach((fn) => fn(specs));
  try {
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(specs));
  } catch (err) {
    console.warn('[lineLegs] save failed', err);
  }
}

/** Account deletion. Clears line legs (`betslip.lineLegs.v1`). */
export async function clearLineLegsForAccountDeletion(): Promise<void> {
  cached = [];
  listeners.forEach((fn) => fn([]));
  await AsyncStorage.removeItem(STORAGE_KEY);
}

export function useLineLegs() {
  const [specs, setSpecs] = useState<LineLegSpec[]>(cached ?? []);
  const [ready, setReady] = useState<boolean>(cached != null);

  useEffect(() => {
    let mounted = true;
    load().then((v) => {
      if (!mounted) return;
      setSpecs(v);
      setReady(true);
    });
    const listener = (v: LineLegSpec[]) => setSpecs(v);
    listeners.add(listener);
    return () => {
      mounted = false;
      listeners.delete(listener);
    };
  }, []);

  const has = useCallback(
    (key: string) => (cached ?? specs).some((s) => lineLegKey(s) === key),
    [specs],
  );

  const add = useCallback((spec: LineLegSpec): Promise<boolean> => {
    return (async () => {
      // The read happens before the list is touched. A game line has no player.
      const index = isGameSpec(spec) ? EMPTY_INJURY_INDEX : await injuryIndexForSport(spec.sport);
      // No await between this read of `cached` and `save` assigning it, so two
      // adds cannot each snapshot the list and drop the other.
      const next = lineLegsAfterAdd(cached ?? [], spec, index);
      if (!next) return false;
      await save(next);
      return true;
    })();
  }, []);

  const remove = useCallback((key: string) => {
    const cur = cached ?? [];
    if (!cur.some((s) => lineLegKey(s) === key)) return;
    save(cur.filter((s) => lineLegKey(s) !== key)).catch((err) =>
      console.warn('[lineLegs] remove failed', err),
    );
  }, []);

  const clear = useCallback(() => {
    save([]).catch((err) => console.warn('[lineLegs] clear failed', err));
  }, []);

  return { specs, count: specs.length, ready, has, add, remove, clear };
}
