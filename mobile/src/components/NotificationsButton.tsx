// NotificationsButton — the header bell that opens the notifications inbox
// (Matt, 2026-11-14). It sits left of the settings gear on every tab, with a
// count of what has not been opened yet.

import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { useInboxUnread } from '@/hooks/useNotificationInbox';
import { badgeText } from '@/lib/notificationInboxHelpers';
import { colors, font, opacity } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

export function NotificationsButton() {
  const navigation = useNavigation<Nav>();
  const unread = useInboxUnread();
  const badge = badgeText(unread);
  return (
    <Pressable
      onPress={() => navigation.navigate('Notifications')}
      hitSlop={8}
      accessibilityRole="button"
      accessibilityLabel={
        badge ? `Notifications, ${unread} unread` : 'Notifications'
      }
      style={({ pressed }) => [styles.btn, pressed && { opacity: opacity.pressed }]}
    >
      <Ionicons
        name={badge ? 'notifications' : 'notifications-outline'}
        size={22}
        color={colors.textSecondary}
      />
      {badge ? (
        <View style={styles.badge} importantForAccessibility="no-hide-descendants">
          <Text style={styles.badgeText} maxFontSizeMultiplier={1.3}>
            {badge}
          </Text>
        </View>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: { padding: 4 },
  badge: {
    position: 'absolute',
    top: 0,
    right: -2,
    minWidth: 18,
    height: 18,
    paddingHorizontal: 4,
    borderRadius: 9,
    backgroundColor: colors.avoid,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
    borderColor: colors.bg,
  },
  badgeText: {
    color: colors.textInverse,
    fontSize: font.size.nano + 1,
    fontWeight: font.weight.bold,
  },
});
