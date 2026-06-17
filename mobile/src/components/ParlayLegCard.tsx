import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { formatAmerican, formatPct } from '@/lib/format';
import { modelShort } from '@/lib/modelMeta';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { ParlayLeg } from '@/lib/parlay';

interface Props {
  leg: ParlayLeg;
  onRemove: () => void;
  /** Optional — when omitted (e.g. manual builder) the swap control is hidden. */
  onSwap?: () => void;
}

/** Compact card for a single parlay leg, modeled on PickCard. Read-mostly with
 * trailing remove / swap controls. */
export function ParlayLegCard({ leg, onRemove, onSwap }: Props) {
  const matchup = leg.game
    ? leg.game.sport === 'GOLF'
      ? leg.game.home_team
      : `${leg.game.away_team} ${leg.game.sport === 'UFC' ? 'vs' : '@'} ${leg.game.home_team}`
    : '';
  return (
    <View style={styles.card}>
      <View style={styles.body}>
        {matchup ? <Text style={styles.matchup}>{matchup}</Text> : null}
        <Text style={styles.label} numberOfLines={2}>
          {leg.label}
        </Text>
        <View style={styles.metaRow}>
          <View style={styles.modelChip}>
            <Text style={styles.modelChipText}>{modelShort(leg.modelId)}</Text>
          </View>
          <View style={[styles.tag, leg.isFavorite ? styles.favTag : styles.dogTag]}>
            <Text style={[styles.tagText, leg.isFavorite ? styles.favText : styles.dogText]}>
              {leg.isFavorite ? 'FAV' : 'DOG'}
            </Text>
          </View>
          <Text style={styles.stat}>{formatPct(leg.modelProb)}</Text>
          <Text style={styles.stat}>{formatAmerican(leg.americanOdds)}</Text>
        </View>
      </View>
      <View style={styles.controls}>
        {onSwap ? (
          <Pressable
            onPress={onSwap}
            hitSlop={8}
            style={({ pressed }) => [styles.ctrl, pressed && styles.pressed]}
          >
            <Ionicons name="swap-horizontal-outline" size={20} color={colors.tint} />
          </Pressable>
        ) : null}
        <Pressable
          onPress={onRemove}
          hitSlop={8}
          style={({ pressed }) => [styles.ctrl, pressed && styles.pressed]}
        >
          <Ionicons name="close-circle-outline" size={20} color={colors.avoid} />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    marginBottom: spacing.sm,
  },
  body: {
    flex: 1,
  },
  matchup: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
    marginBottom: 2,
  },
  label: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  modelChip: {
    backgroundColor: colors.noneSoft,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: radii.pill,
  },
  modelChipText: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontWeight: font.weight.semibold,
  },
  tag: {
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: radii.pill,
  },
  favTag: { backgroundColor: colors.betSoft },
  dogTag: { backgroundColor: '#FFF4E5' },
  tagText: {
    fontSize: 10,
    fontWeight: font.weight.semibold,
    letterSpacing: 0.4,
  },
  favText: { color: colors.bet },
  dogText: { color: colors.med },
  stat: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
  },
  controls: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    marginLeft: spacing.sm,
  },
  ctrl: {
    padding: 4,
  },
  pressed: {
    opacity: 0.5,
  },
});
