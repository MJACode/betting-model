import React, { useEffect, useMemo, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { formatAmerican } from '@/lib/format';
import {
  changesFooter,
  historyTimeLabel,
  LINE_HISTORY_PAGE,
  lineHistoryWindow,
  movementHeadline,
  movementVerdict,
  recentChanges,
  type MovementVerdictKind,
} from '@/lib/lineHistory';
import { canShowLineMovementHistory, formatSideLine, gameMarketForModel, historyBookForPick, isNflLineOnly, lineForSide, lineFromSnapshot, movementFromSameBookHistory, priceForSide, propMarketForModel, type PricedSnapshot, bookName, storedQuoteBook } from '@/lib/markets';
import { fetchOddsHistory, fetchPropOddsHistory } from '@/lib/queries';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { Pick } from '@/types';
import { decisionOdds } from '@/lib/decisionPrice';

interface Props {
  pick: Pick;
  /** Player name parsed from pick_label (prop picks only). */
  playerName: string | null;
  /** games.commence_time, or the pick's game_time when the games row is missing. */
  commenceTime?: string | null;
  /** Live or over. The last pregame row is then the close, not the current number. */
  gameStarted?: boolean;
}

interface Snap extends PricedSnapshot {
  snapshot_at: string;
}

/**
 * Same-book price/line history since the pick was scored. Steam against
 * the lock is the "don't bet this anymore" signal. Fetch is the deciding
 * book (`historyBookForPick`), never a hard-coded DraftKings series.
 */
export function LineMovementCard({ pick, playerName, commenceTime, gameStarted = false }: Props) {
  const [snaps, setSnaps] = useState<Snap[] | null>(null);
  const [moveByAt, setMoveByAt] = useState<ReadonlySet<string>>(new Set());

  const isProp = pick.model_id.includes('prop');
  const market = isProp ? propMarketForModel(pick.model_id) : gameMarketForModel(pick.model_id);
  const historyBook = historyBookForPick(pick);
  const historyWindow = useMemo(
    () =>
      lineHistoryWindow({
        commenceTime,
        createdAt: pick.created_at,
        isLive: pick.is_live,
      }),
    [commenceTime, pick.created_at, pick.is_live],
  );
  // Capped series: the last row is the last pregame snapshot. A live pick's
  // last row is in-play, so it stays unlabeled.
  const atClose = gameStarted && historyWindow.until != null;

  useEffect(() => {
    let mounted = true;
    if (
      !canShowLineMovementHistory(pick) ||
      historyBook == null ||
      market == null ||
      (isProp && !playerName)
    ) {
      setSnaps([]);
      setMoveByAt(new Set());
      return undefined;
    }
    const load = isProp
      ? fetchPropOddsHistory(pick.game_id, market, playerName!, historyBook, historyWindow)
      : fetchOddsHistory(pick.game_id, market, historyBook, historyWindow);
    load
      .then((sample) => {
        if (mounted) {
          setSnaps(sample.rows as Snap[]);
          setMoveByAt(new Set(sample.moveByAt));
        }
      })
      .catch(() => {
        if (mounted) {
          setSnaps([]);
          setMoveByAt(new Set());
        }
      });
    return () => {
      mounted = false;
    };
  }, [pick.pick_id, pick.game_id, historyBook, market, isProp, playerName, historyWindow]);

  if (!snaps || snaps.length === 0 || market == null) return null;

  // NFL game lines compare LINE only (soft-book price is not the snapshot
  // book). Props are not lineOnly — they steam at the deciding book.
  const lineOnly = isNflLineOnly(pick.model_id);
  const latest = snaps[snaps.length - 1];
  const movement = movementFromSameBookHistory(pick, latest, market);
  const lockedPrice = decisionOdds(pick);
  const currentPrice = priceForSide(latest, pick.pick_side);
  const currentLine = lineFromSnapshot(latest, market);

  const verdictKind: MovementVerdictKind = !movement
    ? 'steady'
    : movement.severity === 'skip'
      ? 'against'
      : movement.lineOnly
        ? 'favor'
        : movement.severity === 'caution'
          ? 'steamed'
          : 'eased';
  const verdict = {
    label: movementVerdict({
      kind: verdictKind,
      atClose,
      lock: formatSideLine(movement?.scoredLine ?? pick.scored_line, pick.pick_side, market),
      end: formatSideLine(movement?.currentLine ?? currentLine, pick.pick_side, market),
      pp: movement?.priceShiftPp,
    }),
    color:
      verdictKind === 'against' || verdictKind === 'steamed'
        ? colors.avoidInk
        : verdictKind === 'favor' || verdictKind === 'eased'
          ? colors.betInk
          : colors.textSecondary,
  };

  const showLineCol = market.startsWith('totals') || market.startsWith('spreads') || isProp;
  // A full latest page means the table holds more rows than this series.
  // The footer must not quote the sample length as the book's whole history.
  const partial = snaps.length > LINE_HISTORY_PAGE;
  // M13: a row is a CHANGE, not a raw snapshot — runs at the same line and
  // price collapse, and rows sharing a minute get seconds (lib/lineHistory).
  const { rows: recent, changes, shownChanges, hidden } = recentChanges(
    snaps.map((s) => ({
      at: s.snapshot_at,
      line: showLineCol ? lineForSide(lineFromSnapshot(s, market), pick.pick_side, market) : null,
      price: priceForSide(s, pick.pick_side),
    })),
  );

  return (
    <View style={styles.card}>
      <Text style={styles.heading}>Line Movement</Text>
      <View style={styles.headRow}>
        <Text style={styles.prices}>
          {movementHeadline(
            lineOnly
              ? formatSideLine(pick.scored_line, pick.pick_side, market)
              : formatAmerican(lockedPrice),
            lineOnly ? formatSideLine(currentLine, pick.pick_side, market) : formatAmerican(currentPrice),
            atClose,
          )}
        </Text>
        <Text style={[styles.verdict, { color: verdict.color }]}>{verdict.label}</Text>
      </View>

      <View style={styles.tableHead}>
        <Text style={[styles.cell, styles.cellTime, styles.headText]}>Changed at</Text>
        {showLineCol ? <Text style={[styles.cell, styles.headText]}>Line</Text> : null}
        <Text style={[styles.cell, styles.headText]}>Price</Text>
      </View>
      {recent.map((r, i) => (
        <View key={r.key} style={styles.row}>
          <Text style={[styles.cell, styles.cellTime]}>
            {historyTimeLabel(r.label, {
              atCloseLast: atClose && i === recent.length - 1,
              bounded: moveByAt.has(r.at),
            })}
          </Text>
          {showLineCol ? <Text style={styles.cell}>{r.line ?? '—'}</Text> : null}
          <Text style={styles.cell}>{formatAmerican(r.price)}</Text>
        </View>
      ))}
      {hidden > 0 || snaps.length > recent.length ? (
        <Text style={styles.more}>
          {changesFooter({ changes, shownChanges, hidden }, snaps.length, partial)}
        </Text>
      ) : null}
      <Text style={styles.note}>
        {lineOnly
          ? `Your pick is locked at the number the card took — ` +
            `${formatSideLine(pick.scored_line, pick.pick_side, market)} at ` +
            `${formatAmerican(lockedPrice)} (the book is named in the pick). ` +
            (partial
              ? `The table samples ${bookName(historyBook ?? storedQuoteBook(pick))}'s line from the open through the ${atClose ? 'close' : 'latest snapshots'}, not every tick. `
              : `The table shows ${bookName(historyBook ?? storedQuoteBook(pick))}'s line ${atClose ? 'through the close' : 'since'}. `) +
            `It doesn't change the pick or how it settles.`
          : `Your pick was decided at ${bookName(historyBook ?? storedQuoteBook(pick))} ${formatAmerican(lockedPrice)}` +
            `${showLineCol && movement?.scoredLine != null ? ` (${formatSideLine(movement.scoredLine, pick.pick_side, market)})` : ''}. ` +
            (atClose
              ? `The second number is the closing line, the last price before the game started. `
              : '') +
            (partial
              ? `This samples how that book's line has moved ${atClose ? 'up to the close' : 'since'}, not every tick. It doesn't `
              : `This just shows how that book's line has moved ${atClose ? 'up to the close' : 'since'}, for or against you. It doesn't `) +
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
