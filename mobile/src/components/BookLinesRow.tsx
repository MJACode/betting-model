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
// Live picks (is_live) get one DraftKings chip; the Live board's header and
// the detail screen's provenance line say why (the in-play model prices and
// places at DK only), so the row does not repeat it on every card.

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
  /** Where "+N more" goes — the detail screen's All-books table. Omit on the
   *  detail screen itself, where every book is already listed below. */
  onMore?: () => void;
  /** How many chips to show before "+N more". Three on the card: on a 375pt
   *  phone four plus "+N more" wrapped to three rows (UX review). */
  maxChips?: number;
}

export function BookLinesRow({ pick, bookRows, onMore, maxChips = 3 }: Props) {
  const quotes = pickLineQuotes(pick, bookRows ?? []);
  if (quotes.length === 0) return null;
  // Card (onMore set) vs detail: the card is scanned, so it drops the per-chip
  // icon and the hint — the a11y label and the header say the chip opens the
  // book; the detail screen can breathe and keeps both.
  const compact = onMore != null;
  const { shown, hidden } = selectLineChips(quotes, null, compact ? maxChips : 99);

  return (
    <View style={styles.wrap}>
      <View style={styles.headerRow}>
        <Text style={styles.title}>{quotes.length === 1 ? 'Bet at' : 'Betting lines'}</Text>
        {!compact && quotes.length > 1 ? (
          <Text style={styles.hint} numberOfLines={1}>
            best first · tap to place
          </Text>
        ) : null}
      </View>
      <View style={styles.chips}>
        {shown.map((q) => {
          const isDk = q.bookmaker === MODEL_BOOK;
          // "best" = the top payout; "posted" = the NFL soft book's stored
          // price, the number the pick was posted at (never "given" — jargon).
          const tag = q.isBest && quotes.length > 1 ? 'best' : q.isRecord && !isDk ? 'posted' : null;
          return (
            <Pressable
              key={q.bookmaker}
              onPress={() => {
                void openBookBetslip(q.bookmaker, q.link);
              }}
              // 36pt chip + 4pt slop each side = the 8pt row gap, so adjacent
              // hit areas meet without overlapping.
              hitSlop={4}
              accessibilityRole="button"
              accessibilityLabel={`Bet at ${bookName(q.bookmaker)}, ${formatAmerican(q.price)}${
                tag === 'best' ? ', best price' : tag === 'posted' ? ', the posted price' : ''
              }`}
              style={({ pressed }) => [
                styles.chip,
                isDk && styles.chipDk,
                q.isBest && quotes.length > 1 && styles.chipBest,
                pressed && styles.pressed,
              ]}
            >
              <Text style={[styles.chipBook, isDk && styles.chipTextDk]}>
                {bookLabel(q.bookmaker)}
              </Text>
              <Text style={[styles.chipPrice, isDk && styles.chipTextDk]}>
                {formatAmerican(q.price)}
              </Text>
              {tag ? <Text style={styles.chipTag}>{tag}</Text> : null}
              {compact ? null : (
                <Ionicons
                  name="open-outline"
                  size={11}
                  color={isDk ? colors.textPrimary : colors.textTertiary}
                />
              )}
            </Pressable>
          );
        })}
        {hidden > 0 && onMore ? (
          <Pressable
            onPress={onMore}
            hitSlop={4}
            accessibilityRole="button"
            accessibilityLabel={`${hidden} more sportsbooks price this bet. Open pick details`}
            style={({ pressed }) => [styles.chip, styles.chipMore, pressed && styles.pressed]}
          >
            <Text style={styles.chipMoreText}>+{hidden} more</Text>
          </Pressable>
        ) : null}
      </View>
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
    flexShrink: 1,
    textAlign: 'right',
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
    minHeight: 36,
    paddingVertical: spacing.sm,
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
  // Best payout: the word "best" in dark text (green caption on the grey chip
  // was ~2.0:1) with the green on the border, where contrast is not a rule.
  chipBest: {
    borderColor: colors.bet,
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
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  chipMoreText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  pressed: {
    opacity: 0.6,
  },
});
