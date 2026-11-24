import { useEffect, useState } from 'react';

/**
 * Slips the member has logged in Your bets this session, by key (UX review,
 * 2026-11-24): after "Log bet" the button reads "Logged", and a second tap
 * asks before writing the same bet twice — a duplicate doubles the member's
 * own P&L for it. In memory only: Your bets itself (useManualBets) is the
 * record; this only remembers which button was just used.
 *
 * Keys: `slip:<sorted leg keys>` for the betslip, `saved:<id>` for a saved
 * parlay.
 */
const logged = new Set<string>();
const listeners = new Set<() => void>();

export function betslipLogKey(slipKeys: readonly string[]): string {
  return `slip:${[...slipKeys].sort().join(',')}`;
}

export function savedParlayLogKey(id: string): string {
  return `saved:${id}`;
}

export function markSlipLogged(key: string): void {
  logged.add(key);
  listeners.forEach((fn) => fn());
}

export function isSlipLogged(key: string): boolean {
  return logged.has(key);
}

/** Re-renders the caller when any slip is marked logged. */
export function useLoggedSlips(): (key: string) => boolean {
  const [, bump] = useState(0);
  useEffect(() => {
    const fn = () => bump((n) => n + 1);
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  }, []);
  return isSlipLogged;
}
