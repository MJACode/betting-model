/**
 * Picks → Scoreboard. One card per game, DraftKings game markets only.
 *
 * Live scores are whatever a stored feed already wrote: MLB from
 * live_game_state, NCAAF from ncaaf_live_states, and NFL / NBA / NHL /
 * NCAAB / NCAABW from live_scoreboard (data/ingestors/live_scoreboard.py,
 * every minute from ESPN, Matt 2026-10-29 and 2026-11-15), and EuroLeague
 * into the same table from EuroLeague's own live API (mike, 2026-11-25). The
 * other sports (WNBA, UFC, tennis) have no live feed: a game shows
 * Upcoming, then Final once `games` has the result. A clock that has passed is not a score. A game
 * with no fresh stored row stays Upcoming until `games` has a final score.
 * Nothing here fills a number in.
 */

import {
  MINUS,
  basesLabel,
  formatAmerican,
  formatDayTimeET,
  formatGameTimeET,
  isVersusSport,
  parseStamp,
} from '@/lib/format';
import { sportDisplayName } from '@/lib/liveSports';
import { compactTeam, trueMinus } from '@/lib/signalsCard';

/**
 * Every sport with games (Matt, 2026-11-15). The board's chip row shows only
 * the ones with a game on the chosen day, plus the open one
 * (`scoreboardChipSports`), so an off-season sport does not take a chip.
 */
export const SCOREBOARD_SPORTS = [
  'NFL', 'NCAAF', 'MLB', 'NBA', 'NHL',
  'NCAAB', 'NCAABW', 'EUROLEAGUE', 'WNBA', 'UFC', 'ATP', 'WTA',
] as const;
export type ScoreboardSport = (typeof SCOREBOARD_SPORTS)[number];

export type ScoreboardPhase = 'upcoming' | 'live' | 'final';

/** One list per sport, in this order (Matt, 2026-10-29: no status filter). */
export const SCOREBOARD_PHASE_ORDER: readonly ScoreboardPhase[] = ['live', 'upcoming', 'final'];

/** Sports whose live score comes from live_scoreboard: ESPN's, and EuroLeague's own API. */
export const ESPN_LIVE_SPORTS: readonly string[] = ['NFL', 'NBA', 'NHL', 'NCAAB', 'NCAABW', 'EUROLEAGUE'];

/** Sports whose `games` row names a school, not a code. */
const SCHOOL_SPORTS: ReadonlySet<string> = new Set(['NCAAB', 'NCAABW']);

/** A school or a person: the disc is initials, so the name must stay on the row. */
export function isNameSport(sport: string): boolean {
  return SCHOOL_SPORTS.has(sport) || isVersusSport(sport);
}

/** Sports with a stored live feed. The rest go from Upcoming to Final. */
function hasLiveFeed(sport: string): boolean {
  return sport === 'MLB' || sport === 'NCAAF' || ESPN_LIVE_SPORTS.includes(sport);
}

/** "games", "fights", "matches" — one noun for the title and the nudge. */
export function eventNoun(sport: string, n: number): string {
  const one = sport === 'UFC' ? 'fight' : sport === 'ATP' || sport === 'WTA' ? 'match' : 'game';
  if (n === 1) return one;
  return one === 'match' ? 'matches' : `${one}s`;
}

/**
 * The chips to draw: sports with a game on the day, in SCOREBOARD_SPORTS
 * order, plus the open sport so the chip under the user's finger never
 * vanishes. With no game anywhere, the open sport alone.
 */
export function scoreboardChipSports(
  counts: Readonly<Record<string, number>>,
  open: ScoreboardSport,
): ScoreboardSport[] {
  return SCOREBOARD_SPORTS.filter((id) => id === open || (counts[id] ?? 0) > 0);
}

/**
 * How long a live_scoreboard row may still say the game is in progress.
 * The poller writes every minute while the game is on. Ten minutes covers a
 * few missed ticks and drops a poller that died.
 */
export const ESPN_LIVE_MAX_AGE_MS = 10 * 60 * 1000;

/**
 * How long an NCAAF state row may still say the game is in progress.
 * The loop writes on a score, period or possession change, not on every
 * clock tick, so a drive with none of those is silent for minutes. 45
 * minutes is the window that still covers a drive and drops a poller
 * that died. MLB uses the 15-minute snapshot rule in format.ts instead.
 */
export const NCAAF_LIVE_MAX_AGE_MS = 45 * 60 * 1000;

export const SCOREBOARD_MARKETS = ['h2h', 'spreads', 'totals'] as const;

export const SCOREBOARD_BOOK_NOTE = 'DK · tap for game ›';
/** A live card: the sheet lists every book the member uses (liveBookLines). */
export const SCOREBOARD_LIVE_BOOK_NOTE = 'DK · tap for your books ›';

export interface ScoreboardQuote {
  market: string;
  home_price?: number | string | null;
  away_price?: number | string | null;
  spread_home?: number | string | null;
  total_line?: number | string | null;
  over_price?: number | string | null;
  under_price?: number | string | null;
  snapshot_at?: string | null;
}

export interface ScoreboardGame {
  game_id: string;
  sport: string;
  game_date: string;
  home_team: string;
  away_team: string;
  home_score?: number | string | null;
  away_score?: number | string | null;
  commence_time?: string | null;
  went_to_ot?: number | string | null;
}

/** A stored live row, already judged fresh or terminal. Null fields stay null. */
export interface ScoreboardFeed {
  awayScore: number | null;
  homeScore: number | null;
  inProgress: boolean;
  ended: boolean;
  possession: 'home' | 'away' | null;
  clockLabel: string;
  situation: string | null;
  /** When the stored row was written. Shown next to LIVE. */
  snapshotAt: string;
}

export interface ScoreboardSide {
  name: string;
  disc: string;
  possession: boolean;
  score: string;
  scoreMuted: boolean;
  spread: string;
  spreadPrice: string;
  total: string;
  totalPrice: string;
  ml: string;
}

