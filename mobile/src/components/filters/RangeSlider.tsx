/**
 * Two-thumb percentage range slider for filter sheets.
 *
 * Replaces the pair of numeric text fields the hit-rate band used to ship
 * ("Min hit rate [  ] %  Max hit rate [  ] %", 2026-09-12, Matt's call). Two
 * keyboard-driven fields cost a keyboard raise, two taps and a dismiss to
 * answer a question — "show me the 60-80% guys" — that is a single drag, and
 * the keyboard covered the result count the sheet uses as its feedback.
 *
 * Mechanics worth knowing before editing:
 *
 *  - ONE PanResponder, on the track, not one per thumb. Nested responders in a
 *    ScrollView negotiate badly (the sheet is a ScrollView), and a single
 *    responder gives drag-from-anywhere and tap-to-set for free: the touch
 *    picks the nearer thumb, moves it under the finger, and keeps it.
 *  - `onStartShouldSetPanResponder` claims the touch on contact, so the sheet
 *    cannot scroll from ON the track. That is the standard slider trade and
 *    the track is one row tall; everything around it still scrolls.
 *  - Values are read through refs inside the responder. The responder is built
 *    once, so a captured prop would be the value at mount forever.
 *  - The geometry and the bound-keeping are NOT here: they live in
 *    `lib/rangeSlider.ts`, where they can be verified headlessly
 *    (npx tsx scripts/verify_range_slider.ts). What is left in this file is
 *    wiring — layout, refs, and the responder.
 *
 * Accessibility: each thumb is its own `adjustable` element with increment /
 * decrement actions, so VoiceOver drives the two ends separately. The visual
 * thumb is 28pt inside a 44pt touch area (HIG minimum), and the numbers are
 * printed above the track — colour and position are never the only carrier.
 */

import React, { useCallback, useMemo, useRef, useState } from 'react';
import { PanResponder, StyleSheet, Text, View } from 'react-native';
import {
  applyBound,
  grabTarget,
  resolveTie,
  snapTo,
  valueAtX,
  type Scale,
} from '@/lib/rangeSlider';
import { colors, font, radii, spacing } from '@/lib/theme';

/** Visual thumb diameter. The touch target around it is TAP_W. */
const THUMB = 28;
const TAP_W = 44;
const TRACK_H = 6;

interface Props {
  /** Lower bound of the scale (e.g. 0). */
  min: number;
  /** Upper bound of the scale (e.g. 100). */
  max: number;
  /** Snap interval. */
  step: number;
  low: number;
  high: number;
  onChange: (low: number, high: number) => void;
  /** Renders a value for the read-out and for VoiceOver. */
  format?: (v: number) => string;
  /** VoiceOver labels for the two thumbs. */
  lowLabel: string;
  highLabel: string;
  /** Sentence above the track, e.g. "60–80%". */
  readout: string;
}

