import React, { useMemo, useRef, useState } from 'react';
import { PanResponder, StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Line, Path } from 'react-native-svg';
import {
  areaPath,
  chartDateLabel,
  equitySeriesKey,
  linePath,
  pillFrame,
  plotLayout,
  pointXY,
  scrubBubbleFrame,
  scrubIndex,
  scrubIndexForSeries,
  tickDigits,
  unitAxisTicks,
  type EquityPoint,
} from '@/lib/equityGeometry';

export type { EquityPoint };
import { formatSigned } from '@/lib/format';
import { equityStrokeToken } from '@/lib/recordHero';
import { unitsSpeech } from '@/lib/a11y';
import { colors, font, pnlColor, radii, spacing } from '@/lib/theme';

/**
 * Cumulative posted-stake equity curve. The line is betInk when the hero
 * units are up (never the bright green). The end pill prints the hero's
 * units string. A horizontal drag shows that day's units in a bubble on
 * the top edge. The dashed line is zero.
 */
export function EquityCurve({
  points,
  seriesId,
  width,
  height = 212,
  endUnits,
}: {
  points: EquityPoint[];
  /** Sport (or All). Two sports can share every date; the scrub index must not. */
  seriesId: string;
  width: number;
  height?: number;
  /** The hero's posted-stake units. The end pill prints this, not a second rounding. */
  endUnits: number;
}) {
  const [finger, setFinger] = useState<number | null>(null);
  const [a11yIndex, setA11yIndex] = useState<number | null>(null);
  const [bubbleW, setBubbleW] = useState(160);
  const [pillSize, setPillSize] = useState({ w: 76, h: 22 });
  // Reset before paint when this curve is a different series. RN 0.81 does
  // not tell the view when VoiceOver focus leaves, and onBlur does not
  // fire for that, so focus-leave is not the release. The sport chip is:
  // seriesId plus the dates. The render below also refuses an index past
  // the array, because this render still sees the old state.
  const seriesKey = equitySeriesKey(seriesId, points);
  const [seenKey, setSeenKey] = useState(seriesKey);
  if (seenKey !== seriesKey) {
    setSeenKey(seriesKey);
    setA11yIndex(null);
    setFinger(null);
  }
  const pointsRef = useRef(points);
  pointsRef.current = points;
  const widthRef = useRef(width);
  widthRef.current = width;
  const heightRef = useRef(height);
  heightRef.current = height;

  const responder = useMemo(
    () => PanResponder.create({
      onMoveShouldSetPanResponder: (_, g) => Math.abs(g.dx) > 10 && Math.abs(g.dx) > Math.abs(g.dy) * 1.2,
      onPanResponderTerminationRequest: () => false,
      onPanResponderMove: (e) => {
        const series = pointsRef.current;
        if (series.length < 2) return;
        const layout = plotLayout(widthRef.current, heightRef.current, series.map((p) => p.cumUnits));
        setFinger(scrubIndex(e.nativeEvent.locationX, layout, series.length));
      },
      onPanResponderRelease: () => setFinger(null),
      onPanResponderTerminate: () => setFinger(null),
    }),
    [],
  );

  if (points.length < 2) {
    return (
      <View style={styles.card}>
        <Text style={styles.label}>Units over time</Text>
        <Text style={styles.empty}>Not enough settled days yet to chart.</Text>
      </View>
    );
  }

  const values = points.map((p) => p.cumUnits);
  const layout = plotLayout(width, height, values);
  const xy = points.map((p, i) => pointXY(layout, i, points.length, p.cumUnits));
  const lineD = linePath(xy);
  const zero = pointXY(layout, 0, 2, 0);
  const areaD = areaPath(xy, zero.y);
  const endText = formatSigned(endUnits, 2, 'u');
  const tone = equityStrokeToken(endUnits);
  const stroke = tone === 'avoidInk' ? colors.avoidInk : tone === 'textSecondary' ? colors.textSecondary : colors.betInk;
  const lastPt = xy[xy.length - 1]!;
  const pill = pillFrame(lastPt.x, lastPt.y, width, height, pillSize.w, pillSize.h);
  const ticks = unitAxisTicks(layout.minV, layout.maxV);
  const digits = tickDigits(ticks);
  const scrubAt = scrubIndexForSeries(finger, points.length)
    ?? scrubIndexForSeries(a11yIndex, points.length);
  const scrubPt = scrubAt != null ? points[scrubAt] : null;
  const bubble = scrubPt
    ? scrubBubbleFrame(xy[scrubAt!]!.x, width, bubbleW, layout.plotLeft)
    : null;
  const scrubSpoken = scrubPt
    ? `${chartDateLabel(scrubPt.date)}, ${unitsSpeech(formatSigned(scrubPt.cumUnits, 2, 'u'))} total`
    : null;

  const moveA11y = (dir: 1 | -1) => {
    const cur = scrubIndexForSeries(a11yIndex, points.length) ?? points.length - 1;
    const next = Math.max(0, Math.min(points.length - 1, cur + dir));
    setA11yIndex(next);
  };

  return (
    <View style={styles.card}>
      <Text style={styles.label}>Units over time</Text>
      <View
        style={{ width, height }}
        accessible
        accessibilityRole="adjustable"
        accessibilityLabel={`Units over time, ${unitsSpeech(endText)}, cumulative units, 1 to win. Break-even is the dashed line.`}
        accessibilityValue={{ text: scrubSpoken ?? unitsSpeech(endText) }}
        accessibilityActions={[{ name: 'increment' }, { name: 'decrement' }]}
        onAccessibilityAction={(e) => {
          if (e.nativeEvent.actionName === 'increment') moveA11y(1);
          if (e.nativeEvent.actionName === 'decrement') moveA11y(-1);
        }}
        {...responder.panHandlers}
      >
        <Svg width={width} height={height}>
          <Line
            x1={layout.plotLeft}
            x2={layout.plotLeft + layout.plotWidth}
            y1={zero.y}
            y2={zero.y}
            stroke={colors.separatorOpaque}
            strokeDasharray="4 4"
            strokeWidth={1}
          />
          <Path d={areaD} fill={stroke} fillOpacity={0.12} />
          <Path d={lineD} stroke={stroke} strokeWidth={2} fill="none" />
          <Circle cx={lastPt.x} cy={lastPt.y} r={3.5} fill={stroke} />
          {scrubAt != null ? (
            <Line
              x1={xy[scrubAt]!.x}
              x2={xy[scrubAt]!.x}
              y1={layout.plotTop}
              y2={layout.plotTop + layout.plotHeight}
              stroke={colors.textSecondary}
              strokeWidth={1}
            />
          ) : null}
          {scrubAt != null ? (
            <Circle cx={xy[scrubAt]!.x} cy={xy[scrubAt]!.y} r={3.5} fill={stroke} />
          ) : null}
        </Svg>
        {ticks.map((tick) => {
          const y = pointXY(layout, 0, 2, tick).y;
          return (
            <Text
              key={tick}
              style={[styles.axis, { top: y - 7 }]}
              maxFontSizeMultiplier={1.4}
              numberOfLines={1}
            >
              {formatSigned(tick, digits)}
            </Text>
          );
        })}
        {scrubAt == null ? (
          <View
            style={[styles.pill, { left: pill.left, top: pill.top, maxWidth: pill.maxWidth }]}
            pointerEvents="none"
            onLayout={(e) => {
              const w = Math.ceil(e.nativeEvent.layout.width);
              const h = Math.ceil(e.nativeEvent.layout.height);
              if (w > 0 && h > 0 && (w !== pillSize.w || h !== pillSize.h)) setPillSize({ w, h });
            }}
          >
            <Text
              style={[styles.pillText, { color: pnlColor(endUnits, 2) }]}
              maxFontSizeMultiplier={1.6}
              numberOfLines={1}
              adjustsFontSizeToFit
              minimumFontScale={0.6}
            >
              {endText}
            </Text>
          </View>
        ) : null}
        {scrubPt && bubble ? (
          <View
            style={[styles.bubble, { left: bubble.left, top: bubble.top }]}
            pointerEvents="none"
            onLayout={(e) => {
              const w = Math.ceil(e.nativeEvent.layout.width);
              if (w > 0 && w !== bubbleW) setBubbleW(w);
            }}
          >
            <Text style={styles.bubbleText} maxFontSizeMultiplier={1.6} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7}>
              {chartDateLabel(scrubPt.date)} · {formatSigned(scrubPt.cumUnits, 2, 'u')} total
            </Text>
          </View>
        ) : null}
      </View>
      <Text style={styles.caption}>Cumulative units, 1 to win · break-even = dashed line</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  label: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  empty: { fontSize: font.size.footnote, color: colors.textSecondary, paddingVertical: spacing.md },
  axis: {
    position: 'absolute',
    left: 0,
    width: 44,
    fontSize: font.size.caption,
    color: colors.textSecondary,
  },
  pill: {
    position: 'absolute',
    backgroundColor: colors.bgCard,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.separatorOpaque,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  pillText: { fontSize: font.size.caption, fontWeight: font.weight.bold },
  bubble: {
    position: 'absolute',
    backgroundColor: colors.bgCard,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.separatorOpaque,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  bubbleText: { fontSize: font.size.caption, fontWeight: font.weight.semibold, color: colors.textPrimary },
  caption: { fontSize: font.size.caption, color: colors.textSecondary, marginTop: spacing.sm },
});
