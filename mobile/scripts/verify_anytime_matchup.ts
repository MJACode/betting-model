/**
 * NFL Anytime TD matchup column (Designer Option A).
 *
 *   npx tsx scripts/verify_anytime_matchup.ts
 *
 * Pins the tiers, the dash reasons, the sort tie-break, and the copy the
 * screen is allowed to show. The screen reads ATD_COPY; it does not invent
 * a second wording.
 */
import { FONT_SIZE_MICRO } from '../src/lib/typeScale';
import {
  ATD_COPY,
  ATD_HEADER_ARROW_W,
  ATD_HIT_W,
  ATD_MATCHUP_W,
  ATD_MATCHUP_WORD_W,
  ATD_ODDS_W,
  ATD_STACK_FONT_SCALE,
  BLEND_UNTIL_TEAM_GAMES,
  TIER_FLOORS,
  anyBlended,
  buildAnytimeMatchup,
  compareAnytimeRows,
  defenseKey,
  gapReason,
  groupsUsedByBoard,
  isAnytimeTdBoard,
  matchupSpoken,
  meetsTierFloor,
  nextMatchupSort,
  ordinal,
  rankLine,
  ranksInGroup,
  toughEndRank,
  matchupHeaderFontSize,
  tierBars,
  tierFloorSpoken,
  tierForRank,
  type DefenseRank,
} from '../src/lib/anytimeMatchup';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

check('blend window is 8 team games', BLEND_UNTIL_TEAM_GAMES === 8);
check('metrics stack at font scale 1.3', ATD_STACK_FONT_SCALE === 1.3);
check(
  'MATCHUP stays inside 66pt below the stack',
  matchupHeaderFontSize(1) === FONT_SIZE_MICRO
    && matchupHeaderFontSize(1.2) < FONT_SIZE_MICRO
    && ATD_MATCHUP_WORD_W * (matchupHeaderFontSize(1.2) / FONT_SIZE_MICRO) * 1.2 + ATD_HEADER_ARROW_W <= ATD_MATCHUP_W + 0.01,
);
check('the header size is the shared micro constant', FONT_SIZE_MICRO === 11 && matchupHeaderFontSize(1, ATD_MATCHUP_W, FONT_SIZE_MICRO) === FONT_SIZE_MICRO);
check('columns are Hit 40, Matchup 66, Price 62', ATD_HIT_W === 40 && ATD_MATCHUP_W === 66 && ATD_ODDS_W === 62);

check('1st 2nd 3rd 4th', ordinal(1) === '1st' && ordinal(2) === '2nd' && ordinal(3) === '3rd' && ordinal(4) === '4th');
check('11th 12th 13th stay th', ordinal(11) === '11th' && ordinal(12) === '12th' && ordinal(13) === '13th');
check('21st 22nd 23rd', ordinal(21) === '21st' && ordinal(22) === '22nd' && ordinal(23) === '23rd');

const band = (rank: number) => tierForRank(rank);
check('1 and 6 are Great, five bars', band(1)?.tier === 'Great' && band(1)?.bars === 5 && band(6)?.tier === 'Great');
check('7 and 13 are Good, four bars', band(7)?.tier === 'Good' && band(7)?.bars === 4 && band(13)?.bars === 4);
check('14 and 19 are Average, three bars', band(14)?.tier === 'Average' && band(14)?.bars === 3 && band(19)?.tier === 'Average');
check('20 and 26 are Tough, two bars', band(20)?.tier === 'Tough' && band(20)?.bars === 2 && band(26)?.tier === 'Tough');
check('27 and 32 are Very tough, one bar', band(27)?.tier === 'Very tough' && band(27)?.bars === 1 && band(32)?.tier === 'Very tough');
check('a rank past 32 stays Very tough', band(33)?.tier === 'Very tough' && band(33)?.bars === 1);
check('no rank is no tier', tierForRank(null) === null && tierForRank(0) === null && tierForRank(-1) === null);
check('rank 3 of 32 reads 3rd easiest', rankLine(3, 32) === '3rd easiest');
check('rank 30 of 32 reads 3rd toughest', rankLine(30, 32) === '3rd toughest');
check('rank 32 of 32 reads 1st toughest', rankLine(32, 32) === '1st toughest');
check('the midpoint stays on the easy end', rankLine(16, 32) === '16th easiest' && rankLine(17, 32) === '16th toughest');
const sixAtZero = Array.from({ length: 6 }, () => ({ rank: 27 as number | null }));
check(
  'six defenses tied at zero read 1st toughest',
  toughEndRank(27, sixAtZero) === 1 && rankLine(27, 32, toughEndRank(27, sixAtZero)) === '1st toughest',
);
check(
  'a tie at rank 1 stays 1st easiest',
  rankLine(1, 32) === '1st easiest'
    && rankLine(1, 32, toughEndRank(1, [{ rank: 1 }, { rank: 1 }, { rank: 1 }])) === '1st easiest',
);
check('Very tough is not a filter chip', !TIER_FLOORS.includes('Very tough') && TIER_FLOORS.length === 4);
check(
  'a floor chip speaks the bar count, not a tier word',
  tierBars('Great') === 5 && tierBars('Good') === 4 && tierBars('Average') === 3 && tierBars('Tough') === 2
    && tierFloorSpoken('Tough') === 'strength 2 or more'
    && tierFloorSpoken('Great') === 'strength 5 or more'
    && !tierFloorSpoken('Good').includes('Good'),
);

