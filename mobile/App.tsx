import 'react-native-gesture-handler';
import React, { useEffect, useRef, useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
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
import { useParlaySlip } from '@/hooks/useParlaySlip';
import { useActionThresholds } from '@/hooks/useActionThresholds';
import { useModelClvPedigree } from '@/hooks/useModelClvPedigree';
import { usePushNotifications } from '@/hooks/usePushNotifications';
import { useDailyResults } from '@/hooks/useDailyResults';
import { useDailyRecapControl } from '@/hooks/useDailyRecapControl';
import { OnboardingModal } from '@/components/OnboardingModal';
import { DailyResultsModal } from '@/components/DailyResultsModal';
import { RESULTS_MIN_DATE } from '@/lib/dailyResults';
import { addDays, todayET } from '@/lib/format';
import { ToastHost } from '@/components/Toast';
import { colors } from '@/lib/theme';
import type { RootStackParamList, TabParamList } from '@/types';

const Tab = createBottomTabNavigator<TabParamList>();
const Stack = createNativeStackNavigator<RootStackParamList>();

type IoniconName = React.ComponentProps<typeof Ionicons>['name'];

const TAB_ICONS: Record<keyof TabParamList, IoniconName> = {
  Picks: 'list-outline',
  Live: 'radio-outline',
  TrackRecord: 'shield-checkmark-outline',
  Parlay: 'receipt-outline',
  Performance: 'stats-chart-outline',
  Models: 'construct-outline',
  Stats: 'bar-chart-outline',
};

function TabsRoot() {
  // Slip-count badge on the Betslip tab — legs added anywhere ("Add to betslip"
  // on Stats rows, pick cards, pick detail) show up here immediately.
  const slip = useParlaySlip();
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarActiveTintColor: colors.tint,
        tabBarInactiveTintColor: colors.textTertiary,
        tabBarStyle: { backgroundColor: colors.bgCard },
        tabBarIcon: ({ color, size }) => (
          <Ionicons name={TAB_ICONS[route.name]} color={color} size={size} />
        ),
      })}
    >
      <Tab.Screen name="Picks" component={PicksHomeScreen} />
      <Tab.Screen name="Live" component={LiveScreen} />
      <Tab.Screen
        name="Parlay"
        component={ParlayScreen}
        options={{
          title: 'Betslip',
          tabBarBadge: slip.count > 0 ? slip.count : undefined,
        }}
      />
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
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
    <SafeAreaProvider>
      <OnboardingModal visible={ready && !seen} onDone={markSeen} />
      <DailyRecap onboardingDone={ready && seen} />
      <NavigationContainer>
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
          <Stack.Screen
            name="SavedParlays"
            component={SavedParlaysScreen}
            options={{ title: 'Saved Parlays', headerBackTitle: 'Back' }}
          />
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
      <ToastHost />
    </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
