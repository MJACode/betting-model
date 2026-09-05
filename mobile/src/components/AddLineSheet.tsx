import React, { useMemo } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { showToast } from '@/components/Toast';
import { useLineLegs } from '@/hooks/useLineLegs';
import { usePreferredBooks } from '@/hooks/usePreferredBooks';
import { formatAmerican } from '@/lib/format';
import { lineLegKey, lineLegLabel, type LineSheetInput } from '@/lib/lineLegs';
import { bookLabelShort, bookName, MODEL_BOOK } from '@/lib/markets';
import { matchupForLeg } from '@/lib/parlay';
import { DK_GREEN } from '@/lib/sportsbookLinks';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { GameRow } from '@/types';

/**
 * "Add to betslip?" — what a tap on a Stats line pill opens.
 *
 * Matt, 2026-09-04, with a competitor's flow beside ours: "when you click on
 * one of the records bet lines, it shouldn't take you directly to the book, it
 * should ask you if you want to add to bet slip then bet slip should allow you
 * to add to any book." So the sheet ASKS, once: the player, the line and the
 * side the board was showing, every bettable book's price for it (best
 * starred, DraftKings marked), and one action. The book is chosen later, on
 * the betslip's Open-with row — never here.
 *
 * The leg it adds is a Stats LINE leg (lib/lineLegs.ts): the user's own
 * research bet, priced at DraftKings when DraftKings posts the line and at
 * the best bettable book otherwise, never a model pick. Re-adding the same
 * proposition is a no-op; the button reads "Remove" when it is already in.
 *
 * One sheet for both boards (2026-09-05): a Players pill hands it a prop
 * spec, a Teams pill a game spec — the moneyline, the spread at the board's
 * number, the total — through lib/lineLegs.ts propLineSheetInput /
 * teamLineSheetInput. The sheet itself does not know which it was given.
 */
