/**
 * The Picks Lines board: best bettable price, never a DraftKings-only read,
 * green only on the price that wins its side, a navy pick mark, and the
 * NHL 60-min switch. The tie stays hidden until draw_price is on the row.
 *
 * Run: npx tsx scripts/verify_lines_board.ts
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  LINES_CELL_HINT,
  LINES_EMPTY_GAMES,
  LINES_EMPTY_GAMES_BODY,
  LINES_EMPTY_LINES,
  LINES_ERROR_RETRY,
  LINES_FULL_GAME_NOTE,
  LINES_GAME_UNPRICED,
  LINES_MINUS,
  LINES_NO_PRICE,
  LINES_ODDS_MARKETS,
  LINES_PAUSED_CHIP,
  LINES_REGULATION_NOTE,
  LINES_REGULATION_NOTE_PRICED,
  LINES_SPORT_CHIPS,
  linesBettableBooks,
  linesEmptyGamesBody,
  linesEmptyGamesTitle,
  linesHeaderSubtitle,
  linesLineCaption,
  linesMarketLabel,
  linesMarketsStack,
  linesMarks,
  linesPausedChipLabel,
  linesPickChipLabel,
  linesPriceText,
  linesSheetRows,
  linesSideQuotes,
  type LinesOddsRow,
  type LinesSheetSide,
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
check('the puck line is labelled for the side, with a true minus', home?.label === `COL ${LINES_MINUS}1.5` && away?.label === 'PIT +1.5');
check('the card can put the spread number on its own line', home?.name === 'COL' && home?.lineText === `${LINES_MINUS}1.5` && away?.name === 'PIT' && away?.lineText === '+1.5');
check('a missing price is an em dash', linesPriceText(null) === LINES_NO_PRICE && linesPriceText(undefined) === '—');
check('a negative price is a true minus, and a plus stays a plus', linesPriceText(180) === '+180' && linesPriceText(-110) === `${LINES_MINUS}110` && !linesPriceText(-105).includes('-'));

const mlRows: LinesOddsRow[] = [
  { game_id: 'G', market: 'h2h', bookmaker: 'draftkings', home_price: -220, away_price: 180 },
  { game_id: 'G', market: 'h2h', bookmaker: 'fanduel', home_price: -200, away_price: 190, away_link: 'https://fd.example/a', home_link: 'https://fd.example/h' },
];
const mlSheet = linesSheetRows(mlRows, 'G', 'h2h', teams, null);
const fdMl = mlSheet.find((r) => r.bookmaker === 'fanduel');
const dkMl = mlSheet.find((r) => r.bookmaker === 'draftkings');
const side = (row: { sides: LinesSheetSide[] } | undefined, key: string) => row?.sides.find((s) => s.key === key);
check('exactly one sheet row wins every side', mlSheet.filter((r) => r.isBest).length === 1 && fdMl?.isBest === true && dkMl?.isBest === false);
check('only the winning prices are the best price', side(fdMl, 'home')?.isBestPrice === true && side(fdMl, 'away')?.isBestPrice === true && side(dkMl, 'home')?.isBestPrice === false && side(dkMl, 'away')?.isBestPrice === false);
check('the best row sorts first', mlSheet[0]?.bookmaker === 'fanduel');
check('each side keeps its own link', side(fdMl, 'away')?.link === 'https://fd.example/a' && side(fdMl, 'home')?.link === 'https://fd.example/h');
check('the line caption names the market and drops the home sign', linesLineCaption(-1.5, 'spreads', 'NHL') === 'Puck line 1.5 · the line most books post' && linesLineCaption(-1.5, 'spreads', 'NBA') === 'Spread 1.5 · the line most books post' && linesLineCaption(6.5, 'totals', 'NHL') === 'Total 6.5 · the line most books post');
check('a moneyline sheet has no number to name', linesLineCaption(null, 'h2h', 'NHL') === null);
check('Pinnacle is not a bettable book on this board', !linesBettableBooks().includes('pinnacle') && !linesBettableBooks().includes('bovada') && !linesBettableBooks().includes('espnbet'));

const splitRows: LinesOddsRow[] = [
  { game_id: 'G', market: 'h2h', bookmaker: 'draftkings', home_price: -218, away_price: 180 },
  { game_id: 'G', market: 'h2h', bookmaker: 'fanduel', home_price: -215, away_price: 176 },
];
const splitQuotes = linesSideQuotes(splitRows, 'G', 'h2h', teams, null);
const splitSheet = linesSheetRows(splitRows, 'G', 'h2h', teams, null);
check('each side shows its own best book', splitQuotes.find((s) => s.key === 'away')?.book === 'draftkings' && splitQuotes.find((s) => s.key === 'home')?.book === 'fanduel');
const splitDk = splitSheet.find((r) => r.bookmaker === 'draftkings');
const splitFd = splitSheet.find((r) => r.bookmaker === 'fanduel');
check('a split is not a Best row', splitSheet.every((r) => r.isBest === false));
check('a split greens only the price that wins its side', side(splitDk, 'away')?.isBestPrice === true && side(splitDk, 'home')?.isBestPrice === false && side(splitFd, 'home')?.isBestPrice === true && side(splitFd, 'away')?.isBestPrice === false);

const mtl = { away: 'BOS', home: 'MTL' };
const fdMgm: LinesOddsRow[] = [
  { game_id: 'G', market: 'h2h', bookmaker: 'fanduel', home_price: -140, away_price: 130, home_link: 'https://fd.example/mtl', away_link: 'https://fd.example/bos' },
  { game_id: 'G', market: 'h2h', bookmaker: 'betmgm', home_price: -132, away_price: 120, home_link: 'https://mgm.example/mtl', away_link: 'https://mgm.example/bos' },
];
const fdMgmSheet = linesSheetRows(fdMgm, 'G', 'h2h', mtl, null);
const fdRow = fdMgmSheet.find((r) => r.bookmaker === 'fanduel');
const mgmRow = fdMgmSheet.find((r) => r.bookmaker === 'betmgm');
check('FanDuel −140 is not Best when BetMGM −132 is the better home price', fdMgmSheet.every((r) => r.isBest === false));
check('BetMGM −132 is the green home price and FanDuel +130 is the green away price', side(mgmRow, 'home')?.isBestPrice === true && side(fdRow, 'home')?.isBestPrice === false && side(fdRow, 'away')?.isBestPrice === true && side(mgmRow, 'away')?.isBestPrice === false);
check('MTL at FanDuel keeps the FanDuel link', side(fdRow, 'home')?.link === 'https://fd.example/mtl' && side(fdRow, 'home')?.label === 'MTL');

const tiedRows: LinesOddsRow[] = [
  { game_id: 'G', market: 'h2h', bookmaker: 'fanduel', home_price: -150, away_price: 130 },
  { game_id: 'G', market: 'h2h', bookmaker: 'draftkings', home_price: -150, away_price: 130 },
];
const tiedSheet = linesSheetRows(tiedRows, 'G', 'h2h', teams, null);
check('a tie on every side marks only the earlier shop book Best', tiedSheet.filter((r) => r.isBest).map((r) => r.bookmaker).join(',') === 'draftkings');
check('a tied price stays green on both books', tiedSheet.every((r) => r.sides.every((s) => s.isBestPrice)));

const regRows: LinesOddsRow[] = [
  { game_id: 'G', market: 'h2h_3way', bookmaker: 'draftkings', home_price: -125, away_price: 230, home_link: 'https://dk.example/reg' },
  { game_id: 'G', market: 'h2h', bookmaker: 'draftkings', home_price: -218, away_price: 180 },
];
const reg = linesSheetRows(regRows, 'G', 'h2h', teams, '2026-10-17T01:10:00Z', 'reg');
const tie = reg[0]?.sides.find((s) => s.key === 'tie');
const regHome = reg[0]?.sides.find((s) => s.key === 'home');
check('60 min reads the 3-way price, not the full-game price', regHome?.price === -125, JSON.stringify(regHome));
check('the tie is hidden until draw_price is returned', tie == null && reg[0]?.sides.map((s) => s.key).join(',') === 'away,home');
check('the 60-min note says the tie is not shown yet', LINES_REGULATION_NOTE.includes('60 minutes') && LINES_REGULATION_NOTE.includes('Overtime counts as a loss') && LINES_REGULATION_NOTE.includes('isn’t shown yet'));
check('a returned tie price is a side, and the note no longer says it is missing', (() => {
  const priced = linesSheetRows(
    [{ ...regRows[0]!, draw_price: 330 }],
    'G',
    'h2h',
    teams,
    '2026-10-17T01:10:00Z',
    'reg',
  );
  const shown = priced[0]?.sides.find((s) => s.key === 'tie');
  return shown?.label === 'Tie' && shown.price === 330 && !LINES_REGULATION_NOTE_PRICED.includes('shown yet');
})());
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
const pausedOnly = linesMarks([], [
  { game_id: 'P', model_id: 'nhl_moneyline', signal_type: 'BET', is_live: false, condition_status: null, pick_id: 9, pick_label: 'MTL ML' },
]);
check('a paused-only BET is not the Pick chip and not a navy cell', pausedOnly.get('P')?.chip === false && pausedOnly.get('P')?.cells.size === 0 && pausedOnly.get('P')?.picks.length === 0 && pausedOnly.get('P')?.paused.length === 1 && pausedOnly.get('P')?.paused[0]?.label === 'MTL ML');
check('the chips name a count, and one paused row says Paused pick', linesPickChipLabel(1) === '1 pick' && linesPickChipLabel(2) === '2 picks' && linesPausedChipLabel(1) === LINES_PAUSED_CHIP);

check('NHL spread is the puck line and NBA is the spread', linesMarketLabel('NHL', 'spreads') === 'Puck line' && linesMarketLabel('NBA', 'spreads') === 'Spread');
check('moneyline and total keep their names', linesMarketLabel('NBA', 'h2h') === 'Moneyline' && linesMarketLabel('NHL', 'totals') === 'Total');
check('markets stack at 2× and not below', linesMarketsStack(2) && linesMarketsStack(2.5) && !linesMarketsStack(1.99) && !linesMarketsStack(Number.NaN));
check('sport chips are NHL, NBA, All', LINES_SPORT_CHIPS.map((c) => c.label).join('|') === 'NHL|NBA|All');
check('the odds read includes the 3-way market', (LINES_ODDS_MARKETS as readonly string[]).includes('h2h_3way'));

const noGames: { sport: string }[] = [];
check('header is unknown until the read lands', linesHeaderSubtitle({ loaded: false, error: false, date: '2026-10-16', games: noGames, hasOdds: false }) === '—');
check('header names a failed read', linesHeaderSubtitle({ loaded: false, error: true, date: '2026-10-16', games: noGames, hasOdds: false }) === 'Lines unavailable');
check('header uses the generic empty titles', linesHeaderSubtitle({ loaded: true, error: false, date: '2026-10-16', games: noGames, hasOdds: false, sport: 'all' }) === LINES_EMPTY_GAMES);
check('a sport chip names itself when it hid the slate', linesEmptyGamesTitle('NHL') === 'No NHL games today' && linesEmptyGamesTitle('NBA') === 'No NBA games today' && linesHeaderSubtitle({ loaded: true, error: false, date: '2026-10-16', games: noGames, hasOdds: false, sport: 'NHL' }) === 'No NHL games today');
check('a sport chip that hid the other slate does not say the games are unposted', linesEmptyGamesBody('NHL', true) === 'NBA games are under NBA.' && linesEmptyGamesBody('NBA', true) === 'NHL games are under NHL.' && linesEmptyGamesBody('all', true) === LINES_EMPTY_GAMES_BODY && linesEmptyGamesBody('NHL', false) === LINES_EMPTY_GAMES_BODY);
check('header says no lines yet', linesHeaderSubtitle({ loaded: true, error: false, date: '2026-10-16', games: [{ sport: 'NHL' }, { sport: 'NBA' }], hasOdds: false }) === LINES_EMPTY_LINES);
check('header names the weekday and each sport', linesHeaderSubtitle({ loaded: true, error: false, date: '2026-10-16', games: [{ sport: 'NHL' }, { sport: 'NHL' }, { sport: 'NBA' }], hasOdds: true }) === 'Friday · 2 NHL games · 1 NBA game');
check('the error button says Try again', LINES_ERROR_RETRY === 'Try again');
check('a game with no prices says so in one line', LINES_GAME_UNPRICED === 'No lines posted yet');
check('a cell tells VoiceOver it opens every book', LINES_CELL_HINT === 'Opens every book’s price');

const root = join(import.meta.dirname, '..');
const card = readFileSync(join(root, 'src/components/LinesBoard.tsx'), 'utf8');
const sheet = readFileSync(join(root, 'src/components/AllBooksSheet.tsx'), 'utf8');
const queries = readFileSync(join(root, 'src/lib/queries.ts'), 'utf8');
const picksHome = readFileSync(join(root, 'src/screens/PicksHomeScreen.tsx'), 'utf8');
check('the pick dot is navy', /backgroundColor: colors\.brandNavy/.test(card));
check('the price is the callout, and only the side label is clipped', /styles\.cellPrice/.test(card) && /fontSize: font\.size\.callout/.test(card) && /numberOfLines=\{1\}/.test(card));
check('an unloaded board is the skeleton, not the empty state', /if \(!loaded && !error\)/.test(card));
check('each side opens its own book and its own link', /openBookBetslip\(row\.bookmaker, s\.link, \{ sameBookOnly: true \}\)/.test(sheet));
check('the pick mark is not the bet green', !/colors\.bet(?!Soft|Ink)/.test(card) && !/colors\.bet(?!Soft|Ink)/.test(sheet));
check('green is the winning price, and Best is the word on a row that wins every side', /best && styles\.sideBest/.test(sheet) && /best=\{s\.isBestPrice\}/.test(sheet) && /row\.isBest \? <Text style=\{styles\.best\}>Best<\/Text>/.test(sheet) && !/rowBest/.test(sheet));
check('the book name is allowed to wrap', /<Text style=\{styles\.book\}>\{bookName\(row\.bookmaker\)\}<\/Text>/.test(sheet));
check('the sheet header shows the game time', /when=\{openGame \? formatGameTimeET\(openGame\.commence_time\) : ''\}/.test(card));
check('a game with no prices is one line, not six cells', card.includes('LINES_GAME_UNPRICED') && card.includes('LINES_CELL_HINT'));
check('the Pick chip opens detail and the paused chip is named', /onOpenPick\(picked\.picks, 'pick'\)/.test(card) && /linesPausedChipLabel/.test(card) && /colors\.textTertiary/.test(card));
check('the lines read is the all-books view, paged, for the board markets', /function fetchLinesBoardOdds[\s\S]*?\.from\('v_latest_odds_all_books'\)[\s\S]*?LINES_ODDS_MARKETS[\s\S]*?fetchAllPages/.test(queries) || /fetchAllPages<OddsByBookRow>\([\s\S]*?\.from\('v_latest_odds_all_books'\)[\s\S]*?LINES_ODDS_MARKETS/.test(queries));
check('games are read for the lines sports, not only picked games', /function fetchGamesForLinesBoard[\s\S]*?\.from\('games'\)[\s\S]*?LINES_SPORTS/.test(queries));
check('a paused-only row is not the Pick chip', /const linesPicks: LinesPickRef\[\] = allData\.map/.test(picksHome) && /const linesPaused: LinesPickRef\[\] = pausedData\.map/.test(picksHome));
check('the pick chip opens Pick Detail', /navigation\.navigate\('PickDetail'/.test(picksHome));
check('several paused picks are titled as paused', /Paused picks on this game/.test(picksHome));
const sportsStyle = picksHome.slice(picksHome.indexOf('linesSports:'), picksHome.indexOf('linesSports:') + 900);
check('the sport-chip row keeps 8pt under itself', /marginBottom: spacing\.sm/.test(sportsStyle) && !/marginBottom: spacing\.lg/.test(sportsStyle));
check('the sheet keeps VoiceOver on its rows', /accessibilityViewIsModal/.test(sheet));
const repo = join(import.meta.dirname, '..', '..');
const mig = readFileSync(join(repo, 'data/migrations/add_draw_price_to_latest_odds_view_2026_10_16.sql'), 'utf8');
const active = readFileSync(join(repo, 'data/view_migrations.py'), 'utf8');
check('the draw_price migration appends the column on the state-table view', mig.includes('l.draw_price') && mig.includes('security_invoker = on') && mig.includes('JOIN latest_odds'));
check('that migration is not an active view migration', !active.includes('add_draw_price_to_latest_odds_view_2026_10_16.sql'));

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
console.log('ALL PASS');
