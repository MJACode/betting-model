import React, { useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

import { colors, font, radii, spacing } from '@/lib/theme';
import { addDays, formatAmerican, formatCurrencySigned, formatPctSigned } from '@/lib/format';
import { modelLong, modelShort } from '@/lib/modelMeta';
import { CalendarGrid } from '@/components/CalendarGrid';
import type { CustomModelStats } from '@/hooks/useCustomModelStats';
import {
  ALL_SPORTS,
  EMPTY_DAILY,
  type DailyResults,
  type ModelDayStats,
  type SportDayBreakdown,
} from '@/lib/dailyResults';
import type { Pick } from '@/types';

/**
 * Daily results: how every model did on a given day — a consolidated "All"
 * record + ROI, a per-sport / per-model breakdown, and the individual picks.
 * The user can step days with the chevrons or jump anywhere via the calendar
 * (bounded [minDate, maxDate]). Presentational; the host owns the data
 * (useDailyResults), the selected date, and visibility (useDailyRecapControl).
 */
export function DailyResultsModal({
  visible,
  onClose,
  date,
  minDate,
  maxDate,
  onSelectDate,
  results,
  loading,
  error,
}: {
  visible: boolean;
  onClose: () => void;
  date: string;
  minDate: string;
  maxDate: string;
  onSelectDate: (date: string) => void;
  results: DailyResults;
  loading: boolean;
  error: string | null;
}) {
  const [calendarOpen, setCalendarOpen] = useState(false);

  // Every sport gets a section, in canonical order — sports with no settled
  // picks this day render an explicit empty state instead of disappearing.
  // Any sport the lib returns that isn't in ALL_SPORTS (future addition) is
  // appended so it can never be silently dropped.
  const sportSections: SportDayBreakdown[] = [
    ...ALL_SPORTS.map(
      (sport) =>
        results.sports.find((s) => s.sport === sport) ?? { sport, total: EMPTY_DAILY, models: [] },
    ),
    ...results.sports.filter((s) => !ALL_SPORTS.includes(s.sport)),
  ];

  // The displayed results can lag the selected date by one render while a new
  // day loads — treat that as loading so we never show day A under day B's header.
  const stale = results.date !== date;
  const showLoading = loading || stale;
  const hasResults = !stale && results.overall.picks > 0;
  const pending = stale ? 0 : results.pending ?? 0;
  const isYesterday = date === maxDate;
  const canPrev = date > minDate;
  const canNext = date < maxDate;

  return (
    // A native Modal renders in its own view hierarchy, so the app's root
    // SafeAreaProvider doesn't reach it — without this local provider the
    // SafeAreaView gets a 0 top inset and the close button ends up under the
    // status bar (untappable). onRequestClose handles the Android back button.
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="fullScreen"
      onRequestClose={onClose}
    >
      <SafeAreaProvider>
      <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
        <View style={styles.header}>
          <View style={styles.headerText}>
            <Text style={styles.title}>{isYesterday ? 'Yesterday’s results' : 'Daily results'}</Text>
            <Text style={styles.subtitle}>{prettyDate(date)}</Text>
          </View>
          <Pressable onPress={onClose} hitSlop={12} style={styles.closeBtn}>
            <Ionicons name="close" size={22} color={colors.textSecondary} />
          </Pressable>
        </View>

        {/* Day navigation — always visible so an empty/error day isn't a dead end. */}
        <View style={styles.dateNav}>
          <Pressable
            onPress={() => canPrev && onSelectDate(addDays(date, -1))}
            disabled={!canPrev}
            hitSlop={10}
            accessibilityLabel="Previous day"
            style={({ pressed }) => [styles.navBtn, pressed && { opacity: 0.6 }]}
          >
            <Ionicons
              name="chevron-back"
              size={20}
              color={canPrev ? colors.tint : colors.textTertiary}
            />
          </Pressable>
          <Pressable
            onPress={() => setCalendarOpen((open) => !open)}
            hitSlop={8}
            accessibilityLabel="Pick a date"
            style={({ pressed }) => [styles.dateChip, pressed && { opacity: 0.6 }]}
          >
            <Ionicons name="calendar-outline" size={15} color={colors.tint} />
            <Text style={styles.dateChipText}>{shortDate(date)}</Text>
            <Ionicons
              name={calendarOpen ? 'chevron-up' : 'chevron-down'}
              size={13}
              color={colors.tint}
            />
          </Pressable>
          <Pressable
            onPress={() => canNext && onSelectDate(addDays(date, 1))}
            disabled={!canNext}
            hitSlop={10}
            accessibilityLabel="Next day"
            style={({ pressed }) => [styles.navBtn, pressed && { opacity: 0.6 }]}
          >
            <Ionicons
              name="chevron-forward"
              size={20}
              color={canNext ? colors.tint : colors.textTertiary}
            />
          </Pressable>
        </View>

        {calendarOpen ? (
          <View style={styles.calendarWrap}>
            <CalendarGrid
              // Remount when the day changes so the grid opens on the right month.
              key={date}
              selected={date}
              minDate={minDate}
              maxDate={maxDate}
              onSelect={(d) => {
                setCalendarOpen(false);
                onSelectDate(d);
              }}
            />
          </View>
        ) : null}

        {showLoading ? (
          <View style={styles.center}>
            <ActivityIndicator />
          </View>
        ) : error ? (
          <View style={styles.center}>
            <Text style={styles.error}>Couldn’t load this day’s results.</Text>
            <Text style={styles.errorDetail}>{error}</Text>
          </View>
        ) : !hasResults ? (
          <View style={styles.center}>
            {pending > 0 ? (
              <>
                <Ionicons name="hourglass-outline" size={40} color={colors.textTertiary} />
                <Text style={styles.emptyTitle}>Results still pending</Text>
                <Text style={styles.emptyBody}>
                  {pending} {pending === 1 ? 'pick is' : 'picks are'} still awaiting a result —
                  nothing has graded yet. Check back once the day’s games settle.
                </Text>
              </>
            ) : (
              <>
                <Ionicons name="moon-outline" size={40} color={colors.textTertiary} />
                <Text style={styles.emptyTitle}>No settled picks this day</Text>
                <Text style={styles.emptyBody}>
                  An off day — nothing cleared the bar or no games settled. That’s a valid signal,
                  not a miss.
                </Text>
              </>
            )}
          </View>
        ) : (
          <ScrollView contentContainerStyle={styles.list}>
            {/* Consolidated "All" hero */}
            <View style={styles.hero}>
              <Text style={styles.heroLabel}>All models — flat-bet ROI</Text>
              <Text style={[styles.heroRoi, { color: roiColor(results.overall.roiFlat) }]}>
                {formatPctSigned(results.overall.roiFlat)}
              </Text>
              <Text style={styles.heroRecord}>{recordLine(results.overall)}</Text>
              <View style={styles.heroStats}>
                <HeroStat label="Picks" value={String(results.overall.picks)} />
                <HeroStat
                  label="P&L (flat)"
                  value={formatCurrencySigned(results.overall.profitFlat)}
                  color={roiColor(results.overall.roiFlat)}
                />
                <HeroStat label="Win rate" value={formatPctSigned(results.overall.winRate).replace('+', '')} />
              </View>
              {pending > 0 ? (
                <Text style={styles.pendingNote}>
                  +{pending} more {pending === 1 ? 'pick' : 'picks'} still awaiting a result
                </Text>
              ) : null}
            </View>

            {/* Per-sport breakdown — every sport always listed */}
            {sportSections.map((s) =>
              s.total.picks > 0 ? (
                <View key={s.sport} style={styles.sportCard}>
                  <View style={styles.sportHeader}>
                    <Text style={styles.sportName}>{s.sport}</Text>
                    <Text style={[styles.sportRoi, { color: roiColor(s.total.roiFlat) }]}>
                      {formatPctSigned(s.total.roiFlat)}
                    </Text>
                  </View>
                  <Text style={styles.sportSub}>
                    {recordLine(s.total)} · {formatCurrencySigned(s.total.profitFlat)}
                  </Text>
                  {s.models.map((m) => (
                    <ModelRow key={m.modelId} model={m} />
                  ))}
                </View>
              ) : (
                <View key={s.sport} style={[styles.sportCard, styles.sportCardEmpty]}>
                  <View style={styles.sportHeader}>
                    <Text style={styles.sportNameEmpty}>{s.sport}</Text>
                    <Text style={styles.sportEmptyNote}>No settled picks</Text>
                  </View>
                </View>
              ),
            )}

            {/* Every pick behind the record */}
            {results.gradedPicks.length > 0 ? (
              <View style={styles.sportCard}>
                <Text style={styles.picksTitle}>The picks</Text>
                {results.gradedPicks.map((p) => (
                  <PickRow key={p.pick_id} pick={p} />
                ))}
              </View>
            ) : null}

            <Text style={styles.footer}>
              Settled BET picks only, graded at the current thresholds. Flat ROI assumes a $100
              stake per pick.
            </Text>
          </ScrollView>
        )}
      </SafeAreaView>
      </SafeAreaProvider>
    </Modal>
  );
}

function HeroStat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <View style={styles.heroStat}>
      <Text style={[styles.heroStatValue, color ? { color } : null]}>{value}</Text>
      <Text style={styles.heroStatLabel}>{label}</Text>
    </View>
  );
}

