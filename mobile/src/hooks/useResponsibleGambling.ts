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
 *
 * v1 → v2 (2026-09-20). Under v1 the Settings field divided the entry by 100
 * before storing it, so a member who typed 10 under a "units / day" label got
 * 0.1 stored, and the toggle's own default stored 0.15. PicksHomeScreen has
 * always compared this value against a sum in UNITS, so those caps fired their
 * warning on any day with a single pick — one BET lays ~1.1u. Reading a v1
 * value as units would keep that going silently, so v1 is migrated rather than
 * trusted: × 100 recovers the number the member actually typed (and turns the
 * toggle default into a sane 15u), clamped to the same 100u ceiling the field
 * accepts. Dropping it instead would silently switch OFF a limit somebody chose
 * to turn on, which is the one thing a responsible-gambling control must not do.
 */
const STORAGE_KEY = 'responsibleGambling.v2';
const LEGACY_KEY = 'responsibleGambling.v1';

export interface RGSettings {
  exposureCapUnits: number | null;
}

const DEFAULTS: RGSettings = { exposureCapUnits: null };

const listeners = new Set<(s: RGSettings) => void>();
let cached: RGSettings | null = null;

function sanitize(raw: unknown): RGSettings {
  if (!raw || typeof raw !== 'object') return { ...DEFAULTS };
  const o = raw as Record<string, unknown>;
  const u = typeof o.exposureCapUnits === 'number' && o.exposureCapUnits > 0
    ? o.exposureCapUnits : null;
  return { exposureCapUnits: u };
}

/** v1 stored the typed number divided by 100 (see the note above). */
function migrateFromV1(raw: unknown): RGSettings {
  const { exposureCapUnits } = sanitize(raw);
  if (exposureCapUnits == null) return { ...DEFAULTS };
  return { exposureCapUnits: Math.min(100, Math.round(exposureCapUnits * 100 * 100) / 100) };
}

async function load(): Promise<RGSettings> {
  if (cached) return cached;
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    if (raw) {
      cached = sanitize(JSON.parse(raw));
      return cached;
    }
    const legacy = await AsyncStorage.getItem(LEGACY_KEY);
    if (legacy) {
      cached = migrateFromV1(JSON.parse(legacy));
      // Write the migrated value through before retiring the old key, so an
      // interrupted migration re-runs next launch instead of losing the cap.
      await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(cached));
      await AsyncStorage.removeItem(LEGACY_KEY);
      return cached;
    }
    cached = { ...DEFAULTS };
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
