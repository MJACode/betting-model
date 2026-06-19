import React, { useEffect, useMemo } from 'react';
import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation, useRoute } from '@react-navigation/native';
import { EmptyState } from '@/components/EmptyState';
import { SignalBadge } from '@/components/SignalBadge';
import { StatTile } from '@/components/StatTile';
import { computeBuiltInModelStats, useSettledPicksSincePaperStart } from '@/hooks/useCustomModelStats';
import { useModelRegistry } from '@/hooks/useModelRegistry';
import { useTodayPicks } from '@/hooks/useTodayPicks';
import {
  formatAmerican,
  formatCurrencySigned,
  formatGameTimeET,
  formatPct,
  formatPctSigned,
} from '@/lib/format';
import { featureLabel, MODEL_TOP_FEATURES, numOrNull } from '@/lib/markets';
import { MODEL_META, modelLong, modelShort } from '@/lib/modelMeta';
import { colors, font, radii, spacing } from '@/lib/theme';
import { passesActionFilter } from '@/lib/thresholds';
import type { EnrichedPick, Pick, RootStackParamList } from '@/types';

type Route = RouteProp<RootStackParamList, 'BuiltInModelDetail'>;
type Nav = NativeStackNavigationProp<RootStackParamList>;

export function BuiltInModelDetailScreen() {
  const route = useRoute<Route>();
  const navigation = useNavigation<Nav>();
  const { modelId } = route.params;
  const meta = MODEL_META[modelId];

  const { data: todayRows, loading: todayLoading } = useTodayPicks();
  const {
    rows: settledRows,
    loading: settledLoading,
    error: settledError,
  } = useSettledPicksSincePaperStart();

  const todayPicks = useMemo(
    () => todayRows.filter((r) => r.pick.model_id === modelId && r.pick.signal_type === 'BET'),
    [todayRows, modelId],
  );

  const stats = useMemo(
    () => computeBuiltInModelStats(modelId, settledRows),
    [modelId, settledRows],
  );
  const { registry } = useModelRegistry(modelId);
  const clv = useMemo(() => computeClvStats(modelId, settledRows), [modelId, settledRows]);
  const topFeatures = MODEL_TOP_FEATURES[modelId] ?? [];

  useEffect(() => {
    navigation.setOptions({ title: modelShort(modelId) });
  }, [navigation, modelId]);

  // The ≤5% calibration gate only applies to the binary game/F5 models.
  // Prop models are Poisson count projections whose CalError is naturally
  // high (IP/PA variance, not miscalibration), so the number is misleading —
  // hide it for those.
  const isProp = meta != null && meta.type !== 'game';

  const decided = stats.wins + stats.losses;
  const roiColor =
    stats.roiFlat > 0 ? colors.bet : stats.roiFlat < 0 ? colors.avoid : colors.textSecondary;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <FlatList
        data={todayPicks}
        keyExtractor={(item) => String(item.pick.pick_id)}
        ListHeaderComponent={
          <>
            <View style={styles.headerCard}>
              <View style={styles.headerRow}>
                <View style={styles.modelChip}>
                  <Text style={styles.modelChipText}>{modelShort(modelId)}</Text>
                </View>
                <Text style={styles.modelTitle}>{modelLong(modelId)}</Text>
              </View>
              <Text style={styles.modelSubtitle}>
                {meta ? `Built-in ${categoryLabel(meta.type)} model` : 'Built-in model'}
              </Text>
            </View>

            <Text style={styles.sectionHeader}>Today's BET picks</Text>
          </>
        }
        renderItem={({ item }) => (
          <TodayPickRow
            enriched={item}
            onPress={() =>
              navigation.navigate('PickDetail', { pickId: item.pick.pick_id })
            }
          />
        )}
        ListEmptyComponent={
          todayLoading ? (
            <ActivityIndicator style={styles.loading} />
          ) : (
            <EmptyState
              title="No BET picks today"
              subtitle="This model didn't fire any BET signals for today's slate. Check back after the next pipeline refresh, or pull to refresh on the Picks tab."
            />
          )
        }
        ListFooterComponent={
          <>
            <Text style={styles.sectionHeader}>Since 2026-04-14 · at current thresholds</Text>
            <View style={styles.statRow}>
              <StatTile label="Picks" value={String(stats.picks)} caption="settled, meets current cut" />
              <StatTile
                label="Win %"
                value={decided > 0 ? formatPct(stats.winRate) : '—'}
                caption={
                  decided > 0
                    ? `${stats.wins}-${stats.losses}${stats.pushes > 0 ? `-${stats.pushes}` : ''}`
                    : 'no decided'
                }
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
            {clv ? (
              <>
                <Text style={styles.sectionHeader}>Closing Line Value</Text>
                <View style={styles.statRow}>
                  <StatTile
                    label="Avg CLV"
                    value={`${clv.avg > 0 ? '+' : ''}${clv.avg.toFixed(1)}pp`}
                    tint={clv.avg > 0 ? colors.bet : clv.avg < 0 ? colors.avoid : undefined}
                    caption="vs the closing price"
                  />
                  <StatTile
                    label="Beat close"
                    value={formatPct(clv.beatRate)}
                    tint={clv.beatRate >= 0.5 ? colors.bet : colors.avoid}
                    caption={`${clv.count} picks with CLV`}
                  />
                </View>
              </>
            ) : null}

            {registry ? (
              <>
                <Text style={styles.sectionHeader}>Model card</Text>
                <View style={styles.statRow}>
                  <StatTile
                    label={isProp ? 'Holdout O/U acc' : 'Holdout acc'}
                    value={formatPct(numOrNull(registry.holdout_accuracy))}
                    caption={
                      registry.holdout_season != null
                        ? `${registry.holdout_season} holdout season`
                        : 'holdout'
                    }
                  />
                  {isProp ? null : (
                    <StatTile
                      label="Cal error"
                      value={formatPct(numOrNull(registry.calibration_score))}
                      tint={
                        numOrNull(registry.calibration_score) != null &&
                        numOrNull(registry.calibration_score)! <= 0.05
                          ? colors.bet
                          : colors.med
                      }
                      caption="gate ≤ 5%"
                    />
                  )}
                </View>
                {numOrNull(registry.holdout_roi) ? (
                  <View style={styles.statRow}>
                    <StatTile
                      label="Holdout ROI"
                      value={formatPctSigned(numOrNull(registry.holdout_roi))}
                      caption="backtest, flat bets"
                    />
                  </View>
                ) : null}
                <Text style={styles.registryMeta}>
                  v{registry.version} · trained {registry.trained_on}
                  {registry.holdout_picks != null ? ` · ${registry.holdout_picks} holdout rows` : ''}
                </Text>
              </>
            ) : null}

            {topFeatures.length > 0 ? (
              <>
                <Text style={styles.sectionHeader}>Top model inputs</Text>
                <View style={styles.featureWrap}>
                  {topFeatures.map((f) => (
                    <View key={f} style={styles.featureChip}>
                      <Text style={styles.featureChipText}>{featureLabel(f)}</Text>
                    </View>
                  ))}
                </View>
              </>
            ) : null}

            {settledError ? (
              <View style={styles.errorBanner}>
                <Text style={styles.errorText}>Connection error: {settledError}</Text>
              </View>
            ) : null}
            {settledLoading && stats.picks === 0 ? (
              <ActivityIndicator style={styles.loading} />
            ) : null}
          </>
        }
        contentContainerStyle={styles.list}
      />
    </SafeAreaView>
  );
}

