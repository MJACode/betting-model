/**
 * Standalone verification for the H2H window's pure logic — the two pieces
 * that decide WHICH fixture each row is compared against (nextGameByTeam /
 * h2hMatchups in src/lib/statsBoard.ts) and the one that turns an RPC row into
 * the player page's card (playerHeadToHead in src/lib/playerDetail.ts). Run:
 *
 *   npx tsx scripts/verify_h2h.ts
 *
 * Pins, each of which is a way the feature can be silently WRONG rather than
 * merely broken — a head-to-head against the wrong opponent still renders a
 * confident percentage:
 *
 *   - the fixture spans the whole forward window, not the slate date (the NFL
 *     case: a board opened on Tuesday must still know who plays on Sunday);
 *   - an in-progress or finished game does not beat a later unstarted one, so
 *     a doubleheader resolves to the game that can still be bet;
 *   - a team that has no upcoming game contributes no matchup at all, rather
 *     than a pair with an empty opponent;
 *   - the two arrays stay index-aligned and ordered, because the RPC pairs
 *     them positionally and the board memoises on their content;
 *   - values and dates stay paired in playerHeadToHead even when the two
 *     arrays disagree in length, and the hit count is `>= threshold` — the
 *     same comparison the rest of the player page makes.
 */

import { h2hMatchups, nextGameByTeam } from '../src/lib/statsBoard';
import { playerHeadToHead } from '../src/lib/playerDetail';
import type { GameRow } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = ''): void {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

function game(
  game_id: string,
  home_team: string,
  away_team: string,
  game_date: string,
  commence_time: string,
): GameRow {
  return {
    game_id,
    sport: 'NFL',
    season: 2026,
    game_date,
    home_team,
    away_team,
    home_score: null,
    away_score: null,
    commence_time,
    home_win: null,
  } as unknown as GameRow;
}

const NOW = '2026-09-22T12:00:00Z'; // a Tuesday

// ── 1. The fixture spans the forward window, not "today" ──
// Two NFL games later in the week. Nothing is on today, which is exactly the
// case a slate-date index answers with nothing.
const week = [
  game('g-thu', 'KC', 'IND', '2026-09-24', '2026-09-25T00:20:00Z'),
  game('g-sun', 'BUF', 'NYJ', '2026-09-27', '2026-09-27T17:00:00Z'),
];
const idx = nextGameByTeam(week, NOW);
check('all four teams in the week resolve a fixture', idx.size === 4, `size=${idx.size}`);
check('home team sees the visitor', idx.get('KC')?.opponent === 'IND', String(idx.get('KC')?.opponent));
check('away team sees the host', idx.get('IND')?.opponent === 'KC', String(idx.get('IND')?.opponent));
check('Sunday is found on a Tuesday', idx.get('NYJ')?.opponent === 'BUF', String(idx.get('NYJ')?.opponent));
check('home/away is kept', idx.get('KC')?.isHome === true && idx.get('IND')?.isHome === false);

// ── 2. A started game does not beat a later unstarted one ──
// MLB doubleheader shape: game one is under way, game two is not. The bet that
// can still be made is game two.
const dh = [
  game('dh-1', 'TOR', 'BAL', '2026-09-22', '2026-09-22T11:00:00Z'), // started
  game('dh-2', 'TOR', 'BAL', '2026-09-22', '2026-09-22T17:00:00Z'), // not yet
];
const dhIdx = nextGameByTeam(dh, NOW);
check('doubleheader resolves to the unstarted game', dhIdx.get('TOR')?.game.game_id === 'dh-2',
  String(dhIdx.get('TOR')?.game.game_id));
// Once BOTH have started there is no bettable game left, and the fallback is
// the LAST one — not game one, whose numbers are already history.
const dhIdxLate = nextGameByTeam(dh, '2026-09-22T23:00:00Z');
check('all started → the last game of the day, not the first',
  dhIdxLate.get('TOR')?.game.game_id === 'dh-2', String(dhIdxLate.get('TOR')?.game.game_id));

// ── 3. The matchup arrays ──
const m = h2hMatchups(idx);
check('one entry per team', m.teams.length === 4 && m.opponents.length === 4,
  `${m.teams.length}/${m.opponents.length}`);
check('sorted by team, so the read key is stable',
  m.teams.join() === m.teams.slice().sort().join(), m.teams.join());
const paired = m.teams.map((t, i) => `${t}>${m.opponents[i]}`).sort().join(' ');
check('index i of one array is index i of the other',
  paired === 'BUF>NYJ IND>KC KC>IND NYJ>BUF', paired);
// Re-deriving the index from the same games must produce the same key, or the
// board re-reads the whole leaderboard on every 60s clock tick.
const again = h2hMatchups(nextGameByTeam(week, '2026-09-22T12:01:00Z'));
check('a minute later is the same key',
  again.teams.join() === m.teams.join() && again.opponents.join() === m.opponents.join());

// ── 4. Narrowing to a picked game ──
const narrowed = h2hMatchups(idx, ['KC', 'IND']);
check('only the picked teams survive', narrowed.teams.join() === 'IND,KC', narrowed.teams.join());
check('an empty allow-list narrows nothing', h2hMatchups(idx, []).teams.length === 4);

// ── 5. A team with nothing scheduled contributes no pair ──
// `games` holds finished history too; a team that appears only in a past game
// with no upcoming one must not produce a matchup with an empty opponent.
const emptyIdx = nextGameByTeam([], NOW);
check('no games → no fixtures', emptyIdx.size === 0 && h2hMatchups(emptyIdx).teams.length === 0);
const bogus = h2hMatchups(new Map(idx).set('SF', { ...idx.get('KC')!, opponent: '' }));
check('a fixture with no opponent is dropped, not sent blank',
  !bogus.teams.includes('SF'), bogus.teams.join());

// ── 6. playerHeadToHead ──
const h = playerHeadToHead('KC', [112, 64, 90], ['2026-01-04', '2025-11-10', '2025-09-15'], 90);
check('meetings keep their dates, newest first',
  h.meetings.map((x) => `${x.date}:${x.value}`).join() === '2026-01-04:112,2025-11-10:64,2025-09-15:90',
  JSON.stringify(h.meetings));
check('hits count values AT the threshold (>=, as the page does)', h.bucket.hits === 2,
  String(h.bucket.hits));
check('games and rate', h.bucket.games === 3 && Math.abs((h.bucket.hitRate ?? 0) - 2 / 3) < 1e-9);
check('average over the meetings', Math.abs((h.bucket.avg ?? 0) - (112 + 64 + 90) / 3) < 1e-9);
check('the bucket labels itself by opponent', h.bucket.label === 'vs KC', h.bucket.label);

// A length mismatch must not pair a value with another game's date.
const mismatch = playerHeadToHead('KC', [112, 64, 90], ['2026-01-04'], 50);
check('a short dates array truncates rather than mispairing',
  mismatch.meetings.length === 1 && mismatch.meetings[0]!.date === '2026-01-04',
  JSON.stringify(mismatch.meetings));

// The one-game case the NFL schedule produces for 85% of pairs: it renders,
// and it renders as 1 of 1 rather than as a bare 100%.
const single = playerHeadToHead('KC', [112], ['2026-01-04'], 90);
check('a single meeting is 1 of 1 at 100%',
  single.bucket.games === 1 && single.bucket.hits === 1 && single.bucket.hitRate === 1);

// No meeting at all is still an ANSWER — the card names the opponent and says
// they have not met, so the opponent has to survive an empty values array.
const none = playerHeadToHead('KC', [], [], 90);
check('no meetings → games 0, rate null, opponent kept',
  none.bucket.games === 0 && none.bucket.hitRate === null && none.opponent === 'KC',
  JSON.stringify(none.bucket));

// A non-finite value (a NULL that slipped through as NaN) is dropped from both
// the list and the denominator rather than counted as a zero-yard game.
const nan = playerHeadToHead('KC', [112, NaN], ['2026-01-04', '2025-11-10'], 90);
check('NaN is dropped from the denominator', nan.bucket.games === 1, JSON.stringify(nan.bucket));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
