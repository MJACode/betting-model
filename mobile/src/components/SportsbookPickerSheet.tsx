import React, { useEffect, useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { BookChecklist, toggleBook } from '@/components/BookChecklist';
import { usePreferredBooks, BOOKS, type BookKey } from '@/hooks/usePreferredBooks';
import { MODEL_BOOK } from '@/lib/markets';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * "Your sportsbooks" bottom sheet — the books the member can bet at, MULTI-
 * SELECT (Matt, 2026-09-04, with a competitor's picker beside ours: "give them
 * the option to place on any Sportsbook we have odds for"). Pick DraftKings and
 * FanDuel and the Stats board prints whichever pays more on each line, badged
 * with the book that won it.
 *
 * Scope (Matt, 2026-10-19): the set decides which prices a member SEES —
 * the pick cards, the pick detail, the Stats board's lines and where the
 * betslip's bet button sends them. It never reaches the models: every pick is
 * still decided and graded at the best bettable price (usePreferredBooks).
 * Onboarding opens the same list (OnboardingModal), with every book checked.
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
 * COVERAGE IS SHOWN, NEVER ENFORCED (Matt, 2026-09-05: "if we are getting
 * betting lines for a Sportsbook we should show it as an option and display
 * those lines. It doesn't matter if we don't have as many props as DK"). He
 * had opened this sheet with FanDuel and Caesars showing nothing and read it
 * as us not carrying them; we do — measured that morning, both post Hits,
 * RBIs, Runs, Total Bases and HR, but only through the milestone market,
 * which is OVER-ONLY. So a row can carry a `coverageNote` saying what the
 * board's current stat has at that book, and every row stays selectable
 * whatever it says. Only the Stats screen passes one; Settings has no stat in
 * context and shows the plain list.
 *
 * DK's brand green is the only brand color used — the other books get a neutral
 * badge rather than an approximated hex (a wrong brand color that fails
 * contrast is worse than a consistent one), and no logos: docs/book_logos.md
 * records the four routes tried for the image files and why none landed.
 */
export function SportsbookPickerSheet({
  visible,
  onClose,
  coverageNote,
}: {
  visible: boolean;
  onClose: () => void;
  /** What the caller's current context has at this book — "Hits: At Least
   *  only", "No Hits lines today". Display only: it never disables a row and
   *  never removes one. */
  coverageNote?: (book: BookKey) => string | null;
}) {
  const { books, setBooks } = usePreferredBooks();
  const [selected, setSelected] = useState<BookKey[]>(books);

  // Re-seed the draft from the committed value every time the sheet opens, so
  // an abandoned draft from a previous open can never leak into this one.
  useEffect(() => {
    if (visible) setSelected(books);
  }, [visible, books]);

  const allOn = selected.length === BOOKS.length;
  const toggle = (b: BookKey) => setSelected((prev) => toggleBook(prev, b));
  const toggleAll = () => setSelected(allOn ? [MODEL_BOOK] : [...BOOKS]);

  const apply = () => {
    setBooks(selected);
    onClose();
  };

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.backdrop}>
        {/* Tap-outside-to-close is a SIBLING behind the sheet, not its
            parent: an accessible Pressable groups everything inside it into
            one VoiceOver element, so a backdrop that wrapped the sheet hid the
            sheet's rows and buttons from VoiceOver (audit PR 4). */}
        <Pressable
          style={StyleSheet.absoluteFill}
          onPress={onClose}
          accessibilityRole="button"
          accessibilityLabel="Close sportsbook picker"
        />
        {/* accessible={false}: an accessible Pressable groups its children
            into ONE VoiceOver element, which would leave the book rows, the
            Close button and Apply unreachable. Same fix as StatsLineSheet. */}
        <Pressable style={styles.sheet} onPress={() => {}} accessible={false}>
          <View style={styles.grabber} />
          <View style={styles.header}>
            <Text style={styles.title}>Your sportsbooks</Text>
            <Pressable
              accessibilityRole="button"
              onPress={onClose}
              hitSlop={12}
              accessibilityLabel="Close sportsbook picker"
            >
              <Ionicons name="close" size={24} color={colors.textSecondary} />
            </Pressable>
          </View>
          <Text style={styles.subtitle}>
            Picks and Stats show the best price at these books. The most value comes from
            using every book you can.
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
              <Ionicons name="checkmark-circle" size={22} color={colors.tint} />
            ) : (
              <View style={styles.emptyCircleSm} />
            )}
          </Pressable>

          <ScrollView style={styles.list} bounces={false}>
            <BookChecklist selected={selected} onToggle={toggle} coverageNote={coverageNote} />
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
      </View>
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
  emptyCircleSm: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: colors.separatorOpaque,
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
  // tint + textInverse, as FilterSheet's "Show N picks" (18.6:1). Selected
  // and confirm are tint, never green; white on `bet` was 2.22:1 (audit H6).
  applyBtn: {
    marginTop: spacing.md,
    backgroundColor: colors.tint,
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
    color: colors.textInverse,
  },
  pressed: {
    opacity: 0.7,
  },
});
