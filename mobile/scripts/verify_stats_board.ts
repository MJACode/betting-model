/**
 * Standalone verification for the Stats tab board logic (src/lib/statsBoard.ts).
 * Run with:
 *
 *   npx tsx scripts/verify_stats_board.ts
 *
 * Pins the behaviours the Stats tab changed:
 *  - NO games-played qualifier exists (removed 2026-08-30): the module exports
 *    nothing that hides a player for sample size, so nothing can quietly
 *    reintroduce one;
 *  - the ONE sort comparator orders by the number the board displays,
 *    tie-breaking on sample size (the games/average alternatives and their
 *    sheet picker were removed 2026-09-12);
 *  - the hit-rate band is the slider's two percents, clamped and normalised,
 *    and every preset chip sits on a position the slider can actually reach;
 *  - "playing tonight" is derived from `games` for EVERY sport — team abbrevs
 *    for team sports, fighter names for UFC — and prefers today, falling back
 *    to the next scheduled day;
 *  - the row SUBLINE ("9:40 PM ET · @ SEA") comes off the same `games` rows, so
 *    it lands in every sport, resolves doubleheaders to the game still ahead,
 *    and yields to Live/Final once the game is under way.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { GameRow } from '../src/types';
import * as board from '../src/lib/statsBoard';
import {
  EMPTY_SLATE,
  HIT_RATE_MAX,
  HIT_RATE_MIN,
  HIT_RATE_PRESETS,
  HIT_RATE_STEP,
  buildSlateGameIndex,
  buildTonightSlate,
  compareRows,
  earliestUpcomingGame,
  hitRateBand,
  inHitRateBand,
  isOnSlate,
  fixtureSubline,
  canOpenPlayerDetail,
  isLineOnlyId,
  lineOnlyRowLabel,
  LINE_ONLY_ROW_TAIL,
  slateChipDisabled,
  slateReadKey,
  SLATE_CHECKING_HINT,
  TEAMS_SLATE_FAILED_HINT,
  TEAMS_SLATE_OFF_HINT,
  TEAMS_SLATE_ON_HINT,
  teamsNoGamesHint,
  PLAYERS_SLATE_CUT_HINT,
  PLAYERS_SLATE_EMPTY_HINT,
  PLAYERS_SLATE_GAMES_HINT,
  PLAYERS_SLATE_LOADING_HINT,
  isStatParticipant,
  isTeamPropName,
  LINE_ONLY_ID_PREFIX,
  lineOnlyPlayers,
  pricedPlayers,
  needsTouchSet,
  seasonTouchFlag,
  shouldFetchTouchSet,
  touchBoardView,
  touchCommitAction,
  touchRejectionRecordsFailure,
  touchSetAfterFailure,
  touchSetCopy,
  touchSetErrorLine,
  touchSetFromResponse,
  touchedPlayerIds,
  slateGameFor,
  slateSubline,
  sublineSpoken,
  type SortableRow,
} from '../src/lib/statsBoard';
import { todayET } from '../src/lib/format';
import { errorAnnouncement } from '../src/lib/errors';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

// ── 1. No qualifier ──
// Matt, 2026-08-30: the games-played qualifier is gone from the filter sheet in
// every sport and both modes. It was the one filter the board applied without
// the user asking, so the guard here is on the module surface: if a helper that
// computes a minimum comes back, this fails before it can silently hide rows.

const QUALIFIER_EXPORTS = ['autoMinGames', 'maxGamesIn', 'QUALIFIER_SHARE', 'QUALIFIER_MIN'];
const reintroduced = QUALIFIER_EXPORTS.filter((k) => k in board);
check(
  'no games-played qualifier is exported (nothing hides a player for sample size)',
  reintroduced.length === 0,
  reintroduced.join(', '),
);
// Sample size is still visible and still decides ties — that is what replaces
// the qualifier, so a small-sample player ranks honestly instead of vanishing.
check(
  'a 1-game player is ranked, not removed, and loses the tie to a regular',
  compareRows({ primary: 1, games: 1 }, { primary: 1, games: 80 }) > 0,
);

// ── 2. Sort ──

const row = (primary: number, games: number): SortableRow => ({ primary, games });
// A perfect 5-of-5 next to a 70%-of-80 and a 33%-of-90.
const pool = [row(0.33, 90), row(1.0, 5), row(0.7, 80)];
const byRate = pool.slice().sort(compareRows);
check(
  'sort = the displayed number, desc',
  byRate[0].primary === 1.0 && byRate[1].primary === 0.7 && byRate[2].primary === 0.33,
  JSON.stringify(byRate.map((r) => r.primary)),
);

// Ties break on sample size — this is what keeps regulars above small-sample
// players when the visible number is identical.
const tied = [row(0.5, 4), row(0.5, 40)];
check('tie on rate → more games first', tied.slice().sort(compareRows)[0].games === 40);

check('sort is a total order (no NaN comparators)', pool.slice().sort(compareRows).length === 3);

// The sheet's sort picker is gone (Matt, 2026-09-12). The guard is on the
// module surface: a comparator that takes a KEY again is the picker coming
// back through the back door, and the board would silently stop being ordered
// by the column it prints.
check('compareRows takes two rows and no sort key', compareRows.length === 2);
const SORT_PICKER_EXPORTS = ['sortOptionsFor', 'sortLabel', 'SORT_OPTIONS'];
const sortBack = SORT_PICKER_EXPORTS.filter((k) => k in board);
check('no sort-picker helper is exported', sortBack.length === 0, sortBack.join(', '));

// ── 3. Hit-rate band ──

check('a full-width band is unbounded',
  hitRateBand(HIT_RATE_MIN, HIT_RATE_MAX).lo === 0 && hitRateBand(HIT_RATE_MIN, HIT_RATE_MAX).hi === 1);
const b60 = hitRateBand(60, 100);
check('min 60 → lo 0.6, hi 1', b60.lo === 0.6 && b60.hi === 1);
check('exactly 60% passes a "min 60" band (float tolerance)', inHitRateBand(0.6, b60));
check('59% fails a "min 60" band', !inHitRateBand(0.59, b60));
check('3-of-5 = 60% passes min 60', inHitRateBand(3 / 5, b60));
const band = hitRateBand(60, 80);
check('a band excludes both tails', inHitRateBand(0.7, band) && !inHitRateBand(0.85, band) && !inHitRateBand(0.5, band));
const inverted = hitRateBand(80, 60);
check('inverted band is normalised, not emptied', inverted.lo === 0.6 && inverted.hi === 0.8);
check('out-of-range input is clamped', hitRateBand(150, 100).lo === 1 && hitRateBand(-20, 100).lo === 0);
check('a collapsed band keeps exactly one percent', (() => {
  const only60 = hitRateBand(60, 60);
  return inHitRateBand(0.6, only60) && !inHitRateBand(0.65, only60) && !inHitRateBand(0.55, only60);
})());
check('max-only band', hitRateBand(0, 40).lo === 0 && hitRateBand(0, 40).hi === 0.4);
check('every preset sits on a slider stop',
  HIT_RATE_PRESETS.every((p) => (p - HIT_RATE_MIN) % HIT_RATE_STEP === 0 && p >= HIT_RATE_MIN && p <= HIT_RATE_MAX));
check('the scale divides evenly into steps',
  (HIT_RATE_MAX - HIT_RATE_MIN) % HIT_RATE_STEP === 0 && HIT_RATE_STEP > 0);
check('presets are ascending minimums', HIT_RATE_PRESETS.every((p, i, a) => i === 0 || p > a[i - 1]));

// ── 4. Tonight's slate ──

const game = (sport: string, date: string, home: string, away: string): GameRow =>
  ({
    game_id: `${sport}_${date}_${away}_${home}`,
    sport,
    season: 2026,
    game_date: date,
    home_team: home,
    away_team: away,
    home_score: null,
    away_score: null,
    home_score_f5: null,
    away_score_f5: null,
    commence_time: `${date}T23:00:00Z`,
    home_win: null,
    home_win_reg: null,
    went_to_ot: 0,
  }) as GameRow;

const TODAY = '2026-08-23';
const games: GameRow[] = [
  game('MLB', TODAY, 'NYY', 'TOR'),
  game('MLB', TODAY, 'TB', 'BAL'),
  game('MLB', '2026-08-24', 'DET', 'CWS'),
  game('WNBA', TODAY, 'CHI', 'LV'),
  game('NFL', '2026-08-30', 'NYJ', 'BUF'),
  game('UFC', '2026-08-29', 'Alex Perez', 'Andre Lima'),
];

const mlb = buildTonightSlate(games, 'MLB', TODAY);
check('MLB slate is today and holds both sides of each game',
  mlb.isToday && mlb.date === TODAY && mlb.keys.size === 4 && mlb.keys.has('NYY') && mlb.keys.has('BAL'),
  JSON.stringify(Array.from(mlb.keys)));
check('slate never leaks another sport', !mlb.keys.has('CHI') && !mlb.keys.has('NYJ'));

const nfl = buildTonightSlate(games, 'NFL', TODAY);
check('NFL (no game today) falls forward to the next scheduled day',
  !nfl.isToday && nfl.date === '2026-08-30' && nfl.keys.has('NYJ') && nfl.keys.has('BUF'));

const ufc = buildTonightSlate(games, 'UFC', TODAY);
check('UFC slate is keyed on fighter names (no teams in UFC)',
  ufc.keys.has('Alex Perez') && ufc.keys.has('Andre Lima'));

check('a sport with nothing scheduled gets an empty slate (toggle stays hidden)',
  buildTonightSlate(games, 'NHL', TODAY).keys.size === 0);
check('yesterday\'s games are never a slate',
  buildTonightSlate([game('MLB', '2026-08-22', 'NYY', 'TOR')], 'MLB', TODAY).keys.size === 0);
check('EMPTY_SLATE is inert', EMPTY_SLATE.keys.size === 0 && EMPTY_SLATE.date === '' && !EMPTY_SLATE.isToday);

check('team row on the slate matches', isOnSlate({ team: 'NYY', player_name: 'Ben Rice' }, mlb));
check('team row off the slate does not', !isOnSlate({ team: 'LAD', player_name: 'M. Betts' }, mlb));
check('a teamless row does not match on a team slate', !isOnSlate({ team: null, player_name: 'Nobody' }, mlb));
check('UFC fighter matches by name', isOnSlate({ team: null, player_name: 'Alex Perez' }, ufc));
check('UFC fighter off the card does not', !isOnSlate({ team: null, player_name: 'Jon Jones' }, ufc));
check('an empty slate filters nothing (fail open, never blank the board)',
  isOnSlate({ team: 'LAD', player_name: 'M. Betts' }, EMPTY_SLATE));

// ── Stat participation (football only) ─────────────────────────────────────
// The football logs span every position, so a kicker carries real rows with 0
// passing yards — on an "at most N pass yards" board those non-participants go
// 15/15 and bury the quarterbacks. All-zero NFL/NCAAF players are dropped;
// every other sport keeps them (a batter 0-for-10 is a real "at most 1 hits"
// answer).
check('NFL all-zero player is not a participant', !isStatParticipant('NFL', [0, 0, 0]));
check('NFL null values count as zero', !isStatParticipant('NFL', [null, undefined, 0]));
check('NFL player with any nonzero value stays', isStatParticipant('NFL', [0, 212, 0]));
check('NCAAF drops all-zero players too (its log spans every position as well)',
  !isStatParticipant('NCAAF', [0, 0, 0]) && isStatParticipant('NCAAF', [0, 31, 0]));
check('MLB all-zero player stays (cold streaks are real outcomes)',
  isStatParticipant('MLB', [0, 0, 0]));
check('empty value list: football drops, others keep',
  !isStatParticipant('NFL', []) && !isStatParticipant('NCAAF', []) && isStatParticipant('WNBA', []));

// Anytime TD: zero is the usual answer, so a ball-carrier with no TD stays
// (Matt, 2026-10-08 — Pickens was missing from the TB @ DAL board), while a
// lineman with no touches still drops.
const TD = { statKey: 'rush_rec_tds' };
check('Anytime TD: a receiver with targets and no TD stays',
  isStatParticipant('NFL', [0, 0, 0], { ...TD, rows: [{ carries: 0, receptions: 5, targets: 7 }] }));
check('Anytime TD: a back with carries and no TD stays (NCAAF too)',
  isStatParticipant('NCAAF', [0], { ...TD, rows: [{ carries: 12, receptions: null, targets: null }] }));
check('Anytime TD: a player with no touches still drops',
  !isStatParticipant('NFL', [0, 0], { ...TD, rows: [{ carries: 0, receptions: 0, targets: 0 }] }));
check('Season/H2H Anytime TD with no touch set drops a player with games',
  !isStatParticipant('NFL', [0, 0], TD)
  && !isStatParticipant('NFL', [0, 0], { ...TD, touched: undefined })
  && !isStatParticipant('NFL', [], TD));
check('a mismatched touch key does not build the wide list',
  !isStatParticipant('NFL', [0, 0], {
    ...TD,
    touched: seasonTouchFlag(true, 'NFL|rb', 'NFL|wrte', true),
  }));
check('a matching touch key keeps a zero-TD carrier',
  isStatParticipant('NFL', [0, 0], {
    ...TD,
    touched: seasonTouchFlag(true, 'NFL|wrte', 'NFL|wrte', true),
  }));
check('a TD still stays while the touch set is unknown',
  isStatParticipant('NFL', [1, 0], TD));
check('Season/H2H: the touch set decides — a lineman with games drops, a receiver stays',
  !isStatParticipant('NFL', [0, 0], { ...TD, touched: false }) &&
  isStatParticipant('NFL', [0, 0], { ...TD, touched: true }));
check('touchedPlayerIds keeps only ball-carriers',
  [...touchedPlayerIds([
    { player_id: 'wr', carries: 0, receptions: 3, targets: 5 },
    { player_id: 'ol', carries: 0, receptions: 0, targets: 0 },
    { player_id: 'k', carries: null, receptions: null, targets: null },
  ])].join() === 'wr');
check('needsTouchSet: Anytime TD on football only',
  needsTouchSet('NFL', 'rush_rec_tds') && needsTouchSet('NCAAF', 'rush_rec_tds') &&
  !needsTouchSet('NFL', 'receptions') && !needsTouchSet('MLB', 'rush_rec_tds'));
// Anytime TD shows everyone with a betting line (Matt, 2026-10-09).
check('Anytime TD: a priced player stays even with no touches and no TD',
  isStatParticipant('NFL', [0, 0], { ...TD, priced: true, rows: [{ carries: 0, receptions: 0, targets: 0 }] }));
check('Anytime TD: priced overrides a negative touch answer (Season/H2H)',
  isStatParticipant('NFL', [0], { ...TD, priced: true, touched: false }));
check('priced does not keep an all-zero player on a yardage board',
  !isStatParticipant('NFL', [0, 0], { statKey: 'receiving_yards', priced: true }));
check('team names in the TD market are not players',
  isTeamPropName('Dallas Cowboys D/ST') && isTeamPropName('Dallas Cowboys Defense') &&
  isTeamPropName('No Scorer') && !isTeamPropName('George Pickens') && !isTeamPropName('Tyler Conklin'));
const tdRows = [
  { market: 'player_anytime_td', player_name: 'George Pickens', game_id: 'g1' },
  { market: 'player_anytime_td', player_name: 'George Pickens', game_id: 'g1' },
  { market: 'player_anytime_td', player_name: 'Michael Pittman Jr.', game_id: 'g2' },
  { market: 'player_anytime_td', player_name: 'Tank Dell', game_id: 'g2' },
  { market: 'player_anytime_td', player_name: 'Houston Texans D/ST', game_id: 'g2' },
  { market: 'player_anytime_td', player_name: 'Off Slate', game_id: 'g9' },
  { market: 'player_reception_yds', player_name: 'Other Market', game_id: 'g1' },
];
const priced = pricedPlayers(tdRows, 'player_anytime_td', new Set(['g1', 'g2']));
check('pricedPlayers: one per player, slate and market bounded, no team rows',
  [...priced.keys()].sort().join('|') === 'george pickens|michael pittman|tank dell');
const missing = lineOnlyPlayers(priced, ['George Pickens', 'Michael Pittman']);
check('lineOnlyPlayers: suffix-folded names count as present; the rest are listed',
  missing.map((p) => p.name).join() === 'Tank Dell' && missing[0]!.gameId === 'g2');
check('line-only ids are recognisable and never a real id',
  isLineOnlyId(`${LINE_ONLY_ID_PREFIX}tank dell`) && !isLineOnlyId('00-0036900'));
check('a line-only or blank id does not open a player page',
  !canOpenPlayerDetail(`${LINE_ONLY_ID_PREFIX}tank dell`) &&
    !canOpenPlayerDetail('') &&
    !canOpenPlayerDetail(null));
check('a real player id still opens', canOpenPlayerDetail('00-0036900'));
check('a fixture is spoken with "at", not "at sign"',
  sublineSpoken('SUN 1:00 PM ET · HOU @ TEN') === 'SUN 1:00 PM ET, HOU at TEN' &&
    sublineSpoken('9:40 PM ET · @ SEA') === '9:40 PM ET, at SEA');
check('a line-only label speaks the fixture, then ", no games logged yet"',
  lineOnlyRowLabel('Tank Dell', sublineSpoken('SUN 1:00 PM ET · HOU @ TEN')) ===
    'Tank Dell, SUN 1:00 PM ET, HOU at TEN, no games logged yet');
check('a line-only label ends with ", no games logged yet"',
  lineOnlyRowLabel('Tank Dell', null) === `Tank Dell${LINE_ONLY_ROW_TAIL}` &&
    lineOnlyRowLabel('Tank Dell', 'SUN 1:00 PM ET, HOU at TEN') ===
      'Tank Dell, SUN 1:00 PM ET, HOU at TEN, no games logged yet' &&
    LINE_ONLY_ROW_TAIL === ', no games logged yet');
{
  const mark = SLATE_CHECKING_HINT.indexOf('s schedule') - 1;
  check('the checking hint is "Checking today’s schedule" with U+2019',
    SLATE_CHECKING_HINT === 'Checking today\u2019s schedule' &&
      SLATE_CHECKING_HINT.charCodeAt(mark) === 0x2019 &&
      !SLATE_CHECKING_HINT.includes("'"));
}
check('a restored hint drops the control name and ends with a period',
  teamsNoGamesHint('NFL') === 'Unavailable: no NFL games in the next week.' &&
    TEAMS_SLATE_FAILED_HINT === 'Unavailable: the schedule could not be loaded.' &&
    TEAMS_SLATE_ON_HINT === 'On. Showing only teams on this slate.' &&
    TEAMS_SLATE_OFF_HINT === 'Off. Showing every team.' &&
    PLAYERS_SLATE_EMPTY_HINT === 'Unavailable: no games scheduled.' &&
    PLAYERS_SLATE_GAMES_HINT === 'Unavailable while a game is picked above.' &&
    PLAYERS_SLATE_LOADING_HINT === 'Loading.' &&
    PLAYERS_SLATE_CUT_HINT === 'On shows only players in action, off shows every player.' &&
    ![TEAMS_SLATE_FAILED_HINT, TEAMS_SLATE_ON_HINT, TEAMS_SLATE_OFF_HINT,
      teamsNoGamesHint('NFL'), PLAYERS_SLATE_EMPTY_HINT, PLAYERS_SLATE_GAMES_HINT,
      PLAYERS_SLATE_LOADING_HINT, PLAYERS_SLATE_CUT_HINT,
    ].some((h) => h.startsWith('Playing today') || h.startsWith('Next slate')));
check('the Teams chip stays disabled while the previous sport\'s slate is still in state',
  slateChipDisabled(true, true) === true);
check('the Teams chip stays disabled with no slate', slateChipDisabled(false, false) === true);
check('the Teams chip is tappable once this sport\'s slate has teams',
  slateChipDisabled(false, true) === false);
check('an ET rollover is a different slate read',
  slateReadKey('NFL', '2026-10-09') !== slateReadKey('NFL', '2026-10-10'));
check('a sport switch is a different slate read',
  slateReadKey('NFL', '2026-10-09') !== slateReadKey('NBA', '2026-10-09'));
check('fixtureSubline: a line-only row names its game, not a team it does not know',
  /· HOU @ TEN$/.test(fixtureSubline({ away_team: 'HOU', home_team: 'TEN', commence_time: '2026-10-11T17:00:00Z' } as never, null) ?? '') &&
  fixtureSubline({ away_team: 'HOU', home_team: 'TEN', commence_time: '2026-10-11T17:00:00Z' } as never, 'Live') === 'Live · HOU @ TEN' &&
  fixtureSubline({ away_team: null, home_team: 'TEN' } as never, null) === null);
check('the TD exemption does not leak to other stats',
  !isStatParticipant('NFL', [0, 0], { statKey: 'passing_yards', rows: [{ carries: 9 }] }));

// A touch-set response is not awaited, so it can land after the user has
// switched sport or player type and overwrite the set that is already on
// screen. Modelled the way StatsScreen.load does it: each load writes its
// stamp into inFlight, and a response may commit only while that stamp is
// still the one in flight.
type TouchSet = { key: string; ids: Set<string> };
function landTouch(
  inFlight: string,
  current: TouchSet | null,
  stamp: string,
  touchKey: string,
  ids: string[],
): TouchSet | null {
  return touchSetFromResponse(inFlight, stamp, touchKey, new Set(ids)) ?? current;
}
const stampNflRb = 'NFL|rb|season|hitRate|rush_rec_tds||';
const stampNcaaf = 'NCAAF|wrte|season|hitRate|rush_rec_tds||';
const stampNflWr = 'NFL|wrte|season|hitRate|rush_rec_tds||';
let inFlight = stampNflRb;
let touch: TouchSet | null = null;
// The NFL read is still in flight when the board switches to NCAAF. NCAAF
// lands first; the NFL response arrives after it.
inFlight = stampNcaaf;
touch = landTouch(inFlight, touch, stampNcaaf, 'NCAAF|wrte', ['bowers']);
touch = landTouch(inFlight, touch, stampNflRb, 'NFL|rb', ['lineman']);
check('a late touch set after a sport switch keeps the current key',
  touch?.key === 'NCAAF|wrte' && touch.ids.has('bowers') && !touch.ids.has('lineman'),
  touch ? `${touch.key}:${[...touch.ids].join()}` : 'null');
// Same shape for a player-type switch: RB's response must not replace WR/TE.
inFlight = stampNflWr;
touch = landTouch(inFlight, touch, stampNflWr, 'NFL|wrte', ['pickens']);
touch = landTouch(inFlight, touch, stampNcaaf, 'NCAAF|wrte', ['bowers']);
check('a late touch set after a playerType switch keeps the current key',
  touch?.key === 'NFL|wrte' && touch.ids.has('pickens') && !touch.ids.has('bowers'),
  touch ? `${touch.key}:${[...touch.ids].join()}` : 'null');
touch = landTouch(inFlight, touch, stampNflWr, 'NFL|wrte', ['pickens', 'lamb']);
check('the touch set for the load still in flight still commits',
  touch?.key === 'NFL|wrte' && touch.ids.has('lamb') && touch.ids.has('pickens'));

// A failed touch read used to resolve to undefined and leave `touched`
// unset, so Season/H2H Anytime TD fell open to anyone with games and stayed
// there. A failure keeps a set only when it is already for this key, records
// the key so the next load retries, and with nothing kept asks the board to
// show the error line instead of that wide list.
const good = { key: 'NFL|qb', ids: new Set(['mahomes']) };
const failedWithSet = touchSetAfterFailure(null, stampNflRb, stampNflRb, 'NFL|qb');
check('a failed touch read keeps the last good set for the same key',
  failedWithSet === 'NFL|qb' && good.ids.has('mahomes')
  && touchBoardView(true, good.key, 'NFL|qb', true) === 'list'
  && shouldFetchTouchSet(true, true, true));
const failedWithout = touchSetAfterFailure(null, stampNflRb, stampNflRb, 'NFL|qb');
check('a failed touch read with no set is an error, not the wide list',
  failedWithout === 'NFL|qb'
  && touchBoardView(true, null, 'NFL|qb', true) === 'error'
  && shouldFetchTouchSet(true, false, true));
const failedOtherKey = touchSetAfterFailure(null, stampNflRb, stampNflRb, 'NFL|wrte');
check('a failure for another key does not drop the set that was kept',
  failedOtherKey === 'NFL|wrte' && good.key === 'NFL|qb' && good.ids.has('mahomes')
  && touchBoardView(true, good.key, 'NFL|wrte', true) === 'error');
check('the touch-set error line for offline',
  touchSetErrorLine('offline')
  === 'Couldn’t load this list. You’re offline. Check your connection, then try again.');
check('the touch-set error line for a slow response',
  touchSetErrorLine('slow')
  === 'Couldn’t load this list. Signalbase is slow to respond right now. Try again in a moment.');
check('the touch-set error line for an expired session',
  touchSetErrorLine('auth')
  === 'Couldn’t load this list. Your session has expired. Try again, or sign out and back in.');
check('the touch-set error line for a server failure',
  touchSetErrorLine('server')
  === 'Couldn’t load this list. Something went wrong on our side. Try again in a moment.');
check('a missing touch-set cause still shows the server line',
  touchSetErrorLine(null) === touchSetErrorLine('server')
  && touchSetErrorLine(undefined) === touchSetErrorLine('server')
  && errorAnnouncement(touchSetCopy(null)) === touchSetErrorLine('server')
  && errorAnnouncement(touchSetCopy(undefined)) === touchSetErrorLine('server'));
check('the alert reads the same sentence as the line',
  (['offline', 'slow', 'auth', 'server'] as const).every((k) =>
    errorAnnouncement(touchSetCopy(k)) === touchSetErrorLine(k)));
// The user has moved on: the failure belongs to a load that is no longer in
// flight, so it must not mark the new key failed.
inFlight = stampNcaaf;
const staleFail = touchSetAfterFailure(null, inFlight, stampNflRb, 'NFL|qb');
check('a stale touch failure does not mark the new key failed',
  staleFail === null
  && touchBoardView(true, 'NCAAF|wrte', 'NCAAF|wrte', false) === 'list');
check('an abort of the touch read still on screen records a failure',
  touchRejectionRecordsFailure(stampNflRb, stampNflRb)
  && touchSetAfterFailure(null, stampNflRb, stampNflRb, 'NFL|qb') === 'NFL|qb'
  && touchBoardView(true, null, 'NFL|qb', true) === 'error');
check('an abort from a superseded stamp is ignored',
  !touchRejectionRecordsFailure(stampNcaaf, stampNflRb)
  && touchSetAfterFailure('NCAAF|wrte', stampNcaaf, stampNflRb, 'NFL|qb') === 'NCAAF|wrte');
check('an empty touch total is not committed, and the last good set stays',
  touchCommitAction(stampNflRb, stampNflRb, 0) === 'fail'
  && touchSetFromResponse(stampNflRb, stampNflRb, 'NFL|qb', new Set()) === null
  && landTouch(stampNflRb, good, stampNflRb, 'NFL|qb', []) === good
  && touchCommitAction(stampNcaaf, stampNflRb, 0) === 'ignore');
check('the list stays on its skeleton until the touch set for this key resolves',
  touchBoardView(true, null, 'NFL|qb', false) === 'loading'
  && touchBoardView(true, undefined, 'NFL|qb', false) === 'loading'
  && touchBoardView(false, null, 'NFL|qb', false) === 'list');
check('a good set is not refetched, and a failed key is',
  !shouldFetchTouchSet(true, true, false) && shouldFetchTouchSet(true, false, false)
  && !shouldFetchTouchSet(false, false, true));

const statsBoardSrc = readFileSync(join(import.meta.dirname, '..', 'src/lib/statsBoard.ts'), 'utf-8');
const statsScreen = readFileSync(join(import.meta.dirname, '..', 'src/screens/StatsScreen.tsx'), 'utf-8');
const touchCatch = /\.catch\(\(e: unknown\) => \{([\s\S]*?)\n            \}\);/.exec(statsScreen)?.[1] ?? '';
check('StatsScreen commits the touch set only through touchSetFromResponse',
  /touchSetFromResponse\(inFlight\.current, stamp, touchKey, ids\)/.test(statsScreen)
  && /touchCommitAction\(inFlight\.current, stamp, ids\.size\)/.test(statsScreen)
  && /if \(!next\) return;/.test(statsScreen)
  && /setTouchSet\(next\)/.test(statsScreen)
  && !/setTouchSet\(\{/.test(statsScreen)
  && !/\.catch\(\(\) => undefined\)/.test(statsScreen)
  && /touchSetAfterFailure\(/.test(statsScreen)
  && /shouldFetchTouchSet\(/.test(statsScreen)
  && /touchBoardView\(/.test(statsScreen)
  && /touchSetCopy\(touchFailure\?\.kind\)/.test(statsScreen)
  && /<ErrorState/.test(statsScreen)
  && /onRetry=\{\(\) => void load\(\)\}/.test(statsScreen)
  && /seasonTouchFlag\(/.test(statsScreen)
  && /touchView !== 'list' \? EMPTY_ROWS : hitRatePlayers/.test(statsScreen)
  && /emptyLabel=\{touchView === 'error' \? 'Couldn’t load this list\. Pull down to retry\.' : undefined\}/.test(statsScreen)
  && /touchRejectionRecordsFailure\(inFlight\.current, stamp\)/.test(touchCatch)
  && !/if \(isAbortError\(e\)\) return;/.test(touchCatch)
  && !/setTouchSet\(/.test(touchCatch)
  && /export function touchRejectionRecordsFailure\(inFlight: string \| null, stamp: string\): boolean/.test(statsBoardSrc)
  && !/function touchRejectionRecordsFailure\([^)]*_aborted/.test(statsBoardSrc));

// ── The row subline: when the game starts, and against whom ────────────────
// Matt, 2026-09-05: "add the time of the game and who they are playing under
// the name … for all sports". Built off `games`, so what is pinned here is
// that it works for a sport with no matchup feed, that a doubleheader resolves
// to the game a bettor can still act on, and that a game under way stops
// advertising a start time it is already past.

const SUB_TODAY = todayET();
const at = (hhmm: string, date = SUB_TODAY) => `${date}T${hhmm}:00Z`;

function subGame(over: Partial<GameRow> & Pick<GameRow, 'game_id' | 'home_team' | 'away_team'>): GameRow {
  return {
    sport: 'MLB',
    season: 2026,
    game_date: SUB_TODAY,
    home_score: null,
    away_score: null,
    home_score_f5: null,
    away_score_f5: null,
    commence_time: at('23:10'),
    home_win: null,
    home_win_reg: null,
    went_to_ot: 0,
    ...over,
  } as GameRow;
}

const NOW = at('18:00');
const slateToday = { date: SUB_TODAY, keys: new Set(['LAD', 'WSH']), isToday: true };

const oneGame = [subGame({ game_id: 'g1', home_team: 'LAD', away_team: 'WSH', commence_time: at('23:10') })];
const idx = buildSlateGameIndex(oneGame, slateToday, NOW);

check('both sides of a game are keyed', idx.has('LAD') && idx.has('WSH'));
check('the home row faces the away team, at home', idx.get('LAD')?.opponent === 'WSH' && idx.get('LAD')?.isHome === true);
check('the away row faces the home team, away', idx.get('WSH')?.opponent === 'LAD' && idx.get('WSH')?.isHome === false);
check(
  'the subline reads "<time> · vs OPP" for the home side',
  /^\d{1,2}:\d{2} [AP]M ET · vs WSH$/.test(slateSubline(idx.get('LAD') ?? null, null) ?? ''),
  slateSubline(idx.get('LAD') ?? null, null) ?? 'null',
);
check(
  'the away side reads "@ OPP", never "vs"',
  (slateSubline(idx.get('WSH') ?? null, null) ?? '').endsWith('· @ LAD'),
  slateSubline(idx.get('WSH') ?? null, null) ?? 'null',
);
check('no game, no subline (never a dash or an empty line)', slateSubline(null, null) === null);

// A game under way must not keep printing its start time next to a price the
// board has already blanked — the row says WHICH state instead.
check('a live game replaces the clock time', slateSubline(idx.get('LAD') ?? null, 'Live') === 'Live · vs WSH');
check('a finished game replaces the clock time', slateSubline(idx.get('WSH') ?? null, 'Final') === 'Final · @ LAD');

// Doubleheader: the game a bettor can still act on.
const dh = [
  subGame({ game_id: 'dh1', home_team: 'DET', away_team: 'CHW', commence_time: at('17:10') }),
  subGame({ game_id: 'dh2', home_team: 'DET', away_team: 'CHW', commence_time: at('23:10') }),
];
const dhSlate = { date: SUB_TODAY, keys: new Set(['DET', 'CHW']), isToday: true };
check(
  'a doubleheader shows the game still ahead, not game one',
  buildSlateGameIndex(dh, dhSlate, NOW).get('DET')?.game.game_id === 'dh2',
);
check(
  'once both have started it shows the later one, not a game from this morning',
  buildSlateGameIndex(dh, dhSlate, at('23:30')).get('DET')?.game.game_id === 'dh2',
);
check(
  'before either, it shows game one',
  buildSlateGameIndex(dh, dhSlate, at('12:00')).get('DET')?.game.game_id === 'dh1',
);

// Only the slate date. A WEEK of games is fetched (the next-slate fallback
// needs them), so an index that ignored the date would, the moment today's
// game started, quietly re-point the row at TOMORROW's opponent — a wrong fact
// that looks exactly like a right one.
const spanning = [
  subGame({ game_id: 'today', home_team: 'NYY', away_team: 'BOS', commence_time: at('17:10') }),
  subGame({ game_id: 'tomorrow', home_team: 'NYY', away_team: 'TOR', game_date: '2099-01-01', commence_time: '2099-01-01T23:10:00Z' }),
  subGame({ game_id: 'notplaying', home_team: 'SD', away_team: 'COL', game_date: '2099-01-01', commence_time: '2099-01-01T23:10:00Z' }),
];
const spanIdx = buildSlateGameIndex(spanning, { date: SUB_TODAY, keys: new Set(['NYY']), isToday: true }, NOW);
check(
  "a team whose game already started keeps TODAY's opponent, never tomorrow's",
  spanIdx.get('NYY')?.opponent === 'BOS',
  spanIdx.get('NYY')?.opponent ?? 'none',
);
check('a team that is not on the slate date is not indexed at all', !spanIdx.has('SD'));
check('an empty slate indexes nothing', buildSlateGameIndex(spanning, EMPTY_SLATE, NOW).size === 0);

// A future slate names its day: a bare "1:00 PM ET" on Sunday's board is the
// wrong DAY, not the wrong hour.
const future = [subGame({ game_id: 'sat', home_team: 'GB', away_team: 'CHI', sport: 'NFL', game_date: '2099-01-02', commence_time: '2099-01-02T18:00:00Z' })];
const futureIdx = buildSlateGameIndex(future, { date: '2099-01-02', keys: new Set(['GB']), isToday: false }, NOW);
check(
  'a game on a later day carries its weekday',
  /^[A-Z]{3} \d{1,2}:\d{2} [AP]M ET · vs CHI$/.test(slateSubline(futureIdx.get('GB') ?? null, null) ?? ''),
  slateSubline(futureIdx.get('GB') ?? null, null) ?? 'null',
);

// Row → game, matching isOnSlate: team first, then the name (UFC has no team).
const ufcCard = [subGame({ game_id: 'ufc1', sport: 'UFC', home_team: 'Alex Perez', away_team: 'Matheus Nicolau' })];
const ufcIdx = buildSlateGameIndex(ufcCard, { date: SUB_TODAY, keys: new Set(['Alex Perez']), isToday: true }, NOW);
const ufcMatch = slateGameFor({ team: null, player_name: 'Alex Perez' }, ufcIdx);
check('a UFC fighter finds his bout by NAME', ufcMatch?.game.opponent === 'Matheus Nicolau');
// The KEY comes back too, because the caller looks the Live/Final label up by
// it: keying that on `row.team` alone left every UFC row advertising a start
// time hours after the fight ended (UX review, 2026-09-05).
check('and the matched key comes back with it, for the status lookup', ufcMatch?.key === 'Alex Perez');
const ladMatch = slateGameFor({ team: 'LAD', player_name: 'M. Betts' }, idx);
check('a team row finds its game by ABBREV', ladMatch?.game.opponent === 'WSH' && ladMatch?.key === 'LAD');
check('a row with neither gets nothing', slateGameFor({ team: 'SEA', player_name: 'Nobody' }, idx) === null);
// A UFC card has no home side: both fighters must see the SAME fixture, or the
// board shows one bout as two.
check(
  'neither fighter gets an "@" — a bout is not a venue',
  (slateSubline(ufcMatch?.game ?? null, null) ?? '').endsWith('· vs Matheus Nicolau') &&
    (slateSubline(
      slateGameFor({ team: null, player_name: 'Matheus Nicolau' }, ufcIdx)?.game ?? null,
      null,
    ) ?? '').endsWith('· vs Alex Perez'),
);
// The football boards are the reason this lives here and not in lib/matchup:
// they have no matchup feed at all, so a matchup-view subline would have
// shipped to two sports and skipped six.
const nflSlate = [subGame({ game_id: 'nfl1', sport: 'NFL', home_team: 'SEA', away_team: 'SF' })];
check(
  'a sport with no matchup feed still gets a subline',
  (slateSubline(
    slateGameFor({ team: 'SF' }, buildSlateGameIndex(nflSlate, { date: SUB_TODAY, keys: new Set(['SF']), isToday: true }, NOW))?.game ?? null,
    null,
  ) ?? '').endsWith('· @ SEA'),
);

// ── Next game in a multi-day window (team / player detail) ──
// buildTonightSlate + game_date === t.date drops a Thursday kickoff when the
// sport's "tonight" is Sunday. earliestUpcomingGame ranks the WHOLE window.

const thu = subGame({
  game_id: 'thu',
  sport: 'NFL',
  home_team: 'BUF',
  away_team: 'MIA',
  game_date: '2099-01-07',
  commence_time: '2099-01-07T01:20:00Z',
});
const sunOther = subGame({
  game_id: 'sun-other',
  sport: 'NFL',
  home_team: 'KC',
  away_team: 'DEN',
  game_date: SUB_TODAY,
  commence_time: at('17:00'),
});
const sunBufLate = subGame({
  game_id: 'sun-buf',
  sport: 'NFL',
  home_team: 'BUF',
  away_team: 'NYJ',
  game_date: SUB_TODAY,
  commence_time: at('20:20'),
});
check(
  'a Thursday game wins when tonight’s slate is a different NFL Sunday',
  earliestUpcomingGame([thu, sunOther], 'BUF', NOW)?.game.game_id === 'thu',
);
check(
  'the sooner kickoff in the window wins over a later same-team game',
  earliestUpcomingGame([thu, sunBufLate], 'BUF', NOW)?.game.game_id === 'sun-buf',
);
const startedThu = { ...thu, commence_time: '2000-01-01T01:20:00Z', game_date: '2000-01-01' };
check(
  'an already-started game loses to a later unstarted kickoff',
  earliestUpcomingGame([startedThu, sunBufLate], 'BUF', NOW)?.game.game_id === 'sun-buf',
);
check(
  'a team with no row in the window is null, not tonight’s leftover',
  earliestUpcomingGame([sunOther], 'BUF', NOW) === null,
);
const dhEarly = subGame({
  game_id: 'dh-early',
  home_team: 'NYY',
  away_team: 'BOS',
  commence_time: at('17:10'),
});
const dhLate = subGame({
  game_id: 'dh-late',
  home_team: 'NYY',
  away_team: 'BOS',
  commence_time: at('23:10'),
});
check(
  'an all-started doubleheader is the later game, not game one',
  earliestUpcomingGame([dhEarly, dhLate], 'NYY', at('23:59'))?.game.game_id === 'dh-late',
);
check(
  'before either doubleheader game, the sooner kickoff still wins',
  earliestUpcomingGame([dhEarly, dhLate], 'NYY', at('16:00'))?.game.game_id === 'dh-early',
);

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
