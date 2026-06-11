import React, { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { formatAmerican, formatGameTimeET } from '@/lib/format';
import {
  computeMovement,
  gameMarketForModel,
  lineFromSnapshot,
  priceForSide,
  propMarketForModel,
  type PricedSnapshot,
} from '@/lib/markets';
import { fetchOddsHistory, fetchPropOddsHistory } from '@/lib/queries';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { Pick } from '@/types';

interface Props {
  pick: Pick;
  /** Player name parsed from pick_label (prop picks only). */
  playerName: string | null;
}

interface Snap extends PricedSnapshot {
  snapshot_at: string;
}

/**
 * DK price/line history since the pick was scored. Steam moving against the
 * pick is the single best "don't bet this anymore" signal between refreshes.
 */
export function LineMovementCard({ pick, playerName }: Props) {
  const [snaps, setSnaps] = useState<Snap[] | null>(null);

  const isProp = pick.model_id.includes('prop');
  const market = isProp ? propMarketForModel(pick.model_id) : gameMarketForModel(pick.model_id);

  useEffect(() => {
    let mounted = true;
    if (pick.dk_odds == null || market == null || (isProp && !playerName)) {
      setSnaps([]);
      return undefined;
    }
    const load = isProp
      ? fetchPropOddsHistory(pick.game_id, market, playerName!)
      : fetchOddsHistory(pick.game_id, market);
    load
      .then((rows) => {
        if (mounted) setSnaps(rows as Snap[]);
      })
      .catch(() => {
        if (mounted) setSnaps([]);
      });
    return () => {
      mounted = false;
    };
  }, [pick.pick_id, pick.game_id, pick.dk_odds, market, isProp, playerName]);

  if (!snaps || snaps.length === 0 || market == null) return null;

  const latest = snaps[snaps.length - 1];
  const movement = computeMovement(pick, latest, market);
  const currentPrice = priceForSide(latest, pick.pick_side);

  const verdict = (() => {
    if (!movement) {
      return { label: 'Line steady since pick', color: colors.textSecondary };
    }
    if (movement.severity === 'skip') {
      return {
        label: `Line moved ${movement.scoredLine} → ${movement.currentLine} against your ${pick.pick_side}`,
        color: colors.avoid,
      };
    }
    const pp = movement.priceShiftPp ?? 0;
    if (movement.severity === 'caution') {
      return {
        label: `Steamed ${pp.toFixed(1)}pp against you since scoring`,
        color: colors.avoid,
      };
    }
    return {
      label: `Moved ${Math.abs(pp).toFixed(1)}pp in your favor since scoring`,
      color: colors.bet,
    };
  })();

  const showLineCol = market.startsWith('totals') || market.startsWith('spreads') || isProp;
  const recent = snaps.slice(-8);

  return (
    <View style={styles.card}>
      <Text style={styles.heading}>Line Movement</Text>
      <View style={styles.headRow}>
        <Text style={styles.prices}>
          {formatAmerican(pick.dk_odds)} → {formatAmerican(currentPrice)}
        </Text>
        <Text style={[styles.verdict, { color: verdict.color }]}>{verdict.label}</Text>
      </View>

      <View style={styles.tableHead}>
        <Text style={[styles.cell, styles.cellTime, styles.headText]}>Snapshot</Text>
        {showLineCol ? <Text style={[styles.cell, styles.headText]}>Line</Text> : null}
        <Text style={[styles.cell, styles.headText]}>Price</Text>
      </View>
      {recent.map((s) => (
        <View key={s.snapshot_at} style={styles.row}>
          <Text style={[styles.cell, styles.cellTime]}>{formatGameTimeET(s.snapshot_at)}</Text>
          {showLineCol ? (
            <Text style={styles.cell}>{lineFromSnapshot(s, market) ?? '—'}</Text>
          ) : null}
          <Text style={styles.cell}>{formatAmerican(priceForSide(s, pick.pick_side))}</Text>
        </View>
      ))}
      {snaps.length > recent.length ? (
        <Text style={styles.more}>Showing last {recent.length} of {snaps.length} snapshots</Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  heading: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginBottom: 4,
  },
  headRow: {
    marginBottom: spacing.sm,
  },
  prices: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  verdict: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    marginTop: 2,
  },
  tableHead: {
    flexDirection: 'row',
    paddingBottom: 4,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  headText: {
    color: colors.textTertiary,
    fontSize: font.size.caption,
  },
  row: {
    flexDirection: 'row',
    paddingVertical: 4,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  cell: {
    flex: 1,
    fontSize: font.size.footnote,
    color: colors.textPrimary,
    textAlign: 'right',
  },
  cellTime: {
    flex: 1.6,
    textAlign: 'left',
    color: colors.textSecondary,
  },
  more: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginTop: spacing.sm,
  },
});
