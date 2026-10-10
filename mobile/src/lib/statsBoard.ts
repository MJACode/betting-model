/**
 * Pure ranking/filtering logic for the Stats tab leaderboard.
 *
 * Two concerns live here so they behave identically in every sport and in
 * both modes (Hit Rates / Averages), and so they can be verified offline:
 *
 *  1. SORT — the board is ordered by the number it displays (hit rate), with
 *     sample size as the tie-break. Deliberately NOT a shrinkage-adjusted rank,
 *     and no longer switchable: when the visible column doesn't explain the
 *     order, the list reads as broken.
 *
 *  2. TONIGHT — "only players in action", and the "7:05 PM ET · @ SEA"
 *     subline under each row's name. Both are derived from the `games` table
 *     rather than the MLB/WNBA matchup views, so they work for every sport.
 *
 * There is deliberately NO games-played qualifier (removed 2026-08-30, Matt's
 * call, every sport and both modes). The board shows every player the query
 * returned; sample size is visible on the row and is the tie-break in every
 * sort, so a small-sample player is legible rather than hidden.
 *
 * Verify with: npx tsx scripts/verify_stats_board.ts
 */

// Relative, not '@/…': the verify script below runs this module under tsx,
// which does not resolve the bundler alias for a VALUE import (a type-only
// import is erased, which is why '@/types' can stay).
import { formatGameTimeET, gameStatus, weekdayShortET } from './format';
import type { ErrorKind } from './errors';
import type { GameRow } from '@/types';
import { normalizePlayerName } from './playerNews';

// ── 1. Sort ──

/**
 * The board has ONE order: the number it displays, best first, with sample
 * size as the tie-break.
 *
 * It used to offer hit rate / games played / average in the filter sheet; that
 * picker was removed 2026-09-12 (Matt's call). Three orders for a board whose
 * headline column is the thing you came to rank by is a control that mostly
 * gets set by accident, and a board sorted by something other than the column
 * you are reading looks broken — the reason this was never a shrinkage-adjusted
 * rank either. Games played and average are both still ON the row, so the
 * numbers that drove the other two orders never left the screen.
 */

/** A row reduced to the two numbers the order needs. */
export interface SortableRow {
  /** Hit rate 0..1 in Hit Rates mode; the ranked stat value in Averages mode. */
  primary: number;
  /** Games behind the number (hit-rate denominator / games played). */
  games: number;
}

export function compareRows(a: SortableRow, b: SortableRow): number {
  return b.primary - a.primary || b.games - a.games;
}

// ── 2. Hit-rate band ──

/**
 * The slider's percent bounds (0..100) as a 0..1 band.
 *
 * Numbers rather than the strings the old min/max text fields produced — the
 * fields became a two-thumb slider on 2026-09-12, so there is no longer any
 * such thing as a blank or a typo to parse. Out-of-range values are still
 * clamped and an inverted band (min 80, max 60) is still normalised rather
 * than emptying the board: the slider cannot produce either, but neither can
 * silently wrong an answer here.
 */
export function hitRateBand(min: number, max: number): { lo: number; hi: number } {
  const parse = (n: number, fallback: number) =>
    Number.isFinite(n) ? Math.min(100, Math.max(0, n)) / 100 : fallback;
  const lo = parse(min, 0);
  const hi = parse(max, 1);
  return lo <= hi ? { lo, hi } : { lo: hi, hi: lo };
}

export function inHitRateBand(pct: number, band: { lo: number; hi: number }): boolean {
  // Tolerance absorbs float noise so "min 60" keeps an exact 0.6 (3/5).
  return pct >= band.lo - 1e-9 && pct <= band.hi + 1e-9;
}

/** Quick-pick minimums offered above the slider. */
export const HIT_RATE_PRESETS = [50, 60, 70, 80];

/** The band slider's scale, in whole percent. */
export const HIT_RATE_MIN = 0;
export const HIT_RATE_MAX = 100;
/**
 * Snap interval. 5 rather than 1 because a 1% step on a ~300pt track is a
 * sub-3pt target that no thumb can hold, and because nothing on this board
 * lands between two 5s that matters: a last-5 window quantises to 20%, last-10
 * to 10%, and the presets are all multiples of 5 so every chip is also a
 * reachable drag position (pinned in verify_stats_board.ts).
 */
