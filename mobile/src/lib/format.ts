/** Format an American odds value (-110, +150) for display. */
export function formatAmerican(odds: number | null | undefined): string {
  if (odds == null) return 'N/A';
  const rounded = Math.round(odds);
  return rounded > 0 ? `+${rounded}` : `${rounded}`;
}

/** Convert American odds to decimal odds. -110 -> 1.909, +150 -> 2.50. */
export function americanToDecimal(odds: number): number {
  if (odds > 0) return 1 + odds / 100;
  return 1 + 100 / Math.abs(odds);
}

/** Implied probability from American odds. */
export function americanImplied(odds: number): number {
  return 1 / americanToDecimal(odds);
}

/** Percent formatting — 0.673 -> "67.3%". */
export function formatPct(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return '—';
  return `${(value * 100).toFixed(digits)}%`;
}

/** Signed percent — 0.125 -> "+12.5%". */
export function formatPctSigned(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return '—';
  const v = value * 100;
  const sign = v > 0 ? '+' : '';
  return `${sign}${v.toFixed(digits)}%`;
}

/** Dollars — 30.5 -> "$30.50". */
export function formatCurrency(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  const sign = value < 0 ? '-' : '';
  return `${sign}$${Math.abs(value).toFixed(2)}`;
}

/** Signed dollars — -25 -> "−$25.00", +30 -> "+$30.00". */
export function formatCurrencySigned(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  if (value === 0) return '$0.00';
  const sign = value > 0 ? '+' : '−';
  return `${sign}$${Math.abs(value).toFixed(2)}`;
}

/** Today in America/New_York as YYYY-MM-DD. */
export function todayET(): string {
  const fmt = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/New_York',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
  return fmt.format(new Date());
}

/** Format an ISO timestamp as "h:mm AM/PM ET". */
export function formatGameTimeET(iso: string | null | undefined): string {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    }).format(d) + ' ET';
  } catch {
    return iso;
  }
}

export type GameStatus =
  | { kind: 'pre'; timeLabel: string }
  | { kind: 'live'; awayScore: number | null; homeScore: number | null }
  | { kind: 'final'; awayScore: number; homeScore: number };

interface GameLike {
  commence_time?: string | null;
  home_score?: number | null;
  away_score?: number | null;
}

/**
 * Derive game status from a `games` row.
 *  - both scores present → FINAL
 *  - now >= commence_time → LIVE (score may be null; we don't have a live feed)
 *  - otherwise → PRE (show start time)
 */
export function gameStatus(game: GameLike | null | undefined): GameStatus {
  if (!game) return { kind: 'pre', timeLabel: '' };
  if (game.home_score != null && game.away_score != null) {
    return { kind: 'final', awayScore: game.away_score, homeScore: game.home_score };
  }
  if (game.commence_time) {
    const start = new Date(game.commence_time).getTime();
    if (!Number.isNaN(start) && Date.now() >= start) {
      return {
        kind: 'live',
        awayScore: game.away_score ?? null,
        homeScore: game.home_score ?? null,
      };
    }
  }
  return { kind: 'pre', timeLabel: formatGameTimeET(game.commence_time) };
}

/** Get YYYY-MM-DD from an ISO date string (no time math). */
export function toIsoDate(value: string): string {
  return value.slice(0, 10);
}

/** Add `days` to a YYYY-MM-DD string. Returns YYYY-MM-DD. */
export function addDays(date: string, days: number): string {
  const d = new Date(`${date}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}
