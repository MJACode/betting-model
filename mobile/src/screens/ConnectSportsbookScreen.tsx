import React, { useState } from 'react';
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useSportsbookConnection } from '@/hooks/useSportsbookConnection';
import { colors, font, radii, spacing } from '@/lib/theme';

export function ConnectSportsbookScreen() {
  const { connection, connected, connect, disconnect } = useSportsbookConnection();
  const [pending, setPending] = useState(false);

  const onConnect = () => {
    setPending(true);
    setTimeout(() => {
      connect('draftkings');
      setPending(false);
      Alert.alert(
        'DraftKings connected',
        'Bet history sync is still being built. Once it ships, your wagers will appear on the Performance tab automatically — no further action needed.',
      );
    }, 600);
  };

  const onDisconnect = () => {
    Alert.alert(
      'Disconnect DraftKings?',
      'Performance will fall back to an empty state until you connect a sportsbook again.',
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Disconnect', style: 'destructive', onPress: disconnect },
      ],
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.list}>
        <View style={styles.betaBanner}>
          <Ionicons name="flask-outline" size={14} color={colors.tint} />
          <Text style={styles.betaText}>Beta — bet history sync ships soon</Text>
        </View>

        <View style={styles.bookCard}>
          <View style={styles.bookHeader}>
            <View style={styles.bookLogo}>
              <Text style={styles.bookLogoText}>DK</Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.bookName}>DraftKings</Text>
              <Text style={styles.bookSub}>
                {connected
                  ? `Connected ${formatConnectedAt(connection?.connectedAt)}`
                  : 'Sportsbook'}
              </Text>
            </View>
            {connected ? (
              <View style={styles.statusPillConnected}>
                <View style={styles.statusDot} />
                <Text style={styles.statusPillText}>Connected</Text>
              </View>
            ) : null}
          </View>

          {connected ? (
            <Pressable
              onPress={onDisconnect}
              style={({ pressed }) => [
                styles.btnSecondary,
                pressed && styles.btnPressed,
              ]}
            >
              <Text style={styles.btnSecondaryText}>Disconnect</Text>
            </Pressable>
          ) : (
            <Pressable
              onPress={onConnect}
              disabled={pending}
              style={({ pressed }) => [
                styles.btnPrimary,
                pressed && styles.btnPressed,
                pending && styles.btnDisabled,
              ]}
            >
              {pending ? (
                <ActivityIndicator color={colors.textInverse} />
              ) : (
                <Text style={styles.btnPrimaryText}>Connect DraftKings</Text>
              )}
            </Pressable>
          )}
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>What connecting does</Text>
          <Bullet>
            Reserves your account so bet history backfills automatically the day sync goes live.
          </Bullet>
          <Bullet>
            Performance tab will pull wagers, settlements, and P&L directly from DraftKings — no
            more marking picks by hand.
          </Bullet>
          <Bullet>
            You can disconnect any time. Your bankroll and Kelly settings stay as you configured them.
          </Bullet>
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>Other sportsbooks</Text>
          <View style={styles.comingRow}>
            <View style={[styles.bookLogo, styles.bookLogoMuted]}>
              <Text style={styles.bookLogoTextMuted}>FD</Text>
            </View>
            <Text style={styles.comingLabel}>FanDuel</Text>
            <Text style={styles.comingTag}>Coming soon</Text>
          </View>
          <View style={styles.comingRow}>
            <View style={[styles.bookLogo, styles.bookLogoMuted]}>
              <Text style={styles.bookLogoTextMuted}>MGM</Text>
            </View>
            <Text style={styles.comingLabel}>BetMGM</Text>
            <Text style={styles.comingTag}>Coming soon</Text>
          </View>
          <View style={styles.comingRow}>
            <View style={[styles.bookLogo, styles.bookLogoMuted]}>
              <Text style={styles.bookLogoTextMuted}>C</Text>
            </View>
            <Text style={styles.comingLabel}>Caesars</Text>
            <Text style={styles.comingTag}>Coming soon</Text>
          </View>
        </View>

        <Text style={styles.footnote}>
          We never store your DraftKings password. Connecting in this beta only records intent —
          actual account linking happens through a hosted secure flow when sync ships.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

function Bullet({ children }: { children: React.ReactNode }) {
  return (
    <View style={styles.bulletRow}>
      <Text style={styles.bulletDot}>•</Text>
      <Text style={styles.bulletText}>{children}</Text>
    </View>
  );
}

function formatConnectedAt(iso: string | undefined): string {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
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
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.xl,
  },
  betaBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    alignSelf: 'flex-start',
    backgroundColor: colors.noneSoft,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radii.pill,
    marginBottom: spacing.md,
  },
  betaText: {
    fontSize: font.size.caption,
    color: colors.tint,
    fontWeight: font.weight.semibold,
  },
  bookCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  bookHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    marginBottom: spacing.lg,
  },
  bookLogo: {
    width: 48,
    height: 48,
    borderRadius: radii.sm,
    backgroundColor: '#000000',
    alignItems: 'center',
    justifyContent: 'center',
  },
  bookLogoMuted: {
    backgroundColor: colors.noneSoft,
    width: 36,
    height: 36,
  },
  bookLogoText: {
    color: '#53D337',
    fontWeight: font.weight.bold,
    fontSize: font.size.headline,
  },
  bookLogoTextMuted: {
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
    fontSize: font.size.footnote,
  },
  bookName: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  bookSub: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
  },
  statusPillConnected: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.betSoft,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radii.pill,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.bet,
  },
  statusPillText: {
    fontSize: font.size.caption,
    color: colors.bet,
    fontWeight: font.weight.semibold,
  },
  btnPrimary: {
    backgroundColor: colors.tint,
    paddingVertical: spacing.md,
    borderRadius: radii.md,
    alignItems: 'center',
  },
  btnPrimaryText: {
    color: colors.textInverse,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
  },
  btnSecondary: {
    backgroundColor: colors.bg,
    paddingVertical: spacing.md,
    borderRadius: radii.md,
    alignItems: 'center',
  },
  btnSecondaryText: {
    color: colors.avoid,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
  },
  btnPressed: {
    opacity: 0.7,
  },
  btnDisabled: {
    opacity: 0.5,
  },
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  cardTitle: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  bulletRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  bulletDot: {
    color: colors.tint,
    fontSize: font.size.body,
    lineHeight: 20,
  },
  bulletText: {
    flex: 1,
    color: colors.textSecondary,
    fontSize: font.size.footnote,
    lineHeight: 19,
  },
  comingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.sm,
  },
  comingLabel: {
    flex: 1,
    fontSize: font.size.body,
    color: colors.textPrimary,
    fontWeight: font.weight.medium,
  },
  comingTag: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    fontWeight: font.weight.medium,
  },
  footnote: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    lineHeight: 17,
    paddingHorizontal: spacing.sm,
    marginTop: spacing.sm,
  },
});
