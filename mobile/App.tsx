import 'react-native-gesture-handler';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import {
  DefaultTheme,
  getFocusedRouteNameFromRoute,
  NavigationContainer,
  useNavigation,
  useNavigationContainerRef,
} from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { ActivityIndicator, View } from 'react-native';
import { BottomTabBar, createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { initialWindowMetrics, SafeAreaProvider } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

import { PicksHomeScreen } from '@/screens/PicksHomeScreen';
import { ParlayScreen } from '@/screens/ParlayScreen';
import { SavedParlaysScreen } from '@/screens/SavedParlaysScreen';
import { PerformanceScreen } from '@/screens/PerformanceScreen';
import { ModelsScreen } from '@/screens/ModelsScreen';
import { ModelEditScreen } from '@/screens/ModelEditScreen';
import { ModelDetailScreen } from '@/screens/ModelDetailScreen';
import { BuiltInModelDetailScreen } from '@/screens/BuiltInModelDetailScreen';
import { ByomBuilderScreen } from '@/screens/ByomBuilderScreen';
import { ByomEditScreen } from '@/screens/ByomEditScreen';
import { ByomBetsScreen } from '@/screens/ByomBetsScreen';
import { ByomDetailScreen } from '@/screens/ByomDetailScreen';
import { StatsScreen } from '@/screens/StatsScreen';
import { PlayerStatsScreen } from '@/screens/PlayerStatsScreen';
import { TeamStatsScreen } from '@/screens/TeamStatsScreen';
import { ExplainerScreen } from '@/screens/ExplainerScreen';
import { ConnectSportsbookScreen } from '@/screens/ConnectSportsbookScreen';
import { TrackRecordScreen } from '@/screens/TrackRecordScreen';
import { OpeningComparisonScreen } from '@/screens/OpeningComparisonScreen';
import { SettingsScreen, SettingsSectionScreen } from '@/screens/SettingsScreen';
import { DeleteAccountScreen } from '@/screens/DeleteAccountScreen';
import { SignInScreen } from '@/screens/SignInScreen';
import { PaywallScreen } from '@/screens/PaywallScreen';
import { PickDetailScreen } from '@/screens/PickDetailScreen';
import { ScoreboardGameScreen } from '@/screens/ScoreboardGameScreen';
import { FeedbackScreen } from '@/screens/FeedbackScreen';
import { FeedbackThreadScreen } from '@/screens/FeedbackThreadScreen';
import { useOnboarding } from '@/hooks/useOnboarding';
import { usePreferredBooks } from '@/hooks/usePreferredBooks';
import { useActionThresholds } from '@/hooks/useActionThresholds';
import { useModelClvPedigree } from '@/hooks/useModelClvPedigree';
import { usePushNotifications } from '@/hooks/usePushNotifications';
import { useOtaUpdates } from '@/hooks/useOtaUpdates';
import { usePushDeepLink } from '@/hooks/usePushDeepLink';
import { installNotificationHandler } from '@/lib/pushPresentation';
import { startCrashLogging } from '@/lib/crashLogSetup';
import { setCrashScreen } from '@/lib/crashLog';
import { noteScreen, noteTouch } from '@/lib/freezeLog';
import { startFreezeLogging } from '@/lib/freezeLogSetup';
import { sentryReadyNow, setSentryScreen, startSentry, wrapWithSentry } from '@/lib/sentry';
import { startPerfLogging } from '@/lib/perfLogSetup';
import { setPerfScreen } from '@/lib/perfLog';
import { AppErrorBoundary } from '@/components/AppErrorBoundary';
import { useDailyResults } from '@/hooks/useDailyResults';
import { useDailyRecapControl } from '@/hooks/useDailyRecapControl';
import { OnboardingModal } from '@/components/OnboardingModal';
import { DailyResultsModal } from '@/components/DailyResultsModal';
import { RESULTS_MIN_DATE } from '@/lib/dailyResults';
import { addDays, todayET } from '@/lib/format';
import { ToastHost } from '@/components/Toast';
import { BetslipBar } from '@/components/BetslipBar';
import {
  PlayerStatsBackButton,
  SettingsSectionBackButton,
  SettingsSectionHeaderTitle,
} from '@/components/StackBackButton';
import { SETTINGS_SECTION_TITLE } from '@/lib/settingsHome';
import {
  FALLBACK_TAB_BAR_HEIGHT,
  setTabBarHeight,
  useTabBarHeight,
} from '@/hooks/useTabBarHeight';
import { FeatureGate } from '@/components/FeatureGate';
import { readAuthStatus, useAuth } from '@/hooks/useAuth';
import { useMembership } from '@/hooks/useMembership';
import { AUTH_ENABLED } from '@/lib/authConfig';
import { signedOutRouteIsShell } from '@/lib/authShell';
import { colors } from '@/lib/theme';
import type { RootStackParamList, TabParamList } from '@/types';

const Tab = createBottomTabNavigator<TabParamList>();
const Stack = createNativeStackNavigator<RootStackParamList>();

type IoniconName = React.ComponentProps<typeof Ionicons>['name'];

const TAB_ICONS: Record<keyof TabParamList, IoniconName> = {
  Picks: 'list-outline',
  TrackRecord: 'shield-checkmark-outline',
  Performance: 'stats-chart-outline',
  Models: 'construct-outline',
  Stats: 'bar-chart-outline',
};

/** Routes that sit under the tab bar — the betslip bar has to clear it there. */
const TAB_ROUTE_NAMES = new Set<string>(Object.keys(TAB_ICONS));

/**
 * Screens the betslip bar stays off: the Betslip screen itself (it IS the
 * slip), and the two flag-gated full-screen flows where a floating shortcut
 * would be noise.
 */
const NO_BETSLIP_BAR_ROUTES = new Set<string>(['Betslip', 'SignIn', 'Paywall', 'DeleteAccount']);

/**
 * Stack headers (back chevron, "Back") otherwise keep React Navigation's
 * default iOS blue — a third interactive colour beside the amber tab bar and
 * the navy controls. One theme, from the tokens.
 */
const NAV_THEME = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    primary: colors.tint,
    background: colors.bg,
    card: colors.bgCard,
    text: colors.textPrimary,
    border: colors.separatorOpaque,
    notification: colors.avoid,
  },
};

