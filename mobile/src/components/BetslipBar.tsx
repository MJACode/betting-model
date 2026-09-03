import React, { useMemo } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

import { useParlaySlip } from '@/hooks/useParlaySlip';
import { useResolvedSlip } from '@/hooks/useResolvedSlip';
import { betslipSummary, shouldShowBetslipBar, BETSLIP_BAR_STAKE } from '@/lib/parlay';
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
 * The bar shows only when the slip holds a bet we can actually price. A
 * selection that no longer resolves against today's board (its game ended, the
 * market de-listed) is pruned by useResolvedSlip rather than counted, so the
 * bar can never sit there advertising selections that nothing on screen reads
 * as selected. The one exception is the first load after an add, where the
 * board hasn't landed yet and we say so with a chevron instead of a price.
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
    <BetslipBarContent bottomOffset={bottomOffset} onOpen={onOpen} />
  );
}

function BetslipBarContent({
  bottomOffset,
  onOpen,
}: {
  bottomOffset: number;
  onOpen: () => void;
}) {
  const insets = useSafeAreaInsets();
  const { slip, legs, resolving } = useResolvedSlip();

  const summary = useMemo(
    () => betslipSummary(legs, slip.count),
    [legs, slip.count],
  );

  // Over the tab bar the home-indicator inset is already spent by the tabs;
  // over a pushed stack screen the bar owns the bottom and must clear it itself.
  const overTabBar = bottomOffset > 0;
  const priced = summary.americanOdds != null && summary.payoutPerTen != null;

  // Nothing in the slip resolves to a live, priceable bet — there is no bet to
  // show, so show no bar. Any selection behind this has already been pruned by
  // useResolvedSlip; what's left is an untrusted board (offline, or a genuinely
  // empty slate), where hiding is still the honest answer. The exception is the
  // first paint after an add, where the board hasn't landed yet: that renders
  // with a chevron instead of a price, so the add visibly registers.
  if (!shouldShowBetslipBar(summary, resolving)) return null;

  // The badge counts what's actually in the slip: once the board is known the
  // pruner has reconciled the two, and while it's still loading the raw
  // selection count is the only number we have.
  const badgeCount = priced ? summary.resolved : summary.count;

  return (
    <Pressable
      onPress={onOpen}
      accessibilityRole="button"
      accessibilityLabel={
        priced
          ? `Open betslip, ${badgeCount} selection${badgeCount === 1 ? '' : 's'}, ${formatAmerican(summary.americanOdds)}`
          : `Open betslip, ${badgeCount} selection${badgeCount === 1 ? '' : 's'}`
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
          <Text style={styles.badgeText}>{badgeCount}</Text>
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
      ) : (
        <Ionicons name="chevron-forward" size={20} color={colors.textInverse} />
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
    // Floats over the navy tab bar, so it takes the banner's RAISED navy and
    // the amber badge — the same two-tone the brand mark uses.
    backgroundColor: colors.brandNavyRaised,
    // Raised navy on navy is 1.15:1, so the bar needs an edge: the amber rule
    // along the bottom of the X banner, 2pt.
    borderTopWidth: 2,
    borderTopColor: colors.brand,
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
    backgroundColor: colors.brand,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeText: {
    color: colors.brandInk,
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
