import React, { useEffect, useState } from 'react';
import {
  Alert,
  Linking,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation } from '@react-navigation/native';
import { usePreferredBook, BOOKS } from '@/hooks/usePreferredBook';
import { bookName } from '@/lib/markets';
import { useBankroll } from '@/hooks/useBankroll';
import {
  MULTIPLIER_MAX,
  MULTIPLIER_MIN,
  MULTIPLIER_STEP,
  useKellySettings,
} from '@/hooks/useKellySettings';
import { providerMeta, useSportsbookConnection } from '@/hooks/useSportsbookConnection';
import { useOnboarding } from '@/hooks/useOnboarding';
import { useResponsibleGambling } from '@/hooks/useResponsibleGambling';
import { usePushOptIn } from '@/hooks/usePushOptIn';
import { useFeedbackUnread } from '@/hooks/useFeedback';
import { useAuth } from '@/hooks/useAuth';
import { AUTH_ENABLED } from '@/lib/authConfig';
import { authErrorMessage } from '@/lib/auth';
import { useSubscription } from '@/hooks/useSubscription';
import { billingReady } from '@/lib/billingConfig';
import { billingErrorMessage, openManageSubscription } from '@/lib/billing';
import { describeSubscription } from '@/lib/billingHelpers';
import {
  APP_VERSION,
  DISCORD_URL,
  TWITTER_URL,
  WEBSITE_URL,
  openLink,
} from '@/lib/socialLinks';
import { formatPct } from '@/lib/format';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

/** Section heading — turns a long flat list of cards into scannable groups. */
function SectionHeader({ title }: { title: string }) {
  return <Text style={styles.sectionHeader}>{title}</Text>;
}

/**
 * A tappable row that opens another screen or an external link.
 * `icon` defaults to a chevron (in-app navigation); pass one for anything else.
 */
function LinkRow({
  label,
  sub,
  onPress,
  icon = 'chevron-forward',
  right,
}: {
  label: string;
  sub: string;
  onPress: () => void;
  icon?: React.ComponentProps<typeof Ionicons>['name'];
  right?: React.ReactNode;
}) {
  return (
    <Pressable
      style={({ pressed }) => [styles.linkCard, pressed && styles.pressed]}
      onPress={onPress}
    >
      <View style={{ flex: 1 }}>
        {right ? (
          <View style={styles.bookRow}>
            <Text style={styles.cardLabel}>{label}</Text>
            {right}
          </View>
        ) : (
          <Text style={styles.cardLabel}>{label}</Text>
        )}
        <Text style={styles.sub}>{sub}</Text>
      </View>
      <Ionicons name={icon} size={18} color={colors.textTertiary} />
    </Pressable>
  );
}

