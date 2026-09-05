import React from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { HIT_MODES, hitModeHeadline, type HitMode } from '@/lib/hitMode';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * At Least / Over / Under — which side of the ruler's number the board is
 * about (Matt, 2026-09-05, with a competitor's Leaders tab beside ours).
 *
 * The control it opens from used to be a two-way TOGGLE wearing a
 * chevron-down, which promised a menu and gave a flip. This is the menu, in
 * the app's own sheet shell (StatePickerSheet, SportsbookPickerSheet):
 * single-select, applied on tap, the row it opened from being the feedback.
 *
 * Each row carries what the bet would actually be called at the current ruler
 * position, because the three modes overlap on a whole-number stat — "Over 1"
 * IS "2+" — and a picker that hid that would be inviting the user to hunt for
 * a difference that is not there.
 */
export function HitModeSheet({
  visible,
  mode,
  lineN,
  statLabel,
  onPick,
  onClose,
}: {
  visible: boolean;
  mode: HitMode;
  /** The ruler's current whole number, for the preview on each row. */
  lineN: number;
  statLabel: string;
  onPick: (mode: HitMode) => void;
  onClose: () => void;
}) {
  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose} accessibilityRole="button" accessibilityLabel="Close">
        {/* accessible={false}: an accessible Pressable groups its children into
            ONE VoiceOver element, which would leave the rows unreachable. */}
        <Pressable style={styles.sheet} onPress={() => {}} accessible={false} accessibilityViewIsModal>
          <View style={styles.grabber} />
          <View style={styles.header}>
            <Text style={styles.title}>Show bets that are</Text>
            <Pressable onPress={onClose} hitSlop={12} accessibilityRole="button" accessibilityLabel="Close">
              <Ionicons name="close" size={24} color={colors.textSecondary} />
            </Pressable>
          </View>
          <Text style={styles.subtitle}>
            Which side of {lineN} the board is about. The line and the price follow.
          </Text>
          <View style={styles.list}>
            {HIT_MODES.map((m) => {
              const active = m.mode === mode;
              const preview = hitModeHeadline(lineN, m.mode, statLabel);
              return (
                <Pressable
                  key={m.mode}
                  onPress={() => {
                    onPick(m.mode);
                    onClose();
                  }}
                  accessibilityRole="radio"
                  accessibilityState={{ checked: active }}
                  accessibilityLabel={`${m.label} ${lineN}, that is ${preview}`}
                  style={({ pressed }) => [styles.row, active && styles.rowActive, pressed && styles.pressed]}
                >
                  <Text style={styles.rowName}>{m.label}</Text>
                  <Text style={styles.rowPreview} numberOfLines={1}>
                    {preview}
                  </Text>
                  {active ? (
                    <Ionicons name="checkmark-circle" size={22} color={colors.bet} />
                  ) : (
                    <View style={styles.emptyCircle} />
                  )}
                </Pressable>
              );
            })}
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: '#00000066', justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: colors.bg,
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.xxl,
  },
  grabber: {
    alignSelf: 'center',
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.separatorOpaque,
    marginBottom: spacing.sm,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  title: { fontSize: font.size.title3, fontWeight: font.weight.bold, color: colors.textPrimary },
  subtitle: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },
  list: { gap: spacing.xs },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    minHeight: 52,
    borderRadius: radii.md,
    backgroundColor: colors.bgCard,
  },
  rowActive: { borderWidth: 1.5, borderColor: colors.bet },
  rowName: { flex: 1, fontSize: font.size.body, fontWeight: font.weight.semibold, color: colors.textPrimary },
  rowPreview: { fontSize: font.size.footnote, color: colors.textSecondary },
  emptyCircle: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 1.5,
    borderColor: colors.separatorOpaque,
  },
  pressed: { opacity: 0.7 },
});
