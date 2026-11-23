/**
 * The GAME matchup page (screens/ScoreboardGameScreen) — the pure half.
 * Not lib/matchup.ts, which grades a PLAYER against a defence.
 *
 * Matt, 2026-11-23: "we don't have a nice match up view with games to figure
 * out who to bet". NBA first. The page puts our picks on the game first (or a
 * plain "No pick"), then the two teams side by side: league ranks, recent
 * form against the spread and the total, rest, head-to-head and injuries.
 *
 * No `@/` imports on purpose: tests/test_mobile_game_matchup.py runs this file
 * under node's type stripping, which cannot resolve the app's path alias.
 */

/** Sports that get the matchup sections. Everything else keeps the lines-only page. */
export const MATCHUP_SPORTS: ReadonlySet<string> = new Set(['NBA']);

export function hasMatchupView(sport: string | null | undefined): boolean {
  return sport != null && MATCHUP_SPORTS.has(sport);
}

// ── Side-by-side ranks ──────────────────────────────────────────────────────

/** The fields of lib/teamDetail's TeamStatRank this file reads. */
export interface RankLike {
  def: { key: string; label: string; better?: 'high' | 'low' | null };
  value: number | null;
  rank: number | null;
}

export interface PairedRank<R extends RankLike> {
  key: string;
  label: string;
  away: R | null;
  home: R | null;
  /** Which side ranks better on this stat. Null for a tie, an unranked stat
   *  (pace, over rate: no "better" direction) or a side with no rank. */
  edge: 'away' | 'home' | null;
}

/**
 * Two teams' ranks on one stat group, row by row, in the away list's order.
 * The edge goes to the better RANK, not the bigger number: Def Rtg is better
 * low, and the rank already carries the stat's direction.
 */
export function pairRanks<R extends RankLike>(away: R[], home: R[]): PairedRank<R>[] {
  const homeByKey = new Map(home.map((r) => [r.def.key, r]));
  const keys = [...away.map((r) => r.def.key), ...home.map((r) => r.def.key).filter((k) => !away.some((a) => a.def.key === k))];
  const awayByKey = new Map(away.map((r) => [r.def.key, r]));
  return keys.map((key) => {
    const a = awayByKey.get(key) ?? null;
    const h = homeByKey.get(key) ?? null;
    let edge: PairedRank<R>['edge'] = null;
    if (a?.rank != null && h?.rank != null && a.rank !== h.rank) edge = a.rank < h.rank ? 'away' : 'home';
    return { key, label: (a ?? h)!.def.label, away: a, home: h, edge };
  });
}

// ── Recent results against the number ───────────────────────────────────────

/** One team-game from team_period_results (period 'FG'), the fields read here. */
export interface CoverRow {
  game_id: string;
  game_date: string;
  is_home: boolean;
  ats: 'W' | 'L' | 'P' | null;
  ou: 'O' | 'U' | 'P' | null;
}

export interface CoverSummary {
  /** Games in the window. */
  games: number;
  /** Games that carried a stored line; the W/L counts are out of these. */
  atsGames: number;
  atsW: number;
  atsL: number;
  atsP: number;
  ouGames: number;
  overs: number;
  unders: number;
  ouP: number;
}

/** ATS and over/under counts over the newest `n` rows (all when n is omitted). */
export function coverSummary(rows: CoverRow[], n?: number): CoverSummary {
  const sorted = rows.slice().sort((a, b) => (a.game_date < b.game_date ? 1 : a.game_date > b.game_date ? -1 : 0));
  const slice = n == null ? sorted : sorted.slice(0, n);
  const s: CoverSummary = { games: slice.length, atsGames: 0, atsW: 0, atsL: 0, atsP: 0, ouGames: 0, overs: 0, unders: 0, ouP: 0 };
  for (const r of slice) {
    if (r.ats != null) {
      s.atsGames += 1;
      if (r.ats === 'W') s.atsW += 1;
      else if (r.ats === 'L') s.atsL += 1;
      else s.atsP += 1;
    }
    if (r.ou != null) {
      s.ouGames += 1;
      if (r.ou === 'O') s.overs += 1;
      else if (r.ou === 'U') s.unders += 1;
      else s.ouP += 1;
    }
  }
  return s;
}

/** "7-3" / "7-2-1"; "—" when no game in the window carried a line. */
export function formatAts(s: CoverSummary): string {
  if (s.atsGames === 0) return '—';
  return s.atsP > 0 ? `${s.atsW}-${s.atsL}-${s.atsP}` : `${s.atsW}-${s.atsL}`;
}

/** "6o-4u" / "6o-3u-1p"; "—" when no game in the window carried a total. */
export function formatOu(s: CoverSummary): string {
  if (s.ouGames === 0) return '—';
  return `${s.overs}o-${s.unders}u${s.ouP > 0 ? `-${s.ouP}p` : ''}`;
}

// ── Rest ────────────────────────────────────────────────────────────────────

