/**
 * Pure helpers for the team detail screen (screens/TeamStatsScreen).
 *
 * The screen answers one question — "should I bet this team's next game?" —
 * from data the app already holds, and every reduction it needs is here, off
 * the render path, so each one can be verified with plain inputs:
 *
 *  - the MARKET READ for the next game: how the line has moved since it
 *    opened, where the sharp book (Pinnacle) prices the team against the
 *    member's own book, and where the public's tickets and money sit;
 *  - FORM: the last N results from the team's side, and for the NFL the
 *    cover / over marks per game from the stored closing number;
 *  - HEAD-TO-HEAD against the next opponent;
 *  - OUR RECORD betting on and against the team, from settled BET rows;
 *  - LEAGUE RANKS for the sport's efficiency metrics, from the board rows.
 *
 * Conventions that matter here, all inherited from CLAUDE.md §4 and the
 * team_stats_board SQL: `spread_home` is the HOME number in standard form
 * (negative = home laying points); nflverse's `spread_line` is the OPPOSITE
 * sign and is normalised in `nflCoverMarks` exactly as the board does it; a
 * pick's `pick_side` is 'home' / 'away' / 'over' / 'under', never a team name.
 */
import { americanImplied } from '@/lib/format';
import { hasPricedLine } from '@/lib/decisionPrice';
import {
  teamStatsForSport,
  teamStatValue,
  type TeamStatDef,
} from '@/lib/teamStatCatalog';
import { isThinSample, tertileCuts, tierFor, type Tier } from '@/lib/teamBoard';
import type { Sport } from '@/hooks/useSportFilter';
import type {
  GameRow,
  NflTeamGameStatRow,
  OddsByBookRow,
  OddsSnapshotRow,
  PublicBettingRow,
  SettledPick,
  TeamStatsRow,
} from '@/types';

// ── Prices ──────────────────────────────────────────────────────────────────

/**
 * No-vig probability of side A from a two-way price pair — the multiplicative
 * de-vig `docs/clv.md` grades CLV with. Null when either side is missing.
 */
export function noVigProb(priceA: number | null, priceB: number | null): number | null {
  if (priceA == null || priceB == null) return null;
  const a = americanImplied(priceA);
  const b = americanImplied(priceB);
  if (!(a > 0) || !(b > 0)) return null;
  return a / (a + b);
}

export type TeamMarket = 'h2h' | 'spreads' | 'totals';

/** The team's own price on a game-market row: its ML, its spread price, or the over. */
export function teamPrice(row: OddsByBookRow | OddsSnapshotRow, market: TeamMarket, isHome: boolean): number | null {
  if (market === 'totals') return numOrNull(row.over_price);
  return numOrNull(isHome ? row.home_price : row.away_price);
}

/** The other side's price, for the de-vig pair. */
export function oppPrice(row: OddsByBookRow | OddsSnapshotRow, market: TeamMarket, isHome: boolean): number | null {
  if (market === 'totals') return numOrNull(row.under_price);
  return numOrNull(isHome ? row.away_price : row.home_price);
}

/** The team's own line: its spread (−3.5 = laying) or the total; null on h2h. */
export function teamLine(row: OddsByBookRow | OddsSnapshotRow, market: TeamMarket, isHome: boolean): number | null {
  if (market === 'h2h') return null;
  if (market === 'totals') return numOrNull(row.total_line);
  const home = numOrNull(row.spread_home);
  if (home == null) return null;
  return isHome ? home : -home;
}

// ── Line movement since open ────────────────────────────────────────────────

export interface LineMove {
  market: TeamMarket;
  /** Team-side line at open and now (spread / total); null on h2h. */
  openLine: number | null;
  nowLine: number | null;
  /** Team-side no-vig probability at open and now, 0..1; null when a side is missing. */
  openProb: number | null;
  nowProb: number | null;
  /**
   * Which way the market moved FOR THIS TEAM: 'toward' means the team got
   * dearer (steam on it), 'away' means cheaper, 'flat' means no change.
   * For totals, 'toward' is the total rising (steam on the over).
   */
  direction: 'toward' | 'away' | 'flat';
  /** When the "now" row was captured. */
  asOf: string | null;
}

/**
 * Open → now from the same book. The line is compared first (a spread that
 * moved from +4 to +3.5 is a move even if the price is unchanged); on a
 * moneyline the no-vig probability is what moves.
 */
