/**
 * Stats board accessibility for the three #1091 Lows.
 *
 * Pure — no React Native import — so scripts/verify_stats_board_a11y.ts and
 * the pytest pin can load it under plain `node --experimental-strip-types`.
 *
 * The notes stay behind one ⓘ (Matt, 2026-10-29). These helpers only decide
 * how that ⓘ is spoken, when the inline bet headline may wrap, and when the
 * "Change your sportsbooks" action may present the picker.
 */

/**
 * Same cut as the window strip stacking its mode tabs. Accessibility
 * Dynamic Type sizes sit above this; the default sizes do not.
 */
export const HEADLINE_WRAP_FONT_SCALE = 1.4;

/**
 * How long to wait after Modal `onDismiss` before presenting the picker.
 * The callback runs when the fade finishes, and iOS still refuses a new
 * modal in that same turn.
 */
export const PICKER_AFTER_DISMISS_MS = 100;

/**
 * If `onDismiss` never arrives, open the picker this long after the tap.
 * Longer than the sheet fade plus `PICKER_AFTER_DISMISS_MS`, so the normal
 * path always wins and this only covers a dropped callback.
 */
export const SHEET_DISMISS_FALLBACK_MS = 700;

/** 1 at default type. `undefined` drops the cap so the bet name can wrap. */
export function lineHeadlineNumberOfLines(fontScale: number): number | undefined {
  const scale = Number.isFinite(fontScale) && fontScale > 0 ? fontScale : 1;
  return scale >= HEADLINE_WRAP_FONT_SCALE ? undefined : 1;
}

/**
 * VoiceOver label for the board-notes ⓘ. `missingPriceReason` is set only
 * when the price column is absent — the sentence that says why. A hint can
 * be switched off, and the old label only said how many notes were behind
 * the icon. A one-sided book note is not this: the column is still on screen.
 */
export function boardNotesAccessibilityLabel(
  noteCount: number,
  missingPriceReason: string | null | undefined,
): string {
  const n = Number.isFinite(noteCount) ? Math.max(0, Math.floor(noteCount)) : 0;
  const noun = n === 1 ? 'note' : 'notes';
  const base = `About this board, ${n} ${noun}`;
  const reason = missingPriceReason?.trim() ?? '';
  if (!reason) return base;
  return `${base}, including why prices are missing. ${reason}`;
}

export type PickerHandoffPhase = 'idle' | 'armed' | 'opened';

export type PickerHandoffEvent = 'tap-ios' | 'tap-other' | 'release' | 'fallback';

export type PickerHandoffStep = {
  phase: PickerHandoffPhase;
  /** Present the sportsbook picker. */
  openPicker: boolean;
  /** Close the About sheet. */
  closeSheet: boolean;
  /** Start the timer that opens the picker if onDismiss never fires. */
  armFallback: boolean;
};

/**
 * Sheet → picker. iOS cannot present a Modal while another is fading out,
 * so the tap only arms a hand-off and the picker opens from the sheet's
 * `onDismiss` (`release`). Any other platform opens immediately. A second
 * `release` does not open the picker again. `fallback` presents if `onDismiss`
 * never arrives, and leaves the hand-off armed so a late dismiss can present
 * again — an early present can be refused while the sheet is still up.
 */
export function reducePickerHandoff(phase: PickerHandoffPhase, event: PickerHandoffEvent): PickerHandoffStep {
  if (event === 'tap-ios') {
    if (phase === 'armed') {
      return { phase, openPicker: false, closeSheet: true, armFallback: false };
    }
    return { phase: 'armed', openPicker: false, closeSheet: true, armFallback: true };
  }
  if (event === 'tap-other') {
    return { phase: 'opened', openPicker: true, closeSheet: true, armFallback: false };
  }
  if (event === 'fallback') {
    if (phase !== 'armed') {
      return { phase, openPicker: false, closeSheet: false, armFallback: false };
    }
    return { phase: 'armed', openPicker: true, closeSheet: false, armFallback: false };
  }
  if (phase === 'armed') {
    return { phase: 'opened', openPicker: true, closeSheet: false, armFallback: false };
  }
  return { phase, openPicker: false, closeSheet: false, armFallback: false };
}
