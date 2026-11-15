/**
 * The GAME STATUS filter on the Picks board (Not started / Live / Final).
 *
 * Run with:  npx tsx scripts/verify_game_state_filter.ts
 *
 * Matt, 2026-11-14: "You should be able to filter on games that are live or
 * not played yet." What this pins:
 *
 *   1. EMPTY MEANS EVERY STATE BUT FINAL — Final is opt-in (Matt,
 *      2026-11-15: finished games come back only when Final is picked).
 *   2. THE STATE COMES FROM gameStatus(), the function the card draws with —
 *      'ended' (clock ran out, no score) counts as Final, not Live.
 *   3. THE CHIPS ONLY OFFER STATES THE BOARD HOLDS, in game order, with counts.
 *   4. AN IMPOSSIBLE SELECTION WIDENS, IT DOES NOT EMPTY.
 *   5. THE SCREEN APPLIES IT, the bar shows it, and Clear all clears it.
 *   6. TODAY'S FINISHED GAMES reach the board only through Final, never the
 *      open board other surfaces read, and a graded BET says how it did.
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
import { pickResultView } from '../src/lib/pickResult';

const ROOT = join(import.meta.dirname, '..');
const read = (p: string) => readFileSync(join(ROOT, p), 'utf-8');

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

// 1. Empty = everything still to play or in play; Final only when picked.
const none = new Set<GameState>();
check('empty selection keeps Not started and Live',
  isGameStateSelected('upcoming', none) && isGameStateSelected('live', none));
check('empty selection hides Final', !isGameStateSelected('final', none));
check('picking Final shows Final', isGameStateSelected('final', new Set<GameState>(['final'])));

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
// Picking both is the default board, so it is named but is not a narrowing.
check('Not started + Live: named, same as the default', !gameStatesAreNarrowed(bettable, opts)
  && gameStateSummary(bettable, opts) === 'Not started, Live', gameStateSummary(bettable, opts));

// 4. Impossible selection widens.
const liveOnly = gameStateOptionsFor(['live', 'live'] as GameState[]);
const finalPicked = new Set<GameState>(['final']);
check('impossible selection reads as all',
  effectiveGameStateSelection(finalPicked, liveOnly).size === 0
  && gameStateSummary(finalPicked, liveOnly) === 'All'
  && !gameStatesAreNarrowed(finalPicked, liveOnly));

// 4b. The default with finished games on the board names what it hides, and
// is not a narrowing (no pill); picking Final is one.
const three = gameStateOptionsFor(['upcoming', 'live', 'final'] as GameState[]);
check('default summary says Final is hidden', gameStateSummary(none, three) === 'Final hidden', gameStateSummary(none, three));
check('default is not narrowed', !gameStatesAreNarrowed(none, three));
check('default summary is All with no finished games',
  gameStateSummary(none, gameStateOptionsFor(['upcoming', 'live'] as GameState[])) === 'All');
const finalOnly = new Set<GameState>(['final']);
check('Final picked is narrowed, named', gameStatesAreNarrowed(finalOnly, three) && gameStateSummary(finalOnly, three) === 'Final');
const everything = new Set<GameState>(['upcoming', 'live', 'final']);
check('all three picked reads All and is a change from the default',
  gameStateSummary(everything, three) === 'All' && gameStatesAreNarrowed(everything, three));
check('Final picked when only finished games exist is still a change',
  gameStatesAreNarrowed(finalOnly, gameStateOptionsFor(['final'] as GameState[])));

// 6a. The result chip.
const bet = { signal_type: 'BET', kelly_fraction: 0.02, decision_odds: -110, dk_odds: -110, stake_units: null };
const w = pickResultView({ ...bet, result: 'WIN' });
const l = pickResultView({ ...bet, result: 'LOSS' });
const pu = pickResultView({ ...bet, result: 'PUSH' });
check('WIN -> W, positive units', w?.letter === 'W' && w.unitsText.startsWith('+'), JSON.stringify(w));
check('LOSS -> L, negative units', l?.letter === 'L' && l.unitsText.startsWith('\u2212'), JSON.stringify(l));
check('PUSH -> P, zero', pu?.letter === 'P' && !/[1-9]/.test(pu.unitsText), JSON.stringify(pu));
check('ungraded BET -> no chip', pickResultView({ ...bet, result: null }) === null);
check('a no-bet row -> no chip', pickResultView({ ...bet, signal_type: 'NONE', result: 'WIN' }) === null);
check('a paused card -> no chip', pickResultView({ ...bet, result: 'WIN' }, true) === null);

// 5. Wiring.
const screen = read('src/screens/PicksHomeScreen.tsx');
const filters = read('src/components/filters/PickFilters.tsx');
check('screen applies the cut to the board', /isDateSelected\(d\.pick\.game_date, selectedDates\) && statusOk\(d\)/.test(screen));
check('screen passes the cut to the sheet', screen.includes('onToggleGameState={toggleState}'));
check('screen drops the cut on a sport switch', /setPickedStates\(new Set\(\)\);\s*\}, \[sport\]\)/.test(screen));
check('sheet shows a pill and counts it', filters.includes("key: 'gameStates'") && filters.includes('(statesNarrowed ? 1 : 0)'));
check('Clear all clears it', /onClearGameStates\?\.\(\);/.test(filters));

// 6b. Finished games: kept apart at the source, merged only on this board.
const hook = read('src/hooks/useTodayPicks.ts');
check('the open board other surfaces read excludes finished games',
  hook.includes('setData(open.filter(') && hook.includes('setPausedData(open.filter('));
check('finished games are returned apart', hook.includes('finishedData: board.finishedData'));
check('the board merges them, and the status cut gates them',
  screen.includes('[...activeItems, ...finishedItems]') && /boardItems\.filter\(\(d\) => isDateSelected/.test(screen));
check('header counts and Bet all do not read the finished half',
  !/signalCountsBySport\([^)]*finished/.test(screen) && !/todayStats[\s\S]{0,200}finished/.test(screen));
check('the section shows whenever a finished game is on the board',
  filters.includes("gameStateOptions.some((o) => o.state === 'final')"));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
