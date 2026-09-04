import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

import { lineLegKey, type LineLegSpec } from '@/lib/lineLegs';

/**
 * The betslip's LINE legs — Stats-board lines the user asked to add (Matt,
 * 2026-09-04: "it should ask you if you want to add to bet slip"). Sibling of
 * useParlaySlip, same module-store + listeners pattern, separate storage:
 * a pick leg is a stable KEY resolved against today's picks, a line leg has
 * no pick to resolve against, so the whole SPEC is stored and re-priced from
 * the latest lines on read (lib/lineLegs.ts). Ordered by insertion.
 */

const STORAGE_KEY = 'betslip.lineLegs.v1';

const listeners = new Set<(specs: LineLegSpec[]) => void>();
let cached: LineLegSpec[] | null = null;

function isSpec(v: unknown): v is LineLegSpec {
  if (!v || typeof v !== 'object') return false;
  const s = v as Record<string, unknown>;
  return (
    typeof s.game_id === 'string' &&
    typeof s.market === 'string' &&
    typeof s.player_name === 'string' &&
    typeof s.line === 'number' &&
    (s.side === 'over' || s.side === 'under') &&
    typeof s.statLabel === 'string' &&
    typeof s.sport === 'string'
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
    out.push({ ...v, team: typeof v.team === 'string' ? v.team : null });
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

  const add = useCallback((spec: LineLegSpec) => {
    const cur = cached ?? [];
    const key = lineLegKey(spec);
    if (cur.some((s) => lineLegKey(s) === key)) return;
    save([...cur, spec]).catch((err) => console.warn('[lineLegs] add failed', err));
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
