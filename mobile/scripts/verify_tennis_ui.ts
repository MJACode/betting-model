/**
 * Standalone verification for the tennis sport wiring. Run with:
 *
 *   npx tsx scripts/verify_tennis_ui.ts
 *
 * ATP (men's tennis) and WTA (women's tennis) joined the app on 2026-11-14 so
 * the picks of `atp_moneyline_shop` and `wta_moneyline_shop` reach a board.
 * Before that the app had no chip for either, dropped `sport: 'ATP'` from a
 * push, filed both models under MLB (sportOfModel ends on `return 'MLB'`), and
 * printed a match as "Carlos Alcaraz @ Jannik Sinner".
 *
 * Match winner only, decided once 25 to 35 minutes before the listed start
 * (scripts/tennis_moneyline_card.py). No player or team stats, no in-play
 * model. Tennis prices are in tennis_odds_quotes, which the app does not read,
 * so a tennis card carries the deciding book's price and nothing else.
 */

import { SPORTS, type Sport } from '../src/hooks/useSportFilter';
import { routeForPush, PUSH_ROUTE_VERSION } from '../src/lib/pushRoute';
import {
  betTypeGroups, betTypePickerGroups, modelCategory, modelLong, modelPageTiming, modelShort, sportOfModel,
} from '../src/lib/modelMeta';
import {
  bookLabel, bookLabelShort, bookName, currentLineQuotes, gameMarketForModel, heroAmericanForPick, isBettableBook,
  marketClassForModel, pickTimingInfo, priceAgeFor, storedQuoteBook,
} from '../src/lib/markets';
import { myBooksView } from '../src/lib/myBooks';
import { passesActionFilter } from '../src/lib/thresholds';
import { priceCheckForItem } from '../src/lib/pickPriceCheck';
import { pickCtaFor } from '../src/lib/pickCta';
import { boardSeasonET, gameStatus, isGameOver, isVersusSport } from '../src/lib/format';
import { signalsContextLine, signalsTeamsSpeech } from '../src/lib/signalsCard';
import { matchupForLeg } from '../src/lib/parlay';
import { ALL_SPORTS, computeDailyResults } from '../src/lib/dailyResults';
import { selectableGames } from '../src/lib/gameFilter';
import { slateTeams } from '../src/lib/statsBoard';
import { GROUP_ORDER, defaultStatFor, statsForSport, supportsHitRate } from '../src/lib/statCatalog';
import { supportsTeamBoard, teamSeasonLabel } from '../src/lib/teamStatCatalog';
import { supportsPlayerDetail } from '../src/lib/playerLog';
import { boardSegmentsFor, segmentsForSport } from '../src/lib/statSegments';
import { hasLiveModel } from '../src/lib/liveSports';
import { sportChipState, sportSpokenName } from '../src/lib/loadState';
import type { EnrichedPick, GameRow, Pick } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const ATP = 'ATP' as Sport;
const WTA = 'WTA' as Sport;
const MODELS: Record<string, string> = { ATP: 'atp_moneyline_shop', WTA: 'wta_moneyline_shop' };

// ── The sports ───────────────────────────────────────────────────────────────
check('ATP and WTA are sport chips', SPORTS.includes(ATP) && SPORTS.includes(WTA), SPORTS.join(','));
check('ATP sits right after UFC, WTA right after ATP',
  SPORTS.indexOf(ATP) === SPORTS.indexOf('UFC' as Sport) + 1 && SPORTS.indexOf(WTA) === SPORTS.indexOf(ATP) + 1,
  SPORTS.join(','));
check('both are in the daily recap order, after UFC',
  ALL_SPORTS.indexOf('ATP') === ALL_SPORTS.indexOf('UFC') + 1 && ALL_SPORTS.indexOf('WTA') === ALL_SPORTS.indexOf('ATP') + 1,
  ALL_SPORTS.join(','));

// ── A push naming a tour opens that tour's board ─────────────────────────────
for (const sport of ['ATP', 'WTA']) {
  const route = routeForPush({ v: PUSH_ROUTE_VERSION, type: 'new_bets', sport });
  check(`a new-bets push for ${sport} opens the ${sport} Signals board`,
    route?.kind === 'board' && route.view === 'signals' && route.sport === sport, JSON.stringify(route));
}

