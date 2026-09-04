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

import { usePreferredBooks } from '@/hooks/usePreferredBooks';
import { booksName, MODEL_BOOK } from '@/lib/markets';
import { SportsbookPickerSheet } from '@/components/SportsbookPickerSheet';
import { colors, font, radii, spacing } from '@/lib/theme';

export function SportsbookIndicator() {
  const { books } = usePreferredBooks();
  const [pickerOpen, setPickerOpen] = useState(false);

  // A DraftKings-only member is being told "Picks stay at DraftKings" about a
  // difference they cannot see — for them the line is just the book. The
  // qualifier appears once it is true of something, and says what it protects
  // rather than naming a page (UX review). With several books the line also
  // states the rule, because the cells no longer share one book.
  const onlyModelBook = books.length === 1 && books[0] === MODEL_BOOK;
  const label = onlyModelBook
    ? `Stats lines at ${booksName(books)}`
    : `${books.length > 1 ? 'Best of ' : 'Stats lines at '}${booksName(books)} · Picks stay at DraftKings`;

  return (
    <>
      <Pressable
        onPress={() => setPickerOpen(true)}
        accessibilityRole="button"
        // Voice Control matches spoken commands against the accessibility
        // label, so it has to CONTAIN the visible words — a label that renamed
        // the row made "tap Stats lines" fail on the only entry to the picker
        // outside Settings (UX review).
        accessibilityLabel={`${label}. Your sportsbooks — tap to change.`}
        // The row is caption-height, and with the Picks board's line removed it
        // is the only entry to the picker outside Settings — a missed tap has
        // nowhere else to go (UX review).
        hitSlop={{ top: 12, bottom: 12, left: 8, right: 8 }}
        style={({ pressed }) => [styles.row, pressed && { opacity: 0.6 }]}
      >
        <Ionicons name="wallet-outline" size={13} color={colors.textTertiary} />
        <Text style={styles.text} numberOfLines={1}>
          {label}
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
