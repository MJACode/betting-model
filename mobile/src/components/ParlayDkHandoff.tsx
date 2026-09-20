import React from 'react';
import { FlatList, Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { useBettingState } from '@/hooks/useBettingState';
import { useBookAppInstalled } from '@/hooks/useBookAppInstalled';
import { combineBetslipLinks } from '@/lib/betslipLinks';
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
 * Sportsbook hand-off for a multi-leg slip.
 *
 * `combineBetslipLinks` joins every linked leg into one URL on books whose
 * stored link has a measured multi-selection form (DraftKings `outcomes=`,
 * FanDuel indexed market/selection, BetMGM `options=`, Caesars
 * `selectionIds=`, ESPN BET indexed market_selection_id). Opening that URL
 * is what puts ALL intended picks on the slip — opening only the first
 * linked leg is the bug Matt reported. Books we cannot combine still open the
 * first linked leg; the per-leg "Add to slip" row is how the rest get there.
 */
export function ParlayDkHandoff({ visible, legs, book = MODEL_BOOK, onClose }: Props) {
  const linked = legs.map((l) => l.betLink).filter((u): u is string => !!u && !!u.trim());
  const combined = combineBetslipLinks(linked);
  // A book we cannot join still opens the first linked leg — same as before
  // this fix — so Hard Rock / BetRivers do not lose the one-pick hand-off.
  const openLink = combined ?? linked[0] ?? null;
  const combinedCount = combined && linked.length > 1 ? linked.length : 0;
  const name = bookName(book);
  // Through the hook, not the sync read: betPARX's page depends on the state,
  // which can land after this sheet mounts.
  const { state } = useBettingState();
  const store = bookStoreUrl(book, state);
  const btn = bookButtonColors(book);
  // true / false when the build can ask iOS, null when it cannot (or while
  // the answer loads). The store row is hidden only on a definite yes.
  const installed = useBookAppInstalled(book);

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      {/* Backdrop tap dismisses, as every other sheet in the app does — the X
          alone sits in the one corner a thumb cannot reach (UX review). */}
      <Pressable style={styles.backdrop} onPress={onClose} accessibilityRole="button" accessibilityLabel="Close">
        {/* accessible={false}: an accessible Pressable groups its children into
            ONE VoiceOver element, which would leave the rows unreachable. */}
        <Pressable style={styles.sheet} onPress={() => {}} accessible={false} accessibilityViewIsModal>
          <View style={styles.header}>
            <Text style={styles.title}>Bet on {name}</Text>
            <Pressable onPress={onClose} hitSlop={8} accessibilityRole="button" accessibilityLabel="Close">
              <Ionicons name="close" size={24} color={colors.textSecondary} />
            </Pressable>
          </View>

          <Text style={styles.note}>
            {combinedCount > 0 && combinedCount === legs.length
              ? `Open ${name} with all ${combinedCount} legs on your slip, then place the parlay there.`
              : combinedCount > 0
                ? `Open ${name} with ${combinedCount} of ${legs.length} legs on your slip. ${
                    legs.length - combinedCount === 1
                      ? `The other leg isn't on a link — add it in ${name}`
                      : `The other ${legs.length - combinedCount} legs aren't on a link — add them in ${name}`
                  }, then place the parlay there.`
                : legs.length <= 1
                  ? `Open ${name} with this bet on your slip.`
                  : `${name} can't take every leg from one link. Open ${name}, then add each leg below to your betslip and place the parlay there.`}
            {book !== MODEL_BOOK
              ? ` Prices below are ${name}'s — the models still score at ${bookName(MODEL_BOOK)}.`
              : ''}
          </Text>

          <Pressable
            onPress={() => {
              void openBookBetslip(book, openLink);
            }}
            accessibilityRole="button"
            accessibilityLabel={
              combinedCount > 0
                ? `Open in ${name} with ${combinedCount} picks`
                : `Open in ${name}`
            }
            style={({ pressed }) => [
              styles.openBtn,
              { backgroundColor: btn.bg },
              pressed && styles.pressed,
            ]}
          >
            <Ionicons name="open-outline" size={18} color={btn.fg} />
            <Text style={[styles.openBtnText, { color: btn.fg }]}>Open in {name}</Text>
          </Pressable>
          {/* "If I don't have the Sportsbook for one of them it should take me
              to the App Store to download it" (Matt, 2026-09-04). Offered
              outright unless the build can tell the app IS installed
              (useBookAppInstalled) — a member with the app has no use for the
              store, and an unknown is not a no. */}
          {store && installed !== true ? (
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
                    accessibilityRole="button"
                    accessibilityLabel={`Add ${item.label} to slip`}
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
