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
  linesMarketsStack,
  linesPriceText,
  type LinesMlMode,
  type LinesSheetRow,
} from '@/lib/linesBoard';
import { openBookBetslip } from '@/lib/sportsbookLinks';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * Every bettable book's price for one market. The best row — the book that
 * holds the best price on the most sides — is the only green row. A missing
 * price is "—", including the NHL regulation tie, which this read does not
 * carry (lib/linesBoard.ts).
 */
export function AllBooksSheet({
  visible,
  title,
  matchup,
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
  lineCaption: string | null;
  rows: LinesSheetRow[];
  showRegulationSwitch: boolean;
  mode: LinesMlMode;
  onMode: (mode: LinesMlMode) => void;
  onClose: () => void;
}) {
  const { fontScale } = useWindowDimensions();
  const stack = linesMarketsStack(fontScale);
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
        <Pressable style={styles.sheet} onPress={() => {}} accessible={false}>
          <View style={styles.grabber} />
          <View style={styles.header}>
            <View style={styles.headerBody}>
              <Text style={styles.title} numberOfLines={2}>
                {title}
              </Text>
              {matchup ? (
                <Text style={styles.matchup} numberOfLines={1}>
                  {matchup}
                </Text>
              ) : null}
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
                {mode === 'reg' ? LINES_REGULATION_NOTE : LINES_FULL_GAME_NOTE}
              </Text>
            </View>
          ) : null}
          {rows.length === 0 ? (
            <Text style={styles.empty}>{LINES_EMPTY_LINES}</Text>
          ) : (
            <ScrollView style={styles.list} bounces={false}>
              <View style={styles.listCard}>
                {rows.map((row, i) => (
                  <View
                    key={row.bookmaker}
                    style={[styles.row, i > 0 && styles.rowDivider, row.isBest && styles.rowBest, stack && styles.rowStack]}
                  >
                    <View style={styles.rowBody}>
                      <View style={styles.nameLine}>
                        <Text style={styles.book} numberOfLines={1}>
                          {bookName(row.bookmaker)}
                        </Text>
                        {row.isBest ? <Text style={styles.best}>Best</Text> : null}
                      </View>
                      {row.sides.map((s) => (
                        <Text
                          key={s.key}
                          style={[styles.side, s.price == null && styles.sideMissing, row.isBest && s.price != null && styles.sideBest]}
                          numberOfLines={1}
                        >
                          {s.label} {s.price == null ? LINES_NO_PRICE : linesPriceText(s.price)}
                        </Text>
                      ))}
                    </View>
                    <Pressable
                      onPress={() => {
                        void openBookBetslip(row.bookmaker, row.betLink, { sameBookOnly: true });
                      }}
                      accessibilityRole="button"
                      accessibilityLabel={`${row.betSideLabel ? `Bet ${row.betSideLabel}` : 'Bet'} at ${bookName(row.bookmaker)}${row.isBest ? ', best price' : ''}`}
                      style={({ pressed }) => [styles.bet, pressed && styles.pressed]}
                    >
                      <Text style={styles.betText} numberOfLines={2}>
                        {row.betSideLabel ? `Bet ${row.betSideLabel}` : 'Bet'}
                      </Text>
                    </Pressable>
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
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    minHeight: 44,
  },
  rowStack: {
    alignItems: 'stretch',
  },
  rowDivider: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  rowBest: {
    backgroundColor: colors.betSoft,
  },
  rowBody: {
    flex: 1,
    gap: 2,
  },
  nameLine: {
    flexDirection: 'row',
    alignItems: 'center',
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
  side: {
    fontSize: font.size.footnote,
    color: colors.textPrimary,
    fontVariant: ['tabular-nums'],
  },
  sideBest: {
    color: colors.betInk,
  },
  sideMissing: {
    color: colors.textSecondary,
  },
  bet: {
    minHeight: 44,
    maxWidth: 128,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
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
