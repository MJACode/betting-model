import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { BOOKS, type BookKey } from '@/hooks/usePreferredBooks';
import { bookLabel, bookName, MODEL_BOOK } from '@/lib/markets';
import { DK_GREEN } from '@/lib/sportsbookLinks';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * Checks or unchecks one book. The last one stays on: an empty set would
 * blank every price with nothing on screen to explain it.
 */
export function toggleBook(prev: readonly BookKey[], b: BookKey): BookKey[] {
  if (!prev.includes(b)) return BOOKS.filter((x) => x === b || prev.includes(x));
  if (prev.length === 1) return [...prev];
  return prev.filter((x) => x !== b);
}

/**
 * The book rows, one per bettable book. Shared by the Settings sheet
 * (SportsbookPickerSheet) and the onboarding step (OnboardingModal), so the
 * two lists cannot drift. The caller owns the scroll view and the draft.
 */
export function BookChecklist({
  selected,
  onToggle,
  coverageNote,
}: {
  selected: readonly BookKey[];
  onToggle: (b: BookKey) => void;
  /** What the caller's context has at this book. Display only. */
  coverageNote?: (book: BookKey) => string | null;
}) {
  return (
    <>
      {BOOKS.map((b) => {
        const active = selected.includes(b);
        const isModel = b === MODEL_BOOK;
        const last = active && selected.length === 1;
        // The lock line wins the one sub-line slot: it explains a control the
        // member just tried to use, which the coverage note does not. The note
        // answers "what does this book have", so it does not follow the draft.
        const note = last ? null : (coverageNote?.(b) ?? null);
        return (
          <Pressable
            key={b}
            onPress={() => onToggle(b)}
            accessibilityRole="checkbox"
            accessibilityState={{ checked: active }}
            accessibilityLabel={
              last
                ? `${bookName(b)}, selected. Your only sportsbook — choose another before removing it.`
                : note
                  ? `${bookName(b)}. ${note}`
                  : bookName(b)
            }
            style={({ pressed }) => [styles.row, active && styles.rowActive, pressed && styles.pressed]}
          >
            <View style={[styles.badge, isModel && styles.badgeDk]}>
              <Text style={[styles.badgeText, isModel && styles.badgeTextDk]}>{bookLabel(b)}</Text>
            </View>
            <View style={styles.rowBody}>
              <Text style={styles.rowName}>{bookName(b)}</Text>
              {last ? (
                <View style={styles.lockRow}>
                  <Ionicons name="lock-closed" size={11} color={colors.textTertiary} />
                  <Text style={styles.rowSub}>
                    Your only sportsbook — add another before removing this one
                  </Text>
                </View>
              ) : note ? (
                <Text style={styles.rowSub}>{note}</Text>
              ) : null}
            </View>
            {active ? (
              // Green even when locked: green means selected here, and the
              // lock icon beside the sub-line carries the state (UX review).
              <Ionicons name="checkmark-circle" size={24} color={colors.tint} />
            ) : (
              <View style={styles.emptyCircle} />
            )}
          </Pressable>
        );
      })}
    </>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    borderWidth: 1.5,
    borderColor: 'transparent',
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  rowActive: {
    borderColor: colors.tint,
  },
  badge: {
    width: 44,
    height: 44,
    borderRadius: radii.sm,
    backgroundColor: colors.noneSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeDk: {
    backgroundColor: DK_GREEN,
  },
  badgeText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.bold,
    color: colors.textSecondary,
  },
  badgeTextDk: {
    color: colors.textPrimary,
  },
  rowBody: {
    flex: 1,
  },
  rowName: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  rowSub: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginTop: 1,
  },
  emptyCircle: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 1.5,
    borderColor: colors.separatorOpaque,
  },
  lockRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  pressed: {
    opacity: 0.7,
  },
});
