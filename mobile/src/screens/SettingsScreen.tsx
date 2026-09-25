import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  InputAccessoryView,
  Keyboard,
  Linking,
  Platform,
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
import { usePreferredBooks } from '@/hooks/usePreferredBooks';
import { booksLabel, booksName, booksShortList, MODEL_BOOK } from '@/lib/markets';
import { SportsbookPickerSheet } from '@/components/SportsbookPickerSheet';
import { StatePickerSheet } from '@/components/StatePickerSheet';
import { useBettingState } from '@/hooks/useBettingState';
import { DK_GREEN } from '@/lib/sportsbookLinks';
import { providerMeta, useSportsbookConnection } from '@/hooks/useSportsbookConnection';
import { useOnboarding } from '@/hooks/useOnboarding';
import { useResponsibleGambling } from '@/hooks/useResponsibleGambling';
import { useBankroll } from '@/hooks/useBankroll';
import {
  BANKROLL_CARD_COPY,
  BANKROLL_FOOTER_COPY,
  bankrollFieldText,
  canStepUnitPct,
  checkBankroll,
  formatBankrollInput,
  formatPct,
  stepUnitPct,
  unitRowSubtitle,
  unitRowTitle,
  visibleBankrollError,
} from '@/lib/bankroll';
import { NotificationsCard } from '@/components/NotificationsCard';
import { useFeedbackUnread } from '@/hooks/useFeedback';
import { useAuth } from '@/hooks/useAuth';
import { AUTH_ENABLED } from '@/lib/authConfig';
import { authErrorMessage } from '@/lib/auth';
import { useSubscription } from '@/hooks/useSubscription';
import { useAccess } from '@/hooks/useAccess';
import { useEntitlement } from '@/hooks/useEntitlement';
import { billingReady } from '@/lib/billingConfig';
import { discordLinkReady } from '@/lib/discordConfig';
import { describeDiscordLink, discordErrorMessage } from '@/lib/discord';
import { DiscordLinkModal } from '@/components/DiscordLinkModal';
import { billingErrorMessage, openManageSubscription } from '@/lib/billing';
import { describeSubscription } from '@/lib/billingHelpers';
import { BUILD_STAMP } from '@/lib/buildStamp';
import {
  APP_VERSION,
  DISCORD_URL,
  TWITTER_URL,
  WEBSITE_URL,
  openLink,
} from '@/lib/socialLinks';
import { formatUnits } from '@/lib/thresholds';
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

/** The iOS decimal pad has no return key; this bar is its Done. */
const BANKROLL_ACCESSORY_ID = 'bankrollDone';

/** A labeled Lower | Raise pair — words, not icon steppers, so VoiceOver reads
 *  the action (#786 removed the icon-only ones for exactly that). */
