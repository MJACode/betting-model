// SportsbookIndicator — one always-visible line on the pick boards naming the
// sportsbook whose prices and "Bet on …" buttons are being shown.
//
// The preference lives in Settings ("Your sportsbook"), but nothing on the
// boards said which book was active — so a FanDuel bettor seeing a DK-priced
// prop (coverage fallback) read the whole app as DraftKings-only. This row
// makes the active book explicit everywhere picks render, and tapping it jumps
// straight to Settings to change it.
//
// The models always price against DraftKings — this only concerns what the
// user is SHOWN, mirroring displayQuoteForPick's resolution: their book's
// price where it has one, DK's (labeled) where it doesn't.

import React from 'react';
import { Pressable, StyleSheet, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { usePreferredBook } from '@/hooks/usePreferredBook';
import { bookLabel, bookName, MODEL_BOOK } from '@/lib/markets';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

export function SportsbookIndicator() {
  const navigation = useNavigation<Nav>();
  const { book, isNonModelBook } = usePreferredBook();

  // DK (the default + the modeled book) gets the short form; any other book
  // also explains the fallback, since coverage gaps make "why does this pick
  // say DK?" the first question a non-DK bettor asks.
  const label = isNonModelBook
    ? `Prices & bets at ${bookName(book)} · ${bookLabel(MODEL_BOOK)} shown when ${bookLabel(book)} doesn’t price a bet`
    : `Prices & bets at ${bookName(book)}`;

  return (
    <Pressable
      onPress={() => navigation.navigate('Settings')}
      accessibilityRole="button"
      accessibilityLabel={`Sportsbook: ${bookName(book)}. Change in settings.`}
      style={({ pressed }) => [styles.row, pressed && { opacity: 0.6 }]}
    >
      <Ionicons name="wallet-outline" size={13} color={colors.textTertiary} />
      <Text style={styles.text} numberOfLines={1}>
        {label}
      </Text>
      <Ionicons name="chevron-forward" size={12} color={colors.textTertiary} />
    </Pressable>
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
