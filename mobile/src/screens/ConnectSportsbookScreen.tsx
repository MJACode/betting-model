import React, { useState } from 'react';
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import {
  SPORTSBOOK_PROVIDERS,
  useSportsbookConnection,
  type ProviderMeta,
  type SportsbookProvider,
} from '@/hooks/useSportsbookConnection';
import { useSportsbookSync } from '@/hooks/useSportsbookSync';
import type { LinkedAccount } from '@/lib/sharpsports';
import { colors, font, radii, spacing } from '@/lib/theme';
import { errorText } from '@/lib/errors';

/** Books we don't yet support connecting — shown as "Coming soon". */
const COMING_SOON: { abbrev: string; name: string }[] = [
  { abbrev: 'MGM', name: 'BetMGM' },
  { abbrev: 'C', name: 'Caesars' },
];

export function ConnectSportsbookScreen() {
  // Local intent flag — keeps Settings/Performance "connected" badges working.
  const { connect, disconnect } = useSportsbookConnection();
  // Real linked status + Booklink flow via SharpSports.
  const { accounts, link } = useSportsbookSync();
  const [pending, setPending] = useState<SportsbookProvider | null>(null);

  const accountFor = (id: SportsbookProvider): LinkedAccount | undefined =>
    accounts.find((a) => a.book_abbr === id);

  const onConnect = async (book: ProviderMeta) => {
    setPending(book.id);
    try {
      const result = await link();
      const acc = result?.accounts.find((a) => a.book_abbr === book.id);
      if (acc && acc.status !== 'unverified') {
        connect(book.id); // mirror into the local intent flag
        Alert.alert(
          `${book.name} linked`,
          'Your bet history is syncing now and will appear on the Performance tab.',
        );
      } else if (acc) {
        Alert.alert(
          `${book.name} needs another step`,
          'The link was started but not yet verified. Open the Performance tab and tap refresh, or try linking again.',
        );
      }
      // If no account came back, the user likely cancelled the Booklink flow —
      // stay silent rather than claiming a connection.
    } catch (e) {
      Alert.alert('Could not start linking', errorText(e));
    } finally {
      setPending(null);
    }
  };

  const onDisconnect = (book: ProviderMeta) => {
    Alert.alert(
      `Disconnect ${book.name}?`,
      `Performance will stop showing ${book.name} as connected. Your synced bet history stays until you re-link.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Disconnect',
          style: 'destructive',
          onPress: () => disconnect(book.id),
        },
      ],
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.list}>
        <View style={styles.betaBanner}>
          <Ionicons name="flask-outline" size={14} color={colors.tint} />
          <Text style={styles.betaText}>
            Coming soon — automatic, read-only bet sync isn’t switched on yet.
          </Text>
        </View>

        {SPORTSBOOK_PROVIDERS.map((book) => {
          const acc = accountFor(book.id);
          const linked = acc != null;
          const unverified = acc?.status === 'unverified';
          const isPending = pending === book.id;
          return (
            <View key={book.id} style={styles.bookCard}>
              <View style={styles.bookHeader}>
                <View style={[styles.bookLogo, { backgroundColor: book.logoBg }]}>
                  <Text style={[styles.bookLogoText, { color: book.logoFg }]}>
                    {book.abbrev}
                  </Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.bookName}>{book.name}</Text>
                  <Text style={styles.bookSub}>
                    {!linked
                      ? 'Sportsbook'
                      : unverified
                        ? 'Link needs to be refreshed'
                        : `Linked${acc?.book_region ? ` · ${acc.book_region}` : ''}`}
                  </Text>
                </View>
                {linked ? (
                  <View style={unverified ? styles.statusPillWarn : styles.statusPillConnected}>
                    <View style={unverified ? styles.statusDotWarn : styles.statusDot} />
                    <Text style={unverified ? styles.statusPillWarnText : styles.statusPillText}>
                      {unverified ? 'Reconnect' : 'Connected'}
                    </Text>
                  </View>
                ) : null}
              </View>

              {linked && !unverified ? (
                <Pressable
                  onPress={() => onDisconnect(book)}
                  style={({ pressed }) => [styles.btnSecondary, pressed && styles.btnPressed]}
                >
                  <Text style={styles.btnSecondaryText}>Disconnect</Text>
                </Pressable>
              ) : (
                <Pressable
                  onPress={() => onConnect(book)}
                  disabled={isPending}
                  style={({ pressed }) => [
                    styles.btnPrimary,
                    pressed && styles.btnPressed,
                    isPending && styles.btnDisabled,
                  ]}
                >
                  {isPending ? (
                    <ActivityIndicator color={colors.textInverse} />
                  ) : (
                    <Text style={styles.btnPrimaryText}>
                      {unverified ? `Reconnect ${book.name}` : `Connect ${book.name}`}
                    </Text>
                  )}
                </Pressable>
              )}
            </View>
          );
        })}

        <View style={styles.card}>
          <Text style={styles.cardTitle}>What connecting does</Text>
          <Bullet>
            Securely links your sportsbook through SharpSports so your bet history syncs
            automatically — read-only. We can never place or change bets.
          </Bullet>
          <Bullet>
            The Performance tab shows your real wagers, settlements, and P&L pulled from each
            linked book — no more marking picks by hand.
          </Bullet>
          <Bullet>
            Connect as many books as you bet on. You can disconnect any time, and your bankroll
            and Kelly settings stay as you configured them.
          </Bullet>
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>More sportsbooks</Text>
          {COMING_SOON.map((book) => (
            <View key={book.abbrev} style={styles.comingRow}>
              <View style={[styles.bookLogo, styles.bookLogoMuted]}>
                <Text style={styles.bookLogoTextMuted}>{book.abbrev}</Text>
              </View>
              <Text style={styles.comingLabel}>{book.name}</Text>
              <Text style={styles.comingTag}>Coming soon</Text>
            </View>
          ))}
        </View>

        <Text style={styles.footnote}>
          We never see or store your sportsbook password. You log in through SharpSports' secure
          hosted flow, and the app only ever receives read-only bet history.
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
  statusPillWarn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#FFF4E5',
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radii.pill,
  },
  statusDotWarn: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.med,
  },
  statusPillWarnText: {
    fontSize: font.size.caption,
    color: colors.med,
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
