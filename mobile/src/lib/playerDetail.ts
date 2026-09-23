/**
 * Pure helpers for the player page's added sections (screens/PlayerStatsScreen).
 *
 * The page already charts a stat against a line the reader can step. What it
 * lacked (Matt, 2026-09-20: "do the same for player props, there should be
 * more helpful information there") is everything a bettor checks around that
 * chart:
 *
 *  - TONIGHT'S LINE for the selected stat — the number the books actually
 *    posted, the member's own price on it, the sharp book's no-vig read, and
 *    how DraftKings' line has moved since it opened;
 *  - SPLITS of the same stat at the same line — home / away, against tonight's
 *    opponent, and (basketball) starting vs off the bench;
 *  - OUR RECORD on this player's props, per market, in units.
 *
 * Every function is a reduction over rows the app already fetches; the page
 * decides what to show, this file decides what the numbers are.
 *
 * The page's "line" is an AT-LEAST threshold (5.5 Ks → "6+"), and the book's
 * line is the half-point below it. `thresholdFromBookLine` / `bookLineFromThreshold`
 * are the only two places that conversion lives here.
 */
import { americanImplied, formatSignedUnits } from '@/lib/format';
import { hasPricedLine } from '@/lib/decisionPrice';
import { logStatValue, type PlayerLogEntry } from '@/lib/playerLog';
import { statForPropModel, type StatDef } from '@/lib/statCatalog';
import { modelShort } from '@/lib/modelMeta';
import type { GameRow, PropOddsByBookRow, PropOddsSnapshotRow, SettledPick } from '@/types';

// ── Line conversions ─────────────────────────────────────────────────────────

/** A book's 5.5 is the page's "6+"; a whole-number book line (7) is "7+" for
 *  a hit and a push at exactly 7 — the page treats it as 7+ like the board does. */
export function thresholdFromBookLine(line: number): number {
  return Number.isInteger(line) ? line : Math.ceil(line);
}

/** The page's "6+" is the book's 5.5. */
export function bookLineFromThreshold(threshold: number): number {
  return threshold - 0.5;
}

// ── Tonight's line ───────────────────────────────────────────────────────────

export const SHARP_BOOK = 'pinnacle';

export interface BookQuote {
  book: string;
  line: number;
  over: number | null;
  under: number | null;
  overLink: string | null;
  underLink: string | null;
}

export interface TonightLine {
  market: string;
  /** The line the market is priced at: DraftKings' when it posts one, else
   *  the most common line across books. */
  line: number;
  /** The member's books at that line, in the member's own order. */
  mine: BookQuote[];
  /** Best over / under price among the member's books at that line. */
  bestOver: BookQuote | null;
  bestUnder: BookQuote | null;
  /** Pinnacle's no-vig over probability at that line, and its own line. */
  sharpOverProb: number | null;
  sharpLine: number | null;
  /** The member's first book's no-vig over probability at that line. */
  bookOverProb: number | null;
  /** bookOverProb − sharpOverProb in points; positive = book richer than Pinnacle. */
  gapPp: number | null;
  /** How many books post the market at all. */
  books: number;
}

function num(v: number | string | null | undefined): number | null {
  if (v == null) return null;
  const n = typeof v === 'string' ? Number(v) : v;
  return Number.isFinite(n) ? n : null;
}

/** Multiplicative de-vig (docs/clv.md) — the over's share of the pair. */
export function noVigOver(over: number | null, under: number | null): number | null {
  if (over == null || under == null) return null;
  const a = americanImplied(over);
  const b = americanImplied(under);
  if (!(a > 0) || !(b > 0)) return null;
  return a / (a + b);
}

function quote(r: PropOddsByBookRow): BookQuote | null {
  const line = num(r.line);
  if (line == null) return null;
  return {
    book: r.bookmaker,
    line,
    over: num(r.over_price),
    under: num(r.under_price),
    overLink: r.over_link ?? null,
    underLink: r.under_link ?? null,
  };
}

function better(a: number | null, b: number | null): boolean {
  // Higher American price is better for the bettor: +120 > +105 > −105 > −120.
  if (a == null) return false;
  if (b == null) return true;
  return a > b;
}

