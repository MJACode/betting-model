import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Line, Path } from 'react-native-svg';
import { colors, font, radii, spacing } from '@/lib/theme';

interface Props {
  values: number[]; // most recent first
  line?: number | null; // DK line drawn as dashed horizontal reference
  width?: number;
  height?: number;
  label?: string;
}

export function TrendSparkline({ values, line, width = 280, height = 80, label }: Props) {
  if (values.length === 0) {
    return (
      <View style={[styles.container, { width: undefined }]}>
        {label ? <Text style={styles.label}>{label}</Text> : null}
        <Text style={styles.empty}>No recent data</Text>
      </View>
    );
  }

  // Reverse to render left-to-right by oldest-to-newest.
  const ordered = [...values].reverse();
  const padding = 12;
  const w = width - padding * 2;
  const h = height - padding * 2;
  const maxV = Math.max(...ordered, line ?? 0);
  const minV = Math.min(...ordered, line ?? 0);
  const range = Math.max(0.5, maxV - minV);

  const xStep = ordered.length > 1 ? w / (ordered.length - 1) : w;
  const points = ordered.map((v, i) => {
    const x = padding + i * xStep;
    const y = padding + h - ((v - minV) / range) * h;
    return { x, y, v };
  });

  const pathD = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(' ');

  const lineY =
    line != null ? padding + h - ((line - minV) / range) * h : null;

  return (
    <View style={styles.container}>
      {label ? <Text style={styles.label}>{label}</Text> : null}
      <Svg width={width} height={height}>
        {lineY != null ? (
          <Line
            x1={padding}
            x2={width - padding}
            y1={lineY}
            y2={lineY}
            stroke={colors.tint}
            strokeDasharray="4 4"
            strokeWidth={1}
          />
        ) : null}
        <Path d={pathD} stroke={colors.textPrimary} strokeWidth={2} fill="none" />
        {points.map((p, i) => (
          <Circle key={i} cx={p.x} cy={p.y} r={2.5} fill={colors.textPrimary} />
        ))}
      </Svg>
      {line != null ? (
        <Text style={styles.lineLabel}>
          DK line: <Text style={styles.lineLabelEm}>{line}</Text>
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    alignItems: 'center',
  },
  label: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.semibold,
    marginBottom: spacing.sm,
    alignSelf: 'flex-start',
  },
  empty: {
    fontSize: font.size.body,
    color: colors.textTertiary,
    paddingVertical: spacing.lg,
  },
  lineLabel: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginTop: 4,
  },
  lineLabelEm: {
    color: colors.tint,
    fontWeight: font.weight.semibold,
  },
});
