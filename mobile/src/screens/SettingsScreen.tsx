import React, { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import {
  ActivityIndicator,
  Alert,
  InputAccessoryView,
  Keyboard,
  Linking,
  Platform,
  Pressable,
  ScrollView,
  useWindowDimensions,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation, type RouteProp } from '@react-navigation/native';
import { usePreferredBooks } from '@/hooks/usePreferredBooks';
import { bookLabelShort, booksLabel, booksName, MODEL_BOOK } from '@/lib/markets';
import { SportsbookPickerSheet } from '@/components/SportsbookPickerSheet';
import { StatePickerSheet } from '@/components/StatePickerSheet';
import { useBettingState } from '@/hooks/useBettingState';
import { DK_GREEN } from '@/lib/sportsbookLinks';
import { providerMeta, useSportsbookConnection } from '@/hooks/useSportsbookConnection';
import { useOnboarding } from '@/hooks/useOnboarding';
import { useBankroll } from '@/hooks/useBankroll';
import {
  BANKROLL_CARD_COPY,
  BANKROLL_FOOTER_COPY,
  bankrollDraft,
  bankrollFieldText,
  canStepUnitPct,
  checkBankroll,
  commitBankrollText,
  editBankrollInput,
  formatDollars,
  formatPct,
  unitDollars,
  unitRowSubtitle,
  unitRowTitle,
  visibleBankrollError,
} from '@/lib/bankroll';
import { NotificationsCard } from '@/components/NotificationsCard';
import { usePushOptIn } from '@/hooks/usePushOptIn';
import { usePushState } from '@/hooks/usePushNotifications';
import { useFeedbackUnread } from '@/hooks/useFeedback';
import { useAuth } from '@/hooks/useAuth';
import { AUTH_ENABLED } from '@/lib/authConfig';
import { authErrorMessage } from '@/lib/auth';
import { useAccess } from '@/hooks/useAccess';
import { useMembership } from '@/hooks/useMembership';
import { billingReady, planFor } from '@/lib/billingConfig';
import { discordLinkReady } from '@/lib/discordConfig';
import { describeDiscordLink, discordErrorMessage, discordInviteIfPaid } from '@/lib/discord';
import { DiscordLinkModal } from '@/components/DiscordLinkModal';
import { billingErrorMessage, endTrialEarly, openManageSubscription, restorePurchases } from '@/lib/billing';
import { earlyUnlockLine, isPlanKey, planStatusCopy } from '@/lib/billingHelpers';
import { BUILD_STAMP } from '@/lib/buildStamp';
import { isUpdateReady, subscribeUpdateReady, UPDATE_READY_SETTINGS } from '@/lib/updateReady';
import {
  APP_VERSION,
  PRIVACY_URL,
  TERMS_URL,
  TWITTER_URL,
  WEBSITE_URL,
  openLink,
} from '@/lib/socialLinks';
import {
  EXPLORE_TILE_SUMMARY,
  LEGAL_TILE_SUMMARY,
  SETTINGS_GRID_SECTIONS,
  SETTINGS_SECTION_TITLE,
  accountTileSummary,
  bankrollTileSummary,
  communityTileSummary,
  isSettingsSectionId,
  notificationsTileSummary,
  settingsHomeLayout,
  sportsbooksTileSummary,
  type SettingsSectionId,
} from '@/lib/settingsHome';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';
import { BetslipBarSpacer } from '@/components/BetslipBarSpacer';

type Nav = NativeStackNavigationProp<RootStackParamList>;

const SECTION_ICON: Record<SettingsSectionId, React.ComponentProps<typeof Ionicons>['name']> = {
  sportsbooks: 'storefront-outline',
  bankroll: 'wallet-outline',
  notifications: 'notifications-outline',
  explore: 'compass-outline',
  community: 'chatbubble-outline',
  account: 'person-outline',
  legal: 'shield-checkmark-outline',
};

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
      // Role only, NO accessibilityLabel: a label REPLACES what VoiceOver reads
      // from the children, and five rows carry their status in `right` (Not
      // signed in, Active, the connected books, Connected, "2 new replies").
      // Left to the children, VoiceOver reads label, status and sub in order.
      accessibilityRole="button"
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
  const { fontScale, width } = useWindowDimensions();
  const { summaries, accountSpoken, showAccountSection } = useSettingsHomeModel();
  const websiteLabel = WEBSITE_URL.replace(/^https?:\/\//, '');
  // A newer bundle is downloaded and runs at the next start (src/lib/updateReady.ts).
  const updateReady = useSyncExternalStore(subscribeUpdateReady, isUpdateReady);
  const open = (section: SettingsSectionId) => {
    navigation.navigate('SettingsSection', { section });
  };
  const grid = SETTINGS_GRID_SECTIONS.filter((id) => id !== 'account' || showAccountSection);
  // Half-width tiles collide once Dynamic Type is up, on a narrow phone, or
  // when the count is odd. Legal is always full width, below these.
  const { paired, fullWidth } = settingsHomeLayout(grid, fontScale, width);

  return (
    <SettingsScroll>
      {paired.length > 0 ? (
        <View style={styles.grid}>
          {paired.map((id) => (
            <View key={id} style={styles.tileWrap}>
              <SettingsTile
                title={SETTINGS_SECTION_TITLE[id]}
                summary={summaries[id]}
                spoken={id === 'account' ? accountSpoken : summaries[id]}
                icon={SECTION_ICON[id]}
                onPress={() => open(id)}
              />
            </View>
          ))}
        </View>
      ) : null}
      {fullWidth.map((id) => (
        <SettingsTile
          key={id}
          wide
          title={SETTINGS_SECTION_TITLE[id]}
          summary={summaries[id]}
          spoken={id === 'account' ? accountSpoken : summaries[id]}
          icon={SECTION_ICON[id]}
          onPress={() => open(id)}
        />
      ))}
      <SettingsTile
        wide
        title={SETTINGS_SECTION_TITLE.legal}
        summary={summaries.legal}
        icon={SECTION_ICON.legal}
        onPress={() => open('legal')}
      />
      <Pressable
        onPress={() => openLink(WEBSITE_URL, 'the website')}
        accessibilityRole="link"
        accessibilityLabel={`Signalbase version ${APP_VERSION}, build ${BUILD_STAMP}, ${websiteLabel}`}
        accessibilityHint="Opens the website"
        hitSlop={{ top: 12, bottom: 12, left: 16, right: 16 }}
        style={({ pressed }) => pressed && styles.pressed}
      >
        <Text style={styles.version}>
          Signalbase v{APP_VERSION} · {BUILD_STAMP} · {websiteLabel}
        </Text>
      </Pressable>
      {/* Its own line, outside the website link, so the status is not buried
          in a wrapped caption (UX review, 2026-10-19). */}
      {updateReady ? <Text style={styles.version}>{UPDATE_READY_SETTINGS}</Text> : null}
    </SettingsScroll>
  );
}

export function SettingsSectionScreen({
  route,
}: {
  route: RouteProp<RootStackParamList, 'SettingsSection'>;
}) {
  const section = route.params?.section;
  switch (section) {
    case 'sportsbooks':
      return <SportsbooksSection />;
    case 'bankroll':
      return <BankrollSection />;
    case 'notifications':
      return <NotificationsSection />;
    case 'explore':
      return <ExploreSection />;
    case 'community':
      return <CommunitySection />;
    case 'account':
      return <AccountSection />;
    case 'legal':
      return <LegalSection />;
    default:
      return (
        <SettingsScroll>
          <Text style={styles.sub}>That section is not available.</Text>
        </SettingsScroll>
      );
  }
}

/**
 * One scroll for every Settings surface. automaticallyAdjustKeyboardInsets
 * keeps the bankroll field above the keyboard; the betslip spacer is the
 * last child so the bar never covers the last row.
 */
function SettingsScroll({
  children,
  overlay,
}: {
  children: React.ReactNode;
  overlay?: React.ReactNode;
}) {
  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <ScrollView
        contentContainerStyle={styles.list}
        keyboardShouldPersistTaps="handled"
        automaticallyAdjustKeyboardInsets
      >
        {children}
        <BetslipBarSpacer />
      </ScrollView>
      {overlay}
    </SafeAreaView>
  );
}