function withPremiumGate(
  Screen: React.ComponentType,
  heading: string,
  chrome: boolean,
) {
  function Gated() {
    return (
      <FeatureGate heading={heading} chrome={chrome}>
        <Screen />
      </FeatureGate>
    );
  }
  Gated.displayName = `PremiumGate(${heading})`;
  return Gated;
}

const GatedPerformance = withPremiumGate(PerformanceScreen, 'Performance', true);
const GatedModels = withPremiumGate(ModelsScreen, 'Models', true);
const GatedStats = withPremiumGate(StatsScreen, 'Stats', true);
const GatedPickDetail = withPremiumGate(PickDetailScreen, 'Pick', false);
const GatedScoreboardGame = withPremiumGate(ScoreboardGameScreen, 'Game', false);
const GatedModelEdit = withPremiumGate(ModelEditScreen, 'Model', false);
const GatedModelDetail = withPremiumGate(ModelDetailScreen, 'Model', false);
const GatedBuiltInModel = withPremiumGate(BuiltInModelDetailScreen, 'Model', false);
const GatedByomBuilder = withPremiumGate(ByomBuilderScreen, 'Model', false);
const GatedByomEdit = withPremiumGate(ByomEditScreen, 'Model', false);
const GatedByomDetail = withPremiumGate(ByomDetailScreen, 'Model', false);
const GatedByomBets = withPremiumGate(ByomBetsScreen, 'Model', false);
const GatedPlayerStats = withPremiumGate(PlayerStatsScreen, 'Stats', false);
const GatedTeamStats = withPremiumGate(TeamStatsScreen, 'Stats', false);
const GatedSavedParlays = withPremiumGate(SavedParlaysScreen, 'Parlays', false);

