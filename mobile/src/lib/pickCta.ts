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
 *   - the "Now" price tag reads "Live price";
 *   - Slip is hidden (a slip leg would be bet at the in-play price);
 *   - Track stays (tracking scores the pick at its lock).
 * Live in-play signals (is_live) are made in-game at DraftKings, so their CTA
 * is unchanged. Before the start the hand-off is always the best available
 * book (bestHandoffForPick), never DraftKings-only.
 */
import { formatAmerican } from './format';

export interface PickCtaInput {
  /** pick.is_live — an in-play signal, made after the start by design. */
  isLive: boolean;
  /** gameHasStarted(game, liveState). */
  started: boolean;
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

export function pickCta({ isLive, started }: PickCtaInput): PickCta {
  const lockedOut = started && !isLive;
  return {
    handoff: !lockedOut,
    startedLine: lockedOut,
    slip: !lockedOut,
    track: true,
    priceTag: started ? 'Live price' : 'Now',
  };
}

/** "Game started · picked at −125 DK" — the decision price at the decision book. */
export function gameStartedLine(decisionPrice: number | null | undefined, decisionBookLabel: string): string {
  if (decisionPrice == null) return 'Game started';
  return `Game started · picked at ${formatAmerican(decisionPrice)} ${decisionBookLabel}`.trim();
}

/**
 * The started line as VoiceOver should say it (audit PR 4): the full book
 * name, no "·" separator, and why there's no button — "Game started. Picked
 * at -125 at DraftKings. Betting links are off once a game starts."
 */
export function gameStartedSpeech(decisionPrice: number | null | undefined, decisionBookName: string): string {
  const picked =
    decisionPrice == null ? '' : ` Picked at ${formatAmerican(decisionPrice)}${decisionBookName ? ` at ${decisionBookName}` : ''}.`;
  return `Game started.${picked} Betting links are off once a game starts.`;
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
