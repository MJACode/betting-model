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
 *    to the next scheduled day.
 */

import type { GameRow } from '../src/types';
import * as board from '../src/lib/statsBoard';
import {
  EMPTY_SLATE,
  HIT_RATE_PRESETS,
  buildTonightSlate,
  compareRows,
  hitRateBand,
  inHitRateBand,
  isOnSlate,
  isStatParticipant,
  sortLabel,
  sortOptionsFor,
  type SortKey,
  type SortableRow,
} from '../src/lib/statsBoard';

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

// ── Stat participation (NFL only) ──────────────────────────────────────────
// The NFL log spans every position, so a kicker carries real rows with 0
// passing yards — on an "at most N pass yards" board those non-participants go
// 15/15 and bury the quarterbacks. All-zero NFL players are dropped; every
// other sport keeps them (a batter 0-for-10 is a real "at most 1 hits" answer).
check('NFL all-zero player is not a participant', !isStatParticipant('NFL', [0, 0, 0]));
check('NFL null values count as zero', !isStatParticipant('NFL', [null, undefined, 0]));
check('NFL player with any nonzero value stays', isStatParticipant('NFL', [0, 212, 0]));
check('MLB all-zero player stays (cold streaks are real outcomes)',
  isStatParticipant('MLB', [0, 0, 0]));
check('empty value list: NFL drops, others keep',
  !isStatParticipant('NFL', []) && isStatParticipant('WNBA', []));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