export const HIT_RATE_STEP = 5;

/**
 * Does this player actually PLAY the selected stat?
 *
 * The football player logs span every position, so a kicker has a real row with
 * 0 passing yards in every game — and on an "at most N pass yards" board those
 * non-participants go 15/15 and bury the actual quarterbacks (they'd also pad
 * the bottom of every "at least" board). A player whose value is zero in EVERY
 * loaded game isn't in that stat's market at all, so football boards drop them.
 *
 * FOOTBALL-ONLY on purpose: in the single-role sports a string of zeros is a
 * real outcome of participation — a batter 0-for-his-last-10 genuinely answers
 * "at most 1 hits" and must stay on the board.
 */
const MULTI_ROLE_SPORTS = new Set(['NFL', 'NCAAF']);

/**
 * Stats where ZERO is the usual answer, not a sign of a non-participant. A
 * receiver with no touchdown this season is still in the Anytime TD market —
 * the book prices him tonight — and dropping him hid George Pickens, Chris
 * Godwin and fourteen other ball-carriers off the TB @ DAL board (Matt,
 * 2026-10-08: "It should show everyone regardless if they have scored this
 * year"). For these, taking part means TOUCHING THE BALL, read off the usage
 * columns, not scoring.
 */
const ZERO_IS_AN_ANSWER_KEYS: ReadonlySet<string> = new Set(['rush_rec_tds']);

/** Does this stat's football board need to know who touched the ball? */
export function needsTouchSet(sport: string, statKey: string | null | undefined): boolean {
  return MULTI_ROLE_SPORTS.has(sport) && statKey != null && ZERO_IS_AN_ANSWER_KEYS.has(statKey);
}

/**
 * The touch set a late response is allowed to commit, or null when a newer
 * load has taken the board.
 *
 * The season and H2H reads beside this one drop a response whose stamp is no
 * longer `inFlight`. The touch read is fired and not awaited, so without the
 * same check a response for the sport and player type the user has left
 * overwrites the set that just landed. The key then no longer matches, and
 * Season and H2H Anytime TD would have to answer without a set (review of
 * #898). An empty id set is not committed: that is not a real answer.
 */
export function touchSetFromResponse(
  inFlight: string | null,
  stamp: string,
  touchKey: string,
  ids: Set<string>,
): { key: string; ids: Set<string> } | null {
  if (touchCommitAction(inFlight, stamp, ids.size) !== 'commit') return null;
  return { key: touchKey, ids };
}

/**
 * What a touch-totals response may do. A load the user has left is ignored.
 * An empty id set is not "nobody touched the ball" — committing it would mark
 * every zero-TD carrier as untouched — so it fails like a rejected read.
 */
export function touchCommitAction(
  inFlight: string | null,
  stamp: string,
  idCount: number,
): 'ignore' | 'fail' | 'commit' {
  if (inFlight !== stamp) return 'ignore';
  if (idCount <= 0) return 'fail';
  return 'commit';
}

/**
 * Whether a rejected touch read should mark this key failed.
 *
 * A superseded stamp is ignored, abort or not: that rejection belongs to a
 * load the user has left. An abort of the load still on screen is a failure.
 * Leaving it unrecorded holds the skeleton until the question changes.
 */
export function touchRejectionRecordsFailure(inFlight: string | null, stamp: string): boolean {
  if (inFlight !== stamp) return false;
  // Including an abort of this stamp. Leaving it unrecorded holds the skeleton.
  return true;
}

export interface TouchSet {
  key: string;
  ids: Set<string>;
}

/**
 * Ask for the touch set when Anytime TD needs one we do not have, and again
 * after a failure — the next load and pull-to-refresh both call this. A key
 * that already has a set and has not failed is not asked again.
 */
export function shouldFetchTouchSet(
  needed: boolean,
  haveSetForKey: boolean,
  failedForKey: boolean,
): boolean {
  return needed && (!haveSetForKey || failedForKey);
}

/**
 * A failed touch read. A response for a load the user has left changes
 * nothing. A current failure never drops a set: the last good one for this
 * key stays on screen, and a set for another key stays for the way back.
 * The failed key is recorded so the next load retries.
 */
