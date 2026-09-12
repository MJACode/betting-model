import { useCallback, useEffect, useState } from 'react';

/**
 * The games the user is looking at, shared by the Picks and Stats tabs.
 *
 * Matt, 2026-09-09: the game filter *"should be on picks and stats filter"* —
 * one selection, so picking tonight's SEA-NE on either tab narrows the other to
 * the same two teams and their bets.
 *
 * Same module-level store + listener pattern as `useSportFilter` and
 * `useKellySettings`, and for the same reason: two tabs mounted at once have to
 * see one value, and a context provider for a Set of ids is more wiring than
 * the value is worth.
 *
 * DELIBERATELY NOT PERSISTED — see lib/gameFilter. A `game_id` names one
 * fixture on one date, so a stored selection filters tonight's board by last
 * night's games and does it silently: the board renders empty and correct, and
 * nothing on screen says the reason is yesterday's filter. Sport changes clear
 * it for the same reason.
 */

const listeners = new Set<(s: Set<string>) => void>();
let selected = new Set<string>();
/** Which sport the current selection belongs to, so a switch can drop it. */
let selectionSport: string | null = null;

function publish(next: Set<string>): void {
  selected = next;
  for (const fn of listeners) fn(selected);
}

/** Replace the selection wholesale (the sheet's Clear, and slate pruning). */
export function setGameSelection(next: Set<string>, sport: string): void {
  selectionSport = sport;
  publish(new Set(next));
}

export function useGameSelection(sport: string) {
  const [value, setValue] = useState<Set<string>>(() =>
    selectionSport === null || selectionSport === sport ? selected : new Set<string>(),
  );

  useEffect(() => {
    const fn = (s: Set<string>) => setValue(s);
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  }, []);

  // A selection belongs to the sport it was made on. Cleared on a switch
  // rather than filtered, because the ids simply do not exist on the new
  // board and every one of them would filter it to nothing.
  useEffect(() => {
    if (selectionSport !== null && selectionSport !== sport && selected.size > 0) {
      setGameSelection(new Set<string>(), sport);
    } else {
      selectionSport = sport;
    }
  }, [sport]);

  const toggle = useCallback(
    (gameId: string) => {
      const next = new Set(selected);
      if (next.has(gameId)) next.delete(gameId);
      else next.add(gameId);
      setGameSelection(next, sport);
    },
    [sport],
  );

  const clear = useCallback(() => setGameSelection(new Set<string>(), sport), [sport]);

  const replace = useCallback(
    (next: Set<string>) => setGameSelection(next, sport),
    [sport],
  );

  return { selected: value, toggle, clear, replace };
}

/** Test seam — resets the module store between runs. */
export function __resetGameSelection(): void {
  selected = new Set<string>();
  selectionSport = null;
  listeners.clear();
}
