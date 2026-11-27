/**
 * The Stats tab's Games board (Matt, 2026-11-27): "a separate view that just
 * shows games for the day on the stats page and you can see ML, spread or
 * over under. Something like the scoreboard view … like CBS sports. Past
 * games current and future but only current has bet lines."
 *
 * So: a day strip (three days back to three ahead), one card per game, the
 * score once a game has started, and — on TODAY's games that have not
 * started, and nowhere else — six buttons: each team's spread and moneyline,
 * and the Over and the Under. Each button is the best price among the
 * member's own books (statsOdds.buildTeamLineIndex, the Teams board's rule)
 * and opens the same "Add to betslip?" sheet the Teams pill opens, with the
 * team's ML / spread / Over / Under as its tabs (lineLegs.teamLineSheetChoices).
 *
 * Nothing here is a model pick: a button is the user's own research bet, a
 * Stats line leg (lib/lineLegs.ts), never a signal.
 */

import { addDays, dayLabelET } from '@/lib/format';
import {
  lineLegKey,
  teamLineSheetChoices,
  teamLineSheetInput,
  type LineSheetChoice,
  type LineSheetInput,
} from '@/lib/lineLegs';
import { teamLineCaption, type TeamLineQuote } from '@/lib/statsOdds';
import type { OddsByBookRow } from '@/types';

/** Days either side of today on the strip. */
export const GAMES_DAYS_BACK = 3;
export const GAMES_DAYS_AHEAD = 3;

export interface GamesDay {
  date: string;
  /** "Today", "Yesterday", "Tomorrow", else the short weekday + date. */
  label: string;
}

/** The day strip, oldest first, today in the middle. */
export function gamesDayStrip(today: string): GamesDay[] {
  const out: GamesDay[] = [];
  for (let step = -GAMES_DAYS_BACK; step <= GAMES_DAYS_AHEAD; step++) {
    const date = addDays(today, step);
    out.push({ date, label: dayLabelET(date, today) });
  }
  return out;
}

/** Lines are only offered on today's board — past games are settled and
 *  future days are not priced to a standard we show (Matt: "only current has
 *  bet lines"). */
export function gamesDayHasLines(date: string, today: string): boolean {
  return date === today;
}

/** One tappable price on a game card. */
export interface GameBetCell {
  /** The leg's key — what the betslip stores, and the React key. */
  key: string;
  /** Top line of the button: "−3", "o47.5", "u47.5". Null on a moneyline. */
  line: string | null;
  /** The best price among the member's books. */
  price: number;
  /** The book that price is at. */
  book: string;
  /** What the add-to-betslip sheet opens on. */
  input: LineSheetInput;
  /** The team's other bets, as the sheet's tabs. */
  choices: LineSheetChoice[];
}

export interface GameBetRow {
  spread: GameBetCell | null;
  total: GameBetCell | null;
  ml: GameBetCell | null;
}

export interface GameBetCells {
  away: GameBetRow;
  home: GameBetRow;
}

export interface TeamLineIndexes {
  h2h: ReadonlyMap<string, TeamLineQuote>;
  spreads: ReadonlyMap<string, TeamLineQuote>;
  totals: ReadonlyMap<string, TeamLineQuote>;
}

