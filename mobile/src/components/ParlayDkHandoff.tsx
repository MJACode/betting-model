import React from 'react';
import { FlatList, Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { DK_GREEN, openBetslip } from '@/lib/draftkings';
import { formatAmerican } from '@/lib/format';
import { colors, font, radii, spacing } from '@/lib/theme';

/** Lightweight leg shape — works for both live ParlayLeg and SavedParlayLeg. */
export interface HandoffLeg {
  key: string;
  label: string;
  matchup: string | null;
  americanOdds: number;
  dkBetLink: string | null;
}

interface Props {
  visible: boolean;
  legs: HandoffLeg[];
  onClose: () => void;
}

/**
 * Leg-by-leg DraftKings hand-off. DK has no public multi-leg deep link, so the
 * honest path is: open DK once (pre-filling the first available leg), then let
 * the user add each remaining leg to their DK betslip and place the parlay there.
 */
export function ParlayDkHandoff({ visible, legs, onClose }: Props) {
  const firstLink = legs.find((l) => l.dkBetLink)?.dkBetLink ?? null;

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <View style={styles.header}>
            <Text style={styles.title}>Bet on DraftKings</Text>
            <Pressable onPress={onClose} hitSlop={8}>
              <Ionicons name="close" size={24} color={colors.textSecondary} />
            </Pressable>
          </View>

          <Text style={styles.note}>
            DraftKings can&apos;t accept a whole parlay from a link. Open DK, then add each leg
            below to your betslip and place the parlay there.
          </Text>

          <Pressable
            onPress={() => {
              void openBetslip(firstLink);
            }}
            style={({ pressed }) => [styles.openBtn, pressed && styles.pressed]}
          >
            <Ionicons name="open-outline" size={18} color="#000" />
            <Text style={styles.openBtnText}>Open in DraftKings</Text>
          </Pressable>

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
                {item.dkBetLink ? (
                  <Pressable
                    onPress={() => {
                      void openBetslip(item.dkBetLink);
                    }}
                    style={({ pressed }) => [styles.addBtn, pressed && styles.pressed]}
                    hitSlop={6}
                  >
                    <Text style={styles.addBtnText}>Add to slip</Text>
                    <Ionicons name="open-outline" size={14} color={colors.tint} />
                  </Pressable>
                ) : (
                  <Text style={styles.noLink}>No DK link — add manually</Text>
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
    backgroundColor: DK_GREEN,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    marginBottom: spacing.md,
  },
  openBtnText: {
    color: '#000',
    fontSize: font.size.callout,
    fontWeight: font.weight.bold,
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
