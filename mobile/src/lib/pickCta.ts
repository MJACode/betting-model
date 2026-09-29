/**
 * What a pick offers once its game has started — usability audit H5 (PR 3) —
 * and the Pick Detail reasoning heading (M14). Pure, so the verify script and
 * the pytest run it.
 *
 * H5: a PRE-GAME pick's edge, stake and CLV all come from the locked pre-game
 * price. After first pitch the one-tap "Bet DK −144" sent the user to an
 * in-play price the pick was never made at. So once the game has started:
 *   - the book hand-off becomes a non-interactive "Game started · picked at
 *     −125 DK" line (decision price + decision book);
 *   - the "Now" price tag reads "Live price" while the game is IN PLAY (not
 *     once it is over: a final game's price is not live);
 *   - Slip is hidden (a slip leg would be bet at the in-play price);
 *   - Track stays (tracking scores the pick at its lock).
 * Live in-play signals (is_live) are made in-game at DraftKings, so their CTA
 * is unchanged. Before the start the hand-off is always the best available
 * book (bestHandoffForPick), never DraftKings-only.
 *
 * A game called off before first pitch (gameStartState 'postponed') is not
 * "started": no "Game started" line, and no hand-off or Slip either — there is
 * no game to bet. Track stays.
 */
import { formatAmerican, gameStartState } from './format';

export interface PickCtaInput {
  /** pick.is_live — an in-play signal, made after the start by design. */
  isLive: boolean;
  /** gameHasStarted(game, liveState, pick.game_time). */
  started: boolean;
  /** The game is IN PLAY right now (gameStartState 'live'); drives "Live price". */
  inPlay?: boolean;
  /** Called off before first pitch (gameStartState 'postponed'). */
  postponed?: boolean;
}

export interface PickCta {
  /** The book hand-off may show (the card still applies its own BET / preview / paused rules). */
  handoff: boolean;
  /** Show "Game started · picked at …" where the hand-off would have been. */
  startedLine: boolean;
  /** Slip may show (ANDed with the card's own priced/open rules). */
  slip: boolean;
  /** Track may show (ANDed with the card's own open rule). Always true: Track stays. */
  track: boolean;
  /** The tag on the current-price pill. */
  priceTag: 'Now' | 'Live price';
}

export function pickCta({ isLive, started, inPlay = false, postponed = false }: PickCtaInput): PickCta {
  const lockedOut = started && !isLive;
  const calledOff = postponed && !isLive;
  return {
    handoff: !lockedOut && !calledOff,
    startedLine: lockedOut && !calledOff,
    slip: !lockedOut && !calledOff,
    track: true,
    priceTag: inPlay ? 'Live price' : 'Now',
  };
}

/** The card's and Pick Detail's CTA from the pick, its game row and live snapshot. */
export function pickCtaFor(
  pick: { is_live?: boolean | null; game_time?: string | null },
  game: Parameters<typeof gameStartState>[0],
  live: Parameters<typeof gameStartState>[1],
): PickCta {
  const s = gameStartState(game, live, pick.game_time);
  return pickCta({
    isLive: pick.is_live === true,
    started: s === 'live' || s === 'over',
    inPlay: s === 'live',
    postponed: s === 'postponed',
  });
}

/** "Game started · picked at −125 DK" — the decision price at the decision book. */
export function gameStartedLine(decisionPrice: number | null | undefined, decisionBookLabel: string): string {
  if (decisionPrice == null) return 'Game started';
  return `Game started · picked at ${formatAmerican(decisionPrice)} ${decisionBookLabel}`.trim();
}

/**
 * M14: "Why this bet?" only on a bet. A NONE is not a bet and an AVOID is a
 * reason not to bet; a paused model's or an unlocked preview's BET is shown
 * for reference, not as a signal.
 */
export function reasoningHeading(
  signal: string | null | undefined,
  opts: { paused?: boolean; preview?: boolean } = {},
): string {
  if (signal === 'AVOID') return 'Why avoid?';
  if (signal === 'BET') return opts.paused || opts.preview ? 'Why this pick?' : 'Why this bet?';
  return 'Why no bet?';
}
