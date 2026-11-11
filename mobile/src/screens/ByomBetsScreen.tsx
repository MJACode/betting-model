/**
 * The bets a Build Your Own Model record counts, newest first.
 *
 * Matt, 2026-11-04: "We should show what bets are included in that list."
 * Each row is one counted bet: graded, with a DraftKings American price.
 * The label is the server's (byom_leg_label), quoted as given. No screen
 * rebuilds a spread's number (CLAUDE.md §00). Units are the main models'
 * staking, 1u to win with risk capped at 3u.
 *
 * Two timings, NFL and NBA alike. Official is the first DraftKings line
 * where the bet fit the model's rules, which is when it became a pick.
 * Closing is the last line before the game starts.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { FlatList, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { BetslipBarSpacer } from '@/components/BetslipBarSpacer';
import { ByomPillToggle } from '@/components/byom/ByomPillToggle';
import { ByomSeasonToggle } from '@/components/byom/ByomSeasonToggle';
import { EmptyState } from '@/components/EmptyState';
import { ErrorBanner, ErrorState } from '@/components/ErrorState';
import { Skeleton } from '@/components/Skeleton';
import { useByomSeason } from '@/hooks/useByomSeason';
import {
  fetchByomScopedBets,
  headlineTiming,
  type ByomBet,
  type ByomBetList,
  type ByomTiming,
} from '@/lib/byom';
import { byomFilters } from '@/lib/byomFilters';
import { propMarketLabel, type ByomSeasonScope, byomStartWord } from '@/lib/byomRecord';
import { unitsSpeech } from '@/lib/a11y';
import { errorText, isAbortError } from '@/lib/errors';
import { formatAmerican, formatGameDateET, formatSigned } from '@/lib/format';
import { colors, font, pnlColor, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Route = RouteProp<RootStackParamList, 'ByomBets'>;
type Nav = NativeStackNavigationProp<RootStackParamList>;

const TIMINGS: { value: ByomTiming; label: string }[] = [
  { value: 'official', label: 'Official line' },
  { value: 'close', label: 'Closing line' },
];

/** The list and the toggles it was loaded for. A row never shows under another timing. */
interface LoadedList extends ByomBetList {
  timing: ByomTiming;
  scope: ByomSeasonScope;
}

const RESULT_TEXT: Record<ByomBet['result'], string> = {
  win: 'Won',
  loss: 'Lost',
  push: 'Push',
  tie: 'Tie',
  '': '—',
};

function BetRow({ bet, first, last }: {
  bet: ByomBet; first: boolean; last: boolean;
}) {
  // Two decimals, so the rows add up to the card (UX_REVIEW §7).
  const units = bet.units == null ? '—' : formatSigned(bet.units, 2, 'u');
  const market = propMarketLabel(bet.market);
  const matchup = `${bet.away_team} @ ${bet.home_team}`;
  const price = bet.price == null ? '—' : formatAmerican(bet.price);
  const result = RESULT_TEXT[bet.result];
  // The game's date, not when the line locked (Matt, 2026-11-11).
  const played = formatGameDateET(bet.commence_time);
  const a11y = [
    bet.label,
    market,
    bet.price == null ? 'no price' : price,
    bet.result === '' ? 'no result' : result,
    bet.units == null ? 'no result' : unitsSpeech(units),
    matchup,
    played,
  ].filter(Boolean).join(', ');
  return (
    <View style={[styles.row, first && styles.rowFirst, last && styles.rowLast]} accessible accessibilityLabel={a11y}>
      <View style={styles.rowTop}>
        <Text style={styles.label} numberOfLines={2}>{bet.label}</Text>
        <Text style={[styles.units, { color: bet.units == null ? colors.textSecondary : pnlColor(bet.units, 1) }]}>
          {units}
        </Text>
      </View>
      <View style={styles.rowTop}>
        <Text style={styles.meta} numberOfLines={1}>
          {market ? `${market} · ` : ''}{matchup}{played ? ` · ${played}` : ''}
        </Text>
        <Text style={styles.meta}>{price} · {result}</Text>
      </View>
    </View>
  );
}

