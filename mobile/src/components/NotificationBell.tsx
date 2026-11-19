import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import React, { useEffect } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { readAuthUserId } from '@/hooks/useAuth';
import { refreshNotificationInbox, useNotificationInbox } from '@/hooks/useNotificationInbox';
import { colors, font, opacity } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

/**
 * The header bell. Gold, with the unread count. Sits in every tab's
 * right-hand actions, before settings. Count 0 draws no badge; the bell
 * stays so the 7-day history is one tap away.
 */
export function NotificationBell() {
  const navigation = useNavigation<Nav>();
  const { unread } = useNotificationInbox();

  useEffect(() => {
    void refreshNotificationInbox(readAuthUserId());
  }, []);

  const label = unread > 0 ? `Notifications, ${unread} unread` : 'Notifications';
  const shown = unread > 99 ? '99+' : String(unread);

  return (
    <Pressable
      onPress={() => navigation.navigate('Notifications')}
      hitSlop={8}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => [styles.btn, pressed && { opacity: opacity.pressed }]}
    >
      <Ionicons name="notifications-outline" size={22} color={colors.tint} />
      {unread > 0 ? (
        <View style={styles.badge} importantForAccessibility="no">
          <Text style={styles.badgeText} maxFontSizeMultiplier={1}>{shown}</Text>
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
    right: 0,
    minWidth: 16,
    height: 16,
    paddingHorizontal: 3,
    borderRadius: 8,
    backgroundColor: colors.tint,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeText: {
    fontSize: font.size.nano,
    fontWeight: font.weight.bold,
    color: colors.textInverse,
    fontVariant: ['tabular-nums'],
  },
});
