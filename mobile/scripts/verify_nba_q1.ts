/**
 * Standalone verification for the NBA first-quarter card (src/lib/nbaQ1.ts).
 * Run with:
 *
 *   npx tsx scripts/verify_nba_q1.ts
 *
 * Pins:
 *  - Last 5 / Last 10 are the last N games AT THE VENUE, newest first,
 *    whatever order the read returned them in;
 *  - they reach back into last season and say how many games did;
 *  - Season is the newest game's season only;
 *  - ratings are window sums (points over possessions x 100), not a mean of
 *    per-game ratings, and an unrated game counts in the record but not the
 *    ratings;
 *  - a tied quarter is a tie, not a loss.
 */
import {
  formatQ1Record,
  formatSigned1,
  nbaQ1Windows,
  nbaSeasonLabel,
  summarizeQ1,
  type NbaQ1Game,
} from '../src/lib/nbaQ1';

let failed = 0;
function check(name: string, cond: boolean, detail?: unknown) {
  if (cond) console.log(`  ok  ${name}`);
  else {
    failed += 1;
    console.log(`  FAIL ${name}`, detail ?? '');
  }
}

function g(
  date: string,
  season: number,
  isHome: boolean,
  pf: number,
  pa: number,
  possF: number | null = 25,
  possA: number | null = 25,
): NbaQ1Game {
  return {
    game_id: `NBA_${date}_X_${isHome ? 'BOS' : 'Y'}`,
    team: 'BOS',
    season,
    game_date: date,
    opponent: 'NYK',
    is_home: isHome,
    pts_for: pf,
    pts_against: pa,
    poss_for: possF,
    poss_against: possA,
  };
}

// Six games this season (2027) and six last season (2026), shuffled.
const games: NbaQ1Game[] = [
  g('2026-10-27', 2027, true, 30, 25),
  g('2026-04-10', 2026, true, 20, 30),
  g('2026-10-21', 2027, false, 28, 28),
  g('2026-10-25', 2027, false, 22, 31),
  g('2026-04-08', 2026, false, 33, 20),
  g('2026-10-23', 2027, true, 27, 24, null, null),
  g('2026-04-06', 2026, true, 25, 25),
  g('2026-10-26', 2027, true, 31, 29),
  g('2026-04-04', 2026, false, 18, 26),
  g('2026-10-24', 2027, false, 26, 21),
  g('2026-04-02', 2026, true, 29, 27),
  g('2026-03-31', 2026, true, 24, 22),
];

console.log('venue and ordering');
{
  const home = nbaQ1Windows(games, 'home');
  check('current season is the newest game’s', home.season === 2027, home.season);
  const l5 = home.rows[0].summary;
  // Home, newest first: 10-27 W, 10-26 W, 10-23 W, 04-10 L, 04-06 T.
  check('last 5 home record', formatQ1Record(l5) === '3-1-1', formatQ1Record(l5));
  check('last 5 home reaches 2 games back into last season', l5.priorSeasonGames === 2, l5.priorSeasonGames);
  check('season home is this season only', home.rows[2].summary.games === 3, home.rows[2].summary.games);
  const away = nbaQ1Windows(games, 'away');
  check('away last 10 holds every away game (5)', away.rows[1].summary.games === 5, away.rows[1].summary.games);
  const all = nbaQ1Windows(games, 'all');
  check('all last 10 is 10 games', all.rows[1].summary.games === 10);
  check('all season is 6 games', all.rows[2].summary.games === 6);
}

console.log('ratings');
{
  const s = summarizeQ1(
    [g('2026-10-27', 2027, true, 30, 20, 20, 25), g('2026-10-26', 2027, true, 20, 30, 30, 25)],
    2027,
  );
  // Window sums: 50 on 50 = 100.0; per-game mean would be (150 + 66.7)/2 = 108.3.
  check('ortg is a window sum, not a mean of game ratings', s.ortg === 100, s.ortg);
  check('drtg is a window sum', s.drtg === 100, s.drtg);
  const u = summarizeQ1([g('2026-10-27', 2027, true, 30, 20), g('2026-10-26', 2027, true, 40, 10, null, null)], 2027);
  check('unrated game counts in the record', u.games === 2 && u.wins === 2);
  check('unrated game counts in points', u.ptsFor === 35, u.ptsFor);
  check('unrated game is left out of ratings', u.ortg === 120 && u.ratedGames === 1, u);
  const none = summarizeQ1([], 2027);
  check('empty window has no numbers', none.ortg === null && none.margin === null && none.games === 0);
}

console.log('formatting');
check('signed margin uses a real minus', formatSigned1(-2.5) === '−2.5', formatSigned1(-2.5));
check('positive margin carries a plus', formatSigned1(1) === '+1.0');
check('season label is the ending year', nbaSeasonLabel(2027) === '2026-27', nbaSeasonLabel(2027));
check('record omits zero ties', formatQ1Record({ wins: 3, losses: 2, ties: 0 }) === '3-2');

if (failed) {
  console.log(`\n${failed} check(s) failed`);
  process.exit(1);
}
console.log('\nall checks passed');
