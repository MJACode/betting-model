import React, { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { CalibrationChart } from '@/components/CalibrationChart';
import { buildCalibration } from '@/lib/calibration';
import type { RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation, useRoute } from '@react-navigation/native';
import { EmptyState } from '@/components/EmptyState';
import { InfoTooltip } from '@/components/InfoTooltip';
import { SignalBadge } from '@/components/SignalBadge';
import { StatTile } from '@/components/StatTile';
import { computeBuiltInModelStats, useSettledPicksSincePaperStart, viewRecordToStats } from '@/hooks/useCustomModelStats';
import { useModelPickHistory } from '@/hooks/useModelPickHistory';
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
import type { FullOutcomePickRow } from '@/lib/queries';
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
    records: fullOutcomeRecords,
    loading: settledLoading,
    error: settledError,
  } = useSettledPicksSincePaperStart();

  // Today's BET picks for this model. Game-level and prop picks lock the first
  // time they're scored each day (config.LOCK_GAME_PICKS_AT_FIRST_RUN /
  // LOCK_PROP_PICKS_AT_FIRST_SIGNAL) — once written, a pick's signal never
  // changes for the rest of the day, so there's nothing to track beyond "is it
  // a BET right now."
  const todayPicks = useMemo(
    () => todayRows.filter((d) => d.pick.model_id === modelId && d.pick.signal_type === 'BET'),
    [todayRows, modelId],
  );

  const stats = useMemo(
    () =>
      fullOutcomeRecords[modelId]
        ? viewRecordToStats(fullOutcomeRecords[modelId])
        : computeBuiltInModelStats(modelId, settledRows),
    [modelId, settledRows, fullOutcomeRecords],
  );
  const { registry } = useModelRegistry(modelId);
  const clv = useMemo(() => computeClvStats(modelId, settledRows), [modelId, settledRows]);
  const calib = useMemo(
    () =>
      buildCalibration(
        settledRows.filter((p) => p.model_id === modelId && passesActionFilter(p)),
      ),
    [modelId, settledRows],
  );
  // The full pick-by-pick history behind the aggregate record above. Preferred
  // source is the full-outcome view (every scored pick graded at the current
  // cut — reconciles row-for-row with the record for MLB/WNBA models); models
  // the view doesn't cover fall back to their settled BET picks.
  const pickHistory = useModelPickHistory(modelId);
  const [historyShown, setHistoryShown] = useState(100);
  // Collapsed by default: only the most recent graded day is shown, with a
  // "See all" button to expand into the full history (which then pages 100
  // at a time via Show more). Shared by both history sources below.
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const history = useMemo(
    () =>
      settledRows
        .filter(
          (p) =>
            p.model_id === modelId &&
            passesActionFilter(p) &&
            (p.result === 'WIN' || p.result === 'LOSS' || p.result === 'PUSH'),
        )
        .sort((a, b) => b.game_date.localeCompare(a.game_date)),
    [modelId, settledRows],
  );
  // Rows are sorted newest-first, so the first row's game_date is the latest
  // graded day (usually yesterday — picks grade after games finish).
  const latestOutcomeDate = pickHistory.rows[0]?.game_date ?? null;
  const latestOutcomeRows = useMemo(
    () =>
      latestOutcomeDate
        ? pickHistory.rows.filter((r) => r.game_date === latestOutcomeDate)
        : [],
    [pickHistory.rows, latestOutcomeDate],
  );
  const latestSettledDate = history[0]?.game_date ?? null;
  const latestSettledRows = useMemo(
    () => (latestSettledDate ? history.filter((p) => p.game_date === latestSettledDate) : []),
    [history, latestSettledDate],
  );
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

            <View style={styles.sectionHeaderRow}>
              <Text style={styles.sectionHeader}>Today's potential picks</Text>
              <InfoTooltip
                title="Picks lock for the day"
                body={
                  "A pick locks the first time this model scores it today and never changes after that — it can't flip between BET and AVOID as lines move.\n\nLines refresh hourly 6am–6pm ET, then every 10 minutes until 11pm, but only newly-priced games get scored on later refreshes."
                }
                accessibilityLabel="About today's potential picks"
              />
            </View>
            <Text style={styles.sectionNote}>
              Locked for the day once scored — won't change again until the game ends.
            </Text>
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
              title="No live BET picks right now"
              subtitle="This model hasn't fired a BET signal for today's slate. Check back after the next pipeline refresh, or pull to refresh on the Picks tab."
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

            {pickHistory.rows.length > 0 ? (
              <>
                <Text style={styles.sectionHeader}>
                  All picks in this record · {pickHistory.rows.length}
                </Text>
                <Text style={styles.sectionNote}>
                  {historyExpanded || pickHistory.rows.length === latestOutcomeRows.length
                    ? "Every pick this model scored that clears today's thresholds, graded from final results — the exact set behind the record above. Tap a pick for detail."
                    : `Showing the latest graded day (${latestOutcomeDate}). Tap a pick for detail, or expand to browse every pick behind the record above.`}
                </Text>
                {(historyExpanded
                  ? pickHistory.rows.slice(0, historyShown)
                  : latestOutcomeRows
                ).map((r) => (
                  <FullOutcomeHistoryRow
                    key={String(r.pick_id)}
                    row={r}
                    onPress={() =>
                      navigation.navigate('PickDetail', { pickId: r.pick_id })
                    }
                  />
                ))}
                {!historyExpanded && pickHistory.rows.length > latestOutcomeRows.length ? (
                  <Pressable
                    style={styles.showMoreBtn}
                    onPress={() => setHistoryExpanded(true)}
                  >
                    <Text style={styles.showMoreText}>
                      See all {pickHistory.rows.length} picks
                    </Text>
                  </Pressable>
                ) : null}
                {historyExpanded && pickHistory.rows.length > historyShown ? (
                  <Pressable
                    style={styles.showMoreBtn}
                    onPress={() => setHistoryShown((n) => n + 100)}
                  >
                    <Text style={styles.showMoreText}>
                      Show {Math.min(100, pickHistory.rows.length - historyShown)} more (
                      {pickHistory.rows.length - historyShown} remaining)
                    </Text>
                  </Pressable>
                ) : null}
                {historyExpanded && pickHistory.rows.length > latestOutcomeRows.length ? (
                  <Pressable
                    style={styles.showMoreBtn}
                    onPress={() => {
                      setHistoryExpanded(false);
                      setHistoryShown(100);
                    }}
                  >
                    <Text style={styles.showMoreText}>Show latest day only</Text>
                  </Pressable>
                ) : null}
              </>
            ) : history.length > 0 ? (
              <>
                <Text style={styles.sectionHeader}>
                  Pick history · {history.length} settled
                </Text>
                {!historyExpanded && history.length > latestSettledRows.length ? (
                  <Text style={styles.sectionNote}>
                    Showing the latest settled day ({latestSettledDate}).
                  </Text>
                ) : null}
                {(historyExpanded ? history : latestSettledRows).map((p) => (
                  <HistoryPickRow
                    key={String(p.pick_id)}
                    pick={p}
                    onPress={() =>
                      navigation.navigate('PickDetail', { pickId: p.pick_id })
                    }
                  />
                ))}
                {history.length > latestSettledRows.length ? (
                  <Pressable
                    style={styles.showMoreBtn}
                    onPress={() => setHistoryExpanded((e) => !e)}
                  >
                    <Text style={styles.showMoreText}>
                      {historyExpanded
                        ? 'Show latest day only'
                        : `See all ${history.length} picks`}
                    </Text>
                  </Pressable>
                ) : null}
              </>
            ) : pickHistory.loading ? (
              <ActivityIndicator style={styles.loading} />
            ) : null}

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

            {calib ? (
              <>
                <Text style={styles.sectionHeader}>Calibration — stated odds vs reality</Text>
                <CalibrationChart calibration={calib} />
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

// One graded pick from the full-outcome view — the record's exact pick set.
// No signal badge here: the record grades every scored pick at TODAY's cut, so
// a row may have been a dead-zone NONE when it was scored; showing that badge
// next to a W/L outcome would read as a contradiction. Shows date, DK odds,
// outcome, and flat P&L at the $100-per-bet convention ('—' when the pick had
// no real DK price, e.g. prob-only HR — record-only, no fabricated P&L).
function FullOutcomeHistoryRow({
  row,
  onPress,
}: {
  row: FullOutcomePickRow;
  onPress: () => void;
}) {
  const resultColor =
    row.result === 'WIN'
      ? colors.bet
      : row.result === 'LOSS'
        ? colors.avoid
        : colors.textSecondary;
  const profit = row.profit_units == null ? null : Number(row.profit_units) * 100;
  return (
    <Pressable style={styles.pickRow} onPress={onPress}>
      <View style={styles.pickLeft}>
        <View style={{ flex: 1 }}>
          <Text style={styles.pickLabel} numberOfLines={1}>
            {row.pick_label}
          </Text>
          <View style={styles.pickMeta}>
            <Text style={styles.pickMetaText}>{row.game_date}</Text>
            <Text style={styles.pickMetaText}>· DK {formatAmerican(row.dk_odds)}</Text>
            <Text style={styles.pickMetaText}>· {formatPct(row.model_probability)}</Text>
          </View>
        </View>
      </View>
      <View style={styles.historyRight}>
        <Text style={[styles.historyResult, { color: resultColor }]}>{row.result}</Text>
        <Text style={[styles.historyProfit, { color: resultColor }]}>
          {formatCurrencySigned(profit)}
        </Text>
      </View>
    </Pressable>
  );
}

// One settled pick in the model's history — shows the outcome (WIN/LOSS/PUSH)
// and its flat P&L, colored by result. Tap to open the pick detail.
function HistoryPickRow({ pick, onPress }: { pick: Pick; onPress: () => void }) {
  const resultColor =
    pick.result === 'WIN'
      ? colors.bet
      : pick.result === 'LOSS'
        ? colors.avoid
        : colors.textSecondary;
  return (
    <Pressable style={styles.pickRow} onPress={onPress}>
      <View style={styles.pickLeft}>
        <View style={{ flex: 1 }}>
          <Text style={styles.pickLabel} numberOfLines={1}>
            {pick.pick_label}
          </Text>
          <View style={styles.pickMeta}>
            <SignalBadge signal={pick.signal_type} small />
            <Text style={styles.pickMetaText}>{pick.game_date}</Text>
            <Text style={styles.pickMetaText}>· DK {formatAmerican(pick.dk_odds)}</Text>
          </View>
        </View>
      </View>
      <View style={styles.historyRight}>
        <Text style={[styles.historyResult, { color: resultColor }]}>{pick.result}</Text>
        <Text style={[styles.historyProfit, { color: resultColor }]}>
          {formatCurrencySigned(pick.profit_flat)}
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
  sectionHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  sectionNote: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    paddingHorizontal: spacing.lg,
    marginTop: -spacing.xs,
    marginBottom: spacing.sm,
    lineHeight: 18,
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
  historyRight: {
    alignItems: 'flex-end',
    minWidth: 70,
  },
  historyResult: {
    fontSize: font.size.caption,
    fontWeight: font.weight.bold,
    letterSpacing: 0.4,
  },
  historyProfit: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    marginTop: 2,
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
  showMoreBtn: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    paddingVertical: spacing.md,
    alignItems: 'center',
  },
  showMoreText: {
    fontSize: font.size.footnote,
    color: colors.tint,
    fontWeight: font.weight.semibold,
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