export interface ScoreboardCard {
  gameId: string;
  sport: string;
  phase: ScoreboardPhase;
  /** The game's listed start, for ordering. */
  commenceTime: string | null;
  away: ScoreboardSide;
  home: ScoreboardSide;
  showMl: boolean;
  footerBadge: 'LIVE' | 'F' | null;
  footerText: string;
  /** Clock time of the stored live row. Empty when the game is not live. */
  updatedLabel: string | null;
  situation: string | null;
  awayFull: string;
  homeFull: string;
  linesMuted: boolean;
  accessibilityLabel: string;
  /**
   * Markets whose odds cell is an in-play DraftKings quote.
   * A pre-game % is not shown on those cells.
   */
  liveQuotes: ReadonlySet<string>;
}

interface FeedRaw {
  state: string | null;
  stateName: string | null;
  situation: string | null;
}

function num(v: number | string | null | undefined): number | null {
  if (v == null || v === '') return null;
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

function scoreNum(v: number | string | null | undefined): number | null {
  const n = num(v);
  return n == null ? null : Math.round(n);
}

function dash(text: string | null | undefined): string {
  return text && text.length > 0 ? text : '—';
}

function priceText(v: number | string | null | undefined): string {
  const n = num(v);
  if (n == null) return '—';
  return trueMinus(formatAmerican(n));
}

function signed(n: number | null): string {
  if (n == null) return '—';
  const rounded = Math.round(n * 10) / 10;
  const body = Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
  if (rounded > 0) return `+${body}`;
  return trueMinus(body);
}

function plain(n: number | null): string {
  if (n == null) return '—';
  const rounded = Math.round(n * 10) / 10;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
}

/**
 * "Florida Gulf Coast" → "FGC", "Kentucky" → "KENT", "St. John's" → "SJ",
 * "UC Santa Barbara" → "UCSB" (a word already in capitals is kept whole).
 * At most four letters.
 */
function initialsLabel(name: string): string {
  const words = name
    .replace(/['’.]/g, '')
    .replace(/[^A-Za-z\s]/g, ' ')
    .split(/\s+/)
    .filter((w) => w.length > 0);
  if (words.length === 0) return name.slice(0, 4).toUpperCase();
  if (words.length === 1) return words[0].slice(0, 4).toUpperCase();
  return words
    .map((w) => (w.length > 1 && w.length <= 3 && w === w.toUpperCase() ? w : w[0]))
    .join('')
    .slice(0, 4)
    .toUpperCase();
}

/** Same last word too ("Iowa State" / "Illinois State"): the first word's first four letters. */
function firstWordLabel(name: string): string {
  const words = name.replace(/['’.]/g, '').replace(/[^A-Za-z\s]/g, ' ').split(/\s+/).filter((w) => w.length > 0);
  return (words[0] ?? name).slice(0, 4).toUpperCase();
}

/** Two sides with the same initials: the first four letters of each last word. */
function lastWordLabel(name: string): string {
  const words = name.replace(/['’.]/g, '').replace(/[^A-Za-z\s]/g, ' ').split(/\s+/).filter((w) => w.length > 0);
  return (words[words.length - 1] ?? name).slice(0, 4).toUpperCase();
}

export function discLabel(
  name: string,
  sport: string,
  abbrevs?: ReadonlyMap<string, string> | null,
): string {
  // A school or a person has no code of ours: initials in the disc, the
  // name beside it (sideName).
  if (SCHOOL_SPORTS.has(sport) || isVersusSport(sport)) return initialsLabel(name);
  const compact = compactTeam(name, sport, abbrevs);
  if (sport === 'NCAAF' && compact === name) {
    const letters = name.replace(/[^A-Za-z]/g, '');
    return (letters.slice(0, 3) || name.slice(0, 3)).toUpperCase();
  }
  return compact.slice(0, 5);
}

/**
 * The name beside the disc. A code sport repeats its code; a school keeps
 * its name; a fighter or tennis player is "F. Lastname", everything after
 * the first name kept ("Benoit Saint Denis" → "B. Saint Denis"), a
 * Jr./Sr./II/III dropped ("Rodolfo Vieira Jr." → "R. Vieira").
 */
export function sideName(
  name: string,
  sport: string,
  abbrevs?: ReadonlyMap<string, string> | null,
): string {
  if (SCHOOL_SPORTS.has(sport)) return name;
  if (isVersusSport(sport)) {
    const words = name.trim().split(/\s+/).filter((w) => w.length > 0);
    while (words.length > 2 && /^(jr|sr|ii|iii|iv)\.?$/i.test(words[words.length - 1])) words.pop();
    if (words.length < 2) return name.trim();
    return `${words[0][0].toUpperCase()}. ${words.slice(1).join(' ')}`;
  }
  return discLabel(name, sport, abbrevs);
}

/** UFC stores 1 / 0 for the winner and 0.5 / 0.5 for a draw: W, L, D. */
function fightResult(mine: number | string | null | undefined, theirs: number | string | null | undefined): string {
  const a = num(mine);
  const b = num(theirs);
  if (a == null || b == null) return '—';
  if (a === b) return 'D';
  return a > b ? 'W' : 'L';
}

/**
 * The market tabs a sport gets. A fight has no spread at DraftKings, so UFC
 * opens on the moneyline and has no Spread tab.
 */
export function scoreboardMarketsFor(sport: string): readonly ScoreboardMarket[] {
  return sport === 'UFC' ? ['h2h', 'totals'] : SCOREBOARD_MARKET_ORDER;
}

export function footballClock(
  period: number | null,
  clockSeconds: number | null,
  stateName: string | null,
): string {
  if (stateName && /half/i.test(stateName)) return 'Half · End Q2';
  if (period == null) return '';
  if (period === 2 && clockSeconds === 0) return 'Half · End Q2';
  const clock = clockText(clockSeconds);
  if (period > 4) {
    const n = period - 4;
    const tag = n === 1 ? 'OT' : `OT${n}`;
    return clock ? `${tag} ${clock}` : tag;
  }
  return clock ? `Q${period} ${clock}` : `Q${period}`;
}

function clockText(sec: number | null): string | null {
  if (sec == null || !Number.isFinite(sec)) return null;
  const s = Math.max(0, Math.round(sec));
  const mm = Math.floor(s / 60);
  const ss = s % 60;
  return `${mm}:${String(ss).padStart(2, '0')}`;
}

export function mlbClock(
  inning: number | null,
  half: string | null,
  outs: number | null,
): string {
  if (inning == null) return '';
  const side = half === 'top' ? 'Top ' : half === 'bottom' ? 'Bot ' : '';
  const base = `${side}${ordinal(inning)}`;
  if (outs == null) return base;
  return `${base} · ${outs} ${outs === 1 ? 'out' : 'outs'}`;
}

function ordinal(n: number): string {
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${n}th`;
  const suffix = { 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] ?? 'th';
  return `${n}${suffix}`;
}

export function runnersLine(bases: string | null | undefined): string | null {
  const label = basesLabel(bases ?? null);
  if (!label || label === 'Bases empty') return null;
  if (label === 'Bases loaded') return label;
  return `Runners on ${label}`;
}

function parseRaw(raw: string | null | undefined): FeedRaw {
  if (!raw) return { state: null, stateName: null, situation: null };
  try {
    const o = JSON.parse(raw) as Record<string, unknown>;
    const str = (k: string) => (typeof o[k] === 'string' && (o[k] as string).trim() ? (o[k] as string).trim() : null);
    return { state: str('state'), stateName: str('state_name'), situation: str('situation') };
  } catch {
    return { state: null, stateName: null, situation: null };
  }
}

function sideOf(v: string | null | undefined): 'home' | 'away' | null {
  if (v === 'home' || v === 'away') return v;
  return null;
}

export interface MlbLiveLike {
  snapshot_at: string;
  inning?: number | null;
  inning_half?: string | null;
  outs?: number | null;
  bases_state?: string | null;
  home_score?: number | null;
  away_score?: number | null;
  abstract_game_state?: string | null;
}

/** MLB row → feed. A stale non-final snapshot becomes null, not a frozen inning. */
export function feedFromMlb(row: MlbLiveLike | null | undefined, now: number): ScoreboardFeed | null {
  if (!row) return null;
  const state = row.abstract_game_state;
  const ended = state === 'Final';
  const ts = parseStamp(row.snapshot_at).getTime();
  const fresh = Number.isFinite(ts) && now - ts <= 15 * 60 * 1000;
  if (!ended && !fresh) return null;
  if (state !== 'Live' && state !== 'Final') return null;
  const half = row.inning_half === 'top' || row.inning_half === 'bottom' ? row.inning_half : null;
  return {
    awayScore: scoreNum(row.away_score),
    homeScore: scoreNum(row.home_score),
    inProgress: state === 'Live' && fresh,
    ended,
    possession: half === 'top' ? 'away' : half === 'bottom' ? 'home' : null,
    clockLabel: mlbClock(row.inning ?? null, half, row.outs ?? null),
    situation: runnersLine(row.bases_state),
    snapshotAt: row.snapshot_at,
  };
}

export interface NcaafLiveLike {
  snapshot_at: string;
  period?: number | null;
  clock_seconds?: number | null;
  home_score?: number | null;
  away_score?: number | null;
  possession?: string | null;
  down?: number | null;
  distance?: number | null;
  yardline_100?: number | null;
  raw_state?: string | null;
}

function footballSituation(row: NcaafLiveLike): string | null {
  if (row.down == null) return null;
  const down = ordinal(row.down);
  const goal = row.yardline_100 != null && row.distance != null && row.yardline_100 <= row.distance;
  if (goal) return `${down} & Goal`;
  if (row.distance == null) return down;
  return `${down} & ${row.distance}`;
}

export function feedFromNcaaf(row: NcaafLiveLike | null | undefined, now: number): ScoreboardFeed | null {
  if (!row) return null;
  const bits = parseRaw(row.raw_state);
  const ended = bits.state === 'post' || bits.state === 'final'
    || bits.stateName === 'final' || bits.stateName === 'STATUS_FINAL';
  const ts = parseStamp(row.snapshot_at).getTime();
  const fresh = Number.isFinite(ts) && now - ts >= 0 && now - ts <= NCAAF_LIVE_MAX_AGE_MS;
  const markedLive = bits.state === 'in' || bits.state === 'halftime'
    || (bits.stateName != null && /progress|half/i.test(bits.stateName));
  const scored = scoreNum(row.home_score) != null || scoreNum(row.away_score) != null;
  const inProgress = fresh && !ended && (markedLive || (bits.state == null && scored));
  if (!inProgress && !ended) return null;
  return {
    awayScore: scoreNum(row.away_score),
    homeScore: scoreNum(row.home_score),
    inProgress,
    ended,
    possession: sideOf(row.possession),
    clockLabel: footballClock(row.period ?? null, row.clock_seconds ?? null, bits.stateName),
    situation: bits.situation ?? footballSituation(row),
    snapshotAt: row.snapshot_at,
  };
}

export interface EspnLiveLike {
  snapshot_at: string;
  state: string;
  home_score?: number | null;
  away_score?: number | null;
  clock_label?: string | null;
  situation?: string | null;
  possession?: string | null;
}

/** live_scoreboard row → feed. A stale in-progress row becomes null. */
export function feedFromEspn(row: EspnLiveLike | null | undefined, now: number): ScoreboardFeed | null {
  if (!row) return null;
  const ended = row.state === 'post';
  const ts = parseStamp(row.snapshot_at).getTime();
  const fresh = Number.isFinite(ts) && now - ts >= -60_000 && now - ts <= ESPN_LIVE_MAX_AGE_MS;
  const inProgress = row.state === 'in' && fresh;
  if (!inProgress && !ended) return null;
  return {
    awayScore: scoreNum(row.away_score),
    homeScore: scoreNum(row.home_score),
    inProgress,
    ended,
    possession: inProgress ? sideOf(row.possession) : null,
    clockLabel: row.clock_label ?? '',
    situation: inProgress ? row.situation ?? null : null,
    snapshotAt: row.snapshot_at,
  };
}

/** Live first, then upcoming, then final; by start time inside each. */
export function orderScoreboard(cards: readonly ScoreboardCard[]): ScoreboardCard[] {
  const rank = (c: ScoreboardCard) => SCOREBOARD_PHASE_ORDER.indexOf(c.phase);
  const start = (c: ScoreboardCard) => {
    const t = c.commenceTime ? parseStamp(c.commenceTime).getTime() : NaN;
    return Number.isFinite(t) ? t : Number.MAX_SAFE_INTEGER;
  };
  return [...cards].sort((a, b) => rank(a) - rank(b) || start(a) - start(b) || a.gameId.localeCompare(b.gameId));
}

/**
 * Final when a score is stored on the game, or the feed says the game ended.
 * Live only from a fresh in-progress feed. A past start time is not live.
 */
export function scoreboardPhase(game: ScoreboardGame, feed: ScoreboardFeed | null): ScoreboardPhase {
  if (scoreNum(game.home_score) != null && scoreNum(game.away_score) != null) return 'final';
  if (feed?.ended) return 'final';
  if (feed?.inProgress) return 'live';
  return 'upcoming';
}

export interface InplayChunkResult {
  market: string;
  gameIds: readonly string[];
  ok: boolean;
  rows: readonly (ScoreboardQuote & { game_id: string })[];
  error: string | null;
}

/**
 * Fold one poll of per-market in-play reads onto the lines already shown.
 * A failed chunk keeps that market. A chunk that succeeds with no row
 * drops it, and the card uses the pregame number. Games that are no
 * longer live are left out.
 */
export function mergeDkInplay(
  prev: ReadonlyMap<string, readonly ScoreboardQuote[]>,
  liveIds: readonly string[],
  chunks: readonly InplayChunkResult[],
): { lines: Map<string, ScoreboardQuote[]>; error: string | null } {
  const byGame = new Map<string, Map<string, ScoreboardQuote>>();
  for (const id of liveIds) {
    const markets = new Map<string, ScoreboardQuote>();
    for (const quote of prev.get(id) ?? []) markets.set(quote.market, quote);
    byGame.set(id, markets);
  }
  let error: string | null = null;
  for (const chunk of chunks) {
    if (!chunk.ok) {
      if (!error && chunk.error) error = chunk.error;
      continue;
    }
    const found = new Map<string, ScoreboardQuote & { game_id: string }>();
    for (const row of chunk.rows) found.set(row.game_id, row);
    for (const id of chunk.gameIds) {
      const markets = byGame.get(id);
      if (!markets) continue;
      const row = found.get(id);
      if (row) markets.set(chunk.market, row);
      else markets.delete(chunk.market);
    }
  }
  const lines = new Map<string, ScoreboardQuote[]>();
  for (const [id, markets] of byGame) {
    if (markets.size > 0) lines.set(id, [...markets.values()]);
  }
  return { lines, error };
}

function mergedQuotes(
  pregame: readonly ScoreboardQuote[] | undefined,
  inplay: readonly ScoreboardQuote[] | undefined,
  phase: ScoreboardPhase,
): ScoreboardQuote[] {
  const out = new Map<string, ScoreboardQuote>();
  for (const row of pregame ?? []) out.set(row.market, row);
  if (phase === 'live') {
    for (const row of inplay ?? []) out.set(row.market, row);
  }
  return [...out.values()];
}

function quoteFor(quotes: readonly ScoreboardQuote[] | undefined, market: string): ScoreboardQuote | null {
  return quotes?.find((q) => q.market === market) ?? null;
}

function shownScores(
  game: ScoreboardGame,
  feed: ScoreboardFeed | null,
  phase: ScoreboardPhase,
): { away: number | null; home: number | null } {
  if (phase === 'upcoming') return { away: null, home: null };
  if (scoreNum(game.home_score) != null && scoreNum(game.away_score) != null) {
    return { away: scoreNum(game.away_score), home: scoreNum(game.home_score) };
  }
  if (feed && (feed.ended || feed.inProgress)) {
    return { away: feed.awayScore, home: feed.homeScore };
  }
  return { away: null, home: null };
}

export function presentScoreboard(input: {
  game: ScoreboardGame;
  pregame: readonly ScoreboardQuote[] | undefined;
  inplay: readonly ScoreboardQuote[] | undefined;
  feed: ScoreboardFeed | null;
  abbrevs?: ReadonlyMap<string, string> | null;
  /** Clock for "has it started". Injectable for tests. */
  now?: number;
}): ScoreboardCard {
  const { game, feed } = input;
  const phase = scoreboardPhase(game, feed);
  // Past its start with no live row: a stale or missing feed, not a game
  // that hasn't begun. Say so instead of printing a start time that passed.
  const startMs = game.commence_time ? parseStamp(game.commence_time).getTime() : NaN;
  const startedNoScore = phase === 'upcoming' && Number.isFinite(startMs)
    && startMs <= (input.now ?? Date.now());
  const lines = mergedQuotes(input.pregame, input.inplay, phase);
  const liveQuotes = new Set<string>();
  if (phase === 'live') {
    for (const row of input.inplay ?? []) {
      if (row.market) liveQuotes.add(row.market);
    }
  }
  const spread = quoteFor(lines, 'spreads');
  const total = quoteFor(lines, 'totals');
  const ml = quoteFor(lines, 'h2h');
  const homeSpread = num(spread?.spread_home);
  const totalLine = num(total?.total_line);
  const scores = shownScores(game, feed, phase);
  const awayScore = scores.away;
  const homeScore = scores.home;
  // UFC's stored 0.5 / 0.5 draw must not round to 1-1; compare raw.
  const fight = game.sport === 'UFC';
  const rawAway = num(game.away_score);
  const rawHome = num(game.home_score);
  const awayMuted = phase === 'final' && (fight
    ? rawAway != null && rawHome != null && rawAway < rawHome
    : awayScore != null && homeScore != null && awayScore < homeScore);
  const homeMuted = phase === 'final' && (fight
    ? rawAway != null && rawHome != null && rawHome < rawAway
    : awayScore != null && homeScore != null && homeScore < awayScore);
  const poss = phase === 'live' ? feed?.possession ?? null : null;
  const awayScoreText = fight && phase === 'final'
    ? fightResult(game.away_score, game.home_score)
    : awayScore == null ? '—' : String(awayScore);
  const homeScoreText = fight && phase === 'final'
    ? fightResult(game.home_score, game.away_score)
    : homeScore == null ? '—' : String(homeScore);

  const awayName = sideName(game.away_team, game.sport, input.abbrevs);
  const homeName = sideName(game.home_team, game.sport, input.abbrevs);

  let awayDisc = discLabel(game.away_team, game.sport, input.abbrevs);
  let homeDisc = discLabel(game.home_team, game.sport, input.abbrevs);
  if (awayDisc === homeDisc && isNameSport(game.sport)) {
    // "North Carolina" and "Northern Colorado" are both NC.
    awayDisc = lastWordLabel(game.away_team);
    homeDisc = lastWordLabel(game.home_team);
  }

  const away: ScoreboardSide = {
    name: awayName,
    disc: awayDisc,
    possession: poss === 'away',
    score: awayScoreText,
    scoreMuted: awayMuted,
    spread: signed(homeSpread == null ? null : -homeSpread),
    spreadPrice: priceText(spread?.away_price),
    total: totalLine == null ? '—' : `o${plain(totalLine)}`,
    totalPrice: priceText(total?.over_price),
    ml: priceText(ml?.away_price),
  };
  const home: ScoreboardSide = {
    name: homeName,
    disc: homeDisc,
    possession: poss === 'home',
    score: homeScoreText,
    scoreMuted: homeMuted,
    spread: signed(homeSpread),
    spreadPrice: priceText(spread?.home_price),
    total: totalLine == null ? '—' : `u${plain(totalLine)}`,
    totalPrice: priceText(total?.under_price),
    ml: priceText(ml?.home_price),
  };

  const ot = num(game.went_to_ot) === 1;
  let footerBadge: ScoreboardCard['footerBadge'] = null;
  let footerText = '';
  if (phase === 'live') {
    footerBadge = 'LIVE';
    footerText = feed?.clockLabel ?? '';
  } else if (phase === 'final') {
    footerBadge = 'F';
    footerText = ot ? 'Final/OT' : 'Final';
  } else {
    // A sport with no live feed will never show one: say so, not "yet".
    footerText = startedNoScore
      ? hasLiveFeed(game.sport) ? 'Started · no live score yet' : 'Started · live scores not tracked'
      : formatGameTimeET(game.commence_time);
  }

  const situation = phase === 'live' ? feed?.situation ?? null : null;
  const updatedLabel = phase === 'live' && feed?.snapshotAt
    ? `Updated ${formatGameTimeET(feed.snapshotAt)}`
    : null;
  const matchup = `${game.away_team} ${isVersusSport(game.sport) ? 'versus' : 'at'} ${game.home_team}`;
  const stateWord = phase === 'live' ? 'live' : phase === 'final' ? 'final' : startedNoScore ? 'started' : 'upcoming';
  const scoreSpeech = phase === 'upcoming'
    ? startedNoScore ? 'started, no score stored' : 'not started'
    : fight && phase === 'final'
      ? away.score === 'D' ? 'draw' : `${away.score === 'W' ? game.away_team : game.home_team} won`
      : `${away.score} to ${home.score}`;
  const possTeam = away.possession ? game.away_team : home.possession ? game.home_team : null;
  const possSpeech = possTeam
    ? game.sport === 'MLB' ? `${possTeam} batting. ` : `${possTeam} has the ball. `
    : '';
  const situationSpeech = situation ? `${situation}. ` : '';
  const lineSpeech = [
    lineSpeechSide(game.away_team, away, phase === 'upcoming'),
    lineSpeechSide(game.home_team, home, phase === 'upcoming'),
  ].join('. ');

  return {
    gameId: game.game_id,
    sport: game.sport,
    phase,
    commenceTime: game.commence_time ?? null,
    away,
    home,
    showMl: phase === 'upcoming',
    footerBadge,
    footerText,
    updatedLabel,
    situation,
    linesMuted: phase === 'final',
    awayFull: game.away_team,
    homeFull: game.home_team,
    liveQuotes,
    accessibilityLabel: `${matchup}, ${stateWord}, ${scoreSpeech}. ${possSpeech}${footerText}. ${situationSpeech}${lineSpeech}. ${updatedLabel ? `${updatedLabel}. ` : ''}DraftKings. ${phase === 'live' ? 'Opens live lines at your books.' : 'Opens the game.'}`,
  };
}

function lineSpeechSide(team: string, side: ScoreboardSide, showMl: boolean): string {
  const bits = [`${team}`];
  if (side.spread !== '—') bits.push(`spread ${side.spread} ${side.spreadPrice}`);
  if (side.total !== '—') bits.push(`total ${side.total} ${side.totalPrice}`);
  if (showMl && side.ml !== '—') bits.push(`moneyline ${side.ml}`);
  return bits.join(', ');
}

export function nextSlateText(
  game: { away_team: string; home_team: string; commence_time?: string | null; sport: string } | null,
  abbrevs?: ReadonlyMap<string, string> | null,
): string | null {
  if (!game) return null;
  const when = formatDayTimeET(game.commence_time);
  const away = sideName(game.away_team, game.sport, abbrevs);
  const home = sideName(game.home_team, game.sport, abbrevs);
  const matchup = `${away} ${isVersusSport(game.sport) ? 'vs' : '@'} ${home}`;
  return when ? `${when} · ${matchup}` : matchup;
}

export function scoreboardSwitchLine(
  counts: Readonly<Record<string, number>>,
  sport: string,
  dayPhrase = 'today',
): string | null {
  let best: string | null = null;
  let n = 0;
  for (const [name, count] of Object.entries(counts)) {
    if (name === sport || count <= n) continue;
    best = name;
    n = count;
  }
  if (!best || n === 0) return null;
  return `Or switch sport above — ${sportDisplayName(best)} has ${n} ${eventNoun(best, n)} ${dayPhrase}.`;
}

export function movementText(
  open: ScoreboardQuote | null,
  now: ScoreboardQuote | null,
  market: 'h2h' | 'spreads' | 'totals',
): string | null {
  const a = leg(open, market);
  const b = leg(now, market);
  if (!a && !b) return null;
  if (!a || a === b) return b;
  if (!b) return `Opened ${a}`;
  return `Opened ${a} · Now ${b}`;
}

function leg(q: ScoreboardQuote | null, market: 'h2h' | 'spreads' | 'totals'): string | null {
  if (!q) return null;
  if (market === 'spreads') {
    const line = signed(num(q.spread_home));
    const price = priceText(q.home_price);
    if (line === '—' && price === '—') return null;
    return `${line} ${price}`.trim();
  }
  if (market === 'totals') {
    const line = plain(num(q.total_line));
    const price = priceText(q.over_price);
    if (line === '—' && price === '—') return null;
    return `o${line} ${price}`.trim();
  }
  const away = priceText(q.away_price);
  const home = priceText(q.home_price);
  if (away === '—' && home === '—') return null;
  return `${away} / ${home}`;
}

/** The minus the cards print. Exported so a test can see it is U+2212. */
export const SCOREBOARD_MINUS = MINUS;

// ── % bets / % money (Matt, 2026-10-29) ─────────────────────────────────────
// The board shows one market at a time: Odds, % Bets and % Money per side,
// from scoreboard_splits. Since 2026-11-16 that is DraftKings' own split
// (data/ingestors/dk_splits.py, source 'dk_network'), matching the board's
// "DK" label; the read filters on source. A side with no DK split shows a
// dash. An arrow marks a split that has moved SPLIT_MOVE_POINTS or more
// since the first DK split stored for that side (open_*).
// The percent is the one measured at line_value. It is shown only when that
// number is the line in the odds cell. An in-play DraftKings quote is a
// different line, so the frozen pre-game percent is a dash there too.

export type ScoreboardMarket = 'spreads' | 'totals' | 'h2h';
export const SCOREBOARD_MARKET_ORDER: readonly ScoreboardMarket[] = ['spreads', 'totals', 'h2h'];

export function scoreboardMarketLabel(market: ScoreboardMarket, sport: string): string {
  if (market === 'totals') return 'Total';
  if (market === 'h2h') return 'ML';
  return sport === 'NHL' ? 'Puck line' : 'Spread';
}

export interface ScoreboardSplitRow {
  game_id: string;
  market: string;
  side: string;
  bet_pct: number | string | null;
  money_pct: number | string | null;
  /** The number the percent was measured at. Null on a moneyline. */
  line_value?: number | string | null;
  /** The first DraftKings split stored for this side (the arrow's base). */
  open_bet_pct?: number | string | null;
  open_money_pct?: number | string | null;
}

/** Points a split must move from its opening before it gets an arrow. */
export const SPLIT_MOVE_POINTS = 3;

/** One line under the column labels saying what the source and arrow are. */
export const SPLITS_LEGEND = `DraftKings splits · ▲▼ moved ${SPLIT_MOVE_POINTS}+ points since DK's first split`;

export type SplitMove = 'up' | 'down' | null;

/** The line on the card for one market, and whether that cell is in-play. */
export interface ShownSplitLine {
  away: number | null;
  home: number | null;
  live: boolean;
}

export interface SideSplit {
  bets: number | null;
  money: number | null;
  /** Direction since the opening split, when it moved SPLIT_MOVE_POINTS+. */
  betsMove?: SplitMove;
  moneyMove?: SplitMove;
  /** The rounded opening the move is measured from, for VoiceOver. */
  betsOpen?: number | null;
  moneyOpen?: number | null;
}

/** 'up' / 'down' when `now` is SPLIT_MOVE_POINTS or more from `open`. */
export function splitMove(now: number | null, open: number | string | null | undefined): SplitMove {
  const o = num(open);
  if (now == null || o == null || o < 0 || o > 100) return null;
  const d = now - Math.round(o);
  if (d >= SPLIT_MOVE_POINTS) return 'up';
  if (d <= -SPLIT_MOVE_POINTS) return 'down';
  return null;
}

function lineNumber(text: string): number | null {
  if (!text || text === '—') return null;
  const cleaned = text.replace(/^[ou]/, '').split(MINUS).join('-').trim();
  return num(cleaned);
}

function sameLine(measured: number | string | null | undefined, displayed: number | null): boolean {
  const m = num(measured);
  if (m == null || displayed == null) return false;
  return Math.abs(m - displayed) < 0.001;
}

/** The number in each odds cell, and whether that cell is an in-play quote. */
export function shownSplitLine(card: ScoreboardCard, market: ScoreboardMarket): ShownSplitLine {
  if (market === 'h2h') {
    return { away: null, home: null, live: card.liveQuotes.has(market) };
  }
  return {
    away: lineNumber(marketCell(card.away, market).value),
    home: lineNumber(marketCell(card.home, market).value),
    live: card.liveQuotes.has(market),
  };
}

/**
 * The two rows of a card for one market. Totals follow the card's own
 * layout: Over on the away row, Under on the home row.
 * Spread and total percents show only when line_value is the number in
 * that cell. A live DraftKings quote shows neither, even at the same number:
 * the stored row is the last pre-start split.
 */
export function splitsFor(
  rows: readonly ScoreboardSplitRow[] | undefined,
  market: ScoreboardMarket,
  shown?: ShownSplitLine,
): { away: SideSplit; home: SideSplit } {
  const blank: SideSplit = { bets: null, money: null };
  const pick = (side: string, displayed: number | null): SideSplit => {
    if (shown?.live) return blank;
    const row = rows?.find((r) => r.market === market && r.side === side);
    if (market !== 'h2h' && !sameLine(row?.line_value, displayed)) return blank;
    const pct = (v: number | string | null | undefined) => {
      const n = num(v);
      return n == null || n < 0 || n > 100 ? null : Math.round(n);
    };
    const bets = pct(row?.bet_pct);
    const money = pct(row?.money_pct);
    return {
      bets,
      money,
      betsMove: splitMove(bets, row?.open_bet_pct),
      moneyMove: splitMove(money, row?.open_money_pct),
      betsOpen: pct(row?.open_bet_pct),
      moneyOpen: pct(row?.open_money_pct),
    };
  };
  return market === 'totals'
    ? { away: pick('over', shown?.away ?? null), home: pick('under', shown?.home ?? null) }
    : { away: pick('away', shown?.away ?? null), home: pick('home', shown?.home ?? null) };
}

export function pctText(n: number | null): string {
  return n == null ? '—' : `${n}%`;
}

/** The odds cell of one card row for one market. */
export function marketCell(side: ScoreboardSide, market: ScoreboardMarket): { value: string; price: string } {
  if (market === 'totals') return { value: side.total, price: side.totalPrice };
  if (market === 'h2h') return { value: side.ml, price: '' };
  return { value: side.spread, price: side.spreadPrice };
}

/** What VoiceOver reads for one card's splits in one market. */
export function splitsSpeech(
  card: ScoreboardCard,
  market: ScoreboardMarket,
  splits: { away: SideSplit; home: SideSplit },
): string {
  const label = market === 'totals' ? 'Total' : market === 'h2h' ? 'Moneyline' : 'Spread';
  const empty = (s: SideSplit) => s.bets == null && s.money == null;
  if (empty(splits.away) && empty(splits.home)) return '';
  const moved = (m: SplitMove | undefined, open: number | null | undefined) =>
    m && open != null ? `, ${m} from ${open} at open` : '';
  const side = (name: string, s: SideSplit) =>
    empty(s)
      ? `${name} no split`
      : `${name} ${s.bets ?? 'no'} percent of bets${moved(s.betsMove, s.betsOpen)}, `
        + `${s.money ?? 'no'} percent of money${moved(s.moneyMove, s.moneyOpen)}`;
  const awayName = market === 'totals' ? 'Over' : card.awayFull;
  const homeName = market === 'totals' ? 'Under' : card.homeFull;
  return `${label}: ${side(awayName, splits.away)}; ${side(homeName, splits.home)}.`;
}

// ── The pick card's score pill (Matt, 2026-11-24) ──────────────────────────
// A pick card reads the SAME feed this board reads, so a live NCAAB card shows
// "35–39 · Half" instead of a bare LIVE badge.

/** The fields of a game the card's score pill reads. */
export interface FeedGame {
  sport: string;
  home_team: string;
  away_team: string;
  home_score: number | null;
  away_score: number | null;
}

/** One side of a labelled score: "SJ 50". */
export interface ScoreSide {
  label: string;
  score: number;
  /** The side the pick is on. Only a home / away pick marks one. */
  picked: boolean;
}

/**
 * The score as two labelled sides, away first — the order of the card's
 * "Away @ Home" header (Matt, 2026-11-27: a bare "50–59" read as our team
 * first). Labels are the Scoreboard tab's discs, so the two screens name a
 * side the same way. A totals, prop or draw pick marks neither side: there is
 * no team of ours in the score.
 */
export function scoreSides(
  game: { sport: string; away_team: string; home_team: string } | null | undefined,
  awayScore: number | null | undefined,
  homeScore: number | null | undefined,
  pickSide?: string | null,
  abbrevs?: ReadonlyMap<string, string> | null,
): { away: ScoreSide; home: ScoreSide } | null {
  if (!game || awayScore == null || homeScore == null) return null;
  const label = (name: string) =>
    // NCAAF with no code in the map: initials ("Ohio State" OS), not the
    // first three letters ("OHI"), so a screen without the map still names
    // the school recognisably (UX review, 2026-11-27).
    game.sport === 'NCAAF' && !abbrevs?.get(name)?.trim()
      ? initialsLabel(name)
      : discLabel(name, game.sport, abbrevs);
  let away = label(game.away_team);
  let home = label(game.home_team);
  // Same initials: last words ("CARO" / "COLO"); same last word too ("Iowa
  // State" / "Illinois State"): first words; still the same: no labels, the
  // bare score, rather than two identical names (UX review, 2026-11-27).
  if (away === home) {
    away = lastWordLabel(game.away_team);
    home = lastWordLabel(game.home_team);
  }
  if (away === home) {
    away = firstWordLabel(game.away_team);
    home = firstWordLabel(game.home_team);
  }
  if (away === home) return null;
  return {
    away: { label: away, score: awayScore, picked: pickSide === 'away' },
    home: { label: home, score: homeScore, picked: pickSide === 'home' },
  };
}

export interface FeedView {
  kind: 'live' | 'final';
  /** Raw numbers behind `score`, for the labelled pill. */
  awayScore: number | null;
  homeScore: number | null;
  score: string;
  clock: string;
  speech: string;
}

/**
 * The pill from the Scoreboard's feed, or null to fall back to `live` / the
 * clock. A score already stored on `games` wins: that is the settled result.
 */
export function feedView(
  game: FeedGame | null | undefined,
  feed: ScoreboardFeed | null | undefined,
  now: number = Date.now(),
): FeedView | null {
  if (!game || !feed) return null;
  if (game.home_score != null && game.away_score != null) return null;
  // A read that failed keeps the last feed, so its age is checked here, at
  // render, not only when it was fetched: a frozen score never reads LIVE.
  // The pill then falls back to the bare badge (UX review).
  if (!feed.ended) {
    const maxAge = game.sport === 'NCAAF' ? NCAAF_LIVE_MAX_AGE_MS : ESPN_LIVE_MAX_AGE_MS;
    const ts = parseStamp(feed.snapshotAt).getTime();
    if (!Number.isFinite(ts) || now - ts > maxAge) return null;
  }
  const score = feed.awayScore != null && feed.homeScore != null ? `${feed.awayScore}–${feed.homeScore}` : '';
  const said =
    feed.awayScore != null && feed.homeScore != null
      ? `${game.away_team} ${feed.awayScore}, ${game.home_team} ${feed.homeScore}`
      : '';
  if (feed.ended) {
    if (!score) return null;
    return { kind: 'final', awayScore: feed.awayScore, homeScore: feed.homeScore, score, clock: '', speech: `Final, ${said}` };
  }
  if (!feed.inProgress) return null;
  const clock = feed.clockLabel.trim();
  return {
    kind: 'live',
    awayScore: feed.awayScore,
    homeScore: feed.homeScore,
    score,
    clock,
    speech: ['Live', clock, said].filter((p) => p.length > 0).join(', '),
  };
}

// ── Live lines at the member's books (the game sheet) ─────────────────────────

/**
 * After this long with no new row, a book's live number is shown as "No move
 * in 22m" rather than with a plain age. A row is written when the book CHANGES
 * the number (the odds feed stamps the market's own last_update; DraftKings'
 * board writes only a changed read, data/ingestors/dk_live_board.py), so an old
 * row is a line that has not moved, or a book that stopped posting it, and the
 * stored rows cannot tell the two apart. The number stays on screen, said to be
 * that old, rather than vanishing while the book may still offer it (UX review,
 * 2026-11-25).
 */
export const LIVE_BOOK_QUIET_MS = 15 * 60 * 1000;

/** The fields of an in-play odds row this file reads. */
export interface LiveBookRow {
  market: string;
  bookmaker: string;
  home_price?: number | string | null;
  away_price?: number | string | null;
  spread_home?: number | string | null;
  total_line?: number | string | null;
  over_price?: number | string | null;
  under_price?: number | string | null;
  snapshot_at?: string | null;
}

/** The line on top and the price under it, as the matchup rows draw them. */
export interface LiveBookCell {
  main: string;
  sub?: string;
}

export interface LiveBookLine {
  book: string;
  /** The away side, or the over. */
  away: LiveBookCell;
  /** The home side, or the under. */
  home: LiveBookCell;
  /** "+3.5 at −110", "over 220.5 at −112", "+135". */
  awaySpoken: string;
  homeSpoken: string;
  /** "Now", "4m ago", or "No move in 22m" once quiet. */
  age: string;
  /** "moved just now", "moved 4 minutes ago", "no move in 22 minutes". */
  ageSpoken: string;
  quiet: boolean;
}

/** The age of a book's newest live row, for the eye and for VoiceOver. */
export function liveAge(ms: number): { age: string; ageSpoken: string; quiet: boolean } {
  const min = Math.max(0, Math.floor(ms / 60_000));
  const minutes = `${min} minute${min === 1 ? '' : 's'}`;
  if (ms > LIVE_BOOK_QUIET_MS) {
    return { age: `No move in ${min}m`, ageSpoken: `no move in ${minutes}`, quiet: true };
  }
  if (min < 1) return { age: 'Now', ageSpoken: 'moved just now', quiet: false };
  return { age: `${min}m ago`, ageSpoken: `moved ${minutes} ago`, quiet: false };
}

/**
 * One line per book the member uses that has an in-play row for the market,
 * in the member's own book order. Each book shows its OWN number: a live line
 * moves every few seconds and books disagree, so nothing here picks an anchor
 * or a best. A row without its line or without both prices is no line.
 */
export function liveBookLines(
  rows: readonly LiveBookRow[],
  market: 'h2h' | 'spreads' | 'totals',
  books: readonly string[],
  now: number = Date.now(),
): LiveBookLine[] {
  const rank = new Map(books.map((b, i) => [b, i] as const));
  const newestByBook = new Map<string, LiveBookRow>();
  for (const r of rows) {
    if (r.market !== market || !rank.has(r.bookmaker)) continue;
    const prev = newestByBook.get(r.bookmaker);
    if (!prev || parseStamp(r.snapshot_at ?? '').getTime() > parseStamp(prev.snapshot_at ?? '').getTime()) {
      newestByBook.set(r.bookmaker, r);
    }
  }
  const out: { at: number; line: LiveBookLine }[] = [];
  for (const [book, r] of newestByBook) {
    const at = parseStamp(r.snapshot_at ?? '').getTime();
    if (!Number.isFinite(at)) continue;
    let line: Omit<LiveBookLine, 'age' | 'ageSpoken' | 'quiet'>;
    if (market === 'spreads') {
      const sp = num(r.spread_home);
      if (sp == null || num(r.home_price) == null || num(r.away_price) == null) continue;
      const a = { main: signed(-sp), sub: priceText(r.away_price) };
      const h = { main: signed(sp), sub: priceText(r.home_price) };
      line = { book, away: a, home: h, awaySpoken: `${a.main} at ${a.sub}`, homeSpoken: `${h.main} at ${h.sub}` };
    } else if (market === 'totals') {
      const t = num(r.total_line);
      if (t == null || num(r.over_price) == null || num(r.under_price) == null) continue;
      const a = { main: `o${plain(t)}`, sub: priceText(r.over_price) };
      const h = { main: `u${plain(t)}`, sub: priceText(r.under_price) };
      line = {
        book, away: a, home: h,
        awaySpoken: `over ${plain(t)} at ${a.sub}`, homeSpoken: `under ${plain(t)} at ${h.sub}`,
      };
    } else {
      if (num(r.home_price) == null || num(r.away_price) == null) continue;
      const a = { main: priceText(r.away_price) };
      const h = { main: priceText(r.home_price) };
      line = { book, away: a, home: h, awaySpoken: a.main, homeSpoken: h.main };
    }
    out.push({ at: rank.get(book) ?? 0, line: { ...line, ...liveAge(now - at) } });
  }
  return out.sort((a, b) => a.at - b.at).map((x) => x.line);
}
