import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  SectionList,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation } from '@react-navigation/native';
import { EmptyState } from '@/components/EmptyState';
import { SignalBadge } from '@/components/SignalBadge';
import { useBankroll } from '@/hooks/useBankroll';
import { usePlacedPicks, type PlacedBet } from '@/hooks/usePlacedPicks';
import {
  americanToDecimal,
  formatAmerican,
  formatCurrency,
  formatCurrencySigned,
  formatPct,
  todayET,
} from '@/lib/format';
import { fetchPicksByIds } from '@/lib/queries';
import { modelShort } from '@/lib/modelMeta';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { EnrichedPick, Pick, RootStackParamList, SignalType } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

interface BetRow {
  pickId: number;
  placed: PlacedBet;
  enriched: EnrichedPick | null; // null = hydrate failed / row gone
  // Effective fields (prefer server pick, fall back to snapshot)
  label: string;
  modelId: string;
  signalType: SignalType;
  gameDate: string;
  dkOdds: number | null;
  result: Pick['result'];
  profitKelly: number | null;
  commenceTime: string | null;
  matchup: string | null;
  serverGone: boolean;
}

type Section = { title: string; data: BetRow[]; key: 'today' | 'upcoming' | 'settled' };

const SETTLED_DAYS = 14;

export function MyBetsScreen() {
  const navigation = useNavigation<Nav>();
  const { bankroll } = useBankroll();
  const { overrides, ready } = usePlacedPicks();

  const pickIds = useMemo(
    () => Object.keys(overrides).map((k) => Number(k)).filter((n) => Number.isFinite(n)),
    [overrides],
  );

  const [enrichedById, setEnrichedById] = useState<Map<number, EnrichedPick | null>>(new Map());
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const hydrate = useCallback(async () => {
    if (pickIds.length === 0) {
      setEnrichedById(new Map());
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const rows = await fetchPicksByIds(pickIds);
      const map = new Map<number, EnrichedPick | null>();
      for (const id of pickIds) map.set(id, null);
      for (const r of rows) map.set(r.pick.pick_id, r);
      setEnrichedById(map);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [pickIds]);

  useEffect(() => {
    if (!ready) return;
    void hydrate();
  }, [ready, hydrate]);

  const rows: BetRow[] = useMemo(() => {
    return pickIds
      .map((id): BetRow | null => {
        const placed = overrides[String(id)];
        if (!placed) return null;
        const enriched = enrichedById.get(id) ?? null;
        const pick = enriched?.pick ?? null;
        const game = enriched?.game ?? null;
        const snap = placed.snapshot;
        const label = pick?.pick_label ?? snap?.pickLabel ?? `Pick #${id}`;
        return {
          pickId: id,
          placed,
          enriched,
          label,
          modelId: pick?.model_id ?? snap?.modelId ?? '',
          signalType: pick?.signal_type ?? snap?.signalType ?? 'NONE',
          gameDate: pick?.game_date ?? snap?.gameDate ?? '',
          dkOdds: pick?.dk_odds ?? snap?.dkOdds ?? null,
          result: pick?.result ?? null,
          profitKelly: pick?.profit_kelly != null ? Number(pick.profit_kelly) : null,
          commenceTime: game?.commence_time ?? null,
          matchup: game ? `${game.away_team} @ ${game.home_team}` : null,
          serverGone: !pick && snap != null,
        };
      })
      .filter((r): r is BetRow => r !== null);
  }, [pickIds, overrides, enrichedById]);

  const today = todayET();

  const sections: Section[] = useMemo(() => {
    const todayRows: BetRow[] = [];
    const upcomingRows: BetRow[] = [];
    const settledRows: BetRow[] = [];
    const cutoff = addDays(today, -SETTLED_DAYS);

    for (const r of rows) {
      const date = r.gameDate;
      const settled = r.result != null;
      if (settled) {
        if (date >= cutoff) settledRows.push(r);
        continue;
      }
      if (!date || date === today) todayRows.push(r);
      else if (date > today) upcomingRows.push(r);
      else settledRows.push(r); // unsettled but past — still show under settled
    }

    todayRows.sort(byCommenceTime);
    upcomingRows.sort((a, b) => (a.gameDate || '').localeCompare(b.gameDate || '') || byCommenceTime(a, b));
    settledRows.sort((a, b) => (b.gameDate || '').localeCompare(a.gameDate || ''));

    return [
      { key: 'today', title: 'Open — today', data: todayRows },
      { key: 'upcoming', title: 'Open — upcoming', data: upcomingRows },
      { key: 'settled', title: `Settled — last ${SETTLED_DAYS} days`, data: settledRows },
    ].filter((s) => s.data.length > 0) as Section[];
  }, [rows, today]);

  const totals = useMemo(() => {
    let openExposure = 0;
    let openCount = 0;
    let settledPnl = 0;
    let settledStake = 0;
    for (const r of rows) {
      if (r.result == null) {
        openExposure += r.placed.amount;
        openCount += 1;
      } else {
        settledStake += r.placed.amount;
        if (r.dkOdds != null && r.placed.amount > 0) {
          // Recompute P&L from the user's actual stake, not server's recommended_bet.
          settledPnl += pnlForResult(r.result, r.placed.amount, r.dkOdds);
        }
      }
    }
    return {
      openExposure,
      openCount,
      settledPnl,
      settledStake,
      pctOfRoll: bankroll > 0 ? openExposure / bankroll : 0,
      overExposed: openExposure > bankroll && bankroll > 0,
    };
  }, [rows, bankroll]);

  if (!ready) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <ActivityIndicator style={styles.loading} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <SectionList
        sections={sections}
        keyExtractor={(item) => String(item.pickId)}
        stickySectionHeadersEnabled={false}
        ListHeaderComponent={
          <View>
            <View style={styles.header}>
              <Text style={styles.title}>My Bets</Text>
              <Text style={styles.subtitle}>
                Stakes you've set on tracked picks. Edit any bet from its detail screen.
              </Text>
            </View>

            <View style={styles.totalsCard}>
              <TotalsRow
                label="Open exposure"
                value={`${formatCurrency(totals.openExposure)} (${formatPct(totals.pctOfRoll)})`}
                tint={totals.overExposed ? colors.avoid : colors.textPrimary}
              />
              <TotalsRow label="Open bets" value={String(totals.openCount)} />
              <TotalsRow
                label={`P&L · last ${SETTLED_DAYS}d`}
                value={formatCurrencySigned(totals.settledPnl)}
                tint={
                  totals.settledPnl > 0
                    ? colors.bet
                    : totals.settledPnl < 0
                      ? colors.avoid
                      : colors.textPrimary
                }
              />
            </View>

            {totals.overExposed ? (
              <View style={styles.warnBanner}>
                <Ionicons name="warning-outline" size={16} color={colors.avoid} />
                <Text style={styles.warnText}>
                  Open exposure ({formatCurrency(totals.openExposure)}) exceeds bankroll (
                  {formatCurrency(bankroll)}). Saved stakes are not auto-shrunk.
                </Text>
              </View>
            ) : null}

            {error ? (
              <View style={styles.warnBanner}>
                <Ionicons name="cloud-offline-outline" size={16} color={colors.avoid} />
                <Text style={styles.warnText}>Couldn't refresh from server: {error}</Text>
              </View>
            ) : null}
          </View>
        }
        renderSectionHeader={({ section }) => (
          <Text style={styles.sectionHeader}>{section.title}</Text>
        )}
        renderItem={({ item }) => (
          <BetRowView
            row={item}
            onPress={() => navigation.navigate('PickDetail', { pickId: item.pickId })}
          />
        )}
        ListEmptyComponent={
          loading ? (
            <ActivityIndicator style={styles.loading} />
          ) : (
            <EmptyState
              title="No tracked bets yet"
              subtitle="Open a pick and tap 'I'm betting this' to start tracking. The stake defaults to the Kelly suggestion and is fully editable."
            />
          )
        }
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={hydrate} />}
      />
    </SafeAreaView>
  );
}

