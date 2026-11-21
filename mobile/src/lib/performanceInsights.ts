/**
 * The Performance tab's Insights card: recaps by period, best and worst bet,
 * where the units come from, favourites vs underdogs, closing-line value,
 * streaks, the units line, and the member against the models they follow
 * (Matt, 2026-11-21).
 *
 * Pure on purpose: no value imports, so a node test loads it with type
 * stripping (mobile/scripts/verify_performance_insights.ts). The adapter that
 * turns tracked picks and logged bets into `InsightBet`s lives in
 * performanceInsightsInput.ts, because it needs the market helpers.
 *
 * Every amount is at the 100-is-1u scale (lib/format FLAT_UNIT), the scale
 * the tracked and logged bets already carry. Print with formatFlatUnits.
 *
 * Decisions this encodes (Matt, 2026-11-21):
 *  - A week is Monday to Sunday, a month and a year are calendar ones, all in
 *    ET, keyed on the game date (a logged bet: the ET day it was placed).
 *  - Insights are scored at "My stakes": the member's own stake where they set
 *    one, the posted stake everywhere else.
 *  - Logged bets fold into the recap. They carry no sport, market or CLV, so
 *    they sit out of those breakdowns, never in an invented bucket.
 *  - Every group is shown, however few bets, with its count beside it.
 */

export type InsightPeriod = 'day' | 'week' | 'month' | 'year' | 'all';

export type InsightStatus = 'open' | 'won' | 'lost' | 'push';

export interface InsightBet {
  key: string;
  /** ET calendar day, YYYY-MM-DD. */
  date: string;
  /** Tie-break inside a day, for streak order (ISO; may be ''). */
  stamp: string;
  /** The pick's own label, as every surface quotes it. */
  title: string;
  status: InsightStatus;
  /** Won or lost, 100-is-1u. 0 for open and push. */
  profit: number;
  /** Risked on a decided bet (won or lost), 100-is-1u. 0 otherwise. */
  risked: number;
  /** American price taken, or null. */
  odds: number | null;
  sport: string | null;
  betType: string | null;
  book: string | null;
  modelId: string | null;
  /** Same-book CLV in percent (picks.clv_pct), or null when unmeasured. */
  clvPct: number | null;
  source: 'tracked' | 'logged';
}

export interface InsightRecord {
  net: number;
  wins: number;
  losses: number;
  pushes: number;
  open: number;
  /** Bets in the window, open included. */
  bets: number;
  risked: number;
  /** net / risked; null until something decided for a non-zero stake. */
  roi: number | null;
}

export interface InsightGroup extends InsightRecord {
  label: string;
}

export interface InsightWindow {
  /** Inclusive ET bounds; null on 'all'. */
  from: string | null;
  to: string | null;
}

export interface InsightStreak {
  /** 'W' or 'L'; null when nothing has been decided. */
  kind: 'W' | 'L' | null;
  length: number;
  /** The last up-to-10 decided bets, newest last. */
  last10Wins: number;
  last10Losses: number;
}

export interface InsightClv {
  /** Bets that beat, trailed or matched the close. */
  beats: number;
  losses: number;
  pushes: number;
  /** beats / (beats + losses); null with nothing decisive. */
  beatRate: number | null;
  /** Mean clv_pct across every measured bet, pushes included. */
  avgPct: number | null;
}

export interface CurvePoint {
  date: string;
  /** Running net through this date, 100-is-1u. */
  cum: number;
}

export interface PeriodInsights {
  period: InsightPeriod;
  window: InsightWindow;
  record: InsightRecord;
  /** The same days of the window before this one; null on 'all'. */
  previous: InsightRecord | null;
  best: InsightBet | null;
  worst: InsightBet | null;
  bySport: InsightGroup[];
  byBetType: InsightGroup[];
  byBook: InsightGroup[];
  byPrice: InsightGroup[];
  clv: InsightClv;
  curve: CurvePoint[];
}

// ── Dates (pure string math on YYYY-MM-DD, no clock, no time zone) ───────────

function parts(d: string): [number, number, number] {
  const [y, m, day] = d.split('-').map(Number);
  return [y, m, day];
}

const pad = (n: number) => String(n).padStart(2, '0');

/** A calendar date from parts that may overflow (day 0 is the last of the month before). */
function iso(y: number, m: number, d: number): string {
  const dt = new Date(Date.UTC(y, m - 1, d));
  return `${dt.getUTCFullYear()}-${pad(dt.getUTCMonth() + 1)}-${pad(dt.getUTCDate())}`;
}

function dayNumber(d: string): number {
  const [y, m, day] = parts(d);
  return Math.round(Date.UTC(y, m - 1, day) / 86_400_000);
}

export function shiftDays(d: string, n: number): string {
  const [y, m, day] = parts(d);
  return iso(y, m, day + n);
}

