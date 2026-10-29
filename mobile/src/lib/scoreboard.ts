/**
 * Picks → Scoreboard. One card per game, DraftKings game markets only.
 *
 * Live scores are whatever a stored feed already wrote: MLB from
 * live_game_state, NCAAF from ncaaf_live_states, and NFL / NBA / NHL from
 * live_scoreboard (data/ingestors/live_scoreboard.py, every minute from
 * ESPN, Matt 2026-10-29). A clock that has passed is not a score. A game
 * with no fresh stored row stays Upcoming until `games` has a final score.
 * Nothing here fills a number in.
 */

import {
  MINUS,
  basesLabel,
  formatAmerican,
  formatDayTimeET,
  formatGameTimeET,
  parseStamp,
} from '@/lib/format';
import { compactTeam, trueMinus } from '@/lib/signalsCard';

export const SCOREBOARD_SPORTS = ['NFL', 'NCAAF', 'MLB', 'NBA', 'NHL'] as const;
export type ScoreboardSport = (typeof SCOREBOARD_SPORTS)[number];

export type ScoreboardPhase = 'upcoming' | 'live' | 'final';

/** One list per sport, in this order (Matt, 2026-10-29: no status filter). */
export const SCOREBOARD_PHASE_ORDER: readonly ScoreboardPhase[] = ['live', 'upcoming', 'final'];

/** Sports whose live score comes from live_scoreboard. */
export const ESPN_LIVE_SPORTS: readonly string[] = ['NFL', 'NBA', 'NHL'];

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

export function discLabel(
  name: string,
  sport: string,
  abbrevs?: ReadonlyMap<string, string> | null,
): string {
  const compact = compactTeam(name, sport, abbrevs);
  if (sport === 'NCAAF' && compact === name) {
    const letters = name.replace(/[^A-Za-z]/g, '');
    return (letters.slice(0, 3) || name.slice(0, 3)).toUpperCase();
  }
  return compact.slice(0, 5);
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
  const spread = quoteFor(lines, 'spreads');
  const total = quoteFor(lines, 'totals');
  const ml = quoteFor(lines, 'h2h');
  const homeSpread = num(spread?.spread_home);
  const totalLine = num(total?.total_line);
  const scores = shownScores(game, feed, phase);
  const awayScore = scores.away;
  const homeScore = scores.home;
  const awayMuted = phase === 'final' && awayScore != null && homeScore != null && awayScore < homeScore;
  const homeMuted = phase === 'final' && awayScore != null && homeScore != null && homeScore < awayScore;
  const poss = phase === 'live' ? feed?.possession ?? null : null;

  const awayName = discLabel(game.away_team, game.sport, input.abbrevs);
  const homeName = discLabel(game.home_team, game.sport, input.abbrevs);

  const away: ScoreboardSide = {
    name: awayName,
    disc: awayName,
    possession: poss === 'away',
    score: awayScore == null ? '—' : String(awayScore),
    scoreMuted: awayMuted,
    spread: signed(homeSpread == null ? null : -homeSpread),
    spreadPrice: priceText(spread?.away_price),
    total: totalLine == null ? '—' : `o${plain(totalLine)}`,
    totalPrice: priceText(total?.over_price),
    ml: priceText(ml?.away_price),
  };
  const home: ScoreboardSide = {
    name: homeName,
    disc: homeName,
    possession: poss === 'home',
    score: homeScore == null ? '—' : String(homeScore),
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
    footerText = startedNoScore ? 'Started · no live score yet' : formatGameTimeET(game.commence_time);
  }

  const situation = phase === 'live' ? feed?.situation ?? null : null;
  const updatedLabel = phase === 'live' && feed?.snapshotAt
    ? `Updated ${formatGameTimeET(feed.snapshotAt)}`
    : null;
  const matchup = `${game.away_team} at ${game.home_team}`;
  const stateWord = phase === 'live' ? 'live' : phase === 'final' ? 'final' : startedNoScore ? 'started' : 'upcoming';
  const scoreSpeech = phase === 'upcoming'
    ? startedNoScore ? 'started, no score stored' : 'not started'
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
    accessibilityLabel: `${matchup}, ${stateWord}, ${scoreSpeech}. ${possSpeech}${footerText}. ${situationSpeech}${lineSpeech}. ${updatedLabel ? `${updatedLabel}. ` : ''}DraftKings. Opens the game.`,
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
  const away = discLabel(game.away_team, game.sport, abbrevs);
  const home = discLabel(game.home_team, game.sport, abbrevs);
  const matchup = `${away} @ ${home}`;
  return when ? `${when} · ${matchup}` : matchup;
}

export function scoreboardSwitchLine(
  counts: Readonly<Record<string, number>>,
  sport: string,
): string | null {
  let best: string | null = null;
  let n = 0;
  for (const [name, count] of Object.entries(counts)) {
    if (name === sport || count <= n) continue;
    best = name;
    n = count;
  }
  if (!best || n === 0) return null;
  const games = n === 1 ? 'game' : 'games';
  return `Or switch sport above — ${best} has ${n} ${games} today.`;
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