function ModelRow({ model }: { model: ModelDayStats }) {
  return (
    <View style={styles.modelRow}>
      <View style={styles.modelLeft}>
        <View style={styles.chip}>
          <Text style={styles.chipText}>{modelShort(model.modelId)}</Text>
        </View>
        <View style={styles.modelNameWrap}>
          <Text style={styles.modelName} numberOfLines={1}>
            {modelLong(model.modelId)}
          </Text>
          <Text style={styles.modelSub}>
            {recordLine(model)} · {formatCurrencySigned(model.profitFlat)}
          </Text>
        </View>
      </View>
      <Text style={[styles.modelRoi, { color: roiColor(model.roiFlat) }]}>
        {formatPctSigned(model.roiFlat)}
      </Text>
    </View>
  );
}

const RESULT_STYLE: Record<string, { label: string; color: string; bg: string }> = {
  WIN: { label: 'W', color: colors.positive, bg: colors.betSoft },
  LOSS: { label: 'L', color: colors.negative, bg: colors.avoidSoft },
  PUSH: { label: 'P', color: colors.none, bg: colors.noneSoft },
};

function PickRow({ pick }: { pick: Pick }) {
  const res = RESULT_STYLE[pick.result ?? ''] ?? RESULT_STYLE.PUSH!;
  const profit = Number(pick.profit_flat ?? 0);
  return (
    <View style={styles.modelRow}>
      <View style={[styles.resultBadge, { backgroundColor: res.bg }]}>
        <Text style={[styles.resultBadgeText, { color: res.color }]}>{res.label}</Text>
      </View>
      <View style={styles.modelNameWrap}>
        <Text style={styles.modelName} numberOfLines={2}>
          {pick.pick_label}
        </Text>
        <Text style={styles.modelSub}>
          {modelShort(pick.model_id)}
          {pick.dk_odds != null ? ` · DK ${formatAmerican(pick.dk_odds)}` : ''}
        </Text>
      </View>
      <Text style={[styles.modelRoi, { color: roiColor(profit) }]}>
        {formatCurrencySigned(profit)}
      </Text>
    </View>
  );
}

