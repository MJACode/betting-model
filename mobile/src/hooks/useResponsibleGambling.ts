import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

/**
 * Responsible-gambling guardrails. On-device, opt-in. The disruptor thesis leans
 * on discipline as the moat (and the 2025-26 regulatory tailwind) — this is the
 * one limit we can enforce honestly without bet-sync: a daily exposure cap on
 * the total recommended stake across today's BET picks.
 *
 * exposureCapPct is a fraction of bankroll (e.g. 0.15 = 15%). null = no cap.
 * Module-store + AsyncStorage, same pattern as useSportFilter / useOnboarding.
 */
const STORAGE_KEY = 'responsibleGambling.v1';

export interface RGSettings {
  exposureCapPct: number | null;
}

const DEFAULTS: RGSettings = { exposureCapPct: null };

const listeners = new Set<(s: RGSettings) => void>();
let cached: RGSettings | null = null;

function sanitize(raw: unknown): RGSettings {
  if (!raw || typeof raw !== 'object') return { ...DEFAULTS };
  const o = raw as Record<string, unknown>;
  const pct = typeof o.exposureCapPct === 'number' && o.exposureCapPct > 0 ? o.exposureCapPct : null;
  return { exposureCapPct: pct };
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

  const setExposureCapPct = useCallback((pct: number | null) => {
    void persist({ ...(cached ?? DEFAULTS), exposureCapPct: pct });
  }, []);

  return { settings, ready, setExposureCapPct };
}
