import { useEffect, useRef, useState } from 'react';
import { searchPlayers, type PlayerSearchResult } from '@/lib/playerSearch';
import { errorText } from '@/lib/errors';

const DEBOUNCE_MS = 250;
const MIN_QUERY_LENGTH = 2;

export function usePlayerSearch(rawQuery: string) {
  const [results, setResults] = useState<PlayerSearchResult[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const reqIdRef = useRef(0);

  useEffect(() => {
    const trimmed = rawQuery.trim();
    if (trimmed.length < MIN_QUERY_LENGTH) {
      setResults([]);
      setLoading(false);
      setError(null);
      return;
    }

    const timer = setTimeout(() => {
      const myReqId = ++reqIdRef.current;
      setLoading(true);
      setError(null);
      searchPlayers(trimmed)
        .then((rows) => {
          if (myReqId !== reqIdRef.current) return; // stale
          setResults(rows);
        })
        .catch((e: unknown) => {
          if (myReqId !== reqIdRef.current) return;
          setError(errorText(e));
        })
        .finally(() => {
          if (myReqId !== reqIdRef.current) return;
          setLoading(false);
        });
    }, DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [rawQuery]);

  return { results, loading, error };
}