function SettingsTile({
  title,
  summary,
  spoken,
  icon,
  onPress,
  wide = false,
}: {
  title: string;
  summary: string;
  /** VoiceOver text when the visible summary is shortened. */
  spoken?: string;
  icon: React.ComponentProps<typeof Ionicons>['name'];
  onPress: () => void;
  wide?: boolean;
}) {
  const glyph = (
    <View
      style={styles.tileIcon}
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      <Ionicons name={icon} size={18} color={colors.textSecondary} />
    </View>
  );
  const chevron = <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${title}. ${spoken ?? summary}`}
      onPress={onPress}
      style={({ pressed }) => [wide ? styles.tileWide : styles.tile, pressed && styles.pressed]}
    >
      {wide ? (
        <>
          {glyph}
          <View style={styles.tileWideText}>
            <Text style={[styles.tileTitle, styles.tileTitleInline]}>{title}</Text>
            <Text style={styles.tileSummary} numberOfLines={2}>{summary}</Text>
          </View>
          {chevron}
        </>
      ) : (
        <>
          <View style={styles.tileTop}>
            {glyph}
            {chevron}
          </View>
          <Text style={styles.tileTitle}>{title}</Text>
          <Text style={styles.tileSummary} numberOfLines={2}>{summary}</Text>
        </>
      )}
    </Pressable>
  );
}

/** One row inside an inset group. The label includes the sub so VoiceOver
 *  reads both; these rows have no separate status pill. */
function GroupRow({
  label,
  sub,
  onPress,
  icon = 'chevron-forward',
  first = false,
}: {
  label: string;
  sub: string;
  onPress: () => void;
  icon?: React.ComponentProps<typeof Ionicons>['name'];
  first?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${label}. ${sub}`}
      onPress={onPress}
      style={({ pressed }) => [styles.groupRow, !first && styles.groupRule, pressed && styles.pressed]}
    >
      <View style={styles.groupText}>
        <Text style={styles.cardLabel}>{label}</Text>
        <Text style={styles.sub}>{sub}</Text>
      </View>
      <Ionicons name={icon} size={18} color={colors.textTertiary} />
    </Pressable>
  );
}

