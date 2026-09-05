import { useEffect, useState } from 'react';

/**
 * A clock that re-renders on a tick, for screens that PRINT the time.
 *
 * The Stats board derives three things from `Date.now()` — which games are
 * still bettable, which teams are Live/Final, and the "9:40 PM ET" under every
 * row's name. Read once at mount, all three freeze: a board opened at 6:55pm
 * still says "7:05 PM ET" on twenty-five rows at 7:40, beside prices that are
 * equally stale but only wrong in one place (UX review, 2026-09-05).
 *
 * Thread the returned value into every memo that reads the clock, not just the
 * one printing it — a tick that refreshes the label but not `gameStatus` swaps
 * a stale time for a stale "Live".
 *
 * One minute is the resolution the app displays (`formatGameTimeET` prints no
 * seconds), so a faster tick would re-render for nothing.
 */
export function useNow(intervalMs = 60_000): number {
  const [now, setNow] = useState<number>(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}
