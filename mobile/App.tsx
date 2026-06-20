import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

import { PicksScreen } from '@/screens/PicksScreen';
import { SignalsScreen } from '@/screens/SignalsScreen';
import { ParlayScreen } from '@/screens/ParlayScreen';
import { LiveScreen } from '@/screens/LiveScreen';
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
import { SavedParlaysScreen } from '@/screens/SavedParlaysScreen';
import { SettingsScreen } from '@/screens/SettingsScreen';
import { PickDetailScreen } from '@/screens/PickDetailScreen';
import { useParlaySlip } from '@/hooks/useParlaySlip';
import { useOnboarding } from '@/hooks/useOnboarding';
import { OnboardingModal } from '@/components/OnboardingModal';
import { colors } from '@/lib/theme';
import type { RootStackParamList, TabParamList } from '@/types';

const Tab = createBottomTabNavigator<TabParamList>();
const Stack = createNativeStackNavigator<RootStackParamList>();

type IoniconName = React.ComponentProps<typeof Ionicons>['name'];

const TAB_ICONS: Record<keyof TabParamList, IoniconName> = {
  Picks: 'list-outline',
  Signals: 'flash-outline',
  Parlay: 'layers-outline',
  Live: 'radio-outline',
  Performance: 'stats-chart-outline',
  Models: 'construct-outline',
  Stats: 'bar-chart-outline',
  Settings: 'settings-outline',
};

function TabsRoot() {
  const { count } = useParlaySlip();
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
      <Tab.Screen name="Picks" component={PicksScreen} />
      <Tab.Screen name="Signals" component={SignalsScreen} />
      <Tab.Screen
        name="Parlay"
        component={ParlayScreen}
        options={{ tabBarBadge: count > 0 ? count : undefined }}
      />
      <Tab.Screen name="Live" component={LiveScreen} />
      <Tab.Screen name="Performance" component={PerformanceScreen} />
      <Tab.Screen name="Models" component={ModelsScreen} />
      <Tab.Screen name="Stats" component={StatsScreen} />
      <Tab.Screen name="Settings" component={SettingsScreen} />
    </Tab.Navigator>
  );
}

export default function App() {
  const { seen, ready, markSeen } = useOnboarding();
  return (
    <SafeAreaProvider>
      <OnboardingModal visible={ready && !seen} onDone={markSeen} />
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
            name="TrackRecord"
            component={TrackRecordScreen}
            options={{ title: 'Track Record', headerBackTitle: 'Back' }}
          />
          <Stack.Screen
            name="OpeningComparison"
            component={OpeningComparisonScreen}
            options={{ title: 'Opening vs Live', headerBackTitle: 'Back' }}
          />
          <Stack.Screen
            name="SavedParlays"
            component={SavedParlaysScreen}
            options={{ title: 'Saved Parlays', headerBackTitle: 'Back' }}
          />
        </Stack.Navigator>
        <StatusBar style="auto" />
      </NavigationContainer>
    </SafeAreaProvider>
  );
}