export function RangeSlider({
  min,
  max,
  step,
  low,
  high,
  onChange,
  format = (v) => String(v),
  lowLabel,
  highLabel,
  readout,
}: Props) {
  const [width, setWidth] = useState(0);
  const [dragging, setDragging] = useState<'low' | 'high' | null>(null);

  // The responder is created once; these keep it reading live values.
  const trackRef = useRef<View>(null);
  const widthRef = useRef(0);
  /** Track's left edge in window coordinates — see `valueAt`. */
  const pageXRef = useRef(0);
  const lowRef = useRef(low);
  const highRef = useRef(high);
  const onChangeRef = useRef(onChange);
  widthRef.current = width;
  lowRef.current = low;
  highRef.current = high;
  onChangeRef.current = onChange;

  /** Which thumb the current gesture owns; 'tie' until the first move. */
  const activeRef = useRef<'low' | 'high' | 'tie'>('low');

  const scale: Scale = { min, max, step };
  const scaleRef = useRef(scale);
  scaleRef.current = scale;

  const apply = (which: 'low' | 'high', value: number) => {
    const next = applyBound(which, value, lowRef.current, highRef.current);
    if (next.low !== lowRef.current || next.high !== highRef.current) {
      onChangeRef.current(next.low, next.high);
    }
  };

  /** A touch's window x → the value under it, on the live scale. */
  const valueAt = (pageX: number) =>
    valueAtX(pageX, pageXRef.current, widthRef.current, scaleRef.current);

  const pan = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: () => true,
        // The sheet's ScrollView must not be able to steal a drag in flight.
        onPanResponderTerminationRequest: () => false,
        onPanResponderGrant: (e) => {
          const v = valueAt(e.nativeEvent.pageX);
          const which = grabTarget(v, lowRef.current, highRef.current);
          activeRef.current = which;
          if (which !== 'tie') {
            setDragging(which);
            apply(which, v);
          }
        },
        onPanResponderMove: (e, g) => {
          if (activeRef.current === 'tie') {
            const which = resolveTie(g.dx);
            if (!which) return; // still ambiguous
            activeRef.current = which;
            setDragging(which);
          }
          apply(activeRef.current, valueAt(e.nativeEvent.pageX));
        },
        onPanResponderRelease: () => setDragging(null),
        onPanResponderTerminate: () => setDragging(null),
      }),
    // Built once — everything it reads lives in a ref.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  /**
   * Width AND window origin, both needed to turn a touch into a value. The
   * sheet only ever scrolls vertically, so the x origin measured here stays
   * true for the life of the row.
   */
  const measure = useCallback((w: number) => {
    setWidth(w);
    widthRef.current = w;
    trackRef.current?.measureInWindow((x) => {
      pageXRef.current = x;
    });
  }, []);

  const fracOf = (v: number) => (max === min ? 0 : (v - min) / (max - min));
  const xOf = (v: number) => fracOf(v) * width;

  const thumbA11y = (which: 'low' | 'high') => ({
    accessible: true,
    accessibilityRole: 'adjustable' as const,
    accessibilityLabel: which === 'low' ? lowLabel : highLabel,
    accessibilityValue: {
      min,
      max,
      now: which === 'low' ? low : high,
      text: format(which === 'low' ? low : high),
    },
    accessibilityActions: [{ name: 'increment' }, { name: 'decrement' }],
    onAccessibilityAction: (e: { nativeEvent: { actionName: string } }) => {
      const current = which === 'low' ? low : high;
      const delta = e.nativeEvent.actionName === 'increment' ? step : -step;
      apply(which, snapTo(current + delta, scaleRef.current));
    },
  });

  return (
    <View>
      <View style={styles.readoutRow}>
        <Text style={styles.readout}>{readout}</Text>
      </View>

      {/* The padding keeps a thumb at either end from clipping; the track
          itself is measured inside it, so 0% and 100% land on the ends. */}
      <View style={styles.pad}>
        <View
          ref={trackRef}
          style={styles.track}
          onLayout={(e) => measure(e.nativeEvent.layout.width)}
          {...pan.panHandlers}
        >
          <View style={styles.rail} />
          {width > 0 ? (
            <View
              style={[styles.fill, { left: xOf(low), width: Math.max(0, xOf(high) - xOf(low)) }]}
            />
          ) : null}

          {width > 0
            ? (['low', 'high'] as const).map((which) => (
                <View
                  key={which}
                  style={[styles.tap, { left: xOf(which === 'low' ? low : high) - TAP_W / 2 }]}
                  {...thumbA11y(which)}
                >
                  <View style={[styles.thumb, dragging === which && styles.thumbActive]} />
                </View>
              ))
            : null}
        </View>
      </View>

      <View style={styles.endRow}>
        <Text style={styles.endLabel}>{format(min)}</Text>
        <Text style={styles.endLabel}>{format(max)}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  readoutRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  readout: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  pad: {
    paddingHorizontal: THUMB / 2,
  },
  track: {
    height: TAP_W,
    justifyContent: 'center',
  },
  rail: {
    height: TRACK_H,
    borderRadius: TRACK_H / 2,
    backgroundColor: colors.separatorOpaque,
  },
  fill: {
    position: 'absolute',
    height: TRACK_H,
    borderRadius: TRACK_H / 2,
    backgroundColor: colors.tint,
  },
  tap: {
    position: 'absolute',
    width: TAP_W,
    height: TAP_W,
    alignItems: 'center',
    justifyContent: 'center',
  },
  thumb: {
    width: THUMB,
    height: THUMB,
    borderRadius: radii.pill,
    backgroundColor: colors.bgElevated,
    borderWidth: 2,
    borderColor: colors.tint,
    // Matches the elevation the sheet's other raised elements use.
    shadowColor: '#000',
    shadowOpacity: 0.18,
    shadowRadius: 3,
    shadowOffset: { width: 0, height: 1 },
    elevation: 2,
  },
  thumbActive: {
    backgroundColor: colors.tint,
  },
  endRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: spacing.xs,
  },
  endLabel: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
});
