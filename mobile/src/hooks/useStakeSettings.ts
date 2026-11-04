import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

/**
 * How tracked bets are scored on the Performance tab (lib/trackedStake).
 *
 *   'posted' — the posted stake, the Record tab's units (default): 1u to win
 *              at the decided price, risk capped at 3u, no price at 1u
 *   'custom' — "My stakes": the member's own stake on the bets they set, in
 *              units; a bet they leave alone stays as posted
 *
 * Stakes are STORED at the 100-is-1u scale (lib/format FLAT_UNIT). Screens
 * show units and never dollars (mike, 2026-11-03: "everything must be
 * units"). A custom amount saved before that change was typed as dollars; it
 * now reads as that number / 100 in units.
 *
 * Retired modes fold to 'posted' in `sanitizeMode`, so an upgrading device
 * never lands on a mode that is gone. The old default scored every tracked
 * pick at 1u risked, a second unit basis beside the Record tab's (#1138
 * Decision 1, 2026-11-03). A 'kelly' mode sized each bet off an on-device
 * bankroll until 2026-09-20.
 *
 * Stored on-device (module store + AsyncStorage). Custom stakes are keyed by
 * pick_id.
 */
export type StakeMode = 'posted' | 'custom';

const MODE_KEY = 'stake.mode.v1';
const CUSTOM_KEY = 'stake.custom.v1';

interface StakeState {
  mode: StakeMode;
  custom: Record<string, number>;
}

const DEFAULT_STATE: StakeState = { mode: 'posted', custom: {} };

const listeners = new Set<(s: StakeState) => void>();
let cached: StakeState | null = null;

function sanitizeMode(raw: string | null): StakeMode {
  // The retired 1u-risked and Kelly modes, and anything unrecognised, read
  // as the posted stake.
  return raw === 'custom' ? raw : 'posted';
}

function sanitizeCustom(raw: string | null): Record<string, number> {
  if (!raw) return {};
  try {
    const parsed: unknown = JSON.parse(raw);
    if (parsed == null || typeof parsed !== 'object') return {};
    const out: Record<string, number> = {};
    for (const [k, v] of Object.entries(parsed as Record<string, unknown>)) {
      const n = typeof v === 'number' ? v : NaN;
      if (Number.isFinite(n) && n >= 0) out[k] = n;
    }
    return out;
  } catch {
    return {};
  }
}

async function load(): Promise<StakeState> {
  if (cached) return cached;
  try {
    const [modeRaw, customRaw] = await Promise.all([
      AsyncStorage.getItem(MODE_KEY),
      AsyncStorage.getItem(CUSTOM_KEY),
    ]);
    cached = { mode: sanitizeMode(modeRaw), custom: sanitizeCustom(customRaw) };
  } catch {
    cached = { ...DEFAULT_STATE };
  }
  return cached;
}

function emit(next: StakeState) {
  cached = next;
  listeners.forEach((fn) => fn(next));
}

async function saveMode(mode: StakeMode) {
  emit({ ...(cached ?? DEFAULT_STATE), mode });
  await AsyncStorage.setItem(MODE_KEY, mode);
}

async function saveCustomStake(pickId: number, amount: number | null) {
  const custom = { ...(cached ?? DEFAULT_STATE).custom };
  if (amount == null || !Number.isFinite(amount) || amount < 0) {
    delete custom[String(pickId)];
  } else {
    custom[String(pickId)] = Math.round(amount * 100) / 100;
  }
  emit({ ...(cached ?? DEFAULT_STATE), custom });
  await AsyncStorage.setItem(CUSTOM_KEY, JSON.stringify(custom));
}

/** Account deletion. Posted stakes, no custom stakes, and both keys removed. */
export async function clearStakeSettingsForAccountDeletion(): Promise<void> {
  emit({ ...DEFAULT_STATE, custom: {} });
  await AsyncStorage.multiRemove([MODE_KEY, CUSTOM_KEY]);
}

export function useStakeSettings() {
  const [state, setState] = useState<StakeState>(cached ?? DEFAULT_STATE);
  const [ready, setReady] = useState<boolean>(cached != null);

  useEffect(() => {
    let mounted = true;
    void load().then((s) => {
      if (!mounted) return;
      setState(s);
      setReady(true);
    });
    const listener = (s: StakeState) => setState(s);
    listeners.add(listener);
    return () => {
      mounted = false;
      listeners.delete(listener);
    };
  }, []);

  const setMode = useCallback((mode: StakeMode) => {
    void saveMode(mode);
  }, []);

  const setCustomStake = useCallback((pickId: number, amount: number | null) => {
    void saveCustomStake(pickId, amount);
  }, []);

  return {
    mode: state.mode,
    customStakes: state.custom,
    ready,
    setMode,
    setCustomStake,
  };
}
