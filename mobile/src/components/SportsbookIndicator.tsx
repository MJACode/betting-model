// SportsbookIndicator — the Stats tab's book line: which sportsbook the stat
// board prices its odds column at, and a tap to change it.
//
// This is a STATS-PAGE control (Matt, 2026-09-04). The Picks and Signals boards
// carried the same line until then and no longer do: those boards show the best
// line across every book we price, off a pick modeled at DraftKings, and that
// is not the user's to switch. The label says "this page only" so the scope is
// never left implicit — the old line read as an app-wide pricing setting.
//
// There is no fallback here: pick FanDuel and a row FanDuel hasn't priced shows
// "—" (Matt, 2026-09-03: "if they select FanDuel we only show FanDuel").

import React, { useState } from 'react';
import { Pressable, StyleSheet, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { usePreferredBook } from '@/hooks/usePreferredBook';
import { bookName } from '@/lib/markets';
import { SportsbookPickerSheet } from '@/components/SportsbookPickerSheet';
import { colors, font, radii, spacing } from '@/lib/theme';

export function SportsbookIndicator() {
  const { book } = usePreferredBook();
  const [pickerOpen, setPickerOpen] = useState(false);

  return (
    <>
      <Pressable
        onPress={() => setPickerOpen(true)}
        accessibilityRole="button"
        accessibilityLabel={`Stats page sportsbook: ${bookName(book)}. Tap to switch.`}
        style={({ pressed }) => [styles.row, pressed && { opacity: 0.6 }]}
      >
        <Ionicons name="wallet-outline" size={13} color={colors.textTertiary} />
        <Text style={styles.text} numberOfLines={1}>
          {`Stats lines at ${bookName(book)} · this page only`}
        </Text>
        <Ionicons name="chevron-forward" size={12} color={colors.textTertiary} />
      </Pressable>
      <SportsbookPickerSheet visible={pickerOpen} onClose={() => setPickerOpen(false)} />
    </>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    alignSelf: 'flex-start',
    marginTop: spacing.xs,
    paddingVertical: 2,
    paddingHorizontal: 6,
    marginLeft: -6, // visually align the icon with the header text above
    borderRadius: radii.pill,
  },
  text: {
    flexShrink: 1,
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
});
