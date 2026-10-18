import { useEffect, useState } from 'react';
import { cachedNcaafAbbrevs, fetchNcaafAbbrevs } from '@/lib/ncaafAbbrevs';

const EMPTY: ReadonlyMap<string, string> = new Map();

/**
 * School abbreviations for the Signals compact line. Loaded once when the
 * NCAAF Signals board is on screen. A failed read leaves the map empty and
 * the card prints the school name. A warm module cache paints on the first
 * frame; the cold load can still show school names until the fetch lands.
 */
export function useNcaafAbbrevs(enabled: boolean): ReadonlyMap<string, string> {
  const [map, setMap] = useState<ReadonlyMap<string, string>>(() => cachedNcaafAbbrevs() ?? EMPTY);
  useEffect(() => {
    if (!enabled) return;
    let live = true;
    fetchNcaafAbbrevs()
      .then((next) => {
        if (live) setMap(next);
      })
      .catch(() => {
        // fetchNcaafAbbrevs already warned. School names stay on the card.
      });
    return () => {
      live = false;
    };
  }, [enabled]);
  return enabled ? map : EMPTY;
}
