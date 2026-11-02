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
  MODEL_META, betTypePickerGroups, modelCategory, modelLong, modelPageTiming, modelShort, sportOfModel,
} from '../src/lib/modelMeta';
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
// The custom-model picker offers moneyline, spread and props slots only, so a
// totals model adds no NCAAB row there.
check('the custom-model picker has no NCAAB row for a totals model',
  !betTypePickerGroups().some((g) => g.sport === 'NCAAB'));

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