function BetRowView({ row, onPress }: { row: BetRow; onPress: () => void }) {
  const profitColor =
    row.profitKelly != null && row.profitKelly > 0
      ? colors.bet
      : row.profitKelly != null && row.profitKelly < 0
        ? colors.avoid
        : colors.textSecondary;

  const potentialProfit =
    row.dkOdds != null && row.placed.amount > 0
      ? row.placed.amount * (americanToDecimal(row.dkOdds) - 1)
      : null;

  const dateLabel = row.commenceTime
    ? formatTimeLabel(row.commenceTime)
    : row.gameDate || '—';

  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
    >
      <View style={styles.rowTopLine}>
        <View style={styles.chipRow}>
          {row.modelId ? (
            <View style={styles.modelChip}>
              <Text style={styles.modelChipText}>{modelShort(row.modelId)}</Text>
            </View>
          ) : null}
          <SignalBadge signal={row.signalType} small />
          {row.serverGone ? (
            <View style={styles.warnChip}>
              <Text style={styles.warnChipText}>NO LONGER RECOMMENDED</Text>
            </View>
          ) : null}
        </View>
        <Text style={styles.timeLabel}>{dateLabel}</Text>
      </View>

      <Text style={styles.label}>{row.label}</Text>
      {row.matchup ? <Text style={styles.matchup}>{row.matchup}</Text> : null}

      <View style={styles.metrics}>
        <Metric label="Stake" value={formatCurrency(row.placed.amount)} />
        <Metric label="DK" value={formatAmerican(row.dkOdds)} />
        {row.result == null ? (
          <Metric
            label="To win"
            value={potentialProfit != null ? formatCurrency(potentialProfit) : '—'}
          />
        ) : (
          <Metric
            label={row.result}
            value={row.profitKelly != null ? formatCurrencySigned(row.profitKelly) : '—'}
            tint={profitColor}
          />
        )}
      </View>
    </Pressable>
  );
}

