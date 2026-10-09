/**
 * What the pick screen's line-movement card prints, as plain data. The card
 * (components/LineMovementCard.tsx) only lays it out, so every word here runs
 * under Node in tests/test_mobile_line_movement.py.
 *
 * Review of the since-the-pick change (2026-10-09):
 * - Once the game has started, the verdict is not graded. "In your favor" or
 *   "against you" after kickoff graded the move the opposite way to the
 *   Closing Line Value card on the same screen (pick 3133024, Under 49 at
 *   Fanatics, 49 to 49.5: "in your favor" here, a worse number than the close
 *   there). After the start it says where the line went, in grey, and points
 *   to the Closing Line Value card.
 * - A pick the book has not re-priced since reads "No new price from <book>",
 *   not "Line steady": the only row is the snapshot the pick was scored from.
 * - Every state says how old the newest price is ("As of …").
 * - The first row reads "At pick" only when it is the number the pick locked
 *   (markets.snapshotMatchesLock).
 * - The note says "from your pick" only when the table really runs from it.
 * - Spread rows carry their sign, like the header.
 */

import { decisionOdds } from './decisionPrice';
import { formatAmerican, formatDayTimeET } from './format';
import { changesFooter, recentChanges, type HistoryRow, type PickWindow } from './lineHistory';
import {
  bookName,
  formatLineValue,
  formatSideLine,
  historyBookForPick,
  isNflLineOnly,
  lineForSide,
  lineFromSnapshot,
  movementFromSameBookHistory,
  priceForSide,
  snapshotMatchesLock,
  storedQuoteBook,
  type PricedSnapshot,
} from './markets';
import type { Pick } from '@/types';

export interface Snap extends PricedSnapshot {
  snapshot_at: string;
}

/** How the verdict is coloured: graded for or against the pick, or neither. */
export type Tone = 'neutral' | 'for' | 'against';

export interface CardRow extends HistoryRow {
  /** The line as the pick's side reads it; spreads signed. */
  lineText: string;
  priceText: string;
}

export interface LineMovementView {
  /** "42.5 → 43", "-134 → -135", or the locked number alone when nothing came after it. */
  header: string;
  verdict: { label: string; tone: Tone };
  /** "As of Sun, 10/4, 12:24 PM ET": the newest snapshot the card holds. */
  asOf: string;
  showLineCol: boolean;
  rows: CardRow[];
  footer: string | null;
  note: string;
}

/** Rows the table shows. */
export const TABLE_ROWS = 8;

const CLV_POINTER = 'See Closing Line Value for how your number compared to the close.';

/**
 * The card's text for one pick and its window (lib/lineHistory sincePick).
 * Null when there is nothing to show.
 */
