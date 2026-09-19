import React, { useRef } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import Svg, { Line, Rect, Text as SvgText } from 'react-native-svg';
import { isHit, type HitDirection } from '@/lib/hitRate';
import { colors, font } from '@/lib/theme';

interface Props {
  /** Per-game stat values, MOST RECENT FIRST (matches usePlayerTrends). */
  values: number[];
  /** "At least" threshold — a game hits when value >= line (over), or when it
   *  stays below it (under). */
  line: number;
  /** Which way the bet runs. Defaults to 'over', which is what every caller
   *  did before the player card gained a direction control — so the chart's
   *  colours now follow the bet instead of always drawing an over. Leaving
   *  this out on an under card would paint every losing game green. */
  side?: HitDirection;
  /** What to print on the threshold tick, in the CALLER'S idiom. The line is
   *  drawn at the book's half-point number, but a card headed "2+ Hits" with a
   *  stepper reading "2" and a legend reading "Hit (2+)" would then carry a
   *  lone "1.5" — the only number on screen speaking the other vocabulary
   *  (lib/hitMode.modeLineLabel exists for exactly this). Defaults to the raw
   *  number for callers with no mode behind them. */
  lineLabel?: string;
  avg: number | null;
  median: number | null;
  height?: number;
}

const BAR_W = 16;
const GAP = 10;
const LEFT_PAD = 26;
const RIGHT_PAD = 12;
const TOP_PAD = 18; // room for the value label above each bar
const BOTTOM_PAD = 18; // room for the game-index label under each bar

/**
 * Bar chart of a player's per-game stat, colored by whether the game won the
 * bet. Green = hit, red = miss, with `side` deciding which way that runs. A
 * dashed reference line marks the line and a faint dotted line marks the
 * average. Oldest game on the left, newest on the right; scrolls horizontally
 * when there are many games.
 *
 * `line` is the BOOK'S half-point number (1.5), not the fan's threshold (2).
 * They name the same bet, but only the half-point one can be compared against
 * a game's value without a tie: no game ever lands on 0.5, so every bar is a
 * hit or a miss and none sits ambiguously ON the dashed line.
 */
export function HitRateChart({
  values,
  line,
  side = 'over',
  lineLabel,
  avg,
  median,
  height = 200,
}: Props) {
  const scrollRef = useRef<ScrollView>(null);

  if (values.length === 0) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyText}>No recent games on file.</Text>
      </View>
    );
  }

  // Reverse so the chart reads oldest → newest (newest bar on the right).
  const ordered = [...values].reverse();
  const n = ordered.length;

  const plotH = height - TOP_PAD - BOTTOM_PAD;
  const maxV = Math.max(...ordered, line, median ?? 0, avg ?? 0);
  const scaleMax = Math.max(1, maxV) * 1.12; // headroom so the tallest bar/label fits
  const yFor = (v: number) => TOP_PAD + plotH - (v / scaleMax) * plotH;

  const innerW = n * BAR_W + (n - 1) * GAP;
  const svgW = LEFT_PAD + innerW + RIGHT_PAD;

  const lineY = yFor(line);
  const avgY = avg != null ? yFor(avg) : null;

  const bars = ordered.map((v, i) => {
    const x = LEFT_PAD + i * (BAR_W + GAP);
    const y = yFor(v);
    // The SAME predicate the hit count above the chart uses (lib/hitRate.ts),
    // not a second copy of it. The chart drew `v >= line` against a whole
    // threshold while the count ran `v > line` against the half-point one —
    // identical on integers and NOT on fractional yardage, which is the shape
    // of disagreement nobody reports because both numbers look plausible.
    const hit = isHit(v, line, side);
    return { x, y, h: TOP_PAD + plotH - y, v, hit, gameNo: n - i };
  });

  const chart = (
    <Svg width={svgW} height={height}>
      {/* Average reference (faint, neutral) */}
      {avgY != null ? (
        <Line
          x1={LEFT_PAD}
          x2={svgW - RIGHT_PAD}
          y1={avgY}
          y2={avgY}
          stroke={colors.textTertiary}
          strokeDasharray="2 4"
          strokeWidth={1}
        />
      ) : null}

      {/* Threshold / "at least" line */}
      <Line
        x1={LEFT_PAD}
        x2={svgW - RIGHT_PAD}
        y1={lineY}
        y2={lineY}
        stroke={colors.tint}
        strokeDasharray="5 4"
        strokeWidth={1.5}
      />
      <SvgText
        x={4}
        y={lineY + 3}
        fill={colors.tint}
        fontSize={10}
        fontWeight="700"
      >
        {lineLabel ?? fmtTick(line)}
      </SvgText>

      {bars.map((b, i) => (
        <React.Fragment key={i}>
          <Rect
            x={b.x}
            y={b.y}
            width={BAR_W}
            height={Math.max(2, b.h)}
            rx={3}
            fill={b.hit ? colors.bet : colors.avoid}
          />
          {/* value above bar */}
          <SvgText
            x={b.x + BAR_W / 2}
            y={b.y - 5}
            fill={colors.textSecondary}
            fontSize={9}
            fontWeight="600"
            textAnchor="middle"
          >
            {fmtTick(b.v)}
          </SvgText>
          {/* game number below bar */}
          <SvgText
            x={b.x + BAR_W / 2}
            y={height - 5}
            fill={colors.textTertiary}
            fontSize={9}
            textAnchor="middle"
          >
            {b.gameNo}
          </SvgText>
        </React.Fragment>
      ))}
    </Svg>
  );

  return (
    <ScrollView
      ref={scrollRef}
      horizontal
      showsHorizontalScrollIndicator={false}
      // Keep the most recent games (right edge) in view as data/line changes.
      onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: false })}
      contentContainerStyle={styles.scroll}
    >
      {chart}
    </ScrollView>
  );
}

function fmtTick(v: number): string {
  return Number.isInteger(v) ? String(v) : v.toFixed(1);
}

const styles = StyleSheet.create({
  scroll: {
    paddingRight: 4,
  },
  empty: {
    paddingVertical: 32,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: font.size.body,
    color: colors.textTertiary,
  },
});
