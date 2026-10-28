import React from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { SafeAreaView } from 'react-native-safe-area-context';

import { SettingsButton } from '@/components/SettingsButton';
import { SignalLockCard } from '@/components/SignalLockCard';
import { useMembership } from '@/hooks/useMembership';
import { colors, font, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

/**
 * Free members see the lock instead of the screen. Trial and paid see the
 * screen. While billing is dark this renders the child, so the flag-off app
 * is unchanged.
 *
 * Tabs pass chrome (they have no stack header). Pushed screens leave chrome
 * off — the stack header already has Back.
 */
export function FeatureGate({
  heading,
  chrome = true,
  children,
}: {
  heading: string;
  chrome?: boolean;
  children: React.ReactNode;
}) {
  const navigation = useNavigation<Nav>();
  const { contentLocked, hold } = useMembership();

  if (hold) {
    return (
      <SafeAreaView style={styles.fill} edges={chrome ? ['top'] : []}>
        <ActivityIndicator color={colors.tint} style={styles.spinner} />
      </SafeAreaView>
    );
  }
  if (!contentLocked) return <>{children}</>;

  return (
    <SafeAreaView style={styles.fill} edges={chrome ? ['top'] : []}>
      {chrome ? (
        <View style={styles.header}>
          {navigation.canGoBack() ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Back"
              onPress={() => navigation.goBack()}
              hitSlop={8}
              style={styles.back}
            >
              <Ionicons name="chevron-back" size={26} color={colors.tint} />
            </Pressable>
          ) : null}
          <Text style={styles.heading}>{heading}</Text>
          <SettingsButton />
        </View>
      ) : null}
      <SignalLockCard
        title="Included with Premium"
        onPress={() => navigation.navigate('Paywall')}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1, backgroundColor: colors.bg },
  spinner: { marginTop: spacing.xxl },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  heading: {
    flex: 1,
    fontFamily: font.family,
    fontSize: font.size.largeTitle,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  back: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
