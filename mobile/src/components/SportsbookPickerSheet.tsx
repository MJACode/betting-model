import React from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { usePreferredBook, BOOKS } from '@/hooks/usePreferredBook';
import { bookLabel, bookName, MODEL_BOOK } from '@/lib/markets';
import { DK_GREEN } from '@/lib/sportsbookLinks';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * "Select your sportsbook" bottom sheet — the one place the user switches which
 * book's lines the whole app shows (and where the "Bet on …" buttons send them).
 *
 * Modeled on the betting-app pickers users already know (a sheet of book rows
 * with the active one ringed), but selection applies IMMEDIATELY — no Apply
 * button. That matches the app-wide live-filter convention, and the preference
 * is a single value shared through usePreferredBook, so every board, card, and
 * betslip follows the tap at once.
 *
 * The models always price against DraftKings; this only changes what the user
 * is SHOWN. The footnote says so, and the DraftKings row is tagged as the
 * modeled book. DK's brand green is the only brand color used — the other books
 * get a neutral badge rather than an approximated hex (a wrong brand color that
 * fails contrast is worse than a consistent one).
 */
export function SportsbookPickerSheet({
  visible,
  onClose,
}: {
  visible: boolean;
  onClose: () => void;
}) {
  const { book, setBook } = usePreferredBook();

  const select = (b: (typeof BOOKS)[number]) => {
    setBook(b);
    onClose();
  };

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={() => {}}>
          <View style={styles.grabber} />
          <View style={styles.header}>
            <Text style={styles.title}>Your sportsbook</Text>
            <Pressable onPress={onClose} hitSlop={8} accessibilityLabel="Close">
              <Ionicons name="close" size={24} color={colors.textSecondary} />
            </Pressable>
          </View>
          <Text style={styles.subtitle}>
            Lines and “Bet on …” buttons across the app follow the book you pick here.
          </Text>

          <ScrollView style={styles.list} bounces={false}>
            {BOOKS.map((b) => {
              const active = b === book;
              const isModel = b === MODEL_BOOK;
              return (
                <Pressable
                  key={b}
                  onPress={() => select(b)}
                  accessibilityRole="button"
                  accessibilityState={{ selected: active }}
                  style={({ pressed }) => [
                    styles.row,
                    active && styles.rowActive,
                    pressed && styles.pressed,
                  ]}
                >
                  <View style={[styles.badge, isModel && styles.badgeDk]}>
                    <Text style={[styles.badgeText, isModel && styles.badgeTextDk]}>
                      {bookLabel(b)}
                    </Text>
                  </View>
                  <View style={styles.rowBody}>
                    <Text style={styles.rowName}>{bookName(b)}</Text>
                    {isModel ? (
                      <Text style={styles.rowSub}>
                        Model book — signals and the track record are priced here
                      </Text>
                    ) : null}
                  </View>
                  {active ? (
                    <Ionicons name="checkmark-circle" size={22} color={colors.bet} />
                  ) : (
                    <View style={styles.emptyCircle} />
                  )}
                </Pressable>
              );
            })}
          </ScrollView>

          <Text style={styles.footnote}>
            Picks are always modeled against DraftKings — switching books changes the price and
            line you see, never the pick. If your book hasn’t posted a line, we show the
            DraftKings number and label it.
          </Text>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: '#00000066',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: colors.bg,
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.xxl,
    maxHeight: '80%',
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
  },
  title: {
    fontSize: font.size.headline,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  subtitle: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
    marginBottom: spacing.md,
  },
  list: {
    flexGrow: 0,
  },
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
    borderColor: colors.bet,
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
    color: '#000',
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
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: colors.separatorOpaque,
  },
  footnote: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    lineHeight: 16,
    marginTop: spacing.sm,
  },
  pressed: {
    opacity: 0.7,
  },
});
