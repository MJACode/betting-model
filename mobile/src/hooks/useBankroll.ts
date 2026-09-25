import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

import {
  BANKROLL_DEFAULTS,
  createBankrollStore,
  sanitizeUnitPct,
  type BankrollSettings,
} from '@/lib/bankroll';

/**
 * The optional, display-only bankroll (lib/bankroll.ts): the amount and the
 * unit %, on this device under `bankroll.v2`. One module-level store, as in
 * useResponsibleGambling; its updates merge into the latest value and write
 * in order (createBankrollStore). Nothing sizes a bet off it.
 */
const store = createBankrollStore(AsyncStorage);

export function useBankroll() {
  const [settings, setSettings] = useState<BankrollSettings>(store.get() ?? BANKROLL_DEFAULTS);
  const [ready, setReady] = useState<boolean>(store.get() != null);

  useEffect(() => {
    let mounted = true;
    store.load().then((s) => {
      if (!mounted) return;
      setSettings(store.get() ?? s);
      setReady(true);
    });
    const unsubscribe = store.subscribe(setSettings);
    return () => {
      mounted = false;
      unsubscribe();
    };
  }, []);

  /** A validated amount, or null to clear it. The field never passes an invalid one. */
  const setAmount = useCallback((amount: number | null) => {
    void store.update({ amount });
  }, []);

  const setUnitPct = useCallback((pct: number) => {
    void store.update({ unitPct: sanitizeUnitPct(pct) });
  }, []);

  return { settings, ready, setAmount, setUnitPct };
}
