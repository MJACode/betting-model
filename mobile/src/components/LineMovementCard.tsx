import React, { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { formatAmerican, formatGameTimeET } from '@/lib/format';
import { canShowLineMovementHistory, formatSideLine, gameMarketForModel, historyBookForPick, isNflLineOnly, lineForSide, lineFromSnapshot, movementFromSameBookHistory, priceForSide, propMarketForModel, type PricedSnapshot, bookName, storedQuoteBook } from '@/lib/markets';
import { fetchOddsHistory, fetchPropOddsHistory } from '@/lib/queries';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { Pick } from '@/types';
import { decisionOdds } from '@/lib/decisionPrice';

interface Props {
  pick: Pick;
  /** Player name parsed from pick_label (prop picks only). */
  playerName: string | null;
}

interface Snap extends PricedSnapshot {
  snapshot_at: string;
}

/**
 * Same-book price/line history since the pick was scored. Steam against
 * the lock is the "don't bet this anymore" signal. Fetch is the deciding
 * book (`historyBookForPick`), never a hard-coded DraftKings series.
 */
export function LineMovementCard({ pick, playerName }: Props) {
  const [snaps, setSnaps] = useState<Snap[] | null>(null);

  const isProp = pick.model_id.includes('prop');
  const market = isProp ? propMarketForModel(pick.model_id) : gameMarketForModel(pick.model_id);
  const historyBook = historyBookForPick(pick);

  useEffect(() => {
    let mounted = true;
    if (
      !canShowLineMovementHistory(pick) ||
      historyBook == null ||
      market == null ||
      (isProp && !playerName)
    ) {
      setSnaps([]);
      return undefined;
    }
    const load = isProp
      ? fetchPropOddsHistory(pick.game_id, market, playerName!, historyBook)
      : fetchOddsHistory(pick.game_id, market, historyBook);
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
  }, [pick.pick_id, pick.game_id, historyBook, market, isProp, playerName]);

  if (!snaps || snaps.length === 0 || market == null) return null;

  // NFL game lines compare LINE only (soft-book price is not the snapshot
  // book). Props are not lineOnly — they steam at the deciding book.
  const lineOnly = isNflLineOnly(pick.model_id);
  const latest = snaps[snaps.length - 1];
  const movement = movementFromSameBookHistory(pick, latest, market);
  const lockedPrice = decisionOdds(pick);
  const currentPrice = priceForSide(latest, pick.pick_side);
  const currentLine = lineFromSnapshot(latest, market);

  const verdict = (() => {
    if (!movement) {
      return { label: 'Line steady since pick', color: colors.textSecondary };
    }
    if (movement.severity === 'skip') {
      return {
        label:
          `Line moved ${formatSideLine(movement.scoredLine, pick.pick_side, market)} → ` +
          `${formatSideLine(movement.currentLine, pick.pick_side, market)} against your ${pick.pick_side}`,
        color: colors.avoid,
      };
    }
    if (movement.lineOnly) {
      return {
        label:
          `Line moved ${formatSideLine(movement.scoredLine, pick.pick_side, market)} → ` +
          `${formatSideLine(movement.currentLine, pick.pick_side, market)} in your favor`,
        color: colors.bet,
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
        {lineOnly ? (
          <Text style={styles.prices}>
            {`${formatSideLine(pick.scored_line, pick.pick_side, market)} → ` +
              `${formatSideLine(currentLine, pick.pick_side, market)}`}
          </Text>
        ) : (
          <Text style={styles.prices}>
            {`${formatAmerican(lockedPrice)} → ${formatAmerican(currentPrice)}`}
          </Text>
        )}
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
            <Text style={styles.cell}>
              {lineForSide(lineFromSnapshot(s, market), pick.pick_side, market) ?? '—'}
            </Text>
          ) : null}
          <Text style={styles.cell}>{formatAmerican(priceForSide(s, pick.pick_side))}</Text>
        </View>
      ))}
      {snaps.length > recent.length ? (
        <Text style={styles.more}>Showing last {recent.length} of {snaps.length} snapshots</Text>
      ) : null}
      <Text style={styles.note}>
        {lineOnly
          ? `Your pick is locked at the number the card took — ` +
            `${formatSideLine(pick.scored_line, pick.pick_side, market)} at ` +
            `${formatAmerican(lockedPrice)} (the book is named in the pick). The table shows ` +
            `${bookName(historyBook ?? storedQuoteBook(pick))}'s line since. It doesn't change the pick or how ` +
            `it settles.`
          : `Your pick was decided at ${bookName(historyBook ?? storedQuoteBook(pick))} ${formatAmerican(lockedPrice)}` +
            `${showLineCol && movement?.scoredLine != null ? ` (${formatSideLine(movement.scoredLine, pick.pick_side, market)})` : ''}. ` +
            `This just shows how that book's line has moved since, for or against you. It doesn't ` +
            `change the pick or how it settles.`}
      </Text>
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
  note: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    lineHeight: 16,
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
});
