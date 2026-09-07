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
/** '2026-09-07' -> 'SUN'. Names the day a future slate's lines belong to, so a
 *  column header never reads as "now" on an off day (UX_REVIEW §3). */
export function weekdayET(date: string): string {
  if (!date) return '';
  const d = new Date(`${date}T12:00:00Z`);
  if (Number.isNaN(d.getTime())) return '';
  return new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', weekday: 'short' })
    .format(d)
    .toUpperCase();
}

export function todayET(): string {
  return etDate(new Date());
}

const ET_HOUR = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York',
  hour: '2-digit',
  hourCycle: 'h23',
});

/**
 * Mirror of config.LIVE_SLATE_LOOKBACK_UNTIL_HOUR_ET. Yesterday's slate is
 * carried until 6am ET and no further: nothing is still being played at 6am,
 * and carrying the date forever would put a whole extra slate in every query.
 */
export const LIVE_SLATE_LOOKBACK_UNTIL_HOUR_ET = 6;

/**
 * Every ET game_date whose games could still be IN PROGRESS right now, newest
 * first — the app's copy of config.live_slate_dates(). Today is always first,
 * so a caller that collapses to one date still gets today.
 *
 * A game carries the game_date of its KICKOFF, so a 10:37pm ET start on the
 * west coast is in the fourth quarter at 00:30 ET the next day. Anything that
 * asks for live rows by a single todayET() stops seeing that game the moment
 * the calendar rolls — while the live loops, the push notifier and the Discord
 * producers all keep going, because they already use live_slate_dates(). That
 * asymmetry is exactly how the UCLA @ California live moneyline reached the
 * #ncaaf channel at 1:07am ET on 2026-09-06 under game_date 2026-09-05 and was
 * never on the app's live board (CLAUDE.md §1b: the app, Discord and push show
 * the same picks).
 *
 * Use this ANYWHERE the app resolves which games could be live; todayET() is
 * still right for the day's slate as a unit (the pre-game board).
 *
 * `now` is injectable ONLY so the boundary can be tested at the boundary: the
 * failure is silent, because an empty slate and a missed slate render the same.
 */
export function liveSlateDatesET(now: Date = new Date()): string[] {
  const dates = [etDate(now)];
  if (Number(ET_HOUR.format(now)) < LIVE_SLATE_LOOKBACK_UNTIL_HOUR_ET) {
    dates.push(etDate(new Date(now.getTime() - 24 * 3_600_000)));
  }
  return dates;
}

/**
 * Parse a timestamp string into a Date.
 *
 * Accepts ISO 8601 and the Postgres text form the pipeline writes into the
 * TEXT timestamp columns (picks.created_at, settled_at, clv_captured_at):
 * "2026-09-03 04:20:33.552781+00" — a space instead of "T", up to six
 * fractional digits, and a bare "+00" offset. Node's Date accepts that form,
 * so verify scripts never saw a problem; Hermes (the app's engine) does not —
 * it returns Invalid Date, Intl then throws, and every formatter below fell
 * through to printing the raw string. That was the
 * "Posted 2026-09-03 04:20:33.552781+00" chip on the pick card (2026-09-03).
 */
export function normalizeStamp(stamp: string): string {
  const m =
    /^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(\.\d+)?(Z|[+-]\d{2}(?::?\d{2})?)?$/.exec(
      stamp.trim(),
    );
  if (!m) return stamp;
  const [, date, time, frac, tz] = m;
  // ISO allows any number of fractional digits, but JS engines only promise
  // milliseconds — trim to three, padding a short fraction ("+.5" -> ".500").
  const ms = frac ? frac.slice(0, 4).padEnd(4, '0') : '';
  let zone = tz ?? '';
  if (zone && zone !== 'Z') {
    const digits = zone.slice(1).replace(':', '');
    zone = `${zone[0]}${digits.slice(0, 2)}:${digits.length > 2 ? digits.slice(2, 4) : '00'}`;
  }
  return `${date}T${time}${ms}${zone}`;
}

export function parseStamp(stamp: string): Date {
  return new Date(normalizeStamp(stamp));
}

/** Format an ISO timestamp as "h:mm AM/PM ET". */
export function formatGameTimeET(iso: string | null | undefined): string {
  if (!iso) return '';
  try {
    const d = parseStamp(iso);
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

/** "Tue 8/18, 9:31 AM ET" — full day+time stamp (NFL pick-timing display). */
export function formatDayTimeET(iso: string | null | undefined): string {
  if (!iso) return '';
  try {
    const d = parseStamp(iso);
    const day = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York',
      weekday: 'short',
      month: 'numeric',
      day: 'numeric',
    }).format(d);
    const time = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    }).format(d);
    return `${day}, ${time} ET`;
  } catch {
    return iso;
  }
}

