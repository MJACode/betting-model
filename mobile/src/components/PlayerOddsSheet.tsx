import React, { useMemo } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { useParlaySlip } from '@/hooks/useParlaySlip';
import { usePreferredBook } from '@/hooks/usePreferredBook';
import { expectedValue, formatAmerican, formatPct, formatPctSigned } from '@/lib/format';
import {
  allBookPrices,
  bookName,
  propMarketForModel,
  MODEL_BOOK,
} from '@/lib/markets';
import { slipKeyForPick } from '@/lib/parlay';
import { openBookBetslip } from '@/lib/sportsbookLinks';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { EnrichedPick } from '@/types';

/**
 * Player odds sheet — opened from a Stats leaderboard row's odds pill. The
 * betting-app version of this sheet shows a price at each book and an "add to
 * betslip" button; ours adds the piece none of them have: what OUR model makes
 * of the number (model probability, edge, EV against the DK line it scored).
 *
 * Books list: every book pricing this side, best payout first (the same
 * allBookPrices math as the pick detail's All-books card), the user's book
 * highlighted. Falls back to the stored DK price when no snapshot rows exist,
 * so the sheet never opens empty for a priced pick. Tapping a book opens its
 * betslip (or its site when we have no deep link).
 */
export function PlayerOddsSheet({
  enriched,
  playerName,
  visible,
  onClose,
  onOpenDetail,
  onAdded,
}: {
  enriched: EnrichedPick;
  playerName: string;
  visible: boolean;
  onClose: () => void;
  /** Navigate to the full PickDetail screen (sheet closes first). */
  onOpenDetail?: () => void;
  /** Called right after the pick is ADDED to the betslip (not on removal) —
   * powers the Betslip-tab round-trip ("find a player, come right back"). */
  onAdded?: () => void;
}) {
  const { pick } = enriched;
  const slip = useParlaySlip();
  const { book: preferredBook } = usePreferredBook();

  const market = propMarketForModel(pick.model_id);
  const quotes = useMemo(
    () => allBookPrices(enriched.bookRows ?? [], pick.pick_side, market),
    [enriched.bookRows, pick.pick_side, market],
  );
  const ev = expectedValue(pick.model_probability, pick.dk_odds);

  const key = slipKeyForPick(pick);
  const inSlip = slip.has(key);
  const canSlip = pick.dk_odds != null && pick.result == null;

  const toggleSlip = () => {
    const adding = !inSlip;
    slip.toggle(key);
    if (adding) onAdded?.();
  };

  const sideLine =
    pick.scored_line != null
      ? `${pick.pick_side === 'under' ? 'u' : 'o'}${pick.scored_line}`
      : null;

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={() => {}}>
          <View style={styles.grabber} />
          <View style={styles.header}>
            <View style={styles.headerBody}>
              <Text style={styles.playerName}>{playerName}</Text>
              <Text style={styles.pickLabel} numberOfLines={1}>
                Pick: {pick.pick_label}
              </Text>
            </View>
            <Pressable onPress={onClose} hitSlop={8} accessibilityLabel="Close">
              <Ionicons name="close" size={24} color={colors.textSecondary} />
            </Pressable>
          </View>

          {/* The model's read — the part no odds screen elsewhere has. */}
          <View style={styles.statsRow}>
            <Stat label="Model" value={formatPct(pick.model_probability)} />
            <Stat
              label="Edge"
              value={pick.edge != null ? formatPctSigned(pick.edge) : '—'}
              color={
                pick.edge == null
                  ? undefined
                  : pick.edge >= 0
                    ? colors.bet
                    : colors.avoid
              }
            />
            <Stat
              label="EV"
              value={ev == null ? '—' : formatPctSigned(ev)}
              color={ev == null ? undefined : ev >= 0 ? colors.bet : colors.avoid}
            />
            <Stat
              label="Line"
              value={sideLine ?? '—'}
            />
          </View>

          <Text style={styles.booksTitle}>Sportsbooks</Text>
          <ScrollView style={styles.bookList} bounces={false}>
            {quotes.length > 0 ? (
              quotes.map((q) => {
                const isPreferred = q.bookmaker === preferredBook;
                return (
                  <Pressable
                    key={q.bookmaker}
                    onPress={() => {
                      void openBookBetslip(q.bookmaker, q.link);
                    }}
                    style={({ pressed }) => [
                      styles.bookRow,
                      isPreferred && styles.bookRowPreferred,
                      pressed && styles.pressed,
                    ]}
                  >
                    <View style={styles.bookBody}>
                      <Text style={styles.bookName}>{bookName(q.bookmaker)}</Text>
                      <View style={styles.tagRow}>
                        {q.bookmaker === MODEL_BOOK ? (
                          <Text style={styles.modelTag}>modeled</Text>
                        ) : null}
                        {isPreferred ? <Text style={styles.yoursTag}>yours</Text> : null}
                      </View>
                    </View>
                    {q.line != null ? (
                      <Text style={styles.bookLine}>
                        {pick.pick_side === 'under' ? 'u' : 'o'}
                        {q.line}
                      </Text>
                    ) : null}
                    <View style={styles.bookPriceWrap}>
                      <Text style={[styles.bookPrice, q.isBest && styles.bookPriceBest]}>
                        {formatAmerican(q.price)}
                      </Text>
                      {q.isBest ? <Text style={styles.bestTag}>best</Text> : null}
                    </View>
                    <Ionicons name="open-outline" size={14} color={colors.textTertiary} />
                  </Pressable>
                );
              })
            ) : pick.dk_odds != null ? (
              // No snapshot rows — the stored DK price the model scored against.
              <View style={styles.bookRow}>
                <View style={styles.bookBody}>
                  <Text style={styles.bookName}>{bookName(MODEL_BOOK)}</Text>
                  <View style={styles.tagRow}>
                    <Text style={styles.modelTag}>modeled</Text>
                  </View>
                </View>
                {sideLine ? <Text style={styles.bookLine}>{sideLine}</Text> : null}
                <View style={styles.bookPriceWrap}>
                  <Text style={styles.bookPrice}>{formatAmerican(pick.dk_odds)}</Text>
                </View>
              </View>
            ) : (
              <Text style={styles.noBooks}>
                No book prices this line right now — the pick is scored on model probability
                alone.
              </Text>
            )}
          </ScrollView>

          {canSlip ? (
            <Pressable
              onPress={toggleSlip}
              style={({ pressed }) => [
                styles.addBtn,
                inSlip && styles.addBtnIn,
                pressed && styles.pressed,
              ]}
            >
              <Ionicons
                name={inSlip ? 'checkmark' : 'add'}
                size={18}
                color={inSlip ? colors.bet : colors.textInverse}
              />
              <Text style={[styles.addBtnText, inSlip && styles.addBtnTextIn]}>
                {inSlip ? 'In betslip · tap to remove' : 'Add to betslip'}
              </Text>
            </Pressable>
          ) : (
            <Text style={styles.noSlipNote}>
              This pick has no sportsbook price, so it can’t join a betslip (a parlay leg needs
              a payout).
            </Text>
          )}

          {onOpenDetail ? (
            <Pressable
              onPress={onOpenDetail}
              style={({ pressed }) => [styles.detailLink, pressed && styles.pressed]}
            >
              <Text style={styles.detailLinkText}>Full pick details</Text>
              <Ionicons name="chevron-forward" size={14} color={colors.tint} />
            </Pressable>
          ) : null}
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={[styles.statValue, color ? { color } : null]}>{value}</Text>
    </View>
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
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: spacing.md,
  },
  headerBody: {
    flex: 1,
    paddingRight: spacing.sm,
  },
  playerName: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  pickLabel: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
  },
  statsRow: {
    flexDirection: 'row',
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  stat: { flex: 1 },
  statLabel: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginBottom: 2,
  },
  statValue: {
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  booksTitle: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: spacing.sm,
  },
  bookList: {
    flexGrow: 0,
  },
  bookRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    borderWidth: 1.5,
    borderColor: 'transparent',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginBottom: spacing.sm,
  },
  bookRowPreferred: {
    borderColor: colors.tint,
  },
  bookBody: { flex: 1 },
  bookName: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  tagRow: { flexDirection: 'row', gap: 6, marginTop: 1 },
  modelTag: { fontSize: font.size.caption, color: colors.textSecondary },
  yoursTag: {
    fontSize: font.size.caption,
    color: colors.tint,
    fontWeight: font.weight.semibold,
    backgroundColor: colors.noneSoft,
    borderRadius: radii.pill,
    paddingHorizontal: 6,
    overflow: 'hidden',
  },
  bookLine: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontVariant: ['tabular-nums'],
  },
  bookPriceWrap: {
    alignItems: 'flex-end',
    minWidth: 62,
  },
  bookPrice: {
    fontSize: font.size.body,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    fontVariant: ['tabular-nums'],
  },
  bookPriceBest: {
    color: colors.positive,
  },
  bestTag: {
    fontSize: font.size.caption,
    color: colors.positive,
    fontWeight: font.weight.semibold,
  },
  noBooks: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    lineHeight: 18,
    paddingVertical: spacing.sm,
  },
  addBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    backgroundColor: colors.tint,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    marginTop: spacing.sm,
  },
  addBtnIn: {
    backgroundColor: colors.betSoft,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.bet,
  },
  addBtnText: {
    color: colors.textInverse,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
  },
  addBtnTextIn: {
    color: colors.bet,
  },
  noSlipNote: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    lineHeight: 16,
    marginTop: spacing.sm,
  },
  detailLink: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 2,
    paddingVertical: spacing.md,
  },
  detailLinkText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  pressed: {
    opacity: 0.7,
  },
});
