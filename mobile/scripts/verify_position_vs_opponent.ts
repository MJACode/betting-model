/**
 * Behaviour checks for the position-vs-opponent card's pure layer
 * (src/lib/positionVsOpponent.ts). Run with:
 *
 *   npx tsx scripts/verify_position_vs_opponent.ts
 *
 * Pins what a source grep cannot (UX review, 2026-10-06): the MLB per-player
 * summary groups by player, averages and counts hits from the rows' own
 * `hit`, keeps the name and team of the player's LATEST game, and sorts
 * games -> hit rate -> name; the card drops the page's own player; and
 * doubleheader games are numbered.
 */
import {
  footnoteText,
  nextSeasonChoice,
  playerSummaries,
  positionVsOpponent,
  roleCutText,
  rosterGroup,
  rosterSeasonInProgress,
  seasonSubjectKey,
  type SeasonChoiceInput,
} from '../src/lib/positionVsOpponent';
import type { PositionVsOpponentRow } from '../src/types';

let failed = 0;
function check(name: string, ok: boolean, detail = '') {
  console.log(`${ok ? '  ✓' : '  ✗ FAIL'} ${name}${detail ? ` — ${detail}` : ''}`);
  if (!ok) failed++;
}

function row(p: Partial<PositionVsOpponentRow> & { player_id: string; game_id: string; game_date: string; value: number }): PositionVsOpponentRow {
  return {
    season: 2026, player_name: p.player_id.toUpperCase(), team: 'LAD', pos: '2', week: null,
    avg_allowed: 1, player_games: 10, rank_most_allowed: 3, teams_ranked: 30, ...p,
  } as PositionVsOpponentRow;
}

const rows: PositionVsOpponentRow[] = [
  // a: traded mid-season, 3 games, 2 over 0.5
  row({ player_id: 'a', game_id: 'g1', game_date: '2026-05-01', value: 1, team: 'SD', player_name: 'A Old' }),
  row({ player_id: 'a', game_id: 'g2', game_date: '2026-07-01', value: 0, team: 'LAD', player_name: 'A New' }),
  row({ player_id: 'a', game_id: 'g3', game_date: '2026-06-01', value: 2, team: 'SD', player_name: 'A Old' }),
  // b and c: 2 games each, b 2/2 and c 1/2 -> b first. c is named "Abe" so
  // that NAME order alone would put c first: only the hit-rate key passes.
  row({ player_id: 'c', game_id: 'g4', game_date: '2026-05-02', value: 1, player_name: 'Abe' }),
  row({ player_id: 'c', game_id: 'g5', game_date: '2026-05-03', value: 0, player_name: 'Abe' }),
  row({ player_id: 'b', game_id: 'g6', game_date: '2026-05-02', value: 3 }),
  row({ player_id: 'b', game_id: 'g7', game_date: '2026-05-03', value: 1 }),
  // d and e: 1 game each, both 1/1 -> by name
  row({ player_id: 'e', game_id: 'g8', game_date: '2026-05-04', value: 1, player_name: 'Eve' }),
  row({ player_id: 'd', game_id: 'g9', game_date: '2026-05-04', value: 1, player_name: 'Dan' }),
  // f: two games on one date (a doubleheader), 0/2
  row({ player_id: 'f', game_id: 'h2', game_date: '2026-08-01', value: 0, player_name: 'Fay' }),
  row({ player_id: 'f', game_id: 'h1', game_date: '2026-08-01', value: 0, player_name: 'Fay' }),
  // the page's own player: excluded
  row({ player_id: 'me', game_id: 'g10', game_date: '2026-05-05', value: 9 }),
  // other season: ignored for 2026
  row({ player_id: 'a', game_id: 'old', game_date: '2025-05-05', value: 9, season: 2025 }),
];

const card = positionVsOpponent(rows, {
  opponent: 'NYY', group: 'TOP', season: 2026, excludePlayerId: 'me', line: 0.5, side: 'over',
});
check('own player excluded', !card.entries.some((e) => e.playerId === 'me'));
check('other season excluded', card.entries.length === 11, `got ${card.entries.length}`);
check('hit rate over the season rows', card.hits === 7 && card.total === 11, `${card.hits}/${card.total}`);
const fay = card.entries.filter((e) => e.playerId === 'f').sort((x, y) => (x.gameId < y.gameId ? -1 : 1));
check('doubleheader numbered by game id', fay.map((e) => e.gameOfDay).join(',') === '1,2');
check('single games not numbered', card.entries.find((e) => e.playerId === 'b')?.gameOfDay == null);

const s = playerSummaries(card.entries);
check('one row per player', s.length === 6, s.map((p) => p.playerId).join(','));
check('sorted games -> hit rate -> name', s.map((p) => p.playerId).join(',') === 'a,b,c,f,d,e',
  s.map((p) => `${p.playerId}:${p.hits}/${p.games}`).join(' '));
const a = s.find((p) => p.playerId === 'a')!;
check('latest game decides team and name', a.team === 'LAD' && a.playerName === 'A New', `${a.team} ${a.playerName}`);
check('average over his games', a.avg === 1 && a.games === 3 && a.hits === 2, `${a.avg} ${a.hits}/${a.games}`);
check('last date is the latest', a.lastDate === '2026-07-01');
check('empty in, empty out', playerSummaries([]).length === 0);

const under = positionVsOpponent(rows, {
  opponent: 'NYY', group: 'TOP', season: 2026, excludePlayerId: 'me', line: 0.5, side: 'under',
});
check('summary follows the side via the rows\' hit', playerSummaries(under.entries).find((p) => p.playerId === 'a')!.hits === 1);

