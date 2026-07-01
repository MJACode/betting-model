import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Dimensions,
  Pressable,
  RefreshControl,
  ScrollView,
  Share,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import type { CompositeNavigationProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import type { RootStackParamList, TabParamList } from '@/types';
import {
  fetchPublicTrackRecord,
  fetchTrackRecordDaily,
} from '@/lib/queries';
import { modelLong } from '@/lib/modelMeta';
import { EquityCurve, type EquityPoint } from '@/components/EquityCurve';
import { CalibrationChart } from '@/components/CalibrationChart';
import { SettingsButton } from '@/components/SettingsButton';
import { buildCalibration } from '@/lib/calibration';
import { useSettledPicksSincePaperStart } from '@/hooks/useCustomModelStats';
import { passesActionFilter } from '@/lib/thresholds';
import {
  EMPTY_SUMMARY,
  groupBySport,
  summarize,
  type SportGroup,
  type TrackRecordSummary,
} from '@/lib/trackRecord';
import { buildShareMessage } from '@/lib/shareRecord';
import { showYesterdayResults } from '@/hooks/useDailyRecapControl';
import { formatPct, formatPctSigned } from '@/lib/format';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { TrackRecordDailyRow, TrackRecordRow } from '@/types';

const PAPER_START = '2026-04-14';

function roiColor(roi: number): string {
  if (roi > 0.001) return colors.positive;
  if (roi < -0.001) return colors.negative;
  return colors.textSecondary;
}

export function TrackRecordScreen() {
  const navigation =
    useNavigation<
      CompositeNavigationProp<
        BottomTabNavigationProp<TabParamList, 'TrackRecord'>,
        NativeStackNavigationProp<RootStackParamList>
      >
    >();
  const [rows, setRows] = useState<TrackRecordRow[]>([]);
  const [daily, setDaily] = useState<TrackRecordDailyRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sportSel, setSportSel] = useState<string>('All');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [recRows, dailyRows] = await Promise.all([
        fetchPublicTrackRecord(),
        // Daily series is enrichment for the chart — don't fail the page on it.
        fetchTrackRecordDaily().catch(() => [] as TrackRecordDailyRow[]),
      ]);
      setRows(recRows);
      setDaily(dailyRows);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Sport selector — "All" plus whichever sports actually have record rows,
  // in a stable preferred order.
  const availableSports: string[] = useMemo(() => {
    const present = new Set(rows.map((r) => r.sport));
    const order = ['MLB', 'WNBA', 'NBA', 'UFC', 'NHL', 'GOLF'];
    const known = order.filter((s) => present.has(s));
    const extra = [...present].filter((s) => !order.includes(s)).sort();
    return ['All', ...known, ...extra];
  }, [rows]);

  const visibleRows = useMemo(
    () => (sportSel === 'All' ? rows : rows.filter((r) => r.sport === sportSel)),
    [rows, sportSel],
  );
  const visibleDaily = useMemo(
    () => (sportSel === 'All' ? daily : daily.filter((d) => d.sport === sportSel)),
    [daily, sportSel],
  );

  const overall: TrackRecordSummary = useMemo(
    () => (visibleRows.length ? summarize(visibleRows) : EMPTY_SUMMARY),
    [visibleRows],
  );
  const groups: SportGroup[] = useMemo(() => groupBySport(visibleRows), [visibleRows]);

  // Cumulative flat-bet units over time (sum profit_flat across sports per day).
  const equity: EquityPoint[] = useMemo(() => {
    const byDate = new Map<string, number>();
    for (const d of visibleDaily) {
      byDate.set(d.game_date, (byDate.get(d.game_date) ?? 0) + Number(d.profit_flat ?? 0));
    }
    const dates = [...byDate.keys()].sort();
    let cum = 0;
    return dates.map((date) => {
      cum += byDate.get(date) ?? 0;
      return { date, cumUnits: cum / 100 };
    });
  }, [visibleDaily]);

  // Overall calibration across every settled BET pick that meets current cuts.
  const { rows: settledPicks } = useSettledPicksSincePaperStart();
  const calibration = useMemo(
    () =>
      buildCalibration(
        settledPicks.filter(
          (p) => passesActionFilter(p) && (sportSel === 'All' || p.sport === sportSel),
        ),
        { minTotal: 30 },
      ),
    [settledPicks, sportSel],
  );

  const chartWidth = Dimensions.get('window').width - spacing.lg * 2 - spacing.lg * 2;

  const canShare = rows.length > 0 && overall.picks > 0;
  const onShare = useCallback(() => {
    void Share.share({
      message: buildShareMessage(overall, {
        endUnits: equity.length ? equity[equity.length - 1]!.cumUnits : null,
        since: PAPER_START,
      }),
    }).catch(() => {});
  }, [overall, equity]);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={() => void load()} />}
      >
        <View style={styles.titleRow}>
          <Text style={styles.title}>Track Record</Text>
          <View style={styles.rightActions}>
            <Pressable
              onPress={() => showYesterdayResults()}
              hitSlop={8}
              style={({ pressed }) => [styles.shareBtn, pressed && { opacity: 0.6 }]}
            >
              <Ionicons name="calendar-outline" size={16} color={colors.tint} />
              <Text style={styles.shareBtnText}>Yesterday</Text>
            </Pressable>
            {canShare ? (
              <Pressable
                onPress={onShare}
                hitSlop={8}
                style={({ pressed }) => [styles.shareBtn, pressed && { opacity: 0.6 }]}
              >
                <Ionicons name="share-outline" size={16} color={colors.tint} />
                <Text style={styles.shareBtnText}>Share</Text>
              </Pressable>
            ) : null}
            <SettingsButton />
          </View>
        </View>
        <Text style={styles.subtitle}>
          Every pick the model flagged as a BET that meets our current criteria — wins, losses
          and pushes. Nothing hidden, nothing cherry-picked.
        </Text>

        {availableSports.length > 2 ? (
          <View style={styles.sportTabs}>
            {availableSports.map((s) => {
              const active = s === sportSel;
              return (
                <Pressable
                  key={s}
                  onPress={() => setSportSel(s)}
                  style={({ pressed }) => [
                    styles.sportTab,
                    active && styles.sportTabActive,
                    pressed && { opacity: 0.7 },
                  ]}
                >
                  <Text style={[styles.sportTabText, active && styles.sportTabTextActive]}>{s}</Text>
                </Pressable>
              );
            })}
          </View>
        ) : null}

        {error ? <Text style={styles.error}>Couldn’t load the record: {error}</Text> : null}
        {loading && rows.length === 0 ? <ActivityIndicator style={styles.loading} /> : null}

        {/* Overall hero */}
        <View style={styles.heroCard}>
          <Text style={styles.heroLabel}>Flat-bet ROI</Text>
          <Text style={[styles.heroRoi, { color: roiColor(overall.roiFlat) }]}>
            {formatPctSigned(overall.roiFlat)}
          </Text>
          <Text style={styles.heroRecord}>
            {overall.wins}–{overall.losses}
            {overall.pushes > 0 ? `–${overall.pushes}` : ''} · {overall.picks} settled picks
          </Text>
          <View style={styles.heroStatsRow}>
            <HeroStat label="Win rate" value={formatPct(overall.winRate, 0)} />
            <HeroStat
              label="Beat the close"
              value={overall.clvBeatRate != null ? formatPct(overall.clvBeatRate, 0) : '—'}
            />
            <HeroStat label="Since" value={PAPER_START.slice(5)} />
          </View>
        </View>

        {equity.length >= 2 ? <EquityCurve points={equity} width={chartWidth} /> : null}

        {calibration ? (
          <CalibrationChart
            calibration={calibration}
            flush
            title="Calibration — when we say X, does it happen?"
          />
        ) : null}

        {/* Link to the opening-signal vs live experiment */}
        <Pressable
          onPress={() => navigation.navigate('OpeningComparison')}
          style={({ pressed }) => [styles.expLink, pressed && { opacity: 0.6 }]}
        >
          <Ionicons name="flask-outline" size={16} color={colors.tint} />
          <Text style={styles.expLinkText}>
            Experiment: lock our first signal vs chase the live line
          </Text>
          <Ionicons name="chevron-forward" size={15} color={colors.tint} />
        </Pressable>

        {/* Honest framing — this is paper trading, not all green. */}
        <View style={styles.noteCard}>
          <Text style={styles.noteTitle}>Read this first</Text>
          <Text style={styles.noteBody}>
            This is real, unedited paper-trading performance — flat $100 bets at the DraftKings
            price we scored, every settled pick since {PAPER_START}. Some models are profitable,
            some aren’t yet, and we show them all. A model isn’t cleared for real money until it
            clears 50+ picks with positive ROI and calibration error under 5%.
          </Text>
        </View>

        {/* CLV explainer — the skill metric, translated. */}
        <View style={styles.noteCard}>
          <Text style={styles.noteTitle}>What “beat the close” means</Text>
          <Text style={styles.noteBody}>
            Closing Line Value (CLV) checks whether the price moved in our favor between when we
            posted a pick and when the line closed. Beating the close consistently is the strongest
            evidence a model has a real edge — independent of short-run wins and losses.
            {overall.clvSettled < 30
              ? ' We’ve only just started capturing it, so this number is still building.'
              : ''}
          </Text>
        </View>

        {/* Per-sport breakdown */}
        {groups.map((g) => (
          <View key={g.sport} style={styles.sportCard}>
            <View style={styles.sportHeader}>
              <Text style={styles.sportName}>{g.sport}</Text>
              <Text style={[styles.sportRoi, { color: roiColor(g.summary.roiFlat) }]}>
                {formatPctSigned(g.summary.roiFlat)}
              </Text>
            </View>
            <Text style={styles.sportSub}>
              {g.summary.wins}–{g.summary.losses}
              {g.summary.pushes > 0 ? `–${g.summary.pushes}` : ''} · {g.summary.picks} picks
            </Text>
            {g.models.map((m) => (
              <ModelRow key={m.model_id} row={m} />
            ))}
          </View>
        ))}

        {!loading && rows.length > 0 && groups.length === 0 ? (
          <Text style={styles.empty}>No settled picks meet the current criteria yet.</Text>
        ) : null}

        <Text style={styles.footer}>
          Records reflect our current published criteria applied to every settled pick, updated
          after each morning settlement. Models we’ve paused for poor performance (e.g. Batter
          Home Runs) are excluded — we stopped offering them, so they’re no longer in the picks
          you’d get today.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

