import React from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { PICK_BOOKS_NOTE, type PickSportsbookRow } from '@/lib/pickBooks';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * Selected sportsbooks for one pick, best price first. Same sheet chrome as
 * the Lines all-books sheet. The Best row is a green wash, a Best pill and a
 * green price. A book with no price is an em dash. The bottom button and a
 * row both open that book.
 */
export function PickBooksSheet({
  visible,
  title,
  subtitle,
  lineNote,
  rows,
  betLabel,
  betSpeech,
  onBet,
  onRow,
  onClose,
}: {
  visible: boolean;
  title: string;
  subtitle: string;
  /** The card's Now line, when this sheet's bet is at a moved line. */
  lineNote?: string | null;
  rows: PickSportsbookRow[];
  /** Visible "Bet DK −115". Null when no row has a price. */
  betLabel: string | null;
  /** Spoken "Bet, DraftKings, −115". */
  betSpeech?: string | null;
  onBet: () => void;
  onRow: (row: PickSportsbookRow) => void;
  onClose: () => void;
}) {
  const insets = useSafeAreaInsets();
  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <Pressable
          style={StyleSheet.absoluteFill}
          onPress={onClose}
          accessibilityRole="button"
          accessibilityLabel="Close sportsbooks"
        />
        {/* accessible={false}: an accessible Pressable groups its children into
            ONE VoiceOver element. VoiceOver must reach the rows and Bet. */}
        <Pressable
          style={[styles.sheet, { paddingBottom: Math.max(insets.bottom, spacing.lg) }]}
          onPress={() => {}}
          accessible={false}
          accessibilityViewIsModal
        >
          <View style={styles.grabber} />
          <View style={styles.header}>
            <View style={styles.headerBody}>
              <Text style={styles.title} numberOfLines={2}>
                {title}
              </Text>
              {lineNote ? <Text style={styles.lineNote}>{lineNote}</Text> : null}
              {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
            </View>
            <Pressable
              onPress={onClose}
              hitSlop={12}
              accessibilityRole="button"
              accessibilityLabel="Close sportsbooks"
            >
              <Ionicons name="close" size={24} color={colors.textSecondary} />
            </Pressable>
          </View>
          <ScrollView style={styles.list} bounces={false}>
            <View style={styles.listCard}>
              {rows.map((row, i) => {
                const spoken = row.price == null
                  ? `${row.name}, no price`
                  : `${row.name}, ${row.priceText}${row.isBest ? ', best price' : ''}`;
                return (
                  <Pressable
                    key={row.bookmaker}
                    onPress={() => onRow(row)}
                    accessibilityRole="button"
                    accessibilityLabel={spoken}
                    accessibilityHint={`Opens ${row.name}`}
                    style={({ pressed }) => [
                      styles.row,
                      i > 0 && styles.rowDivider,
                      row.isBest && styles.rowBest,
                      pressed && styles.pressed,
                    ]}
                  >
                    <Text style={styles.book} numberOfLines={1}>
                      {row.name}
                    </Text>
                    <View style={styles.priceSide}>
                      {row.isBest ? (
                        <View
                          style={styles.bestPill}
                          accessibilityElementsHidden
                          importantForAccessibility="no-hide-descendants"
                        >
                          <Text style={styles.bestText}>Best</Text>
                        </View>
                      ) : null}
                      <Text
                        style={[
                          styles.price,
                          row.isBest && styles.priceBest,
                          row.price == null && styles.priceMissing,
                        ]}
                      >
                        {row.priceText}
                      </Text>
                    </View>
                  </Pressable>
                );
              })}
            </View>
          </ScrollView>
          {betLabel ? (
            <Pressable
              onPress={onBet}
              accessibilityRole="button"
              accessibilityLabel={betSpeech || betLabel}
              style={({ pressed }) => [styles.bet, pressed && styles.pressed]}
            >
              <Text style={styles.betText}>{betLabel}</Text>
            </Pressable>
          ) : null}
          <Text style={styles.note}>{PICK_BOOKS_NOTE}</Text>
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
    maxHeight: '85%',
    flexShrink: 1,
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
    paddingRight: spacing.md,
  },
  title: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  lineNote: {
    marginTop: 2,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
    fontVariant: ['tabular-nums'],
  },
  subtitle: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
  },
  list: {
    flexGrow: 0,
    flexShrink: 1,
  },
  listCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    overflow: 'hidden',
  },
  row: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
  },
  rowDivider: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  rowBest: {
    backgroundColor: colors.betSoft,
  },
  book: {
    flexShrink: 1,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  priceSide: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  bestPill: {
    backgroundColor: colors.betInk,
    borderRadius: radii.pill,
    paddingVertical: 2,
    paddingHorizontal: spacing.sm,
  },
  bestText: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.textInverse,
  },
  price: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    fontVariant: ['tabular-nums'],
  },
  priceBest: {
    color: colors.betInk,
  },
  priceMissing: {
    color: colors.textSecondary,
    fontWeight: font.weight.regular,
  },
  bet: {
    marginTop: spacing.md,
    minHeight: 44,
    borderRadius: radii.pill,
    backgroundColor: colors.tint,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.lg,
  },
  betText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textInverse,
    fontVariant: ['tabular-nums'],
  },
  note: {
    marginTop: spacing.sm,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  pressed: {
    opacity: 0.6,
  },
});
