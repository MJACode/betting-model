import React from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * Passing / Rushing / Receiving / Defense — which slice of the stat catalog
 * the chip row beneath the pill is scoped to.
 *
 * Until 2026-09-12 this was a second row of underline tabs sitting directly
 * under Players | Teams, which made three tab rows on one screen at two
 * different sizes: the eye could not use shape to tell a board-level switch
 * from a filter (UX review, 2026-09-12 — "six selection idioms at four
 * levels"). The group is a navigation level whose only job is to scope the
 * row below it, so it collapses into a dropdown pill at the head of that row
 * and gives its 33pt back to the leaderboard. FotMob's team squad stats does
 * the same with its stat selector; the Premier League tables screen puts
 * three of these side by side in the space one tab row would take.
 *
 * The sheet, not a cycling toggle: the NFL catalog carries 33 stats across
 * four groups, so the pill must be able to SHOW the choices rather than flip
 * through them. Shape and behaviour follow HitModeSheet — the app's own
 * single-select shell, applied on tap, the pill it opened from being the
 * feedback.
 */
export function StatGroupSheet<T extends string>({
  visible,
  groups,
  active,
  countFor,
  onPick,
  onClose,
}: {
  visible: boolean;
  groups: readonly T[];
  active: T;
  /** How many stats the group holds — the one thing the old tab row could not
   *  say, and the reason a user opens this rather than guessing. */
  countFor?: (group: T) => number;
  onPick: (group: T) => void;
  onClose: () => void;
}) {
  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <Pressable
        style={styles.backdrop}
        onPress={onClose}
        accessibilityRole="button"
        accessibilityLabel="Close"
      >
        {/* accessible={false}: an accessible Pressable groups its children into
            ONE VoiceOver element, which would leave the rows unreachable. */}
        <Pressable style={styles.sheet} onPress={() => {}} accessible={false} accessibilityViewIsModal>
          <View style={styles.grabber} />
          <View style={styles.header}>
            <Text style={styles.title}>Stat group</Text>
            <Pressable onPress={onClose} hitSlop={12} accessibilityRole="button" accessibilityLabel="Close">
              <Ionicons name="close" size={24} color={colors.textSecondary} />
            </Pressable>
          </View>
          <View style={styles.list}>
            {groups.map((g) => {
              const isActive = g === active;
              const n = countFor?.(g);
              return (
                <Pressable
                  key={g}
                  onPress={() => {
                    onPick(g);
                    onClose();
                  }}
                  accessibilityRole="radio"
                  accessibilityState={{ checked: isActive }}
                  // The count is part of the row's meaning, not decoration, so
                  // it goes in the label rather than being left to a sighted
                  // read of the trailing text.
                  accessibilityLabel={n === undefined ? g : `${g}, ${n} stats`}
                  style={({ pressed }) => [
                    styles.row,
                    isActive && styles.rowActive,
                    pressed && styles.pressed,
                  ]}
                >
                  <View style={styles.rowBody}>
                    <Text style={styles.rowName}>{g}</Text>
                    {n === undefined ? null : (
                      <Text style={styles.rowMeta}>
                        {n} {n === 1 ? 'stat' : 'stats'}
                      </Text>
                    )}
                  </View>
                  {isActive ? (
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
    marginBottom: spacing.md,
  },
  title: { fontSize: font.size.title3, fontWeight: font.weight.bold, color: colors.textPrimary },
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
    // Reserved, not added on selection: a border that appears would make the
    // chosen row taller than its neighbours (HitModeSheet does the same).
    borderWidth: 1.5,
    borderColor: 'transparent',
  },
  rowActive: { borderColor: colors.bet },
  rowBody: { flex: 1, gap: 2 },
  rowName: { fontSize: font.size.body, fontWeight: font.weight.semibold, color: colors.textPrimary },
  rowMeta: { fontSize: font.size.footnote, color: colors.textSecondary },
  emptyCircle: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 1.5,
    borderColor: colors.separatorOpaque,
  },
  pressed: { opacity: 0.7 },
});
