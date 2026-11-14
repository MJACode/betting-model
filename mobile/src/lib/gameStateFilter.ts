/**
 * "Is the game still bettable?" — the GAME STATUS cut on the Picks board.
 *
 * Matt, 2026-11-14, from the NCAAF All board: *"You should be able to filter
 * on games that are live or not played yet."* The All board holds every pick
 * the model scored today, so by the afternoon the cards for games that are
 * already over sit between the ones that can still be bet.
 *
 * Three states, each derived from `gameStatus()` — the same function the cards
 * use to draw LIVE / FINAL — so a chip can never disagree with the card it
 * keeps: `pre` is Not started, `live` is Live, and `final` / `ended` are both
 * Final (`ended` is a game whose clock window has run out with no score yet).
 *
 * EMPTY MEANS EVERY STATE, the Date and Games contract: a filter that starts
 * by hiding the board is a broken screen. NOT PERSISTED for the same reason:
 * the cut is part of the session's slate, and a stored selection would
 * silently filter tomorrow's board.
 */

import type { GameStatus } from './format';

export type GameState = 'upcoming' | 'live' | 'final';

/** Fixed order — the order a game moves through them. */
export const GAME_STATES: GameState[] = ['upcoming', 'live', 'final'];

export const GAME_STATE_LABEL: Record<GameState, string> = {
  upcoming: 'Not started',
  live: 'Live',
  final: 'Final',
};

export interface GameStateOption {
  state: GameState;
  label: string;
  /** Picks on the board in this state. */
  count: number;
}

/** A card's `gameStatus()` → the filter's three states. */
export function gameStateOf(status: GameStatus): GameState {
  if (status.kind === 'live') return 'live';
  if (status.kind === 'final' || status.kind === 'ended') return 'final';
  return 'upcoming';
}

/** The states the picks on screen are in, in game order, each with its count. */
export function gameStateOptionsFor(states: Iterable<GameState>): GameStateOption[] {
  const counts = new Map<GameState, number>();
  for (const s of states) counts.set(s, (counts.get(s) ?? 0) + 1);
  return GAME_STATES.filter((s) => counts.has(s)).map((state) => ({
    state,
    label: GAME_STATE_LABEL[state],
    count: counts.get(state)!,
  }));
}

/** Is a pick in this state in the selection? Empty selection = every state. */
export function isGameStateSelected(state: GameState, selected: Set<GameState>): boolean {
  return selected.size === 0 || selected.has(state);
}

/**
 * The selection THIS board can honour — display only, never written back.
 * If none of the chosen states is on the board (Final picked on All, then the
 * reader opens Live Signals), the cut reads as every state rather than
 * emptying the board behind chips that show nothing selected. The same rule
 * as `effectiveDateSelection`.
 */
export function effectiveGameStateSelection(
  selected: Set<GameState>,
  options: GameStateOption[],
): Set<GameState> {
  if (selected.size === 0) return selected;
  for (const o of options) if (selected.has(o.state)) return selected;
  return new Set<GameState>();
}

/** Is the cut narrowing THIS board? */
export function gameStatesAreNarrowed(
  selected: Set<GameState>,
  options: GameStateOption[],
): boolean {
  if (selected.size === 0) return false;
  const shown = options.filter((o) => selected.has(o.state)).length;
  return shown > 0 && shown < options.length;
}

/** "All" / "Live" / "Not started, Live" — summary and pill label. */
export function gameStateSummary(selected: Set<GameState>, options: GameStateOption[]): string {
  const shown = options.filter((o) => selected.has(o.state));
  if (selected.size === 0 || shown.length === 0 || shown.length === options.length) return 'All';
  return shown.map((o) => o.label).join(', ');
}