function TabsRoot() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { contentLocked } = useMembership();
  const lockedTab = {
    tabPress: () => {
      if (contentLocked) navigation.navigate('Paywall');
    },
  };
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        // The brand chrome: the banner's navy with the mark's amber for the
        // active tab. Amber only ever sits on navy (theme.ts, Brand).
        tabBarActiveTintColor: colors.brand,
        tabBarInactiveTintColor: colors.brandMuted,
        tabBarStyle: {
          backgroundColor: colors.brandNavy,
          borderTopColor: colors.brandSeparator,
        },
        tabBarIcon: ({ color, size }) => (
          <Ionicons name={TAB_ICONS[route.name]} color={color} size={size} />
        ),
      })}
      // The stock tab bar, wrapped only to publish its measured height: the
      // betslip bar floats directly above it and is mounted at the app root,
      // where useBottomTabBarHeight() isn't available.
      tabBar={(props) => (
        <View onLayout={(e) => setTabBarHeight(e.nativeEvent.layout.height)}>
          <BottomTabBar {...props} />
        </View>
      )}
    >
      {/* Picks stays on the free shell: the teaser, not the paywall. Signals
          and Live Signals open the paywall from inside that screen. */}
      <Tab.Screen name="Picks" component={PicksHomeScreen} />
      <Tab.Screen
        name="TrackRecord"
        component={TrackRecordScreen}
        options={{ title: 'Record' }}
      />
      <Tab.Screen name="Performance" component={GatedPerformance} listeners={lockedTab} />
      <Tab.Screen name="Models" component={GatedModels} listeners={lockedTab} />
      <Tab.Screen name="Stats" component={GatedStats} listeners={lockedTab} />
    </Tab.Navigator>
  );
}

/**
 * Owns the daily-results recap: the selected day (defaults to yesterday), its
 * picks fetch, and the once/day auto-pop gate. Mounted once at the root so the
 * auto-pop and the Track Record calendar button drive the same modal. Every
 * open snaps back to yesterday AND refetches — the launch-time fetch can be
 * stale (settlement lands ~7am ET while the app sits in memory) or error-stuck,
 * which previously left the recap permanently empty.
 */
function DailyRecap({ onboardingDone }: { onboardingDone: boolean }) {
  const { visible, autoEligible, close, consumeAuto } = useDailyRecapControl();
  const [date, setDate] = useState(() => addDays(todayET(), -1));
  const [reloadToken, setReloadToken] = useState(0);
  const { results, loading, error } = useDailyResults(date, reloadToken);

  // Auto-pop once/day, only for yesterday's results (the default date).
  useEffect(() => {
    if (
      autoEligible &&
      onboardingDone &&
      !loading &&
      results.date === addDays(todayET(), -1) &&
      results.overall.picks > 0
    ) {
      consumeAuto();
    }
  }, [autoEligible, onboardingDone, loading, results, consumeAuto]);

  const wasVisible = useRef(false);
  useEffect(() => {
    if (visible && !wasVisible.current) {
      setDate(addDays(todayET(), -1));
      setReloadToken((t) => t + 1);
    }
    wasVisible.current = visible;
  }, [visible]);

  return (
    <DailyResultsModal
      visible={visible}
      onClose={close}
      date={date}
      minDate={RESULTS_MIN_DATE}
      maxDate={addDays(todayET(), -1)}
      onSelectDate={setDate}
      results={results}
      loading={loading}
      error={error}
    />
  );
}

