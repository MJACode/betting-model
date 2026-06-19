import React from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation } from '@react-navigation/native';
import { useSportsbookSync } from '@/hooks/useSportsbookSync';
import { formatAmerican, formatCurrency, formatCurrencySigned } from '@/lib/format';
import type { SyncedBet } from '@/lib/sharpsports';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

export function PerformanceScreen() {
  const navigation = useNavigation<Nav>();
  const { accounts, bets, summary, linked, needsReconnect, loading, refresh } =
    useSportsbookSync();

  // First load with nothing linked yet → connect CTA.
  if (!linked && !loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <ScrollView contentContainerStyle={styles.list}>
          <View style={styles.header}>
            <Text style={styles.title}>Performance</Text>
            <Text style={styles.subtitle}>P&L synced from your sportsbook</Text>
          </View>
          <Pressable
            onPress={() => navigation.navigate('TrackRecord')}
            style={({ pressed }) => [styles.trackLink, pressed && styles.btnPressed]}
          >
            <Ionicons name="shield-checkmark-outline" size={16} color={colors.tint} />
            <Text style={styles.trackLinkText}>See the model’s verified track record</Text>
            <Ionicons name="chevron-forward" size={15} color={colors.tint} />
          </Pressable>
          <View style={styles.card}>
            <View style={styles.iconWrap}>
              <Ionicons name="link-outline" size={28} color={colors.tint} />
            </View>
            <Text style={styles.cardTitle}>Connect a sportsbook to see your P&L</Text>
            <Text style={styles.cardBody}>
              Performance tracks your real wagers — not picks you mark by hand. Link DraftKings or
              FanDuel (read-only, via SharpSports) to pull your bet history automatically.
            </Text>
            <Pressable
              onPress={() => navigation.navigate('ConnectSportsbook')}
              style={({ pressed }) => [styles.primaryBtn, pressed && styles.btnPressed]}
            >
              <Text style={styles.primaryBtnText}>Connect a sportsbook</Text>
            </Pressable>
          </View>
        </ScrollView>
      </SafeAreaView>
    );
  }

  const bookLabel = formatBookList(
    Array.from(new Set(accounts.map((a) => a.book).filter(Boolean) as string[])),
  );
  const profitColor =
    summary.net_profit > 0 ? colors.bet : summary.net_profit < 0 ? colors.avoid : colors.textPrimary;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={() => void refresh(true)} />
        }
      >
        <View style={styles.header}>
          <Text style={styles.title}>Performance</Text>
          <Text style={styles.subtitle}>{bookLabel || 'Sportsbook'} · pull to refresh</Text>
        </View>

        <Pressable
          onPress={() => navigation.navigate('TrackRecord')}
          style={({ pressed }) => [styles.trackLink, pressed && styles.btnPressed]}
        >
          <Ionicons name="shield-checkmark-outline" size={16} color={colors.tint} />
          <Text style={styles.trackLinkText}>See the model’s verified track record</Text>
          <Ionicons name="chevron-forward" size={15} color={colors.tint} />
        </Pressable>

        {needsReconnect ? (
          <Pressable
            onPress={() => navigation.navigate('ConnectSportsbook')}
            style={({ pressed }) => [styles.reconnect, pressed && styles.btnPressed]}
          >
            <Ionicons name="alert-circle-outline" size={16} color={colors.med} />
            <Text style={styles.reconnectText}>
              A linked account needs reconnecting — tap to fix.
            </Text>
          </Pressable>
        ) : null}

        <View style={styles.summaryCard}>
          <View style={styles.summaryMain}>
            <Text style={styles.summaryLabel}>Net P&L</Text>
            <Text style={[styles.summaryProfit, { color: profitColor }]}>
              {formatCurrencySigned(summary.net_profit)}
            </Text>
          </View>
          <View style={styles.summaryStatsRow}>
            <SummaryStat
              label="Win rate"
              value={summary.win_rate != null ? `${Math.round(summary.win_rate * 100)}%` : '—'}
            />
            <SummaryStat label="Settled" value={String(summary.settled_bets)} />
            <SummaryStat label="Open" value={String(summary.open_bets)} />
          </View>
        </View>

        {bets.length === 0 ? (
          <Text style={styles.empty}>
            No synced bets yet. Place a bet on a linked book — it’ll appear here after the next
            sync.
          </Text>
        ) : (
          bets.slice(0, 100).map((b) => <BetRow key={b.bet_id} bet={b} />)
        )}

        {loading && bets.length === 0 ? <ActivityIndicator style={styles.loading} /> : null}

        <Pressable
          onPress={() => navigation.navigate('ConnectSportsbook')}
          style={({ pressed }) => [styles.secondaryBtn, pressed && styles.btnPressed]}
        >
          <Text style={styles.secondaryBtnText}>Manage connections</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

