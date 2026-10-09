import React, { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { gameStartAt, historyFrom, sincePick, type PickWindow } from '@/lib/lineHistory';
import { lineMovementView, type Snap } from '@/lib/lineMovementView';
import { canShowLineMovementHistory, gameMarketForModel, historyBookForPick, propMarketForModel } from '@/lib/markets';
import { fetchOddsHistory, fetchPropOddsHistory } from '@/lib/queries';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { Pick } from '@/types';

interface Props {
  pick: Pick;
  /** Player name parsed from pick_label (prop picks only). */
  playerName: string | null;
  /** games.commence_time. The window ends at the earlier of it and pick.game_time. */
  commenceTime?: string | null;
}

const NO_HISTORY: PickWindow<Snap> = { rows: [], fromPick: false, gap: false, since: 0, closed: false };

/**
 * Same-book price/line history since the pick was scored. Steam against
 * the lock is the "don't bet this anymore" signal. Fetch is the deciding
 * book (`historyBookForPick`), never a hard-coded DraftKings series.
 *
 * The rows run from the book's price when the pick was made to the game's
 * start (lib/lineHistory `sincePick`), so the last row is the latest pre-game
 * price. Every word on the card comes from lib/lineMovementView, which runs
 * under Node in the tests: after the start the verdict is not graded (the
 * Closing Line Value card grades the number), and a pick the book has not
 * re-priced reads "No new price". A live pick has no card (`historyFrom`).
 */
export function LineMovementCard({ pick, playerName, commenceTime }: Props) {
  const [hist, setHist] = useState<PickWindow<Snap> | null>(null);

  const isProp = pick.model_id.includes('prop');
  const market = isProp ? propMarketForModel(pick.model_id) : gameMarketForModel(pick.model_id);
  const historyBook = historyBookForPick(pick);
  const startAt = gameStartAt(commenceTime, pick.game_time);
  // The pick, or the start when a pre-game pick sits after it; null for a live pick.
  const from = historyFrom(pick, startAt);

  useEffect(() => {
    let mounted = true;
    if (
      !canShowLineMovementHistory(pick) ||
      historyBook == null ||
      market == null ||
      (isProp && !playerName) ||
      from == null
    ) {
      setHist(NO_HISTORY);
      return undefined;
    }
    const load = isProp
      ? fetchPropOddsHistory(pick.game_id, market, playerName!, historyBook)
      : fetchOddsHistory(pick.game_id, market, historyBook, from, startAt);
    load
      .then((rows) => {
        if (mounted) setHist(sincePick(rows as Snap[], from, startAt));
      })
      .catch(() => {
        if (mounted) setHist(NO_HISTORY);
      });
    return () => {
      mounted = false;
    };
  }, [pick.pick_id, pick.game_id, from, historyBook, market, isProp, playerName, startAt]);

  const view = hist && market != null ? lineMovementView(pick, hist, market, isProp) : null;
  if (!view) return null;
  const verdictColor =
    view.verdict.tone === 'for'
      ? colors.betInk
      : view.verdict.tone === 'against'
        ? colors.avoidInk
        : colors.textSecondary;

  return (
    <View style={styles.card}>
      <Text style={styles.heading}>Line Movement</Text>
      <View style={styles.headRow}>
        <Text style={styles.prices}>{view.header}</Text>
        <Text style={[styles.verdict, { color: verdictColor }]}>{view.verdict.label}</Text>
        <Text style={styles.asOf}>{view.asOf}</Text>
      </View>

      <View style={styles.tableHead}>
        <Text style={[styles.cell, styles.cellTime, styles.headText]}>Time (ET)</Text>
        {view.showLineCol ? <Text style={[styles.cell, styles.headText]}>Line</Text> : null}
        <Text style={[styles.cell, styles.headText]}>Price</Text>
      </View>
      {view.rows.map((r) =>
        r.divider ? (
          <View key={r.key} style={styles.row}>
            <Text style={styles.divider}>{r.label}</Text>
          </View>
        ) : (
          <View key={r.key} style={styles.row}>
            <Text style={[styles.cell, styles.cellTime]}>{r.label}</Text>
            {view.showLineCol ? <Text style={styles.cell}>{r.lineText}</Text> : null}
            <Text style={styles.cell}>{r.priceText}</Text>
          </View>
        ),
      )}
      {view.footer ? <Text style={styles.more}>{view.footer}</Text> : null}
      <Text style={styles.note}>{view.note}</Text>
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
  asOf: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
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
  divider: {
    flex: 1,
    fontSize: font.size.caption,
    color: colors.textTertiary,
    textAlign: 'center',
    fontStyle: 'italic',
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
