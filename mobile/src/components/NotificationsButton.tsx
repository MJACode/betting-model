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
  // A full 44pt box, no hitSlop: the gear beside it is the same box, so the
  // two targets abut instead of overlapping (UX review, 2026-11-14).
  btn: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  badge: {
    position: 'absolute',
    top: 5,
    right: 3,
    minWidth: 18,
    minHeight: 18,
    paddingHorizontal: 4,
    borderRadius: 9,
    // tint, like the Stats filter badge and the Betslip count. Not avoid: that
    // red is the AVOID signal and is 3.55:1 under white text.
    backgroundColor: colors.tint,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
    borderColor: colors.bg,
  },
  badgeText: {
    color: colors.textInverse,
    fontSize: font.size.micro,
    fontWeight: font.weight.bold,
  },
});
