import React, { useMemo } from 'react';
import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation } from '@react-navigation/native';
import { EmptyState } from '@/components/EmptyState';
import { useCustomModels } from '@/hooks/useCustomModels';
import {
  computeCustomModelStats,
  useSettledPicksSincePaperStart,
} from '@/hooks/useCustomModelStats';
import { formatCurrencySigned, formatPct, formatPctSigned } from '@/lib/format';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { CustomModel, RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

export function ModelsScreen() {
  const navigation = useNavigation<Nav>();
  const { models, ready } = useCustomModels();
  const { rows, loading, error } = useSettledPicksSincePaperStart();

  const withStats = useMemo(
    () => models.map((m) => ({ model: m, stats: computeCustomModelStats(m, rows) })),
    [models, rows],
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <View style={styles.titleRow}>
          <Text style={styles.title}>Models</Text>
          <Pressable
            onPress={() => navigation.navigate('ModelEdit', {})}
            style={({ pressed }) => [styles.addBtn, pressed && styles.pressed]}
            hitSlop={6}
          >
            <Ionicons name="add" size={22} color={colors.textInverse} />
          </Pressable>
        </View>
        <Text style={styles.subtitle}>
          Save your own pick filters and see how they would have performed since 2026-04-14.
        </Text>
      </View>

      {error ? (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>Connection error: {error}</Text>
        </View>
      ) : null}

      <FlatList
        data={withStats}
        keyExtractor={(item) => item.model.id}
        renderItem={({ item }) => (
          <ModelRow
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
    </SafeAreaView>
  );
}

interface RowProps {
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

function ModelRow({ model, picks, winRate, wins, losses, roiFlat, profitFlat, onPress, onEdit }: RowProps) {
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
