// SettingsButton — a top-right gear that opens the Settings stack screen.
//
// Settings used to be a bottom tab; it now lives in the top-right of each tab
// screen's header (freeing a tab slot for Live). Drop this in as the rightmost
// element of a screen's header row.
//
// The notifications bell rides with it (Matt, 2026-11-14), so every screen
// that has the gear has the bell beside it, in one flex child, without
// touching eight different header layouts.

import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { NotificationsButton } from '@/components/NotificationsButton';
import { colors, opacity, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

export function SettingsButton() {
  const navigation = useNavigation<Nav>();
  return (
    <View style={styles.row}>
    <NotificationsButton />
    <Pressable
      onPress={() => navigation.navigate('Settings')}
      hitSlop={8}
      accessibilityLabel="Open settings"
      accessibilityRole="button"
      style={({ pressed }) => [styles.btn, pressed && { opacity: opacity.pressed }]}
    >
      <Ionicons name="settings-outline" size={22} color={colors.textSecondary} />
    </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  btn: { padding: 4 },
});
