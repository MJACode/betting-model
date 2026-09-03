// BookLinesRow — "Betting lines": every book a member can place this pick at,
// best price first, each chip a hand-off to that book's betslip.
//
// Replaces two things on the card (Matt, 2026-09-03):
//   - the single full-width "Bet on DraftKings" button, and
//   - the tap-to-switch-sportsbook price column, which changed nothing visible
//     whenever the chosen book had no row for the pick.
// The Discord post already reads "-102 @ DraftKings · also +100 @ ESPN BET";
// this is the same information as buttons.
//
// What a chip means: the SAME bet (same side, same line — docs/best_line.md §5)
// at that book, at that book's latest price. The record chip (DK, or the NFL
// card's soft book) is the stored number the pick was given at and never
// re-prices. The user's own book is ringed; the best payout says "best" in
// words, not just colour.
//
// Live picks (is_live) get one DraftKings chip and a line saying why — the
// in-play model prices and places at DK only.

import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { formatAmerican } from '@/lib/format';
import { bookLabel, bookName, pickLineQuotes, selectLineChips, MODEL_BOOK } from '@/lib/markets';
import { DK_GREEN, openBookBetslip } from '@/lib/sportsbookLinks';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { BookPricedRow, Pick } from '@/types';

interface Props {
  pick: Pick;
  bookRows: BookPricedRow[] | undefined;
  /** The user's sportsbook (usePreferredBook) — ringed when it prices the pick. */
  preferredBook: string;
  /** Where "+N more" goes — the detail screen's All-books table. Omit on the
   *  detail screen itself, where every book is already listed below. */
  onMore?: () => void;
  /** How many chips to show before "+N more". */
  maxChips?: number;
}

export function BookLinesRow({ pick, bookRows, preferredBook, onMore, maxChips = 4 }: Props) {
  const quotes = pickLineQuotes(pick, bookRows ?? []);
  if (quotes.length === 0) return null;
  const live = pick.is_live === true;
  const { shown, hidden } = selectLineChips(quotes, preferredBook, onMore ? maxChips : 99);

  return (
    <View style={styles.wrap}>
      <View style={styles.headerRow}>
        <Text style={styles.title}>{live ? 'Bet at' : 'Betting lines'}</Text>
        {!live && quotes.length > 1 ? (
          <Text style={styles.hint}>best first · tap to place</Text>
        ) : null}
      </View>
      <View style={styles.chips}>
        {shown.map((q) => {
          const isDk = q.bookmaker === MODEL_BOOK;
          const yours = q.bookmaker === preferredBook;
          const tag = q.isBest && quotes.length > 1 ? 'best' : q.isRecord && !isDk ? 'given' : null;
          return (
            <Pressable
              key={q.bookmaker}
              onPress={() => {
                void openBookBetslip(q.bookmaker, q.link);
              }}
              hitSlop={7}
              accessibilityRole="button"
              accessibilityLabel={`Bet at ${bookName(q.bookmaker)}, ${formatAmerican(q.price)}${
                tag ? `, ${tag} price` : ''
              }${yours ? ', your sportsbook' : ''}`}
              style={({ pressed }) => [
                styles.chip,
                isDk && styles.chipDk,
                yours && styles.chipYours,
                pressed && styles.pressed,
              ]}
            >
              <Text style={[styles.chipBook, isDk && styles.chipTextDk]}>
                {bookLabel(q.bookmaker)}
              </Text>
              <Text style={[styles.chipPrice, isDk && styles.chipTextDk]}>
                {formatAmerican(q.price)}
              </Text>
              {tag ? (
                <Text style={[styles.chipTag, isDk ? styles.chipTextDk : styles.chipTagBest]}>
                  {tag}
                </Text>
              ) : null}
              <Ionicons
                name="open-outline"
                size={11}
                color={isDk ? colors.textPrimary : colors.textTertiary}
              />
            </Pressable>
          );
        })}
        {hidden > 0 && onMore ? (
          <Pressable
            onPress={onMore}
            hitSlop={7}
            accessibilityRole="button"
            accessibilityLabel={`${hidden} more sportsbooks price this bet. Open pick details`}
            style={({ pressed }) => [styles.chip, styles.chipMore, pressed && styles.pressed]}
          >
            <Text style={styles.chipMoreText}>+{hidden} more</Text>
          </Pressable>
        ) : null}
      </View>
      {live ? (
        <Text style={styles.note}>
          Live picks are priced and placed at DraftKings only — the in-play model reads DK’s
          line, so your sportsbook setting doesn’t apply here.
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    marginTop: spacing.md,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    marginBottom: spacing.xs + 2,
  },
  title: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  hint: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingVertical: 7,
    paddingHorizontal: spacing.md,
    borderRadius: radii.pill,
    backgroundColor: colors.bgGrouped,
    borderWidth: 1.5,
    borderColor: 'transparent',
  },
  // DraftKings keeps its brand green (the one third-party colour the app
  // carries, shared with the picker and the betslip row).
  chipDk: {
    backgroundColor: DK_GREEN,
  },
  chipYours: {
    borderColor: colors.tint,
  },
  chipMore: {
    backgroundColor: colors.bgCard,
    borderColor: colors.separatorOpaque,
  },
  chipBook: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
    letterSpacing: 0.3,
  },
  chipPrice: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    fontVariant: ['tabular-nums'],
  },
  chipTextDk: {
    color: colors.textPrimary,
  },
  chipTag: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
  },
  chipTagBest: {
    color: colors.positive,
  },
  chipMoreText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  note: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    lineHeight: 16,
    marginTop: spacing.sm,
  },
  pressed: {
    opacity: 0.6,
  },
});
