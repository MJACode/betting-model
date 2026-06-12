import React, { useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, font, radii, spacing } from '@/lib/theme';

interface Props {
  title: string;
  body: string;
  /** Accessibility label for the info icon. Defaults to "More info". */
  accessibilityLabel?: string;
}

/**
 * Small info (ⓘ) icon that opens a centered tooltip modal with explanatory
 * copy. Tap the backdrop or the "Got it" button to dismiss.
 */
export function InfoTooltip({ title, body, accessibilityLabel = 'More info' }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Pressable
        onPress={() => setOpen(true)}
        hitSlop={10}
        accessibilityRole="button"
        accessibilityLabel={accessibilityLabel}
        style={({ pressed }) => [styles.iconBtn, pressed && styles.pressed]}
      >
        <Ionicons name="information-circle-outline" size={20} color={colors.tint} />
      </Pressable>
      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)}>
          {/* Inner Pressable swallows taps so touching the card doesn't dismiss. */}
          <Pressable style={styles.card} onPress={() => {}}>
            <View style={styles.cardHeader}>
              <Ionicons name="information-circle" size={22} color={colors.tint} />
              <Text style={styles.cardTitle}>{title}</Text>
            </View>
            <Text style={styles.cardBody}>{body}</Text>
            <Pressable
              onPress={() => setOpen(false)}
              style={({ pressed }) => [styles.dismissBtn, pressed && styles.pressed]}
            >
              <Text style={styles.dismissText}>Got it</Text>
            </Pressable>
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  iconBtn: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  pressed: { opacity: 0.65 },
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.4)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
  },
  card: {
    width: '100%',
    maxWidth: 360,
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.lg,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  cardTitle: {
    flex: 1,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  cardBody: {
    fontSize: font.size.body,
    lineHeight: 21,
    color: colors.textSecondary,
  },
  dismissBtn: {
    marginTop: spacing.lg,
    alignItems: 'center',
    paddingVertical: spacing.sm + 2,
    borderRadius: radii.sm,
    backgroundColor: colors.tint,
  },
  dismissText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textInverse,
  },
});