function HeroStat({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.heroStat}>
      <Text style={styles.heroStatValue}>{value}</Text>
      <Text style={styles.heroStatLabel}>{label}</Text>
    </View>
  );
}

function ModelRow({ row }: { row: TrackRecordRow }) {
  const decided = Number(row.wins ?? 0) + Number(row.losses ?? 0);
  const roi = Number(row.staked_flat ?? 0) > 0 ? Number(row.profit_flat) / Number(row.staked_flat) : 0;
  return (
    <View style={styles.modelRow}>
      <View style={{ flex: 1 }}>
        <Text style={styles.modelName} numberOfLines={1}>
          {modelLong(row.model_id)}
        </Text>
        <Text style={styles.modelSub}>
          {row.wins}–{row.losses}
          {row.pushes > 0 ? `–${row.pushes}` : ''} · {decided} decided
        </Text>
      </View>
      <Text style={[styles.modelRoi, { color: roiColor(roi) }]}>{formatPctSigned(roi)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  list: { paddingHorizontal: spacing.lg, paddingTop: spacing.md, paddingBottom: spacing.xl },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  rightActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  title: {
    fontSize: font.size.largeTitle,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  shareBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radii.pill,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.tint,
  },
  shareBtnText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  subtitle: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 4,
    marginBottom: spacing.md,
    lineHeight: 18,
  },
  error: {
    fontSize: font.size.footnote,
    color: colors.avoid,
    marginBottom: spacing.md,
  },
  loading: { marginVertical: spacing.lg },
  heroCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
    alignItems: 'center',
  },
  heroLabel: { fontSize: font.size.footnote, color: colors.textTertiary },
  heroRoi: { fontSize: font.size.largeTitle, fontWeight: font.weight.bold, marginVertical: 2 },
  heroRecord: { fontSize: font.size.callout, color: colors.textSecondary, marginBottom: spacing.md },
  heroStatsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignSelf: 'stretch',
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
    paddingTop: spacing.md,
  },
  heroStat: { alignItems: 'center' },
  heroStatValue: {
    fontSize: font.size.title3,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  heroStatLabel: { fontSize: font.size.caption, color: colors.textTertiary, marginTop: 2 },
  expLink: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    paddingVertical: spacing.sm + 2,
    paddingHorizontal: spacing.md,
    marginBottom: spacing.md,
  },
  expLinkText: { flex: 1, fontSize: font.size.footnote, color: colors.tint, fontWeight: font.weight.medium },
  noteCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  noteTitle: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  noteBody: { fontSize: font.size.footnote, color: colors.textSecondary, lineHeight: 19 },
  sportTabs: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
    marginBottom: spacing.md,
  },
  sportTab: {
    paddingVertical: spacing.xs + 1,
    paddingHorizontal: spacing.md,
    borderRadius: radii.sm,
    backgroundColor: colors.noneSoft,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  sportTabActive: { backgroundColor: colors.bgCard, borderColor: colors.tint },
  sportTabText: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
  },
  sportTabTextActive: { color: colors.tint, fontWeight: font.weight.semibold },
  sportCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  sportHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  sportName: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  sportRoi: { fontSize: font.size.headline, fontWeight: font.weight.bold },
  sportSub: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
    marginBottom: spacing.sm,
  },
  modelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  modelName: { fontSize: font.size.body, color: colors.textPrimary, fontWeight: font.weight.medium },
  modelSub: { fontSize: font.size.caption, color: colors.textTertiary, marginTop: 2 },
  modelRoi: { fontSize: font.size.callout, fontWeight: font.weight.semibold, marginLeft: spacing.md },
  empty: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    textAlign: 'center',
    marginVertical: spacing.lg,
  },
  footer: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    textAlign: 'center',
    marginTop: spacing.sm,
    lineHeight: 16,
  },
});