check('no floor keeps everyone', meetsTierFloor(null, null));
check('Great floor keeps only Great', meetsTierFloor('Great', 'Great') && !meetsTierFloor('Good', 'Great'));
check('Good floor includes Great', meetsTierFloor('Great', 'Good') && meetsTierFloor('Good', 'Good') && !meetsTierFloor('Average', 'Good'));
check('Tough floor includes every easier tier', meetsTierFloor('Average', 'Tough') && !meetsTierFloor('Very tough', 'Tough'));
check('unranked stay unless the switch is off', meetsTierFloor(null, 'Good', true) && !meetsTierFloor(null, 'Good', false));

const row = (rank: number | null, primary: number, price: number | null) => ({ rank, primary, price });
check(
  'easiest puts rank 1 above rank 6',
  compareAnytimeRows(row(1, 0, null), row(6, 1, null), 'easiest') < 0,
);
check(
  'toughest puts rank 32 above rank 1',
  compareAnytimeRows(row(32, 0, null), row(1, 1, null), 'toughest') < 0,
);
check(
  'a shared rank falls through to the higher hit rate',
  compareAnytimeRows(row(3, 0.4, -110), row(3, 0.6, -200), 'easiest') > 0,
);
check(
  'then to the better price',
  compareAnytimeRows(row(3, 0.5, -110), row(3, 0.5, 120), 'easiest') > 0,
);
check(
  'a missing price sorts after a priced tie',
  compareAnytimeRows(row(3, 0.5, null), row(3, 0.5, -150), 'easiest') > 0,
);
check(
  'unranked stay last either way',
  compareAnytimeRows(row(null, 1, 500), row(32, 0, -200), 'easiest') > 0
    && compareAnytimeRows(row(null, 1, 500), row(1, 0, -200), 'toughest') > 0,
);
check(
  'sort cycles off, easiest, toughest, off',
  nextMatchupSort(null) === 'easiest'
    && nextMatchupSort('easiest') === 'toughest'
    && nextMatchupSort('toughest') === null,
);

const place = {
  pos: 'WR',
  team: 'BUF',
  opponent: 'MIA',
  leagueHasGames: true,
  teamHasGame: true,
};
check('a ranked spot has no gap', gapReason(place, true) === null);
check('not playing wins when we know it', gapReason({ ...place, inactive: true }, true) === 'not_playing');
check(
  'a bye wins over a missing position',
  gapReason({ pos: null, team: 'BUF', opponent: null, leagueHasGames: true, teamHasGame: false }, false) === 'bye',
);
check(
  'no opponent and no team is no game',
  gapReason({ pos: 'WR', team: null, opponent: null, leagueHasGames: true, teamHasGame: false }, false) === 'no_game',
);
check(
  'an opponent with no position is no position',
  gapReason({ ...place, pos: 'K' }, false) === 'no_position',
);
check('a mapped player with no rank is too early', gapReason(place, false) === 'too_early');