export function lineMovementView(
  pick: Pick,
  hist: PickWindow<Snap>,
  market: string,
  isProp: boolean,
): LineMovementView | null {
  const snaps = hist.rows;
  if (snaps.length === 0) return null;
  const side = pick.pick_side;
  const closed = hist.closed;
  // NFL game lines compare LINE only (soft-book price is not the snapshot
  // book). Props are not lineOnly — they steam at the deciding book.
  const lineOnly = isNflLineOnly(pick.model_id);
  const latest = snaps[snaps.length - 1];
  const movement = movementFromSameBookHistory(pick, latest, market);
  const lockedPrice = decisionOdds(pick);
  const book = bookName(historyBookForPick(pick) ?? storedQuoteBook(pick));
  const line = (v: number | null) => formatSideLine(v, side, market);
  // The only row is the snapshot the pick was scored from: there is nothing
  // to call steady or moved.
  const nothingSince = hist.fromPick && hist.since === 0;

  const locked = lineOnly ? line(pick.scored_line) : formatAmerican(lockedPrice);
  const header = nothingSince
    ? locked
    : `${locked} → ${lineOnly ? line(lineFromSnapshot(latest, market)) : formatAmerican(priceForSide(latest, side))}`;

  const verdict = ((): { label: string; tone: Tone } => {
    if (nothingSince) {
      return {
        label: closed
          ? `No new price from ${book} between your pick and game time`
          : `No new price from ${book} since your pick`,
        tone: 'neutral',
      };
    }
    // After the start: say where the line went, not whether it helped. The
    // Closing Line Value card grades the number against the close.
    if (closed) {
      if (!movement) return { label: 'Line steady from pick to game time', tone: 'neutral' };
      if (movement.lineOnly || movement.severity === 'skip') {
        return { label: `Line moved to ${line(movement.currentLine)} by game time`, tone: 'neutral' };
      }
      return { label: `Price moved to ${formatAmerican(movement.currentPrice)} by game time`, tone: 'neutral' };
    }
    if (!movement) return { label: 'Line steady since pick', tone: 'neutral' };
    if (movement.severity === 'skip') {
      return {
        label: `Line moved ${line(movement.scoredLine)} → ${line(movement.currentLine)} against your ${side}`,
        tone: 'against',
      };
    }
    if (movement.lineOnly) {
      return {
        label: `Line moved ${line(movement.scoredLine)} → ${line(movement.currentLine)} in your favor`,
        tone: 'for',
      };
    }
    const pp = movement.priceShiftPp ?? 0;
    if (movement.severity === 'caution') {
      return { label: `Steamed ${pp.toFixed(1)}pp against you since scoring`, tone: 'against' };
    }
    return { label: `Moved ${Math.abs(pp).toFixed(1)}pp in your favor since scoring`, tone: 'for' };
  })();

  const showLineCol = market.startsWith('totals') || market.startsWith('spreads') || isProp;
  // M13: a row is a CHANGE, not a raw snapshot — runs at the same line and
  // price collapse, and rows sharing a minute get seconds (lib/lineHistory).
  const recent = recentChanges(
    snaps.map((s) => ({
      at: s.snapshot_at,
      line: showLineCol ? lineForSide(lineFromSnapshot(s, market), side, market) : null,
      price: priceForSide(s, side),
    })),
    TABLE_ROWS,
    {
      atPick: hist.fromPick && snapshotMatchesLock(pick, snaps[0], market),
      gap: hist.fromPick && hist.gap,
    },
  );
  const rows: CardRow[] = recent.rows.map((r) => ({
    ...r,
    lineText: formatLineValue(r.line, market),
    priceText: formatAmerican(r.price),
  }));
  const snapshotRows = rows.filter((r) => !r.divider).length;
  const footer =
    hist.gap || !hist.fromPick || recent.hidden > 0 || snaps.length > snapshotRows
      ? changesFooter(recent, { fromPick: hist.fromPick, gap: hist.gap })
      : null;

  // What the table covers. "From your pick" only when it really runs from it.
  const spansPick = hist.fromPick && !hist.gap;
  const covers = spansPick
    ? closed
      ? `how the line at ${book} moved from your pick to game time`
      : `how the line at ${book} has moved since your pick${lineOnly ? '' : ', for or against you'}`
    : hist.fromPick
      ? `the line at ${book} when you picked, then its ${closed ? 'last prices before game time' : 'latest prices'}`
      : `the ${closed ? 'last prices before game time' : 'latest prices'} at ${book}`;
  const lead = lineOnly
    ? `Your pick is locked at the number the card took — ${line(pick.scored_line)} at ` +
      `${formatAmerican(lockedPrice)} (the book is named in the pick).`
    : `Your pick was decided at ${book} ${formatAmerican(lockedPrice)}` +
      `${showLineCol && movement?.scoredLine != null ? ` (${line(movement.scoredLine)})` : ''}.`;
  const note =
    `${lead} The table shows ${covers}.` +
    `${closed ? ` ${CLV_POINTER}` : ''} It doesn't change the pick or how it settles.`;

  return {
    header,
    verdict,
    asOf: `As of ${formatDayTimeET(latest.snapshot_at)}`,
    showLineCol,
    rows,
    footer,
    note,
  };
}