function recordLine(s: CustomModelStats): string {
  const base = `${s.wins}–${s.losses}`;
  return s.pushes > 0 ? `${base}–${s.pushes}` : base;
}

function roiColor(roi: number): string {
  if (roi > 0.001) return colors.positive;
  if (roi < -0.001) return colors.negative;
  return colors.textSecondary;
}

function prettyDate(date: string): string {
  try {
    const d = new Date(`${date}T12:00:00Z`);
    return new Intl.DateTimeFormat('en-US', {
      timeZone: 'UTC',
      weekday: 'long',
      month: 'long',
      day: 'numeric',
    }).format(d);
  } catch {
    return date;
  }
}

function shortDate(date: string): string {
  try {
    const d = new Date(`${date}T12:00:00Z`);
    return new Intl.DateTimeFormat('en-US', {
      timeZone: 'UTC',
      weekday: 'short',
      month: 'short',
      day: 'numeric',
    }).format(d);
  } catch {
    return date;
  }
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
  },
  headerText: { flex: 1 },
  title: {
    fontSize: font.size.title1,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  subtitle: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
  },
  closeBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.noneSoft,
  },
  dateNav: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.sm,
  },
  navBtn: { padding: 4 },
  dateChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs + 2,
    borderRadius: radii.pill,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.tint,
  },
  dateChipText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  calendarWrap: { paddingHorizontal: spacing.lg, paddingBottom: spacing.sm },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.xl,
    gap: spacing.sm,
  },
  error: { fontSize: font.size.callout, fontWeight: font.weight.semibold, color: colors.textPrimary },
  errorDetail: { fontSize: font.size.footnote, color: colors.textSecondary, textAlign: 'center' },
  emptyTitle: {
    fontSize: font.size.title3,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginTop: spacing.sm,
  },
  emptyBody: {
    fontSize: font.size.callout,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
  },
  list: { padding: spacing.lg, paddingTop: spacing.xs, gap: spacing.md },

  hero: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.lg,
    alignItems: 'center',
  },
  heroLabel: { fontSize: font.size.footnote, color: colors.textSecondary },
  heroRoi: {
    fontSize: font.size.largeTitle,
    fontWeight: font.weight.bold,
    marginTop: 2,
  },
  heroRecord: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginTop: 2,
  },
  heroStats: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignSelf: 'stretch',
    marginTop: spacing.md,
  },
  pendingNote: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginTop: spacing.sm,
    textAlign: 'center',
  },
  heroStat: { alignItems: 'center' },
  heroStatValue: { fontSize: font.size.callout, fontWeight: font.weight.semibold, color: colors.textPrimary },
  heroStatLabel: { fontSize: font.size.caption, color: colors.textSecondary, marginTop: 2 },

  sportCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.md,
  },
  sportHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  sportName: { fontSize: font.size.headline, fontWeight: font.weight.bold, color: colors.textPrimary },
  sportRoi: { fontSize: font.size.headline, fontWeight: font.weight.bold },
  sportCardEmpty: { paddingVertical: spacing.sm, opacity: 0.75 },
  sportNameEmpty: {
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  sportEmptyNote: { fontSize: font.size.footnote, color: colors.textTertiary },
  sportSub: { fontSize: font.size.footnote, color: colors.textSecondary, marginTop: 2, marginBottom: spacing.sm },
  picksTitle: {
    fontSize: font.size.headline,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },

  modelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  modelLeft: { flexDirection: 'row', alignItems: 'center', flex: 1, gap: spacing.sm },
  chip: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radii.sm,
    backgroundColor: colors.noneSoft,
  },
  chipText: { fontSize: font.size.caption, fontWeight: font.weight.semibold, color: colors.textSecondary },
  resultBadge: {
    width: 26,
    height: 26,
    borderRadius: 13,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.sm,
  },
  resultBadgeText: { fontSize: font.size.footnote, fontWeight: font.weight.bold },
  modelNameWrap: { flex: 1 },
  modelName: { fontSize: font.size.body, fontWeight: font.weight.medium, color: colors.textPrimary },
  modelSub: { fontSize: font.size.footnote, color: colors.textSecondary, marginTop: 1 },
  modelRoi: { fontSize: font.size.callout, fontWeight: font.weight.semibold, marginLeft: spacing.sm },

  footer: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    textAlign: 'center',
    marginTop: spacing.sm,
    lineHeight: 18,
  },
});
