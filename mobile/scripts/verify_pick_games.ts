/**
 * A pick whose game row moved to another date still gets its game.
 *
 * Run: npx tsx scripts/verify_pick_games.ts
 *
 * 2026-11-15: NCAAB Washington @ Utah was bet "Utah ML" at 10:05 AM ET for a
 * 2 PM ET tip. The game had been postponed to Dec 5, and at 22:11 UTC the
 * ESPN ingest moved its games row to game_date 2026-12-05. The Picks board
 * reads games by the board's date, so the card had no game: no matchup, and
 * a headline of a bare "ML". The fix asks for the missing games by id.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { fillMissingGames, missingGameIds } from '../src/lib/pickGames';
import { signalsBetHeadline } from '../src/lib/signalsCard';
import type { GameRow } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const UTAH = 'NCAAB_2026-11-14_washington_utah';
const utahGame = {
  game_id: UTAH,
  sport: 'NCAAB',
  game_date: '2026-12-05',
  home_team: 'Utah',
  away_team: 'Washington',
  commence_time: '2026-12-06T00:00:00Z',
} as unknown as GameRow;
const otherGame = {
  game_id: 'NCAAB_2026-11-15_cal-poly_montana-state',
  sport: 'NCAAB',
  game_date: '2026-11-15',
  home_team: 'Montana State',
  away_team: 'Cal Poly',
} as unknown as GameRow;

// The picks the board read for 2026-11-15, as stored (pick_id 4498275 and
// 4498274 are both on the moved game).
const picks = [
  { game_id: UTAH, pick_side: 'home', pick_label: 'Utah ML' },
  { game_id: UTAH, pick_side: 'home', pick_label: 'Utah -2.5' },
  { game_id: otherGame.game_id, pick_side: 'under', pick_label: 'First Half Under 80.5' },
];

const headline = (game: GameRow | undefined) =>
  signalsBetHeadline({
    side: 'home',
    line: null,
    market: 'h2h',
    homeTeam: game?.home_team ?? '',
    awayTeam: game?.away_team ?? '',
    player: null,
    stat: null,
    label: 'Utah ML',
  });

async function main() {
  // The by-date read returned only the game still dated 2026-11-15.
  const byDate = () => new Map<string, GameRow>([[otherGame.game_id, otherGame]]);

  // ── the reported bug, reproduced ────────────────────────────────────────
  check('without the game the card says a bare "ML"', headline(byDate().get(UTAH)) === 'ML',
    headline(byDate().get(UTAH)));

  // ── the fix ─────────────────────────────────────────────────────────────
  const asked: string[][] = [];
  const map = byDate();
  await fillMissingGames(picks, map, async (ids) => {
    asked.push(ids);
    return { data: [utahGame], error: null };
  });
  check('the moved game is asked for by id, once', JSON.stringify(asked) === JSON.stringify([[UTAH]]),
    JSON.stringify(asked));
  check('the card gets its game back', map.get(UTAH)?.home_team === 'Utah');
  check('the headline names the team: "Utah ML"', headline(map.get(UTAH)) === 'Utah ML',
    headline(map.get(UTAH)));
  check('a game the date read returned is untouched', map.get(otherGame.game_id) === otherGame);

  // ── no extra read on a normal day ───────────────────────────────────────
  let calls = 0;
  const full = new Map<string, GameRow>([[UTAH, utahGame], [otherGame.game_id, otherGame]]);
  await fillMissingGames(picks, full, async () => {
    calls++;
    return { data: [], error: null };
  });
  check('no read when every game is already there', calls === 0, `calls=${calls}`);
  check('missingGameIds ignores an empty id', missingGameIds([{ game_id: '' }, { game_id: null }], new Map()).length === 0);

  // ── a failed read leaves the board as it was ────────────────────────────
  const errMap = byDate();
  await fillMissingGames(picks, errMap, async () => ({ data: null, error: new Error('503') }));
  check('an error result adds nothing and does not throw', !errMap.has(UTAH) && errMap.size === 1);
  const throwMap = byDate();
  let threw = false;
  try {
    await fillMissingGames(picks, throwMap, async () => {
      throw new Error('network');
    });
  } catch {
    threw = true;
  }
  check('a thrown read does not take the board down', !threw && !throwMap.has(UTAH));

  // ── every board that pairs by-date games with picks asks for the rest ──
  const src = readFileSync(join(import.meta.dirname, '..', 'src', 'lib', 'queries.ts'), 'utf-8');
  for (const fn of [
    'fetchPicksForDate',
    'fetchUpcomingUfcPicks',
    'fetchUpcomingTennisPicks',
    'fetchUpcomingNflPicks',
    'fetchUpcomingNcaafPicks',
    'fetchUpcomingNhlPicks',
  ]) {
    const start = src.indexOf(`export async function ${fn}(`);
    const next = src.indexOf('\nexport ', start + 1);
    const body = src.slice(start, next === -1 ? undefined : next);
    check(`${fn} fills the games its date read missed`, start >= 0 && body.includes('await fillMissingGames('));
  }

  if (failures > 0) {
    console.log(`\n${failures} check(s) failed`);
    process.exit(1);
  }
  console.log('\nall checks passed');
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
