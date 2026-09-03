import React, { useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { SportsbookPickerSheet } from '@/components/SportsbookPickerSheet';
import { useParlaySlip } from '@/hooks/useParlaySlip';
import { formatAmerican } from '@/lib/format';
import { betOnBookLabel, bookName } from '@/lib/markets';
import { slipKeyForPick } from '@/lib/parlay';
import { openBookBetslip } from '@/lib/sportsbookLinks';
import { teamLineCaption, type StatsOddsQuote, type TeamLineQuote } from '@/lib/statsOdds';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { EnrichedPick } from '@/types';

/**
 * The sheet behind a LINE cell on the Stats tab. One sportsbook — the one the
 * user selected — one number, and the button that takes them to it.
 *
 * Matt, 2026-09-03: the Stats tab shows current lines for research and betting,
 * at the user's book only, separate from the models. So there is no all-books
 * table here (that is the pick detail's job), no model probability, no edge and
 * no EV. The one thing a pick still does on this tab is make a parlay leg
 * possible — a leg IS a pick — so "Add to betslip" appears exactly when the
 * model made a pick on this line, and says nothing else about it.
 */
export type StatsLineTarget =
  | { kind: 'player'; quote: StatsOddsQuote; name: string; statLabel: string }
  | { kind: 'team'; quote: TeamLineQuote; statLabel: string };

/** "Over 0.5 Hits" / "Moneyline" / "Spread −1.5" / "Total o8.5". */
export function lineTitle(target: StatsLineTarget): string {
  if (target.kind === 'player') {
    const q = target.quote;
    return `${q.side === 'under' ? 'Under' : 'Over'} ${q.line} ${target.statLabel}`;
  }
  const q = target.quote;
  if (q.market === 'h2h') return 'Moneyline';
  if (q.market === 'spreads') return `Spread ${teamLineCaption(q) ?? ''}`.trim();
  return `Total ${teamLineCaption(q) ?? ''}`.trim();
}

export function StatsLineSheet({
  target,
  visible,
  onClose,
  slipPick,
  onAdded,
}: {
  target: StatsLineTarget;
  visible: boolean;
  onClose: () => void;
  /** The model's pick on this exact line, when one exists — the only way a
   *  leg can join the betslip. Null on a team row and on any line no model
   *  scored. */
  slipPick?: EnrichedPick | null;
  /** Called right after the pick is ADDED to the betslip (not on removal) —
   *  powers the Betslip-tab round-trip ("find a player, come right back"). */
  onAdded?: () => void;
}) {
  const slip = useParlaySlip();
  const [pickerOpen, setPickerOpen] = useState(false);

  const q = target.quote;
  const name = target.kind === 'player' ? target.name : target.quote.team;
  const matchup =
    target.kind === 'team'
      ? `${target.quote.isHome ? 'vs' : '@'} ${target.quote.opponent}`
      : null;

  const key = slipPick ? slipKeyForPick(slipPick.pick) : null;
  const inSlip = key != null && slip.has(key);
  const toggleSlip = () => {
    if (key == null) return;
    const adding = !inSlip;
    slip.toggle(key);
    if (adding) onAdded?.();
  };

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose} accessibilityLabel="Close">
        <Pressable style={styles.sheet} onPress={() => {}}>
          <View style={styles.grabber} />
          <View style={styles.header}>
            <View style={styles.headerBody}>
              <Text style={styles.name}>{name}</Text>
              <Text style={styles.sub} numberOfLines={1}>
                {lineTitle(target)}
                {matchup ? `  ·  ${matchup}` : ''}
              </Text>
            </View>
            <Pressable
              onPress={onClose}
              hitSlop={8}
              accessibilityRole="button"
              accessibilityLabel="Close"
            >
              <Ionicons name="close" size={24} color={colors.textSecondary} />
            </Pressable>
          </View>

          {/* The one book, the one number. */}
          <View style={styles.bookRow}>
            <View style={styles.bookBody}>
              <Text style={styles.bookName}>{bookName(q.book)}</Text>
              <Text style={styles.bookTag}>your sportsbook</Text>
            </View>
            <Text style={styles.price}>{formatAmerican(q.price)}</Text>
          </View>

          <Pressable
            onPress={() => {
              void openBookBetslip(q.book, q.link);
            }}
            accessibilityRole="button"
            accessibilityLabel={betOnBookLabel(q.book)}
            style={({ pressed }) => [styles.betBtn, pressed && styles.pressed]}
          >
            <Ionicons name="open-outline" size={16} color={colors.textInverse} />
            <Text style={styles.betBtnText}>{betOnBookLabel(q.book)}</Text>
          </Pressable>

          {slipPick ? (
            <Pressable
              onPress={toggleSlip}
              accessibilityRole="button"
              accessibilityLabel={inSlip ? 'Remove from betslip' : 'Add to betslip'}
              style={({ pressed }) => [
                styles.slipBtn,
                inSlip && styles.slipBtnIn,
                pressed && styles.pressed,
              ]}
            >
              <Ionicons
                name={inSlip ? 'checkmark' : 'add'}
                size={18}
                color={inSlip ? colors.bet : colors.tint}
              />
              <Text style={[styles.slipBtnText, inSlip && styles.slipBtnTextIn]}>
                {inSlip ? 'In betslip · tap to remove' : 'Add to betslip'}
              </Text>
            </Pressable>
          ) : null}

          <Pressable
            onPress={() => setPickerOpen(true)}
            accessibilityRole="button"
            accessibilityLabel="Switch sportsbook"
            style={({ pressed }) => [styles.switchRow, pressed && styles.pressed]}
          >
            <Ionicons name="wallet-outline" size={14} color={colors.tint} />
            <Text style={styles.switchText}>Switch sportsbook</Text>
            <Ionicons name="chevron-forward" size={14} color={colors.tint} />
          </Pressable>

          {/* The board re-prices under the sheet the moment the book changes,
              so the number this sheet was opened on is stale — close it. */}
          <SportsbookPickerSheet
            visible={pickerOpen}
            onClose={() => {
              setPickerOpen(false);
              onClose();
            }}
          />
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
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: spacing.md,
  },
  headerBody: { flex: 1, paddingRight: spacing.sm },
  name: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  sub: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
  },
  bookRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    borderWidth: 1.5,
    borderColor: colors.tint,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    marginBottom: spacing.md,
  },
  bookBody: { flex: 1 },
  bookName: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  bookTag: {
    fontSize: font.size.caption,
    color: colors.tint,
    fontWeight: font.weight.semibold,
    marginTop: 1,
  },
  price: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    fontVariant: ['tabular-nums'],
  },
  betBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    backgroundColor: colors.tint,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
  },
  betBtnText: {
    color: colors.textInverse,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
  },
  slipBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    borderRadius: radii.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.tint,
    paddingVertical: spacing.md,
    marginTop: spacing.sm,
  },
  slipBtnIn: {
    backgroundColor: colors.betSoft,
    borderColor: colors.bet,
  },
  slipBtnText: {
    color: colors.tint,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
  },
  slipBtnTextIn: { color: colors.bet },
  switchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    paddingVertical: spacing.md,
    marginTop: spacing.xs,
  },
  switchText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  pressed: { opacity: 0.7 },
});