function LowerRaise({
  what,
  canLower,
  canRaise,
  onStep,
}: {
  what: string;
  canLower: boolean;
  canRaise: boolean;
  onStep: (dir: -1 | 1) => void;
}) {
  return (
    <View style={styles.stepPill}>
      {([-1, 1] as const).map((dir) => {
        const enabled = dir === -1 ? canLower : canRaise;
        const word = dir === -1 ? 'Lower' : 'Raise';
        return (
          <Pressable
            key={dir}
            onPress={() => onStep(dir)}
            disabled={!enabled}
            accessibilityRole="button"
            accessibilityLabel={`${word} ${what}`}
            accessibilityState={{ disabled: !enabled }}
            hitSlop={{ top: 6, bottom: 6 }}
            style={({ pressed }) => [
              styles.stepBtn,
              dir === 1 && styles.stepBtnRight,
              pressed && styles.pressed,
            ]}
          >
            <Text style={[styles.stepText, !enabled && styles.stepTextOff]}>{word}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

/**
 * The optional bankroll — display only (lib/bankroll.ts). It converts the
 * app's flat units into the member's dollars and sizes nothing. Invalid text
 * never saves; clearing the field clears the bankroll. Every error waits for
 * blur or Done except the over-$10M one, which shows as you type.
 */
function BankrollCard() {
  const { settings, setAmount, setUnitPct } = useBankroll();
  const [text, setText] = useState(() => bankrollFieldText(settings.amount));
  const [focused, setFocused] = useState(false);
  const [committed, setCommitted] = useState(false);

  // The stored amount arrives after the first render (AsyncStorage); show it
  // unless the member is mid-edit.
  useEffect(() => {
    if (!focused) setText(bankrollFieldText(settings.amount));
  }, [settings.amount]); // not `focused`: a blur must not undo the text just committed

  const check = checkBankroll(text);
  const error = visibleBankrollError(check, committed);

  const onChange = (raw: string) => {
    const next = formatBankrollInput(raw);
    setText(next);
    setCommitted(false);
    const c = checkBankroll(next);
    if (c.state === 'empty') setAmount(null);
    else if (c.state === 'valid') setAmount(c.amount);
  };

  const commit = () => {
    setFocused(false);
    setCommitted(true);
    // A valid entry re-renders in its saved form (a trailing "." goes).
    if (check.state === 'valid') setText(bankrollFieldText(check.amount));
  };

  return (
    <View style={styles.card}>
      <View style={styles.bookRow}>
        <Text style={[styles.cardLabel, styles.noMargin]}>Your bankroll</Text>
        <Text style={styles.bookPillMuted}>Optional</Text>
      </View>
      <Text style={styles.bookHint}>{BANKROLL_CARD_COPY}</Text>
      <View style={[styles.moneyField, error ? styles.moneyFieldError : null]}>
        <Text
          style={[styles.moneyPrefix, text === '' && styles.moneyPrefixEmpty]}
          accessibilityElementsHidden
          importantForAccessibility="no"
        >
          $
        </Text>
        <TextInput
          style={styles.moneyInput}
          value={text}
          onChangeText={onChange}
          onFocus={() => setFocused(true)}
          onBlur={commit}
          onSubmitEditing={() => Keyboard.dismiss()}
          keyboardType="decimal-pad"
          returnKeyType="done"
          clearButtonMode="while-editing"
          placeholder="Enter amount"
          placeholderTextColor={colors.textTertiary}
          inputAccessoryViewID={Platform.OS === 'ios' ? BANKROLL_ACCESSORY_ID : undefined}
          accessibilityLabel="Your bankroll in dollars, optional"
          accessibilityHint="Only used to show your units in dollars. Stays on this device."
        />
      </View>
      {error ? (
        <View style={styles.fieldErrorRow} accessibilityRole="alert" accessibilityLiveRegion="polite">
          <Ionicons name="alert-circle" size={14} color={colors.avoid} />
          <Text style={styles.fieldErrorText}>{error}</Text>
        </View>
      ) : null}

      <View style={styles.unitRow}>
        <View style={styles.unitRowText}>
          <Text style={styles.unitRowTitle}>{unitRowTitle(settings)}</Text>
          <Text style={styles.unitRowSub}>{unitRowSubtitle(settings)}</Text>
        </View>
        <LowerRaise
          what={`unit size, now ${formatPct(settings.unitPct)} of bankroll`}
          canLower={canStepUnitPct(settings.unitPct, -1)}
          canRaise={canStepUnitPct(settings.unitPct, 1)}
          onStep={(dir) => setUnitPct(stepUnitPct(settings.unitPct, dir))}
        />
      </View>
      <Text style={styles.bankrollFooter}>{BANKROLL_FOOTER_COPY}</Text>

      {Platform.OS === 'ios' ? (
        <InputAccessoryView nativeID={BANKROLL_ACCESSORY_ID}>
          <View style={styles.doneBar}>
            <Pressable
              onPress={() => Keyboard.dismiss()}
              accessibilityRole="button"
              accessibilityLabel="Done"
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
              style={({ pressed }) => [styles.doneBtn, pressed && styles.pressed]}
            >
              <Text style={styles.doneText}>Done</Text>
            </Pressable>
          </View>
        </InputAccessoryView>
      ) : null}
    </View>
  );
}

export function SettingsScreen() {
  const navigation = useNavigation<Nav>();
  const { books } = usePreferredBooks();
  const [bookPickerOpen, setBookPickerOpen] = useState(false);
  const { name: stateName } = useBettingState();
  const [statePickerOpen, setStatePickerOpen] = useState(false);
  const { connections, anyConnected: bookConnected } = useSportsbookConnection();
  const { replay: replayIntro } = useOnboarding();
  const { settings: rg, setExposureCapUnits } = useResponsibleGambling();
  const feedbackUnread = useFeedbackUnread();
  const { signedIn, email: authEmail, user: authUser, signOut } = useAuth();
  // Two different questions, deliberately asked of two different hooks:
  // `subscription` DESCRIBES the app subscription (this row is about it), while
  // `entitled` DECIDES access and has to include a Discord-paid member.
  const { subscription } = useSubscription();
  const { entitled } = useEntitlement();
  const { access, unlink, busy: discordBusy } = useAccess();
  const [discordSheet, setDiscordSheet] = useState(false);
  const [rgDraft, setRgDraft] = useState<string>('');

  useEffect(() => {
    setRgDraft(rg.exposureCapUnits != null ? String(rg.exposureCapUnits) : '');
  }, [rg.exposureCapUnits]);

  // The cap is stored, summed and displayed in UNITS end to end
  // (useResponsibleGambling, and PicksHomeScreen's unitsFor sum). This field
  // used to divide the entry by 100 under a "units / day" label, so typing 10
  // stored 0.1u — a ceiling every single pick breached. Units, no conversion.
  const commitRgCap = (raw: string) => {
    if (raw.trim() === '') return;
    const units = parseFloat(raw);
    if (!Number.isFinite(units) || units <= 0 || units > 100) {
      Alert.alert('Invalid limit', 'Enter a number of units between 0 and 100.');
      setRgDraft(rg.exposureCapUnits != null ? String(rg.exposureCapUnits) : '');
      return;
    }
    setExposureCapUnits(units);
  };

  // A typical BET lays ~1.1u, so 10u/day is roughly a nine-pick day.
  const toggleRgCap = (on: boolean) => setExposureCapUnits(on ? 10 : null);

  const openHelpline = () => {
    Linking.openURL('tel:1-800-522-4700').catch(() =>
      Alert.alert('Need help?', 'Call or text 1-800-GAMBLER (1-800-522-4700), available 24/7.'),
    );
  };

  const confirmSignOut = () => {
    Alert.alert('Sign out?', 'Your models and tracked bets stay on this device.', [
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

  const websiteLabel = WEBSITE_URL.replace(/^https?:\/\//, '');
  const showAccountSection = AUTH_ENABLED || billingReady() || discordLinkReady();

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
                Your models and tracked bets stay on this device.
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
              sub="Optional. Everything works without an account — your models and tracked bets stay on this device."
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
              subscription
                ? `${describeSubscription(subscription)} Tap to manage or cancel.`
                : access.discord_access
                  ? 'Included with your Discord membership — nothing to pay here. Manage it where you bought it.'
                  : 'Signals are locked. Tap to see plans.'
            }
            onPress={() => {
              // A Discord-paid member has no App Store subscription to manage,
              // and sending them to the paywall would invite them to buy a
              // second time for something they already have.
              if (subscription) {
                openManageSubscription(authUser?.id ?? null).catch((e) =>
                  Alert.alert('Could not open billing', billingErrorMessage(e)),
                );
              } else if (access.discord_access) {
                Alert.alert(
                  'Included with Discord',
                  'Your Discord membership covers the app. Manage or cancel it where you bought it — cancelling there ends app access too.',
                );
              } else {
                navigation.navigate('Paywall');
              }
            }}
            right={
              entitled ? (
                <View style={styles.bookPill}>
                  <View style={styles.bookDot} />
                  <Text style={styles.bookPillText}>
                    {subscription ? 'Active' : 'Discord'}
                  </Text>
                </View>
              ) : (
                <Text style={styles.bookPillMuted}>Free</Text>
              )
            }
          />
        ) : null}

        <SectionHeader title="Betting" />

        <View style={styles.card}>
          <Text style={styles.cardLabel}>Your sportsbooks</Text>
          <Text style={styles.bookHint}>
            The books you bet at. The Stats page prints the best line among them beside each
            player, and the betslip’s bet button opens the one taking your slip. It changes
            nothing about how picks are priced.
          </Text>
          {/* One selection surface app-wide: this row opens the same picker
              sheet the boards use, instead of carrying its own chip selector. */}
          <Pressable
            onPress={() => setBookPickerOpen(true)}
            accessibilityRole="button"
            accessibilityLabel={`Your sportsbooks: ${booksName(books)}. Tap to change.`}
            style={({ pressed }) => [styles.bookPickRow, pressed && { opacity: 0.7 }]}
          >
            <View
              style={[
                styles.bookBadge,
                books.length === 1 && books[0] === MODEL_BOOK && styles.bookBadgeDk,
              ]}
            >
              <Text
                style={[
                  styles.bookBadgeText,
                  books.length === 1 && books[0] === MODEL_BOOK && styles.bookBadgeTextDk,
                ]}
              >
                {booksLabel(books)}
              </Text>
            </View>
            <Text style={styles.bookRowName}>{booksName(books)}</Text>
            <Text style={styles.bookRowChange}>Change</Text>
            <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
          </Pressable>
          {/* A grouped-list footer is read as the explanation of the control
              above it, so it leads with what this setting does (UX review). The
              long version lives in the Explainer, not here. */}
          <Text style={styles.bookNote}>
            On Stats there is no fallback: a player none of your books has priced shows no
            line. On the betslip there is — a slip none of them can price in full opens at
            DraftKings, so the button never sends you somewhere the bet isn’t, and the
            betslip still lists every book we price so you can place anywhere. Picks and
            Signals always price at DraftKings.
          </Text>
        </View>

        {/* The state three books' betslip links need (lib/sportsbookLinks.ts):
            without it BetMGM, BetRivers and Caesars open at their web root
            instead of in the app with the bet on the slip. */}
        <View style={styles.card}>
          <Text style={styles.cardLabel}>Your state</Text>
          <Text style={styles.bookHint}>
            Where your sportsbook accounts are licensed. BetMGM, BetRivers and Caesars need it to
            open your bet in their app.
          </Text>
          <Pressable
            onPress={() => setStatePickerOpen(true)}
            accessibilityRole="button"
            accessibilityLabel={`Your state: ${stateName ?? 'not set'}. Tap to change.`}
            style={({ pressed }) => [styles.bookPickRow, pressed && { opacity: 0.7 }]}
          >
            <Text style={[styles.bookRowName, !stateName && { color: colors.textTertiary }]}>
              {stateName ?? 'Not set'}
            </Text>
            <Text style={styles.bookRowChange}>{stateName ? 'Change' : 'Set'}</Text>
            <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
          </Pressable>
        </View>

        <LinkRow
          label="Connected books"
          sub={
            bookConnected
              ? 'Linked. Your bet history syncs into Performance (read-only).'
              : 'Automatic bet import is coming soon. For now, log bets yourself on the Performance tab.'
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
              <Text style={styles.bookPillMuted}>Coming soon</Text>
            )
          }
        />

        {/* Display only: units in the member's dollars. The daily exposure
            limit below is unchanged and does not read it. */}
        <SectionHeader title="Bankroll" />

        <BankrollCard />

        <SectionHeader title="Staying in control" />

        <View style={styles.card}>
          <View style={styles.capHeader}>
            <Text style={styles.cardLabel}>Daily exposure limit</Text>
            <Switch value={rg.exposureCapUnits != null} onValueChange={toggleRgCap} />
          </View>
          {rg.exposureCapUnits != null ? (
            <>
              <View style={styles.capRow}>
                <TextInput
                  style={styles.capInput}
                  value={rgDraft}
                  onChangeText={setRgDraft}
                  onBlur={() => commitRgCap(rgDraft)}
                  onSubmitEditing={() => commitRgCap(rgDraft)}
                  keyboardType="decimal-pad"
                  placeholder="10"
                  placeholderTextColor={colors.textTertiary}
                  returnKeyType="done"
                />
                <Text style={styles.capUnit}>units / day</Text>
              </View>
              <Text style={styles.sub}>
                We’ll warn you when today’s recommended stakes add up to more than{' '}
                {formatUnits(rg.exposureCapUnits)}. One unit is one flat bet, so a typical pick
                lays about 1.1u. Staying small keeps you in the game.
              </Text>
            </>
          ) : (
            <Text style={styles.sub}>
              Off by default. Turn it on for a heads-up before a day’s picks over-extend you.
            </Text>
          )}
        </View>

        {/* Its own card, deliberately: this used to sit inside the exposure
            card, which is OFF by default — so the one support resource in the
            app rendered as a footnote on a feature the member had declined. */}
        <View style={styles.card}>
          <Pressable
            onPress={openHelpline}
            accessibilityRole="link"
            accessibilityLabel="Call or text 1-800-GAMBLER, the national problem gambling helpline"
            style={styles.helplineRow}
          >
            <Ionicons name="call-outline" size={15} color={colors.tint} />
            <Text style={styles.helplineText}>
              Gambling a problem? Call/text 1-800-GAMBLER — 24/7, free, confidential.
            </Text>
          </Pressable>
        </View>

        <SectionHeader title="Alerts" />

        <NotificationsCard />

        <SectionHeader title="Explore" />

        <LinkRow
          label="Track record"
          sub="Every settled pick on record — win rate, flat ROI and CLV by sport and model. Nothing cherry-picked."
          // Track Record is a bottom tab, and Settings is a stack screen above
          // the tab navigator — navigate() only bubbles UP, so a bare
          // navigate('TrackRecord') here is never handled. Target the tab
          // explicitly through its parent.
          onPress={() => navigation.navigate('Tabs', { screen: 'TrackRecord' })}
        />

        <LinkRow
          label="Live Signals (beta)"
          sub="In-play picks that update while games are running. They show on Picks under Live Signals, which is always there and fills while a game is in play. The live models are unproven — treat them that way."
          onPress={() =>
            navigation.navigate('Tabs', { screen: 'Picks', params: { view: 'live' } })
          }
        />

        <LinkRow
          label="How this works"
          sub="Edge, BET/AVOID, unit sizing and how results are tracked — explained."
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

        {/* While linking is dark this is exactly today's row: a plain invite
            link, no account involved. Once it is live the row becomes the
            connect/disconnect control, because the invite alone can't grant
            the subscriber role. */}
        {discordLinkReady() && signedIn ? (
          <LinkRow
            label={access.discord_linked ? 'Discord' : 'Connect Discord'}
            sub={describeDiscordLink(access)}
            onPress={() => {
              if (!access.discord_linked) {
                setDiscordSheet(true);
                return;
              }
              Alert.alert(
                'Disconnect Discord?',
                // Say plainly what they lose. A Discord-paid member who
                // disconnects here would lose their free app access, and
                // finding that out afterwards is the worst way to learn it.
                access.discord_access
                  ? 'Your Discord membership is what gives you access to the app. Disconnecting will lock the app until you subscribe here or reconnect.'
                  : "We'll remove the subscriber role we granted you. You'll stay in the server.",
                [
                  { text: 'Cancel', style: 'cancel' },
                  {
                    text: 'Disconnect',
                    style: 'destructive',
                    onPress: () => {
                      unlink().catch((e) =>
                        Alert.alert('Could not disconnect', discordErrorMessage(e)),
                      );
                    },
                  },
                ],
              );
            }}
            icon="logo-discord"
            right={
              discordBusy ? (
                <ActivityIndicator />
              ) : access.discord_linked ? (
                <View style={styles.bookPill}>
                  <View style={styles.bookDot} />
                  <Text style={styles.bookPillText}>Connected</Text>
                </View>
              ) : (
                <Text style={styles.bookPillMuted}>Not connected</Text>
              )
            }
          />
        ) : (
          <LinkRow
            label="Join our Discord"
            sub="Talk picks with other users and tell us what to build next."
            onPress={() => openLink(DISCORD_URL, 'Discord')}
            icon="logo-discord"
          />
        )}

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
            Signalbase v{APP_VERSION} · {BUILD_STAMP} · {websiteLabel}
          </Text>
        </Pressable>
      </ScrollView>
      <SportsbookPickerSheet visible={bookPickerOpen} onClose={() => setBookPickerOpen(false)} />
      <StatePickerSheet visible={statePickerOpen} onClose={() => setStatePickerOpen(false)} />
      <DiscordLinkModal visible={discordSheet} onClose={() => setDiscordSheet(false)} />
    </SafeAreaView>
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
  bookPickRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.bgGrouped,
    borderRadius: radii.md,
    padding: spacing.md,
  },
  bookBadge: {
    width: 36,
    height: 36,
    borderRadius: radii.sm,
    backgroundColor: colors.noneSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  bookBadgeDk: {
    backgroundColor: DK_GREEN,
  },
  bookBadgeText: {
    fontSize: font.size.caption,
    fontWeight: font.weight.bold,
    color: colors.textSecondary,
  },
  bookBadgeTextDk: {
    color: '#000',
  },
  bookRowName: {
    flex: 1,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  bookRowChange: {
    fontSize: font.size.footnote,
    color: colors.tint,
    textDecorationLine: 'underline',
    fontWeight: font.weight.medium,
  },
  bookNote: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginTop: spacing.sm,
  },
  sub: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    lineHeight: 18,
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
  noMargin: {
    marginBottom: 0,
  },
  moneyField: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    backgroundColor: colors.bgGrouped,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: 'transparent',
    paddingHorizontal: spacing.md,
  },
  moneyFieldError: {
    borderColor: colors.avoid,
  },
  moneyPrefix: {
    fontSize: font.size.title3,
    fontWeight: font.weight.medium,
    color: colors.textSecondary,
  },
  moneyPrefixEmpty: {
    color: colors.textTertiary,
  },
  moneyInput: {
    flex: 1,
    minHeight: 48,
    fontSize: font.size.title3,
    fontWeight: font.weight.medium,
    color: colors.textPrimary,
  },
  fieldErrorRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 6,
    marginTop: spacing.sm,
  },
  // Words take the text-safe red; the icon beside them and the field's
  // outline keep `avoid` (non-text, 3:1 is enough there).
  fieldErrorText: {
    flex: 1,
    fontSize: font.size.footnote,
    color: colors.avoidText,
  },
  // The mockup's grouped inset, as the sportsbook row above it uses.
  unitRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    marginTop: spacing.md,
    backgroundColor: colors.bgGrouped,
    borderRadius: radii.md,
    padding: spacing.md,
  },
  unitRowText: {
    flex: 1,
  },
  unitRowTitle: {
    fontSize: font.size.headline,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  unitRowSub: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
  stepPill: {
    flexDirection: 'row',
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.separatorOpaque,
    borderRadius: radii.pill,
    overflow: 'hidden',
  },
  stepBtn: {
    minHeight: 32,
    paddingHorizontal: spacing.md,
    justifyContent: 'center',
  },
  stepBtnRight: {
    borderLeftWidth: 1,
    borderLeftColor: colors.separatorOpaque,
  },
  stepText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  stepTextOff: {
    color: colors.textTertiary,
  },
  bankrollFooter: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginTop: spacing.md,
  },
  doneBar: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    backgroundColor: colors.bgGrouped,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  doneBtn: {
    paddingVertical: spacing.xs,
  },
  doneText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.tint,
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
