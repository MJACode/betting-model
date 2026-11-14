/**
 * Standalone verification for the NCAABW sport wiring. Run with:
 *
 *   npx tsx scripts/verify_ncaabw_ui.ts
 *
 * NCAABW (women's college basketball) joined the app on 2026-11-10 so its
 * totals model's picks reach a board. Before that the app had no NCAABW chip,
 * dropped `sport: 'NCAABW'` from a push, and filed every ncaabw_* model under
 * the MEN'S sport: 'ncaabw_total_blend'.startsWith('ncaab') is true.
 *
 * One pre-game model, `ncaabw_total_blend`, the halftime total, a Players
 * board with the same chips as NCAAB, and a Teams board (Net Rtg). No props.
 */

import { SPORTS, type Sport } from '../src/hooks/useSportFilter';
import { routeForPush, PUSH_ROUTE_VERSION } from '../src/lib/pushRoute';
import {
  MODEL_META, betTypeGroups, betTypePickerGroups, modelCategory, modelLong, modelPageTiming, modelProbabilityNote,
  modelShort, sportOfModel,
} from '../src/lib/modelMeta';
import {
  BETTABLE_BOOKS, bookLabel, bookLabelShort, bookName, gameMarketForModel, isBettableBook, marketClassForModel,
  pickLineQuotes, pickTimingInfo,
} from '../src/lib/markets';
import type { BookPricedRow, Pick } from '../src/types';
import { GROUP_ORDER, defaultStatFor, propMarketForStat, statsForSport, supportsHitRate } from '../src/lib/statCatalog';
import { supportsTeamBoard, teamBoardSeason, teamSeasonLabel } from '../src/lib/teamStatCatalog';
import { supportsPlayerDetail } from '../src/lib/playerLog';
import { boardSegmentsFor, segmentsForSport } from '../src/lib/statSegments';
import { ALL_SPORTS } from '../src/lib/dailyResults';
import { teamScoreUnit } from '../src/lib/teamForm';
import { hasLiveModel, liveEmptySubtitle } from '../src/lib/liveSports';
import { isGameOver } from '../src/lib/format';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const NCAABW = 'NCAABW' as Sport;
const NCAAB = 'NCAAB' as Sport;

// ── The sport ────────────────────────────────────────────────────────────────
check('NCAABW is a sport chip', SPORTS.includes(NCAABW));
check('NCAABW sits right after NCAAB', SPORTS.indexOf(NCAABW) === SPORTS.indexOf(NCAAB) + 1, SPORTS.join(','));
check('NCAABW is in the daily recap order, right after NCAAB',
  ALL_SPORTS.indexOf('NCAABW') === ALL_SPORTS.indexOf('NCAAB') + 1 && ALL_SPORTS.indexOf('NCAAB') >= 0,
  ALL_SPORTS.join(','));

// ── A push that names NCAABW switches the board to it ────────────────────────
const route = routeForPush({ v: PUSH_ROUTE_VERSION, type: 'new_bets', sport: 'NCAABW' });
check('a new-bets push for NCAABW opens the NCAABW Signals board',
  route?.kind === 'board' && route.view === 'signals' && route.sport === 'NCAABW', JSON.stringify(route));
const mens = routeForPush({ v: PUSH_ROUTE_VERSION, type: 'new_bets', sport: 'NCAAB' });
check('a push for the men\'s sport still opens the men\'s board',
  mens?.kind === 'board' && mens.sport === 'NCAAB', JSON.stringify(mens));

// ── The trap: every women's id starts with 'ncaab' ───────────────────────────
const TOTALS = 'ncaabw_total_blend';
check(`${TOTALS} is filed under NCAABW, not NCAAB`, sportOfModel(TOTALS) === 'NCAABW', sportOfModel(TOTALS));
check('any ncaabw_ id is filed under NCAABW', sportOfModel('ncaabw_spread_market') === 'NCAABW',
  sportOfModel('ncaabw_spread_market'));
check('the men\'s ids are unchanged',
  sportOfModel('ncaab_total_blend') === 'NCAAB' && sportOfModel('ncaab_live_spread_h1') === 'NCAAB'
    && sportOfModel('ncaaf_over_under') === 'NCAAF');
