import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { colors, font, spacing } from '@/lib/theme';

interface Props {
  title: string;
  subtitle?: string;
  /** What VoiceOver reads for the subtitle when its text holds codes that
   *  are spelled out letter by letter (two sport codes side by side). */
  subtitleAccessibilityLabel?: string;
  /** Optional undo, e.g. "Clear games" on a Games-emptied board. */
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyState({ title, subtitle, subtitleAccessibilityLabel, actionLabel, onAction }: Props) {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>{title}</Text>
      {subtitle ? (
        <Text style={styles.subtitle} accessibilityLabel={subtitleAccessibilityLabel}>
          {subtitle}
        </Text>
      ) : null}
      {actionLabel && onAction ? (
        <Pressable
          onPress={onAction}
          accessibilityRole="button"
          accessibilityLabel={actionLabel}
          hitSlop={8}
          style={({ pressed }) => [styles.action, pressed && styles.pressed]}
        >
          <Text style={styles.actionText}>{actionLabel}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.xxl * 2,
  },
  title: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: font.size.body,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 20,
  },
  action: {
    marginTop: spacing.md,
    minHeight: 44,
    paddingHorizontal: spacing.lg,
    justifyContent: 'center',
  },
  actionText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  pressed: { opacity: 0.65 },
});