export function lineMove(
  open: OddsSnapshotRow | null,
  now: OddsByBookRow | null,
  market: TeamMarket,
  isHome: boolean,
): LineMove | null {
  if (!open || !now) return null;
  const openLine = teamLine(open, market, isHome);
  const nowLine = teamLine(now, market, isHome);
  const openProb = noVigProb(teamPrice(open, market, isHome), oppPrice(open, market, isHome));
  const nowProb = noVigProb(teamPrice(now, market, isHome), oppPrice(now, market, isHome));
  let direction: LineMove['direction'] = 'flat';
  if (market !== 'h2h' && openLine != null && nowLine != null && openLine !== nowLine) {
    // Spread: a smaller number for the team (−3 → −3.5, +4 → +3.5) means the
    // market moved toward it. Total: rising = toward the over.
    direction = market === 'totals'
      ? (nowLine > openLine ? 'toward' : 'away')
      : (nowLine < openLine ? 'toward' : 'away');
  } else if (openProb != null && nowProb != null && Math.abs(nowProb - openProb) >= 0.005) {
    direction = nowProb > openProb ? 'toward' : 'away';
  }
  return { market, openLine, nowLine, openProb, nowProb, direction, asOf: now.snapshot_at ?? null };
}

// ── Sharp book vs the member's book ────────────────────────────────────────

export const SHARP_BOOK = 'pinnacle';

export interface SharpRead {
  market: TeamMarket;
  /** Pinnacle's no-vig probability of the team's side (over, on totals). */
  sharpProb: number | null;
  sharpLine: number | null;
  /** The member's book's raw implied probability of the same side, vig included. */
  bookProb: number | null;
  /** The member's book's NO-VIG probability of the side — its own two-way pair
   *  de-vigged the same way, so the comparison below is fair-to-fair. */
  bookFairProb: number | null;
  bookLine: number | null;
  book: string | null;
  /**
   * Book implied (vig in) − sharp fair, in probability points. This is the
   * price the member actually pays against fair value; its NEUTRAL is the
   * book's hold (about +2.4pp at −110 both ways), not zero.
   */
  gapPp: number | null;
  /**
   * Book fair − sharp fair, in points. Zero when the two books agree on the
   * side and only the vig differs; this is the number a sentence about
   * "dearer" or "cheaper" has to be built on (UX review, 2026-09-20).
   */
  fairGapPp: number | null;
  /** When the rows were captured — the newest snapshot among the pair. */
  asOf: string | null;
}

/**
 * Where the sharp book has the team against the first of the member's books
 * that posts the market. A sharp book that is not in the rows returns null —
 * the screen says the read is unavailable rather than comparing soft books.
 */
export function sharpRead(
  rows: OddsByBookRow[],
  market: TeamMarket,
  isHome: boolean,
  books: readonly string[],
): SharpRead | null {
  const inMarket = rows.filter((r) => r.market === market);
  const sharp = inMarket.find((r) => r.bookmaker === SHARP_BOOK) ?? null;
  if (!sharp) return null;
  let mine: OddsByBookRow | null = null;
  for (const b of books) {
    const r = inMarket.find((x) => x.bookmaker === b && teamPrice(x, market, isHome) != null);
    if (r) {
      mine = r;
      break;
    }
  }
  const sharpProb = noVigProb(teamPrice(sharp, market, isHome), oppPrice(sharp, market, isHome));
  const bookPrice = mine ? teamPrice(mine, market, isHome) : null;
  const bookProb = bookPrice == null ? null : americanImplied(bookPrice);
  const bookFairProb = mine ? noVigProb(teamPrice(mine, market, isHome), oppPrice(mine, market, isHome)) : null;
  const stamps = [sharp.snapshot_at, mine?.snapshot_at].filter((s): s is string => !!s).sort();
  return {
    market,
    sharpProb,
    sharpLine: teamLine(sharp, market, isHome),
    bookProb,
    bookFairProb,
    bookLine: mine ? teamLine(mine, market, isHome) : null,
    book: mine?.bookmaker ?? null,
    gapPp: sharpProb != null && bookProb != null ? (bookProb - sharpProb) * 100 : null,
    fairGapPp: sharpProb != null && bookFairProb != null ? (bookFairProb - sharpProb) * 100 : null,
    asOf: stamps.length ? stamps[stamps.length - 1]! : null,
  };
}

// ── Public splits ───────────────────────────────────────────────────────────

/**
 * Sports the public-splits ingestor covers. MEASURED 2026-09-20: every row in
 * public_betting is MLB (8,448 rows, 1,408 games). Named here so the page's
 * "captured for MLB only" sentence has one source that a coverage change
 * updates, rather than a literal in a component that goes stale silently.
 */
export const PUBLIC_SPLITS_SPORTS: ReadonlySet<string> = new Set(['MLB']);

