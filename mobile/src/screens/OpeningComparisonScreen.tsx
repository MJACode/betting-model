import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { fetchOpeningVsLive, fetchOpeningSlices } from '@/lib/queries';
import { InfoTooltip } from '@/components/InfoTooltip';
import { formatPct, formatPctSigned } from '@/lib/format';
import { colors, font, radii, spacing } from '@/lib/theme';
import { errorText } from '@/lib/errors';
import type { OpeningVsLiveRow, OpeningSliceRow } from '@/types';

const PAPER_START = '2026-04-14';

function roiColor(roi: number): string {
  if (roi > 0.001) return colors.positive;
  if (roi < -0.001) return colors.negative;
  return colors.textSecondary;
}

function roiOf(r: { profit_flat: number; staked_flat: number }): number {
  return Number(r.staked_flat) > 0 ? Number(r.profit_flat) / Number(r.staked_flat) : 0;
}

const LINE_LABEL: Record<string, string> = {
  toward: 'Line moved toward us',
  against: 'Line moved against us',
  flat: 'Line barely moved',
  unknown: 'No closing line',
};
const PUBLIC_LABEL: Record<string, string> = {
  with_public: 'We’re with the public',
  contrarian: 'We’re contrarian',
  even: 'Public split evenly',
  no_split: 'No public data',
};
const LINE_ORDER = ['toward', 'against', 'flat', 'unknown'];
const PUBLIC_ORDER = ['contrarian', 'with_public', 'even', 'no_split'];

export function OpeningComparisonScreen() {
  const [tracks, setTracks] = useState<OpeningVsLiveRow[]>([]);
  const [slices, setSlices] = useState<OpeningSliceRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [t, s] = await Promise.all([
        fetchOpeningVsLive(),
        fetchOpeningSlices().catch(() => [] as OpeningSliceRow[]),
      ]);
      setTracks(t);
      setSlices(s);
    } catch (e: unknown) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const opening = useMemo(() => tracks.find((t) => t.track === 'opening'), [tracks]);
  const live = useMemo(() => tracks.find((t) => t.track === 'live'), [tracks]);
  const openingHasData = Number(opening?.picks ?? 0) > 0;

  const lineSlices = useMemo(
    () =>
      LINE_ORDER.map((v) => slices.find((s) => s.slice_kind === 'line_move' && s.slice_value === v))
        .filter((s): s is OpeningSliceRow => !!s && Number(s.picks) > 0),
    [slices],
  );
  const publicSlices = useMemo(
    () =>
      PUBLIC_ORDER.map((v) => slices.find((s) => s.slice_kind === 'public' && s.slice_value === v))
        .filter((s): s is OpeningSliceRow => !!s && Number(s.picks) > 0),
    [slices],
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={() => void load()} />}
      >
        <View style={styles.titleRow}>
          <Text style={styles.title}>Opening vs Live</Text>
          <InfoTooltip
            title="What this compares"
            body={
              'Our picks are re-scored every hour, so a game can move in and out of BET as the ' +
              'line shifts. This experiment locks the FIRST time a game becomes a BET (the ' +
              '“opening signal”) and tracks that record separately from the live pick that keeps ' +
              'updating. It also checks how the line moved after we locked — toward us means the ' +
              'market/public came to our side (a good sign), against means it moved away. ' +
              'Game-level bets only, since the record began.'
            }
          />
        </View>
        <Text style={styles.subtitle}>
          Does locking our first signal beat chasing the hourly line? And does public money moving
          the line predict the result? This is a measurement experiment — not a separate product yet.
        </Text>

        {error ? <Text style={styles.error}>Couldn’t load: {error}</Text> : null}
        {loading && tracks.length === 0 ? <ActivityIndicator style={styles.loading} /> : null}

        {/* The two tracks side by side */}
        <View style={styles.row}>
          <TrackCard label="Opening (locked)" row={opening} building={!openingHasData} />
          <TrackCard label="Live (closing)" row={live} building={false} />
        </View>

        {!openingHasData ? (
          <View style={styles.noteCard}>
            <Text style={styles.noteTitle}>Just getting started</Text>
            <Text style={styles.noteBody}>
              We only began locking opening signals recently, so the locked record is still empty —
              the first results settle within a day, and the comparison gets meaningful after a week
              or two. The live record on the right is shown for reference. We’re showing this raw and
              unfinished on purpose.
            </Text>
          </View>
        ) : null}

        {/* Line movement slices */}
        {lineSlices.length > 0 ? (
          <View style={styles.sliceCard}>
            <Text style={styles.sliceHeader}>By how the line moved after we locked</Text>
            {lineSlices.map((s) => (
              <SliceRow key={s.slice_value} label={LINE_LABEL[s.slice_value] ?? s.slice_value} row={s} />
            ))}
          </View>
        ) : null}

        {/* Public side slices */}
        {publicSlices.length > 0 ? (
          <View style={styles.sliceCard}>
            <Text style={styles.sliceHeader}>By which side the public was on</Text>
            {publicSlices.map((s) => (
              <SliceRow key={s.slice_value} label={PUBLIC_LABEL[s.slice_value] ?? s.slice_value} row={s} />
            ))}
            <Text style={styles.sliceNote}>
              Public splits only exist for full-game moneyline/spread/total markets, so many picks
              show “no public data.”
            </Text>
          </View>
        ) : null}

        <Text style={styles.footer}>
          Flat $100 bets at the price we first locked, every settled game-level pick since{' '}
          {PAPER_START.slice(5)}. This is a shadow experiment — it doesn’t change the picks you see
          or our published track record. No bet rule is built from it yet; we’re measuring first.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

