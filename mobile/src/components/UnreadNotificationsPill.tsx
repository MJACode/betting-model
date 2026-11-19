import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { useNotificationInbox } from '@/hooks/useNotificationInbox';
import { unreadPill } from '@/lib/notificationInbox';
import { colors, font, opacity, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

/**
 * Picks only, above Bet all, and only while something is unread.
 * "3 new · Live pick, new signals, line move". Same destination as the bell.
 */
export function UnreadNotificationsPill() {
  const navigation = useNavigation<Nav>();
  const { rows } = useNotificationInbox();
  const pill = unreadPill(rows);
  if (!pill) return null;

  return (
    <Pressable
      onPress={() => navigation.navigate('Notifications')}
      accessibilityRole="button"
      accessibilityLabel={`${pill.count} new. ${pill.summary}`}
      style={({ pressed }) => [styles.pill, pressed && { opacity: opacity.pressed }]}
    >
      <Ionicons name="notifications" size={16} color={colors.tint} />
      <Text style={styles.count}>{pill.count} new</Text>
      <Text style={styles.summary} numberOfLines={1}>
        {pill.summary}
      </Text>
      <View style={styles.spacer} />
      <Ionicons name="chevron-forward" size={16} color={colors.tint} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    minHeight: 44,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.tint,
    backgroundColor: colors.bg,
  },
  count: {
    fontSize: font.size.body,
    fontWeight: font.weight.bold,
    color: colors.tint,
  },
  summary: {
    flexShrink: 1,
    fontSize: font.size.footnote,
    color: colors.textPrimary,
  },
  spacer: { flex: 1 },
});
