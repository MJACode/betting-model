/**
 * The Stats board's LEADERBOARD reads survive the row cap.
 *
 * Run with:  npx tsx scripts/verify_leaderboard_reads.ts
 *
 * verify_row_cap.ts pinned the four all-books LINE reads after the 2026-09-04
 * truncation. The per-player reads behind the board itself were never paged
 * and are all over the same cap — measured 2026-09-09 against production:
 *
 *     player_recent_games_ncaaf(2025, 10)      54,687 rows
 *     player_recent_games_nfl(2025, 10)        12,850 rows   (5.7 MB)
 *     player_window_totals_ncaaf(2025, 10)     12,204
 *     player_recent_games_mlb(2026, b, 10)      6,216
 *     player_recent_games_nba(2026, 10)         5,447
 *     player_recent_games_wnba(2026, 10)        2,074
 *     player_season_stat_values_nfl(2025, ...)  1,798
 *     v_player_season_totals_mlb (2026)         1,568
 *     player_window_totals_nfl(2025, 10)        1,123
 *
 * So every board was drawing an arbitrary first 1,000 rows. It showed up on
 * the NFL board because that one OPENS filtered to the slate: of the 136
 * players who survived the cap, 6 played tonight's SEA-NE opener and not one
 * was a quarterback, so the default Pass Yards board was empty while both
 * starters had a full 10-game log in the table.
 *
 * Paging alone is not the fix — draining 54,687 rows onto a phone to render
 * the players in one game is its own bug — so a board already filtered to a
 * slate asks the server for that slate (statsBoard.slateTeams). Both halves
 * are checked here: the narrowing must agree with the client-side filter it
 * replaces, and the read must still drain the cap when there is no narrowing.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { fetchAllPages } from '../src/lib/paging';
import { buildTonightSlate, isOnSlate, slateTeams } from '../src/lib/statsBoard';
import type { GameRow } from '../src/types';

const ROOT = join(import.meta.dirname, '..');
const read = (p: string) => readFileSync(join(ROOT, p), 'utf-8');

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const game = (over: Partial<GameRow>): GameRow =>
  ({
    game_id: 'g',
    sport: 'NFL',
    season: 2026,
    game_date: '2026-09-09',
    home_team: 'SEA',
    away_team: 'NE',
    commence_time: '2026-09-10T00:20:00+00:00',
    ...over,
  }) as GameRow;

/** A PostgREST that holds `total` rows and never returns more than `cap`. */
function fakeServer<T>(rows: T[], cap: number) {
  let calls = 0;
  const page = (from: number, to: number) => {
    calls++;
    const end = Math.min(to + 1, from + cap, rows.length);
    return Promise.resolve({ data: rows.slice(from, end) as unknown[], error: null });
  };
  return { page, calls: () => calls };
}