export interface PublicRead {
  market: TeamMarket;
  /** % of tickets / money on the TEAM's side (over, on totals). */
  betPct: number | null;
  moneyPct: number | null;
  /** money − tickets: a positive gap is bigger bets on this side. */
  gapPp: number | null;
  snapshotAt: string | null;
}

/** The consensus split on the team's side of a market, from the stored rows. */
export function publicRead(
  rows: PublicBettingRow[],
  market: TeamMarket,
  isHome: boolean,
): PublicRead | null {
  const side = market === 'totals' ? 'over' : isHome ? 'home' : 'away';
  const row = rows.find((r) => r.market === market && r.side === side) ?? null;
  if (!row) return null;
  const betPct = numOrNull(row.public_bet_pct);
  const moneyPct = numOrNull(row.public_money_pct);
  if (betPct == null && moneyPct == null) return null;
  return {
    market,
    betPct,
    moneyPct,
    gapPp: betPct != null && moneyPct != null ? moneyPct - betPct : null,
    snapshotAt: row.snapshot_at ?? null,
  };
}

// ── Form ────────────────────────────────────────────────────────────────────

export interface FormGame {
  gameId: string;
  date: string;
  opponent: string;
  isHome: boolean;
  scored: number;
  allowed: number;
  /** 'W' / 'L' / 'T' from the team's side. */
  result: 'W' | 'L' | 'T';
  margin: number;
  /** Against the closing number, when the sport stores one per game (NFL). */
  ats: 'cover' | 'loss' | 'push' | null;
  ou: 'over' | 'under' | 'push' | null;
  spread: number | null;
  total: number | null;
}

/** Finished games from the team's side, newest first. Games with no final are dropped. */
export function formFromGames(games: GameRow[], team: string): FormGame[] {
  const out: FormGame[] = [];
  for (const g of games) {
    if (g.home_score == null || g.away_score == null) continue;
    const isHome = g.home_team === team;
    if (!isHome && g.away_team !== team) continue;
    const scored = isHome ? g.home_score : g.away_score;
    const allowed = isHome ? g.away_score : g.home_score;
    const margin = scored - allowed;
    out.push({
      gameId: g.game_id,
      date: g.game_date,
      opponent: isHome ? g.away_team : g.home_team,
      isHome,
      scored,
      allowed,
      result: margin > 0 ? 'W' : margin < 0 ? 'L' : 'T',
      margin,
      ats: null,
      ou: null,
      spread: null,
      total: null,
    });
  }
  return out.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
}

/**
 * Cover and over/under marks from nfl_team_game_stats, which stores nflverse's
 * closing line per team-game. nflverse's `spread_line` is POSITIVE when the
 * HOME team is favoured — the opposite of `odds.spread_home` — so the team's
 * own number is `-spread_line` at home and `+spread_line` away, and it covers
 * iff margin + team_spread > 0. Same normalisation as the board SQL, which
 * verified the sign by checking that favourites win 78%, not 32%.
 */
export function nflCoverMarks(rows: NflTeamGameStatRow[]): Map<string, Pick<FormGame, 'ats' | 'ou' | 'spread' | 'total'>> {
  const out = new Map<string, Pick<FormGame, 'ats' | 'ou' | 'spread' | 'total'>>();
  for (const r of rows) {
    if (r.points_for == null || r.points_against == null) continue;
    const spreadLine = numOrNull(r.spread_line);
    const total = numOrNull(r.total_line);
    const teamSpread = spreadLine == null ? null : r.is_home ? -spreadLine : spreadLine;
    const margin = r.points_for - r.points_against;
    let ats: FormGame['ats'] = null;
    if (teamSpread != null) {
      const edge = margin + teamSpread;
      ats = edge > 0 ? 'cover' : edge < 0 ? 'loss' : 'push';
    }
    let ou: FormGame['ou'] = null;
    if (total != null) {
      const pts = r.points_for + r.points_against;
      ou = pts > total ? 'over' : pts < total ? 'under' : 'push';
    }
    out.set(r.game_id, { ats, ou, spread: teamSpread, total });
  }
  return out;
}

/** Form games with the NFL marks merged in by game id. */
export function withCoverMarks(
  form: FormGame[],
  marks: Map<string, Pick<FormGame, 'ats' | 'ou' | 'spread' | 'total'>>,
): FormGame[] {
  return form.map((g) => {
    const m = marks.get(g.gameId);
    return m ? { ...g, ...m } : g;
  });
}

