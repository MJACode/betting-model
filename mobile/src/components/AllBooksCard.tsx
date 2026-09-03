import React from 'react';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';

import {
  allBookPrices,
  bookName,
  gameMarketForModel,
  propMarketForModel,
  MODEL_BOOK,
} from '@/lib/markets';
import { formatAmerican } from '@/lib/format';
import { usePreferredBook } from '@/hooks/usePreferredBook';
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
 */
export function AllBooksCard({
  pick,
  bookRows,
}: {
  pick: Pick;
  bookRows: BookPricedRow[] | undefined;
}) {
  const { book: preferred } = usePreferredBook();

  const market = gameMarketForModel(pick.model_id) ?? propMarketForModel(pick.model_id);
  const quotes = allBookPrices(bookRows ?? [], pick.pick_side, market);

  // One book pricing a side isn't a comparison — nothing to shop.
  if (quotes.length < 2) return null;

  const showLine = quotes.some((q) => q.line != null);

  return (
    <View style={styles.card}>
      <Text style={styles.title}>All books</Text>
      <Text style={styles.subtitle}>
        Same bet, priced at each book. Best payout first.
      </Text>

      <View style={styles.headerRow}>
        <Text style={[styles.h, styles.colBook]}>Book</Text>
        {showLine ? <Text style={[styles.h, styles.colLine]}>Line</Text> : null}
        <Text style={[styles.h, styles.colPrice]}>Price</Text>
      </View>

      {quotes.map((q) => {
        const isPreferred = q.bookmaker === preferred;
        return (
          <Pressable
            key={q.bookmaker}
            style={[styles.row, isPreferred && styles.rowPreferred]}
            disabled={!q.link}
            onPress={() => {
              if (q.link) Linking.openURL(q.link).catch(() => {});
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
                {isPreferred ? <Text style={styles.yoursTag}>yours</Text> : null}
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
        DraftKings line. Tap a book to open its betslip.
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
  rowPreferred: {
    backgroundColor: colors.bgGrouped,
    borderRadius: radii.sm,
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
  yoursTag: {
    fontSize: font.size.caption,
    color: colors.tint,
    fontWeight: '600',
    backgroundColor: colors.noneSoft,
    borderRadius: radii.pill,
    paddingHorizontal: 6,
    overflow: 'hidden',
  },
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