const rank: DefenseRank = {
  defense: 'MIA',
  avgAllowed: 0.42,
  playerGames: 20,
  seasonTeamGames: 8,
  windowTeamGames: 8,
  blended: false,
  rank: 3,
  teamsRanked: 32,
};
const view = buildAnytimeMatchup({ status: 'ok', placement: place, rank });
const tiedZero: DefenseRank = {
  defense: 'MIA',
  avgAllowed: 0,
  playerGames: 8,
  seasonTeamGames: 8,
  windowTeamGames: 8,
  blended: false,
  rank: 27,
  teamsRanked: 32,
};
const tiedGroup = ['MIA', 'BUF', 'NYJ', 'NE', 'KC', 'DAL'].map((defense) => ({ ...tiedZero, defense }));
const tiedView = buildAnytimeMatchup({
  status: 'ok',
  placement: place,
  rank: tiedGroup[0],
});
check(
  'a rank of 27 is one filled bar',
  tiedView.kind === 'rank' && tiedView.bars === 1 && tiedView.spoken.startsWith('Matchup strength 1 of 5'),
);
check(
  'a rank view is five bars and a strength label',
  view.kind === 'rank' && view.bars === 5 && view.spoken === 'Matchup strength 5 of 5, wide receivers.',
);
check(
  'the spoken line names the count and the group, not a tier or a rank word',
  view.kind === 'rank'
    && view.spoken === matchupSpoken(5, 'WR')
    && view.spoken.includes('wide receivers')
    && !view.spoken.includes('Great')
    && !view.spoken.includes('easiest')
    && !view.spoken.includes('bars'),
);
check('loading is not a reason', buildAnytimeMatchup({ status: 'loading', placement: place, rank: null }).kind === 'loading');
check('an error is not Too early', buildAnytimeMatchup({ status: 'error', placement: place, rank }).kind === 'unavailable');
const byeFailed = buildAnytimeMatchup({
  status: 'error',
  placement: { pos: 'WR', team: 'BUF', opponent: null, leagueHasGames: true, teamHasGame: false },
  rank: null,
});
check('a bye stays a bye when ranks fail', byeFailed.kind === 'gap' && byeFailed.label === 'Bye');
const bye = buildAnytimeMatchup({
  status: 'ok',
  placement: { pos: 'WR', team: 'BUF', opponent: null, leagueHasGames: true, teamHasGame: false },
  rank: null,
});
check('a bye dash uses the short label', bye.kind === 'gap' && bye.label === 'Bye' && bye.spoken === 'Matchup, bye week.');

check('this board is NFL anytime TD only', isAnytimeTdBoard('NFL', 'rush_rec_tds'));
check('college anytime TD keeps the grade', !isAnytimeTdBoard('NCAAF', 'rush_rec_tds'));
check('another NFL prop keeps the grade', !isAnytimeTdBoard('NFL', 'receiving_yards') && !isAnytimeTdBoard('NFL', null));

check('the key ignores case', defenseKey('wr', 'mia') === 'WR|MIA');
check(
  'a group read keeps that group only',
  ranksInGroup([['WR|MIA', tiedZero], ['RB|BUF', { ...tiedZero, defense: 'BUF' }]], 'WR').map((r) => r.defense).join(',') === 'MIA',
);
check(
  'one blended defense turns the board note on',
  anyBlended([rank, { ...rank, defense: 'NYJ', blended: true }]) && !anyBlended([rank]),
);

check('the early-season note names 8 games', ATD_COPY.earlySeason.includes('8 games') && ATD_COPY.earlySeason.startsWith('Some defenses'));
check('a missing rank says No rank', ATD_COPY.gaps.too_early === 'No rank' && ATD_COPY.gapSpoken.too_early === 'Matchup, no rank.');
check('loading and a failed load name themselves', ATD_COPY.loadingLabel === 'Loading' && ATD_COPY.unavailableLabel === 'Unavailable');
check('totals header is TD', ATD_COPY.totalHeader === 'TD');
check(
  'the info sheet names the count, the shared rank, and the short sample',
  ATD_COPY.infoBody.includes('per player-game')
    && ATD_COPY.infoBody.includes('Ties share a rank')
    && ATD_COPY.infoBody.includes('short sample')
    && ATD_COPY.infoBody.includes('Five filled is ranks 1–6')
    && ATD_COPY.infoBody.includes('One is 27–32')
    && ATD_COPY.infoBody.includes('higher hit rate')
    && ATD_COPY.infoBody.includes('Five bars, filled from the left')
    && !ATD_COPY.infoBody.includes('Great')
    && !ATD_COPY.infoBody.includes('easiest')
    && !ATD_COPY.infoBody.includes('toughest'),
);
check('the board fetches only groups its rows use', groupsUsedByBoard(['WR', 'TE', 'K', 'FB']).join(',') === 'RB,WR,TE' && groupsUsedByBoard(['CB']).join(',') === 'DB' && groupsUsedByBoard([null, 'OL']).length === 0);
check('headers are HIT %, MATCHUP, BEST', ATD_COPY.hitHeader === 'HIT %' && ATD_COPY.header === 'MATCHUP' && ATD_COPY.priceHeader === 'BEST');
check('the unavailable note is one sentence', ATD_COPY.unavailableNote === 'Defense ranks didn’t load. Ranked matchups say Unavailable.');
check('a partial load names the groups that failed', ATD_COPY.partialNote === 'Some defense ranks didn’t load. Those matchups say Unavailable.');

if (failures > 0) {
  console.error(`${failures} failed`);
  process.exit(1);
}
console.log('anytime matchup checks passed');