/** 0 = Monday … 6 = Sunday. */
function mondayIndex(d: string): number {
  const [y, m, day] = parts(d);
  return (new Date(Date.UTC(y, m - 1, day)).getUTCDay() + 6) % 7;
}

/**
 * The window holding `today` for a period, and the SAME DAYS of the one
 * before it: Monday to Wednesday against last Monday to Wednesday, the 1st to
 * the 19th against last month's 1st to 19th, so an unfinished week is not
 * read as a drop (UX review, 2026-11-21). `current` runs to the period's end,
 * so a game later this week already counts as this week's open bet.
 */
export function periodWindows(
  period: InsightPeriod,
  today: string,
): { current: InsightWindow; previous: InsightWindow | null } {
  const full = fullPeriodWindows(period, today);
  const { current, previous } = full;
  if (!previous || !previous.from || !previous.to || !current.from || period === 'day') return full;
  const elapsed = Math.max(0, dayNumber(today) - dayNumber(current.from));
  const sameDaysEnd = shiftDays(previous.from, elapsed);
  return { current, previous: { from: previous.from, to: sameDaysEnd < previous.to ? sameDaysEnd : previous.to } };
}

function fullPeriodWindows(
  period: InsightPeriod,
  today: string,
): { current: InsightWindow; previous: InsightWindow | null } {
  const [y, m] = parts(today);
  switch (period) {
    case 'day':
      return {
        current: { from: today, to: today },
        previous: { from: shiftDays(today, -1), to: shiftDays(today, -1) },
      };
    case 'week': {
      const mon = shiftDays(today, -mondayIndex(today));
      return {
        current: { from: mon, to: shiftDays(mon, 6) },
        previous: { from: shiftDays(mon, -7), to: shiftDays(mon, -1) },
      };
    }
    case 'month':
      return {
        current: { from: iso(y, m, 1), to: iso(y, m + 1, 0) },
        previous: { from: iso(y, m - 1, 1), to: iso(y, m, 0) },
      };
    case 'year':
      return {
        current: { from: iso(y, 1, 1), to: iso(y, 12, 31) },
        previous: { from: iso(y - 1, 1, 1), to: iso(y - 1, 12, 31) },
      };
    default:
      return { current: { from: null, to: null }, previous: null };
  }
}

export function inWindow(date: string, w: InsightWindow): boolean {
  if (w.from != null && date < w.from) return false;
  if (w.to != null && date > w.to) return false;
  return true;
}

// ── Records ─────────────────────────────────────────────────────────────────

const cents = (n: number) => Math.round(n * 100) / 100;

export function recordOf(bets: InsightBet[]): InsightRecord {
  let net = 0;
  let risked = 0;
  let wins = 0;
  let losses = 0;
  let pushes = 0;
  let open = 0;
  for (const b of bets) {
    if (b.status === 'won') wins++;
    else if (b.status === 'lost') losses++;
    else if (b.status === 'push') pushes++;
    else open++;
    if (b.status === 'won' || b.status === 'lost') {
      net += b.profit;
      risked += b.risked;
    }
  }
  return {
    net: cents(net),
    wins,
    losses,
    pushes,
    open,
    bets: bets.length,
    risked: cents(risked),
    roi: risked > 0 ? net / risked : null,
  };
}

/** Settled groups, best net first; ties by more bets, then by name. */
export function groupBy(bets: InsightBet[], keyOf: (b: InsightBet) => string | null): InsightGroup[] {
  const by = new Map<string, InsightBet[]>();
  for (const b of bets) {
    if (b.status === 'open') continue;
    const k = keyOf(b);
    if (!k) continue;
    const list = by.get(k);
    if (list) list.push(b);
    else by.set(k, [b]);
  }
  return [...by.entries()]
    .map(([label, list]) => ({ label, ...recordOf(list) }))
    .sort((a, b) => b.net - a.net || b.bets - a.bets || a.label.localeCompare(b.label));
}

/** The price bands, in the order the card lists them when tied. */
export const PRICE_BANDS = ['Heavy favorite (−200 or shorter)', 'Favorite (−199 to −101)', 'Even or underdog (−100 and up)'] as const;

export function priceBand(odds: number | null): string | null {
  if (odds == null || !Number.isFinite(odds) || odds === 0) return null;
  if (odds <= -200) return PRICE_BANDS[0];
  if (odds < -100) return PRICE_BANDS[1];
  return PRICE_BANDS[2];
}

/** Within ±0.005 percent of the price taken is a matched close (lib/clvBeat). */
const CLV_PUSH_EPS = 0.005;

export function clvOf(bets: InsightBet[]): InsightClv {
  let beats = 0;
  let losses = 0;
  let pushes = 0;
  let sum = 0;
  let n = 0;
  for (const b of bets) {
    if (b.status === 'open' || b.clvPct == null || !Number.isFinite(b.clvPct)) continue;
    n++;
    sum += b.clvPct;
    if (Math.abs(b.clvPct) < CLV_PUSH_EPS) pushes++;
    else if (b.clvPct > 0) beats++;
    else losses++;
  }
  const decisive = beats + losses;
  return {
    beats,
    losses,
    pushes,
    beatRate: decisive > 0 ? beats / decisive : null,
    avgPct: n > 0 ? sum / n : null,
  };
}

