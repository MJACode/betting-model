/**
 * The player page's defense-toughness filter (Matt, 2026-11-07: "when you
 * click on a player can you select a toughness so that I can see how they do
 * against similar tough opponents").
 *
 * The server (player_vs_defense_<sport>) returns every game the player
 * played in his last three seasons PLAYED, each with that season's rank of
 * the opponent's defense, plus one row (game_id null) for the next opponent.
 * Everything else happens here, so tapping a tier or moving the line never
 * refetches.
 *
 * RANK 1 = THE TOUGHEST DEFENSE (allows the fewest of this stat to this
 * position). Tiers are thirds of the league that season: Tough, Average,
 * Soft. Each game is tiered against ITS OWN season's ranks.
 *
 * Pure on purpose: scripts/verify_defense_tier.ts pins it without React.
 */
import type { ChartGame } from './playerLog';
import type { PlayerVsDefenseRow } from '@/types';

export type DefenseTier = 'tough' | 'avg' | 'soft';
/** What the chip row selects. 'all' = no toughness filter. */
export type DefenseFilter = DefenseTier | 'all';

export const DEFENSE_TIERS: readonly DefenseTier[] = ['tough', 'avg', 'soft'];

/** How many of the player's seasons the read spans. Matt approved 3. */
export const DEFENSE_SEASONS_PLAYED = 3;
/** How many season labels back the read may look to find those three. */
export const DEFENSE_SEASON_LOOKBACK = 5;
/** Under this many games, the next opponent's rank carries a "N games" note. */
export const THIN_RANK_GAMES = 10;

export function tierLabel(t: DefenseTier): string {
  return t === 'tough' ? 'Tough' : t === 'avg' ? 'Average' : 'Soft';
}

/** Filled pips: 3 = tough, 2 = average, 1 = soft. */
export function tierPips(t: DefenseTier): number {
  return t === 'tough' ? 3 : t === 'avg' ? 2 : 1;
}

/**
 * Thirds of the teams ranked that season. 30 teams: 1-10 / 11-20 / 21-30.
 * 32 teams: 1-10 / 11-21 / 22-32. Null when the rank is missing (an opponent
 * with no qualifying games at that position that season).
 */
export function tierOfRank(rank: number | null | undefined, teamsRanked: number | null | undefined): DefenseTier | null {
  const r = Number(rank);
  const n = Number(teamsRanked);
  if (rank == null || teamsRanked == null || !Number.isFinite(r) || !Number.isFinite(n) || r < 1 || n < 1) return null;
  if (r * 3 <= n) return 'tough';
  if (r * 3 <= n * 2) return 'avg';
  return 'soft';
}

/** One of the player's games, tiered. */
export interface TieredGame {
  season: number;
  gameDate: string;
  /** The log's game_id, so minutes outside the loaded window can be fetched. */
  gameId: string;
  opponent: string;
  isHome: boolean | null;
  value: number;
  rank: number | null;
  teamsRanked: number | null;
  tier: DefenseTier | null;
}

export interface NextDefense {
  opponent: string;
  season: number;
  rank: number;
  teamsRanked: number;
  tier: DefenseTier;
  /** The defense's games that season: a rank on fewer than 10 is thin. */
  teamGames: number | null;
}

export interface PlayerDefenseGames {
  /** Newest first, like the chart's log. */
  games: TieredGame[];
  next: NextDefense | null;
}