const womensLabelled = Object.keys(MODEL_META).filter((id) => sportOfModel(id) === 'NCAABW');
check('the app labels exactly the two women\'s models',
  JSON.stringify(womensLabelled) === JSON.stringify([TOTALS, 'ncaabw_live_total_ht']), womensLabelled.join(','));
check('no women\'s model is listed with the men\'s',
  !Object.keys(MODEL_META).some((id) => id.startsWith('ncaabw') && sportOfModel(id) === 'NCAAB'));

// ── The model ────────────────────────────────────────────────────────────────
check('its badge is O/U', modelShort(TOTALS) === 'O/U', modelShort(TOTALS));
check('its name is NCAABW Totals', modelLong(TOTALS) === 'NCAABW Totals', modelLong(TOTALS));
check('it is a game market', modelCategory(TOTALS) === 'game');
check('it is priced off the totals rows', gameMarketForModel(TOTALS) === 'totals', String(gameMarketForModel(TOTALS)));
check('a parlay treats it as a game total', marketClassForModel(TOTALS) === 'game_total', marketClassForModel(TOTALS));
// The custom-model catalog: its own NCAABW group, and nothing of it under NCAAB.
const groups = betTypeGroups();
const womensGroup = groups.find((g) => g.sport === 'NCAABW');
check('the custom-model catalog has an NCAABW group holding the totals model',
  !!womensGroup && womensGroup.options.length === 1 && womensGroup.options[0].id === TOTALS
    && womensGroup.options[0].label === 'NCAABW Totals',
  JSON.stringify(womensGroup));
check('the NCAABW group sits right after the NCAAB group',
  groups.findIndex((g) => g.sport === 'NCAABW') === groups.findIndex((g) => g.sport === 'NCAAB') + 1,
  groups.map((g) => g.sport).join(','));
check('the NCAAB group holds no women\'s model',
  !(groups.find((g) => g.sport === 'NCAAB')?.options ?? []).some((o) => o.id.startsWith('ncaabw')));
// The picker offers moneyline, spread and props slots only, so a totals model
// adds no row (the men's totals model adds none either).
check('the custom-model picker has no NCAABW row (totals are not a slot)',
  betTypePickerGroups().filter((g) => g.sport === 'NCAABW').length === 0);

// ── When it decides (scripts/ncaabw_total_card.py) ───────────────────────────
// Once, at DraftKings' first posted total, only while that total and both
// prices still stand. DraftKings posted its first women's total 1 to 6 Eastern
// dates before the game in 155 of 1,772 priced games, and on the game's own
// date in the rest; that first total stood a median 136 minutes in 2024-25 and
// 85 in 2025-26 (docs/sports/ncaabw.md), and one in ten changed within 10
// minutes (the card's own header). So the men's "day before" and "within half
// an hour" are both wrong for it.
const timing = modelPageTiming(TOTALS);
const allTiming = [timing.title, timing.body, timing.empty, timing.note];
check('its page says it decides at DraftKings\' opening total, usually on the day of the game',
  timing.title === 'Decided when the total opens'
    && timing.body.includes('at DraftKings’ opening total, usually within minutes of it posting')
    && timing.body.includes('DraftKings opens most totals on the day of the game, some up to six days before'),
  `${timing.title} | ${timing.body}`);
check('its page says it bets only that opening total at the same prices, and that an opening total moves',
  timing.body.includes('only if DraftKings still offers that opening total at the same prices')
    && timing.body.includes('it skips the game') && timing.body.includes('An opening total can change within minutes')
    && timing.body.includes('check DraftKings’ total and price') && timing.body.includes('never re-priced')
    && timing.note === 'Posted at DraftKings’ opening total and never re-priced.',
  `${timing.body} | ${timing.note}`);
check('its page does not carry the men\'s measurements',
  !allTiming.some((s) => s.includes('day before') || s.includes('half an hour')), allTiming.join(' | '));
check('its page names no Eastern clock time (DraftKings posts at no fixed hour)',
  !allTiming.some((s) => /\d\s?(am|pm)\b|\d:\d\d/i.test(s)));
