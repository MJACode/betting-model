/**
 * Standalone verification for the EUROLEAGUE sport wiring. Run with:
 *
 *   npx tsx scripts/verify_euroleague_ui.ts
 *
 * EUROLEAGUE joined the app on 2026-11-13 for its one model, the halftime
 * spread (`euroleague_live_spread_ht`, models/euroleague_live_ht.py): the
 * full-game spread, bet once a game during the halftime break. No pre-game
 * model, no player or team stats. Before this the app had no EUROLEAGUE chip,
 * dropped `sport: 'EUROLEAGUE'` from a push, and filed the model under MLB
 * (sportOfModel's default).
 */

import { SPORTS } from '../src/hooks/useSportFilter';
import { routeForPush, PUSH_ROUTE_VERSION } from '../src/lib/pushRoute';
import { MODEL_META, betTypeGroups, modelLong, modelPageTiming, modelShort, sportOfModel } from '../src/lib/modelMeta';
import { gameMarketForModel, marketClassForModel, pickTimingInfo, LIVE_PRICE_SLOT_ONLY } from '../src/lib/markets';
import type { Pick } from '../src/types';
import { GROUP_ORDER, statsForSport } from '../src/lib/statCatalog';
import { supportsTeamBoard } from '../src/lib/teamStatCatalog';
import { boardSegmentsFor, segmentsForSport } from '../src/lib/statSegments';
import { ALL_SPORTS } from '../src/lib/dailyResults';
import { hasLiveModel, liveEmptySubtitle, liveModelSportsSentence, sportDisplayName } from '../src/lib/liveSports';
import { sportSpokenName } from '../src/lib/loadState';
import { isGameOver } from '../src/lib/format';
import { ACTION_THRESHOLDS } from '../src/lib/thresholds.generated';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const EL = 'EUROLEAGUE' as const;
const MODEL = 'euroleague_live_spread_ht';

// ── The chip and the push ────────────────────────────────────────────────────
check('EUROLEAGUE is a sport chip, after every other sport', SPORTS[SPORTS.length - 1] === EL, SPORTS.join(','));
// Its bets are in-play, so the push it sends is live_signals (tracking/push_notifier
// leaves in-play picks out of new_bets): that push opens the EuroLeague Live board.
const route = routeForPush({ v: PUSH_ROUTE_VERSION, type: 'live_signals', sport: EL });
check('a EuroLeague live push opens the EuroLeague Live board, not dropped',
  JSON.stringify(route) === JSON.stringify({ kind: 'board', view: 'live', sport: EL }), JSON.stringify(route));
check('VoiceOver says EuroLeague, not ten capitals', sportSpokenName(EL) === 'EuroLeague');
check('a sentence says EuroLeague; every other code is its own name',
  sportDisplayName(EL) === 'EuroLeague' && sportDisplayName('NCAABW') === 'NCAABW');

// ── The model ────────────────────────────────────────────────────────────────
check('the model belongs to EUROLEAGUE, not the MLB default', sportOfModel(MODEL) === EL);
check('the model is named as mike named it', modelLong(MODEL) === 'EuroLeague Live Spreads'
  && MODEL_META[MODEL]?.longLabel === 'EuroLeague Live Spreads', modelLong(MODEL));
check('its badge is a live spread, cased like the other live badges', modelShort(MODEL) === 'LIVE Spread',
  modelShort(MODEL));
check('its price is looked up in the spreads rows', gameMarketForModel(MODEL) === 'spreads');
check('it is a game spread for the slip', marketClassForModel(MODEL) === 'game_spread');
check('its live price is the slot read only', LIVE_PRICE_SLOT_ONLY.has(MODEL));
check('its floor reached the app', ACTION_THRESHOLDS[MODEL]?.min_odds === -200);
const page = modelPageTiming(MODEL);
check('its page says it bets at halftime, on the full game', page.title === 'Bets at halftime'
  && page.body.includes('during its halftime break') && page.body.includes('full-game spread')
  && page.body.includes('not on the second half'), page.body);
// The four pre-game models (2026-11-14) are in the builder's EuroLeague group;
// the halftime model never is (live markets are excluded).
const elGroup = betTypeGroups().find((g) => g.sport === EL);
check('the custom-model builder offers the four EuroLeague pre-game models and not the live one',
  !!elGroup && elGroup.options.length === 4 && !elGroup.options.some((o) => o.id === MODEL),
  JSON.stringify(elGroup?.options.map((o) => o.id)));

// ── The Live board ───────────────────────────────────────────────────────────
check('EUROLEAGUE has an in-play model', hasLiveModel(EL));
check('the empty Live board says when it bets',
  liveEmptySubtitle(EL).includes('during its halftime break') && liveEmptySubtitle(EL).includes('full-game spread'),
  liveEmptySubtitle(EL));
const sentence = liveModelSportsSentence();
check('the in-play sentence names EuroLeague and still ends on the two college basketball codes',
  sentence === 'MLB, NBA, NFL, NCAAF, EuroLeague, NCAAB and NCAABW', sentence);

const mkPick = (over: Partial<Pick>): Pick => ({
  pick_id: 1, game_id: 'EUROLEAGUE_E2026_110', game_date: '2026-11-13', sport: EL, model_id: MODEL,
  signal_type: 'BET', pick_side: 'away', pick_label: 'BAR +5.5 (live)', scored_line: -5.5, dk_odds: -110,
  decision_odds: -110, decision_book: 'draftkings', line_book: null, created_at: '2026-11-13T20:12:45Z',
  player_id: null, is_live: true, inning_at_pick: 2, ...over,
} as unknown as Pick);
const t = pickTimingInfo(mkPick({}));
check('a EuroLeague live bet says halftime, not a quarter',
  !!t && t.kind === 'live' && t.label.includes('· halftime') && !t.label.includes('Q2'), t?.label ?? 'null');
check('its note says the bet is on the full-game spread and when the price was read',
  !!t && t.note.includes('on the full-game spread') && t.note.includes('read during the break')
  && !t.note.includes('Locked the moment this crossed'), t?.note ?? 'null');

// ── Stats: nothing stored, so nothing promised ──────────────────────────────
check('no EuroLeague stat group', GROUP_ORDER[EL].length === 0 && statsForSport(EL).length === 0);
check('no EuroLeague Teams board', !supportsTeamBoard(EL));
check('EuroLeague draws no segment row', segmentsForSport(EL).length < 2 && boardSegmentsFor(EL).length < 2);

// ── The recap and the board's clock ─────────────────────────────────────────
check('the daily recap carries EuroLeague last', ALL_SPORTS[ALL_SPORTS.length - 1] === EL, ALL_SPORTS.join(','));
const hoursAgo = (h: number) => new Date(Date.now() - h * 3_600_000).toISOString();
check('a EuroLeague game 2h after tip is still on the board',
  !isGameOver({ sport: EL, commence_time: hoursAgo(2), home_score: null, away_score: null }, EL));
check('a EuroLeague game 3.5h after tip has left the board',
  isGameOver({ sport: EL, commence_time: hoursAgo(3.5), home_score: null, away_score: null }, EL));

console.log(failures === 0 ? '\nALL CHECKS PASSED' : `\n${failures} CHECK(S) FAILED`);
if (failures > 0) process.exit(1);