// ── Each model is filed under its own tour, not under MLB ────────────────────
for (const [sport, id] of Object.entries(MODELS)) {
  check(`${id} is filed under ${sport}`, sportOfModel(id) === sport, sportOfModel(id));
  check(`${id} is named ${sport} Match Winner, badge ML`,
    modelLong(id) === `${sport} Match Winner` && modelShort(id) === 'ML', `${modelLong(id)} / ${modelShort(id)}`);
  check(`${id} is a game market priced off the moneyline rows`,
    modelCategory(id) === 'game' && gameMarketForModel(id) === 'h2h', String(gameMarketForModel(id)));
  check(`a parlay treats ${id} as independent, like a fight`, marketClassForModel(id) === 'other',
    marketClassForModel(id));
}
check('the WNBA and UFC ids are unchanged',
  sportOfModel('wnba_moneyline') === 'WNBA' && sportOfModel('ufc_open_moneyline') === 'UFC'
    && sportOfModel('mlb_moneyline') === 'MLB');
const groups = betTypeGroups();
for (const [sport, id] of Object.entries(MODELS)) {
  const g = groups.find((x) => x.sport === sport);
  check(`the custom-model catalog has a ${sport} group holding ${id} only`,
    !!g && g.options.length === 1 && g.options[0].id === id, JSON.stringify(g));
}
check('the custom-model groups run UFC, ATP, WTA',
  groups.findIndex((g) => g.sport === 'ATP') === groups.findIndex((g) => g.sport === 'UFC') + 1
    && groups.findIndex((g) => g.sport === 'WTA') === groups.findIndex((g) => g.sport === 'ATP') + 1,
  groups.map((g) => g.sport).join(','));
check('the MLB group holds no tennis model',
  !(groups.find((g) => g.sport === 'MLB')?.options ?? []).some((o) => o.id.startsWith('atp_') || o.id.startsWith('wta_')));
const picker = betTypePickerGroups();
const mlbMl = picker.find((g) => g.sport === 'MLB')?.choices.find((c) => c.slot === 'ml');
check('the MLB moneyline row in the custom-model picker is MLB only',
  !!mlbMl && !mlbMl.modelIds.some((m) => m.startsWith('atp_') || m.startsWith('wta_')), JSON.stringify(mlbMl?.modelIds));
for (const [sport, id] of Object.entries(MODELS)) {
  const row = picker.find((g) => g.sport === sport);
  check(`the custom-model picker has one ${sport} moneyline row`,
    !!row && row.choices.length === 1 && row.choices[0].slot === 'ml' && row.choices[0].modelIds.join() === id,
    JSON.stringify(row));
}
check('the model page says when it decides',
  modelPageTiming(MODELS.ATP).title === 'Decided about 30 minutes before the match', modelPageTiming(MODELS.ATP).title);

// ── A pick, as the card writes it ────────────────────────────────────────────
const NOW = Date.now();
const startAt = new Date(NOW + 30 * 60_000).toISOString();
const mkPick = (over: Partial<Pick> = {}): Pick => ({
  pick_id: 9, game_id: 'ATP_2026-11-14_carlos-alcaraz_jannik-sinner', game_date: '2026-11-14', sport: 'ATP',
  model_id: MODELS.ATP, signal_type: 'BET', pick_side: 'home', pick_label: 'Jannik Sinner ML',
  scored_line: null, dk_odds: -150, dk_implied_prob: 0.6, edge: 0.03,
  model_probability: 0.63, model_probability_cal: 0.63,
  decision_book: 'betrivers', decision_odds: -145, decision_implied_prob: 0.5918, decision_edge: 0.0382,
  best_book: 'betrivers', best_odds: -145, line_book: null, created_at: new Date(NOW).toISOString(),
  game_time: startAt, player_id: null, is_live: false, result: null, condition_status: null,
  downgrade_reason: null, ...over,
} as unknown as Pick);
const mkGame = (over: Partial<GameRow> = {}): GameRow => ({
  game_id: 'ATP_2026-11-14_carlos-alcaraz_jannik-sinner', sport: 'ATP', season: 2026, game_date: '2026-11-14',
  home_team: 'Jannik Sinner', away_team: 'Carlos Alcaraz', commence_time: startAt,
  home_score: null, away_score: null, ...over,
} as unknown as GameRow);
const pick = mkPick();
const game = mkGame();

