import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, font, spacing } from '@/lib/theme';

/**
 * One label / value / note row inside a card — the "Since open · 5.5 → 6.5 ·
 * money on the over" shape the team and player pages read their market
 * numbers through. Shared so the two pages cannot drift (UX review,
 * 2026-09-20), and ONE VoiceOver element per row: label, value and note were
 * three stops each, so a card of twelve rows was thirty-six swipes, with "→"
 * read as "rightwards arrow".
 */
export function ReadRow({ label, value, note }: { label: string; value: string; note?: string }) {
  const spoken = `${label}, ${value.replace(/→/g, 'to')}${note ? `, ${note.replace(/→/g, 'to')}` : ''}`;
  return (
    <View style={styles.row} accessible accessibilityLabel={spoken}>
      <Text style={styles.label}>{label}</Text>
      <View style={styles.right}>
        <Text style={styles.value}>{value}</Text>
        {note ? <Text style={styles.note}>{note}</Text> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    paddingVertical: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
    gap: spacing.md,
  },
  // A basis, not a width: "Groundball rate" wraps at default type and a fixed
  // width clips it at larger sizes.
  label: { fontSize: font.size.footnote, color: colors.textSecondary, flexBasis: 96, flexShrink: 0 },
  right: { flex: 1, alignItems: 'flex-end' },
  value: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    fontVariant: ['tabular-nums'],
    textAlign: 'right',
  },
  note: { fontSize: font.size.caption, color: colors.textSecondary, marginTop: 1, textAlign: 'right' },
});
