import React, { useMemo } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

import { useParlaySlip } from '@/hooks/useParlaySlip';
import { useTodayPicks } from '@/hooks/useTodayPicks';
import { betslipSummary, resolveSlipLegs, BETSLIP_BAR_STAKE } from '@/lib/parlay';
import { formatAmerican, formatCurrency } from '@/lib/format';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * The persistent betslip bar — one line above the tab bar, on every page, but
 * ONLY while the slip has something in it. Tapping it opens the Betslip screen.
 *
 * This replaces the Betslip tab: a tab spends a permanent slot on a screen
 * that's empty most of the time, and it can't show what's in the slip from the
 * page you're building it on. The bar is the opposite — invisible at zero
 * selections, and once you've added a leg it follows you across the app with
 * the live combined price on it.
 *
 * Mounted ONCE at the app root (App.tsx) rather than per screen, so it survives
 * tab switches and also covers pushed stack screens (pick detail, player stats).
 * That's why it takes its position as props: the root can't ask React
 * Navigation for the tab-bar height (useBottomTabBarHeight only works inside a
 * tab screen), so App passes the measured offset down — see useTabBarHeight.
 */
export function BetslipBar({
  hidden,
  bottomOffset,
  onOpen,
}: {
  /** True on the Betslip screen itself and any screen that owns the bottom. */
  hidden: boolean;
  /** Pixels to lift the bar by — the tab bar's height, or 0 over a stack screen. */
  bottomOffset: number;
  onOpen: () => void;
}) {
  const slip = useParlaySlip();
  // Nothing selected = nothing to show, and (deliberately) nothing fetched:
  // the inner component owns the picks query, so an empty slip costs no
  // network at all.
  if (hidden || !slip.ready || slip.count === 0) return null;
  return (
    <BetslipBarContent
      keys={slip.keys}
      count={slip.count}
      bottomOffset={bottomOffset}
      onOpen={onOpen}
    />
  );
}

function BetslipBarContent({
  keys,
  count,
  bottomOffset,
  onOpen,
}: {
  keys: string[];
  count: number;
  bottomOffset: number;
  onOpen: () => void;
}) {
  const insets = useSafeAreaInsets();
  const { data, loading } = useTodayPicks();

  const summary = useMemo(() => {
    const { legs } = resolveSlipLegs(data, keys);
    return betslipSummary(legs, count);
  }, [data, keys, count]);

  // Over the tab bar the home-indicator inset is already spent by the tabs;
  // over a pushed stack screen the bar owns the bottom and must clear it itself.
  const overTabBar = bottomOffset > 0;
  const priced = summary.americanOdds != null && summary.payoutPerTen != null;
  // First paint after the slip's first leg: the price simply isn't known yet.
  // Show the slip with no price rather than flashing "no live price" at it.
  const pending = !priced && loading && data.length === 0;

  return (
    <Pressable
      onPress={onOpen}
      accessibilityRole="button"
      accessibilityLabel={
        priced
          ? `Open betslip, ${summary.count} selection${summary.count === 1 ? '' : 's'}, ${formatAmerican(summary.americanOdds)}`
          : `Open betslip, ${summary.count} selection${summary.count === 1 ? '' : 's'}`
      }
      style={({ pressed }) => [
        styles.bar,
        {
          bottom: bottomOffset,
          paddingBottom: overTabBar ? spacing.md : Math.max(insets.bottom, spacing.md),
        },
        pressed && styles.pressed,
      ]}
    >
      <View style={styles.left}>
        <Ionicons name="receipt-outline" size={20} color={colors.textInverse} />
        <Text style={styles.title}>Betslip</Text>
        <View style={styles.badge}>
          <Text style={styles.badgeText}>{summary.count}</Text>
        </View>
      </View>

      {priced ? (
        <View style={styles.right}>
          <View style={styles.priceRow}>
            <Text style={styles.priceLabel}>{summary.isParlay ? 'Parlay odds' : 'Odds'}</Text>
            <Text style={styles.priceValue}>{formatAmerican(summary.americanOdds)}</Text>
          </View>
          <View style={styles.priceRow}>
            <Text style={styles.payLabel}>${BETSLIP_BAR_STAKE} pays</Text>
            <Text style={styles.payValue}>{formatCurrency(summary.payoutPerTen)}</Text>
          </View>
        </View>
      ) : pending ? (
        <Ionicons name="chevron-forward" size={20} color={colors.textInverse} />
      ) : (
        // Every selection has settled or lost its price — say so instead of
        // showing odds we can't stand behind.
        <View style={styles.right}>
          <Text style={styles.priceValue}>Review</Text>
          <Text style={styles.payLabel}>no live price</Text>
        </View>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  bar: {
    position: 'absolute',
    left: 0,
    right: 0,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.tint,
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    shadowColor: '#000',
    shadowOpacity: 0.18,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: -2 },
    elevation: 8,
  },
  pressed: {
    opacity: 0.85,
  },
  left: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    flexShrink: 1,
  },
  title: {
    color: colors.textInverse,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
  },
  badge: {
    minWidth: 22,
    height: 22,
    borderRadius: radii.pill,
    paddingHorizontal: 6,
    backgroundColor: colors.textInverse,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeText: {
    color: colors.tint,
    fontSize: font.size.caption,
    fontWeight: font.weight.bold,
  },
  right: {
    alignItems: 'flex-end',
    gap: 2,
  },
  priceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  priceLabel: {
    color: '#FFFFFFB8',
    fontSize: font.size.footnote,
  },
  priceValue: {
    color: colors.textInverse,
    fontSize: font.size.callout,
    fontWeight: font.weight.bold,
  },
  payLabel: {
    color: '#FFFFFFB8',
    fontSize: font.size.caption,
  },
  payValue: {
    color: colors.textInverse,
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
  },
});