export interface FormSummary {
  games: number;
  wins: number;
  losses: number;
  ties: number;
  avgMargin: number | null;
  avgScored: number | null;
  avgAllowed: number | null;
  /** Only counted where the mark exists. */
  atsW: number;
  atsL: number;
  atsP: number;
  overs: number;
  unders: number;
  ouP: number;
}

export function summarizeForm(games: FormGame[], n?: number): FormSummary {
  const slice = n == null ? games : games.slice(0, n);
  const s: FormSummary = {
    games: slice.length, wins: 0, losses: 0, ties: 0,
    avgMargin: null, avgScored: null, avgAllowed: null,
    atsW: 0, atsL: 0, atsP: 0, overs: 0, unders: 0, ouP: 0,
  };
  if (slice.length === 0) return s;
  let margin = 0;
  let scored = 0;
  let allowed = 0;
  for (const g of slice) {
    if (g.result === 'W') s.wins += 1;
    else if (g.result === 'L') s.losses += 1;
    else s.ties += 1;
    margin += g.margin;
    scored += g.scored;
    allowed += g.allowed;
    if (g.ats === 'cover') s.atsW += 1;
    else if (g.ats === 'loss') s.atsL += 1;
    else if (g.ats === 'push') s.atsP += 1;
    if (g.ou === 'over') s.overs += 1;
    else if (g.ou === 'under') s.unders += 1;
    else if (g.ou === 'push') s.ouP += 1;
  }
  s.avgMargin = margin / slice.length;
  s.avgScored = scored / slice.length;
  s.avgAllowed = allowed / slice.length;
  return s;
}

// ── Head-to-head ────────────────────────────────────────────────────────────

export interface HeadToHead {
  opponent: string;
  meetings: FormGame[];
  wins: number;
  losses: number;
  ties: number;
  avgMargin: number | null;
  avgTotal: number | null;
  /** Record in the meetings played at the team's home / away. */
  homeW: number;
  homeL: number;
  awayW: number;
  awayL: number;
}

export function headToHead(games: GameRow[], team: string, opponent: string): HeadToHead {
  const meetings = formFromGames(games, team).filter((g) => g.opponent === opponent);
  const h: HeadToHead = {
    opponent, meetings, wins: 0, losses: 0, ties: 0, avgMargin: null, avgTotal: null,
    homeW: 0, homeL: 0, awayW: 0, awayL: 0,
  };
  if (meetings.length === 0) return h;
  let margin = 0;
  let total = 0;
  for (const g of meetings) {
    if (g.result === 'W') {
      h.wins += 1;
      if (g.isHome) h.homeW += 1; else h.awayW += 1;
    } else if (g.result === 'L') {
      h.losses += 1;
      if (g.isHome) h.homeL += 1; else h.awayL += 1;
    } else {
      h.ties += 1;
    }
    margin += g.margin;
    total += g.scored + g.allowed;
  }
  h.avgMargin = margin / meetings.length;
  h.avgTotal = total / meetings.length;
  return h;
}

// ── Our record on this team ─────────────────────────────────────────────────

export interface PickRecord {
  wins: number;
  losses: number;
  pushes: number;
  /** Flat units over the priced picks; null when none carried a price. */
  units: number | null;
  /** How many of the settled picks had no price (their P&L is excluded, §6). */
  unpriced: number;
}

export interface TeamPickRecords {
  /** Picks ON the team: its moneyline, spread or runline side. */
  on: PickRecord;
  /** Picks AGAINST it: the opponent's side in its games. */
  against: PickRecord;
  /** Totals in its games. */
  over: PickRecord;
  under: PickRecord;
  settled: number;
}

function emptyRecord(): PickRecord {
  return { wins: 0, losses: 0, pushes: 0, units: null, unpriced: 0 };
}

function addPick(rec: PickRecord, p: SettledPick): void {
  if (p.result === 'WIN') rec.wins += 1;
  else if (p.result === 'LOSS') rec.losses += 1;
  else if (p.result === 'PUSH') rec.pushes += 1;
  // profit_flat fabricates −110 for a priceless pick (CLAUDE.md §6), so a
  // pick with no price counts in the record and stays out of the units. Read
  // through decisionPrice, never the columns (UX_REVIEW §0).
  const priced = hasPricedLine(p);
  const pf = numOrNull(p.profit_flat);
  if (priced && pf != null) rec.units = (rec.units ?? 0) + pf / 100;
  else rec.unpriced += 1;
}

/**
 * Settled BET rows in the team's games, split by which side they backed. The
 * input is already the record filter (`signal_type = 'BET'`, a real result,
 * game-level rows) — this only sorts each row into a bucket. Live picks count:
 * a bet on the team is a bet on the team whenever it was placed.
 */
