/**
 * Season scope for My models, the builder preview, and model detail.
 * One module store so those screens grade the same window. Not persisted:
 * opening the tab starts on all seasons.
 */

import { useEffect, useState } from 'react';

import type { ByomSeasonScope } from '@/lib/byomRecord';

const listeners = new Set<(scope: ByomSeasonScope) => void>();
let scope: ByomSeasonScope = 'all';

export function useByomSeason(): {
  scope: ByomSeasonScope;
  setScope: (next: ByomSeasonScope) => void;
} {
  const [value, setValue] = useState(scope);

  useEffect(() => {
    const listener = (next: ByomSeasonScope) => setValue(next);
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, []);

  return {
    scope: value,
    setScope: (next: ByomSeasonScope) => {
      scope = next;
      listeners.forEach((listener) => listener(next));
    },
  };
}
