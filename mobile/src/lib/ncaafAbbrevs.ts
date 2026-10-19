/**
 * NCAAF school → abbreviation, from `ncaaf_teams` (CFBD). The Signals
 * compact line prints "WKU @ SHSU"; the games table stores the school name.
 * A miss stays the school name (`compactTeam`) — this module never invents
 * a code.
 */

import { fetchAllPages } from '@/lib/paging';
import { supabase } from './supabase';

interface NcaafTeamRow {
  school: string;
  abbreviation: string | null;
}

let cached: Map<string, string> | null = null;
let inflight: Promise<ReadonlyMap<string, string>> | null = null;

/** The map from a fetch that already finished. Null until then. */
export function cachedNcaafAbbrevs(): ReadonlyMap<string, string> | null {
  return cached;
}

export function fetchNcaafAbbrevs(): Promise<ReadonlyMap<string, string>> {
  if (cached) return Promise.resolve(cached);
  if (!inflight) {
    inflight = fetchAllPages<NcaafTeamRow>(
      (from, to) =>
        supabase
          .from('ncaaf_teams')
          .select('school, abbreviation')
          .order('school')
          .range(from, to),
      (row) => row.school,
    )
      .then((rows) => {
        const map = new Map<string, string>();
        for (const row of rows) {
          const abbr = row.abbreviation?.trim();
          if (row.school && abbr) map.set(row.school, abbr);
        }
        cached = map;
        return map;
      })
      .catch((err) => {
        inflight = null;
        console.warn('[ncaafAbbrevs] school abbreviations unavailable', err);
        throw err;
      });
  }
  return inflight;
}
