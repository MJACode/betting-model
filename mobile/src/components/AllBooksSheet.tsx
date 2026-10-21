import React from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { SegmentTabs } from '@/components/GroupTabs';
import { bookName } from '@/lib/markets';
import {
  LINES_EMPTY_LINES,
  LINES_FULL_GAME_NOTE,
  LINES_NO_PRICE,
  LINES_REGULATION_NOTE,
  LINES_REGULATION_NOTE_PRICED,
  linesMarketsStack,
  linesPriceText,
  type LinesMlMode,
  type LinesSheetRow,
} from '@/lib/linesBoard';
import { openBookBetslip } from '@/lib/sportsbookLinks';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * Every bettable book's price for one market. Green is a price that wins
 * its side, and the word Best is on a row only when that book wins every
 * side. Each side with a link has its own Bet. The tie is absent until a
 * row carries draw_price (lib/linesBoard.ts).
 */
function SidePrice({ price, best }: { price: string; best: boolean }) {
  return (
    <View style={styles.priceLine}>
      <Text style={[styles.sidePrice, best && styles.sideBest]}>{price}</Text>
      {best ? (
        <Ionicons
          name="checkmark"
          size={16}
          color={colors.betInk}
          accessibilityElementsHidden
          importantForAccessibility="no"
        />
      ) : null}
    </View>
  );
}

export function AllBooksSheet({
  visible,
  title,
  matchup,
  when,
  lineCaption,
  rows,
  showRegulationSwitch,
  mode,
  onMode,
  onClose,
}: {
  visible: boolean;
  title: string;
  matchup: string;
  when: string;
  lineCaption: string | null;
  rows: LinesSheetRow[];
  showRegulationSwitch: boolean;
  mode: LinesMlMode;
  onMode: (mode: LinesMlMode) => void;
  onClose: () => void;
}) {
  const { fontScale } = useWindowDimensions();
  const stack = linesMarketsStack(fontScale);
  const tieShown = rows.some((row) => row.sides.some((s) => s.key === 'tie'));
  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <Pressable
          style={StyleSheet.absoluteFill}
          onPress={onClose}
          accessibilityRole="button"
          accessibilityLabel="Close lines"
        />
        {/* accessible={false}: an accessible Pressable groups its children into
            ONE VoiceOver element. VoiceOver must reach the rows and Bet buttons. */}
        <Pressable style={styles.sheet} onPress={() => {}} accessible={false} accessibilityViewIsModal>
          <View style={styles.grabber} />
          <View style={styles.header}>
            <View style={styles.headerBody}>
              <Text style={styles.title} numberOfLines={2}>
                {title}
              </Text>
              {matchup ? <Text style={styles.matchup}>{matchup}</Text> : null}
              {when ? <Text style={styles.matchup}>{when}</Text> : null}
              {lineCaption ? <Text style={styles.lineCaption}>{lineCaption}</Text> : null}
            </View>
            <Pressable
              onPress={onClose}
              hitSlop={12}
              accessibilityRole="button"
              accessibilityLabel="Close lines"
            >
              <Ionicons name="close" size={24} color={colors.textSecondary} />
            </Pressable>
          </View>
          {showRegulationSwitch ? (
            <View style={styles.switchWrap}>
              <SegmentTabs
                items={['full', 'reg'] as const}
                active={mode}
                onChange={onMode}
                labelFor={(item) => (item === 'full' ? 'Full game' : '60 min')}
                fit
              />
              <Text style={styles.note}>
                {mode === 'reg' ? (tieShown ? LINES_REGULATION_NOTE_PRICED : LINES_REGULATION_NOTE) : LINES_FULL_GAME_NOTE}
              </Text>
            </View>
          ) : null}
          {rows.length === 0 ? (
            <Text style={styles.empty}>{LINES_EMPTY_LINES}</Text>
          ) : (
            <ScrollView style={styles.list} bounces={false}>
              <View style={styles.listCard}>
                {rows.map((row, i) => (
                  <View key={row.bookmaker} style={[styles.row, i > 0 && styles.rowDivider, stack && styles.rowStack]}>
                    <View style={styles.nameLine}>
                      <Text style={styles.book}>{bookName(row.bookmaker)}</Text>
                      {row.isBest ? <Text style={styles.best}>Best</Text> : null}
                    </View>
                    {row.sides.map((s) => {
                      const price = s.price == null ? LINES_NO_PRICE : linesPriceText(s.price);
                      const book = bookName(row.bookmaker);
                      const best = s.isBestPrice ? ', best price' : '';
                      if (s.price == null) {
                        return (
                          <View key={s.key} style={styles.sideRow}>
                            <View style={styles.sideBody}>
                              <Text style={styles.side}>{s.label}</Text>
                              <Text style={[styles.sidePrice, styles.sideMissing]}>{LINES_NO_PRICE}</Text>
                            </View>
                          </View>
                        );
                      }
                      const quoted = `${s.label}, ${price} at ${book}${best}`;
                      // A price with no link is not a bet. Opening the book
                      // with an empty slip, or alerting that it could not open,
                      // is a different action from the one the button names.
                      if (!s.link || !s.link.trim()) {
                        return (
                          <View key={s.key} style={styles.sideRow} accessible accessibilityLabel={quoted}>
                            <View style={styles.sideBody}>
                              <Text style={styles.side}>{s.label}</Text>
                              <SidePrice price={price} best={s.isBestPrice} />
                            </View>
                          </View>
                        );
                      }
                      return (
                        <Pressable
                          key={s.key}
                          onPress={() => {
                            void openBookBetslip(row.bookmaker, s.link, { sameBookOnly: true });
                          }}
                          accessibilityRole="button"
                          accessibilityLabel={`Bet ${quoted}`}
                          style={({ pressed }) => [styles.sideRow, pressed && styles.pressed]}
                        >
                          <View style={styles.sideBody}>
                            <Text style={styles.side}>{s.label}</Text>
                            <SidePrice price={price} best={s.isBestPrice} />
                          </View>
                          <View style={styles.bet}>
                            <Text style={styles.betText}>Bet</Text>
                          </View>
                        </Pressable>
                      );
                    })}
                  </View>
                ))}
              </View>
            </ScrollView>
          )}
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
  matchup: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
  },
  lineCaption: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
  },
  switchWrap: {
    marginBottom: spacing.md,
  },
  note: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    lineHeight: 18,
    marginTop: spacing.sm,
  },
  empty: {
    fontSize: font.size.body,
    color: colors.textSecondary,
    paddingVertical: spacing.lg,
  },
  list: {
    flexGrow: 0,
  },
  listCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
  },
  row: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    gap: spacing.xs,
  },
  rowStack: {
    alignItems: 'stretch',
  },
  rowDivider: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  nameLine: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  book: {
    flexShrink: 1,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  best: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.betInk,
  },
  sideRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    minHeight: 44,
  },
  sideBody: {
    flex: 1,
    gap: 2,
  },
  side: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  priceLine: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  sidePrice: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    fontVariant: ['tabular-nums'],
  },
  sideBest: {
    color: colors.betInk,
  },
  sideMissing: {
    color: colors.textSecondary,
    fontWeight: font.weight.regular,
  },
  bet: {
    minHeight: 44,
    minWidth: 64,
    paddingHorizontal: spacing.md,
    borderRadius: radii.sm,
    backgroundColor: colors.tint,
    alignItems: 'center',
    justifyContent: 'center',
  },
  betText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textInverse,
    textAlign: 'center',
  },
  pressed: {
    opacity: 0.6,
  },
});
