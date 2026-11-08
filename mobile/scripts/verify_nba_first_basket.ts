/**
 * Standalone verification for the NBA 1st Basket board (src/lib/nbaFirstBasket.ts).
 * Run with:
 *
 *   npx tsx scripts/verify_nba_first_basket.ts
 *
 * Pins:
 *  - candidates are this team's players only (a traded player is listed under
 *    his latest team), ranked by first shots, then first baskets, then fewer
 *    games, then name; at most three; nobody with zero of both;
 *  - every number reads "x of N" / "x/N", and an empty denominator is a dash,
 *    never "0 of 0" or "0%";
 *  - a team with no row yet shows dashes, not zeros;
 *  - the comparison reads away then home, and VoiceOver hears both teams;
 *  - the legend says free throws count (Matt's rule, 2026-11-08);
 *  - 1st Basket rides the NBA's top row and no other sport's.
 */
import {
  fbCandidates,
  fbCompareLines,
  fbSlateTeams,
  NBA_FB_LEGEND,
  normalizePlayerRow,
  ofN,
  ofNPct,
  slashN,
  type NbaFbPlayerRow,
  type NbaFbTeamRow,
} from '../src/lib/nbaFirstBasket';
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
  P({ espn_id: 2, name: 'Bravo', team: 'BOS', first_fga: 4, first_fga_made: 1, game_first_scores: 3 }),
  P({ espn_id: 3, name: 'Charlie', team: 'BOS', first_fga: 1, game_first_scores: 0, games: 5 }),
  P({ espn_id: 4, name: 'Delta', team: 'BOS', first_fga: 1, game_first_scores: 0, games: 9 }),
  P({ espn_id: 5, name: 'Echo', team: 'BOS' }), // never first: left out
  P({ espn_id: 6, name: 'Traded', team: 'LAL', first_fga: 9, game_first_scores: 5 }),
  P({ espn_id: 7, name: 'Free Throw Only', team: 'NYK', first_fga: 0, game_first_scores: 1, games: 3 }),
];
const bos = fbCandidates('BOS', players);
check('three at most', bos.length === 3, bos.length);
check('ranked by first shots, then first baskets', bos[0].name === 'Bravo' && bos[1].name === 'Alpha', bos.map((c) => c.name));
check('same count in fewer games ranks higher', bos[2].name === 'Charlie', bos.map((c) => c.name));
check('another team’s player never appears', !bos.some((c) => c.name === 'Traded'));
check('a never-first player is left out', !fbCandidates('BOS', players, 10).some((c) => c.name === 'Echo'));
check('cells', bos[0].firstShot === '4/9' && bos[0].made === '1/4' && bos[0].firstBasket === '3/9', bos[0]);
const nyk = fbCandidates('NYK', players);
check('a first basket on a free throw still lists him', nyk.length === 1 && nyk[0].name === 'Free Throw Only');
check('Made is a dash with no first shot', nyk[0].made === '—', nyk[0].made);
check('a11y names the player and both counts', /Bravo, 9 games\. Took the team's first shot 4 of 9, made 1 of 4\. Scored the game's first basket 3 of 9\./.test(bos[0].a11y), bos[0].a11y);
check('normalize turns string counts into numbers',
  normalizePlayerRow({ ...P({ espn_id: 8, name: 'S', team: 'BOS' }), games: '7' as unknown as number }).games === 7);

console.log('team comparison');
const row = (o: Partial<NbaFbTeamRow> & { team: string }): NbaFbTeamRow => ({
  season: 2027, games: 9, tip_games: 9, tips_won: 6, scored_first: 5, scored_first_won_tip: 4,
  lost_tip_games: 3, scored_first_lost_tip: 1, allowed_first: 4, jumper_espn_id: 10,
  jumper_name: 'Big Man', jumper_jumps: 8, jumper_jumps_won: 5, ...o,
});
const lines = fbCompareLines('NYK', 'BOS', row({ team: 'NYK' }), null);
const get = (k: string) => lines.find((l) => l.key === k)!;
check('away first', get('tips').away === '6 of 9 (67%)' && get('tips').home === '—');
check('a team with no row is dashes, not zeros', lines.every((l) => l.home === '—'), lines.map((l) => l.home));
check('jumper and his tips', get('jumper').away === 'Big Man' && get('jumperTips').away === '5 of 8');
check('split by tip', get('wonTip').away === '4 of 6' && get('lostTip').away === '1 of 3');
check('opponent scored first', get('allows').away === '4 of 9 (44%)', get('allows').away);
check('VoiceOver hears both teams', get('first').a11y === 'Scored first: NYK 5 of 9 (56%), BOS —', get('first').a11y);

console.log('slate and copy');
check('slate teams, sorted, deduplicated',
  fbSlateTeams([{ home_team: 'BOS', away_team: 'NYK' }, { home_team: 'LAL', away_team: 'BOS' }]).join(',') === 'BOS,LAL,NYK');
check('legend: free throws count', /free throws included/.test(NBA_FB_LEGEND));

console.log('segments');
check('NBA top row ends with 1st Basket', boardSegmentsFor('NBA').join('|') === 'players|teams|firstBasket', boardSegmentsFor('NBA'));
for (const s of ['MLB', 'WNBA', 'NHL', 'NFL', 'NCAAF', 'NCAAB', 'UFC'] as const) {
  check(`${s} has no 1st Basket`, !boardSegmentsFor(s).includes('firstBasket'));
}
check('1st Basket is not a position chip', !positionSegmentsFor('NBA').includes('firstBasket'));
check('label', segmentLabel('firstBasket') === '1st Basket');

if (failed > 0) {
  console.log(`\n${failed} check(s) FAILED`);
  process.exit(1);
}
console.log('\nall checks passed');