export function touchSetAfterFailure(
  failedKey: string | null,
  inFlight: string | null,
  stamp: string,
  touchKey: string,
): string | null {
  if (inFlight !== stamp) return failedKey;
  return touchKey;
}

/**
 * The `touched` flag Season and H2H pass. Those reads have no usage columns
 * (`games` is empty). A set for this key answers the question. Anything else
 * — no set, or a set for another sport or player type — is unknown, and
 * `isStatParticipant` then fails closed.
 */
export function seasonTouchFlag(
  gamesEmpty: boolean,
  setKey: string | null | undefined,
  touchKey: string,
  inSet: boolean,
): boolean | undefined {
  if (!gamesEmpty || setKey !== touchKey) return undefined;
  return inSet;
}

export type TouchBoardView = 'list' | 'loading' | 'error';

/**
 * What Season and H2H Anytime TD may paint. A set for this key is the list,
 * including while a retry of that key is in flight. With no set, a failure
 * is an error line; until the read resolves the board stays on its skeleton.
 * Anything that does not need the set paints its rows.
 */
export function touchBoardView(
  needed: boolean,
  setKey: string | null | undefined,
  touchKey: string,
  failedForKey: boolean,
): TouchBoardView {
  if (!needed || setKey === touchKey) return 'list';
  if (failedForKey) return 'error';
  return 'loading';
}

const TOUCH_SET_TITLE = 'Couldn’t load this list';

/** Designer, #899. A missing kind uses the server line, never a blank. */
const TOUCH_SET_CAUSE: Record<ErrorKind, string> = {
  offline: 'You’re offline. Check your connection, then try again.',
  slow: 'Signalbase is slow to respond right now. Try again in a moment.',
  auth: 'Your session has expired. Try again, or sign out and back in.',
  server: 'Something went wrong on our side. Try again in a moment.',
};

export function touchSetCopy(kind: ErrorKind | null | undefined): {
  title: string;
  cause: string;
  kind: ErrorKind;
} {
  const k: ErrorKind = kind != null && kind in TOUCH_SET_CAUSE ? kind : 'server';
  return { title: TOUCH_SET_TITLE, cause: TOUCH_SET_CAUSE[k], kind: k };
}

/** The line under the board when the touch read failed and nothing was kept. */
export function touchSetErrorLine(kind: ErrorKind | null | undefined): string {
  const copy = touchSetCopy(kind);
  return `${copy.title}. ${copy.cause}`;
}

/** The player_ids with any carry, reception or target on a totals read. */
export function touchedPlayerIds(rows: ReadonlyArray<object>): Set<string> {
  const out = new Set<string>();
  for (const r of rows as ReadonlyArray<Record<string, unknown>>) {
    if (TOUCH_KEYS.some((k) => Number(r[k] ?? 0) > 0) && typeof r.player_id === 'string') {
      out.add(r.player_id);
    }
  }
  return out;
}
const TOUCH_KEYS = ['carries', 'receptions', 'targets'] as const;

export function isStatParticipant(
  sport: string,
  values: Array<number | null | undefined>,
  opts?: {
    statKey?: string;
    /** The rows the values came from, when the read carries usage columns
     *  (the Averages and last-N reads do; Season and H2H do not). */
    rows?: ReadonlyArray<object>;
    /** Whether the player touched the ball this season, from a separate
     *  totals read — what Season and H2H use, having no usage columns of
     *  their own. Undefined = not known. */
    touched?: boolean;
    /** A book posts this player a line in the market today. On Anytime TD
     *  that alone keeps him (Matt, 2026-10-09: "ATD should show for
     *  everyone that has a betting line"). */
    priced?: boolean;
  },
): boolean {
  if (!MULTI_ROLE_SPORTS.has(sport)) return true;
  if (values.some((v) => (v ?? 0) !== 0)) return true;
  if (!opts?.statKey || !ZERO_IS_AN_ANSWER_KEYS.has(opts.statKey)) return false;
  if (opts.priced) return true;
  if (opts.touched !== undefined) return opts.touched;
  const rows = (opts.rows ?? []) as ReadonlyArray<Record<string, unknown>>;
  const hasUsage = rows.some((r) => TOUCH_KEYS.some((k) => r[k] != null));
  // No usage columns and no touch answer (missing, or a set for another key).
  // Fail closed: a zero is not evidence the player touched the ball, and
  // keeping anyone with games built the wide list (1,327 Season rows, 897
  // never touched — measured 2026-10-08). A player who scored still stayed,
  // above. Last-N and Averages carry the usage columns and take the branch
  // below.
  if (!hasUsage) return false;
  return rows.some((r) => TOUCH_KEYS.some((k) => Number(r[k] ?? 0) > 0));
}

