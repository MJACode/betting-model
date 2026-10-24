import React from 'react';
import { StyleSheet, Text, useWindowDimensions, View, type StyleProp, type ViewStyle } from 'react-native';
import { MODEL_BADGE_MAX, MODEL_BADGE_MIN, MODEL_BADGE_PAD, STACKED_BLOCK, stackModelBadge } from '@/lib/modelBadgeLayout';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * Badge plus the name (or pick label) beside it.
 *
 * Side by side at 1× on a 393pt phone. At 1.3× text, or on a window under
 * 360pt, the badge moves above the name. Beside the name the chip is 56–112pt
 * and the label shrinks onto one line. Above the name the chip grows with the
 * label, up to the row, and shrinks only if the label is wider than that row.
 */
export function ModelBadgeRow({
  badge,
  children,
  variant = 'pill',
  style,
}: {
  badge: string;
  children: React.ReactNode;
  /** Daily results keeps the squarer chip. Everywhere else is the pill. */
  variant?: 'pill' | 'tile';
  style?: StyleProp<ViewStyle>;
}) {
  const { width, fontScale } = useWindowDimensions();
  const stacked = stackModelBadge(fontScale, width);
  return (
    <View style={[stacked ? styles.stacked : styles.row, style]}>
      <View style={[styles.chip, variant === 'tile' && styles.tile, stacked ? styles.chipStacked : styles.chipCapped]}>
        <Text
          style={[styles.chipText, stacked ? styles.chipTextStacked : styles.chipTextCapped]}
          numberOfLines={1}
          adjustsFontSizeToFit
          // Beside the name the label area is 96pt. "LIVE Carries" at 2× is
          // 143pt, so 0.65 brings it inside. Above the name the chip is as
          // wide as the row, and this is only the backstop past that.
          minimumFontScale={0.65}
        >
          {badge}
        </Text>
      </View>
      <View style={stacked ? styles.bodyStacked : styles.body}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  stacked: {
    ...STACKED_BLOCK,
    flexDirection: 'column',
    alignItems: 'stretch',
    gap: spacing.xs,
  },
  chip: {
    backgroundColor: colors.noneSoft,
    paddingHorizontal: MODEL_BADGE_PAD / 2,
    paddingVertical: 3,
    borderRadius: radii.pill,
    minWidth: MODEL_BADGE_MIN,
    alignSelf: 'flex-start',
    flexShrink: 0,
    alignItems: 'center',
    justifyContent: 'center',
  },
  chipCapped: {
    maxWidth: MODEL_BADGE_MAX,
  },
  chipStacked: {
    maxWidth: '100%',
  },
  tile: {
    borderRadius: radii.sm,
    paddingVertical: 2,
  },
  chipText: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontWeight: font.weight.semibold,
    textAlign: 'center',
  },
  chipTextCapped: {
    // One line inside the 112pt box. Wider text shrinks; it does not wrap.
    maxWidth: MODEL_BADGE_MAX - MODEL_BADGE_PAD,
  },
  chipTextStacked: {
    maxWidth: '100%',
  },
  body: {
    flex: 1,
    flexShrink: 1,
  },
  bodyStacked: {
    ...STACKED_BLOCK,
    alignSelf: 'stretch',
  },
});
