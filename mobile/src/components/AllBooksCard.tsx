import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import {
  allBookPrices,
  bookName,
  gameMarketForModel,
  isBettableBook,
  propMarketForModel,
  MODEL_BOOK,
} from '@/lib/markets';
import { formatAmerican } from '@/lib/format';
import { openBookBetslip } from '@/lib/sportsbookLinks';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { BookPricedRow, Pick } from '@/types';

/**
 * "All books" comparison for one pick — every sportsbook that prices this side,
 * best payout first.
 *
 * The model's number is always DraftKings (that's the price the edge on the card
 * is computed from). This card is purely about where the user can get the best
 * version of the same bet, so it labels the DK row as the modeled price and
 * badges whichever book pays most.
 *
 * The line is shown next to the price because a better price on a worse number
 * is not actually a better bet — the user needs to see both.
 *
 * No row is marked as "yours": the book picker sets the Stats lines and the
 * betslip's bet button, and it does not reach the pick boards
 * (Matt, 2026-09-04).
 */
export function AllBooksCard({
  pick,
  bookRows,
}: {
  pick: Pick;
  bookRows: BookPricedRow[] | undefined;
}) {
  const market = gameMarketForModel(pick.model_id) ?? propMarketForModel(pick.model_id);
  const quotes = allBookPrices(bookRows ?? [], pick.pick_side, market);

  // One book pricing a side isn't a comparison — nothing to shop.
  if (quotes.length < 2) return null;

  const showLine = quotes.some((q) => q.line != null);

  return (
    <View style={styles.card}>
      <Text style={styles.title}>All books</Text>
      <Text style={styles.subtitle}>
        Every book and line, including ones at a different number or that you can’t bet.
        Best payout first.
      </Text>

      <View style={styles.headerRow}>
        <Text style={[styles.h, styles.colBook]}>Book</Text>
        {showLine ? <Text style={[styles.h, styles.colLine]}>Line</Text> : null}
        <Text style={[styles.h, styles.colPrice]}>Price</Text>
      </View>

      {quotes.map((q) => {
        // Pinnacle / Bovada / ESPN BET are reference prices — shown, because
        // the number is real, but never a hand-off (the picker and the chip
        // row exclude them for the same reason).
        const reference = !isBettableBook(q.bookmaker);
        return (
          <Pressable
            key={q.bookmaker}
            style={[styles.row, reference && styles.rowReference]}
            accessibilityRole="button"
            accessibilityState={{ disabled: reference }}
            disabled={reference}
            accessibilityLabel={`${reference ? '' : 'Open '}${bookName(q.bookmaker)}, ${formatAmerican(q.price)}${
              q.isBest ? ', best price' : ''
            }${reference ? ', reference price, not bettable' : ''}`}
            // The shared hand-off: the betslip link, else the book's app or
            // site. A bettable book with no per-outcome link still opens,
            // rather than a dead row beside live ones.
            onPress={() => {
              void openBookBetslip(q.bookmaker, q.link);
            }}
          >
            <View style={styles.colBook}>
              <Text style={styles.bookName} numberOfLines={1}>
                {bookName(q.bookmaker)}
              </Text>
              <View style={styles.tagRow}>
                {q.bookmaker === MODEL_BOOK ? (
                  <Text style={styles.modelTag}>modeled</Text>
                ) : null}
                {reference ? <Text style={styles.modelTag}>reference</Text> : null}
              </View>
            </View>

            {showLine ? (
              <Text style={[styles.line, styles.colLine]}>
                {q.line != null ? q.line : '—'}
              </Text>
            ) : null}

            <View style={styles.colPrice}>
              <Text style={[styles.price, q.isBest && styles.priceBest]}>
                {formatAmerican(q.price)}
              </Text>
              {q.isBest ? <Text style={styles.bestTag}>best</Text> : null}
            </View>
          </Pressable>
        );
      })}

      <Text style={styles.footnote}>
        Model probability, edge, and parlay pricing always come from the
        DraftKings line. Tap a book to open its betslip (reference books excluded).
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.md,
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
  },
  title: {
    fontSize: font.size.headline,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  subtitle: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
    marginBottom: spacing.sm,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingBottom: 6,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  h: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  rowReference: {
    opacity: 0.6,
  },
  colBook: { flex: 1 },
  colLine: { width: 56, textAlign: 'center' },
  colPrice: { width: 84, alignItems: 'flex-end' },
  bookName: {
    fontSize: font.size.body,
    color: colors.textPrimary,
    fontWeight: '600',
  },
  tagRow: { flexDirection: 'row', gap: 6, marginTop: 2 },
  modelTag: { fontSize: font.size.caption, color: colors.textSecondary },
  line: { fontSize: font.size.body, color: colors.textSecondary },
  price: {
    fontSize: font.size.body,
    color: colors.textPrimary,
    fontWeight: '700',
    fontVariant: ['tabular-nums'],
  },
  priceBest: { color: colors.positive },
  bestTag: {
    fontSize: font.size.caption,
    color: colors.positive,
    fontWeight: '600',
  },
  footnote: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginTop: spacing.sm,
  },
});