async function main() {
  // ── the slate narrowing ────────────────────────────────────────────────────
  const nflSlate = buildTonightSlate([game({})], 'NFL', '2026-09-09');
  check('tonight is the NFL slate', nflSlate.date === '2026-09-09' && nflSlate.isToday);

  check(
    'a slate-filtered NFL board narrows to its two teams',
    JSON.stringify(slateTeams('NFL', nflSlate, true)?.slice().sort()) === '["NE","SEA"]',
  );
  check('an unfiltered board reads the whole league', slateTeams('NFL', nflSlate, false) === null);

  // UFC's slate keys are FIGHTER NAMES and its rows carry no team, so a team
  // narrowing there would return nothing at all.
  const ufcSlate = buildTonightSlate(
    [game({ sport: 'UFC', home_team: 'Jon Jones', away_team: 'Tom Aspinall' })],
    'UFC',
    '2026-09-09',
  );
  check('UFC never narrows on team', slateTeams('UFC', ufcSlate, true) === null);
  check('an empty slate never narrows', slateTeams('NFL', buildTonightSlate([], 'NFL', '2026-09-09'), true) === null);

  // The narrowing REPLACES a read the client already filters — the two must
  // pick the same rows, or the board silently disagrees with itself.
  {
    const rows = [
      { player_id: '1', player_name: 'Sam Darnold', team: 'SEA' },
      { player_id: '2', player_name: 'Drake Maye', team: 'NE' },
      { player_id: '3', player_name: 'Patrick Mahomes', team: 'KC' },
      { player_id: '4', player_name: 'No Team', team: null },
    ];
    const teams = slateTeams('NFL', nflSlate, true)!;
    const server = rows.filter((r) => !!r.team && teams.includes(r.team)).map((r) => r.player_id);
    const client = rows.filter((r) => isOnSlate(r, nflSlate)).map((r) => r.player_id);
    check('server narrowing and isOnSlate select the same players', JSON.stringify(server) === JSON.stringify(client), `${server} vs ${client}`);
  }

  // ── the cap ────────────────────────────────────────────────────────────────
  // The shape of the bug: 1,163 NFL players ordered by player_id, tonight's
  // starters near the end of that order, a server that stops at 1,000.
  {
    const all = Array.from({ length: 1163 }, (_, i) => ({
      player_id: String(i).padStart(4, '0'),
      team: i >= 1100 ? (i % 2 ? 'SEA' : 'NE') : 'KC',
    }));
    const unpaged = await fakeServer(all, 1000).page(0, 19999);
    check(
      'ONE capped read loses every player in tonight\'s game (the bug)',
      (unpaged.data as typeof all).filter((r) => r.team !== 'KC').length === 0,
    );

    const drained = await fetchAllPages<(typeof all)[number]>(fakeServer(all, 1000).page, (r) => r.player_id);
    check('paging returns all 1,163', drained.length === 1163, `${drained.length}`);
    check(
      'and tonight\'s players are in it',
      drained.filter((r) => r.team !== 'KC').length === 63,
      `${drained.filter((r) => r.team !== 'KC').length}`,
    );

    // Narrowed, the same board is one page instead of two.
    const narrowed = all.filter((r) => r.team !== 'KC');
    const srv = fakeServer(narrowed, 1000);
    const got = await fetchAllPages<(typeof all)[number]>(srv.page, (r) => r.player_id);
    check('a narrowed read is one page of rows plus the empty proof', got.length === 63 && srv.calls() === 2, `${got.length} rows, ${srv.calls()} calls`);
  }

  // ── source ─────────────────────────────────────────────────────────────────
  const q = read('src/lib/queries.ts');
  const s = read('src/screens/StatsScreen.tsx');

  // Every per-player RPC the board reads, by name. A new one added without
  // paging fails here rather than shipping a 92%-empty board.
  const RPCS = [
    'player_recent_games_mlb',
    'player_recent_games_nba',
    'player_recent_games_wnba',
    'player_recent_games_nfl',
    'player_recent_games_ncaaf',
    'player_window_totals_mlb',
    'player_window_totals_nba',
    'player_window_totals_wnba',
    'player_window_totals_nfl',
    'player_window_totals_ncaaf',
    'player_season_stat_values_mlb',
    'player_season_stat_values_nba',
    'player_season_stat_values_wnba',
    'player_season_stat_values_nfl',
    'player_season_stat_values_ncaaf',
    'fighter_window_totals_ufc',
  ];
  check('no leaderboard RPC is called outside the pager', !/supabase\.rpc\(\s*'?player_(recent_games|window_totals|season_stat_values)/.test(q));
  check('nor is the UFC one', !/supabase\.rpc\(\s*'fighter_window_totals_ufc'/.test(q));
  for (const fn of RPCS) {
    // Named directly, or reached through the two-league `fn` ternaries.
    check(`${fn} is still read by the board`, q.includes(`'${fn}'`) || q.includes(`${fn}`));
  }
  check('pageRpc pages with .range(from, to)', /function pageRpc[\s\S]{0,900}\.range\(from, to\)/.test(q));
  check('pageRpc orders the REQUEST, not just the function body', /function pageRpc[\s\S]{0,900}\.order\(/.test(q));
  check('pageRpc narrows on team when the caller has a slate', /function pageRpc[\s\S]{0,900}\.in\('team'/.test(q));
  check('pageRpc drains through fetchAllPages', /function pageRpc[\s\S]{0,900}fetchAllPages</.test(q));

  // The season-totals VIEWS are the same read by another route. Checked at the
  // `.from(...)` rather than at the name, because the two football views are
  // picked by a ternary well above the read that uses them.
  for (const view of [
    'v_player_season_totals_nfl',
    'v_player_season_totals_ncaaf',
    'v_player_season_totals_mlb',
    'v_player_season_totals_nba',
    'v_player_season_totals_wnba',
    'v_fighter_season_totals_ufc',
  ]) {
    check(`${view} is still read by the board`, q.includes(`'${view}'`));
  }
  // Scoped to fetchSeasonTotals. Each view is named at its own `.from(...)`
  // rather than through a `view` variable, so tests/test_anon_readable.py can
  // see the read at all — the two football views sat outside the read-surface
  // manifest for exactly as long as they were reached through one.
  const totalsAt = q.indexOf('export async function fetchSeasonTotals');
  const totalsBody = q.slice(totalsAt, q.indexOf('\n/**', totalsAt + 10));
  check('fetchSeasonTotals was found', totalsAt > 0 && totalsBody.length > 200, `${totalsBody.length} chars`);
  const totalsFrom = [...totalsBody.matchAll(/\.from\('(v_(?:player|fighter)_season_totals_[a-z]+)'\)/g)];
  check('six season-totals reads, each naming its own view', totalsFrom.length === 6, `${totalsFrom.length}`);
  for (const m of totalsFrom) {
    const at = m.index ?? 0;
    check(`${m[1]}: read inside fetchAllPages`, totalsBody.slice(Math.max(0, at - 700), at).includes('fetchAllPages<'));
    check(`${m[1]}: pages with .range(from, to)`, totalsBody.slice(at, at + 700).includes('.range(from, to)'));
  }

  // The screen has to wait for the slate, or its first read is the whole
  // league and is thrown away the moment the slate lands.
  check('the board waits for the slate before reading', /if \(!slateReady\) return;/.test(s));
  check('the slate releases the board even when it fails', /\.finally\(\(\) => \{[\s\S]{0,120}setSlateReady\(true\)/.test(s));
  for (const fn of ['fetchSeasonStatValues', 'fetchRecentGames', 'fetchWindowTotals']) {
    check(`${fn} is handed the slate teams`, new RegExp(`${fn}\\([^)]*, teams\\)`).test(s));
  }
  check('the narrowing comes from slateTeams, not a hand-rolled set', /slateTeams\(sport, slate, tonightActive\)/.test(s));

  console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILED`);
  process.exit(failures === 0 ? 0 : 1);
}

void main();
