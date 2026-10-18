import React from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * Bottom sheet for the Record card's info buttons. The backdrop is a sibling
 * of the sheet, the same shape as InfoTooltip, so VoiceOver cannot wander
 * out and a tap outside dismisses.
 */
export function RecordInfoSheet({
  visible,
  title,
  body,
  onClose,
}: {
  visible: boolean;
  title: string;
  body: string;
  onClose: () => void;
}) {
  const insets = useSafeAreaInsets();
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <Pressable
          style={StyleSheet.absoluteFill}
          onPress={onClose}
          accessibilityRole="button"
          accessibilityLabel={`Close ${title}`}
        />
        <Pressable
          style={[styles.sheet, { paddingBottom: Math.max(insets.bottom, spacing.lg) }]}
          onPress={() => {}}
          accessible={false}
          accessibilityViewIsModal
        >
          <Text style={styles.title} accessibilityRole="header">{title}</Text>
          <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent} bounces={false}>
            <Text style={styles.body}>{body}</Text>
          </ScrollView>
          <Pressable
            onPress={onClose}
            accessibilityRole="button"
            accessibilityLabel="Got it"
            style={({ pressed }) => [styles.dismissBtn, pressed && styles.pressed]}
          >
            <Text style={styles.dismissText}>Got it</Text>
          </Pressable>
        </Pressable>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.4)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: colors.bgCard,
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    maxHeight: '80%',
  },
  title: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  scroll: { flexGrow: 0, flexShrink: 1 },
  scrollContent: { paddingBottom: spacing.sm },
  body: {
    fontSize: font.size.body,
    lineHeight: 22,
    color: colors.textSecondary,
  },
  dismissBtn: {
    marginTop: spacing.lg,
    alignItems: 'center',
    minHeight: 44,
    justifyContent: 'center',
    borderRadius: radii.sm,
    backgroundColor: colors.tint,
  },
  dismissText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textInverse,
  },
  pressed: { opacity: 0.65 },
});
