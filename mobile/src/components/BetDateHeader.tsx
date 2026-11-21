import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { unitsSpeech } from '@/lib/a11y';
import type { DateSummary } from '@/lib/betDateGroups';
import { FLAT_UNIT_TONE_SCALE, dayLabelET, dayLabelSpokenET, formatFlatUnits, todayET } from '@/lib/format';
import { colors, font, opacity, pnlColor, spacing } from '@/lib/theme';

/** "Sat 11/28", with "/25" on a day from another year so two years never share a label. */
function dayText(date: string): string {
  if (!date) return 'No date';
  const label = dayLabelET(date);
  return date.slice(0, 4) === todayET().slice(0, 4) || !/\d+\/\d+$/.test(label) ? label : `${label}/${date.slice(2, 4)}`;
}

function daySpeech(date: string): string {
  if (!date) return 'No date';
  const spoken = dayLabelSpokenET(date);
  return date.slice(0, 4) === todayET().slice(0, 4) || /^(Today|Tomorrow|Yesterday)$/.test(spoken)
    ? spoken
    : `${spoken}, ${date.slice(0, 4)}`;
}

/**
 * One bet date's header in the Performance tab's lists: the day, how many
 * bets, its units and W-L, and a chevron. Tapping folds or opens the day
 * (lib/betDateGroups.ts).
 */
export function BetDateHeader({
  date,
  count,
  summary,
  open,
  onToggle,
}: {
  date: string;
  count: number;
  summary: DateSummary;
  open: boolean;
  onToggle: () => void;
}) {
  const decided = summary.wins + summary.losses > 0;
  const record =
    summary.settled > 0
      ? `${summary.wins}–${summary.losses}` + (summary.pushes > 0 ? `–${summary.pushes}` : '')
      : null;
  const sub = [
    `${count} ${count === 1 ? 'bet' : 'bets'}`,
    record,
    summary.open > 0 ? `${summary.open} open` : null,
    summary.other > 0 ? `${summary.other} no action` : null,
  ]
    .filter(Boolean)
    .join(' · ');
  const speech = unitsSpeech(
    [
      daySpeech(date),
      `${count} ${count === 1 ? 'bet' : 'bets'}`,
      decided ? formatFlatUnits(summary.net) : null,
      summary.settled > 0
        ? `${summary.wins} won, ${summary.losses} lost` + (summary.pushes > 0 ? `, ${summary.pushes} pushed` : '')
        : null,
      summary.open > 0 ? `${summary.open} open` : null,
      summary.other > 0 ? `${summary.other} no action` : null,
    ]
      .filter(Boolean)
      .join(', '),
  );
  return (
    <Pressable
      onPress={onToggle}
      accessibilityRole="button"
      accessibilityLabel={speech}
      accessibilityState={{ expanded: open }}
      accessibilityHint={open ? 'Hides this day’s bets' : 'Shows this day’s bets'}
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}
    >
      <Ionicons
        name={open ? 'chevron-down' : 'chevron-forward'}
        size={14}
        color={colors.textTertiary}
        style={styles.chevron}
      />
      <View style={styles.main}>
        <Text style={styles.day}>{dayText(date)}</Text>
        <Text style={styles.sub}>{sub}</Text>
      </View>
      {decided ? (
        <Text style={[styles.net, { color: pnlColor(summary.net, 2, FLAT_UNIT_TONE_SCALE) }]}>
          {formatFlatUnits(summary.net)}
        </Text>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  pressed: { opacity: opacity.pressed },
  chevron: { marginRight: spacing.sm },
  main: { flex: 1 },
  day: { fontSize: font.size.footnote, fontWeight: font.weight.semibold, color: colors.textPrimary },
  sub: { fontSize: font.size.caption, color: colors.textTertiary, marginTop: spacing.xs },
  net: { fontSize: font.size.footnote, fontWeight: font.weight.semibold, marginLeft: spacing.md },
});