/**
 * Tonight's number for one market from every book's latest row for the
 * player. `rows` is what fetchPropLineRows returns (one game, one market,
 * alternates folded). Null when no book posts the market.
 */
export function tonightLine(
  rows: PropOddsByBookRow[],
  market: string,
  books: readonly string[],
  modelBook: string,
): TonightLine | null {
  const quotes = rows.map(quote).filter((q): q is BookQuote => q != null);
  if (quotes.length === 0) return null;
  // The line: DraftKings' main line when posted, else the modal line.
  const dk = quotes.find((q) => q.book === modelBook);
  let line: number;
  if (dk) {
    line = dk.line;
  } else {
    const counts = new Map<number, number>();
    for (const q of quotes) counts.set(q.line, (counts.get(q.line) ?? 0) + 1);
    line = [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0] - b[0])[0]![0];
  }
  const rank = new Map(books.map((b, i) => [b, i] as const));
  const mine = quotes
    .filter((q) => q.line === line && rank.has(q.book))
    .sort((a, b) => (rank.get(a.book) ?? 99) - (rank.get(b.book) ?? 99));
  let bestOver: BookQuote | null = null;
  let bestUnder: BookQuote | null = null;
  for (const q of mine) {
    if (better(q.over, bestOver?.over ?? null)) bestOver = q;
    if (better(q.under, bestUnder?.under ?? null)) bestUnder = q;
  }
  const sharp = quotes.find((q) => q.book === SHARP_BOOK && q.line === line)
    ?? quotes.find((q) => q.book === SHARP_BOOK)
    ?? null;
  const sharpOverProb = sharp && sharp.line === line ? noVigOver(sharp.over, sharp.under) : null;
  const first = mine.find((q) => q.over != null) ?? null;
  const bookOverProb = first ? noVigOver(first.over, first.under) : null;
  return {
    market,
    line,
    mine,
    bestOver,
    bestUnder,
    sharpOverProb,
    sharpLine: sharp?.line ?? null,
    bookOverProb,
    gapPp: sharpOverProb != null && bookOverProb != null ? (bookOverProb - sharpOverProb) * 100 : null,
    books: new Set(quotes.map((q) => q.book)).size,
  };
}

export interface PropLineMove {
  openLine: number | null;
  nowLine: number | null;
  openOverProb: number | null;
  nowOverProb: number | null;
  /** 'up' = the line rose or the over got dearer; 'down' the reverse. */
  direction: 'up' | 'down' | 'flat';
}

/**
 * DraftKings' opening snapshot against its latest, for one player market.
 * `history` is oldest-first (fetchPropOddsHistory); `now` is the same book's
 * latest row from the all-books view, which may be newer than the history's
 * last element because that read is capped.
 */
export function propLineMove(
  history: PropOddsSnapshotRow[],
  now: PropOddsByBookRow | null,
): PropLineMove | null {
  const open = history[0] ?? null;
  if (!open) return null;
  const latest: { line: number | null; over: number | null; under: number | null } = now
    ? { line: num(now.line), over: num(now.over_price), under: num(now.under_price) }
    : (() => {
        const l = history[history.length - 1]!;
        return { line: num(l.line), over: num(l.over_price), under: num(l.under_price) };
      })();
  const openLine = num(open.line);
  const openOverProb = noVigOver(num(open.over_price), num(open.under_price));
  const nowOverProb = noVigOver(latest.over, latest.under);
  let direction: PropLineMove['direction'] = 'flat';
  if (openLine != null && latest.line != null && openLine !== latest.line) {
    direction = latest.line > openLine ? 'up' : 'down';
  } else if (openOverProb != null && nowOverProb != null && Math.abs(nowOverProb - openOverProb) >= 0.005) {
    direction = nowOverProb > openOverProb ? 'up' : 'down';
  }
  return { openLine, nowLine: latest.line, openOverProb, nowOverProb, direction };
}

// ── Splits ───────────────────────────────────────────────────────────────────

