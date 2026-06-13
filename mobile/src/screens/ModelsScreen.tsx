import React, { useMemo, useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation } from '@react-navigation/native';
import { EmptyState } from '@/components/EmptyState';
import { SportToggle } from '@/components/SportToggle';
import { useSportFilter } from '@/hooks/useSportFilter';
import { useCustomModels } from '@/hooks/useCustomModels';
import {
  computeBuiltInModelStats,
  computeCustomModelStats,
  useSettledPicksSincePaperStart,
} from '@/hooks/useCustomModelStats';
import { formatCurrencySigned, formatPct, formatPctSigned } from '@/lib/format';
import { MODEL_META, modelLong, modelShort } from '@/lib/modelMeta';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { CustomModel, Pick, RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;
type Tab = 'builtin' | 'custom';

const BUILTIN_MODEL_IDS = Object.keys(MODEL_META);

/** Sport a model belongs to, derived from its id prefix. */
function sportOf(modelId: string): 'MLB' | 'WNBA' | 'UFC' | 'GOLF' {
  if (modelId.startsWith('ufc')) return 'UFC';
  if (modelId.startsWith('golf')) return 'GOLF';
  return modelId.startsWith('wnba') ? 'WNBA' : 'MLB';
}

export function ModelsScreen() {
  const navigation = useNavigation<Nav>();
  const [tab, setTab] = useState<Tab>('builtin');
  const { sport } = useSportFilter();
  const { models, ready } = useCustomModels();
  const { rows, loading, error } = useSettledPicksSincePaperStart();

  // Custom models show under a sport if any of their rules target that sport.
  const customWithStats = useMemo(
    () =>
      models
        .filter((m) => m.rules.some((r) => sportOf(r.model_id) === sport))
        .map((m) => ({ model: m, stats: computeCustomModelStats(m, rows) })),
    [models, rows, sport],
  );

  const builtInWithStats = useMemo(
    () =>
      BUILTIN_MODEL_IDS.filter((modelId) => sportOf(modelId) === sport).map((modelId) => ({
        modelId,
        stats: computeBuiltInModelStats(modelId, rows),
      })),
    [rows, sport],
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <View style={styles.titleRow}>
          <Text style={styles.title}>Models</Text>
          {tab === 'custom' ? (
            <Pressable
              onPress={() => navigation.navigate('ModelEdit', {})}
              style={({ pressed }) => [styles.addBtn, pressed && styles.pressed]}
              hitSlop={6}
            >
              <Ionicons name="add" size={22} color={colors.textInverse} />
            </Pressable>
          ) : null}
        </View>
        <Text style={styles.subtitle}>
          {tab === 'builtin'
            ? 'How each model’s current prob/edge cut has performed since 2026-04-14. Tap one to see today’s picks.'
            : 'Save your own pick filters and see how they would have performed since 2026-04-14.'}
        </Text>

        <View style={styles.sportToggleWrap}>
          <SportToggle />
        </View>

        <View style={styles.segmentRow}>
          <SegmentPill label="Built-in" active={tab === 'builtin'} onPress={() => setTab('builtin')} />
          <SegmentPill label="Custom" active={tab === 'custom'} onPress={() => setTab('custom')} />
        </View>
      </View>

      {error ? (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>Connection error: {error}</Text>
        </View>
      ) : null}

      {tab === 'builtin' ? (
        <FlatList
          data={builtInWithStats}
          keyExtractor={(item) => item.modelId}
          renderItem={({ item }) => (
            <BuiltInModelRow
              modelId={item.modelId}
              stats={item.stats}
              onPress={() =>
                navigation.navigate('BuiltInModelDetail', { modelId: item.modelId })
              }
            />
          )}
          ListEmptyComponent={
            loading ? <ActivityIndicator style={styles.loading} /> : null
          }
          contentContainerStyle={styles.list}
        />
      ) : (
        <FlatList
          data={customWithStats}
          keyExtractor={(item) => item.model.id}
          renderItem={({ item }) => (
            <CustomModelRow
              model={item.model}
              picks={item.stats.picks}
              winRate={item.stats.winRate}
              wins={item.stats.wins}
              losses={item.stats.losses}
              roiFlat={item.stats.roiFlat}
              profitFlat={item.stats.profitFlat}
              onPress={() => navigation.navigate('ModelDetail', { modelId: item.model.id })}
              onEdit={() => navigation.navigate('ModelEdit', { modelId: item.model.id })}
            />
          )}
          ListEmptyComponent={
            !ready || loading ? (
              <ActivityIndicator style={styles.loading} />
            ) : (
              <EmptyState
                title="No custom models yet"
                subtitle="Tap + above to build a filter: which model_ids count, plus your own probability and edge minimums. We'll backtest it against every settled pick."
              />
            )
          }
          contentContainerStyle={styles.list}
        />
      )}
    </SafeAreaView>
  );
}

function SegmentPill({
  label,
  active,
  onPress,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={[styles.segmentPill, active && styles.segmentPillActive]}
    >
      <Text style={[styles.segmentPillText, active && styles.segmentPillTextActive]}>
        {label}
      </Text>
    </Pressable>
  );
}

interface BuiltInRowProps {
  modelId: string;
  stats: ReturnType<typeof computeBuiltInModelStats>;
  onPress: () => void;
}

function BuiltInModelRow({ modelId, stats, onPress }: BuiltInRowProps) {
  const decided = stats.wins + stats.losses;
  const roiColor =
    stats.roiFlat > 0 ? colors.bet : stats.roiFlat < 0 ? colors.avoid : colors.textSecondary;
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.builtInCard, pressed && styles.pressed]}
    >
      <View style={styles.builtInLeft}>
        <View style={styles.modelChip}>
          <Text style={styles.modelChipText}>{modelShort(modelId)}</Text>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.modelName} numberOfLines={1}>
            {modelLong(modelId)}
          </Text>
          <Text style={styles.subtle}>
            {stats.picks} pick{stats.picks === 1 ? '' : 's'}
            {decided > 0 ? ` · ${stats.wins}-${stats.losses}${stats.pushes > 0 ? `-${stats.pushes}` : ''}` : ''}
          </Text>
        </View>
      </View>
      <View style={styles.builtInRight}>
        <Text style={[styles.roi, { color: roiColor }]}>
          {stats.picks > 0 ? formatPctSigned(stats.roiFlat) : '—'}
        </Text>
        <Text style={[styles.profit, { color: roiColor }]}>
          {stats.picks > 0 ? formatCurrencySigned(stats.profitFlat) : '—'}
        </Text>
      </View>
    </Pressable>
  );
}