function useSettingsPlan() {
  const navigation = useNavigation<Nav>();
  const { signedIn, email: authEmail, user: authUser, signOut } = useAuth();
  // `subscription` describes the App Store plan. A Whop membership does not
  // make this row Premium.
  const { subscription, hold: planHold, discordPaid, refresh: refreshMembership } = useMembership();
  const { access, unlink, busy: discordBusy } = useAccess();
  const comped = access.source === 'comped';
  const planStatus = planHold
    ? { badge: 'Free' as const, line: 'Checking your plan…' }
    : planStatusCopy(subscription, { discordPaid: access.discord_access, comped });
  const storePaid = discordPaid;
  const trialPlan = subscription?.plan && isPlanKey(subscription.plan) ? planFor(subscription.plan) : null;
  const linkedName = access.discord_username ?? 'Discord';
  // Discord lives under Community, so it does not open an empty Account section.
  const showAccountSection = AUTH_ENABLED || billingReady();
  const showDiscord = billingReady() ? signedIn : discordLinkReady() && signedIn;
  const planLabel = !billingReady() ? null : planHold ? 'Checking plan…' : planStatus.badge;
  return {
    navigation,
    signedIn,
    authEmail,
    authUser,
    signOut,
    subscription,
    planHold,
    refreshMembership,
    access,
    unlink,
    discordBusy,
    planStatus,
    storePaid,
    trialPlan,
    linkedName,
    showAccountSection,
    showDiscord,
    planLabel,
  };
}

