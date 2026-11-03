/**
 * Standalone verification for the NCAAB sport wiring. Run with:
 *
 *   npx tsx scripts/verify_ncaab_ui.ts
 *
 * NCAAB (men's college basketball) joined the app on 2026-10-30 so its totals
 * model's picks reach a board. Before that the app had no NCAAB chip, filed an
 * ncaab_* model under MLB, and dropped `sport: 'NCAAB'` from a push.
 *
 * The totals model writes its picks as `ncaab_total_blend`
 * (models/ncaab_total_blend.py MODEL_ID, in the model's own pull request). The
 * app first labelled it `ncaab_over_under`, the id in the model's build plan;
 * no model writes that id.
 */

import { SPORTS, type Sport } from '../src/hooks/useSportFilter';
import { routeForPush, PUSH_ROUTE_VERSION } from '../src/lib/pushRoute';
import {
  MODEL_META, betTypePickerGroups, modelCategory, modelLong, modelPageTiming, modelProbabilityNote, modelShort,
  sportOfModel,
} from '../src/lib/modelMeta';
import { recordNoteFor, recordNoteShortFor } from '../src/lib/myBooks';
import { gameMarketForModel, marketClassForModel, pickTimingInfo } from '../src/lib/markets';
import type { Pick } from '../src/types';
import { GROUP_ORDER, defaultStatFor, supportsHitRate } from '../src/lib/statCatalog';
import { supportsTeamBoard } from '../src/lib/teamStatCatalog';
import { segmentsForSport } from '../src/lib/statSegments';
import { ALL_SPORTS } from '../src/lib/dailyResults';
import { teamScoreUnit } from '../src/lib/teamForm';
import { isGameOver } from '../src/lib/format';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const NCAAB = 'NCAAB' as Sport;

// ── The sport ────────────────────────────────────────────────────────────────
check('NCAAB is a sport chip', SPORTS.includes(NCAAB));
check('NCAAB sits right after NCAAF', SPORTS.indexOf(NCAAB) === SPORTS.indexOf('NCAAF' as Sport) + 1,
  SPORTS.join(','));
check('NCAAB is in the daily recap order', ALL_SPORTS.includes('NCAAB'), ALL_SPORTS.join(','));

// ── A push that names NCAAB switches the board to it ─────────────────────────
const route = routeForPush({ v: PUSH_ROUTE_VERSION, type: 'new_bets', sport: 'NCAAB' });
check('a new-bets push for NCAAB opens the NCAAB Signals board',
  route?.kind === 'board' && route.view === 'signals' && route.sport === 'NCAAB', JSON.stringify(route));
const unknown = routeForPush({ v: PUSH_ROUTE_VERSION, type: 'new_bets', sport: 'NCAAW' });
check('a sport the app does not have still leaves the sport alone',
  unknown?.kind === 'board' && unknown.sport === null, JSON.stringify(unknown));

// ── Models ───────────────────────────────────────────────────────────────────
const TOTALS = 'ncaab_total_blend';
check(`${TOTALS} is filed under NCAAB`, sportOfModel(TOTALS) === 'NCAAB');
check('any ncaab_ id is filed under NCAAB, not MLB', sportOfModel('ncaab_spread_market') === 'NCAAB');
check('NCAAF ids are unchanged', sportOfModel('ncaaf_over_under') === 'NCAAF');
check(`${TOTALS} has a label`, !!MODEL_META[TOTALS]);
check('the build-plan id ncaab_over_under has no label (no model writes it)', !MODEL_META.ncaab_over_under);
check('its badge is O/U', modelShort(TOTALS) === 'O/U', modelShort(TOTALS));
check('its name is NCAAB Totals', modelLong(TOTALS) === 'NCAAB Totals', modelLong(TOTALS));
check('it is a game market', modelCategory(TOTALS) === 'game');
check('it is priced off the totals rows', gameMarketForModel(TOTALS) === 'totals',
  String(gameMarketForModel(TOTALS)));
check('a parlay treats it as a game total', marketClassForModel(TOTALS) === 'game_total',
  marketClassForModel(TOTALS));
