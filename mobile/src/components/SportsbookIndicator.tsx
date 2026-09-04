// SportsbookIndicator — one always-visible line on the pick boards naming the
// sportsbook whose prices and "Bet on …" buttons are being shown.
//
// Tapping it opens the sportsbook picker sheet in place (it used to route to
// Settings, which made "switch books" a three-screen trip). The preference is
// the shared usePreferredBook store, so a pick made here follows the user to
// every board, card, and betslip.
//
// The models always price against DraftKings — this only concerns what the
// user is SHOWN, mirroring displayQuoteForPick's resolution: their book's
// price where it has one, DK's (labeled) where it doesn't.

import React, { useState } from 'react';
import { Pressable, StyleSheet, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { usePreferredBook } from '@/hooks/usePreferredBook';
import { bookLabel, bookName, MODEL_BOOK } from '@/lib/markets';
import { SportsbookPickerSheet } from '@/components/SportsbookPickerSheet';
import { colors, font, radii, spacing } from '@/lib/theme';

export function SportsbookIndicator({
  fallsBackToModelBook = true,
}: {
  /** Whether this board substitutes the DraftKings number when the user's
   *  book has not priced a bet. The pick boards do (displayQuoteForPick);
   *  the Stats tab does NOT — Matt, 2026-09-03: "if they select FanDuel we
   *  only show FanDuel" — so its label must not promise a fallback. */
  fallsBackToModelBook?: boolean;
} = {}) {
  const { book, isNonModelBook } = usePreferredBook();
  const [pickerOpen, setPickerOpen] = useState(false);

  // DK (the default + the modeled book) gets the short form; any other book
  // also explains the fallback, since coverage gaps make "why does this pick
  // say DK?" the first question a non-DK bettor asks.
  const label =
    isNonModelBook && fallsBackToModelBook
      ? `Prices & bets at ${bookName(book)} · ${bookLabel(MODEL_BOOK)} shown when ${bookLabel(book)} doesn’t price a bet`
      : `Prices & bets at ${bookName(book)}`;

  return (
    <>
      <Pressable
        onPress={() => setPickerOpen(true)}
        accessibilityRole="button"
        accessibilityLabel={`Sportsbook: ${bookName(book)}. Tap to switch.`}
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
