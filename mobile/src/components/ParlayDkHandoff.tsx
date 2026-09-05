import React from 'react';
import { FlatList, Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { useBettingState } from '@/hooks/useBettingState';
import { bookButtonColors, bookStoreUrl, openBookBetslip, openBookStore } from '@/lib/sportsbookLinks';
import { bookName, MODEL_BOOK } from '@/lib/markets';
import { formatAmerican } from '@/lib/format';
import { colors, font, radii, spacing } from '@/lib/theme';

/** Lightweight leg shape — works for both live ParlayLeg and SavedParlayLeg.
 * `betLink` is the leg's betslip deep link AT THE BOOK BEING HANDED OFF TO
 * (DraftKings' stored link by default; the chosen book's own link when the
 * betslip hands off to the user's book). */
export interface HandoffLeg {
  key: string;
  label: string;
  matchup: string | null;
  americanOdds: number;
  betLink: string | null;
  /** Does the hand-off book price this leg at all? A Stats line leg that
   *  DraftKings never posted is "not posted here", not "add it by hand". */
  posted?: boolean;
}

interface Props {
  visible: boolean;
  legs: HandoffLeg[];
  /** Bookmaker key to hand off to. Defaults to DraftKings. */
  book?: string;
  onClose: () => void;
}

/**
 * Leg-by-leg sportsbook hand-off. No book has a public multi-leg deep link, so
 * the honest path is: open the book once (pre-filling the first available leg),
 * then let the user add each remaining leg to their betslip and place the
 * parlay there.
 */
export function ParlayDkHandoff({ visible, legs, book = MODEL_BOOK, onClose }: Props) {
  const firstLink = legs.find((l) => l.betLink)?.betLink ?? null;
  const name = bookName(book);
  // Through the hook, not the sync read: betPARX's page depends on the state,
  // which can land after this sheet mounts.
  const { state } = useBettingState();
  const store = bookStoreUrl(book, state);
  const btn = bookButtonColors(book);

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <View style={styles.header}>
            <Text style={styles.title}>Bet on {name}</Text>
            <Pressable onPress={onClose} hitSlop={8} accessibilityRole="button" accessibilityLabel="Close">
              <Ionicons name="close" size={24} color={colors.textSecondary} />
            </Pressable>
          </View>

          <Text style={styles.note}>
            {name} can&apos;t accept a whole parlay from a link. Open {name}, then add each leg
            below to your betslip and place the parlay there.
          </Text>

          <Pressable
            onPress={() => {
              void openBookBetslip(book, firstLink);
            }}
            style={({ pressed }) => [
              styles.openBtn,
              { backgroundColor: btn.bg },
              pressed && styles.pressed,
            ]}
          >
            <Ionicons name="open-outline" size={18} color={btn.fg} />
            <Text style={[styles.openBtnText, { color: btn.fg }]}>Open in {name}</Text>
          </Pressable>
          {/* The app cannot tell whether the book is installed (see
              openBookBetslip), so the store is offered outright: "If I don't
              have the Sportsbook for one of them it should take me to the App
              Store to download it" (Matt, 2026-09-04). */}
          {store ? (
            <Pressable
              onPress={() => {
                void openBookStore(book, state);
              }}
              accessibilityRole="link"
              accessibilityLabel={`Get ${name} on the App Store`}
              hitSlop={6}
              style={({ pressed }) => [styles.storeRow, pressed && styles.pressed]}
            >
              <Ionicons name="download-outline" size={15} color={colors.tint} />
              <Text style={styles.storeText}>Get {name} on the App Store</Text>
            </Pressable>
          ) : null}

          <FlatList
            data={legs}
            keyExtractor={(l) => l.key}
            style={styles.list}
            renderItem={({ item, index }) => (
              <View style={styles.row}>
                <View style={styles.rowBody}>
                  {item.matchup ? <Text style={styles.rowMatchup}>{item.matchup}</Text> : null}
                  <Text style={styles.rowLabel} numberOfLines={2}>
                    {index + 1}. {item.label}
                  </Text>
                  <Text style={styles.rowOdds}>{formatAmerican(item.americanOdds)}</Text>
                </View>
                {item.betLink ? (
                  <Pressable
                    onPress={() => {
                      void openBookBetslip(book, item.betLink);
                    }}
                    style={({ pressed }) => [styles.addBtn, pressed && styles.pressed]}
                    hitSlop={6}
                  >
                    <Text style={styles.addBtnText}>Add to slip</Text>
                    <Ionicons name="open-outline" size={14} color={colors.tint} />
                  </Pressable>
                ) : item.posted === false ? (
                  <Text style={styles.noLink}>Not posted at {name}</Text>
                ) : (
                  <Text style={styles.noLink}>No link — add manually</Text>
                )}
              </View>
            )}
          />
        </View>
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
    paddingTop: spacing.lg,
    paddingBottom: spacing.xxl,
    maxHeight: '80%',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  title: {
    fontSize: font.size.headline,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  note: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    lineHeight: 18,
    marginBottom: spacing.md,
  },
  openBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    marginBottom: spacing.md,
  },
  openBtnText: {
    fontSize: font.size.callout,
    fontWeight: font.weight.bold,
  },
  storeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    minHeight: 44,
  },
  storeText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.tint,
    flexShrink: 1,
    textAlign: 'center',
  },
  list: {
    flexGrow: 0,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  rowBody: {
    flex: 1,
  },
  rowMatchup: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginBottom: 2,
  },
  rowLabel: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  rowOdds: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
  },
  addBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.tint,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginLeft: spacing.sm,
  },
  addBtnText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  noLink: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginLeft: spacing.sm,
    maxWidth: 90,
    textAlign: 'right',
  },
  pressed: {
    opacity: 0.6,
  },
});