function num(v: number | string | null | undefined): number | null {
  if (v == null || v === '') return null;
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

/**
 * The Under's best price among the member's books, at the quote's number.
 * `buildTeamLineIndex` prices a total from the Over side; its `bookRows` are
 * every book on the anchored number, so the Under shops the same set.
 * Ties go to the earlier book in the member's list, like `bestOf`.
 */
function bestUnder(q: TeamLineQuote, books: readonly string[]): { price: number; book: string } | null {
  const rank = new Map(books.map((b, i) => [b, i] as const));
  let best: { price: number; book: string; rank: number } | null = null;
  for (const r of q.bookRows as readonly OddsByBookRow[]) {
    const rk = rank.get(r.bookmaker);
    if (rk == null) continue;
    const p = num(r.under_price);
    if (p == null) continue;
    if (best == null || p > best.price || (p === best.price && rk < best.rank)) {
      best = { price: p, book: r.bookmaker, rank: rk };
    }
  }
  return best ? { price: best.price, book: best.book } : null;
}

/**
 * The six buttons for one game, from the three market indexes the board
 * builds over the day's lines. A button is null when none of the member's
 * books prices it, and the card prints a dash there rather than a number
 * the user cannot get.
 *
 * The total is the GAME's: the away row carries the Over and the home row
 * the Under, the way every sportsbook card stacks them.
 */
export function gameBetCells(
  game: { home_team: string | null; away_team: string | null },
  idx: TeamLineIndexes,
  books: readonly string[],
  sport: string,
): GameBetCells | null {
  const { home_team: home, away_team: away } = game;
  if (!home || !away) return null;
  const choicesFor = (team: string) =>
    teamLineSheetChoices(
      { h2h: idx.h2h.get(team), spreads: idx.spreads.get(team), totals: idx.totals.get(team) },
      sport,
    );
  const row = (team: string, totalSide: 'over' | 'under'): GameBetRow => {
    const choices = choicesFor(team);
    // The key is the leg's own (lineLegKey), which is also how the sheet's
    // tabs are keyed, so the tapped button opens on its own tab.
    const cell = (input: LineSheetInput, line: string | null, price: number, book: string): GameBetCell => ({
      key: lineLegKey(input.spec),
      line,
      price,
      book,
      input,
      choices,
    });
    const s = idx.spreads.get(team) ?? null;
    const m = idx.h2h.get(team) ?? null;
    const t = idx.totals.get(team) ?? null;
    let total: GameBetCell | null = null;
    if (t && t.line != null) {
      if (totalSide === 'over') {
        total = cell(teamLineSheetInput(t, sport, 'over'), `o${t.line}`, t.price, t.book);
      } else {
        const u = bestUnder(t, books);
        if (u) total = cell(teamLineSheetInput(t, sport, 'under'), `u${t.line}`, u.price, u.book);
      }
    }
    return {
      spread: s && s.line != null ? cell(teamLineSheetInput(s, sport), teamLineCaption(s), s.price, s.book) : null,
      total,
      ml: m ? cell(teamLineSheetInput(m, sport), null, m.price, m.book) : null,
    };
  };
  return { away: row(away, 'over'), home: row(home, 'under') };
}

/**
 * What VoiceOver hears for a card's header: the matchup, its state, and the
 * score or start time — and no prices. The Scoreboard's own label speaks
 * DraftKings' lines, which on this board would disagree with the buttons
 * (each the best of the member's books) and would name lines on days that
 * show none (UX review, 2026-11-27). The buttons speak their own prices.
 */
export function gamesCardLabel(card: {
  phase: 'upcoming' | 'live' | 'final';
  away: { name: string; score: string };
  home: { name: string; score: string };
  footerText: string;
}): string {
  const scores = `${card.away.name} ${card.away.score}, ${card.home.name} ${card.home.score}`;
  if (card.phase === 'live') return `${scores}. Live${card.footerText ? `, ${card.footerText}` : ''}.`;
  if (card.phase === 'final') return `${scores}. ${card.footerText || 'Final'}.`;
  return `${card.away.name} at ${card.home.name}${card.footerText ? `, ${card.footerText}` : ''}.`;
}

/** The newest snapshot among the lines the board read: "Prices as of …". */
export function newestSnapshot(rows: readonly { snapshot_at?: string | null }[]): string | null {
  let best: string | null = null;
  let bestMs = -Infinity;
  for (const r of rows) {
    if (!r.snapshot_at) continue;
    const ms = Date.parse(r.snapshot_at);
    if (Number.isFinite(ms) && ms > bestMs) {
      bestMs = ms;
      best = r.snapshot_at;
    }
  }
  return best;
}