/**
 * A prop row that names a TEAM, not a player: books list "Dallas Cowboys
 * D/ST" (and "… Defense") and "No Scorer" in the anytime-TD market — 52 of
 * the 427 names on the 2026-10-11 NFL slate. None is a player row.
 */
export function isTeamPropName(name: string | null | undefined): boolean {
  const n = (name ?? '').trim();
  return /(\bD\/ST|\bDefense)$/i.test(n) || /^no (td )?scorer$/i.test(n);
}

/** One player a book prices in the market on the slate. */
export interface PricedPlayer {
  key: string;
  name: string;
  gameId: string;
}

/**
 * The players any book prices in `market` on the slate, at any line, keyed by
 * the folded name the odds column joins on. Rows naming a team are left out.
 */
export function pricedPlayers(
  rows: ReadonlyArray<{ market: string; player_name: string | null; game_id: string }>,
  market: string,
  gameIds?: ReadonlySet<string> | null,
): Map<string, PricedPlayer> {
  const out = new Map<string, PricedPlayer>();
  for (const r of rows) {
    if (r.market !== market) continue;
    if (gameIds && !gameIds.has(r.game_id)) continue;
    if (isTeamPropName(r.player_name)) continue;
    const key = normalizePlayerName(r.player_name);
    if (!key || out.has(key)) continue;
    out.set(key, { key, name: r.player_name ?? '', gameId: r.game_id });
  }
  return out;
}

/**
 * Priced players the board's read has no row for — a line and no game in the
 * log (a player back from injury, a depth tight end, a nickname the book
 * prints): 69 of the 375 priced players on the 2026-10-11 NFL anytime-TD
 * slate. They are listed so the board shows everyone with a line, with no
 * number of their own, since there is none to show.
 */
export function lineOnlyPlayers(
  priced: ReadonlyMap<string, PricedPlayer>,
  boardNames: Iterable<string | null | undefined>,
): PricedPlayer[] {
  const present = new Set<string>();
  for (const n of boardNames) {
    const k = normalizePlayerName(n);
    if (k) present.add(k);
  }
  return [...priced.values()]
    .filter((p) => !present.has(p.key))
    .sort((a, b) => a.name.localeCompare(b.name));
}

/** A game's Live/Final label, or null before kickoff. */
export function startedForGame(g: GameRow): 'Live' | 'Final' | null {
  const kind = gameStatus(g).kind;
  return kind === 'live' ? 'Live' : kind === 'final' || kind === 'ended' ? 'Final' : null;
}

/**
 * The subline for a row that knows its GAME and not its team — a line-only
 * player: "SUN 1:00 PM ET · HOU @ TEN", or "Live · HOU @ TEN" once under way
 * when the price column is hidden (the cell says it otherwise; slateSubline).
 */
export function fixtureSubline(g: GameRow, started: 'Live' | 'Final' | null): string | null {
  const fixture = g.away_team && g.home_team ? `${g.away_team} @ ${g.home_team}` : null;
  if (!fixture) return null;
  if (started) return `${started} · ${fixture}`;
  const time = formatGameTimeET(g.commence_time);
  if (!time) return fixture;
  const day = weekdayShortET(g.commence_time);
  return `${day ? `${day} ` : ''}${time} · ${fixture}`;
}

/** The synthetic id a line-only row carries — never a real player_id. */
export const LINE_ONLY_ID_PREFIX = 'line-only:';
export function isLineOnlyId(id: string): boolean {
  return id.startsWith(LINE_ONLY_ID_PREFIX);
}

/**
 * Whether a row may open PlayerStats.
 *
 * A line-only row has no `player_id`. Navigating with `''` lands on an empty
 * page — the detail screen's log read has nothing to ask for. A blank id is
 * the same. A real id opens.
 */
export function canOpenPlayerDetail(playerId: string | null | undefined): boolean {
  return !!playerId && !isLineOnlyId(playerId);
}