/**
 * Days off before this game: 0 is the second night of a back-to-back. Null
 * with no earlier game. Dates are ISO calendar days (games.game_date), so the
 * difference is whole days with no clock or zone in it.
 */
export function restDays(lastGameDate: string | null, gameDate: string): number | null {
  if (!lastGameDate) return null;
  const a = Date.parse(`${lastGameDate}T00:00:00Z`);
  const b = Date.parse(`${gameDate}T00:00:00Z`);
  if (!Number.isFinite(a) || !Number.isFinite(b) || b <= a) return null;
  return Math.round((b - a) / 86_400_000) - 1;
}

export function restText(days: number | null): string {
  if (days == null) return '—';
  if (days === 0) return 'Back-to-back';
  return `${days} day${days === 1 ? '' : 's'} rest`;
}

// ── Picks on this game ──────────────────────────────────────────────────────

/**
 * The picks the Signals board would show for this game, and no others: the
 * same `passesActionFilter` / `passesRecordFilter` tests, passed in so this
 * file stays free of the threshold store. Open picks come from the board's
 * `data`, today's finished ones from `finishedData`; a graded pick is history
 * and is cut by the record test, an ungraded one by the action test — the
 * exact split PicksHomeScreen's finishedItems makes.
 */
export function gamePicks<T extends { pick: { game_id: string; result?: string | null } }>(
  gameId: string,
  open: T[],
  finished: T[],
  tests: {
    action: (item: T) => boolean;
    record: (item: T) => boolean;
  },
): T[] {
  const out: T[] = [];
  const seen = new Set<T>();
  for (const d of open) {
    if (d.pick.game_id !== gameId || seen.has(d)) continue;
    if (tests.action(d)) {
      out.push(d);
      seen.add(d);
    }
  }
  for (const d of finished) {
    if (d.pick.game_id !== gameId || seen.has(d)) continue;
    const r = d.pick.result;
    const graded = r === 'WIN' || r === 'LOSS' || r === 'PUSH';
    if (graded ? tests.record(d) : tests.action(d)) {
      out.push(d);
      seen.add(d);
    }
  }
  return out;
}

// ── The under ───────────────────────────────────────────────────────────────

/** The fields of an all-books odds row the under shop reads. */
export interface TotalRowLike {
  game_id: string;
  market: string;
  bookmaker: string;
  total_line: number | string | null;
  under_price: number | string | null;
}

function num(v: number | string | null | undefined): number | null {
  if (v == null) return null;
  const n = typeof v === 'string' ? Number(v) : v;
  return Number.isFinite(n) ? n : null;
}

/**
 * The best UNDER price among the member's books, at the same number the over
 * cell anchors to: the first of `books` (in the member's order) that posts a
 * total for this game. A better price at another number is a different bet
 * (docs/best_line.md §5), so only books on the anchor compete — the rule
 * lib/statsOdds buildTeamLineIndex applies to the over. Null when none of the
 * member's books posts the total.
 */
export function bestUnder<R extends TotalRowLike>(
  rows: R[],
  gameId: string,
  books: readonly string[],
): { row: R; price: number; line: number } | null {
  const rank = new Map(books.map((b, i) => [b, i] as const));
  const mine = rows
    .filter((r) => r.game_id === gameId && r.market === 'totals' && rank.has(r.bookmaker) && num(r.total_line) != null)
    .sort((a, b) => (rank.get(a.bookmaker) ?? 0) - (rank.get(b.bookmaker) ?? 0));
  if (mine.length === 0) return null;
  const line = num(mine[0].total_line)!;
  let best: { row: R; price: number; line: number } | null = null;
  for (const r of mine) {
    if (Math.abs((num(r.total_line) ?? NaN) - line) > 1e-9) continue;
    const p = num(r.under_price);
    if (p == null) continue;
    if (best == null || betterAmerican(p, best.price)) best = { row: r, price: p, line };
  }
  return best;
}

/** True when American price `a` pays more than `b` (+120 beats −110 beats −130). */
export function betterAmerican(a: number, b: number): boolean {
  const payout = (p: number) => (p > 0 ? p / 100 : 100 / Math.abs(p));
  return payout(a) > payout(b);
}

// ── Injuries ────────────────────────────────────────────────────────────────

const STATUS_ORDER = ['out', 'doubtful', 'questionable', 'probable', 'day-to-day'];

/** One team's injury rows, worst status first, then by name. */
export function teamInjuries<T extends { team: string; status: string | null; player_name: string | null }>(
  rows: T[],
  team: string,
): T[] {
  const rank = (s: string | null) => {
    const i = STATUS_ORDER.indexOf((s ?? '').toLowerCase());
    return i < 0 ? STATUS_ORDER.length : i;
  };
  return rows
    .filter((r) => r.team === team)
    .sort((a, b) => rank(a.status) - rank(b.status) || (a.player_name ?? '').localeCompare(b.player_name ?? ''));
}
