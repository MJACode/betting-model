import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';
import { americanToDecimal } from '@/lib/format';

/**
 * On-device manual bet log — the fallback when a book doesn't auto-sync (the #1
 * complaint about sync-only trackers like Pikkit: MFA books and DFS that don't
 * sync, with no manual option). Also makes the Performance tab useful before the
 * SharpSports keys are live. Stored locally; never leaves the device.
 *
 * Module-store + AsyncStorage, same pattern as useSportFilter / useOnboarding.
 */
export type ManualBetResult = 'open' | 'won' | 'lost' | 'push';

export interface ManualBet {
  id: string;
  description: string;
  book: string | null;
  stake: number;
  odds_american: number | null;
  placed_at: string; // ISO
  result: ManualBetResult;
  profit: number; // 0 while open; computed on settle
}

export interface ManualBetInput {
  description: string;
  book: string | null;
  stake: number;
  odds_american: number | null;
}

const STORAGE_KEY = 'manualBets.v1';

const listeners = new Set<(b: ManualBet[]) => void>();
let cached: ManualBet[] | null = null;

async function load(): Promise<ManualBet[]> {
  if (cached) return cached;
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    cached = raw ? (JSON.parse(raw) as ManualBet[]) : [];
  } catch {
    cached = [];
  }
  return cached;
}

async function persist(next: ManualBet[]) {
  cached = next;
  listeners.forEach((fn) => fn(next));
  try {
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch (err) {
    console.warn('[manualBets] save failed', err);
  }
}

/** Profit for a settled bet on the given stake/odds. */
export function settledProfit(
  stake: number,
  oddsAmerican: number | null,
  result: ManualBetResult,
): number {
  if (result === 'lost') return -stake;
  if (result === 'push' || result === 'open') return 0;
  // won
  if (oddsAmerican == null) return 0;
  return stake * (americanToDecimal(oddsAmerican) - 1);
}

export function useManualBets() {
  const [bets, setBets] = useState<ManualBet[]>(cached ?? []);
  const [ready, setReady] = useState<boolean>(cached != null);

  useEffect(() => {
    let mounted = true;
    load().then((b) => {
      if (!mounted) return;
      setBets(b);
      setReady(true);
    });
    const listener = (b: ManualBet[]) => setBets(b);
    listeners.add(listener);
    return () => {
      mounted = false;
      listeners.delete(listener);
    };
  }, []);

  const add = useCallback((input: ManualBetInput) => {
    const bet: ManualBet = {
      id: `m_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      description: input.description,
      book: input.book,
      stake: input.stake,
      odds_american: input.odds_american,
      placed_at: new Date().toISOString(),
      result: 'open',
      profit: 0,
    };
    void persist([bet, ...(cached ?? [])]);
  }, []);

  const settle = useCallback((id: string, result: ManualBetResult) => {
    const next = (cached ?? []).map((b) =>
      b.id === id ? { ...b, result, profit: settledProfit(b.stake, b.odds_american, result) } : b,
    );
    void persist(next);
  }, []);

  const remove = useCallback((id: string) => {
    void persist((cached ?? []).filter((b) => b.id !== id));
  }, []);

  return { bets, ready, add, settle, remove };
}
