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

/** Per-$1 expected value of a single pick: model_prob × decimal_odds − 1.
 *  Null when dk_odds is null (prob-only markets have no payout). */
export function expectedValue(
  modelProbability: number,
  dkOdds: number | null | undefined,
): number | null {
  if (dkOdds == null) return null;
  return modelProbability * americanToDecimal(dkOdds) - 1;
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

/** "Sat 6/14" for a commence time on a future ET day; null when it's today. */
export function gameDayLabelET(iso: string | null | undefined): string | null {
  if (!iso) return null;
  try {
    const d = new Date(iso);
    const dateET = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'America/New_York',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(d);
    if (dateET === todayET()) return null;
    return new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York',
      weekday: 'short',
      month: 'numeric',
      day: 'numeric',
    }).format(d);
  } catch {
    return null;
  }
}

export type InningHalf = 'top' | 'bottom';

export type GameStatus =
  | { kind: 'pre'; timeLabel: string }
  | {
      kind: 'live';
      awayScore: number | null;
      homeScore: number | null;
      /** Live-feed detail. Null for sports/games with no live poller row. */
      inning: number | null;
      inningHalf: InningHalf | null;
      outs: number | null;
      bases: string | null;
    }
  | { kind: 'final'; awayScore: number; homeScore: number };

interface GameLike {
  commence_time?: string | null;
  home_score?: number | null;
  away_score?: number | null;
}

/** Shape of a v_live_game_state_latest row (only the fields status needs). */
interface LiveStateLike {
  inning?: number | null;
  inning_half?: string | null;
  outs?: number | null;
  bases_state?: string | null;
  home_score?: number | null;
  away_score?: number | null;
  abstract_game_state?: string | null;
}

function halfOf(value: string | null | undefined): InningHalf | null {
  if (value === 'top' || value === 'bottom') return value;
  return null;
}

/**
 * Derive game status from a `games` row, refined by the live feed when we have
 * a fresh snapshot for the game (MLB only — the live poller's coverage).
 *
 * Precedence:
 *  - settled scores in `games` → FINAL (authoritative; written at settlement)
 *  - live snapshot says Final → FINAL at the live score (hours before settlement)
 *  - live snapshot says Live  → LIVE with real score + inning/outs/bases
 *  - live snapshot says Preview → PRE, even if commence_time has passed
 *    (a delayed first pitch no longer reads as in-progress)
 *  - no snapshot, now >= commence_time → LIVE with unknown score (pre-live-feed
 *    behavior; still the case for every non-MLB sport)
 *  - otherwise → PRE (show start time)
 */
export function gameStatus(
  game: GameLike | null | undefined,
  live?: LiveStateLike | null,
): GameStatus {
  if (!game) return { kind: 'pre', timeLabel: '' };
  if (game.home_score != null && game.away_score != null) {
    return { kind: 'final', awayScore: game.away_score, homeScore: game.home_score };
  }
  if (live) {
    const state = live.abstract_game_state;
    if (state === 'Final' && live.home_score != null && live.away_score != null) {
      return { kind: 'final', awayScore: live.away_score, homeScore: live.home_score };
    }
    if (state === 'Live') {
      return {
        kind: 'live',
        awayScore: live.away_score ?? null,
        homeScore: live.home_score ?? null,
        inning: live.inning ?? null,
        inningHalf: halfOf(live.inning_half),
        outs: live.outs ?? null,
        bases: live.bases_state ?? null,
      };
    }
    if (state === 'Preview') {
      return { kind: 'pre', timeLabel: formatGameTimeET(game.commence_time) };
    }
  }
  if (game.commence_time) {
    const start = new Date(game.commence_time).getTime();
    if (!Number.isNaN(start) && Date.now() >= start) {
      return {
        kind: 'live',
        awayScore: game.away_score ?? null,
        homeScore: game.home_score ?? null,
        inning: null,
        inningHalf: null,
        outs: null,
        bases: null,
      };
    }
  }
  return { kind: 'pre', timeLabel: formatGameTimeET(game.commence_time) };
}

/** "T5" / "B9" — the compact inning chip for a pick card. */
export function inningShort(inning: number | null, half: InningHalf | null): string | null {
  if (inning == null) return null;
  const prefix = half === 'top' ? 'T' : half === 'bottom' ? 'B' : '';
  return `${prefix}${inning}`;
}

/** "Top 5th · 2 out" — the roomier live line for the pick detail screen. */
export function inningLong(
  inning: number | null,
  half: InningHalf | null,
  outs?: number | null,
): string | null {
  if (inning == null) return null;
  const side = half === 'top' ? 'Top ' : half === 'bottom' ? 'Bot ' : '';
  const base = `${side}${ordinal(inning)}`;
  if (outs == null) return base;
  return `${base} · ${outs} out`;
}

/** "Bases loaded" / "1st & 3rd" / "Bases empty" from a '000'..'111' string. */
export function basesLabel(bases: string | null): string | null {
  if (!bases || bases.length !== 3 || !/^[01]{3}$/.test(bases)) return null;
  const on: string[] = [];
  if (bases[0] === '1') on.push('1st');
  if (bases[1] === '1') on.push('2nd');
  if (bases[2] === '1') on.push('3rd');
  if (on.length === 0) return 'Bases empty';
  if (on.length === 3) return 'Bases loaded';
  return on.join(' & ');
}

function ordinal(n: number): string {
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${n}th`;
  const suffix = { 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] ?? 'th';
  return `${n}${suffix}`;
}

/**
 * Estimated game length (hours) used to drop a game from today's list once it
 * has almost certainly ended. We have no live final-whistle feed — scores only
 * land at next-morning settlement — so for team sports we fall back to elapsed
 * time past the start. Per-sport so a ~3h NBA game drops sooner than MLB.
 */
const GAME_DURATION_HOURS: Record<string, number> = {
  MLB: 4,
  NHL: 3.5,
  NBA: 3,
  WNBA: 3,
  UFC: 6,
};

/**
 * True once a game has finished and should drop off today's board.
 *  - both scores present → over (final)
 *  - otherwise, for time-bounded team sports, over when now is past
 *    commence_time + the sport's estimated duration
 *  - GOLF tournaments span multiple days, so they're never time-dropped —
 *    they fall off via settlement scores instead.
 */
export function isGameOver(game: GameLike | null | undefined, sport?: string): boolean {
  if (!game) return false;
  if (game.home_score != null && game.away_score != null) return true;
  if (!sport || sport === 'GOLF') return false;
  const hours = GAME_DURATION_HOURS[sport];
  if (hours == null || !game.commence_time) return false;
  const start = new Date(game.commence_time).getTime();
  if (Number.isNaN(start)) return false;
  return Date.now() >= start + hours * 3_600_000;
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
