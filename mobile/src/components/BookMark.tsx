import React from 'react';
import { StyleSheet, View } from 'react-native';

import { bookName } from '@/lib/markets';
import { radii } from '@/lib/theme';

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
  const Glyph = BOOK_GLYPHS[book];
  // No glyph, no stand-in. A "DK" in the pill repeats the column header two
  // characters at a time, 25 rows down — that is the header, not a brand mark,
  // and it is what pushed the pill past its column for the five-letter books
  // (BALLY, REBET). Apple Sports has the licence and still prints the mark ONCE
  // under the module rather than per row. The pill's own accessibility label
  // already names the book, so nothing is lost by drawing nothing.
  if (!Glyph) return null;
  return (
    <View
      style={styles.wrap}
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      <Glyph size={size} color={color} />
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
});
