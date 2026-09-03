import React, { useEffect, useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { usePreferredBook, BOOKS, type BookKey } from '@/hooks/usePreferredBook';
import { bookLabel, bookName, MODEL_BOOK } from '@/lib/markets';
import { DK_GREEN } from '@/lib/sportsbookLinks';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * "Select Your Sportsbook" bottom sheet — the one place the user switches which
 * book's lines the whole app shows (and where the "Bet on …" buttons send them).
 *
 * Modeled on the betting-app pickers users already know: a sheet of book rows
 * with the chosen one ringed and checked, committed by a green Apply button.
 * Selection is a DRAFT until Apply — tapping rows just moves the ring, and
 * dismissing the sheet (backdrop, X, back) discards the draft. That matches the
 * reference UI this mirrors; the app's live-apply convention stays for filters,
 * where the list below IS the feedback — here the whole app changes, so an
 * explicit commit reads better.
 *
 * The list is BETTABLE_BOOKS — the books we ingest lines for AND a member can
 * place at from the US — so the user can never select a book we hold no
 * prices for, or one (Pinnacle, Bovada) that will not take their bet. The
 * models always price against DraftKings; this only changes what the user is
 * SHOWN, and when their book hasn't posted a line for a bet we show the
 * DraftKings number and label it (displayQuoteForPick's fallback). DK's brand
 * green is the only brand color used — the other books get a neutral badge
 * rather than an approximated hex (a wrong brand color that fails contrast is
 * worse than a consistent one).
 */
export function SportsbookPickerSheet({
  visible,
  onClose,
}: {
  visible: boolean;
  onClose: () => void;
}) {
  const { book, setBook } = usePreferredBook();
  const [selected, setSelected] = useState<BookKey>(book);

  // Re-seed the draft from the committed value every time the sheet opens, so
  // an abandoned draft from a previous open can never leak into this one.
  useEffect(() => {
    if (visible) setSelected(book);
  }, [visible, book]);

  const apply = () => {
    setBook(selected);
    onClose();
  };

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={() => {}}>
          <View style={styles.grabber} />
          <View style={styles.header}>
            <Text style={styles.title}>Select Your Sportsbook</Text>
            <Pressable onPress={onClose} hitSlop={8} accessibilityLabel="Close">
              <Ionicons name="close" size={24} color={colors.textSecondary} />
            </Pressable>
          </View>
          <Text style={styles.subtitle}>
            Your book is highlighted on every pick’s betting lines, and its price is the one the
            stake is sized from. Only books we pull live lines from, and that you can bet at, are
            listed.
          </Text>

          <ScrollView style={styles.list} bounces={false}>
            {BOOKS.map((b) => {
              const active = b === selected;
              const isModel = b === MODEL_BOOK;
              return (
                <Pressable
                  key={b}
                  onPress={() => setSelected(b)}
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
                    <Ionicons name="checkmark-circle" size={24} color={colors.bet} />
                  ) : (
                    <View style={styles.emptyCircle} />
                  )}
                </Pressable>
              );
            })}
          </ScrollView>

          <Text style={styles.footnote}>
            Picks are always modeled against DraftKings — switching books changes the price you
            see, never the pick. Every pick still lists each book’s line, best price first, so you
            can place it wherever pays most. Live picks are DraftKings only.
          </Text>

          <Pressable
            onPress={apply}
            accessibilityRole="button"
            accessibilityLabel="Apply sportsbook selection"
            style={({ pressed }) => [styles.applyBtn, pressed && styles.applyBtnPressed]}
          >
            <Text style={styles.applyText}>Apply</Text>
          </Pressable>
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
    maxHeight: '85%',
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
    fontSize: font.size.title3,
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
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 1.5,
    borderColor: colors.separatorOpaque,
  },
  footnote: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    lineHeight: 16,
    marginTop: spacing.sm,
  },
  applyBtn: {
    marginTop: spacing.md,
    backgroundColor: colors.bet,
    borderRadius: radii.pill,
    paddingVertical: 14,
    alignItems: 'center',
  },
  applyBtnPressed: {
    opacity: 0.8,
  },
  applyText: {
    fontSize: font.size.headline,
    fontWeight: font.weight.bold,
    color: '#fff',
  },
  pressed: {
    opacity: 0.7,
  },
});