/** Splits the server rows into the player's games and the next opponent. */
export function splitDefenseRows(rows: readonly PlayerVsDefenseRow[]): PlayerDefenseGames {
  const games: TieredGame[] = [];
  let next: NextDefense | null = null;
  for (const r of rows) {
    if (r.game_id == null) {
      const tier = tierOfRank(r.def_rank, r.teams_ranked);
      if (tier && r.opponent) {
        next = {
          opponent: r.opponent,
          season: Number(r.season),
          rank: Number(r.def_rank),
          teamsRanked: Number(r.teams_ranked),
          tier,
          teamGames: r.def_team_games == null ? null : Number(r.def_team_games),
        };
      }
      continue;
    }
    const v = Number(r.value);
    if (r.value == null || !Number.isFinite(v)) continue;
    games.push({
      season: Number(r.season),
      gameDate: String(r.game_date ?? ''),
      gameId: String(r.game_id),
      opponent: String(r.opponent ?? ''),
      isHome: r.is_home == null ? null : Boolean(r.is_home),
      value: v,
      rank: r.def_rank == null ? null : Number(r.def_rank),
      teamsRanked: r.teams_ranked == null ? null : Number(r.teams_ranked),
      tier: tierOfRank(r.def_rank, r.teams_ranked),
    });
  }
  // Newest first (Array.prototype.sort is stable, so a same-day pair keeps server order).
  games.sort((a, b) => (a.gameDate < b.gameDate ? 1 : a.gameDate > b.gameDate ? -1 : 0));
  return { games, next };
}

/** Games per tier, for the chip counts. */
export function tierCounts(games: readonly TieredGame[]): Record<DefenseTier, number> {
  const out: Record<DefenseTier, number> = { tough: 0, avg: 0, soft: 0 };
  for (const g of games) if (g.tier) out[g.tier] += 1;
  return out;
}

/** "11/4/26" — the filter spans seasons, so the year is on every bar. */
export function dateWithYear(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return '';
  return `${Number(m[2])}/${Number(m[3])}/${m[1].slice(2)}`;
}

/**
 * The chart's games for one tier, newest first, cut to the page's window
 * (L5 / L10 / L20 / All). Each bar carries its defense rank.
 */
export function tierChartGames(
  games: readonly TieredGame[],
  tier: DefenseTier,
  window: number | 'all',
): ChartGame[] {
  const out: ChartGame[] = [];
  for (const g of games) {
    if (g.tier !== tier) continue;
    const at = g.isHome === true ? 'vs ' : g.isHome === false ? '@' : '';
    out.push({
      value: g.value,
      date: dateWithYear(g.gameDate),
      iso: g.gameDate,
      gameId: g.gameId,
      opp: `${at}${g.opponent}`,
      oppFull: `${g.isHome === false ? '@ ' : at}${g.opponent}`,
      rank: g.rank,
    });
    if (window !== 'all' && out.length >= window) break;
  }
  return out;
}

/**
 * The chip the page opens on: the next opponent's tier, when the read has
 * one and the player has at least one game in it; otherwise All.
 */
export function openingDefenseFilter(d: PlayerDefenseGames | null): DefenseFilter {
  if (!d?.next) return 'all';
  return tierCounts(d.games)[d.next.tier] > 0 ? d.next.tier : 'all';
}

/** "BKN: #7 of 30 vs guards · 8 games in" — the games note only while the rank is thin. */
export function nextDefenseLine(next: NextDefense, groupNoun: string): string {
  const base = `${next.opponent}: #${next.rank} of ${next.teamsRanked} vs ${groupNoun}`;
  return next.teamGames != null && next.teamGames < THIN_RANK_GAMES
    ? `${base} · ${next.teamGames} game${next.teamGames === 1 ? '' : 's'} in`
    : base;
}

/** Seasons to ask for: the label in progress and the four before it. */
export function defenseSeasons(seasonInProgress: number): number[] {
  return Array.from({ length: DEFENSE_SEASON_LOOKBACK }, (_, i) => seasonInProgress - i);
}

/** "guards", "WRs" — what the rank is measured against, for the caption. */
export function groupNoun(group: string): string {
  switch (group) {
    case 'G': return 'guards';
    case 'F': return 'forwards';
    case 'C': return 'centers';
    case 'QB': return 'QBs';
    case 'RB': return 'RBs';
    case 'WR': return 'WRs';
    case 'TE': return 'TEs';
    case 'DL': return 'defensive linemen';
    case 'LB': return 'linebackers';
    case 'DB': return 'defensive backs';
    default: return group;
  }
}