/**
 * "11:07 AM ET" when the stamp falls on today's ET date, else
 * "Tue 8/18 · 9:31 AM ET". Used for when a pick posted — the day only matters
 * when it isn't today, and on a same-day board the date would be noise. The
 * day label already carries its own comma ("Tue, 8/18" in most locales' data),
 * so the two halves are joined with a separator rather than another comma.
 */
export function formatStampET(iso: string | null | undefined): string {
  const time = formatGameTimeET(iso);
  if (!time) return '';
  const day = gameDayLabelET(iso);
  return day ? `${day} · ${time}` : time;
}

/**
 * "SAT" for a commence time on a future ET day; null when it's today.
 *
 * The short sibling of `gameDayLabelET`, and it lives HERE rather than in the
 * board that wanted it: a hand-rolled date format in a screen is how two
 * surfaces end up printing the same day differently (UX review, 2026-09-05 —
 * the first version of this shipped inside `statsBoard.ts`). The Stats board
 * wants three letters because it prints the label on every row, where
 * "Sat 6/14" would eat the width the opponent needs.
 */
export function weekdayShortET(iso: string | null | undefined): string | null {
  if (!iso) return null;
  try {
    const d = parseStamp(iso);
    if (etDate(d) === todayET()) return null;
    return new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', weekday: 'short' })
      .format(d)
      .toUpperCase();
  } catch {
    return null;
  }
}

/** A Date as its America/New_York calendar date, YYYY-MM-DD. */
export function etDate(d: Date): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/New_York',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(d);
}