// ── roster sports (phase 3) ──────────────────────────────────────────────
// Season labels (CLAUDE.md §4): NBA ending year, WNBA year of play, NCAAF
// starting year — measured on production in queries.ts h2hSeasonCandidates.
check('NBA Oct 2026 is the 2027 season', rosterSeasonInProgress('NBA', '2026-10-06') === 2027);
check('NBA Apr 2026 is the 2026 season', rosterSeasonInProgress('NBA', '2026-04-12') === 2026);
check('WNBA Mar 2027 shows 2026', rosterSeasonInProgress('WNBA', '2027-03-01') === 2026);
check('WNBA Jul 2026 is 2026', rosterSeasonInProgress('WNBA', '2026-07-01') === 2026);
check('NCAAF Jan 2027 is 2026', rosterSeasonInProgress('NCAAF', '2027-01-10') === 2026);
check('NCAAF Sep 2026 is 2026', rosterSeasonInProgress('NCAAF', '2026-09-20') === 2026);
check('basketball groups G/F/C', rosterGroup('NBA', 'g') === 'G' && rosterGroup('WNBA', 'C') === 'C');
check('a football group is not a basketball group', rosterGroup('NBA', 'WR') === null);
check('NCAAF groups are the NFL buckets', rosterGroup('NCAAF', 'DB') === 'DB' && rosterGroup('NCAAF', 'OL') === null);
check('no position, no group', rosterGroup('NCAAF', null) === null);
check('NCAAF receiver cut is a catch', roleCutText('WR', 'NCAAF') === '1+ catch' && roleCutText('WR', 'NFL') === '3+ targets');
check('NCAAF QB falls back to the shared cut', roleCutText('QB', 'NCAAF') === '10+ pass attempts');
check('NCAAF receiver footnote names the missing targets', /no targets/.test(footnoteText('WR', 'NCAAF')));
check('NFL receiver footnote does not', !/no targets/.test(footnoteText('WR', 'NFL')));

check('footnote keeps abbreviations upper case', footnoteText('WR', 'NCAAF').startsWith('Counts WRs '),
  footnoteText('WR', 'NCAAF'));
check('footnote lower-cases words', footnoteText('G', 'NBA') === 'Counts guards with 15+ minutes in the game.',
  footnoteText('G', 'NBA'));

// ── the once-only "open on last season" flag ─────────────────────────────
// The card stays mounted when the reader opens another player. The flag
// has to reset with the player or the opponent, and a season they tapped
// for this same player has to stay put.
function choiceInput(over: Partial<SeasonChoiceInput>): SeasonChoiceInput {
  return {
    subjectKey: seasonSubjectKey('p1', 'ATL'),
    seenKey: null,
    decided: false,
    readerPicked: false,
    choice: 'this',
    loading: false,
    rows: [{ player_id: 'other', season: 2025 }],
    playerId: 'p1',
    seasonThis: 2026,
    ...over,
  };
}
const opened = nextSeasonChoice(choiceInput({}));
check('empty this season opens on last, once', opened.choice === 'last' && opened.decided,
  `${opened.choice} decided=${opened.decided}`);
const held = nextSeasonChoice(choiceInput({
  seenKey: opened.seenKey, decided: opened.decided, choice: opened.choice,
  rows: [{ player_id: 'other', season: 2025 }],
}));
check('same player and opponent does not decide again', held.choice === 'last' && held.subjectChanged === false);
const reader = nextSeasonChoice(choiceInput({
  seenKey: seasonSubjectKey('p1', 'ATL'),
  decided: true,
  readerPicked: true,
  choice: 'this',
  rows: [{ player_id: 'other', season: 2025 }],
}));
check('a season the reader picked for this player stays', reader.choice === 'this' && reader.readerPicked);
const otherOpponent = nextSeasonChoice(choiceInput({
  subjectKey: seasonSubjectKey('p1', 'BUF'),
  seenKey: seasonSubjectKey('p1', 'ATL'),
  decided: true,
  readerPicked: true,
  choice: 'this',
  rows: [{ player_id: 'other', season: 2025 }],
}));
check('a new opponent does not override the reader\'s season for the same player',
  otherOpponent.choice === 'this' && otherOpponent.readerPicked && otherOpponent.subjectChanged);
const nextPlayer = nextSeasonChoice(choiceInput({
  subjectKey: seasonSubjectKey('p2', 'ATL'),
  seenKey: seasonSubjectKey('p1', 'ATL'),
  decided: true,
  readerPicked: true,
  choice: 'this',
  playerId: 'p2',
  rows: [{ player_id: 'other', season: 2025 }],
}));
check('a new player resets the flag and can open on last season',
  nextPlayer.choice === 'last' && nextPlayer.decided && nextPlayer.readerPicked === false
  && nextPlayer.subjectChanged);
const autoThenOpponent = nextSeasonChoice(choiceInput({
  subjectKey: seasonSubjectKey('p1', 'BUF'),
  seenKey: seasonSubjectKey('p1', 'ATL'),
  decided: true,
  readerPicked: false,
  choice: 'last',
  rows: [{ player_id: 'other', season: 2026 }],
}));
check('an auto choice re-decides when only the opponent changes',
  autoThenOpponent.choice === 'this' && autoThenOpponent.decided && autoThenOpponent.readerPicked === false);

console.log(failed ? `\n${failed} FAILED` : '\nALL PASS');
process.exit(failed ? 1 : 0);
