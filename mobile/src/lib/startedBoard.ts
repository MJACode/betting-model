/**
 * Where a Signals pick renders (Picks declutter, Matt 2026-11-27).
 *
 * `pre` stays on the main list. `live` and `final` fold into the Started
 * group. The same two reads the card uses — `gameStatus` (the Status filter)
 * and the Scoreboard feed — so a game the card would mark LIVE or FINAL
 * cannot stay in the main list.
 */
import { gameStatus } from '@/lib/format';
import { gameStateOf } from '@/lib/gameStateFilter';
import { feedView, type ScoreboardFeed } from '@/lib/scoreboard';
import type { GameRow, LiveGameStateRow } from '@/types';

export type StartedBoardKind = 'pre' | 'live' | 'final';

export function startedBoardKind(
  game: GameRow | null | undefined,
  live: LiveGameStateRow | null | undefined,
  feed: ScoreboardFeed | null | undefined,
): StartedBoardKind {
  const st = gameStateOf(gameStatus(game, live));
  const fed = feedView(game, feed);
  if (st === 'final' || fed?.kind === 'final') return 'final';
  if (st === 'live' || fed?.kind === 'live') return 'live';
  return 'pre';
}
