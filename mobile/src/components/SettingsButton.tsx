// SettingsButton — a top-right gear that opens the Settings stack screen.
//
// Settings used to be a bottom tab; it now lives in the top-right of each tab
// screen's header (freeing a tab slot for Live). Drop this in as the rightmost
// element of a screen's header row.

import React from 'react';
import { Pressable, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { colors } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

export function SettingsButton() {
  const navigation = useNavigation<Nav>();
  return (
    <Pressable
      onPress={() => navigation.navigate('Settings')}
      hitSlop={8}
      accessibilityLabel="Open settings"
      accessibilityRole="button"
      style={({ pressed }) => [styles.btn, pressed && { opacity: 0.6 }]}
    >
      <Ionicons name="settings-outline" size={22} color={colors.textSecondary} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: { padding: 4 },
});