// It decides each game once, the evening before (scripts/ncaab_total_card.py).
const timing = modelPageTiming(TOTALS);
check('its page says it decides the evening before', timing.title === 'Decided the evening before', timing.title);
check('its page names no Eastern clock time (22:00 UTC moves with DST)',
  ![timing.title, timing.body, timing.empty, timing.note].some((s) => /\d\s?(am|pm)\b|\d:\d\d/i.test(s)));
const posted = pickTimingInfo({
  pick_id: 1, model_id: TOTALS, sport: 'NCAAB', signal_type: 'BET', created_at: '2026-11-01T22:05:00Z',
  player_id: null, is_live: false,
} as unknown as Pick);
check('its Pick Detail note says posted once, not the first scoring run of the day',
  !!posted && posted.kind === 'posted' && !posted.note.includes('first scoring run'), posted?.note ?? 'null');
// The moneyline model (models/ncaab_moneyline_own_spread.py) has 'spread' in
// its id, because each book's moneyline is priced off that book's own spread,
// but every pick it writes is a MONEYLINE (2026-11-02).
const ML = 'ncaab_moneyline_own_spread';
check(`${ML} is filed under NCAAB`, sportOfModel(ML) === 'NCAAB');
check('its badge is ML and its name NCAAB Moneyline',
  modelShort(ML) === 'ML' && modelLong(ML) === 'NCAAB Moneyline', `${modelShort(ML)} / ${modelLong(ML)}`);
check('it is priced off the moneyline rows, not the spreads rows its id names',
  gameMarketForModel(ML) === 'h2h', String(gameMarketForModel(ML)));
check('a parlay treats it as a moneyline', marketClassForModel(ML) === 'game_ml', marketClassForModel(ML));
check('the spread model is still priced off the spreads rows',
  gameMarketForModel('ncaab_spread_market') === 'spreads', String(gameMarketForModel('ncaab_spread_market')));
const mlTiming = modelPageTiming(ML);
check('its page says it decides the morning of the game, against each book\'s own spread, at a price',
  mlTiming.title === 'Decided the morning of the game' && mlTiming.body.includes('moneyline')
    && mlTiming.body.includes('same book’s spread') && !mlTiming.body.includes('line and price'),
  mlTiming.body);
check('the spread model\'s page is unchanged',
  modelPageTiming('ncaab_spread_market').body.startsWith(
    'This model decides each game once, on the morning of game day, from the spread at each book we price.'));
check('its probability note says the chance comes from the bet book\'s own spread',
  modelProbabilityNote(ML).includes('spread at the book we bet'), modelProbabilityNote(ML));
check('its record note never claims the best price (the edge book is not always the best price)',
  !recordNoteFor(ML).includes('best price') && !recordNoteShortFor(ML).includes('best price'),
  `${recordNoteFor(ML)} | ${recordNoteShortFor(ML)}`);
check('no model claims the best price: every one says the price the model found',
  [ML, 'ncaab_spread_market', 'nba_total_luck'].every((m) =>
    recordNoteFor(m) === 'Model records and stats use the price the model found, not your book’s.'
      && recordNoteShortFor(m) === 'record kept at that price'),
  `${recordNoteFor('ncaab_spread_market')} | ${recordNoteShortFor('nba_total_luck')}`);
const mlPosted = pickTimingInfo({
  pick_id: 2, model_id: ML, sport: 'NCAAB', signal_type: 'BET', created_at: '2026-12-05T15:05:00Z',
  player_id: null, is_live: false,
} as unknown as Pick);
check('its Pick Detail note says posted once',
  !!mlPosted && mlPosted.kind === 'posted' && mlPosted.note.startsWith('Posted once'), mlPosted?.note ?? 'null');
// The opening-moneyline model (models/ncaab_moneyline_first_post.py, 2026-11-03)
// bets a book's moneyline the moment the book first posts it.
const FP = 'ncaab_moneyline_first_post';
check(`${FP} is filed under NCAAB`, sportOfModel(FP) === 'NCAAB');
check('its badge is ML and its name NCAAB Opening Moneyline',
  modelShort(FP) === 'ML' && modelLong(FP) === 'NCAAB Opening Moneyline', `${modelShort(FP)} / ${modelLong(FP)}`);
