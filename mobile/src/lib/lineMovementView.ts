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
 *
 * Second review (2026-10-09):
 * - "Steady" is decided from the numbers on the card, not from whether the
 *   betting rule (markets.computeMovement) fired. That rule ignores a move in
 *   the bettor's favour under one point of implied chance, one against under
 *   three, and any line move in the bettor's favour outside the NFL, so it
 *   called a 44.5 → 43.5 Over "steady" (pick 3352861) and a -134 → -135 prop
 *   "steady" after the start (3359501). A price that wandered and came back
 *   reads "Back to …" (3352648). Before the start the rule still grades the
 *   moves it covers.
 * - "At pick" also needs the row to be recent: a five-week-old snapshot is the
 *   book's last stored price, not its price at the pick (AT_PICK_MAX_MS).
 *   With nothing after it, the verdict describes what we hold ("Our newest
 *   DraftKings price is from Sat, 9/5, before your pick").
 * - A first row that is not the locked number is named in the note, never
 *   called the price at the pick (3386046).
 * - A pre-game pick made after the start the card uses (an NHL start moved
 *   earlier at settlement) reads the last price before the start. It never
 *   says "No new price … since your pick" or "from your pick to game time":
 *   by the card's own clock there is no such stretch (3414594, 3328652).
 * - The footer shows only when part of the window is not on screen and the
 *   divider row does not already say so (3423329).
 */

import { decisionOdds } from './decisionPrice';
import { formatAmerican, formatDayTimeET, parseStamp } from './format';
import { changesFooter, recentChanges, type HistoryRow, type PickWindow } from './lineHistory';
import {
  bookName,
  formatLineValue,
  formatSideLine,
  historyBookForPick,
  isNflLineOnly,
  lineForSide,
  lineFromSnapshot,
  lockedLineAtHistoryBook,
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

/**
 * How long before the pick the book's last price can be and still read "At
 * pick". Measured 2026-10-09 with read-only SQL, picks made since 10-06: of
 * 978 non-NFL game-line picks with a deciding book, 778 sit within an hour of
 * that book's last snapshot before them (median 6.5 minutes) and the other 200
 * more than seven days (NCAAF games whose feed stopped on 09-06); nothing sits
 * in between. 400 of 400 prop picks sit within 31 minutes. The NFL cards read
 * hourly series (43 and 52 minutes on picks 3133024 and 3386046). Six hours
 * clears the hourly writers with room and is far short of the stale ones.
 */
export const AT_PICK_MAX_MS = 6 * 60 * 60 * 1000;

const CLV_POINTER = 'See Closing Line Value for how your number compared to the close.';

const dayFmt = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York',
  weekday: 'short',
  month: 'numeric',
  day: 'numeric',
});

/** A stamp's instant in ms, or NaN (parseStamp: Hermes rejects the space form). */
function instant(at: string | null | undefined): number {
  return at ? parseStamp(at).getTime() : NaN;
}

/** "Sat, 9/5" in Eastern time. */
function dayET(at: string): string {
  const t = instant(at);
  return Number.isNaN(t) ? '—' : dayFmt.format(new Date(t));
}

