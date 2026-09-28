import React from 'react';
import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from 'react-native';
import { InfoTooltip } from '@/components/InfoTooltip';
import { colors, font, spacing } from '@/lib/theme';

/**
 * A grouped-list section header — uppercase footnote in textSecondary, the
 * app's card-rhythm heading (UX_REVIEW §1) — with an optional ⓘ that opens
 * the explanation behind the section. One component for the team page and
 * the player page, because two detail pages built the same week had already
 * drifted on it (UX review, 2026-09-20).
 */
export function SectionTitle({
  title,
  tooltip,
  accessibilityLabel,
  style,
}: {
  title: string;
  tooltip?: { title: string; body: string };
  /** What VoiceOver says, when the printed title abbreviates ("SAT 11/28"). */
  accessibilityLabel?: string;
  /** Merged onto the row — e.g. no top margin for the first title in a list. */
  style?: StyleProp<ViewStyle>;
}) {
  return (
    <View style={[styles.row, style]}>
      {/* A heading, so the VoiceOver Headings rotor can jump between them. */}
      <Text style={styles.title} accessibilityRole="header" accessibilityLabel={accessibilityLabel ?? title}>
        {title.toUpperCase()}
      </Text>
      {tooltip ? (
        <InfoTooltip title={tooltip.title} body={tooltip.body} accessibilityLabel={`About ${title}`} />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    paddingHorizontal: spacing.lg,
    marginTop: spacing.lg,
    marginBottom: spacing.xs,
  },
  title: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
    letterSpacing: 0.4,
  },
});
