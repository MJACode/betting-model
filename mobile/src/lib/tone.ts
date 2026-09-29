/**
 * Colour ROLES for signed results and the signal badge, as theme token names.
 *
 * Pure (no react-native), so `scripts/verify_contrast_tokens.ts` can import it
 * and measure each pairing against the real hexes in theme.ts. Screens use
 * `pnlColor()` from theme.ts and `SignalBadge`, never these names directly.
 *
 * Usability audit 2026-09-25: H1 (badge ink + glyph), H2 (P&L text ink).
 */
import type { SignalType } from '@/types';

/** A text token that clears 4.5:1 on the ground it is paired with. */
export type InkToken = 'betInk' | 'avoidInk' | 'textSecondary';

/**
 * The value a signed result DISPLAYS: `value × scale` rounded to `digits`
 * decimals exactly as `toFixed` (and so `formatSigned`) rounds it. Missing or
 * non-finite → null. `-0` comes back for a tiny loss, and `-0 < 0` is false,
 * so it reads as zero.
 */
export function roundedAt(
  value: number | null | undefined,
  digits: number,
  scale = 1,
): number | null {
  // Number(): PostgREST can send NUMERIC as a string ("12.5").
  const n = Number(value);
  if (value == null || !Number.isFinite(n)) return null;
  return Number((n * scale).toFixed(digits));
}

/** True when the shown number is 0 at this precision ("0.0%", "$0.00"). */
export function roundsToZero(value: number | null | undefined, digits: number, scale = 1): boolean {
  return roundedAt(value, digits, scale) === 0;
}

/**
 * Gain → betInk, loss → avoidInk, zero / push / missing → textSecondary.
 *
 * The tone comes from the ROUNDED value the screen prints, never the raw one,
 * so the colour always agrees with the sign: pass the display's `digits` and
 * `scale` (a ratio shown by `formatPctSigned` is `digits = 1, scale = 100`;
 * dollars by `formatCurrencySigned` are `2`; CLV in pp is `1`). −0.0004 as a
 * percent prints "0.0%" and is grey, not red; 1e-13 dollars print "$0.00" and
 * are grey, not green; 0.0008 prints "+0.1%" and is green, not grey.
 */
export function pnlTone(value: number | null | undefined, digits: number, scale = 1): InkToken {
  const r = roundedAt(value, digits, scale);
  if (r == null) return 'textSecondary';
  if (r > 0) return 'betInk';
  if (r < 0) return 'avoidInk';
  return 'textSecondary';
}

export interface SignalBadgeSpec {
  label: string;
  /**
   * Ionicons glyph drawn before the word, so BET and AVOID differ in SHAPE
   * and not only in hue (WCAG 1.4.1; ~8% of men cannot separate the green
   * from the red): ✓ check, – dash, ✕ cross.
   */
  glyph: 'checkmark' | 'remove' | 'close';
  /** Text AND glyph colour. */
  ink: InkToken;
  /** The soft wash behind it — unchanged. */
  fill: 'betSoft' | 'avoidSoft' | 'noneSoft';
}

export const SIGNAL_BADGE: Record<SignalType, SignalBadgeSpec> = {
  BET: { label: 'BET', glyph: 'checkmark', ink: 'betInk', fill: 'betSoft' },
  NONE: { label: 'NONE', glyph: 'remove', ink: 'textSecondary', fill: 'noneSoft' },
  AVOID: { label: 'AVOID', glyph: 'close', ink: 'avoidInk', fill: 'avoidSoft' },
};

/**
 * Badge glyph size in points. Ionicons `size` is NOT scaled by Dynamic Type
 * the way <Text> is, so the glyph is sized off the badge font times the
 * system font scale, capped at 2x, and keeps pace with the word beside it.
 */
export function badgeGlyphSize(fontSize: number, fontScale: number): number {
  const scale = Number.isFinite(fontScale) && fontScale > 0 ? fontScale : 1;
  return Math.round(fontSize * Math.min(scale, 2));
}