check('it is priced off the moneyline rows', gameMarketForModel(FP) === 'h2h', String(gameMarketForModel(FP)));
check('a parlay treats it as a moneyline', marketClassForModel(FP) === 'game_ml', marketClassForModel(FP));
const fpTiming = modelPageTiming(FP);
check('its page says it decides when the line opens, names the moving price, and prints no clock time',
  fpTiming.title === 'Decided when the line opens' && fpTiming.body.includes('first posts its moneyline')
    && fpTiming.body.includes('move within minutes')
    && ![fpTiming.title, fpTiming.body, fpTiming.empty, fpTiming.note].some((s) => /\d\s?(am|pm)\b|\d:\d\d/i.test(s)),
  fpTiming.body);
check('its probability note says the chance comes from the bet book\'s own spread when it opened',
  modelProbabilityNote(FP).includes('spread at the book we bet') && modelProbabilityNote(FP).includes('first posted'),
  modelProbabilityNote(FP));
const fpPosted = pickTimingInfo({
  pick_id: 3, model_id: FP, sport: 'NCAAB', signal_type: 'BET', created_at: '2026-12-04T23:41:00Z',
  player_id: null, is_live: false,
} as unknown as Pick);
check('its Pick Detail note says posted once',
  !!fpPosted && fpPosted.kind === 'posted' && fpPosted.note.startsWith('Posted once'), fpPosted?.note ?? 'null');
// The custom-model picker offers moneyline, spread and props slots only, so the
// totals model adds no NCAAB row there. The spread model
// (models/ncaab_spread_market.py) adds the Spread choice, as NCAAF's and the
// NFL's spread models do (2026-11-02), and the moneyline model
// (models/ncaab_moneyline_own_spread.py) the ML choice: its id has 'spread'
// in it, and it must land under ML, never under Spread. The opening-moneyline
// model (models/ncaab_moneyline_first_post.py) joins the same ML choice: one
// NCAAB moneyline rule, both moneyline models, one bet a game between them.
const ncaabRows = betTypePickerGroups().filter((g) => g.sport === 'NCAAB');
const ncaabChoice = (label: string) =>
  ncaabRows.length === 1 ? ncaabRows[0].choices.find((c) => c.label === label) : undefined;
check('the custom-model picker has one NCAAB row: ML (both moneyline models) and Spread (the spread model)',
  ncaabRows.length === 1 && ncaabRows[0].choices.length === 2
    && JSON.stringify([...(ncaabChoice('ML')?.modelIds ?? [])].sort())
      === JSON.stringify(['ncaab_moneyline_first_post', 'ncaab_moneyline_own_spread'])
    && JSON.stringify(ncaabChoice('Spread')?.modelIds) === JSON.stringify(['ncaab_spread_market']),
  JSON.stringify(ncaabRows));

// ── Stats: nothing to show yet, and nothing broken ───────────────────────────
check('NCAAB has no leaderboard stats', GROUP_ORDER.NCAAB.length === 0 && defaultStatFor(NCAAB) === null);
check('NCAAB has no hit-rate view', !supportsHitRate(NCAAB));
check('NCAAB has no Teams board', !supportsTeamBoard(NCAAB));
check('NCAAB draws no segment row', segmentsForSport(NCAAB).length < 2, segmentsForSport(NCAAB).join(','));
check('an NCAAB form strip reads PTS', teamScoreUnit('NCAAB') === 'PTS');

// ── When a game leaves the board ─────────────────────────────────────────────
const hoursAgo = (h: number) => new Date(Date.now() - h * 3_600_000).toISOString();
check('an NCAAB game 2h after tip is still on the board',
  !isGameOver({ sport: 'NCAAB', commence_time: hoursAgo(2), home_score: null, away_score: null }, 'NCAAB'));
check('an NCAAB game 3h after tip with no final has left the board',
  isGameOver({ sport: 'NCAAB', commence_time: hoursAgo(3.05), home_score: null, away_score: null }, 'NCAAB'));
check('an NCAAB final leaves the board at once',
  isGameOver({ sport: 'NCAAB', commence_time: hoursAgo(0.5), home_score: 71, away_score: 68 }, 'NCAAB'));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILED`);
if (failures > 0) process.exit(1);
