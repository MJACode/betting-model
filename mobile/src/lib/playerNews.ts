/**
 * Recent player news — the sheet the prop screens open from their top-right
 * newspaper icon.
 *
 * A prop is a bet on one player, and what moves it most often is a sentence,
 * not a number: "on a 75-pitch limit", "scratched with hamstring tightness",
 * "moved up to leadoff". The rows come from `player_news`, which the pipeline
 * fills from whichever provider config.PLAYER_NEWS_PROVIDER names.
 */

import type { PlayerNewsRow } from '@/types';

/**
 * MIRROR of data/name_match.py::normalize_player_name — the fold the ingestor
 * stored `player_key` with. The two must agree or the name fallback silently
 * finds nothing, which is exactly the accented-name gap that cost ~9% of an MLB
 * slate on the odds side. Keep them in step: diacritics stripped, lowercased,
 * apostrophes/periods deleted, hyphens folded to spaces, trailing generational
 * suffix dropped, whitespace collapsed.
 */
const SUFFIXES = new Set(['jr', 'sr', 'ii', 'iii', 'iv', 'v']);

export function normalizePlayerName(name: string | null | undefined): string {
  if (!name) return '';
  const parts = name
    .normalize('NFKD')
    // Combining marks — the accent halves NFKD just split off.
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/['‘’ʼ.]/g, '')
    .replace(/[-‐‑‒–—_]/g, ' ')
    .split(/\s+/)
    .filter(Boolean);
  while (parts.length > 1 && SUFFIXES.has(parts[parts.length - 1]!)) parts.pop();
  return parts.join(' ');
}

/** Who wrote the note, for the sheet's "Powered by" line. */
export function sourceLabel(source: string | null | undefined): string {
  if (!source) return '';
  const known: Record<string, string> = {
    espn: 'ESPN',
    rotowire: 'RotoWire',
    rotoballer: 'RotoBaller',
    sportsdataio: 'SportsDataIO',
  };
  return known[source.toLowerCase()] ?? source.toUpperCase();
}

const DAYS = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/**
 * The date pill on each note: "SUN Aug 23". Rendered in the reader's own
 * timezone — a note published 9pm ET reads as the day it happened.
 */
export function newsDateLabel(publishedAt: string): string {
  const d = new Date(publishedAt);
  if (Number.isNaN(d.getTime())) return '';
  return `${DAYS[d.getDay()]} ${MONTHS[d.getMonth()]} ${d.getDate()}`;
}

/** Hours within which a note counts as new enough to dot the icon. */
export const NEWS_FRESH_HOURS = 48;

export function hasFreshNews(rows: PlayerNewsRow[], now: number = Date.now()): boolean {
  return rows.some((r) => {
    const t = new Date(r.published_at).getTime();
    return !Number.isNaN(t) && now - t <= NEWS_FRESH_HOURS * 3600 * 1000;
  });
}