function TrackCard({
  label,
  row,
  building,
}: {
  label: string;
  row?: OpeningVsLiveRow;
  building: boolean;
}) {
  const roi = row ? roiOf(row) : 0;
  const decided = Number(row?.wins ?? 0) + Number(row?.losses ?? 0);
  const winRate = decided > 0 ? Number(row?.wins ?? 0) / decided : 0;
  const clvSettled = Number(row?.clv_settled ?? 0);
  const clvBeat = Number(row?.clv_beat ?? 0);
  return (
    <View style={styles.trackCard}>
      <Text style={styles.trackLabel}>{label}</Text>
      {building ? (
        <Text style={styles.trackBuilding}>Building…</Text>
      ) : (
        <>
          <Text style={[styles.trackRoi, { color: roiColor(roi) }]}>{formatPctSigned(roi)}</Text>
          <Text style={styles.trackRecord}>
            {Number(row?.wins ?? 0)}–{Number(row?.losses ?? 0)}
            {Number(row?.pushes ?? 0) > 0 ? `–${row?.pushes}` : ''}
          </Text>
          <View style={styles.trackStatsRow}>
            <Text style={styles.trackStat}>Win {formatPct(winRate, 0)}</Text>
            <Text style={styles.trackStat}>
              Beat close {clvSettled > 0 ? formatPct(clvBeat / clvSettled, 0) : '—'}
            </Text>
          </View>
        </>
      )}
    </View>
  );
}

function SliceRow({ label, row }: { label: string; row: OpeningSliceRow }) {
  const roi = roiOf(row);
  const decided = Number(row.wins) + Number(row.losses);
  return (
    <View style={styles.sliceRow}>
      <View style={{ flex: 1 }}>
        <Text style={styles.sliceLabel}>{label}</Text>
        <Text style={styles.sliceSub}>
          {row.wins}–{row.losses}
          {Number(row.pushes) > 0 ? `–${row.pushes}` : ''} · {decided} decided
        </Text>
      </View>
      <Text style={[styles.sliceRoi, { color: roiColor(roi) }]}>{formatPctSigned(roi)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  list: { paddingHorizontal: spacing.lg, paddingTop: spacing.md, paddingBottom: spacing.xl },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  title: { fontSize: font.size.largeTitle, fontWeight: font.weight.bold, color: colors.textPrimary },
  subtitle: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 4,
    marginBottom: spacing.md,
    lineHeight: 18,
  },
  error: { fontSize: font.size.footnote, color: colors.avoid, marginBottom: spacing.md },
  loading: { marginVertical: spacing.lg },
  row: { flexDirection: 'row', gap: spacing.md, marginBottom: spacing.md },
  trackCard: {
    flex: 1,
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    alignItems: 'center',
  },
  trackLabel: { fontSize: font.size.footnote, color: colors.textTertiary, marginBottom: 4 },
  trackBuilding: {
    fontSize: font.size.title3,
    color: colors.textTertiary,
    marginVertical: spacing.sm,
  },
  trackRoi: { fontSize: font.size.title1, fontWeight: font.weight.bold },
  trackRecord: { fontSize: font.size.callout, color: colors.textSecondary, marginTop: 2 },
  trackStatsRow: {
    flexDirection: 'row',
    gap: spacing.md,
    marginTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
    paddingTop: spacing.sm,
  },
  trackStat: { fontSize: font.size.caption, color: colors.textTertiary },
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
  sliceCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  sliceHeader: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  sliceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  sliceLabel: { fontSize: font.size.body, color: colors.textPrimary, fontWeight: font.weight.medium },
  sliceSub: { fontSize: font.size.caption, color: colors.textTertiary, marginTop: 2 },
  sliceRoi: { fontSize: font.size.callout, fontWeight: font.weight.semibold, marginLeft: spacing.md },
  sliceNote: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginTop: spacing.sm,
    lineHeight: 15,
  },
  footer: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    textAlign: 'center',
    marginTop: spacing.sm,
    lineHeight: 16,
  },
});