/** Spoken ending of a line-only row. It goes at the end of the label. */
export const LINE_ONLY_ROW_TAIL = ', no games logged yet';

/**
 * The line-only row's accessibility label. Name, then the spoken fixture,
 * then the tail — VoiceOver reads that the row has no games after it has
 * said who and which game. The row is not a button and has no hint.
 */
export function lineOnlyRowLabel(name: string, spokenSubline: string | null): string {
  const head = spokenSubline ? `${name}, ${spokenSubline}` : name;
  return `${head}${LINE_ONLY_ROW_TAIL}`;
}

/**
 * VoiceOver hint while a slate read is in flight, on the Teams chip and the
 * Players Availability switch. The apostrophe is U+2019.
 */
export const SLATE_CHECKING_HINT = 'Checking today\u2019s schedule';

/**
 * Identity of one slate read. A sport switch or an ET-date rollover is a
 * different slate. Both boards key the fetch on this, so an app left open
 * overnight does not keep filtering on yesterday's teams under "Playing today".
 * Pull-to-refresh passes a separate nonce beside the key.
 */
export function slateReadKey(sport: string, etDay: string): string {
  return `${sport}|${etDay}`;
}

/**
 * The Teams "Playing today" chip.
 *
 * Disabled while the slate for THIS sport has not settled. The previous
 * sport's teams are still in state for that moment, and `!hasSlate` alone
 * leaves the chip tappable — labelled with the old slate, filtering by the
 * old teams — while VoiceOver says "checking the schedule". Also disabled
 * when the settled read has no games.
 */
export function slateChipDisabled(slateChecking: boolean, hasSlate: boolean): boolean {
  return slateChecking || !hasSlate;
}

// ── 3. Tonight's slate ──

export interface TonightSlate {
  /** ET date the slate is for ('' when nothing is scheduled). */
  date: string;
  /** Team abbrevs in action — plus fighter names for UFC, which has no teams. */
  keys: Set<string>;
  /** True when `date` is today (vs the next scheduled day). */
  isToday: boolean;
}

export const EMPTY_SLATE: TonightSlate = { date: '', keys: new Set(), isToday: false };

/** '2026-08-30' → 'Sun 8/30' (for the next-slate label). */
function shortSlateDate(date: string): string {
  if (!date) return '';
  const d = new Date(`${date}T12:00:00Z`);
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'UTC',
    weekday: 'short',
    month: 'numeric',
    day: 'numeric',
  }).format(d);
}

/**
 * The slate cut's name — ONE expression for the Players board's Availability
 * switch and the Teams board's chip, so a sport tab never has two names for
 * the same cut (UX review, 2026-10-09).
 */
export function slateLabelFor(slate: { date: string; isToday: boolean }): string {
  return slate.isToday ? 'Playing today' : `Next slate ${shortSlateDate(slate.date)}`;
}

/**
 * Reduce upcoming games to the slate to filter on: today's games when there
 * are any, otherwise the next scheduled day. Sports that don't play daily
 * (NFL, UFC) would otherwise have a permanently useless toggle.
 *
 * `games` may span several days and sports; both are filtered here.
 */
export function buildTonightSlate(games: GameRow[], sport: string, today: string): TonightSlate {
  const byDate = new Map<string, GameRow[]>();
  for (const g of games) {
    if (g.sport !== sport) continue;
    if (!g.game_date || g.game_date < today) continue;
    const arr = byDate.get(g.game_date);
    if (arr) arr.push(g);
    else byDate.set(g.game_date, [g]);
  }
  if (byDate.size === 0) return EMPTY_SLATE;
  const date = byDate.has(today) ? today : Array.from(byDate.keys()).sort()[0];
  const keys = new Set<string>();
  for (const g of byDate.get(date) ?? []) {
    if (g.home_team) keys.add(g.home_team);
    if (g.away_team) keys.add(g.away_team);
  }
  return { date, keys, isToday: date === today };
}

/**
 * Is this leaderboard row in the slate? Team sports match on the team abbrev
 * (`games.home_team` and every player game log use the same abbrevs). UFC has
 * no team, so its fighters match on display name — which is exactly what a UFC
 * `games` row stores.
 */
