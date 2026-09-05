import 'react-native-gesture-handler';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import {
  DefaultTheme,
  NavigationContainer,
  useNavigationContainerRef,
} from '@react-navigation/native';
import { View } from 'react-native';
import { BottomTabBar, createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

import { PicksHomeScreen } from '@/screens/PicksHomeScreen';
import { LiveScreen } from '@/screens/LiveScreen';
import { ParlayScreen } from '@/screens/ParlayScreen';
import { SavedParlaysScreen } from '@/screens/SavedParlaysScreen';
import { PerformanceScreen } from '@/screens/PerformanceScreen';
import { ModelsScreen } from '@/screens/ModelsScreen';
import { ModelEditScreen } from '@/screens/ModelEditScreen';
import { ModelDetailScreen } from '@/screens/ModelDetailScreen';
import { BuiltInModelDetailScreen } from '@/screens/BuiltInModelDetailScreen';
import { StatsScreen } from '@/screens/StatsScreen';
import { PlayerStatsScreen } from '@/screens/PlayerStatsScreen';
import { ExplainerScreen } from '@/screens/ExplainerScreen';
import { ConnectSportsbookScreen } from '@/screens/ConnectSportsbookScreen';
import { TrackRecordScreen } from '@/screens/TrackRecordScreen';
import { OpeningComparisonScreen } from '@/screens/OpeningComparisonScreen';
import { SettingsScreen } from '@/screens/SettingsScreen';
import { SignInScreen } from '@/screens/SignInScreen';
import { PaywallScreen } from '@/screens/PaywallScreen';
import { PickDetailScreen } from '@/screens/PickDetailScreen';
import { FeedbackScreen } from '@/screens/FeedbackScreen';
import { FeedbackThreadScreen } from '@/screens/FeedbackThreadScreen';
import { useOnboarding } from '@/hooks/useOnboarding';
import { useActionThresholds } from '@/hooks/useActionThresholds';
import { useModelClvPedigree } from '@/hooks/useModelClvPedigree';
import { usePushNotifications } from '@/hooks/usePushNotifications';
import { useOtaUpdates } from '@/hooks/useOtaUpdates';
import { useDailyResults } from '@/hooks/useDailyResults';
import { useDailyRecapControl } from '@/hooks/useDailyRecapControl';
import { OnboardingModal } from '@/components/OnboardingModal';
import { DailyResultsModal } from '@/components/DailyResultsModal';
import { RESULTS_MIN_DATE } from '@/lib/dailyResults';
import { addDays, todayET } from '@/lib/format';
import { ToastHost } from '@/components/Toast';
import { BetslipBar } from '@/components/BetslipBar';
import {
  FALLBACK_TAB_BAR_HEIGHT,
  setTabBarHeight,
  useTabBarHeight,
} from '@/hooks/useTabBarHeight';
import { colors } from '@/lib/theme';
import type { RootStackParamList, TabParamList } from '@/types';

const Tab = createBottomTabNavigator<TabParamList>();
const Stack = createNativeStackNavigator<RootStackParamList>();

type IoniconName = React.ComponentProps<typeof Ionicons>['name'];

const TAB_ICONS: Record<keyof TabParamList, IoniconName> = {
  Picks: 'list-outline',
  Live: 'radio-outline',
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
const NO_BETSLIP_BAR_ROUTES = new Set<string>(['Betslip', 'SignIn', 'Paywall']);

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

function TabsRoot() {
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
      <Tab.Screen name="Picks" component={PicksHomeScreen} />
      <Tab.Screen name="Live" component={LiveScreen} />
      <Tab.Screen
        name="TrackRecord"
        component={TrackRecordScreen}
        options={{ title: 'Record' }}
      />
      <Tab.Screen name="Performance" component={PerformanceScreen} />
      <Tab.Screen name="Models" component={ModelsScreen} />
      <Tab.Screen name="Stats" component={StatsScreen} />
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

export default function App() {
  const { seen, ready, markSeen } = useOnboarding();
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
  const tabBarHeight = useTabBarHeight();
  const syncRoute = useCallback(() => {
    setRouteName(navRef.getCurrentRoute()?.name);
  }, [navRef]);
  const openBetslip = useCallback(() => {
    navRef.navigate('Betslip');
  }, [navRef]);
  const overTabs = routeName != null && TAB_ROUTE_NAMES.has(routeName);

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
    <SafeAreaProvider>
      <OnboardingModal visible={ready && !seen} onDone={markSeen} />
      <DailyRecap onboardingDone={ready && seen} />
      <NavigationContainer
        ref={navRef}
        theme={NAV_THEME}
        onReady={syncRoute}
        onStateChange={syncRoute}
      >
        <Stack.Navigator>
          <Stack.Screen name="Tabs" component={TabsRoot} options={{ headerShown: false }} />
          <Stack.Screen
            name="PickDetail"
            component={PickDetailScreen}
            options={{ title: 'Pick Detail', headerBackTitle: 'Back' }}
          />
          <Stack.Screen
            name="ModelEdit"
            component={ModelEditScreen}
            options={{ title: 'Model', headerBackTitle: 'Back' }}
          />
          <Stack.Screen
            name="ModelDetail"
            component={ModelDetailScreen}
            options={{ title: 'Model', headerBackTitle: 'Back' }}
          />
          <Stack.Screen
            name="BuiltInModelDetail"
            component={BuiltInModelDetailScreen}
            options={{ title: 'Model', headerBackTitle: 'Back' }}
          />
          <Stack.Screen
            name="PlayerStats"
            component={PlayerStatsScreen}
            options={{ title: 'Player Stats', headerBackTitle: 'Back' }}
          />
          <Stack.Screen
            name="Explainer"
            component={ExplainerScreen}
            options={{ title: 'How this works', headerBackTitle: 'Back' }}
          />
          <Stack.Screen
            name="ConnectSportsbook"
            component={ConnectSportsbookScreen}
            options={{ title: 'Connect Sportsbook', headerBackTitle: 'Back' }}
          />
          <Stack.Screen
            name="Settings"
            component={SettingsScreen}
            options={{ title: 'Settings', headerBackTitle: 'Back' }}
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
            component={SavedParlaysScreen}
            options={{ title: 'Saved Parlays', headerBackTitle: 'Back' }}
          />
          {/* No UI navigates here since the Track Record link was removed
              (2026-09-05). The opening-signal shadow track still runs
              server-side; the route is kept so the screen stays compiled. */}
          <Stack.Screen
            name="OpeningComparison"
            component={OpeningComparisonScreen}
            options={{ title: 'Opening vs Live', headerBackTitle: 'Back' }}
          />
          <Stack.Screen
            name="Feedback"
            component={FeedbackScreen}
            options={{ title: 'Feedback', headerBackTitle: 'Back' }}
          />
          <Stack.Screen
            name="FeedbackThread"
            component={FeedbackThreadScreen}
            options={{ title: 'Conversation', headerBackTitle: 'Back' }}
          />
          {/* Auth is behind AUTH_ENABLED (lib/authConfig.ts). Registering the
              route costs nothing while the flag is off — no UI navigates to it
              — and keeps the screen compiled so it can't rot. */}
          <Stack.Screen
            name="SignIn"
            component={SignInScreen}
            options={{ title: 'Sign in', headerBackTitle: 'Back' }}
          />
          {/* Paywall is behind BILLING_ENABLED (lib/billingConfig.ts). Same
              posture as SignIn — registered, but nothing navigates to it while
              the flag is off. */}
          <Stack.Screen
            name="Paywall"
            component={PaywallScreen}
            options={{ title: 'Subscribe', headerBackTitle: 'Back' }}
          />
        </Stack.Navigator>
        <StatusBar style="auto" />
      </NavigationContainer>
      <BetslipBar
        hidden={routeName == null || NO_BETSLIP_BAR_ROUTES.has(routeName)}
        bottomOffset={overTabs ? tabBarHeight || FALLBACK_TAB_BAR_HEIGHT : 0}
        onOpen={openBetslip}
      />
      <ToastHost />
    </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