/** "BetRivers'", "FanDuel's". */
function possessive(name: string): string {
  return name.endsWith('s') ? `${name}'` : `${name}'s`;
}

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
  const first = snaps[0];
  const latest = snaps[snaps.length - 1];
  const movement = movementFromSameBookHistory(pick, latest, market);
  const lockedPrice = decisionOdds(pick);
  const book = bookName(historyBookForPick(pick) ?? storedQuoteBook(pick));
  const line = (v: number | null) => formatSideLine(v, side, market);
  const showLineCol = market.startsWith('totals') || market.startsWith('spreads') || isProp;
  /** Home-relative on spreads, like scored_line. */
  const lineOf = (s: Snap) => lineFromSnapshot(s, market);
  const priceOf = (s: Snap) => priceForSide(s, side);
  /** "+7.5 at -117", or the price alone where the table has no line column. */
  const numbers = (s: Snap) =>
    showLineCol ? `${line(lineOf(s))} at ${formatAmerican(priceOf(s))}` : formatAmerican(priceOf(s));

  // What the first row is. With `afterStart` it is the last price before the
  // start, which is before the pick time; otherwise, with `fromPick`, the
  // book's last price at or before the pick. It reads "At pick" only when it
  // is the locked number and recent.
  const pickPrice = hist.fromPick && !hist.afterStart;
  const stale = pickPrice && instant(pick.created_at) - instant(first.snapshot_at) > AT_PICK_MAX_MS;
  const pickRowIsLock = pickPrice && !stale && snapshotMatchesLock(pick, first, market);
  // The only row is the book's price before the pick: nothing to call steady or moved.
  const nothingSince = pickPrice && hist.since === 0;

  // What "moved" is measured from: the locked number where a same-book
  // snapshot can be compared with it (NFL: the line; others: the price, and
  // the line when it is the deciding book's own), else the price at the pick
  // when the first row is it. Never a first row that is not the lock.
  const lockLine = lockedLineAtHistoryBook(pick, market);
  const lockPrice = lineOnly ? null : lockedPrice;
  let refLine = lockLine ?? (pickRowIsLock ? lineOf(first) : null);
  let refPrice = lockPrice ?? (pickRowIsLock ? priceOf(first) : null);
  if (refLine == null && refPrice == null && hist.fromPick) {
    // Nothing locked to compare with: the book's own last price before the pick.
    refLine = lineOf(first);
    refPrice = priceOf(first);
  }
  const latestLine = lineOf(latest);
  const latestPrice = priceOf(latest);
  const lineMoved = refLine != null && latestLine != null && latestLine !== refLine;
  const priceMoved = refPrice != null && latestPrice != null && latestPrice !== refPrice;
  const differs = (s: Snap) => {
    const l = lineOf(s);
    const p = priceOf(s);
    return (refLine != null && l != null && l !== refLine) || (refPrice != null && p != null && p !== refPrice);
  };
  // A row after the pick at another number: it moved and came back.
  const wandered = snaps.slice(hist.fromPick ? 1 : 0).some(differs);

  const locked = lineOnly ? line(pick.scored_line) : formatAmerican(lockedPrice);
  const nowText = lineOnly ? line(latestLine) : formatAmerican(latestPrice);
  // After the start the only row can be another price than the lock (pick
  // 3328652: -113 locked, -115 the last price before the start).
  const header = nothingSince || (hist.afterStart && nowText === locked) ? locked : `${locked} → ${nowText}`;

  const verdict = ((): { label: string; tone: Tone } => {
    const neutral = (label: string): { label: string; tone: Tone } => ({ label, tone: 'neutral' });
    if (hist.afterStart) {
      return neutral(`${possessive(book)} last price before the start was ${numbers(latest)}`);
    }
    if (nothingSince) {
      // Describe the data we hold, not the book: the feed, not the book, can
      // be what stopped (every book's rows for some NCAAF games end 09-06).
      if (stale) return neutral(`Our newest ${book} price is from ${dayET(first.snapshot_at)}, before your pick`);
      return neutral(
        closed ? `No new price from ${book} between your pick and game time` : `No new price from ${book} since your pick`,
      );
    }
    // Before the start the betting rule grades the moves it covers.
    if (!closed && movement) {
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
    }
    // Everything else, and everything after the start (the Closing Line Value
    // card grades the number against the close): where the numbers went.
    if (lineMoved) {
      return neutral(
        closed ? `Line moved to ${line(latestLine)} by game time` : `Line moved ${line(refLine)} → ${line(latestLine)}`,
      );
    }
    if (priceMoved) {
      return neutral(
        closed
          ? `Price moved to ${formatAmerican(latestPrice)} by game time`
          : `Price moved ${formatAmerican(refPrice)} → ${formatAmerican(latestPrice)}`,
      );
    }
    if (wandered) {
      return neutral(closed ? `Back to ${numbers(latest)} by game time` : `Back to ${numbers(latest)} since your pick`);
    }
    // Snapshots after the pick were dropped: what they held is unknown, so
    // not "steady".
    if (hist.gap) {
      return neutral(
        closed ? `Same at game time as at your pick: ${numbers(latest)}` : `Same as at your pick: ${numbers(latest)}`,
      );
    }
    return neutral(closed ? 'Line steady from pick to game time' : 'Line steady since pick');
  })();

  // M13: a row is a CHANGE, not a raw snapshot — runs at the same line and
  // price collapse, and rows sharing a minute get seconds (lib/lineHistory).
  const recent = recentChanges(
    snaps.map((s) => ({
      at: s.snapshot_at,
      line: showLineCol ? lineForSide(lineOf(s), side, market) : null,
      price: priceOf(s),
    })),
    TABLE_ROWS,
    {
      atPick: pickRowIsLock,
      gap: hist.fromPick && hist.gap,
      anchorAt: pick.created_at,
    },
  );
  const rows: CardRow[] = recent.rows.map((r) => ({
    ...r,
    lineText: formatLineValue(r.line, market),
    priceText: formatAmerican(r.price),
  }));
  // Only when part of the window is not on screen: snapshots after the pick
  // were dropped, there is no price at the pick, or rows sit above the table.
  // A divider on screen already says what is missing.
  const dividerShown = rows.some((r) => r.divider);
  const footer =
    !dividerShown && (hist.gap || !hist.fromPick || recent.hidden > 0)
      ? changesFooter(recent, { fromPick: hist.fromPick, gap: hist.gap })
      : null;

  // What the table covers. "When you picked" and "since your pick" only about
  // a row that is on screen and is the price at the pick.
  const pickRowShown = pickPrice && rows.length > 0 && !rows[0].divider && rows[0].at === first.snapshot_at;
  const differsFromLock =
    (lockLine != null && lineOf(first) !== lockLine) || (lockPrice != null && priceOf(first) !== lockPrice);
  const firstRow =
    `${possessive(book)} last stored price before your pick (${numbers(first)}` +
    `${stale ? `, from ${dayET(first.snapshot_at)}` : ''})` +
    `${differsFromLock ? ', not the number your pick locked' : ''}`;
  const tail = closed ? 'nothing newer was stored before game time' : 'nothing newer is stored';
  let body: string;
  if (hist.afterStart) {
    body = `The game's recorded start is before your pick, so the table shows the last price at ${book} before the start.`;
  } else if (nothingSince) {
    body = pickRowIsLock
      ? `The table shows the price at ${book} when you picked; ${tail}.`
      : `The table shows ${firstRow}; ${tail}.`;
  } else if (pickRowShown && pickRowIsLock) {
    const covers = hist.gap
      ? `the line at ${book} when you picked, then its ${closed ? 'last prices before game time' : 'latest prices'}`
      : closed
        ? `how the line at ${book} moved from your pick to game time`
        : `how the line at ${book} has moved since your pick${lineOnly ? '' : ', for or against you'}`;
    body = `The table shows ${covers}.`;
  } else if (pickRowShown) {
    body =
      `The table shows ${closed ? `the last prices at ${book} before game time` : `the latest prices at ${book} since your pick`}.` +
      ` The first row is ${firstRow}.`;
  } else if (hist.fromPick && !hist.gap) {
    // The price at the pick is above the table; the footer counts the changes.
    body = `The table shows ${closed ? `the last changes at ${book} before game time` : `the latest changes at ${book} since your pick`}.`;
  } else {
    body = `The table shows the ${closed ? 'last prices before game time' : 'latest prices'} at ${book}.`;
  }
  const lead = lineOnly
    ? `Your pick is locked at the number the card took — ${line(pick.scored_line)} at ` +
      `${formatAmerican(lockedPrice)} (the book is named in the pick).`
    : `Your pick was decided at ${book} ${formatAmerican(lockedPrice)}` +
      `${showLineCol && movement?.scoredLine != null ? ` (${line(movement.scoredLine)})` : ''}.`;
  const note = `${lead} ${body}${closed ? ` ${CLV_POINTER}` : ''} It doesn't change the pick or how it settles.`;

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
