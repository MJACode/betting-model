import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, font, spacing } from '@/lib/theme';

/**
 * The Stats tab's tab bar, both levels of it.
 *
 * Matt, 2026-09-04: "for us batting and pitching is floating to nowhere, can
 * you have those have the same pattern as players and team." The stat groups
 * were small-caps text scrolling in open space, which read as a caption rather
 * than a control, while Players | Teams directly above them were proper
 * underlined tabs. Now both levels are the same component, so they cannot drift
 * apart again — the two-level pattern the category standardised on (DAZN and
 * FotMob both stack a section tab row under the league header; the competitor
 * stacks QB | WR/TE | RB under Players | Teams).
 *
 * Full width and evenly divided rather than scrolling: the widest set anywhere
 * is the NFL's four groups, which fits at 25% each.
 */
export function SegmentTabs<T extends string>({
  items,
  active,
  onChange,
  labelFor,
  /** The second level — one size down, and no top rule (see below). */
  second = false,
}: {
  items: readonly T[];
  active: T;
  onChange: (item: T) => void;
  labelFor?: (item: T) => string;
  second?: boolean;
}) {
  if (items.length < 2) return null;
  return (
    <View style={[styles.row, second && styles.rowSecond]} accessibilityRole="tablist">
      {items.map((item) => {
        const isActive = item === active;
        return (
          <Pressable
            key={item}
            onPress={() => onChange(item)}
            accessibilityRole="tab"
            accessibilityState={{ selected: isActive }}
            style={[styles.tab, second && styles.tabSecond, isActive && styles.tabActive]}
          >
            <Text
              style={[
                styles.text,
                second && styles.textSecond,
                isActive && styles.textActive,
              ]}
              numberOfLines={1}
            >
              {labelFor ? labelFor(item) : item}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

/** The stat groups — BATTING / PITCHING, the NFL's four, the Teams board's three. */
export function GroupTabs<T extends string>({
  groups,
  active,
  onChange,
}: {
  groups: readonly T[];
  active: T;
  onChange: (g: T) => void;
}) {
  return (
    <SegmentTabs
      items={groups}
      active={active}
      onChange={onChange}
      labelFor={(g) => g.toUpperCase()}
      second
    />
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    backgroundColor: colors.bgCard,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  // No top rule on the second level: it sits directly under the first, and two
  // hairlines a few points apart read as a boxed-in strip rather than one bar.
  rowSecond: {
    borderTopWidth: 0,
  },
  tab: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  tabSecond: {
    paddingVertical: 7,
  },
  tabActive: {
    borderBottomColor: colors.tint,
  },
  text: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  textSecond: {
    fontSize: font.size.footnote,
    letterSpacing: 0.3,
  },
  textActive: {
    color: colors.tint,
  },
});
