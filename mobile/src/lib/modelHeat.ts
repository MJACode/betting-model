/**
 * Each model's published record, and whether it is HOT or COLD — for the
 * Model section of the Picks filter sheet (Matt, 2026-11-18).
 *
 *   - The number on the row is the model's TOTAL published record: units and
 *     settled bets since the record started (v_public_track_record, the same
 *     rows the Record tab and Discord #results sum).
 *   - HOT / COLD reads the last 7 days, ending yesterday ET
 *     (v_public_track_record_model_daily): up or down at least
 *     HEAT_MIN_UNITS on at least HEAT_MIN_BETS settled bets. Anything else
 *     carries no tag — one bad night is not a cold streak.
 *
 * Pure: the hook (useModelFilterRecords) fetches, this decides.
 */

export const HEAT_WINDOW_DAYS = 7;
export const HEAT_MIN_UNITS = 3;
export const HEAT_MIN_BETS = 8;

export type ModelHeat = 'hot' | 'cold' | null;

export interface ModelRecordSummary {
  /** Settled bets in the whole published record. */
  bets: number;
  /** Units on the posted stake, whole published record. */
  units: number;
  /** Settled bets and units in the heat window. */
  windowBets: number;
  windowUnits: number;
  heat: ModelHeat;
}

export interface ModelTotalRow {
  model_id: string;
  picks: number | string | null;
  units?: number | string | null;
}

export interface ModelDailyRow {
  game_date: string;
  model_id: string;
  picks: number | string | null;
  units?: number | string | null;
}

/** 'YYYY-MM-DD' plus n days (n may be negative). Calendar arithmetic only. */
export function addDays(date: string, n: number): string {
  const [y, m, d] = date.split('-').map(Number);
  const t = new Date(Date.UTC(y, m - 1, d + n, 12));
  return t.toISOString().slice(0, 10);
}

/** The heat window for a given ET "today": [first, last], both inclusive. */
export function heatWindow(today: string): { first: string; last: string } {
  return { first: addDays(today, -HEAT_WINDOW_DAYS), last: addDays(today, -1) };
}

export function heatFor(windowBets: number, windowUnits: number): ModelHeat {
  if (windowBets < HEAT_MIN_BETS) return null;
  if (windowUnits >= HEAT_MIN_UNITS) return 'hot';
  if (windowUnits <= -HEAT_MIN_UNITS) return 'cold';
  return null;
}

/**
 * One summary per model. A model can have several total rows (one per sport
 * it was scored under); they are summed. Daily rows outside the window are
 * ignored, so the caller may pass a wider read.
 */
export function buildModelRecords(
  totals: ModelTotalRow[],
  daily: ModelDailyRow[],
  today: string,
): Record<string, ModelRecordSummary> {
  const out: Record<string, ModelRecordSummary> = {};
  const get = (id: string) =>
    (out[id] ??= { bets: 0, units: 0, windowBets: 0, windowUnits: 0, heat: null });
  for (const r of totals) {
    const s = get(r.model_id);
    s.bets += Number(r.picks ?? 0);
    s.units += Number(r.units ?? 0);
  }
  const { first, last } = heatWindow(today);
  for (const r of daily) {
    if (r.game_date < first || r.game_date > last) continue;
    const s = get(r.model_id);
    s.windowBets += Number(r.picks ?? 0);
    s.windowUnits += Number(r.units ?? 0);
  }
  for (const s of Object.values(out)) s.heat = heatFor(s.windowBets, s.windowUnits);
  return out;
}

/** "+4.2u · 61 bets". No bets yet reads as such, never "+0.0u". */
export function modelRecordLine(r: ModelRecordSummary | undefined): string {
  if (!r || r.bets === 0) return 'No settled bets yet';
  const u = Math.round(r.units * 10) / 10;
  const sign = u > 0 ? '+' : u < 0 ? '−' : '';
  return `${sign}${Math.abs(u).toFixed(1)}u · ${r.bets} bet${r.bets === 1 ? '' : 's'}`;
}

/** Spoken form of modelRecordLine and the tag. */
export function modelRecordSpoken(r: ModelRecordSummary | undefined): string {
  if (!r || r.bets === 0) return 'no settled bets yet';
  const u = Math.round(r.units * 10) / 10;
  const dir = u > 0 ? 'up' : u < 0 ? 'down' : 'even,';
  const amt = u === 0 ? '' : ` ${Math.abs(u).toFixed(1)} units`;
  const tag =
    r.heat === 'hot' ? ', hot over the last 7 days' : r.heat === 'cold' ? ', cold over the last 7 days' : '';
  return `${dir}${amt} over ${r.bets} bet${r.bets === 1 ? '' : 's'}${tag}`;
}
