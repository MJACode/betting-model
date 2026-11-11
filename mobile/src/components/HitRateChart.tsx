import React, { useEffect, useRef, useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import Svg, { Line, Rect, Text as SvgText } from 'react-native-svg';
import { isHit, type HitDirection } from '@/lib/hitRate';
import { describeSelectedGame, minuteLabel, type ChartGame } from '@/lib/playerLog';
import { ordinal } from '@/lib/teamDetail';
import { colors, font, spacing } from '@/lib/theme';

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
  /** Each game's date and opponent, SAME ORDER AND LENGTH as `values` (newest
   *  first) — lib/playerLog.chartGames builds both in one pass. When given,
   *  every bar is labelled "@CHI / 10/26" instead of a bare game number
   *  (Matt, 2026-10-28: "I cannot tell which is the recent game"), the
   *  newest is tagged LATEST, and tapping a bar names that game above the
   *  chart. */
  games?: ChartGame[];
  /** The stat's name, read by VoiceOver after the value. Not printed: a
   *  plural label reads "1 Points" on screen. */
  unit?: string;
  /** 9pt "34m" under each bar, and minutes in the caption. Basketball stat tabs. */
  showMinuteLabels?: boolean;
  /** The bars are minutes: navy, no threshold, no hit or miss. */
  minutesMode?: boolean;
  /** Fired when the selected bar changes. `fromUser` is false when the
   *  selection resets to the newest game. */
  onSelect?: (game: ChartGame, index: number, fromUser: boolean) => void;
}

