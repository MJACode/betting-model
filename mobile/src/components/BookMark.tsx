import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { usePreferredBooks } from '@/hooks/usePreferredBooks';
import { bookLabelShort, bookName } from '@/lib/markets';
import { font, radii } from '@/lib/theme';

/**
 * The sportsbook's mark, as it sits inside a line pill.
 *
 * Matt, 2026-09-04, on a competitor's leaderboard: "mirror exactly how they
 * show the draft kings line and its betable link directly to that sportsbook."
 * Their pill carries DraftKings' crown; ours carries the book's short label
 * ("DK", "FD", "MGM") in the same slot, at the same size.
 *
 * WHY NOTHING RENDERS TODAY. The marks are the books' trademarks and
 * the licensed source is each book's own affiliate kit. This sandbox cannot
 * reach an image host either way — the egress proxy denies upload.wikimedia.org
 * and every CDN tried, npm carries no sportsbook icon set (simple-icons is
 * 3,457 marks and none of them is a book), so there is no honest file to ship
 * yet. `docs/book_logos.md` has the one command that fetches them and where to
 * drop the files.
 *
 * ADDING THE LOGOS LATER IS A ONE-FILE CHANGE. Put an SVG component per book in
 * BOOK_GLYPHS below; every pill on every board picks it up, because they all
 * render through here. Nothing else needs to know.
 *
 * UNTIL THEY LAND, A TEXT LABEL STANDS IN — but only when the member has more
 * than one book selected (2026-09-04, UX review Blocker). With one book the
 * column header names it and every cell is that book, so a label per row is the
 * header repeated 25 times. With several, the header can only name the RULE
 * ("BEST") and fill-vs-outline separates DraftKings from everything else and
 * nothing else from anything — so a member on FanDuel + BetMGM read 25
 * identical pills and a tap ejected them into a sportsbook they had no way to
 * predict. VoiceOver was told which book all along; sighted users were not.
 *
 * This component reads the set itself rather than taking a prop, so the choice
 * lives beside the glyph map it will one day be replaced by, and no board has
 * to thread a flag down through its row components.
 */

/** Book key -> its mark. Empty until the licensed files land; see the note above. */
const BOOK_GLYPHS: Record<string, React.ComponentType<{ size: number; color: string }>> = {};

export function BookMark({
  book,
  size = 13,
  color,
}: {
  book: string;
  /** Cap height of the mark. Matches the price text beside it. */
  size?: number;
  /** Foreground of the pill it sits in, so the mark can never fail contrast. */
  color: string;
}) {
  const { books } = usePreferredBooks();
  const Glyph = BOOK_GLYPHS[book];
  // One book: the header names it and every cell is it. Drawing nothing is
  // right, and it is what keeps the densest column on the board readable.
  if (!Glyph && books.length < 2) return null;
  return (
    <View
      style={styles.wrap}
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      {Glyph ? (
        <Glyph size={size} color={color} />
      ) : (
        <Text style={[styles.label, { color, fontSize: Math.max(9, size - 3) }]}>
          {bookLabelShort(book)}
        </Text>
      )}
    </View>
  );
}

/** For an accessibility label, where the mark itself is silent. */
export function bookMarkLabel(book: string): string {
  return bookName(book);
}

const styles = StyleSheet.create({
  wrap: {
    borderRadius: radii.sm,
    justifyContent: 'center',
  },
  // Quieter than the price it sits beside: the number is the answer, the book
  // is the provenance. `color` comes from the pill so contrast can never fail.
  label: {
    fontWeight: font.weight.semibold,
    opacity: 0.75,
    letterSpacing: 0.2,
  },
});
