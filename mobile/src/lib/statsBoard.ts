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
import { formatGameTimeET, weekdayShortET } from './format';
import type { GameRow } from '@/types';

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

export function isStatParticipant(
  sport: string,
  values: Array<number | null | undefined>,
): boolean {
  if (!MULTI_ROLE_SPORTS.has(sport)) return true;
  return values.some((v) => (v ?? 0) !== 0);
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
    const isHome = NEUTRAL_SITE_SPORTS.has(game.sport) ? null : game.home_team === key;
    out.set(key, {
      game,
      opponent: game.home_team === key ? game.away_team : game.home_team,
      isHome,
    });
  }
  return out;
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
  return subline.replace(/ · /g, ', ').replace(/(^|, )@ /, '$1at ');
}
