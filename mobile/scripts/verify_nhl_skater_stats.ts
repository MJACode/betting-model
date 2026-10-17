/**
 * NHL skater chips on the Stats tab: Shots, Points, Goals, Assists, priced
 * from the existing prop markets, summed from nhl_skater_stats. Hit rate
 * stays off. Run with:
 *
 *   npx tsx scripts/verify_nhl_skater_stats.ts
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  GROUP_ORDER,
  STAT_CATALOG,
  defaultStatFor,
  propMarketForStat,
  propModelForStat,
  statsForSport,
  supportsHitRate,
} from '../src/lib/statCatalog';
import {
  aggregateNhlSkaterTotals,
  createNhlSkaterReader,
  NHL_SKATER_CACHE_TTL_MS,
  nhlSeasonCandidates,
} from '../src/lib/nhlSkaterTotals';
import {
  lineOnlyPlayers,
  lineOnlyRowLabel,
  listsPricedWithoutLog,
  needsTouchSet,
  pricedPlayers,
  rankedBoardChrome,
} from '../src/lib/statsBoard';
import { hitModeHeadline, selectionFor } from '../src/lib/hitMode';
import { defaultLineN } from '../src/lib/lineRuler';
import { normalizePlayerName } from '../src/lib/playerNews';
import { oneWayMarket, propDisplayLabel } from '../src/lib/markets';
import type { Sport } from '../src/hooks/useSportFilter';

const read = (p: string) => readFileSync(join(import.meta.dirname, '..', p), 'utf-8');

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const nhl = statsForSport('NHL' as Sport);
check('four skater chips, in order', nhl.map((d) => d.label).join(',') === 'Shots,Points,Goals,Assists',
  nhl.map((d) => d.label).join(','));
check('the group is NHL', GROUP_ORDER.NHL.join() === 'NHL' && nhl.every((d) => d.group === 'NHL'));
check('opens on Shots', defaultStatFor('NHL' as Sport)?.key === 'shots_on_goal');
check('Shots is on the Players segment',
  defaultStatFor('NHL' as Sport) != null);

const markets: Record<string, string> = {
  shots_on_goal: 'player_shots_on_goal',
  points: 'player_points',
  goals: 'player_goal_scorer_anytime',
  assists: 'player_assists',
};
for (const def of nhl) {
  const want = markets[String(def.key)];
  check(`${def.label} prices ${want}`, propMarketForStat(def) === want, String(propMarketForStat(def)));
  check(`${def.label} is not a model pick`, propModelForStat(def) === null);
}
check('no other NHL chip was invented', nhl.length === 4);
check('blocked shots is not a chip — nhl_skater_stats has no column for it',
  !STAT_CATALOG.some((d) => d.sport === 'NHL' && String(d.key) === 'blocked_shots'));

check('NHL is not a hit-rate sport', !supportsHitRate('NHL' as Sport));
const catalog = read('src/lib/statCatalog.ts');
check('HIT_RATE_SPORTS does not name NHL',
  !/HIT_RATE_SPORTS = new Set<Sport>\(\[[^\]]*NHL/.test(catalog));

check('a basketball points chip is not the NHL market',
  propMarketForStat(statsForSport('NBA' as Sport).find((d) => d.key === 'points')!) === 'player_points');
check('anytime goal scorer has no Under', oneWayMarket('player_goal_scorer_anytime', 'under')
  && !oneWayMarket('player_goal_scorer_anytime', 'over'));
check('anytime TD is still one-way on Under only',
  oneWayMarket('player_anytime_td', 'under') && !oneWayMarket('player_anytime_td', 'over'));
check('a Goals bet is named Anytime Goal, not the chip',
  propDisplayLabel('player_goal_scorer_anytime', 'Goals') === 'Anytime Goal');
check('Shots keeps its chip name on the leg',
  propDisplayLabel('player_shots_on_goal', 'Shots') === 'Shots');
check('Anytime TD keeps its own leg name',
  propDisplayLabel('player_anytime_td', 'Anytime TD') === 'Anytime TD');
check('the averages caption names 3+ Shots and 1+ Anytime Goal',
  hitModeHeadline(3, 'atLeast', 'Shots') === '3+ Shots'
  && hitModeHeadline(1, 'atLeast', 'Anytime Goal') === '1+ Anytime Goal');
check('an empty-log row does not say the player has no games',
  lineOnlyRowLabel('Matthews', 'TOR at BOS', '') === 'Matthews, TOR at BOS');

check('NHL lists a priced player the log missed', listsPricedWithoutLog('NHL', 'shots_on_goal'));
check('MLB does not', !listsPricedWithoutLog('MLB', 'hits'));
check('the football touch set is unchanged',
  needsTouchSet('NFL', 'rush_rec_tds') && !needsTouchSet('NHL', 'shots_on_goal'));

check('October 2026 asks for the ending year first',
  nhlSeasonCandidates(2026, 10).join() === '2027,2026');
check('January does not ask for next year',
  nhlSeasonCandidates(2027, 1).join() === '2027' && nhlSeasonCandidates(2027, 6).join() === '2027');

const shots = nhl.find((d) => d.key === 'shots_on_goal')!;
check('Shots opens on the 2.5 line, spoken as 3+',
  shots.defaultLine === 2.5
  && defaultLineN(shots) === 3
  && selectionFor(defaultLineN(shots), 'atLeast').line === 2.5
  && hitModeHeadline(defaultLineN(shots), 'atLeast', 'Shots') === '3+ Shots');

const matthews = aggregateNhlSkaterTotals([
  { player_id: '8479318', player_name: 'Auston Matthews', team: 'TOR', position: 'C', season: 2027, game_date: '2026-10-14', game_id: 'g', goals: 1, assists: 0, points: 1, shots_on_goal: 4 },
], 2027, null, null);
const pricedMatthews = pricedPlayers(
  [{ market: 'player_shots_on_goal', player_name: 'Auston Matthews Jr.', game_id: 'g' }],
  'player_shots_on_goal',
);
check('a book name that folds to the log name is not a second row',
  matthews.length === 1
  && normalizePlayerName('Auston Matthews Jr.') === normalizePlayerName(matthews[0]!.player_name)
  && lineOnlyPlayers(pricedMatthews, matthews.map((r) => r.player_name)).length === 0);

const games = [
  { player_id: '1', player_name: 'A', team: 'BOS', position: 'C', season: 2027, game_date: '2026-10-10', game_id: 'g1', goals: 1, assists: 0, points: 1, shots_on_goal: 4 },
  { player_id: '1', player_name: 'A', team: 'TOR', position: 'C', season: 2027, game_date: '2026-10-14', game_id: 'g2', goals: 0, assists: 2, points: 2, shots_on_goal: 3 },
  { player_id: '2', player_name: 'B', team: 'BOS', position: 'D', season: 2027, game_date: '2026-10-14', game_id: 'g3', goals: 0, assists: 0, points: 0, shots_on_goal: 1 },
];
const all = aggregateNhlSkaterTotals(games, 2027, null, null);
const a = all.find((r) => r.player_id === '1')!;
check('a traded skater keeps both games under his newest team',
  a.team === 'TOR' && a.games_played === 2 && a.goals === 1 && a.assists === 2 && a.points === 3 && a.shots_on_goal === 7,
  JSON.stringify(a));
const last1 = aggregateNhlSkaterTotals(games, 2027, 1, null).find((r) => r.player_id === '1')!;
check('last-1 is the newest game only',
  last1.games_played === 1 && last1.goals === 0 && last1.shots_on_goal === 3 && last1.team === 'TOR');
const tor = aggregateNhlSkaterTotals(games, 2027, null, ['TOR']);
check('a slate of TOR keeps the skater now on TOR and not the one still on BOS',
  tor.length === 1 && tor[0]!.player_id === '1' && tor[0]!.shots_on_goal === 7);
check('numeric strings from the feed still sum',
  aggregateNhlSkaterTotals(
    [{ ...games[1]!, shots_on_goal: '5', goals: '1', assists: '0', points: '1' }],
    2027, null, null,
  )[0]!.shots_on_goal === 5);

const queries = read('src/lib/queries.ts');
check('the board names nhl_skater_stats at .from', queries.includes(".from('nhl_skater_stats')"));
check('season totals routes NHL before the MLB view',
  queries.indexOf("if (sport === 'NHL') return fetchNhlSkaterBoard(season, null, teams)") <
    queries.indexOf(".from('v_player_season_totals_mlb')"));
check('window totals routes NHL',
  queries.includes("if (sport === 'NHL') return fetchNhlSkaterBoard(season, window, teams)"));
check('the per-game read is not narrowed with .in(\'team\'',
  !/from\('nhl_skater_stats'\)[\s\S]{0,240}\.in\('team'/.test(queries));
check('the pages are remembered per season',
  queries.includes('createNhlSkaterReader({ fetchGames: fetchNhlSkaterGames })'));

const screen = read('src/screens/StatsScreen.tsx');
const teamsAt = screen.indexOf("if (boardMode === 'teams' && supportsTeamBoard(sport))");
const noStatAt = screen.indexOf('NHL is not this');
check('Teams returns before the empty-catalog guard', teamsAt > 0 && noStatAt > teamsAt);
check('the player board lists priced NHL skaters the log missed',
  screen.includes('listsPricedWithoutLog(sport, String(stat.key))'));
check('an empty NHL log does not cover a line-only board',
  screen.includes('boardChrome.suppressEmpty ? null'));
check('only NHL drops a carried Under',
  /if \(sport === 'NHL'\) setHitMode\('atLeast'\)/.test(screen));
check('pull-to-refresh drops the skater cache',
  screen.includes('invalidateNhlSkaterCache()'));
check('averages on that sport names the bet under the chips',
  screen.includes('!canHitRate && showOdds') && screen.includes('hitModeHeadline(lineN, hitMode, betLabel)'));
check('an empty skater log says the totals are not in',
  screen.includes('Lines are up. Season totals aren\u2019t in yet.'));
check('that case drops the no-games value label',
  screen.includes('omitNoGames={seasonLogEmpty}') && screen.includes('omitNoGames ? null : <Text style={styles.valueLabel}>no games</Text>'));
check('the sort claim is withheld when nothing is ranked',
  screen.includes('sorted={boardChrome.headerSorted}')
  && screen.includes("accessible={!sorted}")
  && screen.includes('sorted ? `${rightLabel}, sorted highest first` : rightLabel'));
check('the filter count goes through the same chrome',
  screen.includes('resultCount={boardChrome.resultCount}'));

const nflEmpty = rankedBoardChrome('NFL', 0, 4);
const nflRanked = rankedBoardChrome('NFL', 12, 4);
const ncaafEmpty = rankedBoardChrome('NCAAF', 0, 3);
const nhlEmpty = rankedBoardChrome('NHL', 0, 5);
const nhlBoth = rankedBoardChrome('NHL', 8, 2);
check('an empty NFL ranked list keeps the master header and count',
  !nflEmpty.showHeader && nflEmpty.headerSorted === false && !nflEmpty.suppressEmpty && nflEmpty.resultCount === 0);
check('a ranked NFL board does not add the line-only tail to the count',
  nflRanked.showHeader && nflRanked.headerSorted && !nflRanked.suppressEmpty && nflRanked.resultCount === 12);
check('NCAAF matches that',
  !ncaafEmpty.showHeader && !ncaafEmpty.suppressEmpty && ncaafEmpty.resultCount === 0
  && rankedBoardChrome('NCAAF', 9, 2).resultCount === 9);
check('an empty NHL log is the board',
  nhlEmpty.showHeader && !nhlEmpty.headerSorted && nhlEmpty.suppressEmpty && nhlEmpty.resultCount === 5);
check('NHL with rows still counts the tail',
  nhlBoth.showHeader && nhlBoth.headerSorted && !nhlBoth.suppressEmpty && nhlBoth.resultCount === 10);

void (async () => {
  const asked: number[] = [];
  let now = 1_000;
  const one = [{ player_id: '1', player_name: 'A', team: 'TOR', season: 2027, game_date: '2026-10-14', game_id: 'g', goals: 1, assists: 0, points: 1, shots_on_goal: 4 }];
  const reader = createNhlSkaterReader({
    fetchGames: async (season) => {
      asked.push(season);
      if (season === 2028) return [];
      return one;
    },
    now: () => now,
  });
  const seasonBoard = await reader.board(2026, 10, null, null);
  const windowBoard = await reader.board(2026, 10, 5, null);
  check('a window change does not page the season again',
    asked.join() === '2027' && seasonBoard.length === 1 && windowBoard[0]!.games_played === 1);
  now += NHL_SKATER_CACHE_TTL_MS + 1;
  await reader.board(2026, 10, 5, null);
  check('the cache expires', asked.join() === '2027,2027');
  reader.invalidate();
  await reader.board(2026, 10, 5, null);
  check('pull-to-refresh pages again', asked.join() === '2027,2027,2027');
  const jan: number[] = [];
  const january = createNhlSkaterReader({
    fetchGames: async (season) => {
      jan.push(season);
      return one;
    },
    now: () => now,
  });
  await january.board(2027, 1, null, null);
  check('January does not page next year', jan.join() === '2027');
  let calls = 0;
  let release: (rows: typeof one) => void = () => {};
  const shared = createNhlSkaterReader({
    fetchGames: () => {
      calls += 1;
      return new Promise((resolve) => { release = resolve; });
    },
    now: () => now,
  });
  const first = shared.board(2026, 10, null, null);
  const second = shared.board(2026, 10, 3, null);
  release(one);
  await Promise.all([first, second]);
  check('two windows in flight share one page', calls === 1);
check('a sport with no ruler does not show the direction-lock note',
  screen.includes('canHitRate && dirLockNote'));
check('the off-line explainer uses the bet name',
  screen.includes('const lineHeadline = hitModeHeadline(lineN, hitMode, betLabel)'));
check('an empty-log dash is not spoken',
  screen.includes('accessibilityElementsHidden={omitNoGames}'));

if (failures) {
  console.log(`\n${failures} failed`);
  process.exit(1);
}
console.log('\nall passed');
})();
