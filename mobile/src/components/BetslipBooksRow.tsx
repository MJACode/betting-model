import React, { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { InfoTooltip } from '@/components/InfoTooltip';
import { ParlayDkHandoff, type HandoffLeg } from '@/components/ParlayDkHandoff';
import { formatAmerican } from '@/lib/format';
import { bookLabel, bookName, BETTABLE_BOOKS } from '@/lib/markets';
import { handoffAtBook, matchupForLeg, priceBooksForParlay, type ParlayLeg } from '@/lib/parlay';
import { DK_GREEN } from '@/lib/sportsbookLinks';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * "Open with" — this slip priced at every book a member can bet at
 * (BETTABLE_BOOKS), one tile per book:
 * combined odds where the book prices every leg, otherwise how many legs it
 * covers (N/M). The best payout is starred (ties all starred).
 *
 * THIS ROW IS THE BET CONTROL (Matt, 2026-09-08): "why does it say bet DK at
 * the bottom when we give the user the ability to bet with multiple
 * sportsbooks". A green "Bet on <one book>" button used to sit under the legs,
 * naming the member's stored preference — or DraftKings when theirs could not
 * take the slip — while this row, 40pt above it, already priced the slip at
 * every book. Two controls for one action, and the button was the one that
 * showed no prices.
 *
 * So a tile now opens the same leg-by-leg hand-off sheet that button opened, at
 * that book. It is the tap that chooses the book, which is what the old
 * button's DraftKings fallback existed to guess. A partial tile opens too — its
 * sheet marks the legs that book does not post, rather than pretending to a
 * quote it cannot give.
 *
 * The odds differ per book because each leg is re-priced at that book's own
 * line-shop snapshot; the slip's win probability is book-independent, so the
 * highest payout is simply the best place to put the slip on. DraftKings
 * prices every pick and custom leg, but a Stats LINE leg it never posted
 * (lib/lineLegs.ts) leaves its tile partial like any other book's — so the
 * row can, on such a slip, hold no complete quote at all.
 */
export function BetslipBooksRow({ legs }: { legs: ParlayLeg[] }) {
  const quotes = useMemo(
    // Bettable books only: a tile opens the book, and Pinnacle / Bovada /
    // ESPN BET cannot take the slip (legFromPick prices no leg there anyway).
    () => priceBooksForParlay(legs, 1, BETTABLE_BOOKS),
    [legs],
  );
  // The book whose hand-off sheet is open, or null. Held as the book key rather
  // than a boolean so the sheet's own `book` prop cannot drift from the tile
  // that opened it.
  const [openBook, setOpenBook] = useState<string | null>(null);
  const handoff = useMemo(
    () => (openBook ? handoffAtBook(legs, openBook) : null),
    [legs, openBook],
  );
  const handoffLegs: HandoffLeg[] = useMemo(
    () =>
      handoff == null
        ? []
        : legs.map((l, i) => ({
            key: String(l.pickId),
            label: l.label,
            matchup: matchupForLeg(l.game),
            // THAT BOOK'S price, not DraftKings' (UX review, 2026-09-08). The
            // whole premise of this row is that the prices differ, so listing DK
            // numbers under a sheet titled "Bet on FanDuel" is two prices for
            // one slip, one tap apart. Falls back to the leg's DK price only
            // where the book prices no leg — the sheet marks those `posted:
            // false` anyway.
            americanOdds: handoff.prices[i] ?? l.americanOdds,
            betLink: handoff.links[i] ?? null,
            posted: handoff.posted[i] ?? true,
          })),
    [legs, handoff],
  );

  if (legs.length === 0 || quotes.length === 0) return null;
  // "Best payout" only means something against another fully-priced book.
  // Since legs price at the same line only, DK is often the sole full quote,
  // and starring it with nothing to beat says "best" about nothing.
  const fullCount = quotes.filter((q) => q.americanOdds != null).length;

  return (
    <View style={styles.wrap}>
      {/* Title, an (i) for the mechanics, and the star's meaning stated where
          the stars are — the reference betslip Matt sent puts the legend on
          this row rather than in a paragraph under the tiles, and a legend
          beside the thing it labels is read; a paragraph below it is not. */}
      <View style={styles.headerRow}>
        <View style={styles.headerLeft}>
          <Text style={styles.title}>Place this bet at</Text>
          <InfoTooltip
            title="Place this bet at"
            body={
              'Every book we price this slip at, best payout first. Tap one to place the slip there.\n\nN/M legs means that book doesn’t post every leg at the same line, so it can’t price the whole slip — you can still open it and add the legs it does have.\n\nBooks can’t accept a whole parlay from a link, so you add each leg once you’re there — the sheet lists them in order.\n\nThis row is every book, not just the ones you selected in Settings. The slip is always priced and modelled at DraftKings, whichever book you place it at.'
            }
            accessibilityLabel="About placing this bet"
          />
        </View>
        <Text style={styles.headerHint}>★ = best odds</Text>
      </View>

      {/* The indicator stays ON here, unlike every other horizontal strip in
          the app. There are 10 bettable books at 86pt in a ~311pt card, so 7 of
          them are off-screen — and since this row became the bet control there
          is no other affordance saying the rest exist (UX review). */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator
        contentContainerStyle={styles.tiles}
      >
        {quotes.map((q) => {
          const full = q.americanOdds != null;
          return (
            <Pressable
              key={q.book}
              onPress={() => setOpenBook(q.book)}
              accessibilityRole="button"
              accessibilityLabel={
                full
                  ? `Bet on ${bookName(q.book)}, combined odds ${formatAmerican(q.americanOdds!)}${
                      q.isBest && fullCount > 1 ? ', best payout' : ''
                    }`
                  : `Bet on ${bookName(q.book)}, prices ${q.priced} of ${q.total} legs at these lines`
              }
              accessibilityHint="Opens the leg-by-leg hand-off for this book"
              // A partial tile fades its ODDS only (oddsNa below): the badge
              // and the "2/3 legs" coverage are the information, and at 55%
              // on textTertiary they were under AA — on DraftKings' own tile,
              // the one users look for first, whenever a Stats line leg DK
              // never posted is in the slip (UX review).
              style={({ pressed }) => [styles.tile, pressed && styles.pressed]}
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

      {/* Sibling of the tiles, not a child of one: a Modal that ever became a
          layout participant would open a gap in the horizontal row. */}
      <ParlayDkHandoff
        visible={openBook != null}
        legs={handoffLegs}
        book={openBook ?? undefined}
        onClose={() => setOpenBook(null)}
      />
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
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  title: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  headerHint: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
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
  pressed: {
    opacity: 0.6,
  },
});
