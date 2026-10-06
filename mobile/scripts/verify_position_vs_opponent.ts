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
import { playerSummaries, positionVsOpponent } from '../src/lib/positionVsOpponent';
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

console.log(failed ? `\n${failed} FAILED` : '\nALL PASS');
process.exit(failed ? 1 : 0);