function TodayPickRow({
  enriched,
  onPress,
}: {
  enriched: EnrichedPick;
  onPress: () => void;
}) {
  const { pick, game } = enriched;
  const timeLabel = formatGameTimeET(game?.commence_time);
  return (
    <Pressable style={styles.pickRow} onPress={onPress}>
      <View style={styles.pickLeft}>
        <View style={{ flex: 1 }}>
          <Text style={styles.pickLabel} numberOfLines={1}>
            {pick.pick_label}
          </Text>
          <View style={styles.pickMeta}>
            <SignalBadge signal={pick.signal_type} small />
            {timeLabel ? <Text style={styles.pickMetaText}>{timeLabel}</Text> : null}
            <Text style={styles.pickMetaText}>· DK {formatAmerican(pick.dk_odds)}</Text>
          </View>
        </View>
      </View>
      <View style={styles.pickStats}>
        <Text style={styles.pickProb}>{formatPct(pick.model_probability)}</Text>
        <Text style={[styles.pickEdge, edgeColorStyle(pick.edge)]}>
          {formatPctSigned(pick.edge)}
        </Text>
      </View>
    </Pressable>
  );
}

function edgeColorStyle(edge: number) {
  return { color: edge > 0 ? colors.bet : edge < 0 ? colors.avoid : colors.textSecondary };
}

// Aggregate closing line value across this model's settled BET picks that
// clear the current action thresholds — same pick set as the record above.
// Positive avg CLV = the model consistently beats the closing price — the
// strongest available evidence its edge is real.
function computeClvStats(
  modelId: string,
  settled: Pick[],
): { avg: number; beatRate: number; count: number } | null {
  const vals = settled
    .filter((p) => p.model_id === modelId && passesActionFilter(p) && p.clv_pct != null)
    .map((p) => Number(p.clv_pct));
  if (vals.length === 0) return null;
  const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
  const beatRate = vals.filter((v) => v > 0).length / vals.length;
  return { avg, beatRate, count: vals.length };
}

function categoryLabel(type: 'game' | 'pitcher_prop' | 'batter_prop' | 'player_prop'): string {
  if (type === 'pitcher_prop') return 'pitcher prop';
  if (type === 'batter_prop') return 'batter prop';
  if (type === 'player_prop') return 'player prop';
  return 'game';
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
  modelTitle: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    flex: 1,
  },
  modelSubtitle: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  sectionHeader: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  statRow: {
    flexDirection: 'row',
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
    gap: spacing.md,
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
  pickMetaText: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
  },
  pickStats: {
    alignItems: 'flex-end',
    minWidth: 70,
  },
  pickProb: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  pickEdge: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    marginTop: 2,
  },
  registryMeta: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  featureWrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  featureChip: {
    backgroundColor: colors.noneSoft,
    borderRadius: radii.pill,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  featureChipText: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
  },
  loading: { marginVertical: spacing.xl },
  errorBanner: {
    backgroundColor: colors.avoidSoft,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    borderRadius: 8,
  },
  errorText: { color: colors.avoid, fontSize: font.size.footnote },
});