interface CustomRowProps {
  model: CustomModel;
  picks: number;
  winRate: number;
  wins: number;
  losses: number;
  roiFlat: number;
  profitFlat: number;
  onPress: () => void;
  onEdit: () => void;
}

function CustomModelRow({
  model,
  picks,
  winRate,
  wins,
  losses,
  roiFlat,
  profitFlat,
  onPress,
  onEdit,
}: CustomRowProps) {
  const decided = wins + losses;
  const roiColor = roiFlat > 0 ? colors.bet : roiFlat < 0 ? colors.avoid : colors.textSecondary;
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
    >
      <View style={styles.cardHeader}>
        <View style={{ flex: 1 }}>
          <Text style={styles.modelName}>{model.name}</Text>
          <Text style={styles.ruleCount}>
            {model.rules.length} rule{model.rules.length === 1 ? '' : 's'}
          </Text>
        </View>
        <Pressable onPress={onEdit} hitSlop={8} style={styles.editBtn}>
          <Ionicons name="pencil" size={16} color={colors.tint} />
        </Pressable>
      </View>

      <View style={styles.statsRow}>
        <Stat label="Picks" value={String(picks)} />
        <Stat
          label="Win %"
          value={decided > 0 ? formatPct(winRate) : '—'}
          caption={decided > 0 ? `${wins}-${losses}` : 'no decided'}
        />
        <Stat
          label="Flat ROI"
          value={picks > 0 ? formatPctSigned(roiFlat) : '—'}
          color={roiColor}
        />
        <Stat
          label="P&L"
          value={picks > 0 ? formatCurrencySigned(profitFlat) : '—'}
          color={roiColor}
        />
      </View>
    </Pressable>
  );
}

function Stat({
  label,
  value,
  color,
  caption,
}: {
  label: string;
  value: string;
  color?: string;
  caption?: string;
}) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={[styles.statValue, color ? { color } : null]}>{value}</Text>
      {caption ? <Text style={styles.statCaption}>{caption}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.md,
  },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
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
  sportToggleWrap: {
    marginTop: spacing.md,
  },
  segmentRow: {
    flexDirection: 'row',
    backgroundColor: colors.bgCard,
    borderRadius: radii.pill,
    padding: 3,
    marginTop: spacing.md,
    alignSelf: 'flex-start',
  },
  segmentPill: {
    paddingHorizontal: spacing.lg,
    paddingVertical: 6,
    borderRadius: radii.pill,
  },
  segmentPillActive: {
    backgroundColor: colors.tint,
  },
  segmentPillText: {
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
    fontSize: font.size.footnote,
  },
  segmentPillTextActive: {
    color: colors.textInverse,
    fontWeight: font.weight.semibold,
  },
  addBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.tint,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pressed: { opacity: 0.7 },
  list: {
    paddingTop: spacing.sm,
    paddingBottom: spacing.xl,
  },
  builtInCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    gap: spacing.md,
  },
  builtInLeft: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  builtInRight: {
    alignItems: 'flex-end',
    minWidth: 90,
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
  subtle: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginTop: 1,
  },
  roi: {
    fontSize: font.size.callout,
    fontWeight: font.weight.bold,
  },
  profit: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    marginTop: 2,
  },
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.lg,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  modelName: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  ruleCount: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
  },
  editBtn: {
    padding: 6,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  stat: { flex: 1 },
  statLabel: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginBottom: 2,
  },
  statValue: {
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  statCaption: {
    fontSize: 10,
    color: colors.textTertiary,
    marginTop: 1,
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
});
