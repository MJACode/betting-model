import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { formatAmerican, formatPct } from '@/lib/format';
import { bookLabel } from '@/lib/markets';
import { isLineLeg } from '@/lib/lineLegs';
import { modelShort } from '@/lib/modelMeta';
import { colors, font, radii, spacing } from '@/lib/theme';
import { matchupForLeg, type ParlayLeg } from '@/lib/parlay';

interface Props {
  leg: ParlayLeg;
  /** Optional — when omitted (e.g. SGP suggestions) the remove control is hidden. */
  onRemove?: () => void;
  /** Optional — when omitted (e.g. manual builder) the swap control is hidden. */
  onSwap?: () => void;
}

/** Compact card for a single parlay leg, modeled on PickCard. Read-mostly with
 * trailing remove / swap controls. */
export function ParlayLegCard({ leg, onRemove, onSwap }: Props) {
  // A leg rebuilt from a saved parlay carries no live game, but its snapshot
  // kept the matchup — so it reads "MIL @ CHC / Over 8.5" here the same way it
  // does on the saved card, instead of losing the game it belongs to.
  const matchup = matchupForLeg(leg.game) ?? leg.saved?.matchup ?? null;
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
          {/* A Stats line leg has no model: its probability is the odds-implied
              one, and it says so rather than reading as a model call. */}
          <Text style={styles.stat}>
            {isLineLeg(leg) ? `implied ${formatPct(leg.modelProb)}` : formatPct(leg.modelProb)}
          </Text>
          <Text style={styles.stat}>
            {formatAmerican(leg.americanOdds)}
            {leg.dkPriced === false && leg.pricedAt ? ` · ${bookLabel(leg.pricedAt)}` : ''}
          </Text>
          {leg.bestBook ? (
            <Text style={styles.bestBook}>
              {bookLabel(leg.bestBook.bookmaker)} {formatAmerican(leg.bestBook.american)}
            </Text>
          ) : null}
        </View>
      </View>
      {onSwap || onRemove ? (
        <View style={styles.controls}>
          {onSwap ? (
            <Pressable
              onPress={onSwap}
              hitSlop={8}
              accessibilityRole="button"
              accessibilityLabel={`Swap ${leg.label} for another leg`}
              style={({ pressed }) => [styles.ctrl, pressed && styles.pressed]}
            >
              <Ionicons name="swap-horizontal-outline" size={20} color={colors.tint} />
            </Pressable>
          ) : null}
          {onRemove ? (
            <Pressable
              onPress={onRemove}
              hitSlop={8}
              accessibilityRole="button"
              accessibilityLabel={`Remove ${leg.label} from the slip`}
              style={({ pressed }) => [styles.ctrl, pressed && styles.pressed]}
            >
              <Ionicons name="close-circle-outline" size={20} color={colors.avoid} />
            </Pressable>
          ) : null}
        </View>
      ) : null}
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
  bestBook: {
    fontSize: font.size.footnote,
    color: colors.bet,
    fontWeight: font.weight.semibold,
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
