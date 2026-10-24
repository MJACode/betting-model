/**
 * Model-badge box. It sizes to the label, from 56pt to 112pt. A fixed 112
 * left the name about 96pt, and at large text that split words mid-way
 * ("Moneyline", "Spreads").
 *
 * The badge moves above the name at 1.3× text, or when the window is under
 * 360pt. 1.3× is the measured point: at 1.3× on a 393pt screen, "Completions"
 * beside "Pass Comp" is 135pt in a 126pt column (Inter SemiBold).
 *
 * From 1.5×, and from 1.3× on a narrow window, the record column moves under
 * the name. The left column alone is 162pt on a 320pt phone, and "Moneyline"
 * at 2× headline is 171pt. The name then uses the full card width (264pt on
 * that phone), which holds every model-name word through 2×.
 */

/** Shortest badge box. "TT" and "ML" sit in this, so a short chip still reads as a chip. */
export const MODEL_BADGE_MIN = 56;
/** Longest badge box. A longer label shrinks onto one line inside it. */
export const MODEL_BADGE_MAX = 112;
/** Horizontal padding inside the chip (8 + 8). The label shrinks inside the rest. */
export const MODEL_BADGE_PAD = 16;
/** Text size at which a badge beside the name splits a word. */
export const MODEL_BADGE_STACK_SCALE = 1.3;
/** Text size at which the record column also has to move under the name. */
export const MODEL_RECORD_BELOW_SCALE = 1.5;
/** Below this window width the badge stacks even at 1×. 320 stacks; 393 does not. */
export const MODEL_BADGE_NARROW_WIDTH = 360;

export function stackModelBadge(fontScale: number, windowWidth: number): boolean {
  return fontScale >= MODEL_BADGE_STACK_SCALE || windowWidth < MODEL_BADGE_NARROW_WIDTH;
}

export function modelRecordBelow(fontScale: number, windowWidth: number): boolean {
  if (fontScale >= MODEL_RECORD_BELOW_SCALE) return true;
  return fontScale >= MODEL_BADGE_STACK_SCALE && windowWidth < MODEL_BADGE_NARROW_WIDTH;
}

/**
 * Models list, left of the record column.
 * 32pt row margins + 24pt card padding + 12pt gap + 90pt record column.
 */
export const MODELS_LIST_CHROME = 32 + 24 + 12 + 90;

/** Margins and card padding only. Used once the record sits under the name. */
export const MODELS_LIST_INSET = 32 + 24;

export function modelsListLeftWidth(windowWidth: number): number {
  return windowWidth - MODELS_LIST_CHROME;
}

/** Chip width for a label already measured at the current text size. */
export function badgeBoxWidth(textWidth: number): number {
  return Math.min(MODEL_BADGE_MAX, Math.max(MODEL_BADGE_MIN, textWidth + MODEL_BADGE_PAD));
}

/** Width the model name can use on a Models-list row. */
export function modelsListNameWidth(
  windowWidth: number,
  fontScale: number,
  badgeTextWidth: number,
): number {
  if (modelRecordBelow(fontScale, windowWidth)) return windowWidth - MODELS_LIST_INSET;
  const left = modelsListLeftWidth(windowWidth);
  if (stackModelBadge(fontScale, windowWidth)) return left;
  return left - 8 - badgeBoxWidth(badgeTextWidth);
}
