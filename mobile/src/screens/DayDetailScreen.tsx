import React, { useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation, useRoute } from '@react-navigation/native';
import { EmptyState } from '@/components/EmptyState';
import { SignalBadge } from '@/components/SignalBadge';
import { fetchSettledPicks } from '@/lib/queries';
import { formatCurrencySigned } from '@/lib/format';
import { modelShort } from '@/lib/modelMeta';
import { colors, font, radii, spacing } from '@/lib/theme';
import { isPlaced, usePlacedPicks } from '@/hooks/usePlacedPicks';
import type { Pick, RootStackParamList } from '@/types';

type DayRoute = RouteProp<RootStackParamList, 'DayDetail'>;
type Nav = NativeStackNavigationProp<RootStackParamList>;

export function DayDetailScreen() {
  const route = useRoute<DayRoute>();
  const navigation = useNavigation<Nav>();
  const { date } = route.params;
  const { overrides } = usePlacedPicks();

  const [rows, setRows] = useState<Pick[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    fetchSettledPicks(date, date)
      .then((data) => {
        if (mounted) setRows(data);
      })
      .catch((e: unknown) => {
        if (mounted) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [date]);

  const placed = rows.filter((p) => isPlaced(p.pick_id, p.signal_type, overrides));

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.title}>{date}</Text>
        <Text style={styles.subtitle}>
          {placed.length} placed pick{placed.length === 1 ? '' : 's'}
        </Text>
      </View>
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <FlatList
        data={placed}
        keyExtractor={(p) => String(p.pick_id)}
        renderItem={({ item }) => (
          <Pressable
            style={styles.row}
            onPress={() => navigation.navigate('PickDetail', { pickId: item.pick_id })}
          >
            <View style={styles.rowLeft}>
              <View style={styles.modelChip}>
                <Text style={styles.modelChipText}>{modelShort(item.model_id)}</Text>
              </View>
              <View style={styles.rowText}>
                <Text style={styles.label}>{item.pick_label}</Text>
                <View style={styles.metaRow}>
                  <SignalBadge signal={item.signal_type} small />
                  <Text style={styles.result}>{item.result ?? '—'}</Text>
                </View>
              </View>
            </View>
            <View style={styles.rowRight}>
              <Text
                style={[
                  styles.profit,
                  {
                    color:
                      (item.profit_kelly ?? 0) > 0
                        ? colors.bet
                        : (item.profit_kelly ?? 0) < 0
                          ? colors.avoid
                          : colors.textSecondary,
                  },
                ]}
              >
                {formatCurrencySigned(item.profit_kelly)}
              </Text>
              <Text style={styles.profitLabel}>Kelly</Text>
            </View>
          </Pressable>
        )}
        ListEmptyComponent={
          loading ? (
            <ActivityIndicator style={styles.loading} />
          ) : (
            <EmptyState
              title="No placed picks settled on this day"
              subtitle="Either no picks were marked Placed, or settlement hasn't run yet."
            />
          )
        }
        contentContainerStyle={styles.list}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  header: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.md,
  },
  title: {
    fontSize: font.size.title2,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  subtitle: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 4,
  },
  list: {
    paddingBottom: spacing.xl,
  },
  row: {
    flexDirection: 'row',
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    alignItems: 'center',
  },
  rowLeft: {
    flex: 1,
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
  rowText: {
    flex: 1,
  },
  label: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginBottom: 4,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  result: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
  },
  rowRight: {
    alignItems: 'flex-end',
  },
  profit: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
  },
  profitLabel: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
  loading: {
    marginVertical: spacing.xxl,
  },
  error: {
    color: colors.avoid,
    paddingHorizontal: spacing.lg,
  },
});
