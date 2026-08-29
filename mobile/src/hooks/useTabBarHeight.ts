import { useEffect, useState } from 'react';

/**
 * The measured height of the bottom tab bar, published from the tab navigator's
 * own tabBar renderer (App.tsx) and read by anything that floats above it —
 * today just the persistent betslip bar.
 *
 * Measured rather than assumed: the tab bar's height is platform- and
 * device-dependent (it includes the home-indicator inset), so a hard-coded
 * number would leave the betslip bar overlapping the tabs on some phones and
 * hovering above them on others. @react-navigation's useBottomTabBarHeight only
 * works from INSIDE a tab screen; the betslip bar is mounted once at the app
 * root so it can also show over pushed stack screens, hence this store.
 *
 * Module-store + listener pattern, same as useParlaySlip / useSportFilter.
 */

const listeners = new Set<(h: number) => void>();
let current = 0;

/** Fallback for the frame or two before the tab bar has laid out. */
export const FALLBACK_TAB_BAR_HEIGHT = 56;

export function setTabBarHeight(height: number): void {
  const h = Math.round(height);
  if (h === current || h <= 0) return;
  current = h;
  listeners.forEach((fn) => fn(h));
}

export function useTabBarHeight(): number {
  const [height, setHeight] = useState<number>(current);
  useEffect(() => {
    const listener = (h: number) => setHeight(h);
    listeners.add(listener);
    // A tab bar laid out before this hook mounted has already published.
    if (current !== height) setHeight(current);
    return () => {
      listeners.delete(listener);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return height;
}
