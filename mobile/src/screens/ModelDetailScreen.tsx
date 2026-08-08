import React, { useEffect, useMemo } from 'react';
import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation, useRoute } from '@react-navigation/native';
import { EmptyState } from '@/components/EmptyState';
import { SignalBadge } from '@/components/SignalBadge';
import { StatTile } from '@/components/StatTile';
import { useCustomModels, pickMatchesModel } from '@/hooks/useCustomModels';
import { useCustomModelStats } from '@/hooks/useCustomModelStats';
import { useTodayPicks } from '@/hooks/useTodayPicks';
import { describeFilters } from '@/lib/customModelFilters';
import {
  formatAmerican,
  formatCurrencySigned,
  formatGameTimeET,
  formatPct,
  formatPctSigned,
  gameDayLabelET,
} from '@/lib/format';
import { modelShort, modelLong } from '@/lib/modelMeta';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Route = RouteProp<RootStackParamList, 'ModelDetail'>;
type Nav = NativeStackNavigationProp<RootStackParamList>;

export function ModelDetailScreen() {
  const route = useRoute<Route>();
  const navigation = useNavigation<Nav>();
  const { modelId } = route.params;
  const { get } = useCustomModels();
  const model = get(modelId);
  const { stats, matchingPicks, loading, error } = useCustomModelStats(model ?? null);
  const filterChips = describeFilters(model?.filters);

  // Live board: today's picks plus the UFC/golf events scored up to a week out,
  // so a saved model surfaces its picks as they come up rather than only after
  // they settle.
  const { data: todayPicks, loading: todayLoading } = useTodayPicks();
  const upcoming = useMemo(
    () => (model ? todayPicks.filter((ep) => pickMatchesModel(ep.pick, model)) : []),
    [todayPicks, model],
  );

  useEffect(() => {
    navigation.setOptions({ title: model?.name ?? 'Model' });
  }, [navigation, model]);

  if (!model) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <Text style={styles.error}>Model not found.</Text>
      </SafeAreaView>
    );
  }

  const decided = stats.wins + stats.losses;
  const roiColor = stats.roiFlat > 0 ? colors.bet : stats.roiFlat < 0 ? colors.avoid : colors.textSecondary;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <FlatList
        data={[...matchingPicks].sort((a, b) => b.game_date.localeCompare(a.game_date))}
        keyExtractor={(p) => String(p.pick_id)}
        ListHeaderComponent={
          <>
            <View style={styles.headerCard}>
              <View style={styles.headerRow}>
                <Text style={styles.modelTitle}>{model.name}</Text>
                <Pressable onPress={() => navigation.navigate('ModelEdit', { modelId })} hitSlop={6}>
                  <Ionicons name="pencil" size={18} color={colors.tint} />
                </Pressable>
              </View>
              <Text style={styles.ruleHeader}>MODELS</Text>
              {model.rules.map((r, i) => (
                <View key={i} style={styles.ruleRow}>
                  <Text style={styles.ruleName}>{modelLong(r.model_id)}</Text>
                  <Text style={styles.ruleParams}>
                    prob ≥ {Math.round(r.min_prob * 100)}% · edge ≥ {Math.round(r.min_edge * 100)}%
                  </Text>
                </View>
              ))}
              {filterChips.length > 0 ? (
                <>
                  <Text style={[styles.ruleHeader, styles.filterHeader]}>FILTERS</Text>
                  <View style={styles.filterChips}>
                    {filterChips.map((c) => (
                      <View key={c} style={styles.filterChip}>
                        <Text style={styles.filterChipText}>{c}</Text>
                      </View>
                    ))}
                  </View>
                </>
              ) : null}
            </View>

            <View style={styles.statRow}>
              <StatTile label="Picks matched" value={String(stats.picks)} caption="since 2026-04-14" />
              <StatTile
                label="Win %"
                value={decided > 0 ? formatPct(stats.winRate) : '—'}
                caption={decided > 0 ? `${stats.wins}-${stats.losses}-${stats.pushes}` : 'no decided'}
              />
            </View>
            <View style={styles.statRow}>
              <StatTile
                label="Flat ROI"
                value={stats.picks > 0 ? formatPctSigned(stats.roiFlat) : '—'}
                tint={roiColor}
                caption="vs $100 flat per bet"
              />
              <StatTile
                label="P&L"
                value={stats.picks > 0 ? formatCurrencySigned(stats.profitFlat) : '—'}
                tint={roiColor}
                caption="settled only"
              />
            </View>

            {error ? (
              <View style={styles.errorBanner}>
                <Text style={styles.errorText}>Connection error: {error}</Text>
              </View>
            ) : null}

            <Text style={styles.sectionHeader}>
              Live picks{upcoming.length > 0 ? ` · ${upcoming.length}` : ''}
            </Text>
            {todayLoading && upcoming.length === 0 ? (
              <ActivityIndicator style={styles.upcomingLoading} />
            ) : upcoming.length === 0 ? (
              <Text style={styles.upcomingEmpty}>
                Nothing on the board matches right now. Picks appear here as they're scored.
              </Text>
            ) : (
              upcoming.map((ep) => (
                <Pressable
                  key={ep.pick.pick_id}
                  style={styles.pickRow}
                  onPress={() => navigation.navigate('PickDetail', { pickId: ep.pick.pick_id })}
                >
                  <View style={styles.pickLeft}>
                    <View style={styles.modelChip}>
                      <Text style={styles.modelChipText}>{modelShort(ep.pick.model_id)}</Text>
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.pickLabel} numberOfLines={1}>
                        {ep.pick.pick_label}
                      </Text>
                      <View style={styles.pickMeta}>
                        <SignalBadge signal={ep.pick.signal_type} small />
                        <Text style={styles.pickDate}>
                          {gameDayLabelET(ep.pick.game_time) ?? 'Today'}
                          {ep.pick.game_time ? ` ${formatGameTimeET(ep.pick.game_time)}` : ''}
                        </Text>
                      </View>
                    </View>
                  </View>
                  <Text style={styles.upcomingOdds}>{formatAmerican(ep.pick.dk_odds)}</Text>
                </Pressable>
              ))
            )}

            <Text style={styles.sectionHeader}>Settled picks</Text>
          </>
        }
        renderItem={({ item }) => (
          <Pressable
            style={styles.pickRow}
            onPress={() => navigation.navigate('PickDetail', { pickId: item.pick_id })}
          >
            <View style={styles.pickLeft}>
              <View style={styles.modelChip}>
                <Text style={styles.modelChipText}>{modelShort(item.model_id)}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.pickLabel} numberOfLines={1}>
                  {item.pick_label}
                </Text>
                <View style={styles.pickMeta}>
                  <SignalBadge signal={item.signal_type} small />
                  <Text style={styles.pickDate}>{item.game_date}</Text>
                  <Text style={styles.pickDate}>· {item.result ?? '—'}</Text>
                </View>
              </View>
            </View>
            <Text
              style={[
                styles.pickProfit,
                {
                  color:
                    (item.profit_flat ?? 0) > 0
                      ? colors.bet
                      : (item.profit_flat ?? 0) < 0
                        ? colors.avoid
                        : colors.textSecondary,
                },
              ]}
            >
              {formatCurrencySigned(item.profit_flat)}
            </Text>
          </Pressable>
        )}
        ListEmptyComponent={
          loading ? (
            <ActivityIndicator style={styles.loading} />
          ) : (
            <EmptyState
              title="No settled picks match yet"
              subtitle="Either no picks have matched these rules yet, or the matching picks haven't settled. Lower the thresholds or add more model_id rules."
            />
          )
        }
        contentContainerStyle={styles.list}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  list: { paddingBottom: spacing.xl },
  headerCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
    marginBottom: spacing.md,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.md,
  },
  modelTitle: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    flex: 1,
  },
  ruleHeader: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginBottom: spacing.xs,
  },
  ruleRow: {
    paddingVertical: 6,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  ruleName: {
    fontSize: font.size.body,
    color: colors.textPrimary,
    fontWeight: font.weight.medium,
  },
  ruleParams: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
  },
  filterHeader: {
    marginTop: spacing.md,
  },
  filterChips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
  },
  filterChip: {
    backgroundColor: colors.noneSoft,
    borderRadius: radii.pill,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  filterChipText: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
  },
  statRow: {
    flexDirection: 'row',
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
    gap: spacing.md,
  },
  sectionHeader: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  pickRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
  },
  pickLeft: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  modelChip: {
    backgroundColor: colors.noneSoft,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
    minWidth: 50,
    alignItems: 'center',
  },
  modelChipText: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontWeight: font.weight.semibold,
  },
  pickLabel: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  pickMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginTop: 2,
  },
  pickDate: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
  },
  pickProfit: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
  },
  upcomingLoading: { marginVertical: spacing.lg },
  upcomingEmpty: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.sm,
  },
  upcomingOdds: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  loading: { marginVertical: spacing.xxl },
  errorBanner: {
    backgroundColor: colors.avoidSoft,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    borderRadius: 8,
  },
  errorText: { color: colors.avoid, fontSize: font.size.footnote },
  error: { color: colors.avoid, padding: spacing.lg, fontSize: font.size.body },
});