/**
 * One pair of hit-rate cut-offs for every traffic light on the player page —
 * the badge above the chart and the split tiles below it. Two lights with two
 * cut-offs made a 42% split read neutral while the 42% badge read red (UX
 * review, 2026-09-20). Display bands, not model thresholds.
 */
export const HIT_RATE_GOOD = 0.6;
export const HIT_RATE_WEAK = 0.45;

export interface SplitBucket {
  label: string;
  games: number;
  avg: number | null;
  /** Share of games at or above the page's threshold; null with no games. */
  hitRate: number | null;
  hits: number;
}

export interface StatSplits {
  home: SplitBucket;
  away: SplitBucket;
  /** Basketball only — the log carries is_starter. */
  starting: SplitBucket | null;
  bench: SplitBucket | null;
}

// ── Head-to-head with the next opponent ─────────────────────────────

/** One previous meeting: when it was, and what the player did in it. */
export interface H2HMeeting {
  date: string;
  value: number;
}

export interface PlayerHeadToHead {
  opponent: string;
  /** Newest first. */
  meetings: H2HMeeting[];
  /** The same numbers as a split, so it reads beside Home / Away unchanged. */
  bucket: SplitBucket;
}

/**
 * The H2H card's numbers, off one player_h2h_stat_values_* row.
 *
 * THIS REPLACED A `vsOpponent` SPLIT COMPUTED OVER THE LOADED LOG, and the
 * reason is span, not shape. That log is 25 rows in football and 50 elsewhere
 * (playerLog.logFetchLimit) — about a third of an MLB season — so "vs BAL"
 * silently meant "vs BAL inside the last fifty games", which in September is a
 * different question from the one the label asked. Two seasons is the span
 * Matt asked for (2026-09-20), and the RPC is bounded to it server-side.
 *
 * `values` and `dates` arrive index-aligned from the RPC (it filters both on
 * the same non-null condition); a length mismatch would pair a number with
 * another game's date, so the pairing stops at the shorter of the two rather
 * than trusting either length.
 */
export function playerHeadToHead(
  opponent: string,
  values: readonly number[],
  dates: readonly string[],
  threshold: number,
): PlayerHeadToHead {
  const n = Math.min(values.length, dates.length);
  const meetings: H2HMeeting[] = [];
  for (let i = 0; i < n; i++) {
    const v = Number(values[i]);
    if (!Number.isFinite(v)) continue;
    meetings.push({ date: dates[i]!, value: v });
  }
  const nums = meetings.map((m) => m.value);
  const hits = nums.filter((v) => v >= threshold).length;
  return {
    opponent,
    meetings,
    bucket: {
      label: `vs ${opponent}`,
      games: nums.length,
      avg: nums.length ? nums.reduce((a, b) => a + b, 0) / nums.length : null,
      hitRate: nums.length ? hits / nums.length : null,
      hits,
    },
  };
}

function bucket(label: string, entries: PlayerLogEntry[], stat: StatDef | null, threshold: number): SplitBucket {
  const values = entries.map((e) => logStatValue(e, stat)).filter((v): v is number => v != null);
  const hits = values.filter((v) => v >= threshold).length;
  return {
    label,
    games: values.length,
    avg: values.length ? values.reduce((a, b) => a + b, 0) / values.length : null,
    hitRate: values.length ? hits / values.length : null,
    hits,
  };
}

/** Which side the player's team was on in each logged game, from the games table. */
export function sideOf(entry: PlayerLogEntry, game: GameRow | undefined): { isHome: boolean | null; opponent: string | null } {
  if (!game) {
    // Football logs name the opponent themselves; home/away is still unknown.
    return { isHome: null, opponent: entry.opponent ?? null };
  }
  const team = entry.team;
  if (team && game.home_team === team) return { isHome: true, opponent: game.away_team };
  if (team && game.away_team === team) return { isHome: false, opponent: game.home_team };
  return { isHome: null, opponent: entry.opponent ?? null };
}

