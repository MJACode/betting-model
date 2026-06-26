import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Line, Path } from 'react-native-svg';
import { calibrationVerdict, type Calibration } from '@/lib/calibration';
import { formatPct } from '@/lib/format';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * Reliability diagram: predicted probability (x) vs empirical win rate (y) for
 * settled BET picks. Dots on the dashed diagonal = perfectly calibrated. Axes
 * auto-fit the observed range so favorite-heavy and low-prob (prop/golf) models
 * both read clearly; the y=x diagonal is scale-independent so it stays valid.
 */
export function CalibrationChart({
  calibration,
  width,
  height = 150,
  title = 'Calibration',
  flush = false,
}: {
  calibration: Calibration;
  width: number;
  height?: number;
  title?: string;
  /** Drop the horizontal margin when nested in an already-padded container. */
  flush?: boolean;
}) {
  const { bins, gap, n } = calibration;
  const pad = 14;
  const w = width - pad * 2;
  const h = height - pad * 2;

  // Shared scale across both axes from the observed predicted + actual values.
  const vals = bins.flatMap((b) => [b.predMean, b.actualRate]);
  let lo = Math.min(...vals);
  let hi = Math.max(...vals);
  const span = Math.max(hi - lo, 0.1);
  lo = Math.max(0, lo - span * 0.12);
  hi = Math.min(1, hi + span * 0.12);
  const range = Math.max(hi - lo, 0.01);

  const sx = (v: number) => pad + ((v - lo) / range) * w;
  const sy = (v: number) => pad + h - ((v - lo) / range) * h;

  const lineD = bins
    .map((b, i) => `${i === 0 ? 'M' : 'L'}${sx(b.predMean).toFixed(1)} ${sy(b.actualRate).toFixed(1)}`)
    .join(' ');
  const maxN = Math.max(...bins.map((b) => b.n), 1);

  const gapColor = gap <= 0.05 ? colors.bet : gap <= 0.1 ? colors.med : colors.avoid;

  return (
    <View style={[styles.card, flush && styles.flush]}>
      <View style={styles.headerRow}>
        <Text style={styles.label}>{title}</Text>
        <Text style={[styles.gap, { color: gapColor }]}>{formatPct(gap, 1)} gap</Text>
      </View>
      <Svg width={width} height={height}>
        {/* perfect-calibration diagonal */}
        <Line
          x1={sx(lo)}
          y1={sy(lo)}
          x2={sx(hi)}
          y2={sy(hi)}
          stroke={colors.separatorOpaque}
          strokeDasharray="4 4"
          strokeWidth={1}
        />
        {bins.length > 1 ? (
          <Path d={lineD} stroke={colors.tint} strokeWidth={2} fill="none" />
        ) : null}
        {bins.map((b, i) => (
          <Circle
            key={i}
            cx={sx(b.predMean)}
            cy={sy(b.actualRate)}
            r={3 + (b.n / maxN) * 4}
            fill={colors.tint}
          />
        ))}
      </Svg>
      <View style={styles.axisRow}>
        <Text style={styles.axisText}>Predicted →</Text>
        <Text style={styles.axisText}>↑ Actual win rate</Text>
      </View>
      <Text style={styles.caption}>
        {calibrationVerdict(gap)} On the dashed line = stated odds match reality. {n} settled picks.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  flush: { marginHorizontal: 0 },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  label: { fontSize: font.size.headline, fontWeight: font.weight.semibold, color: colors.textPrimary },
  gap: { fontSize: font.size.headline, fontWeight: font.weight.bold },
  axisRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 2,
  },
  axisText: { fontSize: font.size.caption, color: colors.textTertiary },
  caption: { fontSize: font.size.caption, color: colors.textTertiary, marginTop: spacing.sm, lineHeight: 17 },
});
