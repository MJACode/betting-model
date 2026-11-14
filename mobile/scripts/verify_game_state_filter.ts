/**
 * The GAME STATUS filter on the Picks board (Not started / Live / Final).
 *
 * Run with:  npx tsx scripts/verify_game_state_filter.ts
 *
 * Matt, 2026-11-14: "You should be able to filter on games that are live or
 * not played yet." What this pins:
 *
 *   1. EMPTY MEANS EVERY STATE — the default hides nothing.
 *   2. THE STATE COMES FROM gameStatus(), the function the card draws with —
 *      'ended' (clock ran out, no score) counts as Final, not Live.
 *   3. THE CHIPS ONLY OFFER STATES THE BOARD HOLDS, in game order, with counts.
 *   4. AN IMPOSSIBLE SELECTION WIDENS, IT DOES NOT EMPTY.
 *   5. THE SCREEN APPLIES IT, the bar shows it, and Clear all clears it.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  effectiveGameStateSelection,
  gameStateOf,
  gameStateOptionsFor,
  gameStateSummary,
  gameStatesAreNarrowed,
  isGameStateSelected,
  type GameState,
} from '../src/lib/gameStateFilter';
import { gameStatus } from '../src/lib/format';

const ROOT = join(import.meta.dirname, '..');
const read = (p: string) => readFileSync(join(ROOT, p), 'utf-8');

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

// 1. Empty = everything.
const none = new Set<GameState>();
check('empty selection keeps every state',
  (['upcoming', 'live', 'final'] as GameState[]).every((s) => isGameStateSelected(s, none)));

// 2. Mapping through the card's own gameStatus().
const future = new Date(Date.now() + 3 * 3600_000).toISOString();
const started = new Date(Date.now() - 20 * 60_000).toISOString();
const longAgo = new Date(Date.now() - 2 * 86400_000).toISOString();
check('future kickoff -> upcoming',
  gameStateOf(gameStatus({ sport: 'NCAAF', commence_time: future } as never)) === 'upcoming');
check('kicked off 20 min ago -> live',
  gameStateOf(gameStatus({ sport: 'NCAAF', commence_time: started } as never)) === 'live');
check('clock window run out, no score -> final (not live)',
  gameStateOf(gameStatus({ sport: 'NCAAF', commence_time: longAgo } as never)) === 'final');
check('scored game -> final',
  gameStateOf(gameStatus({ sport: 'NCAAF', commence_time: longAgo, home_score: 21, away_score: 14 } as never)) === 'final');
check('no game row -> upcoming', gameStateOf(gameStatus(null)) === 'upcoming');

// 3. Options.
const opts = gameStateOptionsFor(['final', 'upcoming', 'upcoming', 'live'] as GameState[]);
check('options in game order with counts',
  JSON.stringify(opts.map((o) => [o.state, o.count])) === JSON.stringify([['upcoming', 2], ['live', 1], ['final', 1]]),
  JSON.stringify(opts));
check('absent state not offered', gameStateOptionsFor(['upcoming'] as GameState[]).length === 1);

// The ask itself: Not started + Live.
const bettable = new Set<GameState>(['upcoming', 'live']);
check('Not started + Live hides Final', !isGameStateSelected('final', bettable)
  && isGameStateSelected('live', bettable) && isGameStateSelected('upcoming', bettable));
check('narrowed + summary', gameStatesAreNarrowed(bettable, opts)
  && gameStateSummary(bettable, opts) === 'Not started, Live', gameStateSummary(bettable, opts));

// 4. Impossible selection widens.
const liveOnly = gameStateOptionsFor(['live', 'live'] as GameState[]);
const finalPicked = new Set<GameState>(['final']);
check('impossible selection reads as all',
  effectiveGameStateSelection(finalPicked, liveOnly).size === 0
  && gameStateSummary(finalPicked, liveOnly) === 'All'
  && !gameStatesAreNarrowed(finalPicked, liveOnly));

// 5. Wiring.
const screen = read('src/screens/PicksHomeScreen.tsx');
const filters = read('src/components/filters/PickFilters.tsx');
check('screen applies the cut to the board', /isDateSelected\(d\.pick\.game_date, selectedDates\) && statusOk\(d\)/.test(screen));
check('screen passes the cut to the sheet', screen.includes('onToggleGameState={toggleState}'));
check('screen drops the cut on a sport switch', /setPickedStates\(new Set\(\)\);\s*\}, \[sport\]\)/.test(screen));
check('sheet shows a pill and counts it', filters.includes("key: 'gameStates'") && filters.includes('(statesNarrowed ? 1 : 0)'));
check('Clear all clears it', /onClearGameStates\?\.\(\);/.test(filters));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
