/**
 * NHL skater chips on the Stats tab: Shots, Points, Goals, Assists, priced
 * from the existing prop markets. Totals come from player_window_totals_nhl.
 * Hit rate
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
import { nhlSeasonCandidates } from '../src/lib/nhlSkaterTotals';
import {
  mostCommonPostedLine,
  nhlBetCaption,
  nhlEmptyBoardText,
  nhlLineOnlyTitle,
  nhlOffLineCount,
  nhlSkaterReadMissing,
  shouldOpenShotsLine,
  stopForPostedLine,
} from '../src/lib/nhlBoard';
import { lineLegLabel, nhlBookListing, propLineSheetInput } from '../src/lib/lineLegs';
import type { StatsOddsQuote } from '../src/lib/statsOdds';
import { lineOnlyRowLabel, listsPricedWithoutLog, needsTouchSet, rankedBoardChrome } from '../src/lib/statsBoard';
import { hitModeHeadline, selectionFor } from '../src/lib/hitMode';
import { defaultLineN } from '../src/lib/lineRuler';
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
check('opens on Shots', defaultStatFor('NHL' as Sport)?.key === 'shots');
check('Shots is on the Players segment',
  defaultStatFor('NHL' as Sport) != null);

const markets: Record<string, string> = {
  shots: 'player_shots_on_goal',
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
check('NHL is not a hit-rate sport', !supportsHitRate('NHL' as Sport));
const catalog = read('src/lib/statCatalog.ts');
check('blocked shots and hits are on the log and are not chips',
  catalog.includes('`blocked_shots` and `hits`')
  && !STAT_CATALOG.some((d) => d.sport === 'NHL' && (String(d.key) === 'blocked_shots' || String(d.key) === 'hits')));
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

check('NHL lists a priced player the log missed', listsPricedWithoutLog('NHL', 'shots'));
check('MLB does not', !listsPricedWithoutLog('MLB', 'hits'));
check('the football touch set is unchanged',
  needsTouchSet('NFL', 'rush_rec_tds') && !needsTouchSet('NHL', 'shots'));

check('October 2026 asks for the ending year first',
  nhlSeasonCandidates(2026, 10).join() === '2027,2026');
check('January does not ask for next year',
  nhlSeasonCandidates(2027, 1).join() === '2027' && nhlSeasonCandidates(2027, 6).join() === '2027');

const shots = nhl.find((d) => d.key === 'shots')!;
check('Shots falls back to 2.5 when nothing is posted',
  shots.defaultLine === 2.5
  && defaultLineN(shots) === 3
  && selectionFor(3, 'atLeast').line === 2.5);
check('a posted 1.5 is spoken as 2 or more shots',
  stopForPostedLine(1.5) === 2
  && nhlBetCaption(1.5, 'shots') === '2 or more shots'
  && nhlBetCaption(2.5, 'shots') === '3 or more shots');
check('the four captions are one sentence',
  nhlBetCaption(0.5, 'points') === '1 or more points'
  && nhlBetCaption(0.5, 'goals') === 'Anytime goal scorer: 1 or more goals'
  && nhlBetCaption(0.5, 'assists') === '1 or more assists');
check('anytime goals are captioned only at the priced 0.5',
  nhlBetCaption(1.5, 'goals') === null && nhlBetCaption(0.5, 'shots') === '1 or more shots');
const shotsLeg = {
  kind: 'prop' as const,
  game_id: 'g',
  sport: 'NHL',
  market: 'player_shots_on_goal',
  player_name: 'Auston Matthews',
  team: 'TOR',
  side: 'over' as const,
  statLabel: 'Shots',
};
check('an NHL shots leg says the book line and the plain count',
  lineLegLabel({ ...shotsLeg, line: 2.5 }) === 'Auston Matthews Over 2.5 shots (3 or more)'
  && lineLegLabel({ ...shotsLeg, line: 1.5 }) === 'Auston Matthews Over 1.5 shots (2 or more)');
check('a baseball leg is unchanged',
  lineLegLabel({ ...shotsLeg, sport: 'MLB', market: 'batter_hits', line: 0.5, statLabel: 'Hits' }) === 'Auston Matthews Over 0.5 Hits');
check('the sheet explainer names the book line',
  nhlBookListing('draftkings', 1.5, 'over') === 'DraftKings lists this as Over 1.5.');
check('an off-line pill says 3 or more',
  nhlOffLineCount(2.5, 'over') === '3 or more' && nhlOffLineCount(1.5, 'over') === '2 or more');
const sheetQuote: StatsOddsQuote = {
  playerKey: 'auston matthews',
  playerName: 'Auston Matthews',
  gameId: 'NHL_2026-10-17_BOS_TOR',
  market: 'player_shots_on_goal',
  line: 1.5,
  side: 'over',
  book: 'draftkings',
  price: -110,
  link: null,
  bookRows: [{ bookmaker: 'draftkings', line: 1.5, over_price: -110, under_price: null }],
};
const sheet = propLineSheetInput(sheetQuote, 'NHL', 'Shots', '2 or more shots');
check('the NHL sheet keeps the plain title and puts the book line under it',
  sheet.explainer === 'DraftKings lists this as Over 1.5. Add it to your betslip now — you’ll choose the sportsbook there.');
check('Shots opens on the posted line once per NHL visit',
  shouldOpenShotsLine('NHL', 'shots', 1.5, null)
  && !shouldOpenShotsLine('NHL', 'shots', 1.5, 'NHL')
  && !shouldOpenShotsLine('NHL', 'points', 1.5, null)
  && !shouldOpenShotsLine('NHL', 'shots', null, null)
  && !shouldOpenShotsLine('NFL', 'shots', 1.5, null));
check('a missing function or a denied log is an empty average',
  nhlSkaterReadMissing({ code: '42501', message: 'permission denied for table nhl_skater_game_log' })
  && nhlSkaterReadMissing({ code: 'PGRST202', message: 'Could not find the function public.player_window_totals_nhl' })
  && nhlSkaterReadMissing({ code: '42883', message: 'function player_window_totals_nhl(integer, integer) does not exist' })
  && !nhlSkaterReadMissing({ code: '57014', message: 'canceling statement due to statement timeout' })
  && !nhlSkaterReadMissing({ message: 'permission denied for table nhl_skater_game_log' })
  && !nhlSkaterReadMissing('42501'));
check('tonight’s most common line wins, and a tie keeps the lower line',
  mostCommonPostedLine([
    { player_name: 'A', line: 1.5 },
    { player_name: 'A', line: 1.5 },
    { player_name: 'B', line: 2.5 },
    { player_name: 'C', line: 1.5 },
  ]) === 1.5
  && mostCommonPostedLine([
    { player_name: 'A', line: 2.5 },
    { player_name: 'B', line: 1.5 },
  ]) === 1.5
  && mostCommonPostedLine([]) === null);
check('an empty log does not claim the totals are missing',
  nhlLineOnlyTitle(true) === 'Lines are up.'
  && nhlLineOnlyTitle(false) === 'Has a line'
  && nhlEmptyBoardText(false, 'Shots') === 'No Shots lines posted yet.'
  && nhlEmptyBoardText(true, 'Shots') === null);

const queries = read('src/lib/queries.ts');
check('the board does not read the empty nhl_skater_stats table',
  !queries.includes("nhl_skater_stats"));
check('season totals routes NHL before the MLB view',
  queries.indexOf("if (sport === 'NHL') return fetchNhlSkaterBoard(season, null, teams)") <
    queries.indexOf(".from('v_player_season_totals_mlb')"));
check('window totals routes NHL',
  queries.includes("if (sport === 'NHL') return fetchNhlSkaterBoard(season, window, teams)"));
check('the sum is the same RPC the other sports use',
  queries.includes("const fn = 'player_window_totals_nhl'"));
check('those two failures become an empty read and every other error is thrown',
  queries.includes('if (nhlSkaterReadMissing(e)) return [];')
  && queries.includes('throw e;'));

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
check('betLabel is declared before the line-only rows',
  screen.indexOf('const betLabel = propDisplayLabel') > 0
  && screen.indexOf('const betLabel = propDisplayLabel') < screen.indexOf('const lineOnlySection'));
check('averages on that sport names the bet under the chips',
  screen.includes('!canHitRate && showOdds && lineHeadline') && screen.includes('{lineHeadline}'));
check('the posted shots line is applied once',
  screen.includes('shouldOpenShotsLine(') && screen.includes('shotsOpenKey'));
check('an empty NHL log does not say the totals are not in',
  screen.includes('nhlLineOnlyTitle(nhlLogEmpty)') && !screen.includes('Season totals aren’t in yet'));
check('NHL drops the no-games label; football keeps it',
  screen.includes('omitNoGames={nhlLinesOnly}')
  && screen.includes("'Has a line · no games logged'"));
check('the sort claim is withheld when nothing is ranked',
  screen.includes('sorted={boardChrome.headerSorted}')
  && screen.includes("accessible={!sorted}")
  && screen.includes('sorted ? `${rightLabel}, sorted highest first` : rightLabel'));
check('the filter count goes through the same chrome',
  screen.includes('resultCount={boardChrome.resultCount}'));
check('an NHL off-line pill uses the plain count',
  screen.includes('if (sport === \'NHL\') return nhlOffLineCount(line, side);'));
check('the load error is not capped at three lines',
  screen.includes('Couldn’t load the board.') && !screen.includes('numberOfLines={3}'));
const sheetSrc = read('src/components/AddLineSheet.tsx');
check('sheet prices use the minus glyph',
  sheetSrc.includes('formatAmerican(p.price).replace(/-/g, MINUS)'));

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

check('the window chips hide while the NHL log is empty',
  screen.includes("sport === 'NHL' && !loading && !error && !rowsAreStale && shownKey === readKey && rows.length === 0"));
check('a missing line is not described as missing games',
  screen.includes('nhlEmptyBoardText('));
check('the odds pill uses the minus glyph',
  screen.includes("formatAmerican(quote.price).replace(/-/g, MINUS)"));
check('a sport with no ruler does not show the direction-lock note',
  screen.includes('canHitRate && dirLockNote'));
check('the sheet title can match the caption',
  screen.includes('title: `${lineSheet.playerName} ${nhlBetCaption'));
check('an empty-log dash is not spoken',
  screen.includes('accessibilityElementsHidden={omitNoGames}'));

if (failures) {
  console.log(`\n${failures} failed`);
  process.exit(1);
}
console.log('\nall passed');
