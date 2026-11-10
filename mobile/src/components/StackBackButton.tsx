import React from 'react';
import { Pressable, StyleSheet, Text, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { PLAYER_DETAIL_PARENT, playerTitleMaxWidth, stackBackDecision } from '@/lib/stackBack';
import { colors, font } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

/** Centered player name. One line, and no wider than the gap between the pills. */
export function PlayerStatsHeaderTitle({
  children,
  tintColor,
}: {
  children?: React.ReactNode;
  tintColor?: string;
}) {
  const { width, fontScale } = useWindowDimensions();
  return (
    <Text
      numberOfLines={1}
      maxFontSizeMultiplier={2}
      style={[styles.title, { color: tintColor, maxWidth: playerTitleMaxWidth(width, fontScale) }]}
    >
      {children}
    </Text>
  );
}

/**
 * The "< Back" pill for the player / prop detail screen.
 *
 * It replaces UIKit's back button on that screen. The system pill sits in
 * the iOS 26/27 bar, and after a modal it stops taking taps (the restarts
 * on PlayerStats). This one is a React pressable in the header's left slot.
 * The stack insets that header by the safe area; the provider is seeded so
 * the inset exists on the first frame. 44pt is the floor. hitSlop grows the
 * target inside the bar; it does not reach down into the player name.
 * zIndex / elevation order the pill inside its own header slot. The title
 * width is what keeps a long name off it — the title is a UIKit label, and
 * a React zIndex does not paint over that.
 */
export function PlayerStatsBackButton() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { fontScale } = useWindowDimensions();
  const icon = Math.round(22 * Math.min(Math.max(fontScale, 1), 2));
  const onPress = () => {
    if (stackBackDecision(navigation.canGoBack()) === 'pop') navigation.goBack();
    else navigation.replace(PLAYER_DETAIL_PARENT.name, { screen: PLAYER_DETAIL_PARENT.screen });
  };
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel="Back"
      hitSlop={{ top: 12, bottom: 0, left: 8, right: 8 }}
      style={({ pressed }) => [styles.pill, pressed && styles.pressed]}
    >
      <Ionicons name="chevron-back" size={icon} color={colors.tint} />
      <Text style={styles.label} numberOfLines={1} maxFontSizeMultiplier={2}>
        Back
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  title: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    textAlign: 'center',
  },
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    minWidth: 44,
    minHeight: 44,
    zIndex: 20,
    elevation: 20,
  },
  pressed: { opacity: 0.5 },
  label: {
    fontSize: font.size.headline,
    color: colors.tint,
    fontWeight: font.weight.regular,
  },
});
