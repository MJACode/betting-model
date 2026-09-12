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
  /** Inline in a control row rather than spanning the screen: no card, no top
   *  rule, and the tabs size to their labels instead of splitting the width.
   *  Added 2026-09-12 so Hit Rates | Averages could stop spending a full 38pt
   *  row on a two-value switch and ride the end of the time-window row — the
   *  roles below travel with it, which is the whole reason it reuses this
   *  component rather than hand-rolling a segment (UX review, 2026-09-12). */
  compact = false,
}: {
  items: readonly T[];
  active: T;
  onChange: (item: T) => void;
  labelFor?: (item: T) => string;
  second?: boolean;
  compact?: boolean;
}) {
  if (items.length < 2) return null;
  return (
    <View
      style={[styles.row, second && styles.rowSecond, compact && styles.rowCompact]}
      accessibilityRole="tablist"
    >
      {items.map((item) => {
        const isActive = item === active;
        return (
          <Pressable
            key={item}
            onPress={() => onChange(item)}
            accessibilityRole="tab"
            accessibilityState={{ selected: isActive }}
            // The tabs are 33-38pt tall, under the 44pt HIG floor, and adding
            // height is the one thing this screen cannot spend (UX review,
            // 2026-09-12). hitSlop makes the target up instead.
            hitSlop={{ top: 6, bottom: 6, left: 4, right: 4 }}
            style={[
              styles.tab,
              second && styles.tabSecond,
              compact && styles.tabCompact,
              isActive && (second || compact ? styles.tabActiveSecond : styles.tabActive),
            ]}
          >
            <Text
              style={[
                styles.text,
                second && styles.textSecond,
                compact && styles.textCompact,
                isActive && (second || compact ? styles.textActiveSecond : styles.textActive),
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
  /** False on a screen with no bar above it — the player detail screen has no
   *  first level, so its group row needs the top rule and the full size or it
   *  is exactly the "floating to nowhere" this component was built to end. */
  second = true,
}: {
  groups: readonly T[];
  active: T;
  onChange: (g: T) => void;
  second?: boolean;
}) {
  return (
    <SegmentTabs
      items={groups}
      active={active}
      onChange={onChange}
      second={second}
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
  // Inline: it is a control sitting in a control row, not a bar spanning the
  // screen, so it sheds the card and the rule that made it look like one.
  rowCompact: {
    backgroundColor: 'transparent',
    borderTopWidth: 0,
  },
  tab: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  // The second level is not just smaller: a 1px rule against the first level's
  // 2px, and the active label in textPrimary rather than tint. Two 2px tint
  // underlines thirty points apart read as one control that wrapped, and the
  // lower one — nearest the data — was pulling the eye first. Tint is reserved
  // for the level that changes the board's subject.
  tabSecond: {
    paddingVertical: 7,
    borderBottomWidth: 1,
  },
  // No flex: the inline control sizes to its two labels and leaves the rest of
  // the row to the chips it shares it with.
  tabCompact: {
    // flex: 0, not `undefined` — RN flattens style arrays key by key, so an
    // undefined value is not a reliable way to unset the `flex: 1` above it.
    // 0 is flexGrow 0 / flexShrink 0 / flexBasis auto, which is what "size to
    // your label" means here.
    flex: 0,
    paddingVertical: 6,
    paddingHorizontal: spacing.sm,
    // 1px, and the active label in textPrimary rather than tint (see
    // `tabSecond` above): a 2px tint underline here would be the SECOND one on
    // the screen, ~140pt under Players | Teams, and tint is reserved for the
    // level that changes the board's subject. Uppercase is deliberately NOT
    // inherited — this sits in a row of sentence-case pill chips.
    borderBottomWidth: 1,
  },
  tabActive: {
    borderBottomColor: colors.tint,
  },
  tabActiveSecond: {
    borderBottomColor: colors.textPrimary,
  },
  text: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  textSecond: {
    fontSize: font.size.footnote,
    letterSpacing: 0.3,
    // Uppercase as a style, so VoiceOver reads "Batting" and not B-A-T-T-I-N-G
    // the day a group name is an initialism.
    textTransform: 'uppercase',
  },
  textCompact: {
    fontSize: font.size.footnote,
  },
  textActiveSecond: {
    color: colors.textPrimary,
  },
  textActive: {
    color: colors.tint,
  },
});
