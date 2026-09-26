import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

import {
  BANKROLL_DEFAULTS,
  createBankrollStore,
  stepUnitPct,
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

  /** Lower (−1) / Raise (+1), stepped inside the store from the LATEST stored
   *  %, so a tap before the first read lands can't step the 1% default over it. */
  const stepUnit = useCallback((dir: -1 | 1) => {
    void store.update((latest) => ({ unitPct: stepUnitPct(latest.unitPct, dir) }));
  }, []);

  return { settings, ready, setAmount, stepUnit };
}
