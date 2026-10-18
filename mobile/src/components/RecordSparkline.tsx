import React, { useMemo } from 'react';
import Svg, { Path } from 'react-native-svg';
import { SPARK_PAD, linePath, plotLayout, pointXY, type EquityPoint } from '@/lib/equityGeometry';
import { equityStrokeToken } from '@/lib/recordHero';
import { colors } from '@/lib/theme';

/**
 * The hero's small chart. Same series as the equity curve, no axes.
 * The stroke follows the hero's units: betInk when they are up.
 */
export function RecordSparkline({
  points,
  width,
  height = 56,
  endUnits,
}: {
  points: EquityPoint[];
  width: number;
  height?: number;
  endUnits: number;
}) {
  const d = useMemo(() => {
    if (points.length < 2 || width < 8) return '';
    const layout = plotLayout(width, height, points.map((p) => p.cumUnits), SPARK_PAD);
    const xy = points.map((p, i) => pointXY(layout, i, points.length, p.cumUnits));
    return linePath(xy);
  }, [points, width, height]);
  if (!d) return null;
  const tone = equityStrokeToken(endUnits);
  const stroke = tone === 'avoidInk' ? colors.avoidInk : tone === 'textSecondary' ? colors.textSecondary : colors.betInk;
  return (
    <Svg width={width} height={height}>
      <Path d={d} stroke={stroke} strokeWidth={2} fill="none" />
    </Svg>
  );
}
