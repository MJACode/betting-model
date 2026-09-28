/**
 * Tap-target and screen-reader helpers (usability audit PR 4: H9, M8, M26…).
 *
 * Pure — no React Native import — so scripts/verify_a11y.ts and the pytest pin
 * can load it under plain `node --experimental-strip-types`.
 *
 * The 44pt floor is Apple's HIG minimum (Android's is 48dp; 44pt is what the
 * audit measured against). Where a control's VISUAL can't grow without moving
 * the layout, we grow its touch area with hitSlop instead — the audit rule was
 * "hit areas and insets only, no visual change".
 */

/** Apple HIG minimum touch target, in points. */
export const MIN_TAP = 44;

export type Slop = { top: number; bottom: number; left: number; right: number };

/**
 * hitSlop that takes a control of `height` × `width` points to at least
 * MIN_TAP on each axis. Split evenly (rounded up) so the target stays centred
 * on the visual. A dimension already at the floor gets no slop on that axis.
 */
export function slopFor(height: number, width: number = MIN_TAP): Slop {
  const v = Math.max(0, Math.ceil((MIN_TAP - height) / 2));
  const h = Math.max(0, Math.ceil((MIN_TAP - width) / 2));
  return { top: v, bottom: v, left: h, right: h };
}

/** Effective target size of a control once `slop` is applied. */
export function targetSize(
  height: number,
  width: number,
  slop: Partial<Slop> | number | null | undefined,
): { height: number; width: number } {
  const s: Slop =
    typeof slop === 'number'
      ? { top: slop, bottom: slop, left: slop, right: slop }
      : { top: slop?.top ?? 0, bottom: slop?.bottom ?? 0, left: slop?.left ?? 0, right: slop?.right ?? 0 };
  return { height: height + s.top + s.bottom, width: width + s.left + s.right };
}

/**
 * Vertical breathing room for a horizontal ScrollView row whose chips need
 * vertical hitSlop. A touch outside a view's parent bounds is never delivered
 * (iOS hit-tests the parent first; Android clips), so slop that pokes out of a
 * ~27pt-tall horizontal ScrollView does nothing. The row pads its content by
 * this much and pulls itself back with an equal negative margin: the ScrollView
 * now spans the full 44pt target while the layout around it doesn't move.
 *
 * ONLY where the strip it reaches into is whitespace or non-interactive (Track
 * Record: the subtitle above, its own bottom margin below). A negative margin
 * over a neighbouring control is worse than no slop: the later sibling wins
 * the overlap, so taps there land on an empty ScrollView and do nothing. Rows
 * with a neighbouring control use reachFrame, which splits the shared gap.
 */
export const ROW_SLOP_PAD = 11;

export type ReachFrame = {
  /** The ScrollView's own style: pulled back so nothing around it moves. */
  frame: { marginTop: number; marginBottom: number; zIndex?: number };
  /** Its contentContainerStyle padding: the room its chips' hitSlop may use. */
  content: { paddingTop: number; paddingBottom: number };
};

/**
 * H9 for a horizontal ScrollView row with neighbours: grow its touchable
 * bounds by `above` / `below` points with no visual change (pad the content,
 * pull the frame back by the same). `marginTop` is the frame's margin before
 * the reach, so a row can take whitespace that used to be its own margin.
 *
 * - `above` may cover only whitespace or non-interactive content drawn
 *   earlier: the row is the later sibling, so it is hit-tested first there.
 * - `below` covers a LATER sibling, which would otherwise win the overlap, so
 *   pass `raise` (zIndex 1: hit-tested first on iOS and Android). Give it only
 *   whitespace, or HALF of a gap shared with the next row's chips, so the two
 *   targets tile instead of stealing from each other. Not needed when `below`
 *   only covers the parent's own padding.
 */
export function reachFrame(
  above: number,
  below: number = 0,
  opts: { raise?: boolean; marginTop?: number } = {},
): ReachFrame {
  return {
    frame: {
      marginTop: (opts.marginTop ?? 0) - above,
      marginBottom: -below,
      ...(opts.raise ? { zIndex: 1 } : {}),
    },
    content: { paddingTop: above, paddingBottom: below },
  };
}

/** "Page 2 of 4" — onboarding dots and any other pager (M19). */
export function pageLabel(index: number, total: number): string {
  return `Page ${index + 1} of ${total}`;
}

