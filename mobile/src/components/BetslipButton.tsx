// BetslipButton — a top-right receipt icon that opens the Betslip screen.
//
// The betslip is no longer a tab, and the persistent betslip bar only appears
// once something is IN the slip. This is the way in when it's empty — without
// it the parlay optimizer and the same-game finder would be unreachable until
// the user had already added a leg by hand.
//
// Drop it in beside SettingsButton in a screen's header row.

import React from 'react';
import { Pressable, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { colors } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

export function BetslipButton() {
  const navigation = useNavigation<Nav>();
  return (
    <Pressable
      onPress={() => navigation.navigate('Betslip')}
      hitSlop={8}
      accessibilityLabel="Open betslip"
      accessibilityRole="button"
      style={({ pressed }) => [styles.btn, pressed && { opacity: 0.6 }]}
    >
      <Ionicons name="receipt-outline" size={22} color={colors.textSecondary} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: { padding: 4 },
});
