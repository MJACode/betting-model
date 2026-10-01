import { useEffect, useState } from 'react';

/**
 * How far the persistent betslip bar reaches up into the content area right
 * now — 0 while it's hidden (empty slip, or a route that owns the bottom).
 *
 * The bar is mounted once at the app root and floats over every screen, so the
 * last row of any list sat underneath it with no way to scroll it clear
 * (usability audit M7). BetslipBar publishes its measured overlap here and
 * BetslipBarSpacer adds that much room to the end of every vertical list.
 *
 * Module-store + listener pattern, same as useTabBarHeight / useParlaySlip.
 */

const listeners = new Set<(h: number) => void>();
let current = 0;

export function setBetslipBarInset(height: number): void {
  const h = Math.max(0, Math.round(height));
  if (h === current) return;
  current = h;
  listeners.forEach((fn) => fn(h));
}

export function useBetslipBarInset(): number {
  const [inset, setInset] = useState<number>(current);
  useEffect(() => {
    const listener = (h: number) => setInset(h);
    listeners.add(listener);
    if (current !== inset) setInset(current);
    return () => {
      listeners.delete(listener);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return inset;
}