function useSettingsHomeModel() {
  const plan = useSettingsPlan();
  const { books, ready: booksReady } = usePreferredBooks();
  const { name: stateName, ready: stateReady } = useBettingState();
  const { settings: bankroll, ready: bankrollReady } = useBankroll();
  const { enabled, ready: pushReady } = usePushOptIn();
  const { status } = usePushState();
  const feedbackUnread = useFeedbackUnread();
  const unit = unitDollars(bankroll);
  const unitLabel =
    unit == null ? `1u = ${formatPct(bankroll.unitPct)}` : `1u = ${formatDollars(unit, unit)}`;
  const amountLabel = bankroll.amount == null ? null : formatDollars(bankroll.amount, bankroll.amount);
  const accountSpoken = accountTileSummary(plan.signedIn, plan.authEmail, plan.planLabel);
  const summaries: Record<SettingsSectionId, string> = {
    sportsbooks:
      booksReady && stateReady
        ? sportsbooksTileSummary(books.map(bookLabelShort), stateName)
        : 'Checking',
    bankroll: bankrollReady ? bankrollTileSummary(amountLabel, unitLabel) : 'Checking',
    notifications: notificationsTileSummary(enabled, status, pushReady),
    explore: EXPLORE_TILE_SUMMARY,
    community: communityTileSummary(plan.showDiscord, feedbackUnread),
    account: accountTileSummary(plan.signedIn, plan.authEmail, plan.planLabel, true),
    legal: LEGAL_TILE_SUMMARY,
  };
  return { summaries, accountSpoken, showAccountSection: plan.showAccountSection };
}

function SportsbooksSection() {
  const navigation = useNavigation<Nav>();
  const { books } = usePreferredBooks();
  const [bookPickerOpen, setBookPickerOpen] = useState(false);
  const { name: stateName } = useBettingState();
  const [statePickerOpen, setStatePickerOpen] = useState(false);
  const { connections, anyConnected: bookConnected } = useSportsbookConnection();
  return (
    <SettingsScroll
      overlay={
        <>
          <SportsbookPickerSheet visible={bookPickerOpen} onClose={() => setBookPickerOpen(false)} />
          <StatePickerSheet visible={statePickerOpen} onClose={() => setStatePickerOpen(false)} />
        </>
      }
    >
        <View style={styles.card}>
          <Text style={styles.cardLabel}>Your sportsbooks</Text>
          <Text style={styles.bookHint}>
            The books you can bet at. Picks and Stats show the best price among them. You get
            the most value by using every book you can. Model records and stats still use the
            price the model found.
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
    </SettingsScroll>
  );
}

function BankrollSection() {
  return (
    <SettingsScroll>
      {/* Display only: units in the member's dollars. Nothing is sized off it. */}
      <BankrollCard />
    </SettingsScroll>
  );
}

function NotificationsSection() {
  return (
    <SettingsScroll>
      <NotificationsCard />
    </SettingsScroll>
  );
}

function ExploreSection() {
  const navigation = useNavigation<Nav>();
  const { replay: replayIntro } = useOnboarding();
  return (
    <SettingsScroll>
      <View style={styles.groupCard}>
        <GroupRow
          first
          label="Track record"
          sub="Every settled pick on record — win rate, return on bets and CLV by sport and model. Nothing cherry-picked."
          // Track Record is a bottom tab, and Settings is a stack screen above
          // the tab navigator — navigate() only bubbles UP, so a bare
          // navigate('TrackRecord') here is never handled. Target the tab
          // explicitly through its parent.
          onPress={() => navigation.navigate('Tabs', { screen: 'TrackRecord' })}
        />

        <GroupRow
          label="Live Signals (beta)"
          sub="In-play picks that update while games are running. They show on Picks under Live Signals, which is always there and fills while a game is in play. The live models are unproven — treat them that way."
          onPress={() =>
            navigation.navigate('Tabs', { screen: 'Picks', params: { view: 'live' } })
          }
        />

        <GroupRow
          label="How this works"
          sub="Edge, BET/AVOID, unit sizing and how results are tracked — explained."
          onPress={() => navigation.navigate('Explainer')}
        />

        <GroupRow
          label="Replay intro"
          sub="Re-read how the model works and what realistic results look like."
          onPress={replayIntro}
          icon="refresh-outline"
        />
      </View>
    </SettingsScroll>
  );
}

