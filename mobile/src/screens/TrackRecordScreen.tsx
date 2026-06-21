import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Dimensions,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';
import type { RootStackParamList } from '@/types';
import {
  fetchParlayTrackRecord,
  fetchPublicTrackRecord,
  fetchTrackRecordDaily,
} from '@/lib/queries';
import { modelLong } from '@/lib/modelMeta';
import { EquityCurve, type EquityPoint } from '@/components/EquityCurve';
import {
  EMPTY_SUMMARY,
  groupBySport,
  summarize,
  summarizeParlays,
  type ParlaySummary,
  type SportGroup,
  type TrackRecordSummary,
} from '@/lib/trackRecord';
import { formatAmerican, formatPct, formatPctSigned } from '@/lib/format';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { ParlayTrackRow, TrackRecordDailyRow, TrackRecordRow } from '@/types';

const PAPER_START = '2026-04-14';

function roiColor(roi: number): string {
  if (roi > 0.001) return colors.positive;
  if (roi < -0.001) return colors.negative;
  return colors.textSecondary;
}

export function TrackRecordScreen() {
  const navigation =
    useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const [rows, setRows] = useState<TrackRecordRow[]>([]);
  const [daily, setDaily] = useState<TrackRecordDailyRow[]>([]);
  const [parlays, setParlays] = useState<ParlayTrackRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [recRows, dailyRows, parlayRows] = await Promise.all([
        fetchPublicTrackRecord(),
        // Daily series is enrichment for the chart — don't fail the page on it.
        fetchTrackRecordDaily().catch(() => [] as TrackRecordDailyRow[]),
        // Parlay record is a separate section — don't fail the page on it.
        fetchParlayTrackRecord().catch(() => [] as ParlayTrackRow[]),
      ]);
      setRows(recRows);
      setDaily(dailyRows);
      setParlays(parlayRows);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const overall: TrackRecordSummary = useMemo(
    () => (rows.length ? summarize(rows) : EMPTY_SUMMARY),
    [rows],
  );
  const groups: SportGroup[] = useMemo(() => groupBySport(rows), [rows]);

  // Cumulative flat-bet units over time (sum profit_flat across sports per day).
  const equity: EquityPoint[] = useMemo(() => {
    const byDate = new Map<string, number>();
    for (const d of daily) {
      byDate.set(d.game_date, (byDate.get(d.game_date) ?? 0) + Number(d.profit_flat ?? 0));
    }
    const dates = [...byDate.keys()].sort();
    let cum = 0;
    return dates.map((date) => {
      cum += byDate.get(date) ?? 0;
      return { date, cumUnits: cum / 100 };
    });
  }, [daily]);

  // Parlay record: settled parlays only for the headline + equity.
  const settledParlays = useMemo(() => parlays.filter((p) => p.result != null), [parlays]);
  const parlaySummary: ParlaySummary = useMemo(
    () => summarizeParlays(settledParlays),
    [settledParlays],
  );
  const parlayEquity: EquityPoint[] = useMemo(() => {
    const byDate = new Map<string, number>();
    for (const p of settledParlays) {
      if (p.result === 'WIN' || p.result === 'LOSS') {
        byDate.set(p.game_date, (byDate.get(p.game_date) ?? 0) + Number(p.profit_flat ?? 0));
      }
    }
    const dates = [...byDate.keys()].sort();
    let cum = 0;
    return dates.map((date) => {
      cum += byDate.get(date) ?? 0;
      return { date, cumUnits: cum }; // profit_flat already in units
    });
  }, [settledParlays]);

  const chartWidth = Dimensions.get('window').width - spacing.lg * 2 - spacing.lg * 2;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={() => void load()} />}
      >
        <Text style={styles.title}>Track Record</Text>
        <Text style={styles.subtitle}>
          Every pick the model flagged as a BET that meets our current criteria — wins, losses
          and pushes. Nothing hidden, nothing cherry-picked.
        </Text>

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

        {/* Parlay record — the daily canonical cross-game parlay, published. */}
        <ParlayRecordCard
          summary={parlaySummary}
          equity={parlayEquity}
          recent={parlays}
          chartWidth={chartWidth}
        />

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

function fmtUnits(n: number): string {
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}u`;
}

function parseLegLabels(json: string): string[] {
  try {
    const v = JSON.parse(json);
    return Array.isArray(v) ? v.map(String) : [];
  } catch {
    return [];
  }
}

function ParlayRecordCard({
  summary,
  equity,
  recent,
  chartWidth,
}: {
  summary: ParlaySummary;
  equity: EquityPoint[];
  recent: ParlayTrackRow[];
  chartWidth: number;
}) {
  const settled = recent.filter((p) => p.result != null).slice(0, 6);
  return (
    <View style={styles.sportCard}>
      <View style={styles.sportHeader}>
        <Text style={styles.sportName}>Parlay record</Text>
        {summary.parlays > 0 ? (
          <Text style={[styles.sportRoi, { color: roiColor(summary.roiFlat) }]}>
            {formatPctSigned(summary.roiFlat)}
          </Text>
        ) : null}
      </View>
      <Text style={styles.sportSub}>
        One cross-game parlay a day, 1-unit flat — every result published.
      </Text>

      {summary.parlays === 0 ? (
        <Text style={styles.parlayBuilding}>
          Building as the daily parlays settle. Check back after a few slates.
        </Text>
      ) : (
        <>
          <Text style={styles.parlayRecord}>
            {summary.wins}–{summary.losses}
            {summary.pushes > 0 ? `–${summary.pushes}` : ''} · {summary.parlays} settled ·{' '}
            {fmtUnits(summary.profitFlat)}
          </Text>
          {equity.length >= 2 ? <EquityCurve points={equity} width={chartWidth} /> : null}
          {settled.map((p) => {
            const legs = parseLegLabels(p.leg_labels);
            const won = p.result === 'WIN';
            const push = p.result === 'PUSH';
            return (
              <View key={p.parlay_key} style={styles.parlayRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.parlayRowTitle}>
                    {p.sport} · {p.n_legs} legs · {formatAmerican(p.combined_american)}
                  </Text>
                  <Text style={styles.parlayRowLegs} numberOfLines={2}>
                    {legs.join('  +  ')}
                  </Text>
                </View>
                <Text
                  style={[
                    styles.parlayRowResult,
                    { color: push ? colors.textSecondary : won ? colors.positive : colors.negative },
                  ]}
                >
                  {p.result}
                  {p.profit_flat != null ? `\n${fmtUnits(Number(p.profit_flat))}` : ''}
                </Text>
              </View>
            );
          })}
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  list: { paddingHorizontal: spacing.lg, paddingTop: spacing.md, paddingBottom: spacing.xl },
  title: {
    fontSize: font.size.largeTitle,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
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
  parlayBuilding: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
    marginTop: spacing.xs,
  },
  parlayRecord: {
    fontSize: font.size.callout,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  parlayRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  parlayRowTitle: {
    fontSize: font.size.footnote,
    color: colors.textPrimary,
    fontWeight: font.weight.medium,
  },
  parlayRowLegs: { fontSize: font.size.caption, color: colors.textTertiary, marginTop: 2 },
  parlayRowResult: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    marginLeft: spacing.md,
    textAlign: 'right',
  },
  footer: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    textAlign: 'center',
    marginTop: spacing.sm,
    lineHeight: 16,
  },
});