export function statSplits(
  entries: PlayerLogEntry[],
  gamesById: ReadonlyMap<string, GameRow>,
  stat: StatDef | null,
  threshold: number,
  hasStarterFlag: boolean,
): StatSplits {
  const home: PlayerLogEntry[] = [];
  const away: PlayerLogEntry[] = [];
  const starting: PlayerLogEntry[] = [];
  const bench: PlayerLogEntry[] = [];
  for (const e of entries) {
    const { isHome } = sideOf(e, gamesById.get(e.game_id));
    if (isHome === true) home.push(e);
    else if (isHome === false) away.push(e);
    if (hasStarterFlag) {
      // Stored as an integer column (measured: nba/wnba_player_game_log.is_starter
      // is `integer`); a NUMERIC-as-string arrives as '1' / '0'.
      const s = e.is_starter;
      if (s === 1 || s === '1') starting.push(e);
      else if (s === 0 || s === '0') bench.push(e);
    }
  }
  return {
    home: bucket('Home', home, stat, threshold),
    away: bucket('Away', away, stat, threshold),
    starting: hasStarterFlag ? bucket('Starting', starting, stat, threshold) : null,
    bench: hasStarterFlag ? bucket('Off bench', bench, stat, threshold) : null,
  };
}

// ── Our record on this player ────────────────────────────────────────────────

export interface PlayerPickLine {
  modelId: string;
  /** The stat the model prices ("Hits", "Points"), or the model's short label. */
  label: string;
  wins: number;
  losses: number;
  pushes: number;
  units: number | null;
  unpriced: number;
  /** Over / under split of the settled picks, for the "we've been on the under" read. */
  overs: number;
  unders: number;
}

export interface PlayerPickRecord {
  lines: PlayerPickLine[];
  settled: number;
  wins: number;
  losses: number;
  pushes: number;
  units: number | null;
  unpriced: number;
}

/**
 * Settled BETs on this player, grouped by model. Input is already the record
 * filter (BET, a real result); this only sorts and sums. A pick with no price
 * counts in the record and not in the units (CLAUDE.md §6).
 */
export function playerPickRecord(picks: SettledPick[]): PlayerPickRecord {
  const by = new Map<string, PlayerPickLine>();
  const total: PlayerPickRecord = { lines: [], settled: 0, wins: 0, losses: 0, pushes: 0, units: null, unpriced: 0 };
  for (const p of picks) {
    if (p.signal_type !== 'BET') continue;
    if (p.result !== 'WIN' && p.result !== 'LOSS' && p.result !== 'PUSH') continue;
    let line = by.get(p.model_id);
    if (!line) {
      const stat = statForPropModel(p.model_id);
      line = {
        modelId: p.model_id,
        label: stat?.label ?? modelShort(p.model_id),
        wins: 0, losses: 0, pushes: 0, units: null, unpriced: 0, overs: 0, unders: 0,
      };
      by.set(p.model_id, line);
    }
    if (p.result === 'WIN') { line.wins += 1; total.wins += 1; }
    else if (p.result === 'LOSS') { line.losses += 1; total.losses += 1; }
    else { line.pushes += 1; total.pushes += 1; }
    const side = String(p.pick_side ?? '').toLowerCase();
    if (side === 'over') line.overs += 1;
    else if (side === 'under') line.unders += 1;
    // Through decisionPrice, never the columns (UX_REVIEW §0).
    const priced = hasPricedLine(p);
    const pf = num(p.profit_flat);
    if (priced && pf != null) {
      line.units = (line.units ?? 0) + pf / 100;
      total.units = (total.units ?? 0) + pf / 100;
    } else {
      line.unpriced += 1;
      total.unpriced += 1;
    }
    total.settled += 1;
  }
  total.lines = [...by.values()].sort((a, b) => (b.wins + b.losses + b.pushes) - (a.wins + a.losses + a.pushes));
  return total;
}

export function formatRecordLine(r: { wins: number; losses: number; pushes: number; units: number | null }): string {
  const rec = r.pushes > 0 ? `${r.wins}-${r.losses}-${r.pushes}` : `${r.wins}-${r.losses}`;
  if (r.units == null) return rec;
  return `${rec} · ${formatSignedUnits(r.units)}`;
}