check('its page is not the default "locks for the day" copy',
  !allTiming.some((s) => s.includes('pipeline refresh') || s.includes('hourly')), allTiming.join(' | '));
const mensTiming = modelPageTiming('ncaab_total_blend');
check('the men\'s totals page is unchanged',
  mensTiming.body.includes('DraftKings opens most totals the day before the game, some on game day')
    && mensTiming.body.includes('often changes within half an hour'), mensTiming.body);
check('its probability note is the plain sentence',
  modelProbabilityNote(TOTALS) === 'What our model says is the chance this side hits.');

const mkPick = (over: Partial<Pick>): Pick => ({
  pick_id: 1, game_id: 'NCAABW_2026-11-10_youngstown-state_toledo', game_date: '2026-11-10', sport: 'NCAABW',
  model_id: TOTALS, signal_type: 'BET', pick_side: 'over', pick_label: 'Youngstown State vs Toledo Over 131.5',
  scored_line: 131.5, dk_odds: -110, decision_odds: -110, decision_book: 'draftkings', line_book: null,
  created_at: '2026-11-10T16:05:00Z', player_id: null, is_live: false, ...over,
} as unknown as Pick);
const posted = pickTimingInfo(mkPick({}));
check('its Pick Detail note says posted once, not the first scoring run of the day',
  !!posted && posted.kind === 'posted' && posted.note.startsWith('Posted once') && !posted.note.includes('first scoring run'),
  posted?.note ?? 'null');
check('its Pick Detail note says an opening total moves, and to check DraftKings\' total and price',
  !!posted && posted.note.includes('An opening total can change within minutes')
    && posted.note.includes('check DraftKings’ total and price before you bet') && !posted.note.includes('half an hour'),
  posted?.note ?? 'null');

// ── The women's extra books (config.NCAABW_EXTRA_BOOKMAKERS) ─────────────────
// Stored for women's games as reference prices; none is a book a pick may
// name. Read in production 2026-11-10: v_latest_odds_all_books held rows at
// all seven for the women's games of 2026-11-08 to 11-10.
const EXTRA = ['espnbet', 'ballybet', 'fliff', 'betonlineag', 'lowvig', 'unibet', 'betwhale'];
check('none of the seven is a book a member is sent to',
  EXTRA.every((b) => !isBettableBook(b) && !(BETTABLE_BOOKS as string[]).includes(b)),
  EXTRA.filter((b) => isBettableBook(b)).join(','));
check('each of the seven prints a name, never its feed key',
  EXTRA.every((b) => bookName(b) !== b), EXTRA.map((b) => bookName(b)).join(', '));
check('each has a short label of five letters or fewer',
  EXTRA.every((b) => bookLabel(b).length <= 5), EXTRA.map((b) => `${b}=${bookLabel(b)}`).join(' '));
// With no label of its own a key is clipped to four letters: BETO, LOWV, UNIB, BETW.
check('the four books only this feed carries have a label of their own, not a clipped key',
  ['betonlineag', 'lowvig', 'unibet', 'betwhale'].every((b) => bookLabel(b) !== b.slice(0, 4).toUpperCase()),
  ['betonlineag', 'lowvig', 'unibet', 'betwhale'].map((b) => bookLabel(b)).join(' '));
check('no three-letter label of the seven is another bettable book\'s',
  EXTRA.every((b) => !BETTABLE_BOOKS.some((x) => bookLabelShort(x) === bookLabelShort(b))),
  EXTRA.map((b) => bookLabelShort(b)).join(' '));
check('DraftKings, the only book the model names, is still bettable', isBettableBook('draftkings'));
// A women's pick's line chips: DraftKings' locked price, and a bettable book
// at the same total. Never one of the seven, and never a different total.
const row = (bookmaker: string, total: number, over: number): BookPricedRow => ({
  game_id: 'NCAABW_2026-11-10_youngstown-state_toledo', market: 'totals', bookmaker,
  home_price: null, away_price: null, over_price: over, under_price: -110, spread_home: null, total_line: total,
  home_link: null, away_link: null, over_link: null, under_link: null, snapshot_at: '2026-11-10T16:00:00Z',
} as unknown as BookPricedRow);
const chips = pickLineQuotes(mkPick({}), [
  row('draftkings', 131.5, -112), row('fanduel', 131.5, -105), row('betmgm', 132.5, +100),
  row('ballybet', 131.5, +100), row('fliff', 131.5, +105), row('betwhale', 131.5, +110), row('espnbet', 131.5, +102),
]).map((q) => `${q.bookmaker}:${q.price}${q.isRecord ? ':record' : ''}`);
check('a women\'s pick offers DraftKings\' locked price and FanDuel\'s, and none of the seven',
  JSON.stringify(chips) === JSON.stringify(['fanduel:-105', 'draftkings:-110:record']), chips.join(' '));

