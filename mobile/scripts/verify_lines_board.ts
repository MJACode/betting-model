/**
 * The Picks Lines board: best bettable price, never a DraftKings-only read,
 * one green row in the sheet, a navy pick mark, and the NHL 60-min switch.
 *
 * Run: npx tsx scripts/verify_lines_board.ts
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  LINES_EMPTY_GAMES,
  LINES_EMPTY_GAMES_BODY,
  LINES_EMPTY_LINES,
  LINES_ERROR_RETRY,
  LINES_FULL_GAME_NOTE,
  LINES_NO_PRICE,
  LINES_ODDS_MARKETS,
  LINES_REGULATION_NOTE,
  LINES_SPORT_CHIPS,
  linesBettableBooks,
  linesEmptyGamesBody,
  linesEmptyGamesTitle,
  linesHeaderSubtitle,
  linesLineCaption,
  linesMarketLabel,
  linesMarketsStack,
  linesMarks,
  linesPriceText,
  linesSheetRows,
  linesSideQuotes,
  type LinesOddsRow,
} from '../src/lib/linesBoard';

let passed = 0;
let failed = 0;
function check(name: string, cond: boolean, detail = '') {
  if (cond) {
    console.log(`  PASS  ${name}`);
    passed++;
  } else {
    console.log(`  FAIL  ${name}${detail ? ` — ${detail}` : ''}`);
    failed++;
  }
}

const teams = { away: 'PIT', home: 'COL' };

const spreadRows: LinesOddsRow[] = [
  { game_id: 'G', market: 'spreads', bookmaker: 'draftkings', home_price: -110, away_price: -110, spread_home: -1.5, home_link: 'https://dk.example/h', away_link: 'https://dk.example/a' },
  { game_id: 'G', market: 'spreads', bookmaker: 'fanduel', home_price: -105, away_price: -115, spread_home: -1.5, home_link: 'https://fd.example/h' },
  { game_id: 'G', market: 'spreads', bookmaker: 'betmgm', home_price: 150, away_price: -180, spread_home: -2.5 },
  { game_id: 'G', market: 'spreads', bookmaker: 'pinnacle', home_price: 200, away_price: -250, spread_home: -1.5 },
];

const spread = linesSideQuotes(spreadRows, 'G', 'spreads', teams, null);
const home = spread.find((s) => s.key === 'home');
const away = spread.find((s) => s.key === 'away');
check('spread home is FanDuel -105, not the -2.5 or Pinnacle', home?.price === -105 && home.book === 'fanduel', JSON.stringify(home));
check('spread away stays DraftKings -110 when DraftKings is the best bettable price', away?.price === -110 && away.book === 'draftkings', JSON.stringify(away));
check('the puck line is labelled for the side', home?.label === 'COL -1.5' && away?.label === 'PIT +1.5');
check('a missing price is an em dash', linesPriceText(null) === LINES_NO_PRICE && linesPriceText(undefined) === '—');
check('a price uses the American formatter', linesPriceText(180) === '+180' && linesPriceText(-110) === '-110');

const mlRows: LinesOddsRow[] = [
  { game_id: 'G', market: 'h2h', bookmaker: 'draftkings', home_price: -220, away_price: 180 },
  { game_id: 'G', market: 'h2h', bookmaker: 'fanduel', home_price: -200, away_price: 190, away_link: 'https://fd.example/a', home_link: 'https://fd.example/h' },
];
const mlSheet = linesSheetRows(mlRows, 'G', 'h2h', teams, null);
check('exactly one sheet row is the best row', mlSheet.filter((r) => r.isBest).length === 1);
check('FanDuel wins both sides, so FanDuel is the only green row', mlSheet.find((r) => r.isBest)?.bookmaker === 'fanduel');
check('the best row sorts first', mlSheet[0]?.bookmaker === 'fanduel');
check('the bet button names the side it opens', mlSheet.find((r) => r.bookmaker === 'fanduel')?.betSideLabel === 'PIT +190', JSON.stringify(mlSheet[0]));
check('a spread sheet says which number it is showing', linesLineCaption(-1.5, 'spreads') === 'Showing -1.5, the number most books have.');
check('a moneyline sheet has no number to name', linesLineCaption(null, 'h2h') === null);
check('Pinnacle is not a bettable book on this board', !linesBettableBooks().includes('pinnacle') && !linesBettableBooks().includes('bovada') && !linesBettableBooks().includes('espnbet'));

const splitRows: LinesOddsRow[] = [
  { game_id: 'G', market: 'h2h', bookmaker: 'draftkings', home_price: -218, away_price: 180 },
  { game_id: 'G', market: 'h2h', bookmaker: 'fanduel', home_price: -215, away_price: 176 },
];
const splitQuotes = linesSideQuotes(splitRows, 'G', 'h2h', teams, null);
const splitSheet = linesSheetRows(splitRows, 'G', 'h2h', teams, null);
check('each side shows its own best book', splitQuotes.find((s) => s.key === 'away')?.book === 'draftkings' && splitQuotes.find((s) => s.key === 'home')?.book === 'fanduel');
check('a split still greens one row, the earlier shop book', splitSheet.filter((r) => r.isBest).map((r) => r.bookmaker).join(',') === 'draftkings');

const regRows: LinesOddsRow[] = [
  { game_id: 'G', market: 'h2h_3way', bookmaker: 'draftkings', home_price: -125, away_price: 230, home_link: 'https://dk.example/reg' },
  { game_id: 'G', market: 'h2h', bookmaker: 'draftkings', home_price: -218, away_price: 180 },
];
const reg = linesSheetRows(regRows, 'G', 'h2h', teams, '2026-10-17T01:10:00Z', 'reg');
const tie = reg[0]?.sides.find((s) => s.key === 'tie');
const regHome = reg[0]?.sides.find((s) => s.key === 'home');
check('60 min reads the 3-way price, not the full-game price', regHome?.price === -125, JSON.stringify(regHome));
check('the tie is its own side and has no price on this read', tie?.label === 'Tie' && tie.price == null);
check('the 60-min note names the rule and the dash', LINES_REGULATION_NOTE.includes('60 minutes') && LINES_REGULATION_NOTE.includes('—'));
check('full game says overtime is included', LINES_FULL_GAME_NOTE.toLowerCase().includes('overtime'));

const late: LinesOddsRow[] = [
  { game_id: 'G', market: 'h2h', bookmaker: 'fanduel', home_price: -105, away_price: 190, snapshot_at: '2026-10-17T02:00:00Z' },
  { game_id: 'G', market: 'h2h', bookmaker: 'draftkings', home_price: -218, away_price: 180, snapshot_at: '2026-10-17T00:00:00Z' },
];
const bounded = linesSideQuotes(late, 'G', 'h2h', teams, '2026-10-17T01:10:00Z');
check('a snapshot after the opening pitch is not the price', bounded.find((s) => s.key === 'home')?.book === 'draftkings', JSON.stringify(bounded));

const marks = linesMarks([
  { game_id: 'G', model_id: 'nhl_puckline', signal_type: 'BET', is_live: false, condition_status: null },
  { game_id: 'G', model_id: 'nhl_prop_shots_on_goal', signal_type: 'BET', is_live: false, condition_status: null },
  { game_id: 'G', model_id: 'nhl_moneyline', signal_type: 'NONE', is_live: false, condition_status: null },
  { game_id: 'G', model_id: 'nhl_moneyline_regulation', signal_type: 'AVOID', is_live: false, condition_status: null },
  { game_id: 'G2', model_id: 'nhl_moneyline', signal_type: 'BET', is_live: true, condition_status: null },
  { game_id: 'G3', model_id: 'nhl_moneyline', signal_type: 'BET', is_live: false, condition_status: 'DUPLICATE' },
  { game_id: 'G4', model_id: 'nhl_moneyline_regulation', signal_type: 'BET', is_live: false, condition_status: null },
  { game_id: 'G5', model_id: 'nba_spread', signal_type: 'BET', is_live: false, condition_status: null },
]);
check('a puck-line BET marks the spread cell and the card', marks.get('G')?.chip === true && marks.get('G')?.cells.has('spreads') === true && !marks.get('G')?.cells.has('h2h'));
check('a prop BET marks the card and no cell', marks.get('G')?.cells.size === 1);
check('NONE, AVOID, a live BET and a duplicate do not mark', !marks.has('G2') && !marks.has('G3'));
check('a regulation BET marks the moneyline cell', marks.get('G4')?.cells.has('h2h') === true);
check('an NBA spread BET marks the spread cell', marks.get('G5')?.cells.has('spreads') === true);

check('NHL spread is the puck line and NBA is the spread', linesMarketLabel('NHL', 'spreads') === 'Puck line' && linesMarketLabel('NBA', 'spreads') === 'Spread');
check('moneyline and total keep their names', linesMarketLabel('NBA', 'h2h') === 'Moneyline' && linesMarketLabel('NHL', 'totals') === 'Total');
check('markets stack at 2× and not below', linesMarketsStack(2) && linesMarketsStack(2.5) && !linesMarketsStack(1.99) && !linesMarketsStack(Number.NaN));
check('sport chips are NHL, NBA, All', LINES_SPORT_CHIPS.map((c) => c.label).join('|') === 'NHL|NBA|All');
check('the odds read includes the 3-way market', (LINES_ODDS_MARKETS as readonly string[]).includes('h2h_3way'));

check('header is unknown until the read lands', linesHeaderSubtitle({ loaded: false, error: false, date: '2026-10-16', games: 0, hasOdds: false }) === '—');
check('header names a failed read', linesHeaderSubtitle({ loaded: false, error: true, date: '2026-10-16', games: 0, hasOdds: false }) === 'Lines unavailable');
check('header uses the generic empty titles', linesHeaderSubtitle({ loaded: true, error: false, date: '2026-10-16', games: 0, hasOdds: false, sport: 'all' }) === LINES_EMPTY_GAMES);
check('a sport chip names itself when it hid the slate', linesEmptyGamesTitle('NHL') === 'No NHL games today' && linesEmptyGamesTitle('NBA') === 'No NBA games today' && linesHeaderSubtitle({ loaded: true, error: false, date: '2026-10-16', games: 0, hasOdds: false, sport: 'NHL' }) === 'No NHL games today');
check('a sport chip that hid the other slate does not say the games are unposted', linesEmptyGamesBody('NHL', true) === 'NBA games are under NBA.' && linesEmptyGamesBody('NBA', true) === 'NHL games are under NHL.' && linesEmptyGamesBody('all', true) === LINES_EMPTY_GAMES_BODY && linesEmptyGamesBody('NHL', false) === LINES_EMPTY_GAMES_BODY);
check('header says no lines yet', linesHeaderSubtitle({ loaded: true, error: false, date: '2026-10-16', games: 2, hasOdds: false }) === LINES_EMPTY_LINES);
check('header counts games', linesHeaderSubtitle({ loaded: true, error: false, date: '2026-10-16', games: 2, hasOdds: true }) === '2026-10-16 · 2 games');
check('the error button says Try again', LINES_ERROR_RETRY === 'Try again');

const root = join(import.meta.dirname, '..');
const card = readFileSync(join(root, 'src/components/LinesBoard.tsx'), 'utf8');
const sheet = readFileSync(join(root, 'src/components/AllBooksSheet.tsx'), 'utf8');
const queries = readFileSync(join(root, 'src/lib/queries.ts'), 'utf8');
const picksHome = readFileSync(join(root, 'src/screens/PicksHomeScreen.tsx'), 'utf8');
check('the pick dot is navy', /backgroundColor: colors\.brandNavy/.test(card));
check('the price is the callout, and only the side label is clipped', /styles\.cellPrice/.test(card) && /fontSize: font\.size\.callout/.test(card) && /numberOfLines=\{1\}/.test(card));
check('an unloaded board is the skeleton, not the empty state', /if \(!loaded && !error\)/.test(card));
check('a row opens its own book only', /openBookBetslip\(row\.bookmaker, row\.betLink, \{ sameBookOnly: true \}\)/.test(sheet));
check('the pick mark is not the bet green', !/colors\.bet(?!Soft|Ink)/.test(card) && !/colors\.bet(?!Soft|Ink)/.test(sheet));
check('the sheet greens only the best row', /row\.isBest && styles\.rowBest/.test(sheet));
check('the lines read is the all-books view, paged, for the board markets', /function fetchLinesBoardOdds[\s\S]*?\.from\('v_latest_odds_all_books'\)[\s\S]*?LINES_ODDS_MARKETS[\s\S]*?fetchAllPages/.test(queries) || /fetchAllPages<OddsByBookRow>\([\s\S]*?\.from\('v_latest_odds_all_books'\)[\s\S]*?LINES_ODDS_MARKETS/.test(queries));
check('games are read for the lines sports, not only picked games', /function fetchGamesForLinesBoard[\s\S]*?\.from\('games'\)[\s\S]*?LINES_SPORTS/.test(queries));
check('a paused-only row is not the Pick chip', /const linesPicks: LinesPickRef\[\] = allData\.map/.test(picksHome));

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
console.log('ALL PASS');