export function teamPickRecords(picks: SettledPick[], games: GameRow[], team: string): TeamPickRecords {
  const byId = new Map(games.map((g) => [g.game_id, g] as const));
  const out: TeamPickRecords = {
    on: emptyRecord(), against: emptyRecord(), over: emptyRecord(), under: emptyRecord(), settled: 0,
  };
  for (const p of picks) {
    const g = byId.get(p.game_id);
    if (!g) continue;
    if (p.signal_type !== 'BET') continue;
    if (p.result !== 'WIN' && p.result !== 'LOSS' && p.result !== 'PUSH') continue;
    const side = String(p.pick_side ?? '').toLowerCase();
    const teamIsHome = g.home_team === team;
    if (side === 'over') addPick(out.over, p);
    else if (side === 'under') addPick(out.under, p);
    else if (side === 'home') addPick(teamIsHome ? out.on : out.against, p);
    else if (side === 'away') addPick(teamIsHome ? out.against : out.on, p);
    else continue;
    out.settled += 1;
  }
  return out;
}

export function formatPickRecord(r: PickRecord): string {
  const rec = r.pushes > 0 ? `${r.wins}-${r.losses}-${r.pushes}` : `${r.wins}-${r.losses}`;
  if (r.units == null) return rec;
  return `${rec} · ${formatSignedUnits(r.units)}`;
}

/** "3-1" or "3-1-1" — the record without the units. */
export function formatWinLoss(r: { wins: number; losses: number; pushes: number }): string {
  return r.pushes > 0 ? `${r.wins}-${r.losses}-${r.pushes}` : `${r.wins}-${r.losses}`;
}

/**
 * "+2.4u" / "−0.5u" — a SIGNED result in units (CLAUDE.md §4). Named apart
 * from thresholds.ts's `formatUnits`, which prints an unsigned stake ("2.4u"):
 * two exports with one name and two meanings is how the next screen imports
 * the wrong one (UX review, 2026-09-20).
 */
export function formatSignedUnits(u: number): string {
  const rounded = Math.round(u * 10) / 10;
  if (rounded === 0) return '0.0u';
  return `${rounded > 0 ? '+' : '−'}${Math.abs(rounded).toFixed(1)}u`;
}

// ── League ranks ────────────────────────────────────────────────────────────

export interface TeamStatRank {
  def: TeamStatDef;
  value: number | null;
  /** 1 = best in the league by the stat's own direction; null when unranked. */
  rank: number | null;
  of: number;
  tier: Tier;
}

/**
 * The team's league rank on every stat in a group, from the board's rows. A
 * stat with no direction (pace, over rate) is listed with its value and no
 * rank; a thin split is listed and left untinted, as on the board.
 */
export function teamRanks(rows: TeamStatsRow[], team: string, sport: Sport, group: TeamStatDef['group']): TeamStatRank[] {
  const mine = rows.find((r) => r.team === team) ?? null;
  const out: TeamStatRank[] = [];
  for (const def of teamStatsForSport(sport).filter((d) => d.group === group)) {
    const value = mine ? teamStatValue(mine, def) : null;
    const ranked = rows
      .filter((r) => !isThinSample(r, def))
      .map((r) => teamStatValue(r, def))
      .filter((v): v is number => v != null);
    const cuts = tertileCuts(ranked);
    const thin = mine ? isThinSample(mine, def) : true;
    let rank: number | null = null;
    if (value != null && def.better != null && !thin) {
      const better = ranked.filter((v) => (def.better === 'high' ? v > value : v < value)).length;
      rank = better + 1;
    }
    out.push({
      def,
      value,
      rank,
      of: ranked.length,
      tier: thin ? 'none' : tierFor(value, cuts, def.better),
    });
  }
  return out;
}

/** "3rd of 32" */
export function ordinal(n: number): string {
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${n}th`;
  switch (n % 10) {
    case 1: return `${n}st`;
    case 2: return `${n}nd`;
    case 3: return `${n}rd`;
    default: return `${n}th`;
  }
}

// ── Small shared bits ───────────────────────────────────────────────────────

export function numOrNull(v: number | string | null | undefined): number | null {
  if (v == null) return null;
  const n = typeof v === 'string' ? Number(v) : v;
  return Number.isFinite(n) ? n : null;
}

/** "+3.5" / "−3.5" / "PK" for a team-side spread; a plain number for a total. */
export function formatTeamLine(line: number | null, market: TeamMarket): string {
  if (line == null) return '—';
  if (market === 'totals') return `${line}`;
  if (line === 0) return 'PK';
  return `${line > 0 ? '+' : '−'}${Math.abs(line)}`;
}
