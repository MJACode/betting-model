/**
 * Standalone verification of the player page's defense-toughness filter
 * (src/lib/defenseTier.ts — Matt, 2026-11-07). Run with:
 *
 *   npx tsx scripts/verify_defense_tier.ts
 *
 * Pins: thirds of the league per season (30 and 32 teams), the split of the
 * server rows into games and the next opponent, newest-first order, the span
 * cut (L-n / All), that a game with no rank is in no tier, the opening chip
 * (next opponent's tier only when the player has a game in it), the thin-rank
 * note, and the season lookback. The fixtures carry the cases that can
 * disagree: an unranked opponent, a value-less row, two seasons with
 * different league sizes, and a next opponent in a tier the player never met.
 */
import {
  DEFENSE_SEASON_LOOKBACK,
  dateWithYear,
  defenseSeasons,
  nextDefenseLine,
  openingDefenseFilter,
  splitDefenseRows,
  tierChartGames,
  tierCounts,
  tierOfRank,
} from '../src/lib/defenseTier';
import type { PlayerVsDefenseRow } from '../src/types';

let failed = 0;
function check(name: string, ok: boolean, detail = ''): void {
  if (ok) console.log(`ok   ${name}`);
  else {
    failed += 1;
    console.log(`FAIL ${name} ${detail}`);
  }
}
const eq = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

// ── Tiers are thirds of that season's league ───────────────────────────────
check('30 teams: #10 tough', tierOfRank(10, 30) === 'tough');
check('30 teams: #11 avg', tierOfRank(11, 30) === 'avg');
check('30 teams: #20 avg', tierOfRank(20, 30) === 'avg');
check('30 teams: #21 soft', tierOfRank(21, 30) === 'soft');
check('32 teams: #10 tough, #11 avg', tierOfRank(10, 32) === 'tough' && tierOfRank(11, 32) === 'avg');
check('32 teams: #21 avg, #22 soft', tierOfRank(21, 32) === 'avg' && tierOfRank(22, 32) === 'soft');
check('missing rank is no tier', tierOfRank(null, 30) === null && tierOfRank(5, null) === null);
check('rank 0 is no tier', tierOfRank(0, 30) === null);

// ── Rows from the server ───────────────────────────────────────────────────
const row = (p: Partial<PlayerVsDefenseRow>): PlayerVsDefenseRow => ({
  season: 2027, game_id: 'g', game_date: '2026-11-04', opponent: 'SAS', is_home: false,
  value: 29, def_rank: 6, teams_ranked: 30, avg_allowed: 11.9, def_team_games: 9, ...p,
});
const rows: PlayerVsDefenseRow[] = [
  // Older season first, as the request orders them: the split re-sorts.
  row({ season: 2025, game_id: 'a', game_date: '2025-02-12', opponent: 'GSW', is_home: true, value: '42', def_rank: 4 }),
  row({ season: 2025, game_id: 'b', game_date: '2025-03-01', opponent: 'MIL', is_home: true, value: 31, def_rank: 27 }),
  row({ season: 2027, game_id: 'c', game_date: '2026-10-28', opponent: 'OKC', is_home: true, value: 15, def_rank: 9 }),
  row({ season: 2027, game_id: 'd', game_date: '2026-11-04', opponent: 'SAS', is_home: false, value: 29, def_rank: 6 }),
  // An opponent with no qualifying games at the position: kept, no tier.
  row({ season: 2027, game_id: 'e', game_date: '2026-11-01', opponent: 'XXX', value: 20, def_rank: null, teams_ranked: null }),
  // No value for the stat: dropped.
  row({ season: 2027, game_id: 'f', game_date: '2026-10-30', opponent: 'HOU', value: null, def_rank: 12 }),
  // NFL-sized league in another season.
  row({ season: 2026, game_id: 'h', game_date: '2025-12-01', opponent: 'KC', value: 18, def_rank: 22, teams_ranked: 32 }),
  // The next opponent.
  row({ season: 2027, game_id: null, game_date: null, opponent: 'BKN', is_home: null, value: null, def_rank: 7, def_team_games: 8 }),
];
const d = splitDefenseRows(rows);
check('value-less row dropped', d.games.length === 6, String(d.games.length));
check('newest first', eq(d.games.map((g) => g.opponent), ['SAS', 'XXX', 'OKC', 'KC', 'MIL', 'GSW']));
check('string value parsed', d.games.find((g) => g.opponent === 'GSW')?.value === 42);
check('unranked game has no tier', d.games.find((g) => g.opponent === 'XXX')?.tier === null);
check('32-team season tiered on 32', d.games.find((g) => g.opponent === 'KC')?.tier === 'soft');
check('next opponent read', eq(d.next, { opponent: 'BKN', season: 2027, rank: 7, teamsRanked: 30, tier: 'tough', teamGames: 8 }));
check('counts', eq(tierCounts(d.games), { tough: 3, avg: 0, soft: 2 }));

// ── The chart's games ──────────────────────────────────────────────────────
const tough = tierChartGames(d.games, 'tough', 'all');
check('tier games newest first', eq(tough.map((g) => g.opp), ['@SAS', 'vs OKC', 'vs GSW']));
check('dates carry the year', eq(tough.map((g) => g.date), ['11/4/26', '10/28/26', '2/12/25']));
check('bars carry the rank', eq(tough.map((g) => g.rank), [6, 9, 4]));
check('span cut keeps the newest', eq(tierChartGames(d.games, 'tough', 2).map((g) => g.opp), ['@SAS', 'vs OKC']));
check('unranked game never charted in a tier', ![...tierChartGames(d.games, 'tough', 'all'), ...tierChartGames(d.games, 'avg', 'all'), ...tierChartGames(d.games, 'soft', 'all')].some((g) => g.opp?.includes('XXX')));
check('away caption spaced', tough[0].oppFull === '@ SAS');
check('date helper', dateWithYear('2024-12-21') === '12/21/24' && dateWithYear('') === '');

// ── Where the page opens ───────────────────────────────────────────────────
check('opens on the next opponent tier', openingDefenseFilter(d) === 'tough');
const nextInEmptyTier = splitDefenseRows([
  ...rows.filter((r) => r.game_id != null),
  row({ game_id: null, opponent: 'UTA', value: null, def_rank: 15, def_team_games: 9 }),
]);
check('next tier with no games opens on All', openingDefenseFilter(nextInEmptyTier) === 'all');
check('no next opponent opens on All', openingDefenseFilter(splitDefenseRows(rows.filter((r) => r.game_id != null))) === 'all');
check('no data opens on All', openingDefenseFilter(null) === 'all');

// ── The note under the chips ───────────────────────────────────────────────
check('thin rank says games in', nextDefenseLine(d.next!, 'guards') === 'BKN: #7 of 30 vs guards · 8 games in');
check('settled rank has no note', nextDefenseLine({ ...d.next!, teamGames: 10 }, 'guards') === 'BKN: #7 of 30 vs guards');
check('one game singular', nextDefenseLine({ ...d.next!, teamGames: 1 }, 'WRs').endsWith('1 game in'));

// ── Seasons asked for ──────────────────────────────────────────────────────
check('lookback is five labels, newest first', eq(defenseSeasons(2027), [2027, 2026, 2025, 2024, 2023]) && DEFENSE_SEASON_LOOKBACK === 5);

if (failed > 0) {
  console.log(`\n${failed} check(s) failed`);
  process.exit(1);
}
console.log('\nall defense-tier checks passed');
