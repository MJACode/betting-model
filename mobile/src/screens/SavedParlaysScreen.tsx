import React, { useMemo, useState } from 'react';
import { Alert, FlatList, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { EmptyState } from '@/components/EmptyState';
import { ParlayDkHandoff, type HandoffLeg } from '@/components/ParlayDkHandoff';
import { useSavedParlays } from '@/hooks/useSavedParlays';
import { setParlayRestore } from '@/hooks/useParlayRestore';
import {
  computeParlayMetrics,
  savedLegToParlayLeg,
  type SavedParlay,
} from '@/lib/parlay';
import { modelShort } from '@/lib/modelMeta';
import { formatAmerican, formatPct, formatPctSigned } from '@/lib/format';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList, 'SavedParlays'>;

/** Short relative time — "just now", "3h ago", "2d ago". */
function savedAgo(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const mins = Math.max(0, Math.round((Date.now() - then) / 60000));
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  return `${days}d ago`;
}

export function SavedParlaysScreen() {
  const navigation = useNavigation<Nav>();
  const { items, remove } = useSavedParlays();
  const [handoff, setHandoff] = useState<HandoffLeg[] | null>(null);

  const editInBuilder = (sp: SavedParlay) => {
    const pickIds = sp.legs.filter((l) => l.pickId >= 0).map((l) => l.pickId);
    const customLegs = sp.legs.filter((l) => l.pickId < 0).map(savedLegToParlayLeg);
    setParlayRestore({ pickIds, customLegs });
    navigation.navigate('Tabs', { screen: 'Parlay' });
  };

  const confirmDelete = (sp: SavedParlay) => {
    Alert.alert('Delete parlay?', 'This removes the saved parlay.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: () => remove(sp.id) },
    ]);
  };

  const betOnDk = (sp: SavedParlay) => {
    setHandoff(
      sp.legs.map((l) => ({
        key: String(l.pickId),
        label: l.label,
        matchup: l.matchup,
        americanOdds: l.americanOdds,
        dkBetLink: l.dkBetLink,
      })),
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <FlatList
        data={items}
        keyExtractor={(p) => p.id}
        contentContainerStyle={styles.scroll}
        ListEmptyComponent={
          <EmptyState
            title="No saved parlays"
            subtitle="Build a parlay, then tap “Save parlay” to keep it here for later."
          />
        }
        renderItem={({ item }) => (
          <SavedParlayCard
            parlay={item}
            onBet={() => betOnDk(item)}
            onEdit={() => editInBuilder(item)}
            onDelete={() => confirmDelete(item)}
          />
        )}
      />

      <ParlayDkHandoff
        visible={handoff != null}
        legs={handoff ?? []}
        onClose={() => setHandoff(null)}
      />
    </SafeAreaView>
  );
}

function SavedParlayCard({
  parlay,
  onBet,
  onEdit,
  onDelete,
}: {
  parlay: SavedParlay;
  onBet: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const metrics = useMemo(
    () => computeParlayMetrics(parlay.legs.map(savedLegToParlayLeg)),
    [parlay.legs],
  );
  return (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <Text style={styles.cardTitle}>
          {parlay.legs.length}-Leg · {formatAmerican(metrics.americanOdds)}
        </Text>
        <Text style={styles.cardMeta}>
          {parlay.sport} · {savedAgo(parlay.createdAt)}
        </Text>
      </View>

      <View style={styles.statsRow}>
        <Stat label="Model" value={formatPct(metrics.parlayProb)} />
        <Stat
          label="EV"
          value={formatPctSigned(metrics.ev)}
          color={metrics.ev >= 0 ? colors.bet : colors.avoid}
        />
        <Stat
          label="Edge"
          value={formatPctSigned(metrics.edgeVsDk)}
          color={metrics.edgeVsDk >= 0 ? colors.bet : colors.avoid}
        />
        <Stat label="DK imp." value={formatPct(metrics.dkImpliedProb)} />
      </View>

      <View style={styles.legsList}>
        {parlay.legs.map((leg) => (
          <View key={leg.pickId} style={styles.legRow}>
            <View style={styles.legBody}>
              {leg.matchup ? <Text style={styles.legMatchup}>{leg.matchup}</Text> : null}
              <Text style={styles.legLabel} numberOfLines={2}>
                {leg.label}
              </Text>
            </View>
            <View style={styles.legMeta}>
              <View style={styles.modelChip}>
                <Text style={styles.modelChipText}>{modelShort(leg.modelId)}</Text>
              </View>
              <Text style={styles.legOdds}>{formatAmerican(leg.americanOdds)}</Text>
            </View>
          </View>
        ))}
      </View>

      <View style={styles.actions}>
        <Pressable onPress={onBet} style={({ pressed }) => [styles.betBtn, pressed && styles.pressed]}>
          <Ionicons name="open-outline" size={16} color={colors.textInverse} />
          <Text style={styles.betBtnText}>Bet on DraftKings</Text>
        </Pressable>
        <View style={styles.secondaryRow}>
          <Pressable onPress={onEdit} style={({ pressed }) => [styles.editBtn, pressed && styles.pressed]}>
            <Ionicons name="create-outline" size={16} color={colors.tint} />
            <Text style={styles.editBtnText}>Edit in builder</Text>
          </Pressable>
          <Pressable onPress={onDelete} style={({ pressed }) => [styles.deleteBtn, pressed && styles.pressed]}>
            <Ionicons name="trash-outline" size={16} color={colors.avoid} />
            <Text style={styles.deleteBtnText}>Delete</Text>
          </Pressable>
        </View>
      </View>
    </View>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={[styles.statValue, color ? { color } : null]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  scroll: {
    padding: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  cardTitle: {
    fontSize: font.size.headline,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  cardMeta: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: spacing.md,
    paddingBottom: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  stat: {
    flex: 1,
  },
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
  legsList: {
    marginBottom: spacing.md,
  },
  legRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
  },
  legBody: {
    flex: 1,
  },
  legMatchup: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginBottom: 2,
  },
  legLabel: {
    fontSize: font.size.body,
    fontWeight: font.weight.medium,
    color: colors.textPrimary,
  },
  legMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginLeft: spacing.sm,
  },
  modelChip: {
    backgroundColor: colors.noneSoft,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: radii.pill,
  },
  modelChipText: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontWeight: font.weight.semibold,
  },
  legOdds: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
    minWidth: 44,
    textAlign: 'right',
  },
  actions: {
    gap: spacing.sm,
  },
  betBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    backgroundColor: colors.tint,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
  },
  betBtnText: {
    color: colors.textInverse,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
  },
  secondaryRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  editBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.tint,
    borderRadius: radii.md,
    paddingVertical: spacing.sm,
  },
  editBtnText: {
    color: colors.tint,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
  },
  deleteBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    borderRadius: radii.md,
    paddingVertical: spacing.sm,
  },
  deleteBtnText: {
    color: colors.avoid,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
  },
  pressed: {
    opacity: 0.6,
  },
});
