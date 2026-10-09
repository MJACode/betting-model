import React, { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { formatAmerican } from '@/lib/format';
import { changesFooter, gameStartAt, pickedBeforeStart, recentChanges, sincePick, type PickWindow } from '@/lib/lineHistory';
import { canShowLineMovementHistory, formatSideLine, gameMarketForModel, historyBookForPick, isNflLineOnly, lineForSide, lineFromSnapshot, movementFromSameBookHistory, priceForSide, propMarketForModel, type PricedSnapshot, bookName, storedQuoteBook } from '@/lib/markets';
import { fetchOddsHistory, fetchPropOddsHistory } from '@/lib/queries';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { Pick } from '@/types';
import { decisionOdds } from '@/lib/decisionPrice';

interface Props {
  pick: Pick;
  /** Player name parsed from pick_label (prop picks only). */
  playerName: string | null;
  /** games.commence_time. The window ends at the earlier of it and pick.game_time. */
  commenceTime?: string | null;
}

interface Snap extends PricedSnapshot {
  snapshot_at: string;
}

const NO_HISTORY: PickWindow<Snap> = { rows: [], fromPick: false, closed: false };

/**
 * Same-book price/line history since the pick was scored. Steam against
 * the lock is the "don't bet this anymore" signal. Fetch is the deciding
 * book (`historyBookForPick`), never a hard-coded DraftKings series.
 *
 * The rows run from the book's price when the pick was made to the game's
 * start (lib/lineHistory `sincePick`), so the last row is the latest pre-game
 * price, and after the start the card says "by game time", not "now". A pick
 * made after the start (a live pick) has no pre-game line since it: no card.
 */
export function LineMovementCard({ pick, playerName, commenceTime }: Props) {
  const [hist, setHist] = useState<PickWindow<Snap> | null>(null);

  const isProp = pick.model_id.includes('prop');
  const market = isProp ? propMarketForModel(pick.model_id) : gameMarketForModel(pick.model_id);
  const historyBook = historyBookForPick(pick);
  const startAt = gameStartAt(commenceTime, pick.game_time);

  useEffect(() => {
    let mounted = true;
    if (
      !canShowLineMovementHistory(pick) ||
      historyBook == null ||
      market == null ||
      (isProp && !playerName) ||
      !pickedBeforeStart(pick.created_at, startAt)
    ) {
      setHist(NO_HISTORY);
      return undefined;
    }
    const load = isProp
      ? fetchPropOddsHistory(pick.game_id, market, playerName!, historyBook)
      : fetchOddsHistory(pick.game_id, market, historyBook, pick.created_at, startAt);
    load
      .then((rows) => {
        if (mounted) setHist(sincePick(rows as Snap[], pick.created_at, startAt));
      })
      .catch(() => {
        if (mounted) setHist(NO_HISTORY);
      });
    return () => {
      mounted = false;
    };
  }, [pick.pick_id, pick.game_id, pick.created_at, historyBook, market, isProp, playerName, startAt]);

  if (!hist || hist.rows.length === 0 || market == null) return null;
  const snaps = hist.rows;
  // After the start the last row is the last price before it, not "now".
  const byGameTime = hist.closed;

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
      return {
        label: byGameTime ? 'Line steady from pick to game time' : 'Line steady since pick',
        color: colors.textSecondary,
      };
    }
    const when = byGameTime ? ' by game time' : '';
    if (movement.severity === 'skip') {
      return {
        label:
          `Line moved ${formatSideLine(movement.scoredLine, pick.pick_side, market)} → ` +
          `${formatSideLine(movement.currentLine, pick.pick_side, market)} against your ${pick.pick_side}${when}`,
        color: colors.avoidInk,
      };
    }
    if (movement.lineOnly) {
      return {
        label:
          `Line moved ${formatSideLine(movement.scoredLine, pick.pick_side, market)} → ` +
          `${formatSideLine(movement.currentLine, pick.pick_side, market)} in your favor${when}`,
        color: colors.betInk,
      };
    }
    const pp = movement.priceShiftPp ?? 0;
    const since = byGameTime ? 'by game time' : 'since scoring';
    if (movement.severity === 'caution') {
      return {
        label: `Steamed ${pp.toFixed(1)}pp against you ${since}`,
        color: colors.avoidInk,
      };
    }
    return {
      label: `Moved ${Math.abs(pp).toFixed(1)}pp in your favor ${since}`,
      color: colors.betInk,
    };
  })();

  const showLineCol = market.startsWith('totals') || market.startsWith('spreads') || isProp;
  // M13: a row is a CHANGE, not a raw snapshot — runs at the same line and
  // price collapse, and rows sharing a minute get seconds (lib/lineHistory).
  // The first row is the price at the pick ("At pick"), not the opener.
  const { fromPick } = hist;
  const { rows: recent, changes, shownChanges, hidden } = recentChanges(
    snaps.map((s) => ({
      at: s.snapshot_at,
      line: showLineCol ? lineForSide(lineFromSnapshot(s, market), pick.pick_side, market) : null,
      price: priceForSide(s, pick.pick_side),
    })),
    8,
    fromPick,
  );

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
        <Text style={[styles.cell, styles.cellTime, styles.headText]}>Changed at</Text>
        {showLineCol ? <Text style={[styles.cell, styles.headText]}>Line</Text> : null}
        <Text style={[styles.cell, styles.headText]}>Price</Text>
      </View>
      {recent.map((r) => (
        <View key={r.key} style={styles.row}>
          <Text style={[styles.cell, styles.cellTime]}>{r.label}</Text>
          {showLineCol ? <Text style={styles.cell}>{r.line ?? '—'}</Text> : null}
          <Text style={styles.cell}>{formatAmerican(r.price)}</Text>
        </View>
      ))}
      {hidden > 0 || snaps.length > recent.length ? (
        <Text style={styles.more}>
          {changesFooter({ changes, shownChanges, hidden }, snaps.length, fromPick)}
        </Text>
      ) : null}
      <Text style={styles.note}>
        {lineOnly
          ? `Your pick is locked at the number the card took — ` +
            `${formatSideLine(pick.scored_line, pick.pick_side, market)} at ` +
            `${formatAmerican(lockedPrice)} (the book is named in the pick). The table shows ` +
            `${bookName(historyBook ?? storedQuoteBook(pick))}'s line ${byGameTime ? 'from your pick to game time' : 'since'}. ` +
            `It doesn't change the pick or how it settles.`
          : `Your pick was decided at ${bookName(historyBook ?? storedQuoteBook(pick))} ${formatAmerican(lockedPrice)}` +
            `${showLineCol && movement?.scoredLine != null ? ` (${formatSideLine(movement.scoredLine, pick.pick_side, market)})` : ''}. ` +
            `This just shows how that book's line ${byGameTime ? 'moved from your pick to game time' : 'has moved since'}, ` +
            `for or against you. It doesn't change the pick or how it settles.`}
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