/** "Sat 6/14" for a commence time on a future ET day; null when it's today. */
export function gameDayLabelET(iso: string | null | undefined): string | null {
  if (!iso) return null;
  try {
    const d = parseStamp(iso);
    if (etDate(d) === todayET()) return null;
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
  | { kind: 'final'; awayScore: number; homeScore: number }
  /**
   * Started long enough ago that it is over, but we have no score to show —
   * the live feed never captured a final (or doesn't cover this sport) and
   * settlement hasn't written `games` scores yet. Renders no status at all,
   * which is the honest answer: better than a stale LIVE badge or a made-up
   * final score.
   */
  | { kind: 'ended' };

interface GameLike {
  sport?: string | null;
  commence_time?: string | null;
  home_score?: number | null;
  away_score?: number | null;
}

/**
 * How long after first pitch a game may still read LIVE on the strength of the
 * clock alone, when no live snapshot confirms it.
 *
 * This path carries more than it looks like: the live poller is MLB-only, so
 * every other sport rides it for the entire game, and `games` scores don't land
 * until the next morning's settlement. Uncapped, a finished game stayed badged
 * LIVE for ~15 hours. Values are generous upper bounds on event length (extra
 * innings, OT, rain delays) — the cap only has to catch "hours past any
 * plausible finish", not the exact final out.
 */
const BLIND_LIVE_WINDOW_MS: Record<string, number> = {
  MLB: 6 * 3_600_000,
  NHL: 5 * 3_600_000,
  NBA: 5 * 3_600_000,
  WNBA: 5 * 3_600_000,
  // Football, and the reason these two are named rather than left on the
  // default: they are the sports that play late and are NOT covered by the live
  // poller, so the blind window is all they have. Once the app's live board
  // carries the whole slate window (liveSlateDatesET), a 10:37pm ET kickoff is
  // no longer dropped at midnight by a game_date filter — so the 6h default
  // would have kept a finished NCAAF game reading LIVE until 4:37am, with a
  // stale in-play price and a betslip hand-off (UX review, 2026-09-06). A
  // college game runs ~3h25m and an NFL game ~3h10m; 4h leaves weather-delay
  // margin. The durable fix is a real end-of-game signal for non-MLB sports,
  // server-side — this is a display bound, not a substitute for one.
  NCAAF: 4 * 3_600_000,
  NFL: 4 * 3_600_000,
  // A UFC card runs from the first prelim through the main event.
  UFC: 8 * 3_600_000,
  // A golf "game" row is a whole tournament (commence_time = the earliest
  // round-1 tee time), so its window is days, not hours.
  GOLF: 5 * 24 * 3_600_000,
};
const DEFAULT_BLIND_LIVE_WINDOW_MS = 6 * 3_600_000;

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
 * Snapshots older than this are dropped rather than displayed. The poller
 * writes every ~15s while a game is live, so a gap this large means it died or
 * the slate ended — better to show no inning than a frozen one. (The backend
 * scorer uses a tighter 5-minute guard, config.LIVE_STATE_MAX_AGE_SEC; display
 * can tolerate more lag than a bet decision.)
 */
const LIVE_SNAPSHOT_MAX_AGE_MS = 15 * 60_000;

/**
 * Whether a live snapshot is trustworthy enough to display.
 *
 * A Final row is exempt from the age check: it is terminal, and the poller
 * stops writing once a game ends, so every Final snapshot is guaranteed to age
 * out within the same day. Expiring it discarded the one fact that ends the
 * LIVE badge and dropped the card back onto the clock-based fallback.
 */
export function isLiveSnapshotUsable(
  row: Pick<LiveStateLike, 'abstract_game_state'> & { snapshot_at: string },
  now: number,
): boolean {
  if (row.abstract_game_state === 'Final') return true;
  const ts = parseStamp(row.snapshot_at).getTime();
  if (Number.isNaN(ts)) return false;
  return now - ts <= LIVE_SNAPSHOT_MAX_AGE_MS;
}

/**
 * If any game updated this recently, the poller is actively running right now.
 * It writes every ~15s, so this is generous — it only has to separate "the loop
 * is alive" from "the loop is dead or the slate is over".
 */
const POLLER_ALIVE_WINDOW_MS = 3 * 60_000;

/**
 * Reduce a day's snapshots to what each game should actually display.
 *
 * Beyond dropping stale rows, this reads one signal a single row can't: whether
 * the poller is still running. The poller stops writing for a game the moment it
 * goes Final, so a game that has gone quiet *while other games are still
 * updating* has ended — even if we never captured its Final row (the loop can
 * exit between a game's last pitch and its Final cycle).
 *
 * Such a game is marked terminal with its scores cleared. Clearing them is the
 * honest part: the last snapshot may be mid-inning, so its score is not the
 * final score — we know the game is over, not how it finished. `gameStatus`
 * renders that as ENDED (no badge) rather than a stale LIVE.
 *
 * When no game is updating we can't tell "slate over" from "poller died", so
 * stale rows are simply dropped and the clock-based window decides.
 */
export function reconcileLiveSnapshots<
  T extends Pick<LiveStateLike, 'abstract_game_state'> & { game_id: string; snapshot_at: string },
>(rows: readonly T[], now: number): Map<string, T> {
  const freshest = rows.reduce((max, r) => {
    const ts = parseStamp(r.snapshot_at).getTime();
    return Number.isNaN(ts) ? max : Math.max(max, ts);
  }, 0);
  const pollerAlive = freshest > 0 && now - freshest <= POLLER_ALIVE_WINDOW_MS;

  const out = new Map<string, T>();
  for (const row of rows) {
    if (isLiveSnapshotUsable(row, now)) {
      out.set(row.game_id, row);
    } else if (pollerAlive) {
      out.set(row.game_id, {
        ...row,
        abstract_game_state: 'Final',
        home_score: null,
        away_score: null,
      });
    }
  }
  return out;
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
 *  - no snapshot, within BLIND_LIVE_WINDOW_MS of commence_time → LIVE with
 *    unknown score (pre-live-feed behavior; still the case for every non-MLB
 *    sport)
 *  - no snapshot, past that window → ENDED (no badge). Without this a finished
 *    game read LIVE until settlement wrote scores the next morning.
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
    if (state === 'Final') {
      if (live.home_score != null && live.away_score != null) {
        return { kind: 'final', awayScore: live.away_score, homeScore: live.home_score };
      }
      // Final is terminal even when the snapshot is missing scores — never let
      // it fall through to the clock-based LIVE branch below.
      return { kind: 'ended' };
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
    const start = parseStamp(game.commence_time).getTime();
    const elapsed = Date.now() - start;
    if (!Number.isNaN(start) && elapsed >= 0) {
      const window =
        BLIND_LIVE_WINDOW_MS[game.sport ?? ''] ?? DEFAULT_BLIND_LIVE_WINDOW_MS;
      if (elapsed > window) return { kind: 'ended' };
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
  const start = parseStamp(game.commence_time).getTime();
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
