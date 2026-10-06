import React, { useEffect, useMemo, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import {
  changesFooter,
  formatHistoryAmerican,
  formatHistoryLine,
  historyRowAccessibilityLabel,
  historyTimeLabel,
  inPlayMovementLabel,
  LINE_HISTORY_PAGE,
  lineHistoryWindow,
  movementHeadline,
  movementHeadlineLabel,
  movementVerdict,
  recentChanges,
  type MovementVerdictKind,
} from '@/lib/lineHistory';
import { canShowLineMovementHistory, gameMarketForModel, historyBookForPick, isNflLineOnly, lineForSide, lineFromSnapshot, movementFromSameBookHistory, priceForSide, propMarketForModel, type PricedSnapshot, bookName, storedQuoteBook } from '@/lib/markets';
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
  // Capped series: the last row is the last pregame snapshot. A true live
  // pick (is_live only) ends on Final, not Close.
  const inPlay = pick.is_live === true;
  const atClose = gameStarted && historyWindow.until != null && !inPlay;

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
    // The other side's price is not this pick's line. A tick there must not
    // move the time the card prints.
    const sideQuote = (snap: Snap) => {
      const showLine =
        market != null && (market.startsWith('totals') || market.startsWith('spreads') || isProp);
      const line =
        showLine && market != null
          ? lineForSide(lineFromSnapshot(snap, market), pick.pick_side, market)
          : null;
      return `${line ?? ''}|${priceForSide(snap, pick.pick_side) ?? ''}`;
    };
    const load = isProp
      ? fetchPropOddsHistory(pick.game_id, market, playerName!, historyBook, historyWindow, sideQuote)
      : fetchOddsHistory(pick.game_id, market, historyBook, historyWindow, sideQuote);
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
  }, [pick.pick_id, pick.game_id, pick.pick_side, historyBook, market, isProp, playerName, historyWindow]);

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
  // Spreads show a sign. The verdict uses the same minus as the headline
  // on this card (U+2212), so a negative number does not switch glyphs.
  const signLine = market.startsWith('spreads');
  const verdictLine = (line: number | null) =>
    formatHistoryLine(lineForSide(line, pick.pick_side, market), signLine);
  // A green "in your favor" on an in-play price read a loss as a win.
  // Live picks get one neutral sentence. Pregame keeps the colored verdict.
  const verdict = inPlay
    ? { label: inPlayMovementLabel(), color: colors.textSecondary }
    : {
        label: movementVerdict({
          kind: verdictKind,
          atClose,
          lock: verdictLine(movement?.scoredLine ?? pick.scored_line),
          end: verdictLine(movement?.currentLine ?? currentLine),
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
  const book = bookName(historyBook ?? storedQuoteBook(pick));
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
        <Text
          style={styles.prices}
          accessibilityLabel={movementHeadlineLabel({
            kind: lineOnly ? 'line' : 'price',
            lock: lineOnly ? lineForSide(pick.scored_line, pick.pick_side, market) : lockedPrice,
            end: lineOnly ? lineForSide(currentLine, pick.pick_side, market) : currentPrice,
            atClose,
            signedLine: signLine,
          })}
        >
          {movementHeadline(
            lineOnly
              ? formatHistoryLine(lineForSide(pick.scored_line, pick.pick_side, market), signLine)
              : formatHistoryAmerican(lockedPrice),
            lineOnly
              ? formatHistoryLine(lineForSide(currentLine, pick.pick_side, market), signLine)
              : formatHistoryAmerican(currentPrice),
            atClose,
          )}
        </Text>
        <Text style={[styles.verdict, { color: verdict.color }]}>{verdict.label}</Text>
      </View>

      <View style={styles.tableHead}>
        <Text style={[styles.cell, styles.cellTime, styles.headText]}>Changed at (ET)</Text>
        {showLineCol ? <Text style={[styles.cell, styles.headText]}>Line</Text> : null}
        <Text style={[styles.cell, styles.headText]}>Price</Text>
      </View>
      {recent.map((r, i) => {
        const timeLabel = historyTimeLabel(r.label, {
          atCloseLast: atClose && i === recent.length - 1,
          atFinalLast: inPlay && i === recent.length - 1,
          bounded: moveByAt.has(r.at),
        });
        return (
          <View
            key={r.key}
            style={styles.row}
            accessible
            accessibilityLabel={historyRowAccessibilityLabel({
              marker: timeLabel,
              at: r.at,
              line: showLineCol ? r.line : null,
              price: r.price,
              showLine: showLineCol,
              signedLine: signLine,
            })}
          >
            <Text style={[styles.cell, styles.cellTime]}>{timeLabel}</Text>
            {showLineCol ? <Text style={styles.cell}>{formatHistoryLine(r.line, signLine)}</Text> : null}
            <Text style={styles.cell}>{formatHistoryAmerican(r.price)}</Text>
          </View>
        );
      })}
      {hidden > 0 || snaps.length > recent.length ? (
        <Text style={styles.more}>
          {changesFooter({ changes, shownChanges, hidden }, snaps.length, partial)}
        </Text>
      ) : null}
      <Text style={styles.note}>
        {lineOnly
          ? `Your pick is locked at the number the card took — ` +
            `${formatHistoryLine(lineForSide(pick.scored_line, pick.pick_side, market), signLine)} at ` +
            `${formatHistoryAmerican(lockedPrice)} (the book is named in the pick). ` +
            (partial
              ? `The table samples the line at ${book} ${inPlay ? 'since your pick' : atClose ? 'from the open through the close' : 'since the open'}, not every tick. `
              : `The table shows the line at ${book} ${atClose ? 'through the close' : inPlay ? 'since your pick' : 'since the open'}. `) +
            `It doesn't change the pick or how it settles.`
          : `Your pick was decided at ${book} ${formatHistoryAmerican(lockedPrice)}` +
            `${showLineCol && movement?.scoredLine != null ? ` (${formatHistoryLine(lineForSide(movement.scoredLine, pick.pick_side, market), signLine)})` : ''}. ` +
            (atClose
              ? `The second number is the closing line, the last price before the game started. `
              : '') +
            (partial
              ? `This samples the line at ${book} ${atClose ? 'up to the close' : inPlay ? 'since your pick' : 'since the open'}, not every tick. It doesn't `
              : `This just shows the line at ${book} ${atClose ? 'up to the close' : inPlay ? 'since your pick' : 'since the open'}${inPlay ? '' : ', for or against you'}. It doesn't `) +
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
    flex: 2.2,
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