// ── Stats: the Players board, the same chips as NCAAB, and nothing else ──────
const statKeys = statsForSport(NCAABW).map((d) => d.key);
check('NCAABW has the NCAAB chips, Points first',
  GROUP_ORDER.NCAABW.join() === 'NCAABW'
    && defaultStatFor(NCAABW)?.key === 'points'
    && statKeys.join() === 'points,rebounds,assists,threes,pra,steals,blocks,minutes',
  statKeys.join());
check('NCAABW has a hit-rate view', supportsHitRate(NCAABW));
check('NCAABW has a player page', supportsPlayerDetail(NCAABW));
check('NCAABW has a Teams board, Players | Teams',
  supportsTeamBoard(NCAABW)
    && segmentsForSport(NCAABW).join() === 'players,teams'
    && boardSegmentsFor(NCAABW).join() === 'players,teams');
check('no NCAABW chip carries a prop market',
  statsForSport(NCAABW).every((d) => propMarketForStat(d) == null));
check('NCAABW draws a Players | Teams row',
  segmentsForSport(NCAABW).length === 2 && boardSegmentsFor(NCAABW).length === 2,
  segmentsForSport(NCAABW).join(','));
// The halftime total (models/ncaabw_live_ht.py, 2026-11-11) is the women's
// in-play model: the Live board says when it bets, and the model resolves to
// the game's total everywhere a price is looked up.
check('NCAABW has an in-play model', hasLiveModel('NCAABW'));
check('the empty Live board says the model bets at halftime',
  liveEmptySubtitle('NCAABW').includes('during its halftime break')
  && liveEmptySubtitle('NCAABW').includes('at most once'), liveEmptySubtitle('NCAABW'));
check('the halftime model belongs to NCAABW, not NCAAB', sportOfModel('ncaabw_live_total_ht') === 'NCAABW');
check('the halftime model has its own name',
  MODEL_META.ncaabw_live_total_ht?.longLabel === 'NCAABW Live Totals'
  && MODEL_META.ncaabw_live_total_ht?.shortLabel === 'LIVE O/U');
check('an NCAABW form strip reads PTS', teamScoreUnit('NCAABW') === 'PTS');
// ESPN labels the women's season by its ending year: 2026-27 is 2027.
check('an NCAABW season is labelled by its ending year',
  teamBoardSeason(NCAABW, new Date('2026-11-10T17:00:00Z')) === 2027
    && teamBoardSeason(NCAABW, new Date('2027-03-10T17:00:00Z')) === 2027
    && teamSeasonLabel(NCAABW, 2027) === '2026-27',
  `${teamBoardSeason(NCAABW, new Date('2026-11-10T17:00:00Z'))} ${teamSeasonLabel(NCAABW, 2027)}`);

// ── When a game leaves the board ─────────────────────────────────────────────
const hoursAgo = (h: number) => new Date(Date.now() - h * 3_600_000).toISOString();
check('an NCAABW game 2h after tip is still on the board',
  !isGameOver({ sport: 'NCAABW', commence_time: hoursAgo(2), home_score: null, away_score: null }, 'NCAABW'));
check('an NCAABW game 3h after tip with no final has left the board',
  isGameOver({ sport: 'NCAABW', commence_time: hoursAgo(3.05), home_score: null, away_score: null }, 'NCAABW'));
check('an NCAABW final leaves the board at once',
  isGameOver({ sport: 'NCAABW', commence_time: hoursAgo(0.5), home_score: 71, away_score: 68 }, 'NCAABW'));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILED`);
if (failures > 0) process.exit(1);
