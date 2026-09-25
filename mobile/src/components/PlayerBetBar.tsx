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

import { formatAmerican, formatDayTimeET } from '@/lib/format';
import { modeLineLabel, type HitMode } from '@/lib/hitMode';
import type { HitDirection } from '@/lib/hitRate';
import { bookName, booksNoneName, sideNotPostedNote } from '@/lib/markets';
import { matchupForLeg } from '@/lib/parlay';
import { bookButtonColors, openBookBetslip } from '@/lib/sportsbookLinks';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { StatsOddsQuote } from '@/lib/statsOdds';
import type { GameRow } from '@/types';

export function PlayerBetBar({
  quote,
  game,
  headline,
  mode,
  side,
  books,
  statLabel,
  marketPriced,
  hasGame,
  sidePosted,
  loading,
  error,
  onRetry,
  onCompare,
}: {
  quote: StatsOddsQuote | null;
  /** The game the price is for — named under the proposition, because a player
   *  reached from search carries no matchup line in the header. */
  game: GameRow | null;
  /** The bet in the active idiom — "2+ Total Bases", "Over 1.5 Total Bases". */
  headline: string;
  mode: HitMode;
  /** Which way the card's bet runs, for the not-posted sentence. */
  side: HitDirection;
  /** The member's sportsbooks, for the "none of them posts this" copy. */
  books: readonly string[];
  statLabel: string;
  /** Does ANY book price this stat? False for stats nobody posts a line on. */
  marketPriced: boolean;
  /** Does the player have an unstarted game we can price? */
  hasGame: boolean;
  sidePosted: boolean;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onCompare: () => void;
}) {
  if (loading && !quote) {
    return (
      <View style={[styles.card, styles.cardQuiet]}>
        <ActivityIndicator />
      </View>
    );
  }

  // BEFORE the empty branch, and never folded into it. A failed read has no
  // idea what the member's books post, so falling through would answer a
  // network error with "Neither DraftKings nor FanDuel has posted this line
  // yet" — a confident, false claim about their sportsbooks (UX review).
  if (error) {
    return (
      <View style={[styles.card, styles.cardQuiet]}>
        <Text style={styles.emptyText}>{error}</Text>
        <Pressable
          onPress={onRetry}
          accessibilityRole="button"
          accessibilityLabel="Try loading the odds again"
          style={({ pressed }) => [styles.retry, pressed && styles.pressed]}
        >
          <Text style={styles.retryText}>Try again</Text>
        </Pressable>
      </View>
    );
  }

  if (!quote) {
    // Each of these is a DIFFERENT fact, and collapsing them into one "no line
    // available" is what makes a screen feel broken: nobody prices this stat,
    // the player isn't playing, their books don't sell this side, and their
    // books simply haven't posted this player are four separate answers.
    // NOT GATED ON `mode === 'under'`. A market the member's books sell only
    // one way can be missing EITHER side — FanDuel's and Caesars' milestone
    // markets carry an over and no under, and the mirror exists — so the
    // sentence takes the card's own side rather than assuming which one is
    // ever absent (UX review).
    const note = !marketPriced
      ? `No sportsbook posts ${statLabel} lines.`
      : !hasGame
        ? 'No upcoming game to price.'
        : !sidePosted
          ? sideNotPostedNote(books, side, statLabel)
          : `${booksNoneName(books)} ${books.length === 1 ? 'hasn’t' : 'has'} posted this line yet.`;
    return (
      <View style={[styles.card, styles.cardQuiet]}>
        <Text style={styles.emptyText}>{note}</Text>
      </View>
    );
  }

  const { bg, fg } = bookButtonColors(quote.book);
  // "PHI @ NYM · Fri 7:05 PM ET" — the same matchup string the betslip's leg
  // cards and AddLineSheet use, so one bet reads the same wherever it appears.
  const fixture = matchupForLeg(game);
  const when = formatDayTimeET(game?.commence_time ?? null);
  const matchup = fixture ? (when ? `${fixture} · ${when}` : fixture) : null;
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
          {/* WHICH GAME the price is for. The header's matchup line only
              exists when the Stats board handed it over, so a player opened
              from search would otherwise read a bettable price for an unnamed
              event (UX review). */}
          {matchup ? (
            <Text style={styles.matchup} numberOfLines={1}>
              {matchup}
            </Text>
          ) : null}
        </View>
      </View>

      <View style={styles.actions}>
        <Pressable
          onPress={() => {
            void openBookBetslip(quote.book, quote.link);
          }}
          accessibilityRole="button"
          // Spelled out: VoiceOver reads "+129" as "plus one hundred twenty
          // nine" either way, but "Bet" and the book's full name are what say
          // this LEAVES the app.
          accessibilityLabel={`Bet ${proposition}${matchup ? `, ${matchup}` : ''} at ${bookName(
            quote.book,
          )}, ${formatAmerican(quote.price)}. Opens ${bookName(quote.book)}`}
          style={({ pressed }) => [styles.place, { backgroundColor: bg }, pressed && styles.pressed]}
        >
          {/* A VERB, and an icon at the same weight as the compare button's.
              "+129 at DraftKings" under a 13pt glyph reads as a price tag, so
              the sighted member never learned the tap LEAVES the app while
              the VoiceOver label said so plainly (UX review). */}
          <Text style={[styles.placeVerb, { color: fg }]}>Bet</Text>
          <Text style={[styles.placePrice, { color: fg }]}>{formatAmerican(quote.price)}</Text>
          <Text style={[styles.placeBook, { color: fg }]} numberOfLines={1}>
            at {bookName(quote.book)}
          </Text>
          <Ionicons name="open-outline" size={16} color={fg} />
        </Pressable>
        <Pressable
          onPress={onCompare}
          accessibilityRole="button"
          accessibilityLabel="Compare odds at every sportsbook, and add to betslip"
          style={({ pressed }) => [styles.compare, pressed && styles.pressed]}
        >
          <Ionicons name="git-compare-outline" size={16} color={colors.textPrimary} />
          <Text style={styles.compareText} numberOfLines={1}>
            Compare odds
          </Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  // A SECTION of the hit card it sits in, not a card of its own. It was a
  // bgCard box with its own side margin and padding inside a bgCard box that
  // already had both, so the bet read indented by a second gutter and had
  // ~70% of the row to fit "Bet +3400 at DraftKings" in, which it could not
  // (Matt, 2026-09-25: "Draft kings UI looks bad"). A hairline separates it
  // from the stepper above instead.
  card: {
    marginTop: spacing.md,
    paddingTop: spacing.md,
    // The chart follows directly; without this "Compare odds" sat on it.
    marginBottom: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
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
  matchup: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
  retry: {
    marginTop: spacing.sm,
    minHeight: 44,
    justifyContent: 'center',
    paddingHorizontal: spacing.md,
  },
  retryText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  // STACKED, primary on top. Side by side, the Bet button's text is wider than
  // what is left beside Compare for any long price or book name, and a Text
  // that will not shrink overflows its pill — the price printed half outside
  // the green (2026-09-25). Full width, it always fits.
  actions: {
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
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    minHeight: 48,
    paddingHorizontal: spacing.md,
    borderRadius: radii.pill,
  },
  placeVerb: {
    fontSize: font.size.headline,
    fontWeight: font.weight.bold,
  },
  placePrice: {
    fontSize: font.size.headline,
    fontWeight: font.weight.bold,
    fontVariant: ['tabular-nums'],
  },
  // Shrinks only at an accessibility text size, where the full-width button
  // still cannot hold it; the price beside it never does.
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
