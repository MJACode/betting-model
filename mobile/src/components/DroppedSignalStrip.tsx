import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { formatGameTimeET, formatPct, formatPctSigned } from '@/lib/format';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { DropReason } from '@/lib/signalBoard';
import type { OpeningSignalRow } from '@/types';

type IoniconName = React.ComponentProps<typeof Ionicons>['name'];

const REASON_META: Record<
  DropReason,
  { label: string; color: string; soft: string; icon: IoniconName }
> = {
  avoid: { label: 'Flipped to Avoid', color: colors.avoid, soft: colors.avoidSoft, icon: 'close-circle-outline' },
  weakened: { label: 'Weakened', color: colors.med, soft: '#FFF4E5', icon: 'trending-down-outline' },
  none: { label: 'No signal', color: colors.none, soft: colors.noneSoft, icon: 'remove-circle-outline' },
  off_board: { label: 'Off the board', color: colors.none, soft: colors.noneSoft, icon: 'eye-off-outline' },
};

/**
 * Movement banner shown above a Dropped signal's PickCard: a colored badge for
 * what it became now, plus the locked-open snapshot (when + how strong the
 * signal was when it first fired) so the movement is always visible.
 */
export function DroppedSignalStrip({
  reason,
  opening,
}: {
  reason: DropReason;
  opening: OpeningSignalRow;
}) {
  const meta = REASON_META[reason];
  const lockedAt = formatGameTimeET(opening.locked_at);
  const wasStrength =
    opening.edge != null
      ? `${formatPctSigned(opening.edge)} edge`
      : formatPct(opening.model_probability);

  return (
    <View style={styles.wrap}>
      <View style={[styles.badge, { backgroundColor: meta.soft }]}>
        <Ionicons name={meta.icon} size={13} color={meta.color} />
        <Text style={[styles.badgeText, { color: meta.color }]}>{meta.label}</Text>
      </View>
      <Text style={styles.note} numberOfLines={1}>
        Locked{lockedAt ? ` ${lockedAt}` : ''} · was {wasStrength}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginHorizontal: spacing.lg,
    marginBottom: -spacing.xs,
    paddingHorizontal: spacing.sm,
  },
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: font.weight.semibold,
  },
  note: {
    flex: 1,
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
});