export function isOnSlate(
  row: { team?: string | null; player_name?: string | null },
  slate: TonightSlate,
): boolean {
  if (slate.keys.size === 0) return true; // nothing to filter against
  if (row.team && slate.keys.has(row.team)) return true;
  return !!row.player_name && slate.keys.has(row.player_name);
}

/**
 * The slate as a TEAM narrowing the server can apply to a leaderboard read, or
 * null when the board must read the whole league.
 *
 * `isOnSlate` above is the same filter client-side, and the two must agree:
 * this exists because the read it narrows is over the row cap in every sport
 * (lib/paging.ts — the NFL's last-10 read is 12,850 rows and the NCAAF's is
 * 54,687), so the board was being handed an arbitrary first 1,000 and drawing
 * whatever survived. On 2026-09-09 that left the NFL board — which opens
 * filtered to the slate — with 6 of tonight's 73 players and not one
 * quarterback, so the default Pass Yards board was empty.
 *
 * NULL, NOT [], FOR UFC: its slate keys are FIGHTER NAMES, not teams
 * (`isOnSlate`'s second clause), and its rows carry no team to match them
 * against — narrowing on `team` there would return nothing at all. Null for an
 * unresolved or empty slate too: the board is showing the league, so read it.
 */
const TEAMLESS_SPORTS = new Set(['UFC', 'GOLF']);

export function slateTeams(
  sport: string,
  slate: TonightSlate,
  active: boolean,
): string[] | null {
  if (!active || TEAMLESS_SPORTS.has(sport) || slate.keys.size === 0) return null;
  return Array.from(slate.keys);
}

// ── 4. The row's own game: when it starts, and against whom ──

/**
 * "9:40 PM ET · @ SEA" under the player's name (Matt, 2026-09-05, from a
 * competitor screenshot: "add the time of the game and who they are playing
 * under the name … for all sports").
 *
 * Sourced from `games`, NOT from the MLB/WNBA matchup views, for the same
 * reason the slate above is: `games` is the one table every sport writes, so
 * one implementation covers football, basketball and the UFC card instead of
 * two sports getting a subline and six getting nothing.
 *
 * This REVERSES 2026-09-04's "nothing under the player name", which is why the
 * SPOT column exists at all. What the SPOT column keeps is its FACT (the
 * opposing starter's ERA, the defence's rating) — the opponent moved back under
 * the name and must not be printed twice on one row, so MatchupCell drops its
 * own `vs OPP` line whenever a subline is carrying it.
 */
export interface SlateGame {
  game: GameRow;
  /** The other side, from this row's perspective. */
  opponent: string;
  /**
   * True at home, false away, NULL where the fixture has no home side.
   *
   * A UFC `games` row stores the two FIGHTERS in `home_team`/`away_team` —
   * they are slots, not venues — so reading them as home/away printed
   * "vs Amanda Nunes" on one fighter's row and "@ Ronda Rousey" on the other's
   * FOR THE SAME BOUT, which reads as two different fixtures on one board (UX
   * review, 2026-09-05). Golf is the same shape (`away_team = 'FIELD'`) and is
   * safe today only because it has no player leaderboard yet.
   */
  isHome: boolean | null;
}

/** Sports whose `games` row has no home side — see `SlateGame.isHome`. */
const NEUTRAL_SITE_SPORTS = new Set(['UFC', 'GOLF']);

function toSlateGame(game: GameRow, key: string): SlateGame {
  const isHome = NEUTRAL_SITE_SPORTS.has(game.sport) ? null : game.home_team === key;
  return {
    game,
    opponent: game.home_team === key ? game.away_team : game.home_team,
    isHome,
  };
}

/** Soonest kickoff, then game_date, then game_id. Missing commence_time sorts last. */
export function compareKickoff(a: GameRow, b: GameRow): number {
  const ta = Date.parse(a.commence_time ?? '');
  const tb = Date.parse(b.commence_time ?? '');
  if (Number.isNaN(ta) && Number.isNaN(tb)) {
    if (a.game_date !== b.game_date) return a.game_date < b.game_date ? -1 : 1;
    return a.game_id < b.game_id ? -1 : 1;
  }
  if (Number.isNaN(ta)) return 1;
  if (Number.isNaN(tb)) return -1;
  if (ta !== tb) return ta - tb;
  return a.game_id < b.game_id ? -1 : 1;
}

