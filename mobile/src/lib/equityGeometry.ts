export interface EquityPoint {
  date: string;
  cumUnits: number;
}

/**
 * Geometry for the Record equity curve and the hero sparkline.
 * Pure so a headless script can pin the scrub index, the zero line and the
 * end pill without mounting React Native.
 */

export interface PlotPad {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

export interface PlotLayout {
  plotLeft: number;
  plotTop: number;
  plotWidth: number;
  plotHeight: number;
  minV: number;
  maxV: number;
  range: number;
}

/** Y-axis gutter on the full chart. The sparkline passes a tight pad instead. */
export const CHART_PAD: PlotPad = { left: 48, right: 8, top: 28, bottom: 8 };
export const SPARK_PAD: PlotPad = { left: 2, right: 2, top: 4, bottom: 4 };

export function plotLayout(
  width: number,
  height: number,
  values: number[],
  pad: PlotPad = CHART_PAD,
): PlotLayout {
  const vals = values.length ? values : [0];
  const rawMax = Math.max(...vals, 0);
  const rawMin = Math.min(...vals, 0);
  const ticks = unitAxisTicks(rawMin, rawMax);
  const maxV = ticks[ticks.length - 1] ?? 0;
  const minV = ticks[0] ?? 0;
  const range = Math.max(1e-6, maxV - minV);
  return {
    plotLeft: pad.left,
    plotTop: pad.top,
    plotWidth: Math.max(1, width - pad.left - pad.right),
    plotHeight: Math.max(1, height - pad.top - pad.bottom),
    minV,
    maxV,
    range,
  };
}

export function pointXY(
  layout: PlotLayout,
  index: number,
  count: number,
  value: number,
): { x: number; y: number } {
  const x = count <= 1
    ? layout.plotLeft + layout.plotWidth
    : layout.plotLeft + (index / (count - 1)) * layout.plotWidth;
  const y = layout.plotTop + layout.plotHeight
    - ((value - layout.minV) / layout.range) * layout.plotHeight;
  return { x, y };
}

export function linePath(pts: { x: number; y: number }[]): string {
  return pts
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(' ');
}

/** Close the line down to the zero baseline and back, for the soft fill. */
export function areaPath(pts: { x: number; y: number }[], zeroY: number): string {
  if (pts.length === 0) return '';
  const last = pts[pts.length - 1]!;
  const first = pts[0]!;
  return `${linePath(pts)} L${last.x.toFixed(1)} ${zeroY.toFixed(1)} L${first.x.toFixed(1)} ${zeroY.toFixed(1)} Z`;
}

function niceStep(rough: number): number {
  if (!Number.isFinite(rough) || rough <= 0) return 1;
  const pow = Math.pow(10, Math.floor(Math.log10(rough)));
  const n = rough / pow;
  const f = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10;
  return f * pow;
}

/** Tick marks spanning the series, always including zero. */
export function unitAxisTicks(minV: number, maxV: number): number[] {
  const min = Math.min(minV, 0);
  const max = Math.max(maxV, 0);
  const step = niceStep(Math.max(max - min, 1) / 4);
  let start = Math.floor(min / step + 1e-9) * step;
  let end = Math.ceil(max / step - 1e-9) * step;
  if (Math.abs(start) < 1e-6) start = 0;
  if (Math.abs(end) < 1e-6) end = 0;
  if (end <= start) end = start + step;
  const ticks: number[] = [];
  for (let v = start; v <= end + step * 0.01 && ticks.length < 8; v += step) {
    ticks.push(Math.abs(v) < 1e-6 ? 0 : Number(v.toFixed(6)));
  }
  if (!ticks.some((t) => t === 0)) ticks.push(0);
  ticks.sort((a, b) => a - b);
  return ticks;
}

export function tickDigits(ticks: number[]): number {
  return ticks.every((t) => Math.abs(t - Math.round(t)) < 1e-6) ? 0 : 1;
}

/** Finger x → a point index, clamped to the series. */
export function scrubIndex(x: number, layout: PlotLayout, count: number): number {
  if (count <= 1) return 0;
  const t = (x - layout.plotLeft) / layout.plotWidth;
  const i = Math.round(t * (count - 1));
  return Math.max(0, Math.min(count - 1, i));
}

/**
 * End-of-line pill. Prefer above the point; drop below when the point is
 * already in the top gutter. Clamp so the pill stays inside the chart.
 */
export function pillFrame(
  x: number,
  y: number,
  width: number,
  height: number,
  pillW = 76,
  pillH = 22,
): { left: number; top: number } {
  const left = Math.max(0, Math.min(x - pillW / 2, width - pillW));
  const above = y - pillH - 4;
  const top = above >= 0 ? above : Math.min(height - pillH, y + 4);
  return { left, top: Math.max(0, top) };
}

/** Scrub readout sits on the top edge, centered on the point, clear of the y-axis. */
export function scrubBubbleFrame(
  x: number,
  width: number,
  bubbleW: number,
  minLeft = 48,
): { left: number; top: number } {
  const maxLeft = Math.max(minLeft, width - bubbleW);
  return {
    left: Math.max(minLeft, Math.min(x - bubbleW / 2, maxLeft)),
    top: 0,
  };
}

const SHORT_MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

/** "2026-09-12" → "Sep 12" for the scrub bubble. */
export function chartDateLabel(ymd: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(ymd);
  if (!m) return ymd;
  const month = SHORT_MONTHS[Number(m[2]) - 1];
  return month ? `${month} ${Number(m[3])}` : ymd;
}
