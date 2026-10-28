/**
 * NBA first-quarter team stats (Matt, 2026-10-28, from member feedback: "1Q
 * records last 5/10 games, home/away splits, 1Q offensive/defensive
 * efficiency").
 *
 * The rows come from `nba_team_q1_games`, one per team per regular-season game,
 * written by the worker (data/ingestors/nba_team_q1.py). Points are the
 * official first-quarter score. Possessions are counted from play-by-play, and
 * are null where that count could not be checked against the score — such a
 * game counts in the record and the points, never in the ratings.
 *
 * Ratings are points per 100 possessions over the WINDOW (sum of points over
 * sum of possessions), not an average of per-game ratings: a 22-possession
 * quarter and a 30-possession one should not weigh the same.
 *
 * Last 5 / Last 10 are the team's last N games AT THAT VENUE ("last 5 home"),
 * and they reach back into last season early on, as every NBA last-N read does
 * (Matt, 2026-10-23). Season is this season only.
 *
 * These are stats, not picks. The first-quarter model was tested and closed
 * (docs/nba_models_2026.md §9).
 *
 * Pure: verified offline by `npx tsx scripts/verify_nba_q1.ts`.
 */

export interface NbaQ1Game {
  game_id: string;
  team: string;
  season: number;
  game_date: string;
  opponent: string;
  is_home: boolean;
  pts_for: number;
  pts_against: number;
  poss_for: number | null;
  poss_against: number | null;
}

/** One row of `v_nba_team_q1_season`: the season-long ranks for one venue. */
export interface NbaQ1SeasonRow {
  season: number;
  team: string;
  venue: NbaQ1Venue;
  games: number;
  rated_games: number;
  ortg: number | null;
  drtg: number | null;
  net_rtg: number | null;
  ortg_rank: number;
  drtg_rank: number;
  net_rank: number;
  teams: number;
}

export type NbaQ1Venue = 'all' | 'home' | 'away';
export const NBA_Q1_VENUES: readonly NbaQ1Venue[] = ['all', 'home', 'away'];
export const NBA_Q1_VENUE_LABEL: Record<NbaQ1Venue, string> = { all: 'All', home: 'Home', away: 'Away' };

/** Enough for a last-10 at one venue to reach back across a season start. */
export const NBA_Q1_FETCH_GAMES = 40;

export interface NbaQ1Summary {
  games: number;
  wins: number;
  losses: number;
  ties: number;
  /** Mean first-quarter margin; null with no games. */
  margin: number | null;
  ptsFor: number | null;
  ptsAgainst: number | null;
  /** Points per 100 possessions; null when no game in the window is rated. */
  ortg: number | null;
  drtg: number | null;
  ratedGames: number;
  /** Games in the window from an earlier season than `currentSeason`. */
  priorSeasonGames: number;
}

function round1(x: number): number {
  return Math.round(x * 10) / 10;
}

function atVenue(g: NbaQ1Game, venue: NbaQ1Venue): boolean {
  return venue === 'all' || (venue === 'home') === g.is_home;
}

/** Newest first, ties broken by game_id so the order never depends on the read. */
export function newestFirst(games: readonly NbaQ1Game[]): NbaQ1Game[] {
  return [...games].sort((a, b) =>
    a.game_date === b.game_date ? (a.game_id < b.game_id ? 1 : -1) : a.game_date < b.game_date ? 1 : -1,
  );
}

export function summarizeQ1(games: readonly NbaQ1Game[], currentSeason: number | null): NbaQ1Summary {
  let wins = 0;
  let losses = 0;
  let ties = 0;
  let pf = 0;
  let pa = 0;
  let rpf = 0;
  let rpa = 0;
  let possF = 0;
  let possA = 0;
  let rated = 0;
  let prior = 0;
  for (const g of games) {
    if (g.pts_for > g.pts_against) wins += 1;
    else if (g.pts_for < g.pts_against) losses += 1;
    else ties += 1;
    pf += g.pts_for;
    pa += g.pts_against;
    if (g.poss_for != null && g.poss_against != null && g.poss_for > 0 && g.poss_against > 0) {
      rated += 1;
      rpf += g.pts_for;
      rpa += g.pts_against;
      possF += g.poss_for;
      possA += g.poss_against;
    }
    if (currentSeason != null && g.season < currentSeason) prior += 1;
  }
  const n = games.length;
  return {
    games: n,
    wins,
    losses,
    ties,
    margin: n ? round1((pf - pa) / n) : null,
    ptsFor: n ? round1(pf / n) : null,
    ptsAgainst: n ? round1(pa / n) : null,
    ortg: rated ? round1((100 * rpf) / possF) : null,
    drtg: rated ? round1((100 * rpa) / possA) : null,
    ratedGames: rated,
    priorSeasonGames: prior,
  };
}

export interface NbaQ1WindowRow {
  key: 'l5' | 'l10' | 'season';
  label: string;
  summary: NbaQ1Summary;
}

/**
 * The three rows the card draws for one venue. `games` may arrive in any
 * order and from two seasons; the current season is the newest game's.
 */
export function nbaQ1Windows(games: readonly NbaQ1Game[], venue: NbaQ1Venue): {
  season: number | null;
  rows: NbaQ1WindowRow[];
} {
  const sorted = newestFirst(games).filter((g) => atVenue(g, venue));
  const season = newestFirst(games)[0]?.season ?? null;
  const thisSeason = sorted.filter((g) => g.season === season);
  return {
    season,
    rows: [
      { key: 'l5', label: 'Last 5', summary: summarizeQ1(sorted.slice(0, 5), season) },
      { key: 'l10', label: 'Last 10', summary: summarizeQ1(sorted.slice(0, 10), season) },
      { key: 'season', label: 'Season', summary: summarizeQ1(thisSeason, season) },
    ],
  };
}

export function formatQ1Record(s: Pick<NbaQ1Summary, 'wins' | 'losses' | 'ties'>): string {
  return `${s.wins}-${s.losses}${s.ties ? `-${s.ties}` : ''}`;
}

export function formatSigned1(x: number | null): string {
  if (x == null) return '—';
  if (x === 0) return '0.0';
  return `${x > 0 ? '+' : '−'}${Math.abs(x).toFixed(1)}`;
}

export function formatRating(x: number | null): string {
  return x == null ? '—' : x.toFixed(1);
}

/** "2025-26" for the NBA's ending-year season label 2026 (CLAUDE.md §4). */
export function nbaSeasonLabel(season: number): string {
  return `${season - 1}-${String(season % 100).padStart(2, '0')}`;
}