export function SettingsScreen() {
  const navigation = useNavigation<Nav>();
  const { bankroll, setBankroll, ready } = useBankroll();
  const { book, setBook } = usePreferredBook();
  const { multiplier, cap, setMultiplier, setCap } = useKellySettings();
  const { connections, anyConnected: bookConnected } = useSportsbookConnection();
  const { replay: replayIntro } = useOnboarding();
  const { settings: rg, setExposureCapPct } = useResponsibleGambling();
  const { enabled: pushEnabled, setOptIn: setPushOptIn } = usePushOptIn();
  const feedbackUnread = useFeedbackUnread();
  const { signedIn, email: authEmail, user: authUser, signOut } = useAuth();
  const { subscription, entitled } = useSubscription();
  const [draft, setDraft] = useState<string>('');
  const [capDraft, setCapDraft] = useState<string>('');
  const [rgDraft, setRgDraft] = useState<string>('');

  useEffect(() => {
    setRgDraft(rg.exposureCapPct != null ? (rg.exposureCapPct * 100).toFixed(0) : '');
  }, [rg.exposureCapPct]);

  useEffect(() => {
    if (ready) setDraft(String(bankroll));
  }, [bankroll, ready]);

  useEffect(() => {
    setCapDraft(cap != null ? (cap * 100).toFixed(2) : '');
  }, [cap]);

  const onSave = () => {
    const v = parseFloat(draft);
    if (!Number.isFinite(v) || v <= 0) {
      Alert.alert('Invalid bankroll', 'Enter a positive number.');
      return;
    }
    setBankroll(v);
    Alert.alert('Saved', `Bankroll set to $${v.toFixed(2)}.`);
  };

  const stepMultiplier = (delta: number) => {
    const next = Math.round((multiplier + delta) * 100) / 100;
    const clamped = Math.max(MULTIPLIER_MIN, Math.min(MULTIPLIER_MAX, next));
    setMultiplier(clamped);
  };

  const commitCap = (raw: string) => {
    if (raw.trim() === '') return;
    const pct = parseFloat(raw);
    if (!Number.isFinite(pct) || pct <= 0 || pct > 100) {
      Alert.alert('Invalid cap', 'Enter a percent between 0 and 100.');
      setCapDraft(cap != null ? (cap * 100).toFixed(2) : '');
      return;
    }
    setCap(pct / 100);
  };

  const toggleCap = (on: boolean) => {
    if (!on) {
      setCap(null);
    } else {
      // Sensible default when enabling: 5% of bankroll (the old hard cap).
      setCap(0.05);
    }
  };

  const commitRgCap = (raw: string) => {
    if (raw.trim() === '') return;
    const pct = parseFloat(raw);
    if (!Number.isFinite(pct) || pct <= 0 || pct > 100) {
      Alert.alert('Invalid limit', 'Enter a percent between 0 and 100.');
      setRgDraft(rg.exposureCapPct != null ? (rg.exposureCapPct * 100).toFixed(0) : '');
      return;
    }
    setExposureCapPct(pct / 100);
  };

  const toggleRgCap = (on: boolean) => setExposureCapPct(on ? 0.15 : null);

  const openHelpline = () => {
    Linking.openURL('tel:1-800-522-4700').catch(() =>
      Alert.alert('Need help?', 'Call or text 1-800-GAMBLER (1-800-522-4700), available 24/7.'),
    );
  };

  const confirmSignOut = () => {
    Alert.alert('Sign out?', 'Your bankroll, models and tracked bets stay on this device.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Sign out',
        style: 'destructive',
        onPress: () => {
          signOut().catch((e) => Alert.alert('Could not sign out', authErrorMessage(e)));
        },
      },
    ]);
  };

  const multLabel = describeMultiplier(multiplier);
  const websiteLabel = WEBSITE_URL.replace(/^https?:\/\//, '');
  const showAccountSection = AUTH_ENABLED || billingReady();

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.list} keyboardShouldPersistTaps="handled">

        {/* Account + Subscription. Both are behind flags — while auth is dark
            this is the ONLY sign-in entry point in the app, so the whole
            section stays invisible until a flag flips. */}
        {showAccountSection ? <SectionHeader title="Account" /> : null}

        {AUTH_ENABLED ? (
          signedIn ? (
            <View style={styles.card}>
              <View style={styles.bookRow}>
                <Text style={[styles.cardLabel, styles.flexShrink]} numberOfLines={1}>
                  {authEmail ?? 'Signed in'}
                </Text>
                <View style={styles.bookPill}>
                  <View style={styles.bookDot} />
                  <Text style={styles.bookPillText}>Signed in</Text>
                </View>
              </View>
              <Text style={styles.sub}>
                Your bankroll, models and tracked bets stay on this device.
              </Text>
              <Pressable
                onPress={confirmSignOut}
                style={({ pressed }) => [styles.signOutBtn, pressed && styles.pressed]}
              >
                <Text style={styles.signOutText}>Sign out</Text>
              </Pressable>
            </View>
          ) : (
            // Deliberately does NOT promise cross-device sync — auth is
            // session-only today. Update when account-scoped data lands.
            <LinkRow
              label="Sign in"
              sub="Optional. Everything works without an account — your bankroll, models and tracked bets stay on this device."
              onPress={() => navigation.navigate('SignIn')}
              right={<Text style={styles.bookPillMuted}>Not signed in</Text>}
            />
          )
        ) : null}

        {/* Subscription renders only when billing is live AND auth is on —
            billingReady() enforces that pairing, since a subscription with no
            account behind it can't survive a reinstall. */}
        {billingReady() ? (
          <LinkRow
            label="Subscription"
            sub={
              entitled
                ? `${describeSubscription(subscription)} Tap to manage or cancel.`
                : 'Signals are locked. Tap to see plans.'
            }
            onPress={() => {
              if (entitled && subscription) {
                openManageSubscription(authUser?.id ?? null).catch((e) =>
                  Alert.alert('Could not open billing', billingErrorMessage(e)),
                );
              } else {
                navigation.navigate('Paywall');
              }
            }}
            right={
              entitled ? (
                <View style={styles.bookPill}>
                  <View style={styles.bookDot} />
                  <Text style={styles.bookPillText}>Active</Text>
                </View>
              ) : (
                <Text style={styles.bookPillMuted}>Free</Text>
              )
            }
          />
        ) : null}

        <SectionHeader title="Betting" />

        <View style={styles.card}>
          <Text style={styles.cardLabel}>Bankroll</Text>
          <View style={styles.bankrollRow}>
            <Text style={styles.dollar}>$</Text>
            <TextInput
              style={styles.input}
              value={draft}
              onChangeText={setDraft}
              keyboardType="decimal-pad"
              placeholder="1000"
              placeholderTextColor={colors.textTertiary}
            />
            <Pressable onPress={onSave} style={styles.saveBtn}>
              <Text style={styles.saveBtnText}>Save</Text>
            </Pressable>
          </View>
          <Text style={styles.sub}>
            Bet sizes recompute across the app. Stored on this device.
          </Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.cardLabel}>Your sportsbook</Text>
          <Text style={styles.bookHint}>
            Where you actually bet. Picks show this book’s price and line, and the “Bet on…”
            button opens its betslip.
          </Text>
          <View style={styles.bookSelectRow}>
            {BOOKS.map((b) => {
              const active = b === book;
              return (
                <Pressable
                  key={b}
                  onPress={() => setBook(b)}
                  style={[styles.bookChip, active && styles.bookChipActive]}
                >
                  <Text style={[styles.bookChipText, active && styles.bookChipTextActive]}>
                    {bookName(b)}
                  </Text>
                </Pressable>
              );
            })}
          </View>
          <Text style={styles.bookNote}>
            Signals and parlays are always priced against DraftKings — the book the models score
            and our track record is graded against. This only changes the odds you see, never the
            pick. If your book hasn’t posted a line, we show the DraftKings price and label it.
          </Text>
        </View>

        <LinkRow
          label="Connected books"
          sub={
            bookConnected
              ? 'Linked. Your bet history syncs into Performance (read-only).'
              : 'Link DraftKings or FanDuel so Performance uses your real bets instead of manual tracking.'
          }
          onPress={() => navigation.navigate('ConnectSportsbook')}
          right={
            bookConnected ? (
              <View style={styles.bookPills}>
                {connections.map((c) => (
                  <View key={c.provider} style={styles.bookPill}>
                    <View style={styles.bookDot} />
                    <Text style={styles.bookPillText}>{providerMeta(c.provider).name}</Text>
                  </View>
                ))}
              </View>
            ) : (
              <Text style={styles.bookPillMuted}>Not connected</Text>
            )
          }
        />

        <SectionHeader title="Bet sizing" />

        <View style={styles.card}>
          <Text style={styles.cardLabel}>Kelly aggressiveness</Text>
          <View style={styles.stepperRow}>
            <Pressable
              onPress={() => stepMultiplier(-MULTIPLIER_STEP)}
              style={({ pressed }) => [styles.stepperBtn, pressed && styles.pressed]}
              disabled={multiplier <= MULTIPLIER_MIN}
            >
              <Ionicons name="remove" size={20} color={colors.tint} />
            </Pressable>
            <View style={styles.multValueWrap}>
              <Text style={styles.multValue}>{multiplier.toFixed(2)}×</Text>
              <Text style={styles.multSub}>{multLabel}</Text>
            </View>
            <Pressable
              onPress={() => stepMultiplier(MULTIPLIER_STEP)}
              style={({ pressed }) => [styles.stepperBtn, pressed && styles.pressed]}
              disabled={multiplier >= MULTIPLIER_MAX}
            >
              <Ionicons name="add" size={20} color={colors.tint} />
            </Pressable>
          </View>
          <Text style={styles.sub}>
            Scales the tenth-Kelly stake we recommend. 1.00× is the default; 2.50× ≈ quarter-Kelly,
            5.00× ≈ half-Kelly, 10.00× = full Kelly.
          </Text>
        </View>

        <View style={styles.card}>
          <View style={styles.capHeader}>
            <Text style={styles.cardLabel}>Max bet cap</Text>
            <Switch value={cap != null} onValueChange={toggleCap} />
          </View>
          {cap != null ? (
            <>
              <View style={styles.capRow}>
                <TextInput
                  style={styles.capInput}
                  value={capDraft}
                  onChangeText={setCapDraft}
                  onBlur={() => commitCap(capDraft)}
                  onSubmitEditing={() => commitCap(capDraft)}
                  keyboardType="decimal-pad"
                  placeholder="5"
                  placeholderTextColor={colors.textTertiary}
                  returnKeyType="done"
                />
                <Text style={styles.capUnit}>% of bankroll</Text>
              </View>
              <Text style={styles.sub}>
                No suggestion will exceed {formatPct(cap)} of your bankroll. Stakes you’ve already
                saved aren’t changed.
              </Text>
            </>
          ) : (
            <Text style={styles.sub}>
              No cap — suggestions are bounded only by the multiplier above. Turn this on to set
              your own ceiling.
            </Text>
          )}
        </View>

        <View style={styles.card}>
          <View style={styles.capHeader}>
            <Text style={styles.cardLabel}>Daily exposure limit</Text>
            <Switch value={rg.exposureCapPct != null} onValueChange={toggleRgCap} />
          </View>
          {rg.exposureCapPct != null ? (
            <>
              <View style={styles.capRow}>
                <TextInput
                  style={styles.capInput}
                  value={rgDraft}
                  onChangeText={setRgDraft}
                  onBlur={() => commitRgCap(rgDraft)}
                  onSubmitEditing={() => commitRgCap(rgDraft)}
                  keyboardType="decimal-pad"
                  placeholder="15"
                  placeholderTextColor={colors.textTertiary}
                  returnKeyType="done"
                />
                <Text style={styles.capUnit}>% of bankroll / day</Text>
              </View>
              <Text style={styles.sub}>
                We’ll warn you when today’s recommended stakes add up to more than{' '}
                {formatPct(rg.exposureCapPct)} of your bankroll. Staying small keeps you in the
                game.
              </Text>
            </>
          ) : (
            <Text style={styles.sub}>
              Off by default. Turn it on for a heads-up before a day’s picks over-extend you.
            </Text>
          )}
          <Pressable onPress={openHelpline} style={styles.helplineRow}>
            <Ionicons name="call-outline" size={15} color={colors.tint} />
            <Text style={styles.helplineText}>
              Gambling a problem? Call/text 1-800-GAMBLER — 24/7, free, confidential.
            </Text>
          </Pressable>
        </View>

        <SectionHeader title="Alerts" />

        <View style={styles.card}>
          <View style={styles.capHeader}>
            <Text style={styles.cardLabel}>Notifications</Text>
            <Switch value={pushEnabled} onValueChange={setPushOptIn} />
          </View>
          <Text style={styles.sub}>
            {pushEnabled
              ? 'On — new BET signals, big line moves on bets you track, and live in-play signals.'
              : 'New BET signals, big line moves on bets you track, and live in-play signals. Needs an app build with push support.'}
          </Text>
        </View>

        <SectionHeader title="Explore" />

        <LinkRow
          label="Track record"
          sub="Every settled pick since paper trading began — win rate, flat ROI and CLV by sport and model. Nothing cherry-picked."
          // Track Record is a bottom tab, and Settings is a stack screen above
          // the tab navigator — navigate() only bubbles UP, so a bare
          // navigate('TrackRecord') here is never handled. Target the tab
          // explicitly through its parent.
          onPress={() => navigation.navigate('Tabs', { screen: 'TrackRecord' })}
        />

        <LinkRow
          label="Live betting (beta)"
          sub="In-play picks that update while games are running. The live models are still calibrating, so treat these as paper trades."
          onPress={() => navigation.navigate('Tabs', { screen: 'Live' })}
        />

        <LinkRow
          label="How this works"
          sub="Edge, BET/AVOID, Kelly sizing and how results are tracked — explained."
          onPress={() => navigation.navigate('Explainer')}
        />

        <LinkRow
          label="Replay intro"
          sub="Re-read how the model works and what realistic results look like."
          onPress={replayIntro}
          icon="refresh-outline"
        />

        <SectionHeader title="Community" />

        <LinkRow
          label="Follow us on X"
          sub="Model notes, daily results and release news."
          onPress={() => openLink(TWITTER_URL, 'X')}
          icon="logo-x"
        />

        <LinkRow
          label="Join our Discord"
          sub="Talk picks with other users and tell us what to build next."
          onPress={() => openLink(DISCORD_URL, 'Discord')}
          icon="logo-discord"
        />

        <LinkRow
          label="Send feedback"
          sub={
            feedbackUnread > 0
              ? "We replied to you — open to read it."
              : 'Bug, feature idea, or a pick that looks wrong? Send it here and we reply in the app.'
          }
          onPress={() => navigation.navigate('Feedback')}
          icon="chatbubble-ellipses-outline"
          right={
            feedbackUnread > 0 ? (
              <View style={styles.unreadPill}>
                <Text style={styles.unreadPillText}>
                  {feedbackUnread} new {feedbackUnread === 1 ? 'reply' : 'replies'}
                </Text>
              </View>
            ) : undefined
          }
        />

        <Pressable
          onPress={() => openLink(WEBSITE_URL, 'the website')}
          style={({ pressed }) => pressed && styles.pressed}
        >
          <Text style={styles.version}>
            Signalbase v{APP_VERSION} · {websiteLabel}
          </Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

