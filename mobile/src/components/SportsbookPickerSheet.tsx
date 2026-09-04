import React, { useEffect, useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { usePreferredBooks, BOOKS, type BookKey } from '@/hooks/usePreferredBooks';
import { bookLabel, bookName, MODEL_BOOK } from '@/lib/markets';
import { DK_GREEN } from '@/lib/sportsbookLinks';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * "Your sportsbooks" bottom sheet — the books the member can bet at, MULTI-
 * SELECT (Matt, 2026-09-04, with a competitor's picker beside ours: "give them
 * the option to place on any Sportsbook we have odds for"). Pick DraftKings and
 * FanDuel and the Stats board prints whichever pays more on each line, badged
 * with the book that won it.
 *
 * Scope is the whole point of this sheet's copy. The setting used to price
 * every board, and the Picks header carried a line saying so. It no longer
 * does: Picks and Signals show the best line across every book we price, off a
 * pick modeled at DraftKings, and a member cannot change that. What the set
 * decides is the Stats board's lines and where the betslip's bet button sends
 * them.
 *
 * THE LAST BOOK CANNOT BE UNCHECKED. An empty set would blank the Stats column
 * with nothing on screen to explain it, so the final checkmark is inert and
 * says why rather than silently refusing.
 *
 * Selection is a DRAFT until Apply — tapping rows just moves checkmarks, and
 * dismissing the sheet (backdrop, X, back) discards the draft. That matches the
 * reference UI this mirrors; the app's live-apply convention stays for filters,
 * where the list below IS the feedback — here two screens change, so an
 * explicit commit reads better.
 *
 * The list is BETTABLE_BOOKS — the books we ingest lines for AND a member can
 * place at from the US — so the user can never select a book we hold no prices
 * for, or one (Pinnacle, Bovada) that will not take their bet. The reference
 * picker also lists DFS platforms (PrizePicks, Pick6); we carry no odds for
 * those, so listing them would be a checkbox that changes nothing.
 *
 * DK's brand green is the only brand color used — the other books get a neutral
 * badge rather than an approximated hex (a wrong brand color that fails
 * contrast is worse than a consistent one), and no logos: docs/book_logos.md
 * records the four routes tried for the image files and why none landed.
 */
export function SportsbookPickerSheet({
  visible,
  onClose,
}: {
  visible: boolean;
  onClose: () => void;
}) {
  const { books, setBooks } = usePreferredBooks();
  const [selected, setSelected] = useState<BookKey[]>(books);

  // Re-seed the draft from the committed value every time the sheet opens, so
  // an abandoned draft from a previous open can never leak into this one.
  useEffect(() => {
    if (visible) setSelected(books);
  }, [visible, books]);

  const allOn = selected.length === BOOKS.length;
  const toggle = (b: BookKey) => {
    setSelected((prev) => {
      if (!prev.includes(b)) return BOOKS.filter((x) => x === b || prev.includes(x));
      // The last one stays on: an empty set has no honest Stats column.
      if (prev.length === 1) return prev;
      return prev.filter((x) => x !== b);
    });
  };
  const toggleAll = () => setSelected(allOn ? [MODEL_BOOK] : [...BOOKS]);

  const apply = () => {
    setBooks(selected);
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
            <Text style={styles.title}>Your sportsbooks</Text>
            <Pressable onPress={onClose} hitSlop={12} accessibilityLabel="Close">
              <Ionicons name="close" size={24} color={colors.textSecondary} />
            </Pressable>
          </View>
          <Text style={styles.subtitle}>
            Your Stats lines show the best of these, and the betslip opens the one taking
            your slip.
          </Text>

          <Pressable
            onPress={toggleAll}
            accessibilityRole="checkbox"
            accessibilityState={{ checked: allOn }}
            accessibilityLabel={allOn ? 'Keep DraftKings only' : 'Select all sportsbooks'}
            hitSlop={8}
            style={({ pressed }) => [styles.selectAllRow, pressed && styles.pressed]}
          >
            <Text style={styles.selectAllText}>{allOn ? 'Keep DraftKings only' : 'Select all'}</Text>
            {allOn ? (
              <Ionicons name="checkmark-circle" size={22} color={colors.bet} />
            ) : (
              <View style={styles.emptyCircleSm} />
            )}
          </Pressable>

          <ScrollView style={styles.list} bounces={false}>
            {BOOKS.map((b) => {
              const active = selected.includes(b);
              const isModel = b === MODEL_BOOK;
              const last = active && selected.length === 1;
              return (
                <Pressable
                  key={b}
                  onPress={() => toggle(b)}
                  accessibilityRole="checkbox"
                  accessibilityState={{ checked: active }}
                  accessibilityLabel={
                    last
                      ? `${bookName(b)}, selected. Your only sportsbook — choose another before removing it.`
                      : bookName(b)
                  }
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
                    {last ? (
                      <View style={styles.lockRow}>
                        <Ionicons name="lock-closed" size={11} color={colors.textTertiary} />
                        <Text style={styles.rowSub}>
                          Your only sportsbook — add another before removing this one
                        </Text>
                      </View>
                    ) : null}
                  </View>
                  {active ? (
                    // Green even when locked: in this sheet green means
                    // selected, and greying the one book that is definitively
                    // on made it look the most off (UX review). The lock icon
                    // beside the sub-line carries the state instead.
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
          <Pressable
            onPress={apply}
            accessibilityRole="button"
            accessibilityLabel={`Apply. ${selected.length} sportsbook${selected.length === 1 ? '' : 's'} selected.`}
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
  emptyCircleSm: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: colors.separatorOpaque,
  },
  lockRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  selectAllRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  selectAllText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.tint,
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
