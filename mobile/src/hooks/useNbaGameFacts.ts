/**
 * Whether NBA byom_game_facts has a row. NFL is ready. An unknown sport
 * stays loading. A known NBA row in this process starts ready, so the
 * tiles do not flash. A failed read is an error, not "no history."
 */

import { useCallback, useEffect, useState } from 'react';

import { fetchNbaGameFactsReady, nbaGameFactsAreKnown } from '@/lib/byom';
import { errorText, isAbortError } from '@/lib/errors';
import type { ByomSport } from '@/lib/byomRecord';

export type NbaGameFactsStatus = 'ready' | 'loading' | 'missing' | 'error';

function initial(sport: ByomSport | null): NbaGameFactsStatus {
  if (sport == null) return 'loading';
  if (sport !== 'NBA') return 'ready';
  return nbaGameFactsAreKnown() ? 'ready' : 'loading';
}

export function useNbaGameFacts(sport: ByomSport | null) {
  const [status, setStatus] = useState<NbaGameFactsStatus>(() => initial(sport));
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (sport == null) {
      setStatus('loading');
      setError(null);
      return;
    }
    if (sport !== 'NBA') {
      setStatus('ready');
      setError(null);
      return;
    }
    if (nbaGameFactsAreKnown()) {
      setStatus('ready');
      setError(null);
      return;
    }
    let live = true;
    setStatus('loading');
    setError(null);
    void fetchNbaGameFactsReady()
      .then((next) => {
        if (!live) return;
        setStatus(next === 'ready' ? 'ready' : 'missing');
      })
      .catch((e: unknown) => {
        if (!live || isAbortError(e)) return;
        setStatus('error');
        if (!isAbortError(e)) setError(errorText(e));
      });
    return () => {
      live = false;
    };
  }, [sport, attempt]);

  const retry = useCallback(() => {
    setAttempt((n) => n + 1);
  }, []);

  return { status, error, retry };
}
