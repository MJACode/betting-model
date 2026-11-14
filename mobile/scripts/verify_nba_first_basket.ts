/**
 * Standalone verification for the NBA 1st Basket board (src/lib/nbaFirstBasket.ts).
 * Run with:
 *
 *   npx tsx scripts/verify_nba_first_basket.ts
 *
 * Pins:
 *  - candidates are this team's players only (a traded player is listed under
 *    his latest team), ranked by first shots, then first baskets, then fewer
 *    starts, then name; at most three; nobody with zero of both; rates over
 *    STARTS; a player ruled out tonight is dropped and the next moves up, a
 *    Questionable one keeps his place and his tag;
 *  - rate cells lead with the % and carry "x of N" under it;
 *  - the usual jumper says when he is out;
 *  - started games sort last;
 *  - every number reads "x of N" / "x/N", and an empty denominator is a dash,
 *    never "0 of 0" or "0%";
 *  - a team with no row yet shows dashes, not zeros;
 *  - the comparison reads away then home, and VoiceOver hears both teams;
 *  - the legend says free throws count (Matt's rule, 2026-11-08);
 *  - 1st Basket rides the NBA's top row and no other sport's.
 */
import {
  fbCandidates,
  fbCandidatesEmptyText,
  fbCompareLines,
  fbGameStarted,
  fbOrderGames,
  fbSlateTeams,
  NBA_FB_LEGEND,
  normalizePlayerRow,
  ofN,
  ofNPct,
  slashN,
  type NbaFbPlayerRow,
  type NbaFbTeamRow,
} from '../src/lib/nbaFirstBasket';
import { injuryTag } from '../src/lib/injuryStatus';
import { boardSegmentsFor, positionSegmentsFor, segmentLabel } from '../src/lib/statSegments';

let failed = 0;
function check(name: string, cond: boolean, detail?: unknown) {
  if (cond) console.log(`  ok  ${name}`);
  else {
    failed++;
    console.log(`  FAIL ${name}`, detail === undefined ? '' : JSON.stringify(detail));
  }
}

const P = (o: Partial<NbaFbPlayerRow> & { espn_id: number; name: string; team: string }): NbaFbPlayerRow => ({
  season: 2027,
  games: 9,
  starts: 9,
  first_fga: 0,
  first_fga_made: 0,
  game_first_scores: 0,
  team_first_scores: 0,
  jumps: 0,
  jumps_won: 0,
  last_game_date: '2026-11-07',
  ...o,
});

console.log('formatting');
check('ofN', ofN(6, 9) === '6 of 9');
check('ofN empty is a dash', ofN(0, 0) === '—');
check('slashN empty is a dash', slashN(0, 0) === '—');
check('ofNPct rounds', ofNPct(2, 3) === '2 of 3 (67%)', ofNPct(2, 3));
check('ofNPct empty has no 0%', ofNPct(0, 0) === '—');

console.log('candidates');
const players: NbaFbPlayerRow[] = [
  P({ espn_id: 1, name: 'Alpha', team: 'BOS', first_fga: 4, first_fga_made: 2, game_first_scores: 2 }),
  P({ espn_id: 2, name: 'Bravo', team: 'BOS', first_fga: 4, first_fga_made: 1, game_first_scores: 3, games: 10 }),
  P({ espn_id: 3, name: 'Charlie', team: 'BOS', first_fga: 1, game_first_scores: 0, starts: 5 }),
  P({ espn_id: 4, name: 'Delta', team: 'BOS', first_fga: 1, game_first_scores: 0, starts: 9 }),
  P({ espn_id: 5, name: 'Echo', team: 'BOS' }), // never first: left out
  P({ espn_id: 6, name: 'Traded', team: 'LAL', first_fga: 9, game_first_scores: 5 }),
  P({ espn_id: 7, name: 'Free Throw Only', team: 'NYK', first_fga: 0, game_first_scores: 1, starts: 3 }),
  P({ espn_id: 8, name: 'Bench Guy', team: 'NYK', first_fga: 0, game_first_scores: 1, starts: 0 }),
];
const bos = fbCandidates('BOS', players);
check('three at most', bos.length === 3, bos.length);
check('ranked by first shots, then first baskets', bos[0].name === 'Bravo' && bos[1].name === 'Alpha', bos.map((c) => c.name));
check('same count in fewer starts ranks higher', bos[2].name === 'Charlie', bos.map((c) => c.name));
check('another team’s player never appears', !bos.some((c) => c.name === 'Traded'));
check('a never-first player is left out', !fbCandidates('BOS', players, 10).some((c) => c.name === 'Echo'));
check('rates are over starts, not games', bos[0].firstShot === '4/9' && bos[0].made === '1/4' && bos[0].firstBasket === '3/9', bos[0]);
const nyk = fbCandidates('NYK', players);
check('a first basket on a free throw still lists him', nyk.length === 1 && nyk[0].name === 'Free Throw Only', nyk.map((c) => c.name));
check('a player with no start is left out', !nyk.some((c) => c.name === 'Bench Guy'));
check('Made is a dash with no first shot', nyk[0].made === '\u2014', nyk[0].made);
check('a11y names the player, starts and both counts', /Bravo, 9 starts\. Took the team's first shot 4 of 9, made 1 of 4\. Scored the game's first basket 3 of 9\./.test(bos[0].a11y), bos[0].a11y);
check('normalize turns string counts into numbers',
  normalizePlayerRow({ ...P({ espn_id: 9, name: 'S', team: 'BOS' }), games: '7' as unknown as number }).games === 7);

