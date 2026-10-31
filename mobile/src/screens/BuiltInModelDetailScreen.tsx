import React, { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation, useRoute } from '@react-navigation/native';
import { EmptyState } from '@/components/EmptyState';
import { ModelBadgeRow } from '@/components/ModelBadgeRow';
import { InfoTooltip } from '@/components/InfoTooltip';
import { SignalBadge } from '@/components/SignalBadge';
import { StatTile } from '@/components/StatTile';
import { TagChip } from '@/components/TagChip';
import { computeBuiltInModelStats, useSettledPicksSincePaperStart, viewRecordToStats } from '@/hooks/useCustomModelStats';
import { useModelRegistry } from '@/hooks/useModelRegistry';
import { useTodayPicks } from '@/hooks/useTodayPicks';
import {
  dayLabelET,
  dayLabelSpokenET,
  formatAmerican,
  formatCurrencySigned,
  formatGameTimeET,
  formatPct,
  formatPctSigned,
  formatSigned,
  gameDayLabelET,
} from '@/lib/format';
import { featureLabel, MODEL_TOP_FEATURES, numOrNull } from '@/lib/markets';
import { MODEL_META, modelDetailTitle, modelLong, modelPageTiming, modelShort, sportOfModel } from '@/lib/modelMeta';
import { navShowsSportOnly } from '@/lib/modelBadgeLayout';
import { signalsContextTime } from '@/lib/signalsCard';
import { colors, font, pnlColor, radii, spacing } from '@/lib/theme';
import { ErrorBanner } from '@/components/ErrorState';
import { roundsToZero, signalDisplayName } from '@/lib/tone';
import { isModelPaused, isUnlockedPreview, passesRecordFilter, publishedRecordKeeps } from '@/lib/thresholds';
import type { EnrichedPick, RootStackParamList, SettledPick } from '@/types';
import { LIVE_RECORD_START_SHORT, MIN_PICKS_FOR_COLOURED_ROI, thinSampleCaption } from '@/lib/recordStart';
import { bookLabelShort, pickRowTitle, storedQuoteBook } from '@/lib/markets';
import { decisionEdge, decisionOdds } from '@/lib/decisionPrice';
import { BetslipBarSpacer } from '@/components/BetslipBarSpacer';

type Route = RouteProp<RootStackParamList, 'BuiltInModelDetail'>;
type Nav = NativeStackNavigationProp<RootStackParamList>;