const BAR_W = 16;
const GAP = 10;
// Labelled bars are wider: "vs MIA" and "10/26" have to fit under one bar at
// 9pt, and bar + gap is the tap column, which HIG wants at 44pt.
const LABELLED_BAR_W = 26;
const LABELLED_GAP = 18;
const LEFT_PAD = 26;
const RIGHT_PAD = 12;
const TOP_PAD = 18; // room for the value label above each bar
const BOTTOM_PAD = 18; // room for the game-index label under each bar
// Opponent, date, and the LATEST tag under the newest bar.
const LABELLED_BOTTOM_PAD = 46;
// One more line under each bar when the games carry a defense rank
// (the defense-toughness filter, lib/defenseTier).
const RANK_LINE = 13;

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
  games,
  unit,
  showMinuteLabels = false,
  minutesMode = false,
  onSelect,
}: Props) {
  const scrollRef = useRef<ScrollView>(null);
  // Labels only when they line up one-to-one with the values.
  const labelled = games != null && games.length === values.length && values.length > 0;
  // Index into `values` (0 = newest). Defaults to the newest game; reset when
  // the window or stat changes so it never points past the end.
  const [selected, setSelected] = useState(0);
  // The "Tap a bar" hint goes once a bar has been tapped.
  const [tapped, setTapped] = useState(false);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  useEffect(() => {
    setSelected(0);
    setTapped(false);
    const first = games?.[0];
    if (first) onSelectRef.current?.(first, 0, false);
  }, [values.length, games]);

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
  const barW = labelled ? LABELLED_BAR_W : BAR_W;
  const gap = labelled ? LABELLED_GAP : GAP;
  // Ranked only when every labelled game carries one: a partly ranked chart
  // would print "#7" under some bars and nothing under others.
  const ranked = labelled && games!.every((g) => g.rank != null);
  // One more line for "34m" / "DNP" under the date.
  const minuteLine = labelled && (showMinuteLabels || games!.some((g) => g.dnp === true));
  const bottomPad = labelled
    ? LABELLED_BOTTOM_PAD + (minuteLine ? RANK_LINE : 0) + (ranked ? RANK_LINE : 0)
    : BOTTOM_PAD;
  // The chart keeps its plot height when labels are added, so the bars do not
  // shrink to make room for them.
  const svgH = labelled ? height - BOTTOM_PAD + bottomPad : height;

  const plotH = svgH - TOP_PAD - bottomPad;
  // A DNP contributes no height, and the Minutes tab has no threshold to scale to.
  const plotVals = ordered.filter((_, i) => !(labelled && games![n - 1 - i]?.dnp));
  const maxV = Math.max(...(plotVals.length ? plotVals : [0]), minutesMode ? 0 : line, median ?? 0, avg ?? 0);
  const scaleMax = Math.max(1, maxV) * 1.12; // headroom so the tallest bar/label fits
  const yFor = (v: number) => TOP_PAD + plotH - (v / scaleMax) * plotH;

  const innerW = n * barW + (n - 1) * gap;
  const svgW = LEFT_PAD + innerW + RIGHT_PAD;

  const lineY = yFor(line);
  const avgY = avg != null ? yFor(avg) : null;

  const bars = ordered.map((v, i) => {
    const x = LEFT_PAD + i * (barW + gap);
    const y = yFor(v);
    // The SAME predicate the hit count above the chart uses (lib/hitRate.ts),
    // not a second copy of it. The chart drew `v >= line` against a whole
    // threshold while the count ran `v > line` against the half-point one —
    // identical on integers and NOT on fractional yardage, which is the shape
    // of disagreement nobody reports because both numbers look plausible.
    const hit = isHit(v, line, side);
    // valueIdx: position in `values`/`games`, newest = 0.
    return { x, y, h: TOP_PAD + plotH - y, v, hit, gameNo: n - i, valueIdx: n - 1 - i };
  });
  const labelY = TOP_PAD + plotH;

  const pick = (idx: number) => {
    setSelected(idx);
    setTapped(true);
    const g = games?.[idx];
    if (g) onSelect?.(g, idx, true);
  };

  const chart = (
    <Svg width={svgW} height={svgH}>
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

      {/* Threshold / "at least" line. The Minutes tab has no line. */}
      {minutesMode ? null : (
        <>
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
        </>
      )}

      {bars.map((b, i) => {
        const g = labelled ? games![b.valueIdx] : null;
        const isLatest = b.valueIdx === 0;
        const isSel = labelled && b.valueIdx === selected;
        const cx = b.x + barW / 2;
        const dnp = g?.dnp === true;
        return (
          <React.Fragment key={i}>
            {dnp ? null : (
              <Rect
                x={b.x}
                y={b.y}
                width={barW}
                height={Math.max(2, b.h)}
                rx={3}
                fill={minutesMode ? colors.tint : b.hit ? colors.bet : colors.avoid}
                stroke={isSel ? (minutesMode ? colors.textInverse : colors.textPrimary) : undefined}
                strokeWidth={isSel ? 2 : 0}
              />
            )}
            {/* value above bar */}
            {dnp ? null : (
              <SvgText
                x={cx}
                y={b.y - 5}
                fill={isSel ? colors.textPrimary : colors.textSecondary}
                fontSize={9}
                fontWeight={isSel ? '700' : '600'}
                textAnchor="middle"
              >
                {fmtTick(b.v)}
              </SvgText>
            )}
            {g ? (
              <>
                <SvgText
                  x={cx}
                  y={labelY + 13}
                  fill={isLatest ? colors.tint : colors.textSecondary}
                  fontSize={9}
                  fontWeight={isLatest ? '700' : '600'}
                  textAnchor="middle"
                >
                  {g.opp ?? '—'}
                </SvgText>
                <SvgText
                  x={cx}
                  y={labelY + 25}
                  fill={isLatest ? colors.tint : colors.textTertiary}
                  fontSize={9}
                  fontWeight={isLatest ? '700' : '400'}
                  textAnchor="middle"
                >
                  {g.date}
                </SvgText>
                {minuteLine ? (
                  <SvgText
                    x={cx}
                    y={labelY + 37}
                    fill={g.dnp ? colors.textSecondary : g.lowMin ? colors.medInk : colors.textSecondary}
                    fontSize={9}
                    fontWeight="700"
                    textAnchor="middle"
                  >
                    {g.dnp ? 'DNP' : showMinuteLabels && typeof g.minutes === 'number' ? minuteLabel(g.minutes) : ''}
                  </SvgText>
                ) : null}
                {ranked ? (
                  <SvgText
                    x={cx}
                    y={labelY + 38 + (minuteLine ? RANK_LINE : 0)}
                    fill={isLatest ? colors.tint : colors.textPrimary}
                    fontSize={font.size.nano}
                    fontWeight="700"
                    textAnchor="middle"
                  >
                    {`#${g.rank}`}
                  </SvgText>
                ) : null}
                {isLatest ? (
                  <SvgText
                    x={cx}
                    y={labelY + 38 + (minuteLine ? RANK_LINE : 0) + (ranked ? RANK_LINE : 0)}
                    fill={colors.tint}
                    fontSize={font.size.nano}
                    fontWeight="800"
                    textAnchor="middle"
                  >
                    LATEST
                  </SvgText>
                ) : null}
                {/* Tap target: the whole column, bar plus labels. */}
                <Rect
                  x={b.x - gap / 2}
                  y={0}
                  width={barW + gap}
                  height={svgH}
                  fill="transparent"
                  onPress={() => pick(b.valueIdx)}
                />
              </>
            ) : (
              /* game number below bar */
              <SvgText
                x={cx}
                y={svgH - 5}
                fill={colors.textTertiary}
                fontSize={9}
                textAnchor="middle"
              >
                {b.gameNo}
              </SvgText>
            )}
          </React.Fragment>
        );
      })}
    </Svg>
  );

  const sel = labelled ? games![Math.min(selected, n - 1)] : null;
  const selHit = sel && !sel.dnp ? isHit(sel.value, line, side) : false;
  const ago = selected === 0 ? 'Latest' : selected === 1 ? '1 game ago' : `${selected} games ago`;
  const rankText = sel?.rank != null ? `#${sel.rank} defense` : null;
  const rankSpoken = sel?.rank != null ? `${ordinal(sel.rank)} toughest defense` : null;
  const readout = sel
    ? describeSelectedGame({
        ago,
        game: sel,
        unit,
        hit: selHit,
        mode: sel.dnp ? 'stat' : minutesMode ? 'minutes' : showMinuteLabels ? 'stat' : 'plain',
        rankCaption: rankText,
        rankSpoken,
      })
    : null;
  const caption = readout?.caption ?? null;
  const spoken = readout?.spoken ?? '';
  const selLow = readout?.low === true;

  const scroller = (
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
  if (!caption) return scroller;
  return (
    <View>
      {/* Which game the highlighted bar is. Starts on the newest; tap any bar
          to read another. The bars are SVG and VoiceOver cannot reach them,
          so this row is ONE adjustable element: swipe up/down moves to the
          older/newer game (the Stats ruler's pattern, UX review 2026-10-28). */}
      <View
        accessible
        accessibilityRole="adjustable"
        accessibilityLabel="Game"
        accessibilityValue={{ text: spoken }}
        accessibilityHint="Swipe up or down to move between games"
        accessibilityActions={[{ name: 'increment' }, { name: 'decrement' }]}
        onAccessibilityAction={(e) => {
          // Increment = older (further left), decrement = newer.
          const next = selected + (e.nativeEvent.actionName === 'increment' ? 1 : -1);
          if (next < 0 || next >= n) return;
          setSelected(next);
          setTapped(true);
          const g = games?.[next];
          if (g) onSelect?.(g, next, true);
        }}
      >
        <View style={styles.captionRow}>
          <View
            style={[
              styles.captionDot,
              {
                backgroundColor: sel?.dnp
                  ? colors.none
                  : minutesMode
                    ? colors.tint
                    : selHit
                      ? colors.bet
                      : colors.avoid,
              },
            ]}
          />
          <Text style={styles.captionText} numberOfLines={1}>
            {caption}
          </Text>
          {selLow ? <Text style={styles.lowMin}>Low MIN</Text> : null}
          {readout?.result ? (
            <Text style={[styles.captionResult, { color: readout.result === 'Hit' ? colors.betInk : colors.avoidInk }]}>
              {readout.result}
            </Text>
          ) : null}
        </View>
        {readout?.detail ? <Text style={styles.captionDetail}>{readout.detail}</Text> : null}
      </View>
      {scroller}
      {tapped ? null : <Text style={styles.hint}>Tap a bar to see that game</Text>}
    </View>
  );
}

function fmtTick(v: number): string {
  return Number.isInteger(v) ? String(v) : v.toFixed(1);
}

const styles = StyleSheet.create({
  captionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    marginBottom: spacing.xs,
  },
  captionDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  captionText: {
    flex: 1,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  // Sits under the opponent line, past the dot, so a long school name cannot
  // ellipsize the minutes. Not limited to one line.
  captionDetail: {
    marginLeft: spacing.md,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  captionResult: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.bold,
  },
  lowMin: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.bold,
    color: colors.medInk,
  },
  hint: {
    marginTop: 2,
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
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