/**
 * The next game for one team (or UFC fighter name) in a multi-day window.
 *
 * Primary: the soonest UNSTARTED kickoff. Fallback (every game in the
 * window has started): the LATEST kickoff — last-of-day on a doubleheader,
 * not game one. `buildTonightSlate` is a board filter and is not used here:
 * a Thursday NFL game must still win when that filter's date is Sunday.
 */
export function earliestUpcomingGame(
  games: GameRow[],
  team: string,
  nowIso: string,
): SlateGame | null {
  if (!team) return null;
  const mine = games.filter((g) => g.home_team === team || g.away_team === team);
  if (mine.length === 0) return null;
  const unstarted = mine.filter((g) => !!g.commence_time && g.commence_time > nowIso);
  const ranked = (unstarted.length > 0 ? unstarted : mine).slice().sort(compareKickoff);
  const timed = ranked.filter((g) => !!g.commence_time);
  const pool = timed.length > 0 ? timed : ranked;
  const game = unstarted.length > 0 ? pool[0] : pool[pool.length - 1];
  return game ? toSlateGame(game, team) : null;
}

/**
 * key → the game that key plays on the slate date. Keyed by BOTH team abbrevs,
 * which is what `isOnSlate` matches on: team sports key on the abbrev, and UFC
 * — which has no teams — keys on the fighter names its `games` row stores in
 * `home_team` / `away_team`.
 *
 * Doubleheaders resolve to the game a bettor can still act on: the earliest
 * game that has not started yet, falling back to the last one of the day once
 * they all have. `nowIso` is passed in rather than read from the clock so the
 * choice is verifiable offline (the same shape as `unstartedGameIds`).
 */
export function buildSlateGameIndex(
  games: GameRow[],
  slate: TonightSlate,
  nowIso: string,
): Map<string, SlateGame> {
  const out = new Map<string, SlateGame>();
  if (!slate.date) return out;
  const byKey = new Map<string, GameRow[]>();
  for (const g of games) {
    if (g.game_date !== slate.date) continue;
    for (const key of [g.home_team, g.away_team]) {
      if (!key) continue;
      const arr = byKey.get(key);
      if (arr) arr.push(g);
      else byKey.set(key, [g]);
    }
  }
  for (const [key, list] of byKey) {
    const sorted = list
      .slice()
      .sort((a, b) => String(a.commence_time ?? '').localeCompare(String(b.commence_time ?? '')));
    const upcoming = sorted.find((g) => !!g.commence_time && g.commence_time > nowIso);
    const game = upcoming ?? sorted[sorted.length - 1];
    out.set(key, toSlateGame(game, key));
  }
  return out;
}

// ── 5. Head-to-head: who each team is about to play ──

/**
 * Every team in the forward window mapped to its NEXT game.
 *
 * NOT `buildSlateGameIndex`, and the difference is the whole point of the H2H
 * window. That index is bounded to ONE date (`slate.date`) because it feeds the
 * row subline on a board that is about tonight. H2H is about the fixture a
 * bettor is pricing, and in a weekly sport that fixture is usually not today:
 * bounded to the slate date, an NFL H2H board opened on a Tuesday would have
 * covered the two teams playing Thursday and left the other thirty blank.
 *
 * So this spans whatever window it is handed (the board reads seven days) and
 * resolves each team with the same rule the player page uses — soonest
 * unstarted kickoff, falling back to the last game once they have all started,
 * which keeps a doubleheader on the game that can still be bet.
 *
 * TEAM-KEYED ONLY. `buildSlateGameIndex` also keys UFC fighters by name; the
 * H2H window is offered only for the sports with a per-game player log
 * (`supportsHitRate`), none of which are teamless, and a fighter-name key here
 * would pair a person with a person in a read that expects two teams.
 */
export function nextGameByTeam(games: GameRow[], nowIso: string): Map<string, SlateGame> {
  const out = new Map<string, SlateGame>();
  const teams = new Set<string>();
  for (const g of games) {
    if (g.home_team) teams.add(g.home_team);
    if (g.away_team) teams.add(g.away_team);
  }
  for (const team of teams) {
    const entry = earliestUpcomingGame(games, team, nowIso);
    if (entry) out.set(team, entry);
  }
  return out;
}