function CommunitySection() {
  const {
    navigation,
    signedIn,
    authUser,
    subscription,
    planHold,
    refreshMembership,
    access,
    unlink,
    discordBusy,
    planStatus,
    storePaid,
    trialPlan,
    linkedName,
  } = useSettingsPlan();
  const feedbackUnread = useFeedbackUnread();
  const [discordSheet, setDiscordSheet] = useState(false);
  const [endingTrial, setEndingTrial] = useState(false);

  const onUnlockDiscord = () => {
    const userId = authUser?.id;
    const plan = subscription?.plan;
    if (!userId || !plan || !isPlanKey(plan)) {
      Alert.alert(
        'Could not end the trial',
        'Your trial plan is not on this device yet. Try again in a moment.',
      );
      return;
    }
    setEndingTrial(true);
    endTrialEarly(plan, userId)
      .then((result) => {
        if (result.outcome !== 'completed') return;
        return refreshMembership().then(() => {
          setTimeout(() => {
            void refreshMembership();
          }, 4000);
        });
      })
      .catch((e) => Alert.alert('Could not end the trial', billingErrorMessage(e)))
      .finally(() => setEndingTrial(false));
  };

  return (
    <SettingsScroll
      overlay={<DiscordLinkModal visible={discordSheet} onClose={() => setDiscordSheet(false)} />}
    >
        <LinkRow
          label="Follow us on X"
          sub="Model notes, daily results and release news."
          onPress={() => openLink(TWITTER_URL, 'X')}
          icon="logo-x"
        />

        {/* No public invite. Join Discord is inside the paid card only. */}
        {billingReady() ? (
          !signedIn ? null : planHold ? (
          <View style={styles.card}>
            <Text style={styles.cardLabel}>Discord for members</Text>
            <Text style={styles.sub}>Checking your plan…</Text>
          </View>
          ) : (
          <>
          <View style={styles.card}>
            <View style={styles.bookRow}>
              <Text style={styles.cardLabel}>Discord for members</Text>
              {storePaid ? (
                <View style={styles.bookPill}>
                  <View style={styles.bookDot} />
                  <Text style={styles.bookPillText}>Included</Text>
                </View>
              ) : (
                <Ionicons name="lock-closed" size={16} color={colors.textTertiary} />
              )}
            </View>
            <Text style={styles.sub}>
              {storePaid
                ? 'Talk picks with other subscribers.'
                : planStatus.badge === 'Trial'
                  ? 'Unlocks when your paid plan starts, after the free trial. No invite is shown until then.'
                  : 'Included with a paid plan. No invite is shown until then.'}
            </Text>
            {planStatus.badge === 'Trial' && trialPlan ? (
              <Text style={[styles.sub, styles.chargeLine]}>{earlyUnlockLine(trialPlan.key)}</Text>
            ) : null}
            {storePaid ? (
              <Pressable
                onPress={() => {
                  const invite = discordInviteIfPaid(true);
                  if (invite) void openLink(invite, 'Discord');
                }}
                accessibilityRole="button"
                accessibilityLabel="Join Discord"
                style={({ pressed }) => [styles.manageBtn, pressed && styles.pressed]}
              >
                <Text style={styles.manageText}>Join Discord</Text>
              </Pressable>
            ) : planStatus.badge === 'Trial' ? (
              <Pressable
                onPress={onUnlockDiscord}
                disabled={endingTrial}
                accessibilityRole="button"
                accessibilityLabel="Unlock Discord early"
                accessibilityState={{ busy: endingTrial, disabled: endingTrial }}
                style={({ pressed }) => [styles.manageBtn, pressed && styles.pressed]}
              >
                {endingTrial ? (
                  <ActivityIndicator color={colors.textInverse} />
                ) : (
                  <Text style={styles.manageText}>Unlock Discord early</Text>
                )}
              </Pressable>
            ) : planStatus.badge === 'Free' ? (
              <Pressable
                onPress={() => navigation.navigate('Paywall')}
                accessibilityRole="button"
                accessibilityLabel="Upgrade to Premium"
                style={({ pressed }) => [styles.manageBtn, pressed && styles.pressed]}
              >
                <Text style={styles.manageText}>Upgrade to Premium</Text>
              </Pressable>
            ) : null}
            {access.discord_linked ? (
              <>
                <Text style={[styles.sub, styles.connectedLine]}>{`Connected as ${linkedName}.`}</Text>
                <Pressable
                  onPress={() => {
                    Alert.alert(
                      'Disconnect Discord?',
                      "We'll remove the subscriber role we granted you. You'll stay in the server.",
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
                  accessibilityRole="button"
                  accessibilityLabel="Disconnect Discord"
                  style={({ pressed }) => [styles.restoreBtn, pressed && styles.pressed]}
                >
                  <Text style={styles.restoreText}>Disconnect Discord</Text>
                </Pressable>
              </>
            ) : null}
          </View>
          {!access.discord_linked && (planStatus.badge === 'Free' || planStatus.badge === 'Trial') ? (
            <View style={styles.card}>
              <Text style={styles.sub}>
                Already in Discord via Whop? Connect Discord to link your account. Premium in the app is still via Apple.
              </Text>
              <Pressable
                onPress={() => setDiscordSheet(true)}
                accessibilityRole="button"
                accessibilityLabel="Connect Discord"
                style={({ pressed }) => [styles.restoreBtn, pressed && styles.pressed]}
              >
                <Text style={styles.restoreText}>Connect Discord</Text>
              </Pressable>
            </View>
          ) : null}
          </>
          )
        ) : discordLinkReady() && signedIn ? (
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
                "We'll remove the subscriber role we granted you. You'll stay in the server.",
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
        ) : null}

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
    </SettingsScroll>
  );
}

function AccountSection() {
  const {
    navigation,
    signedIn,
    authEmail,
    authUser,
    signOut,
    subscription,
    planHold,
    planStatus,
  } = useSettingsPlan();

  const onRestore = () => {
    const userId = authUser?.id;
    if (!userId) return;
    restorePurchases(userId)
      .then((restored) => {
        Alert.alert(
          restored ? 'Purchases restored' : 'Nothing to restore',
          restored
            ? 'Your subscription is active on this device.'
            : 'No active subscription was found for this App Store account.',
        );
      })
      .catch((e) => Alert.alert('Could not restore', billingErrorMessage(e)));
  };

  const onManage = () => {
    if (subscription) {
      openManageSubscription(authUser?.id ?? null).catch((e) =>
        Alert.alert('Could not open billing', billingErrorMessage(e)),
      );
      return;
    }
    navigation.navigate('Paywall');
  };

  const confirmSignOut = () => {
    Alert.alert('Sign out?', 'Your models and tracked bets stay on this device.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Sign out',
        onPress: () => {
          signOut().catch((e) => Alert.alert('Could not sign out', authErrorMessage(e)));
        },
      },
    ]);
  };

  return (
    <SettingsScroll>
        {/* Account + Subscription, near the bottom (Matt, 2026-11-09). Both are
            behind flags, so the whole section stays invisible until one flips. */}
        {AUTH_ENABLED ? (
          signedIn ? (
            <>
            <View style={styles.card}>
              <View
                accessible
                accessibilityLabel={`Signed in as ${authEmail ?? 'your account'}`}
                style={styles.bookRow}
              >
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
                accessibilityRole="button"
                accessibilityLabel="Sign out"
                style={({ pressed }) => [styles.signOutBtn, pressed && styles.pressed]}
              >
                <Text style={styles.signOutText}>Sign out</Text>
              </Pressable>
            </View>
            <Pressable
              onPress={() => navigation.navigate('DeleteAccount')}
              accessibilityRole="button"
              accessibilityLabel="Delete account"
              accessibilityHint="Opens a screen that explains what is deleted."
              style={({ pressed }) => [styles.deleteRow, pressed && styles.pressed]}
            >
              <Text style={styles.deleteText}>Delete account</Text>
              <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
            </Pressable>
            </>
          ) : (
            // Deliberately does NOT promise cross-device sync — auth is
            // session-only today. Update when account-scoped data lands.
            <LinkRow
              label="Sign in"
              sub="An account is needed to start a trial, subscribe and restore purchases. Your models and tracked bets stay on this device."
              onPress={() => navigation.navigate('SignIn')}
              right={<Text style={styles.bookPillMuted}>Not signed in</Text>}
            />
          )
        ) : null}

        {/* Subscription renders only when billing is live AND auth is on —
            billingReady() enforces that pairing, since a subscription with no
            account behind it can't survive a reinstall. */}
        {billingReady() ? (
          <View style={styles.card}>
            <View style={styles.bookRow}>
              <Text style={styles.cardLabel}>Plan</Text>
              {planHold ? null : planStatus.badge === 'Free' ? (
                <View style={styles.freePill}>
                  <Text style={styles.freePillText}>{planStatus.badge}</Text>
                </View>
              ) : (
                <View style={styles.bookPill}>
                  <View style={styles.bookDot} />
                  <Text style={styles.bookPillText}>{planStatus.badge}</Text>
                </View>
              )}
            </View>
            <Text style={styles.sub}>{planStatus.line}</Text>
            {planHold ? null : planStatus.badge === 'Free' ? (
              <Pressable
                onPress={() => navigation.navigate('Paywall')}
                accessibilityRole="button"
                accessibilityLabel="Upgrade to Premium"
                style={({ pressed }) => [styles.manageBtn, pressed && styles.pressed]}
              >
                <Text style={styles.manageText}>Upgrade to Premium</Text>
              </Pressable>
            ) : (
              <Pressable
                onPress={onManage}
                accessibilityRole="button"
                accessibilityLabel="Manage subscription"
                style={({ pressed }) => [styles.manageBtn, pressed && styles.pressed]}
              >
                <Text style={styles.manageText}>Manage subscription</Text>
              </Pressable>
            )}
            <Pressable
              onPress={onRestore}
              accessibilityRole="button"
              accessibilityLabel="Restore purchases"
              style={({ pressed }) => [styles.restoreBtn, pressed && styles.pressed]}
            >
              <Text style={styles.restoreText}>Restore purchases</Text>
            </Pressable>
          </View>
        ) : null}
    </SettingsScroll>
  );
}

function LegalSection() {
  // Starts collapsed, the same disclosure as before. Terms and Privacy are
  // the pages the paywall already opens. The Apple EULA stays on the paywall.
  const [helpOpen, setHelpOpen] = useState(false);
  const openHelpline = () => {
    Linking.openURL('tel:1-800-522-4700').catch(() =>
      Alert.alert('Need help?', 'Call or text 1-800-GAMBLER (1-800-522-4700), available 24/7.'),
    );
  };
  const termsHost = TERMS_URL.replace(/^https?:\/\//, '');
  const privacyHost = PRIVACY_URL.replace(/^https?:\/\//, '');
  return (
    <SettingsScroll>
      <View style={styles.groupCard}>
          <Pressable
            onPress={() => setHelpOpen((o) => !o)}
            accessibilityRole="button"
            accessibilityLabel="Gambling help and resources"
            accessibilityState={{ expanded: helpOpen }}
            style={({ pressed }) => [styles.disclosureRow, pressed && styles.pressed]}
          >
            <Text style={[styles.cardLabel, styles.noMargin]}>Gambling help &amp; resources</Text>
            <Ionicons
              name={helpOpen ? 'chevron-up' : 'chevron-down'}
              size={18}
              color={colors.textTertiary}
            />
          </Pressable>
          {helpOpen ? (
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
          ) : null}
        <GroupRow
          label="Terms of Use"
          sub={termsHost}
          onPress={() => openLink(TERMS_URL, 'Terms of Use')}
        />
        <GroupRow
          label="Privacy Policy"
          sub={privacyHost}
          onPress={() => openLink(PRIVACY_URL, 'Privacy Policy')}
        />
      </View>
    </SettingsScroll>
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
 * app's flat units into the member's dollars and sizes nothing. Typing only
 * edits the field (the unit row follows it); blur or Done saves a valid amount,
 * clears on empty, and on invalid keeps the saved amount, shows the error and
 * puts the saved amount back. Every error waits for blur or Done except the
 * over-$10M one, which shows as you type.
 */
function BankrollCard() {
  const { settings, ready, setAmount, stepUnit } = useBankroll();
  const [text, setText] = useState(() => bankrollFieldText(settings.amount));
  const [focused, setFocused] = useState(false);
  const [blurError, setBlurError] = useState<string | null>(null);

  // The stored amount arrives after the first render (AsyncStorage); show it
  // unless the member is mid-edit.
  useEffect(() => {
    if (!focused) setText(bankrollFieldText(settings.amount));
  }, [settings.amount]); // not `focused`: a blur must not undo the text just committed

  const fieldMessage = visibleBankrollError(checkBankroll(text), false) ?? blurError;
  const shown = bankrollDraft(text, settings.unitPct);

  const onChange = (raw: string) => {
    setText(editBankrollInput(text, raw));
    setBlurError(null);
  };

  const commit = () => {
    setFocused(false);
    const c = commitBankrollText(text, settings.amount);
    setText(c.text);
    setBlurError(c.error);
    if (c.save !== undefined) setAmount(c.save);
  };

  // Back can unmount the field without a blur. Save the same way blur does.
  const latest = useRef({ text, amount: settings.amount });
  latest.current = { text, amount: settings.amount };
  const setAmountRef = useRef(setAmount);
  setAmountRef.current = setAmount;
  useEffect(() => {
    return () => {
      const c = commitBankrollText(latest.current.text, latest.current.amount);
      if (c.save !== undefined) setAmountRef.current(c.save);
    };
  }, []);

  return (
    <View style={styles.card}>
      <View style={styles.bookRow}>
        <Text style={[styles.cardLabel, styles.noMargin]}>Your bankroll</Text>
        <Text style={styles.bookPillMuted}>Optional</Text>
      </View>
      <Text style={styles.bookHint}>{BANKROLL_CARD_COPY}</Text>
      <View style={[styles.moneyField, fieldMessage ? styles.moneyFieldError : null]}>
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
      {fieldMessage ? (
        <View style={styles.fieldErrorRow} accessibilityRole="alert" accessibilityLiveRegion="polite">
          <Ionicons name="alert-circle" size={14} color={colors.avoid} />
          <Text style={styles.fieldErrorText}>{fieldMessage}</Text>
        </View>
      ) : null}

      <View style={styles.unitRow}>
        <View style={styles.unitRowText}>
          <Text style={styles.unitRowTitle}>{unitRowTitle(shown)}</Text>
          <Text style={styles.unitRowSub}>{unitRowSubtitle(shown)}</Text>
        </View>
        {/* Disabled until the stored % has loaded, and stepped inside the
            store from the latest value either way. */}
        <LowerRaise
          what={`unit size, now ${formatPct(settings.unitPct)} of bankroll`}
          canLower={ready && canStepUnitPct(settings.unitPct, -1)}
          canRaise={ready && canStepUnitPct(settings.unitPct, 1)}
          onStep={stepUnit}
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
  // Negative margin lets the half-width cells share a 16pt gutter and still
  // line up with the full-width Legal tile.
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginHorizontal: -spacing.sm,
  },
  tileWrap: {
    width: '50%',
    paddingHorizontal: spacing.sm,
    paddingBottom: spacing.md,
  },
  tile: {
    flex: 1,
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    minHeight: 44,
  },
  tileWide: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
    minHeight: 44,
  },
  tileWideText: {
    flex: 1,
  },
  tileTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  tileIcon: {
    width: 36,
    height: 36,
    borderRadius: radii.sm,
    backgroundColor: colors.noneSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tileTitle: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginTop: spacing.sm,
  },
  tileTitleInline: {
    marginTop: 0,
  },
  tileSummary: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: spacing.xs,
    lineHeight: 18,
  },
  groupCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    marginBottom: spacing.md,
    overflow: 'hidden',
  },
  groupRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    padding: spacing.lg,
    minHeight: 44,
  },
  groupRule: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  groupText: {
    flex: 1,
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
    color: colors.textPrimary,
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
  chargeLine: {
    marginTop: spacing.sm,
  },
  connectedLine: {
    marginTop: spacing.md,
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
    color: colors.avoidInk,
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
  // The whole row toggles, at least 44pt tall (HIG), with no extra bottom gap.
  disclosureRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    minHeight: 44,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  helplineRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: spacing.md,
    paddingTop: spacing.md,
    paddingBottom: spacing.md,
    paddingHorizontal: spacing.lg,
    minHeight: 44,
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
    color: colors.betInk,
    fontWeight: font.weight.semibold,
  },
  bookPillMuted: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    fontWeight: font.weight.medium,
  },
  freePill: {
    backgroundColor: colors.noneSoft,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  freePillText: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
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
  manageBtn: {
    marginTop: spacing.md,
    minHeight: 48,
    borderRadius: radii.md,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.brandNavy,
  },
  manageText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textInverse,
  },
  restoreBtn: {
    marginTop: spacing.sm,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  restoreText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  signOutBtn: {
    marginTop: spacing.md,
    minHeight: 44,
    borderRadius: radii.md,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.tintSoft,
  },
  signOutText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  deleteRow: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
    minHeight: 52,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  deleteText: {
    flexShrink: 1,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.avoidInk,
  },
  version: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    textAlign: 'center',
    marginTop: spacing.sm,
  },
});
