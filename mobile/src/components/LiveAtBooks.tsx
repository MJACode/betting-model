import React, { useMemo, useState } from 'react';
import { StyleSheet, Text } from 'react-native';

import { SegmentTabs } from '@/components/GroupTabs';
import { Section, TeamHeads, TriRow } from '@/components/MatchupSections';
import { bookName, booksName } from '@/lib/markets';
import { liveBookLines, scoreboardMarketLabel, type LiveBookRow } from '@/lib/scoreboard';
import { colors, font } from '@/lib/theme';

type Market = 'h2h' | 'spreads' | 'totals';

/**
 * "Live at your books" on the game page (mike, 2026-11-25: "why not FanDuel,
 * MGM etc"): every book the member uses, each with its own live number, one
 * market at a time. Rows are the matchup page's TriRow, so they stack at large
 * text the way the Best price rows do; the book and when it last moved sit in
 * the middle column. No best is marked: live books are often on different
 * numbers, and a price is only better than another at the same number.
 */
export function LiveAtBooks({
  sport,
  markets,
  rows,
  books,
  teams,
  loading,
  error,
  failedBooks,
  onRetry,
}: {
  sport: string;
  markets: readonly Market[];
  rows: readonly LiveBookRow[];
  books: readonly string[];
  /** Codes for the column heads, full names for VoiceOver. */
  teams: { away: string; home: string; awayFull: string; homeFull: string };
  loading: boolean;
  error: string | null;
  /** The books whose read failed, for the caption. */
  failedBooks: readonly string[];
  onRetry: () => void;
}) {
  const [market, setMarket] = useState<Market>(markets.includes('spreads') ? 'spreads' : markets[0] ?? 'h2h');
  const byMarket = useMemo(() => {
    const now = Date.now();
    return new Map(markets.map((m) => [m, liveBookLines(rows, m, books, now)] as const));
  }, [rows, books, markets]);
  const none = markets.every((m) => (byMarket.get(m) ?? []).length === 0);
  const title = (m: Market) => (m === 'h2h' ? 'Moneyline' : scoreboardMarketLabel(m, sport));
  const sides = market === 'totals' ? { away: 'Over', home: 'Under' } : { away: teams.away, home: teams.home };
  const lines = byMarket.get(market) ?? [];
  return (
    <Section
      title="Live at your books"
      loading={loading}
      error={none ? error : null}
      onRetry={onRetry}
      note="Each book’s own number, and when that book last moved it. This page re-reads every 30 seconds."
    >
      {none ? (
        <Text style={styles.note}>None of your sportsbooks has a live line stored for this game.</Text>
      ) : (
        <>
          {/* Full width and `fit`, with the board's short labels: three
              compact tabs ran off the card at AX3 (UX review, 2026-11-25). */}
          <SegmentTabs
            fit
            items={markets}
            active={market}
            onChange={setMarket}
            labelFor={(m) => scoreboardMarketLabel(m, sport)}
            accessibilityLabelFor={title}
          />
          {lines.length > 0 ? <TeamHeads away={sides.away} home={sides.home} hideStacked /> : null}
          {lines.length === 0 ? (
            <Text style={styles.note}>None of your sportsbooks has a live {title(market).toLowerCase()} stored.</Text>
          ) : (
            lines.map((l) => (
              <TriRow
                key={l.book}
                label={`${bookName(l.book)}\n${l.age}`}
                away={{ ...l.away, muted: l.quiet }}
                home={{ ...l.home, muted: l.quiet }}
                sides={sides}
                spoken={
                  market === 'totals'
                    ? `${title(market)}, ${bookName(l.book)}: ${l.awaySpoken}; ${l.homeSpoken}; ${l.ageSpoken}`
                    : `${title(market)}, ${bookName(l.book)}: ${teams.awayFull} ${l.awaySpoken}; ` +
                      `${teams.homeFull} ${l.homeSpoken}; ${l.ageSpoken}`
                }
              />
            ))
          )}
          {error ? (
            <Text style={styles.note}>
              {`Couldn’t load ${failedLabel(failedBooks)}. ` +
                'This page tries again every 30 seconds.'}
            </Text>
          ) : null}
        </>
      )}
    </Section>
  );
}

/** "FanDuel", "FanDuel and BetMGM", "3 of your sportsbooks": booksName's two-book
 *  rule. Not its "your 3 sportsbooks", which would read as all of them. */
function failedLabel(books: readonly string[]): string {
  if (books.length === 0) return 'some of your sportsbooks';
  if (books.length <= 2) return booksName(books);
  return `${books.length} of your sportsbooks`;
}

const styles = StyleSheet.create({
  note: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
});
