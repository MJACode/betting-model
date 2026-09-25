import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

import {
  BANKROLL_DEFAULTS,
  readBankroll,
  sanitizeUnitPct,
  writeBankroll,
  type BankrollSettings,
} from '@/lib/bankroll';

/**
 * The optional, display-only bankroll (lib/bankroll.ts): the amount and the
 * unit %, on this device under `bankroll.v2`. Module store + AsyncStorage,
 * same pattern as useResponsibleGambling. Nothing sizes a bet off it.
 */
const listeners = new Set<(s: BankrollSettings) => void>();
let cached: BankrollSettings | null = null;

async function load(): Promise<BankrollSettings> {
  if (cached) return cached;
  cached = await readBankroll(AsyncStorage);
  return cached;
}

function persist(next: BankrollSettings) {
  cached = next;
  listeners.forEach((fn) => fn(next));
  writeBankroll(AsyncStorage, next).catch((err) => console.warn('[bankroll] save failed', err));
}

export function useBankroll() {
  const [settings, setSettings] = useState<BankrollSettings>(cached ?? BANKROLL_DEFAULTS);
  const [ready, setReady] = useState<boolean>(cached != null);

  useEffect(() => {
    let mounted = true;
    load().then((s) => {
      if (!mounted) return;
      setSettings(s);
      setReady(true);
    });
    const listener = (s: BankrollSettings) => setSettings(s);
    listeners.add(listener);
    return () => {
      mounted = false;
      listeners.delete(listener);
    };
  }, []);

  /** A validated amount, or null to clear it. The field never passes an invalid one. */
  const setAmount = useCallback((amount: number | null) => {
    // After load, so an edit in the first frame cannot overwrite the stored
    // unit % with the default.
    void load().then((base) => persist({ ...base, amount }));
  }, []);

  const setUnitPct = useCallback((pct: number) => {
    void load().then((base) => persist({ ...base, unitPct: sanitizeUnitPct(pct) }));
  }, []);

  return { settings, ready, setAmount, setUnitPct };
}