function describeMultiplier(m: number): string {
  if (m <= 0.5) return 'Conservative';
  if (m < 1) return 'Below tenth-Kelly';
  if (m === 1) return 'Tenth-Kelly (default)';
  if (m < 2.5) return 'Above tenth-Kelly';
  if (m < 5) return 'Roughly quarter-Kelly';
  if (m < 10) return 'Roughly half-Kelly';
  return 'Full Kelly';
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
  sectionHeader: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginTop: spacing.sm,
    marginBottom: spacing.sm,
    marginLeft: 2,
  },
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  linkCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  pressed: {
    opacity: 0.6,
  },
  // A long email must truncate rather than shove the "Signed in" pill off-row.
  flexShrink: {
    flexShrink: 1,
    marginRight: spacing.sm,
  },
  cardLabel: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  bookHint: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  bookSelectRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  bookChip: {
    paddingVertical: 6,
    paddingHorizontal: spacing.md,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.separatorOpaque,
    backgroundColor: colors.bgGrouped,
  },
  bookChipActive: {
    backgroundColor: colors.tint,
    borderColor: colors.tint,
  },
  bookChipText: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
  },
  bookChipTextActive: {
    color: colors.textInverse,
    fontWeight: font.weight.semibold,
  },
  bookNote: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginTop: spacing.sm,
  },
  bankrollRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  dollar: {
    fontSize: font.size.title3,
    color: colors.textPrimary,
    fontWeight: font.weight.semibold,
  },
  input: {
    flex: 1,
    fontSize: font.size.title3,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    backgroundColor: colors.bg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radii.sm,
  },
  saveBtn: {
    backgroundColor: colors.tint,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: radii.sm,
  },
  saveBtnText: {
    color: colors.textInverse,
    fontWeight: font.weight.semibold,
    fontSize: font.size.body,
  },
  sub: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  stepperRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.bg,
    borderRadius: radii.sm,
    padding: spacing.sm,
    marginBottom: spacing.sm,
  },
  stepperBtn: {
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.sm,
    backgroundColor: colors.bgCard,
  },
  multValueWrap: {
    alignItems: 'center',
    flex: 1,
  },
  multValue: {
    fontSize: font.size.title2,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  multSub: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginTop: 2,
  },
  capHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  capRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  capInput: {
    width: 80,
    fontSize: font.size.title3,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    backgroundColor: colors.bg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radii.sm,
    textAlign: 'center',
  },
  capUnit: {
    fontSize: font.size.body,
    color: colors.textSecondary,
  },
  helplineRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  helplineText: {
    flex: 1,
    fontSize: font.size.footnote,
    color: colors.tint,
    fontWeight: font.weight.medium,
  },
  bookRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  bookPills: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'flex-end',
    gap: 6,
    flexShrink: 1,
  },
  bookPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.betSoft,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  bookDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.bet,
  },
  bookPillText: {
    fontSize: font.size.caption,
    color: colors.bet,
    fontWeight: font.weight.semibold,
  },
  bookPillMuted: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    fontWeight: font.weight.medium,
  },
  unreadPill: {
    backgroundColor: colors.tint,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  unreadPillText: {
    fontSize: font.size.caption,
    color: colors.textInverse,
    fontWeight: font.weight.semibold,
  },
  signOutBtn: {
    marginTop: spacing.md,
    height: 40,
    borderRadius: radii.md,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.avoidSoft,
  },
  signOutText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.avoid,
  },
  version: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    textAlign: 'center',
    marginTop: spacing.sm,
  },
});
