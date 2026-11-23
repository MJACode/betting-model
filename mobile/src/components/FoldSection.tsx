import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { colors, font, opacity, spacing } from '@/lib/theme';

/**
 * A titled section that folds under its header (Matt, 2026-11-23: the
 * Performance tab's Insights card "is overwhelming", so everything below the
 * headline and the units chart folds, starting closed). The header is the
 * whole tap target, 44pt tall, with a trailing chevron and an optional
 * one-line peek (`hint`) so a closed section still says what is inside.
 *
 * Chevrons: a SECTION folds with a trailing down/up chevron (this, and the
 * Tracked picks card); a ROW inside a list folds with BetDateHeader's leading
 * forward/down chevron. New folds follow the same split.
 */
export function FoldSection({
  title,
  hint,
  initiallyOpen = false,
  children,
}: {
  title: string;
  /** Short value shown at the right of a section header, e.g. "+1.00u". */
  hint?: string | null;
  initiallyOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(initiallyOpen);
  return (
    <View style={styles.section}>
      <Pressable
        onPress={() => setOpen((o) => !o)}
        accessibilityRole="button"
        accessibilityLabel={hint ? `${title}, ${hint}` : title}
        accessibilityState={{ expanded: open }}
        accessibilityHint={open ? 'Hides this section' : 'Shows this section'}
        style={({ pressed }) => [styles.header, pressed && styles.pressed]}
      >
        {/* Wraps rather than truncates at large Dynamic Type: on a closed
            fold the title is the only clue to what is inside. */}
        <Text style={styles.title}>{title}</Text>
        {hint ? (
          <Text style={styles.hint} numberOfLines={1}>
            {hint}
          </Text>
        ) : null}
        <Ionicons
          name={open ? 'chevron-up' : 'chevron-down'}
          size={16}
          color={colors.textTertiary}
          style={styles.chevron}
        />
      </Pressable>
      {open ? <View style={styles.body}>{children}</View> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  section: {
    marginTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  header: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingVertical: spacing.sm + 2,
  },
  pressed: { opacity: opacity.pressed },
  title: {
    flex: 1,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  hint: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
    marginLeft: spacing.sm,
    marginTop: 2,
    flexShrink: 0,
  },
  chevron: { marginLeft: spacing.xs, marginTop: 3 },
  body: { paddingBottom: spacing.xs },
});
