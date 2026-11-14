/**
 * Bet all (Matt, 2026-11-14). Every pre-game signal on the board, sent to the
 * member's sportsbooks as SINGLE bets: "They are all singles and should not be
 * considered for a parlay." Two ways to send them:
 *
 *   best  (the default) each pick at its best line among the member's books,
 *         so the picks split across books and the member opens one book at a
 *         time.
 *   book  every pick at one book. A pick that book does not have is named,
 *         never dropped without a word.
 *
 * Live bets are not part of it, and the sheet says so (Matt, same day).
 *
 * No book takes a bet from an app: a link only fills the slip, and the member
 * places each bet in the book. A link carries no stake, so every leg here
 * carries the stake to type in, sized at THAT book's price the same way the
 * Signals card sizes it (stakeFor at the member's price).
 *
 * Pure: no React, so scripts/verify_bet_all.ts runs it.
 */
import type { EnrichedPick, LiveGameStateRow, Pick } from '@/types';
import { pickPriceView } from './pickPriceView';
import { bookLabel, bookName, handoffQuotesForPick, LINE_SHOP_BOOKS } from './markets';
import { pickSportsbookRows } from './pickBooks';
import { pickCtaFor } from './pickCta';
import { openForAction } from './discordPublish';
import {
  isPausedForDisplay,
  isUnlockedPreview,
  passesActionFilter,
  stakeFor,
  type UnitStake,
} from './thresholds';
import { americanToDecimal, labelWithoutStake } from './format';
import { combineSinglesLinks } from './betslipLinks';

export type BetAllMode = 'best' | 'book';

/** Why a signal on the board is not in Bet all. Each is said to the member. */
export type BetAllSkipReason = 'started' | 'priceCheck' | 'oldPrice' | 'notAtMyBooks' | 'noPrice';

export const BET_ALL_SKIP_TEXT: Record<BetAllSkipReason, string> = {
  started: 'Game started',
  priceCheck: 'Price check',
  oldPrice: 'Old price',
  notAtMyBooks: 'Not at your books',
  noPrice: 'No price at your books',
};

/** Said wherever Bet all is offered (Matt, 2026-11-14). */
export const BET_ALL_LIVE_NOTE = 'Pre-game signals only. Live bets aren’t included.';

/** Said on every step: a link fills the slip, it cannot choose the bet type. */
export const BET_ALL_SINGLES_NOTE =
  'Each pick is a single bet. In the slip, choose Straight (or Singles), not Parlay, and enter each stake.';

export interface BetAllQuote {
  bookmaker: string;
  price: number;
  link: string | null;
}

export interface BetAllPick {
  key: string;
  pick: Pick;
  /** The pick's label word for word, without the stake suffix (CLAUDE.md §00). */
  label: string;
  /** Same bet at the member's books, best payout first. Never empty. */
  quotes: BetAllQuote[];
}

export interface BetAllSkipped {
  key: string;
  pick: Pick;
  label: string;
  reason: BetAllSkipReason;
}

export interface BetAllCandidates {
  picks: BetAllPick[];
  skipped: BetAllSkipped[];
}

export function betAllKey(pick: Pick): string {
  return String(pick.pick_id);
}

/**
 * The signals Bet all can send. A pick is in only when its Signals card would
 * offer the bet: a BET past its model's cut, open, not paused or a preview,
 * pre-game, not price-checked, not at an old price, and priced at one of the
 * member's books at the pick's own line. Live picks are left out altogether.
 * Anything else that is a signal on the board is listed in `skipped` with
 * the reason, so the count on the button never hides a pick.
 */
export function betAllCandidates(
  items: readonly EnrichedPick[],
  liveStateFor: (gameId: string) => LiveGameStateRow | null | undefined,
  myBooks: readonly string[],
): BetAllCandidates {
  const picks: BetAllPick[] = [];
  const skipped: BetAllSkipped[] = [];
  const seen = new Set<string>();
  for (const item of items) {
    const { pick, game } = item;
    const key = betAllKey(pick);
    if (seen.has(key)) continue;
    seen.add(key);
    if (pick.is_live === true) continue;
    if (pick.signal_type !== 'BET' || !passesActionFilter(pick)) continue;
    if (isUnlockedPreview(pick) || isPausedForDisplay(pick) || !openForAction(pick)) continue;
    const label = labelWithoutStake(pick.pick_label).trim();
    const liveState = liveStateFor(pick.game_id) ?? null;
    const skip = (reason: BetAllSkipReason) => skipped.push({ key, pick, label, reason });
    if (!pickCtaFor(pick, game, liveState).handoff) {
      skip('started');
      continue;
    }
    const view = pickPriceView(item, liveState, myBooks, true);
    if (view.flagged) {
      skip('priceCheck');
      continue;
    }
    if (view.heroPrice?.stale) {
      skip('oldPrice');
      continue;
    }
    if (view.notAtMyBooks) {
      skip('notAtMyBooks');
      continue;
    }
    const rows = pickSportsbookRows(
      handoffQuotesForPick(pick, item.bookRows, view.heroPrice, view.priceAge, myBooks),
      null,
    ).filter((r) => r.price != null && !r.otherLine && myBooks.includes(r.bookmaker));
    if (rows.length === 0) {
      skip('noPrice');
      continue;
    }
    picks.push({
      key,
      pick,
      label,
      quotes: rows.map((r) => ({ bookmaker: r.bookmaker, price: r.price as number, link: r.link })),
    });
  }
  return { picks, skipped };
}

