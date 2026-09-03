import React, { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { usePreferredBook } from '@/hooks/usePreferredBook';
import { formatAmerican } from '@/lib/format';
import { bookLabel, bookName, BETTABLE_BOOKS } from '@/lib/markets';
import { priceBooksForParlay, type ParlayLeg } from '@/lib/parlay';
import { DK_GREEN, openBookBetslip } from '@/lib/sportsbookLinks';
import { SportsbookPickerSheet } from '@/components/SportsbookPickerSheet';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * "Open with" — this slip priced at every book a member can bet at
 * (BETTABLE_BOOKS), one tile per book:
 * combined odds where the book prices every leg, otherwise how many legs it
 * covers (N/M). The best payout is starred (ties all starred), the user's own
 * book is ringed, and tapping a tile opens that book (its first leg's betslip
 * link when we have one, else the book's app/site).
 *
 * The odds differ per book because each leg is re-priced at that book's own
 * line-shop snapshot; the slip's win probability is book-independent, so the
 * highest payout is simply the best place to put the slip on. DraftKings is
 * always fully priced (every leg requires a DK price to be a leg), so the row
 * always has at least one complete quote.
 */
export function BetslipBooksRow({ legs }: { legs: ParlayLeg[] }) {
  const { book: preferredBook } = usePreferredBook();
  const [pickerOpen, setPickerOpen] = useState(false);

  const quotes = useMemo(
    // Bettable books only: a tile opens the book, and Pinnacle / Bovada /
    // ESPN BET cannot take the slip (legFromPick prices no leg there anyway).
    () => priceBooksForParlay(legs, 1, BETTABLE_BOOKS),
    [legs],
  );

  if (legs.length === 0 || quotes.length === 0) return null;
  // "Best payout" only means something against another fully-priced book.
  // Since legs price at the same line only, DK is often the sole full quote,
  // and starring it with nothing to beat says "best" about nothing.
  const fullCount = quotes.filter((q) => q.americanOdds != null).length;

  return (
    <View style={styles.wrap}>
      <View style={styles.headerRow}>
        <Text style={styles.title}>Open with</Text>
        <Pressable
          onPress={() => setPickerOpen(true)}
          hitSlop={6}
          style={({ pressed }) => [styles.bookChip, pressed && styles.pressed]}
          accessibilityLabel={`Your sportsbook is ${bookName(preferredBook)}. Tap to switch.`}
        >
          <Ionicons name="wallet-outline" size={12} color={colors.tint} />
          <Text style={styles.bookChipText}>{bookName(preferredBook)}</Text>
          <Ionicons name="chevron-down" size={12} color={colors.tint} />
        </Pressable>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.tiles}
      >
        {quotes.map((q) => {
          const full = q.americanOdds != null;
          const isPreferred = q.book === preferredBook;
          const firstLink = q.links.find((l) => l != null) ?? null;
          return (
            <Pressable
              key={q.book}
              onPress={() => {
                void openBookBetslip(q.book, firstLink);
              }}
              accessibilityRole="button"
              accessibilityLabel={
                full
                  ? `Open ${bookName(q.book)}, combined odds ${formatAmerican(q.americanOdds!)}${
                      q.isBest && fullCount > 1 ? ', best payout' : ''
                    }${isPreferred ? ', your sportsbook' : ''}`
                  : `Open ${bookName(q.book)}, prices ${q.priced} of ${q.total} legs at these lines${
                      isPreferred ? ', your sportsbook' : ''
                    }`
              }
              style={({ pressed }) => [
                styles.tile,
                isPreferred && styles.tilePreferred,
                !full && styles.tilePartial,
                pressed && styles.pressed,
              ]}
            >
              {q.isBest && fullCount > 1 ? (
                <View style={styles.star}>
                  <Ionicons name="star" size={11} color={colors.best} />
                </View>
              ) : null}
              <View style={[styles.badge, q.isModelBook && styles.badgeDk]}>
                <Text style={[styles.badgeText, q.isModelBook && styles.badgeTextDk]}>
                  {bookLabel(q.book)}
                </Text>
              </View>
              <Text style={[styles.odds, !full && styles.oddsNa]}>
                {full ? formatAmerican(q.americanOdds!) : 'N/A'}
              </Text>
              <Text style={styles.coverage}>
                {q.priced}/{q.total} legs
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>

      <Text style={styles.hint}>
        ★ best payout · your book highlighted · tap a book to open it. N/M legs: that book
        doesn’t post every leg at the same line, so it can’t price the whole slip. Books can’t
        accept a whole parlay from a link, so add each leg there.
      </Text>

      <SportsbookPickerSheet visible={pickerOpen} onClose={() => setPickerOpen(false)} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  title: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  bookChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.tint,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  bookChipText: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  tiles: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  tile: {
    width: 86,
    alignItems: 'center',
    backgroundColor: colors.bgGrouped,
    borderRadius: radii.md,
    borderWidth: 1.5,
    borderColor: 'transparent',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.xs,
  },
  tilePreferred: {
    borderColor: colors.tint,
  },
  tilePartial: {
    opacity: 0.55,
  },
  star: {
    position: 'absolute',
    top: 4,
    left: 5,
  },
  badge: {
    minWidth: 40,
    borderRadius: radii.sm,
    backgroundColor: colors.noneSoft,
    alignItems: 'center',
    paddingVertical: 3,
    paddingHorizontal: 6,
  },
  badgeDk: {
    backgroundColor: DK_GREEN,
  },
  badgeText: {
    fontSize: font.size.caption,
    fontWeight: font.weight.bold,
    color: colors.textSecondary,
  },
  badgeTextDk: {
    color: '#000',
  },
  odds: {
    fontSize: font.size.callout,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    marginTop: 6,
    fontVariant: ['tabular-nums'],
  },
  oddsNa: {
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
  },
  coverage: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginTop: 2,
  },
  hint: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    lineHeight: 15,
    marginTop: spacing.sm,
  },
  pressed: {
    opacity: 0.6,
  },
});
