import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

/**
 * The member's betting STATE — the US state their sportsbook accounts are
 * licensed in.
 *
 * Why the app needs it (2026-09-04): the betslip links our odds feed carries
 * for three books are TEMPLATES, not URLs —
 *
 *   BetMGM     https://sports.{state}.betmgm.com/en/sports?options=...
 *   BetRivers  https://{state}.betrivers.com/?page=sportsbook#event/...
 *   Caesars    https://sportsbook.caesars.com/us/{state}/bet/betslip?...
 *
 * — and the app was opening them verbatim. `{state}` is not a host, so the
 * open failed and the fallback took the member to the book's web root instead
 * of its app with the bet on the slip. Matt: "I tried to place a parlay with
 * mgm but it didn't open my mgm app like it does for DK." DraftKings' links
 * carry no placeholder, which is why DraftKings worked.
 *
 * Filled in, those are the books' own universal links, and iOS routes a
 * universal link opened from another app to the installed app — the same
 * mechanism DraftKings' links use. Nothing is guessed: with no state set the
 * link is left unopened and the member is told what to set.
 *
 * Same module-store + listeners pattern as usePreferredBooks. Stored on this
 * device only; never sent anywhere. `getBettingState()` is the synchronous
 * read for lib code that cannot use a hook (sportsbookLinks.ts).
 */

/** US jurisdictions with legal online sportsbooks, as the books spell them in
 *  their own URLs (lower-case two-letter codes). */
export const BETTING_STATES: { code: string; name: string }[] = [
  { code: 'az', name: 'Arizona' },
  { code: 'co', name: 'Colorado' },
  { code: 'ct', name: 'Connecticut' },
  { code: 'dc', name: 'Washington, D.C.' },
  { code: 'il', name: 'Illinois' },
  { code: 'in', name: 'Indiana' },
  { code: 'ia', name: 'Iowa' },
  { code: 'ks', name: 'Kansas' },
  { code: 'ky', name: 'Kentucky' },
  { code: 'la', name: 'Louisiana' },
  { code: 'me', name: 'Maine' },
  { code: 'md', name: 'Maryland' },
  { code: 'ma', name: 'Massachusetts' },
  { code: 'mi', name: 'Michigan' },
  { code: 'nv', name: 'Nevada' },
  { code: 'nh', name: 'New Hampshire' },
  { code: 'nj', name: 'New Jersey' },
  { code: 'ny', name: 'New York' },
  { code: 'nc', name: 'North Carolina' },
  { code: 'oh', name: 'Ohio' },
  { code: 'or', name: 'Oregon' },
  { code: 'pa', name: 'Pennsylvania' },
  { code: 'tn', name: 'Tennessee' },
  { code: 'vt', name: 'Vermont' },
  { code: 'va', name: 'Virginia' },
  { code: 'wv', name: 'West Virginia' },
  { code: 'wy', name: 'Wyoming' },
];

const STORAGE_KEY = 'betting.state';

const listeners = new Set<(s: string | null) => void>();
let cached: string | null | undefined; // undefined = not read yet

export function isBettingState(v: unknown): v is string {
  return typeof v === 'string' && BETTING_STATES.some((s) => s.code === v);
}

export function bettingStateName(code: string | null): string | null {
  return BETTING_STATES.find((s) => s.code === code)?.name ?? null;
}

async function load(): Promise<string | null> {
  if (cached !== undefined) return cached;
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    cached = isBettingState(raw) ? raw : null;
  } catch {
    cached = null;
  }
  return cached;
}

async function save(v: string | null) {
  const next = isBettingState(v) ? v : null;
  cached = next;
  listeners.forEach((fn) => fn(next));
  try {
    if (next) await AsyncStorage.setItem(STORAGE_KEY, next);
    else await AsyncStorage.removeItem(STORAGE_KEY);
  } catch (err) {
    console.warn('[bettingState] save failed', err);
  }
}

/** Synchronous read for lib code. Null until storage has answered or when
 *  nothing is set — callers must treat both the same: "not set". */
export function getBettingState(): string | null {
  if (cached === undefined) {
    // Kick the read so the next call has it; this one answers "not set".
    void load();
    return null;
  }
  return cached;
}

export function useBettingState() {
  const [state, setStateValue] = useState<string | null>(cached ?? null);
  const [ready, setReady] = useState<boolean>(cached !== undefined);

  useEffect(() => {
    let mounted = true;
    load().then((v) => {
      if (!mounted) return;
      setStateValue(v);
      setReady(true);
    });
    const listener = (v: string | null) => setStateValue(v);
    listeners.add(listener);
    return () => {
      mounted = false;
      listeners.delete(listener);
    };
  }, []);

  const setState = useCallback((v: string | null) => {
    save(v).catch((err) => console.warn('[bettingState] set failed', err));
  }, []);

  return { state, name: bettingStateName(state), setState, ready };
}