function byTime(a: InsightBet, b: InsightBet): number {
  return a.date.localeCompare(b.date) || a.stamp.localeCompare(b.stamp) || a.key.localeCompare(b.key);
}

/** Running net by day across the window's decided bets. */
export function curveOf(bets: InsightBet[]): CurvePoint[] {
  const byDay = new Map<string, number>();
  for (const b of bets) {
    if (b.status !== 'won' && b.status !== 'lost') continue;
    byDay.set(b.date, (byDay.get(b.date) ?? 0) + b.profit);
  }
  let cum = 0;
  return [...byDay.keys()].sort().map((date) => {
    cum += byDay.get(date) ?? 0;
    return { date, cum: cents(cum) };
  });
}

/** Current streak and last-10 across every decided bet. A push breaks nothing. */
export function streakOf(bets: InsightBet[]): InsightStreak {
  const decided = bets.filter((b) => b.status === 'won' || b.status === 'lost').sort(byTime);
  let kind: 'W' | 'L' | null = null;
  let length = 0;
  for (let i = decided.length - 1; i >= 0; i--) {
    const k = decided[i].status === 'won' ? 'W' : 'L';
    if (kind == null) kind = k;
    if (k !== kind) break;
    length++;
  }
  const last = decided.slice(-10);
  return {
    kind,
    length,
    last10Wins: last.filter((b) => b.status === 'won').length,
    last10Losses: last.filter((b) => b.status === 'lost').length,
  };
}

export function periodInsights(bets: InsightBet[], period: InsightPeriod, today: string): PeriodInsights {
  const { current, previous } = periodWindows(period, today);
  const inCur = bets.filter((b) => inWindow(b.date, current));
  const won = inCur.filter((b) => b.status === 'won').sort((a, b) => b.profit - a.profit || byTime(b, a));
  const lost = inCur.filter((b) => b.status === 'lost').sort((a, b) => a.profit - b.profit || byTime(b, a));
  return {
    period,
    window: current,
    record: recordOf(inCur),
    previous: previous ? recordOf(bets.filter((b) => inWindow(b.date, previous))) : null,
    best: won[0] ?? null,
    worst: lost[0] ?? null,
    bySport: groupBy(inCur, (b) => b.sport),
    byBetType: groupBy(inCur, (b) => b.betType),
    byBook: groupBy(inCur, (b) => b.book),
    byPrice: groupBy(inCur, (b) => priceBand(b.odds)),
    clv: clvOf(inCur),
    curve: curveOf(inCur),
  };
}

// ── You vs the models you follow ────────────────────────────────────────────

/** One row of v_public_track_record_model_daily, units in 1u (not 100-is-1u). */
export interface ModelDayRecord {
  game_date: string;
  model_id: string;
  wins: number;
  losses: number;
  pushes: number;
  units: number;
  risked: number;
}

export interface VersusModels {
  /** Model ids the member tracked a decided pick from in the window. */
  models: string[];
  you: InsightRecord;
  /** The same models' whole posted record over the same window, 100-is-1u. */
  models_record: InsightRecord;
}

/**
 * The member's tracked picks against every posted pick from the same models
 * over the same window. Logged bets have no model, so they sit out. ROI is the
 * comparable number: the member's stakes and the posted stakes differ.
 */
export function versusModels(
  bets: InsightBet[],
  daily: ModelDayRecord[],
  window: InsightWindow,
  unit = 100,
): VersusModels | null {
  const mine = bets.filter(
    (b) => b.source === 'tracked' && b.modelId && (b.status === 'won' || b.status === 'lost' || b.status === 'push') && inWindow(b.date, window),
  );
  if (mine.length === 0) return null;
  const models = [...new Set(mine.map((b) => b.modelId as string))].sort();
  const set = new Set(models);
  let wins = 0;
  let losses = 0;
  let pushes = 0;
  let net = 0;
  let risked = 0;
  for (const r of daily) {
    if (!set.has(r.model_id) || !inWindow(r.game_date, window)) continue;
    wins += Number(r.wins) || 0;
    losses += Number(r.losses) || 0;
    pushes += Number(r.pushes) || 0;
    net += (Number(r.units) || 0) * unit;
    risked += (Number(r.risked) || 0) * unit;
  }
  return {
    models,
    you: recordOf(mine),
    models_record: {
      net: cents(net),
      wins,
      losses,
      pushes,
      open: 0,
      bets: wins + losses + pushes,
      risked: cents(risked),
      roi: risked > 0 ? net / risked : null,
    },
  };
}