export function AddLineSheet({
  input,
  game,
  onClose,
  onAdded,
}: {
  /** The proposition and every bettable book's price for it; null closes. */
  input: LineSheetInput | null;
  game: GameRow | null;
  onClose: () => void;
  /** Called after a successful add — the Stats screen uses it to bounce back
   *  to the betslip when the user came from there. */
  onAdded?: () => void;
}) {
  const legs = useLineLegs();
  const { books: myBooks } = usePreferredBooks();

  const spec = input?.spec ?? null;
  const key = spec ? lineLegKey(spec) : null;
  const inSlip = key != null && legs.has(key);

  // Every bettable book pricing THIS side at THIS line, best payout first
  // (American odds are monotonic in payout; ties keep the board's order) —
  // already in that order from the input helper.
  const prices = useMemo(() => input?.prices ?? [], [input]);
  const best = prices[0]?.price ?? null;

  // The title IS the proposition — the exact string the betslip's leg card
  // will show, so the slip entry is recognisable from here.
  const title = spec ? lineLegLabel(spec) : '';
  const matchup = matchupForLeg(game);

  const act = () => {
    if (!spec || !key) return;
    if (inSlip) {
      legs.remove(key);
      showToast('Removed from betslip');
      onClose();
      return;
    }
    legs.add(spec);
    showToast('Added to betslip');
    onClose();
    onAdded?.();
  };

  return (
    <Modal visible={input != null} animationType="slide" transparent onRequestClose={onClose}>
      <Pressable
        style={styles.backdrop}
        onPress={onClose}
        accessibilityRole="button"
        accessibilityLabel="Close"
      >
        {/* accessible={false}: an accessible Pressable groups its children into
            ONE VoiceOver element, which would leave the price rows and the
            buttons unreachable. Same fix as SportsbookPickerSheet. */}
        <Pressable style={styles.sheet} onPress={() => {}} accessible={false} accessibilityViewIsModal>
          <View style={styles.grabber} />
          <View style={styles.header}>
            <View style={styles.headerBody}>
              <Text style={styles.title} numberOfLines={2}>
                {title}
              </Text>
              {matchup ? <Text style={styles.matchup}>{matchup}</Text> : null}
            </View>
            <Pressable onPress={onClose} hitSlop={12} accessibilityRole="button" accessibilityLabel="Close">
              <Ionicons name="close" size={24} color={colors.textSecondary} />
            </Pressable>
          </View>
          {/* The ask, and where the book gets chosen — under the title, where
              the reference sheets put their one-line explainer, not as a
              caption under the list (UX review). */}
          <Text style={styles.subtitle}>
            {input?.explainer ?? 'Add it to your betslip now — you’ll choose the sportsbook there.'}
          </Text>

          <Text style={styles.sectionTitle}>Where it&apos;s posted</Text>
          {/* One card, hairline rows: a read-only comparison, styled unlike
              the picker's tappable cards one screen over so nobody taps a
              row expecting to choose it. "Yours" marks the member's own books
              — the pill they came from was the best of those. */}
          <ScrollView style={styles.list} bounces={false}>
            <View style={styles.listCard}>
              {prices.map((p, i) => {
                const isModel = p.book === MODEL_BOOK;
                const isBest = best != null && p.price === best;
                const mine = (myBooks as readonly string[]).includes(p.book);
                return (
                  <View
                    key={p.book}
                    style={[styles.row, i > 0 && styles.rowDivider]}
                    accessible
                    accessibilityLabel={`${bookName(p.book)}${mine ? ', yours' : ''}, ${formatAmerican(p.price)}${isBest ? ', best odds' : ''}`}
                  >
                    <View style={[styles.badge, isModel && styles.badgeDk]}>
                      <Text style={[styles.badgeText, isModel && styles.badgeTextDk]}>{bookLabelShort(p.book)}</Text>
                    </View>
                    <Text style={styles.rowName} numberOfLines={1}>
                      {bookName(p.book)}
                    </Text>
                    {mine ? <Text style={styles.yours}>Yours</Text> : null}
                    <Text style={styles.rowPrice}>{formatAmerican(p.price)}</Text>
                    {isBest ? (
                      <Ionicons name="star" size={14} color={colors.best} accessibilityElementsHidden />
                    ) : (
                      <View style={styles.starGap} />
                    )}
                  </View>
                );
              })}
            </View>
          </ScrollView>

          <Pressable
            onPress={act}
            accessibilityRole="button"
            accessibilityLabel={inSlip ? 'Remove from betslip' : 'Add to betslip'}
            style={({ pressed }) => [
              styles.primary,
              inSlip && styles.primaryRemove,
              pressed && styles.pressed,
            ]}
          >
            <Ionicons
              name={inSlip ? 'remove-circle-outline' : 'add-circle-outline'}
              size={20}
              color={inSlip ? colors.textPrimary : colors.textInverse}
            />
            <Text style={[styles.primaryText, inSlip && styles.primaryTextRemove]}>
              {inSlip ? 'Remove from betslip' : 'Add to betslip'}
            </Text>
          </Pressable>
          <Pressable
            onPress={onClose}
            accessibilityRole="button"
            accessibilityLabel="Not now"
            style={({ pressed }) => [styles.secondary, pressed && styles.pressed]}
          >
            <Text style={styles.secondaryText}>Not now</Text>
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
    alignItems: 'flex-start',
    marginBottom: spacing.md,
  },
  headerBody: {
    flex: 1,
    paddingRight: spacing.md,
  },
  title: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  subtitle: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: -spacing.xs,
    marginBottom: spacing.md,
  },
  matchup: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
  },
  sectionTitle: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginBottom: spacing.xs,
  },
  list: {
    flexGrow: 0,
  },
  listCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    paddingHorizontal: spacing.sm,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.sm,
    minHeight: 44,
  },
  rowDivider: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  badge: {
    minWidth: 44,
    minHeight: 32,
    paddingHorizontal: spacing.xs,
    borderRadius: radii.sm,
    backgroundColor: colors.noneSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeDk: {
    backgroundColor: DK_GREEN,
  },
  badgeText: {
    fontSize: font.size.caption,
    fontWeight: font.weight.bold,
    color: colors.textSecondary,
  },
  badgeTextDk: {
    color: colors.textPrimary,
  },
  rowName: {
    flex: 1,
    fontSize: font.size.body,
    color: colors.textPrimary,
  },
  yours: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  rowPrice: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    fontVariant: ['tabular-nums'],
  },
  starGap: {
    width: 14,
  },
  primary: {
    marginTop: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    backgroundColor: colors.tint,
    borderRadius: radii.pill,
    minHeight: 48,
    paddingHorizontal: spacing.lg,
  },
  primaryRemove: {
    backgroundColor: colors.bgCard,
    borderWidth: 1.5,
    borderColor: colors.separatorOpaque,
  },
  primaryText: {
    fontSize: font.size.body,
    fontWeight: font.weight.bold,
    color: colors.textInverse,
  },
  primaryTextRemove: {
    color: colors.textPrimary,
  },
  secondary: {
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 44,
    marginTop: spacing.xs,
  },
  secondaryText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  pressed: {
    opacity: 0.7,
  },
});
