/**
 * How a finished pick did, for the card (Matt, 2026-11-15: completed games
 * come back on the Picks board through the Status filter's Final chip, and
 * the card says how the pick went once it is graded).
 *
 * The units are the posted stake's — `postedPickUnits`, the same number the
 * Yesterday's results recap and the Record tab add — so a card can never
 * disagree with the record it feeds. Only a BET has a result to show: an
 * AVOID or a dead-zone row was never staked, and a paused model's
 * unposted row is shown for reference, not as a bet.
 */
import { formatSigned } from '@/lib/format';
import { postedPickUnits } from '@/lib/thresholds';
import { unitsSpeech } from '@/lib/a11y';

export type PickResult = 'WIN' | 'LOSS' | 'PUSH';

export interface PickResultView {
  result: PickResult;
  /** "W" / "L" / "P" — the letter the results recap draws. */
  letter: string;
  /** "+0.91u" / "−1.10u" / "0u". */
  unitsText: string;
  /** "Win, plus 0.91 units" — the card speaks it after the game status. */
  spoken: string;
}

const LETTER: Record<PickResult, string> = { WIN: 'W', LOSS: 'L', PUSH: 'P' };
const WORD: Record<PickResult, string> = { WIN: 'Win', LOSS: 'Loss', PUSH: 'Push' };

export function pickResultView(
  pick: {
    signal_type?: string | null;
    result?: string | null;
    kelly_fraction?: number | null;
    dk_odds?: number | null;
    decision_odds?: number | null;
    stake_units?: number | null;
  },
  paused = false,
): PickResultView | null {
  if (paused || pick.signal_type !== 'BET') return null;
  const r = pick.result;
  if (r !== 'WIN' && r !== 'LOSS' && r !== 'PUSH') return null;
  const unitsText = formatSigned(postedPickUnits(pick).units, 2, 'u');
  return {
    result: r,
    letter: LETTER[r],
    unitsText,
    spoken: `${WORD[r]}, ${unitsSpeech(unitsText)}`,
  };
}