export interface BetAllLeg {
  key: string;
  pick: Pick;
  label: string;
  bookmaker: string;
  price: number;
  link: string | null;
  stake: UnitStake;
  /** This book's price is the best among the member's books for this pick. */
  atBest: boolean;
}

export interface BetAllStep {
  bookmaker: string;
  name: string;
  short: string;
  legs: BetAllLeg[];
  /**
   * What the step opens, in order. One URL when the book has a singles form
   * that carries every linked leg, else one per linked leg. Legs with no link
   * are not in it: the member adds those in the book.
   */
  links: string[];
  /** Legs no link can put on the slip. */
  unlinked: BetAllLeg[];
}

function shopOrder(book: string): number {
  const i = (LINE_SHOP_BOOKS as readonly string[]).indexOf(book);
  return i < 0 ? LINE_SHOP_BOOKS.length : i;
}

function legAt(p: BetAllPick, q: BetAllQuote): BetAllLeg {
  const best = p.quotes[0]!;
  return {
    key: p.key,
    pick: p.pick,
    label: p.label,
    bookmaker: q.bookmaker,
    price: q.price,
    link: q.link,
    // Sized at THIS book's price, as the card sizes it at the member's price.
    stake: stakeFor(p.pick.kelly_fraction, q.price, p.pick.stake_units),
    atBest: americanToDecimal(q.price) >= americanToDecimal(best.price),
  };
}

function stepFor(bookmaker: string, legs: BetAllLeg[]): BetAllStep {
  const linked = legs.filter((l) => l.link != null && l.link.trim() !== '');
  const unlinked = legs.filter((l) => !linked.includes(l));
  const one = linked.length > 1 ? combineSinglesLinks(linked.map((l) => l.link)) : null;
  return {
    bookmaker,
    name: bookName(bookmaker),
    short: bookLabel(bookmaker),
    legs,
    links: one ? [one] : linked.map((l) => l.link as string),
    unlinked,
  };
}

/** Best line: each selected pick at its best book. Biggest book first. */
export function bestLinePlan(picks: readonly BetAllPick[], selected: ReadonlySet<string>): BetAllStep[] {
  const byBook = new Map<string, BetAllLeg[]>();
  for (const p of picks) {
    if (!selected.has(p.key)) continue;
    const q = p.quotes[0]!;
    const legs = byBook.get(q.bookmaker) ?? [];
    legs.push(legAt(p, q));
    byBook.set(q.bookmaker, legs);
  }
  return [...byBook.entries()]
    .sort((a, b) => b[1].length - a[1].length || shopOrder(a[0]) - shopOrder(b[0]))
    .map(([book, legs]) => stepFor(book, legs));
}

export interface BookCoverage {
  bookmaker: string;
  name: string;
  short: string;
  /** Selected picks this book has, at the pick's own line. */
  covered: number;
  /** Of those, how many it has at the best price among the member's books. */
  atBest: number;
}

/**
 * Every member book that has at least one selected pick, most picks first,
 * then most at the best price, then sportsbook order.
 */
export function bookCoverage(
  picks: readonly BetAllPick[],
  selected: ReadonlySet<string>,
  myBooks: readonly string[],
): BookCoverage[] {
  const out: BookCoverage[] = [];
  for (const book of myBooks) {
    let covered = 0;
    let atBest = 0;
    for (const p of picks) {
      if (!selected.has(p.key)) continue;
      const q = p.quotes.find((x) => x.bookmaker === book);
      if (!q) continue;
      covered += 1;
      if (americanToDecimal(q.price) >= americanToDecimal(p.quotes[0]!.price)) atBest += 1;
    }
    if (covered > 0) {
      out.push({ bookmaker: book, name: bookName(book), short: bookLabel(book), covered, atBest });
    }
  }
  return out.sort(
    (a, b) => b.covered - a.covered || b.atBest - a.atBest || shopOrder(a.bookmaker) - shopOrder(b.bookmaker),
  );
}

/** One book: every selected pick it has. `missing` are the ones it does not. */
export function oneBookPlan(
  picks: readonly BetAllPick[],
  selected: ReadonlySet<string>,
  book: string,
): { step: BetAllStep | null; missing: BetAllPick[] } {
  const legs: BetAllLeg[] = [];
  const missing: BetAllPick[] = [];
  for (const p of picks) {
    if (!selected.has(p.key)) continue;
    const q = p.quotes.find((x) => x.bookmaker === book);
    if (q) legs.push(legAt(p, q));
    else missing.push(p);
  }
  return { step: legs.length > 0 ? stepFor(book, legs) : null, missing };
}

/** Units risked and to win across the plan's legs. */
export function planTotals(steps: readonly BetAllStep[]): { legs: number; risk: number; win: number } {
  let legs = 0;
  let risk = 0;
  let win = 0;
  for (const s of steps) {
    for (const l of s.legs) {
      legs += 1;
      risk += l.stake.risk;
      win += l.stake.win;
    }
  }
  return { legs, risk, win };
}