// Module scope, so it is in place before any screen mounts and before a
// notification that launched the app is handed over.
installNotificationHandler();
// Same reason: catch an error from the first render, and record how the
// previous launch ended before this one can overwrite the marker.
// Sentry first: native crashes and iOS app hangs (lib/sentry.ts). When the
// device id is already on disk, init happens in this turn and the other
// loggers follow immediately. The first launch of a build with a DSN waits
// for AsyncStorage, then inits, so the first event already carries the id
// the crash log uses. An empty DSN skips init and the other loggers still
// start in this turn. The crash log wraps the JS error handler, so both see
// every error.
function startOtherLoggers(): void {
  startCrashLogging();
  // Freeze tracking: a trail of screens, taps and pop-ups on every report, and
  // a `restart` report when the last session looks force-quit (lib/freezeLog.ts).
  startFreezeLogging();
  // Load times: the first screen is timed from here (lib/perfLog.ts).
  startPerfLogging();
}
const sentryStarting = startSentry();
if (sentryReadyNow()) startOtherLoggers();
else void sentryStarting.then(startOtherLoggers);

function App() {
  const { seen, ready, markSeen } = useOnboarding();
  const { ready: authReady, signedIn } = useAuth();
  // A member who saw the intro before the sportsbook step existed gets that
  // step on its own, once (OnboardingModal booksOnly).
  const { needsChoice: needsBooks } = usePreferredBooks();
  useActionThresholds(); // hydrate live action thresholds from model_action_thresholds
  useModelClvPedigree(); // hydrate per-model CLV pedigree for the Sharp Score
  usePushNotifications(); // register push token when user opts in
  // Pull and apply published JS bundles at launch and on foreground. Without
  // this an installed build sits on whatever bundle it launched with until
  // someone force-quits it, so a merged fix can go undelivered for days.
  useOtaUpdates();

  // The betslip bar lives OUTSIDE the navigator so one instance covers every
  // screen (tabs and pushed alike). It therefore needs the container ref to
  // navigate, and the focused route name to know where it's floating.
  const navRef = useNavigationContainerRef<RootStackParamList>();
  const [routeName, setRouteName] = useState<string | undefined>(undefined);
  const [navReady, setNavReady] = useState(false);
  const tabBarHeight = useTabBarHeight();
  const syncRoute = useCallback(() => {
    const name = navRef.getCurrentRoute()?.name;
    setCrashScreen(name);
    noteScreen(name);
    setSentryScreen(name);
    setPerfScreen(name);
    setRouteName(name);
  }, [navRef]);
  // Retry after a crash remounts the navigator; onReady sets this back, and
  // usePushDeepLink replays a pending notification route when it does.
  const resetNav = useCallback(() => setNavReady(false), []);
  const onNavReady = useCallback(() => {
    setNavReady(true);
    syncRoute();
  }, [syncRoute]);

  // Send a tapped notification to the pick or board it is about. Mounted here,
  // beside the container ref it navigates with — the same reason BetslipBar is
  // out here. Covers the tap that LAUNCHES the app, not just the one that
  // arrives while it is already running.
  usePushDeepLink(navRef, navReady);
  const openBetslip = useCallback(() => {
    navRef.navigate('Betslip');
  }, [navRef]);
  const overTabs = routeName != null && TAB_ROUTE_NAMES.has(routeName);
  const authHold = AUTH_ENABLED && !authReady;
  const signedOut = AUTH_ENABLED && authReady && !signedIn;
  // The paywall is the first screen after a fresh sign-in. The intro and the
  // daily recap are modals, so they would cover it. Hold both until Close.
  const holdIntro = routeName === 'Paywall' || routeName === 'SignIn';

  // Auth on: the shell is unreachable signed out. Read the module status, not
  // the React copy — a sign-in updates the module before this render, and a
  // reset here would throw that sign-in back to SignIn. routeName re-runs
  // this after a push deep link or any other navigation off SignIn.
  useEffect(() => {
    if (!AUTH_ENABLED || !navReady) return;
    if (readAuthStatus() !== 'signedOut') return;
    if (!signedOutRouteIsShell(navRef.getCurrentRoute()?.name)) return;
    navRef.reset({ index: 0, routes: [{ name: 'SignIn' }] });
  }, [signedOut, navReady, navRef, routeName]);

  return (
    // onTouchStart only records the tap (freezeLog); it never claims it.
    <GestureHandlerRootView style={{ flex: 1 }} onTouchStart={noteTouch}>
    <SafeAreaProvider initialMetrics={initialWindowMetrics}>
    <AppErrorBoundary onReset={resetNav}>
      <OnboardingModal
        visible={ready && (!seen || needsBooks) && (!AUTH_ENABLED || signedIn) && !holdIntro}
        booksOnly={seen && needsBooks}
        onDone={markSeen}
      />
      <DailyRecap onboardingDone={ready && seen && !needsBooks && (!AUTH_ENABLED || signedIn) && !holdIntro} />
      {authHold ? (
        <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator color={colors.tint} />
        </View>
      ) : (
      <NavigationContainer
        ref={navRef}
        theme={NAV_THEME}
        onReady={onNavReady}
        onStateChange={syncRoute}
      >
        <Stack.Navigator
          initialRouteName={signedOut ? 'SignIn' : 'Tabs'}
          // ARROW-ONLY BACK BUTTON, NO CUSTOM LABEL (Matt, 2026-11-08). On iOS
          // 27.2 the native Back stopped responding after a pop-up had been
          // opened on the screen: Settings twice, then Player Stats after
          // Compare odds. The freeze trail showed no stuck pop-up and no JS
          // stall, only taps that went nowhere. Apple's reported iOS 27 bug is a
          // Back button carrying a custom title; its workaround is this mode.
          // So no screen sets headerBackTitle (tests/test_mobile_back_button.py).
          screenOptions={{ headerBackButtonDisplayMode: 'minimal' }}
        >
          <Stack.Screen
            name="Tabs"
            component={TabsRoot}
            // With the arrow-only Back, iOS's long-press Back menu lists the
            // earlier screen by its title. Without one it would read "Tabs".
            // It names the tab the reader came from (UX review, 2026-11-08).
            options={({ route }) => {
              const tab = getFocusedRouteNameFromRoute(route) ?? 'Picks';
              return { headerShown: false, title: tab === 'TrackRecord' ? 'Record' : tab };
            }}
          />
          <Stack.Screen
            name="PickDetail"
            component={GatedPickDetail}
            options={{ title: 'Pick Detail' }}
          />
          <Stack.Screen
            name="ScoreboardGame"
            component={GatedScoreboardGame}
            options={{ title: 'Game' }}
          />
          <Stack.Screen
            name="ModelEdit"
            component={GatedModelEdit}
            options={{ title: 'Model' }}
          />
          <Stack.Screen
            name="ModelDetail"
            component={GatedModelDetail}
            options={{ title: 'Model' }}
          />
          <Stack.Screen
            name="BuiltInModelDetail"
            component={GatedBuiltInModel}
            options={{ title: 'Model' }}
          />
          <Stack.Screen
            name="ByomBuilder"
            component={GatedByomBuilder}
            options={({ route }) => ({
              title: route.params?.sport === 'NBA' ? 'New NBA model' : 'New NFL model',
            })}
          />
          <Stack.Screen
            name="ByomEdit"
            component={GatedByomEdit}
            options={{ title: 'Edit model' }}
          />
          <Stack.Screen
            name="ByomDetail"
            component={GatedByomDetail}
            options={{ title: 'Model' }}
          />
          <Stack.Screen
            name="ByomBets"
            component={GatedByomBets}
            options={{ title: 'Bets' }}
          />
          {/* JS Back pill, not UIKit's. On iOS 27 the system "< Back" pill
              stops popping after a modal on this screen (Compare odds).
              react-native-screens 4.16 also measures that pill from the
              pre-iOS 26 button frame, so it sits under the status bar.
              This screen's left slot is our pressable, in the header the
              stack already insets (SafeAreaProvider is seeded with
              initialWindowMetrics so that inset is not 0 on the first frame).
              gestureEnabled is the edge swipe. Full-screen swipe stays off:
              the stat and range rows are horizontal scrolls. */}
          <Stack.Screen
            name="PlayerStats"
            component={GatedPlayerStats}
            options={{
              title: 'Player Stats',
              headerShown: true,
              headerTransparent: false,
              headerBackVisible: false,
              gestureEnabled: true,
              fullScreenGestureEnabled: false,
              headerLeft: () => <PlayerStatsBackButton />,
            }}
          />
          <Stack.Screen
            name="TeamStats"
            component={GatedTeamStats}
            options={{ title: 'Team' }}
          />
          <Stack.Screen
            name="Explainer"
            component={ExplainerScreen}
            options={{ title: 'How this works' }}
          />
          <Stack.Screen
            name="ConnectSportsbook"
            component={ConnectSportsbookScreen}
            options={{ title: 'Connect Sportsbook' }}
          />
          <Stack.Screen
            name="Settings"
            component={SettingsScreen}
            options={{ title: 'Settings' }}
          />
          {/* Chevron + "Back" (#1239), same pill as Player Stats. Settings
              itself keeps the arrow-only system back from screenOptions. */}
          <Stack.Screen
            name="SettingsSection"
            component={SettingsSectionScreen}
            options={({ route }) => {
              const section = route.params?.section;
              const title =
                section && section in SETTINGS_SECTION_TITLE
                  ? SETTINGS_SECTION_TITLE[section]
                  : 'Settings';
              return {
                title,
                headerBackVisible: false,
                gestureEnabled: true,
                headerTitle: (props) => <SettingsSectionHeaderTitle {...props} />,
                headerLeft: () => <SettingsSectionBackButton />,
              };
            }}
          />
          <Stack.Screen
            name="DeleteAccount"
            component={DeleteAccountScreen}
            options={{ title: 'Delete account' }}
          />
          {/* The betslip renders its own header (close chevron, saved parlays,
              settings) so it reads like the sheet it is — hence headerShown
              false. Reached from the betslip bar, or from Stats/Saved. */}
          <Stack.Screen
            name="Betslip"
            component={ParlayScreen}
            options={{ headerShown: false }}
          />
          <Stack.Screen
            name="SavedParlays"
            component={GatedSavedParlays}
            options={{ title: 'Saved Parlays' }}
          />
          {/* No UI navigates here since the Track Record link was removed
              (2026-09-05). The opening-signal shadow track still runs
              server-side; the route is kept so the screen stays compiled. */}
          <Stack.Screen
            name="OpeningComparison"
            component={OpeningComparisonScreen}
            options={{ title: 'Opening vs Live' }}
          />
          <Stack.Screen
            name="Feedback"
            component={FeedbackScreen}
            options={{ title: 'Feedback' }}
          />
          <Stack.Screen
            name="FeedbackThread"
            component={FeedbackThreadScreen}
            options={{ title: 'Conversation' }}
          />
          {/* Auth is behind AUTH_ENABLED (lib/authConfig.ts). Registering the
              route costs nothing while the flag is off — no UI navigates to it
              — and keeps the screen compiled so it can't rot. */}
          <Stack.Screen
            name="SignIn"
            component={SignInScreen}
            options={{ headerShown: false, gestureEnabled: false }}
          />
          {/* Paywall is behind BILLING_ENABLED (lib/billingConfig.ts). Same
              posture as SignIn — registered, but nothing navigates to it while
              the flag is off. */}
          <Stack.Screen
            name="Paywall"
            component={PaywallScreen}
            options={{ headerShown: false, title: 'Subscribe' }}
          />
        </Stack.Navigator>
        <StatusBar style="auto" />
      </NavigationContainer>
      )}
      <BetslipBar
        hidden={routeName == null || NO_BETSLIP_BAR_ROUTES.has(routeName)}
        bottomOffset={overTabs ? tabBarHeight || FALLBACK_TAB_BAR_HEIGHT : 0}
        onOpen={openBetslip}
      />
      <ToastHost />
    </AppErrorBoundary>
    </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

export default wrapWithSentry(App);