const OUT = injuryTag('Out');
const Q = injuryTag('Questionable');
const inj = (name: string | null | undefined) => (name === 'Bravo' ? OUT : name === 'Alpha' ? Q : name === 'Big Man' ? OUT : null);
const bosInj = fbCandidates('BOS', players, undefined, inj);
check('a player ruled out is dropped and the next moves up', bosInj.map((c) => c.name).join(',') === 'Alpha,Charlie,Delta', bosInj.map((c) => c.name));
check('a Questionable player keeps his place and his tag', bosInj[0].injury?.label === 'Q' && /Alpha, Questionable, 9 starts/.test(bosInj[0].a11y), bosInj[0]);

const allOut = () => OUT;
check('every first-shot player out: says so, not "none stored"',
  /Everyone on BOS with a first shot this season is ruled out tonight\./.test(fbCandidatesEmptyText('BOS', players, allOut)));
check('no first shots at all: says none stored',
  fbCandidatesEmptyText('PHX', players, allOut) === 'No first shots stored for PHX this season yet.');

console.log('game order');
const now = Date.parse('2026-11-08T01:00:00Z');
const g = (id: string, t: string) => ({ game_id: id, commence_time: t });
const order = fbOrderGames([g('late', '2026-11-08T03:00:00Z'), g('started', '2026-11-08T00:00:00Z'), g('early', '2026-11-08T01:30:00Z')], now);
check('started games sort last, the rest by tip time', order.map((x) => x.game_id).join(',') === 'early,late,started', order.map((x) => x.game_id));
check('started at tip time', fbGameStarted(g('x', '2026-11-08T01:00:00Z'), now) && !fbGameStarted(g('y', ''), now));

console.log('team comparison');
const row = (o: Partial<NbaFbTeamRow> & { team: string }): NbaFbTeamRow => ({
  season: 2027, games: 9, tip_games: 9, tips_won: 6, scored_first: 5, scored_first_won_tip: 4,
  lost_tip_games: 3, scored_first_lost_tip: 1, allowed_first: 4, jumper_espn_id: 10,
  jumper_name: 'Big Man', jumper_jumps: 8, jumper_jumps_won: 5, ...o,
});
const lines = fbCompareLines('NYK', 'BOS', row({ team: 'NYK' }), null);
const get = (k: string) => lines.find((l) => l.key === k)!;
check('percentage first, count under it', get('tips').away.value === '67%' && get('tips').away.sub === '6 of 9', get('tips').away);
check('a team with no row is dashes, not zeros', lines.every((l) => l.home.value === '\u2014' && l.home.sub === null), lines.map((l) => l.home));
check('jumper and his tips', get('jumper').away.value === 'Big Man' && get('jumperTips').away.sub === '5 of 8');
check('split by tip', get('wonTip').away.sub === '4 of 6' && get('lostTip').away.sub === '1 of 3');
check('opponent scored first', get('allows').away.value === '44%' && get('allows').away.sub === '4 of 9', get('allows').away);
check('VoiceOver hears both teams, in counts', get('first').a11y === 'Scored first: NYK 5 of 9, BOS no games yet', get('first').a11y);
check('no cell value is longer than "100%" or a name',
  lines.filter((l) => l.key !== 'jumper').every((l) => l.away.value.length <= 4), lines.map((l) => l.away.value));
const outLines = fbCompareLines('NYK', 'BOS', row({ team: 'NYK' }), null, inj);
const j = outLines.find((l) => l.key === 'jumper')!;
check('the usual jumper says when he is out', j.away.sub === 'Out, not playing' && /Big Man, Out, not playing/.test(j.a11y), j);

console.log('slate and copy');
check('slate teams, sorted, deduplicated',
  fbSlateTeams([{ home_team: 'BOS', away_team: 'NYK' }, { home_team: 'LAL', away_team: 'BOS' }]).join(',') === 'BOS,LAL,NYK');
check('legend: free throws count', /free throws included/.test(NBA_FB_LEGEND));

console.log('segments');
check('NBA top row ends with 1st Basket', boardSegmentsFor('NBA').join('|') === 'players|teams|firstBasket', boardSegmentsFor('NBA'));
for (const s of ['MLB', 'WNBA', 'NHL', 'NFL', 'NCAAF', 'NCAAB', 'NCAABW', 'UFC', 'ATP', 'WTA'] as const) {
  check(`${s} has no 1st Basket`, !boardSegmentsFor(s).includes('firstBasket'));
}
check('1st Basket is not a position chip', !positionSegmentsFor('NBA').includes('firstBasket'));
check('label', segmentLabel('firstBasket') === '1st Basket');

if (failed > 0) {
  console.log(`\n${failed} check(s) FAILED`);
  process.exit(1);
}
console.log('\nall checks passed');
