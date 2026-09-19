// PlayerBetBar — the player card's bet action: the proposition on screen, the
// best price among the member's books, and one tap to place it.
//
// Matt, 2026-09-18, with a competitor's player card beside ours: "I should be
// able to select different bet types for a player by selecting the play type
// and should be able to place directly with a sports book."
//
// TWO ACTIONS, AND THE SPLIT IS THE POINT. The primary places — straight to
// the book's pre-filled betslip, the route `openBookBetslip` already owns
// (installed app -> the filled link, not installed -> the App Store, unknown
// -> link then store). The secondary compares and builds: it opens the same
// AddLineSheet a Stats pill opens, which lists every bettable book's price and
// puts the line in OUR betslip.
//
// THIS DOES NOT REVERSE 2026-09-04. Matt's "it shouldn't take you directly to
// the book, it should ask you" was about the Stats BOARD's pills — a list, one
// tap per row, where a stray tap on the wrong row would open a book at a bet
// the reader never chose. The board still asks. A player card is the other
// end: the reader has drilled into one player, chosen a stat, and set a
// threshold, so the bet is already the thing they are looking at. The compare
// route is still one tap away and is named in words, not left implied.
//
// THE HEADLINE IS THE MEMBER'S BOOKS AND NOTHING OUTSIDE THE SET — the rule
// from 2026-09-03 ("If they select FanDuel we only show FanDuel"). The sheet
// behind "Compare odds" lists every bettable book, so the set narrows the
// default and never the options.
//
// The empty states are computed from the rows actually loaded
// (usePlayerPropQuote's coverage), never from a per-sport coverage table: the
// card is live on seven sports and a hard-coded claim about which of them
// price what is a sentence that goes quietly wrong.

import React from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { formatAmerican } from '@/lib/format';
import { modeLineLabel, type HitMode } from '@/lib/hitMode';
import { bookName, booksNoneName } from '@/lib/markets';
import { bookButtonColors, openBookBetslip } from '@/lib/sportsbookLinks';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { StatsOddsQuote } from '@/lib/statsOdds';

export function PlayerBetBar({
  quote,
  headline,
  mode,
  books,
  statLabel,
  marketPriced,
  hasGame,
  sidePosted,
  loading,
  onCompare,
}: {
  quote: StatsOddsQuote | null;
  /** The bet in the active idiom — "2+ Total Bases", "Over 1.5 Total Bases". */
  headline: string;
  mode: HitMode;
  /** The member's sportsbooks, for the "none of them posts this" copy. */
  books: readonly string[];
  statLabel: string;
  /** Does ANY book price this stat? False for stats nobody posts a line on. */
  marketPriced: boolean;
  /** Does the player have an unstarted game we can price? */
  hasGame: boolean;
  sidePosted: boolean;
  loading: boolean;
  onCompare: () => void;
}) {
  if (loading && !quote) {
    return (
      <View style={[styles.card, styles.cardQuiet]}>
        <ActivityIndicator />
      </View>
    );
  }

  if (!quote) {
    // Each of these is a DIFFERENT fact, and collapsing them into one "no line
    // available" is what makes a screen feel broken: nobody prices this stat,
    // the player isn't playing, their books don't sell this side, and their
    // books simply haven't posted this player are four separate answers.
    const note = !marketPriced
      ? `No sportsbook posts ${statLabel} lines.`
      : !hasGame
        ? 'No upcoming game to price.'
        : !sidePosted && mode === 'under'
          ? // `booksNoneName` carries its OWN negation only from two books up
            // ("Neither X nor Y", "None of your 3 sportsbooks"); at one book it
            // is the bare name, so the verb has to supply it or the sentence
            // says the exact opposite of what it means. Both plural forms take
            // a SINGULAR verb — "Neither X nor Y posts", not "post".
            books.length === 1
            ? `${bookName(books[0])} doesn’t post the under on ${statLabel}.`
            : `${booksNoneName(books)} posts the under on ${statLabel}.`
          : `${booksNoneName(books)} ${books.length === 1 ? 'hasn’t' : 'has'} posted this line yet.`;
    return (
      <View style={[styles.card, styles.cardQuiet]}>
        <Text style={styles.emptyText}>{note}</Text>
      </View>
    );
  }

  const { bg, fg } = bookButtonColors(quote.book);
  // An off-line quote is a DIFFERENT BET from the one the ruler names
  // (docs/best_line.md §5), so the button says the book's own number instead
  // of the headline — never the headline at someone else's line.
  const proposition = quote.offLine
    ? `${modeLineLabel(quote.line, quote.side, mode)} ${statLabel}`
    : headline;

  return (
    <View style={styles.card}>
      <View style={styles.top}>
        <View style={styles.propWrap}>
          <Text style={styles.prop} numberOfLines={2}>
            {proposition}
          </Text>
          {quote.offLine ? (
            <Text style={styles.offLine} numberOfLines={2}>
              {bookName(quote.book)} posts this line, not {headline}.
            </Text>
          ) : null}
        </View>
      </View>

      <View style={styles.actions}>
        <Pressable
          onPress={onCompare}
          accessibilityRole="button"
          accessibilityLabel="Compare odds at every sportsbook, and add to betslip"
          style={({ pressed }) => [styles.compare, pressed && styles.pressed]}
        >
          <Ionicons name="git-compare-outline" size={16} color={colors.textPrimary} />
          <Text style={styles.compareText}>Compare odds</Text>
        </Pressable>

        <Pressable
          onPress={() => {
            void openBookBetslip(quote.book, quote.link);
          }}
          accessibilityRole="button"
          // Spelled out: VoiceOver reads "+129" as "plus one hundred twenty
          // nine" either way, but "Bet" and the book's full name are what say
          // this LEAVES the app.
          accessibilityLabel={`Bet ${proposition} at ${bookName(quote.book)}, ${formatAmerican(
            quote.price,
          )}. Opens ${bookName(quote.book)}`}
          style={({ pressed }) => [styles.place, { backgroundColor: bg }, pressed && styles.pressed]}
        >
          <Text style={[styles.placePrice, { color: fg }]}>{formatAmerican(quote.price)}</Text>
          <Text style={[styles.placeBook, { color: fg }]} numberOfLines={1}>
            at {bookName(quote.book)}
          </Text>
          <Ionicons name="open-outline" size={13} color={fg} />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    padding: spacing.md,
  },
  cardQuiet: {
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 64,
  },
  top: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: spacing.sm,
  },
  propWrap: { flex: 1 },
  prop: {
    fontSize: font.size.headline,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  offLine: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
  actions: {
    flexDirection: 'row',
    alignItems: 'stretch',
    gap: spacing.sm,
  },
  compare: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    minHeight: 48,
    paddingHorizontal: spacing.md,
    borderRadius: radii.pill,
    backgroundColor: colors.bgGrouped,
    borderWidth: 1.5,
    borderColor: colors.separatorOpaque,
  },
  compareText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  place: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    minHeight: 48,
    paddingHorizontal: spacing.md,
    borderRadius: radii.pill,
  },
  placePrice: {
    fontSize: font.size.headline,
    fontWeight: font.weight.bold,
    fontVariant: ['tabular-nums'],
  },
  placeBook: {
    flexShrink: 1,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
  },
  emptyText: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  pressed: { opacity: 0.7 },
});
