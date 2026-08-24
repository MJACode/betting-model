import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

/**
 * Responsible-gambling guardrails. On-device, opt-in. The disruptor thesis leans
 * on discipline as the moat (and the 2025-26 regulatory tailwind) — this is the
 * one limit we can enforce honestly without bet-sync: a daily exposure cap on
 * the total recommended stake across today's BET picks.
 *
 * exposureCapUnits is a daily stake ceiling in UNITS (e.g. 10 = 10u). null = no
 * cap. Units, not a fraction of bankroll: stakes are published in units now, so
 * a cap denominated in anything else can't be compared to them.
 * Module-store + AsyncStorage, same pattern as useSportFilter / useOnboarding.
 */
const STORAGE_KEY = 'responsibleGambling.v1';

export interface RGSettings {
  exposureCapUnits: number | null;
}

const DEFAULTS: RGSettings = { exposureCapUnits: null };

const listeners = new Set<(s: RGSettings) => void>();
let cached: RGSettings | null = null;

function sanitize(raw: unknown): RGSettings {
  if (!raw || typeof raw !== 'object') return { ...DEFAULTS };
  const o = raw as Record<string, unknown>;
  // A legacy exposureCapPct (fraction of bankroll) has no honest conversion to
  // units, so it is dropped rather than guessed at — the cap is opt-in and
  // defaults to off, so this re-prompts rather than silently mis-capping.
  const u = typeof o.exposureCapUnits === 'number' && o.exposureCapUnits > 0
    ? o.exposureCapUnits : null;
  return { exposureCapUnits: u };
}

async function load(): Promise<RGSettings> {
  if (cached) return cached;
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    cached = raw ? sanitize(JSON.parse(raw)) : { ...DEFAULTS };
  } catch {
    cached = { ...DEFAULTS };
  }
  return cached;
}

async function persist(next: RGSettings) {
  cached = next;
  listeners.forEach((fn) => fn(next));
  try {
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch (err) {
    console.warn('[responsibleGambling] save failed', err);
  }
}

export function useResponsibleGambling() {
  const [settings, setSettings] = useState<RGSettings>(cached ?? DEFAULTS);
  const [ready, setReady] = useState<boolean>(cached != null);

  useEffect(() => {
    let mounted = true;
    load().then((s) => {
      if (!mounted) return;
      setSettings(s);
      setReady(true);
    });
    const listener = (s: RGSettings) => setSettings(s);
    listeners.add(listener);
    return () => {
      mounted = false;
      listeners.delete(listener);
    };
  }, []);

  const setExposureCapUnits = useCallback((units: number | null) => {
    void persist({ ...(cached ?? DEFAULTS), exposureCapUnits: units });
  }, []);

  return { settings, ready, setExposureCapUnits };
}
