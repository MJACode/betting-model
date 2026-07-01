import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

import { todayET } from '@/lib/format';

/**
 * Controls the single root-mounted "Yesterday's results" modal.
 *
 * Two ways in:
 *  - manual: showYesterdayResults() (called from the Track Record button) — never gated.
 *  - auto: consumeAuto() — host calls it once per day after onboarding + when there's
 *    data; gated by an AsyncStorage "last shown" date so it only auto-pops once a day.
 *
 * Module-store + listener pattern, same as Toast / useOnboarding.
 */
const STORAGE_KEY = 'yesterdayRecap.lastShown.v1';

const listeners = new Set<() => void>();

/** Open the modal manually (e.g. from the Track Record "Yesterday" button). */
export function showYesterdayResults(): void {
  listeners.forEach((fn) => fn());
}

async function markShownToday(): Promise<void> {
  try {
    await AsyncStorage.setItem(STORAGE_KEY, todayET());
  } catch (err) {
    console.warn('[recap] save failed', err);
  }
}

async function autoShownToday(): Promise<boolean> {
  try {
    return (await AsyncStorage.getItem(STORAGE_KEY)) === todayET();
  } catch {
    return false;
  }
}

export function useDailyRecapControl() {
  const [visible, setVisible] = useState(false);
  // null while the AsyncStorage gate is still loading; true = auto-pop pending.
  const [autoEligible, setAutoEligible] = useState<boolean | null>(null);

  useEffect(() => {
    let mounted = true;
    autoShownToday().then((shown) => {
      if (mounted) setAutoEligible(!shown);
    });
    const listener = () => setVisible(true);
    listeners.add(listener);
    return () => {
      mounted = false;
      listeners.delete(listener);
    };
  }, []);

  const close = useCallback(() => {
    setVisible(false);
  }, []);

  /** Fire today's auto-pop and persist so it won't repeat (no-op if already shown). */
  const consumeAuto = useCallback(() => {
    setVisible(true);
    setAutoEligible(false);
    void markShownToday();
  }, []);

  return { visible, autoEligible, close, consumeAuto };
}
