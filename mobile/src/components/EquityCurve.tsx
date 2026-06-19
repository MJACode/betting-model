import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Svg, { Line, Path } from 'react-native-svg';
import { colors, font, radii, spacing } from '@/lib/theme';

export interface EquityPoint {
  date: string;
  cumUnits: number; // cumulative flat-bet units (profit / 100), oldest → newest
}

/**
 * Cumulative flat-bet equity curve for the Track Record screen — the visual
 * proof of the model's record over time. Area chart with a dashed break-even
 * line at zero; tinted green/red by where the line ends.
 */
export function EquityCurve({
  points,
  width,
  height = 140,
}: {
  points: EquityPoint[];
  width: number;
  height?: number;
}) {
  if (points.length < 2) {
    return (
      <View style={styles.card}>
        <Text style={styles.label}>Equity curve</Text>
        <Text style={styles.empty}>Not enough settled days yet to chart.</Text>
      </View>
    );
  }

  const pad = 10;
  const w = width - pad * 2;
  const h = height - pad * 2;

  const vals = points.map((p) => p.cumUnits);
  const maxV = Math.max(...vals, 0);
  const minV = Math.min(...vals, 0);
  const range = Math.max(1, maxV - minV);

  const xStep = w / (points.length - 1);
  const xy = points.map((p, i) => ({
    x: pad + i * xStep,
    y: pad + h - ((p.cumUnits - minV) / range) * h,
  }));

  const lineD = xy.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
  const zeroY = pad + h - ((0 - minV) / range) * h;
  const last = points[points.length - 1].cumUnits;
  const stroke = last > 0 ? colors.positive : last < 0 ? colors.negative : colors.textSecondary;
  // Area fill: line down to the zero baseline and back.
  const areaD = `${lineD} L${xy[xy.length - 1].x.toFixed(1)} ${zeroY.toFixed(1)} L${xy[0].x.toFixed(1)} ${zeroY.toFixed(1)} Z`;

  const sign = last > 0 ? '+' : '';

  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <Text style={styles.label}>Equity curve</Text>
        <Text style={[styles.units, { color: stroke }]}>
          {sign}
          {last.toFixed(1)}u
        </Text>
      </View>
      <Svg width={width} height={height}>
        <Line x1={pad} x2={width - pad} y1={zeroY} y2={zeroY} stroke={colors.separatorOpaque} strokeDasharray="4 4" strokeWidth={1} />
        <Path d={areaD} fill={stroke} fillOpacity={0.12} />
        <Path d={lineD} stroke={stroke} strokeWidth={2} fill="none" />
      </Svg>
      <Text style={styles.caption}>Cumulative units on flat $100 bets · break-even = dashed line</Text>
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
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  label: { fontSize: font.size.headline, fontWeight: font.weight.semibold, color: colors.textPrimary },
  units: { fontSize: font.size.headline, fontWeight: font.weight.bold },
  empty: { fontSize: font.size.footnote, color: colors.textTertiary, paddingVertical: spacing.md },
  caption: { fontSize: font.size.caption, color: colors.textTertiary, marginTop: spacing.sm },
});
