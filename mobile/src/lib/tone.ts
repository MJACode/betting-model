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
 * Gain → betInk, loss → avoidInk, zero / push / missing → textSecondary.
 * |value| ≤ epsilon counts as zero (a ratio that prints as 0.0% is not a win).
 */
export function pnlTone(value: number | null | undefined, epsilon = 0): InkToken {
  if (value == null || Number.isNaN(value)) return 'textSecondary';
  if (value > epsilon) return 'betInk';
  if (value < -epsilon) return 'avoidInk';
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