export function ByomBetsScreen() {
  const navigation = useNavigation<Nav>();
  const { filters: rawFilters, sport, title, timing: openedAt } = useRoute<Route>().params;
  const { scope } = useByomSeason();
  // A card that fell back to the close (no official rows yet, e.g. while
  // the NBA backfill runs) opens here without the Official toggle, so the
  // list never reads empty for a model whose bets exist (UX review).
  const offersOfficial = headlineTiming(sport) === 'official' && openedAt !== 'close';
  const start = byomStartWord(sport);
  const [timing, setTiming] = useState<ByomTiming>(
    openedAt ?? (offersOfficial ? 'official' : 'close'));
  const [list, setList] = useState<LoadedList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const filterKey = JSON.stringify(byomFilters(rawFilters));
  const seq = useRef(0);

  useEffect(() => {
    navigation.setOptions({ title: title ?? 'Bets' });
  }, [navigation, title]);

  const load = useCallback(async () => {
    const id = ++seq.current;
    setLoading(true);
    setError(null);
    try {
      const next = await fetchByomScopedBets(
        scope, JSON.parse(filterKey), timing, new Date(), sport);
      if (seq.current !== id) return;
      setList({ ...next, timing, scope });
    } catch (e: unknown) {
      if (seq.current !== id) return;
      if (!isAbortError(e)) setError(errorText(e));
    } finally {
      if (seq.current === id) setLoading(false);
    }
  }, [scope, filterKey, timing, sport]);

  useEffect(() => {
    void load();
  }, [load]);

  // Rows load for one timing and one season scope. After a toggle the old
  // rows are not shown under the new label (§1c): the skeleton stands in.
  const shown = list != null && list.timing === timing && list.scope === scope ? list : null;

  const header = (
    <View>
      <ByomSeasonToggle />
      {offersOfficial ? (
        <ByomPillToggle options={TIMINGS} value={timing} onChange={setTiming} />
      ) : null}
      <Text style={styles.explain}>
        {timing === 'official'
          ? 'The first DraftKings line where the bet fit your rules. That line and price are the bet, even if the line moved later.'
          : `The last DraftKings line before ${start}.`}
      </Text>
      {shown != null && shown.cappedSeasons > 0 ? (
        <Text style={styles.explain}>
          Showing {shown.bets.length} of {shown.total} bets. A season with more than 500 shows its newest 500.
        </Text>
      ) : null}
      {error && shown != null ? (
        <ErrorBanner what="these bets" error={error} onRetry={() => void load()} retrying={loading} />
      ) : null}
    </View>
  );

  return (
    <SafeAreaView style={styles.screen} edges={['bottom']}>
      {shown == null && (loading || error == null) ? (
        <View style={styles.content}>
          {header}
          <Skeleton label="these bets">
            <View style={styles.skel} />
          </Skeleton>
        </View>
      ) : shown == null ? (
        <View style={styles.content}>
          {header}
          <ErrorState what="these bets" error={error} onRetry={() => void load()} />
        </View>
      ) : (
        <FlatList
          data={shown.bets}
          keyExtractor={(bet) => bet.key}
          renderItem={({ item, index }) => (
            <BetRow bet={item}
              first={index === 0} last={index === shown.bets.length - 1} />
          )}
          ItemSeparatorComponent={() => <View style={styles.sep} />}
          ListHeaderComponent={header}
          ListEmptyComponent={
            <EmptyState
              title="No bets match"
              subtitle={shown.timing === 'official'
                ? 'No bet fit your rules at a DraftKings line.'
                : `None of these bets had a DraftKings line at ${start}.`}
            />
          }
          ListFooterComponent={<BetslipBarSpacer />}
          contentContainerStyle={styles.content}
          refreshing={loading}
          onRefresh={() => void load()}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  content: { padding: spacing.lg },
  explain: {
    fontSize: font.size.footnote,
    lineHeight: 18,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },
  row: {
    backgroundColor: colors.bgCard,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
  },
  rowFirst: { borderTopLeftRadius: radii.md, borderTopRightRadius: radii.md },
  rowLast: { borderBottomLeftRadius: radii.md, borderBottomRightRadius: radii.md },
  rowTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    gap: spacing.sm,
  },
  label: {
    flex: 1,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  units: {
    fontSize: font.size.body,
    fontWeight: font.weight.bold,
  },
  meta: {
    marginTop: 2,
    flexShrink: 1,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  // One grouped list: hairlines between rows, not a card per bet.
  sep: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: colors.separator,
    marginLeft: spacing.lg,
  },
  skel: {
    height: 240,
    borderRadius: radii.lg,
    backgroundColor: colors.noneSoft,
  },
});