function SummaryStat({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.summaryStat}>
      <Text style={styles.summaryStatValue}>{value}</Text>
      <Text style={styles.summaryStatLabel}>{label}</Text>
    </View>
  );
}

function BetRow({ bet }: { bet: SyncedBet }) {
  const settled = bet.settled;
  const profit = Number(bet.profit ?? 0);
  const resultColor = !settled
    ? colors.textSecondary
    : profit > 0
      ? colors.bet
      : profit < 0
        ? colors.avoid
        : colors.textSecondary;
  const right = settled
    ? formatCurrencySigned(profit)
    : bet.stake != null
      ? `${formatCurrency(bet.stake)} risked`
      : 'Open';

  return (
    <View style={styles.betRow}>
      <View style={{ flex: 1 }}>
        <Text style={styles.betTitle} numberOfLines={1}>
          {bet.book ?? 'Bet'}
          {bet.type ? ` · ${bet.type}` : ''}
        </Text>
        <Text style={styles.betSub} numberOfLines={1}>
          {[
            bet.odds_american != null ? formatAmerican(bet.odds_american) : null,
            (bet.status ?? '').toString() || null,
            formatDate(bet.placed_at),
          ]
            .filter(Boolean)
            .join(' · ')}
        </Text>
      </View>
      <Text style={[styles.betRight, { color: resultColor }]}>{right}</Text>
    </View>
  );
}

function formatDate(iso: string | null): string | null {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return null;
  }
}

function formatBookList(names: string[]): string {
  if (names.length === 0) return '';
  if (names.length === 1) return names[0];
  if (names.length === 2) return `${names[0]} & ${names[1]}`;
  return `${names.slice(0, -1).join(', ')} & ${names[names.length - 1]}`;
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  list: {
    paddingBottom: spacing.xl,
  },
  header: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.md,
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
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginHorizontal: spacing.lg,
    alignItems: 'center',
  },
  iconWrap: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.bg,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
    marginTop: spacing.sm,
  },
  cardTitle: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    textAlign: 'center',
    marginBottom: spacing.sm,
  },
  cardBody: {
    fontSize: font.size.body,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: spacing.lg,
  },
  summaryCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  summaryMain: {
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  summaryLabel: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
    marginBottom: 2,
  },
  summaryProfit: {
    fontSize: font.size.largeTitle,
    fontWeight: font.weight.bold,
  },
  summaryStatsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
    paddingTop: spacing.md,
  },
  summaryStat: {
    alignItems: 'center',
  },
  summaryStatValue: {
    fontSize: font.size.title3,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  summaryStatLabel: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginTop: 2,
  },
  trackLink: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  trackLinkText: {
    flex: 1,
    fontSize: font.size.callout,
    color: colors.tint,
    fontWeight: font.weight.semibold,
  },
  reconnect: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#FFF4E5',
    borderRadius: radii.md,
    padding: spacing.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  reconnectText: {
    flex: 1,
    fontSize: font.size.footnote,
    color: colors.med,
    fontWeight: font.weight.medium,
  },
  betRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
  },
  betTitle: {
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    textTransform: 'capitalize',
  },
  betSub: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginTop: 2,
    textTransform: 'capitalize',
  },
  betRight: {
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    marginLeft: spacing.md,
  },
  empty: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    textAlign: 'center',
    paddingHorizontal: spacing.xl,
    marginVertical: spacing.lg,
    lineHeight: 19,
  },
  primaryBtn: {
    backgroundColor: colors.tint,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
    borderRadius: radii.md,
    alignSelf: 'stretch',
    alignItems: 'center',
  },
  primaryBtnText: {
    color: colors.textInverse,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
  },
  secondaryBtn: {
    backgroundColor: colors.bgCard,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
    borderRadius: radii.md,
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
    alignItems: 'center',
  },
  secondaryBtnText: {
    color: colors.tint,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
  },
  btnPressed: {
    opacity: 0.7,
  },
  loading: {
    marginTop: spacing.lg,
  },
});