/**
 * The fixture list the H2H read is narrowed by — team i plays opponent i.
 *
 * TWO PARALLEL ARRAYS rather than one array of 'TEAM|OPP' strings: an NCAAF
 * team id is a school NAME (CLAUDE.md §4), so any separator is a character
 * that can occur inside a key. The RPC pairs them by ordinal.
 *
 * Sorted by team so the read key the board memoises on is stable — a Map's
 * iteration order follows insertion, which follows whatever order the slate
 * rows arrived in, and an unstable key re-reads the whole board for nothing.
 */
export function h2hMatchups(
  index: Map<string, SlateGame>,
  onlyTeams?: readonly string[] | null,
): { teams: string[]; opponents: string[] } {
  const allow = onlyTeams && onlyTeams.length > 0 ? new Set(onlyTeams) : null;
  const teams: string[] = [];
  const opponents: string[] = [];
  for (const team of Array.from(index.keys()).sort()) {
    if (allow && !allow.has(team)) continue;
    const opponent = index.get(team)?.opponent;
    if (!opponent) continue;
    teams.push(team);
    opponents.push(opponent);
  }
  return { teams, opponents };
}

/**
 * The key a leaderboard row matched on — team first, then name (UFC).
 *
 * Returned alongside the game because the CALLER needs it too: the board's
 * Live/Final map is keyed the same way, and looking that up by `row.team`
 * alone left every UFC row advertising a start time hours after the fight
 * ended (UX review, 2026-09-05).
 */
export function slateGameFor(
  row: { team?: string | null; player_name?: string | null },
  index: Map<string, SlateGame>,
): { key: string; game: SlateGame } | null {
  if (row.team) {
    const byTeam = index.get(row.team);
    if (byTeam) return { key: row.team, game: byTeam };
  }
  if (row.player_name) {
    const byName = index.get(row.player_name);
    if (byName) return { key: row.player_name, game: byName };
  }
  return null;
}

/**
 * The subline itself: "9:40 PM ET · @ SEA".
 *
 * `started` is the board's Live/Final label for this row, and it is passed
 * ONLY when the price column is hidden. Two rules meet here:
 *   - once a game is under way its start time is not the fact a bettor needs;
 *   - but the price cell already prints "Live"/"Final" to explain its missing
 *     number, and the same word twice on one row reads as a bug the reader has
 *     to rule out (UX review, 2026-09-05) — the same duplication the opponent
 *     had against the MATCHUP column.
 * So when the price column is visible it owns the status and the subline keeps
 * the start time; when it is hidden the subline takes the status over.
 *
 * A slate that is not today gets a weekday in front ("SAT 1:00 PM ET"),
 * because a bare clock time on Sunday's board is the wrong day, not the wrong
 * hour.
 *
 * `null` — never an empty string or a dash — when the row has no game: the row
 * then renders its name alone rather than a placeholder line.
 */
export function slateSubline(
  entry: SlateGame | null,
  started: 'Live' | 'Final' | null,
): string | null {
  if (!entry) return null;
  // No home side, no "@": both fighters on a card see the same fixture.
  const side = entry.isHome === null ? `vs ${entry.opponent}` : `${entry.isHome ? 'vs' : '@'} ${entry.opponent}`;
  if (started) return `${started} · ${side}`;
  const time = formatGameTimeET(entry.game.commence_time);
  if (!time) return side;
  const day = weekdayShortET(entry.game.commence_time);
  return `${day ? `${day} ` : ''}${time} · ${side}`;
}

/**
 * The subline as words. VoiceOver skips a bare "·" and reads "@ SEA" as
 * "at sign SEA", so the separator becomes a comma and the away marker becomes
 * the word.
 *
 * It lives beside `slateSubline` rather than in the screen because the subline
 * renders in THREE places — the two Players rows and the Teams row — and the
 * first version, defined in StatsScreen, reached only the tappable one (UX
 * review, 2026-09-05).
 */
export function sublineSpoken(subline: string): string {
  // "HOU @ TEN" is not the away marker "@ SEA". VoiceOver reads a bare "@"
  // as "at sign", so both shapes become the word.
  return subline.replace(/ · /g, ', ').replace(/(^|, )@ /, '$1at ').replace(/ @ /g, ' at ');
}
