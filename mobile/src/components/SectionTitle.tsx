import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
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
}: {
  title: string;
  tooltip?: { title: string; body: string };
}) {
  return (
    <View style={styles.row}>
      <Text style={styles.title}>{title.toUpperCase()}</Text>
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
