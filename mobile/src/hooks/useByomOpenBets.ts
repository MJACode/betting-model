/**
 * The signed-in member's open bets on their own models. Signed out, or
 * before the hand migration is applied, it holds no bets and no error, so
 * a screen shows nothing extra.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { useAuth } from '@/hooks/useAuth';
import { fetchByomOpenBets, type ByomOpenBet } from '@/lib/byomAlerts';
import { isAbortError, splitLoadError } from '@/lib/errors';

export function useByomOpenBets(enabled = true) {
  const { user } = useAuth();
  const [bets, setBets] = useState<ByomOpenBet[]>([]);
  const [available, setAvailable] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seq = useRef(0);
  const active = enabled && user != null;

  const load = useCallback(async () => {
    const id = ++seq.current;
    if (!active) {
      setBets([]);
      setAvailable(false);
      setError(null);
      return;
    }
    setLoading(true);
    try {
      const result = await fetchByomOpenBets();
      if (seq.current !== id) return;
      setError(null);
      if (result.status === 'unavailable') {
        setAvailable(false);
        setBets([]);
      } else {
        setAvailable(true);
        setBets(result.bets);
      }
    } catch (e: unknown) {
      if (seq.current !== id || isAbortError(e)) return;
      // Keep the cards already shown; the screen shows the error beside them.
      setError(splitLoadError(e).error);
    } finally {
      if (seq.current === id) setLoading(false);
    }
  }, [active]);

  useEffect(() => {
    void load();
  }, [load]);

  return { bets, available, loading, error, reload: load };
}
