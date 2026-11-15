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
 *      With Final on, the staked total and Bet all still exclude them.
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
  toggleGameState,
  type GameState,
} from '../src/lib/gameStateFilter';
import { gameStatus } from '../src/lib/format';
import { pickResultView } from '../src/lib/pickResult';
import { betAllCandidates } from '../src/lib/betAll';
import { decisionOdds } from '../src/lib/decisionPrice';
import { passesActionFilter, unitsFor } from '../src/lib/thresholds';
import type { EnrichedPick } from '../src/types';

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
check('all three picked names every state (never a bare "All" pill) and is a change',
  gameStateSummary(everything, three) === 'Not started, Live, Final' && gameStatesAreNarrowed(everything, three),
  gameStateSummary(everything, three));

// 4c. Tapping from the default: Final ADDS to the open board, it does not
// replace it; a lit Live chip tapped takes Live away (UX review, 2026-11-15).
const addFinal = toggleGameState(none, 'final');
check('Final from the default adds to Not started + Live',
  addFinal.has('upcoming') && addFinal.has('live') && addFinal.has('final'), JSON.stringify([...addFinal]));
const dropLive = toggleGameState(none, 'live');
check('Live from the default removes Live', dropLive.has('upcoming') && !dropLive.has('live') && !dropLive.has('final'));
check('the toggle never mutates its input', none.size === 0);
// The review's repro: Not started dropped ({live}), then every Live game
// ends. Live is no longer a chip, so the chips draw the default (Not
// started lit, Final off). The tap starts from that drawn set.
const ghost = new Set<GameState>(['live']);
const noLive = gameStateOptionsFor(['upcoming', 'final'] as GameState[]);
const drawn = effectiveGameStateSelection(ghost, noLive);
check('once Live is gone the chips draw Not started lit and Final off',
  drawn.size === 0 && isGameStateSelected('upcoming', drawn) && !isGameStateSelected('final', drawn));
const afterTap = toggleGameState(drawn, 'final');
check('a stale pick does not switch Not started off when Final is tapped',
  afterTap.has('upcoming') && afterTap.has('final') && isGameStateSelected('upcoming', afterTap),
  JSON.stringify([...afterTap]));
const rawTap = toggleGameState(ghost, 'final');
check('toggling the stored set would have dropped Not started',
  !rawTap.has('upcoming') && rawTap.has('live') && rawTap.has('final'), JSON.stringify([...rawTap]));
const liveStillOn = gameStateOptionsFor(['upcoming', 'live', 'final'] as GameState[]);
const liveOnlyTap = toggleGameState(effectiveGameStateSelection(ghost, liveStillOn), 'final');
check('a Live chip that is still lit stays the start, so Not started stays off',
  !liveOnlyTap.has('upcoming') && liveOnlyTap.has('live') && liveOnlyTap.has('final'),
  JSON.stringify([...liveOnlyTap]));
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
check('chips draw lit from the effective selection', filters.includes('active={isGameStateSelected(o.state, selectedGameStates)}'));
check('an all-over board offers Final, not "no picks yet"', screen.includes('actionLabel="Show Final"'));
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
check('Bet all reads the open subset, never a finished game',
  screen.includes('betAllCandidates(openFiltered,') && !screen.includes('betAllCandidates(filtered,'));
check('the staked total reads the open subset',
  screen.includes('return openFiltered.reduce(') && !screen.includes('return filtered.reduce('));
check('the open subset drops Final',
  screen.includes("filtered.filter((d) => stateByItem.get(d) !== 'final')"));
check('a tap toggles from the drawn selection',
  screen.includes('toggleGameState(effectiveGameStateSelection(prev, gameStateOptions), state)'));
check('the section shows whenever a finished game is on the board',
  filters.includes("gameStateOptions.some((o) => o.state === 'final')"));

// 6c. Final is on, so the filtered board holds an open bet and today's
// finished bets. The staked total and Bet all use the same exclusion the
// screen does (`state !== 'final'`): finished picks are not stakes and not
// Bet all rows. Reading the whole board first shows the ungraded finished
// bet would have been listed as started.
function boardPick(
  id: number,
  game: { sport: string; commence_time: string; home_score?: number; away_score?: number },
  stakeUnits: number,
  result: string | null,
): EnrichedPick {
  return {
    pick: {
      pick_id: id,
      pick_label: `NCAAF pick ${id}`,
      signal_type: 'BET',
      model_id: 'ncaaf_spread',
      sport: 'NCAAF',
      game_date: '2026-11-15',
      game_id: `g${id}`,
      model_probability: 0.62,
      edge: 0.08,
      dk_odds: -110,
      decision_odds: -110,
      kelly_fraction: 0.02,
      stake_units: stakeUnits,
      result,
      is_live: false,
      condition_status: null,
    },
    game,
    weather: null,
  } as unknown as EnrichedPick;
}
const openPick = boardPick(1, { sport: 'NCAAF', commence_time: future }, 1, null);
const ungradedFinal = boardPick(
  2, { sport: 'NCAAF', commence_time: longAgo, home_score: 28, away_score: 17 }, 2, null);
const gradedFinal = boardPick(
  3, { sport: 'NCAAF', commence_time: longAgo, home_score: 21, away_score: 14 }, 3, 'WIN');
const stateOf = (d: EnrichedPick) => gameStateOf(gameStatus(d.game));
const finalOn = new Set<GameState>(['upcoming', 'live', 'final']);
const withFinalOn = [openPick, ungradedFinal, gradedFinal].filter((d) =>
  isGameStateSelected(stateOf(d), finalOn));
check('Final on puts the finished picks on the filtered board', withFinalOn.length === 3
  && stateOf(openPick) === 'upcoming' && stateOf(ungradedFinal) === 'final' && stateOf(gradedFinal) === 'final');
const openOnly = withFinalOn.filter((d) => stateOf(d) !== 'final');
const stakeOf = (d: EnrichedPick) =>
  unitsFor(d.pick.kelly_fraction, decisionOdds(d.pick), d.pick.stake_units);
const staked = openOnly.reduce((sum, d) => sum + stakeOf(d), 0);
const finishedStake = stakeOf(ungradedFinal) + stakeOf(gradedFinal);
check('staked total with Final on is the open pick only',
  openOnly.length === 1 && openOnly[0] === openPick && staked === stakeOf(openPick) && finishedStake > staked,
  `staked=${staked} finished=${finishedStake}`);
check('the ungraded finished bet clears the action filter', passesActionFilter(ungradedFinal.pick));
const wholeBoard = betAllCandidates(withFinalOn, () => null, ['draftkings']);
const betAllOpen = betAllCandidates(openOnly, () => null, ['draftkings']);
const listed = (rows: { key: string }[], id: number) => rows.some((r) => r.key === String(id));
check('reading the whole board lists the ungraded finished bet as started',
  wholeBoard.skipped.some((s) => s.key === '2' && s.reason === 'started') && !listed(wholeBoard.picks, 2));
check('Bet all with Final on omits both finished picks',
  !listed(betAllOpen.picks, 2) && !listed(betAllOpen.skipped, 2)
  && !listed(betAllOpen.picks, 3) && !listed(betAllOpen.skipped, 3));
check('Bet all with Final on still has the open pick',
  listed(betAllOpen.picks, 1) || listed(betAllOpen.skipped, 1));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
