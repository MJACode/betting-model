import React, { useEffect, useRef } from 'react';
import { Animated, StyleSheet, View, type DimensionValue, type StyleProp, type ViewStyle } from 'react-native';
import { card, colors, radii, spacing } from '@/lib/theme';
import { useReduceMotion } from '@/hooks/useReduceMotion';

/**
 * PATTERNS §E2 loading placeholders, lifted from the Stats board skeleton
 * (StatsScreen BoardSkeleton): `noneSoft` blocks shaped like the content, so a
 * first load never flashes zeros or an empty state (UX_REVIEW §3; audit H3).
 *
 * The pulse holds still when Reduce Motion is on. The wrapper is ONE
 * accessibility element, "Loading {thing}", marked busy; the blocks are hidden.
 */
export function Skeleton({
  label,
  children,
  style,
}: {
  /** What is loading, e.g. "the track record". Read as "Loading the track record". */
  label: string;
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
}) {
  const reduce = useReduceMotion();
  const pulse = useRef(new Animated.Value(1)).current;
  useEffect(() => {
    if (reduce) {
      pulse.setValue(1);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 0.45, duration: 700, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 1, duration: 700, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [reduce, pulse]);
  return (
    <Animated.View
      accessible
      accessibilityRole="progressbar"
      accessibilityLabel={`Loading ${label}`}
      accessibilityState={{ busy: true }}
      style={[style, { opacity: pulse }]}
    >
      {children}
    </Animated.View>
  );
}

/** One grey bar. Radius follows the text it stands in for. */
export function SkeletonBlock({
  width = '100%',
  height = 10,
  style,
}: {
  width?: DimensionValue;
  height?: number;
  style?: StyleProp<ViewStyle>;
}) {
  return <View style={[styles.block, { width, height }, style]} />;
}

/** A list row: a title bar over a shorter subtitle bar, with a value at the end. */
export function SkeletonRow() {
  return (
    <View style={styles.row}>
      <View style={styles.rowText}>
        <SkeletonBlock width="55%" />
        <SkeletonBlock width="35%" height={8} />
      </View>
      <SkeletonBlock width={48} />
    </View>
  );
}

/**
 * A section still loading: a standard card holding `rows` SkeletonRows. The
 * drop-in for a bare spinner under a section header, so a detail screen
 * loads the way the main tabs do (UI consistency pass, 2026-11-14: Player
 * Stats, Team Stats, Scoreboard game, Performance and both model pages used
 * a spinner where Picks, Stats, Models and Record show placeholders).
 */
export function SkeletonList({
  label,
  rows = 3,
  style,
}: {
  /** What is loading, read as "Loading {label}". */
  label: string;
  rows?: number;
  /** Outer margins, to sit on the screen's own gutter. */
  style?: StyleProp<ViewStyle>;
}) {
  return (
    <Skeleton label={label} style={[styles.list, style]}>
      {Array.from({ length: rows }, (_, i) => (
        <SkeletonRow key={i} />
      ))}
    </Skeleton>
  );
}

const styles = StyleSheet.create({
  list: {
    ...card,
    paddingVertical: spacing.xs,
  },
  block: {
    borderRadius: radii.sm,
    backgroundColor: colors.noneSoft,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.md,
  },
  rowText: { flex: 1, gap: 6 },
});
