import React from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { HIT_MODES, hitModeHeadline, rulerValueLabel, type HitMode } from '@/lib/hitMode';
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
 * position — "1+ Hits", "Over 0.5 Hits", "Under 0.5 Hits". THIS SHEET IS THE
 * ONE PLACE THE THREE IDIOMS APPEAR TOGETHER, which is why the equivalence
 * lives here and nowhere else: At Least and Over name the SAME bet at the
 * same price, in the fan's words and the book's, and a user who could not see
 * the two side by side would go hunting for a difference that is not there.
 * The board itself then speaks only the one they chose (lib/hitMode.ts).
 */
export function HitModeSheet({
  visible,
  mode,
  lineN,
  statLabel,
  onPick,
  onClose,
  overAvailable = true,
  underAvailable = true,
  unavailableNote,
}: {
  visible: boolean;
  mode: HitMode;
  /** The ruler's current stop, for the preview on each row. Each mode prints
   *  it in its own idiom, so the sheet shows one bet under three names. */
  lineN: number;
  statLabel: string;
  onPick: (mode: HitMode) => void;
  onClose: () => void;
  /** Do the member's books price each side? A book that posts only the over —
   *  FanDuel's and Caesars' milestone markets do — leaves At Least and Over
   *  live and only Under unpriceable, so the ROW is marked rather than the
   *  whole control locked. Both default true: fail open while the read is in
   *  flight, exactly as the screen does. */
  overAvailable?: boolean;
  underAvailable?: boolean;
  /** Why, naming the book. A greyed row with no reason is the "why is FanDuel
   *  blank" question in a smaller box. */
  unavailableNote?: string | null;
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
          {/* SAYS THE EQUIVALENCE OUT LOUD, because two of the rows below name
              the same bet and this sheet is the only place they appear
              together. A subtitle that described the modes without naming both
              numbers left the duplicate looking like a mistake and sent the
              user hunting for a difference that is not there (UX review,
              2026-09-06). */}
          <Text style={styles.subtitle}>
            At Least {lineN} and Over {rulerValueLabel(lineN, 'over')} are the same bet at the same
            price — At Least is how a fan says it, Over is how your sportsbook posts it. Under{' '}
            {rulerValueLabel(lineN, 'under')} is the other side of it.
          </Text>
          <View style={styles.list}>
            {HIT_MODES.map((m) => {
              const active = m.mode === mode;
              const preview = hitModeHeadline(lineN, m.mode, statLabel);
              // The side this mode bets — it does not depend on the ruler.
              const priced = m.mode === 'under' ? underAvailable : overAvailable;
              return (
                <Pressable
                  key={m.mode}
                  onPress={() => {
                    if (!priced) return;
                    onPick(m.mode);
                    onClose();
                  }}
                  disabled={!priced}
                  accessibilityRole="radio"
                  accessibilityState={{ checked: active, disabled: !priced }}
                  // One shape for both branches. They had drifted into two —
                  // the priced one stuttering the mode word, the unpriced one
                  // dropping the stat label (UX review, 2026-09-06). The row's
                  // own name is spoken by rowName either way, so neither
                  // repeats it.
                  accessibilityLabel={
                    priced ? preview : `${preview}, not priced by your sportsbooks`
                  }
                  style={({ pressed }) => [
                    styles.row,
                    active && styles.rowActive,
                    !priced && styles.rowDisabled,
                    pressed && priced && styles.pressed,
                  ]}
                >
                  <View style={styles.rowBody}>
                    <Text style={[styles.rowName, !priced && styles.textDisabled]}>{m.label}</Text>
                    <Text style={[styles.rowPreview, !priced && styles.textDisabled]}>
                      {priced ? preview : 'Not priced by your sportsbooks'}
                    </Text>
                  </View>
                  {active ? (
                    <Ionicons name="checkmark-circle" size={22} color={colors.bet} />
                  ) : (
                    <View style={styles.emptyCircle} />
                  )}
                </Pressable>
              );
            })}
            {unavailableNote ? <Text style={styles.note}>{unavailableNote}</Text> : null}
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
    // Reserved, not added on selection: a border that appears would make the
    // chosen row 3pt taller than its neighbours in a three-row list whose
    // whole point is comparing them (StatePickerSheet does the same).
    borderWidth: 1.5,
    borderColor: 'transparent',
  },
  rowActive: { borderColor: colors.bet },
  rowBody: { flex: 1, gap: 2 },
  rowName: { fontSize: font.size.body, fontWeight: font.weight.semibold, color: colors.textPrimary },
  rowPreview: { fontSize: font.size.footnote, color: colors.textSecondary },
  emptyCircle: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 1.5,
    borderColor: colors.separatorOpaque,
  },
  rowDisabled: { opacity: 0.45 },
  textDisabled: { color: colors.textTertiary },
  note: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: spacing.sm,
  },
  pressed: { opacity: 0.7 },
});