export function BuiltInModelDetailScreen() {
  const route = useRoute<Route>();
  const navigation = useNavigation<Nav>();
  const { modelId } = route.params;
  const meta = MODEL_META[modelId];
  // A paused model is LISTED and reachable (mike, 2026-09-12: "Don't hide
  // detail of paused models unless I say so"), so every surface here has to say
  // which state it is in rather than leaving it to be inferred from an empty
  // board.
  const paused = isModelPaused(modelId);

  const { data: todayRows, loading: todayLoading } = useTodayPicks();
  const {
    rows: settledRows,
    records: fullOutcomeRecords,
    loading: settledLoading,
    error: settledError,
    refresh: refreshSettled,
  } = useSettledPicksSincePaperStart();

  // Today's BET picks for this model. Game-level and prop picks lock the first
  // time they're scored each day (config.LOCK_GAME_PICKS_AT_FIRST_RUN /
  // LOCK_PROP_PICKS_AT_FIRST_SIGNAL) — once written, a pick's signal never
  // changes for the rest of the day, so there's nothing to track beyond "is it
  // a BET right now."
  const todayPicks = useMemo(
    () =>
      todayRows.filter(
        (d) =>
          d.pick.model_id === modelId &&
          d.pick.signal_type === 'BET' &&
          // Future-dated UFC/golf picks are unlocked previews, not signals.
          !isUnlockedPreview(d.pick),
      ),
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
  // The tiles read v_public_track_record when that fetch succeeded. The list
  // matches them: a row counts only when Discord still has it. A failed
  // ledger read stamps `unknown` and does not throw, so the view can be
  // present while the stamp is not. Those rows stay, and the note says the
  // check did not finish. When the view itself is missing, the tiles use the
  // same keep-unknown fallback as this list.
  const viewPresent = fullOutcomeRecords[modelId] != null;
  const ledgerUnread = settledRows.some(
    (p) => p.model_id === modelId && p.discordPublish === 'unknown',
  );
  const clv = useMemo(
    () =>
      computeClvStats(
        modelId,
        viewPresent && !ledgerUnread
          ? settledRows.filter((p) => p.discordPublish === 'published')
          : settledRows,
      ),
    [modelId, settledRows, viewPresent, ledgerUnread],
  );
  const [historyShown, setHistoryShown] = useState(100);
  // Collapsed by default: only the most recent graded day is shown, with a
  // "See all" button to expand into the full history (which then pages 100
  // at a time via Show more).
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const history = useMemo(
    () =>
      settledRows
        .filter(
          (p) =>
            p.model_id === modelId &&
            passesRecordFilter(p) &&
            (p.result === 'WIN' || p.result === 'LOSS' || p.result === 'PUSH') &&
            (viewPresent && !ledgerUnread
              ? p.discordPublish === 'published'
              : publishedRecordKeeps(p)),
        )
        .sort((a, b) => b.game_date.localeCompare(a.game_date)),
    [modelId, settledRows, viewPresent, ledgerUnread],
  );
  // Rows are sorted newest-first, so the first row's game_date is the latest
  // graded day (usually yesterday — picks grade after games finish).
  const latestSettledDate = history[0]?.game_date ?? null;
  const latestSettledRows = useMemo(
    () => (latestSettledDate ? history.filter((p) => p.game_date === latestSettledDate) : []),
    [history, latestSettledDate],
  );
  const topFeatures = MODEL_TOP_FEATURES[modelId] ?? [];
  const { fontScale } = useWindowDimensions();

  // The long name: the prop-market rules share the short label "Props", so a
  // short title made their screens indistinguishable. The chip keeps it.
  // At 1.5× and above the bar truncates ("NBA Team T…"), so it shows the sport.
  useEffect(() => {
    navigation.setOptions({
      title: navShowsSportOnly(fontScale) ? sportOfModel(modelId) : modelLong(modelId),
    });
  }, [navigation, modelId, fontScale]);

  // Prop models are Poisson count projections, so the model card labels their
  // holdout accuracy as over/under accuracy rather than a straight hit rate.
  const isProp = meta != null && meta.type !== 'game';

  const decided = stats.wins + stats.losses;
  // Settled with no book price: in the W-L, not in the money (flatPnl).
  const unpriced = stats.picks - Math.round(stats.stakedFlat / 100);
  // The row that opened this screen greys a thin ROI and captions it; the
  // drill-down is where a member lingers and screenshots, so it cannot be the
  // one surface that shows the same 1-bet number in full bet-green with no
  // qualifier. Same constant, same caption, same rule.
  const thin = decided < MIN_PICKS_FOR_COLOURED_ROI;
  // Each tile's tone comes from the number it prints, rounded as printed.
  const roiColor = thin
    ? colors.textSecondary
    : pnlColor(stats.roiFlat, 1, 100);
  const pnlTint = thin
    ? colors.textSecondary
    : pnlColor(stats.profitFlat, 2);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <FlatList
        data={todayPicks}
        keyExtractor={(item) => String(item.pick.pick_id)}
        ListHeaderComponent={
          <>
            <View style={styles.headerCard}>
              <ModelBadgeRow badge={modelShort(modelId)}>
                <Text
                  style={styles.modelTitle}
                  adjustsFontSizeToFit
                  minimumFontScale={0.85}
                >
                  {modelDetailTitle(modelId)}
                </Text>
                {paused ? (
                  <View style={styles.pausedChip}>
                    <TagChip label="Paused" />
                  </View>
                ) : null}
              </ModelBadgeRow>
              <Text style={styles.modelSubtitle}>
                {meta ? `Built-in ${categoryLabel(meta.type)} model` : 'Built-in model'}
              </Text>
              {/* A pause is about the FUTURE. Said plainly here so the settled
                  record below — which stays, and is why a paused model is shown
                  at all — is not read as a live model's. */}
              {paused ? (
                <Text style={styles.modelSubtitle}>
                  Paused — not producing new picks. The record below is what it bet
                  while it was live, and it stays.
                </Text>
              ) : null}
            </View>

            <View style={styles.sectionHeaderRow}>
              <Text style={styles.sectionHeader}>Today's potential picks</Text>
              <InfoTooltip
                title={modelPageTiming(modelId).title}
                body={modelPageTiming(modelId).body}
                accessibilityLabel="About today's potential picks"
              />
            </View>
            <Text style={styles.sectionNote}>
              {paused
                ? 'Paused, so there are no picks today.'
                : modelPageTiming(modelId).note}
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
              subtitle={modelPageTiming(modelId).empty}
            />
          )
        }
        ListFooterComponent={
          <>
            <Text style={styles.sectionHeader}>Since {LIVE_RECORD_START_SHORT} · settled bets, as posted</Text>
            <View style={styles.statRow}>
              <StatTile
                label="Picks"
                value={String(stats.picks)}
                caption={`settled, as posted${unpriced > 0 ? ` · ${unpriced} unpriced` : ''}`}
              />
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
                value={stats.stakedFlat > 0 ? formatPctSigned(stats.roiFlat) : '—'}
                tint={roiColor}
                caption={thin && stats.stakedFlat > 0 ? thinSampleCaption() : 'vs $100 flat per bet'}
              />
              <StatTile
                label="P&L"
                value={stats.stakedFlat > 0 ? formatCurrencySigned(stats.profitFlat) : '—'}
                tint={pnlTint}
                caption="settled only"
              />
            </View>

            {history.length > 0 ? (
              <>
                <Text style={styles.sectionHeader}>
                  Picks behind this record · {history.length}
                </Text>
                <Text style={styles.sectionNote}>
                  {viewPresent && ledgerUnread
                    ? 'The Discord check did not finish, so this list can be wider than the tiles. Tap a pick for detail.'
                    : !viewPresent && ledgerUnread
                      ? 'The Discord check did not finish. The tiles and this list both keep picks whose posting status is unknown.'
                    : historyExpanded || history.length === latestSettledRows.length
                      ? 'Posted picks that settled into the record above. Tap a pick for detail.'
                      : `Showing the latest posted day (${dayLabelET(latestSettledDate ?? '')}). Tap a pick for detail, or expand to browse every posted pick behind the record above.`}
                </Text>
                {(historyExpanded ? history.slice(0, historyShown) : latestSettledRows).map((p) => (
                  <HistoryPickRow
                    key={String(p.pick_id)}
                    pick={p}
                    onPress={() =>
                      navigation.navigate('PickDetail', { pickId: p.pick_id })
                    }
                  />
                ))}
                {!historyExpanded && history.length > latestSettledRows.length ? (
                  <Pressable
                    accessibilityRole="button"
                    accessibilityLabel={`See all ${history.length} picks`}
                    hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                    style={styles.showMoreBtn}
                    onPress={() => setHistoryExpanded(true)}
                  >
                    <Text style={styles.showMoreText}>
                      See all {history.length} picks
                    </Text>
                  </Pressable>
                ) : null}
                {historyExpanded && history.length > historyShown ? (
                  <Pressable
                    accessibilityRole="button"
                    accessibilityLabel={`Show ${Math.min(100, history.length - historyShown)} more, ${history.length - historyShown} remaining`}
                    hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                    style={styles.showMoreBtn}
                    onPress={() => setHistoryShown((n) => n + 100)}
                  >
                    <Text style={styles.showMoreText}>
                      Show {Math.min(100, history.length - historyShown)} more (
                      {history.length - historyShown} remaining)
                    </Text>
                  </Pressable>
                ) : null}
                {historyExpanded && history.length > latestSettledRows.length ? (
                  <Pressable
                    accessibilityRole="button"
                    accessibilityLabel="Show latest day only"
                    hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
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
            ) : settledLoading ? (
              <ActivityIndicator style={styles.loading} />
            ) : settledError ? null : (
              <Text style={styles.sectionNote}>No posted picks in this record.</Text>
            )}

            {clv ? (
              <>
                <Text style={styles.sectionHeader}>Closing Line Value</Text>
                <View style={styles.statRow}>
                  <StatTile
                    label="Avg CLV"
                    value={formatSigned(clv.avg, 1, '%')}
                    tint={roundsToZero(clv.avg, 1) ? undefined : pnlColor(clv.avg, 1)}
                    caption={
                      ledgerUnread
                        ? 'Discord check did not finish, so this includes picks whose posting status is unknown'
                        : 'vs the book we bet'
                    }
                  />
                  <StatTile
                    label="Beat close"
                    value={formatPct(clv.beatRate)}
                    tint={clv.beatRate >= 0.5 ? colors.betInk : colors.avoidInk}
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
                  {/* Paired, always. StatTile is flex:1, so a lone tile stretches
                      edge to edge and breaks the 2-up grid every other section on
                      this screen uses — render the ROI tile with an em-dash rather
                      than dropping it. */}
                  <StatTile
                    label="Holdout ROI"
                    value={
                      numOrNull(registry.holdout_roi) != null
                        ? formatPctSigned(numOrNull(registry.holdout_roi))
                        : '—'
                    }
                    caption="backtest, flat bets"
                  />
                </View>
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
                    <TagChip key={f} label={featureLabel(f)} />
                  ))}
                </View>
              </>
            ) : null}

            {settledError ? (
              <ErrorBanner
                what="this model’s record"
                error={settledError}
                onRetry={() => void refreshSettled()}
                retrying={settledLoading}
                style={styles.errorBannerInset}
              />
            ) : null}
            {settledLoading && stats.picks === 0 && history.length > 0 ? (
              <ActivityIndicator style={styles.loading} />
            ) : null}
            <BetslipBarSpacer />
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
  // The day as well as the time for a game that is not today: look-ahead
  // rows (the NCAAB model decides the evening before) read as tonight with a
  // clock time alone. A game today keeps the time alone.
  const timeLabel = signalsContextTime(gameDayLabelET(game?.commence_time), formatGameTimeET(game?.commence_time));
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={[pick.pick_label, signalDisplayName(pick.signal_type), timeLabel, `${bookLabelShort(storedQuoteBook(pick))} ${formatAmerican(decisionOdds(pick))}`, `Model ${formatPct(pick.model_probability)}`, `Edge ${formatPctSigned(decisionEdge(pick))}`].filter(Boolean).join(', ')}
      style={styles.pickRow}
      onPress={onPress}
    >
      <View style={styles.pickLeft}>
        <View style={{ flex: 1 }}>
          <Text style={styles.pickLabel} numberOfLines={1}>
            {pickRowTitle(pick)}
          </Text>
          <View style={styles.pickMeta}>
            <SignalBadge signal={pick.signal_type} small />
            {timeLabel ? <Text style={styles.pickMetaText}>{timeLabel}</Text> : null}
            <Text style={styles.pickMetaText}>· {bookLabelShort(storedQuoteBook(pick))} {formatAmerican(decisionOdds(pick))}</Text>
          </View>
        </View>
      </View>
      <View style={styles.pickStats}>
        <Text style={styles.pickProb}>{formatPct(pick.model_probability)}</Text>
        <Text style={[styles.pickEdge, edgeColorStyle(decisionEdge(pick))]}>
          {formatPctSigned(decisionEdge(pick))}
        </Text>
      </View>
    </Pressable>
  );
}