function Metric({ label, value, tint }: { label: string; value: string; tint?: string }) {
  return (
    <View style={styles.metric}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={[styles.metricValue, tint ? { color: tint } : null]}>{value}</Text>
    </View>
  );
}

function TotalsRow({
  label,
  value,
  tint,
}: {
  label: string;
  value: string;
  tint?: string;
}) {
  return (
    <View style={styles.totalsRow}>
      <Text style={styles.totalsLabel}>{label}</Text>
      <Text style={[styles.totalsValue, tint ? { color: tint } : null]}>{value}</Text>
    </View>
  );
}

function byCommenceTime(a: BetRow, b: BetRow): number {
  const ta = a.commenceTime ?? '';
  const tb = b.commenceTime ?? '';
  return ta.localeCompare(tb);
}

function addDays(date: string, days: number): string {
  const d = new Date(`${date}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function formatTimeLabel(iso: string): string {
  try {
    return new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function pnlForResult(result: Pick['result'], stake: number, americanOdds: number): number {
  if (result === 'WIN') return stake * (americanToDecimal(americanOdds) - 1);
  if (result === 'LOSS') return -stake;
  return 0; // PUSH / NO_ACTION
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  list: {
    paddingBottom: spacing.xl,
  },
  loading: {
    marginVertical: spacing.xxl,
  },
  header: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  title: {
    fontSize: font.size.largeTitle,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  subtitle: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 4,
  },
  totalsCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    marginHorizontal: spacing.lg,
    marginVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  totalsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.xs,
  },
  totalsLabel: {
    fontSize: font.size.body,
    color: colors.textSecondary,
  },
  totalsValue: {
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  warnBanner: {
    backgroundColor: colors.avoidSoft,
    borderRadius: radii.sm,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  warnText: {
    flex: 1,
    color: colors.avoid,
    fontSize: font.size.footnote,
    lineHeight: 18,
  },
  sectionHeader: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.xs,
  },
  row: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  rowPressed: {
    opacity: 0.7,
  },
  rowTopLine: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.xs,
  },
  chipRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    flexShrink: 1,
  },
  modelChip: {
    backgroundColor: colors.noneSoft,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  modelChipText: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontWeight: font.weight.semibold,
  },
  warnChip: {
    backgroundColor: colors.avoidSoft,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  warnChipText: {
    fontSize: 10,
    fontWeight: font.weight.semibold,
    color: colors.avoid,
    letterSpacing: 0.3,
  },
  timeLabel: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    fontWeight: font.weight.medium,
  },
  label: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginBottom: 2,
  },
  matchup: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  metrics: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: spacing.xs,
  },
  metric: {
    flex: 1,
  },
  metricLabel: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginBottom: 2,
  },
  metricValue: {
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
});