check('a BET at -145 is a signal', passesActionFilter(pick));
check('a NONE row is not', !passesActionFilter(mkPick({ signal_type: 'NONE' })));
check('a BET shorter than the -500 floor is not',
  !passesActionFilter(mkPick({ decision_odds: -520, dk_odds: -520 })));
const timing = pickTimingInfo(pick);
check('its Pick Detail note says posted once, at the price shown, not the first scoring run',
  !!timing && timing.kind === 'posted'
    && timing.note === 'Posted once and never re-priced. This is when the bet posted, at the price shown.',
  timing?.note ?? 'null');

// No tennis price is in the app's odds views: the card shows the deciding
// book's price, and the only quote is that book's.
const age = priceAgeFor(pick, game, null);
const hero = heroAmericanForPick(pick, null, [], age);
check('the card shows the price it was decided at, at the book it was decided at',
  hero?.kind === 'decision' && hero.price === -145 && hero.book === 'betrivers', JSON.stringify(hero));
const quotes = currentLineQuotes(pick, [], hero, age);
check('the only quote is the deciding book\'s',
  quotes.length === 1 && quotes[0].bookmaker === 'betrivers' && quotes[0].isRecord, JSON.stringify(quotes));
check('the record book is the deciding book', storedQuoteBook(pick) === 'betrivers');
const mine = myBooksView({ quotes, recordBook: 'betrivers', myBooks: ['betrivers', 'draftkings'], modelProbability: 0.63 });
check('a member with the deciding book sees the pick as decided', mine.status === 'record', mine.status);
// The known limit: the app holds no other book's tennis price, so a member
// without the deciding book is told it is not at their books.
const notMine = myBooksView({ quotes, recordBook: 'betrivers', myBooks: ['draftkings', 'fanduel'], modelProbability: 0.63 });
check('a member without the deciding book sees "Not offered at your books" (no tennis prices in the app)',
  notMine.status === 'none', notMine.status);
const item = { pick, game, weather: null, latestOdds: null, bookRows: [] } as unknown as EnrichedPick;
check('the price check does not flag a pick with no reference row',
  !priceCheckForItem(item, null).flagged, JSON.stringify(priceCheckForItem(item, null)));
// The seven books the rule may decide at (models/tennis_moneyline_shop.py DECIDABLE).
const DECIDABLE = ['draftkings', 'fanduel', 'betmgm', 'williamhill_us', 'fanatics', 'betrivers', 'hardrockbet'];
check('every book the rule decides at is bettable and has a name and a label',
  DECIDABLE.every((b) => isBettableBook(b) && bookName(b) !== b && bookLabel(b).length <= 5 && bookLabelShort(b).length <= 3),
  DECIDABLE.map((b) => `${b}=${bookLabel(b)}/${bookName(b)}`).join(' '));

// ── "A vs B": two players, no home side ──────────────────────────────────────
check('UFC, ATP and WTA are versus sports, nothing else',
  isVersusSport('UFC') && isVersusSport('ATP') && isVersusSport('WTA') && !isVersusSport('NBA')
    && !isVersusSport('WNBA') && !isVersusSport(null) && !isVersusSport(undefined));
const ctx = signalsContextLine({ sport: 'ATP', away: 'Carlos Alcaraz', home: 'Jannik Sinner', timeLabel: '8:00 PM ET' });
check('the signals card reads "A vs B"', ctx === 'Carlos Alcaraz vs Jannik Sinner · ATP · 8:00 PM ET', ctx);
check('VoiceOver reads "versus"',
  signalsTeamsSpeech('WTA', 'Iga Swiatek', 'Coco Gauff') === 'Iga Swiatek versus Coco Gauff',
  String(signalsTeamsSpeech('WTA', 'Iga Swiatek', 'Coco Gauff')));
check('the betslip leg reads "A vs B"', matchupForLeg(game) === 'Carlos Alcaraz vs Jannik Sinner',
  String(matchupForLeg(game)));