// One settled pick in the model's history — shows the outcome (WIN/LOSS/PUSH)
// and its flat P&L, colored by result. Tap to open the pick detail.
function HistoryPickRow({ pick, onPress }: { pick: SettledPick; onPress: () => void }) {
  const resultColor =
    pick.result === 'WIN'
      ? colors.betInk
      : pick.result === 'LOSS'
        ? colors.avoidInk
        : colors.textSecondary;
  const profitLabel = decisionOdds(pick) == null ? '—' : formatCurrencySigned(pick.profit_flat);
  return (
    <Pressable
      style={styles.pickRow}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={[
        pick.pick_label,
        pick.result,
        dayLabelSpokenET(pick.game_date),
        `${bookLabelShort(storedQuoteBook(pick))} ${formatAmerican(decisionOdds(pick))}`,
        profitLabel,
      ].filter(Boolean).join(', ')}
    >
      <View style={styles.pickLeft}>
        <View style={{ flex: 1 }}>
          <Text style={styles.pickLabel} numberOfLines={1}>
            {pickRowTitle(pick)}
          </Text>
          <View style={styles.pickMeta}>
            <Text style={styles.pickMetaText}>{dayLabelET(pick.game_date)}</Text>
            <Text style={styles.pickMetaText}>· {bookLabelShort(storedQuoteBook(pick))} {formatAmerican(decisionOdds(pick))}</Text>
          </View>
        </View>
      </View>
      <View style={styles.historyRight}>
        <Text style={[styles.historyResult, { color: resultColor }]}>{pick.result}</Text>
        <Text style={[styles.historyProfit, { color: resultColor }]}>
          {/* No price, no money — the row's total excludes this pick, so the
              list must not show the -110 that settlement invented for it. */}
          {decisionOdds(pick) == null ? '—' : formatCurrencySigned(pick.profit_flat)}
        </Text>
      </View>
    </Pressable>
  );
}

function edgeColorStyle(edge: number) {
  return { color: pnlColor(edge, 1, 100) };
}

// Aggregate closing line value across this model's settled BET picks that
// clear the current action thresholds — same pick set as the record above.
// Positive avg CLV = the model consistently beats the closing price — the
// strongest available evidence its edge is real.
function computeClvStats(
  modelId: string,
  settled: SettledPick[],
): { avg: number; beatRate: number; count: number } | null {
  const vals = settled
    .filter((p) => p.model_id === modelId && passesRecordFilter(p) && publishedRecordKeeps(p) && p.clv_method === 'standard_v2' && p.clv_pct != null)
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
  pausedChip: {
    alignSelf: 'flex-start',
    marginTop: spacing.xs,
  },
  modelTitle: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
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
    textDecorationLine: 'underline',
    fontWeight: font.weight.semibold,
  },
  loading: { marginVertical: spacing.xl },
  // ErrorBanner (PATTERNS §E3) keeps this screen's old banner spacing.
  errorBannerInset: { marginTop: 0, marginBottom: spacing.sm },
});
