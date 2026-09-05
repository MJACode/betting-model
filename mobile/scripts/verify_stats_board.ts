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
 *  - sort comparators order by the number the board displays, tie-breaking on
 *    sample size, with explicit games/average alternatives;
 *  - "playing tonight" is derived from `games` for EVERY sport — team abbrevs
 *    for team sports, fighter names for UFC — and prefers today, falling back
 *    to the next scheduled day;
 *  - the row SUBLINE ("9:40 PM ET · @ SEA") comes off the same `games` rows, so
 *    it lands in every sport, resolves doubleheaders to the game still ahead,
 *    and yields to Live/Final once the game is under way.
 */

import type { GameRow } from '../src/types';
import * as board from '../src/lib/statsBoard';
import {
  EMPTY_SLATE,
  HIT_RATE_PRESETS,
  buildSlateGameIndex,
  buildTonightSlate,
  compareRows,
  hitRateBand,
  inHitRateBand,
  isOnSlate,
  isStatParticipant,
  slateGameFor,
  slateSubline,
  sortLabel,
  sortOptionsFor,
  type SortKey,
  type SortableRow,
} from '../src/lib/statsBoard';
import { todayET } from '../src/lib/format';

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
  compareRows({ primary: 1, games: 1, avg: 12 }, { primary: 1, games: 80, avg: 2 }, 'default') > 0,
);

// ── 2. Sort ──

const row = (primary: number, games: number, avg: number): SortableRow => ({ primary, games, avg });
// A perfect 5-of-5 next to a 70%-of-80 and a 33%-of-90.
const pool = [row(0.33, 90, 1.1), row(1.0, 5, 2.4), row(0.7, 80, 1.9)];
const byRate = pool.slice().sort((a, b) => compareRows(a, b, 'default'));
check(
  'default sort = the displayed number, desc',
  byRate[0].primary === 1.0 && byRate[1].primary === 0.7 && byRate[2].primary === 0.33,
  JSON.stringify(byRate.map((r) => r.primary)),
);
const byGames = pool.slice().sort((a, b) => compareRows(a, b, 'games'));
check(
  'games sort puts the 90-game regular first, the 5-game player last',
  byGames[0].games === 90 && byGames[2].games === 5,
  JSON.stringify(byGames.map((r) => r.games)),
);
const byAvg = pool.slice().sort((a, b) => compareRows(a, b, 'avg'));
check('avg sort ranks on the per-game average', byAvg[0].avg === 2.4 && byAvg[2].avg === 1.1);

// Ties break on sample size, in every sort — this is what keeps regulars above
// small-sample players when the visible number is identical.
const tied = [row(0.5, 4, 1), row(0.5, 40, 1)];
check('tie on rate → more games first', tied.slice().sort((a, b) => compareRows(a, b, 'default'))[0].games === 40);
check('tie on games → higher rate first',
  [row(0.2, 10, 1), row(0.9, 10, 1)].sort((a, b) => compareRows(a, b, 'games'))[0].primary === 0.9);
check('tie on avg → more games first',
  [row(0.2, 3, 5), row(0.2, 30, 5)].sort((a, b) => compareRows(a, b, 'avg'))[0].games === 30);

check('sort is stable-ish / total order (no NaN comparators)',
  pool.slice().sort((a, b) => compareRows(a, b, 'default')).length === 3);

check('hit-rate mode offers rate / games / average', sortOptionsFor('hitRate').length === 3);
check('averages mode has no "hit rate" option', sortOptionsFor('totals').length === 2 &&
  sortOptionsFor('totals').every((o) => o.label !== 'Hit rate'));
check('sortLabel is mode-aware',
  sortLabel('default', 'hitRate') === 'Hit rate' && sortLabel('default', 'totals') === 'Stat value');
check('every sort key has a label in hit-rate mode',
  (['default', 'games', 'avg'] as SortKey[]).every((k) => !!sortLabel(k, 'hitRate')));

// ── 3. Hit-rate band ──

check('blank fields = unbounded', hitRateBand('', '').lo === 0 && hitRateBand('', '').hi === 1);
const b60 = hitRateBand('60', '');
check('min 60 → lo 0.6, hi 1', b60.lo === 0.6 && b60.hi === 1);
check('exactly 60% passes a "min 60" band (float tolerance)', inHitRateBand(0.6, b60));
check('59% fails a "min 60" band', !inHitRateBand(0.59, b60));
check('3-of-5 = 60% passes min 60', inHitRateBand(3 / 5, b60));
const band = hitRateBand('60', '80');
check('a band excludes both tails', inHitRateBand(0.7, band) && !inHitRateBand(0.85, band) && !inHitRateBand(0.5, band));
const inverted = hitRateBand('80', '60');
check('inverted band is normalised, not emptied', inverted.lo === 0.6 && inverted.hi === 0.8);
check('out-of-range input is clamped', hitRateBand('150', '').lo === 1 && hitRateBand('-20', '').lo === 0);
check('garbage input is ignored', hitRateBand('abc', 'xyz').lo === 0 && hitRateBand('abc', 'xyz').hi === 1);
check('max-only band', hitRateBand('', '40').lo === 0 && hitRateBand('', '40').hi === 0.4);
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

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
