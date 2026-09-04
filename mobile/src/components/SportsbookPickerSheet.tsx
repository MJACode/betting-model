import React, { useEffect, useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { usePreferredBook, BOOKS, type BookKey } from '@/hooks/usePreferredBook';
import { bookLabel, bookName, MODEL_BOOK } from '@/lib/markets';
import { DK_GREEN } from '@/lib/sportsbookLinks';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * "Stats Page Sportsbook" bottom sheet — where the user switches which book's
 * lines the STATS page prices its odds column at.
 *
 * Scope is the whole point of this sheet's copy (Matt, 2026-09-04). It used to
 * set the price shown on every board, and the Picks header carried a line
 * saying so. It no longer does: Picks and Signals show the best line across
 * every book we price, off a pick modeled at DraftKings, and a member cannot
 * change that. The title, the subtitle and the footnote each say "Stats page"
 * so a user who opens this from Settings cannot read it as app-wide.
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
 * prices for, or one (Pinnacle, Bovada) that will not take their bet. DK's
 * brand green is the only brand color used — the other books get a neutral
 * badge rather than an approximated hex (a wrong brand color that fails
 * contrast is worse than a consistent one).
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
      <Pressable
        style={styles.backdrop}
        onPress={onClose}
        accessibilityRole="button"
        accessibilityLabel="Close"
      >
        {/* accessible={false}: an accessible Pressable groups its children
            into ONE VoiceOver element, which would leave the book rows, the
            Close button and Apply unreachable. Same fix as StatsLineSheet. */}
        <Pressable style={styles.sheet} onPress={() => {}} accessible={false}>
          <View style={styles.grabber} />
          <View style={styles.header}>
            <Text style={styles.title}>Your sportsbook</Text>
            <Pressable onPress={onClose} hitSlop={8} accessibilityLabel="Close">
              <Ionicons name="close" size={24} color={colors.textSecondary} />
            </Pressable>
          </View>
          <Text style={styles.subtitle}>
            Sets which book’s line the Stats page prints beside each player. Only books we pull
            live lines from, and that you can bet at, are listed.
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
                    {isModel ? null : (
                      <Text style={styles.rowSub}>
                        No fallback — a Stats player {bookName(b)} hasn’t priced shows no line
                      </Text>
                    )}
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

          {/* One sentence, not a paragraph: Settings states the scope above
              this sheet and the Explainer carries the long version, so a third
              copy here reads as the app being defensive (UX review). */}
          <Text style={styles.footnote}>
            Sets the Stats page’s lines and where the betslip sends you. Picks and Signals
            always price at DraftKings and list every book best price first.
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
