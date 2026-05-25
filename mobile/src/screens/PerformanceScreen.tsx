import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation } from '@react-navigation/native';
import { useBankroll } from '@/hooks/useBankroll';
import { useSportsbookConnection } from '@/hooks/useSportsbookConnection';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

export function PerformanceScreen() {
  const navigation = useNavigation<Nav>();
  const { bankroll } = useBankroll();
  const { connection, connected: bookConnected } = useSportsbookConnection();

  if (!bookConnected) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <ScrollView contentContainerStyle={styles.list}>
          <View style={styles.header}>
            <Text style={styles.title}>Performance</Text>
            <Text style={styles.subtitle}>P&L synced from your sportsbook</Text>
          </View>
          <View style={styles.card}>
            <View style={styles.iconWrap}>
              <Ionicons name="link-outline" size={28} color={colors.tint} />
            </View>
            <Text style={styles.cardTitle}>Connect DraftKings to see your P&L</Text>
            <Text style={styles.cardBody}>
              The Performance calendar now tracks real wagers from your sportsbook — not picks
              you mark by hand. Connect DraftKings to get started.
            </Text>
            <Pressable
              onPress={() => navigation.navigate('ConnectSportsbook')}
              style={({ pressed }) => [styles.primaryBtn, pressed && styles.btnPressed]}
            >
              <Text style={styles.primaryBtnText}>Connect DraftKings</Text>
            </Pressable>
            <Text style={styles.footnote}>Beta — bet history sync ships soon</Text>
          </View>
        </ScrollView>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={styles.list}>
        <View style={styles.header}>
          <Text style={styles.title}>Performance</Text>
          <Text style={styles.subtitle}>
            DraftKings connected · Bankroll ${bankroll.toFixed(0)}
          </Text>
        </View>
        <View style={styles.card}>
          <View style={styles.statusRow}>
            <View style={styles.dot} />
            <Text style={styles.statusText}>
              DraftKings connected
              {connection?.connectedAt ? ` ${formatConnectedShort(connection.connectedAt)}` : ''}
            </Text>
          </View>
          <Text style={styles.cardTitle}>Bet history sync is in beta</Text>
          <Text style={styles.cardBody}>
            Your DK wagers, settlements, and daily P&L will land here automatically once sync
            ships. You don't need to do anything else — we'll backfill from your connect date.
          </Text>
          <Pressable
            onPress={() => navigation.navigate('ConnectSportsbook')}
            style={({ pressed }) => [styles.secondaryBtn, pressed && styles.btnPressed]}
          >
            <Text style={styles.secondaryBtnText}>Manage connection</Text>
          </Pressable>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function formatConnectedShort(iso: string): string {
  try {
    const d = new Date(iso);
    return `· ${d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`;
  } catch {
    return '';
  }
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  list: {
    paddingBottom: spacing.xl,
  },
  header: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.md,
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
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginHorizontal: spacing.lg,
    alignItems: 'center',
  },
  iconWrap: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.bg,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
    marginTop: spacing.sm,
  },
  cardTitle: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    textAlign: 'center',
    marginBottom: spacing.sm,
  },
  cardBody: {
    fontSize: font.size.body,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: spacing.lg,
  },
  primaryBtn: {
    backgroundColor: colors.tint,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
    borderRadius: radii.md,
    alignSelf: 'stretch',
    alignItems: 'center',
  },
  primaryBtnText: {
    color: colors.textInverse,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
  },
  secondaryBtn: {
    backgroundColor: colors.bg,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
    borderRadius: radii.md,
    alignSelf: 'stretch',
    alignItems: 'center',
  },
  secondaryBtnText: {
    color: colors.tint,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
  },
  btnPressed: {
    opacity: 0.7,
  },
  footnote: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginTop: spacing.md,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.betSoft,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radii.pill,
    marginBottom: spacing.md,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.bet,
  },
  statusText: {
    fontSize: font.size.caption,
    color: colors.bet,
    fontWeight: font.weight.semibold,
  },
});
