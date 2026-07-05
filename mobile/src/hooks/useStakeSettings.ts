import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

/**
 * How tracked bets are scored on the Performance tab.
 *
 *   'flat'   — $100 per bet (default; matches the rest of the app's records)
 *   'kelly'  — each bet at its pick's Kelly-sized stake (kelly_fraction x the
 *              user's bankroll x their Kelly multiplier/cap — the same number
 *              the pick card showed as "Bet $X")
 *   'custom' — per-bet dollar amounts the user enters (default $100 each)
 *
 * Stored on-device (module store + AsyncStorage, same pattern as
 * useKellySettings). Custom stakes are keyed by pick_id.
 */
export type StakeMode = 'flat' | 'kelly' | 'custom';

export const FLAT_STAKE = 100;

const MODE_KEY = 'stake.mode.v1';
const CUSTOM_KEY = 'stake.custom.v1';

interface StakeState {
  mode: StakeMode;
  custom: Record<string, number>;
}

const DEFAULT_STATE: StakeState = { mode: 'flat', custom: {} };

const listeners = new Set<(s: StakeState) => void>();
let cached: StakeState | null = null;

function sanitizeMode(raw: string | null): StakeMode {
  return raw === 'kelly' || raw === 'custom' ? raw : 'flat';
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