/** Joins label parts, dropping empties: ['MLB', null, '2 signals'] → "MLB, 2 signals". */
export function joinLabel(parts: ReadonlyArray<string | null | undefined | false>): string {
  return parts.filter((p): p is string => typeof p === 'string' && p.trim().length > 0).join(', ');
}

function ordinal(n: number): string {
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${n}th`;
  const suffix = ({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[n % 10] ?? 'th';
  return `${n}${suffix}`;
}

/** Structural copy of lib/format's GameStatus, so this file stays import-free. */
export type StatusForSpeech =
  | { kind: 'pre'; timeLabel: string }
  | {
      kind: 'live';
      awayScore: number | null;
      homeScore: number | null;
      inning: number | null;
      inningHalf: 'top' | 'bottom' | null;
      outs: number | null;
    }
  | { kind: 'final'; awayScore: number; homeScore: number }
  | { kind: 'ended' };

/**
 * What VoiceOver should say for GameStatusPill (audit M22): the pill prints
 * "3–2 B9 LIVE", which reads as "3 dash 2 B 9 live". This says "Live, bottom
 * 9th, 3 to 2". Scores are away–home, as printed. Null when the pill renders
 * nothing (no start time, or an ended game with no score).
 */
export function gameStatusSpeech(status: StatusForSpeech, dayLabel?: string | null): string | null {
  if (status.kind === 'pre') {
    if (!status.timeLabel) return null;
    return `Starts ${dayLabel ? `${dayLabel}, ` : ''}${status.timeLabel}`;
  }
  if (status.kind === 'ended') return null;
  if (status.kind === 'final') return `Final, ${status.awayScore} to ${status.homeScore}`;
  const inning =
    status.inning == null
      ? null
      : `${status.inningHalf === 'top' ? 'top ' : status.inningHalf === 'bottom' ? 'bottom ' : 'inning '}${ordinal(status.inning)}`;
  const outs = status.outs == null ? null : `${status.outs} out${status.outs === 1 ? '' : 's'}`;
  const score =
    status.awayScore == null || status.homeScore == null
      ? null
      : `${status.awayScore} to ${status.homeScore}`;
  return joinLabel(['Live', inning, outs, score]);
}

/**
 * A header line with unknown counts ("—", PATTERNS §F5) as VoiceOver should
 * say it, in the sub-tabs' words: "Sep 28 · — bets · — scored" reads "Sep 28,
 * bets count not available, scored count not available". Lines with no "—"
 * only lose the "·" separators.
 */
export function unknownCountSpeech(text: string): string {
  return joinLabel(
    text.split(/\s*·\s*/).map((part) => {
      const m = /^—\s*(.+)$/.exec(part.trim());
      return m ? `${m[1]} count not available` : part;
    }),
  );
}

/**
 * M25: why the disabled "Add bet" (ManualBetModal) can't be pressed, as its
 * accessibilityHint — "Enter a stake above zero to add this bet." It names
 * only what is still missing; undefined once the bet can be added.
 */
export function addBetHint(o: { bet: string; stake: string }): string | undefined {
  const stake = parseFloat(o.stake);
  const missing = [
    o.bet.trim().length > 0 ? null : 'the bet',
    Number.isFinite(stake) && stake > 0 ? null : 'a stake above zero',
  ].filter((m): m is string => m != null);
  return missing.length === 0 ? undefined : `Enter ${missing.join(' and ')} to add this bet.`;
}

/** "1.2u → 1.0u" is read as "1.2 u arrow"; this says "stake 1.2 units to win 1.0 units". */
export function unitsSpeech(text: string): string {
  return text.replace(/(\d)u\b/g, '$1 units').replace(/\s*→\s*/g, ' to win ');
}

/** "Sharp score 35 of 100, strong" (audit M5). Tier word is optional. */
export function sharpScoreSpeech(score: number, tier?: string | null): string {
  return joinLabel([`Sharp score ${Math.round(score)} of 100`, tier ?? null]);
}

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

/** "2026-09-28" → "September 28, 2026" — calendar day cells read as a date, not "28". */
export function spokenDate(ymd: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(ymd);
  if (!m) return ymd;
  const month = MONTHS[Number(m[2]) - 1];
  return month ? `${month} ${Number(m[3])}, ${m[1]}` : ymd;
}
