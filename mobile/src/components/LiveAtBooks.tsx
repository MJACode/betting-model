import React, { useMemo, useState } from 'react';
import { StyleSheet, Text } from 'react-native';

import { SegmentTabs } from '@/components/GroupTabs';
import { Section, TeamHeads, TriRow } from '@/components/MatchupSections';
import { bookName } from '@/lib/markets';
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
  onRetry: () => void;
}) {
  const [market, setMarket] = useState<Market>(markets.includes('spreads') ? 'spreads' : markets[0] ?? 'h2h');
  const byMarket = useMemo(() => {
    const now = Date.now();
    return new Map(markets.map((m) => [m, liveBookLines(rows, m, books, now)] as const));
  }, [rows, books, markets]);
  const none = markets.every((m) => (byMarket.get(m) ?? []).length === 0);
  const title = (m: Market) => (m === 'h2h' ? 'Moneyline' : scoreboardMarketLabel(m, sport));
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
          <SegmentTabs compact items={markets} active={market} onChange={setMarket} labelFor={title} />
          <TeamHeads
            away={market === 'totals' ? 'Over' : teams.away}
            home={market === 'totals' ? 'Under' : teams.home}
          />
          {lines.length === 0 ? (
            <Text style={styles.note}>None of your sportsbooks has a live {title(market).toLowerCase()} stored.</Text>
          ) : (
            lines.map((l) => (
              <TriRow
                key={l.book}
                label={`${bookName(l.book)}\n${l.age}`}
                away={l.away}
                home={l.home}
                spoken={
                  market === 'totals'
                    ? `${title(market)}, ${bookName(l.book)}: ${l.awaySpoken}; ${l.homeSpoken}; ${l.ageSpoken}`
                    : `${title(market)}, ${bookName(l.book)}: ${teams.awayFull} ${l.awaySpoken}; ` +
                      `${teams.homeFull} ${l.homeSpoken}; ${l.ageSpoken}`
                }
              />
            ))
          )}
          {error ? <Text style={styles.note}>Couldn’t load some of your books. This page tries again every 30 seconds.</Text> : null}
        </>
      )}
    </Section>
  );
}

const styles = StyleSheet.create({
  note: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
});