check('a team sport still reads "@"',
  signalsContextLine({ sport: 'NBA', away: 'BOS', home: 'MIL', timeLabel: '' }) === 'BOS @ MIL · NBA'
    && signalsContextLine({ sport: 'UFC', away: 'A', home: 'B', timeLabel: '' }) === 'A vs B · UFC'
    && matchupForLeg({ ...game, sport: 'NBA', away_team: 'BOS', home_team: 'MIL' } as GameRow) === 'BOS @ MIL');
const recap = computeDailyResults('2026-11-14', [mkPick({ result: 'WIN', profit_flat: 68.97 })], [mkGame()]);
check('the daily recap reads "A vs B"', recap.games[0]?.matchup === 'Carlos Alcaraz vs Jannik Sinner',
  JSON.stringify(recap.games[0]?.matchup));
check('the board offers no Games filter for a match (two slots, not fixtures)',
  selectableGames([mkGame()], 'ATP', '2026-11-14').length === 0);
check('the slate is not narrowed by team for tennis',
  slateTeams('WTA', { keys: new Set(['Coco Gauff']) } as never, true) === null);

// ── The clock ────────────────────────────────────────────────────────────────
const at = (hoursAgo: number) => mkGame({ commence_time: new Date(NOW - hoursAgo * 3_600_000).toISOString() });
check('before the listed start: the start time', gameStatus(mkGame()).kind === 'pre');
check('2h after the listed start: LIVE', gameStatus(at(2)).kind === 'live');
check('7h after the listed start: no badge', gameStatus(at(7)).kind === 'ended');
check('before the listed start the card offers the hand-off',
  pickCtaFor(pick, mkGame(), null).handoff && !pickCtaFor(pick, mkGame(), null).startedLine);
check('after it, the card says the match has started and offers none (the board keeps it all day)',
  !pickCtaFor(pick, at(2), null).handoff && pickCtaFor(pick, at(2), null).startedLine
    && !pickCtaFor(pick, at(20), null).handoff);
check('a match with no final is never dropped on the clock',
  !isGameOver(at(20), 'ATP') && !isGameOver(at(20), 'WTA'));
// Settlement writes the sets won when it grades a bet (paper_tracker._settle_tennis_picks).
const graded = mkGame({ commence_time: new Date(NOW - 3 * 3_600_000).toISOString(), home_score: 2, away_score: 1 } as Partial<GameRow>);
const finalStatus = gameStatus(graded);
check('a graded match leaves the board and reads FINAL on its sets, away first like the matchup',
  isGameOver(graded, 'ATP') && finalStatus.kind === 'final'
    && finalStatus.awayScore === 1 && finalStatus.homeScore === 2, JSON.stringify(finalStatus));
check('a team sport still is', isGameOver({ ...at(20), sport: 'NBA' } as GameRow, 'NBA'));
check('a tennis season is the year of play',
  boardSeasonET('ATP') === Number(new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', year: 'numeric' }).format(new Date()))
    && teamSeasonLabel(ATP, 2026) === '2026');

// ── Stats: nothing for tennis ────────────────────────────────────────────────
for (const s of [ATP, WTA]) {
  check(`${s} has no stat catalog, so the Stats tab shows its empty state`,
    GROUP_ORDER[s].length === 0 && statsForSport(s).length === 0 && defaultStatFor(s) === null);
  check(`${s} has no Teams board, hit rate or player page`,
    !supportsTeamBoard(s) && !supportsHitRate(s) && !supportsPlayerDetail(s));
  check(`${s} draws no segment row`, segmentsForSport(s).length < 2 && boardSegmentsFor(s).length < 2);
  check(`${s} has no in-play model`, !hasLiveModel(s));
}

// ── VoiceOver ────────────────────────────────────────────────────────────────
check('VoiceOver names each tour in words, with the chip\'s code',
  sportSpokenName('ATP') === 'ATP men’s tennis' && sportSpokenName('WTA') === 'WTA women’s tennis');
const chip = sportChipState({ sport: 'WTA', active: false, available: new Set(['WTA']), count: 2, live: false });
check('the chip speaks the name and its count', chip.label.startsWith('WTA women’s tennis, 2 signals'), chip.label);

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILED`);
if (failures > 0) process.exit(1);
